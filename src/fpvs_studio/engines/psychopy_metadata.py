"""Runtime metadata construction for the PsychoPy engine."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from typing import Any

from fpvs_studio.core.execution import FrameIntervalRecord, RuntimeMetadata
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.engines.psychopy_timing import TimingConfig, estimate_refresh_hz


def runtime_metadata_for_run(
    *,
    engine_name: str,
    psychopy_version: str | None,
    window: Any,
    runtime_options: Mapping[str, object],
    run_spec: RunSpec,
    frame_intervals: list[FrameIntervalRecord],
    timing_config: TimingConfig,
    warmup_intervals: list[float],
    timing_max_interval_s: float | None,
    timing_first_bad_frame_index: int | None,
    timing_strict_abort: bool,
) -> RuntimeMetadata:
    """Build neutral runtime metadata for one completed run."""

    measured_refresh_hz = estimate_refresh_hz(
        [interval.interval_s for interval in frame_intervals],
        fallback_intervals=warmup_intervals,
    )

    size = getattr(window, "size", None)
    width = int(size[0]) if size is not None else None
    height = int(size[1]) if size is not None else None
    monitor = getattr(window, "monitor", None)
    monitor_name = (
        monitor.getName() if monitor is not None and hasattr(monitor, "getName") else None
    )
    display_index = runtime_options.get("display_index")
    if not isinstance(display_index, int):
        display_index = None

    return RuntimeMetadata(
        engine_name=engine_name,
        engine_version=psychopy_version,
        python_version=sys.version.split()[0],
        display_index=display_index,
        monitor_name=monitor_name,
        screen_width_px=width,
        screen_height_px=height,
        fullscreen=bool(runtime_options.get("fullscreen", True)),
        requested_refresh_hz=run_spec.display.refresh_hz,
        actual_refresh_hz=measured_refresh_hz,
        frame_interval_recording=True,
        test_mode=bool(runtime_options.get("test_mode")),
        timing_qc_expected_interval_s=timing_config.expected_interval_s,
        timing_qc_threshold_interval_s=timing_config.miss_threshold_s,
        timing_qc_warmup_frames=timing_config.warmup_frames,
        timing_qc_measured_refresh_hz=measured_refresh_hz,
        timing_qc_max_interval_s=timing_max_interval_s,
        timing_qc_first_bad_frame_index=timing_first_bad_frame_index,
        timing_qc_strict_abort=timing_strict_abort,
    )
