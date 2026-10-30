"""Visible, isolated coverage for action discovery and its existing command routes."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QKeySequence, QPalette
from PySide6.QtWidgets import QAbstractButton, QApplication, QMessageBox
from tests.gui.helpers import assert_visible_children_within_parent, open_created_project

from fpvs_studio.gui.action_palette import ActionEntry, ActionPaletteDialog


def _visible_rows(dialog):
    return [
        dialog.results.topLevelItem(index)
        for index in range(dialog.results.topLevelItemCount())
        if not dialog.results.topLevelItem(index).isHidden()
    ]


def _open_palette(qtbot, entries):
    dialog = ActionPaletteDialog(entries)
    qtbot.addWidget(dialog)
    dialog.open()
    QApplication.processEvents()
    return dialog


def test_search_matches_all_tokens_across_action_location_and_keywords(qtbot):
    bundle = QAction("Project Bundle...")
    settings = QAction("Settings...")
    dialog = _open_palette(qtbot, [
        ActionEntry(bundle, "File > Import", keywords="portable experiment"),
        ActionEntry(settings, "File", keywords="preferences"),
    ])

    dialog.search_edit.setText("  IMPORT\tportable  bUnDlE ")
    rows = _visible_rows(dialog)
    assert len(rows) == 1
    assert rows[0].text(0) == "Project Bundle"
    assert rows[0].text(1) == "File > Import"
    assert "1" in dialog.result_count_label.text()

    dialog.search_edit.setText("import preferences")
    assert not _visible_rows(dialog)
    assert dialog.empty_label.isVisible()
    assert dialog.empty_label.text()
    assert not dialog.open_button.isEnabled()

    dialog.search_edit.clear()
    assert len(_visible_rows(dialog)) == 2
    assert not dialog.empty_label.isVisible()


def test_label_override_is_searchable_and_preserves_original_action(qtbot):
    action = QAction("Project Bundle...")
    triggered = []
    action.triggered.connect(lambda: triggered.append(True))
    dialog = _open_palette(qtbot, [
        ActionEntry(action, "File > Export", label="Export portable experiment"),
    ])
    dialog.search_edit.setText("portable")
    assert _visible_rows(dialog)[0].text(0) == "Export portable experiment"
    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Return)
    QApplication.processEvents()
    assert triggered == [True]
    assert action.text() == "Project Bundle..."
    assert not dialog.isVisible()


def test_disabled_action_stays_discoverable_and_cannot_dispatch(qtbot):
    action = QAction("Update Project Version...")
    action.setEnabled(False)
    triggered = []
    action.triggered.connect(lambda: triggered.append(True))
    dialog = _open_palette(qtbot, [ActionEntry(action, "File", keywords="update")])

    assert len(_visible_rows(dialog)) == 1
    assert not dialog.open_button.isEnabled()
    assert "unavailable" in dialog.result_count_label.text().casefold()
    assert "unavailable" in _visible_rows(dialog)[0].toolTip(0).casefold()
    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Return)
    assert triggered == []
    assert dialog.isVisible()

    action.setEnabled(True)
    QApplication.processEvents()
    assert dialog.open_button.isEnabled()
    qtbot.mouseClick(dialog.open_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert triggered == [True]
    assert not dialog.isVisible()


def test_action_changes_refresh_results_and_hidden_actions_stay_hidden(qtbot):
    action = QAction("Old name")
    hidden = QAction("Hidden command")
    hidden.setVisible(False)
    dialog = _open_palette(qtbot, [ActionEntry(action, "View"), ActionEntry(hidden, "View")])

    assert len(_visible_rows(dialog)) == 1
    action.setText("New name")
    action.setShortcut(QKeySequence("Ctrl+Alt+N"))
    QApplication.processEvents()
    row = _visible_rows(dialog)[0]
    assert row.text(0) == "New name"
    assert row.text(2) == action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)

    dialog.search_edit.setText("new")
    action.setVisible(False)
    QApplication.processEvents()
    assert not _visible_rows(dialog)
    assert dialog.empty_label.isVisible()
    action.setVisible(True)
    QApplication.processEvents()
    assert len(_visible_rows(dialog)) == 1


def test_closed_palette_defers_action_updates_and_reopens_with_current_state(qtbot, monkeypatch):
    action = QAction("Old name")
    hidden = QAction("Hidden command")
    dialog = _open_palette(qtbot, [ActionEntry(action, "View"), ActionEntry(hidden, "View")])
    dialog.search_edit.setText("old")
    dialog.reject()
    refreshes = []
    original_refresh = dialog._refresh_results

    def refresh(*args):
        refreshes.append(True)
        original_refresh(*args)

    monkeypatch.setattr(dialog, "_refresh_results", refresh)
    action.setEnabled(False)
    action.setText("New name")
    action.setShortcut(QKeySequence("Ctrl+Alt+N"))
    hidden.setVisible(False)
    QApplication.processEvents()
    assert refreshes == []

    dialog.open()
    QApplication.processEvents()
    assert refreshes == [True]
    assert dialog.search_edit.text() == ""
    rows = _visible_rows(dialog)
    assert len(rows) == 1
    assert rows[0].text(0) == "New name"
    assert rows[0].text(2) == action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
    assert rows[0].isDisabled()
    assert not dialog.open_button.isEnabled()


def test_search_arrow_keys_choose_command_and_enter_dispatches_once(qtbot):
    actions = [QAction("Alpha command"), QAction("Beta command")]
    triggered = []
    for action in actions:
        action.triggered.connect(lambda checked=False, value=action: triggered.append(value.text()))
    dialog = _open_palette(qtbot, [ActionEntry(action, "View") for action in actions])
    rows = _visible_rows(dialog)
    dialog.search_edit.setFocus()

    assert dialog.results.currentItem() is rows[0]
    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Down)
    assert dialog.results.currentItem() is rows[1]
    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Up)
    assert dialog.results.currentItem() is rows[0]
    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Down)
    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Return)
    QApplication.processEvents()

    assert triggered == [rows[1].text(0)]
    assert not dialog.isVisible()


def test_escape_dismisses_without_dispatch(qtbot):
    action = QAction("Settings...")
    triggered = []
    action.triggered.connect(lambda: triggered.append(True))
    dialog = _open_palette(qtbot, [ActionEntry(action, "File")])

    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Escape)
    QApplication.processEvents()
    assert not dialog.isVisible()
    assert triggered == []


def test_action_refresh_preserves_selected_command(qtbot):
    actions = [QAction("First"), QAction("Second"), QAction("Third")]
    dialog = _open_palette(qtbot, [ActionEntry(action, "View") for action in actions])
    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Down)
    assert dialog.results.currentItem().text(0) == "Second"

    actions[0].setText("First renamed")
    QApplication.processEvents()
    assert dialog.results.currentItem().text(0) == "Second"

    actions[1].setEnabled(False)
    QApplication.processEvents()
    assert dialog.results.currentItem().text(0) != "Second"
    assert dialog.open_button.isEnabled()


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("size", [(600, 400), (680, 460)])
def test_palette_long_content_and_empty_state_fit_documented_sizes(qtbot, qapp, dark, size):
    original_palette = qapp.palette()
    qapp.setPalette(QPalette(QColor("#202124" if dark else "#f4f7fb")))
    try:
        label = "Export completed project configuration for a multi-condition visual study"
        category = "File > Export"
        action = QAction(label)
        action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        dialog = _open_palette(qtbot, [ActionEntry(action, category)])
        assert dialog.minimumSize().toTuple() == (600, 400)
        assert dialog.size().toTuple() == (680, 460)
        dialog.resize(*size)
        QApplication.processEvents()

        assert dialog.size().toTuple() == size
        assert_visible_children_within_parent(dialog)
        row = _visible_rows(dialog)[0]
        assert label in row.toolTip(0)
        assert dialog.results.textElideMode() == Qt.TextElideMode.ElideRight
        assert dialog.results.horizontalScrollBar().maximum() == 0
        for widget in (dialog.result_count_label, dialog.open_button):
            assert widget.width() >= widget.fontMetrics().horizontalAdvance(widget.text())

        dialog.search_edit.setText("no such command")
        QApplication.processEvents()
        assert dialog.empty_label.isVisible()
        assert_visible_children_within_parent(dialog)
        assert dialog.empty_label.height() >= dialog.empty_label.heightForWidth(
            dialog.empty_label.width()
        )
    finally:
        qapp.setPalette(original_palette)


def test_file_menu_palette_is_nonblocking_lazy_and_dispatches_existing_settings(
    qtbot, controller, tmp_path, monkeypatch,
):
    _, window = open_created_project(controller, qtbot, tmp_path, "Discover commands")
    requested = []
    monkeypatch.setattr(window, "_on_request_settings", lambda: requested.append(True))
    assert window._setup_wizard_page is None
    assert window.find_action_action.shortcut() == QKeySequence("Ctrl+F")
    assert window.file_menu.actions().count(window.find_action_action) == 1
    assert window.find_action_action not in window.view_menu.actions()
    assert window.findChild(QAbstractButton, "find_action_button") is None

    qtbot.mouseClick(
        window.menuBar(), Qt.MouseButton.LeftButton,
        pos=window.menuBar().actionGeometry(window.file_menu.menuAction()).center(),
    )
    QApplication.processEvents()
    assert window.file_menu.isVisible()
    qtbot.mouseClick(
        window.file_menu, Qt.MouseButton.LeftButton,
        pos=window.file_menu.actionGeometry(window.find_action_action).center(),
    )
    QApplication.processEvents()
    dialog = window._action_palette
    assert dialog is not None
    assert dialog.isVisible()
    assert dialog.windowModality() == Qt.WindowModality.WindowModal
    assert window._setup_wizard_page is None
    assert window.main_stack.currentWidget() is window.home_page

    window.show_action_palette()
    assert window._action_palette is dialog
    dialog.search_edit.setText("settings")
    assert len(_visible_rows(dialog)) == 1
    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Return)
    QApplication.processEvents()
    assert requested == [True]
    assert not dialog.isVisible()
    assert window._setup_wizard_page is None

    window.raise_()
    window.activateWindow()
    QApplication.processEvents()
    qtbot.keyClick(
        window.home_page, Qt.Key.Key_F,
        Qt.KeyboardModifier.ControlModifier,
    )
    QApplication.processEvents()
    assert window._action_palette.isVisible()
    assert window._setup_wizard_page is None
    qtbot.keyClick(window._action_palette.search_edit, Qt.Key.Key_Escape)
    assert requested == [True]


def test_main_window_catalog_distinguishes_import_export_and_excludes_launch_publish(
    qtbot, controller, tmp_path,
):
    _, window = open_created_project(controller, qtbot, tmp_path, "Command locations")
    entries = window._action_palette_entries()
    by_action = {entry.action: entry for entry in entries}
    assert "import" in by_action[window.import_project_bundle_action].category.casefold()
    assert "export" in by_action[window.export_project_bundle_action].category.casefold()
    assert "import" in by_action[window.import_project_config_action].category.casefold()
    assert "export" in by_action[window.export_project_config_action].category.casefold()
    assert window.settings_action in by_action
    assert window.save_project_action in by_action
    assert window.home_action in by_action
    assert window.setup_action in by_action
    assert window.launch_action not in by_action
    assert window.submit_library_action not in by_action
    assert window.publish_library_action not in by_action
    assert window._setup_wizard_page is None


def test_palette_navigation_reuses_setup_and_preserves_pending_edits(
    qtbot, controller, tmp_path, monkeypatch,
):
    _, window = open_created_project(controller, qtbot, tmp_path, "Palette navigation")
    window.show_action_palette()
    dialog = window._action_palette
    dialog.search_edit.setText("setup")
    assert len(_visible_rows(dialog)) == 1
    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Return)
    QApplication.processEvents()
    wizard = window._setup_wizard_page
    assert wizard is not None
    assert window.main_stack.currentWidget() is wizard

    window.show_setup_wizard(step_key="project", allow_step_jumps=True)
    description = wizard.project_overview_editor.project_description_edit
    description.setPlainText("Pending description entered through Setup.")
    window.show_action_palette()
    dialog.search_edit.setText("setup")
    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Return)
    QApplication.processEvents()
    assert window.main_stack.currentWidget() is wizard
    assert description.toPlainText() == "Pending description entered through Setup."

    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    window.show_action_palette()
    dialog.search_edit.setText("return overview")
    assert len(_visible_rows(dialog)) == 1
    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Return)
    QApplication.processEvents()
    assert window.main_stack.currentWidget() is window.home_page
    assert window.document.project.meta.description == "Pending description entered through Setup."
    assert window.document.dirty


def _activate_home_from_palette(qtbot, window):
    window.show_action_palette()
    dialog = window._action_palette
    assert dialog is not None and dialog.isVisible()
    dialog.search_edit.setText("return overview")
    assert len(_visible_rows(dialog)) == 1
    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Return)
    QApplication.processEvents()
    assert not dialog.isVisible()


@pytest.mark.parametrize("accept", [False, True])
def test_palette_home_keeps_incomplete_setup_confirmation(
    qtbot, controller, tmp_path, monkeypatch, accept,
):
    _, window = open_created_project(controller, qtbot, tmp_path, "Incomplete palette exit")
    window.show_setup_wizard(step_key="project", allow_step_jumps=True)
    wizard = window.setup_wizard_page
    prompts = []

    def confirm(_parent, title, message, *_args):
        prompts.append((title, message))
        return QMessageBox.StandardButton.Yes if accept else QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", confirm)
    _activate_home_from_palette(qtbot, window)

    assert len(prompts) == 1
    assert prompts[0][0] == "Setup Incomplete"
    assert "not ready to launch" in prompts[0][1]
    assert window.main_stack.currentWidget() is (window.home_page if accept else wizard)


@pytest.mark.parametrize("accept", [False, True])
def test_palette_home_from_review_confirms_without_saving(
    qtbot, controller, tmp_path, monkeypatch, accept,
):
    _, window = open_created_project(controller, qtbot, tmp_path, "Review palette exit")
    window.document.update_project_name("Unsaved review name")
    window.show_setup_wizard(step_key="review", allow_step_jumps=True)
    wizard = window.setup_wizard_page
    assert wizard.step_stack.currentWidget() is wizard.review_step_surface
    prompts, saved = [], []
    monkeypatch.setattr(wizard, "is_launch_ready", lambda: True)
    monkeypatch.setattr(window.document, "save", lambda: saved.append(True))

    def confirm(_parent, title, message, *_args):
        prompts.append((title, message))
        return QMessageBox.StandardButton.Yes if accept else QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", confirm)
    _activate_home_from_palette(qtbot, window)

    assert len(prompts) == 1
    assert prompts[0][0] == "Unsaved Changes"
    assert "without saving to disk" in prompts[0][1]
    assert saved == []
    assert window.document.dirty
    assert window.document.project.meta.name == "Unsaved review name"
    assert window.main_stack.currentWidget() is (window.home_page if accept else wizard)


@pytest.mark.parametrize("surface,size", [("home", (760, 520)), ("setup", (1120, 820))])
def test_menu_save_feedback_fits_home_and_setup(
    qtbot, controller, tmp_path, surface, size,
):
    _, window = open_created_project(controller, qtbot, tmp_path, "Command bar layout")
    if surface == "setup":
        window.show_setup_wizard(step_key="project", allow_step_jumps=True)
    else:
        window.show_home()
    window.resize(*size)
    window.show()

    for state, text in (
        ("ready", "Saved"),
        ("warning", "Unsaved changes"),
        ("error", "Save blocked"),
        ("error", "Save failed"),
        ("ready", "Saved"),
    ):
        window._set_save_feedback(state, text, "Full save state explanation")
        QApplication.processEvents()
        corner = window.save_state_label
        assert window.menuBar().cornerWidget() is corner
        assert window.size().toTuple() == size
        if state == "ready":
            assert not corner.isVisible()
            continue
        assert window.save_state_label.isVisible()
        assert window.menuBar().rect().contains(corner.geometry())
        assert window.save_state_label.width() >= window.save_state_label.sizeHint().width()
        menu_right = max(
            window.menuBar().actionGeometry(action).right()
            for action in window.menuBar().actions()
        )
        assert menu_right < corner.geometry().left()


def _set_busy(monkeypatch, window, state):
    if state == "launch":
        monkeypatch.setattr(window, "is_launch_busy", lambda: True)
    elif state == "launch-after-seed":
        monkeypatch.setattr(window, "_launch_after_session_seed_ready", True)
    elif state == "bundle-export":
        monkeypatch.setattr(window, "_active_bundle_export_task", object())
    elif state == "bundle-import":
        monkeypatch.setattr(window, "_bundle_import_processing_active", True)
    elif state == "condition-images":
        monkeypatch.setattr(window.setup_wizard_page, "_condition_image_task_active", lambda: True)
    elif state == "condition-import":
        monkeypatch.setattr(window.setup_wizard_page.condition_setup_step, "is_busy", lambda: True)
    else:
        monkeypatch.setattr(window.image_resizer_page, "_active_task", object())


@pytest.mark.parametrize("state", [
    "launch", "launch-after-seed", "bundle-export", "bundle-import",
    "condition-images", "condition-import", "resizer",
])
def test_main_window_busy_guards_block_opening_and_late_dispatch(
    qtbot, controller, tmp_path, monkeypatch, state,
):
    _, window = open_created_project(controller, qtbot, tmp_path, "Busy command protection")
    requested = []
    monkeypatch.setattr(window, "_on_request_settings", lambda: requested.append(True))
    with monkeypatch.context() as busy:
        _set_busy(busy, window, state)
        window.show_action_palette()
        assert window._action_palette is None or not window._action_palette.isVisible()
        assert window.statusBar().isVisible()
        assert "current operation" in window.statusBar().currentMessage()

    window.show_action_palette()
    dialog = window._action_palette
    assert dialog is not None and dialog.isVisible()
    dialog.search_edit.setText("settings")
    assert dialog.open_button.isEnabled()
    with monkeypatch.context() as busy:
        _set_busy(busy, window, state)
        qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Return)
        QApplication.processEvents()
        assert requested == []
        assert not dialog.isVisible()
        assert window.statusBar().isVisible()
        assert "current operation" in window.statusBar().currentMessage()
