"""Real local outbox orchestration with fake receipt and comparison transports."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from threading import Event
from unittest.mock import Mock
from uuid import uuid4

import pytest
from tests.unit.test_data_sharing_client import (
    HASH,
    ORIGIN,
    Store,
    credential,
    profile,
    receipt_bytes,
    report,
)

from fpvs_studio.core.data_sharing import SharingSettings
from fpvs_studio.core.library_origin import LibraryProjectOrigin, save_library_origin
from fpvs_studio.core.serialization import save_project_file
from fpvs_studio.data_sharing.client import DataSharingClient
from fpvs_studio.data_sharing.errors import DataSharingError
from fpvs_studio.data_sharing.service import (
    archive_project,
    disconnect_project,
    enroll_project,
    load_view,
    set_sharing_enabled,
    sync_project,
    sync_startup_project,
)
from fpvs_studio.data_sharing.storage import (
    SharingStorageError,
    list_records,
    load_settings,
    queue_report,
    save_settings,
    update_record,
)


def client(transport, store=None):
    saved = store or Store(credential())
    return DataSharingClient(ORIGIN, transport=transport, store_factory=lambda *_: saved)


def empty_comparison():
    return json.dumps(
        {
            "schema_version": "1.0",
            "experiment_id": "study",
            "experiment_version": "1.0",
            "protocol_sha256": HASH,
            "minimum_sessions": 10,
            "minimum_devices": 3,
            "conditions": [],
            "generated_at": "2026-10-05T12:00:00Z",
        }
    ).encode()


def enable(root):
    save_settings(root, SharingSettings(enabled=True, profile=profile()))


@pytest.mark.timeout(600)
def test_1500_acknowledged_sessions_retire_exact_history_and_keep_latest(tmp_path):
    from pathlib import Path
    from tempfile import gettempdir

    from tests.unit.test_data_sharing_storage import _capture

    # Keep this volume fixture within pytest's isolated root but below Windows'
    # legacy path length. Dedicated storage/path tests cover extended namespaces.
    tmp_path = Path(gettempdir()) / "report-volume"
    tmp_path.mkdir()
    enable(tmp_path)
    research = tmp_path / "runs" / "research.csv"
    research.parent.mkdir()
    research.write_bytes(b"original participant data")
    accepted = {}

    def transport(method, url, body, headers, cancel):
        assert url.endswith("/reports")  # Delivery-only never asks for a comparison.
        key = json.loads(body)["report_id"]
        assert key not in accepted
        accepted[key] = body
        return receipt_bytes(body)

    backend = client(transport)
    base = report()
    for index in range(1500):
        current = base.model_copy(update={
            "report_id": str(uuid4()),
            "completed_at": base.completed_at + timedelta(seconds=index),
        })
        queue_report(tmp_path, current)
        _capture(tmp_path, current)
        view = sync_project(tmp_path, HASH, Event(), client=backend, fetch_comparison=False)
        assert view.uploaded_count == 1 and view.pending_count == 0 and not view.error
    assert len(accepted) == 1500
    assert list_records(tmp_path)[0].report_id == current.report_id
    assert view.latest_completed_at == current.completed_at.isoformat()
    archive = tmp_path / "logs/data-sharing/archive"
    assert len(list(archive.iterdir())) == 1499
    for folder in archive.iterdir():
        receipt_record = json.loads((folder / "report.json").read_text())
        assert receipt_record["payload_json"].encode() == accepted[folder.name]
        assert receipt_record["state"] == "uploaded" and receipt_record["receipt"]
        capture = json.loads((folder / "capture.json").read_text())
        assert capture["state"] == "finalized" and capture["report_id"] == folder.name
    assert len(list((tmp_path / "logs/data-sharing/intents").iterdir())) == 1
    assert research.read_bytes() == b"original participant data"


@pytest.mark.parametrize("move", ["intents", "outbox"])
def test_automatic_cleanup_failure_preserves_receipts_and_resumes(tmp_path, monkeypatch, move):
    from pathlib import Path

    from tests.unit.test_data_sharing_storage import _capture

    enable(tmp_path)
    first, second = report(), report()
    queue_report(tmp_path, first)
    _capture(tmp_path, first)
    backend = client(lambda method, url, body, *_: receipt_bytes(body))
    sync_project(tmp_path, HASH, Event(), client=backend, fetch_comparison=False)
    queue_report(tmp_path, second)
    _capture(tmp_path, second)
    original = Path.rename

    def fail_move(source, target):
        if source.parent.name == move:
            raise PermissionError("Synthetic archive failure")
        return original(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "rename", fail_move)
        result = sync_project(tmp_path, HASH, Event(), client=backend, fetch_comparison=False)
    assert "cleanup needs attention" in result.error
    assert result.status == "uploaded" and result.uploaded_count == 2
    assert all(record.receipt and record.state == "uploaded" for record in list_records(tmp_path))
    sends = []
    result = sync_project(tmp_path, HASH, Event(),
                          client=client(lambda *args: sends.append(args)), fetch_comparison=False)
    assert not sends and not result.error and result.uploaded_count == 1


def test_receipt_write_failure_retries_original_identity_without_duplicate(tmp_path, monkeypatch):
    import fpvs_studio.data_sharing.storage as storage

    enable(tmp_path)
    queued = queue_report(tmp_path, report())
    server, attempts = {}, []

    def transport(method, url, body, *_args):
        attempts.append(body)
        server.setdefault(json.loads(body)["report_id"], body)
        return receipt_bytes(body)

    backend = client(transport)
    original = storage._save_record

    def fail_receipt(root, record):
        if record.state == "uploaded":
            raise SharingStorageError("Synthetic receipt write failure")
        original(root, record)

    with monkeypatch.context() as patch:
        patch.setattr(storage, "_save_record", fail_receipt)
        with pytest.raises(SharingStorageError, match="receipt write"):
            sync_project(tmp_path, HASH, Event(), client=backend, fetch_comparison=False)
    assert list_records(tmp_path)[0].state == "pending"
    result = sync_project(tmp_path, HASH, Event(), client=backend, fetch_comparison=False)
    assert result.uploaded_count == 1 and len(server) == 1
    assert attempts == [queued.payload_json.encode()] * 2


def test_startup_retires_old_full_history_before_recovery(tmp_path, sample_project, monkeypatch):
    from tests.unit.test_data_sharing_storage import _capture, _upload

    import fpvs_studio.data_sharing.service as service
    import fpvs_studio.data_sharing.storage as storage
    import fpvs_studio.runtime.data_sharing as capture_runtime

    save_project_file(sample_project, tmp_path / "project.json")
    enable(tmp_path)
    monkeypatch.setattr(storage, "MAX_RECORDS", 3)
    monkeypatch.setattr(service, "protocol_fingerprint", lambda *_args, **_kwargs: HASH)
    for _ in range(2):
        old = report()
        _upload(tmp_path, old)
        _capture(tmp_path, old)
    pending = queue_report(tmp_path, report())
    original = capture_runtime.recover_captures
    recovered = []

    def recover(root):
        assert len(list_records(root)) == 2  # Startup retired pre-change history first.
        recovered.append(root)
        return original(root)

    monkeypatch.setattr(capture_runtime, "recover_captures", recover)
    result = sync_startup_project(tmp_path, Event(),
                                 client=client(lambda method, url, body, *_: receipt_bytes(body)))
    assert recovered == [tmp_path]
    assert result.uploaded_count == 1 and list_records(tmp_path)[0].report_id == pending.report_id


@pytest.mark.parametrize("code", ["network", "timeout", "throttled", "unavailable"])
def test_startup_retry_only_bypasses_connectivity_delay(
    tmp_path, monkeypatch, sample_project, code,
):
    import fpvs_studio.data_sharing.service as service

    save_project_file(sample_project, tmp_path / "project.json")
    monkeypatch.setattr(service, "protocol_fingerprint", lambda *_args, **_kwargs: HASH)
    enable(tmp_path)
    queued = queue_report(tmp_path, report())
    deferred = queued.model_copy(update={
        "last_error_code": code,
        "next_attempt_at": datetime.now(timezone.utc) + timedelta(hours=1),
    })
    update_record(tmp_path, deferred)
    sends = []

    def transport(method, url, body, *_):
        sends.append(body)
        return receipt_bytes(body)

    result = sync_startup_project(tmp_path, Event(), client=client(transport))
    if code in {"network", "timeout"}:
        assert sends == [queued.payload_json.encode()]
        assert result.uploaded_count == 1
    else:
        assert not sends and list_records(tmp_path)[0] == deferred


def test_offline_exit_and_connected_startup_preserve_two_machine_reports(
    tmp_path, monkeypatch, sample_project,
):
    import fpvs_studio.data_sharing.service as service

    monkeypatch.setattr(service, "protocol_fingerprint", lambda *_args, **_kwargs: HASH)
    server = {}
    for machine in ("pc1", "pc2"):
        root = tmp_path / machine
        root.mkdir()
        save_project_file(sample_project, root / "project.json")
        enable(root)
        queued = queue_report(root, report())

        def offline(*args):
            raise DataSharingError("Connection unavailable", code="network", retryable=True)

        view = sync_project(root, HASH, Event(), client=client(offline), fetch_comparison=False)
        assert view.status == "waiting_connection" and view.pending_count == 1
        assert list_records(root)[0].last_error_code == "network"

        # A new client/process uses only persisted state; no project is reopened.
        def connected(method, url, body, *_):
            assert url.endswith("/reports")
            server[json.loads(body)["report_id"]] = body
            return receipt_bytes(body)

        view = sync_startup_project(root, Event(), client=client(connected))
        assert view.uploaded_count == 1 and view.pending_count == 0
        assert server[queued.report_id] == queued.payload_json.encode()
    assert len(server) == 2


@pytest.mark.parametrize("state", ["off", "held", "failed", "protocol", "credentials"])
def test_startup_never_releases_or_sends_unapproved_work(
    tmp_path, monkeypatch, sample_project, state,
):
    import fpvs_studio.data_sharing.service as service

    save_project_file(sample_project, tmp_path / "project.json")
    monkeypatch.setattr(service, "protocol_fingerprint",
                        lambda *_args, **_kwargs: "b" * 64 if state == "protocol" else HASH)
    enable(tmp_path)
    queued = queue_report(tmp_path, report())
    if state == "off":
        save_settings(tmp_path, load_settings(tmp_path).model_copy(update={"enabled": False}))
    elif state in {"held", "failed"}:
        update_record(tmp_path, queued.model_copy(update={"state": state}))
    calls = []
    view = sync_startup_project(tmp_path, Event(),
                               client=client(lambda *args: calls.append(args), Store()))
    assert not calls and view.uploaded_count == 0
    if state == "protocol":
        assert view.status == "protocol_mismatch"
    if state == "credentials":
        assert view.status == "failed" and view.error
    assert len(list_records(tmp_path)) == 1


def test_storage_budget_status_survives_restart_and_waits_for_explicit_retry(
    tmp_path, sample_project, monkeypatch,
):
    import fpvs_studio.data_sharing.service as service

    save_project_file(sample_project, tmp_path / "project.json")
    monkeypatch.setattr(service, "protocol_fingerprint", lambda *_args, **_kwargs: HASH)
    enable(tmp_path)
    queue_report(tmp_path, report())

    def full(*args):
        raise DataSharingError("Project reporting budget reached", code="storage_limit")

    view = sync_startup_project(tmp_path, Event(), client=client(full))
    assert view.status == "failed" and list_records(tmp_path)[0].last_error_code == "storage_limit"
    assert list_records(tmp_path)[0].next_attempt_at is None
    calls = []
    view = sync_startup_project(tmp_path, Event(), client=client(lambda *args: calls.append(args)))
    assert not calls and "reporting budget" in view.error
    view = sync_project(tmp_path, HASH, Event(), release_held=True, fetch_comparison=False,
                        client=client(lambda method, url, body, *_: receipt_bytes(body)))
    assert view.uploaded_count == 1 and not view.error


def test_startup_missing_project_does_not_create_metadata(tmp_path):
    missing = tmp_path / "moved"
    assert sync_startup_project(missing, Event()) is None
    assert not missing.exists()


def test_another_project_with_same_protocol_never_sends_previous_project_reports(tmp_path):
    first, second = str(uuid4()), str(uuid4())
    previous = profile().model_copy(update={"project_id": first})
    save_settings(tmp_path, SharingSettings(enabled=True, profile=previous))
    queue_report(tmp_path, report(), project_id=first)
    current = previous.model_copy(update={"project_id": second})
    save_settings(tmp_path, SharingSettings(enabled=True, profile=current))
    calls = []

    def transport(method, url, body, headers, cancel):
        calls.append(url)
        assert url.endswith("/comparison")
        return empty_comparison()

    view = sync_project(tmp_path, HASH, Event(), client=client(transport), release_held=True)
    assert not view.local_conditions
    assert list_records(tmp_path)[0].state == "held"
    assert calls == [ORIGIN + "/results/v1/experiments/study/comparison"]


def library_origin(root, *, item_id="study", version="1.0"):
    save_library_origin(
        root,
        LibraryProjectOrigin(
            service_url="https://library.example.invalid",
            item_id=item_id,
            installed_version=version,
            local_project_id="local-study",
        ),
    )


def test_library_enrollment_sends_exact_installed_identity_without_opting_in(tmp_path):
    library_origin(tmp_path)
    bodies = []

    def transport(method, url, body, headers, cancel):
        bodies.append(json.loads(body))
        return profile().model_dump_json().encode()

    result = enroll_project(tmp_path, "code", HASH, Event(), client=client(transport, Store()))
    assert not result.settings.enabled
    assert bodies[0]["experiment_id"] == "study"
    assert bodies[0]["experiment_version"] == "1.0"


@pytest.mark.parametrize("item_id,version", [("another-study", "1.0"), ("study", "2.0")])
def test_same_protocol_wrong_library_scope_cannot_send_compare_or_enable(
    tmp_path,
    item_id,
    version,
):
    enable(tmp_path)
    queued = queue_report(tmp_path, report())
    library_origin(tmp_path, item_id=item_id, version=version)
    calls = []
    backend = client(lambda *args: calls.append(args))
    view = sync_project(tmp_path, HASH, Event(), release_held=True, client=backend)
    assert view.status == "protocol_mismatch"
    assert "different Library experiment or version" in view.error
    assert not view.local_conditions and view.remote is None and not calls
    assert list_records(tmp_path)[0] == queued
    with pytest.raises(DataSharingError, match="different Library experiment or version"):
        set_sharing_enabled(tmp_path, True, HASH, Event(), client=backend)
    with pytest.raises(DataSharingError):
        backend.submit(tmp_path, profile(), queued.payload_json.encode(), Event())
    with pytest.raises(DataSharingError):
        backend.comparison(tmp_path, profile(), Event())
    assert not calls
    disabled = set_sharing_enabled(tmp_path, False, HASH, Event(), client=backend)
    assert not disabled.settings.enabled and list_records(tmp_path)[0].state == "held"


@pytest.mark.parametrize("unknown_version", [True, False])
def test_unconfirmed_or_malformed_library_link_blocks_enrollment_before_credentials(
    tmp_path,
    unknown_version,
):
    library_origin(tmp_path, version=None if unknown_version else "1.0")
    if not unknown_version:
        (tmp_path / ".fpvs-library" / "project-origin.json").write_text("invalid")
    calls = []
    store = Store()
    backend = client(lambda *args: calls.append(args), store)
    with pytest.raises(DataSharingError):
        enroll_project(tmp_path, "code", HASH, Event(), client=backend)
    assert not calls and store.value is None
    assert load_settings(tmp_path).profile is None


def test_unrelated_enrollment_response_cannot_be_saved_for_a_library_project(tmp_path):
    library_origin(tmp_path)
    wrong_profile = profile().model_copy(update={"experiment_version": "2.0"})
    store = Store()
    backend = client(lambda *_: wrong_profile.model_dump_json().encode(), store)
    with pytest.raises(DataSharingError, match="different Library experiment or version"):
        enroll_project(tmp_path, "code", HASH, Event(), client=backend)
    assert load_settings(tmp_path).profile is None
    assert store.value is not None and store.value.connection is None


def test_enrollment_does_not_opt_in_or_submit_existing_history(tmp_path):
    calls = []

    def transport(method, url, body, headers, cancel):
        calls.append(url)
        return profile().model_dump_json().encode()

    result = enroll_project(tmp_path, "code", HASH, Event(), client=client(transport, Store()))
    assert not result.settings.enabled
    assert calls == [ORIGIN + "/results/v1/enroll"]
    assert list_records(tmp_path) == ()


def test_off_and_changed_protocol_cannot_send_or_compare(tmp_path):
    calls = []
    transport = client(lambda *args: calls.append(args))
    enable(tmp_path)
    queue_report(tmp_path, report())
    result = sync_project(tmp_path, "b" * 64, Event(), client=transport)
    assert result.status == "protocol_mismatch" and not calls
    set_sharing_enabled(tmp_path, False, HASH, Event(), client=transport)
    assert list_records(tmp_path)[0].state == "held"
    sync_project(tmp_path, HASH, Event(), client=transport)
    assert not calls


def test_ambiguous_delivery_retries_exact_bytes_and_verified_receipt(tmp_path):
    enable(tmp_path)
    queued = queue_report(tmp_path, report())
    payloads = []

    def transport(method, url, body, headers, cancel):
        if url.endswith("/comparison"):
            return empty_comparison()
        payloads.append(body)
        if len(payloads) == 1:
            raise DataSharingError("Synthetic lost acknowledgement", code="network", retryable=True)
        return receipt_bytes(body)

    backend = client(transport)
    first = sync_project(tmp_path, HASH, Event(), client=backend)
    assert first.pending_count == 1 and list_records(tmp_path)[0].state == "pending"
    second = sync_project(tmp_path, HASH, Event(), release_held=True, client=backend)
    assert second.uploaded_count == 1
    accepted = list_records(tmp_path)[0]
    assert accepted.receipt.report_id == queued.report_id
    assert accepted.attempt_count == 2 and payloads[0] == payloads[1]
    assert second.remote.status == "insufficient_cohort"


def test_reenable_does_not_release_old_optout_backlog(tmp_path):
    enable(tmp_path)
    queue_report(tmp_path, report())
    set_sharing_enabled(tmp_path, False, HASH, Event())
    set_sharing_enabled(tmp_path, True, HASH, Event())
    payloads = []

    def transport(method, url, body, headers, cancel):
        if url.endswith("/comparison"):
            return empty_comparison()
        payloads.append(body)
        return receipt_bytes(body)

    backend = client(transport)
    sync_project(tmp_path, HASH, Event(), client=backend)
    assert not payloads and list_records(tmp_path)[0].state == "held"
    sync_project(tmp_path, HASH, Event(), client=backend, release_held=True)
    assert len(payloads) == 1 and list_records(tmp_path)[0].state == "uploaded"


def test_inflight_optout_keeps_receipt_and_prevents_next_report(tmp_path):
    enable(tmp_path)
    for _ in range(2):
        queue_report(tmp_path, report())
    sends = []

    def transport(method, url, body, headers, cancel):
        sends.append(body)
        save_settings(tmp_path, load_settings(tmp_path).model_copy(update={"enabled": False}))
        return receipt_bytes(body)

    sync_project(tmp_path, HASH, Event(), client=client(transport))
    assert len(sends) == 1
    assert sorted(row.state for row in list_records(tmp_path)) == ["held", "uploaded"]


def test_local_comparison_is_latest_session_with_target_weighting(tmp_path):
    enable(tmp_path)
    base = report()
    old = base.model_copy(update={"completed_at": datetime(2026, 10, 4, tzinfo=timezone.utc)})
    queue_report(tmp_path, old)
    repeated = base.occurrences[0].model_copy(
        update={
            "occurrence_index": 2,
            "total_targets": 30,
            "hit_count": 15,
            "miss_count": 15,
            "accuracy_percent": 50.0,
            "rt_count": 15,
        }
    )
    newer = base.model_copy(
        update={"report_id": str(uuid4()), "occurrences": (base.occurrences[0], repeated)}
    )
    queue_report(tmp_path, newer)
    view = load_view(tmp_path, HASH, Event())
    row = view.local_conditions[0]
    assert row.fixation_targets == 40 and row.fixation_hits == 23
    assert row.accuracy_percent == 57.5 and row.session_count == 1


def test_protocol_mismatch_cannot_be_explicitly_enabled(tmp_path):
    save_settings(tmp_path, SharingSettings(profile=profile()))
    with pytest.raises(DataSharingError):
        set_sharing_enabled(tmp_path, True, "b" * 64, Event())
    assert not load_settings(tmp_path).enabled


@pytest.mark.parametrize("source, window", [("frames", 1000.0), ("timestamps", 900.0)])
def test_reference_metrics_suppressed_when_local_scoring_differs(tmp_path, source, window):
    enable(tmp_path)
    queue_report(tmp_path, report())
    response = json.loads(empty_comparison())
    response["conditions"] = [
        {
            "condition_id": "faces",
            "session_count": 10,
            "device_count": 3,
            "eligible": True,
            "total_targets": 100,
            "hit_count": 80,
            "accuracy_percent": 80.0,
            "mean_rt_ms": 350.0,
            "rt_count": 80,
            "scoring_source": source,
            "response_window_ms": window,
        }
    ]

    def transport(method, url, body, headers, cancel):
        return json.dumps(response).encode() if url.endswith("/comparison") else receipt_bytes(body)

    view = sync_project(tmp_path, HASH, Event(), client=client(transport))
    assert view.remote.status == "insufficient_cohort"
    reference = view.remote.conditions[0]
    assert not reference.eligible
    assert reference.fixation_targets is reference.fixation_hits is None
    assert reference.mean_rt_ms is reference.accuracy_percent is None
    assert (reference.session_count, reference.device_count) == (10, 3)
    assert view.local_conditions[0].accuracy_percent == 80.0


def test_revoked_enrollment_can_disconnect_and_reenroll_without_losing_reports(tmp_path):
    enable(tmp_path)
    queued = queue_report(tmp_path, report())
    store = Store(credential())
    calls = []

    def transport(method, url, body, headers, cancel):
        calls.append(method)
        if method == "DELETE":
            raise DataSharingError("Synthetic revoked token", code="authorization")
        return profile().model_dump_json().encode()

    backend = client(transport, store)
    disconnected = disconnect_project(tmp_path, HASH, Event(), client=backend)
    assert not disconnected.settings.enabled and disconnected.settings.profile is None
    assert "service access was already rejected" in disconnected.error
    assert store.value is None
    assert list_records(tmp_path)[0].report_id == queued.report_id
    assert list_records(tmp_path)[0].state == "held"
    reconnected = enroll_project(tmp_path, "new code", HASH, Event(), client=backend)
    assert reconnected.settings.profile == profile() and not reconnected.settings.enabled
    assert calls == ["DELETE", "POST"]


def test_copied_enrollment_with_no_os_credential_can_be_cleared_locally(tmp_path):
    enable(tmp_path)
    store = Store()
    calls = []
    backend = client(lambda *args: calls.append(args), store)
    result = disconnect_project(tmp_path, HASH, Event(), client=backend)
    assert result.settings.profile is None and not calls


def test_offline_disconnect_retains_disabled_enrollment_for_retry(tmp_path):
    enable(tmp_path)
    store = Store(credential())

    def transport(*args):
        raise DataSharingError("Synthetic offline service", code="network", retryable=True)

    with pytest.raises(DataSharingError):
        disconnect_project(tmp_path, HASH, Event(), client=client(transport, store))
    assert not load_settings(tmp_path).enabled
    assert load_settings(tmp_path).profile == profile() and store.value == credential()


def test_archive_service_uses_no_network_and_retains_latest_local_session(tmp_path):
    enable(tmp_path)
    latest = None
    for day in (4, 5):
        item = report().model_copy(
            update={"completed_at": datetime(2026, 10, day, tzinfo=timezone.utc)}
        )
        queued = queue_report(tmp_path, item)
        from fpvs_studio.core.data_sharing import DeliveryReceipt

        accepted = DeliveryReceipt.model_validate_json(receipt_bytes(queued.payload_json.encode()))
        update_record(
            tmp_path, queued.model_copy(update={"state": "uploaded", "receipt": accepted})
        )
        latest = item
    calls = []
    result = archive_project(
        tmp_path, HASH, Event(), client=client(lambda *args: calls.append(args))
    )
    assert not calls and result.uploaded_count == 1
    assert result.latest_completed_at == latest.completed_at.isoformat()
    assert "Archived 1" in result.error
    assert len(tuple((tmp_path / "logs/data-sharing/archive").glob("*/report.json"))) == 1


def test_default_512_capture_limit_is_visible_with_ordinary_aborted_history(tmp_path):
    from tests.unit.test_data_sharing_storage import _excluded_capture

    enable(tmp_path)
    for _ in range(512):
        _excluded_capture(tmp_path)
    view = load_view(tmp_path, HASH, Event())
    assert view.settings.enabled and view.status == "failed"
    assert view.capture_count == view.capture_limit == view.reviewable_capture_count == 512
    assert "full (512/512)" in view.error and "Review captures" in view.error


def test_capture_review_and_confirmed_archive_are_local_without_http(tmp_path, monkeypatch):
    from tests.unit.test_data_sharing_storage import _excluded_capture

    from fpvs_studio.data_sharing.service import archive_captures_project, review_captures_project

    enable(tmp_path)
    _excluded_capture(tmp_path)
    monkeypatch.setattr(
        DataSharingClient, "configured", Mock(side_effect=AssertionError("HTTP owner"))
    )
    review = review_captures_project(tmp_path, HASH, Event()).capture_review
    assert review is not None and len(review.captures) == 1
    view = archive_captures_project(tmp_path, HASH, Event(), review=review)
    assert view.capture_count == 0 and "Archived 1 reviewed excluded capture" in view.error
