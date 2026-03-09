"""GUI-test fixtures that keep Qt runs headless and non-blocking."""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog, QMessageBox
import pytest

from fpvs_studio.gui.create_project_dialog import CreateProjectDialog


@pytest.fixture(autouse=True)
def _clear_fpvs_root_setting() -> None:
    """Reset app-level root-folder preference between GUI tests."""

    settings = QSettings(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        "FPVS Studio",
        "FPVS Studio",
    )
    settings.remove("paths/fpvs_root_dir")
    settings.sync()
    yield
    settings.remove("paths/fpvs_root_dir")
    settings.sync()


@pytest.fixture(autouse=True)
def _stub_modal_dialogs(monkeypatch) -> None:
    """Prevent GUI tests from opening real blocking dialogs."""

    monkeypatch.setattr(
        CreateProjectDialog,
        "exec",
        lambda self: int(CreateProjectDialog.DialogCode.Rejected),
    )
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args, **kwargs: "")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: ("", ""))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: int(QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )
