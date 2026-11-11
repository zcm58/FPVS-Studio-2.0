"""Mac repair diagnostics survive failures and IDE handoff without running native tools."""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "macos_repair_diagnostics", ROOT / "Repair Mac.py",
)
assert SPEC is not None and SPEC.loader is not None
repair = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repair)


@pytest.fixture(autouse=True)
def isolated_processes(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Tests must replace every native subprocess and signal.")

    monkeypatch.setattr(repair.subprocess, "run", unexpected)
    monkeypatch.setattr(repair.subprocess, "Popen", unexpected)
    monkeypatch.setattr(repair.os, "kill", unexpected)
    monkeypatch.setattr(repair.os, "killpg", unexpected, raising=False)
    monkeypatch.setattr(repair, "_offer_report", lambda *args: None, raising=False)
    monkeypatch.setattr(repair, "_DIAGNOSTICS", None)
    launcher = SimpleNamespace(**vars(repair.sys))
    launcher.platform = "darwin"
    monkeypatch.setattr(repair, "sys", launcher)
    monkeypatch.setattr(repair.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(repair.platform, "release", lambda: "25.0.0")
    monkeypatch.setattr(repair.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(repair.platform, "mac_ver", lambda: ("26.0", (), "arm64"))


@pytest.fixture
def diagnostics(tmp_path):
    session = repair._Diagnostics(tmp_path)
    try:
        yield session
    finally:
        session.close()


@pytest.mark.parametrize("source,secret", [
    ("https://alice:secret-value@packages.example/simple", "alice:secret-value"),
    ("Authorization: Bearer secret-value", "secret-value"),
    ("https://example.test/?token=secret-value&safe=1", "secret-value"),
    ('{"receipt_token": "secret-value"}', "secret-value"),
    ("--repair-token secret-value", "secret-value"),
    ("https://reports.example/verify#intent_id=example&token=secret-value", "secret-value"),
    ("/Users/researcher/Studio/project", "researcher"),
    (str(PureWindowsPath("C:/") / "Users" / "researcher" / "Studio" / "project"), "researcher"),
    ("pycharm-repair/" + "a" * 32 + ".log", "a" * 32),
])
def test_shareable_logs_redact_credentials_and_home_paths(source, secret):
    assert secret not in repair._redact(source)


@pytest.mark.parametrize("source", [
    'password="unfinished secret\nnext log line',
    "token='two words'\nnext log line",
    "--repair-token=abcdef\nnext log line",
])
def test_redaction_is_idempotent_and_does_not_consume_following_lines(source):
    result = repair._redact(source)
    assert "next log line" in result
    assert "unfinished secret" not in result and "two words" not in result
    assert "abcdef" not in result
    assert repair._redact(result) == result


def test_log_records_full_chained_traceback_with_redaction(diagnostics):
    try:
        try:
            raise OSError("https://alice:secret-value@example.test/simple failed")
        except OSError as cause:
            raise RuntimeError("Engine import failed") from cause
    except RuntimeError:
        repair._LOGGER.exception("Check failed")

    text = diagnostics.path.read_text(encoding="utf-8")
    assert "OSError" in text and "RuntimeError" in text
    assert "direct cause" in text and "Traceback" in text
    assert "Engine import failed" in text
    assert "alice:secret-value" not in text
    assert "[redacted]@example.test" in text


def test_log_handlers_are_removed_and_logger_state_restored(tmp_path):
    before = (repair._LOGGER.level, repair._LOGGER.propagate, repair._LOGGER.handlers[:])
    diagnostics = repair._Diagnostics(tmp_path)
    diagnostics.close()
    assert (repair._LOGGER.level, repair._LOGGER.propagate, repair._LOGGER.handlers) == before
    assert diagnostics.stream.closed


def test_disk_write_failure_is_reported_without_losing_console_output(tmp_path, capsys):
    class Unwritable:
        def write(self, text):
            raise OSError("disk full")

        def flush(self):
            pass

    session = repair._Diagnostics(tmp_path)
    session.file_handler.setStream(Unwritable())
    repair._LOGGER.error("Engine failed: please keep this error")
    assert session.file_handler.failed
    session.close()
    output = capsys.readouterr().err
    assert "Engine failed: please keep this error" in output
    assert "Could not save the complete diagnostic log" in output
    assert "Copy the PyCharm console" in output


@pytest.mark.parametrize("relative", [
    ".fpvs-macos", ".fpvs-macos/diagnostics", ".fpvs-macos/diagnostics/run",
    ".fpvs-macos/diagnostics/run/repair.log",
])
def test_diagnostic_paths_reject_linked_ancestors(monkeypatch, tmp_path, relative):
    linked = tmp_path / relative
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == linked or original(path))
    with pytest.raises(ValueError, match="links"):
        repair._owned_path(tmp_path, tmp_path / ".fpvs-macos/diagnostics/run/repair.log")


def test_diagnostic_paths_cannot_escape_checkout(tmp_path):
    for path in (tmp_path / "outside.log", tmp_path / ".fpvs-macos/../../outside.log"):
        with pytest.raises(ValueError):
            repair._owned_path(tmp_path, path)


def test_private_state_failure_preserves_previous_receipt(monkeypatch, tmp_path):
    path = tmp_path / "receipt.json"
    path.write_text('{"delivery": "uncertain"}', encoding="utf-8")

    def fail(*args):
        raise OSError("disk refused replacement")

    monkeypatch.setattr(repair.os, "replace", fail)
    with pytest.raises(OSError, match="replacement"):
        repair._private_json(path, {"delivery": "submitted"})
    assert json.loads(path.read_text()) == {"delivery": "uncertain"}
    assert list(tmp_path.iterdir()) == [path]


def test_private_state_is_flushed_before_atomic_replacement(monkeypatch, tmp_path):
    path = tmp_path / "receipt.json"
    calls = []
    replace = repair.os.replace
    monkeypatch.setattr(repair.os, "fsync", lambda fd: calls.append("sync"))

    def tracked_replace(source, destination):
        calls.append("replace")
        replace(source, destination)

    monkeypatch.setattr(repair.os, "replace", tracked_replace)
    repair._private_json(path, {"delivery": "uncertain"})
    assert calls == ["sync", "replace"]
    assert json.loads(path.read_text()) == {"delivery": "uncertain"}


def test_source_context_does_not_import_studio_or_read_research_files(tmp_path, diagnostics):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "fpvs-studio"\nversion = "2.9.0"\n'
        '[tool.unrelated]\nversion = "99.0"\n', encoding="utf-8",
    )
    (tmp_path / "participant.csv").write_text("PRIVATE RESEARCH CONTENT", encoding="utf-8")
    repair._log_context(tmp_path, True)
    text = diagnostics.path.read_text(encoding="utf-8")
    assert "version 2.9.0" in text
    assert "check_only=True" in text
    assert "Launcher Python" in text and "base_prefix=" in text
    assert "Source SHA256 pyproject.toml" in text
    assert "PRIVATE RESEARCH CONTENT" not in text


def test_subprocess_output_is_captured_before_wait_returns(monkeypatch, diagnostics):
    output = "pip consistency failed\nTraceback (most recent call last):\nRuntimeError: engine\n"
    calls = []

    class Child:
        stdout = io.StringIO(output)

        def wait(self, timeout=None):
            # The reader starts before wait, and its output is retained before command returns.
            calls.append(("wait", timeout))
            return 7

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return Child()

    monkeypatch.setattr(repair.subprocess, "Popen", popen)
    result = diagnostics.command(["python", "-I", "-c", "private probe source"],
                                 cwd=diagnostics.root, timeout=30)
    text = diagnostics.path.read_text(encoding="utf-8")
    assert result.returncode == 7
    assert "pip consistency failed" in text and "RuntimeError: engine" in text
    assert "exit=7" in text and "elapsed=" in text
    assert "private probe source" not in text
    assert calls[0][1]["stderr"] == subprocess.STDOUT
    assert calls[0][1]["start_new_session"] is True
    assert calls[-1] == ("wait", 30)


def test_timed_out_child_group_is_stopped_and_failure_preserved(monkeypatch, diagnostics):
    calls = []

    class Child:
        stdout = io.StringIO("output before timeout\n")
        pid = 517

        def wait(self, timeout=None):
            calls.append(("wait", timeout))
            if timeout == 30:
                raise subprocess.TimeoutExpired("probe", timeout)
            return -15

    monkeypatch.setattr(repair.subprocess, "Popen", lambda *args, **kwargs: Child())
    monkeypatch.setattr(repair.os, "killpg", lambda pid, sig: calls.append(("kill", pid, sig)))
    with pytest.raises(subprocess.TimeoutExpired):
        diagnostics.command(["python", "-I", "-c", "probe"], cwd=diagnostics.root, timeout=30)
    assert ("kill", 517, repair.signal.SIGTERM) in calls
    assert calls[-1] == ("wait", 5)
    text = diagnostics.path.read_text(encoding="utf-8")
    assert "output before timeout" in text and "STOP Python probe" in text


def test_pending_job_path_is_accepted_only_from_owned_job_directory(diagnostics):
    job = diagnostics.root / ".fpvs-macos/pycharm-repair" / ("a" * 32 + ".log")
    diagnostics.observe(f"Environment verified. Repair log: {job}\n")
    assert diagnostics.job_log == job
    with pytest.raises(ValueError):
        diagnostics.observe(f"Repair log: {diagnostics.root / 'personal.log'}")
    with pytest.raises(ValueError, match="Unrecognized"):
        diagnostics.observe(f"Repair log: {job.with_name('unrelated.log')}")


def test_continuation_runs_same_file_with_verified_interpreter(monkeypatch, diagnostics):
    job = diagnostics.root / ".fpvs-macos/pycharm-repair" / ("a" * 32 + ".log")
    diagnostics.job_log = job
    calls = []
    monkeypatch.setattr(
        repair.subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    repair._continue_diagnostics(diagnostics)
    state_path = diagnostics.path.with_name("continuation.json")
    state = json.loads(state_path.read_text())
    assert state["log"] == str(diagnostics.path)
    assert state["job_log"] == str(job)
    command = calls[0][0][0]
    assert command == [
        str(diagnostics.root / ".venv3.10/bin/python"), "-I",
        str(Path(repair.__file__).absolute()), "--finish-diagnostics", str(state_path),
    ]
    assert calls[0][1]["start_new_session"] is True
    assert calls[0][1]["stdin"] == subprocess.DEVNULL


def _continuation(root, *, success=True, claim=True, result=True, job_text="Configured PyCharm\n"):
    session = repair._Diagnostics(root)
    log = session.path
    session.close()
    job = root / ".fpvs-macos/pycharm-repair" / ("b" * 32 + ".log")
    job.parent.mkdir(parents=True)
    job.write_text(job_text, encoding="utf-8")
    if claim:
        job.with_suffix(".claim").write_text("123")
    if result:
        job.with_suffix(".result.json").write_text(json.dumps({
            "success": success, "message": "PyCharm reopened" if success else "Quit was canceled",
        }), encoding="utf-8")
    state_path = log.with_name("continuation.json")
    state_path.write_text(json.dumps({
        "log": str(log), "job_log": str(job), "app_version": "2.9.0",
    }), encoding="utf-8")
    return state_path, log


@pytest.mark.parametrize("success,result,job_text,expected", [
    (True, True, "Configured PyCharm\n", 0),
    (False, True, "Quit was canceled\n", 1),
    (True, False, "Failed before receipt\n", 1),
    (True, True, "Could not release this PyCharm repair request\n", 1),
    (True, True, "Could not retain the PyCharm repair result\n", 1),
])
def test_finalizer_outcome_and_errors_join_original_log(
    monkeypatch, tmp_path, success, result, job_text, expected,
):
    state, log = _continuation(tmp_path, success=success, result=result, job_text=job_text)
    offers = []
    monkeypatch.setattr(repair, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(repair, "_offer_report", lambda *args: offers.append(args))
    assert repair._finish_diagnostics(tmp_path, state) == expected
    text = log.read_text(encoding="utf-8")
    assert job_text.strip() in text
    assert f"exit={expected}" in text
    assert offers[0][0] == log and offers[0][2] == "2.9.0"


@pytest.mark.parametrize("claim", [False, True])
def test_success_receipt_requires_confirmed_worker_exit(monkeypatch, tmp_path, claim):
    state, log = _continuation(tmp_path, claim=claim)
    clock = iter([0, 0, 0, 421])
    monkeypatch.setattr(repair.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(repair.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(repair, "_pid_alive", lambda pid: True)
    assert repair._finish_diagnostics(tmp_path, state) == 1
    assert "exit=1" in log.read_text(encoding="utf-8")


def test_observer_reports_incomplete_log_even_when_repair_succeeded(monkeypatch, tmp_path):
    state, log = _continuation(tmp_path)
    create_diagnostics = repair._Diagnostics
    offers = []

    def failed_log(*args, **kwargs):
        session = create_diagnostics(*args, **kwargs)
        session.file_handler.failed = True
        return session

    monkeypatch.setattr(repair, "_Diagnostics", failed_log)
    monkeypatch.setattr(repair, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(repair, "_offer_report", lambda *args: offers.append(args))
    repair._finish_diagnostics(tmp_path, state)
    assert offers[0][0] == log
    assert "log" in offers[0][1].lower()
    assert any(word in offers[0][1].lower() for word in ("incomplete", "could not save", "missing"))


def test_invalid_continuation_cannot_read_external_file(monkeypatch, tmp_path):
    state, log = _continuation(tmp_path)
    data = json.loads(state.read_text())
    external = tmp_path / "private.log"
    external.write_text("DO NOT READ", encoding="utf-8")
    data["job_log"] = str(external)
    state.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        repair._finish_diagnostics(tmp_path, state)
    assert "DO NOT READ" not in log.read_text(encoding="utf-8")


@pytest.mark.parametrize("result", [0, 1])
def test_main_saves_logs_then_offers_report_even_for_failed_checks(monkeypatch, tmp_path, result):
    monkeypatch.setattr(repair, "__file__", str(tmp_path / "Repair Mac.py"))
    offers = []
    monkeypatch.setattr(repair, "repair_environment", lambda *args, **kwargs: result)
    monkeypatch.setattr(repair, "_offer_report", lambda *args: offers.append(args))
    assert repair.main([]) == result
    assert len(offers) == 1
    log = offers[0][0].read_text(encoding="utf-8")
    assert "RESULT:" in log and f"exit={result}" in log
    assert "--report-log" in log
    assert repair._DIAGNOSTICS is None


def test_unexpected_failure_keeps_full_traceback_and_report_action(monkeypatch, tmp_path):
    monkeypatch.setattr(repair, "__file__", str(tmp_path / "Repair Mac.py"))
    offers = []

    def fail(*args, **kwargs):
        raise RuntimeError("Unexpected engine failure")

    monkeypatch.setattr(repair, "repair_environment", fail)
    monkeypatch.setattr(repair, "_offer_report", lambda *args: offers.append(args))
    assert repair.main([]) == 1
    text = offers[0][0].read_text(encoding="utf-8")
    assert "RuntimeError: Unexpected engine failure" in text
    assert "Traceback" in text and "exit=1" in text


def test_main_pending_handoff_defers_report_until_finalizer(monkeypatch, tmp_path):
    monkeypatch.setattr(repair, "__file__", str(tmp_path / "Repair Mac.py"))
    calls = []

    def pending(*args, **kwargs):
        repair._DIAGNOSTICS.pending = True
        return 0

    monkeypatch.setattr(repair, "repair_environment", pending)
    monkeypatch.setattr(repair, "_continue_diagnostics", lambda session: calls.append("continue"))
    monkeypatch.setattr(repair, "_offer_report", lambda *args: calls.append("offer"))
    assert repair.main([]) == 0
    assert calls == ["continue"]


def test_handoff_launch_failure_offers_failure_report(monkeypatch, tmp_path):
    monkeypatch.setattr(repair, "__file__", str(tmp_path / "Repair Mac.py"))
    offers = []

    def pending(*args, **kwargs):
        repair._DIAGNOSTICS.pending = True
        return 0

    def fail(session):
        raise OSError("observer could not start")

    monkeypatch.setattr(repair, "repair_environment", pending)
    monkeypatch.setattr(repair, "_continue_diagnostics", fail)
    monkeypatch.setattr(repair, "_offer_report", lambda *args: offers.append(args))
    assert repair.main([]) == 1
    assert "observer could not start" in offers[0][0].read_text(encoding="utf-8")


@pytest.mark.parametrize("keep_log", [False, True])
def test_detached_failure_before_logger_opens_is_visible(monkeypatch, tmp_path, keep_log):
    state, log = _continuation(tmp_path)
    if not keep_log:
        log.unlink()
    monkeypatch.setattr(repair, "__file__", str(tmp_path / "Repair Mac.py"))
    shown = []

    def fail(*args):
        raise OSError("Cannot append diagnostic log")

    monkeypatch.setattr(repair, "_finish_diagnostics", fail)
    monkeypatch.setattr(repair, "_offer_report", lambda *args: shown.append(("report", args)))
    monkeypatch.setattr(repair, "_native_dialog", lambda *args: shown.append(("notice", args)))
    assert repair.main(["--finish-diagnostics", str(state)]) == 1
    assert shown[0][0] == ("report" if keep_log else "notice")
    assert "Cannot append diagnostic log" in str(shown)


def test_report_only_does_not_repeat_environment_repair(monkeypatch, tmp_path):
    _state, log = _continuation(tmp_path)
    monkeypatch.setattr(repair, "__file__", str(tmp_path / "Repair Mac.py"))
    offers = []

    def unexpected(*args, **kwargs):
        raise AssertionError("Report-only mode must not repair.")

    monkeypatch.setattr(repair, "repair_environment", unexpected)
    monkeypatch.setattr(repair, "_offer_report", lambda *args: offers.append(args))
    assert repair.main(["--report-log", str(log)]) == 0
    assert offers[0][0] == log


def test_native_dialog_passes_user_text_as_literal_argv(monkeypatch):
    message = 'Failure "quoted"\n$(do not execute); & unexpected'
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="Send Error Report\n")

    monkeypatch.setattr(repair.subprocess, "run", run)
    assert repair._native_dialog(
        message, ("Close", "Copy Log", "Send Error Report"), "Close",
    ) == "Send Error Report"
    command, options = calls[0]
    assert command[3:] == [message, "Close", "Close", "Copy Log", "Send Error Report"]
    assert message not in command[2]
    assert options["timeout"] == 130
    assert "shell" not in options


def test_native_dialog_timeout_does_not_authorize_submission(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("dialog", 130)

    monkeypatch.setattr(repair.subprocess, "run", timeout)
    assert repair._native_dialog("Finished", ("Close", "Send Error Report"), "Close") == "Close"
