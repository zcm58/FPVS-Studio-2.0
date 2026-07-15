"""Low-level frame-timing helpers for FPVS display compatibility. Core validation and
compilation use these utilities to derive per-cycle frame counts and duty-cycle on/off
splits before RunSpec emission. This module owns timing arithmetic only, not project
validation policy, session planning, or runtime launch checks."""

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
    """Resolve a positive requested cadence to the nearest whole-frame duration."""

    raw_frames = refresh_hz / base_hz
    if raw_frames < 1.0 and not math.isclose(raw_frames, 1.0, abs_tol=tolerance):
        raise FrameValidationError(
            f"Base rate {base_hz:g} Hz is faster than the {refresh_hz:g} Hz display; "
            "each stimulus requires at least one display frame."
        )
    nearest = math.floor(raw_frames + 0.5)
    return max(1, nearest)


def validate_blank_mode_frames(frames_per_stimulus_value: int) -> None:
    """Enforce the even-frame requirement for 50% blank mode."""

    if frames_per_stimulus_value % 2 != 0:
        raise FrameValidationError(
            "Duty cycle 'blank_50' requires an even number of frames per stimulus cycle."
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
