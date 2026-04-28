"""PySide6 GUI workflow tests for the Phase 5 authoring application."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QToolBar,
    QWidget,
)
from tests.gui.helpers import (
    _list_widget_text,
    _open_created_project,
    _prepare_compile_ready_project,
)

from fpvs_studio.core.condition_template_profiles import (
    SIXTY_HZ_BLANK_FIXATION_PROFILE_ID,
    built_in_condition_template_profiles,
)
from fpvs_studio.core.enums import DutyCycleMode, InterConditionMode, StimulusVariant
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.gui.animations import AnimatedTabBar
from fpvs_studio.gui.controller import StudioController


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
        qtbot.waitUntil(
            lambda scroll_area=scroll_area: scroll_area.verticalScrollBar().maximum() <= 1
        )
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
    assert (
        conditions_page.master_detail_layout.itemAt(0).widget()
        is conditions_page.condition_list_card
    )
    assert (
        conditions_page.master_detail_layout.itemAt(1).widget()
        is conditions_page.condition_detail_stack
    )
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
    assert dashboard.runtime_settings_editor.refresh_hz_spin.value() == pytest.approx(
        75.0, abs=0.01
    )
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
    qtbot.waitUntil(
        lambda: all(tab_bar.tabRect(index).width() > 0 for index in range(tab_bar.count()))
    )

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
    assert (
        window.setup_dashboard_page.project_overview_editor.apply_profile_to_conditions_button
        is not None
    )

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

    profile_index = (
        window.setup_dashboard_page.project_overview_editor.condition_profile_combo.findData(
            SIXTY_HZ_BLANK_FIXATION_PROFILE_ID
        )
    )
    assert profile_index >= 0
    window.setup_dashboard_page.project_overview_editor.condition_profile_combo.setCurrentIndex(
        profile_index
    )
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

    assert (
        window.setup_dashboard_page.project_overview_editor.findChild(
            QWidget, "background_color_edit"
        )
        is None
    )

    runtime_background_combo = window.run_page.findChild(
        QComboBox, "runtime_background_color_combo"
    )
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
    legacy_settings = legacy_project.settings.model_copy(
        update={"display": legacy_display_settings}
    )
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
        lambda: (
            "status: launch checks passed" in window.run_page.summary_text.toPlainText().lower()
        ),
    )


