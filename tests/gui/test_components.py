"""Smoke tests for shared GUI component helpers."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton

from fpvs_studio.gui.components import (
    SectionCard,
    SetupChecklistPanel,
    SetupMetricStrip,
    SetupProgressStepper,
    SetupSidePanel,
    SetupSourceCard,
    SetupWorkspaceFrame,
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


def test_setup_checklist_panel_renders_status_rows(qtbot) -> None:
    checklist = SetupChecklistPanel("Setup Checklist")
    qtbot.addWidget(checklist)

    checklist.set_items([("Name", True, "Complete"), ("Images", False, "Missing")])

    item_text = [label.text() for label in checklist.item_labels()]
    status_text = [label.text() for label in checklist.status_labels()]
    assert item_text == ["\u2713 Name", "\u2715 Images"]
    assert status_text == ["Complete", "Missing"]
    assert checklist.item_labels()[0].property("setupChecklistState") == "complete"
    assert checklist.status_labels()[1].property("setupChecklistState") == "incomplete"


def test_setup_workspace_and_summary_components_construct(qtbot) -> None:
    left = QLabel("Left")
    main = QLabel("Main")
    right = QLabel("Right")
    workspace = SetupWorkspaceFrame()
    workspace.set_regions(left=left, main=main, right=right)
    side_panel = SetupSidePanel("Protocol Defaults")
    side_panel.set_rows([("Image Version:", "Original")])
    metric_strip = SetupMetricStrip()
    metric_strip.set_rows([("Base Rate", "6.0 Hz")])
    source_card = SetupSourceCard("Base Images", "Choose Base Images...")
    source_card.set_source_state(
        ready=True,
        folder="stimuli/source/condition-1-base/originals",
        image_count="16 images",
        resolution="512 x 512",
        variants="original",
    )
    for widget in (workspace, side_panel, metric_strip, source_card):
        qtbot.addWidget(widget)

    assert workspace.property("setupWorkspaceFrame") == "true"
    assert side_panel.property("setupSidePanel") == "true"
    assert metric_strip.property("setupMetricStrip") == "true"
    assert source_card.property("setupSourceCard") == "true"
    assert source_card.status_badge.text() == "Ready"


def test_theme_stylesheet_builders_expose_expected_selectors(qapp) -> None:
    assert "QTabWidget#main_tabs::pane" in studio_theme_stylesheet()
    assert "QWidget#home_page" in home_page_stylesheet()
    assert "QFrame#fixation_feasibility_card" in fixation_settings_stylesheet()
    assert 'QFrame[sectionCard="true"]' in section_card_stylesheet()
    assert "QFrame#welcome_content_frame" in welcome_window_stylesheet(qapp.palette())
    assert "setupProgressStepper" in studio_theme_stylesheet()
    assert "setup_wizard_status_strip" in studio_theme_stylesheet()
    assert "#a1332b" in error_text_stylesheet()
    assert "text-decoration: underline" in condition_template_details_header_stylesheet()
