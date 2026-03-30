"""PySide6 GUI workflow tests for the Phase 5 authoring application."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialogButtonBox,
    QGroupBox,
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QToolBar,
    QWidget,
)

from fpvs_studio.core.condition_template_profiles import (
    SIXTY_HZ_BLANK_FIXATION_PROFILE_ID,
    STUDIO_DEFAULT_PROFILE_ID,
    built_in_condition_template_profiles,
    list_condition_template_profiles,
)
from fpvs_studio.core.enums import DutyCycleMode, InterConditionMode, RunMode, StimulusVariant
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.gui.animations import AnimatedTabBar
from fpvs_studio.gui.application import create_application
from fpvs_studio.gui.condition_template_manager_dialog import (
    ConditionTemplateManagerDialog,
    ConditionTemplateProfileEditorDialog,
)
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.create_project_dialog import CreateProjectDialog
from fpvs_studio.gui.document import _CONDITION_LENGTH_ERROR_MESSAGE
from fpvs_studio.gui.main_window import ParticipantNumberDialog
from fpvs_studio.gui.settings_dialog import AppSettingsDialog
from fpvs_studio.gui.welcome_window import WelcomeWindow


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


def _list_widget_text(list_widget: QListWidget) -> str:
    return "\n".join(
        list_widget.item(index).text() for index in range(list_widget.count())
    )


def _find_profile_row(dialog: ConditionTemplateManagerDialog, profile_id: str) -> int:
    for index in range(dialog.profile_list.count()):
        item = dialog.profile_list.item(index)
        if item.data(Qt.ItemDataRole.UserRole) == profile_id:
            return index
    raise AssertionError(f"Profile id '{profile_id}' not found in manager list.")


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


@pytest.fixture(autouse=True)
def _disable_launch_interstitial_delay(monkeypatch) -> None:
    monkeypatch.setattr("fpvs_studio.gui.main_window._LAUNCH_INTERSTITIAL_DURATION_MS", 0)


def test_welcome_window_smoke(qtbot, controller: StudioController) -> None:
    welcome = controller.welcome_window
    assert welcome is not None
    create_button = welcome.findChild(QPushButton, "create_project_button")
    open_button = welcome.findChild(QPushButton, "open_project_button")

    with qtbot.waitSignal(welcome.create_requested, timeout=1000):
        qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)
    with qtbot.waitSignal(welcome.open_requested, timeout=1000):
        qtbot.mouseClick(open_button, Qt.MouseButton.LeftButton)


def test_welcome_window_copy_and_primary_hierarchy(controller: StudioController) -> None:
    welcome = controller.welcome_window
    assert welcome is not None

    headline = welcome.findChild(QLabel, "welcome_headline_label")
    body = welcome.findChild(QLabel, "welcome_body_label")
    create_button = welcome.findChild(QPushButton, "create_project_button")
    open_button = welcome.findChild(QPushButton, "open_project_button")

    assert headline is not None
    assert body is not None
    assert create_button is not None
    assert open_button is not None

    assert headline.text() == "Welcome to FPVS Studio"
    assert body.text() == "Create a new FPVS project or open an existing one."
    assert create_button.text() == "New Project"
    assert open_button.text() == "Open Project"
    assert create_button.property("welcomeRole") == "primary"
    assert open_button.property("welcomeRole") != "primary"


def test_welcome_window_action_buttons_are_horizontally_centered(
    controller: StudioController,
) -> None:
    welcome = controller.welcome_window
    assert welcome is not None

    content_frame = welcome.findChild(QWidget, "welcome_content_frame")
    create_button = welcome.findChild(QPushButton, "create_project_button")
    open_button = welcome.findChild(QPushButton, "open_project_button")

    assert content_frame is not None
    assert create_button is not None
    assert open_button is not None

    welcome.resize(1200, 760)
    QApplication.processEvents()

    create_left = create_button.mapTo(content_frame, create_button.rect().topLeft()).x()
    create_right = create_button.mapTo(content_frame, create_button.rect().bottomRight()).x()
    open_left = open_button.mapTo(content_frame, open_button.rect().topLeft()).x()
    open_right = open_button.mapTo(content_frame, open_button.rect().bottomRight()).x()

    group_left = min(create_left, open_left)
    group_right = max(create_right, open_right)
    button_group_midpoint = (group_left + group_right) / 2.0
    content_midpoint = content_frame.width() / 2.0

    assert abs(button_group_midpoint - content_midpoint) <= 6.0


def test_welcome_window_hero_stack_is_centered_in_panel(controller: StudioController) -> None:
    welcome = controller.welcome_window
    assert welcome is not None

    content_frame = welcome.findChild(QWidget, "welcome_content_frame")
    hero_container = welcome.findChild(QWidget, "welcome_hero_container")

    assert content_frame is not None
    assert hero_container is not None

    welcome.resize(1280, 720)
    QApplication.processEvents()

    hero_center = hero_container.geometry().center()
    frame_center_x = content_frame.width() / 2.0
    frame_center_y = content_frame.height() / 2.0

    assert abs(hero_center.x() - frame_center_x) <= 10.0
    assert abs(hero_center.y() - frame_center_y) <= 18.0


def test_welcome_window_does_not_expose_recent_projects_panel(
    controller: StudioController,
) -> None:
    welcome = controller.welcome_window
    assert welcome is not None
    assert welcome.findChild(QWidget, "welcome_recent_projects_panel") is None


def test_application_bootstrap_sets_non_null_welcome_icon(qapp) -> None:
    app = create_application([])
    assert not app.windowIcon().isNull()
    welcome = WelcomeWindow()
    try:
        assert not welcome.windowIcon().isNull()
    finally:
        welcome.deleteLater()


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


def test_open_project_randomizes_session_seed_per_open_without_dirtying_document(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Seed Randomization")
    project_root = window.document.project_root
    project_file_path = window.document.project_file_path
    persisted_seed = load_project_file(project_file_path).settings.session.session_seed

    seed_values = iter((111_111_111, 222_222_222))

    class _DeterministicSystemRandom:
        def randrange(self, _upper_bound: int) -> int:
            return next(seed_values)

    deterministic_rng = _DeterministicSystemRandom()
    monkeypatch.setattr(
        "fpvs_studio.gui.document.random.SystemRandom",
        lambda: deterministic_rng,
    )

    first_opened = controller.open_project(project_root)
    assert first_opened is not None
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)
    assert controller.main_window.document.project.settings.session.session_seed == 111_111_111
    assert controller.main_window.document.dirty is False

    second_opened = controller.open_project(project_root)
    assert second_opened is not None
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)
    assert controller.main_window.document.project.settings.session.session_seed == 222_222_222
    assert controller.main_window.document.dirty is False
    assert load_project_file(project_file_path).settings.session.session_seed == persisted_seed


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


def test_show_create_project_dialog_normalizes_legacy_template_library(
    controller: StudioController,
    monkeypatch,
) -> None:
    root_dir = controller.load_fpvs_root_dir()
    assert root_dir is not None

    legacy_path = root_dir / "condition_templates.json"
    legacy_path.write_text('{"profiles":[]}', encoding="utf-8")
    assert legacy_path.is_file()
    assert not (root_dir / "templates" / "condition_templates.json").exists()

    def _capture_exec(_dialog: CreateProjectDialog) -> int:
        return int(CreateProjectDialog.DialogCode.Rejected)

    monkeypatch.setattr(CreateProjectDialog, "exec", _capture_exec)
    controller.show_create_project_dialog()

    assert not legacy_path.exists()
    assert (root_dir / "templates" / "condition_templates.json").is_file()


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
    shutil.rmtree(deleted_root)

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


def test_settings_dialog_manage_templates_button_triggers_callback(
    qtbot,
    tmp_path: Path,
) -> None:
    root_dir = tmp_path / "settings-root"
    root_dir.mkdir(parents=True, exist_ok=True)
    callback_calls = 0

    def _capture_manage_templates() -> None:
        nonlocal callback_calls
        callback_calls += 1

    dialog = AppSettingsDialog(
        fpvs_root_dir=root_dir,
        on_change_fpvs_root_dir=lambda _path: None,
        on_manage_condition_templates=_capture_manage_templates,
    )
    qtbot.addWidget(dialog)

    manage_button = dialog.findChild(QPushButton, "manage_condition_templates_button")
    assert manage_button is not None
    qtbot.mouseClick(manage_button, Qt.MouseButton.LeftButton)
    assert callback_calls == 1


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


def test_create_project_dialog_requires_condition_template_selection(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    dialog = CreateProjectDialog(condition_template_profiles=built_in_condition_template_profiles())
    qtbot.addWidget(dialog)
    messages: list[str] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.create_project_dialog.QMessageBox.warning",
        lambda _parent, _title, message: messages.append(message),
    )

    dialog.project_name_edit.setText("Condition Template Required")
    dialog.project_root_edit.setText(str(tmp_path))
    dialog.accept()

    assert dialog.result() != int(dialog.DialogCode.Accepted)
    assert any("condition template profile" in message.lower() for message in messages)

    dialog.condition_profile_combo.setCurrentIndex(0)
    dialog.accept()
    assert dialog.result() == int(dialog.DialogCode.Accepted)


def test_create_project_dialog_rejects_reserved_project_name(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    dialog = CreateProjectDialog(condition_template_profiles=built_in_condition_template_profiles())
    qtbot.addWidget(dialog)
    messages: list[str] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.create_project_dialog.QMessageBox.warning",
        lambda _parent, _title, message: messages.append(message),
    )

    ok_button = dialog.button_box.button(QDialogButtonBox.StandardButton.Ok)
    assert ok_button is not None

    dialog.project_name_edit.setText("Templates")
    dialog.project_root_edit.setText(str(tmp_path))
    dialog.condition_profile_combo.setCurrentIndex(0)
    assert dialog.project_name_validation_label.text() != ""
    assert "reserved root folder 'templates'" in dialog.project_name_validation_label.text().lower()
    assert ok_button.isEnabled() is False

    dialog.accept()
    assert dialog.result() != int(dialog.DialogCode.Accepted)
    assert any("reserved root folder 'templates'" in message.lower() for message in messages)

    dialog.project_name_edit.setText("Valid Project")
    assert ok_button.isEnabled() is True
    dialog.accept()
    assert dialog.result() == int(dialog.DialogCode.Accepted)


def test_create_project_dialog_manage_templates_refreshes_profile_options(qtbot) -> None:
    initial_profiles = built_in_condition_template_profiles()[:1]
    refreshed_profiles = built_in_condition_template_profiles()

    dialog = CreateProjectDialog(
        condition_template_profiles=initial_profiles,
        on_manage_templates=lambda: refreshed_profiles,
    )
    qtbot.addWidget(dialog)
    assert dialog.condition_profile_combo.count() == 1

    manage_button = dialog.findChild(QPushButton, "manage_condition_templates_button")
    assert manage_button is not None
    qtbot.mouseClick(manage_button, Qt.MouseButton.LeftButton)

    assert dialog.condition_profile_combo.count() == 2


def test_manage_condition_templates_dialog_renders_hierarchical_details(
    qtbot,
    tmp_path: Path,
) -> None:
    root_dir = tmp_path / "template-manager-root"
    root_dir.mkdir(parents=True, exist_ok=True)

    dialog = ConditionTemplateManagerDialog(root_dir=root_dir)
    qtbot.addWidget(dialog)

    list_text = _list_widget_text(dialog.profile_list)
    assert "Default Template 1: Continuous Images" in list_text
    assert "Default Template 2: 83ms blank" in list_text
    assert STUDIO_DEFAULT_PROFILE_ID not in list_text
    assert SIXTY_HZ_BLANK_FIXATION_PROFILE_ID not in list_text
    assert "[Built-in]" not in list_text

    details_header = dialog.findChild(QLabel, "condition_template_details_header")
    assert details_header is not None
    assert details_header.text() == "Details"
    assert details_header.alignment() == Qt.AlignmentFlag.AlignCenter
    assert "font-size: 18px" in details_header.styleSheet()
    assert "font-weight: 700" in details_header.styleSheet()
    assert "text-decoration: underline" in details_header.styleSheet()

    studio_row = _find_profile_row(dialog, STUDIO_DEFAULT_PROFILE_ID)
    dialog.profile_list.setCurrentRow(studio_row)
    QApplication.processEvents()

    details_text = dialog.profile_details.text()
    assert (
        '<span style="font-size: 14px; font-weight: 700; text-decoration: underline;">'
        "Template</span>"
    ) in details_text
    assert (
        '<span style="font-size: 14px; font-weight: 700; text-decoration: underline;">'
        "Display</span>"
    ) in details_text
    assert (
        '<span style="font-size: 14px; font-weight: 700; text-decoration: underline;">'
        "Fixation Cross</span>"
    ) in details_text
    assert (
        '<span style="font-size: 14px; font-weight: 700; text-decoration: underline;">'
        "Condition Settings</span>"
    ) in details_text
    assert (
        '<span style="font-size: 14px; font-weight: 700; text-decoration: underline;">'
        "Description</span>"
    ) in details_text
    assert details_text.count('<div style="height: 12px;"></div>') >= 4
    assert "Template Name: Default Template 1: Continuous Images" in details_text
    assert "Built-in: Yes" in details_text
    assert "Display Refresh Rate: Not Set" in details_text
    assert "Display Resolution: Full Screen (1920 × 1080)" in details_text
    assert "Fixation Cross: Enabled" in details_text
    assert "Fixation Cross Accuracy Task: Enabled" in details_text
    assert "Total cross color changes in each condition: 7 ± 1" in details_text
    assert "Fixation cross timing: 250 ms" in details_text
    assert "Minimum time between color changes: 1000 ms" in details_text
    assert "Maximum time between color changes: 3000 ms" in details_text
    assert "Duty Cycle: Continuous" in details_text
    assert "Repeats: 1" in details_text
    assert "Cycles per Repeat: 146" in details_text
    assert "Display preferred refresh:" not in details_text
    assert "Fixation: enabled=" not in details_text
    assert dialog.edit_button.isEnabled() is False
    assert dialog.delete_button.isEnabled() is False
    assert dialog.duplicate_button.isEnabled() is True

    blank_row = _find_profile_row(dialog, SIXTY_HZ_BLANK_FIXATION_PROFILE_ID)
    dialog.profile_list.setCurrentRow(blank_row)
    QApplication.processEvents()

    blank_details_text = dialog.profile_details.text()
    assert "Template Name: Default Template 2: 83ms blank" in blank_details_text
    assert "Duty Cycle: 50% Blank" in blank_details_text
    assert "Total cross color changes in each condition: 7 ± 1" in blank_details_text
    assert "Display Refresh Rate: Not Set" in blank_details_text


def test_manage_condition_templates_add_edit_duplicate_delete_round_trip(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    root_dir = tmp_path / "template-manager-mutate-root"
    root_dir.mkdir(parents=True, exist_ok=True)
    dialog = ConditionTemplateManagerDialog(root_dir=root_dir)
    qtbot.addWidget(dialog)

    def _accept_add(editor: ConditionTemplateProfileEditorDialog) -> int:
        editor.profile_id_edit.setText("custom-profile")
        editor.display_name_edit.setText("Custom Profile")
        editor.description_edit.setText("Custom profile for GUI lifecycle test.")
        editor.duty_cycle_combo.setCurrentIndex(editor.duty_cycle_combo.findData(DutyCycleMode.BLANK_50))
        editor.sequence_count_spin.setValue(2)
        editor.oddball_cycles_spin.setValue(120)
        editor.preferred_refresh_enabled_checkbox.setChecked(True)
        editor.preferred_refresh_spin.setValue(120.0)
        editor.fixation_enabled_checkbox.setChecked(True)
        editor.accuracy_enabled_checkbox.setChecked(True)
        editor.target_count_mode_combo.setCurrentIndex(editor.target_count_mode_combo.findData("fixed"))
        editor.changes_per_sequence_spin.setValue(5)
        editor.target_duration_spin.setValue(300)
        editor.min_gap_spin.setValue(900)
        editor.max_gap_spin.setValue(1800)
        editor._saved_profile = editor._build_profile()
        return int(editor.DialogCode.Accepted)

    monkeypatch.setattr(ConditionTemplateProfileEditorDialog, "exec", _accept_add)
    qtbot.mouseClick(dialog.add_button, Qt.MouseButton.LeftButton)
    custom_row = _find_profile_row(dialog, "custom-profile")
    dialog.profile_list.setCurrentRow(custom_row)
    assert dialog.edit_button.isEnabled() is True
    assert dialog.delete_button.isEnabled() is True

    def _accept_edit(editor: ConditionTemplateProfileEditorDialog) -> int:
        editor.display_name_edit.setText("Custom Profile Edited")
        editor.description_edit.setText("Edited custom profile for GUI lifecycle test.")
        editor.sequence_count_spin.setValue(3)
        editor._saved_profile = editor._build_profile()
        return int(editor.DialogCode.Accepted)

    monkeypatch.setattr(ConditionTemplateProfileEditorDialog, "exec", _accept_edit)
    qtbot.mouseClick(dialog.edit_button, Qt.MouseButton.LeftButton)

    custom_row = _find_profile_row(dialog, "custom-profile")
    assert "Custom Profile Edited" in dialog.profile_list.item(custom_row).text()

    def _accept_duplicate(editor: ConditionTemplateProfileEditorDialog) -> int:
        editor._saved_profile = editor._build_profile()
        return int(editor.DialogCode.Accepted)

    monkeypatch.setattr(ConditionTemplateProfileEditorDialog, "exec", _accept_duplicate)
    qtbot.mouseClick(dialog.duplicate_button, Qt.MouseButton.LeftButton)
    duplicate_row = _find_profile_row(dialog, "custom-profile-copy")
    dialog.profile_list.setCurrentRow(duplicate_row)

    monkeypatch.setattr(
        "fpvs_studio.gui.condition_template_manager_dialog.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    qtbot.mouseClick(dialog.delete_button, Qt.MouseButton.LeftButton)

    ids_after_delete = {
        dialog.profile_list.item(index).data(Qt.ItemDataRole.UserRole)
        for index in range(dialog.profile_list.count())
    }
    assert "custom-profile-copy" not in ids_after_delete

    profiles_by_id = {
        profile.profile_id: profile for profile in list_condition_template_profiles(root_dir)
    }
    assert profiles_by_id["custom-profile"].display_name == "Custom Profile Edited"
    assert "custom-profile-copy" not in profiles_by_id


def test_create_project_flow_scaffolds_project_and_opens_main_window(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    dialog = CreateProjectDialog(condition_template_profiles=built_in_condition_template_profiles())
    qtbot.addWidget(dialog)
    dialog.project_name_edit.setText("Visual Oddball")
    dialog.project_root_edit.setText(str(tmp_path))
    dialog.condition_profile_combo.setCurrentIndex(0)
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
    assert window.setup_dashboard_page.project_overview_editor.project_name_edit.text() == "Visual Oddball"


def test_open_existing_project_populates_gui_correctly(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    scaffold = create_project(tmp_path, "Opened Project")

    controller.open_project(scaffold.project_root)
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)

    assert controller.main_window.setup_dashboard_page.project_overview_editor.project_name_edit.text() == "Opened Project"
    assert controller.main_window.setup_dashboard_page.project_overview_editor.project_root_value.text().endswith("opened-project")


def test_home_tab_is_first_and_existing_tabs_remain_usable(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Home Tabs Project")

    expected_tabs = [
        "Home",
        "Setup Dashboard",
        "Conditions",
        "Stimuli Manager",
        "Runtime",
    ]
    tab_labels = [window.main_tabs.tabText(index) for index in range(window.main_tabs.count())]
    assert tab_labels == expected_tabs

    window.main_tabs.setCurrentWidget(window.setup_dashboard_page)
    assert window.main_tabs.currentWidget() is window.setup_dashboard_page
    window.main_tabs.setCurrentWidget(window.conditions_page)
    assert window.main_tabs.currentWidget() is window.conditions_page
    window.main_tabs.setCurrentWidget(window.assets_page)
    assert window.main_tabs.currentWidget() is window.assets_page
    window.main_tabs.setCurrentWidget(window.run_page)
    assert window.main_tabs.currentWidget() is window.run_page
    assert window.main_tabs.indexOf(window.conditions_page) == 2
    assert window.main_tabs.indexOf(window.session_structure_page) == -1
    assert window.main_tabs.indexOf(window.fixation_cross_settings_page) == -1
    assert window.conditions_page.add_condition_button is not None
    assert window.session_structure_page.block_count_spin is not None
    assert window.fixation_cross_settings_page.fixation_enabled_checkbox is not None


def test_setup_dashboard_tab_exists_and_uses_single_column_shell_with_workspace(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Setup Dashboard Shell")

    dashboard = window.setup_dashboard_page
    dashboard_index = window.main_tabs.indexOf(dashboard)
    assert dashboard_index == 1
    assert window.main_tabs.tabText(dashboard_index) == "Setup Dashboard"
    assert dashboard.shell.layout_mode == "single_column"
    assert dashboard.workspace.layout() is not None


def test_major_tabs_share_page_container_width_presets(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Shared Page Container")

    assert window.home_page.page_container.width_preset == "wide"
    assert window.home_page.page_container.max_content_width() == 1280
    assert window.setup_dashboard_page.shell.page_container.width_preset == "wide"
    assert window.conditions_page.shell.page_container.width_preset == "wide"
    assert window.assets_page.shell.page_container.width_preset == "full"
    assert window.assets_page.shell.page_container.max_content_width() == 16_777_215
    assert window.run_page.shell.page_container.width_preset == "medium"


def test_page_headers_use_home_left_alignment_and_non_home_center_alignment(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Header Geometry")
    assert (
        window.home_page.current_project_header.parent()
        is window.home_page.page_container.header_widget
    )
    assert (
        window.home_page.current_project_subtitle.parent()
        is window.home_page.page_container.header_widget
    )
    assert window.home_page.current_project_header.alignment() & Qt.AlignmentFlag.AlignLeft
    assert window.home_page.current_project_subtitle.alignment() & Qt.AlignmentFlag.AlignLeft
    assert window.setup_dashboard_page.shell.title_label.alignment() & Qt.AlignmentFlag.AlignCenter
    assert window.conditions_page.shell.title_label.alignment() & Qt.AlignmentFlag.AlignCenter
    assert window.assets_page.shell.title_label.alignment() & Qt.AlignmentFlag.AlignCenter


def test_stimuli_manager_page_uses_table_focused_layout(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Stimuli Manager Layout")
    page = window.assets_page
    header = page.assets_table.horizontalHeader()

    assert window.main_tabs.tabText(window.main_tabs.indexOf(page)) == "Stimuli Manager"
    assert page.shell.title_label.text() == "Stimuli Manager"
    assert "stimulus sources" in page.shell.subtitle_label.text().lower()
    assert page.assets_table.horizontalHeaderItem(2).text() == "Source Path"
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Interactive
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.ResizeToContents
    assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(5) == QHeaderView.ResizeMode.Interactive
    assert header.stretchLastSection() is False
    assert not page.assets_table.verticalHeader().isVisible()
    assert page.assets_status_text.maximumHeight() == 96
    assert page.shell.page_container.layout().contentsMargins().left() == 24
    assert page.shell.page_container.layout().contentsMargins().right() == 24


def test_switching_main_tabs_keeps_outer_window_size_stable(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Stable Window Size")
    initial_size = window.size()

    for page in (
        window.home_page,
        window.setup_dashboard_page,
        window.conditions_page,
        window.assets_page,
        window.run_page,
    ):
        window.main_tabs.setCurrentWidget(page)
        QApplication.processEvents()
        assert window.size() == initial_size


def test_primary_tabs_fit_default_window_without_page_level_scrollbars(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "No Scroll Layout")
    _prepare_compile_ready_project(window, tmp_path / "no-scroll-ready")
    window.resize(1200, 860)
    window.show()
    QApplication.processEvents()

    page_specs = [
        (window.home_page, window.home_page.page_container.scroll_area),
        (
            window.setup_dashboard_page,
            window.setup_dashboard_page.shell.page_container.scroll_area,
        ),
        (window.conditions_page, window.conditions_page.shell.page_container.scroll_area),
        (window.assets_page, window.assets_page.shell.page_container.scroll_area),
        (window.run_page, window.run_page.shell.page_container.scroll_area),
    ]

    for page, scroll_area in page_specs:
        window.main_tabs.setCurrentWidget(page)
        QApplication.processEvents()
        qtbot.waitUntil(lambda scroll_area=scroll_area: scroll_area.verticalScrollBar().maximum() <= 1)
        assert scroll_area.verticalScrollBar().maximum() <= 1


def test_conditions_tab_uses_horizontal_master_detail_shell(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Conditions Shell")

    conditions_page = window.conditions_page
    assert window.main_tabs.indexOf(conditions_page) == 2
    assert window.main_tabs.tabText(2) == "Conditions"
    assert conditions_page.shell.layout_mode == "single_column"
    assert conditions_page.master_detail_layout.itemAt(0).widget() is conditions_page.condition_list_card
    assert conditions_page.master_detail_layout.itemAt(1).widget() is conditions_page.condition_detail_stack
    detail_stack_layout = conditions_page.condition_detail_stack.layout()
    assert detail_stack_layout is not None
    assert detail_stack_layout.itemAt(0).widget() is conditions_page.condition_editor_card
    assert detail_stack_layout.itemAt(1).widget() is conditions_page.stimulus_sources_card


def test_setup_dashboard_surfaces_project_session_fixation_runtime_and_assets_controls(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Setup Dashboard Content")
    dashboard = window.setup_dashboard_page
    window.main_tabs.setCurrentWidget(dashboard)
    QApplication.processEvents()

    project_editor = dashboard.project_overview_editor
    session_editor = dashboard.session_structure_editor
    fixation_editor = dashboard.fixation_settings_editor
    runtime_editor = dashboard.runtime_settings_editor
    assets_editor = dashboard.assets_readiness_editor

    assert project_editor.project_name_edit is not None
    assert project_editor.project_description_edit is not None
    assert project_editor.project_root_value is not None
    assert project_editor.condition_profile_combo is not None
    assert project_editor.manage_templates_button is not None
    assert project_editor.apply_profile_to_conditions_button is not None

    assert session_editor.block_count_spin is not None
    assert session_editor.inter_condition_mode_combo is not None

    assert fixation_editor.fixation_enabled_checkbox is not None
    assert fixation_editor.target_count_mode_combo is not None
    assert "Estimated maximum feasible cross changes per condition:" in (
        fixation_editor.fixation_feasibility_label.text()
    )

    assert runtime_editor.refresh_hz_spin is not None
    assert runtime_editor.runtime_background_color_combo is not None
    assert runtime_editor.serial_baudrate_spin.isEnabled() is False
    assert not hasattr(runtime_editor, "display_index_edit")

    assert assets_editor.refresh_button.text() == "Refresh Inspection"
    assert assets_editor.materialize_button.text() == "Materialize Supported Variants"
    assert "Condition stimulus rows:" in assets_editor.condition_rows_value.text()
    assert dashboard.findChild(QWidget, "condition_name_edit") is None
    assert dashboard.findChild(QWidget, "condition_list") is None
    assert dashboard.workspace_left_column.layout().itemAt(0).widget() is project_editor
    assert dashboard.workspace_left_column.layout().itemAt(1).widget() is session_editor
    assert dashboard.workspace_center_column.layout().itemAt(0).widget() is fixation_editor
    assert dashboard.workspace_right_column.layout().itemAt(0).widget() is assets_editor
    assert dashboard.workspace_right_column.layout().itemAt(1).widget() is runtime_editor


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

    conditions_page = window.conditions_page
    window.main_tabs.setCurrentWidget(conditions_page)
    qtbot.mouseClick(conditions_page.add_condition_button, Qt.MouseButton.LeftButton)
    conditions_page.condition_name_edit.setText("Dashboard Faces")
    conditions_page.condition_name_edit.editingFinished.emit()
    conditions_page.instructions_edit.setPlainText("Look at the faces.")
    conditions_page.trigger_code_spin.setValue(21)
    conditions_page.sequence_count_spin.setValue(2)
    conditions_page.variant_combo.setCurrentIndex(
        conditions_page.variant_combo.findData(StimulusVariant.GRAYSCALE)
    )
    conditions_page.duty_cycle_combo.setCurrentIndex(
        conditions_page.duty_cycle_combo.findData(DutyCycleMode.BLANK_50)
    )

    window.main_tabs.setCurrentWidget(dashboard)
    session_editor = dashboard.session_structure_editor
    session_editor.block_count_spin.setValue(4)
    session_editor.inter_condition_mode_combo.setCurrentIndex(
        session_editor.inter_condition_mode_combo.findData(InterConditionMode.MANUAL_CONTINUE)
    )
    session_editor.continue_key_edit.setText("return")
    session_editor.continue_key_edit.editingFinished.emit()

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
    runtime_editor.serial_port_edit.setText("COM9")
    runtime_editor.serial_port_edit.editingFinished.emit()
    runtime_editor.fullscreen_checkbox.setChecked(False)
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
    assert settings.session.continue_key == "return"
    assert settings.fixation_task.target_count_mode == "randomized"
    assert settings.fixation_task.target_count_min == 2
    assert settings.fixation_task.target_count_max == 5
    assert settings.fixation_task.no_immediate_repeat_count is True
    assert settings.display.preferred_refresh_hz == pytest.approx(59.94, abs=0.01)
    assert settings.display.background_color == "#101010"
    assert settings.triggers.serial_port == "COM9"
    assert settings.triggers.baudrate == 115200

    assert window.session_structure_page.block_count_spin.value() == 4
    assert (
        window.session_structure_page.inter_condition_mode_combo.currentData()
        == InterConditionMode.MANUAL_CONTINUE
    )
    assert window.fixation_cross_settings_page.target_count_mode_combo.currentData() == "randomized"
    assert window.fixation_cross_settings_page.target_count_min_spin.value() == 2
    assert window.fixation_cross_settings_page.target_count_max_spin.value() == 5
    assert window.run_page.refresh_hz_spin.value() == pytest.approx(59.94, abs=0.01)
    assert window.run_page.runtime_background_color_combo.currentData() == "#101010"
    assert window.run_page.serial_port_edit.text() == "COM9"
    assert window.run_page.serial_baudrate_spin.value() == 115200
    assert dashboard.runtime_settings_editor.serial_baudrate_spin.isEnabled() is False
    assert window.run_page.serial_baudrate_spin.isEnabled() is False
    assert window.run_page.fullscreen_checkbox.isChecked() is False


def test_dedicated_tab_edits_refresh_setup_dashboard_controls(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Setup Dashboard Reverse Sync")

    window.session_structure_page.block_count_spin.setValue(6)
    window.session_structure_page.inter_condition_mode_combo.setCurrentIndex(
        window.session_structure_page.inter_condition_mode_combo.findData(
            InterConditionMode.FIXED_BREAK
        )
    )
    window.session_structure_page.break_seconds_spin.setValue(8.5)

    fixation_page = window.fixation_cross_settings_page
    fixation_page.fixation_enabled_checkbox.setChecked(True)
    fixation_page.fixation_accuracy_checkbox.setChecked(False)
    fixation_page.target_count_mode_combo.setCurrentIndex(
        fixation_page.target_count_mode_combo.findData("fixed")
    )
    fixation_page.changes_per_sequence_spin.setValue(7)

    run_page = window.run_page
    run_page.refresh_hz_spin.setValue(75.0)
    run_page.serial_port_edit.setText("COM4")
    run_page.serial_port_edit.editingFinished.emit()
    window.document.update_trigger_settings(baudrate=230400)
    run_page.fullscreen_checkbox.setChecked(False)
    QApplication.processEvents()

    dashboard = window.setup_dashboard_page
    assert dashboard.session_structure_editor.block_count_spin.value() == 6
    assert (
        dashboard.session_structure_editor.inter_condition_mode_combo.currentData()
        == InterConditionMode.FIXED_BREAK
    )
    assert dashboard.session_structure_editor.break_seconds_spin.value() == pytest.approx(
        8.5,
        abs=0.01,
    )
    assert dashboard.fixation_settings_editor.target_count_mode_combo.currentData() == "fixed"
    assert dashboard.fixation_settings_editor.changes_per_sequence_spin.value() == 7
    assert dashboard.runtime_settings_editor.refresh_hz_spin.value() == pytest.approx(75.0, abs=0.01)
    assert dashboard.runtime_settings_editor.serial_port_edit.text() == "COM4"
    assert dashboard.runtime_settings_editor.serial_baudrate_spin.value() == 230400
    assert dashboard.runtime_settings_editor.serial_baudrate_spin.isEnabled() is False
    assert run_page.serial_baudrate_spin.value() == 230400
    assert run_page.serial_baudrate_spin.isEnabled() is False
    assert dashboard.runtime_settings_editor.fullscreen_checkbox.isChecked() is False


def test_setup_dashboard_save_load_smoke_persists_dashboard_edited_settings(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Setup Dashboard Save Load")
    dashboard = window.setup_dashboard_page

    dashboard.session_structure_editor.block_count_spin.setValue(3)
    dashboard.session_structure_editor.inter_condition_mode_combo.setCurrentIndex(
        dashboard.session_structure_editor.inter_condition_mode_combo.findData(
            InterConditionMode.MANUAL_CONTINUE
        )
    )
    dashboard.session_structure_editor.continue_key_edit.setText("space")
    dashboard.session_structure_editor.continue_key_edit.editingFinished.emit()

    fixation_editor = dashboard.fixation_settings_editor
    fixation_editor.fixation_enabled_checkbox.setChecked(True)
    fixation_editor.fixation_accuracy_checkbox.setChecked(True)
    fixation_editor.target_count_mode_combo.setCurrentIndex(
        fixation_editor.target_count_mode_combo.findData("fixed")
    )
    fixation_editor.changes_per_sequence_spin.setValue(6)
    fixation_editor.base_color_edit.setText("#112233")
    fixation_editor.base_color_edit.editingFinished.emit()
    fixation_editor.target_color_edit.setText("#445566")
    fixation_editor.target_color_edit.editingFinished.emit()
    fixation_editor.response_key_edit.setText("space")
    fixation_editor.response_key_edit.editingFinished.emit()

    runtime_editor = dashboard.runtime_settings_editor
    runtime_editor.refresh_hz_spin.setValue(120.0)
    dark_gray_index = runtime_editor.runtime_background_color_combo.findData("#101010")
    assert dark_gray_index >= 0
    runtime_editor.runtime_background_color_combo.setCurrentIndex(dark_gray_index)
    runtime_editor.serial_port_edit.setText("COM5")
    runtime_editor.serial_port_edit.editingFinished.emit()
    window.document.update_trigger_settings(baudrate=38400)
    runtime_editor.fullscreen_checkbox.setChecked(False)

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
    assert fixation.base_color == "#112233"
    assert fixation.target_color == "#445566"
    assert fixation.response_key == "space"
    assert display.preferred_refresh_hz == pytest.approx(120.0, abs=0.01)
    assert display.background_color == "#101010"
    assert triggers.serial_port == "COM5"
    assert triggers.baudrate == 38400

    assert reopened_dashboard.session_structure_editor.block_count_spin.value() == 3
    assert reopened_dashboard.fixation_settings_editor.changes_per_sequence_spin.value() == 6
    assert reopened_dashboard.runtime_settings_editor.serial_port_edit.text() == "COM5"
    assert reopened_dashboard.runtime_settings_editor.serial_baudrate_spin.value() == 38400
    assert reopened_dashboard.runtime_settings_editor.serial_baudrate_spin.isEnabled() is False
    assert reopened_window.run_page.serial_baudrate_spin.value() == 38400
    assert reopened_window.run_page.serial_baudrate_spin.isEnabled() is False
    assert reopened_window.run_page.fullscreen_checkbox.isChecked() is True


def test_home_header_updates_when_project_name_changes(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Home Header Project")
    header_label = window.home_page.findChild(QLabel, "home_current_project_header")
    assert header_label is not None
    assert header_label.parent() is window.home_page.page_container.header_widget
    assert header_label.text() == "Home Header Project"

    window.setup_dashboard_page.project_overview_editor.project_name_edit.setText("Renamed Header Project")
    window.setup_dashboard_page.project_overview_editor.project_name_edit.editingFinished.emit()

    qtbot.waitUntil(lambda: header_label.text() == "Renamed Header Project")
    assert window.document.project.meta.name == "Renamed Header Project"


def test_home_quick_action_buttons_present_and_wired(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Home Actions Project")
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.ParticipantNumberDialog.exec",
        lambda self: int(self.DialogCode.Rejected),
    )

    new_button = window.home_page.findChild(QPushButton, "home_create_project_button")
    open_button = window.home_page.findChild(QPushButton, "home_open_project_button")
    save_button = window.home_page.findChild(QPushButton, "home_save_project_button")
    launch_button = window.home_page.findChild(QPushButton, "home_launch_test_session_button")
    assert new_button is not None
    assert open_button is not None
    assert save_button is not None
    assert launch_button is not None
    assert launch_button.text() == "Launch Experiment"
    assert window.run_page.launch_button.text() == "Launch Experiment"
    assert window.launch_action.text() == "Launch Experiment"
    assert "alpha test-mode" in window.launch_action.toolTip().lower()
    qtbot.waitUntil(lambda: launch_button.width() > 0)
    ordered_buttons = sorted(
        (open_button, new_button, save_button, launch_button),
        key=lambda button: button.geometry().x(),
    )
    assert [button.objectName() for button in ordered_buttons] == [
        "home_open_project_button",
        "home_create_project_button",
        "home_save_project_button",
        "home_launch_test_session_button",
    ]
    assert launch_button.geometry().right() == max(
        button.geometry().right() for button in ordered_buttons
    )
    assert len({button.width() for button in ordered_buttons}) == 1
    assert {button.minimumWidth() for button in ordered_buttons} == {176}
    assert {button.maximumWidth() for button in ordered_buttons} == {176}

    trigger_counts = {"new": 0, "open": 0, "save": 0, "launch": 0}
    window.new_project_action.triggered.connect(
        lambda _checked=False: trigger_counts.__setitem__("new", trigger_counts["new"] + 1)
    )
    window.open_project_action.triggered.connect(
        lambda _checked=False: trigger_counts.__setitem__("open", trigger_counts["open"] + 1)
    )
    window.save_project_action.triggered.connect(
        lambda _checked=False: trigger_counts.__setitem__("save", trigger_counts["save"] + 1)
    )
    window.launch_action.triggered.connect(
        lambda _checked=False: trigger_counts.__setitem__("launch", trigger_counts["launch"] + 1)
    )

    qtbot.mouseClick(new_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(open_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(save_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(launch_button, Qt.MouseButton.LeftButton)

    assert trigger_counts == {"new": 1, "open": 1, "save": 1, "launch": 1}


def test_launch_buttons_share_primary_visual_role(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Launch Role Project")
    home_launch_button = window.home_page.findChild(QPushButton, "home_launch_test_session_button")
    run_launch_button = window.run_page.findChild(QPushButton, "launch_test_session_button")
    assert home_launch_button is not None
    assert run_launch_button is not None
    assert home_launch_button.text() == "Launch Experiment"
    assert run_launch_button.text() == "Launch Experiment"
    assert home_launch_button.property("launchActionRole") == "primary"
    assert run_launch_button.property("launchActionRole") == "primary"


def test_main_tabs_use_animated_tab_bar(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Animated Tabs Project")
    assert isinstance(window.main_tabs.tabBar(), AnimatedTabBar)


def test_main_tabs_use_equal_width_tab_geometry(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Equal Width Tabs Project")
    tab_bar = window.main_tabs.tabBar()
    assert isinstance(tab_bar, AnimatedTabBar)

    qtbot.waitUntil(lambda: tab_bar.count() == window.main_tabs.count())
    qtbot.waitUntil(lambda: all(tab_bar.tabRect(index).width() > 0 for index in range(tab_bar.count())))

    tab_widths = [tab_bar.tabRect(index).width() for index in range(tab_bar.count())]
    hint_widths = [tab_bar.tabSizeHint(index).width() for index in range(tab_bar.count())]

    assert len(set(tab_widths)) == 1
    assert len(set(hint_widths)) == 1


def test_main_window_buttons_are_hover_animation_enabled(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Hover Buttons Project")
    create_button = window.home_page.findChild(QPushButton, "home_create_project_button")
    run_compile_button = window.run_page.findChild(QPushButton, "compile_session_button")
    run_launch_button = window.run_page.findChild(QPushButton, "launch_test_session_button")
    assert create_button is not None
    assert run_compile_button is not None
    assert run_launch_button is not None
    assert run_compile_button.text() == "Preview Session Plan"
    assert create_button.property("hoverAnimationEnabled") is True
    assert run_compile_button.property("hoverAnimationEnabled") is True
    assert run_launch_button.property("hoverAnimationEnabled") is True


def test_run_page_preview_copy_and_home_status_are_compile_agnostic(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Preview Copy Project")

    preview_button = window.run_page.findChild(QPushButton, "compile_session_button")
    readiness_list = window.run_page.findChild(QListWidget, "run_readiness_checklist")
    home_status = window.home_page.findChild(QLabel, "home_launch_status_indicator")

    assert preview_button is not None
    assert readiness_list is not None
    assert home_status is not None

    assert preview_button.text() == "Preview Session Plan"
    assert (
        window.run_page.summary_text.placeholderText()
        == "Preview the session plan or launch to populate runtime diagnostics."
    )
    assert (
        "launch will compile and run launch checks automatically"
        in window.run_page.readiness_summary_value.text().lower()
    )
    assert "compile once on run / runtime" not in _list_widget_text(readiness_list).lower()
    assert "needs compile" not in home_status.text().lower()
    assert "compile" not in home_status.toolTip().lower()


def test_animated_tab_hover_progress_updates_on_mouse_move(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Animated Tab Hover Project")
    tab_bar = window.main_tabs.tabBar()
    assert isinstance(tab_bar, AnimatedTabBar)

    target_index = 1
    qtbot.waitUntil(lambda: tab_bar.tabRect(target_index).width() > 0)
    target_center = tab_bar.tabRect(target_index).center()
    qtbot.mouseMove(tab_bar, target_center)
    if tab_bar.hovered_tab_index() != target_index:
        tab_bar._set_hovered_tab(target_index)
    qtbot.waitUntil(lambda: tab_bar.hovered_tab_index() == target_index)
    qtbot.waitUntil(lambda: tab_bar.tab_hover_progress(target_index) > 0.0)

    qtbot.mouseMove(window, QPoint(2, window.height() - 2))
    if tab_bar.hovered_tab_index() != -1:
        QApplication.sendEvent(tab_bar, QEvent(QEvent.Type.HoverLeave))
    qtbot.waitUntil(lambda: tab_bar.hovered_tab_index() == -1)


def test_no_standalone_preflight_controls_are_exposed(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "No Preflight Controls")

    assert window.run_page.findChild(QPushButton, "preflight_button") is None
    assert window.home_page.findChild(QPushButton, "home_preflight_button") is None
    assert not hasattr(window, "preflight_action")

    top_menu_labels = [action.text() for action in window.menuBar().actions() if action.text()]
    assert "Run" not in top_menu_labels

    menu_labels = [
        action.text()
        for menu_action in window.menuBar().actions()
        for action in ((menu_action.menu().actions() if menu_action.menu() is not None else []))
        if action.text()
    ]
    assert "Settings..." in menu_labels
    assert "Create New Project" not in menu_labels
    assert "Open Project..." not in menu_labels
    assert "Save" not in menu_labels
    assert "Launch Experiment" not in menu_labels
    assert "Preflight" not in menu_labels

    toolbar_labels = [
        action.text()
        for toolbar in window.findChildren(QToolBar)
        for action in toolbar.actions()
        if action.text()
    ]
    assert "Create New Project" not in toolbar_labels
    assert "Open Project..." not in toolbar_labels
    assert "Save" not in toolbar_labels
    assert "Launch Experiment" not in toolbar_labels
    assert "Preflight" not in toolbar_labels


def test_window_title_and_status_bar_surface_alpha_runtime_designation(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Alpha Label Project")
    alpha_label = window.findChild(QLabel, "alpha_runtime_status_label")

    assert alpha_label is not None
    assert alpha_label.text() == "Alpha: test-mode runtime path only"
    assert "(Alpha)" in window.windowTitle()


def test_home_overview_panels_show_project_session_and_runtime_metadata(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Home Metadata Project")
    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)

    window.session_structure_page.block_count_spin.setValue(2)

    condition_count_label = window.home_page.findChild(QLabel, "home_condition_count_value")
    block_count_label = window.home_page.findChild(QLabel, "home_block_count_value")
    fixation_label = window.home_page.findChild(QLabel, "home_fixation_task_value")
    accuracy_label = window.home_page.findChild(QLabel, "home_accuracy_task_value")
    template_label = window.home_page.findChild(QLabel, "home_project_template_value")
    description_label = window.home_page.findChild(QLabel, "home_project_description_value")
    root_path_label = window.home_page.findChild(QLabel, "home_project_root_value")
    status_label = window.home_page.findChild(QLabel, "home_launch_status_indicator")
    assert condition_count_label is not None
    assert block_count_label is not None
    assert fixation_label is not None
    assert accuracy_label is not None
    assert template_label is not None
    assert description_label is not None
    assert root_path_label is not None
    assert status_label is not None

    project_labels = {
        label.text().strip()
        for label in window.setup_dashboard_page.project_overview_editor.findChildren(QLabel)
        if label.text().strip()
    }
    assert "Protocol Template" not in project_labels
    assert "Template Status" not in project_labels
    assert "Condition Template" in project_labels
    assert window.setup_dashboard_page.project_overview_editor.condition_profile_combo is not None
    assert window.setup_dashboard_page.project_overview_editor.manage_templates_button is not None
    assert window.setup_dashboard_page.project_overview_editor.apply_profile_to_conditions_button is not None

    assert condition_count_label.text() == "1"
    assert block_count_label.text() == "2"
    assert fixation_label.text() == "Disabled"
    assert accuracy_label.text() == "Disabled"
    assert str(window.document.project_root) in {
        root_path_label.text(),
        root_path_label.toolTip(),
    }
    assert status_label.text().startswith("Status: ")
    assert template_label.text() == "No template selected"
    assert description_label.text() == "No description set yet."

    profile_index = window.setup_dashboard_page.project_overview_editor.condition_profile_combo.findData(
        SIXTY_HZ_BLANK_FIXATION_PROFILE_ID
    )
    assert profile_index >= 0
    window.setup_dashboard_page.project_overview_editor.condition_profile_combo.setCurrentIndex(profile_index)
    QApplication.processEvents()
    assert template_label.text() == "Default Template 2: 83ms blank"
    assert SIXTY_HZ_BLANK_FIXATION_PROFILE_ID not in template_label.text()
    assert "fpvs_6hz_every5_v1" not in template_label.text()

    missing_profile = built_in_condition_template_profiles()[0].model_copy(
        update={"profile_id": "missing-home-template-profile"},
    )
    window.document.apply_condition_template_profile(missing_profile)
    QApplication.processEvents()
    assert template_label.text() == "Missing template: missing-home-template-profile"


def test_background_color_control_is_run_tab_presets_only(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Runtime Background Presets")

    assert window.setup_dashboard_page.project_overview_editor.findChild(QWidget, "background_color_edit") is None

    runtime_background_combo = window.run_page.findChild(QComboBox, "runtime_background_color_combo")
    assert runtime_background_combo is not None
    assert runtime_background_combo.count() == 2
    assert runtime_background_combo.itemText(0) == "Black"
    assert runtime_background_combo.itemData(0) == "#000000"
    assert runtime_background_combo.itemText(1) == "Dark Gray"
    assert runtime_background_combo.itemData(1) == "#101010"
    assert runtime_background_combo.currentText() == "Black"

    scope_label = window.run_page.findChild(QLabel, "runtime_background_scope_label")
    assert scope_label is not None
    assert scope_label.text() == "Used during FPVS image presentation."


def test_run_page_refresh_normalizes_legacy_background_to_black_and_marks_dirty(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    scaffold = create_project(tmp_path, "Legacy Background Migration")
    project_file_path = scaffold.project_root / "project.json"
    legacy_project = load_project_file(project_file_path)
    assert legacy_project.settings.display.background_color == "#000000"
    legacy_display_settings = legacy_project.settings.display.model_copy(
        update={"background_color": "#123456"}
    )
    legacy_settings = legacy_project.settings.model_copy(update={"display": legacy_display_settings})
    save_project_file(
        legacy_project.model_copy(update={"settings": legacy_settings}),
        project_file_path,
    )
    assert load_project_file(project_file_path).settings.display.background_color == "#123456"

    document = controller.open_project(scaffold.project_root)
    assert document is not None
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)
    window = controller.main_window

    assert window.document.project.settings.display.background_color == "#000000"
    assert window.document.dirty is True
    assert window.run_page.runtime_background_color_combo.currentText() == "Black"


def test_run_page_readiness_and_launch_feedback_is_updated_on_launch(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Home Status Project")
    run_readiness_list = window.run_page.findChild(QListWidget, "run_readiness_checklist")
    run_launch_button = window.run_page.findChild(QPushButton, "launch_test_session_button")
    run_status_label = window.run_page.findChild(QLabel, "run_readiness_badge")
    assert run_readiness_list is not None
    assert run_launch_button is not None
    assert run_status_label is not None
    assert "runtime path: alpha test-mode only" in _list_widget_text(run_readiness_list).lower()
    assert run_status_label.text()

    _prepare_compile_ready_project(window, tmp_path / "home-status-preflight")

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
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", lambda: None)

    qtbot.mouseClick(run_launch_button, Qt.MouseButton.LeftButton)

    assert window.home_page.findChild(QListWidget, "home_readiness_checklist") is None
    assert window.home_page.findChild(QListWidget, "home_recent_activity_list") is None
    assert window.home_page.findChild(QGroupBox, "home_preflight_card") is None

    assert captures["project_root"] == window.document.project_root
    qtbot.waitUntil(
        lambda: "status: launch checks passed"
        in window.run_page.summary_text.toPlainText().lower(),
    )


def test_project_description_typing_round_trips_without_cursor_reset(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    typed_text = "testing this, why is this happening"
    _, window = _open_created_project(controller, qtbot, tmp_path, "Description Project")

    window.main_tabs.setCurrentWidget(window.setup_dashboard_page)
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

    assert reopened_window.setup_dashboard_page.project_overview_editor.project_description_edit.toPlainText() == typed_text
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

    session_page = window.session_structure_page
    session_page.block_count_spin.setValue(3)
    session_page.session_seed_spin.setValue(123456)
    session_page.randomize_checkbox.setChecked(False)
    session_page.inter_condition_mode_combo.setCurrentIndex(
        session_page.inter_condition_mode_combo.findData(InterConditionMode.MANUAL_CONTINUE)
    )
    session_page.continue_key_edit.setText("return")
    session_page.continue_key_edit.editingFinished.emit()

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
    fixation_page.base_color_edit.setText("#112233")
    fixation_page.base_color_edit.editingFinished.emit()
    fixation_page.target_color_edit.setText("#445566")
    fixation_page.target_color_edit.editingFinished.emit()
    fixation_page.response_key_edit.setText("space")
    fixation_page.response_key_edit.editingFinished.emit()
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


def test_fixation_cross_settings_page_maps_fixed_target_count_mode_to_backend(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Fixed Target Count")

    window.main_tabs.setCurrentWidget(window.setup_dashboard_page)
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

    window.main_tabs.setCurrentWidget(window.setup_dashboard_page)
    page = window.setup_dashboard_page.fixation_settings_editor
    assert page.findChild(type(page.fixation_accuracy_checkbox), "fixation_accuracy_checkbox") is not None
    assert page.findChild(type(page.target_count_mode_combo), "target_count_mode_combo") is not None
    assert page.findChild(type(page.target_count_min_spin), "target_count_min_spin") is not None
    assert page.findChild(type(page.target_count_max_spin), "target_count_max_spin") is not None
    assert page.findChild(type(page.no_repeat_count_checkbox), "no_immediate_repeat_count_checkbox") is not None
    assert page.findChild(type(page.response_key_edit), "response_key_edit") is not None
    assert page.findChild(type(page.response_window_spin), "response_window_seconds_spin") is not None


def test_session_structure_rows_toggle_with_inter_condition_mode(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Session Structure Visibility")

    page = window.setup_dashboard_page.session_structure_editor
    window.main_tabs.setCurrentWidget(window.setup_dashboard_page)
    QApplication.processEvents()

    page.inter_condition_mode_combo.setCurrentIndex(
        page.inter_condition_mode_combo.findData(InterConditionMode.FIXED_BREAK)
    )
    QApplication.processEvents()
    assert page.break_seconds_spin.isVisible()
    assert not page.continue_key_edit.isVisible()

    page.inter_condition_mode_combo.setCurrentIndex(
        page.inter_condition_mode_combo.findData(InterConditionMode.MANUAL_CONTINUE)
    )
    QApplication.processEvents()
    assert not page.break_seconds_spin.isVisible()
    assert page.continue_key_edit.isVisible()


def test_fixation_color_change_mode_toggles_relevant_controls(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Fixation Mode Visibility")

    page = window.setup_dashboard_page.fixation_settings_editor
    window.main_tabs.setCurrentWidget(window.setup_dashboard_page)
    page.fixation_enabled_checkbox.setChecked(True)
    QApplication.processEvents()

    page.target_count_mode_combo.setCurrentIndex(page.target_count_mode_combo.findData("fixed"))
    QApplication.processEvents()
    assert page.changes_per_sequence_spin.isEnabled()
    assert not page.target_count_min_spin.isEnabled()
    assert not page.target_count_max_spin.isEnabled()
    assert not page.no_repeat_count_checkbox.isEnabled()

    page.target_count_mode_combo.setCurrentIndex(page.target_count_mode_combo.findData("randomized"))
    QApplication.processEvents()
    assert not page.changes_per_sequence_spin.isEnabled()
    assert page.target_count_min_spin.isEnabled()
    assert page.target_count_max_spin.isEnabled()
    assert page.no_repeat_count_checkbox.isEnabled()


def test_fixation_accuracy_toggle_controls_response_visibility(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Fixation Accuracy Visibility")

    page = window.setup_dashboard_page.fixation_settings_editor
    window.main_tabs.setCurrentWidget(window.setup_dashboard_page)
    page.fixation_enabled_checkbox.setChecked(True)
    QApplication.processEvents()

    page.fixation_accuracy_checkbox.setChecked(False)
    QApplication.processEvents()
    assert not page.response_key_edit.isVisible()
    assert not page.response_window_spin.isVisible()

    page.fixation_accuracy_checkbox.setChecked(True)
    QApplication.processEvents()
    assert page.response_key_edit.isVisible()
    assert page.response_window_spin.isVisible()


def test_fixation_disable_hides_dependent_sections(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Fixation Enablement Visibility")

    page = window.setup_dashboard_page.fixation_settings_editor
    window.main_tabs.setCurrentWidget(window.setup_dashboard_page)
    page.fixation_enabled_checkbox.setChecked(True)
    page.fixation_accuracy_checkbox.setChecked(True)
    QApplication.processEvents()
    assert page.target_count_mode_combo.isVisible()
    assert page.target_duration_spin.isVisible()
    assert page.base_color_edit.isVisible()
    assert page.response_key_edit.isVisible()
    assert page.fixation_accuracy_checkbox.isEnabled()

    page.fixation_enabled_checkbox.setChecked(False)
    QApplication.processEvents()
    assert not page.target_count_mode_combo.isVisible()
    assert not page.target_duration_spin.isVisible()
    assert not page.base_color_edit.isVisible()
    assert not page.response_key_edit.isVisible()
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
    window.main_tabs.setCurrentWidget(window.setup_dashboard_page)
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
    window.main_tabs.setCurrentWidget(window.setup_dashboard_page)
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

    profile_index = window.setup_dashboard_page.project_overview_editor.condition_profile_combo.findData(
        SIXTY_HZ_BLANK_FIXATION_PROFILE_ID
    )
    assert profile_index >= 0
    window.setup_dashboard_page.project_overview_editor.condition_profile_combo.setCurrentIndex(profile_index)

    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = window.conditions_page.selected_condition_id()
    assert condition_id is not None
    condition = window.document.get_condition(condition_id)
    assert condition is not None

    assert condition.duty_cycle_mode == DutyCycleMode.BLANK_50
    assert condition.sequence_count == 1
    assert condition.oddball_cycle_repeats_per_sequence == 146


def test_apply_condition_template_profile_to_all_conditions_standardizes_existing_rows(
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

    profile_index = window.setup_dashboard_page.project_overview_editor.condition_profile_combo.findData(
        SIXTY_HZ_BLANK_FIXATION_PROFILE_ID
    )
    assert profile_index >= 0
    window.setup_dashboard_page.project_overview_editor.condition_profile_combo.setCurrentIndex(profile_index)

    first_before = window.document.get_condition(first_condition_id)
    second_before = window.document.get_condition(second_condition_id)
    assert first_before is not None
    assert second_before is not None
    assert first_before.sequence_count == 2
    assert second_before.sequence_count == 3

    qtbot.mouseClick(
        window.setup_dashboard_page.project_overview_editor.apply_profile_to_conditions_button,
        Qt.MouseButton.LeftButton,
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
    assert "Catalog status:" in window.assets_page.assets_status_text.toPlainText()
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


def test_launch_invokes_backend_preflight_before_participant_prompt(
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
        "fpvs_studio.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    phase_trace: list[str] = []

    def _fake_prompt() -> None:
        phase_trace.append("prompt")
        return None

    launch_calls = 0

    def _fake_launch(*_args, **_kwargs):
        nonlocal launch_calls
        launch_calls += 1
        raise AssertionError("launch_session should not run when prompt returns None")

    def _capture_preflight(project_root, session_plan, engine):
        phase_trace.append("preflight")
        captures.update(
            {
                "project_root": project_root,
                "session_id": session_plan.session_id,
                "engine": engine,
            }
        )

    monkeypatch.setattr("fpvs_studio.gui.document.preflight_session_plan", _capture_preflight)
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", _fake_prompt)
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    assert captures["project_root"] == window.document.project_root
    assert captures["engine"] == {"engine_name": "psychopy"}
    assert phase_trace == ["preflight", "prompt"]
    assert launch_calls == 0
    assert "launch checks passed" in window.run_page.summary_text.toPlainText().lower()


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
    progress_events: list[str] = []
    progress_dialogs: list[object] = []

    class _FakeProgressDialog:
        def __init__(self, label, cancel_text, minimum, maximum, parent) -> None:
            self.label = label
            self.cancel_text = cancel_text
            self.minimum = minimum
            self.maximum = maximum
            self.parent = parent
            self.window_title = ""
            self.cancel_button = object()
            self.window_modality = None
            self.minimum_duration = None
            self.shown = False
            self.closed = False
            progress_events.append("created")
            progress_dialogs.append(self)

        def setWindowTitle(self, title) -> None:  # noqa: N802
            self.window_title = title

        def setCancelButton(self, button) -> None:  # noqa: N802
            self.cancel_button = button

        def setWindowModality(self, modality) -> None:  # noqa: N802
            self.window_modality = modality

        def setMinimumDuration(self, duration_ms) -> None:  # noqa: N802
            self.minimum_duration = duration_ms

        def show(self) -> None:
            self.shown = True
            progress_events.append("shown")

        def close(self) -> None:
            self.closed = True
            progress_events.append("closed")

    def _fake_launch(project_root, session_plan, participant_number, launch_settings):
        assert progress_events == ["created", "shown", "closed"]
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

    monkeypatch.setattr(
        window.document,
        "prepare_test_session_launch",
        lambda refresh_hz, engine_name="psychopy": window.document.compile_session(
            refresh_hz=refresh_hz
        ),
    )
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", _fake_prompt)
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)
    monkeypatch.setattr("fpvs_studio.gui.main_window.QProgressDialog", _FakeProgressDialog)
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )

    window.run_page.serial_port_edit.setText("COM3")
    window.run_page.serial_port_edit.editingFinished.emit()
    window.document.update_trigger_settings(baudrate=57600)
    window.run_page.display_index_edit.setText("1")
    assert window.run_page.serial_baudrate_spin.isEnabled() is False
    assert window.setup_dashboard_page.runtime_settings_editor.serial_baudrate_spin.isEnabled() is False
    assert window.run_page.fullscreen_checkbox.isChecked() is True

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    launch_settings = captures["launch_settings"]
    assert len(progress_dialogs) == 1
    progress_dialog = progress_dialogs[0]
    assert prompt_calls == 1
    assert captures["participant_number"] == participant_number
    assert captures["project_root"] == window.document.project_root
    assert progress_dialog.label == "Launching experiment: Please wait"
    assert progress_dialog.window_title == "FPVS Studio"
    assert progress_dialog.minimum == 0
    assert progress_dialog.maximum == 0
    assert progress_dialog.cancel_button is None
    assert progress_dialog.window_modality == Qt.WindowModality.WindowModal
    assert progress_dialog.minimum_duration == 0
    assert progress_dialog.shown is True
    assert progress_dialog.closed is True
    assert progress_events == ["created", "shown", "closed"]
    assert launch_settings.serial_port == "COM3"
    assert launch_settings.serial_baudrate == 57600
    assert launch_settings.display_index == 1
    assert launch_settings.test_mode is True
    assert launch_settings.fullscreen is True
    assert launch_settings.strict_timing is True
    assert launch_settings.strict_timing_warmup is False
    assert launch_settings.timing_miss_threshold_multiplier == 4.0
    assert f"participant number: {participant_number}" in window.run_page.summary_text.toPlainText().lower()
    assert "runtime launch completed" in window.run_page.summary_text.toPlainText().lower()


def test_launch_after_preview_reprepares_once_per_click(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Preview Then Launch Project")
    _prepare_compile_ready_project(window, tmp_path / "preview-then-launch")

    qtbot.mouseClick(window.run_page.compile_button, Qt.MouseButton.LeftButton)
    assert "session preview refreshed" in window.run_page.summary_text.toPlainText().lower()

    original_prepare = window.document.prepare_test_session_launch
    prepare_calls: list[float] = []
    preflight_session_ids: list[str] = []
    launched_session_ids: list[str] = []

    def _capture_prepare(*, refresh_hz, engine_name="psychopy"):
        prepare_calls.append(refresh_hz)
        return original_prepare(refresh_hz=refresh_hz, engine_name=engine_name)

    def _capture_launch(project_root, session_plan, participant_number, launch_settings):
        launched_session_ids.append(session_plan.session_id)
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

    monkeypatch.setattr(window.document, "prepare_test_session_launch", _capture_prepare)
    monkeypatch.setattr(
        "fpvs_studio.gui.document.create_engine",
        lambda engine_name: {"engine_name": engine_name},
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.document.preflight_session_plan",
        lambda project_root, session_plan, engine: preflight_session_ids.append(
            session_plan.session_id
        ),
    )
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", lambda: "00052")
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _capture_launch)
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    assert len(prepare_calls) == 1
    assert len(preflight_session_ids) == 1
    assert launched_session_ids == preflight_session_ids
    assert "runtime launch completed" in window.run_page.summary_text.toPlainText().lower()


def test_launch_action_surfaces_abort_reason_when_runtime_aborts(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Launch Abort Project")
    _prepare_compile_ready_project(window, tmp_path / "launch-abort")

    participant_number = "00043"
    info_calls = 0
    warning_payloads: list[tuple[str, str]] = []

    def _fake_launch(project_root, session_plan, participant_number, launch_settings):
        return SessionExecutionSummary(
            project_id=session_plan.project_id,
            session_id=session_plan.session_id,
            engine_name="stub",
            run_mode=RunMode.TEST,
            participant_number=participant_number,
            random_seed=session_plan.random_seed,
            started_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 3, 8, 10, 0, 1, tzinfo=timezone.utc),
            total_condition_count=session_plan.total_runs,
            completed_condition_count=0,
            aborted=True,
            abort_reason=(
                "Strict timing aborted run during warmup: frame interval at index 18 was "
                "0.025840 s, exceeding 1.50x expected 0.016667 s."
            ),
            output_dir="runs/00043",
        )

    def _capture_information(*_args, **_kwargs):
        nonlocal info_calls
        info_calls += 1
        return QMessageBox.StandardButton.Ok

    def _capture_warning(_parent, title, text):
        warning_payloads.append((title, text))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(
        window.document,
        "prepare_test_session_launch",
        lambda refresh_hz, engine_name="psychopy": window.document.compile_session(
            refresh_hz=refresh_hz
        ),
    )
    monkeypatch.setattr(
        window.run_page,
        "_prompt_participant_number",
        lambda: participant_number,
    )
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.information",
        _capture_information,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.warning",
        _capture_warning,
    )

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    summary_text = window.run_page.summary_text.toPlainText().lower()
    assert info_calls == 0
    assert len(warning_payloads) == 1
    assert warning_payloads[0][0] == "Launch Aborted"
    assert "strict timing aborted run during warmup" in warning_payloads[0][1].lower()
    assert "runtime launch completed" not in summary_text
    assert "runtime launch aborted" in summary_text
    assert "abort reason:" in summary_text


def test_launch_action_closes_progress_dialog_when_runtime_launch_raises(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Launch Error Progress Project")
    _prepare_compile_ready_project(window, tmp_path / "launch-error-progress")

    events: list[str] = []
    captured_errors: list[tuple[str, str]] = []

    class _FakeProgressDialog:
        def __init__(self, label, cancel_text, minimum, maximum, parent) -> None:
            self.label = label
            self.cancel_text = cancel_text
            self.minimum = minimum
            self.maximum = maximum
            self.parent = parent
            self.window_title = ""
            self.cancel_button = object()
            self.window_modality = None
            self.minimum_duration = None
            self.closed = False
            events.append("created")

        def setWindowTitle(self, title) -> None:  # noqa: N802
            self.window_title = title

        def setCancelButton(self, button) -> None:  # noqa: N802
            self.cancel_button = button

        def setWindowModality(self, modality) -> None:  # noqa: N802
            self.window_modality = modality

        def setMinimumDuration(self, duration_ms) -> None:  # noqa: N802
            self.minimum_duration = duration_ms

        def show(self) -> None:
            events.append("shown")

        def close(self) -> None:
            self.closed = True
            events.append("closed")

    def _fake_launch(*_args, **_kwargs):
        events.append("launch_called")
        raise RuntimeError("Intentional launch failure.")

    def _capture_error_dialog(_parent, title, error) -> None:
        events.append("error_dialog")
        captured_errors.append((title, str(error)))

    monkeypatch.setattr(
        window.document,
        "prepare_test_session_launch",
        lambda refresh_hz, engine_name="psychopy": window.document.compile_session(
            refresh_hz=refresh_hz
        ),
    )
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", lambda: "00077")
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)
    monkeypatch.setattr("fpvs_studio.gui.main_window.QProgressDialog", _FakeProgressDialog)
    monkeypatch.setattr("fpvs_studio.gui.main_window._show_error_dialog", _capture_error_dialog)

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    assert captured_errors == [("Launch Error", "Intentional launch failure.")]
    assert events == ["created", "shown", "closed", "launch_called", "error_dialog"]


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

    monkeypatch.setattr(
        window.document,
        "prepare_test_session_launch",
        lambda refresh_hz, engine_name="psychopy": window.document.compile_session(
            refresh_hz=refresh_hz
        ),
    )
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

    monkeypatch.setattr(
        window.document,
        "prepare_test_session_launch",
        lambda refresh_hz, engine_name="psychopy": window.document.compile_session(
            refresh_hz=refresh_hz
        ),
    )
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

    monkeypatch.setattr(
        window.document,
        "prepare_test_session_launch",
        lambda refresh_hz, engine_name="psychopy": window.document.compile_session(
            refresh_hz=refresh_hz
        ),
    )
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

    window.setup_dashboard_page.project_overview_editor.project_name_edit.setText("Dirty Project Updated")
    window.setup_dashboard_page.project_overview_editor.project_name_edit.editingFinished.emit()
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

