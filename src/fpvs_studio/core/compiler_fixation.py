"""Fixation target-count realization and event scheduling for compilation."""

from __future__ import annotations

import random

from fpvs_studio.core.compiler_support import CompileError
from fpvs_studio.core.models import FixationTaskSettings
from fpvs_studio.core.run_spec import FixationEvent


def build_fixation_events(
    *,
    total_frames: int,
    total_event_count: int,
    target_duration_frames: int,
    min_gap_frames: int,
    rng: random.Random,
) -> list[FixationEvent]:
    """Generate balanced, seeded fixation events across one full condition run."""

    if total_event_count <= 0 or target_duration_frames <= 0 or total_frames <= 0:
        return []

    available_gap_space = total_frames - (total_event_count * target_duration_frames)
    required_minimum = (total_event_count + 1) * min_gap_frames
    if available_gap_space < required_minimum:
        raise CompileError(
            "Fixation settings do not fit within one condition run at the selected refresh rate. "
            f"Need at least {required_minimum} gap frames but only "
            f"{available_gap_space} are available "
            "after allocating fixation target durations."
        )

    first_start_frame = min_gap_frames
    last_start_frame = total_frames - min_gap_frames - target_duration_frames
    if last_start_frame < first_start_frame:
        raise CompileError(
            "Fixation settings do not fit within one condition run after reserving "
            "the minimum-gap edge buffers."
        )

    required_start_spacing = target_duration_frames + min_gap_frames
    if total_event_count == 1:
        anchor = (first_start_frame + last_start_frame) / 2
        jitter_radius = (last_start_frame - first_start_frame) * 0.25
        start_frame = _clamped_jittered_start(
            anchor=anchor,
            jitter_radius=jitter_radius,
            lower_bound=first_start_frame,
            upper_bound=last_start_frame,
            rng=rng,
        )
        return [
            FixationEvent(
                event_index=0,
                start_frame=start_frame,
                duration_frames=target_duration_frames,
            )
        ]

    anchor_step = (last_start_frame - first_start_frame) / (total_event_count - 1)
    slack_per_interval = anchor_step - required_start_spacing
    if slack_per_interval < 0:
        raise CompileError(
            "Fixation settings do not fit within one condition run after applying "
            "minimum-gap spacing between balanced target anchors."
        )

    jitter_radius = min(slack_per_interval / 2, anchor_step * 0.25)
    fixation_events: list[FixationEvent] = []
    for event_index in range(total_event_count):
        anchor = first_start_frame + (event_index * anchor_step)
        earliest_start = (
            first_start_frame
            if event_index == 0
            else fixation_events[-1].start_frame + required_start_spacing
        )
        latest_start = last_start_frame - (
            (total_event_count - event_index - 1) * required_start_spacing
        )
        lower_bound = max(earliest_start, round(anchor - jitter_radius))
        upper_bound = min(latest_start, round(anchor + jitter_radius))
        start_frame = _clamped_jittered_start(
            anchor=anchor,
            jitter_radius=jitter_radius,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            rng=rng,
        )
        fixation_events.append(
            FixationEvent(
                event_index=event_index,
                start_frame=start_frame,
                duration_frames=target_duration_frames,
            )
        )

    _validate_balanced_fixation_events(
        fixation_events,
        total_frames=total_frames,
        target_duration_frames=target_duration_frames,
        min_gap_frames=min_gap_frames,
    )
    return fixation_events


def _clamped_jittered_start(
    *,
    anchor: float,
    jitter_radius: float,
    lower_bound: int,
    upper_bound: int,
    rng: random.Random,
) -> int:
    if lower_bound > upper_bound:
        raise CompileError(
            "Fixation settings do not leave enough room for balanced seeded jitter."
        )
    if jitter_radius <= 0:
        return min(max(round(anchor), lower_bound), upper_bound)
    jittered_start = round(anchor + rng.uniform(-jitter_radius, jitter_radius))
    return min(max(jittered_start, lower_bound), upper_bound)


def _validate_balanced_fixation_events(
    fixation_events: list[FixationEvent],
    *,
    total_frames: int,
    target_duration_frames: int,
    min_gap_frames: int,
) -> None:
    previous_event: FixationEvent | None = None
    for event in fixation_events:
        if event.duration_frames != target_duration_frames:
            raise CompileError("Fixation event duration changed during scheduling.")
        if event.start_frame < min_gap_frames:
            raise CompileError("Fixation event scheduling violated the starting edge buffer.")
        if event.start_frame + event.duration_frames > total_frames - min_gap_frames:
            raise CompileError("Fixation event scheduling violated the ending edge buffer.")
        if previous_event is not None:
            previous_end = previous_event.start_frame + previous_event.duration_frames
            if event.start_frame - previous_end < min_gap_frames:
                raise CompileError(
                    "Fixation event scheduling violated the configured minimum gap."
                )
        previous_event = event


def resolve_realized_target_count(
    fixation_settings: FixationTaskSettings,
    *,
    rng: random.Random,
    previous_count: int | None,
    max_supported_count: int | None = None,
) -> int:
    """Resolve a deterministic realized fixation target count for one run."""

    if not fixation_settings.enabled:
        return 0
    if fixation_settings.target_count_mode == "fixed":
        # Backward-compatible key name; interpreted as color changes per condition.
        return fixation_settings.changes_per_sequence

    candidate_counts = list(
        range(fixation_settings.target_count_min, fixation_settings.target_count_max + 1)
    )
    if max_supported_count is not None:
        candidate_counts = [count for count in candidate_counts if count <= max_supported_count]
    if (
        fixation_settings.no_immediate_repeat_count
        and previous_count is not None
        and previous_count in candidate_counts
    ):
        candidate_counts = [count for count in candidate_counts if count != previous_count]
    if not candidate_counts:
        raise CompileError(
            "Randomized fixation target count range cannot satisfy feasibility/no-immediate-repeat "
            "constraints for this condition duration."
        )
    return rng.choice(candidate_counts)
