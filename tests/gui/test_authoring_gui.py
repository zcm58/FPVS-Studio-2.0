"""PySide6 GUI workflow tests for the Phase 5 authoring application."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton
import pytest

from fpvs_studio.core.enums import DutyCycleMode, InterConditionMode, RunMode, StimulusVariant
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import load_project_file
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.create_project_dialog import CreateProjectDialog
from fpvs_studio.gui.document import _CONDITION_LENGTH_ERROR_MESSAGE
from fpvs_studio.gui.main_window import ParticipantNumberDialog
from fpvs_studio.gui.settings_dialog import AppSettingsDialog


def _write_image_directory(target_dir: Path, *, size: tuple[int, int] = (96, 96)) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, 4):
        Image.new("RGB", size, color=(index * 20, index * 10, index * 5)).save(
            target_dir / f"stimulus-{index:02d}.png"
        )
    return target_dir


def _open_created_project(controller: StudioController, qtbot, tmp_path: Path, name: str = "Demo Project"):
    document = controller.create_project(name, tmp_path)
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)
    return document, controller.main_window


def _prepare_compile_ready_project(window, tmp_path: Path) -> None:
    window.conditions_page._add_condition()
    base_dir = _write_image_directory(tmp_path / "base")
    oddball_dir = _write_image_directory(tmp_path / "oddball")
    condition_id = window.conditions_page.selected_condition_id()
    assert condition_id is not None
    window.document.import_condition_stimulus_folder(condition_id, role="base", source_dir=base_dir)
    window.document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=oddball_dir,
    )


@pytest.fixture
def controller(qtbot, qapp, tmp_path: Path) -> StudioController:
    controller = StudioController(qapp)
    fpvs_root_dir = tmp_path / "fpvs-root"
    fpvs_root_dir.mkdir(parents=True, exist_ok=True)
    controller.save_fpvs_root_dir(fpvs_root_dir)
    controller.show_welcome()
    assert controller.welcome_window is not None
    qtbot.addWidget(controller.welcome_window)
    return controller


def test_welcome_window_smoke(qtbot, controller: StudioController) -> None:
    welcome = controller.welcome_window
    assert welcome is not None
    create_button = welcome.findChild(QPushButton, "create_project_button")
    open_button = welcome.findChild(QPushButton, "open_project_button")

    with qtbot.waitSignal(welcome.create_requested, timeout=1000):
        qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)
    with qtbot.waitSignal(welcome.open_requested, timeout=1000):
        qtbot.mouseClick(open_button, Qt.MouseButton.LeftButton)


def test_open_existing_project_dialog_uses_saved_root_as_default(
    controller: StudioController,
    monkeypatch,
) -> None:
    root_dir = controller.load_fpvs_root_dir()
    assert root_dir is not None

    captured_initial_dirs: list[str] = []

    def _capture_directory(_parent, _title, initial_directory):
        captured_initial_dirs.append(initial_directory)
        return ""

    monkeypatch.setattr(
        "fpvs_studio.gui.controller.QFileDialog.getExistingDirectory",
        _capture_directory,
    )

    controller.show_open_project_dialog()

    assert captured_initial_dirs == [str(root_dir)]


def test_create_project_dialog_prefills_saved_root_parent_directory(
    controller: StudioController,
    monkeypatch,
) -> None:
    root_dir = controller.load_fpvs_root_dir()
    assert root_dir is not None

    captured_parent_dirs: list[str] = []

    def _capture_exec(dialog: CreateProjectDialog) -> int:
        captured_parent_dirs.append(dialog.project_root_edit.text())
        return int(dialog.DialogCode.Rejected)

    monkeypatch.setattr(CreateProjectDialog, "exec", _capture_exec)

    controller.show_create_project_dialog()

    assert captured_parent_dirs == [str(root_dir)]


def test_show_welcome_requires_fpvs_root_and_cancel_path_exits_app(
    qapp,
    monkeypatch,
) -> None:
    controller = StudioController(qapp)

    prompt_calls = 0
    quit_calls = 0

    def _cancel_selection(*_args, **_kwargs) -> str:
        nonlocal prompt_calls
        prompt_calls += 1
        return ""

    def _confirm_exit(*_args, **_kwargs):
        return QMessageBox.StandardButton.Yes

    def _capture_quit() -> None:
        nonlocal quit_calls
        quit_calls += 1

    monkeypatch.setattr(
        "fpvs_studio.gui.controller.QFileDialog.getExistingDirectory",
        _cancel_selection,
    )
    monkeypatch.setattr("fpvs_studio.gui.controller.QMessageBox.question", _confirm_exit)
    monkeypatch.setattr(qapp, "quit", _capture_quit)

    controller.show_welcome()

    assert prompt_calls == 1
    assert quit_calls == 1
    assert controller.welcome_window is None


def test_show_welcome_prompts_for_missing_root_then_persists_selection(
    qtbot,
    qapp,
    tmp_path: Path,
    monkeypatch,
) -> None:
    controller = StudioController(qapp)
    selected_root = tmp_path / "selected-fpvs-root"
    selected_root.mkdir(parents=True, exist_ok=True)

    prompt_titles: list[str] = []

    def _select_root(_parent, title, _initial_directory) -> str:
        prompt_titles.append(title)
        return str(selected_root)

    monkeypatch.setattr(
        "fpvs_studio.gui.controller.QFileDialog.getExistingDirectory",
        _select_root,
    )

    controller.show_welcome()

    assert controller.welcome_window is not None
    qtbot.addWidget(controller.welcome_window)
    assert controller.welcome_window.isVisible()
    assert controller.load_fpvs_root_dir() == selected_root
    assert prompt_titles == ["Choose FPVS Studio Root Folder"]


def test_invalid_saved_root_is_reprompted_on_startup(
    qtbot,
    qapp,
    tmp_path: Path,
    monkeypatch,
) -> None:
    controller = StudioController(qapp)
    deleted_root = tmp_path / "missing-root"
    deleted_root.mkdir(parents=True, exist_ok=True)
    controller.save_fpvs_root_dir(deleted_root)
    deleted_root.rmdir()

    replacement_root = tmp_path / "replacement-root"
    replacement_root.mkdir(parents=True, exist_ok=True)

    prompt_calls = 0

    def _select_replacement(*_args, **_kwargs) -> str:
        nonlocal prompt_calls
        prompt_calls += 1
        return str(replacement_root)

    monkeypatch.setattr(
        "fpvs_studio.gui.controller.QFileDialog.getExistingDirectory",
        _select_replacement,
    )

    controller.show_welcome()

    assert controller.welcome_window is not None
    qtbot.addWidget(controller.welcome_window)
    assert prompt_calls == 1
    assert controller.load_fpvs_root_dir() == replacement_root


def test_settings_dialog_shows_root_and_change_button_updates_value(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    initial_root = tmp_path / "initial-root"
    initial_root.mkdir(parents=True, exist_ok=True)
    updated_root = tmp_path / "updated-root"
    updated_root.mkdir(parents=True, exist_ok=True)

    changed_roots: list[Path] = []
    dialog = AppSettingsDialog(
        fpvs_root_dir=initial_root,
        on_change_fpvs_root_dir=lambda path: changed_roots.append(path),
    )
    qtbot.addWidget(dialog)

    root_value_label = dialog.findChild(QLabel, "fpvs_root_dir_value")
    change_button = dialog.findChild(QPushButton, "change_fpvs_root_dir_button")
    assert root_value_label is not None
    assert change_button is not None
    assert root_value_label.text() == str(initial_root)

    monkeypatch.setattr(
        "fpvs_studio.gui.settings_dialog.QFileDialog.getExistingDirectory",
        lambda *_args, **_kwargs: str(updated_root),
    )
    qtbot.mouseClick(change_button, Qt.MouseButton.LeftButton)

    assert changed_roots == [updated_root]
    assert root_value_label.text() == str(updated_root)


def test_file_settings_action_changes_root_and_updates_open_create_defaults(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Settings Flow Project")
    original_root = controller.load_fpvs_root_dir()
    assert original_root is not None

    updated_root = tmp_path / "updated-fpvs-root"
    updated_root.mkdir(parents=True, exist_ok=True)

    assert window.settings_action.text() == "Settings..."
    assert window.settings_action.objectName() == "settings_action"

    monkeypatch.setattr(
        "fpvs_studio.gui.settings_dialog.QFileDialog.getExistingDirectory",
        lambda *_args, **_kwargs: str(updated_root),
    )

    def _fake_settings_exec(dialog: AppSettingsDialog) -> int:
        root_value_label = dialog.findChild(QLabel, "fpvs_root_dir_value")
        assert root_value_label is not None
        assert root_value_label.text() == str(original_root)
        dialog._change_fpvs_root_directory()
        return int(dialog.DialogCode.Accepted)

    monkeypatch.setattr(AppSettingsDialog, "exec", _fake_settings_exec)

    window.settings_action.trigger()
    assert controller.load_fpvs_root_dir() == updated_root

    captured_open_default_dirs: list[str] = []

    def _capture_open_directory(_parent, _title, initial_directory):
        captured_open_default_dirs.append(initial_directory)
        return ""

    monkeypatch.setattr(
        "fpvs_studio.gui.controller.QFileDialog.getExistingDirectory",
        _capture_open_directory,
    )
    controller.show_open_project_dialog()
    assert captured_open_default_dirs[-1] == str(updated_root)

    captured_create_default_dirs: list[str] = []

    def _capture_create_exec(dialog: CreateProjectDialog) -> int:
        captured_create_default_dirs.append(dialog.project_root_edit.text())
        return int(dialog.DialogCode.Rejected)

    monkeypatch.setattr(CreateProjectDialog, "exec", _capture_create_exec)
    controller.show_create_project_dialog()
    assert captured_create_default_dirs[-1] == str(updated_root)


def test_opening_project_outside_saved_root_is_allowed_and_keeps_saved_root(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    root_dir = controller.load_fpvs_root_dir()
    assert root_dir is not None

    outside_parent = tmp_path / "outside-root-parent"
    outside_parent.mkdir(parents=True, exist_ok=True)
    scaffold = create_project(outside_parent, "Outside Root Project")

    document = controller.open_project(scaffold.project_root)
    assert document is not None
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)
    assert controller.load_fpvs_root_dir() == root_dir


def test_create_project_flow_scaffolds_project_and_opens_main_window(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    dialog = CreateProjectDialog()
    qtbot.addWidget(dialog)
    dialog.project_name_edit.setText("Visual Oddball")
    dialog.project_root_edit.setText(str(tmp_path))
    dialog.accept()
    assert dialog.result() == dialog.DialogCode.Accepted

    document, window = _open_created_project(
        controller,
        qtbot,
        dialog.parent_directory,
        dialog.project_name,
    )

    assert window.isVisible()
    assert document.project_root.name == "visual-oddball"
    assert (document.project_root / "project.json").is_file()
    assert window.project_page.project_name_edit.text() == "Visual Oddball"


def test_open_existing_project_populates_gui_correctly(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    scaffold = create_project(tmp_path, "Opened Project")

    controller.open_project(scaffold.project_root)
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)

    assert controller.main_window.project_page.project_name_edit.text() == "Opened Project"
    assert controller.main_window.project_page.project_root_value.text().endswith("opened-project")


def test_project_description_typing_round_trips_without_cursor_reset(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    typed_text = "testing this, why is this happening"
    _, window = _open_created_project(controller, qtbot, tmp_path, "Description Project")

    description_edit = window.project_page.project_description_edit
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

    assert reopened_window.project_page.project_description_edit.toPlainText() == typed_text
    assert reopened_project.meta.description == typed_text


def test_condition_editor_round_trip(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Roundtrip Conditions")

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
    window.conditions_page.duty_cycle_combo.setCurrentIndex(
        window.conditions_page.duty_cycle_combo.findData(DutyCycleMode.BLANK_50)
    )

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

    page = window.session_fixation_page
    page.block_count_spin.setValue(3)
    page.session_seed_spin.setValue(123456)
    page.randomize_checkbox.setChecked(False)
    page.inter_condition_mode_combo.setCurrentIndex(
        page.inter_condition_mode_combo.findData(InterConditionMode.MANUAL_CONTINUE)
    )
    page.continue_key_edit.setText("return")
    page.continue_key_edit.editingFinished.emit()
    page.fixation_enabled_checkbox.setChecked(True)
    page.changes_per_sequence_spin.setValue(4)
    page.fixation_accuracy_checkbox.setChecked(True)
    page.target_count_mode_combo.setCurrentIndex(page.target_count_mode_combo.findData("randomized"))
    page.target_count_min_spin.setValue(2)
    page.target_count_max_spin.setValue(5)
    page.no_repeat_count_checkbox.setChecked(True)
    page.target_duration_spin.setValue(300)
    page.base_color_edit.setText("#112233")
    page.base_color_edit.editingFinished.emit()
    page.target_color_edit.setText("#445566")
    page.target_color_edit.editingFinished.emit()
    page.response_key_edit.setText("space")
    page.response_key_edit.editingFinished.emit()
    page.response_window_spin.setValue(1.25)
    page.cross_size_spin.setValue(52)
    page.line_width_spin.setValue(6)

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
    assert session.continue_key == "return"
    assert fixation.enabled is True
    assert fixation.accuracy_task_enabled is True
    assert fixation.target_count_mode == "randomized"
    assert fixation.changes_per_sequence == 4
    assert fixation.target_count_min == 2
    assert fixation.target_count_max == 5
    assert fixation.no_immediate_repeat_count is True
    assert fixation.target_duration_ms == 300
    assert fixation.base_color == "#112233"
    assert fixation.target_color == "#445566"
    assert fixation.response_key == "space"
    assert fixation.response_window_seconds == 1.25
    assert fixation.response_keys == ["space"]
    assert fixation.cross_size_px == 52
    assert fixation.line_width_px == 6


def test_fixation_session_page_maps_fixed_target_count_mode_to_backend(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Fixed Target Count")

    page = window.session_fixation_page
    page.target_count_mode_combo.setCurrentIndex(page.target_count_mode_combo.findData("fixed"))
    page.changes_per_sequence_spin.setValue(7)

    fixation = window.document.project.settings.fixation_task
    assert fixation.target_count_mode == "fixed"
    assert fixation.changes_per_sequence == 7


def test_fixation_session_page_exposes_accuracy_task_controls(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Fixation Controls")

    page = window.session_fixation_page
    assert page.findChild(type(page.fixation_accuracy_checkbox), "fixation_accuracy_checkbox") is not None
    assert page.findChild(type(page.target_count_mode_combo), "target_count_mode_combo") is not None
    assert page.findChild(type(page.target_count_min_spin), "target_count_min_spin") is not None
    assert page.findChild(type(page.target_count_max_spin), "target_count_max_spin") is not None
    assert page.findChild(type(page.no_repeat_count_checkbox), "no_immediate_repeat_count_checkbox") is not None
    assert page.findChild(type(page.response_key_edit), "response_key_edit") is not None
    assert page.findChild(type(page.response_window_spin), "response_window_seconds_spin") is not None


def test_cycle_tooltips_and_condition_guidance_render_and_update(
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

    page = window.session_fixation_page
    guidance_before = page.fixation_guidance_text.toPlainText()
    assert "Color changes are distributed across each full condition duration." in guidance_before
    assert "Condition 1:" in guidance_before
    assert "estimated max feasible color changes per condition" in guidance_before

    page.target_duration_spin.setValue(900)
    guidance_after = page.fixation_guidance_text.toPlainText()
    assert guidance_after != guidance_before


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


def test_compile_and_preflight_blocked_when_condition_repeat_cycle_values_differ(
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

    qtbot.mouseClick(window.run_page.compile_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.run_page.preflight_button, Qt.MouseButton.LeftButton)

    matching_messages = [message for message in messages if _CONDITION_LENGTH_ERROR_MESSAGE in message]
    assert len(matching_messages) >= 2


def test_new_condition_inherits_first_condition_repeat_cycle_values(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Condition Inheritance")

    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)
    first_condition_id = window.conditions_page.selected_condition_id()
    assert first_condition_id is not None

    window.conditions_page.sequence_count_spin.setValue(3)
    window.conditions_page.oddball_cycles_spin.setValue(101)

    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)
    second_condition_id = window.conditions_page.selected_condition_id()
    assert second_condition_id is not None
    assert second_condition_id != first_condition_id

    second_condition = window.document.get_condition(second_condition_id)
    assert second_condition is not None
    assert second_condition.sequence_count == 3
    assert second_condition.oddball_cycle_repeats_per_sequence == 101


def test_preflight_reports_actionable_condition_level_fixation_error(
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

    page = window.session_fixation_page
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

    qtbot.mouseClick(window.run_page.preflight_button, Qt.MouseButton.LeftButton)

    assert any("Required duration:" in message for message in messages)
    assert any(
        "Color changes are distributed across the full condition duration." in message
        for message in messages
    )
    assert any("Minimum cycle count needed" in message for message in messages)


def test_assets_preprocessing_import_and_materialize_updates_status(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Assets Project")
    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)

    base_dir = _write_image_directory(tmp_path / "asset-base")
    oddball_dir = _write_image_directory(tmp_path / "asset-oddball")
    selection = iter([str(base_dir), str(oddball_dir)])
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: next(selection),
    )

    window.main_tabs.setCurrentWidget(window.assets_page)
    window.assets_page.assets_table.selectRow(0)
    qtbot.mouseClick(window.assets_page.import_source_button, Qt.MouseButton.LeftButton)
    window.assets_page.assets_table.selectRow(1)
    qtbot.mouseClick(window.assets_page.import_source_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.assets_page.materialize_button, Qt.MouseButton.LeftButton)

    assert window.document.manifest is not None
    assert "Manifest status:" in window.assets_page.assets_status_text.toPlainText()
    assert StimulusVariant.GRAYSCALE in window.document.project.stimulus_sets[0].available_variants


def test_assets_import_validation_failure_is_reported(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Invalid Assets Project")
    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)

    invalid_dir = tmp_path / "invalid-assets"
    _write_image_directory(invalid_dir, size=(96, 96))
    Image.new("RGB", (128, 96), color=(255, 0, 0)).save(invalid_dir / "mismatch.png")

    messages: list[str] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(invalid_dir),
    )

    def _capture_exec(dialog: QMessageBox) -> int:
        messages.append(dialog.text())
        return int(QMessageBox.StandardButton.Ok)

    monkeypatch.setattr("fpvs_studio.gui.main_window.QMessageBox.exec", _capture_exec)

    window.main_tabs.setCurrentWidget(window.assets_page)
    window.assets_page.assets_table.selectRow(0)
    qtbot.mouseClick(window.assets_page.import_source_button, Qt.MouseButton.LeftButton)

    assert any("identical resolution" in message for message in messages)


def test_preflight_action_invokes_backend_preflight(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Preflight Project")
    _prepare_compile_ready_project(window, tmp_path / "preflight")

    captures: dict[str, object] = {}
    monkeypatch.setattr(
        "fpvs_studio.gui.document.create_engine",
        lambda engine_name: {"engine_name": engine_name},
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.document.preflight_session_plan",
        lambda project_root, session_plan, engine: captures.update(
            {
                "project_root": project_root,
                "session_id": session_plan.session_id,
                "engine": engine,
            }
        ),
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )

    qtbot.mouseClick(window.run_page.preflight_button, Qt.MouseButton.LeftButton)

    assert captures["project_root"] == window.document.project_root
    assert captures["engine"] == {"engine_name": "psychopy"}
    assert "preflight passed" in window.run_page.summary_text.toPlainText().lower()


def test_launch_action_wires_runtime_launcher_with_serial_settings(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Launch Project")
    _prepare_compile_ready_project(window, tmp_path / "launch")

    captures: dict[str, object] = {}
    participant_number = "00042"
    prompt_calls = 0

    def _fake_launch(project_root, session_plan, participant_number, launch_settings):
        captures["project_root"] = project_root
        captures["session_plan"] = session_plan
        captures["participant_number"] = participant_number
        captures["launch_settings"] = launch_settings
        return SessionExecutionSummary(
            project_id=session_plan.project_id,
            session_id=session_plan.session_id,
            engine_name="stub",
            run_mode=RunMode.TEST,
            participant_number=participant_number,
            random_seed=session_plan.random_seed,
            started_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 3, 8, 10, 1, tzinfo=timezone.utc),
            total_condition_count=session_plan.total_runs,
            completed_condition_count=session_plan.total_runs,
            output_dir=f"runs/{session_plan.session_id}",
        )

    def _fake_prompt() -> str:
        nonlocal prompt_calls
        prompt_calls += 1
        return participant_number

    monkeypatch.setattr(window.run_page, "_prompt_participant_number", _fake_prompt)
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )

    window.run_page.serial_port_edit.setText("COM3")
    window.run_page.serial_port_edit.editingFinished.emit()
    window.run_page.serial_baudrate_spin.setValue(57600)
    window.run_page.display_index_edit.setText("1")
    assert window.run_page.fullscreen_checkbox.isChecked() is True

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    launch_settings = captures["launch_settings"]
    assert prompt_calls == 1
    assert captures["participant_number"] == participant_number
    assert captures["project_root"] == window.document.project_root
    assert launch_settings.serial_port == "COM3"
    assert launch_settings.serial_baudrate == 57600
    assert launch_settings.display_index == 1
    assert launch_settings.test_mode is True
    assert launch_settings.fullscreen is True
    assert f"participant number: {participant_number}" in window.run_page.summary_text.toPlainText().lower()
    assert "runtime launch completed" in window.run_page.summary_text.toPlainText().lower()


def test_launch_action_duplicate_participant_yes_still_launches(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Duplicate Participant Yes")
    _prepare_compile_ready_project(window, tmp_path / "launch-duplicate-yes")

    captures: dict[str, object] = {}
    prompt_calls = 0
    warning_messages: list[str] = []

    def _fake_launch(project_root, session_plan, participant_number, launch_settings):
        captures["participant_number"] = participant_number
        return SessionExecutionSummary(
            project_id=session_plan.project_id,
            session_id=session_plan.session_id,
            engine_name="stub",
            run_mode=RunMode.TEST,
            participant_number=participant_number,
            random_seed=session_plan.random_seed,
            started_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 3, 8, 10, 1, tzinfo=timezone.utc),
            total_condition_count=session_plan.total_runs,
            completed_condition_count=session_plan.total_runs,
            output_dir="runs/00011_run2",
        )

    def _fake_prompt() -> str:
        nonlocal prompt_calls
        prompt_calls += 1
        return "00011"

    def _fake_question(_parent, _title, text, *_args, **_kwargs):
        warning_messages.append(text)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(window.run_page, "_prompt_participant_number", _fake_prompt)
    monkeypatch.setattr(window.document, "has_completed_session_for_participant", lambda value: value == "00011")
    monkeypatch.setattr("fpvs_studio.gui.main_window.QMessageBox.question", _fake_question)
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    assert prompt_calls == 1
    assert captures["participant_number"] == "00011"
    assert len(warning_messages) == 1
    assert "already completed this study" in warning_messages[0]


def test_launch_action_duplicate_participant_no_reprompts_until_new_value(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Duplicate Participant No")
    _prepare_compile_ready_project(window, tmp_path / "launch-duplicate-no")

    captures: dict[str, object] = {}
    prompt_sequence = iter(["00011", "00011", "00012"])
    prompt_calls = 0
    warning_messages: list[str] = []

    def _fake_launch(project_root, session_plan, participant_number, launch_settings):
        captures["participant_number"] = participant_number
        return SessionExecutionSummary(
            project_id=session_plan.project_id,
            session_id=session_plan.session_id,
            engine_name="stub",
            run_mode=RunMode.TEST,
            participant_number=participant_number,
            random_seed=session_plan.random_seed,
            started_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 3, 8, 10, 1, tzinfo=timezone.utc),
            total_condition_count=session_plan.total_runs,
            completed_condition_count=session_plan.total_runs,
            output_dir="runs/00012",
        )

    def _fake_prompt() -> str:
        nonlocal prompt_calls
        prompt_calls += 1
        return next(prompt_sequence)

    def _fake_question(_parent, _title, text, *_args, **_kwargs):
        warning_messages.append(text)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(window.run_page, "_prompt_participant_number", _fake_prompt)
    monkeypatch.setattr(window.document, "has_completed_session_for_participant", lambda value: value == "00011")
    monkeypatch.setattr("fpvs_studio.gui.main_window.QMessageBox.question", _fake_question)
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    assert prompt_calls == 3
    assert len(warning_messages) == 2
    assert captures["participant_number"] == "00012"


def test_launch_action_cancelled_participant_prompt_aborts_launch(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Launch Cancel Project")
    _prepare_compile_ready_project(window, tmp_path / "launch-cancel")

    launch_calls = 0

    def _fake_launch(*args, **kwargs):
        nonlocal launch_calls
        launch_calls += 1
        raise AssertionError("launch_session should not be called when participant entry is cancelled")

    monkeypatch.setattr(window.run_page, "_prompt_participant_number", lambda: None)
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    assert launch_calls == 0
    assert "runtime launch completed" not in window.run_page.summary_text.toPlainText().lower()


def test_participant_number_dialog_requires_digits_and_trims_whitespace(qtbot, monkeypatch) -> None:
    dialog = ParticipantNumberDialog()
    qtbot.addWidget(dialog)
    assert dialog.prompt_label.text() == "Please enter the participant number."

    messages: list[str] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.warning",
        lambda _parent, _title, message: messages.append(message),
    )

    dialog.participant_number_edit.setText("   ")
    dialog.accept()
    assert dialog.result() != int(dialog.DialogCode.Accepted)

    dialog.participant_number_edit.setText("A12")
    dialog.accept()
    assert dialog.result() != int(dialog.DialogCode.Accepted)

    dialog.participant_number_edit.setText(" 0012 ")
    dialog.accept()
    assert dialog.result() == int(dialog.DialogCode.Accepted)
    assert dialog.participant_number == "0012"
    assert any("Enter a participant number" in message for message in messages)
    assert any("digits only" in message for message in messages)


def test_unsaved_changes_state_and_guard(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Dirty Project")

    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)
    assert window.document.dirty is True
    assert window.windowTitle().startswith("*")

    assert window.save_project() is True
    assert window.document.dirty is False
    assert not window.windowTitle().startswith("*")

    window.project_page.project_name_edit.setText("Dirty Project Updated")
    window.project_page.project_name_edit.editingFinished.emit()
    assert window.document.dirty is True

    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )
    assert window.maybe_save_changes() is False

    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )
    assert window.maybe_save_changes() is True
