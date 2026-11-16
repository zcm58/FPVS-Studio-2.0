"""Repair completion is concise and automatic, including the detached IDE result."""

from __future__ import annotations

import importlib.util
import io
import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("repair_completion_tests", ROOT / "Repair Mac.py")
assert SPEC is not None and SPEC.loader is not None
repair = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repair)


@pytest.fixture
def session(tmp_path):
    diagnostics = repair._Diagnostics(tmp_path)
    try:
        yield diagnostics
    finally:
        diagnostics.close()


def facts(studio="2.8.1", scipy="1.15.3"):
    return "FPVS_REPAIR_FACTS " + json.dumps({
        "fpvs-studio": studio, "scipy": scipy, "python_version": "3.10.22",
        "python_cpu": "arm64", "psychopy_version": "2026.2.5",
        "numpy_version": "2.2.6", "pyside6_version": "6.11.3",
    })


def fake_metadata_process(monkeypatch, state):
    monkeypatch.setattr(repair, "_log_context", lambda *args: None)

    def launch(command, **kwargs):
        assert command[1:3] == ["-I", "-c"]
        assert "FPVS_REPAIR_FACTS" in command[3]
        assert "load_psychopy_modules" not in command[3]
        assert "import tomli" not in command[3]
        if state.get("unrunnable"):
            raise OSError("Interpreter cannot run")

        class Child:
            stdout = io.StringIO(state["facts"] + "\n")

            def wait(self, timeout=None):
                assert timeout == 15
                return 0

        return Child()

    monkeypatch.setattr(repair.subprocess, "Popen", launch)


@pytest.mark.parametrize("initial", ["missing", "unrunnable"])
def test_rebuilt_environment_is_never_reported_as_the_original(monkeypatch, tmp_path, initial):
    python = tmp_path / ".venv3.10/bin/python"
    if initial == "unrunnable":
        python.parent.mkdir(parents=True)
        python.touch()
    state = {"unrunnable": initial == "unrunnable", "facts": facts("3.0.1", "1.14.1")}
    fake_metadata_process(monkeypatch, state)
    monkeypatch.setattr(repair, "__file__", str(tmp_path / "Repair Mac.py"))
    monkeypatch.setattr(repair, "_collect_macos_build", lambda session: None)
    reports = []

    def rebuild(*args, **kwargs):
        python.parent.mkdir(parents=True, exist_ok=True)
        python.touch()
        state["unrunnable"] = False
        repair._DIAGNOSTICS.observe(state["facts"])
        return 0

    monkeypatch.setattr(repair, "repair_environment", rebuild)
    monkeypatch.setattr(repair, "_complete_automatic_report", lambda *args: reports.append(args))
    assert repair.main(["--automatic-report"]) == 0
    details = reports[0][0].details
    assert details["initial_studio_version"] == ("missing" if initial == "missing" else "unknown")
    assert details["initial_scipy_version"] == ("missing" if initial == "missing" else "unknown")
    assert details["final_scipy_version"] == "1.14.1"


@pytest.mark.parametrize("final", ["installed", "unrunnable"])
def test_failed_setup_still_snapshots_actual_final_packages(monkeypatch, tmp_path, final):
    python = tmp_path / ".venv3.10/bin/python"
    python.parent.mkdir(parents=True)
    python.touch()
    state = {"facts": facts()}
    fake_metadata_process(monkeypatch, state)
    monkeypatch.setattr(repair, "__file__", str(tmp_path / "Repair Mac.py"))
    monkeypatch.setattr(repair, "_collect_macos_build", lambda session: None)
    reports = []

    def install_then_fail(*args, **kwargs):
        repair._DIAGNOSTICS.observe(facts())
        state["facts"] = facts("3.0.1", "1.14.1")
        state["unrunnable"] = final == "unrunnable"
        return 1

    monkeypatch.setattr(repair, "repair_environment", install_then_fail)
    monkeypatch.setattr(repair, "_complete_automatic_report", lambda *args: reports.append(args))
    assert repair.main(["--automatic-report"]) == 1
    details = reports[0][0].details
    assert details["initial_scipy_version"] == "1.15.3"
    assert details["final_scipy_version"] == ("1.14.1" if final == "installed" else "unknown")
    assert details["final_studio_version"] == ("3.0.1" if final == "installed" else "unknown")
    assert details["python_version"] == ("3.10.22" if final == "installed" else "unknown")


def test_versions_keep_before_after_and_native_architecture(session):
    session.details["cpu"] = "arm64"
    session.observe(facts())
    session.observe(facts("3.0.1", "1.14.1"))
    assert session.details["initial_studio_version"] == "2.8.1"
    assert session.details["initial_scipy_version"] == "1.15.3"
    assert session.details["final_scipy_version"] == "1.14.1"
    assert session.details["rosetta"] == "native"


def test_pip_chatter_stays_local_and_repeated_failure_is_shown_once(monkeypatch, session):
    error = "ImportError: scipy __thread_bss has a zero-fill type but offset is not zero"
    chatter = "Requirement already satisfied: package in /Users/private-name/env\n" * 4000

    class Child:
        stdout = io.StringIO(chatter + error + "\n" + error + "\n")

        def wait(self, timeout=None):
            return 1

    monkeypatch.setattr(repair.subprocess, "Popen", lambda *args, **kwargs: Child())
    console = io.StringIO()
    session.console_handler.setStream(console)
    session.command(["python", "-m", "pip", "install"], cwd=session.root)
    output = console.getvalue()
    assert "Requirement already satisfied" not in output
    assert output.count(error) == 1
    assert "Requirement already satisfied" in session.path.read_text(encoding="utf-8")
    assert "private-name" not in session.path.read_text(encoding="utf-8")
    assert session.details["failure_code"] == "scipy_macho"
    session.failure("setup_failed")
    assert session.details["failure_code"] == "scipy_macho"


@pytest.mark.parametrize("late_error, expected", [
    ("ImportError: a native graphics library could not load", "setup_failed"),
    ("ModuleNotFoundError: No module named 'graphics_dependency'", "missing_dependency"),
])
def test_new_setup_failure_does_not_reuse_or_replace_the_original_cause(
    monkeypatch, session, late_error, expected,
):
    session.failure("dependency_mismatch")
    session.details.update(dependency_check="passed", engine_import="failed")
    monkeypatch.setattr(repair, "_DIAGNOSTICS", session)

    def fail_after_install(*args, **kwargs):
        session.observe(facts("3.0.1", "1.14.1"))
        session.observe(late_error)
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(repair, "_command", fail_after_install)
    assert not repair._run_setup(session.root)
    assert session.details["initial_failure_code"] == "dependency_mismatch"
    assert session.details["failure_code"] == expected
    assert session.details["final_scipy_version"] == "1.14.1"
    assert session.details["dependency_check"] == "unknown"
    assert session.details["engine_import"] == "unknown"


@pytest.mark.parametrize("engine_exit, expected", [(0, "none"), (1, "engine_import_failed")])
def test_new_engine_check_uses_its_own_failure_and_preserves_the_initial_cause(
    monkeypatch, session, engine_exit, expected,
):
    session.failure("dependency_mismatch")
    monkeypatch.setattr(repair, "_DIAGNOSTICS", session)
    results = iter((0, engine_exit))
    monkeypatch.setattr(repair, "_run", lambda *args, **kwargs: next(results))
    assert repair._check_environment(session.root, "python") == (engine_exit == 0)
    assert session.details["initial_failure_code"] == "dependency_mismatch"
    assert session.details["failure_code"] == expected
    assert session.details["dependency_check"] == "passed"
    assert session.details["engine_import"] == ("passed" if engine_exit == 0 else "failed")


@pytest.mark.parametrize("status", ["submitted", "queued", "offline", "disabled", "rejected"])
def test_completion_persists_summary_before_network_and_reports_own_delivery(
    monkeypatch, tmp_path, status,
):
    module = repair._workflow_module(ROOT)
    calls = []

    class Reporter:
        def queue(self, report):
            assert list(tmp_path.rglob("completion.json"))
            assert list(tmp_path.rglob("completion.txt"))
            calls.append(("queue", report["report_id"]))
            return status != "disabled"

        def deliver(self):
            calls.append(("deliver",))
            if status == "offline":
                raise module.WorkflowReportError("The reporting service is unreachable.")
            return 1  # Could be a different queued report; never use this as our receipt.

        def status(self, report_id):
            assert report_id == calls[0][1]
            return "queued" if status == "offline" else status

    monkeypatch.setattr(module, "WorkflowReporter", Reporter)
    monkeypatch.setattr(repair, "_workflow_module", lambda root: module)
    monkeypatch.setattr(repair.platform, "mac_ver", lambda: ("27.0", (), "arm64"))
    monkeypatch.setattr(repair, "_native_dialog", lambda *args: "Close")
    diagnostics = repair._Diagnostics(tmp_path)
    diagnostics.automatic_report = True
    diagnostics.details["cpu"] = "arm64"
    diagnostics.observe(facts())
    diagnostics.observe("ImportError: scipy __thread_bss offset is not zero")
    diagnostics.observe(facts("3.0.1", "1.14.1"))
    diagnostics.close()
    messages = []
    monkeypatch.setattr(
        repair._LOGGER, "info", lambda message, *args: messages.append(message % args),
    )
    repair._complete_automatic_report(diagnostics, 0, "3.0.1")
    report = json.loads(diagnostics.path.with_name("completion.json").read_text())
    assert report["outcome"] == "success"
    assert report["details"]["initial_failure_code"] == "scipy_macho"
    assert report["details"]["failure_code"] == "none"
    summary = diagnostics.path.with_name("completion.txt").read_text(encoding="utf-8")
    assert len(summary) < 6000 and "Requirement already" not in summary
    repair._complete_automatic_report(diagnostics, 0, "3.0.1")
    assert calls[0][1] == calls[2][1]  # Same completion keeps its immutable identity.
    output = "\n".join(messages)
    assert ("Completion report submitted" in output) == (status == "submitted")


@pytest.mark.parametrize("code", [0, 1, 130])
def test_automatic_entry_reports_failure_success_and_cancellation_without_manual_flow(
    monkeypatch, tmp_path, code,
):
    monkeypatch.setattr(repair, "__file__", str(tmp_path / "Repair Mac.py"))
    monkeypatch.setattr(repair, "_collect_macos_build", lambda session: None)
    calls = []

    def operation(*args, **kwargs):
        if code == 130:
            raise KeyboardInterrupt
        return code

    def no_manual(*args):
        pytest.fail("Automatic completion must not request manual submission")

    monkeypatch.setattr(repair, "repair_environment", operation)
    monkeypatch.setattr(repair, "_offer_report", no_manual)
    monkeypatch.setattr(repair, "_complete_automatic_report", lambda *args: calls.append(args))
    assert repair.main(["--automatic-report"]) == code
    assert len(calls) == 1 and calls[0][1] == code
    assert calls[0][0].stream.closed


def test_new_entry_point_runs_shared_helper_with_automatic_reporting(monkeypatch):
    calls = []
    original = runpy.run_path
    monkeypatch.setattr(runpy, "run_path", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr("sys.argv", ["Repair Mac 2.py", "--check"])
    original(str(ROOT / "Repair Mac 2.py"), run_name="__main__")
    assert calls[0][0] == (str(ROOT / "Repair Mac.py"),)
    assert repair.sys.argv[1:] == ["--automatic-report", "--check"]


def test_detached_completion_keeps_auto_mode_and_final_result(monkeypatch, tmp_path):
    diagnostics = repair._Diagnostics(tmp_path)
    log = diagnostics.path
    diagnostics.close()
    job = tmp_path / ".fpvs-macos/pycharm-repair" / ("c" * 32 + ".log")
    job.parent.mkdir()
    job.write_text("IDE finished")
    job.with_suffix(".claim").write_text("123")
    job.with_suffix(".result.json").write_text(json.dumps({"success": False}))
    state = log.with_name("continuation.json")
    state.write_text(json.dumps({
        "log": str(log), "job_log": str(job), "app_version": "3.0.1",
        "automatic_report": True, "details": {"initial_scipy_version": "1.15.3"},
    }))
    calls = []
    monkeypatch.setattr(repair, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(repair, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(repair, "_complete_automatic_report", lambda *args: calls.append(args))
    python = tmp_path / ".venv3.10/bin/python"
    python.parent.mkdir(parents=True)
    python.touch()
    fake_metadata_process(monkeypatch, {"facts": facts("3.0.1", "1.14.1")})
    assert repair._finish_diagnostics(tmp_path, state) == 1
    assert calls[0][0].details["pycharm_configuration"] == "failed"
    assert calls[0][0].details["initial_scipy_version"] == "1.15.3"
    assert calls[0][0].details["final_scipy_version"] == "1.14.1"
    assert calls[0][1] == 1


@pytest.mark.parametrize("success", [True, False])
@pytest.mark.parametrize("summary_saved", [True, False])
def test_detached_reporting_failure_keeps_repair_outcome_and_never_offers_manual_submission(
    monkeypatch, tmp_path, success, summary_saved,
):
    diagnostics = repair._Diagnostics(tmp_path)
    log = diagnostics.path
    diagnostics.close()
    job = tmp_path / ".fpvs-macos/pycharm-repair" / ("d" * 32 + ".log")
    job.parent.mkdir()
    job.write_text("IDE finished")
    job.with_suffix(".claim").write_text("123")
    job.with_suffix(".result.json").write_text(json.dumps({"success": success}))
    state = log.with_name("continuation.json")
    state.write_text(json.dumps({
        "log": str(log), "job_log": str(job), "app_version": "3.0.1",
        "automatic_report": True, "details": {},
    }))

    def fail_reporting(session, code, version):
        if summary_saved:
            session.path.with_name("completion.txt").write_text("Retained completion summary")
            raise ValueError("Invalid reporting origin")
        raise OSError("Could not persist completion")

    def no_manual(*args):
        pytest.fail("Automatic delivery errors must not offer manual browser submission")

    dialogs = []
    monkeypatch.setattr(repair, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(repair, "__file__", str(tmp_path / "Repair Mac.py"))
    monkeypatch.setattr(repair, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(repair, "_snapshot_environment", lambda *args: None)
    monkeypatch.setattr(repair, "_complete_automatic_report", fail_reporting)
    monkeypatch.setattr(repair, "_offer_report", no_manual)
    monkeypatch.setattr(repair, "_native_dialog", lambda *args: dialogs.append(args) or "Close")
    assert repair.main(["--finish-diagnostics", str(state)]) == (0 if success else 1)
    assert len(dialogs) == 1 and dialogs[0][1] == ("Close",)
    message = dialogs[0][0]
    assert ("Repair completed successfully." in message) == success
    assert ("could not be confirmed" in message) == summary_saved
    assert ("could not be saved or sent" in message) != summary_saved
