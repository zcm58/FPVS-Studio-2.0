"""Session-local endpoint estimates for the reusable backward-counting tasks."""

from __future__ import annotations

from collections.abc import Callable

from fpvs_studio.core.backward_counting import (
    COUNTING_ENDPOINT_QUESTION_ID,
    COUNTING_INTERVAL_STEP_ID,
    COUNTING_READY_STEP_ID,
)
from fpvs_studio.core.execution import RunExecutionSummary
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.task_models import (
    BackwardCountingResult,
    BackwardCountingRole,
    TaskModuleSpec,
    TaskResponseRecord,
)


class BackwardCountingSession:
    """Retain interval state without placing participant answers in compiled specs."""

    def __init__(self) -> None:
        self._intervals: dict[tuple[str, str], BackwardCountingResult] = {}
        self._baselines: dict[int, float] = {}

    def record(
        self, module: TaskModuleSpec, response: TaskResponseRecord,
    ) -> TaskResponseRecord:
        spec = module.backward_counting
        if spec is None:
            return response
        key = (response.run_id, spec.link_id)
        if response.step_id == COUNTING_READY_STEP_ID:
            result = BackwardCountingResult(
                role=spec.role, link_id=spec.link_id, start_number=spec.start_number,
                subtraction_step=spec.subtraction_step,
                interval_seconds=spec.duration_seconds,
            )
            self._intervals[key] = result
        else:
            prior = self._intervals.get(key)
            if prior is None:
                raise ValueError("Backward-counting report has no started interval.")
            if (prior.start_number, prior.subtraction_step, prior.interval_seconds) != (
                spec.start_number, spec.subtraction_step, spec.duration_seconds,
            ):
                raise ValueError("Backward-counting report does not match its interval.")
            result = prior.model_copy(update={"role": spec.role})

        if response.step_id == COUNTING_INTERVAL_STEP_ID:
            observed = response.reaction_time_s
            result = result.model_copy(update={
                "interval_completed": (
                    response.valid and observed is not None
                    and observed >= spec.duration_seconds
                ),
                "observed_interval_seconds": observed,
            })
            self._intervals[key] = result

        if response.question_id == COUNTING_ENDPOINT_QUESTION_ID:
            raw_endpoint = response.numeric_value
            valid = (
                response.valid and raw_endpoint is not None
                and float(raw_endpoint).is_integer()
            )
            response = response.model_copy(update={"valid": valid})
            endpoint = int(raw_endpoint) if valid and raw_endpoint is not None else None
            baseline = self._baselines.get(spec.subtraction_step)
            updates: dict[str, object] = {
                "endpoint": endpoint,
                "baseline_steps_per_second": baseline,
            }
            if endpoint is not None and result.interval_completed:
                difference = spec.start_number - endpoint
                estimated_steps = difference / spec.subtraction_step
                rate = estimated_steps / spec.duration_seconds
                updates.update({
                    "estimated_steps": estimated_steps,
                    "subtraction_remainder": difference % spec.subtraction_step,
                    "steps_per_second": rate,
                    "baseline_rate_ratio": (
                        rate / baseline
                        if baseline is not None and baseline > 0 else None
                    ),
                })
                if spec.role == BackwardCountingRole.BASELINE:
                    self._baselines[spec.subtraction_step] = rate
            result = result.model_copy(update=updates)
        return response.model_copy(update={
            "backward_counting": result, "correct": None, "score": None,
        })

    def finish_run(
        self,
        summary: RunExecutionSummary,
        run_spec: RunSpec,
        *,
        checkpoint: Callable[[TaskResponseRecord], None],
    ) -> RunExecutionSummary:
        """Checkpoint interval completion before an endpoint screen can be interrupted."""

        if not any(response.backward_counting is not None
                   and response.backward_counting.role == BackwardCountingRole.LOAD_START
                   for response in summary.task_responses):
            return summary
        completed = (
            not summary.aborted
            and summary.completed_frames == run_spec.display.total_frames
        )
        intervals = summary.frame_intervals
        observed = (
            sum(interval.interval_s for interval in intervals)
            if summary.completed_frames > 0
            and len(intervals) == summary.completed_frames
            and {interval.frame_index for interval in intervals}
            == set(range(summary.completed_frames))
            else None
        )
        responses: list[TaskResponseRecord] = []
        for response in summary.task_responses:
            result = response.backward_counting
            if result is not None and result.role == BackwardCountingRole.LOAD_START:
                result = result.model_copy(update={
                    "interval_completed": completed,
                    "observed_interval_seconds": observed,
                })
                self._intervals[(summary.run_id, result.link_id)] = result
                response = response.model_copy(update={"backward_counting": result})
                # JSONL is append-only; the latest record for a response_index wins.
                checkpoint(response)
            responses.append(response)
        return summary.model_copy(update={"task_responses": responses})
