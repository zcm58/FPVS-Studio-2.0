"""Smoke tests for shared GUI component helpers."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
)
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.gui.components import (
    SectionCard,
    SetupMetricStrip,
    SetupProgressStepper,
    SetupSourceCard,
    apply_dialog_theme,
    condition_template_details_header_stylesheet,
    error_text_stylesheet,
    fixation_settings_stylesheet,
    form_controls_stylesheet,
    home_page_stylesheet,
    image_size_preview_dialog_stylesheet,
    mark_error_text,
    mark_launch_action,
    mark_primary_action,
    mark_secondary_action,
    mark_welcome_action,
    section_card_stylesheet,
    setup_wizard_stylesheet,
    studio_theme_stylesheet,
    welcome_window_stylesheet,
)
from fpvs_studio.gui.design_system import (
    DARK_STUDIO_THEME,
    LIGHT_STUDIO_THEME,
    StudioColorScheme,
    contrast_ratio,
    resolve_studio_theme,
)


def _palette_with_window_color(window_color: str) -> QPalette:
    palette = QPalette()
    color = QColor(window_color)
    palette.setColor(QPalette.ColorRole.Window, color)
    palette.setColor(QPalette.ColorRole.Base, color)
    palette.setColor(QPalette.ColorRole.Button, color)
    text_color = QColor("#f3f6fb" if color.lightness() < 128 else "#1f2f44")
    palette.setColor(QPalette.ColorRole.Text, text_color)
    palette.setColor(
        QPalette.ColorRole.WindowText,
        text_color,
    )
    return palette


def test_action_role_helpers_mark_expected_properties(qtbot) -> None:
    primary_button = QPushButton("Primary")
    secondary_button = QPushButton("Secondary")
    launch_button = QPushButton("Launch")
    welcome_button = QPushButton("Welcome")
    for button in (primary_button, secondary_button, launch_button, welcome_button):
        qtbot.addWidget(button)

    mark_primary_action(primary_button)
    mark_secondary_action(secondary_button)
    mark_launch_action(launch_button, home=True)
    mark_welcome_action(welcome_button, "primary")

    assert primary_button.property("primaryActionRole") == "true"
    assert secondary_button.property("secondaryActionRole") == "true"
    assert launch_button.property("launchActionRole") == "primary"
    assert launch_button.property("primaryActionRole") == "true"
    assert launch_button.property("homeActionRole") == "primary"
    assert welcome_button.property("welcomeRole") == "primary"


def test_error_text_helper_marks_and_styles_label(qtbot) -> None:
    label = QLabel("Invalid")
    qtbot.addWidget(label)

    mark_error_text(label)

    assert label.property("errorText") == "true"
    assert resolve_studio_theme(label.palette()).error_text in label.styleSheet()


def test_public_section_card_reexport_constructs(qtbot) -> None:
    card = SectionCard(title="Reusable", subtitle="Shared card")
    qtbot.addWidget(card)

    assert card.property("sectionCard") == "true"
    assert card.title_label.text() == "Reusable"


def test_setup_progress_stepper_marks_step_states(qtbot) -> None:
    stepper = SetupProgressStepper(["Project Details", "Conditions", "Review"])
    qtbot.addWidget(stepper)

    stepper.set_active_index(1)

    assert stepper.objectName() == "setup_wizard_progress_steps"
    assert stepper.step_items[0].objectName() == "setup_wizard_step_1_project_details"
    assert stepper.step_items[0].property("setupProgressState") == "complete"
    assert stepper.step_items[1].property("setupProgressState") == "current"
    assert stepper.step_items[2].property("setupProgressState") == "upcoming"
    assert stepper.step_circles[0].text() == "\u2713"
    assert stepper.step_circles[1].text() == "2"


def test_setup_progress_stepper_emits_clicks_only_when_navigation_enabled(qtbot) -> None:
    stepper = SetupProgressStepper(["Project", "Conditions", "Review"])
    qtbot.addWidget(stepper)
    requested: list[int] = []
    stepper.step_requested.connect(requested.append)

    qtbot.mouseClick(stepper.step_circles[2], Qt.MouseButton.LeftButton)
    assert requested == []

    stepper.set_navigation_enabled(True)
    qtbot.mouseClick(stepper.step_circles[2], Qt.MouseButton.LeftButton)
    assert requested == [2]


def test_setup_summary_components_construct(qtbot) -> None:
    metric_strip = SetupMetricStrip()
    metric_strip.set_rows([("Base Rate", "6.0 Hz")])
    source_card = SetupSourceCard("Base Images", "Choose Base Images...")
    source_card.set_source_state(
        ready=True,
        folder="stimuli/original-images/condition-1-base",
        image_count="16 images",
        resolution="512 x 512",
        variants="original",
    )
    for widget in (metric_strip, source_card):
        qtbot.addWidget(widget)

    assert metric_strip.property("setupMetricStrip") == "true"
    assert source_card.property("setupSourceCard") == "true"
    assert source_card.status_badge.text() == "Ready"


def test_theme_stylesheet_builders_expose_expected_selectors(qapp) -> None:
    assert "QStackedWidget#main_stack" in studio_theme_stylesheet()
    assert "QWidget#home_page" in home_page_stylesheet(qapp.palette())
    assert 'QWidget[launchSurfaceRoot="true"]' in home_page_stylesheet(qapp.palette())
    assert "QFrame#fixation_feasibility_card" in fixation_settings_stylesheet()
    assert 'QFrame[sectionCard="true"]' in section_card_stylesheet()
    assert 'QFrame[launchSurfaceFrame="true"]' in welcome_window_stylesheet(qapp.palette())
    assert "setupProgressStepper" in studio_theme_stylesheet()
    assert "QDialog#image_size_preview_dialog" in image_size_preview_dialog_stylesheet()
    assert resolve_studio_theme().error_text in error_text_stylesheet()
    assert "text-decoration: underline" in condition_template_details_header_stylesheet()


def test_theme_resolver_maps_light_and_dark_palettes(qapp) -> None:
    assert resolve_studio_theme(_palette_with_window_color("#f4f7fb")).scheme is (
        StudioColorScheme.LIGHT
    )
    assert resolve_studio_theme(_palette_with_window_color("#202124")).scheme is (
        StudioColorScheme.DARK
    )


def test_studio_themes_keep_accessible_text_contrast(qapp) -> None:
    for theme in (LIGHT_STUDIO_THEME, DARK_STUDIO_THEME):
        assert contrast_ratio(theme.text_primary, theme.page_background) >= 4.5
        assert contrast_ratio(theme.text_primary, theme.surface_elevated) >= 4.5
        assert contrast_ratio(theme.text_secondary, theme.surface_elevated) >= 4.5
        assert contrast_ratio(theme.selected_text, theme.primary) >= 4.5
        assert contrast_ratio(theme.error_text, theme.page_background) >= 4.5
        assert contrast_ratio(theme.error_text, theme.surface_elevated) >= 4.5
        assert theme.error_text in error_text_stylesheet(theme)


def test_dark_theme_stylesheets_use_dark_tokens(qapp) -> None:
    dark_palette = _palette_with_window_color("#202124")
    dark_theme = resolve_studio_theme(dark_palette)

    assert "background-color: #ffffff;" not in home_page_stylesheet(dark_palette)
    assert f"background-color: {dark_theme.page_background};" in home_page_stylesheet(
        dark_palette
    )
    assert f"background-color: {dark_theme.surface};" in welcome_window_stylesheet(
        dark_palette
    )
    assert f"background-color: {dark_theme.surface_elevated};" in section_card_stylesheet(
        dark_palette
    )
    assert f"color: {dark_theme.text_primary};" in setup_wizard_stylesheet(dark_palette)


def test_error_label_follows_palette_changes(qtbot) -> None:
    label = QLabel("Choose a source folder before continuing.")
    qtbot.addWidget(label)
    label.setPalette(_palette_with_window_color("#f4f7fb"))
    mark_error_text(label)
    assert LIGHT_STUDIO_THEME.error_text in label.styleSheet()

    label.setPalette(_palette_with_window_color("#202124"))
    QApplication.processEvents()
    assert DARK_STUDIO_THEME.error_text in label.styleSheet()


def test_form_styles_preserve_native_arrow_subcontrols(qapp) -> None:
    stylesheet = form_controls_stylesheet()
    assert "QComboBox:focus" in stylesheet
    assert "QAbstractSpinBox:disabled" in stylesheet
    assert "QAbstractSpinBox QLineEdit" in stylesheet
    for subcontrol in ("::down-arrow", "::up-arrow", "::up-button", "::down-button"):
        assert subcontrol not in stylesheet


def test_shared_fields_keep_keyboard_editing_and_selection(qtbot) -> None:
    dialog = QDialog()
    qtbot.addWidget(dialog)
    layout = QFormLayout(dialog)
    name = QLineEdit("Condition", dialog)
    combo = QComboBox(dialog)
    combo.addItems(["Continuous images", "Contrast modulation"])
    repeats = QSpinBox(dialog)
    repeats.setValue(3)
    layout.addRow("Name", name)
    layout.addRow("Presentation", combo)
    layout.addRow("Repeats", repeats)
    apply_dialog_theme(dialog)
    dialog.resize(420, 200)
    dialog.show()
    name.setFocus()
    name.selectAll()
    qtbot.keyClicks(name, "Renamed condition")
    combo.setFocus()
    qtbot.keyClick(combo, Qt.Key.Key_Down)
    repeats.setFocus()
    qtbot.keyClick(repeats, Qt.Key.Key_Up)
    QApplication.processEvents()

    assert name.text() == "Renamed condition"
    assert combo.currentText() == "Contrast modulation"
    assert repeats.value() == 4
    assert_visible_children_within_parent(dialog)


def test_eight_setup_steps_show_complete_labels_at_compact_width(qtbot) -> None:
    titles = [
        "Project", "Conditions", "Timing", "Image Size", "Session",
        "Fixation", "Response", "Review",
    ]
    stepper = SetupProgressStepper(titles)
    qtbot.addWidget(stepper)
    stepper.resize(1040, stepper.minimumHeight())
    stepper.show()
    QApplication.processEvents()

    assert_visible_children_within_parent(stepper)
    assert [label.text() for label in stepper.step_labels] == titles
    for label in stepper.step_labels:
        assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())


def test_source_details_exposes_and_copies_full_long_path(qtbot) -> None:
    source = SetupSourceCard("Base images", "Choose images", show_details=True)
    qtbot.addWidget(source)
    assert not source.source_details_button.isEnabled()
    path = "C:/Research/" + "Long source folder for stimulus inspection/" * 8
    source.set_source_details(path)
    source.show()
    qtbot.mouseClick(source.source_details_button, Qt.MouseButton.LeftButton)
    dialog = source.findChild(QDialog, "setup_source_card_source_details_dialog")
    assert dialog is not None
    QApplication.processEvents()
    assert not dialog.isModal()
    assert_visible_children_within_parent(dialog)
    path_text = dialog.findChild(QTextEdit, "source_details_path")
    assert path_text is not None
    assert path_text.toPlainText() == path
    copy_button = dialog.findChild(QPushButton, "source_details_copy_path")
    assert copy_button is not None
    qtbot.mouseClick(copy_button, Qt.MouseButton.LeftButton)
    assert QApplication.clipboard().text() == path
    replacement_path = "C:/Research/Another condition/oddball images"
    source.set_source_details(replacement_path)
    assert path_text.toPlainText() == replacement_path
    qtbot.mouseClick(copy_button, Qt.MouseButton.LeftButton)
    assert QApplication.clipboard().text() == replacement_path
    qtbot.mouseClick(source.source_details_button, Qt.MouseButton.LeftButton)
    assert source.findChild(QDialog, "setup_source_card_source_details_dialog") is dialog
    source.set_source_details("")
    assert not source.source_details_button.isEnabled()
    assert not dialog.isVisible()
