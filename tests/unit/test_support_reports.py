"""Safe report collection/persistence tests using only synthetic local files."""

from __future__ import annotations

import ast
import json
import logging
import os
import stat
from pathlib import Path
from threading import Event
from types import SimpleNamespace

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


@pytest.fixture
def load_report_draft():
    """Run the real controller load path without importing Qt or a transport."""
    source = Path(__file__).resolve().parents[2] / "src/fpvs_studio/gui/bug_report_controller.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    controller = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "BugReportController"
    )
    method = next(
        node for node in controller.body
        if isinstance(node, ast.FunctionDef) and node.name == "_load"
    )
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        method,
    ], type_ignores=[])
    collections = []
    namespace = {
        "__version__": "2.5.1",
        "collect_diagnostics": lambda root: collections.append(root) or "Synthetic logs",
    }
    exec(compile(ast.fix_missing_locations(module), str(source), "exec"), namespace)

    def load(store, kind):
        context = SimpleNamespace(
            store=lambda: store,
            kind=kind,
            _empty_draft=lambda: Draft(
                report=Report(kind=kind, app_version="2.5.1"), include_logs=kind == "bug"
            ),
        )
        return namespace["_load"](context, Event())

    return load, collections


@pytest.mark.parametrize("kind", ["bug", "feature"])
@pytest.mark.parametrize("include_logs", [False, True])
def test_editable_saved_report_uses_current_version_without_losing_draft(
    tmp_path, load_report_draft, kind, include_logs,
):
    load, collections = load_report_draft
    store = DraftStore(tmp_path, kind=kind)
    store.save(Draft(
        report=Report(
            kind=kind, app_version="2.4.8", os_version="Synthetic OS",
            title="Saved summary", happened="Saved description", steps="Saved steps",
            expected="Saved expectation", email="reporter@example.test",
            diagnostics="Previously reviewed logs",
        ),
        include_logs=include_logs, service_url="https://reports.example.test",
    ))
    before = store.load_latest()
    loaded, fresh = load(store, kind)

    expected = before.model_dump()
    expected["report"]["app_version"] = "2.5.1"
    assert not fresh
    assert loaded.model_dump() == expected
    assert json.loads(loaded.report.payload())["app_version"] == "2.5.1"
    assert "Application\n2.5.1" in loaded.report.as_text()
    assert collections == []
    store.save(loaded)
    persisted = store.load_latest()
    assert persisted.model_dump(exclude={"updated_at"}) == loaded.model_dump(
        exclude={"updated_at"}
    )


@pytest.mark.parametrize("kind", ["bug", "feature"])
@pytest.mark.parametrize("delivery", ["uncertain", "received", "submitted"])
def test_locked_saved_report_preserves_version_payload_and_receipt(
    tmp_path, load_report_draft, kind, delivery,
):
    load, collections = load_report_draft
    store = DraftStore(tmp_path, kind=kind)
    store.save(Draft(
        report=Report(
            kind=kind, app_version="2.4.8", title="Saved summary",
            happened="Submitted description", diagnostics="Reviewed logs",
        ),
        delivery=delivery, include_logs=False, service_url="https://reports.example.test",
    ))
    before = store.load_latest()
    loaded, fresh = load(store, kind)

    assert not fresh
    assert loaded.model_dump() == before.model_dump()
    assert loaded.report.payload() == before.report.payload()
    assert loaded.report.digest(include_logs=False) == before.report.digest(include_logs=False)
    assert collections == []
    assert store.load_latest().model_dump() == before.model_dump()


@pytest.mark.parametrize("kind", ["bug", "feature"])
def test_fresh_report_keeps_current_version_and_collects_only_bug_logs(
    tmp_path, load_report_draft, kind,
):
    load, collections = load_report_draft
    store = DraftStore(tmp_path, kind=kind)
    loaded, fresh = load(store, kind)

    assert fresh
    assert loaded.report.app_version == "2.5.1"
    assert loaded.report.kind == kind
    assert loaded.delivery == "editing"
    assert loaded.report.diagnostics == ("Synthetic logs" if kind == "bug" else "")
    assert loaded.include_logs == (kind == "bug")
    assert collections == ([tmp_path] if kind == "bug" else [])
    assert store.load_latest() is None


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


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('{"token": "two private words", "mode": "lab"}',
         '{"token": "<redacted>", "mode": "lab"}'),
        ("{'secret': 'two private words', 'mode': 'lab'}",
         "{'secret': '<redacted>', 'mode': 'lab'}"),
        ('API_KEY = "private value"; mode=lab', 'API_KEY = "<redacted>"; mode=lab'),
        ('password="two words', 'password="<redacted>"'),
        ('password="two words\\', 'password="<redacted>"'),
        ("password='two words", "password='<redacted>'"),
        ('token=private-value; mode=lab', 'token=<redacted>; mode=lab'),
        ('Authorization: Bearer abc+/._~-==', 'Authorization: Bearer <redacted>'),
        ('{"authorization": "bEaReR abc+/._~-==", "mode": "lab"}',
         '{"authorization": "Bearer <redacted>", "mode": "lab"}'),
        ('tokenize=public; secret_count=2; mode=lab',
         'tokenize=public; secret_count=2; mode=lab'),
    ],
)
def test_redaction_covers_quoted_credentials_and_complete_bearer_tokens(source, expected):
    assert redact(source) == expected
    assert redact(expected) == expected


def test_redaction_preserves_nested_json_around_escaped_secret_values():
    source = json.dumps({
        "configuration": {"token": 'private "quoted" value \\ suffix', "mode": "lab"},
        "password": "private 'quoted' words", "status": "failed",
    })
    expected = {
        "configuration": {"token": "<redacted>", "mode": "lab"},
        "password": "<redacted>", "status": "failed",
    }
    result = redact(source)
    assert json.loads(result) == expected
    assert redact(result) == result


class _RacedLog:
    name = "session-" + "c" * 32 + ".log"

    def __init__(self, error):
        self.error = error

    def is_file(self):
        return True

    def is_symlink(self):
        return False

    def stat(self):
        raise self.error("Synthetic peer log race")

    def lstat(self):
        raise self.error("Synthetic peer log race")


def _inject_raced_log(monkeypatch, folder, *, phase="startup", error=FileNotFoundError):
    folder = storage.filesystem_path(folder)
    original = Path.iterdir
    raced = _RacedLog(error)
    scans = []

    def iterdir(path):
        entries = list(original(path))
        if path == folder:
            scans.append(True)
            if phase == "startup" or len(scans) > 1:
                entries.append(raced)
        return iter(entries)

    monkeypatch.setattr(Path, "iterdir", iterdir)
    return scans


@pytest.mark.parametrize("phase", ["startup", "record"])
def test_logging_continues_when_peer_log_disappears_during_scan(tmp_path, monkeypatch, phase):
    monkeypatch.setattr(diagnostics, "_logging_notice", "")
    folder = tmp_path / "logs"
    folder.mkdir()
    scans = _inject_raced_log(monkeypatch, folder, phase=phase)
    session = DiagnosticLogging(tmp_path)
    session.start()
    try:
        assert session.ready.wait(2)
        session.logger.warning("First message survives a rotated peer log")
        session.logger.warning("Subsequent message is also retained")
    finally:
        session.close()
    assert len(scans) >= 3
    text = (folder / f"session-{session.session_id}.log").read_text(encoding="utf-8")
    assert "First message survives" in text
    assert "Subsequent message" in text
    assert diagnostics._logging_notice == ""


def test_collection_keeps_healthy_logs_when_peer_disappears_during_scan(tmp_path, monkeypatch):
    folder = tmp_path / "logs"
    folder.mkdir()
    (folder / ("session-" + "a" * 32 + ".log")).write_text("Healthy diagnostic", encoding="utf-8")
    _inject_raced_log(monkeypatch, folder)
    assert "Healthy diagnostic" in collect_diagnostics(tmp_path)


def test_collection_keeps_healthy_logs_when_peer_disappears_before_open(tmp_path, monkeypatch):
    folder = tmp_path / "logs"
    folder.mkdir()
    healthy = folder / ("session-" + "a" * 32 + ".log")
    vanished = folder / ("session-" + "b" * 32 + ".log")
    healthy.write_text("Healthy diagnostic", encoding="utf-8")
    vanished.write_text("Vanished diagnostic", encoding="utf-8")
    original = Path.open

    def open_log(path, *args, **kwargs):
        if path == storage.filesystem_path(vanished):
            raise FileNotFoundError("Synthetic rotation after metadata snapshot")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_log)
    result = collect_diagnostics(tmp_path)
    assert "Healthy diagnostic" in result
    assert "Vanished diagnostic" not in result


def test_collection_keeps_permission_errors_visible(tmp_path, monkeypatch):
    folder = tmp_path / "logs"
    folder.mkdir()
    _inject_raced_log(monkeypatch, folder, error=PermissionError)
    with pytest.raises(PermissionError, match="Synthetic peer log race"):
        collect_diagnostics(tmp_path)


def test_logging_keeps_permission_errors_visible(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostics, "_logging_notice", "")
    folder = tmp_path / "logs"
    folder.mkdir()
    _inject_raced_log(monkeypatch, folder, error=PermissionError)
    session = DiagnosticLogging(tmp_path)
    session.start()
    try:
        assert session.ready.wait(2)
    finally:
        session.close()
    assert diagnostics._logging_notice == (
        "Persistent application logs are unavailable on this machine."
    )


def test_collection_excludes_reparse_logs_without_opening_them(tmp_path, monkeypatch):
    folder = tmp_path / "logs"
    folder.mkdir()
    link = folder / ("session-" + "b" * 32 + ".log")
    link.write_text("Never collect redirected content", encoding="utf-8")
    original = Path.lstat

    def lstat(path):
        if path == storage.filesystem_path(link):
            return SimpleNamespace(
                st_mode=stat.S_IFREG, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
            )
        return original(path)

    monkeypatch.setattr(Path, "lstat", lstat)
    assert "Never collect" not in collect_diagnostics(tmp_path)


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


def test_queued_logging_preserves_records_with_malformed_unicode(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostics, "_logging_notice", "")
    session = DiagnosticLogging(tmp_path)
    # Keep the deliberate surrogate in Studio's handler; xdist reports require UTF-8.
    monkeypatch.setattr(session.logger, "propagate", False)
    session.start()
    try:
        logging.getLogger("fpvs_studio.test").warning("Synthetic filename: bad\ud800name")
    finally:
        session.close()

    text = collect_diagnostics(tmp_path)
    assert "Synthetic filename: bad?name" in text
    assert text.encode("utf-8")
    assert diagnostics._logging_notice == ""


def test_native_capture_retains_descriptor_and_redacts_collected_trace(tmp_path, monkeypatch):
    opened = []
    disabled = []
    monkeypatch.setattr(diagnostics.faulthandler, "is_enabled", lambda: False)
    monkeypatch.setattr(
        diagnostics.faulthandler, "enable",
        lambda *, file, all_threads: opened.append((file, all_threads)),
    )
    monkeypatch.setattr(diagnostics.faulthandler, "disable", lambda: disabled.append(True))
    session = DiagnosticLogging(tmp_path, capture_native=True)
    session.start()
    try:
        assert session.ready.wait(1)
        stream, all_threads = opened[0]
        assert all_threads
        assert not stream.closed
        os.write(stream.fileno(), b'File "C:\\Users\\synthetic\\worker.py", line 9\n')
        diagnostics.record_qt_fatal("Synthetic Qt failure token=private-secret")
    finally:
        session.close()
    assert stream.closed
    assert disabled == [True]
    text = collect_diagnostics(tmp_path)
    assert "worker.py" in text
    assert "Synthetic Qt failure" in text
    assert "private-secret" not in text
    assert "synthetic" not in text


def test_native_capture_preserves_existing_fault_handler(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostics.faulthandler, "is_enabled", lambda: True)
    monkeypatch.setattr(
        diagnostics.faulthandler, "enable", lambda **_kwargs: pytest.fail("replaced handler")
    )
    monkeypatch.setattr(
        diagnostics.faulthandler, "disable", lambda: pytest.fail("disabled external handler")
    )
    session = DiagnosticLogging(tmp_path, capture_native=True)
    session.start()
    session.close()
    assert not list((tmp_path / "logs").glob("*-native.log"))


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
