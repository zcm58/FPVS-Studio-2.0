"""PsychoPy-backed renderer for compiled FPVS runs. It lazily imports PsychoPy and executes
one RunSpec at a time while honoring runtime-owned transition, feedback, and trigger
seams. This module owns presentation details only; session flow, fixation scoring, and
neutral export contracts stay outside the engine."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fpvs_studio.core.enums import EngineName, RunMode
from fpvs_studio.core.execution import (
    FrameIntervalRecord,
    ResponseRecord,
    RunExecutionSummary,
    RuntimeMetadata,
    TriggerRecord,
)
from fpvs_studio.core.run_spec import FixationEvent, RunSpec, TriggerEvent
from fpvs_studio.engines.base import FixationTutorialAttemptResult, PresentationEngine
from fpvs_studio.engines.psychopy_loader import load_psychopy_modules
from fpvs_studio.engines.psychopy_metadata import runtime_metadata_for_run
from fpvs_studio.engines.psychopy_stimuli import (
    fixation_color_for_frame,
    prepare_stimuli,
    release_stimuli,
    should_draw_stimulus,
)
from fpvs_studio.engines.psychopy_text_screens import show_text_screen
from fpvs_studio.engines.psychopy_timing import (
    TimingConfig,
    timing_config_for_run,
    timing_violation_reason,
)
from fpvs_studio.engines.psychopy_triggers import build_trigger_lookup, emit_trigger
from fpvs_studio.engines.psychopy_window import build_window_kwargs, create_fixation_stim
from fpvs_studio.triggers.base import TriggerBackend

LOGGER = logging.getLogger(__name__)
TIMING_DIAGNOSTIC_THRESHOLD_MULTIPLIER = 1.5


class PsychoPyEngine(PresentationEngine):
    """PsychoPy-backed presentation engine."""

    def __init__(self) -> None:
        self._psychopy: Any | None = None
        self._visual: Any | None = None
        self._core: Any | None = None
        self._keyboard_module: Any | None = None
        self._psychopy_logging: Any | None = None
        self._window: Any | None = None
        self._keyboard: Any | None = None
        self._runtime_options: dict[str, object] = {}
        self._aborted = False
        self._active_run_clock: Any | None = None

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
        visual = psychopy.visual
        keyboard_module = psychopy.hardware.keyboard

        self._runtime_options = dict(runtime_options or {})
        self._window = visual.Window(**build_window_kwargs(self._runtime_options))
        self._window.recordFrameIntervals = True
        self._keyboard = keyboard_module.Keyboard()
        self._keyboard.clearEvents()
        self._aborted = False

    def current_display_size_px(self) -> tuple[int, int] | None:
        window = self._window
        if window is None:
            return None
        size = getattr(window, "size", None)
        if not isinstance(size, (list, tuple)) or len(size) < 2:
            return None
        return (max(1, int(size[0])), max(1, int(size[1])))

    def show_transition_screen(
        self,
        *,
        heading: str,
        body: str | None = None,
        countdown_seconds: float | None = None,
        continue_key: str | None = None,
        continue_prompt: str | None = None,
    ) -> bool:
        return self._show_text_screen(
            heading=heading,
            body=body,
            countdown_seconds=countdown_seconds,
            continue_key=continue_key,
            continue_prompt=continue_prompt,
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
            continue_prompt=None,
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
            continue_prompt=None,
        )

    def run_fixation_tutorial_attempt(
        self,
        run_spec: RunSpec,
        *,
        target_delay_seconds: float,
    ) -> FixationTutorialAttemptResult:
        self.open_session(runtime_options=self._runtime_options)
        visual = self._require_visual()
        window = self._require_window()
        keyboard = self._require_keyboard()
        fixation_stim = create_fixation_stim(visual=visual, window=window, run_spec=run_spec)
        target_delay_frames = max(
            1,
            round(float(target_delay_seconds) * float(run_spec.display.refresh_hz)),
        )
        response_window_frames = max(1, run_spec.fixation.response_window_frames)
        response_key = run_spec.fixation.response_key
        key_list = [response_key, "escape"]
        previous_record_frame_intervals = bool(getattr(window, "recordFrameIntervals", False))
        window.recordFrameIntervals = False
        if hasattr(window, "frameIntervals"):
            window.frameIntervals = []
        try:
            keyboard.clearEvents()
            fixation_stim.lineColor = run_spec.fixation.default_color
            for _frame_index in range(target_delay_frames):
                if self._aborted:
                    return FixationTutorialAttemptResult(hit=False, aborted=True)
                fixation_stim.draw()
                window.flip()
                if self._tutorial_escape_pressed(keyboard, key_list=key_list):
                    return FixationTutorialAttemptResult(hit=False, aborted=True)

            keyboard.clock.reset()
            keyboard.clearEvents()
            fixation_stim.lineColor = run_spec.fixation.target_color
            for frame_index in range(response_window_frames):
                if self._aborted:
                    return FixationTutorialAttemptResult(hit=False, aborted=True)
                fixation_stim.draw()
                window.flip()
                keys = keyboard.getKeys(
                    keyList=key_list,
                    waitRelease=False,
                    clear=True,
                )
                for key in keys:
                    key_name = getattr(key, "name", str(key))
                    if key_name == "escape":
                        self._aborted = True
                        return FixationTutorialAttemptResult(hit=False, aborted=True)
                    if key_name == response_key:
                        key_rt = getattr(key, "rt", None)
                        reaction_time_s = (
                            float(key_rt)
                            if key_rt is not None
                            else frame_index / float(run_spec.display.refresh_hz)
                        )
                        return FixationTutorialAttemptResult(
                            hit=True,
                            reaction_time_s=reaction_time_s,
                        )
            return FixationTutorialAttemptResult(hit=False)
        finally:
            window.recordFrameIntervals = previous_record_frame_intervals
            if hasattr(window, "frameIntervals"):
                window.frameIntervals = []

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
        timing_first_bad_phase: str | None = None
        timing_first_bad_frame_index: int | None = None
        timing_max_interval_s: float | None = None
        timing_strict_violation = False
        timing_strict_violation_reason: str | None = None
        warmup_intervals: list[float] = []
        stimuli: dict[str, Any] = {}

        try:
            stimuli = self._prepare_stimuli(project_root, run_spec=run_spec)
            fixation_stim = create_fixation_stim(visual=visual, window=window, run_spec=run_spec)
            keyboard.clock.reset()
            keyboard.clearEvents()
            window.color = run_spec.display.background_color
            window.recordFrameIntervals = True
            if hasattr(window, "frameIntervals"):
                window.frameIntervals = []

            warmup_clock = core.Clock()
            warmup_last_flip_time: float | None = None
            warmup_strict_timing_enabled = (
                timing_config.strict_timing and timing_config.strict_timing_warmup
            )
            for warmup_frame_index in range(timing_config.warmup_frames):
                flip_time = window.flip()
                current_time_s = (
                    float(flip_time)
                    if flip_time is not None
                    else warmup_clock.getTime()
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
                        timing_first_bad_phase = "warmup"
                        timing_first_bad_frame_index = warmup_interval_index
                    post_settle_window = warmup_frame_index >= timing_config.warmup_settle_frames
                    interval_is_miss = interval_s > timing_config.miss_threshold_s
                    if (
                        warmup_strict_timing_enabled
                        and post_settle_window
                        and interval_is_miss
                    ):
                        timing_strict_violation = True
                        if timing_strict_violation_reason is None:
                            timing_strict_violation_reason = self._timing_violation_reason(
                                phase="warmup",
                                frame_index=warmup_interval_index,
                                interval_s=interval_s,
                                timing_config=timing_config,
                            )
                warmup_last_flip_time = current_time_s

            keyboard.clock.reset()
            keyboard.clearEvents()
            self._active_run_clock = core.Clock()
            reset_run_clock = getattr(self._active_run_clock, "reset", None)
            if callable(reset_run_clock):
                reset_run_clock()
            stimulus_index = 0
            fixation_index = 0
            completed_frames = 0
            last_flip_time: float | None = None
            frame_intervals: list[FrameIntervalRecord] = []
            response_log: list[ResponseRecord] = []
            trigger_log: list[TriggerRecord] = []
            trigger_event_lookup = self._build_trigger_lookup(run_spec)

            for frame_index in range(run_spec.display.total_frames):
                if self._aborted:
                    break

                while (
                    stimulus_index + 1 < len(run_spec.stimulus_sequence)
                    and run_spec.stimulus_sequence[stimulus_index + 1].on_start_frame
                    <= frame_index
                ):
                    stimulus_index += 1

                stimulus_event = (
                    run_spec.stimulus_sequence[stimulus_index]
                    if run_spec.stimulus_sequence
                    else None
                )
                if stimulus_event is not None and should_draw_stimulus(
                    stimulus_event,
                    frame_index,
                ):
                    stimulus = stimuli.get(stimulus_event.stimulus_id)
                    if stimulus is None:
                        raise RuntimeError(
                            "Prepared stimulus is missing for compiled stimulus id "
                            f"'{stimulus_event.stimulus_id}'."
                        )
                    stimulus.draw()

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
                current_time_s = (
                    float(flip_time)
                    if flip_time is not None
                    else self._active_run_clock.getTime()
                )
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
                        timing_first_bad_phase = "run"
                        timing_first_bad_frame_index = frame_index - 1
                    if timing_config.strict_timing and interval_s > timing_config.miss_threshold_s:
                        timing_strict_violation = True
                        if timing_strict_violation_reason is None:
                            timing_strict_violation_reason = self._timing_violation_reason(
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
                timing_first_bad_phase=timing_first_bad_phase,
                timing_first_bad_frame_index=timing_first_bad_frame_index,
                timing_strict_violation=timing_strict_violation,
                timing_strict_violation_reason=timing_strict_violation_reason,
            )
            self._log_timing_diagnostics(
                run_spec,
                timing_config=timing_config,
                warmup_intervals=warmup_intervals,
                frame_intervals=frame_intervals,
            )
            return RunExecutionSummary(
                project_id=run_spec.project_id,
                session_id=None,
                run_id=run_spec.run_id,
                condition_id=run_spec.condition.condition_id,
                condition_name=run_spec.condition.name,
                engine_name=self.engine_id,
                run_mode=(
                    RunMode.TEST
                    if bool((runtime_options or {}).get("test_mode"))
                    else RunMode.SESSION
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
        finally:
            release_stimuli(stimuli)
            self._active_run_clock = None

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
            continue_prompt=None,
        )

    def close_session(self) -> None:
        window = self._window
        self._window = None
        self._keyboard = None
        self._active_run_clock = None
        if window is not None:
            window.close()

    def abort(self) -> None:
        self._aborted = True

    def _build_trigger_lookup(self, run_spec: RunSpec) -> dict[int, tuple[TriggerEvent, ...]]:
        return build_trigger_lookup(run_spec)

    def _emit_trigger(
        self,
        trigger_backend: TriggerBackend,
        code: int,
        label: str,
        frame_index: int,
    ) -> None:
        emit_trigger(
            trigger_backend=trigger_backend,
            active_run_clock=self._active_run_clock,
            code=code,
            label=label,
            frame_index=frame_index,
        )

    def _fixation_color_for_frame(
        self,
        fixation_events: list[FixationEvent],
        default_color: str,
        target_color: str,
        fixation_index: int,
        frame_index: int,
    ) -> str:
        return fixation_color_for_frame(
            fixation_events,
            default_color,
            target_color,
            fixation_index,
            frame_index,
        )

    def _prepare_stimuli(
        self,
        project_root: Path,
        *,
        run_spec: RunSpec,
    ) -> dict[str, Any]:
        return prepare_stimuli(
            visual=self._require_visual(),
            window=self._require_window(),
            project_root=project_root,
            run_spec=run_spec,
        )

    def _runtime_metadata_for_run(
        self,
        run_spec: RunSpec,
        frame_intervals: list[FrameIntervalRecord],
        *,
        timing_config: TimingConfig,
        warmup_intervals: list[float],
        timing_max_interval_s: float | None,
        timing_first_bad_phase: str | None,
        timing_first_bad_frame_index: int | None,
        timing_strict_violation: bool,
        timing_strict_violation_reason: str | None,
    ) -> RuntimeMetadata:
        psychopy = self._load_psychopy()
        return runtime_metadata_for_run(
            engine_name=self.engine_id,
            psychopy_version=getattr(psychopy, "__version__", None),
            window=self._require_window(),
            runtime_options=self._runtime_options,
            run_spec=run_spec,
            frame_intervals=frame_intervals,
            timing_config=timing_config,
            warmup_intervals=warmup_intervals,
            timing_max_interval_s=timing_max_interval_s,
            timing_first_bad_phase=timing_first_bad_phase,
            timing_first_bad_frame_index=timing_first_bad_frame_index,
            timing_strict_violation=timing_strict_violation,
            timing_strict_violation_reason=timing_strict_violation_reason,
        )

    def _timing_config_for_run(self, run_spec: RunSpec) -> TimingConfig:
        return timing_config_for_run(run_spec, self._runtime_options)

    def _timing_violation_reason(
        self,
        *,
        phase: str,
        frame_index: int,
        interval_s: float,
        timing_config: TimingConfig,
    ) -> str:
        return timing_violation_reason(
            phase=phase,
            frame_index=frame_index,
            interval_s=interval_s,
            timing_config=timing_config,
        )

    def _log_timing_diagnostics(
        self,
        run_spec: RunSpec,
        *,
        timing_config: TimingConfig,
        warmup_intervals: list[float],
        frame_intervals: list[FrameIntervalRecord],
    ) -> None:
        diagnostic_threshold_s = (
            timing_config.expected_interval_s * TIMING_DIAGNOSTIC_THRESHOLD_MULTIPLIER
        )
        self._log_timing_phase_diagnostics(
            run_spec,
            phase="warmup",
            intervals=[
                FrameIntervalRecord(frame_index=index, interval_s=interval_s)
                for index, interval_s in enumerate(warmup_intervals)
            ],
            expected_interval_s=timing_config.expected_interval_s,
            diagnostic_threshold_s=diagnostic_threshold_s,
        )
        self._log_timing_phase_diagnostics(
            run_spec,
            phase="playback",
            intervals=frame_intervals,
            expected_interval_s=timing_config.expected_interval_s,
            diagnostic_threshold_s=diagnostic_threshold_s,
        )

    def _log_timing_phase_diagnostics(
        self,
        run_spec: RunSpec,
        *,
        phase: str,
        intervals: list[FrameIntervalRecord],
        expected_interval_s: float,
        diagnostic_threshold_s: float,
    ) -> None:
        long_intervals = [
            interval for interval in intervals if interval.interval_s > diagnostic_threshold_s
        ]
        if not long_intervals:
            return
        max_interval = max(long_intervals, key=lambda interval: interval.interval_s)
        first_interval = long_intervals[0]
        message = (
            f"PsychoPy timing diagnostic: run_id={run_spec.run_id} "
            f"condition_id={run_spec.condition.condition_id} phase={phase} "
            f"long_interval_count={len(long_intervals)} "
            f"first_long_frame={first_interval.frame_index} "
            f"first_long_interval_ms={first_interval.interval_s * 1000.0:.2f} "
            f"max_long_frame={max_interval.frame_index} "
            f"max_long_interval_ms={max_interval.interval_s * 1000.0:.2f} "
            f"expected_interval_ms={expected_interval_s * 1000.0:.2f} "
            f"diagnostic_threshold_ms={diagnostic_threshold_s * 1000.0:.2f}."
        )
        self._log_psychopy_warning(message)

    def _log_psychopy_warning(self, message: str) -> None:
        warning = getattr(self._psychopy_logging, "warning", None)
        if callable(warning):
            warning(message)
            return
        LOGGER.warning(message)

    def _show_text_screen(
        self,
        *,
        heading: str,
        body: str | None,
        countdown_seconds: float | None,
        continue_key: str | None,
        continue_prompt: str | None,
    ) -> bool:
        self.open_session(runtime_options=self._runtime_options)
        window = self._require_window()
        previous_record_frame_intervals = bool(getattr(window, "recordFrameIntervals", False))
        window.recordFrameIntervals = False
        if hasattr(window, "frameIntervals"):
            window.frameIntervals = []
        try:
            return show_text_screen(
                visual=self._require_visual(),
                core=self._require_core(),
                window=window,
                keyboard=self._require_keyboard(),
                is_aborted=lambda: self._aborted,
                set_aborted=self.abort,
                heading=heading,
                body=body,
                countdown_seconds=countdown_seconds,
                continue_key=continue_key,
                continue_prompt=continue_prompt,
            )
        finally:
            window.recordFrameIntervals = previous_record_frame_intervals
            if hasattr(window, "frameIntervals"):
                window.frameIntervals = []

    def _tutorial_escape_pressed(self, keyboard: Any, *, key_list: list[str]) -> bool:
        keys = keyboard.getKeys(
            keyList=key_list,
            waitRelease=False,
            clear=True,
        )
        if any(getattr(key, "name", str(key)) == "escape" for key in keys):
            self._aborted = True
            return True
        return False

    def _load_psychopy(self) -> Any:
        if self._psychopy is not None:
            return self._psychopy

        modules = load_psychopy_modules()
        self._psychopy = modules.psychopy
        self._visual = modules.visual
        self._core = modules.core
        self._keyboard_module = modules.keyboard
        self._psychopy_logging = modules.logging
        return modules.psychopy

    def _require_core(self) -> Any:
        self._load_psychopy()
        return self._core

    def _require_visual(self) -> Any:
        self._load_psychopy()
        return self._visual

    def _require_window(self) -> Any:
        if self._window is None:
            raise RuntimeError("PsychoPy session window has not been opened.")
        return self._window

    def _require_keyboard(self) -> Any:
        if self._keyboard is None:
            raise RuntimeError("PsychoPy keyboard has not been initialized.")
        return self._keyboard
