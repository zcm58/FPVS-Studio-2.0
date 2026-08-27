"""PsychoPy-backed renderer for compiled FPVS runs. It lazily imports PsychoPy and executes
one RunSpec at a time while honoring runtime-owned transition, feedback, and trigger
seams. This module owns presentation details only; session flow, fixation scoring, and
neutral export contracts stay outside the engine."""

from __future__ import annotations

import gc
import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any

from PIL import Image

from fpvs_studio.core.enums import EngineName, RunMode
from fpvs_studio.core.execution import (
    FixationTargetOnsetRecord,
    FrameIntervalRecord,
    ResponseRecord,
    RunExecutionSummary,
    RuntimeMetadata,
)
from fpvs_studio.core.paths import resolve_project_relative_path
from fpvs_studio.core.run_spec import FixationEvent, RunSpec, TriggerEvent
from fpvs_studio.engines.base import (
    FixationTutorialAttemptResult,
    PresentationEngine,
    ResolvedTaskStep,
    TaskEngineInput,
)
from fpvs_studio.engines.graphics_readiness import (
    BudgetEvaluationPhase,
    GraphicsReadinessResult,
    GraphicsReadinessStatus,
    estimate_run_spec_image_memory,
    evaluate_graphics_readiness,
    observe_windows_graphics_budget,
    probe_renderer_from_gl,
)
from fpvs_studio.engines.psychopy_loader import load_psychopy_modules
from fpvs_studio.engines.psychopy_metadata import runtime_metadata_for_run
from fpvs_studio.engines.psychopy_stimuli import (
    ConditionResourceCleanupError,
    PreparedConditionResources,
    StimulusCleanupReport,
    prepare_condition_resources,
    should_draw_stimulus,
)
from fpvs_studio.engines.psychopy_tasks import render_task_step
from fpvs_studio.engines.psychopy_text_screens import show_text_screen
from fpvs_studio.engines.psychopy_timing import (
    TimingConfig,
    measure_window_refresh_hz,
    timing_config_for_run,
    timing_violation_reason,
)
from fpvs_studio.engines.psychopy_triggers import build_trigger_lookup, emit_trigger
from fpvs_studio.engines.psychopy_window import (
    build_refresh_probe_window_kwargs,
    build_window_kwargs,
    create_fixation_stim,
)
from fpvs_studio.engines.windows_graphics_budget import (
    WindowsGraphicsBudgetObserver,
    activate_renderer_candidates_conservatively,
)
from fpvs_studio.triggers.base import TriggerBackend

LOGGER = logging.getLogger(__name__)
TIMING_DIAGNOSTIC_THRESHOLD_MULTIPLIER = 1.5


class PsychoPyEngine(PresentationEngine):
    """PsychoPy-backed presentation engine."""

    def __init__(self) -> None:
        self._psychopy: Any | None = None
        self._visual: Any | None = None
        self._core: Any | None = None
        self._event: Any | None = None
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

    def measure_refresh_hz(
        self,
        *,
        runtime_options: Mapping[str, object] | None = None,
    ) -> float:
        """Measure the current display with a temporary fullscreen PsychoPy window."""

        visual = self._require_visual()
        probe_window = visual.Window(**build_refresh_probe_window_kwargs(runtime_options))
        try:
            return measure_window_refresh_hz(probe_window)
        finally:
            probe_window.close()

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
        self._event = getattr(psychopy, "event", self._event)

        self._runtime_options = dict(runtime_options or {})
        self._window = visual.Window(**build_window_kwargs(self._runtime_options))
        try:
            self._window.recordFrameIntervals = True
            self._keyboard = keyboard_module.Keyboard()
            self._keyboard.clearEvents()
        except BaseException:
            self.close_session()
            raise
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
        warmup_intervals: list[float] = []
        pre_stream_qc_frames = 0
        stream_onset_interval_s: float | None = None
        raw_frame_intervals: list[float | None] = [None] * run_spec.display.total_frames
        raw_responses: list[tuple[str, int, float | None]] = []
        raw_fixation_target_onsets: list[tuple[int, int, float]] = []
        completed_frames = 0
        resources: PreparedConditionResources | None = None
        cleanup_report: StimulusCleanupReport | None = None
        graphics_readiness: GraphicsReadinessResult | None = None
        keyboard_backend: str | None = None
        cache_gpu_synchronized = False
        cache_unique_variant_count = 0
        playback_plan: list[
            tuple[
                Any | None,
                Any,
                tuple[TriggerEvent, ...],
                tuple[FixationEvent, ...],
            ]
        ] = []
        preparation_succeeded = False
        condition_failed = False
        stimulus_draw: Any | None = None

        try:
            window.color = run_spec.display.background_color
            default_fixation_stim = create_fixation_stim(
                visual=visual,
                window=window,
                run_spec=run_spec,
                color=run_spec.fixation.default_color,
            )
            target_fixation_stim = create_fixation_stim(
                visual=visual,
                window=window,
                run_spec=run_spec,
                color=run_spec.fixation.target_color,
            )
            graphics_context = self._graphics_readiness_before_preparation(
                project_root,
                run_spec,
            )
            resources = prepare_condition_resources(
                visual=visual,
                window=window,
                project_root=project_root,
                run_spec=run_spec,
                fixation_stimuli=(default_fixation_stim, target_fixation_stim),
            )
            if not resources.ready:
                raise RuntimeError("Condition graphics resources did not reach READY state.")
            cache_gpu_synchronized = resources.gpu_synchronized
            cache_unique_variant_count = len(resources.stimuli)
            graphics_readiness = self._graphics_readiness_after_preparation(graphics_context)
            playback_plan = self._build_playback_plan(
                run_spec,
                prepared_sequence=resources.prepared_sequence,
                default_fixation_stim=default_fixation_stim,
                target_fixation_stim=target_fixation_stim,
            )
            response_keys = list(dict.fromkeys((*run_spec.fixation.response_keys, "escape")))
            escape_keys = ["escape"]
            flip = window.flip
            call_on_flip = window.callOnFlip
            get_keys = keyboard.getKeys
            keyboard_clock = keyboard.clock
            keyboard_backend = self._keyboard_backend_name(keyboard)
            capture_key_timestamps = keyboard_backend in {"ptb", "iohub"}
            keyboard_flip_time_offset: float | None = None
            self._active_run_clock = core.Clock()
            reset_run_clock = getattr(self._active_run_clock, "reset", None)
            run_clock_get_time = self._active_run_clock.getTime

            keyboard.clock.reset()
            keyboard.clearEvents()
            window.recordFrameIntervals = True
            if hasattr(window, "frameIntervals"):
                window.frameIntervals = []

            warmup_clock = core.Clock()
            warmup_last_flip_time: float | None = None
            warmup_last_flip_has_timestamp = False
            lead_in_frames = max(
                0,
                int(getattr(run_spec, "pre_stream_fixation_frames", 0)),
            )
            blank_warmup_frames = max(0, timing_config.warmup_frames - lead_in_frames)
            pre_stream_frame_count = max(timing_config.warmup_frames, lead_in_frames)
            keyboard_clock_armed = False
            gc_was_enabled = gc.isenabled()
            if gc_was_enabled:
                gc.disable()
            try:
                for warmup_frame_index in range(pre_stream_frame_count):
                    if lead_in_frames > 0 and warmup_frame_index > 0:
                        keys = get_keys(
                            keyList=escape_keys,
                            waitRelease=False,
                            clear=True,
                        )
                        if any(getattr(key, "name", str(key)) == "escape" for key in keys):
                            self._aborted = True
                            abort_reason = "Escape pressed before condition playback."
                            break

                    if warmup_frame_index + 1 == pre_stream_frame_count:
                        keyboard_clock.reset()
                        keyboard.clearEvents()
                        keyboard_flip_time_offset = (
                            self._keyboard_flip_time_offset(keyboard_clock)
                            if capture_key_timestamps
                            else None
                        )
                        keyboard_clock_armed = True

                    if warmup_frame_index >= blank_warmup_frames:
                        default_fixation_stim.draw()
                    flip_time = flip()
                    pre_stream_qc_frames += 1
                    current_time_s = (
                        float(flip_time) if flip_time is not None else warmup_clock.getTime()
                    )
                    current_has_timestamp = flip_time is not None
                    if (
                        warmup_last_flip_time is not None
                        and warmup_last_flip_has_timestamp == current_has_timestamp
                    ):
                        interval_s = current_time_s - warmup_last_flip_time
                        warmup_intervals.append(interval_s)
                    warmup_last_flip_time = current_time_s
                    warmup_last_flip_has_timestamp = current_has_timestamp

                if not self._aborted:
                    if not keyboard_clock_armed:
                        keyboard_clock.reset()
                        keyboard.clearEvents()
                        keyboard_flip_time_offset = (
                            self._keyboard_flip_time_offset(keyboard_clock)
                            if capture_key_timestamps
                            else None
                        )
                    # All allocation and method binding is already complete. Resetting
                    # this lightweight clock is the only setup between the final
                    # warmup flip and drawing stream frame zero.
                    if callable(reset_run_clock):
                        reset_run_clock()

                    last_flip_time: float | None = None
                    last_flip_has_timestamp = False
                    for frame_index, frame_plan in enumerate(playback_plan):
                        if self._aborted:
                            break
                        (
                            stimulus_draw,
                            fixation_draw,
                            trigger_events,
                            target_onset_events,
                        ) = frame_plan
                        if stimulus_draw is not None:
                            stimulus_draw()
                        fixation_draw()

                        # Trigger writes are the only experiment callbacks on a timed
                        # flip; fixation timing uses the returned flip timestamp.
                        if trigger_backend is not None:
                            for trigger_event in trigger_events:
                                call_on_flip(
                                    self._emit_trigger,
                                    trigger_backend,
                                    trigger_event.code,
                                    trigger_event.label,
                                    frame_index,
                                )
                        flip_time = flip()
                        current_has_timestamp = flip_time is not None
                        current_time_s = (
                            float(flip_time) if current_has_timestamp else run_clock_get_time()
                        )
                        if (
                            target_onset_events
                            and current_has_timestamp
                            and keyboard_flip_time_offset is not None
                        ):
                            target_onset_time_s = current_time_s + keyboard_flip_time_offset
                            raw_fixation_target_onsets.extend(
                                (
                                    fixation_event.event_index,
                                    frame_index,
                                    target_onset_time_s,
                                )
                                for fixation_event in target_onset_events
                            )
                        if (
                            frame_index == 0
                            and warmup_last_flip_time is not None
                            and warmup_last_flip_has_timestamp
                            and current_has_timestamp
                        ):
                            stream_onset_interval_s = current_time_s - warmup_last_flip_time
                        if (
                            last_flip_time is not None
                            and last_flip_has_timestamp == current_has_timestamp
                        ):
                            raw_frame_intervals[frame_index - 1] = (
                                current_time_s - last_flip_time
                            )
                        last_flip_time = current_time_s
                        last_flip_has_timestamp = current_has_timestamp
                        completed_frames = frame_index + 1

                        if self._aborted:
                            break
                        abort_reason = self._capture_response_batch(
                            get_keys(
                                keyList=response_keys,
                                waitRelease=False,
                                clear=True,
                            ),
                            frame_index=frame_index,
                            raw_responses=raw_responses,
                            abort_reason=abort_reason,
                            capture_timestamps=capture_key_timestamps,
                        )
                        if self._aborted:
                            break

                    if completed_frames > 0 and last_flip_time is not None:
                        # This is an offset boundary, not another compiled frame. It
                        # removes a continuous final image and closes a final blank_50
                        # interval without changing the compiled cadence or triggers.
                        default_fixation_stim.draw()
                        terminal_flip_time = flip()
                        terminal_has_timestamp = terminal_flip_time is not None
                        terminal_time_s = (
                            float(terminal_flip_time)
                            if terminal_has_timestamp
                            else run_clock_get_time()
                        )
                        if last_flip_has_timestamp == terminal_has_timestamp:
                            raw_frame_intervals[completed_frames - 1] = (
                                terminal_time_s - last_flip_time
                            )
                        if not self._aborted:
                            abort_reason = self._capture_response_batch(
                                get_keys(
                                    keyList=response_keys,
                                    waitRelease=False,
                                    clear=True,
                                ),
                                frame_index=completed_frames - 1,
                                raw_responses=raw_responses,
                                abort_reason=abort_reason,
                                capture_timestamps=capture_key_timestamps,
                            )
            finally:
                if gc_was_enabled:
                    gc.enable()

            finished_at = datetime.now(timezone.utc)
            preparation_succeeded = True
        except BaseException:
            condition_failed = True
            raise
        finally:
            stimulus_draw = None
            playback_plan.clear()
            if resources is not None:
                cleanup_report = resources.release()
                if not cleanup_report.succeeded:
                    self.close_session()
                    if preparation_succeeded:
                        raise ConditionResourceCleanupError(cleanup_report)
                    LOGGER.error(
                        "Condition cleanup failed while another playback error was active; "
                        "the graphics context was closed."
                    )
            if condition_failed:
                # A failed swap or callOnFlip callback leaves front-buffer and callback
                # state uncertain. Invalidate the session only after condition-owned GL
                # objects have had a chance to release against the live context.
                self.close_session()
            self._active_run_clock = None

        frame_intervals = [
            FrameIntervalRecord(frame_index=frame_index, interval_s=interval_s)
            for frame_index, interval_s in enumerate(raw_frame_intervals)
            if interval_s is not None
        ]
        response_log = [
            ResponseRecord(
                response_index=response_index,
                key=key,
                frame_index=frame_index,
                time_s=time_s,
            )
            for response_index, (key, frame_index, time_s) in enumerate(raw_responses)
        ]
        fixation_target_onsets = [
            FixationTargetOnsetRecord(
                event_index=event_index,
                frame_index=frame_index,
                time_s=time_s,
            )
            for event_index, frame_index, time_s in raw_fixation_target_onsets
        ]
        (
            timing_max_interval_s,
            timing_first_bad_phase,
            timing_first_bad_frame_index,
            timing_strict_violation,
            timing_strict_violation_reason,
        ) = self._evaluate_timing_qc(
            timing_config=timing_config,
            warmup_intervals=warmup_intervals,
            stream_onset_interval_s=stream_onset_interval_s,
            frame_intervals=frame_intervals,
        )
        runtime_metadata = self._runtime_metadata_for_run(
            run_spec,
            frame_intervals,
            timing_config=timing_config,
            warmup_intervals=warmup_intervals,
            pre_stream_qc_frames=pre_stream_qc_frames,
            timing_max_interval_s=timing_max_interval_s,
            timing_first_bad_phase=timing_first_bad_phase,
            timing_first_bad_frame_index=timing_first_bad_frame_index,
            timing_strict_violation=timing_strict_violation,
            timing_strict_violation_reason=timing_strict_violation_reason,
        ).model_copy(
            update={
                **self._graphics_metadata_updates(
                    graphics_readiness=graphics_readiness,
                    cleanup_report=cleanup_report,
                    gpu_synchronized=cache_gpu_synchronized,
                    unique_variant_count=cache_unique_variant_count,
                ),
                "keyboard_backend": keyboard_backend,
            }
        )
        self._log_timing_diagnostics(
            run_spec,
            timing_config=timing_config,
            warmup_intervals=warmup_intervals,
            stream_onset_interval_s=stream_onset_interval_s,
            frame_intervals=frame_intervals,
        )
        return RunExecutionSummary(
            project_id=run_spec.project_id,
            session_id=None,
            run_id=run_spec.run_id,
            condition_id=run_spec.condition.condition_id,
            condition_name=run_spec.condition.name,
            engine_name=self.engine_id,
            run_mode=RunMode.SESSION,
            started_at=started_at,
            finished_at=finished_at,
            completed_frames=completed_frames,
            aborted=self._aborted,
            abort_reason=abort_reason if self._aborted else None,
            runtime_metadata=runtime_metadata,
            frame_intervals=frame_intervals,
            fixation_target_onsets=fixation_target_onsets,
            fixation_responses=[],
            response_log=response_log,
            trigger_log=[],
        )

    def render_task_step(
        self,
        step: ResolvedTaskStep,
        project_root: Path,
    ) -> TaskEngineInput:
        """Render one runtime-owned modular task screen outside FPVS timing."""

        self.open_session(runtime_options=self._runtime_options)
        window = self._require_window()
        previous_record_frame_intervals = bool(getattr(window, "recordFrameIntervals", False))
        window.recordFrameIntervals = False
        if hasattr(window, "frameIntervals"):
            window.frameIntervals = []
        try:
            return render_task_step(
                visual=self._require_visual(),
                core=self._require_core(),
                event=self._require_event(),
                window=window,
                keyboard=self._require_keyboard(),
                project_root=project_root,
                step=step,
                is_aborted=lambda: self._aborted,
                set_aborted=self.abort,
            )
        finally:
            window.recordFrameIntervals = previous_record_frame_intervals
            if hasattr(window, "frameIntervals"):
                window.frameIntervals = []

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
        raw_countdown_seconds = self._runtime_options.get(
            "completion_screen_seconds",
            0.5,
        )
        countdown_seconds = (
            float(raw_countdown_seconds)
            if isinstance(raw_countdown_seconds, (int, float))
            and not isinstance(raw_countdown_seconds, bool)
            and raw_countdown_seconds >= 0
            else 0.5
        )
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

    def _build_playback_plan(
        self,
        run_spec: RunSpec,
        *,
        prepared_sequence: Any,
        default_fixation_stim: Any,
        target_fixation_stim: Any,
    ) -> list[tuple[Any | None, Any, tuple[TriggerEvent, ...], tuple[FixationEvent, ...]]]:
        """Compile model-heavy frame decisions into bound draw calls before playback."""

        if len(prepared_sequence) != len(run_spec.stimulus_sequence):
            raise RuntimeError("Prepared stimulus sequence does not match the RunSpec.")
        trigger_lookup = self._build_trigger_lookup(run_spec)
        draw_by_stimulus_identity: dict[int, Any] = {}
        prepared_draw_sequence: list[Any] = []
        for stimulus in prepared_sequence:
            stimulus_identity = id(stimulus)
            stimulus_draw = draw_by_stimulus_identity.get(stimulus_identity)
            if stimulus_draw is None:
                stimulus_draw = stimulus.draw
                draw_by_stimulus_identity[stimulus_identity] = stimulus_draw
            prepared_draw_sequence.append(stimulus_draw)
        default_fixation_draw = default_fixation_stim.draw
        target_fixation_draw = target_fixation_stim.draw
        target_onset_lookup: dict[int, list[FixationEvent]] = {}
        ordered_fixation_events = sorted(
            run_spec.fixation_events,
            key=lambda event: (event.start_frame, event.event_index),
        )
        for fixation_event in ordered_fixation_events:
            target_onset_lookup.setdefault(fixation_event.start_frame, []).append(fixation_event)

        plan: list[tuple[Any | None, Any, tuple[TriggerEvent, ...], tuple[FixationEvent, ...]]] = []
        stimulus_index = 0
        fixation_index = 0
        for frame_index in range(run_spec.display.total_frames):
            while (
                stimulus_index + 1 < len(run_spec.stimulus_sequence)
                and run_spec.stimulus_sequence[stimulus_index + 1].on_start_frame <= frame_index
            ):
                stimulus_index += 1
            stimulus_event = (
                run_spec.stimulus_sequence[stimulus_index] if run_spec.stimulus_sequence else None
            )
            stimulus_draw = (
                prepared_draw_sequence[stimulus_index]
                if should_draw_stimulus(stimulus_event, frame_index)
                else None
            )

            while (
                fixation_index + 1 < len(ordered_fixation_events)
                and ordered_fixation_events[fixation_index + 1].start_frame <= frame_index
            ):
                fixation_index += 1
            target_active = False
            if ordered_fixation_events:
                fixation_event = ordered_fixation_events[fixation_index]
                target_active = (
                    fixation_event.start_frame
                    <= frame_index
                    < fixation_event.start_frame + fixation_event.duration_frames
                )
            fixation_draw = (
                target_fixation_draw if target_active else default_fixation_draw
            )
            plan.append(
                (
                    stimulus_draw,
                    fixation_draw,
                    trigger_lookup.get(frame_index, ()),
                    tuple(target_onset_lookup.get(frame_index, ())),
                )
            )
        return plan

    def _keyboard_flip_time_offset(self, keyboard_clock: Any) -> float | None:
        """Return the conversion from window flip time to keyboard-clock time."""

        default_clock = getattr(self._psychopy_logging, "defaultClock", None)
        default_reset_time = getattr(default_clock, "getLastResetTime", None)
        keyboard_reset_time = getattr(keyboard_clock, "getLastResetTime", None)
        if not callable(default_reset_time) or not callable(keyboard_reset_time):
            return None
        try:
            return float(default_reset_time()) - float(keyboard_reset_time())
        except (TypeError, ValueError):
            return None

    def _keyboard_backend_name(self, keyboard: Any) -> str | None:
        """Return PsychoPy's active input backend without assuming timestamp quality."""

        get_backend = getattr(keyboard, "getBackend", None)
        if not callable(get_backend):
            return None
        try:
            value = get_backend()
        except Exception:
            return None
        if not isinstance(value, str):
            return None
        normalized = value.strip().casefold()
        return normalized or None

    def _capture_response_batch(
        self,
        keys: list[Any],
        *,
        frame_index: int,
        raw_responses: list[tuple[str, int, float | None]],
        abort_reason: str | None,
        capture_timestamps: bool,
    ) -> str | None:
        """Collect primitive keyboard data without constructing validated models."""

        for key in keys:
            key_name = getattr(key, "name", None)
            if key_name is None:
                key_name = str(key)
            if key_name == "escape":
                self._aborted = True
                return abort_reason or "Escape pressed during condition playback."
            key_time = getattr(key, "rt", None) if capture_timestamps else None
            raw_responses.append(
                (
                    str(key_name),
                    frame_index,
                    float(key_time) if key_time is not None else None,
                )
            )
        return abort_reason

    def _graphics_readiness_before_preparation(
        self,
        project_root: Path,
        run_spec: RunSpec,
    ) -> tuple[Any, Any, WindowsGraphicsBudgetObserver] | None:
        """Enforce renderer/RAM/VRAM headroom before allocating condition textures."""

        if not bool(self._runtime_options.get("verify_graphics_memory", False)):
            return None
        gl_module = import_module("psychopy.visual.basevisual").GL
        renderer = probe_renderer_from_gl(gl_module)
        decoded_dimensions, decoded_modes = self._decoded_image_metadata(project_root, run_spec)
        estimate = estimate_run_spec_image_memory(
            run_spec,
            decoded_dimensions=decoded_dimensions,
            decoded_modes=decoded_modes,
        )
        observer = WindowsGraphicsBudgetObserver(renderer_hint=renderer.renderer)
        observation = activate_renderer_candidates_conservatively(
            observe_windows_graphics_budget(observer),
            renderer_hint=renderer.renderer,
        )
        readiness = evaluate_graphics_readiness(
            renderer=renderer,
            estimate=estimate,
            observation=observation,
            phase=BudgetEvaluationPhase.BEFORE_UPLOAD,
        )
        self._require_graphics_readiness(readiness, phase="before image upload")
        return (renderer, estimate, observer)

    def _graphics_readiness_after_preparation(
        self,
        context: tuple[Any, Any, WindowsGraphicsBudgetObserver] | None,
    ) -> GraphicsReadinessResult | None:
        """Confirm actual post-upload headroom after the explicit GPU barrier."""

        if context is None:
            return None
        renderer, estimate, observer = context
        observation = activate_renderer_candidates_conservatively(
            observe_windows_graphics_budget(observer),
            renderer_hint=renderer.renderer,
        )
        readiness = evaluate_graphics_readiness(
            renderer=renderer,
            estimate=estimate,
            observation=observation,
            phase=BudgetEvaluationPhase.AFTER_UPLOAD,
        )
        self._require_graphics_readiness(readiness, phase="after image upload")
        return readiness

    def _decoded_image_metadata(
        self,
        project_root: Path,
        run_spec: RunSpec,
    ) -> tuple[dict[str, tuple[int, int]], dict[str, str]]:
        """Read unique image geometry/modes through the contained resolver."""

        dimensions: dict[str, tuple[int, int]] = {}
        modes: dict[str, str] = {}
        for event in run_spec.stimulus_sequence:
            image_path = event.image_path
            if image_path is None or image_path in dimensions:
                continue
            absolute_path = resolve_project_relative_path(project_root, image_path)
            with Image.open(absolute_path) as image:
                dimensions[image_path] = (int(image.width), int(image.height))
                modes[image_path] = image.mode
        return dimensions, modes

    def _require_graphics_readiness(
        self,
        readiness: GraphicsReadinessResult,
        *,
        phase: str,
    ) -> None:
        if readiness.status == GraphicsReadinessStatus.READY:
            return
        reasons = "; ".join(readiness.reasons) or "No readiness reason was reported."
        raise RuntimeError(
            "Condition graphics readiness "
            f"{readiness.status.value} {phase}; playback did not begin. {reasons}"
        )

    def _graphics_metadata_updates(
        self,
        *,
        graphics_readiness: GraphicsReadinessResult | None,
        cleanup_report: StimulusCleanupReport | None,
        gpu_synchronized: bool,
        unique_variant_count: int,
    ) -> dict[str, object]:
        cleanup_succeeded = cleanup_report.succeeded if cleanup_report is not None else None
        cleanup_failure_count = len(cleanup_report.failures) if cleanup_report is not None else 0
        updates: dict[str, object] = {
            "condition_cache_unique_variant_count": unique_variant_count,
            "condition_cache_gpu_synchronized": gpu_synchronized,
            "condition_cache_cleanup_succeeded": cleanup_succeeded,
            "condition_cache_cleanup_failure_count": cleanup_failure_count,
        }
        if graphics_readiness is None:
            updates.update(
                {
                    "graphics_readiness_status": "disabled",
                    "graphics_readiness_reasons": [
                        "Graphics-memory verification was explicitly disabled for this launch."
                    ],
                }
            )
            return updates

        renderer = graphics_readiness.renderer
        estimate = graphics_readiness.estimate
        updates.update(
            {
                "graphics_readiness_status": graphics_readiness.status.value,
                "graphics_readiness_reasons": list(graphics_readiness.reasons),
                "graphics_renderer_vendor": renderer.vendor,
                "graphics_renderer_name": renderer.renderer,
                "graphics_renderer_version": renderer.version,
                "graphics_renderer_classification": renderer.classification.value,
                "graphics_memory_estimated_gpu_bytes": estimate.estimated_gpu_bytes,
                "graphics_memory_conservative_gpu_bytes": (estimate.conservative_gpu_bytes),
            }
        )
        if graphics_readiness.adapter_assessments:
            tightest_adapter = min(
                graphics_readiness.adapter_assessments,
                key=lambda assessment: assessment.projected_headroom_bytes,
            )
            updates.update(
                {
                    "graphics_memory_budget_bytes": tightest_adapter.budget_bytes,
                    "graphics_memory_usage_bytes": tightest_adapter.current_usage_bytes,
                    "graphics_memory_headroom_bytes": (tightest_adapter.projected_headroom_bytes),
                }
            )
        if graphics_readiness.system_memory_assessment is not None:
            updates["graphics_system_available_bytes"] = (
                graphics_readiness.system_memory_assessment.available_bytes
            )
        return updates

    def _evaluate_timing_qc(
        self,
        *,
        timing_config: TimingConfig,
        warmup_intervals: list[float],
        stream_onset_interval_s: float | None,
        frame_intervals: list[FrameIntervalRecord],
    ) -> tuple[float | None, str | None, int | None, bool, str | None]:
        """Evaluate all timing records after the allocation-minimal display loop."""

        chronological: list[tuple[str, int, float]] = [
            ("warmup", index, interval_s) for index, interval_s in enumerate(warmup_intervals)
        ]
        if stream_onset_interval_s is not None:
            chronological.append(("stream_onset", 0, stream_onset_interval_s))
        chronological.extend(
            ("run", interval.frame_index, interval.interval_s) for interval in frame_intervals
        )
        timing_max_interval_s = (
            max(interval_s for _phase, _frame_index, interval_s in chronological)
            if chronological
            else None
        )
        first_bad = next(
            (
                (phase, frame_index)
                for phase, frame_index, interval_s in chronological
                if interval_s > timing_config.miss_threshold_s
            ),
            None,
        )
        timing_first_bad_phase = first_bad[0] if first_bad is not None else None
        timing_first_bad_frame_index = first_bad[1] if first_bad is not None else None

        strict_miss: tuple[str, int, float] | None = None
        if timing_config.strict_timing and timing_config.strict_timing_warmup:
            strict_miss = next(
                (
                    ("warmup", index, interval_s)
                    for index, interval_s in enumerate(warmup_intervals)
                    if index + 1 >= timing_config.warmup_settle_frames
                    and interval_s > timing_config.miss_threshold_s
                ),
                None,
            )
        if (
            strict_miss is None
            and timing_config.strict_timing
            and stream_onset_interval_s is not None
            and stream_onset_interval_s > timing_config.miss_threshold_s
        ):
            strict_miss = ("stream_onset", 0, stream_onset_interval_s)
        if strict_miss is None and timing_config.strict_timing:
            strict_miss = next(
                (
                    ("run", interval.frame_index, interval.interval_s)
                    for interval in frame_intervals
                    if interval.interval_s > timing_config.miss_threshold_s
                ),
                None,
            )
        strict_reason = (
            self._timing_violation_reason(
                phase=strict_miss[0],
                frame_index=strict_miss[1],
                interval_s=strict_miss[2],
                timing_config=timing_config,
            )
            if strict_miss is not None
            else None
        )
        return (
            timing_max_interval_s,
            timing_first_bad_phase,
            timing_first_bad_frame_index,
            strict_miss is not None,
            strict_reason,
        )

    def _runtime_metadata_for_run(
        self,
        run_spec: RunSpec,
        frame_intervals: list[FrameIntervalRecord],
        *,
        timing_config: TimingConfig,
        warmup_intervals: list[float],
        pre_stream_qc_frames: int,
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
            pre_stream_qc_frames=pre_stream_qc_frames,
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
        stream_onset_interval_s: float | None,
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
        if stream_onset_interval_s is not None:
            self._log_timing_phase_diagnostics(
                run_spec,
                phase="stream_onset",
                intervals=[
                    FrameIntervalRecord(
                        frame_index=0,
                        interval_s=stream_onset_interval_s,
                    )
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
        self._event = modules.event
        self._keyboard_module = modules.keyboard
        self._psychopy_logging = modules.logging
        return modules.psychopy

    def _require_core(self) -> Any:
        self._load_psychopy()
        return self._core

    def _require_visual(self) -> Any:
        self._load_psychopy()
        return self._visual

    def _require_event(self) -> Any:
        self._load_psychopy()
        if self._event is None:
            event_module = getattr(self._psychopy, "event", None)
            if event_module is None:
                raise RuntimeError("PsychoPy mouse support is unavailable.")
            self._event = event_module
        return self._event

    def _require_window(self) -> Any:
        if self._window is None:
            raise RuntimeError("PsychoPy session window has not been opened.")
        return self._window

    def _require_keyboard(self) -> Any:
        if self._keyboard is None:
            raise RuntimeError("PsychoPy keyboard has not been initialized.")
        return self._keyboard
