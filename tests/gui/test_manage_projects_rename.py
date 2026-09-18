"""Renaming through Manage Projects preserves files and live unsaved edits."""

import json

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QInputDialog, QPushButton
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import load_project_file
from fpvs_studio.gui.manage_projects_dialog import ManageProjectsDialog


def _dialog(qtbot, controller):
    dialog = ManageProjectsDialog(entries=controller.load_manageable_project_entries())
    qtbot.addWidget(dialog)
    dialog.rename_requested.connect(lambda root: controller._rename_managed_project(dialog, root))
    dialog.show()
    return dialog


def test_rename_updates_filtered_list_and_reopens_under_new_name(qtbot, controller, monkeypatch):
    scaffold = create_project(controller.load_fpvs_root_dir(), "Original name")
    create_project(controller.load_fpvs_root_dir(), "Another project")
    dialog = _dialog(qtbot, controller)
    dialog.filter_edit.setText("Original name")
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("Renamed project", True))
    dialog.rename_button.click()
    assert dialog.name_label.text() == "Renamed project"
    assert dialog.project_list.currentItem().text() == "Renamed project"
    assert dialog.filter_edit.text() == ""
    assert scaffold.project_root.is_dir()
    controller.open_project(scaffold.project_root)
    qtbot.addWidget(controller.main_window)
    assert controller.main_window.document.project.meta.name == "Renamed project"
    assert "Renamed project" in controller.main_window.windowTitle()


@pytest.mark.parametrize("dirty", [False, True])
def test_rename_open_project_preserves_unsaved_edits(qtbot, controller, monkeypatch, dirty):
    scaffold = create_project(controller.load_fpvs_root_dir(), "Open project")
    controller.open_project(scaffold.project_root)
    window = controller.main_window
    qtbot.addWidget(window)
    document = window.document
    old_description = document.project.meta.description
    if dirty:
        document.update_project_description("Unsaved description")
        document.update_project_name("Unsaved name")
    dialog = _dialog(qtbot, controller)
    assert dialog.rename_button.isEnabled()
    assert not dialog.delete_button.isEnabled()
    name = "Unsaved name" if dirty else "New project name"
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: (name, True))
    dialog.rename_button.click()
    saved = load_project_file(document.project_file_path)
    assert saved.meta.name == document.project.meta.name == name
    assert saved.meta.description == old_description
    assert document.dirty is dirty
    if dirty:
        assert document.project.meta.description == "Unsaved description"
    assert name in window.windowTitle()
    assert dialog.name_label.text() == name


@pytest.mark.parametrize("answer", [("Ignored", False), ("  ", True)])
def test_cancel_and_empty_name_leave_project_unchanged(qtbot, controller, monkeypatch, answer):
    scaffold = create_project(controller.load_fpvs_root_dir(), "Original")
    path = scaffold.project_root / "project.json"
    before = path.read_bytes()
    errors = []
    monkeypatch.setattr("fpvs_studio.gui.controller._show_error", lambda *args: errors.append(args))
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: answer)
    dialog = _dialog(qtbot, controller)
    dialog.rename_button.click()
    assert path.read_bytes() == before
    assert dialog.name_label.text() == "Original"
    assert bool(errors) is answer[1]


def test_failed_rename_keeps_open_document_and_disk(qtbot, controller, monkeypatch):
    scaffold = create_project(controller.load_fpvs_root_dir(), "Original")
    controller.open_project(scaffold.project_root)
    qtbot.addWidget(controller.main_window)
    document = controller.main_window.document
    before = document.project.model_dump()
    disk = document.project_file_path.read_bytes()
    errors = []
    monkeypatch.setattr("fpvs_studio.gui.controller._show_error", lambda *args: errors.append(args))
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ("Renamed", True))

    def fail_replace(*args):
        raise PermissionError("Read-only project")

    monkeypatch.setattr("fpvs_studio.core.project_service.atomic_text_write", fail_replace)
    dialog = _dialog(qtbot, controller)
    dialog.rename_button.click()
    assert errors
    assert document.project.model_dump() == before
    assert document.project_file_path.read_bytes() == disk
    assert not document.dirty


def test_rename_disabled_for_empty_filtered_and_invalid_projects(qtbot, controller):
    dialog = _dialog(qtbot, controller)
    assert not dialog.rename_button.isEnabled()
    root = controller.load_fpvs_root_dir() / "invalid"
    root.mkdir()
    (root / "project.json").write_text(json.dumps({"broken": True}))
    dialog.set_project_entries(controller.load_manageable_project_entries())
    assert not dialog.rename_button.isEnabled()
    create_project(controller.load_fpvs_root_dir(), "Valid")
    dialog.set_project_entries(controller.load_manageable_project_entries())
    dialog.filter_edit.setText("does not exist")
    assert not dialog.rename_button.isEnabled()


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_rename_action_fits_manage_projects_minimum(qtbot, qapp, controller, background):
    original = qapp.palette()
    palette = QPalette(original)
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    qapp.setPalette(palette)
    try:
        create_project(
            controller.load_fpvs_root_dir(),
            "Long experiment name comparing recognition across different stimulus categories",
        )
        dialog = _dialog(qtbot, controller)
        dialog.resize(860, 520)
        qtbot.waitUntil(lambda: dialog.isVisible())
        assert (dialog.width(), dialog.height()) == (860, 520)
        assert_visible_children_within_parent(dialog)
        for button in dialog.findChildren(QPushButton):
            if button.isVisible():
                assert button.width() >= button.fontMetrics().horizontalAdvance(button.text())
        label = dialog.name_label
        assert label.height() >= label.heightForWidth(label.width())
    finally:
        qapp.setPalette(original)
