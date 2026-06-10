"""Focused GUI workflow tests split from the former layout dashboard suite."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QWidget,
)
from tests.gui.helpers import (
    _open_created_project,
    _write_image_directory,
)

from fpvs_studio.core.condition_template_profiles import (
    SIXTY_HZ_BLANK_FIXATION_PROFILE_ID,
    STUDIO_DEFAULT_PROFILE_ID,
)
from fpvs_studio.gui.controller import StudioController


def test_setup_wizard_surfaces_steps_and_keeps_shared_editors_available(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Setup Guide Content")
    dashboard = window.setup_wizard_page
    window.main_stack.setCurrentWidget(dashboard)
    QApplication.processEvents()

    project_editor = dashboard.project_overview_editor
    session_editor = dashboard.session_structure_editor
    fixation_editor = dashboard.fixation_settings_editor
    runtime_editor = dashboard.runtime_settings_editor

    assert project_editor.project_name_edit is not None
    assert project_editor.project_description_edit is not None
    assert project_editor.project_root_value is not None
    assert project_editor.condition_profile_combo is not None
    assert project_editor.condition_profile_combo.itemText(0) == "Continuous Images"
    assert project_editor.condition_profile_combo.itemData(0) is not None
    assert "(" not in project_editor.condition_profile_combo.itemText(0)
    continuous_index = project_editor.condition_profile_combo.findData(STUDIO_DEFAULT_PROFILE_ID)
    blank_index = project_editor.condition_profile_combo.findData(
        SIXTY_HZ_BLANK_FIXATION_PROFILE_ID
    )
    assert (
        project_editor.condition_profile_combo.itemData(
            continuous_index,
            Qt.ItemDataRole.ToolTipRole,
        )
        == "Use this template if you want to display one image immediately after the "
        "previous image with no blanks in between."
    )
    assert (
        project_editor.condition_profile_combo.itemData(
            blank_index,
            Qt.ItemDataRole.ToolTipRole,
        )
        == "Use this template if you'd like to display images with 50% of the image "
        "display period being blank before the next image is shown."
    )
    assert project_editor.manage_templates_button is not None
    assert project_editor.apply_profile_to_conditions_button is not None
    assert project_editor.apply_profile_to_conditions_button.isVisible() is False
    assert project_editor.participant_tutorial_checkbox is not None
    assert project_editor.participant_tutorial_checkbox.text() == "Enable participant tutorial?"
    assert project_editor.participant_tutorial_checkbox.toolTip()
    assert project_editor.project_overview_card.maximumWidth() == 930
    assert project_editor.project_overview_card.title_label.text() == "Project Details"
    assert project_editor.project_overview_card.title_label.isVisible() is False
    setup_icon = project_editor.findChild(QLabel, "setup_project_icon")
    checklist = project_editor.setup_checklist
    assert setup_icon is not None
    assert setup_icon.width() == 52
    assert setup_icon.height() == 52
    assert project_editor.findChild(QLabel, "project_overview_title").text() == "Project Details"
    project_default_cue = project_editor.findChild(QLabel, "project_overview_subtitle")
    assert project_default_cue.property("setupDefaultCue") == "true"
    assert project_default_cue.text() == (
        "Recommended start: Continuous Images; participant tutorial enabled."
    )
    assert project_editor.findChild(QLabel, "project_overview_step_badge") is None
    assert checklist.objectName() == "project_overview_checklist"
    assert checklist.title_label.text() == "Ready for next step"
    assert 210 <= checklist.minimumWidth() <= checklist.maximumWidth()
    checklist_items = checklist.item_labels()
    assert [label.text() for label in checklist_items] == [
        "✓ Name",
        "✕ Description",
        "✓ Template",
    ]
    assert checklist_items[0].property("setupChecklistState") == "complete"
    assert checklist_items[1].property("setupChecklistState") == "incomplete"
    assert checklist_items[2].property("setupChecklistState") == "complete"
    assert dashboard.step_title_label.isVisible() is False
    assert dashboard.step_status_badge.isVisible() is False
    assert project_editor.project_root_value.wordWrap() is False
    assert project_editor.project_root_value.maximumHeight() <= 34
    assert str(window.document.project_root) in {
        project_editor.project_root_value.text(),
        project_editor.project_root_value.toolTip(),
    }

    assert session_editor.block_count_spin is not None
    assert session_editor.inter_condition_mode_combo is not None

    assert fixation_editor.fixation_enabled_checkbox is not None
    assert not fixation_editor.fixation_enabled_checkbox.isVisible()
    assert fixation_editor.target_count_mode_combo is not None
    assert "Recommended maximum cross changes per condition:" in (
        fixation_editor.fixation_feasibility_label.text()
    )

    assert runtime_editor.refresh_hz_spin is not None
    assert runtime_editor.runtime_background_color_combo is not None
    assert not hasattr(runtime_editor, "serial_port_edit")
    assert not hasattr(runtime_editor, "serial_baudrate_spin")
    assert not hasattr(runtime_editor, "fullscreen_checkbox")
    assert not hasattr(runtime_editor, "test_mode_checkbox")

    assert dashboard.conditions_page is window.conditions_page
    assert dashboard.condition_setup_step.condition_name_edit is not None
    assert dashboard.condition_setup_step.trigger_code_spin is not None
    assert dashboard.condition_setup_step.instructions_edit is not None
    assert dashboard.condition_setup_step.base_import_button is not None
    assert dashboard.condition_setup_step.oddball_import_button is not None
    assert not hasattr(dashboard.condition_setup_step, "sequence_count_spin")
    assert not hasattr(dashboard.condition_setup_step, "duty_cycle_combo")
    assert not hasattr(dashboard.condition_setup_step, "variant_combo")
    assert dashboard.assets_page is window.assets_page
    assert dashboard.run_page is window.run_page
    assert len(dashboard.progress_steps.step_items) == 6
    step_metadata_text = "\n".join(item.toolTip() for item in dashboard.progress_steps.step_items)
    assert "Project" in step_metadata_text
    assert "Conditions" in step_metadata_text
    assert "Experiment" in step_metadata_text
    assert "Fixation" in step_metadata_text
    assert "Response" in step_metadata_text
    assert "Review" in step_metadata_text


def test_setup_wizard_navigation_has_no_conditions_advanced_editor(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Setup Guide Actions")
    guide = window.setup_wizard_page
    window.main_stack.setCurrentWidget(guide)
    guide.project_overview_editor.project_description_edit.setPlainText(
        "Required setup description."
    )
    guide.flush_pending_edits()
    guide.refresh()

    back_button = guide.findChild(QPushButton, "setup_wizard_back_button")
    next_button = guide.findChild(QPushButton, "setup_wizard_next_button")
    return_home_button = guide.findChild(QPushButton, "setup_wizard_return_home_button")
    assert back_button is not None
    assert next_button is not None
    assert guide.findChild(QPushButton, "setup_wizard_advanced_button") is None
    assert return_home_button is not None

    assert guide.step_stack.currentIndex() == 0
    assert next_button.isEnabled()
    qtbot.mouseClick(next_button, Qt.MouseButton.LeftButton)
    assert guide.step_stack.currentIndex() == 1
    assert guide.step_stack.currentWidget() is guide.conditions_step_surface
    assert guide.conditions_step_surface.content is guide.condition_setup_step
    assert guide.content_stack.currentWidget() is guide.guided_panel
    assert not next_button.isEnabled()
    assert guide.findChild(QListWidget, "setup_wizard_condition_list") is not None
    assert guide.findChild(QWidget, "setup_conditions_left_panel") is not None
    assert guide.findChild(QWidget, "setup_conditions_main_panel") is not None
    assert guide.findChild(QWidget, "setup_conditions_details_section") is not None
    assert guide.findChild(QPushButton, "setup_conditions_edit_advanced_timing_button") is None
    label_text = "\n".join(
        label.text() for label in guide.condition_setup_step.findChildren(QLabel)
    )
    assert "Condition List" not in label_text
    assert "Selected Condition" not in label_text
    assert "Base Images" in label_text
    assert "Oddball Images" in label_text
    assert "Stimulus Variant" not in label_text
    assert "Cycles / Repeat" not in label_text

    information_prompts: list[str] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.QMessageBox.information",
        lambda *args, **kwargs: information_prompts.append(str(args[2])),
    )
    qtbot.mouseClick(guide.add_condition_button, Qt.MouseButton.LeftButton)
    assert information_prompts == ["Please ensure you create all conditions before proceeding."]
    assert not next_button.isEnabled()
    assert "name every condition" in guide.step_status_label.text().lower()

    condition_id = guide.condition_setup_step.selected_condition_id()
    assert isinstance(condition_id, str)
    guide._document.update_condition(condition_id, name="Faces")
    qtbot.waitUntil(lambda: "assign base and oddball" in guide.step_status_label.text().lower())
    assert not next_button.isEnabled()
    assert "assign base and oddball" in guide.step_status_label.text().lower()
    assert guide.condition_setup_step.selected_condition_id() == condition_id

    base_dir = _write_image_directory(tmp_path / "wizard-condition-base")
    oddball_dir = _write_image_directory(tmp_path / "wizard-condition-oddball")
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="base",
        source_dir=base_dir,
    )
    QApplication.processEvents()
    assert not next_button.isEnabled()
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=oddball_dir,
    )
    qtbot.waitUntil(next_button.isEnabled)

    qtbot.mouseClick(next_button, Qt.MouseButton.LeftButton)
    assert guide.step_stack.currentWidget() is guide.experiment_step_surface
    assert guide.experiment_step_surface.content.objectName() == (
        "setup_wizard_experiment_settings_page"
    )
    assert not guide.step_title_label.isVisible()
    assert guide.experiment_settings_card.isAncestorOf(guide.runtime_settings_editor)
    assert guide.experiment_settings_card.isAncestorOf(guide.session_structure_editor)
    assert guide.content_stack.currentWidget() is guide.guided_panel

    qtbot.mouseClick(next_button, Qt.MouseButton.LeftButton)
    assert guide.step_stack.currentWidget() is guide.fixation_step_surface
    assert guide.fixation_step_surface.content is guide.fixation_schedule_editor
    assert guide.step_title_label.text() == "Fixation"
    qtbot.mouseClick(next_button, Qt.MouseButton.LeftButton)
    assert guide.step_stack.currentWidget() is guide.response_step_surface
    assert guide.response_step_surface.content is guide.fixation_response_editor
    assert guide.step_title_label.text() == "Response"
    assert guide.fixation_response_editor.preview_widget is not None

    qtbot.mouseClick(back_button, Qt.MouseButton.LeftButton)
    assert guide.step_stack.currentWidget() is guide.fixation_step_surface
    qtbot.mouseClick(back_button, Qt.MouseButton.LeftButton)
    assert guide.step_stack.currentWidget() is guide.experiment_step_surface
    qtbot.mouseClick(back_button, Qt.MouseButton.LeftButton)
    assert guide.step_stack.currentIndex() == 1
    assert guide.content_stack.currentWidget() is guide.guided_panel

    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    qtbot.mouseClick(return_home_button, Qt.MouseButton.LeftButton)
    assert window.main_stack.currentWidget() is window.home_page


def test_project_details_step_requires_description_before_next(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Description Gate")
    guide = window.setup_wizard_page
    window.main_stack.setCurrentWidget(guide)

    next_button = guide.findChild(QPushButton, "setup_wizard_next_button")
    description_edit = guide.project_overview_editor.project_description_edit
    assert next_button is not None

    description_edit.clear()
    guide.flush_pending_edits()
    guide.refresh()
    assert guide.step_stack.currentIndex() == 0
    assert not next_button.isEnabled()
    assert "project description" in guide.step_status_label.text().lower()
    assert "✕ Description" in {
        label.text()
        for label in guide.project_overview_editor.setup_checklist.item_labels()
    }

    description_edit.setPlainText("This experiment measures FPVS responses.")
    guide.flush_pending_edits()
    guide.refresh()
    qtbot.waitUntil(next_button.isEnabled)
    assert "✓ Description" in {
        label.text()
        for label in guide.project_overview_editor.setup_checklist.item_labels()
    }

    qtbot.mouseClick(next_button, Qt.MouseButton.LeftButton)
    assert guide.step_stack.currentIndex() == 1


def test_project_description_typing_commits_once_after_debounce(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Description Debounce")
    guide = window.setup_wizard_page
    description_edit = guide.project_overview_editor.project_description_edit
    project_changes = 0

    def _count_project_change() -> None:
        nonlocal project_changes
        project_changes += 1

    window.document.project_changed.connect(_count_project_change)
    description_edit.setPlainText("Debounced project description.")

    assert window.document.project.meta.description == ""
    assert project_changes == 0

    qtbot.waitUntil(
        lambda: window.document.project.meta.description == "Debounced project description.",
        timeout=1000,
    )
    assert project_changes <= 1


def test_pending_text_edits_flush_before_setup_navigation(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Navigation Flush")
    guide = window.setup_wizard_page
    next_button = guide.findChild(QPushButton, "setup_wizard_next_button")
    assert next_button is not None

    guide.project_overview_editor.project_description_edit.setPlainText(
        "Navigation should commit this description."
    )
    QApplication.processEvents()
    qtbot.waitUntil(next_button.isEnabled)
    assert window.document.project.meta.description == ""
    qtbot.mouseClick(next_button, Qt.MouseButton.LeftButton)

    assert window.document.project.meta.description == "Navigation should commit this description."
    assert guide.step_stack.currentIndex() == 1


def test_project_description_typing_reduces_validation_churn(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Validation Churn")
    guide = window.setup_wizard_page
    validation_calls = 0
    original_validation_report = window.document.validation_report

    def _count_validation_report(*args, **kwargs):
        nonlocal validation_calls
        validation_calls += 1
        return original_validation_report(*args, **kwargs)

    monkeypatch.setattr(window.document, "validation_report", _count_validation_report)
    guide.project_overview_editor.project_description_edit.setPlainText("Validation debounce.")

    qtbot.waitUntil(
        lambda: window.document.project.meta.description == "Validation debounce.",
        timeout=1000,
    )
    assert validation_calls <= 8
