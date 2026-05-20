"""Focused GUI workflow tests split from the former layout dashboard suite."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QPoint,
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QLabel,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QWidget,
)
from tests.gui.helpers import (
    _assert_balanced_setup_stepper,
    _assert_setup_wizard_vertical_scrolling_disabled,
    _assert_visible_children_within_parent,
    _open_created_project,
    _prepare_compile_ready_project,
)

from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.design_system import COLOR_PAGE_BACKGROUND


def test_main_window_uses_home_and_setup_wizard_stack(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Home Stack Project")

    assert window.main_stack.count() == 3
    assert window.main_stack.indexOf(window.home_page) == 0
    assert window.main_stack.indexOf(window.setup_wizard_page) == 1
    assert window.main_stack.indexOf(window.image_resizer_page) == 2
    assert window.main_stack.indexOf(window.conditions_page) == -1
    assert window.main_stack.indexOf(window.assets_page) == -1
    assert window.main_stack.indexOf(window.run_page) == -1
    assert window.main_stack.currentWidget() is window.home_page
    assert window.conditions_page.add_condition_button is not None
    assert window.session_structure_page.block_count_spin is not None
    assert window.fixation_cross_settings_page.fixation_enabled_checkbox is not None


def test_setup_wizard_exists_and_uses_single_column_shell_with_steps(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Setup Wizard Shell")

    wizard = window.setup_wizard_page
    window.show_setup_wizard()
    QApplication.processEvents()
    assert window.main_stack.indexOf(wizard) == 1
    _assert_setup_wizard_vertical_scrolling_disabled(wizard)
    assert wizard.shell.layout_mode == "single_column"
    assert wizard.shell.page_container.width_preset == "full"
    assert wizard.shell.title_label.text() == "Setup Wizard"
    assert wizard.findChild(QListWidget, "setup_wizard_step_list") is None
    assert wizard.findChild(QLabel, "setup_wizard_progress_header") is None
    assert wizard.progress_steps.objectName() == "setup_wizard_progress_steps"
    assert wizard.step_status_badge.objectName() == "setup_wizard_ready_badge"
    assert len(wizard.progress_steps.step_items) == 6
    assert wizard.step_stack.count() == 6
    assert wizard.project_step_surface.property("setupStepSurface") == "true"
    assert wizard.conditions_step_surface.property("setupStepSurface") == "true"
    assert wizard.conditions_step_surface.content.maximumWidth() == 1040
    assert wizard.experiment_step_surface.property("setupStepSurface") == "true"
    assert wizard.fixation_step_surface.property("setupStepSurface") == "true"
    assert wizard.response_step_surface.property("setupStepSurface") == "true"
    assert wizard.review_step_surface.property("setupStepSurface") == "true"
    assert wizard.content_stack.currentWidget() is wizard.guided_panel
    assert wizard.advanced_stack.indexOf(wizard.conditions_page) >= 0
    assert wizard.conditions_page.isVisible() is False
    assert wizard.findChild(QPushButton, "setup_wizard_advanced_button") is None
    QApplication.processEvents()
    qtbot.waitUntil(lambda: all(label.text().strip() for label in wizard.progress_step_labels))
    _assert_balanced_setup_stepper(wizard)
    step_text = "\n".join(label.text() for label in wizard.progress_step_labels)
    step_metadata_text = "\n".join(item.toolTip() for item in wizard.progress_steps.step_items)
    assert "[OK]" not in step_text
    assert "[TODO]" not in step_text
    assert "Step 1 of 6" not in "\n".join(label.text() for label in wizard.findChildren(QLabel))
    assert "Project" in step_metadata_text
    assert "Conditions" in step_metadata_text
    assert "Experiment" in step_metadata_text
    assert "Display Settings" not in step_metadata_text
    assert "Session Design" not in step_metadata_text
    assert "Fixation" in step_metadata_text
    assert "Response" in step_metadata_text
    assert "Review" in step_metadata_text
    assert wizard.findChild(QWidget, "setup_wizard_step_1_project") is not None
    assert wizard.findChild(QWidget, "setup_wizard_step_2_conditions") is not None
    assert wizard.findChild(QWidget, "setup_wizard_step_3_experiment") is not None
    assert wizard.findChild(QWidget, "setup_wizard_step_4_fixation") is not None
    assert wizard.findChild(QWidget, "setup_wizard_step_5_response") is not None
    assert wizard.findChild(QWidget, "setup_wizard_step_6_review") is not None
    assert wizard.progress_steps.step_circles[0].property("setupProgressState") == "current"
    initial_progress_labels = [label.text() for label in wizard.progress_step_labels]
    for item in wizard.progress_steps.step_items:
        item_right = item.mapTo(
            wizard.progress_steps,
            QPoint(item.width(), 0),
        ).x()
        assert item_right <= wizard.progress_steps.width()
    wizard.project_overview_editor.project_description_edit.setPlainText("First paint smoke.")
    wizard.flush_pending_edits()
    next_button = wizard.findChild(QPushButton, "setup_wizard_next_button")
    back_button = wizard.findChild(QPushButton, "setup_wizard_back_button")
    assert next_button is not None
    assert back_button is not None
    qtbot.mouseClick(next_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(back_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert [label.text() for label in wizard.progress_step_labels] == initial_progress_labels
    _assert_balanced_setup_stepper(wizard)
    label_text = "\n".join(label.text() for label in wizard.findChildren(QLabel))
    assert "Current Step" not in label_text
    assert "Only the controls needed for this setup step are shown." not in label_text
    for step_key in (
        "project",
        "conditions",
        "experiment",
        "fixation",
        "response",
        "review",
    ):
        wizard.open_wizard(step_key=step_key)
        QApplication.processEvents()
        _assert_setup_wizard_vertical_scrolling_disabled(wizard)
        _assert_visible_children_within_parent(wizard.step_stack.currentWidget())
        assert not wizard.step_status_badge.isVisible()
    wizard.open_wizard(step_key="project")
    QApplication.processEvents()
    assert "Complete each setup step once" not in label_text
    assert "Setup Wizard uses the same project document" not in label_text
    assert "Beta: test-mode runtime path only" not in label_text
    assert "Confirm the project name and template." not in label_text
    assert wizard.shell.footer_strip.isVisible() is False
    assert wizard.step_title_label.isVisible() is False
    assert wizard.step_status_badge.isVisible() is False
    assert wizard.property("launchSurfaceRoot") == "true"
    assert wizard.step_card.property("launchSurfaceFrame") == "true"
    assert wizard.step_card.property("sectionCard") == "false"
    assert wizard.step_card.property("wizardProjectStepFrame") == "false"
    assert 'QFrame[launchSurfaceFrame="true"]' in wizard.styleSheet()
    assert "QFrame#non_home_shell_content_frame" in wizard.styleSheet()
    assert "QWidget#page_container_scroll_content" in wizard.styleSheet()
    assert wizard.step_card.isAncestorOf(wizard.progress_panel_shell)
    assert wizard.step_card.isAncestorOf(wizard.step_content_anchor)
    assert wizard.step_content_anchor.isAncestorOf(wizard.content_stack)
    assert wizard.step_card.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    assert wizard.step_card.maximumHeight() <= 552
    assert wizard.progress_panel_shell.sizePolicy().verticalPolicy() == (
        QSizePolicy.Policy.Fixed
    )
    progress_top = wizard.progress_panel_shell.mapTo(
        wizard.step_card,
        wizard.progress_panel_shell.rect().topLeft(),
    ).y()
    assert progress_top <= 12
    assert window.conditions_page.shell is None
    assert window.assets_page.shell.footer_strip.isVisible() is False
    assert window.run_page.shell.footer_strip.isVisible() is False


def test_setup_wizard_compact_steps_do_not_clip_visible_content(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Setup No Clip")
    wizard = window.setup_wizard_page
    window.resize(1120, 720)
    window.show_setup_wizard()
    QApplication.processEvents()

    frame_heights: list[int] = []
    frame_tops: list[int] = []
    progress_tops: list[int] = []
    back_button_lefts: list[int] = []
    for step_key in (
        "project",
        "conditions",
        "experiment",
        "fixation",
        "response",
        "review",
    ):
        wizard.open_wizard(step_key=step_key)
        QApplication.processEvents()
        _assert_setup_wizard_vertical_scrolling_disabled(wizard)
        assert wizard.shell.page_container.scroll_area.verticalScrollBar().maximum() == 0
        _assert_visible_children_within_parent(wizard.step_stack.currentWidget())

        frame_heights.append(wizard.step_card.height())
        frame_tops.append(wizard.step_card.mapTo(wizard, wizard.step_card.rect().topLeft()).y())
        progress_tops.append(
            wizard.progress_panel_shell.mapTo(
                wizard.step_card,
                wizard.progress_panel_shell.rect().topLeft(),
            ).y()
        )
        back_button_lefts.append(
            wizard.setup_wizard_back_button.mapTo(
                wizard,
                wizard.setup_wizard_back_button.rect().topLeft(),
            ).x()
        )
        assert wizard.step_stack.currentWidget().height() <= wizard.content_stack.height()

        for button in (
            wizard.setup_wizard_back_button,
            wizard.setup_wizard_next_button,
            wizard.setup_wizard_return_home_button,
        ):
            if button.isVisible():
                bottom = button.mapTo(wizard, button.rect().bottomLeft()).y()
                assert bottom <= wizard.height()

    assert len(set(frame_heights)) == 1
    assert len(set(frame_tops)) == 1
    assert len(set(progress_tops)) == 1
    assert len(set(back_button_lefts)) == 1
    assert progress_tops[0] <= 12


def test_major_tabs_share_page_container_width_presets(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Shared Page Container")

    assert not hasattr(window.home_page, "page_container")
    assert window.home_page.launch_surface.page_layout.contentsMargins().left() == 32
    assert window.home_page.launch_surface.content_layout.contentsMargins().left() == 44
    assert window.home_page.launch_surface.hero_container.maximumWidth() == 760
    assert window.home_page.launch_surface.property("launchSurfaceRoot") == "true"
    assert 'QWidget[launchSurfaceRoot="true"]' in window.home_page.styleSheet()
    assert window.setup_wizard_page.shell.page_container.width_preset == "full"
    assert window.setup_wizard_page.shell.page_container.max_content_width() == 16_777_215
    assert window.setup_wizard_page.property("launchSurfaceRoot") == "true"
    assert window.setup_wizard_page.step_card.property("launchSurfaceFrame") == "true"
    assert window.setup_wizard_page.step_card.sizePolicy().verticalPolicy() == (
        QSizePolicy.Policy.Expanding
    )
    assert window.setup_wizard_page.step_card.isAncestorOf(
        window.setup_wizard_page.progress_panel_shell
    )
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
    home_hero_container = window.home_page.findChild(QWidget, "home_hero_container")
    assert home_launch_panel is not None
    assert home_hero_container is not None
    assert (
        window.home_page.current_project_header.parentWidget().parentWidget()
        is home_hero_container
    )
    assert (
        window.home_page.current_project_subtitle.parentWidget().parentWidget()
        is home_hero_container
    )
    assert window.home_page.current_project_header.alignment() & Qt.AlignmentFlag.AlignLeft
    assert window.home_page.current_project_subtitle.alignment() & Qt.AlignmentFlag.AlignLeft
    assert window.setup_wizard_page.shell.title_label.alignment() & Qt.AlignmentFlag.AlignCenter
    assert window.conditions_page.embedded is True
    assert window.assets_page.shell.title_label.alignment() & Qt.AlignmentFlag.AlignCenter


def test_home_launch_card_is_centered_in_page_viewport(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Home Centered Card")
    _prepare_compile_ready_project(window, tmp_path)
    window.main_stack.setCurrentWidget(window.home_page)
    window.home_page.refresh()
    QApplication.processEvents()

    launch_panel = window.home_page.findChild(QWidget, "home_launch_panel")
    summary_label = window.home_page.findChild(QLabel, "home_launch_status_summary")

    assert launch_panel is not None
    assert summary_label is not None
    assert launch_panel.property("launchSurfaceFrame") == "true"
    assert 'QFrame[launchSurfaceFrame="true"]' in window.home_page.styleSheet()
    qtbot.waitUntil(lambda: launch_panel.width() > 0 and window.home_page.width() > 0)

    panel_center = launch_panel.mapTo(
        window.home_page,
        QPoint(launch_panel.width() // 2, launch_panel.height() // 2),
    )
    assert abs(panel_center.x() - (window.home_page.width() / 2)) < 20
    assert abs(panel_center.y() - (window.home_page.height() / 2)) < 35
    assert summary_label.text() == ""
    assert not summary_label.isVisible()


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
    _, window = _open_created_project(controller, qtbot, tmp_path, "Workflow Window Size")

    assert window.main_stack.currentWidget() is window.home_page
    assert window.objectName() == "studio_main_window"
    assert "QMainWindow#studio_main_window" in window.styleSheet()
    assert "QStackedWidget#main_stack" in window.styleSheet()
    assert f"background-color: {COLOR_PAGE_BACKGROUND};" in window.styleSheet()
    assert window.menuBar().isVisible()
    assert not window.statusBar().isVisible()
    assert window.minimumWidth() == 760
    assert window.minimumHeight() == 520
    assert window.width() == 1120
    assert window.height() == 720

    window.show_setup_wizard()
    QApplication.processEvents()

    assert window.main_stack.currentWidget() is window.setup_wizard_page
    assert window.menuBar().isVisible()
    assert window.statusBar().isVisible()
    assert window.minimumWidth() == 960
    assert window.minimumHeight() == 640
    assert window.width() == 1120
    assert window.height() == 720

    window.show_home()
    QApplication.processEvents()

    assert window.main_stack.currentWidget() is window.home_page
    assert window.menuBar().isVisible()
    assert not window.statusBar().isVisible()
    menu_height = window.menuBar().height() or window.menuBar().sizeHint().height()
    assert window.home_page.launch_surface.page_layout.contentsMargins().top() == max(
        0,
        32 - menu_height,
    )
    assert window.minimumWidth() == 760
    assert window.minimumHeight() == 520
    assert window.width() == 1120
    assert window.height() == 720

    window.resize(1110, 700)
    QApplication.processEvents()
    compact_home_size = window.size()

    window.show_setup_wizard()
    QApplication.processEvents()

    assert window.main_stack.currentWidget() is window.setup_wizard_page
    assert window.menuBar().isVisible()
    assert window.statusBar().isVisible()
    assert window.minimumWidth() == 960
    assert window.minimumHeight() == 640
    assert window.width() == 1110
    assert window.height() == 700

    window.show_home()
    QApplication.processEvents()

    assert window.main_stack.currentWidget() is window.home_page
    assert window.menuBar().isVisible()
    assert not window.statusBar().isVisible()
    assert window.minimumWidth() == 760
    assert window.minimumHeight() == 520
    assert window.size() == compact_home_size

    window.show_setup_wizard()
    QApplication.processEvents()

    window.resize(1500, 950)
    window.show_home()
    QApplication.processEvents()

    assert window.main_stack.currentWidget() is window.home_page
    assert window.menuBar().isVisible()
    assert not window.statusBar().isVisible()
    assert window.minimumWidth() == 760
    assert window.minimumHeight() == 520
    assert window.width() == 1500
    assert window.height() == 950


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

    window.main_stack.setCurrentWidget(window.home_page)
    QApplication.processEvents()
    launch_panel = window.home_page.findChild(QWidget, "home_launch_panel")
    assert launch_panel is not None
    assert launch_panel.height() <= window.home_page.height()
    assert launch_panel.width() <= window.home_page.width()

    window.main_stack.setCurrentWidget(window.setup_wizard_page)
    QApplication.processEvents()
    setup_scroll_area = window.setup_wizard_page.shell.page_container.scroll_area
    qtbot.waitUntil(lambda: setup_scroll_area.verticalScrollBar().maximum() <= 0)
    assert setup_scroll_area.verticalScrollBar().maximum() == 0
    _assert_setup_wizard_vertical_scrolling_disabled(window.setup_wizard_page)


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
    assert not hasattr(conditions_page, "duty_cycle_combo")
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


def test_setup_wizard_stepper_is_passive_during_first_time_setup(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Initial Stepper Project")
    guide = window.setup_wizard_page
    window.show_setup_wizard()
    QApplication.processEvents()

    qtbot.mouseClick(guide.progress_steps.step_circles[3], Qt.MouseButton.LeftButton)

    assert guide.step_stack.currentWidget() is guide.project_step_surface


def test_edit_setup_stepper_can_jump_to_any_step(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Editable Stepper Project")
    _prepare_compile_ready_project(window, tmp_path / "editable-stepper-assets")
    assert window.save_project() is True

    controller.open_project(window.document.project_root)
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)
    reopened = controller.main_window
    assert reopened.main_stack.currentWidget() is reopened.home_page

    edit_setup_button = reopened.home_page.findChild(QPushButton, "home_edit_setup_button")
    assert edit_setup_button is not None
    qtbot.mouseClick(edit_setup_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    guide = reopened.setup_wizard_page
    qtbot.mouseClick(guide.progress_steps.step_circles[4], Qt.MouseButton.LeftButton)
    assert guide.step_stack.currentWidget() is guide.response_step_surface

    qtbot.mouseClick(guide.progress_steps.step_circles[1], Qt.MouseButton.LeftButton)
    assert guide.step_stack.currentWidget() is guide.conditions_step_surface


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
