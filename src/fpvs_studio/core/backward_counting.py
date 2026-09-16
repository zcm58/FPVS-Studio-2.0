"""Reusable backward-counting modules and their ordinary participant screens."""

from __future__ import annotations

from fpvs_studio.core.task_models import (
    BackwardCountingConfig,
    BackwardCountingRole,
    BackwardCountingSpec,
    TaskModule,
    TaskQuestion,
    TaskQuestionKind,
    TaskStep,
    TaskStepKind,
    TaskSubmissionMode,
)

COUNTING_READY_STEP_ID = "counting-ready"
COUNTING_INTERVAL_STEP_ID = "counting-interval"
COUNTING_REPORT_STEP_ID = "counting-report"
COUNTING_ENDPOINT_QUESTION_ID = "counting-end-number"


def create_backward_counting_baseline_task(
    *,
    task_id: str = "backward-counting-baseline",
    name: str = "Backward-counting baseline",
    link_id: str = "backward-counting-baseline",
    subtraction_step: int = 13,
    duration_seconds: float = 120.0,
    start_min: int = 1000,
    start_max: int = 9999,
) -> TaskModule:
    """Build a timed counting interval followed by a typed endpoint report."""
    return TaskModule(
        task_id=task_id, name=name,
        backward_counting=BackwardCountingConfig(
            role=BackwardCountingRole.BASELINE, link_id=link_id,
            subtraction_step=subtraction_step, duration_seconds=duration_seconds,
            start_min=start_min, start_max=start_max,
        ),
    )


def create_backward_counting_start_task(
    *,
    task_id: str = "backward-counting-start",
    name: str = "Backward counting during FPVS",
    link_id: str = "backward-counting-load",
    subtraction_step: int = 13,
    duration_seconds: float = 120.0,
    start_min: int = 1000,
    start_max: int = 9999,
) -> TaskModule:
    """Introduce the number to hold until the FPVS images appear."""
    return TaskModule(
        task_id=task_id, name=name,
        backward_counting=BackwardCountingConfig(
            role=BackwardCountingRole.LOAD_START, link_id=link_id,
            subtraction_step=subtraction_step, duration_seconds=duration_seconds,
            start_min=start_min, start_max=start_max,
        ),
    )


def create_backward_counting_report_task(
    *,
    task_id: str = "backward-counting-report",
    name: str = "Backward-counting endpoint",
    link_id: str = "backward-counting-load",
    subtraction_step: int = 13,
    duration_seconds: float = 120.0,
    start_min: int = 1000,
    start_max: int = 9999,
) -> TaskModule:
    """Report an endpoint using the linked start module's realized settings."""
    return TaskModule(
        task_id=task_id, name=name,
        backward_counting=BackwardCountingConfig(
            role=BackwardCountingRole.LOAD_REPORT, link_id=link_id,
            subtraction_step=subtraction_step, duration_seconds=duration_seconds,
            start_min=start_min, start_max=start_max,
        ),
    )


def backward_counting_steps(spec: BackwardCountingSpec) -> list[TaskStep]:
    """Expand counting settings without adding a special presentation primitive."""
    steps: list[TaskStep] = []
    if spec.role != BackwardCountingRole.LOAD_REPORT:
        if spec.role == BackwardCountingRole.BASELINE:
            instructions = (
                f"Count backward silently by {spec.subtraction_step} for "
                f"{spec.duration_seconds:g} seconds. Keep your current number in mind. "
                "When the screen changes, stop and enter the number you reached. "
                "Negative numbers are allowed. Press Space to begin."
            )
        else:
            instructions = (
                f"Remember {spec.start_number}. Count backward silently by "
                f"{spec.subtraction_step} while watching the images. "
                "Start counting only when the images appear; stop when the images disappear. "
                "Then enter the number you reached. Negative numbers are allowed. "
                "Press Space when ready."
            )
        if spec.instructions is not None:
            instructions = (
                (f"Remember {spec.start_number}. Subtract {spec.subtraction_step}.\n"
                 if spec.role == BackwardCountingRole.LOAD_START else "")
                + spec.instructions
            )
        steps.append(TaskStep(
            step_id=COUNTING_READY_STEP_ID, kind=TaskStepKind.INSTRUCTION,
            text=instructions, continue_key="space",
        ))
    if spec.role == BackwardCountingRole.BASELINE:
        steps.append(TaskStep(
            step_id=COUNTING_INTERVAL_STEP_ID, kind=TaskStepKind.TIMED_FEEDBACK,
            text=f"Start at {spec.start_number}.\nKeep subtracting {spec.subtraction_step}.",
            duration_seconds=spec.duration_seconds,
        ))
    if spec.role != BackwardCountingRole.LOAD_START:
        steps.append(TaskStep(
            step_id=COUNTING_REPORT_STEP_ID, kind=TaskStepKind.QUESTIONNAIRE,
            text="Stop counting.", submit_label="Next",
            submission_mode=TaskSubmissionMode.EXPLICIT,
            retry_on_invalid=True, max_attempts=3,
            questions=[TaskQuestion(
                question_id=COUNTING_ENDPOINT_QUESTION_ID, kind=TaskQuestionKind.NUMERIC,
                prompt=spec.endpoint_prompt or ("What number did you reach? Enter a whole number, "
                        "including a minus sign if needed."),
                min_value=-(2**53 - 1), max_value=2**53 - 1, step=1,
            )],
        ))
    return steps
