"""Runtime worker that executes run specs through a presentation engine."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from fpvs_studio.core.enums import InterConditionMode, RunMode
from fpvs_studio.core.execution import (
    FixationTaskSummary,
    RunExecutionSummary,
    RuntimeMetadata,
    SessionExecutionSummary,
    FrameIntervalRecord,
)
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.session_plan import SessionEntry, SessionPlan
from fpvs_studio.engines.base import PresentationEngine
from fpvs_studio.runtime.fixation import build_fixation_task_summary, score_fixation_responses
from fpvs_studio.runtime.session_export import write_run_artifacts, write_session_artifacts
from fpvs_studio.runtime.triggers import LoggedTriggerBackend, build_trigger_backend


class RuntimeWorker:
    """Execute neutral run specs through a selected presentation engine."""

    def __init__(self, engine: PresentationEngine) -> None:
        self._engine = engine

    def execute(
        self,
        project_root: Path,
        run_spec: RunSpec,
        output_dir: Path,
        *,
        participant_number: str,
        runtime_options: Mapping[str, object] | None = None,
        relative_output_dir: str | None = None,
    ) -> RunExecutionSummary:
        """Run one compiled condition and write its neutral artifact set."""

        trigger_backend, trigger_warnings = build_trigger_backend(runtime_options)
        trigger_backend.connect()
        session_open = False
        try:
            self._engine.open_session(runtime_options=runtime_options)
            session_open = True
            trigger_start_index = len(trigger_backend.records)
            run_summary = self._engine.run_condition(
                run_spec,
                project_root,
                runtime_options=runtime_options,
                trigger_backend=trigger_backend,
            )
            run_summary = self._finalize_run_summary(
                run_summary,
                run_spec,
                runtime_options=runtime_options,
                relative_output_dir=relative_output_dir,
                session_id=run_summary.session_id,
                participant_number=participant_number,
                trigger_backend=trigger_backend,
                trigger_start_index=trigger_start_index,
                warnings=trigger_warnings,
            )
            if not run_summary.aborted and self._show_condition_feedback(run_spec, run_summary):
                run_summary = run_summary.model_copy(
                    update={
                        "aborted": True,
                        "abort_reason": "Run aborted during the condition feedback screen.",
                    }
                )
            if not run_summary.aborted:
                self._engine.show_completion_screen(
                    completed_condition_count=1,
                    total_condition_count=1,
                    was_aborted=False,
                )
        finally:
            if session_open:
                self._engine.close_session()
            trigger_backend.close()

        write_run_artifacts(output_dir, run_spec, run_summary)
        return run_summary

    def execute_session(
        self,
        project_root: Path,
        session_plan: SessionPlan,
        output_dir: Path,
        *,
        participant_number: str,
        runtime_options: Mapping[str, object] | None = None,
        relative_output_dir: str | None = None,
    ) -> SessionExecutionSummary:
        """Run every entry in a session plan and write session-level artifacts."""

        trigger_backend, trigger_warnings = build_trigger_backend(runtime_options)
        trigger_backend.connect()
        session_open = False
        warnings = list(trigger_warnings)
        run_results: list[RunExecutionSummary] = []
        abort_reason: str | None = None
        ordered_entries = session_plan.ordered_entries()

        try:
            self._engine.open_session(runtime_options=runtime_options)
            session_open = True
            for entry in ordered_entries:
                if self._show_transition(entry, session_plan, runtime_options=runtime_options):
                    abort_reason = (
                        f"Session aborted during the transition screen before run '{entry.run_id}'."
                    )
                    break

                run_output_dir = output_dir / entry.run_id
                run_relative_output_dir = (
                    f"{relative_output_dir}/{entry.run_id}" if relative_output_dir is not None else None
                )
                trigger_start_index = len(trigger_backend.records)
                run_summary = self._engine.run_condition(
                    entry.run_spec,
                    project_root,
                    runtime_options=runtime_options,
                    trigger_backend=trigger_backend,
                )
                run_summary = self._finalize_run_summary(
                    run_summary,
                    entry.run_spec,
                    runtime_options=runtime_options,
                    relative_output_dir=run_relative_output_dir,
                    session_id=session_plan.session_id,
                    participant_number=participant_number,
                    trigger_backend=trigger_backend,
                    trigger_start_index=trigger_start_index,
                    warnings=(),
                )
                previous_feedback_summary = _latest_fixation_task_summary(run_results)
                warnings.extend(run_summary.warnings)
                run_results.append(run_summary)
                write_run_artifacts(run_output_dir, entry.run_spec, run_summary)

                if run_summary.aborted:
                    abort_reason = run_summary.abort_reason or f"Run '{entry.run_id}' was aborted."
                    break

                if self._show_condition_feedback(
                    entry.run_spec,
                    run_summary,
                    previous_summary=previous_feedback_summary,
                ):
                    abort_reason = (
                        f"Session aborted during the condition feedback screen after run "
                        f"'{entry.run_id}'."
                    )
                    break

                if self._show_block_break(entry, session_plan):
                    abort_reason = (
                        f"Session aborted during the inter-block break after block "
                        f"{entry.block_index + 1}."
                    )
                    break

            if abort_reason is None:
                completion_aborted = self._engine.show_completion_screen(
                    completed_condition_count=len(run_results),
                    total_condition_count=session_plan.total_runs,
                    was_aborted=False,
                )
                if completion_aborted:
                    abort_reason = "Session aborted while showing the completion screen."
        finally:
            if session_open:
                self._engine.close_session()
            trigger_backend.close()

        session_summary = SessionExecutionSummary(
            project_id=session_plan.project_id,
            session_id=session_plan.session_id,
            engine_name=self._engine.engine_id,
            run_mode=_run_mode(runtime_options),
            participant_number=participant_number,
            random_seed=session_plan.random_seed,
            started_at=run_results[0].started_at if run_results else None,
            finished_at=run_results[-1].finished_at if run_results else None,
            total_condition_count=session_plan.total_runs,
            completed_condition_count=sum(0 if result.aborted else 1 for result in run_results),
            aborted=abort_reason is not None,
            abort_reason=abort_reason,
            warnings=warnings,
            runtime_metadata=_pick_session_runtime_metadata(run_results),
            realized_block_orders=[list(block.condition_order) for block in session_plan.blocks],
            run_results=run_results,
            output_dir=relative_output_dir,
        )
        write_session_artifacts(output_dir, session_plan, session_summary)
        return session_summary

    def _finalize_run_summary(
        self,
        run_summary: RunExecutionSummary,
        run_spec: RunSpec,
        *,
        runtime_options: Mapping[str, object] | None,
        relative_output_dir: str | None,
        session_id: str | None,
        participant_number: str,
        trigger_backend: LoggedTriggerBackend,
        trigger_start_index: int,
        warnings: list[str] | tuple[str, ...],
    ) -> RunExecutionSummary:
        scored_fixation_responses = run_summary.fixation_responses
        scored_response_log = run_summary.response_log
        fixation_task_summary = run_summary.fixation_task_summary
        if not scored_fixation_responses:
            scored_fixation_responses, scored_response_log = score_fixation_responses(
                run_spec.fixation_events,
                run_summary.response_log,
                response_key=run_spec.fixation.response_key,
                response_window_frames=run_spec.fixation.response_window_frames,
            )
        if run_spec.fixation.accuracy_task_enabled and fixation_task_summary is None:
            fixation_task_summary = build_fixation_task_summary(
                scored_fixation_responses,
                scored_response_log,
                refresh_hz=run_spec.display.refresh_hz,
            )
        if not run_spec.fixation.accuracy_task_enabled:
            fixation_task_summary = None

        runtime_metadata = run_summary.runtime_metadata or RuntimeMetadata(
            engine_name=self._engine.engine_id,
            display_index=_coerce_int(runtime_options, "display_index"),
            fullscreen=bool((runtime_options or {}).get("fullscreen", True)),
            requested_refresh_hz=run_spec.display.refresh_hz,
            test_mode=bool((runtime_options or {}).get("test_mode")),
        )
        if runtime_metadata.actual_refresh_hz is None:
            estimated_refresh_hz = _estimate_refresh_hz(run_summary.frame_intervals)
            if estimated_refresh_hz is not None:
                runtime_metadata = runtime_metadata.model_copy(
                    update={"actual_refresh_hz": estimated_refresh_hz}
                )

        trigger_log = list(run_summary.trigger_log)
        if not trigger_log:
            trigger_log = list(trigger_backend.records[trigger_start_index:])

        combined_warnings = list(warnings) + list(run_summary.warnings)
        return run_summary.model_copy(
            update={
                "session_id": session_id,
                "engine_name": self._engine.engine_id,
                "run_mode": _run_mode(runtime_options),
                "participant_number": participant_number,
                "warnings": combined_warnings,
                "runtime_metadata": runtime_metadata,
                "fixation_responses": scored_fixation_responses,
                "fixation_task_summary": fixation_task_summary,
                "response_log": scored_response_log,
                "trigger_log": trigger_log,
                "output_dir": run_summary.output_dir or relative_output_dir,
            }
        )

    def _show_transition(
        self,
        entry: SessionEntry,
        session_plan: SessionPlan,
        *,
        runtime_options: Mapping[str, object] | None,
    ) -> bool:
        heading = (
            f"Condition {entry.global_order_index + 1} of {session_plan.total_runs}: "
            f"{entry.condition_name}"
        )
        body_parts = [
            f"Block {entry.block_index + 1}, item {entry.index_within_block + 1}",
        ]
        if entry.run_spec.condition.instructions_text:
            body_parts.insert(0, entry.run_spec.condition.instructions_text)

        if session_plan.transition.mode == InterConditionMode.FIXED_BREAK:
            return self._engine.show_transition_screen(
                heading=heading,
                body="\n\n".join(body_parts),
                countdown_seconds=session_plan.transition.break_seconds,
                continue_key=None,
            )

        continue_key = session_plan.transition.continue_key or "space"
        body_parts.append(f"Press '{continue_key}' to continue.")
        return self._engine.show_transition_screen(
            heading=heading,
            body="\n\n".join(body_parts),
            countdown_seconds=None,
            continue_key=continue_key,
        )

    def _show_block_break(
        self,
        entry: SessionEntry,
        session_plan: SessionPlan,
    ) -> bool:
        if entry.block_index >= session_plan.block_count - 1:
            return False
        block = session_plan.blocks[entry.block_index]
        if entry.index_within_block != len(block.entries) - 1:
            return False
        return self._engine.show_block_break_screen(
            completed_block_index=entry.block_index,
            total_block_count=session_plan.block_count,
            next_block_index=entry.block_index + 1,
        )

    def _show_condition_feedback(
        self,
        run_spec: RunSpec,
        run_summary: RunExecutionSummary,
        *,
        previous_summary: FixationTaskSummary | None = None,
    ) -> bool:
        if not run_spec.fixation.accuracy_task_enabled:
            return False
        summary = run_summary.fixation_task_summary
        if summary is None:
            return False
        return self._engine.show_condition_feedback_screen(
            heading="Condition complete.",
            body=_format_condition_feedback(summary, previous_summary=previous_summary),
            continue_key="space",
        )


def _coerce_int(runtime_options: Mapping[str, object] | None, key: str) -> int | None:
    value = (runtime_options or {}).get(key)
    return value if isinstance(value, int) else None


def _estimate_refresh_hz(frame_intervals: list[FrameIntervalRecord]) -> float | None:
    intervals = [
        interval.interval_s
        for interval in frame_intervals
        if hasattr(interval, "interval_s") and getattr(interval, "interval_s") > 0
    ]
    if not intervals:
        return None
    return 1.0 / (sum(intervals) / len(intervals))


def _pick_session_runtime_metadata(
    run_results: list[RunExecutionSummary],
) -> RuntimeMetadata | None:
    for run_result in run_results:
        if run_result.runtime_metadata is not None:
            return run_result.runtime_metadata
    return None


def _run_mode(runtime_options: Mapping[str, object] | None) -> RunMode:
    return RunMode.TEST if bool((runtime_options or {}).get("test_mode")) else RunMode.SESSION


def _latest_fixation_task_summary(
    run_results: list[RunExecutionSummary],
) -> FixationTaskSummary | None:
    for run_result in reversed(run_results):
        if run_result.fixation_task_summary is not None:
            return run_result.fixation_task_summary
    return None


def _format_condition_feedback(
    summary: FixationTaskSummary,
    *,
    previous_summary: FixationTaskSummary | None = None,
) -> str:
    target_label = "color change" if summary.total_targets == 1 else "color changes"
    detected_line = (
        f"You successfully detected {summary.hit_count}/{summary.total_targets} {target_label}."
        if summary.total_targets > 0
        else "No color changes were scheduled in this condition."
    )
    mean_rt_line = (
        "Your average reaction time was not available for this condition."
        if summary.mean_rt_ms is None
        else f"Your average reaction time was {summary.mean_rt_ms:.0f} milliseconds."
    )
    false_alarm_line = (
        "Great timing: no extra responses were recorded."
        if summary.false_alarm_count == 0
        else (
            "You made 1 extra response outside a color change."
            if summary.false_alarm_count == 1
            else f"You made {summary.false_alarm_count} extra responses outside a color change."
        )
    )
    lines = [detected_line, mean_rt_line, false_alarm_line]
    comparison_line = _format_condition_feedback_comparison(summary, previous_summary)
    if comparison_line is not None:
        lines.append(comparison_line)
    return "\n".join(lines)


def _format_condition_feedback_comparison(
    summary: FixationTaskSummary,
    previous_summary: FixationTaskSummary | None,
) -> str | None:
    if previous_summary is None:
        return None

    accuracy_delta = summary.accuracy_percent - previous_summary.accuracy_percent
    if abs(accuracy_delta) < 0.05:
        accuracy_text = "your detection rate stayed about the same"
    elif accuracy_delta > 0:
        accuracy_text = f"your detection rate improved by {accuracy_delta:.1f} percentage points"
    else:
        accuracy_text = f"your detection rate dropped by {abs(accuracy_delta):.1f} percentage points"

    rt_text = _format_rt_comparison(summary.mean_rt_ms, previous_summary.mean_rt_ms)
    if rt_text is None:
        return f"Compared with the previous condition, {accuracy_text}."
    return f"Compared with the previous condition, {accuracy_text}, and {rt_text}."


def _format_rt_comparison(
    current_mean_rt_ms: float | None,
    previous_mean_rt_ms: float | None,
) -> str | None:
    if current_mean_rt_ms is None or previous_mean_rt_ms is None:
        return None

    rt_delta_ms = current_mean_rt_ms - previous_mean_rt_ms
    if abs(rt_delta_ms) < 0.5:
        return "your reaction time stayed about the same"
    if rt_delta_ms < 0:
        return f"you were {abs(rt_delta_ms):.0f} milliseconds faster"
    return f"you were {rt_delta_ms:.0f} milliseconds slower"
