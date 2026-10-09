"""Qt warnings and isolated fatal capture without contacting real services."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QtMsgType

from fpvs_studio.gui import qt_diagnostics
from fpvs_studio.support.diagnostics import DiagnosticLogging, collect_diagnostics


def test_qt_settings_are_in_workspace_test_profile(_workspace_env):
    settings = QSettings(QSettings.IniFormat, QSettings.UserScope, "FPVS Studio", "FPVS Studio")
    assert Path(settings.fileName()).resolve().is_relative_to(_workspace_env.resolve())


def test_qt_warning_is_collected_and_redacted(tmp_path, monkeypatch):
    monkeypatch.setattr(qt_diagnostics, "_previous_handler", None)
    session = DiagnosticLogging(tmp_path)
    session.start()
    try:
        qt_diagnostics._qt_message(
            QtMsgType.QtWarningMsg, None, "Synthetic Qt warning token=private-value"
        )
    finally:
        session.close()
    text = collect_diagnostics(tmp_path)
    assert "Synthetic Qt warning" in text
    assert "WARNING" in text
    assert "private-value" not in text


def test_qt_fatal_records_breadcrumb_even_without_console(monkeypatch):
    messages = []
    monkeypatch.setattr(qt_diagnostics, "_previous_handler", None)
    monkeypatch.setattr(qt_diagnostics, "record_qt_fatal", messages.append)

    def no_console(*_args):
        raise OSError("Windowed executable has no stderr")

    monkeypatch.setattr(qt_diagnostics.os, "write", no_console)
    qt_diagnostics._qt_message(QtMsgType.QtFatalMsg, None, "Synthetic fatal Qt error")
    assert messages == ["Synthetic fatal Qt error"]


def test_install_keeps_previous_handler_and_is_idempotent(monkeypatch):
    installations = []
    forwarded = []
    monkeypatch.setattr(qt_diagnostics, "_installed", False)
    monkeypatch.setattr(qt_diagnostics, "_previous_handler", None)

    def install(handler):
        installations.append(handler)
        return lambda kind, context, message: forwarded.append(message)

    monkeypatch.setattr(qt_diagnostics, "qInstallMessageHandler", install)
    qt_diagnostics.install_qt_diagnostics()
    qt_diagnostics.install_qt_diagnostics()
    qt_diagnostics._qt_message(QtMsgType.QtWarningMsg, None, "Synthetic forwarded warning")
    assert len(installations) == 1
    assert forwarded == ["Synthetic forwarded warning"]


def test_native_abort_leaves_redacted_fatal_breadcrumb_and_trace(tmp_path):
    # Isolate the intentional fatal event from pytest's QApplication. This is part
    # of explicitly approved native Qt coverage, never the default non-Qt suite.
    script = f'''
from pathlib import Path
from fpvs_studio.support.diagnostics import DiagnosticLogging
session = DiagnosticLogging(Path({str(tmp_path)!r}), capture_native=True)
session.start()
assert session.ready.wait(2)
from fpvs_studio.gui.qt_diagnostics import install_qt_diagnostics
from PySide6.QtCore import qFatal
install_qt_diagnostics()
qFatal("Synthetic fatal capture token=private-test-value")
'''
    environment = os.environ.copy()
    environment.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run(
        [sys.executable, "-c", script], env=environment,
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert result.returncode != 0
    text = collect_diagnostics(tmp_path)
    assert "Qt fatal:" in text
    assert "private-test-value" not in text
    assert "record_qt_fatal" in text
