"""Resolve condition timing and propose atomic frequency/duration edits."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import floor, isclose, isfinite

from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.frame_validation import FRAME_TOLERANCE, frames_per_stimulus
from fpvs_studio.core.masking import (
    condition_masking,
    masking_frame_counts,
    validate_masking_catch_trials,
)
from fpvs_studio.core.models import Condition, ProjectFile, ProtocolSettings


@dataclass(frozen=True)
class ConditionStreamTiming:
    """Resolved stream timing, excluding lead-in and participant tasks."""

    total_oddball_cycles: int
    total_stimuli: int
    frames_per_stimulus: int
    total_frames: int
    duration_seconds: float


class ConditionDurationError(ValueError):
    """An authored duration cannot fit complete oddball cycles on this display."""

    def __init__(
        self, condition: Condition, *, requested_seconds: float,
        cycle_frames: int, refresh_hz: float,
    ) -> None:
        self.condition_id = condition.condition_id
        self.requested_seconds = requested_seconds
        lower = max(1, floor(requested_seconds * refresh_hz / cycle_frames))
        self.valid_durations = tuple(
            count * cycle_frames / refresh_hz for count in (lower, lower + 1)
        )
        durations = " or ".join(f"{value:.12g}" for value in self.valid_durations)
        super().__init__(
            f"{condition.name}: {requested_seconds:.12g} seconds does not fit complete oddball "
            f"cycles on the {refresh_hz:g} Hz display. Valid durations: {durations} seconds."
        )


def effective_condition_base_hz(project: ProjectFile, condition: Condition) -> float:
    """Return an explicit condition frequency or its inherited project frequency."""

    return condition.base_hz if condition.base_hz is not None else project.settings.protocol.base_hz


def resolve_condition_stream_timing(
    project: ProjectFile, condition: Condition, refresh_hz: float,
) -> ConditionStreamTiming:
    """Resolve requested seconds or unchanged legacy continuous cycle counts.

    A one-millionth-frame tolerance accommodates floating arithmetic and copying
    valid durations displayed to nine decimal places. It cannot admit a neighboring
    frame or a partial oddball cycle.
    """

    frame_count = frames_per_stimulus(refresh_hz, effective_condition_base_hz(project, condition))
    cadence = project.settings.protocol.oddball_every_n
    cycle_frames = cadence * frame_count
    if condition.stream_duration_seconds is None:
        cycles = condition.sequence_count * condition.oddball_cycle_repeats_per_sequence
    else:
        requested_frames = condition.stream_duration_seconds * refresh_hz
        if not isfinite(requested_frames):
            raise ValueError(
                f"{condition.name}: stream duration is too large for this display rate."
            )
        cycles = round(requested_frames / cycle_frames)
        if cycles < 1 or not isclose(
            requested_frames, cycles * cycle_frames, rel_tol=0.0, abs_tol=FRAME_TOLERANCE,
        ):
            raise ConditionDurationError(
                condition, requested_seconds=condition.stream_duration_seconds,
                cycle_frames=cycle_frames, refresh_hz=refresh_hz,
            )
    total_frames = cycles * cycle_frames
    return ConditionStreamTiming(
        total_oddball_cycles=cycles, total_stimuli=cycles * cadence,
        frames_per_stimulus=frame_count, total_frames=total_frames,
        duration_seconds=total_frames / refresh_hz,
    )


def condition_stream_duration_seconds(
    project: ProjectFile, condition: Condition, refresh_hz: float | None,
) -> float | None:
    """Return authored seconds, or legacy seconds only with a known refresh target."""

    if condition.stream_duration_seconds is not None:
        return condition.stream_duration_seconds
    if refresh_hz is None:
        return None
    return resolve_condition_stream_timing(project, condition, refresh_hz).duration_seconds


def propose_condition_timing(
    project: ProjectFile,
    *,
    shared_base_hz: float | None = None,
    overrides: Mapping[str, float | None] | None = None,
    durations: Mapping[str, float] | None = None,
    presentation_counts: Mapping[str, int] | None = None,
    refresh_hz: float | None = None,
) -> ProjectFile:
    """Return one validated draft, preserving seconds without partial source edits."""

    from fpvs_studio.core.validation import (
        condition_fixation_guidance,
        validate_condition_repeat_cycle_consistency,
        validate_display_refresh,
    )

    draft = project.model_copy(deep=True)
    if shared_base_hz is not None:
        draft.settings.protocol = ProtocolSettings.model_validate({
            **draft.settings.protocol.model_dump(), "base_hz": shared_base_hz,
        })
    by_id = {condition.condition_id: condition for condition in draft.conditions}
    edited_ids = set(overrides or {}) | set(durations or {}) | set(presentation_counts or {})
    for condition_id in edited_ids:
        if condition_id not in by_id:
            raise ValueError(f"Unknown condition '{condition_id}'.")
        updates: dict[str, object] = {}
        if condition_id in (overrides or {}):
            updates["base_hz"] = (overrides or {})[condition_id]
        if condition_id in (durations or {}):
            value = (durations or {})[condition_id]
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not isfinite(value) or value <= 0):
                raise ValueError(
                    f"{by_id[condition_id].name}: stream duration must be a finite number "
                    "greater than zero."
                )
            updates["stream_duration_seconds"] = value
        if condition_id in (presentation_counts or {}):
            count = (presentation_counts or {})[condition_id]
            if type(count) is not int or count < 1:
                raise ValueError(
                    f"{by_id[condition_id].name}: total presentations must be a positive integer."
                )
            updates["presentation_count"] = count
        by_id[condition_id] = Condition.model_validate({
            **by_id[condition_id].model_dump(), **updates,
        })
    draft.conditions = [by_id[condition.condition_id] for condition in draft.conditions]
    draft = ProjectFile.model_validate(draft.model_dump())
    if presentation_counts is not None:
        from fpvs_studio.core.session_ordering import validate_condition_presentation_counts

        validate_condition_presentation_counts(draft)
    changed = (
        bool(durations) or draft.settings.protocol.base_hz != project.settings.protocol.base_hz
        or any(condition.base_hz != original.base_hz
               or condition.stream_duration_seconds != original.stream_duration_seconds
               for original, condition in zip(project.conditions, draft.conditions, strict=True))
    )
    if not changed:
        return draft
    if project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK:
        raise ValueError("Edit Attentional-Blink timing in the letter-stream designer.")
    if refresh_hz is None:
        raise ValueError("Select a monitor refresh rate before changing presentation timing.")
    if draft.settings.protocol.base_hz != project.settings.protocol.base_hz:
        shared_report = validate_display_refresh(
            refresh_hz, base_hz=draft.settings.protocol.base_hz,
            oddball_every_n=draft.settings.protocol.oddball_every_n,
        )
        if not shared_report.compatible:
            raise ValueError(" ".join(shared_report.errors))
    edited: set[str] = set()
    for original, condition in zip(project.conditions, draft.conditions, strict=True):
        before = effective_condition_base_hz(project, original)
        after = effective_condition_base_hz(draft, condition)
        if (before == after
                and condition.stream_duration_seconds == original.stream_duration_seconds
                and condition.condition_id not in (durations or {})):
            continue
        report = validate_display_refresh(
            refresh_hz, base_hz=after, duty_cycle_mode=condition.duty_cycle_mode,
            oddball_every_n=draft.settings.protocol.oddball_every_n,
        )
        if not report.compatible:
            raise ValueError(f"{condition.name}: {' '.join(report.errors)}")
        masking = condition_masking(draft, condition)
        if masking is not None:
            masking_frame_counts(masking, refresh_hz=refresh_hz, base_hz=after)
        if condition.stream_duration_seconds is None:
            condition.stream_duration_seconds = condition_stream_duration_seconds(
                project, original, refresh_hz,
            )
        resolved = resolve_condition_stream_timing(draft, condition, refresh_hz)
        condition.sequence_count = 1
        condition.oddball_cycle_repeats_per_sequence = resolved.total_oddball_cycles
        edited.add(condition.condition_id)
    validate_masking_catch_trials(draft, draft.conditions, refresh_hz=refresh_hz)
    issues = validate_condition_repeat_cycle_consistency(draft, refresh_hz=refresh_hz)
    if issues:
        raise ValueError(" ".join(issue.message for issue in issues))
    if draft.settings.fixation_task.enabled:
        settings = draft.settings.fixation_task
        required = (settings.target_count_min if settings.target_count_mode == "randomized"
                    else settings.changes_per_sequence)
        for row in condition_fixation_guidance(draft, refresh_hz=refresh_hz):
            if (row.condition_id in edited
                    and required > row.estimated_max_color_changes_per_condition):
                raise ValueError(
                    f"{row.condition_name}: fixation color-change settings do not fit this "
                    "stream duration. Increase the duration or reduce the fixation target "
                    "count, target duration or minimum gap."
                )
    return ProjectFile.model_validate(draft.model_dump())


def propose_condition_frequencies(
    project: ProjectFile,
    *,
    shared_base_hz: float | None = None,
    overrides: Mapping[str, float | None] | None = None,
    refresh_hz: float | None = None,
) -> ProjectFile:
    """Preserve the public frequency-edit route through the shared timing owner."""

    return propose_condition_timing(
        project, shared_base_hz=shared_base_hz, overrides=overrides, refresh_hz=refresh_hz,
    )
