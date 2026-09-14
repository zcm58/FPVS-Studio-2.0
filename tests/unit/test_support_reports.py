"""Safe report collection/persistence tests using only synthetic local files."""

from __future__ import annotations

import json
import logging
import os

import pytest

from fpvs_studio.support import diagnostics, storage
from fpvs_studio.support.diagnostics import (
    DiagnosticLogging,
    bounded_text,
    collect_diagnostics,
    redact,
)
from fpvs_studio.support.models import MAX_LOG_BYTES, Draft, Report
from fpvs_studio.support.storage import DraftStore, export_report


@pytest.mark.parametrize(
    "text", ["a" * 4000, "😀" * 4000, "\x01" * 4000], ids=["ascii", "emoji", "escaped"]
)
def test_feature_limits_and_text_only_payload(text):
    report = Report(kind="feature", happened=text, diagnostics="secret", email="private")
    assert not report.problems()
    payload = json.loads(report.payload())
    assert set(payload) == {
        "schema_version", "kind", "report_id", "created_at", "app_version", "description"
    }
    assert payload["kind"] == "feature"
    assert payload["description"] == text
    assert report.payload() == report.payload(include_logs=False)
    assert "secret" not in report.as_text()
    report.happened += "a"
    assert "happened" in report.problems()
    report.happened = " \n\t"
    assert "happened" in report.problems()


def test_feature_and_bug_drafts_are_independent(tmp_path):
    bug_store = DraftStore(tmp_path)
    feature_store = DraftStore(tmp_path, kind="feature")
    bug = Draft(report=Report(title="Bug", happened="Failure"))
    feature = Draft(report=Report(kind="feature", happened="Add a shortcut"), include_logs=False)
    bug_store.save(bug)
    feature_store.save(feature)
    assert bug_store.load_latest().report.report_id == bug.report.report_id
    assert feature_store.load_latest().report.report_id == feature.report.report_id
    with pytest.raises(ValueError, match="belong"):
        bug_store.save(feature)
    feature_store.discard(feature)
    assert feature_store.load_latest() is None
    assert bug_store.load_latest().report.report_id == bug.report.report_id


def test_old_bug_draft_keeps_wire_hash():
    report = Report(title="Bug", happened="Failure")
    legacy = report.model_dump(mode="json", exclude={"kind"})
    expected = json.dumps(legacy, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert Report.model_validate(legacy).payload() == expected.encode("utf-8")


def test_reviewed_payload_excludes_logs_and_all_delivery_secrets():
    draft = Draft(
        report=Report(
            title="Save failed", happened="Save closed the window.", diagnostics="private-log"
        )
    )
    draft.include_logs = False
    draft.service_url = "https://reports.zack-murphy.com"
    payload = json.loads(draft.report.payload(include_logs=False))
    assert payload["diagnostics"] == ""
    assert payload["title"] == "Save failed"
    assert set(payload) == {
        "schema_version",
        "report_id",
        "created_at",
        "title",
        "happened",
        "steps",
        "expected",
        "email",
        "app_version",
        "os_version",
        "diagnostics",
    }
    text = draft.report.as_text(include_logs=False)
    assert "private-log" not in text
    assert draft.receipt_token not in text
    assert draft.service_url not in text
    assert draft.report.digest(include_logs=False) != draft.report.digest(include_logs=True)


def test_validation_counts_utf8_and_optional_email():
    report = Report(title="Missing export", happened="It stopped.")
    assert report.problems() == {}
    report.happened = "界" * 6000
    assert "happened" in report.problems()
    report.email = "not an email"
    assert "email" in report.problems()
    report.diagnostics = "x" * (MAX_LOG_BYTES + 1)
    assert "diagnostics" in report.problems()
    assert "diagnostics" not in report.problems(include_logs=False)


def test_redaction_preserves_trace_module_but_removes_common_private_values():
    source = (
        'File "C:\\Users\\Researcher\\secret-project\\worker.py", line 8\n'
        "C:\\Data\\participant-list.csv\nparticipant_id=ABC123\n"
        "token=super-secret\nAuthorization: Bearer jwt.secret.value\n"
        "email researcher@example.org\n/home/alice/experiment/file.txt"
    )
    safe = redact(source)
    assert "worker.py" in safe
    for secret in (
        "Researcher",
        "secret-project",
        "participant-list",
        "ABC123",
        "super-secret",
        "jwt.secret.value",
        "researcher@example.org",
        "/home/alice",
    ):
        assert secret not in safe


def test_collection_reads_only_owned_regular_logs_and_caps_bytes(tmp_path):
    folder = tmp_path / "logs"
    folder.mkdir()
    (folder / ("session-" + "a" * 32 + ".log")).write_text("界" * 50000, encoding="utf-8")
    (folder / "participant_summary.csv").write_text("NEVER COLLECT", encoding="utf-8")
    result = collect_diagnostics(tmp_path)
    assert len(result.encode()) <= MAX_LOG_BYTES
    assert "NEVER COLLECT" not in result
    assert len(bounded_text("界" * 50000).encode()) <= MAX_LOG_BYTES


def test_draft_roundtrip_preserves_ambiguous_identity_and_export_strips_secret(tmp_path):
    store = DraftStore(tmp_path / "local support ü")
    draft = Draft(
        report=Report(title="A", happened="B", diagnostics="sensitive log"),
        delivery="uncertain",
        include_logs=False,
    )
    store.save(draft)
    loaded = store.load_latest()
    assert loaded is not None
    assert loaded.report.report_id == draft.report.report_id
    assert loaded.receipt_token == draft.receipt_token
    assert loaded.locked
    destination = tmp_path / "chosen report ü.txt"
    export_report(destination, loaded)
    assert "sensitive log" not in destination.read_text(encoding="utf-8")
    assert draft.receipt_token not in destination.read_text(encoding="utf-8")
    store.discard(draft)
    assert store.load_latest() is None


def test_retention_keeps_five_recent_drafts_and_preserves_unowned_files(tmp_path):
    store = DraftStore(tmp_path)
    for _ in range(7):
        store.save(Draft())
    folder = tmp_path / "drafts"
    user_file = folder / "keep-my-notes.txt"
    user_file.write_text("user data", encoding="utf-8")
    assert len(list(folder.glob("draft-*.json"))) == 5
    for path in folder.glob("draft-*.json"):
        os.utime(path, (1, 1))
    assert store.load_latest() is None
    assert user_file.read_text() == "user data"


def test_corrupt_or_oversized_draft_is_reported_without_deleting_it(tmp_path):
    store = DraftStore(tmp_path)
    draft = Draft()
    store.save(draft)
    path = tmp_path / "drafts" / f"draft-{draft.report.report_id}.json"
    path.write_text("broken", encoding="utf-8")
    with pytest.raises(ValueError):
        store.load_latest()
    assert path.read_text() == "broken"
    path.write_bytes(b"x" * (storage.MAX_DRAFT_BYTES + 1))
    with pytest.raises(ValueError, match="limit"):
        store.load_latest()


def test_failed_replace_preserves_original_and_cleans_only_temporary_file(tmp_path, monkeypatch):
    target = tmp_path / "report.txt"
    target.write_text("original", encoding="utf-8")

    def fail(*args):
        raise PermissionError("test")

    monkeypatch.setattr(storage.os, "replace", fail)
    with pytest.raises(PermissionError):
        export_report(target, Draft())
    assert target.read_text() == "original"
    assert list(tmp_path.iterdir()) == [target]


def test_exclusive_temp_collision_does_not_delete_existing_file(tmp_path, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(storage, "uuid4", lambda: SimpleNamespace(hex="fixed"))
    collision = tmp_path / ".report.txt.fixed.tmp"
    collision.write_text("Do not delete", encoding="utf-8")
    with pytest.raises(FileExistsError):
        export_report(tmp_path / "report.txt", Draft())
    assert collision.read_text() == "Do not delete"


def test_draft_and_export_support_long_windows_paths(tmp_path):
    from fpvs_studio.core.paths import filesystem_path

    long_root = tmp_path.joinpath(*[f"long-support-directory-{i}" for i in range(13)])
    filesystem_path(long_root).mkdir(parents=True)
    store = DraftStore(long_root)
    draft = Draft(report=Report(title="Unicode ü", happened="A long-path failure"))
    store.save(draft)
    assert store.load_latest().report.title == "Unicode ü"
    destination = long_root / "export.txt"
    export_report(destination, draft)
    assert "Unicode ü" in filesystem_path(destination).read_text(encoding="utf-8")


def test_unwritable_support_directory_fails_without_project_fallback(tmp_path):
    unavailable = tmp_path / "support"
    unavailable.write_text("not a directory", encoding="utf-8")
    with pytest.raises(OSError):
        DraftStore(unavailable).save(Draft())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["support"]


def test_path_is_os_local_and_never_falls_back_to_project(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert storage.support_directory() == tmp_path / "FPVS Studio/support"
    monkeypatch.delenv("LOCALAPPDATA")
    with pytest.raises(OSError):
        storage.support_directory()


def test_queued_logging_writes_redacted_trace_and_restores_hooks(tmp_path):
    session = DiagnosticLogging(tmp_path)
    original = diagnostics.sys.excepthook
    session.start()
    try:
        try:
            raise RuntimeError("token=do-not-export")
        except RuntimeError:
            logging.getLogger("fpvs_studio.test").exception("Synthetic failure")
    finally:
        session.close()
    assert diagnostics.sys.excepthook is original
    text = collect_diagnostics(tmp_path)
    assert "Synthetic failure" in text
    assert "RuntimeError" in text
    assert "do-not-export" not in text


def test_collection_does_not_follow_symlink(tmp_path):
    folder = tmp_path / "logs"
    folder.mkdir()
    outside = tmp_path / "user.txt"
    outside.write_text("outside", encoding="utf-8")
    try:
        (folder / ("session-" + "b" * 32 + ".log")).symlink_to(outside)
    except OSError:
        pytest.skip("Creating symlinks requires Windows permission")
    assert "outside" not in collect_diagnostics(tmp_path)
