"""Smoke tests for shared GUI component helpers."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton

from fpvs_studio.gui.components import (
    SectionCard,
    condition_template_details_header_stylesheet,
    error_text_stylesheet,
    fixation_settings_stylesheet,
    home_page_stylesheet,
    mark_error_text,
    mark_launch_action,
    mark_primary_action,
    mark_secondary_action,
    mark_welcome_action,
    section_card_stylesheet,
    studio_theme_stylesheet,
    welcome_window_stylesheet,
)


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
    assert "#a1332b" in label.styleSheet()


def test_public_section_card_reexport_constructs(qtbot) -> None:
    card = SectionCard(title="Reusable", subtitle="Shared card")
    qtbot.addWidget(card)

    assert card.property("sectionCard") == "true"
    assert card.title_label.text() == "Reusable"


def test_theme_stylesheet_builders_expose_expected_selectors(qapp) -> None:
    assert "QTabWidget#main_tabs::pane" in studio_theme_stylesheet()
    assert "QWidget#home_page" in home_page_stylesheet()
    assert "QFrame#fixation_feasibility_card" in fixation_settings_stylesheet()
    assert 'QFrame[sectionCard="true"]' in section_card_stylesheet()
    assert "QFrame#welcome_content_frame" in welcome_window_stylesheet(qapp.palette())
    assert "#a1332b" in error_text_stylesheet()
    assert "text-decoration: underline" in condition_template_details_header_stylesheet()
