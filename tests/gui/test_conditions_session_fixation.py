"""PySide6 GUI workflow tests for the Phase 5 authoring application."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
    QWidget,
)
from tests.gui.helpers import (
    _open_created_project,
    _prepare_compile_ready_project,
)

from fpvs_studio.core.condition_template_profiles import (
    SIXTY_HZ_BLANK_FIXATION_PROFILE_ID,
    STUDIO_DEFAULT_PROFILE_ID,
)
from fpvs_studio.core.enums import DutyCycleMode, InterConditionMode, StimulusVariant
from fpvs_studio.core.serialization import load_project_file
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.document import _CONDITION_LENGTH_ERROR_MESSAGE


def test_project_description_typing_round_trips_without_cursor_reset(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    typed_text = "testing this, why is this happening"
    _, window = _open_created_project(controller, qtbot, tmp_path, "Description Project")

    window.main_stack.setCurrentWidget(window.setup_wizard_page)
    description_edit = window.setup_dashboard_page.project_overview_editor.project_description_edit
    description_edit.setFocus()
    qtbot.waitUntil(description_edit.hasFocus)
    qtbot.keyClicks(description_edit, typed_text)

    cursor = description_edit.textCursor()
    assert description_edit.toPlainText() == typed_text
    assert cursor.position() == len(typed_text)
    assert cursor.anchor() == len(typed_text)

    assert window.save_project() is True
    controller.open_project(window.document.project_root)
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)

    reopened_window = controller.main_window
    reopened_project = load_project_file(reopened_window.document.project_file_path)

    assert (
        reopened_window.setup_dashboard_page.project_overview_editor.project_description_edit.toPlainText()
        == typed_text
    )
    assert reopened_project.meta.description == typed_text


def test_condition_editor_round_trip(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Roundtrip Conditions")

    blank_index = (
        window.setup_dashboard_page.project_overview_editor.condition_profile_combo.findData(
            SIXTY_HZ_BLANK_FIXATION_PROFILE_ID
        )
    )
    assert blank_index >= 0
    window.setup_dashboard_page.project_overview_editor.condition_profile_combo.setCurrentIndex(
        blank_index
    )
    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)
    window.conditions_page.condition_name_edit.clear()
    window.conditions_page.condition_name_edit.setText("Faces Condition")
    window.conditions_page.condition_name_edit.editingFinished.emit()
    window.conditions_page.instructions_edit.setPlainText("Look at the faces.")
    window.conditions_page.trigger_code_spin.setValue(21)
    window.conditions_page.sequence_count_spin.setValue(2)
    window.conditions_page.variant_combo.setCurrentIndex(
        window.conditions_page.variant_combo.findData(StimulusVariant.GRAYSCALE)
    )
    assert not hasattr(window.conditions_page, "duty_cycle_combo")

    assert window.save_project() is True
    controller.open_project(window.document.project_root)
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)

    reopened_project = load_project_file(controller.main_window.document.project_file_path)
    condition = reopened_project.conditions[0]
    assert condition.name == "Faces Condition"
    assert condition.instructions == "Look at the faces."
    assert condition.trigger_code == 21
    assert condition.sequence_count == 2
    assert condition.stimulus_variant == StimulusVariant.GRAYSCALE
    assert condition.duty_cycle_mode == DutyCycleMode.BLANK_50


def test_condition_instructions_strip_bidi_controls_during_edit(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Instruction Sanitization")

    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)
    window.conditions_page.instructions_edit.setPlainText("\u202eRead this text.\u202c")
    window.flush_pending_edits()

    condition_id = window.conditions_page.selected_condition_id()
    assert condition_id is not None
    condition = window.document.get_condition(condition_id)

    assert condition is not None
    assert condition.instructions == "Read this text."
    assert window.conditions_page.instructions_edit.toPlainText() == "Read this text."


def test_session_and_fixation_settings_round_trip(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Roundtrip Settings")

    session_page = window.session_structure_page
    session_page.block_count_spin.setValue(3)
    session_page.session_seed_spin.setValue(123456)
    session_page.randomize_checkbox.setChecked(False)

    fixation_page = window.fixation_cross_settings_page
    fixation_page.fixation_enabled_checkbox.setChecked(True)
    fixation_page.changes_per_sequence_spin.setValue(4)
    fixation_page.fixation_accuracy_checkbox.setChecked(True)
    fixation_page.target_count_mode_combo.setCurrentIndex(
        fixation_page.target_count_mode_combo.findData("randomized")
    )
    fixation_page.target_count_min_spin.setValue(2)
    fixation_page.target_count_max_spin.setValue(5)
    fixation_page.no_repeat_count_checkbox.setChecked(True)
    fixation_page.target_duration_spin.setValue(300)
    assert fixation_page.base_color_combo.findData("#0000FF") >= 0
    assert fixation_page.base_color_combo.findData("#FFFFFF") >= 0
    assert fixation_page.target_color_combo.findData("#FF0000") >= 0
    assert fixation_page.base_color_combo.toolTip()
    assert fixation_page.target_color_combo.toolTip()
    fixation_page.base_color_combo.setCurrentIndex(
        fixation_page.base_color_combo.findData("#FFFFFF")
    )
    fixation_page.target_color_combo.setCurrentIndex(
        fixation_page.target_color_combo.findData("#FF0000")
    )
    qtbot.mouseClick(fixation_page.response_key_button, Qt.MouseButton.LeftButton)
    f_key_button = fixation_page.response_key_popover.key_button("f")
    assert f_key_button is not None
    qtbot.mouseClick(f_key_button, Qt.MouseButton.LeftButton)
    fixation_page.response_window_spin.setValue(1.25)
    fixation_page.cross_size_spin.setValue(52)
    fixation_page.line_width_spin.setValue(6)

    assert window.save_project() is True
    controller.open_project(window.document.project_root)
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)

    reopened_project = load_project_file(controller.main_window.document.project_file_path)
    session = reopened_project.settings.session
    fixation = reopened_project.settings.fixation_task
    assert session.block_count == 3
    assert session.session_seed == 123456
    assert session.randomize_conditions_per_block is False
    assert session.inter_condition_mode == InterConditionMode.MANUAL_CONTINUE
    assert session.continue_key == "space"
    assert fixation.enabled is True
    assert fixation.accuracy_task_enabled is True
    assert fixation.target_count_mode == "randomized"
    assert fixation.changes_per_sequence == 4
    assert fixation.target_count_min == 2
    assert fixation.target_count_max == 5
    assert fixation.no_immediate_repeat_count is True
    assert fixation.target_duration_ms == 300
    assert fixation.base_color == "#FFFFFF"
    assert fixation.target_color == "#FF0000"
    assert fixation.response_key == "f"
    assert fixation.response_window_seconds == 1.25
    assert fixation.response_keys == ["f"]
    assert fixation.cross_size_px == 52
    assert fixation.line_width_px == 6


def test_fixation_cross_settings_page_maps_fixed_target_count_mode_to_backend(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Fixed Target Count")

    window.main_stack.setCurrentWidget(window.setup_wizard_page)
    page = window.setup_dashboard_page.fixation_settings_editor
    page.target_count_mode_combo.setCurrentIndex(page.target_count_mode_combo.findData("fixed"))
    page.changes_per_sequence_spin.setValue(7)

    fixation = window.document.project.settings.fixation_task
    assert fixation.target_count_mode == "fixed"
    assert fixation.changes_per_sequence == 7


def test_fixation_cross_settings_page_exposes_accuracy_task_controls(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Fixation Controls")

    window.main_stack.setCurrentWidget(window.setup_wizard_page)
    page = window.setup_dashboard_page.fixation_settings_editor
    assert (
        page.findChild(type(page.fixation_accuracy_checkbox), "fixation_accuracy_checkbox")
        is not None
    )
    assert page.findChild(type(page.target_count_mode_combo), "target_count_mode_combo") is not None
    assert page.findChild(type(page.target_count_min_spin), "target_count_min_spin") is not None
    assert page.findChild(type(page.target_count_max_spin), "target_count_max_spin") is not None
    assert (
        page.findChild(type(page.no_repeat_count_checkbox), "no_immediate_repeat_count_checkbox")
        is not None
    )
    assert page.findChild(type(page.response_key_edit), "response_key_edit") is not None
    assert page.response_key_edit.isReadOnly()
    assert page.findChild(type(page.response_key_button), "response_key_choose_button") is not None
    assert page.response_key_edit.toolTip()
    assert page.response_key_button.toolTip()
    assert (
        page.findChild(type(page.response_window_spin), "response_window_seconds_spin") is not None
    )


def test_session_structure_uses_space_start_without_timed_break_controls(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Session Space Start")

    page = window.setup_dashboard_page.session_structure_editor
    window.setup_wizard_page.open_wizard(step_key="session")
    window.main_stack.setCurrentWidget(window.setup_wizard_page)
    QApplication.processEvents()

    QApplication.processEvents()
    assert page.inter_condition_mode_combo.findData(InterConditionMode.FIXED_BREAK) == -1
    assert not page.inter_condition_mode_combo.isVisible()
    assert not page.break_seconds_spin.isVisible()
    assert not page.break_seconds_spin.isEnabled()
    assert page.continue_key_edit.isVisible()
    assert not page.continue_key_edit.isEnabled()
    assert page.continue_key_edit.text() == "space"


def test_fixation_color_change_mode_toggles_relevant_controls(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Fixation Mode Visibility")

    page = window.setup_dashboard_page.fixation_settings_editor
    window.setup_wizard_page.open_wizard(step_key="fixation")
    window.main_stack.setCurrentWidget(window.setup_wizard_page)
    page.fixation_enabled_checkbox.setChecked(True)
    QApplication.processEvents()

    page.target_count_mode_combo.setCurrentIndex(page.target_count_mode_combo.findData("fixed"))
    QApplication.processEvents()
    assert page.changes_per_sequence_spin.isEnabled()
    assert not page.target_count_min_spin.isEnabled()
    assert not page.target_count_max_spin.isEnabled()
    assert not page.no_repeat_count_checkbox.isEnabled()

    page.target_count_mode_combo.setCurrentIndex(
        page.target_count_mode_combo.findData("randomized")
    )
    QApplication.processEvents()
    assert not page.changes_per_sequence_spin.isEnabled()
    assert page.target_count_min_spin.isEnabled()
    assert page.target_count_max_spin.isEnabled()
    assert page.no_repeat_count_checkbox.isEnabled()


def test_fixation_response_key_picker_updates_model_with_keyboard_buttons(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Response Key Picker")

    page = window.setup_dashboard_page.fixation_settings_editor
    window.setup_wizard_page.open_wizard(step_key="fixation")
    window.main_stack.setCurrentWidget(window.setup_wizard_page)
    page.fixation_enabled_checkbox.setChecked(True)
    page.fixation_accuracy_checkbox.setChecked(True)
    QApplication.processEvents()

    assert page.response_key_edit.text() == "space"
    assert page.response_key_popover.isVisible() is False
    assert "escape" not in page.response_key_popover.key_values()

    qtbot.mouseClick(page.response_key_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert page.response_key_popover.isVisible()

    f_key_button = page.response_key_popover.key_button("f")
    g_key_button = page.response_key_popover.key_button("g")
    assert f_key_button is not None
    assert g_key_button is not None
    assert f_key_button.property("hoverAnimationEnabled") is True
    assert g_key_button.property("hoverAnimationEnabled") is True
    assert page.response_key_popover.key_button("left") is None
    assert page.response_key_popover.key_button("right") is None
    assert page.response_key_popover.key_button("up") is None
    assert page.response_key_popover.key_button("down") is None
    assert page.response_key_popover.key_button("f1") is None
    assert page.response_key_popover.key_button("f12") is None

    qtbot.mouseClick(g_key_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert page.response_key_popover.isVisible() is False
    assert page.response_key_edit.text() == "g"
    assert window.document.project.settings.fixation_task.response_key == "g"
    assert window.document.project.settings.fixation_task.response_keys == ["g"]


def test_fixation_randomized_min_above_max_shows_plain_language_error(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Fixation Range Error")

    page = window.setup_dashboard_page.fixation_settings_editor
    window.setup_wizard_page.open_wizard(step_key="fixation")
    window.main_stack.setCurrentWidget(window.setup_wizard_page)
    page.fixation_enabled_checkbox.setChecked(True)
    page.target_count_mode_combo.setCurrentIndex(
        page.target_count_mode_combo.findData("randomized")
    )
    QApplication.processEvents()

    captured_errors: list[tuple[str, str]] = []

    def _capture_error(_parent, title, error):
        captured_errors.append((title, str(error)))

    monkeypatch.setattr(
        "fpvs_studio.gui.fixation_settings_page._show_error_dialog",
        _capture_error,
    )
    page.target_count_min_spin.setValue(page.target_count_max_spin.value() + 1)
    QApplication.processEvents()

    assert captured_errors == [
        (
            "Fixation Settings Error",
            "Minimum changes per condition cannot be higher than maximum changes. "
            "Lower Minimum changes or increase Maximum changes, then try again.",
        )
    ]
    assert "target_count_min" not in captured_errors[0][1]
    assert "ValidationError" not in captured_errors[0][1]


def test_fixation_accuracy_toggle_controls_response_visibility(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Fixation Accuracy Visibility")

    page = window.setup_dashboard_page.fixation_settings_editor
    window.setup_wizard_page.open_wizard(step_key="fixation")
    window.main_stack.setCurrentWidget(window.setup_wizard_page)
    page.fixation_enabled_checkbox.setChecked(True)
    QApplication.processEvents()

    page.fixation_accuracy_checkbox.setChecked(False)
    QApplication.processEvents()
    assert not page.response_key_edit.isVisible()
    assert not page.response_key_button.isVisible()
    assert not page.response_window_spin.isVisible()

    page.fixation_accuracy_checkbox.setChecked(True)
    QApplication.processEvents()
    assert page.response_key_edit.isVisible()
    assert page.response_key_button.isVisible()
    assert page.response_window_spin.isVisible()


def test_fixation_disable_hides_dependent_sections(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Fixation Enablement Visibility")

    page = window.setup_dashboard_page.fixation_settings_editor
    window.setup_wizard_page.open_wizard(step_key="fixation")
    window.main_stack.setCurrentWidget(window.setup_wizard_page)
    page.fixation_enabled_checkbox.setChecked(True)
    page.fixation_accuracy_checkbox.setChecked(True)
    QApplication.processEvents()
    assert page.target_count_mode_combo.isVisible()
    assert page.target_duration_spin.isVisible()
    assert page.base_color_combo.isVisible()
    assert page.response_key_edit.isVisible()
    assert page.response_key_button.isVisible()
    assert page.fixation_accuracy_checkbox.isEnabled()

    page.fixation_enabled_checkbox.setChecked(False)
    QApplication.processEvents()
    assert not page.target_count_mode_combo.isVisible()
    assert not page.target_duration_spin.isVisible()
    assert not page.base_color_combo.isVisible()
    assert not page.response_key_edit.isVisible()
    assert not page.response_key_button.isVisible()
    assert not page.fixation_accuracy_checkbox.isEnabled()
    assert page.fixation_accuracy_checkbox.isChecked() is False


def test_cycle_tooltips_and_fixation_feasibility_render_and_update(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Cycle Guidance")

    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)
    assert (
        window.conditions_page.sequence_count_spin.toolTip()
        == "Cycle = one turn of base presentations plus one oddball presentation."
    )
    assert (
        window.conditions_page.oddball_cycles_spin.toolTip()
        == "Cycle = one turn of base presentations plus one oddball presentation."
    )

    page = window.setup_dashboard_page.fixation_settings_editor
    window.main_stack.setCurrentWidget(window.setup_wizard_page)
    page.fixation_enabled_checkbox.setChecked(True)
    page.target_count_mode_combo.setCurrentIndex(page.target_count_mode_combo.findData("fixed"))
    page.changes_per_sequence_spin.setValue(4)
    QApplication.processEvents()

    guidance_before = page.fixation_feasibility_label.text()
    assert "Estimated maximum feasible cross changes per condition:" in guidance_before
    assert "Refresh rate:" not in guidance_before
    assert "Per-condition estimated feasible max color changes:" not in guidance_before
    assert (
        page.fixation_feasibility_label.toolTip()
        == "Derived from each condition's duration and the current fixation timing settings."
    )
    feasibility_card = page.findChild(QWidget, "fixation_feasibility_card")
    assert feasibility_card is not None
    assert (
        feasibility_card.toolTip()
        == "Derived from each condition's duration and the current fixation timing settings."
    )

    page.target_duration_spin.setValue(900)
    QApplication.processEvents()
    guidance_after = page.fixation_feasibility_label.text()
    assert guidance_after != guidance_before
    assert "Estimated maximum feasible cross changes per condition:" in guidance_after


def test_fixation_feasibility_shows_single_value_for_uniform_condition_lengths(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Uniform Feasibility")
    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)

    page = window.setup_dashboard_page.fixation_settings_editor
    window.main_stack.setCurrentWidget(window.setup_wizard_page)
    QApplication.processEvents()

    guidance = page.fixation_feasibility_label.text()
    assert "Estimated maximum feasible cross changes per condition:" in guidance
    assert "varies by condition" not in guidance
    assert "\n" not in guidance


def test_save_blocked_when_condition_repeat_cycle_values_differ(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Save Consistency Gate")

    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)
    ordered_conditions = window.document.ordered_conditions()
    assert len(ordered_conditions) == 2

    window.document.update_condition(
        ordered_conditions[1].condition_id,
        sequence_count=ordered_conditions[0].sequence_count + 1,
    )

    messages: list[str] = []

    def _capture_exec(dialog: QMessageBox) -> int:
        messages.append(dialog.text())
        return int(QMessageBox.StandardButton.Ok)

    monkeypatch.setattr("fpvs_studio.gui.main_window.QMessageBox.exec", _capture_exec)

    assert window.save_project() is False
    assert window.document.dirty is True
    assert any(_CONDITION_LENGTH_ERROR_MESSAGE in message for message in messages)


def test_launch_blocked_when_condition_repeat_cycle_values_differ(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Run Consistency Gate")
    _prepare_compile_ready_project(window, tmp_path / "consistency-gate-1")
    _prepare_compile_ready_project(window, tmp_path / "consistency-gate-2")
    ordered_conditions = window.document.ordered_conditions()
    assert len(ordered_conditions) == 2

    window.document.update_condition(
        ordered_conditions[1].condition_id,
        oddball_cycle_repeats_per_sequence=(
            ordered_conditions[0].oddball_cycle_repeats_per_sequence + 1
        ),
    )

    messages: list[str] = []

    def _capture_exec(dialog: QMessageBox) -> int:
        messages.append(dialog.text())
        return int(QMessageBox.StandardButton.Ok)

    monkeypatch.setattr("fpvs_studio.gui.main_window.QMessageBox.exec", _capture_exec)
    prompt_calls = 0
    launch_calls = 0

    def _capture_prompt() -> str:
        nonlocal prompt_calls
        prompt_calls += 1
        return "00011"

    def _capture_launch(*_args, **_kwargs):
        nonlocal launch_calls
        launch_calls += 1
        raise AssertionError("launch_session should not be called when launch preflight fails")

    monkeypatch.setattr(window.run_page, "_prompt_participant_number", _capture_prompt)
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _capture_launch)

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    assert prompt_calls == 0
    assert launch_calls == 0
    assert any(_CONDITION_LENGTH_ERROR_MESSAGE in message for message in messages)


def test_new_condition_uses_project_condition_defaults(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Condition Defaults")

    profile_index = (
        window.setup_dashboard_page.project_overview_editor.condition_profile_combo.findData(
            SIXTY_HZ_BLANK_FIXATION_PROFILE_ID
        )
    )
    assert profile_index >= 0
    window.setup_dashboard_page.project_overview_editor.condition_profile_combo.setCurrentIndex(
        profile_index
    )

    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = window.conditions_page.selected_condition_id()
    assert condition_id is not None
    condition = window.document.get_condition(condition_id)
    assert condition is not None

    assert condition.duty_cycle_mode == DutyCycleMode.BLANK_50
    assert condition.sequence_count == 1
    assert condition.oddball_cycle_repeats_per_sequence == 146


def test_condition_template_selection_standardizes_existing_rows(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Condition Standardization")

    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)
    first_condition_id = window.conditions_page.selected_condition_id()
    assert first_condition_id is not None
    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)
    second_condition_id = window.conditions_page.selected_condition_id()
    assert second_condition_id is not None
    assert second_condition_id != first_condition_id

    window.document.update_condition(
        first_condition_id,
        sequence_count=2,
        oddball_cycle_repeats_per_sequence=88,
        duty_cycle_mode=DutyCycleMode.CONTINUOUS,
    )
    window.document.update_condition(
        second_condition_id,
        sequence_count=3,
        oddball_cycle_repeats_per_sequence=90,
        duty_cycle_mode=DutyCycleMode.CONTINUOUS,
    )

    profile_index = (
        window.setup_dashboard_page.project_overview_editor.condition_profile_combo.findData(
            SIXTY_HZ_BLANK_FIXATION_PROFILE_ID
        )
    )
    assert profile_index >= 0
    window.setup_dashboard_page.project_overview_editor.condition_profile_combo.setCurrentIndex(
        profile_index
    )

    first_after = window.document.get_condition(first_condition_id)
    second_after = window.document.get_condition(second_condition_id)
    assert first_after is not None
    assert second_after is not None
    assert first_after.duty_cycle_mode == DutyCycleMode.BLANK_50
    assert second_after.duty_cycle_mode == DutyCycleMode.BLANK_50
    assert first_after.sequence_count == 1
    assert second_after.sequence_count == 1
    assert first_after.oddball_cycle_repeats_per_sequence == 146
    assert second_after.oddball_cycle_repeats_per_sequence == 146


def test_switching_existing_blank_project_to_continuous_compiles_without_blank_frames(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Continuous Launch")

    blank_index = (
        window.setup_dashboard_page.project_overview_editor.condition_profile_combo.findData(
            SIXTY_HZ_BLANK_FIXATION_PROFILE_ID
        )
    )
    assert blank_index >= 0
    window.setup_dashboard_page.project_overview_editor.condition_profile_combo.setCurrentIndex(
        blank_index
    )
    _prepare_compile_ready_project(window, tmp_path / "continuous-launch")
    condition_id = window.conditions_page.selected_condition_id()
    assert condition_id is not None
    condition = window.document.get_condition(condition_id)
    assert condition is not None
    assert condition.duty_cycle_mode == DutyCycleMode.BLANK_50

    continuous_index = (
        window.setup_dashboard_page.project_overview_editor.condition_profile_combo.findData(
            STUDIO_DEFAULT_PROFILE_ID
        )
    )
    assert continuous_index >= 0
    window.setup_dashboard_page.project_overview_editor.condition_profile_combo.setCurrentIndex(
        continuous_index
    )

    condition = window.document.get_condition(condition_id)
    assert condition is not None
    assert condition.duty_cycle_mode == DutyCycleMode.CONTINUOUS
    session_plan = window.document.compile_session(refresh_hz=60.0)
    run_spec = session_plan.ordered_entries()[0].run_spec
    assert run_spec.display.on_frames == run_spec.display.frames_per_stimulus
    assert run_spec.display.off_frames == 0
    assert all(event.off_frames == 0 for event in run_spec.stimulus_sequence)


def test_launch_reports_actionable_condition_level_fixation_error_before_prompt(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Fixation Fit Error")
    _prepare_compile_ready_project(window, tmp_path / "fixation-fit-error")
    condition_id = window.conditions_page.selected_condition_id()
    assert condition_id is not None
    window.document.update_condition(
        condition_id,
        oddball_cycle_repeats_per_sequence=2,
        sequence_count=1,
    )

    page = window.fixation_cross_settings_page
    page.fixation_enabled_checkbox.setChecked(True)
    page.target_count_mode_combo.setCurrentIndex(page.target_count_mode_combo.findData("fixed"))
    page.changes_per_sequence_spin.setValue(4)
    page.target_duration_spin.setValue(230)
    page.min_gap_spin.setValue(1000)
    page.max_gap_spin.setValue(3000)

    messages: list[str] = []

    def _capture_exec(dialog: QMessageBox) -> int:
        messages.append(dialog.text())
        return int(QMessageBox.StandardButton.Ok)

    monkeypatch.setattr("fpvs_studio.gui.main_window.QMessageBox.exec", _capture_exec)
    prompt_calls = 0
    launch_calls = 0

    def _capture_prompt() -> str:
        nonlocal prompt_calls
        prompt_calls += 1
        return "00123"

    def _capture_launch(*_args, **_kwargs):
        nonlocal launch_calls
        launch_calls += 1
        raise AssertionError("launch_session should not be called when launch preflight fails")

    monkeypatch.setattr(window.run_page, "_prompt_participant_number", _capture_prompt)
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _capture_launch)

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    assert any("Required duration:" in message for message in messages)
    assert any(
        "Color changes are distributed across the full condition duration." in message
        for message in messages
    )
    assert any("Minimum cycle count needed" in message for message in messages)
    assert prompt_calls == 0
    assert launch_calls == 0


