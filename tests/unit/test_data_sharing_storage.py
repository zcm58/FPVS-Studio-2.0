"""Atomic outbox replay, opt-out, capacity and hostile path regressions."""

from datetime import datetime, timedelta, timezone
from threading import Event
from unittest.mock import Mock
from uuid import uuid4

import pytest
from tests.unit.test_data_sharing_models import report_fixture

from fpvs_studio.core.data_sharing import DeliveryReceipt, SharingProfile, SharingSettings
from fpvs_studio.data_sharing import storage


def enable(root):
    profile = SharingProfile(
        experiment_id="study",
        experiment_version="1.0",
        protocol_sha256="a" * 64,
        title="Study",
        device_id="device1",
    )
    settings = SharingSettings(enabled=True, profile=profile)
    storage.save_settings(root, settings)
    return settings


def test_queue_is_immutable_and_idempotent(tmp_path):
    enable(tmp_path)
    report = report_fixture()
    record = storage.queue_report(tmp_path, report)
    assert storage.queue_report(tmp_path, report) == record
    assert storage.read_payload(tmp_path, report.report_id) == report.model_dump_json().encode()
    with pytest.raises(storage.SharingStorageError, match="different immutable bytes"):
        storage.queue_report(tmp_path, report.model_copy(update={"studio_version": "4.0"}))
    assert len(storage.list_records(tmp_path)) == 1


def test_queue_project_scope_survives_reconnection_without_relabeling(tmp_path):
    settings = enable(tmp_path)
    first, second = str(uuid4()), str(uuid4())
    profile = settings.profile.model_copy(update={"project_id": first})
    storage.save_settings(tmp_path, settings.model_copy(update={"profile": profile}))
    report = report_fixture()
    original = storage.queue_report(tmp_path, report, project_id=first)
    assert original.state == "pending"
    profile = profile.model_copy(update={"project_id": second})
    storage.save_settings(tmp_path, settings.model_copy(update={"profile": profile}))
    storage.release_held(tmp_path)
    assert storage.list_records(tmp_path)[0].state == "held"
    with pytest.raises(storage.SharingStorageError, match="immutable"):
        storage.queue_report(tmp_path, report, project_id=second)
    with pytest.raises(storage.SharingStorageError, match="immutable"):
        storage.update_record(tmp_path, original.model_copy(update={"project_id": second}))
    assert storage.list_records(tmp_path)[0].project_id == first


def test_off_pauses_and_reenable_requires_explicit_backlog_release(tmp_path):
    settings = enable(tmp_path)
    report = report_fixture()
    storage.queue_report(tmp_path, report)
    storage.save_settings(tmp_path, settings.model_copy(update={"enabled": False}))
    assert not storage.list_pending(tmp_path)
    storage.save_settings(tmp_path, settings)
    assert not storage.list_pending(tmp_path)
    storage.release_held(tmp_path)
    assert storage.list_pending(tmp_path)[0].report_id == report.report_id


def test_corrupt_outbox_cannot_prevent_off_or_reopen_the_send_gate(tmp_path):
    settings = enable(tmp_path)
    record = storage.queue_report(tmp_path, report_fixture())
    path = storage._record_path(tmp_path, record.report_id)
    path.write_bytes(b"corrupt record")
    with pytest.raises(storage.SharingStorageError, match="malformed"):
        storage.save_settings(tmp_path, settings.model_copy(update={"enabled": False}))
    assert not storage.load_settings(tmp_path).enabled
    assert path.read_bytes() == b"corrupt record"
    with pytest.raises(storage.SharingStorageError, match="malformed"):
        storage.save_settings(tmp_path, settings)
    assert not storage.load_settings(tmp_path).enabled
    assert path.read_bytes() == b"corrupt record"
    path.write_text(record.model_dump_json(), encoding="utf-8")
    storage.save_settings(tmp_path, settings)
    assert storage.list_records(tmp_path)[0].state == "held"
    assert not storage.list_pending(tmp_path)


def test_failed_backlog_pause_cannot_reenable_sharing(tmp_path, monkeypatch):
    settings = enable(tmp_path)
    record = storage.queue_report(tmp_path, report_fixture())
    original = storage._save_record
    monkeypatch.setattr(storage, "_save_record", Mock(side_effect=PermissionError("pause")))
    with pytest.raises(PermissionError, match="pause"):
        storage.save_settings(tmp_path, settings.model_copy(update={"enabled": False}))
    assert not storage.load_settings(tmp_path).enabled
    with pytest.raises(PermissionError, match="pause"):
        storage.save_settings(tmp_path, settings)
    assert not storage.load_settings(tmp_path).enabled
    assert storage.list_records(tmp_path) == (record,)
    monkeypatch.setattr(storage, "_save_record", original)
    storage.save_settings(tmp_path, settings)
    assert storage.list_records(tmp_path)[0].state == "held"


def test_inflight_receipt_survives_optout(tmp_path):
    settings = enable(tmp_path)
    record = storage.queue_report(tmp_path, report_fixture())
    storage.save_settings(tmp_path, settings.model_copy(update={"enabled": False}))
    receipt = DeliveryReceipt(
        report_id=record.report_id,
        experiment_id=record.experiment_id,
        experiment_version=record.experiment_version,
        protocol_sha256=record.protocol_sha256,
        sha256=record.payload_sha256,
        received_at=datetime.now(timezone.utc),
    )
    uploaded = record.model_copy(update={"state": "uploaded", "receipt": receipt})
    storage.update_record(tmp_path, uploaded)
    assert storage.list_records(tmp_path)[0].state == "uploaded"
    with pytest.raises(storage.SharingStorageError, match="cannot be overwritten"):
        storage.update_record(tmp_path, record)


def test_stale_retry_cannot_undo_optout(tmp_path):
    settings = enable(tmp_path)
    record = storage.queue_report(tmp_path, report_fixture())
    storage.save_settings(tmp_path, settings.model_copy(update={"enabled": False}))
    storage.update_record(tmp_path, record.model_copy(update={"attempt_count": 1}))
    assert storage.list_records(tmp_path)[0].state == "held"


def test_failed_atomic_replace_preserves_existing_record(tmp_path, monkeypatch):
    enable(tmp_path)
    record = storage.queue_report(tmp_path, report_fixture())
    monkeypatch.setattr(storage, "atomic_text_write", Mock(side_effect=PermissionError("locked")))
    with pytest.raises(storage.SharingStorageError):
        storage.update_record(tmp_path, record.model_copy(update={"attempt_count": 1}))
    assert storage.list_records(tmp_path) == (record,)


def test_malformed_record_and_capacity_are_not_silently_skipped(tmp_path, monkeypatch):
    enable(tmp_path)
    record = storage.queue_report(tmp_path, report_fixture())
    monkeypatch.setattr(storage, "MAX_RECORDS", 1)
    with pytest.raises(storage.SharingStorageError, match="full"):
        storage.queue_report(tmp_path, report_fixture())
    path = storage._record_path(tmp_path, record.report_id)
    path.write_text("broken")
    with pytest.raises(storage.SharingStorageError, match="malformed"):
        storage.list_pending(tmp_path)


def test_link_and_reparse_paths_rejected(tmp_path, monkeypatch):
    settings = enable(tmp_path)
    path = tmp_path / ".fpvs-data-sharing" / "settings.json"
    original = type(path).lstat

    def reparse(candidate):
        info = original(candidate)
        if candidate.name == path.name and candidate.parent.name == path.parent.name:
            return type("ReparseInfo", (), {"st_mode": info.st_mode, "st_file_attributes": 0x400})()
        return info

    monkeypatch.setattr(type(path), "lstat", reparse)
    with pytest.raises(storage.SharingStorageError, match="reparse"):
        storage.save_settings(tmp_path, settings)


def _upload(root, report):
    record = storage.queue_report(root, report)
    receipt = DeliveryReceipt(
        report_id=record.report_id,
        experiment_id=record.experiment_id,
        experiment_version=record.experiment_version,
        protocol_sha256=record.protocol_sha256,
        sha256=record.payload_sha256,
        received_at=datetime.now(timezone.utc),
    )
    storage.update_record(root, record.model_copy(update={"state": "uploaded", "receipt": receipt}))
    return record


def _capture(root, report, *, state="finalized"):
    from fpvs_studio.runtime.data_sharing import CaptureIntent, _save_intent

    profile = storage.load_settings(root).profile
    intent = CaptureIntent(
        report_id=report.report_id,
        profile=profile,
        actual_protocol_sha256=report.protocol_sha256,
        project_id="local",
        session_id="session1",
        participant_number="0007",
        participant_session_number=1,
        run_ids=("run1",),
        experiment_test_mode=False,
        pilot_mode=False,
        state=state,
        report=report,
        research_committed=True,
        evidence_sha256="b" * 64,
    )
    _save_intent(root, intent)
    return root / "logs/data-sharing/intents" / f"{report.report_id}.json"


def test_archive_preserves_latest_scope_pending_and_research(tmp_path, monkeypatch):
    enable(tmp_path)
    first = report_fixture(completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    second = report_fixture(completed_at=first.completed_at + timedelta(seconds=1))
    another_scope = report_fixture(experiment_version="2.0")
    for report in (first, second, another_scope):
        _upload(tmp_path, report)
    pending = storage.queue_report(tmp_path, report_fixture())
    intent_path = _capture(tmp_path, first)
    research = tmp_path / "logs/research.csv"
    research.write_bytes(b"unchanged research")
    monkeypatch.setattr(storage, "MAX_RECORDS", 4)
    with pytest.raises(storage.SharingStorageError, match="full"):
        storage.queue_report(tmp_path, report_fixture())
    assert storage.archive_uploaded(tmp_path) == 1
    assert {item.report_id for item in storage.list_records(tmp_path)} == {
        second.report_id,
        another_scope.report_id,
        pending.report_id,
    }
    archive = tmp_path / "logs/data-sharing/archive" / first.report_id
    assert (archive / "report.json").exists()
    assert (archive / "capture.json").exists()
    assert not intent_path.exists()
    assert research.read_bytes() == b"unchanged research"
    storage.queue_report(tmp_path, report_fixture())


def test_archive_corrupt_intent_fails_before_any_file_move(tmp_path):
    enable(tmp_path)
    first = report_fixture(completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    second = report_fixture()
    _upload(tmp_path, first)
    _upload(tmp_path, second)
    path = _capture(tmp_path, first)
    path.write_text("invalid")
    with pytest.raises(storage.SharingStorageError, match="malformed"):
        storage.archive_uploaded(tmp_path)
    assert len(storage.list_records(tmp_path)) == 2
    assert not (tmp_path / "logs/data-sharing/archive").exists()


def test_archive_never_moves_unfinished_capture(tmp_path):
    enable(tmp_path)
    first = report_fixture(completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    second = report_fixture()
    _upload(tmp_path, first)
    _upload(tmp_path, second)
    _capture(tmp_path, first, state="eligible")
    assert storage.archive_uploaded(tmp_path) == 0
    assert len(storage.list_records(tmp_path)) == 2


def test_partial_archive_retains_receipt_and_resumes_without_overwrite(tmp_path, monkeypatch):
    enable(tmp_path)
    first = report_fixture(completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    second = report_fixture()
    _upload(tmp_path, first)
    _upload(tmp_path, second)
    path = _capture(tmp_path, first)
    original = type(path).rename

    def fail_report_move(source, target):
        if source.parent.name == "outbox":
            raise PermissionError("archive")
        return original(source, target)

    monkeypatch.setattr(type(path), "rename", fail_report_move)
    with pytest.raises(storage.SharingStorageError, match="remain recoverable"):
        storage.archive_uploaded(tmp_path)
    assert len(storage.list_records(tmp_path)) == 2
    assert (tmp_path / "logs/data-sharing/archive" / first.report_id / "capture.json").exists()
    monkeypatch.setattr(type(path), "rename", original)
    assert storage.archive_uploaded(tmp_path) == 1
    assert len(storage.list_records(tmp_path)) == 1


def _excluded_capture(root, *, reason="incomplete_session", report_id=None):
    from fpvs_studio.runtime.data_sharing import CaptureIntent, _save_intent

    intent = CaptureIntent(
        report_id=report_id or str(uuid4()), profile=storage.load_settings(root).profile,
        actual_protocol_sha256="a" * 64, project_id="local", session_id="session1",
        participant_number="0007", participant_session_number=1, run_ids=("run1",),
        experiment_test_mode=False, pilot_mode=False, state="ineligible", reason=reason,
    )
    _save_intent(root, intent)
    return intent


def test_reviewed_archive_preserves_bytes_and_all_report_recovery_evidence(tmp_path):
    from fpvs_studio.runtime.data_sharing import _save_intent

    enable(tmp_path)
    first = _excluded_capture(tmp_path)
    second = _excluded_capture(tmp_path, reason="protocol_mismatch")
    running = first.model_copy(update={
        "report_id": str(uuid4()), "state": "running", "reason": None,
    })
    _save_intent(tmp_path, running)
    eligible_report = report_fixture()
    _capture(tmp_path, eligible_report, state="eligible")
    acknowledged = report_fixture()
    _upload(tmp_path, acknowledged)
    _capture(tmp_path, acknowledged)
    for state in ("pending", "held", "failed"):
        record = storage.queue_report(tmp_path, report_fixture())
        storage.update_record(tmp_path, record.model_copy(update={"state": state}))
    records = storage.list_records(tmp_path)
    sources = tmp_path / "logs/data-sharing/intents"
    original = {path.name: path.read_bytes() for path in sources.iterdir()}
    research = tmp_path / "logs/research.csv"
    research.write_bytes(b"private research remains unchanged")
    review = storage.review_terminal_captures(tmp_path, cancel=Event())
    assert {item.report_id for item in review.captures} == {first.report_id, second.report_id}
    assert review.reason_counts == (("incomplete_session", 1), ("protocol_mismatch", 1))
    assert all((sources / filename).exists() for filename in original)  # Review has no moves.
    assert storage.archive_reviewed_captures(tmp_path, review, cancel=Event()) == 2
    for intent in (first, second):
        destination = tmp_path / "logs/data-sharing/archive" / intent.report_id / "capture.json"
        assert destination.read_bytes() == original[f"{intent.report_id}.json"]
        assert not (sources / f"{intent.report_id}.json").exists()
    for identity in (running.report_id, eligible_report.report_id, acknowledged.report_id):
        assert (sources / f"{identity}.json").read_bytes() == original[f"{identity}.json"]
    assert storage.list_records(tmp_path) == records
    assert research.read_bytes() == b"private research remains unchanged"


@pytest.mark.parametrize("change", ["changed", "malformed", "destination", "report", "hardlink"])
def test_review_revalidates_all_evidence_before_any_archive_move(tmp_path, change):
    import os

    from fpvs_studio.runtime.data_sharing import _save_intent

    enable(tmp_path)
    first, second = _excluded_capture(tmp_path), _excluded_capture(tmp_path)
    review = storage.review_terminal_captures(tmp_path, cancel=Event())
    source = tmp_path / "logs/data-sharing/intents" / f"{second.report_id}.json"
    if change == "changed":
        _save_intent(tmp_path, second.model_copy(update={"participant_number": "different"}))
    elif change == "malformed":
        source.write_bytes(b"malformed evidence must remain intact")
    elif change == "destination":
        target = tmp_path / "logs/data-sharing/archive" / second.report_id / "capture.json"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"existing evidence must not be replaced")
    elif change == "report":
        storage.queue_report(tmp_path, report_fixture(report_id=second.report_id))
    else:
        os.link(source, tmp_path / "linked-evidence.json")
    before = {path.name: path.read_bytes() for path in source.parent.iterdir()}
    with pytest.raises(storage.SharingStorageError):
        storage.archive_reviewed_captures(tmp_path, review, cancel=Event())
    assert {path.name: path.read_bytes() for path in source.parent.iterdir()} == before
    assert (source.parent / f"{first.report_id}.json").exists()
    if change == "destination":
        assert target.read_bytes() == b"existing evidence must not be replaced"


def test_new_capture_after_review_is_not_silently_included_and_wrong_root_is_rejected(tmp_path):
    enable(tmp_path)
    first = _excluded_capture(tmp_path)
    review = storage.review_terminal_captures(tmp_path, cancel=Event())
    later = _excluded_capture(tmp_path)
    other_root = tmp_path / "other-project"
    other_root.mkdir()
    with pytest.raises(storage.SharingStorageError, match="another project"):
        storage.archive_reviewed_captures(other_root, review, cancel=Event())
    assert storage.archive_reviewed_captures(tmp_path, review, cancel=Event()) == 1
    assert (tmp_path / "logs/data-sharing/intents" / f"{later.report_id}.json").exists()
    assert (tmp_path / "logs/data-sharing/archive" / first.report_id / "capture.json").exists()


def test_partial_reviewed_archive_preserves_evidence_and_can_be_reviewed_again(
    tmp_path, monkeypatch,
):
    enable(tmp_path)
    _excluded_capture(tmp_path)
    _excluded_capture(tmp_path)
    review = storage.review_terminal_captures(tmp_path, cancel=Event())
    rename = type(tmp_path).rename
    second = review.captures[1].report_id

    def interrupted(source, destination):
        if source.stem == second:
            raise PermissionError("synthetic second move failure")
        return rename(source, destination)

    with monkeypatch.context() as patch:
        patch.setattr(type(tmp_path), "rename", interrupted)
        with pytest.raises(storage.SharingStorageError, match="Evidence is retained"):
            storage.archive_reviewed_captures(tmp_path, review, cancel=Event())
    remaining = storage.review_terminal_captures(tmp_path, cancel=Event())
    assert len(remaining.captures) == 1 and remaining.captures[0].report_id == second
    assert storage.archive_reviewed_captures(tmp_path, remaining, cancel=Event()) == 1
    assert len(list((tmp_path / "logs/data-sharing/archive").glob("*/capture.json"))) == 2


def test_canceled_capture_review_and_archive_never_move_evidence(tmp_path):
    from fpvs_studio.data_sharing.errors import DataSharingCancelled

    enable(tmp_path)
    intent = _excluded_capture(tmp_path)
    review = storage.review_terminal_captures(tmp_path, cancel=Event())
    canceled = Event()
    canceled.set()
    with pytest.raises(DataSharingCancelled):
        storage.review_terminal_captures(tmp_path, cancel=canceled)
    with pytest.raises(DataSharingCancelled):
        storage.archive_reviewed_captures(tmp_path, review, cancel=canceled)
    assert (tmp_path / "logs/data-sharing/intents" / f"{intent.report_id}.json").exists()
