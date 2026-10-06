"""Real local outbox orchestration with fake receipt and comparison transports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from threading import Event
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
from fpvs_studio.data_sharing.client import DataSharingClient
from fpvs_studio.data_sharing.errors import DataSharingError
from fpvs_studio.data_sharing.service import (
    archive_project,
    disconnect_project,
    enroll_project,
    load_view,
    set_sharing_enabled,
    sync_project,
)
from fpvs_studio.data_sharing.storage import (
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


def library_origin(root, *, item_id="study", version="1.0"):
    save_library_origin(root, LibraryProjectOrigin(
        service_url="https://library.example.invalid", item_id=item_id,
        installed_version=version, local_project_id="local-study",
    ))


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
    tmp_path, item_id, version,
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
    tmp_path, unknown_version,
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
    assert calls == [ORIGIN + "/v1/enroll"]
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
