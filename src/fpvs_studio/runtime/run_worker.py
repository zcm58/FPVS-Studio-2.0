"""Runtime worker that executes run specs through a presentation engine."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from fpvs_studio.core.enums import InterConditionMode, RunMode
from fpvs_studio.core.execution import (
    RunExecutionSummary,
    RuntimeMetadata,
    SessionExecutionSummary,
    FrameIntervalRecord,
)
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.session_plan import SessionEntry, SessionPlan
from fpvs_studio.engines.base import PresentationEngine
from fpvs_studio.runtime.fixation import score_fixation_responses
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
                trigger_backend=trigger_backend,
                trigger_start_index=trigger_start_index,
                warnings=trigger_warnings,
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
                    trigger_backend=trigger_backend,
                    trigger_start_index=trigger_start_index,
                    warnings=(),
                )
                warnings.extend(run_summary.warnings)
                run_results.append(run_summary)
                write_run_artifacts(run_output_dir, entry.run_spec, run_summary)

                if run_summary.aborted:
                    abort_reason = run_summary.abort_reason or f"Run '{entry.run_id}' was aborted."
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
        trigger_backend: LoggedTriggerBackend,
        trigger_start_index: int,
        warnings: list[str] | tuple[str, ...],
    ) -> RunExecutionSummary:
        scored_fixation_responses = run_summary.fixation_responses
        scored_response_log = run_summary.response_log
        if not scored_fixation_responses:
            scored_fixation_responses, scored_response_log = score_fixation_responses(
                run_spec.fixation_events,
                run_summary.response_log,
            )

        runtime_metadata = run_summary.runtime_metadata or RuntimeMetadata(
            engine_name=self._engine.engine_id,
            display_index=_coerce_int(runtime_options, "display_index"),
            fullscreen=not bool((runtime_options or {}).get("test_mode")),
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
                "warnings": combined_warnings,
                "runtime_metadata": runtime_metadata,
                "fixation_responses": scored_fixation_responses,
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
