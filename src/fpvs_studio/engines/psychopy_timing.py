"""Timing helpers for the PsychoPy engine."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from fpvs_studio.core.run_spec import RunSpec

WARMUP_SETTLE_FRAMES = 30
WARMUP_SEVERE_MISS_MULTIPLIER = 2.0


@dataclass(frozen=True)
class TimingConfig:
    strict_timing: bool
    strict_timing_warmup: bool
    expected_interval_s: float
    miss_threshold_multiplier: float
    miss_threshold_s: float
    warmup_frames: int
    warmup_settle_frames: int
    severe_miss_threshold_s: float


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
        severe_miss_threshold_s=expected_interval_s * WARMUP_SEVERE_MISS_MULTIPLIER,
    )


def timing_abort_reason(
    *,
    phase: str,
    frame_index: int,
    interval_s: float,
    timing_config: TimingConfig,
) -> str:
    """Build the strict-timing abort message."""

    return (
        "Strict timing aborted run during "
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
