"""Small helpers for frame-based FPVS timing validation."""

from __future__ import annotations

import math

from fpvs_studio.core.enums import DutyCycleMode

FRAME_TOLERANCE = 1e-6


class FrameValidationError(ValueError):
    """Raised when a refresh rate cannot support the locked FPVS timing."""


def frames_per_stimulus(
    refresh_hz: float,
    base_hz: float,
    *,
    tolerance: float = FRAME_TOLERANCE,
) -> int:
    """Return the integer frames per 6 Hz stimulus or raise on incompatibility."""

    raw_frames = refresh_hz / base_hz
    nearest = round(raw_frames)
    if not math.isclose(raw_frames, nearest, abs_tol=tolerance):
        raise FrameValidationError(
            f"Refresh rate {refresh_hz:g} Hz is incompatible with {base_hz:g} Hz FPVS timing."
        )
    return int(nearest)


def validate_blank_mode_frames(frames_per_stimulus_value: int) -> None:
    """Enforce the even-frame requirement for 50% blank mode."""

    if frames_per_stimulus_value % 2 != 0:
        raise FrameValidationError(
            "Duty cycle 'blank_50' requires an even number of frames per 6 Hz cycle."
        )


def on_off_frames(
    frames_per_stimulus_value: int,
    duty_cycle_mode: DutyCycleMode,
) -> tuple[int, int]:
    """Derive stimulus on/off frames from the configured duty-cycle mode."""

    if duty_cycle_mode == DutyCycleMode.CONTINUOUS:
        return frames_per_stimulus_value, 0
    validate_blank_mode_frames(frames_per_stimulus_value)
    half_cycle = frames_per_stimulus_value // 2
    return half_cycle, half_cycle
