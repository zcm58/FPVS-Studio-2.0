"""PySide6 GUI workflow tests for the Phase 5 authoring application."""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QWidget,
)
from tests.gui.helpers import (
    _find_profile_row,
    _list_widget_text,
    _open_created_project,
)

from fpvs_studio.core.condition_template_profiles import (
    SIXTY_HZ_BLANK_FIXATION_PROFILE_ID,
    STUDIO_DEFAULT_PROFILE_ID,
    built_in_condition_template_profiles,
    list_condition_template_profiles,
)
from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import load_project_file
from fpvs_studio.gui.application import create_application
from fpvs_studio.gui.condition_template_manager_dialog import (
    ConditionTemplateManagerDialog,
    ConditionTemplateProfileEditorDialog,
)
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.create_project_dialog import CreateProjectDialog
from fpvs_studio.gui.settings_dialog import AppSettingsDialog
from fpvs_studio.gui.welcome_window import WelcomeWindow


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


def test_welcome_window_hides_recent_projects_panel_when_empty(
    controller: StudioController,
) -> None:
    welcome = controller.welcome_window
    assert welcome is not None
    recent_panel = welcome.findChild(QWidget, "welcome_recent_projects_panel")
    recent_list = welcome.findChild(QListWidget, "welcome_recent_project_list")
    assert recent_panel is not None
    assert recent_list is not None
    assert recent_panel.isVisible() is False
    assert recent_list.count() == 0


def test_recent_projects_render_and_open_from_welcome(
    qtbot,
    qapp,
    tmp_path: Path,
) -> None:
    controller = StudioController(qapp)
    root_dir = tmp_path / "fpvs-root"
    root_dir.mkdir(parents=True, exist_ok=True)
    controller.save_fpvs_root_dir(root_dir)
    scaffold = create_project(root_dir, "Recent Launch Project")
    stale_path = root_dir / "missing-project"
    controller._settings.setValue(
        "projects/recent_project_roots",
        [str(stale_path), str(scaffold.project_root)],
    )
    controller._settings.sync()

    controller.show_welcome()
    assert controller.welcome_window is not None
    qtbot.addWidget(controller.welcome_window)

    recent_panel = controller.welcome_window.findChild(QWidget, "welcome_recent_projects_panel")
    recent_list = controller.welcome_window.findChild(QListWidget, "welcome_recent_project_list")
    assert recent_panel is not None
    assert recent_list is not None
    assert recent_panel.isVisible() is True
    assert recent_list.count() == 1
    assert recent_list.item(0).text() == str(scaffold.project_root)

    qtbot.mouseClick(
        recent_list.viewport(),
        Qt.MouseButton.LeftButton,
        pos=recent_list.visualItemRect(recent_list.item(0)).center(),
    )

    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)
    assert controller.main_window.document.project_root == scaffold.project_root


def test_opening_project_records_recent_project_root(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    scaffold = create_project(tmp_path, "Recorded Recent Project")

    document = controller.open_project(scaffold.project_root)

    assert document is not None
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)
    assert controller.load_recent_project_roots() == [scaffold.project_root]


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
        editor.duty_cycle_combo.setCurrentIndex(
            editor.duty_cycle_combo.findData(DutyCycleMode.BLANK_50)
        )
        editor.sequence_count_spin.setValue(2)
        editor.oddball_cycles_spin.setValue(120)
        editor.preferred_refresh_enabled_checkbox.setChecked(True)
        editor.preferred_refresh_spin.setValue(120.0)
        editor.fixation_enabled_checkbox.setChecked(True)
        editor.accuracy_enabled_checkbox.setChecked(True)
        editor.target_count_mode_combo.setCurrentIndex(
            editor.target_count_mode_combo.findData("fixed")
        )
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
    assert (
        window.setup_dashboard_page.project_overview_editor.project_name_edit.text()
        == "Visual Oddball"
    )


def test_open_existing_project_populates_gui_correctly(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    scaffold = create_project(tmp_path, "Opened Project")

    controller.open_project(scaffold.project_root)
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)

    assert (
        controller.main_window.setup_dashboard_page.project_overview_editor.project_name_edit.text()
        == "Opened Project"
    )
    assert (
        controller.main_window.setup_dashboard_page.project_overview_editor.project_root_value.text().endswith(
            "opened-project"
        )
    )


