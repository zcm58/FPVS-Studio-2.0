"""Validation tests."""

from __future__ import annotations

from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.models import ImageResolution
from fpvs_studio.core.validation import (
    condition_fixation_guidance,
    validate_display_refresh,
    validate_project,
)


def test_refresh_validation_accepts_supported_refresh_rate() -> None:
    report = validate_display_refresh(60.0, duty_cycle_mode=DutyCycleMode.CONTINUOUS)

    assert report.compatible is True
    assert report.frames_per_cycle == 10
    assert report.errors == []


def test_refresh_validation_rejects_non_integer_frame_cycles() -> None:
    report = validate_display_refresh(75.0, duty_cycle_mode=DutyCycleMode.CONTINUOUS)

    assert report.compatible is False
    assert report.frames_per_cycle is None
    assert "incompatible" in report.errors[0]


def test_refresh_validation_rejects_blank_50_on_odd_frame_cycles() -> None:
    report = validate_display_refresh(90.0, duty_cycle_mode=DutyCycleMode.BLANK_50)

    assert report.compatible is False
    assert any("blank_50" in message for message in report.errors)


def test_project_validation_rejects_resolution_mismatch(sample_project) -> None:
    sample_project.stimulus_sets[1].resolution = ImageResolution(width_px=512, height_px=512)

    report = validate_project(sample_project)

    assert report.is_valid is False
    assert any("mismatched resolutions" in issue.message for issue in report.issues)


def test_project_validation_rejects_condition_repeat_mismatch(multi_condition_project) -> None:
    multi_condition_project.conditions[1].sequence_count = 3

    report = validate_project(multi_condition_project)

    assert report.is_valid is False
    assert any(
        "Expected pair from first ordered condition" in issue.message
        and "Condition Repeats=1" in issue.message
        and "Actual pair for condition 'Condition 2'" in issue.message
        and "Condition Repeats=3" in issue.message
        and "Align all conditions before save/run." in issue.message
        for issue in report.issues
    )


def test_project_validation_rejects_condition_cycle_mismatch(multi_condition_project) -> None:
    multi_condition_project.conditions[2].oddball_cycle_repeats_per_sequence = 120

    report = validate_project(multi_condition_project)

    assert report.is_valid is False
    assert any(
        "Expected pair from first ordered condition" in issue.message
        and "Cycles / Condition Repeat=146" in issue.message
        and "Actual pair for condition 'Condition 3'" in issue.message
        and "Cycles / Condition Repeat=120" in issue.message
        for issue in report.issues
    )


def test_project_validation_accepts_uniform_condition_repeat_cycle_settings(
    multi_condition_project,
) -> None:
    multi_condition_project.conditions[0].sequence_count = 2
    multi_condition_project.conditions[1].sequence_count = 2
    multi_condition_project.conditions[2].sequence_count = 2
    multi_condition_project.conditions[3].sequence_count = 2
    multi_condition_project.conditions[0].oddball_cycle_repeats_per_sequence = 99
    multi_condition_project.conditions[1].oddball_cycle_repeats_per_sequence = 99
    multi_condition_project.conditions[2].oddball_cycle_repeats_per_sequence = 99
    multi_condition_project.conditions[3].oddball_cycle_repeats_per_sequence = 99

    report = validate_project(multi_condition_project)

    assert report.is_valid is True
    assert not any(
        "Condition repeat/cycle settings must match across all conditions." in issue.message
        for issue in report.issues
    )


def test_condition_fixation_guidance_reports_duration_and_max_feasible_changes(sample_project) -> None:
    sample_project.conditions[0].sequence_count = 2
    sample_project.conditions[0].oddball_cycle_repeats_per_sequence = 3
    sample_project.settings.fixation_task.target_duration_ms = 250
    sample_project.settings.fixation_task.min_gap_ms = 1000

    guidance_rows = condition_fixation_guidance(sample_project, refresh_hz=60.0)

    assert len(guidance_rows) == 1
    row = guidance_rows[0]
    assert row.condition_name == "Faces"
    assert row.total_cycles == 6
    assert row.total_frames == 300
    assert row.condition_duration_seconds == 5.0
    assert row.estimated_max_color_changes_per_condition == 3
