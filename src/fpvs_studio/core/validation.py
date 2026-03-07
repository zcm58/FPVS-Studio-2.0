"""Validation helpers for editable FPVS Studio project state."""

from __future__ import annotations

from fpvs_studio.core.enums import DutyCycleMode, ValidationSeverity
from fpvs_studio.core.frame_validation import (
    FrameValidationError,
    frames_per_stimulus,
    validate_blank_mode_frames,
)
from fpvs_studio.core.models import (
    DisplayValidationReport,
    FixationTaskSettings,
    ProjectFile,
    ProjectValidationReport,
    ValidationIssue,
)
from fpvs_studio.core.template_library import default_template, get_template


def validate_display_refresh(
    refresh_hz: float,
    *,
    duty_cycle_mode: DutyCycleMode | None = None,
    base_hz: float | None = None,
) -> DisplayValidationReport:
    """Validate whether a refresh rate supports the fixed v1 protocol."""

    template = default_template()
    base_rate = base_hz if base_hz is not None else template.base_hz
    frames_per_cycle_raw = refresh_hz / base_rate
    errors: list[str] = []
    frames_per_cycle: int | None = None
    compatible = True

    try:
        frames_per_cycle = frames_per_stimulus(refresh_hz, base_rate)
    except FrameValidationError as exc:
        compatible = False
        errors.append(str(exc))

    if compatible and duty_cycle_mode == DutyCycleMode.BLANK_50 and frames_per_cycle is not None:
        try:
            validate_blank_mode_frames(frames_per_cycle)
        except FrameValidationError as exc:
            compatible = False
            errors.append(str(exc))

    return DisplayValidationReport(
        refresh_hz=refresh_hz,
        base_hz=base_rate,
        duty_cycle_mode=duty_cycle_mode,
        frames_per_cycle_raw=frames_per_cycle_raw,
        frames_per_cycle=frames_per_cycle,
        compatible=compatible,
        errors=errors,
    )


def validate_fixation_settings(settings: FixationTaskSettings) -> list[ValidationIssue]:
    """Return user-facing fixation-task validation issues."""

    issues: list[ValidationIssue] = []
    if settings.enabled and settings.target_duration_ms <= 0:
        issues.append(
            ValidationIssue(
                location="settings.fixation_task.target_duration_ms",
                message="Target duration must be greater than 0 ms when the fixation task is enabled.",
            )
        )
    if settings.min_gap_ms > settings.max_gap_ms:
        issues.append(
            ValidationIssue(
                location="settings.fixation_task",
                message="Fixation min_gap_ms must be less than or equal to max_gap_ms.",
            )
        )
    if settings.changes_per_sequence < 0:
        issues.append(
            ValidationIssue(
                location="settings.fixation_task.changes_per_sequence",
                message="changes_per_sequence must be non-negative.",
            )
        )
    return issues


def validate_project(project: ProjectFile, *, refresh_hz: float | None = None) -> ProjectValidationReport:
    """Validate cross-field project rules with user-friendly issues."""

    issues: list[ValidationIssue] = []
    template = get_template(project.meta.template_id)
    stimulus_sets = {item.set_id: item for item in project.stimulus_sets}

    issues.extend(validate_fixation_settings(project.settings.fixation_task))

    for condition in project.conditions:
        if not condition.name.strip():
            issues.append(
                ValidationIssue(
                    location=f"conditions.{condition.condition_id}.name",
                    message="Condition name may not be empty.",
                )
            )
        if condition.base_stimulus_set_id not in stimulus_sets:
            issues.append(
                ValidationIssue(
                    location=f"conditions.{condition.condition_id}.base_stimulus_set_id",
                    message=(
                        f"Condition '{condition.name}' references missing base stimulus set "
                        f"'{condition.base_stimulus_set_id}'."
                    ),
                )
            )
        if condition.oddball_stimulus_set_id not in stimulus_sets:
            issues.append(
                ValidationIssue(
                    location=f"conditions.{condition.condition_id}.oddball_stimulus_set_id",
                    message=(
                        f"Condition '{condition.name}' references missing oddball stimulus set "
                        f"'{condition.oddball_stimulus_set_id}'."
                    ),
                )
            )

        base_set = stimulus_sets.get(condition.base_stimulus_set_id)
        oddball_set = stimulus_sets.get(condition.oddball_stimulus_set_id)
        if base_set is not None and base_set.image_count <= 0:
            issues.append(
                ValidationIssue(
                    location=f"stimulus_sets.{base_set.set_id}.image_count",
                    message=f"Stimulus set '{base_set.name}' does not contain any imported images.",
                )
            )
        if oddball_set is not None and oddball_set.image_count <= 0:
            issues.append(
                ValidationIssue(
                    location=f"stimulus_sets.{oddball_set.set_id}.image_count",
                    message=f"Stimulus set '{oddball_set.name}' does not contain any imported images.",
                )
            )
        if (
            base_set is not None
            and oddball_set is not None
            and base_set.resolution is not None
            and oddball_set.resolution is not None
            and base_set.resolution != oddball_set.resolution
        ):
            issues.append(
                ValidationIssue(
                    location=f"conditions.{condition.condition_id}",
                    message=(
                        f"Condition '{condition.name}' uses stimulus sets with mismatched "
                        "resolutions."
                    ),
                )
            )

        if refresh_hz is not None:
            display_report = validate_display_refresh(
                refresh_hz,
                duty_cycle_mode=condition.duty_cycle_mode,
                base_hz=template.base_hz,
            )
            for error in display_report.errors:
                issues.append(
                    ValidationIssue(
                        location=f"conditions.{condition.condition_id}.duty_cycle_mode",
                        message=error,
                    )
                )

    if not project.conditions:
        issues.append(
            ValidationIssue(
                location="conditions",
                message="Project does not contain any conditions to compile or run.",
                severity=ValidationSeverity.WARNING,
            )
        )

    return ProjectValidationReport(issues=issues)
