"""Shared fixation-task planning helpers used by compiler and validation."""

from __future__ import annotations

import math


def milliseconds_to_frames(milliseconds: int, refresh_hz: float) -> int:
    """Convert a millisecond duration to a positive frame count when needed."""

    if milliseconds <= 0:
        return 0
    return max(1, math.ceil((milliseconds / 1000.0) * refresh_hz))


def seconds_to_frames(seconds: float, refresh_hz: float) -> int:
    """Convert a second duration to a positive frame count when needed."""

    if seconds <= 0:
        return 0
    return max(1, math.ceil(seconds * refresh_hz))


def required_fixation_frames(
    *,
    color_change_count: int,
    target_duration_frames: int,
    min_gap_frames: int,
) -> int:
    """Return minimum frames required to fit color changes within one condition run."""

    if color_change_count <= 0:
        return min_gap_frames
    return (color_change_count * target_duration_frames) + (
        (color_change_count + 1) * min_gap_frames
    )


def max_supported_color_changes(
    *,
    total_frames: int,
    target_duration_frames: int,
    min_gap_frames: int,
) -> int:
    """Return max color changes that fit one condition run under min-gap rules."""

    if total_frames <= 0 or target_duration_frames <= 0:
        return 0
    if total_frames < min_gap_frames:
        return 0
    return max(0, (total_frames - min_gap_frames) // (target_duration_frames + min_gap_frames))


def minimum_cycles_required(
    *,
    required_frames: int,
    frames_per_stimulus: int,
    oddball_every_n: int,
    condition_repeat_count: int,
) -> tuple[int, int]:
    """Return minimum oddball cycles needed as total and per-condition-repeat counts."""

    frames_per_cycle = frames_per_stimulus * oddball_every_n
    minimum_total_cycles = max(1, math.ceil(required_frames / frames_per_cycle))
    minimum_cycles_per_repeat = max(
        1,
        math.ceil(minimum_total_cycles / max(1, condition_repeat_count)),
    )
    return minimum_total_cycles, minimum_cycles_per_repeat
