"""Focused GUI workflow tests split from the former layout dashboard suite."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
)
from tests.gui.helpers import _open_created_project

from fpvs_studio.core.condition_template_profiles import SIXTY_HZ_BLANK_FIXATION_PROFILE_ID
from fpvs_studio.core.enums import (
    DutyCycleMode,
    InterConditionMode,
    StimulusVariant,
)
from fpvs_studio.core.serialization import load_project_file
from fpvs_studio.gui.controller import StudioController


def test_setup_dashboard_edits_sync_document_and_dedicated_tabs(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Setup Dashboard Forward Sync")
    dashboard = window.setup_dashboard_page

    project_editor = dashboard.project_overview_editor
    project_editor.project_name_edit.setText("Dashboard Renamed Project")
    project_editor.project_name_edit.editingFinished.emit()
    project_editor.project_description_edit.setPlainText("Setup dashboard project description.")
    blank_index = project_editor.condition_profile_combo.findData(
        SIXTY_HZ_BLANK_FIXATION_PROFILE_ID
    )
    assert blank_index >= 0
    project_editor.condition_profile_combo.setCurrentIndex(blank_index)

    conditions_page = window.conditions_page
    conditions_page.add_condition_button.click()
    conditions_page.condition_name_edit.setText("Dashboard Faces")
    conditions_page.condition_name_edit.editingFinished.emit()
    conditions_page.instructions_edit.setPlainText("Look at the faces.")
    conditions_page.trigger_code_spin.setValue(21)
    conditions_page.sequence_count_spin.setValue(2)
    conditions_page.variant_combo.setCurrentIndex(
        conditions_page.variant_combo.findData(StimulusVariant.GRAYSCALE)
    )
    assert not hasattr(conditions_page, "duty_cycle_combo")

    window.main_stack.setCurrentWidget(dashboard)
    session_editor = dashboard.session_structure_editor
    session_editor.block_count_spin.setValue(4)

    fixation_editor = dashboard.fixation_settings_editor
    fixation_editor.fixation_enabled_checkbox.setChecked(True)
    fixation_editor.fixation_accuracy_checkbox.setChecked(True)
    fixation_editor.target_count_mode_combo.setCurrentIndex(
        fixation_editor.target_count_mode_combo.findData("randomized")
    )
    fixation_editor.target_count_min_spin.setValue(2)
    fixation_editor.target_count_max_spin.setValue(5)
    fixation_editor.no_repeat_count_checkbox.setChecked(True)

    runtime_editor = dashboard.runtime_settings_editor
    runtime_editor.refresh_hz_spin.setValue(59.94)
    dark_gray_index = runtime_editor.runtime_background_color_combo.findData("#101010")
    assert dark_gray_index >= 0
    runtime_editor.runtime_background_color_combo.setCurrentIndex(dark_gray_index)
    image_size_editor = dashboard.image_display_size_editor
    image_size_editor.width_degrees_spin.setValue(7.5)
    image_size_editor.viewing_distance_spin.setValue(82.0)
    image_size_editor.screen_width_spin.setValue(54.0)
    image_size_editor.screen_width_px_spin.setValue(1920)
    image_size_editor.screen_height_px_spin.setValue(1080)
    window.flush_pending_edits()
    QApplication.processEvents()

    conditions = window.document.ordered_conditions()
    assert len(conditions) == 1
    assert conditions[0].name == "Dashboard Faces"
    assert conditions[0].instructions == "Look at the faces."
    assert conditions[0].trigger_code == 21
    assert conditions[0].sequence_count == 2
    assert conditions[0].stimulus_variant == StimulusVariant.GRAYSCALE
    assert conditions[0].duty_cycle_mode == DutyCycleMode.BLANK_50

    assert window.document.project.meta.name == "Dashboard Renamed Project"
    assert window.document.project.meta.description == "Setup dashboard project description."
    settings = window.document.project.settings
    assert settings.session.block_count == 4
    assert settings.session.inter_condition_mode == InterConditionMode.MANUAL_CONTINUE
    assert settings.session.continue_key == "space"
    assert settings.fixation_task.target_count_mode == "randomized"
    assert settings.fixation_task.target_count_min == 2
    assert settings.fixation_task.target_count_max == 5
    assert settings.fixation_task.no_immediate_repeat_count is True
    assert settings.display.preferred_refresh_hz == pytest.approx(59.94, abs=0.01)
    assert settings.display.background_color == "#101010"
    assert settings.display.stimulus_width_degrees == pytest.approx(7.5, abs=0.01)
    assert settings.display.viewing_distance_cm == pytest.approx(82.0, abs=0.01)
    assert settings.display.screen_width_cm == pytest.approx(54.0, abs=0.01)
    assert settings.display.screen_width_px == 1920
    assert settings.display.screen_height_px == 1080
    assert settings.triggers.serial_port is None
    assert settings.triggers.baudrate == 115200

    assert window.session_structure_page.block_count_spin.value() == 4
    assert (
        window.session_structure_page.inter_condition_mode_combo.currentData()
        == InterConditionMode.MANUAL_CONTINUE
    )
    assert window.session_structure_page.inter_condition_mode_combo.isVisible() is False
    assert window.session_structure_page.break_seconds_spin.isVisible() is False
    assert window.session_structure_page.continue_key_edit.text() == "space"
    assert window.session_structure_page.continue_key_edit.isEnabled() is False
    assert window.fixation_cross_settings_page.target_count_mode_combo.currentData() == "randomized"
    assert window.fixation_cross_settings_page.target_count_min_spin.value() == 2
    assert window.fixation_cross_settings_page.target_count_max_spin.value() == 5
    assert window.run_page.refresh_hz_spin.value() == pytest.approx(59.94, abs=0.01)
    assert window.run_page.runtime_background_color_combo.currentData() == "#101010"
    assert window.run_page.findChild(QWidget, "serial_port_edit") is None
    assert window.run_page.findChild(QWidget, "serial_baudrate_spin") is None
    assert window.run_page.findChild(QWidget, "fullscreen_checkbox") is None
    assert window.run_page.findChild(QWidget, "test_mode_checkbox") is None
    assert window.run_page.findChild(QWidget, "display_index_edit") is None
    assert window.run_page.findChild(QWidget, "engine_name_value") is None


def test_dedicated_tab_edits_refresh_setup_dashboard_controls(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Setup Dashboard Reverse Sync")

    window.session_structure_page.block_count_spin.setValue(6)

    fixation_page = window.fixation_cross_settings_page
    fixation_page.fixation_enabled_checkbox.setChecked(True)
    fixation_page.fixation_accuracy_checkbox.setChecked(False)
    fixation_page.target_count_mode_combo.setCurrentIndex(
        fixation_page.target_count_mode_combo.findData("fixed")
    )
    fixation_page.changes_per_sequence_spin.setValue(7)

    run_page = window.run_page
    run_page.refresh_hz_spin.setValue(75.0)
    QApplication.processEvents()

    dashboard = window.setup_dashboard_page
    assert dashboard.session_structure_editor.block_count_spin.value() == 6
    assert (
        dashboard.session_structure_editor.inter_condition_mode_combo.currentData()
        == InterConditionMode.MANUAL_CONTINUE
    )
    assert dashboard.session_structure_editor.inter_condition_mode_combo.isVisible() is False
    assert dashboard.session_structure_editor.break_seconds_spin.isVisible() is False
    assert dashboard.session_structure_editor.continue_key_edit.text() == "space"
    assert dashboard.fixation_settings_editor.target_count_mode_combo.currentData() == "fixed"
    assert dashboard.fixation_settings_editor.changes_per_sequence_spin.value() == 7
    assert dashboard.runtime_settings_editor.refresh_hz_spin.value() == pytest.approx(
        75.0, abs=0.01
    )
    assert not hasattr(dashboard.runtime_settings_editor, "serial_port_edit")
    assert not hasattr(dashboard.runtime_settings_editor, "serial_baudrate_spin")
    assert not hasattr(dashboard.runtime_settings_editor, "fullscreen_checkbox")
    assert not hasattr(run_page, "serial_baudrate_spin")
    assert not hasattr(run_page, "fullscreen_checkbox")


def test_setup_dashboard_save_load_smoke_persists_dashboard_edited_settings(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Setup Dashboard Save Load")
    dashboard = window.setup_dashboard_page

    dashboard.session_structure_editor.block_count_spin.setValue(3)

    fixation_editor = dashboard.fixation_settings_editor
    fixation_editor.fixation_enabled_checkbox.setChecked(True)
    fixation_editor.fixation_accuracy_checkbox.setChecked(True)
    fixation_editor.target_count_mode_combo.setCurrentIndex(
        fixation_editor.target_count_mode_combo.findData("fixed")
    )
    fixation_editor.changes_per_sequence_spin.setValue(6)
    fixation_editor.base_color_combo.setCurrentIndex(
        fixation_editor.base_color_combo.findData("#FFFFFF")
    )
    fixation_editor.target_color_combo.setCurrentIndex(
        fixation_editor.target_color_combo.findData("#FF0000")
    )
    fixation_editor._set_response_key("g")

    runtime_editor = dashboard.runtime_settings_editor
    runtime_editor.refresh_hz_spin.setValue(120.0)
    dark_gray_index = runtime_editor.runtime_background_color_combo.findData("#101010")
    assert dark_gray_index >= 0
    runtime_editor.runtime_background_color_combo.setCurrentIndex(dark_gray_index)
    image_size_editor = dashboard.image_display_size_editor
    image_size_editor.width_degrees_spin.setValue(9.0)
    image_size_editor.viewing_distance_spin.setValue(85.0)
    image_size_editor.screen_width_spin.setValue(55.0)
    image_size_editor.screen_width_px_spin.setValue(1920)
    image_size_editor.screen_height_px_spin.setValue(1080)

    assert window.save_project() is True
    controller.open_project(window.document.project_root)
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)

    reopened_window = controller.main_window
    reopened_dashboard = reopened_window.setup_dashboard_page
    reopened_project = load_project_file(reopened_window.document.project_file_path)

    session = reopened_project.settings.session
    fixation = reopened_project.settings.fixation_task
    display = reopened_project.settings.display
    triggers = reopened_project.settings.triggers
    assert session.block_count == 3
    assert session.inter_condition_mode == InterConditionMode.MANUAL_CONTINUE
    assert session.continue_key == "space"
    assert fixation.enabled is True
    assert fixation.accuracy_task_enabled is True
    assert fixation.target_count_mode == "fixed"
    assert fixation.changes_per_sequence == 6
    assert fixation.base_color == "#FFFFFF"
    assert fixation.target_color == "#FF0000"
    assert fixation.response_key == "g"
    assert display.preferred_refresh_hz == pytest.approx(120.0, abs=0.01)
    assert display.background_color == "#101010"
    assert display.stimulus_width_degrees == pytest.approx(9.0, abs=0.01)
    assert display.viewing_distance_cm == pytest.approx(85.0, abs=0.01)
    assert display.screen_width_cm == pytest.approx(55.0, abs=0.01)
    assert display.screen_width_px == 1920
    assert display.screen_height_px == 1080
    assert triggers.serial_port is None
    assert triggers.baudrate == 115200

    assert reopened_dashboard.session_structure_editor.block_count_spin.value() == 3
    assert reopened_dashboard.fixation_settings_editor.changes_per_sequence_spin.value() == 6
    assert reopened_dashboard.runtime_settings_editor.refresh_hz_spin.value() == pytest.approx(
        120.0, abs=0.01
    )
    assert reopened_dashboard.image_display_size_editor.width_degrees_spin.value() == pytest.approx(
        9.0, abs=0.01
    )
    assert reopened_dashboard.image_display_size_editor.screen_width_px_spin.value() == 1920
    assert reopened_dashboard.image_display_size_editor.screen_height_px_spin.value() == 1080
    reopened_background = (
        reopened_dashboard.runtime_settings_editor.runtime_background_color_combo.currentData()
    )
    assert reopened_background == "#101010"
    assert not hasattr(reopened_dashboard.runtime_settings_editor, "serial_port_edit")
    assert not hasattr(reopened_window.run_page, "serial_baudrate_spin")
    assert not hasattr(reopened_window.run_page, "fullscreen_checkbox")
