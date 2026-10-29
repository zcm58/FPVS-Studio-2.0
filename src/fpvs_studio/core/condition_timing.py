"""Resolve condition frequencies and propose atomic, duration-preserving edits."""

from __future__ import annotations

from collections.abc import Mapping
from math import floor

from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.frame_validation import frames_per_stimulus
from fpvs_studio.core.masking import (
    condition_masking,
    masking_frame_counts,
    validate_masking_catch_trials,
)
from fpvs_studio.core.models import Condition, ProjectFile, ProtocolSettings


def effective_condition_base_hz(project: ProjectFile, condition: Condition) -> float:
    """Return an explicit condition frequency or its inherited project frequency."""

    return condition.base_hz if condition.base_hz is not None else project.settings.protocol.base_hz


def propose_condition_frequencies(
    project: ProjectFile,
    *,
    shared_base_hz: float | None = None,
    overrides: Mapping[str, float | None] | None = None,
    refresh_hz: float | None = None,
) -> ProjectFile:
    """Return a validated draft, preserving stream frames at a known display rate.

    This does not mutate the source project or create a duration authoring setting.
    Legacy sequence counts retain their continuous-stream meaning. A changed rate
    must fit complete cycles within each existing sequence; otherwise the caller
    receives the nearest valid duration choices without any partial edits.
    """

    from fpvs_studio.core.validation import (
        validate_condition_repeat_cycle_consistency,
        validate_display_refresh,
    )

    draft = project.model_copy(deep=True)
    if shared_base_hz is not None:
        draft.settings.protocol = ProtocolSettings.model_validate({
            **draft.settings.protocol.model_dump(), "base_hz": shared_base_hz,
        })
    by_id = {condition.condition_id: condition for condition in draft.conditions}
    for condition_id, base_hz in (overrides or {}).items():
        if condition_id not in by_id:
            raise ValueError(f"Unknown condition '{condition_id}'.")
        by_id[condition_id] = Condition.model_validate({
            **by_id[condition_id].model_dump(), "base_hz": base_hz,
        })
    draft.conditions = [by_id[condition.condition_id] for condition in draft.conditions]
    draft = ProjectFile.model_validate(draft.model_dump())
    changed = draft.settings.protocol.base_hz != project.settings.protocol.base_hz or any(
        condition.base_hz != original.base_hz
        for original, condition in zip(project.conditions, draft.conditions, strict=True)
    )
    if not changed:
        return draft
    if project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK:
        raise ValueError("Edit Attentional-Blink presentation rates in the letter-stream designer.")
    if refresh_hz is None:
        raise ValueError("Select a monitor refresh rate before changing presentation frequency.")
    if draft.settings.protocol.base_hz != project.settings.protocol.base_hz:
        shared_report = validate_display_refresh(
            refresh_hz, base_hz=draft.settings.protocol.base_hz,
            oddball_every_n=draft.settings.protocol.oddball_every_n,
        )
        if not shared_report.compatible:
            raise ValueError(" ".join(shared_report.errors))
    for original, condition in zip(project.conditions, draft.conditions, strict=True):
        before = effective_condition_base_hz(project, original)
        after = effective_condition_base_hz(draft, condition)
        if before == after:
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
        previous_frames = (
            original.sequence_count * original.oddball_cycle_repeats_per_sequence
            * project.settings.protocol.oddball_every_n * frames_per_stimulus(refresh_hz, before)
        )
        assert report.frames_per_cycle is not None
        new_sequence_frames = (
            condition.sequence_count * draft.settings.protocol.oddball_every_n
            * report.frames_per_cycle
        )
        cycles, remainder = divmod(previous_frames, new_sequence_frames)
        if remainder or cycles < 1:
            lower = max(1, floor(previous_frames / new_sequence_frames))
            choices = sorted({lower, max(1, lower + 1)})
            durations = " or ".join(
                f"{count * new_sequence_frames / refresh_hz:.12g}"
                for count in choices
            )
            raise ValueError(
                f"{condition.name}: changing presentation frequency cannot preserve the "
                f"{previous_frames / refresh_hz:.12g}-second stream using complete oddball "
                f"cycles. Valid durations at this frequency: {durations} seconds."
            )
        condition.oddball_cycle_repeats_per_sequence = cycles
    validate_masking_catch_trials(draft, draft.conditions)
    issues = validate_condition_repeat_cycle_consistency(draft)
    if issues:
        raise ValueError(" ".join(issue.message for issue in issues))
    return ProjectFile.model_validate(draft.model_dump())
