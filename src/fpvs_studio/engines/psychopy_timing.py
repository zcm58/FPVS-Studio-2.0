"""Timing helpers for the PsychoPy engine."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

from fpvs_studio.core.run_spec import RunSpec

WARMUP_SETTLE_FRAMES = 30


def measure_window_refresh_hz(window: Any) -> float:
    """Measure a PsychoPy window's stable actual frame rate."""

    get_actual_frame_rate = getattr(window, "getActualFrameRate", None)
    if not callable(get_actual_frame_rate):
        raise RuntimeError("PsychoPy cannot measure the connected display refresh rate.")
    measured = get_actual_frame_rate(
        nIdentical=20,
        nMaxFrames=240,
        nWarmUpFrames=60,
        threshold=0.5,
        infoMsg="FPVS Studio is measuring this display's refresh rate...",
    )
    if measured is None:
        raise RuntimeError(
            "PsychoPy could not obtain a stable display refresh measurement. "
            "Close other graphics-intensive applications and try again."
        )
    try:
        measured_hz = float(measured)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("PsychoPy returned an invalid display refresh measurement.") from exc
    if not isfinite(measured_hz) or measured_hz <= 0:
        raise RuntimeError("PsychoPy returned an invalid display refresh measurement.")
    return measured_hz


@dataclass(frozen=True)
class TimingConfig:
    strict_timing: bool
    strict_timing_warmup: bool
    expected_interval_s: float
    miss_threshold_multiplier: float
    miss_threshold_s: float
    warmup_frames: int
    warmup_settle_frames: int


def timing_config_for_run(
    run_spec: RunSpec,
    runtime_options: Mapping[str, object],
) -> TimingConfig:
    """Resolve runtime timing-QC settings for one run."""

    strict_timing = bool(runtime_options.get("strict_timing", True))
    strict_timing_warmup = bool(runtime_options.get("strict_timing_warmup", True))
    expected_interval_s = 1.0 / run_spec.display.refresh_hz
    raw_multiplier = runtime_options.get("timing_miss_threshold_multiplier", 1.5)
    multiplier = (
        float(raw_multiplier)
        if isinstance(raw_multiplier, (int, float)) and raw_multiplier > 1.0
        else 1.5
    )
    raw_warmup_frames = runtime_options.get("timing_warmup_frames", 240)
    warmup_frames = (
        raw_warmup_frames if isinstance(raw_warmup_frames, int) and raw_warmup_frames >= 0 else 240
    )
    return TimingConfig(
        strict_timing=strict_timing,
        strict_timing_warmup=strict_timing_warmup,
        expected_interval_s=expected_interval_s,
        miss_threshold_multiplier=multiplier,
        miss_threshold_s=expected_interval_s * multiplier,
        warmup_frames=warmup_frames,
        warmup_settle_frames=min(WARMUP_SETTLE_FRAMES, warmup_frames),
    )


def timing_violation_reason(
    *,
    phase: str,
    frame_index: int,
    interval_s: float,
    timing_config: TimingConfig,
) -> str:
    """Build the strict-timing violation message."""

    return (
        "Strict timing QC flagged playback during "
        f"{phase}: frame interval at index {frame_index} was {interval_s:.6f} s, "
        f"exceeding {timing_config.miss_threshold_multiplier:.2f}x expected "
        f"{timing_config.expected_interval_s:.6f} s."
    )


def estimate_refresh_hz(
    intervals: list[float],
    *,
    fallback_intervals: list[float] | None = None,
) -> float | None:
    """Estimate measured refresh rate from frame intervals."""

    source_intervals = [interval for interval in intervals if interval > 0]
    if not source_intervals and fallback_intervals is not None:
        source_intervals = [interval for interval in fallback_intervals if interval > 0]
    if not source_intervals:
        return None
    return 1.0 / (sum(source_intervals) / len(source_intervals))
