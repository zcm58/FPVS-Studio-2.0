"""Validation helpers for editable authoring state before compilation or launch. These
routines check ProjectFile settings against protocol rules and frame-compatibility
constraints so compiler inputs stay explicit and friendly. The module owns authoring-
time diagnostics, not manifest generation, session execution, or engine timing loops."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor, isclose, isfinite

from fpvs_studio.core.enums import DutyCycleMode, StimulusModality, ValidationSeverity
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
from fpvs_studio.core.template_library import default_template

APPROVED_MONITOR_REFRESH_RATES_HZ: tuple[float, ...] = (
    59.94,
    60.0,
    120.0,
    144.0,
    240.0,
)
REFRESH_MEASUREMENT_RELATIVE_TOLERANCE = 0.01


def approved_monitor_refresh_rate(refresh_hz: float) -> float | None:
    """Return the canonical approved rate for an authored value, if any."""

    if not isfinite(refresh_hz) or refresh_hz <= 0:
        return None
    return next(
        (
            candidate
            for candidate in APPROVED_MONITOR_REFRESH_RATES_HZ
            if isclose(refresh_hz, candidate, rel_tol=0.0, abs_tol=1e-6)
        ),
        None,
    )


def measured_refresh_matches_configured(
    configured_hz: float,
    measured_hz: float,
) -> bool:
    """Return whether a measured rate is close enough to the configured target."""

    if approved_monitor_refresh_rate(configured_hz) is None:
        return False
    if not isfinite(measured_hz) or measured_hz <= 0:
        return False
    return isclose(
        configured_hz,
        measured_hz,
        rel_tol=REFRESH_MEASUREMENT_RELATIVE_TOLERANCE,
        abs_tol=0.0,
    )


def nearest_approved_monitor_refresh_rate(measured_hz: float) -> float | None:
    """Return the nearest approved rate when a display measurement is within tolerance."""

    if not isfinite(measured_hz) or measured_hz <= 0:
        return None
    nearest = min(
        APPROVED_MONITOR_REFRESH_RATES_HZ,
        key=lambda candidate: abs(candidate - measured_hz),
    )
    return nearest if measured_refresh_matches_configured(nearest, measured_hz) else None


def approved_monitor_refresh_rates_text() -> str:
    """Return the approved rates as compact user-facing text."""

    values = [f"{rate:g}" for rate in APPROVED_MONITOR_REFRESH_RATES_HZ]
    return f"{', '.join(values[:-1])}, or {values[-1]} Hz"


@dataclass(frozen=True)
class ConditionFixationGuidance:
    """Read-only condition-level fixation feasibility guidance for the GUI."""

    condition_id: str
    condition_name: str
    total_cycles: int
    total_frames: int
    condition_duration_seconds: float
    estimated_max_color_changes_per_condition: int
    recommended_max_color_changes_per_condition: int


@dataclass(frozen=True)
class StimulusRepeatRoleGuidance:
    """Read-only condition-role stimulus repeat balance guidance."""

    condition_id: str
    condition_name: str
    role: str
    modality: StimulusModality
    presentation_count: int
    image_count: int
    target_repeats_per_image: int
    recommended_minimum_images: int
    min_repeats_per_image: int
    max_repeats_per_image: int
    evenly_distributed: bool


def duration_based_fixation_change_cap(condition_duration_seconds: float) -> int:
    """Return the conservative fixation change cap derived from condition duration."""

    return max(1, floor(condition_duration_seconds * 15 / 120))


def validate_display_refresh(
    refresh_hz: float,
    *,
    duty_cycle_mode: DutyCycleMode | None = None,
    base_hz: float | None = None,
    oddball_every_n: int | None = None,
) -> DisplayValidationReport:
    """Resolve requested FPVS timing and report exact or approximate compatibility."""

    template = default_template()
    base_rate = base_hz if base_hz is not None else template.base_hz
    frames_per_cycle_raw = refresh_hz / base_rate
    errors: list[str] = []
    warnings: list[str] = []
    frames_per_cycle: int | None = None
    timing_is_exact = False
    realized_base_hz: float | None = None
    requested_oddball_hz = (
        base_rate / oddball_every_n if oddball_every_n is not None else None
    )
    realized_oddball_hz: float | None = None
    compatible = True

    if approved_monitor_refresh_rate(refresh_hz) is None:
        compatible = False
        errors.append(
            "Monitor refresh rate must be an approved value: "
            f"{approved_monitor_refresh_rates_text()}."
        )

    try:
        frames_per_cycle = frames_per_stimulus(refresh_hz, base_rate)
    except FrameValidationError as exc:
        compatible = False
        errors.append(str(exc))

    if frames_per_cycle is not None:
        timing_is_exact = isclose(
            frames_per_cycle_raw,
            frames_per_cycle,
            abs_tol=1e-6,
        )
        realized_base_hz = refresh_hz / frames_per_cycle
        if oddball_every_n is not None:
            realized_oddball_hz = realized_base_hz / oddball_every_n
        if not timing_is_exact:
            oddball_detail = (
                f" and {realized_oddball_hz:.6g} Hz oddball timing"
                if realized_oddball_hz is not None
                else ""
            )
            warnings.append(
                "Approximate frame timing: "
                f"{refresh_hz:g} Hz / {base_rate:g} Hz = {frames_per_cycle_raw:.6g} "
                f"frames. Using {frames_per_cycle} whole frames realizes "
                f"{realized_base_hz:.6g} Hz base timing{oddball_detail}. "
                "Dropped or late frames are reported separately by runtime timing QC."
            )

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
        timing_is_exact=timing_is_exact,
        realized_base_hz=realized_base_hz,
        oddball_every_n=oddball_every_n,
        requested_oddball_hz=requested_oddball_hz,
        realized_oddball_hz=realized_oddball_hz,
        compatible=compatible,
        errors=errors,
        warnings=warnings,
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

    protocol = project.settings.protocol
    frames_per_stimulus_value = frames_per_stimulus(refresh_hz, protocol.base_hz)
    fixation = project.settings.fixation_task
    target_duration_frames = milliseconds_to_frames(
        fixation.target_duration_ms,
        refresh_hz,
    )
    min_gap_frames = milliseconds_to_frames(fixation.min_gap_ms, refresh_hz)

    guidance_rows: list[ConditionFixationGuidance] = []
    for condition in sorted(project.conditions, key=lambda item: item.order_index):
        total_cycles = condition.oddball_cycle_repeats_per_sequence * condition.sequence_count
        total_stimuli = total_cycles * protocol.oddball_every_n
        total_frames = total_stimuli * frames_per_stimulus_value
        physical_max = max_supported_color_changes(
            total_frames=total_frames,
            target_duration_frames=target_duration_frames,
            min_gap_frames=min_gap_frames,
        )
        duration_cap = duration_based_fixation_change_cap(total_frames / refresh_hz)
        guidance_rows.append(
            ConditionFixationGuidance(
                condition_id=condition.condition_id,
                condition_name=condition.name,
                total_cycles=total_cycles,
                total_frames=total_frames,
                condition_duration_seconds=total_frames / refresh_hz,
                estimated_max_color_changes_per_condition=physical_max,
                recommended_max_color_changes_per_condition=min(physical_max, duration_cap),
            )
        )
    return guidance_rows


def condition_stimulus_repeat_guidance(project: ProjectFile) -> list[StimulusRepeatRoleGuidance]:
    """Return condition-level base/oddball per-image repeat guidance."""

    oddball_every_n = project.settings.protocol.oddball_every_n
    stimulus_sets = {item.set_id: item for item in project.stimulus_sets}
    target_repeats = project.settings.condition_defaults.target_repeats_per_image
    guidance_rows: list[StimulusRepeatRoleGuidance] = []

    for condition in sorted(project.conditions, key=lambda item: item.order_index):
        oddball_presentations = (
            condition.oddball_cycle_repeats_per_sequence * condition.sequence_count
        )
        role_presentations = {
            "base": oddball_presentations * (oddball_every_n - 1),
            "oddball": oddball_presentations,
        }
        role_set_ids = {
            "base": condition.base_stimulus_set_id,
            "oddball": condition.oddball_stimulus_set_id,
        }
        for role, presentation_count in role_presentations.items():
            stimulus_set = stimulus_sets.get(role_set_ids[role])
            modality = stimulus_set.modality if stimulus_set is not None else StimulusModality.IMAGE
            image_count = (
                stimulus_set.image_count
                if stimulus_set is not None and modality == StimulusModality.IMAGE
                else stimulus_set.word_count
                if stimulus_set is not None and modality == StimulusModality.WORD
                else 0
            )
            if image_count <= 0:
                min_repeats = 0
                max_repeats = 0
                evenly_distributed = False
            else:
                min_repeats = presentation_count // image_count
                max_repeats = ceil(presentation_count / image_count)
                evenly_distributed = presentation_count % image_count == 0
            guidance_rows.append(
                StimulusRepeatRoleGuidance(
                    condition_id=condition.condition_id,
                    condition_name=condition.name,
                    role=role,
                    modality=modality,
                    presentation_count=presentation_count,
                    image_count=image_count,
                    target_repeats_per_image=target_repeats,
                    recommended_minimum_images=ceil(presentation_count / target_repeats),
                    min_repeats_per_image=min_repeats,
                    max_repeats_per_image=max_repeats,
                    evenly_distributed=evenly_distributed,
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
    stimulus_sets = {item.set_id: item for item in project.stimulus_sets}

    if refresh_hz is not None:
        protocol = project.settings.protocol
        protocol_report = validate_display_refresh(
            refresh_hz,
            base_hz=protocol.base_hz,
            oddball_every_n=protocol.oddball_every_n,
        )
        for error in protocol_report.errors:
            issues.append(
                ValidationIssue(
                    location="settings.protocol.base_hz",
                    message=error,
                )
            )
        for warning in protocol_report.warnings:
            issues.append(
                ValidationIssue(
                    location="settings.protocol.base_hz",
                    message=warning,
                    severity=ValidationSeverity.WARNING,
                )
            )

    issues.extend(validate_fixation_settings(project.settings.fixation_task))
    issues.extend(validate_condition_repeat_cycle_consistency(project))
    for row in condition_stimulus_repeat_guidance(project):
        if row.image_count <= 0:
            continue
        role_label = "Base" if row.role == "base" else "Oddball"
        item_label = "images" if row.modality == StimulusModality.IMAGE else "words"
        repeat_label = "image" if row.modality == StimulusModality.IMAGE else "word"
        repeat_range = (
            f"{row.min_repeats_per_image}"
            if row.min_repeats_per_image == row.max_repeats_per_image
            else f"{row.min_repeats_per_image}-{row.max_repeats_per_image}"
        )
        if row.image_count < row.recommended_minimum_images:
            issues.append(
                ValidationIssue(
                    location=f"conditions.{row.condition_id}.{row.role}_stimulus_set_id",
                    message=(
                        f"{role_label} stimulus set for condition '{row.condition_name}' has "
                        f"{row.image_count} {item_label}, but "
                        f"{row.recommended_minimum_images} are recommended for <= "
                        f"{row.target_repeats_per_image} repeats/{repeat_label} across "
                        f"{row.presentation_count} presentations. Current scheduling gives "
                        f"{repeat_range} repeats/{repeat_label}."
                    ),
                    severity=ValidationSeverity.WARNING,
                )
            )
        if not row.evenly_distributed:
            issues.append(
                ValidationIssue(
                    location=f"conditions.{row.condition_id}.{row.role}_stimulus_set_id",
                    message=(
                        f"{role_label} presentations for condition '{row.condition_name}' "
                        f"do not divide evenly across {row.image_count} {item_label}; "
                        f"current scheduling gives {repeat_range} repeats/{repeat_label}."
                    ),
                    severity=ValidationSeverity.WARNING,
                )
            )

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
        if (
            base_set is not None
            and oddball_set is not None
            and base_set.modality != oddball_set.modality
        ):
            issues.append(
                ValidationIssue(
                    location=f"conditions.{condition.condition_id}",
                    message=(
                        f"Condition '{condition.name}' cannot mix base "
                        f"{base_set.modality.value} stimuli with oddball "
                        f"{oddball_set.modality.value} stimuli."
                    ),
                )
            )
            continue
        if (
            base_set is not None
            and oddball_set is not None
            and base_set.modality == StimulusModality.IMAGE
            and base_set.source_dir == oddball_set.source_dir
        ):
            issues.append(
                ValidationIssue(
                    location=f"conditions.{condition.condition_id}",
                    message=(
                        f"Condition '{condition.name}' cannot use the same folder for base "
                        "and oddball images."
                    ),
                )
            )
        if (
            base_set is not None
            and base_set.modality == StimulusModality.IMAGE
            and base_set.image_count <= 0
        ):
            issues.append(
                ValidationIssue(
                    location=f"stimulus_sets.{base_set.set_id}.image_count",
                    message=f"Stimulus set '{base_set.name}' does not contain any imported images.",
                )
            )
        if (
            oddball_set is not None
            and oddball_set.modality == StimulusModality.IMAGE
            and oddball_set.image_count <= 0
        ):
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
            and base_set.modality == StimulusModality.WORD
            and base_set.word_count <= 0
        ):
            issues.append(
                ValidationIssue(
                    location=f"stimulus_sets.{base_set.set_id}.words",
                    message=f"Stimulus set '{base_set.name}' does not contain any words.",
                )
            )
        if (
            oddball_set is not None
            and oddball_set.modality == StimulusModality.WORD
            and oddball_set.word_count <= 0
        ):
            issues.append(
                ValidationIssue(
                    location=f"stimulus_sets.{oddball_set.set_id}.words",
                    message=f"Stimulus set '{oddball_set.name}' does not contain any words.",
                )
            )
        for role, stimulus_set in (("base", base_set), ("oddball", oddball_set)):
            if stimulus_set is None:
                continue
            if stimulus_set.modality != StimulusModality.IMAGE:
                continue
            role_label = "Base" if role == "base" else "Oddball"
            if stimulus_set.resolution is None:
                issues.append(
                    ValidationIssue(
                        location=f"conditions.{condition.condition_id}.{role}_stimulus_set_id",
                        message=(
                            f"{role_label} stimulus set for condition '{condition.name}' must "
                            "be normalized to square images before launch."
                        ),
                    )
                )
                continue
            if stimulus_set.resolution.width_px != stimulus_set.resolution.height_px:
                issues.append(
                    ValidationIssue(
                        location=f"conditions.{condition.condition_id}.{role}_stimulus_set_id",
                        message=(
                            f"{role_label} stimulus set for condition '{condition.name}' uses "
                            f"non-square {stimulus_set.resolution.width_px}x"
                            f"{stimulus_set.resolution.height_px} images. Normalize the selected "
                            "images to square PNG copies before launch."
                        ),
                    )
                )

        if refresh_hz is not None:
            display_report = validate_display_refresh(
                refresh_hz,
                duty_cycle_mode=condition.duty_cycle_mode,
                base_hz=project.settings.protocol.base_hz,
                oddball_every_n=project.settings.protocol.oddball_every_n,
            )
            for error in display_report.errors:
                if error in protocol_report.errors:
                    continue
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
