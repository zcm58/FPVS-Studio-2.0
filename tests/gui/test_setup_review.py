"""Focused GUI workflow tests split from the former layout dashboard suite."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QPoint,
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QMessageBox,
    QPushButton,
)
from tests.gui.helpers import (
    _open_created_project,
    _prepare_compile_ready_project,
    _write_image_directory,
)

from fpvs_studio.gui.controller import StudioController


def test_setup_wizard_review_uses_centered_confirmation_checklist(
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
    assert not guide.step_title_label.isVisible()
    assert not guide.step_status_badge.isVisible()

    review_card = guide.review_card
    assert review_card.minimumWidth() == 700
    assert review_card.maximumWidth() == 880
    review_page = guide.step_stack.currentWidget()
    card_left = review_card.mapTo(review_page, QPoint(0, 0)).x()
    card_center = card_left + (review_card.width() / 2)
    assert abs(card_center - (review_page.width() / 2)) < 20
    assert review_card.width() >= 700

    label_text = "\n".join(label.text() for label in review_card.findChildren(QLabel))
    assert "Review Your Experiment" in label_text
    assert "Please confirm your experiment settings." in label_text
    assert "Would you like to save your experiment?" not in label_text
    assert "Project Details" in label_text
    assert "Conditions" in label_text
    assert "Experiment Settings" in label_text
    assert "Fixation Cross" in label_text
    assert "Project details complete: Review Checklist Project" in label_text
    assert "2 conditions configured" in label_text
    assert "Timing: Continuous Images" in label_text
    assert "Faces: base 3 images, oddball 3 images" not in label_text
    assert "Objects: base 3 images, oddball 3 images" not in label_text
    assert "Each condition will repeat 2 times in randomized block order" in label_text
    assert "Condition order is randomized automatically at launch" in label_text
    assert "Estimated run time: 10 minutes" in label_text
    assert "Condition durations:" not in label_text
    assert "Break estimate:" not in label_text
    assert "Total estimated run:" not in label_text
    assert "Random order seed:" not in label_text
    assert "Display: 60.00 Hz, Black background" in label_text
    assert "Fixation cross has been configured" in label_text
    assert "Launch requirements are satisfied" not in label_text
    summary_sections = [
        section
        for section in review_card.findChildren(QFrame)
        if section.property("reviewSummarySection") == "true"
    ]
    checklist_rows = [
        row
        for row in review_card.findChildren(QFrame)
        if row.property("reviewChecklistRow") == "true"
    ]
    check_icons = [
        label
        for label in review_card.findChildren(QLabel)
        if label.property("reviewCheckIcon") == "true"
    ]
    assert len(summary_sections) == 4
    assert len(checklist_rows) == 9
    assert len(check_icons) == len(checklist_rows)
    section_title_tops = [
        next(
            label
            for label in section.findChildren(QLabel)
            if label.property("reviewSummarySectionTitle") == "true"
        ).mapTo(section, QPoint(0, 0)).y()
        for section in summary_sections
    ]
    assert max(section_title_tops) - min(section_title_tops) <= 1
    for row in checklist_rows:
        text_label = next(
            label
            for label in row.findChildren(QLabel)
            if label.property("reviewChecklistLine") == "true"
        )
        assert text_label.alignment() & Qt.AlignmentFlag.AlignHCenter
    fixation_row = next(
        row
        for row in checklist_rows
        if any(
            label.text() == "Fixation cross has been configured"
            for label in row.findChildren(QLabel)
        )
    )
    fixation_check_icon = next(
        label
        for label in fixation_row.findChildren(QLabel)
        if label.property("reviewCheckIcon") == "true"
    )
    fixation_text_label = next(
        label
        for label in fixation_row.findChildren(QLabel)
        if label.property("reviewChecklistLine") == "true"
    )
    icon_center_y = fixation_check_icon.mapTo(
        fixation_row,
        QPoint(0, fixation_check_icon.height() // 2),
    ).y()
    text_center_y = fixation_text_label.mapTo(
        fixation_row,
        QPoint(0, fixation_text_label.height() // 2),
    ).y()
    assert abs(icon_center_y - text_center_y) <= 1

    assert guide.review_save_button.text() == "Save and Return Home"
    assert guide.review_return_home_button.text() == "Return Home Without Saving"
    assert guide.setup_wizard_return_home_button.isHidden()
    assert guide.setup_wizard_next_button.isHidden()
    assert guide.setup_wizard_back_button.isVisible()
    assert (
        len(
            [
                button
                for button in review_card.findChildren(QPushButton)
                if button.text() == "Return Home Without Saving"
            ]
        )
        == 1
    )
    assert window.document.dirty is True

    prompts: list[str] = []

    def _decline_unsaved_return(*args, **_kwargs):
        prompts.append(str(args[2]))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.QMessageBox.question",
        _decline_unsaved_return,
    )
    save_confirmations: list[str] = []

    def _capture_save_confirmation(*args, **_kwargs):
        save_confirmations.append(str(args[2]))
        assert window.main_stack.currentWidget() is guide
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.QMessageBox.information",
        _capture_save_confirmation,
    )
    qtbot.mouseClick(guide.review_return_home_button, Qt.MouseButton.LeftButton)

    assert window.main_stack.currentWidget() is guide
    assert prompts == ["Are you sure you want to return home without saving your changes?"]

    qtbot.mouseClick(guide.review_save_button, Qt.MouseButton.LeftButton)
    assert window.document.dirty is False
    assert save_confirmations == ["Experiment settings have been saved."]
    assert window.main_stack.currentWidget() is window.home_page

    window.main_stack.setCurrentWidget(guide)
    guide.open_wizard(step_key="review")
    QApplication.processEvents()
    prompts.clear()
    qtbot.mouseClick(guide.review_return_home_button, Qt.MouseButton.LeftButton)
    assert window.main_stack.currentWidget() is guide
    assert prompts == ["Are you sure you want to return home without saving your changes?"]

    window.home_page.refresh()
    assert "Launch requirements are satisfied" not in window.home_page.launch_status_summary.text()
    assert window.home_page.launch_status_summary.text() == ""


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
