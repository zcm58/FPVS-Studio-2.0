"""Validation helpers for editable authoring state before compilation or launch. These
routines check ProjectFile settings against protocol rules and frame-compatibility
constraints so compiler inputs stay explicit and friendly. The module owns authoring-
time diagnostics, not manifest generation, session execution, or engine timing loops."""

from __future__ import annotations

from dataclasses import dataclass

from fpvs_studio.core.enums import DutyCycleMode, ValidationSeverity
from fpvs_studio.core.fixation_planning import (
    max_supported_color_changes,
    milliseconds_to_frames,
)
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


@dataclass(frozen=True)
class ConditionFixationGuidance:
    """Read-only condition-level fixation feasibility guidance for the GUI."""

    condition_id: str
    condition_name: str
    total_cycles: int
    total_frames: int
    condition_duration_seconds: float
    estimated_max_color_changes_per_condition: int


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
                message=(
                    "Target duration must be greater than 0 ms when the fixation task is enabled."
                ),
            )
        )
    if settings.min_gap_ms > settings.max_gap_ms:
        issues.append(
            ValidationIssue(
                location="settings.fixation_task",
                message="Fixation min_gap_ms must be less than or equal to max_gap_ms.",
            )
        )
    if settings.accuracy_task_enabled and not settings.enabled:
        issues.append(
            ValidationIssue(
                location="settings.fixation_task.accuracy_task_enabled",
                message="Fixation task must be enabled when the fixation accuracy task is enabled.",
            )
        )
    if settings.response_window_seconds <= 0:
        issues.append(
            ValidationIssue(
                location="settings.fixation_task.response_window_seconds",
                message="Fixation response window must be greater than 0 seconds.",
            )
        )
    if not settings.response_key.strip():
        issues.append(
            ValidationIssue(
                location="settings.fixation_task.response_key",
                message="Fixation response key may not be blank.",
            )
        )
    if settings.target_count_mode == "randomized":
        if settings.target_count_min > settings.target_count_max:
            issues.append(
                ValidationIssue(
                    location="settings.fixation_task",
                    message=(
                        "Fixation target_count_min must be less than or equal to target_count_max."
                    ),
                )
            )
        if (
            settings.no_immediate_repeat_count
            and settings.target_count_min == settings.target_count_max
        ):
            issues.append(
                ValidationIssue(
                    location="settings.fixation_task",
                    message=(
                        "Randomized color changes per condition (target counts) require "
                        "min/max to differ when no immediate repeat is enabled."
                    ),
                )
            )
    if settings.changes_per_sequence < 0:
        issues.append(
            ValidationIssue(
                location="settings.fixation_task.changes_per_sequence",
                message="Color changes per condition must be non-negative.",
            )
        )
    return issues


def condition_fixation_guidance(
    project: ProjectFile,
    *,
    refresh_hz: float,
) -> list[ConditionFixationGuidance]:
    """Return condition-level duration and max-feasible fixation guidance."""

    template = get_template(project.meta.template_id)
    frames_per_stimulus_value = frames_per_stimulus(refresh_hz, template.base_hz)
    fixation = project.settings.fixation_task
    target_duration_frames = milliseconds_to_frames(
        fixation.target_duration_ms,
        refresh_hz,
    )
    min_gap_frames = milliseconds_to_frames(fixation.min_gap_ms, refresh_hz)

    guidance_rows: list[ConditionFixationGuidance] = []
    for condition in sorted(project.conditions, key=lambda item: item.order_index):
        total_cycles = condition.oddball_cycle_repeats_per_sequence * condition.sequence_count
        total_stimuli = total_cycles * template.oddball_every_n
        total_frames = total_stimuli * frames_per_stimulus_value
        guidance_rows.append(
            ConditionFixationGuidance(
                condition_id=condition.condition_id,
                condition_name=condition.name,
                total_cycles=total_cycles,
                total_frames=total_frames,
                condition_duration_seconds=total_frames / refresh_hz,
                estimated_max_color_changes_per_condition=max_supported_color_changes(
                    total_frames=total_frames,
                    target_duration_frames=target_duration_frames,
                    min_gap_frames=min_gap_frames,
                ),
            )
        )
    return guidance_rows


def validate_condition_repeat_cycle_consistency(project: ProjectFile) -> list[ValidationIssue]:
    """Return issues when condition repeat/cycle settings are not uniform."""

    ordered_conditions = sorted(project.conditions, key=lambda item: item.order_index)
    if len(ordered_conditions) <= 1:
        return []

    first_condition = ordered_conditions[0]
    expected_sequence_count = first_condition.sequence_count
    expected_cycle_repeats = first_condition.oddball_cycle_repeats_per_sequence
    issues: list[ValidationIssue] = []

    for condition in ordered_conditions[1:]:
        if (
            condition.sequence_count == expected_sequence_count
            and condition.oddball_cycle_repeats_per_sequence == expected_cycle_repeats
        ):
            continue
        issues.append(
            ValidationIssue(
                location=f"conditions.{condition.condition_id}",
                message=(
                    "Condition repeat/cycle settings must match across all conditions. "
                    f"Expected pair from first ordered condition '{first_condition.name}': "
                    f"(Condition Repeats={expected_sequence_count}, "
                    f"Cycles / Condition Repeat={expected_cycle_repeats}). "
                    f"Actual pair for condition '{condition.name}': "
                    f"(Condition Repeats={condition.sequence_count}, "
                    f"Cycles / Condition Repeat={condition.oddball_cycle_repeats_per_sequence}). "
                    "Align all conditions before save/run."
                ),
            )
        )

    return issues


def validate_project(
    project: ProjectFile, *, refresh_hz: float | None = None
) -> ProjectValidationReport:
    """Validate cross-field project rules with user-friendly issues."""

    issues: list[ValidationIssue] = []
    template = get_template(project.meta.template_id)
    stimulus_sets = {item.set_id: item for item in project.stimulus_sets}

    issues.extend(validate_fixation_settings(project.settings.fixation_task))
    issues.extend(validate_condition_repeat_cycle_consistency(project))

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
                    message=(
                        f"Stimulus set '{oddball_set.name}' does not contain any imported images."
                    ),
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
