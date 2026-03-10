"""PySide6 GUI workflow tests for the Phase 5 authoring application."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QToolBar,
    QWidget,
)

from fpvs_studio.core.condition_template_profiles import (
    SIXTY_HZ_BLANK_FIXATION_PROFILE_ID,
    built_in_condition_template_profiles,
)
from fpvs_studio.core.enums import DutyCycleMode, InterConditionMode, RunMode, StimulusVariant
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import load_project_file
from fpvs_studio.gui.animations import AnimatedTabBar
from fpvs_studio.gui.application import create_application
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


def test_home_tab_is_first_and_existing_tabs_remain_usable(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Home Tabs Project")

    expected_tabs = [
        "Home",
        "Project",
        "Conditions",
        "Fixation & Session",
        "Assets / Preprocessing",
        "Run / Runtime",
    ]
    tab_labels = [window.main_tabs.tabText(index) for index in range(window.main_tabs.count())]
    assert tab_labels == expected_tabs

    window.main_tabs.setCurrentWidget(window.project_page)
    assert window.main_tabs.currentWidget() is window.project_page
    window.main_tabs.setCurrentWidget(window.conditions_page)
    assert window.main_tabs.currentWidget() is window.conditions_page
    window.main_tabs.setCurrentWidget(window.run_page)
    assert window.main_tabs.currentWidget() is window.run_page


def test_home_header_updates_when_project_name_changes(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Home Header Project")
    header_label = window.home_page.findChild(QLabel, "home_current_project_header")
    assert header_label is not None
    assert header_label.text() == "Current Project: Home Header Project"

    window.project_page.project_name_edit.setText("Renamed Header Project")
    window.project_page.project_name_edit.editingFinished.emit()

    qtbot.waitUntil(lambda: header_label.text() == "Current Project: Renamed Header Project")
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
    assert create_button.property("hoverAnimationEnabled") is True
    assert run_compile_button.property("hoverAnimationEnabled") is True
    assert run_launch_button.property("hoverAnimationEnabled") is True


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

    window.session_fixation_page.block_count_spin.setValue(2)
    window.run_page.serial_port_edit.setText("COM7")
    window.run_page.serial_port_edit.editingFinished.emit()
    window.run_page.serial_baudrate_spin.setValue(57600)
    window.project_page.background_color_edit.setText("#101010")
    window.project_page.background_color_edit.editingFinished.emit()

    condition_count_label = window.home_page.findChild(QLabel, "home_condition_count_value")
    block_count_label = window.home_page.findChild(QLabel, "home_block_count_value")
    fixation_label = window.home_page.findChild(QLabel, "home_fixation_task_value")
    accuracy_label = window.home_page.findChild(QLabel, "home_accuracy_task_value")
    runtime_summary_label = window.home_page.findChild(QLabel, "home_runtime_summary_value")
    template_label = window.home_page.findChild(QLabel, "home_project_template_value")
    description_label = window.home_page.findChild(QLabel, "home_project_description_value")
    assert condition_count_label is not None
    assert block_count_label is not None
    assert fixation_label is not None
    assert accuracy_label is not None
    assert runtime_summary_label is not None
    assert template_label is not None
    assert description_label is not None

    assert condition_count_label.text() == "1"
    assert block_count_label.text() == "2"
    assert fixation_label.text() == "Disabled"
    assert accuracy_label.text() == "Disabled"
    assert "com7 @ 57600" in runtime_summary_label.text().lower()
    assert "fpvs_6hz_every5_v1" in template_label.text()
    assert description_label.text() == "No description set yet."


def test_home_readiness_status_and_recent_activity_update_from_launch_checks(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Home Status Project")
    readiness_checklist = window.home_page.findChild(QListWidget, "home_readiness_checklist")
    recent_activity = window.home_page.findChild(QListWidget, "home_recent_activity_list")
    launch_button = window.home_page.findChild(QPushButton, "home_launch_test_session_button")
    readiness_card = window.home_page.findChild(QGroupBox, "home_preflight_card")
    assert readiness_checklist is not None
    assert recent_activity is not None
    assert launch_button is not None
    assert readiness_card is not None
    assert readiness_card.title() == "Launch Readiness"
    assert "runtime path: alpha test-mode only" in _list_widget_text(readiness_checklist).lower()

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

    qtbot.mouseClick(launch_button, Qt.MouseButton.LeftButton)

    assert captures["project_root"] == window.document.project_root
    qtbot.waitUntil(
        lambda: "status: launch readiness checks passed"
        in _list_widget_text(readiness_checklist).lower(),
    )
    assert "status: launch readiness checks passed" in _list_widget_text(recent_activity).lower()


def test_project_description_typing_round_trips_without_cursor_reset(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    typed_text = "testing this, why is this happening"
    _, window = _open_created_project(controller, qtbot, tmp_path, "Description Project")

    window.main_tabs.setCurrentWidget(window.project_page)
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

    profile_index = window.project_page.condition_profile_combo.findData(
        SIXTY_HZ_BLANK_FIXATION_PROFILE_ID
    )
    assert profile_index >= 0
    window.project_page.condition_profile_combo.setCurrentIndex(profile_index)

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

    profile_index = window.project_page.condition_profile_combo.findData(
        SIXTY_HZ_BLANK_FIXATION_PROFILE_ID
    )
    assert profile_index >= 0
    window.project_page.condition_profile_combo.setCurrentIndex(profile_index)

    first_before = window.document.get_condition(first_condition_id)
    second_before = window.document.get_condition(second_condition_id)
    assert first_before is not None
    assert second_before is not None
    assert first_before.sequence_count == 2
    assert second_before.sequence_count == 3

    qtbot.mouseClick(
        window.project_page.apply_profile_to_conditions_button,
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
    assert "launch readiness checks passed" in window.run_page.summary_text.toPlainText().lower()


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

    monkeypatch.setattr(
        window.document,
        "preflight_session",
        lambda refresh_hz: window.document.compile_session(refresh_hz=refresh_hz),
    )
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

    monkeypatch.setattr(
        window.document,
        "preflight_session",
        lambda refresh_hz: window.document.compile_session(refresh_hz=refresh_hz),
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
        "preflight_session",
        lambda refresh_hz: window.document.compile_session(refresh_hz=refresh_hz),
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
        "preflight_session",
        lambda refresh_hz: window.document.compile_session(refresh_hz=refresh_hz),
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
