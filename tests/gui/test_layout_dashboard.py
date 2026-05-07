"""PySide6 GUI workflow tests for the Phase 5 authoring application."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QToolBar,
    QWidget,
)
from tests.gui.helpers import (
    _list_widget_text,
    _open_created_project,
    _prepare_compile_ready_project,
    _write_image_directory,
)

from fpvs_studio.core.enums import DutyCycleMode, InterConditionMode, StimulusVariant
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.gui.controller import StudioController


def test_main_window_uses_home_and_setup_wizard_stack(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Home Stack Project")

    assert window.main_stack.count() == 2
    assert window.main_stack.indexOf(window.home_page) == 0
    assert window.main_stack.indexOf(window.setup_wizard_page) == 1
    assert window.main_stack.indexOf(window.conditions_page) == -1
    assert window.main_stack.indexOf(window.assets_page) == -1
    assert window.main_stack.indexOf(window.run_page) == -1
    assert window.main_stack.currentWidget() is window.setup_wizard_page
    assert window.conditions_page.add_condition_button is not None
    assert window.session_structure_page.block_count_spin is not None
    assert window.fixation_cross_settings_page.fixation_enabled_checkbox is not None


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


def test_setup_wizard_exists_and_uses_single_column_shell_with_steps(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Setup Wizard Shell")

    wizard = window.setup_wizard_page
    assert window.main_stack.indexOf(wizard) == 1
    assert wizard.shell.layout_mode == "single_column"
    assert wizard.shell.page_container.width_preset == "full"
    assert wizard.shell.title_label.text() == "Setup Wizard"
    assert wizard.setup_wizard_step_list.objectName() == "setup_wizard_step_list"
    assert wizard.setup_wizard_step_list.isVisible() is False
    assert wizard.progress_header_label.objectName() == "setup_wizard_progress_header"
    assert wizard.progress_steps.objectName() == "setup_wizard_progress_steps"
    assert wizard.step_status_badge.objectName() == "setup_wizard_ready_badge"
    assert wizard.setup_wizard_step_list.count() == 6
    assert wizard.step_stack.count() == 6
    assert wizard.content_stack.currentWidget() is wizard.guided_panel
    step_text = "\n".join(label.text() for label in wizard.progress_step_labels)
    assert "[OK]" not in step_text
    assert "[TODO]" not in step_text
    assert wizard.progress_header_label.text() == "Step 1 of 6: Project Details"
    assert "Project Details" in step_text
    assert "Conditions" in step_text
    assert "Stimuli" not in step_text
    assert "Display Settings" in step_text
    assert "Session Design" in step_text
    assert "Fixation Cross" in step_text
    assert "Review" in step_text
    assert wizard.findChild(QWidget, "setup_wizard_step_1_project_details") is not None
    assert wizard.findChild(QWidget, "setup_wizard_step_2_conditions") is not None
    assert wizard.findChild(QWidget, "setup_wizard_step_3_display_settings") is not None
    assert wizard.progress_steps.step_circles[0].property("setupProgressState") == "current"
    label_text = "\n".join(label.text() for label in wizard.findChildren(QLabel))
    assert "Current Step" not in label_text
    assert "Only the controls needed for this setup step are shown." not in label_text
    assert "Complete each setup step once" not in label_text
    assert "Setup Wizard uses the same project document" in label_text
    assert "Confirm the project name and template." not in label_text
    assert wizard.shell.footer_strip.objectName() == "setup_wizard_status_strip"
    assert wizard.shell.footer_strip.isVisible()
    assert wizard.setup_wizard_runtime_mode_label.text() == "Alpha: test-mode runtime path only"
    assert wizard.step_title_label.isVisible() is False
    assert wizard.step_status_badge.isVisible() is False
    assert wizard.step_card.property("wizardProjectStepFrame") == "true"
    assert window.conditions_page.shell is None
    assert window.assets_page.shell.footer_strip.isVisible() is False
    assert window.run_page.shell.footer_strip.isVisible() is False


def test_major_tabs_share_page_container_width_presets(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Shared Page Container")

    assert window.home_page.page_container.width_preset == "wide"
    assert window.home_page.page_container.max_content_width() == 1280
    assert window.setup_wizard_page.shell.page_container.width_preset == "full"
    assert window.setup_wizard_page.shell.page_container.max_content_width() == 16_777_215
    assert window.conditions_page.embedded is True
    assert window.conditions_page.shell is None
    assert window.assets_page.shell.page_container.width_preset == "full"
    assert window.assets_page.shell.page_container.max_content_width() == 16_777_215
    assert window.run_page.shell.page_container.width_preset == "medium"


def test_page_headers_use_home_left_alignment_and_non_home_center_alignment(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Header Geometry")
    home_launch_panel = window.home_page.findChild(QWidget, "home_launch_panel")
    assert home_launch_panel is not None
    assert (
        window.home_page.current_project_header.parent()
        is not window.home_page.page_container.header_widget
    )
    assert (
        window.home_page.current_project_subtitle.parent()
        is not window.home_page.page_container.header_widget
    )
    assert (
        window.home_page.current_project_header.parentWidget().parentWidget()
        is home_launch_panel
    )
    assert (
        window.home_page.current_project_subtitle.parentWidget().parentWidget()
        is home_launch_panel
    )
    assert window.home_page.current_project_header.alignment() & Qt.AlignmentFlag.AlignLeft
    assert window.home_page.current_project_subtitle.alignment() & Qt.AlignmentFlag.AlignLeft
    assert window.setup_wizard_page.shell.title_label.alignment() & Qt.AlignmentFlag.AlignCenter
    assert window.conditions_page.embedded is True
    assert window.assets_page.shell.title_label.alignment() & Qt.AlignmentFlag.AlignCenter


def test_stimuli_manager_page_uses_table_focused_layout(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Stimuli Manager Layout")
    page = window.assets_page
    header = page.assets_table.horizontalHeader()

    assert page.shell.title_label.text() == "Stimuli Manager"
    assert page.shell.subtitle_label.isVisible() is False
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


def test_switching_main_workflow_stack_keeps_outer_window_size_stable(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Stable Window Size")
    initial_size = window.size()

    for page in (
        window.home_page,
        window.setup_wizard_page,
    ):
        window.main_stack.setCurrentWidget(page)
        QApplication.processEvents()
        assert window.size() == initial_size


def test_primary_workflow_surfaces_fit_default_window_with_bounded_page_scrollbars(
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
        (window.home_page, window.home_page.page_container.scroll_area, 1),
        (
            window.setup_wizard_page,
            window.setup_wizard_page.shell.page_container.scroll_area,
            80,
        ),
    ]

    for page, scroll_area, max_scroll in page_specs:
        window.main_stack.setCurrentWidget(page)
        QApplication.processEvents()
        qtbot.waitUntil(
            lambda scroll_area=scroll_area, max_scroll=max_scroll: (
                scroll_area.verticalScrollBar().maximum() <= max_scroll
            )
        )
        assert scroll_area.verticalScrollBar().maximum() <= max_scroll


def test_conditions_advanced_editor_uses_flat_horizontal_master_detail_layout(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Conditions Shell")

    conditions_page = window.conditions_page
    assert window.main_stack.indexOf(conditions_page) == -1
    assert conditions_page.embedded is True
    assert conditions_page.shell is None
    assert conditions_page.condition_list_card.property("sectionCard") == "false"
    assert conditions_page.condition_editor_card.property("sectionCard") == "false"
    assert conditions_page.stimulus_sources_card.property("sectionCard") == "false"
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
    assert project_editor.manage_templates_button is not None
    assert project_editor.apply_profile_to_conditions_button is not None
    assert project_editor.apply_profile_to_conditions_button.isVisible() is False
    assert project_editor.project_overview_card.maximumWidth() == 820
    assert project_editor.project_overview_card.title_label.text() == "Project Details"
    assert project_editor.project_overview_card.title_label.isVisible() is False
    setup_icon = project_editor.findChild(QLabel, "setup_project_icon")
    checklist = project_editor.setup_checklist
    assert setup_icon is not None
    assert setup_icon.width() == 52
    assert setup_icon.height() == 52
    assert project_editor.findChild(QLabel, "project_overview_title").text() == "Project Details"
    assert project_editor.findChild(QLabel, "project_overview_step_badge").text() == "Step 1 of 6"
    assert checklist.objectName() == "project_overview_checklist"
    assert checklist.title_label.text() == "Ready for next step"
    assert 210 <= checklist.minimumWidth() <= checklist.maximumWidth()
    checklist_items = checklist.item_labels()
    assert [label.text() for label in checklist_items] == [
        "✓ Name",
        "✕ Description",
        "✕ Template",
    ]
    assert checklist_items[0].property("setupChecklistState") == "complete"
    assert checklist_items[1].property("setupChecklistState") == "incomplete"
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
    assert fixation_editor.target_count_mode_combo is not None
    assert "Estimated maximum feasible cross changes per condition:" in (
        fixation_editor.fixation_feasibility_label.text()
    )

    assert runtime_editor.refresh_hz_spin is not None
    assert runtime_editor.runtime_background_color_combo is not None
    assert runtime_editor.serial_baudrate_spin.isEnabled() is False
    assert not hasattr(runtime_editor, "display_index_edit")

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
    assert dashboard.setup_wizard_step_list.count() == 6
    assert "Project Details" in dashboard.setup_wizard_step_list.item(0).text()
    assert "Conditions" in dashboard.setup_wizard_step_list.item(1).text()
    assert "Display Settings" in dashboard.setup_wizard_step_list.item(2).text()
    assert "Session Design" in dashboard.setup_wizard_step_list.item(3).text()
    assert "Fixation Cross" in dashboard.setup_wizard_step_list.item(4).text()
    assert "Review" in dashboard.setup_wizard_step_list.item(5).text()


def test_setup_wizard_navigation_and_advanced_editor_access(
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
    advanced_button = guide.findChild(QPushButton, "setup_wizard_advanced_button")
    return_home_button = guide.findChild(QPushButton, "setup_wizard_return_home_button")
    assert back_button is not None
    assert next_button is not None
    assert advanced_button is not None
    assert return_home_button is not None

    assert guide.step_stack.currentIndex() == 0
    assert next_button.isEnabled()
    qtbot.mouseClick(next_button, Qt.MouseButton.LeftButton)
    assert guide.step_stack.currentIndex() == 1
    assert guide.step_stack.currentWidget() is guide.condition_setup_step
    assert guide.content_stack.currentWidget() is guide.guided_panel
    assert not next_button.isEnabled()
    assert advanced_button.isEnabled()
    assert guide.findChild(QListWidget, "setup_wizard_condition_list") is not None
    assert guide.findChild(QWidget, "setup_conditions_left_panel") is not None
    assert guide.findChild(QWidget, "setup_conditions_main_panel") is not None
    assert guide.findChild(QWidget, "setup_conditions_protocol_defaults_panel") is not None
    assert guide.findChild(QWidget, "setup_conditions_checklist_panel") is not None
    label_text = "\n".join(
        label.text() for label in guide.condition_setup_step.findChildren(QLabel)
    )
    assert "Image Version:" in label_text
    assert "Stimulus Variant" not in label_text
    assert "Cycles / Repeat" not in label_text
    qtbot.mouseClick(advanced_button, Qt.MouseButton.LeftButton)
    assert guide.content_stack.currentWidget() is guide.advanced_stack
    assert guide.advanced_stack.currentWidget() is window.conditions_page
    qtbot.mouseClick(advanced_button, Qt.MouseButton.LeftButton)
    assert guide.content_stack.currentWidget() is guide.guided_panel

    information_prompts: list[str] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.QMessageBox.information",
        lambda *args, **kwargs: information_prompts.append(str(args[2])),
    )
    qtbot.mouseClick(guide.add_condition_button, Qt.MouseButton.LeftButton)
    assert information_prompts == ["Please ensure you create all conditions before proceeding."]
    assert not next_button.isEnabled()
    assert advanced_button.isEnabled()
    assert "name every condition" in guide.step_status_label.text().lower()

    condition_id = guide.condition_setup_step.selected_condition_id()
    assert isinstance(condition_id, str)
    guide._document.update_condition(condition_id, name="Faces")
    qtbot.waitUntil(
        lambda: "assign base and oddball" in guide.step_status_label.text().lower()
    )
    assert not next_button.isEnabled()
    assert "assign base and oddball" in guide.step_status_label.text().lower()

    base_dir = _write_image_directory(tmp_path / "wizard-condition-base")
    oddball_dir = _write_image_directory(tmp_path / "wizard-condition-oddball")
    guide._document.import_condition_stimulus_folder(condition_id, role="base", source_dir=base_dir)
    QApplication.processEvents()
    assert not next_button.isEnabled()
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=oddball_dir,
    )
    qtbot.waitUntil(next_button.isEnabled)

    qtbot.mouseClick(next_button, Qt.MouseButton.LeftButton)
    assert guide.step_stack.currentWidget() is guide.runtime_settings_editor
    assert advanced_button.isEnabled()
    qtbot.mouseClick(advanced_button, Qt.MouseButton.LeftButton)
    assert guide.content_stack.currentWidget() is guide.advanced_stack
    assert guide.advanced_stack.currentWidget() is window.run_page
    assert advanced_button.text() == "Back to Guided Step"

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


def test_setup_wizard_refresh_skips_hidden_heavy_pages(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Refresh Scope")
    guide = window.setup_wizard_page
    guide.open_wizard(step_key="project")
    calls = {"assets": 0, "run": 0}

    def _count_assets_refresh() -> None:
        calls["assets"] += 1

    def _count_run_refresh() -> None:
        calls["run"] += 1

    monkeypatch.setattr(window.assets_page, "refresh", _count_assets_refresh)
    monkeypatch.setattr(window.run_page, "refresh", _count_run_refresh)

    guide.refresh()

    assert calls == {"assets": 0, "run": 0}


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


def test_setup_wizard_conditions_step_duplicates_metadata_without_images(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Condition Duplicate")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")

    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert isinstance(condition_id, str)
    step.condition_name_edit.setText("Faces")
    step.condition_name_edit.editingFinished.emit()
    step.trigger_code_spin.setValue(42)
    step.instructions_edit.setPlainText("Look at each image.")

    qtbot.mouseClick(step.duplicate_condition_button, Qt.MouseButton.LeftButton)

    duplicated_id = step.selected_condition_id()
    assert isinstance(duplicated_id, str)
    assert duplicated_id != condition_id
    duplicated = window.document.get_condition(duplicated_id)
    assert duplicated is not None
    assert duplicated.name == "Faces Copy"
    assert duplicated.trigger_code == 2
    assert duplicated.instructions == "Look at each image."
    base_set = window.document.get_condition_stimulus_set(duplicated_id, "base")
    oddball_set = window.document.get_condition_stimulus_set(duplicated_id, "oddball")
    assert base_set.image_count == 0
    assert oddball_set.image_count == 0
    assert "Needs images" in step.condition_list.currentItem().text()


def test_setup_wizard_conditions_step_requires_descriptive_name_and_positive_trigger(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Condition Gate")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")
    next_button = guide.findChild(QPushButton, "setup_wizard_next_button")
    assert next_button is not None

    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert isinstance(condition_id, str)
    assert "Needs name" in step.condition_list.currentItem().text()
    assert step.name_check_status.text() == "Enter a descriptive name"
    assert step.base_check_status.text() == "Base Images Not Selected"
    assert step.oddball_check_status.text() == "Oddball Images Not Selected"
    assert not next_button.isEnabled()

    for invalid_name in ("A", "AB", "Condition 3"):
        guide._document.update_condition(condition_id, name=invalid_name)
        QApplication.processEvents()
        assert step.name_check_status.text() == "Enter a descriptive name"
        assert not next_button.isEnabled()

    guide._document.update_condition(condition_id, name="Dog")
    QApplication.processEvents()
    assert step.name_check_status.text() == "Complete"

    guide._document.update_condition(condition_id, trigger_code=0)
    QApplication.processEvents()
    assert step.trigger_check_status.text() == "Use a trigger code of 1 or higher"

    base_dir = _write_image_directory(tmp_path / "gated-condition-base")
    oddball_dir = _write_image_directory(tmp_path / "gated-condition-oddball")
    guide._document.import_condition_stimulus_folder(condition_id, role="base", source_dir=base_dir)
    guide._document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=oddball_dir,
    )
    QApplication.processEvents()
    assert step.base_check_status.text() == "Complete"
    assert step.oddball_check_status.text() == "Complete"
    assert not next_button.isEnabled()

    guide._document.update_condition(condition_id, trigger_code=1)
    QApplication.processEvents()
    assert step.trigger_check_status.text() == "Complete"
    assert next_button.isEnabled()


def test_setup_wizard_condition_image_picker_starts_in_project_stimuli_folder(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Wizard Image Picker")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")
    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)

    calls: list[tuple[str, str]] = []

    def _capture_directory(_parent, title: str, directory: str) -> str:
        calls.append((title, directory))
        return ""

    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step.QFileDialog.getExistingDirectory",
        _capture_directory,
    )

    qtbot.mouseClick(step.base_import_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(step.oddball_import_button, Qt.MouseButton.LeftButton)

    expected_start = str(window.document.project_root / "stimuli")
    assert calls == [
        ("Choose Base Stimulus Folder", expected_start),
        ("Choose Oddball Stimulus Folder", expected_start),
    ]


def test_setup_wizard_control_condition_button_requires_assigned_images(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Control Condition Enable")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")

    assert not step.create_control_condition_button.isEnabled()

    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert condition_id is not None
    assert not step.create_control_condition_button.isEnabled()

    base_dir = _write_image_directory(tmp_path / "control-enable-base")
    oddball_dir = _write_image_directory(tmp_path / "control-enable-oddball")
    window.document.import_condition_stimulus_folder(condition_id, role="base", source_dir=base_dir)
    window.document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=oddball_dir,
    )
    qtbot.waitUntil(step.create_control_condition_button.isEnabled)


@pytest.mark.parametrize(
    ("variant", "name"),
    [
        (StimulusVariant.GRAYSCALE, "Faces Grayscale Control"),
        (StimulusVariant.ROT180, "Faces 180 Degree Rotated Control"),
        (StimulusVariant.PHASE_SCRAMBLED, "Faces Phase-Scrambled Control"),
    ],
)
def test_setup_wizard_creates_control_condition_from_existing_stimuli(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
    variant: StimulusVariant,
    name: str,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, f"{variant.value} Control")
    guide = window.setup_wizard_page
    step = guide.condition_setup_step
    guide.open_wizard(step_key="conditions")
    qtbot.mouseClick(step.add_condition_button, Qt.MouseButton.LeftButton)
    condition_id = step.selected_condition_id()
    assert condition_id is not None
    window.document.update_condition(condition_id, name="Faces")
    base_dir = _write_image_directory(tmp_path / f"{variant.value}-base")
    oddball_dir = _write_image_directory(tmp_path / f"{variant.value}-oddball")
    window.document.import_condition_stimulus_folder(condition_id, role="base", source_dir=base_dir)
    window.document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=oddball_dir,
    )
    qtbot.waitUntil(step.create_control_condition_button.isEnabled)
    materialize_calls = 0

    def _count_materialization() -> None:
        nonlocal materialize_calls
        materialize_calls += 1

    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step.ControlConditionDialog.exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step.ControlConditionDialog.selected_variant",
        lambda self: variant,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.condition_setup_step.ControlConditionDialog.condition_name",
        lambda self: name,
    )
    monkeypatch.setattr(step, "_materialize_control_variant", _count_materialization)

    qtbot.mouseClick(step.create_control_condition_button, Qt.MouseButton.LeftButton)

    selected_id = step.selected_condition_id()
    assert selected_id is not None
    source = window.document.get_condition(condition_id)
    control = window.document.get_condition(selected_id)
    assert source is not None
    assert control is not None
    assert control.name == name
    assert control.base_stimulus_set_id == source.base_stimulus_set_id
    assert control.oddball_stimulus_set_id == source.oddball_stimulus_set_id
    assert control.stimulus_variant == variant
    assert control.trigger_code == 2
    assert materialize_calls == 1


def test_advanced_conditions_image_picker_starts_in_project_stimuli_folder(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Advanced Image Picker")
    page = window.conditions_page
    qtbot.mouseClick(page.add_condition_button, Qt.MouseButton.LeftButton)

    calls: list[tuple[str, str]] = []

    def _capture_directory(_parent, title: str, directory: str) -> str:
        calls.append((title, directory))
        return ""

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", _capture_directory)

    qtbot.mouseClick(page.base_import_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(page.oddball_import_button, Qt.MouseButton.LeftButton)

    expected_start = str(window.document.project_root / "stimuli")
    assert calls == [
        ("Choose Base Stimulus Folder", expected_start),
        ("Choose Oddball Stimulus Folder", expected_start),
    ]


def test_setup_wizard_advanced_replaces_guided_view_for_session_step(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Session Advanced Swap")
    guide = window.setup_wizard_page
    window.main_stack.setCurrentWidget(guide)
    guide.open_wizard(step_key="session")

    assert guide.content_stack.currentWidget() is guide.guided_panel
    assert guide.step_stack.currentWidget().findChild(QLabel, "setup_wizard_session_summary")

    qtbot.mouseClick(guide.setup_wizard_advanced_button, Qt.MouseButton.LeftButton)

    assert guide.content_stack.currentWidget() is guide.advanced_stack
    assert guide.advanced_stack.currentWidget() is window.session_structure_page

    qtbot.mouseClick(guide.setup_wizard_advanced_button, Qt.MouseButton.LeftButton)
    guide.open_wizard(step_key="fixation")

    assert guide.content_stack.currentWidget() is guide.guided_panel
    assert guide.step_stack.currentWidget().findChild(QLabel, "setup_wizard_fixation_summary")

    qtbot.mouseClick(guide.setup_wizard_advanced_button, Qt.MouseButton.LeftButton)

    assert guide.content_stack.currentWidget() is guide.advanced_stack
    assert guide.advanced_stack.currentWidget() is window.fixation_cross_settings_page


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
    conditions_page.add_condition_button.click()
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

    window.main_stack.setCurrentWidget(dashboard)
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
    launch_panel = window.home_page.findChild(QWidget, "home_launch_panel")
    assert header_label is not None
    assert launch_panel is not None
    assert header_label.parentWidget().parentWidget() is launch_panel
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
    assert save_button is not None
    assert launch_button is not None
    assert edit_setup_button is not None
    assert stimuli_button is None
    assert runtime_button is None
    assert launch_button.text() == "Launch Experiment"
    assert window.run_page.launch_button.text() == "Launch Experiment"
    assert window.launch_action.text() == "Launch Experiment"
    assert "alpha test-mode" in window.launch_action.toolTip().lower()
    qtbot.waitUntil(lambda: launch_button.width() > 0)
    utility_buttons = (open_button, new_button, save_button, edit_setup_button)
    ordered_buttons = sorted(
        utility_buttons,
        key=lambda button: button.geometry().x(),
    )
    assert [button.objectName() for button in ordered_buttons] == [
        "home_open_project_button",
        "home_create_project_button",
        "home_save_project_button",
        "home_edit_setup_button",
    ]
    assert len({button.width() for button in ordered_buttons}) == 1
    assert {button.minimumWidth() for button in ordered_buttons} == {160}
    assert launch_button.width() > ordered_buttons[0].width()
    assert launch_button.parent() is window.home_page.findChild(QWidget, "home_launch_panel")
    launch_panel = launch_button.parentWidget()
    assert launch_panel is not None
    assert launch_panel.maximumWidth() == 860
    assert launch_button.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed

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
    qtbot.mouseClick(edit_setup_button, Qt.MouseButton.LeftButton)
    assert window.main_stack.currentWidget() is window.setup_wizard_page

    assert trigger_counts == {"new": 1, "open": 1, "save": 1, "launch": 1}


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
    assert status_label.text().startswith("Status: ")
    assert subtitle_label.text() == "No description set yet."

    window.setup_dashboard_page.project_overview_editor.project_description_edit.setPlainText(
        "This is the participant-facing project summary."
    )
    window.flush_pending_edits()
    QApplication.processEvents()
    assert subtitle_label.text() == "This is the participant-facing project summary."


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
    readiness_text = _list_widget_text(run_readiness_list)
    assert "[OK]" not in readiness_text
    assert "[TODO]" not in readiness_text
    assert "runtime path: alpha test-mode only" in readiness_text.lower()
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


