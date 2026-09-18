"""Visible, isolated checks for project loading and authoring save feedback."""

from threading import Event

import pytest
from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QColor, QKeySequence, QPalette
from PySide6.QtWidgets import QApplication, QPushButton
from tests.gui.helpers import _open_created_project, assert_visible_children_within_parent

from fpvs_studio.gui import document as document_module
from fpvs_studio.gui.document import ProjectDocument


@pytest.mark.parametrize("outcome", ["success", "cancel", "error"])
def test_project_open_keeps_ui_responsive_and_preserves_current_on_failure(
    qtbot, qapp, controller, tmp_path, monkeypatch, outcome,
):
    _, previous = _open_created_project(controller, qtbot, tmp_path, "Current project")
    incoming = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Incoming project")
    entered, release = Event(), Event()
    threads, errors, ticks = [], [], []
    original = document_module.load_project_file

    def delayed_load(path):
        threads.append(QThread.currentThread())
        entered.set()
        assert release.wait(5), "Project reading blocked the GUI thread"
        if outcome == "error":
            raise ValueError("The selected project file is damaged.")
        return original(path)

    monkeypatch.setattr(document_module, "load_project_file", delayed_load)
    monkeypatch.setattr("fpvs_studio.gui.controller._show_error", lambda *args: errors.append(args))
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start()
    try:
        controller.open_recent_project(str(incoming.project_root))
        qtbot.waitUntil(entered.is_set)
        ticks.clear()
        qtbot.waitUntil(lambda: bool(ticks))
        assert controller.main_window is previous
        assert threads == [threads[0]] and threads[0] != qapp.thread()
        dialog = controller._project_open_dialog
        assert dialog.isVisible()
        assert "Opening" in dialog.labelText()
        if outcome == "cancel":
            qtbot.mouseClick(dialog.findChild(QPushButton), Qt.MouseButton.LeftButton)
            assert controller._project_open_job.cancel_event.is_set()
        release.set()
        qtbot.waitUntil(lambda: controller._project_open_job is None)
        if outcome == "success":
            window = controller.main_window
            qtbot.addWidget(window)
            assert window is not previous
            assert window.document.project_root == incoming.project_root
            assert window.document.thread() == qapp.thread()
            assert not errors
        else:
            assert controller.main_window is previous
            assert bool(errors) == (outcome == "error")
        assert controller._project_open_dialog is None
    finally:
        release.set()
        timer.stop()
        qtbot.waitUntil(lambda: getattr(controller, "_project_open_job", None) is None)


@pytest.mark.parametrize("dark", [False, True])
def test_save_feedback_and_shortcut_work_on_home_and_setup(
    qtbot, qapp, controller, tmp_path, monkeypatch, dark,
):
    palette = qapp.palette()
    qapp.setPalette(QPalette(QColor("#202124" if dark else "#f4f7fb")))
    try:
        _, window = _open_created_project(controller, qtbot, tmp_path, "Save feedback")
        window.show()
        badge = window.save_state_label
        assert window.save_project_action in window.file_menu.actions()
        assert window.save_project_action.shortcut() == QKeySequence(QKeySequence.StandardKey.Save)
        assert badge.text() == "Saved"
        assert badge.isVisible()
        window.show_setup_wizard(step_key="project", allow_step_jumps=True)
        window.raise_()
        window.activateWindow()
        QApplication.processEvents()
        description = window.setup_wizard_page.project_overview_editor.project_description_edit
        description.setFocus()
        qtbot.keyClicks(description, "A new study description.")
        assert badge.text() == "Unsaved changes"
        QApplication.processEvents()
        assert badge.width() >= badge.sizeHint().width()
        assert badge.geometry().right() < window.menuBar().width()
        qtbot.keyClick(description, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
        QApplication.processEvents()
        assert not window.document.dirty
        assert window.document.project.meta.description.endswith("A new study description.")
        assert badge.text() == "Saved"

        original_flush = window.flush_pending_edits
        monkeypatch.setattr(window, "flush_pending_edits", lambda: False)
        assert not window.save_project()
        assert badge.text() == "Save blocked"
        QApplication.processEvents()
        assert badge.width() >= badge.sizeHint().width()
        assert badge.geometry().right() < window.menuBar().width()
        monkeypatch.setattr(window, "flush_pending_edits", original_flush)
        window.document.update_project_name("An edited study")
        assert badge.text() == "Unsaved changes"
        original_save = window.document.save
        errors = []
        monkeypatch.setattr(
            "fpvs_studio.gui.main_window._show_error_dialog", lambda *a: errors.append(a),
        )

        def fail_save():
            raise OSError("Disk full")

        monkeypatch.setattr(window.document, "save", fail_save)
        assert not window.save_project()
        assert window.document.dirty
        assert badge.text() == "Save failed"
        QApplication.processEvents()
        assert badge.width() >= badge.sizeHint().width()
        assert badge.geometry().right() < window.menuBar().width()
        assert "Disk full" in badge.toolTip()
        assert errors
        monkeypatch.setattr(window.document, "save", original_save)
        assert window.save_project()
        window.show_home()
        QApplication.processEvents()
        assert badge.text() == "Saved"
        assert badge.isVisible()
        assert badge.width() >= badge.fontMetrics().horizontalAdvance(badge.text())
        assert badge.geometry().right() <= window.menuBar().width()
    finally:
        qapp.setPalette(palette)


@pytest.mark.parametrize("field", ["project", "condition"])
def test_save_shortcut_commits_the_focused_name(qtbot, controller, tmp_path, field):
    _, window = _open_created_project(controller, qtbot, tmp_path, "Name editing")
    condition_id = window.document.create_condition(name="Original condition")
    window.save_project()
    window.show_setup_wizard(
        step_key="project" if field == "project" else "conditions", allow_step_jumps=True,
    )
    window.raise_()
    window.activateWindow()
    QApplication.processEvents()
    wizard = window.setup_wizard_page
    edit = (wizard.project_overview_editor.project_name_edit if field == "project"
            else wizard.condition_setup_step.condition_name_edit)
    edit.setFocus()
    edit.selectAll()
    qtbot.keyClicks(edit, "A revised name")
    assert window.save_state_label.text() == "Unsaved changes"
    qtbot.keyClick(edit, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    QApplication.processEvents()
    actual = (window.document.project.meta.name if field == "project"
              else window.document.get_condition(condition_id).name)
    assert actual == "A revised name"
    assert not window.document.dirty
    assert window.save_state_label.text() == "Saved"


@pytest.mark.parametrize("dark", [False, True])
def test_home_long_project_identity_fits_and_preserves_full_name(
    qtbot, qapp, controller, tmp_path, dark,
):
    palette = qapp.palette()
    qapp.setPalette(QPalette(QColor("#202124" if dark else "#f4f7fb")))
    try:
        _, window = _open_created_project(controller, qtbot, tmp_path, "Long identity")
        name = (
            "Visual Categorization and Attentional Processing — Counterbalanced Session " * 3
        ).strip()
        window.document.update_project_name(name)
        window.document.update_project_description(
            "Compare face and object categorization across repeated participant visits "
            "with counterbalanced visual conditions and condition-specific instructions."
        )
        window.show_home()
        window.resize(1120, 720)
        window.show()
        QApplication.processEvents()
        assert window.size().width() == 1120
        assert window.size().height() == 720
        header = window.home_page.current_project_header
        assert header.width() >= header.fontMetrics().horizontalAdvance(header.text())
        assert header.toolTip() == name.strip()
        assert header.accessibleDescription() == name.strip()
        assert_visible_children_within_parent(window.home_page)
        window.document.update_project_name("Brief title")
        QApplication.processEvents()
        assert header.text() == "Brief title"
    finally:
        qapp.setPalette(palette)


def test_canceled_project_read_cannot_replace_a_later_selection(
    qtbot, controller, tmp_path, monkeypatch,
):
    _, previous = _open_created_project(controller, qtbot, tmp_path, "Keep current")
    first = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Slow selection")
    second = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Latest selection")
    entered, release = Event(), Event()
    original = document_module.load_project_file

    def delayed_first(path):
        if path.parent == first.project_root:
            entered.set()
            assert release.wait(5)
        return original(path)

    monkeypatch.setattr(document_module, "load_project_file", delayed_first)
    controller.open_recent_project(str(first.project_root))
    first_job = controller._project_open_job
    try:
        qtbot.waitUntil(entered.is_set)
        controller._project_open_dialog.cancel()
        controller._project_open_dialog.canceled.emit()
        controller.open_recent_project(str(second.project_root))
        qtbot.waitUntil(lambda: controller.main_window is not previous)
        current = controller.main_window
        qtbot.addWidget(current)
        assert current.document.project_root == second.project_root
        release.set()
        qtbot.waitUntil(lambda: not first_job.is_running)
        assert controller.main_window is current
    finally:
        release.set()
        qtbot.waitUntil(lambda: not first_job.is_running)
