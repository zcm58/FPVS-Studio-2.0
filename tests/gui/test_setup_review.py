"""Focused GUI workflow tests split from the former layout dashboard suite."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMessageBox,
)
from tests.gui.helpers import (
    _open_created_project,
    _prepare_compile_ready_project,
    _write_image_directory,
    assert_visible_children_within_parent,
)

from fpvs_studio.gui.controller import StudioController


def test_setup_wizard_review_summarizes_actual_settings_and_supports_editing(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Review Checklist Project")
    guide = window.setup_wizard_page
    guide.project_overview_editor.project_description_edit.setPlainText(
        "Review checklist project description."
    )
    guide.project_overview_editor.project_name_edit.setText(
        "Longitudinal face and object discrimination with contrast modulation and response tracking"
    )
    guide.flush_pending_edits()

    for index, condition_name in enumerate(("Faces", "Objects"), start=1):
        window.conditions_page._add_condition()
        condition_id = window.conditions_page.selected_condition_id()
        assert condition_id is not None
        window.document.update_condition(
            condition_id,
            name=condition_name,
            trigger_code=index,
            oddball_cycle_repeats_per_sequence=144,
        )
        window.document.import_condition_stimulus_folder(
            condition_id,
            role="base",
            source_dir=_write_image_directory(tmp_path / f"{condition_name}-base"),
        )
        window.document.import_condition_stimulus_folder(
            condition_id,
            role="oddball",
            source_dir=_write_image_directory(tmp_path / f"{condition_name}-oddball"),
        )

    guide.session_structure_editor.block_count_spin.setValue(2)
    guide.fixation_settings_editor.fixation_enabled_checkbox.setChecked(True)
    guide.fixation_settings_editor.fixation_accuracy_checkbox.setChecked(True)
    guide.fixation_settings_editor._set_response_key("g")
    window.main_stack.setCurrentWidget(guide)
    guide.open_wizard(step_key="review")
    QApplication.processEvents()
    assert guide.step_stack.currentWidget() is guide.review_step_surface
    window.resize(1120, 720)
    QApplication.processEvents()
    review_card = guide.review_card
    label_text = "\n".join(label.text() for label in review_card.findChildren(QLabel))
    assert "Review Your Experiment" in label_text
    assert "2 conditions" in label_text
    assert "2 repeats per condition" in label_text
    assert "Accuracy tracking: On" in label_text
    assert "Response: G within" in label_text
    assert "Participant tutorial: On" in label_text
    assert "Task flow: 0 pre-condition, 0 post-condition bindings" in label_text
    assert "Display verification required" in label_text
    assert not [
        label
        for label in review_card.findChildren(QLabel)
        if label.property("reviewCheckIcon") == "true"
    ]
    assert not any(item.edit_button.isVisible() for item in guide._review_summary_widgets)
    assert not any(item.fixation_edit_button.isVisible() for item in guide._review_summary_widgets)
    assert_visible_children_within_parent(review_card)

    guide.open_wizard(step_key="review", allow_step_jumps=True)
    QApplication.processEvents()
    assert_visible_children_within_parent(guide.review_step_surface)
    assert guide.shell.page_container.scroll_area.verticalScrollBar().maximum() == 0
    for label in review_card.findChildren(QLabel):
        if label.isVisible() and label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width()), label.text()
    fixation_edit = next(
        item.fixation_edit_button
        for item in guide._review_summary_widgets
        if item.fixation_edit_button.isVisible()
    )
    qtbot.mouseClick(fixation_edit, Qt.MouseButton.LeftButton)
    assert guide.step_stack.currentWidget() is guide.fixation_step_surface
    guide.open_wizard(step_key="review", allow_step_jumps=True)
    session_edit = next(
        item.edit_button
        for item in guide._review_summary_widgets
        if item.edit_button.property("reviewStepKey") == "session"
    )
    qtbot.mouseClick(session_edit, Qt.MouseButton.LeftButton)
    assert guide.step_stack.currentWidget() is guide.session_step_surface
    guide.session_structure_editor.block_count_spin.setValue(3)
    guide.open_wizard(step_key="review")
    assert any(
        "3 repeats per condition" in label.text() for label in review_card.findChildren(QLabel)
    )

    prompts: list[str] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.QMessageBox.question",
        lambda *args, **kwargs: prompts.append(str(args[2])) or QMessageBox.StandardButton.No,
    )
    qtbot.mouseClick(guide.review_return_home_button, Qt.MouseButton.LeftButton)
    assert window.main_stack.currentWidget() is guide
    assert "without saving to disk" in prompts[0]
    assert "remain in this open project" in prompts[0]

    def _unexpected_save_modal(*_args, **_kwargs):
        raise AssertionError("A successful save should use the existing nonmodal status message.")

    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.QMessageBox.information", _unexpected_save_modal
    )
    qtbot.mouseClick(guide.review_save_button, Qt.MouseButton.LeftButton)
    assert window.document.dirty is False
    assert window.main_stack.currentWidget() is window.home_page
    assert window.statusBar().currentMessage() == "Project saved."


def test_setup_review_reports_effective_tutorial_and_response_state(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Review Effective Response")
    guide = window.setup_wizard_page
    guide.project_overview_editor.participant_tutorial_checkbox.setChecked(True)
    guide.fixation_settings_editor.fixation_accuracy_checkbox.setChecked(False)
    window.main_stack.setCurrentWidget(guide)
    window.resize(1120, 720)
    guide.open_wizard(step_key="review", allow_step_jumps=True)
    QApplication.processEvents()
    text = "\n".join(label.text() for label in guide.review_card.findChildren(QLabel))
    assert "Accuracy tracking: Off" in text
    assert "Response scoring: Off" in text
    assert "Participant tutorial: Off (accuracy tracking is off)" in text
    assert "Participant tutorial: On" not in text
    assert_visible_children_within_parent(guide.review_step_surface)
    for label in guide.review_card.findChildren(QLabel):
        if label.isVisible() and label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width()), label.text()

    project_edit = next(
        item.edit_button
        for item in guide._review_summary_widgets
        if item.edit_button.property("reviewStepKey") == "project"
    )
    qtbot.mouseClick(project_edit, Qt.MouseButton.LeftButton)
    assert guide.project_overview_editor.participant_tutorial_checkbox.isVisible()
    guide.project_overview_editor.participant_tutorial_checkbox.setChecked(False)
    guide.open_wizard(step_key="review", allow_step_jumps=True)
    text = "\n".join(label.text() for label in guide.review_card.findChildren(QLabel))
    assert "Participant tutorial: Off" in text
    assert "accuracy tracking is off" not in text

    response_edit = next(
        item.edit_button
        for item in guide._review_summary_widgets
        if item.edit_button.property("reviewStepKey") == "response"
    )
    qtbot.mouseClick(response_edit, Qt.MouseButton.LeftButton)
    assert guide.step_stack.currentWidget() is guide.response_step_surface


def test_setup_wizard_review_save_failure_stays_on_review(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Review Save Failure")
    guide = window.setup_wizard_page
    window.main_stack.setCurrentWidget(guide)
    guide.open_wizard(step_key="review")
    QApplication.processEvents()
    save_calls = 0
    return_home_calls = 0
    save_confirmations: list[str] = []

    def _save_failure() -> bool:
        nonlocal save_calls
        save_calls += 1
        return False

    def _return_home() -> None:
        nonlocal return_home_calls
        return_home_calls += 1

    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.QMessageBox.information",
        lambda *args, **kwargs: save_confirmations.append(str(args[2])),
    )

    guide._on_save_project = _save_failure
    guide._on_return_home = _return_home

    qtbot.mouseClick(guide.review_save_button, Qt.MouseButton.LeftButton)

    assert save_calls == 1
    assert return_home_calls == 0
    assert save_confirmations == []
    assert window.main_stack.currentWidget() is guide


def test_setup_wizard_review_return_without_saving_accepts_confirmation(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Review Return Without Save")
    guide = window.setup_wizard_page
    window.main_stack.setCurrentWidget(guide)
    guide.open_wizard(step_key="review")
    QApplication.processEvents()
    save_calls = 0

    def _unexpected_save() -> bool:
        nonlocal save_calls
        save_calls += 1
        return True

    guide._on_save_project = _unexpected_save
    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    qtbot.mouseClick(guide.review_return_home_button, Qt.MouseButton.LeftButton)

    assert save_calls == 0
    assert window.main_stack.currentWidget() is window.home_page


def test_setup_wizard_return_home_confirms_incomplete_setup(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Incomplete Exit Guard")
    guide = window.setup_wizard_page
    window.main_stack.setCurrentWidget(guide)

    prompts: list[str] = []

    def _decline_return(*args, **_kwargs):
        prompts.append(str(args[2]))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.QMessageBox.question",
        _decline_return,
    )
    qtbot.mouseClick(guide.setup_wizard_return_home_button, Qt.MouseButton.LeftButton)

    assert window.main_stack.currentWidget() is guide
    assert prompts
    assert "not ready to launch" in prompts[0]

    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    qtbot.mouseClick(guide.setup_wizard_return_home_button, Qt.MouseButton.LeftButton)
    assert window.main_stack.currentWidget() is window.home_page


def test_setup_wizard_ready_project_returns_home_without_confirmation(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Ready Exit Guard")
    _prepare_compile_ready_project(window, tmp_path / "ready-exit-assets")
    assert window.save_project() is True
    guide = window.setup_wizard_page
    window.main_stack.setCurrentWidget(guide)

    def _unexpected_prompt(*_args, **_kwargs):
        raise AssertionError("Ready setup should not ask before returning Home.")

    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.QMessageBox.question",
        _unexpected_prompt,
    )
    qtbot.mouseClick(guide.setup_wizard_return_home_button, Qt.MouseButton.LeftButton)

    assert window.main_stack.currentWidget() is window.home_page
