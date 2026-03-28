"""PsychoPy-backed renderer for compiled FPVS runs.
It lazily imports PsychoPy and executes one RunSpec at a time while honoring runtime-owned transition, feedback, and trigger seams.
This module owns presentation details only; session flow, fixation scoring, and neutral export contracts stay outside the engine."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys

from fpvs_studio.core.enums import EngineName, RunMode
from fpvs_studio.core.execution import FrameIntervalRecord, ResponseRecord, RunExecutionSummary, RuntimeMetadata
from fpvs_studio.core.run_spec import FixationEvent, RunSpec, StimulusEvent
from fpvs_studio.engines.base import PresentationEngine
from fpvs_studio.triggers.base import TriggerBackend

WARMUP_SETTLE_FRAMES = 30
WARMUP_SEVERE_MISS_MULTIPLIER = 2.0


@dataclass(frozen=True)
class _TimingConfig:
    strict_timing: bool
    strict_timing_warmup: bool
    expected_interval_s: float
    miss_threshold_multiplier: float
    miss_threshold_s: float
    warmup_frames: int
    warmup_settle_frames: int
    severe_miss_threshold_s: float


class PsychoPyEngine(PresentationEngine):
    """PsychoPy-backed presentation engine."""

    def __init__(self) -> None:
        self._psychopy: object | None = None
        self._visual: object | None = None
        self._core: object | None = None
        self._keyboard_module: object | None = None
        self._window: object | None = None
        self._keyboard: object | None = None
        self._runtime_options: dict[str, object] = {}
        self._image_stim_cache: dict[str, object] = {}
        self._aborted = False
        self._active_run_clock: object | None = None

    @property
    def engine_id(self) -> str:
        return EngineName.PSYCHOPY.value

    def probe_displays(self) -> list[dict[str, object]]:
        try:
            psychopy = self._load_psychopy()
        except RuntimeError:
            return []

        monitors = getattr(psychopy, "monitors", None)
        if monitors is None or not hasattr(monitors, "getAllMonitors"):
            return []
        return [{"monitor_name": name} for name in monitors.getAllMonitors()]

    def open_session(
        self,
        *,
        runtime_options: Mapping[str, object] | None = None,
    ) -> None:
        if self._window is not None:
            self._runtime_options = dict(runtime_options or {})
            return

        psychopy = self._load_psychopy()
        visual = getattr(psychopy, "visual")
        keyboard_module = getattr(getattr(psychopy, "hardware"), "keyboard")

        self._runtime_options = dict(runtime_options or {})
        test_mode = bool(self._runtime_options.get("test_mode"))
        fullscreen = bool(self._runtime_options.get("fullscreen", True))
        display_index = self._runtime_options.get("display_index")
        window_kwargs: dict[str, object] = {
            "fullscr": fullscreen,
            "screen": display_index if isinstance(display_index, int) else 0,
            "allowGUI": not fullscreen,
            "waitBlanking": True,
            "color": "black",
            "units": "pix",
        }
        if test_mode and not fullscreen:
            window_kwargs["size"] = [1280, 720]

        self._window = visual.Window(**window_kwargs)
        setattr(self._window, "recordFrameIntervals", True)
        self._keyboard = keyboard_module.Keyboard()
        self._keyboard.clearEvents()
        self._aborted = False

    def show_transition_screen(
        self,
        *,
        heading: str,
        body: str | None = None,
        countdown_seconds: float | None = None,
        continue_key: str | None = None,
    ) -> bool:
        return self._show_text_screen(
            heading=heading,
            body=body,
            countdown_seconds=countdown_seconds,
            continue_key=continue_key,
        )

    def show_block_break_screen(
        self,
        *,
        completed_block_index: int,
        total_block_count: int,
        next_block_index: int,
    ) -> bool:
        heading = f"Block {completed_block_index + 1} of {total_block_count} complete."
        body = f"Press Space to continue to Block {next_block_index + 1}."
        return self._show_text_screen(
            heading=heading,
            body=body,
            countdown_seconds=None,
            continue_key="space",
        )

    def show_condition_feedback_screen(
        self,
        *,
        heading: str,
        body: str,
        continue_key: str,
    ) -> bool:
        return self._show_text_screen(
            heading=heading,
            body=body,
            countdown_seconds=None,
            continue_key=continue_key,
        )

    def run_condition(
        self,
        run_spec: RunSpec,
        project_root: Path,
        *,
        runtime_options: Mapping[str, object] | None = None,
        trigger_backend: TriggerBackend | None = None,
    ) -> RunExecutionSummary:
        self.open_session(runtime_options=runtime_options)
        self._aborted = False
        started_at = datetime.now(timezone.utc)

        visual = self._require_visual()
        core = self._require_core()
        window = self._require_window()
        keyboard = self._require_keyboard()
        self._runtime_options = dict(runtime_options or {})
        timing_config = self._timing_config_for_run(run_spec)
        abort_reason: str | None = None
        timing_first_bad_frame_index: int | None = None
        timing_max_interval_s: float | None = None
        timing_strict_abort = False
        warmup_intervals: list[float] = []

        absolute_paths = {
            event.image_path: project_root / Path(event.image_path) for event in run_spec.stimulus_sequence
        }
        stimuli = self._prepare_stimuli(absolute_paths)
        fixation_stim = visual.ShapeStim(
            window,
            vertices=(
                (0, -(run_spec.fixation.cross_size_px // 2)),
                (0, run_spec.fixation.cross_size_px // 2),
                (0, 0),
                (-(run_spec.fixation.cross_size_px // 2), 0),
                (run_spec.fixation.cross_size_px // 2, 0),
            ),
            closeShape=False,
            lineWidth=run_spec.fixation.line_width_px,
            lineColor=run_spec.fixation.default_color,
            fillColor=None,
            autoLog=False,
        )
        keyboard.clock.reset()
        keyboard.clearEvents()
        setattr(window, "color", run_spec.display.background_color)
        setattr(window, "recordFrameIntervals", True)
        if hasattr(window, "frameIntervals"):
            setattr(window, "frameIntervals", [])

        self._active_run_clock = core.Clock()
        warmup_last_flip_time: float | None = None
        warmup_miss_count = 0
        warmup_strict_timing_enabled = (
            timing_config.strict_timing and timing_config.strict_timing_warmup
        )
        for warmup_frame_index in range(timing_config.warmup_frames):
            flip_time = window.flip()
            current_time_s = (
                float(flip_time) if flip_time is not None else self._active_run_clock.getTime()
            )
            if warmup_last_flip_time is not None:
                warmup_interval_index = warmup_frame_index - 1
                interval_s = current_time_s - warmup_last_flip_time
                warmup_intervals.append(interval_s)
                timing_max_interval_s = (
                    interval_s
                    if timing_max_interval_s is None
                    else max(timing_max_interval_s, interval_s)
                )
                if (
                    timing_first_bad_frame_index is None
                    and interval_s > timing_config.miss_threshold_s
                ):
                    timing_first_bad_frame_index = warmup_interval_index
                post_settle_window = (
                    warmup_frame_index >= timing_config.warmup_settle_frames
                )
                interval_is_miss = interval_s > timing_config.miss_threshold_s
                interval_is_severe = interval_s > timing_config.severe_miss_threshold_s
                if warmup_strict_timing_enabled and post_settle_window and interval_is_miss:
                    warmup_miss_count += 1
                if warmup_strict_timing_enabled and post_settle_window and (
                    interval_is_severe or warmup_miss_count >= 2
                ):
                    timing_strict_abort = True
                    self._aborted = True
                    abort_reason = self._timing_abort_reason(
                        phase="warmup",
                        frame_index=warmup_interval_index,
                        interval_s=interval_s,
                        timing_config=timing_config,
                    )
                    break
            warmup_last_flip_time = current_time_s

        keyboard.clock.reset()
        keyboard.clearEvents()
        stimulus_index = 0
        fixation_index = 0
        completed_frames = 0
        last_flip_time: float | None = None
        frame_intervals: list[FrameIntervalRecord] = []
        response_log: list[ResponseRecord] = []
        trigger_log: list[object] = []
        trigger_event_lookup = self._build_trigger_lookup(run_spec)

        for frame_index in range(run_spec.display.total_frames):
            if self._aborted:
                break

            while (
                stimulus_index + 1 < len(run_spec.stimulus_sequence)
                and run_spec.stimulus_sequence[stimulus_index + 1].on_start_frame <= frame_index
            ):
                stimulus_index += 1

            stimulus_event = (
                run_spec.stimulus_sequence[stimulus_index] if run_spec.stimulus_sequence else None
            )
            if self._should_draw_stimulus(stimulus_event, frame_index):
                stimuli[stimulus_event.image_path].draw()

            while (
                fixation_index + 1 < len(run_spec.fixation_events)
                and run_spec.fixation_events[fixation_index + 1].start_frame <= frame_index
            ):
                fixation_index += 1
            fixation_stim.lineColor = self._fixation_color_for_frame(
                run_spec.fixation_events,
                run_spec.fixation.default_color,
                run_spec.fixation.target_color,
                fixation_index,
                frame_index,
            )
            fixation_stim.draw()

            for trigger_event in trigger_event_lookup.get(frame_index, ()):
                if trigger_backend is not None:
                    window.callOnFlip(
                        self._emit_trigger,
                        trigger_backend,
                        trigger_event.code,
                        trigger_event.label,
                        frame_index,
                    )

            flip_time = window.flip()
            current_time_s = float(flip_time) if flip_time is not None else self._active_run_clock.getTime()
            if last_flip_time is not None:
                interval_s = current_time_s - last_flip_time
                frame_intervals.append(
                    FrameIntervalRecord(
                        frame_index=frame_index - 1,
                        interval_s=interval_s,
                    )
                )
                timing_max_interval_s = (
                    interval_s
                    if timing_max_interval_s is None
                    else max(timing_max_interval_s, interval_s)
                )
                if (
                    timing_first_bad_frame_index is None
                    and interval_s > timing_config.miss_threshold_s
                ):
                    timing_first_bad_frame_index = frame_index - 1
                if timing_config.strict_timing and interval_s > timing_config.miss_threshold_s:
                    timing_strict_abort = True
                    self._aborted = True
                    abort_reason = self._timing_abort_reason(
                        phase="run",
                        frame_index=frame_index - 1,
                        interval_s=interval_s,
                        timing_config=timing_config,
                    )
            last_flip_time = current_time_s
            completed_frames = frame_index + 1

            if self._aborted:
                break

            keys = keyboard.getKeys(
                keyList=list(run_spec.fixation.response_keys) + ["escape"],
                waitRelease=False,
                clear=True,
            )
            for key in keys:
                key_name = getattr(key, "name", str(key))
                if key_name == "escape":
                    self._aborted = True
                    if abort_reason is None:
                        abort_reason = "Escape pressed during condition playback."
                    break
                key_time = getattr(key, "rt", None)
                response_log.append(
                    ResponseRecord(
                        response_index=len(response_log),
                        key=key_name,
                        frame_index=frame_index,
                        time_s=(
                            float(key_time)
                            if key_time is not None
                            else self._active_run_clock.getTime()
                        ),
                    )
                )
            if self._aborted:
                break

        finished_at = datetime.now(timezone.utc)
        runtime_metadata = self._runtime_metadata_for_run(
            run_spec,
            frame_intervals,
            timing_config=timing_config,
            warmup_intervals=warmup_intervals,
            timing_max_interval_s=timing_max_interval_s,
            timing_first_bad_frame_index=timing_first_bad_frame_index,
            timing_strict_abort=timing_strict_abort,
        )
        self._active_run_clock = None
        return RunExecutionSummary(
            project_id=run_spec.project_id,
            session_id=None,
            run_id=run_spec.run_id,
            condition_id=run_spec.condition.condition_id,
            condition_name=run_spec.condition.name,
            engine_name=self.engine_id,
            run_mode=(
                RunMode.TEST if bool((runtime_options or {}).get("test_mode")) else RunMode.SESSION
            ),
            started_at=started_at,
            finished_at=finished_at,
            completed_frames=completed_frames,
            aborted=self._aborted,
            abort_reason=abort_reason if self._aborted else None,
            runtime_metadata=runtime_metadata,
            frame_intervals=frame_intervals,
            fixation_responses=[],
            response_log=response_log,
            trigger_log=trigger_log,
        )

    def show_completion_screen(
        self,
        *,
        completed_condition_count: int,
        total_condition_count: int,
        was_aborted: bool,
    ) -> bool:
        heading = "Session aborted" if was_aborted else "Session complete"
        body = (
            f"Completed {completed_condition_count} of {total_condition_count} conditions."
            if was_aborted
            else f"Completed all {total_condition_count} conditions."
        )
        countdown_seconds = 0.5 if bool(self._runtime_options.get("test_mode")) else 2.0
        return self._show_text_screen(
            heading=heading,
            body=body,
            countdown_seconds=countdown_seconds,
            continue_key=None,
        )

    def close_session(self) -> None:
        window = self._window
        self._window = None
        self._keyboard = None
        self._image_stim_cache = {}
        self._active_run_clock = None
        if window is not None:
            window.close()

    def abort(self) -> None:
        self._aborted = True

    def _build_trigger_lookup(self, run_spec: RunSpec) -> dict[int, tuple[object, ...]]:
        trigger_lookup: dict[int, list[object]] = {}
        for trigger_event in run_spec.trigger_events:
            trigger_lookup.setdefault(trigger_event.frame_index, []).append(trigger_event)
        return {frame_index: tuple(events) for frame_index, events in trigger_lookup.items()}

    def _emit_trigger(
        self,
        trigger_backend: TriggerBackend,
        code: int,
        label: str,
        frame_index: int,
    ) -> None:
        time_s = self._active_run_clock.getTime() if self._active_run_clock is not None else None
        trigger_backend.send_trigger(
            code,
            frame_index=frame_index,
            label=label,
            time_s=time_s,
        )

    def _fixation_color_for_frame(
        self,
        fixation_events: list[FixationEvent],
        default_color: str,
        target_color: str,
        fixation_index: int,
        frame_index: int,
    ) -> str:
        if not fixation_events:
            return default_color
        fixation_event = fixation_events[fixation_index]
        if fixation_event.start_frame <= frame_index < (
            fixation_event.start_frame + fixation_event.duration_frames
        ):
            return target_color
        return default_color

    def _prepare_stimuli(self, absolute_paths: Mapping[str, Path]) -> dict[str, object]:
        visual = self._require_visual()
        window = self._require_window()
        for relative_path, absolute_path in absolute_paths.items():
            if relative_path not in self._image_stim_cache:
                self._image_stim_cache[relative_path] = visual.ImageStim(
                    window,
                    image=str(absolute_path),
                    autoLog=False,
                )
        return {path: self._image_stim_cache[path] for path in absolute_paths}

    def _runtime_metadata_for_run(
        self,
        run_spec: RunSpec,
        frame_intervals: list[FrameIntervalRecord],
        *,
        timing_config: _TimingConfig,
        warmup_intervals: list[float],
        timing_max_interval_s: float | None,
        timing_first_bad_frame_index: int | None,
        timing_strict_abort: bool,
    ) -> RuntimeMetadata:
        window = self._require_window()
        measured_refresh_hz = self._estimate_refresh_hz(
            [interval.interval_s for interval in frame_intervals],
            fallback_intervals=warmup_intervals,
        )

        size = getattr(window, "size", None)
        width = int(size[0]) if size is not None else None
        height = int(size[1]) if size is not None else None
        monitor = getattr(window, "monitor", None)
        monitor_name = monitor.getName() if monitor is not None and hasattr(monitor, "getName") else None
        psychopy = self._load_psychopy()

        return RuntimeMetadata(
            engine_name=self.engine_id,
            engine_version=getattr(psychopy, "__version__", None),
            python_version=sys.version.split()[0],
            display_index=self._runtime_options.get("display_index")
            if isinstance(self._runtime_options.get("display_index"), int)
            else None,
            monitor_name=monitor_name,
            screen_width_px=width,
            screen_height_px=height,
            fullscreen=bool(self._runtime_options.get("fullscreen", True)),
            requested_refresh_hz=run_spec.display.refresh_hz,
            actual_refresh_hz=measured_refresh_hz,
            frame_interval_recording=True,
            test_mode=bool(self._runtime_options.get("test_mode")),
            timing_qc_expected_interval_s=timing_config.expected_interval_s,
            timing_qc_threshold_interval_s=timing_config.miss_threshold_s,
            timing_qc_warmup_frames=timing_config.warmup_frames,
            timing_qc_measured_refresh_hz=measured_refresh_hz,
            timing_qc_max_interval_s=timing_max_interval_s,
            timing_qc_first_bad_frame_index=timing_first_bad_frame_index,
            timing_qc_strict_abort=timing_strict_abort,
        )

    def _timing_config_for_run(self, run_spec: RunSpec) -> _TimingConfig:
        strict_timing = bool(self._runtime_options.get("strict_timing", True))
        strict_timing_warmup = bool(self._runtime_options.get("strict_timing_warmup", True))
        expected_interval_s = 1.0 / run_spec.display.refresh_hz
        raw_multiplier = self._runtime_options.get("timing_miss_threshold_multiplier", 1.5)
        multiplier = (
            float(raw_multiplier)
            if isinstance(raw_multiplier, (int, float)) and raw_multiplier > 1.0
            else 1.5
        )
        raw_warmup_frames = self._runtime_options.get("timing_warmup_frames", 240)
        warmup_frames = (
            raw_warmup_frames if isinstance(raw_warmup_frames, int) and raw_warmup_frames >= 0 else 240
        )
        return _TimingConfig(
            strict_timing=strict_timing,
            strict_timing_warmup=strict_timing_warmup,
            expected_interval_s=expected_interval_s,
            miss_threshold_multiplier=multiplier,
            miss_threshold_s=expected_interval_s * multiplier,
            warmup_frames=warmup_frames,
            warmup_settle_frames=min(WARMUP_SETTLE_FRAMES, warmup_frames),
            severe_miss_threshold_s=expected_interval_s * WARMUP_SEVERE_MISS_MULTIPLIER,
        )

    def _timing_abort_reason(
        self,
        *,
        phase: str,
        frame_index: int,
        interval_s: float,
        timing_config: _TimingConfig,
    ) -> str:
        return (
            "Strict timing aborted run during "
            f"{phase}: frame interval at index {frame_index} was {interval_s:.6f} s, "
            f"exceeding {timing_config.miss_threshold_multiplier:.2f}x expected "
            f"{timing_config.expected_interval_s:.6f} s."
        )

    def _estimate_refresh_hz(
        self,
        intervals: list[float],
        *,
        fallback_intervals: list[float] | None = None,
    ) -> float | None:
        source_intervals = [interval for interval in intervals if interval > 0]
        if not source_intervals and fallback_intervals is not None:
            source_intervals = [interval for interval in fallback_intervals if interval > 0]
        if not source_intervals:
            return None
        return 1.0 / (sum(source_intervals) / len(source_intervals))

    def _should_draw_stimulus(
        self,
        stimulus_event: StimulusEvent | None,
        frame_index: int,
    ) -> bool:
        if stimulus_event is None:
            return False
        local_frame = frame_index - stimulus_event.on_start_frame
        return 0 <= local_frame < stimulus_event.on_frames

    def _show_text_screen(
        self,
        *,
        heading: str,
        body: str | None,
        countdown_seconds: float | None,
        continue_key: str | None,
    ) -> bool:
        self.open_session(runtime_options=self._runtime_options)
        visual = self._require_visual()
        core = self._require_core()
        window = self._require_window()
        keyboard = self._require_keyboard()
        keyboard.clearEvents()
        screen_clock = core.Clock()

        while True:
            if self._aborted:
                return True

            footer = ""
            if continue_key is not None:
                footer = f"Press '{continue_key}' to continue. Press Escape to abort."
            elif countdown_seconds is not None:
                remaining = max(0.0, countdown_seconds - screen_clock.getTime())
                footer = f"Starting automatically in {remaining:0.1f} s. Press Escape to abort."
            else:
                footer = "Press Escape to abort."

            visual.TextStim(
                window,
                text=heading,
                height=36,
                pos=(0, 140),
                wrapWidth=1200,
                color="white",
                autoLog=False,
            ).draw()
            if body:
                visual.TextStim(
                    window,
                    text=body,
                    height=28,
                    pos=(0, 10),
                    wrapWidth=1200,
                    color="white",
                    autoLog=False,
                ).draw()
            visual.TextStim(
                window,
                text=footer,
                height=24,
                pos=(0, -220),
                wrapWidth=1200,
                color="white",
                autoLog=False,
            ).draw()
            window.flip()

            keys = keyboard.getKeys(
                keyList=[key for key in [continue_key, "escape"] if key is not None],
                waitRelease=False,
                clear=True,
            )
            for key in keys:
                key_name = getattr(key, "name", str(key))
                if key_name == "escape":
                    self._aborted = True
                    return True
                if continue_key is not None and key_name == continue_key:
                    return False

            if countdown_seconds is not None and screen_clock.getTime() >= countdown_seconds:
                return False

    def _load_psychopy(self) -> object:
        if self._psychopy is not None:
            return self._psychopy

        try:
            import psychopy  # type: ignore[import-not-found]
            from psychopy import core, visual  # type: ignore[import-not-found]
            from psychopy.hardware import keyboard  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - exercised by import-boundary tests
            raise RuntimeError(
                "PsychoPy is not installed. Install the optional 'engine' dependencies to use this engine."
            ) from exc

        self._psychopy = psychopy
        self._visual = visual
        self._core = core
        self._keyboard_module = keyboard
        return psychopy

    def _require_core(self) -> object:
        self._load_psychopy()
        return self._core

    def _require_visual(self) -> object:
        self._load_psychopy()
        return self._visual

    def _require_window(self) -> object:
        if self._window is None:
            raise RuntimeError("PsychoPy session window has not been opened.")
        return self._window

    def _require_keyboard(self) -> object:
        if self._keyboard is None:
            raise RuntimeError("PsychoPy keyboard has not been initialized.")
        return self._keyboard
