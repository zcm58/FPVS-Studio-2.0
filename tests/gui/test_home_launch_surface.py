"""Focused GUI workflow tests split from the former layout dashboard suite."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QToolBar,
    QWidget,
)
from tests.gui.helpers import (
    _assert_visible_children_within_parent,
    _list_widget_text,
    _open_created_project,
    _prepare_compile_ready_project,
)

from fpvs_studio.gui.controller import StudioController


def test_ready_project_reopens_to_home_launch_surface(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Ready Home Project")
    _prepare_compile_ready_project(window, tmp_path / "ready-home-assets")
    assert window.save_project() is True

    controller.open_project(window.document.project_root)
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)

    reopened = controller.main_window
    assert reopened.main_stack.currentWidget() is reopened.home_page
    assert reopened.home_page.findChild(QPushButton, "home_launch_experiment_button") is not None


def test_ready_project_home_inherits_welcome_window_size(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Welcome Sized Home")
    _prepare_compile_ready_project(window, tmp_path / "welcome-sized-home-assets")
    assert window.save_project() is True
    project_root = window.document.project_root
    assert project_root is not None
    welcome = controller.welcome_window
    assert welcome is not None

    QApplication.processEvents()
    controller.show_welcome()
    QApplication.processEvents()
    assert welcome.isVisible()
    welcome.resize(1110, 700)
    QApplication.processEvents()
    welcome_size = welcome.size()

    controller.open_project(project_root)
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)

    reopened = controller.main_window
    assert reopened.main_stack.currentWidget() is reopened.home_page
    assert reopened.isVisible()
    assert welcome.isVisible()
    assert reopened.size() == welcome_size
    QApplication.processEvents()
    qtbot.waitUntil(lambda: not welcome.isVisible())


def test_home_header_updates_when_project_name_changes(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Home Header Project")
    header_label = window.home_page.findChild(QLabel, "home_current_project_header")
    launch_panel = window.home_page.findChild(QWidget, "home_launch_panel")
    home_hero_container = window.home_page.findChild(QWidget, "home_hero_container")
    assert header_label is not None
    assert launch_panel is not None
    assert home_hero_container is not None
    assert header_label.parentWidget().parentWidget() is home_hero_container
    assert header_label.text() == "Home Header Project"

    window.setup_dashboard_page.project_overview_editor.project_name_edit.setText(
        "Renamed Header Project"
    )
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
    launch_button = window.home_page.findChild(QPushButton, "home_launch_experiment_button")
    edit_setup_button = window.home_page.findChild(QPushButton, "home_edit_setup_button")
    stimuli_button = window.home_page.findChild(QPushButton, "home_stimuli_manager_button")
    runtime_button = window.home_page.findChild(QPushButton, "home_runtime_settings_button")
    assert new_button is not None
    assert open_button is not None
    assert save_button is None
    assert launch_button is not None
    assert edit_setup_button is not None
    assert stimuli_button is None
    assert runtime_button is None
    assert launch_button.text() == "Launch Experiment"
    assert window.run_page.launch_button.text() == "Launch Experiment"
    assert window.launch_action.text() == "Launch Experiment"
    assert "beta test-mode" in window.launch_action.toolTip().lower()
    assert launch_button.isEnabled() is False
    assert launch_button.property("launchActionRole") == "primary"
    assert edit_setup_button.text() == "Complete Setup"
    assert edit_setup_button.property("primaryActionRole") == "true"
    assert edit_setup_button.property("secondaryActionRole") == "false"
    qtbot.waitUntil(lambda: launch_button.width() > 0)
    metric_text = "\n".join(
        label.text() for label in window.home_page.findChildren(QLabel)
    )
    assert "Fixation Cross" in metric_text
    assert "Accuracy Tracking" in metric_text
    assert "Fixation Task" not in metric_text
    assert "Accuracy Task" not in metric_text

    utility_buttons = (open_button, new_button, edit_setup_button)
    ordered_buttons = sorted(
        utility_buttons,
        key=lambda button: button.geometry().x(),
    )
    assert [button.objectName() for button in ordered_buttons] == [
        "home_open_project_button",
        "home_create_project_button",
        "home_edit_setup_button",
    ]
    button_widths = [button.width() for button in ordered_buttons]
    assert max(button_widths) - min(button_widths) <= 1
    assert {button.minimumWidth() for button in ordered_buttons} == {160}
    assert launch_button.width() > ordered_buttons[0].width()
    assert launch_button.parent() is window.home_page.findChild(QWidget, "home_hero_container")
    launch_panel = window.home_page.findChild(QWidget, "home_launch_panel")
    home_hero_container = window.home_page.findChild(QWidget, "home_hero_container")
    assert launch_panel is not None
    assert home_hero_container is not None
    assert home_hero_container.maximumWidth() == 760
    assert launch_button.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed

    trigger_counts = {"new": 0, "open": 0, "launch": 0}
    window.new_project_action.triggered.connect(
        lambda _checked=False: trigger_counts.__setitem__("new", trigger_counts["new"] + 1)
    )
    window.open_project_action.triggered.connect(
        lambda _checked=False: trigger_counts.__setitem__("open", trigger_counts["open"] + 1)
    )
    window.launch_action.triggered.connect(
        lambda _checked=False: trigger_counts.__setitem__("launch", trigger_counts["launch"] + 1)
    )

    qtbot.mouseClick(new_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(open_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(launch_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(edit_setup_button, Qt.MouseButton.LeftButton)
    assert window.main_stack.currentWidget() is window.setup_wizard_page
    assert window.setup_wizard_page.step_stack.currentWidget() is (
        window.setup_wizard_page.project_step_surface
    )

    assert trigger_counts == {"new": 1, "open": 1, "launch": 0}


def test_launch_buttons_share_primary_visual_role(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Launch Role Project")
    home_launch_button = window.home_page.findChild(QPushButton, "home_launch_experiment_button")
    run_launch_button = window.run_page.findChild(QPushButton, "launch_test_session_button")
    assert home_launch_button is not None
    assert run_launch_button is not None
    assert home_launch_button.text() == "Launch Experiment"
    assert run_launch_button.text() == "Launch Experiment"
    assert home_launch_button.property("launchActionRole") == "primary"
    assert home_launch_button.property("homeLaunchHeroAction") == "true"
    assert not home_launch_button.icon().isNull()
    assert run_launch_button.property("launchActionRole") == "primary"


def test_incomplete_home_launch_state_is_error_and_disabled(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Incomplete Home State")

    status_label = window.home_page.findChild(QLabel, "home_launch_status_indicator")
    home_launch_button = window.home_page.findChild(QPushButton, "home_launch_experiment_button")
    complete_setup_button = window.home_page.findChild(QPushButton, "home_edit_setup_button")
    run_launch_button = window.run_page.findChild(QPushButton, "launch_test_session_button")

    assert status_label is not None
    assert home_launch_button is not None
    assert complete_setup_button is not None
    assert run_launch_button is not None
    assert status_label.text() == "Setup Required"
    assert status_label.property("statusState") == "error"
    assert status_label.alignment() == Qt.AlignmentFlag.AlignCenter
    assert status_label.minimumWidth() == 224
    assert status_label.minimumHeight() >= 34
    assert home_launch_button.isEnabled() is False
    assert "Needs setup:" in home_launch_button.toolTip()
    assert home_launch_button.statusTip() == home_launch_button.toolTip()
    assert complete_setup_button.text() == "Complete Setup"
    assert complete_setup_button.property("primaryActionRole") == "true"
    assert complete_setup_button.property("secondaryActionRole") == "false"
    assert run_launch_button.isEnabled() is False


def test_complete_setup_jumps_to_earliest_incomplete_step(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Complete Setup Jump")

    window.setup_wizard_page.project_overview_editor.project_description_edit.setPlainText(
        "Project details are complete, but conditions are not."
    )
    window.flush_pending_edits()
    window.show_home()
    QApplication.processEvents()

    complete_setup_button = window.home_page.findChild(QPushButton, "home_edit_setup_button")
    launch_button = window.home_page.findChild(QPushButton, "home_launch_experiment_button")
    assert complete_setup_button is not None
    assert launch_button is not None
    assert complete_setup_button.text() == "Complete Setup"
    assert launch_button.isEnabled() is False

    qtbot.mouseClick(complete_setup_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert window.main_stack.currentWidget() is window.setup_wizard_page
    assert window.setup_wizard_page.step_stack.currentWidget() is (
        window.setup_wizard_page.conditions_step_surface
    )
    assert window.setup_wizard_page.progress_steps.step_circles[1].property(
        "setupProgressState"
    ) == "current"


def test_main_window_no_longer_exposes_top_level_tab_bar(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "No Tabs Project")
    assert not hasattr(window.main_stack, "tabBar")
    assert window.main_stack.indexOf(window.home_page) >= 0
    assert window.main_stack.indexOf(window.setup_wizard_page) >= 0


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


def test_ready_home_launch_state_does_not_keep_blocker_tooltip(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Ready Tooltip Project")
    _prepare_compile_ready_project(window, tmp_path / "ready-tooltip-assets")

    launch_button = window.home_page.findChild(QPushButton, "home_launch_experiment_button")

    assert launch_button is not None
    assert launch_button.isEnabled()
    assert "Needs setup:" not in launch_button.toolTip()
    assert "beta test-mode" in launch_button.toolTip().lower()


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
        for action in (menu_action.menu().actions() if menu_action.menu() is not None else [])
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


def test_window_title_and_status_bar_surface_beta_runtime_designation(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Beta Label Project")
    beta_label = window.findChild(QLabel, "beta_runtime_status_label")

    assert beta_label is None
    assert "FPVS Studio Beta" in window.windowTitle()


def test_home_launch_surface_shows_only_essential_project_session_metadata(
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
    launch_panel = window.home_page.findChild(QWidget, "home_launch_panel")
    project_icon = window.home_page.findChild(QLabel, "home_project_icon")
    metrics_panel = window.home_page.findChild(QWidget, "home_metrics_panel")
    readiness_list = window.home_page.findChild(QListWidget, "home_readiness_list")
    subtitle_label = window.home_page.findChild(QLabel, "home_current_project_subtitle")
    assert condition_count_label is not None
    assert block_count_label is not None
    assert fixation_label is not None
    assert accuracy_label is not None
    assert template_label is None
    assert description_label is None
    assert root_path_label is None
    assert readiness_list is None
    assert status_label is not None
    assert launch_panel is not None
    assert project_icon is not None
    assert not project_icon.pixmap().isNull()
    assert metrics_panel is not None
    assert subtitle_label is not None

    project_labels = {
        label.text().strip()
        for label in window.setup_dashboard_page.project_overview_editor.findChildren(QLabel)
        if label.text().strip()
    }
    assert "Protocol Template" not in project_labels
    assert "Template Status" not in project_labels
    assert "Image Timing" in project_labels
    assert window.setup_dashboard_page.project_overview_editor.condition_profile_combo is not None
    assert window.setup_dashboard_page.project_overview_editor.manage_templates_button is not None
    assert (
        window.setup_dashboard_page.project_overview_editor.apply_profile_to_conditions_button
        is not None
    )

    assert condition_count_label.text() == "1"
    assert block_count_label.text() == "2"
    assert fixation_label.text() == "Disabled"
    assert accuracy_label.text() == "Disabled"
    assert status_label.text()
    assert subtitle_label.text() == "No description set yet."

    window.setup_dashboard_page.project_overview_editor.project_description_edit.setPlainText(
        "This is the participant-facing project summary."
    )
    window.flush_pending_edits()
    QApplication.processEvents()
    assert subtitle_label.text() == "This is the participant-facing project summary."

    long_description = " ".join(
        [
            "This FPVS Studio project description is intentionally long enough to test",
            "the bounded Home screen preview without limiting the saved project text.",
            "It should not overlap action buttons, metrics, or the launch control.",
        ]
    )
    window.setup_dashboard_page.project_overview_editor.project_description_edit.setPlainText(
        long_description
    )
    window.flush_pending_edits()
    QApplication.processEvents()

    assert window.document.project.meta.description == long_description
    assert subtitle_label.text().endswith("...")
    assert len(subtitle_label.text()) <= 96
    assert subtitle_label.toolTip() == long_description
    assert subtitle_label.maximumHeight() <= subtitle_label.fontMetrics().lineSpacing() * 2 + 4
    _assert_visible_children_within_parent(launch_panel)
