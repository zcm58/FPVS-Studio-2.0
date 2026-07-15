"""Validation tests."""

from __future__ import annotations

from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.models import ImageResolution
from fpvs_studio.core.validation import (
    APPROVED_MONITOR_REFRESH_RATES_HZ,
    approved_monitor_refresh_rate,
    condition_fixation_guidance,
    condition_stimulus_repeat_guidance,
    measured_refresh_matches_configured,
    nearest_approved_monitor_refresh_rate,
    validate_display_refresh,
    validate_project,
)


def test_refresh_validation_accepts_supported_refresh_rate() -> None:
    report = validate_display_refresh(60.0, duty_cycle_mode=DutyCycleMode.CONTINUOUS)

    assert report.compatible is True
    assert report.frames_per_cycle == 10
    assert report.timing_is_exact is True
    assert report.realized_base_hz == 6.0
    assert report.errors == []
    assert report.warnings == []


def test_refresh_validation_accepts_144hz_as_exact() -> None:
    report = validate_display_refresh(
        144.0,
        duty_cycle_mode=DutyCycleMode.CONTINUOUS,
        base_hz=6.0,
        oddball_every_n=6,
    )

    assert report.compatible is True
    assert report.frames_per_cycle == 24
    assert report.timing_is_exact is True
    assert report.realized_oddball_hz == 1.0
    assert report.warnings == []


def test_refresh_validation_accepts_5994hz_with_realized_rate_warning() -> None:
    report = validate_display_refresh(
        59.94,
        duty_cycle_mode=DutyCycleMode.CONTINUOUS,
        base_hz=6.0,
        oddball_every_n=6,
    )

    assert report.compatible is True
    assert report.frames_per_cycle == 10
    assert report.timing_is_exact is False
    assert report.realized_base_hz == 5.994
    assert report.realized_oddball_hz == 0.999
    assert report.errors == []
    assert "Approximate frame timing" in report.warnings[0]


def test_approved_monitor_refresh_rates_are_canonical() -> None:
    assert APPROVED_MONITOR_REFRESH_RATES_HZ == (59.94, 60.0, 120.0, 144.0, 240.0)
    assert approved_monitor_refresh_rate(144.0) == 144.0
    assert approved_monitor_refresh_rate(75.0) is None


def test_measured_refresh_selects_nearest_approved_rate_within_tolerance() -> None:
    assert nearest_approved_monitor_refresh_rate(59.94) == 59.94
    assert nearest_approved_monitor_refresh_rate(60.02) == 60.0
    assert nearest_approved_monitor_refresh_rate(143.8) == 144.0
    assert nearest_approved_monitor_refresh_rate(75.0) is None
    assert measured_refresh_matches_configured(144.0, 143.8) is True
    assert measured_refresh_matches_configured(240.0, 60.0) is False


def test_refresh_validation_rejects_unapproved_refresh_rate() -> None:
    report = validate_display_refresh(75.0, duty_cycle_mode=DutyCycleMode.CONTINUOUS)

    assert report.compatible is False
    assert "approved value" in report.errors[0]


def test_refresh_validation_rejects_sub_frame_base_rate() -> None:
    report = validate_display_refresh(
        60.0,
        duty_cycle_mode=DutyCycleMode.CONTINUOUS,
        base_hz=120.0,
    )

    assert report.compatible is False
    assert report.frames_per_cycle is None
    assert "at least one display frame" in report.errors[0]


def test_refresh_validation_rejects_blank_50_on_odd_frame_cycles() -> None:
    report = validate_display_refresh(
        60.0,
        duty_cycle_mode=DutyCycleMode.BLANK_50,
        base_hz=4.0,
    )

    assert report.compatible is False
    assert any("blank_50" in message for message in report.errors)


def test_project_validation_accepts_different_square_source_resolutions(sample_project) -> None:
    sample_project.stimulus_sets[1].resolution = ImageResolution(width_px=512, height_px=512)

    report = validate_project(sample_project)

    assert report.is_valid is True
    assert not any("non-square" in issue.message for issue in report.issues)


def test_project_validation_rejects_non_square_source_resolution(sample_project) -> None:
    sample_project.stimulus_sets[1].resolution = ImageResolution(width_px=512, height_px=384)

    report = validate_project(sample_project)

    assert report.is_valid is False
    assert any("non-square 512x384" in issue.message for issue in report.issues)


def test_project_validation_rejects_same_base_and_oddball_folder(sample_project) -> None:
    sample_project.stimulus_sets[1] = sample_project.stimulus_sets[1].model_copy(
        update={"source_dir": sample_project.stimulus_sets[0].source_dir}
    )

    report = validate_project(sample_project)

    assert report.is_valid is False
    assert any(
        "same folder for base and oddball images" in issue.message for issue in report.issues
    )


def test_stimulus_repeat_guidance_reports_default_v1_presentation_counts(
    sample_project,
) -> None:
    rows = condition_stimulus_repeat_guidance(sample_project)
    rows_by_role = {row.role: row for row in rows}

    base = rows_by_role["base"]
    oddball = rows_by_role["oddball"]

    assert base.presentation_count == 584
    assert base.recommended_minimum_images == 84
    assert base.min_repeats_per_image == 194
    assert base.max_repeats_per_image == 195
    assert base.evenly_distributed is False
    assert oddball.presentation_count == 146
    assert oddball.recommended_minimum_images == 21
    assert oddball.min_repeats_per_image == 48
    assert oddball.max_repeats_per_image == 49
    assert oddball.evenly_distributed is False


def test_project_validation_warns_for_too_few_stimulus_images_without_blocking(
    sample_project,
) -> None:
    report = validate_project(sample_project)

    assert report.is_valid is True
    assert any(issue.severity.value == "warning" for issue in report.issues)
    assert any(
        "Base stimulus set" in issue.message
        and "84 are recommended for <= 7 repeats/image"
        for issue in report.issues
    )
    assert any(
        "Oddball stimulus set" in issue.message
        and "21 are recommended for <= 7 repeats/image"
        for issue in report.issues
    )


def test_project_validation_warns_for_uneven_stimulus_repeat_distribution(
    sample_project,
) -> None:
    sample_project.settings.condition_defaults.target_repeats_per_image = 10
    sample_project.stimulus_sets[0].image_count = 100
    sample_project.stimulus_sets[1].image_count = 100

    report = validate_project(sample_project)

    assert report.is_valid is True
    assert not any("are recommended for <=" in issue.message for issue in report.issues)
    assert any(
        "Base presentations" in issue.message
        and "5-6 repeats/image" in issue.message
        for issue in report.issues
    )
    assert any(
        "Oddball presentations" in issue.message
        and "1-2 repeats/image" in issue.message
        for issue in report.issues
    )


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


def test_condition_fixation_guidance_reports_duration_and_max_feasible_changes(
    sample_project,
) -> None:
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
    assert row.recommended_max_color_changes_per_condition == 1


def test_project_validation_ignores_legacy_fixation_max_gap_contract(sample_project) -> None:
    sample_project.settings.fixation_task.min_gap_ms = 3000
    sample_project.settings.fixation_task.max_gap_ms = 1000

    report = validate_project(sample_project)

    assert not any("max_gap_ms" in issue.message for issue in report.issues)
