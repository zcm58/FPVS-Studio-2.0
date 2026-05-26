"""Focused GUI workflow tests split from the former layout dashboard suite."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import (
    QPoint,
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QLabel,
    QPushButton,
    QWidget,
)
from tests.gui.helpers import (
    _assert_balanced_setup_stepper,
    _assert_setup_wizard_vertical_scrolling_disabled,
    _open_created_project,
)

from fpvs_studio.gui.controller import StudioController


def test_setup_wizard_experiment_and_fixation_steps_are_width_safe(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Experiment Settings Guided")
    guide = window.setup_wizard_page
    window.show_setup_wizard(step_key="experiment")

    assert guide.content_stack.currentWidget() is guide.guided_panel
    assert guide.step_stack.currentWidget() is guide.experiment_step_surface
    assert guide.experiment_step_surface.content.objectName() == (
        "setup_wizard_experiment_settings_page"
    )
    assert guide.findChild(QPushButton, "setup_wizard_advanced_button") is None
    _assert_setup_wizard_vertical_scrolling_disabled(guide)
    assert guide.runtime_settings_editor.refresh_hz_spin is not None
    assert guide.image_display_size_editor.width_degrees_spin is not None
    assert guide.session_structure_editor.block_count_spin is not None
    assert guide.fixation_settings_editor is not guide.step_stack.currentWidget()
    assert guide.runtime_settings_editor.card is None
    assert guide.session_structure_editor.session_card is None
    assert guide.experiment_settings_card.objectName() == "setup_wizard_experiment_settings_card"
    assert guide.experiment_settings_card.maximumWidth() == 880
    assert guide.experiment_settings_card.minimumHeight() == 280
    assert guide.experiment_settings_card.findChild(
        QLabel,
        "setup_wizard_experiment_settings_card_title",
    ) is None
    assert guide.session_structure_editor.block_count_spin.value() == 2
    show_title_checkbox = guide.session_structure_editor.findChild(
        QCheckBox,
        "show_condition_title_checkbox",
    )
    assert show_title_checkbox is not None
    assert show_title_checkbox.text() == "Show condition title on experiment screen"
    assert show_title_checkbox.isChecked() is True
    show_title_checkbox.setChecked(False)
    assert (
        window.document.project.settings.session.show_condition_title_on_screen
        is False
    )
    assert not guide.session_structure_editor.generate_seed_button.isVisible()
    assert not guide.session_structure_editor.session_seed_spin.isVisible()
    assert not guide.session_structure_editor.seed_row_widget.isVisible()
    assert guide.session_structure_editor.session_layout.horizontalSpacing() == 12
    assert guide.session_structure_editor.session_layout.verticalSpacing() == 10
    assert not guide.runtime_settings_editor.runtime_background_scope_label.isVisible()
    experiment_labels = "\n".join(
        label.text() for label in guide.experiment_settings_card.findChildren(QLabel)
    )
    assert "Display refresh rate" in experiment_labels
    assert "Image Size" in experiment_labels
    assert "Image width" in experiment_labels
    assert "Viewing distance" in experiment_labels
    assert "Screen width" in experiment_labels
    assert "Repeats per condition" in experiment_labels
    assert "Condition order" in experiment_labels
    assert "randomized automatically" in experiment_labels
    assert "Experiment Settings" not in experiment_labels
    assert "Block count" not in experiment_labels
    assert "Random order seed" not in experiment_labels
    assert "New Seed" not in experiment_labels
    assert "Used during FPVS image presentation." not in experiment_labels
    assert len(
        [
            widget
            for widget in guide.experiment_settings_card.findChildren(QWidget)
            if widget.property("experimentSettingsSection") == "true"
        ]
    ) == 3
    for section in guide.experiment_settings_card.findChildren(QWidget):
        if section.property("experimentSettingsSection") == "true":
            assert section.minimumHeight() == 224
    assert window.minimumWidth() == 960
    assert window.minimumHeight() == 640

    for width, height in ((1120, 720), (1180, 760)):
        window.resize(width, height)
        QApplication.processEvents()
        experiment_page = guide.experiment_step_surface
        experiment_card = guide.experiment_settings_card
        display_panel = guide.runtime_settings_editor
        image_size_panel = guide.image_display_size_editor
        session_panel = guide.session_structure_editor
        assert guide.shell.page_container.scroll_area.horizontalScrollBar().maximum() == 0
        _assert_setup_wizard_vertical_scrolling_disabled(guide)
        _assert_balanced_setup_stepper(guide)
        card_left = experiment_card.mapTo(experiment_page, QPoint(0, 0)).x()
        card_right = experiment_card.mapTo(
            experiment_page,
            QPoint(experiment_card.width(), 0),
        ).x()
        display_right = display_panel.mapTo(
            experiment_card,
            QPoint(display_panel.width(), 0),
        ).x()
        image_size_left = image_size_panel.mapTo(experiment_card, QPoint(0, 0)).x()
        image_size_right = image_size_panel.mapTo(
            experiment_card,
            QPoint(image_size_panel.width(), 0),
        ).x()
        session_left = session_panel.mapTo(experiment_card, QPoint(0, 0)).x()
        session_right = session_panel.mapTo(
            experiment_card,
            QPoint(session_panel.width(), 0),
        ).x()
        assert card_left >= 0
        assert card_right <= experiment_page.width()
        assert experiment_card.width() <= 880
        assert display_right <= image_size_left
        assert image_size_right <= session_left
        assert session_right <= experiment_card.width()

        review_item = guide.progress_steps.step_items[-1]
        review_right = review_item.mapTo(
            guide.progress_steps,
            QPoint(review_item.width(), 0),
        ).x()
        assert review_right <= guide.progress_steps.width()

    window.resize(1120, 720)
    QApplication.processEvents()
    assert guide.shell.page_container.scroll_area.verticalScrollBar().maximum() == 0


def test_setup_wizard_experiment_image_size_controls_update_preview_and_review(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Image Size Guided")
    guide = window.setup_wizard_page
    window.main_stack.setCurrentWidget(guide)
    guide.open_wizard(step_key="experiment")
    editor = guide.image_display_size_editor
    preview_captures: dict[str, object] = {}

    class _FakePreviewDialog:
        def __init__(self, document, parent=None) -> None:
            preview_captures["document"] = document
            preview_captures["parent"] = parent

        def setGeometry(self, geometry) -> None:  # noqa: N802
            preview_captures["geometry"] = geometry

        def windowState(self):  # noqa: N802
            return Qt.WindowState.WindowNoState

        def setWindowState(self, state) -> None:  # noqa: N802
            preview_captures["state"] = state

        def exec(self) -> int:
            preview_captures["exec_count"] = int(preview_captures.get("exec_count", 0)) + 1
            return 1

    monkeypatch.setattr(
        "fpvs_studio.gui.runtime_settings_page.ImageSizePreviewDialog",
        _FakePreviewDialog,
    )

    assert editor.width_degrees_spin.value() == pytest.approx(5.0, abs=0.01)
    assert editor.viewing_distance_spin.value() == pytest.approx(57.0, abs=0.01)
    assert editor.screen_width_spin.value() == pytest.approx(56.25, abs=0.01)
    image_size_labels = "\n".join(label.text() for label in editor.findChildren(QLabel))
    assert "Image width (deg)" in image_size_labels
    assert "Viewing distance (cm)" in image_size_labels
    assert "Screen width (cm)" in image_size_labels
    assert "Resolution width (px)" in image_size_labels
    assert "Resolution height (px)" in image_size_labels
    original_preview_text = editor.preview_value_label.text()

    editor.width_degrees_spin.setValue(6.5)
    editor.viewing_distance_spin.setValue(75.0)
    editor.screen_width_spin.setValue(60.0)
    editor.screen_width_px_spin.setValue(1920)
    editor.screen_height_px_spin.setValue(1080)
    QApplication.processEvents()

    display = window.document.project.settings.display
    assert display.stimulus_width_degrees == pytest.approx(6.5, abs=0.01)
    assert display.viewing_distance_cm == pytest.approx(75.0, abs=0.01)
    assert display.screen_width_cm == pytest.approx(60.0, abs=0.01)
    assert display.screen_width_px == 1920
    assert display.screen_height_px == 1080
    assert display.use_current_screen_resolution is False
    assert editor.preview_value_label.text() != original_preview_text
    assert "cm wide" in editor.preview_value_label.text()
    assert "1920 px-wide display" in editor.preview_value_label.text()
    editor.full_screen_preview_button.click()
    assert preview_captures["document"] is window.document
    assert preview_captures["parent"] is editor
    assert preview_captures["exec_count"] == 1
    assert preview_captures["state"] & Qt.WindowState.WindowFullScreen

    guide.open_wizard(step_key="review")
    review_text = "\n".join(label.text() for label in guide.review_card.findChildren(QLabel))
    assert "Image width: 6.5 deg at 75 cm on 1920 x 1080" in review_text
    next_bottom = guide.setup_wizard_next_button.mapTo(
        guide,
        QPoint(0, guide.setup_wizard_next_button.height()),
    ).y()
    back_bottom = guide.setup_wizard_back_button.mapTo(
        guide,
        QPoint(0, guide.setup_wizard_back_button.height()),
    ).y()
    assert next_bottom <= guide.height()
    assert back_bottom <= guide.height()

    guide.open_wizard(step_key="fixation")
    assert guide.step_stack.currentWidget() is guide.fixation_step_surface
    assert guide.fixation_step_surface.content is guide.fixation_schedule_editor
    assert guide.findChild(QPushButton, "setup_wizard_advanced_button") is None
    _assert_setup_wizard_vertical_scrolling_disabled(guide)
    assert not guide.step_title_label.isVisible()
    assert not guide.step_status_badge.isVisible()
    assert guide.step_card.property("launchSurfaceFrame") == "true"
    assert guide.step_card.property("wizardProjectStepFrame") == "false"
    assert not hasattr(guide.fixation_schedule_editor.fixation_panel, "title_label")
    assert guide.fixation_schedule_editor.fixation_panel.objectName() == "fixation_settings_panel"
    assert not guide.fixation_schedule_editor.fixation_enabled_checkbox.isVisible()
    assert not guide.fixation_schedule_editor.fixation_accuracy_checkbox.isVisible()
    assert guide.fixation_schedule_editor.preview_card is None
    assert guide.fixation_schedule_editor.preview_panel is None
    guide.fixation_schedule_editor.fixation_enabled_checkbox.setChecked(True)
    QApplication.processEvents()
    feasibility_card = guide.fixation_schedule_editor.findChild(
        QWidget,
        "fixation_feasibility_card",
    )
    assert feasibility_card is not None
    assert feasibility_card.maximumHeight() == 42
    assert len(
        [
            widget
            for widget in guide.fixation_schedule_editor.findChildren(QWidget)
            if widget.property("fixationSettingsSection") == "true"
            and widget.isVisible()
        ]
    ) == 2
    label_text = "\n".join(
        label.text()
        for label in guide.fixation_schedule_editor.findChildren(QLabel)
        if label.isVisible()
    )
    assert "Fixation Cross" not in label_text
    assert "Behavior" in label_text
    assert "Timing" in label_text
    assert "Response" not in label_text
    assert "Appearance" not in label_text
    assert guide.fixation_schedule_editor.fixation_behavior_panel.minimumHeight() == 210
    assert guide.fixation_schedule_editor.fixation_timing_panel.minimumHeight() == 210

    guide.open_wizard(step_key="response")
    assert guide.step_stack.currentWidget() is guide.response_step_surface
    assert guide.response_step_surface.content is guide.fixation_response_editor
    assert guide.response_step_surface.content.maximumWidth() == 1040
    guide.fixation_response_editor.fixation_accuracy_checkbox.setChecked(True)
    QApplication.processEvents()
    assert not guide.fixation_response_editor.fixation_enabled_checkbox.isVisible()
    assert guide.fixation_response_editor.fixation_accuracy_checkbox.isVisible()
    assert not hasattr(guide.fixation_response_editor.fixation_panel, "title_label")
    assert guide.fixation_response_editor.preview_card is None
    assert guide.fixation_response_editor.preview_panel is not None
    assert guide.fixation_response_editor.preview_widget is not None
    assert guide.fixation_response_editor.preview_panel.maximumHeight() == 220
    assert guide.fixation_response_editor.preview_widget.maximumHeight() == 170
    assert guide.findChild(QWidget, "fixation_cross_preview_card") is None
    assert (
        guide.fixation_response_editor.preview_panel.property("fixationPreviewPanel")
        == "true"
    )
    assert len(
        [
            widget
            for widget in guide.fixation_response_editor.findChildren(QWidget)
            if widget.property("fixationSettingsSection") == "true"
            and widget.isVisible()
        ]
    ) == 2
    label_text = "\n".join(
        label.text()
        for label in guide.fixation_response_editor.findChildren(QLabel)
        if label.isVisible()
    )
    assert "Behavior" not in label_text
    assert "Timing" not in label_text
    assert "Response" in label_text
    assert "Fixation Cross Appearance" in label_text
    assert "Preview" in label_text
    assert "Response and Appearance" not in label_text
    assert "Color-change task, response, and cross appearance." not in label_text
    assert guide.fixation_response_editor.fixation_response_panel.minimumHeight() == 182
    assert guide.fixation_response_editor.fixation_appearance_panel.minimumHeight() == 182
    assert guide.fixation_response_editor.fixation_accuracy_checkbox.parentWidget() is (
        guide.fixation_response_editor.fixation_response_group
    )
    assert (
        guide.fixation_response_editor.findChild(QWidget, "fixation_response_key_row")
        is not None
    )
    section_titles = [
        label
        for label in guide.fixation_response_editor.findChildren(QLabel)
        if label.property("fixationSettingsSectionTitle") == "true" and label.isVisible()
    ]
    assert {label.text() for label in section_titles} == {
        "Response",
        "Fixation Cross Appearance",
    }
    assert all(label.alignment() & Qt.AlignmentFlag.AlignCenter for label in section_titles)
    title_offsets = {
        label.mapTo(label.parentWidget(), QPoint(0, 0)).y() for label in section_titles
    }
    assert len(title_offsets) == 1

    preview = guide.fixation_response_editor.preview_widget
    fixation = window.document.project.settings.fixation_task
    assert fixation.cross_size_px == 27
    assert fixation.line_width_px == 2
    assert preview.preview_state() == (
        "#000000",
        str(fixation.base_color),
        str(fixation.target_color),
        fixation.cross_size_px,
        fixation.line_width_px,
    )
    base_color_combo = guide.fixation_response_editor.base_color_combo
    target_color_combo = guide.fixation_response_editor.target_color_combo
    assert base_color_combo.findData("#0000FF") >= 0
    assert base_color_combo.findData("#FFFFFF") >= 0
    assert target_color_combo.findData("#FF0000") >= 0
    assert base_color_combo.toolTip()
    assert target_color_combo.toolTip()
    base_color_combo.setCurrentIndex(base_color_combo.findData("#FFFFFF"))
    guide.fixation_response_editor.cross_size_spin.setValue(72)
    guide.fixation_response_editor.line_width_spin.setValue(6)
    QApplication.processEvents()
    assert preview.preview_state() == ("#000000", "#FFFFFF", "#FF0000", 72, 6)

    for width, height in ((1120, 720), (1180, 760)):
        window.resize(width, height)
        QApplication.processEvents()
        fixation_page = guide.response_step_surface
        fixation_panel = guide.fixation_response_editor.fixation_panel
        preview_panel = guide.fixation_response_editor.preview_panel
        assert preview_panel is not None
        assert guide.shell.page_container.scroll_area.horizontalScrollBar().maximum() == 0
        fixation_right = fixation_panel.mapTo(
            fixation_page,
            QPoint(fixation_panel.width(), 0),
        ).x()
        preview_right = preview_panel.mapTo(
            fixation_panel,
            QPoint(preview_panel.width(), 0),
        ).x()
        assert fixation_right <= fixation_page.width()
        assert preview_right <= fixation_panel.width()


def test_full_screen_image_size_preview_edits_sync_with_experiment_page(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    from fpvs_studio.gui.runtime_settings_page import ImageSizePreviewDialog

    _, window = _open_created_project(controller, qtbot, tmp_path, "Image Size Preview Edit")
    guide = window.setup_wizard_page
    guide.open_wizard(step_key="experiment")
    editor = guide.image_display_size_editor
    dialog = ImageSizePreviewDialog(window.document, editor)
    qtbot.addWidget(dialog)

    modal_labels = "\n".join(label.text() for label in dialog.findChildren(QLabel))
    assert "Image width (deg)" in modal_labels
    assert "Viewing distance (cm)" in modal_labels
    assert "Screen width (cm)" in modal_labels
    assert "Resolution width (px)" in modal_labels
    assert "Resolution height (px)" in modal_labels
    assert dialog.exit_button.text() == "Exit Preview"
    original_readout = dialog.preview_value_label.text()

    dialog.width_degrees_spin.setValue(10.0)
    dialog.viewing_distance_spin.setValue(100.0)
    dialog.screen_width_spin.setValue(60.0)
    dialog.screen_width_px_spin.setValue(1920)
    dialog.screen_height_px_spin.setValue(1080)
    QApplication.processEvents()

    display = window.document.project.settings.display
    assert display.stimulus_width_degrees == pytest.approx(10.0, abs=0.01)
    assert display.viewing_distance_cm == pytest.approx(100.0, abs=0.01)
    assert display.screen_width_cm == pytest.approx(60.0, abs=0.01)
    assert display.screen_width_px == 1920
    assert display.screen_height_px == 1080
    assert display.use_current_screen_resolution is False
    assert editor.width_degrees_spin.value() == pytest.approx(10.0, abs=0.01)
    assert editor.viewing_distance_spin.value() == pytest.approx(100.0, abs=0.01)
    assert editor.screen_width_spin.value() == pytest.approx(60.0, abs=0.01)
    assert editor.screen_width_px_spin.value() == 1920
    assert editor.screen_height_px_spin.value() == 1080
    assert dialog.preview_value_label.text() != original_readout
    assert "10.0 deg at 100.0 cm" in dialog.preview_value_label.text()
    assert "cm wide" in dialog.preview_value_label.text()

    dialog.use_current_resolution_checkbox.setChecked(True)
    QApplication.processEvents()
    assert window.document.project.settings.display.use_current_screen_resolution is True
    assert not dialog.screen_width_px_spin.isEnabled()
    assert not editor.screen_width_px_spin.isEnabled()
