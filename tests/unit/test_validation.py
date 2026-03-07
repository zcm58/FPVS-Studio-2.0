"""Validation tests."""

from __future__ import annotations

from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.models import ImageResolution
from fpvs_studio.core.validation import validate_display_refresh, validate_project


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
