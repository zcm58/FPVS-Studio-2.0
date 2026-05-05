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
    max_gap_frames: int,
) -> list[FixationEvent]:
    """Generate deterministic, non-overlapping fixation events for one run."""

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

    preferred_gap = available_gap_space // (total_event_count + 1)
    gap_frames = min(max_gap_frames, max(min_gap_frames, preferred_gap))
    fixation_events: list[FixationEvent] = []
    current_start = gap_frames
    for event_index in range(total_event_count):
        if current_start + target_duration_frames > total_frames:
            raise CompileError(
                "Fixation event scheduling exceeded the condition duration after "
                "applying spacing constraints."
            )
        fixation_events.append(
            FixationEvent(
                event_index=event_index,
                start_frame=current_start,
                duration_frames=target_duration_frames,
            )
        )
        current_start += target_duration_frames + gap_frames

    return fixation_events


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
