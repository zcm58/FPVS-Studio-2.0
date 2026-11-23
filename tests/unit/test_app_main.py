"""Application entry-point tests."""

from __future__ import annotations

import logging
import sys
import threading
import types

from fpvs_studio.app.main import main
from fpvs_studio.support import diagnostics


def test_main_lazily_delegates_to_gui_runner(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("fpvs_studio.support.diagnostics.support_directory", lambda: tmp_path)
    captures: dict[str, object] = {}
    fake_module = types.ModuleType("fpvs_studio.gui.application")

    def _fake_run_gui_app(argv=None) -> int:
        captures["argv"] = argv
        return 7

    fake_module.run_gui_app = _fake_run_gui_app
    monkeypatch.setitem(sys.modules, "fpvs_studio.gui.application", fake_module)

    exit_code = main(["--demo"])

    assert exit_code == 7
    assert captures["argv"] == ["--demo"]


def test_main_can_start_when_optional_diagnostic_thread_cannot_start(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(diagnostics, "support_directory", lambda: tmp_path)
    monkeypatch.setattr(diagnostics, "_active_logging", None)
    monkeypatch.setattr(diagnostics, "_logging_notice", "")
    logger = logging.getLogger("fpvs_studio")
    handlers, level = logger.handlers[:], logger.level
    process_hook, thread_hook = sys.excepthook, threading.excepthook
    # Restore the previous globals even if startup leaves a partially installed session.
    monkeypatch.setattr(logger, "handlers", handlers[:])
    monkeypatch.setattr(logger, "level", level)
    monkeypatch.setattr(sys, "excepthook", process_hook)
    monkeypatch.setattr(threading, "excepthook", thread_hook)
    thread_start = threading.Thread.start
    rejected_threads = []

    def fail_diagnostic_start(thread: threading.Thread) -> None:
        if thread.name == "fpvs-support-log":
            rejected_threads.append(thread)
            raise RuntimeError("can't start new thread")
        thread_start(thread)

    monkeypatch.setattr(threading.Thread, "start", fail_diagnostic_start)
    fake_module = types.ModuleType("fpvs_studio.gui.application")
    fake_module.run_gui_app = lambda argv=None: 7
    monkeypatch.setitem(sys.modules, "fpvs_studio.gui.application", fake_module)

    assert main(["--demo"]) == 7
    (worker,) = rejected_threads
    assert not worker.is_alive()
    assert diagnostics._active_logging is None
    assert sys.excepthook is process_hook
    assert threading.excepthook is thread_hook
    assert logger.handlers == handlers
    assert logger.level == level
    assert diagnostics._logging_notice == (
        "Persistent application logs are unavailable on this machine."
    )


def test_main_lazily_delegates_to_packaged_smoke(monkeypatch) -> None:
    captures: dict[str, object] = {}
    fake_module = types.ModuleType("fpvs_studio.app.packaged_smoke")

    def _fake_run_packaged_smoke(argv) -> int:
        captures["argv"] = argv
        return 3

    fake_module.run_packaged_smoke = _fake_run_packaged_smoke
    monkeypatch.setitem(sys.modules, "fpvs_studio.app.packaged_smoke", fake_module)

    exit_code = main(["--packaged-smoke-output", "report.json"])

    assert exit_code == 3
    assert captures["argv"] == ["--packaged-smoke-output", "report.json"]
