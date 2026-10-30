"""Simple post-condition questionnaires and immutable original execution context."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from fpvs_studio.core.task_models import (
    PostQuestionDefinition,
    PostQuestionnaireContext,
    TaskBinding,
    TaskModule,
    TaskModuleSpec,
    TaskOccurrence,
    TaskOption,
    TaskPhase,
    TaskQuestion,
    TaskQuestionKind,
    TaskStep,
    TaskStepKind,
    TaskSubmissionMode,
)

if TYPE_CHECKING:
    from fpvs_studio.core.models import ProjectFile


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def make_yes_no_question(prompt: str, *, question_id: str | None = None) -> TaskQuestion:
    """Create required unscored Yes/No answers with stable option identities."""

    return TaskQuestion(
        question_id=_new_id("question") if question_id is None else question_id,
        kind=TaskQuestionKind.SINGLE_CHOICE,
        prompt=prompt, required=True,
        options=[TaskOption(option_id="yes", label="Yes"), TaskOption(option_id="no", label="No")],
    )


def make_post_questionnaire(
    questions: Sequence[TaskQuestion], *, task_id: str | None = None,
    name: str = "Post-condition Questions",
) -> TaskModule:
    """Create one ordinary after-only module, with deliberate self-paced submission."""

    return TaskModule(
        task_id=_new_id("post-questions") if task_id is None else task_id,
        name=name, simple_post_questions=True,
        steps=[TaskStep(
            step_id="questions", kind=TaskStepKind.QUESTIONNAIRE,
            questions=[question.model_copy(deep=True) for question in questions],
            submission_mode=TaskSubmissionMode.EXPLICIT, submit_label="Continue",
        )],
    )


def validate_simple_post_questionnaire(module: TaskModule | TaskModuleSpec) -> None:
    """Refuse complex flows whose answers cannot represent one final value per question."""

    if (module.repeat_count != 1 or module.backward_counting is not None
            or module.image_memory is not None or getattr(module, "modifier", None) is not None
            or not module.steps):
        raise ValueError(
                "Post-condition Questions require a separate questionnaire that runs once."
            )
    for step in module.steps:
        if (step.kind != TaskStepKind.QUESTIONNAIRE or not step.questions or step.items
                or step.repeat_count != 1 or step.max_attempts != 1 or step.branch_rules
                or step.retry_on_invalid or step.retry_on_incorrect):
            raise ValueError(
                "Post-condition Questions support one pass without branching, repeats or retries. "
                "Keep complex tasks in the advanced custom flow."
            )
        if step.submission_mode != TaskSubmissionMode.EXPLICIT:
            raise ValueError("Post-condition Questions require an explicit Continue submission.")


def question_definition_version(question: TaskQuestion) -> str:
    """Version original authored meaning before any execution option shuffle."""

    encoded = json.dumps(question.model_dump(mode="json"), sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_post_question_bindings(
    *, pre_bindings: Sequence[TaskBinding], post_bindings: Sequence[TaskBinding],
    modules: Sequence[TaskModule],
) -> None:
    """Keep marked flows after every presentation at source/config boundaries."""

    simple_ids = {module.task_id for module in modules if module.simple_post_questions}
    if any(binding.task_id in simple_ids for binding in pre_bindings):
        raise ValueError("Post-condition Questions may only run after each presentation.")
    marked_ids = [binding.task_id for binding in post_bindings if binding.task_id in simple_ids]
    if len(marked_ids) != len(set(marked_ids)):
        raise ValueError("Post-condition Questions may only run once per condition presentation.")
    if any(binding.task_id in simple_ids and (
        binding.occurrence != TaskOccurrence.EVERY_ENTRY or binding.replaces_condition_start_gate
    ) for binding in post_bindings):
        raise ValueError("Post-condition Questions must run after every presentation.")


def compile_post_question_context(
    module: TaskModule, *, condition_id: str, condition_name: str,
    presentation_index: int, presentation_count: int,
) -> PostQuestionnaireContext:
    """Snapshot original question wording/labels and chronological condition occurrence."""

    validate_simple_post_questionnaire(module)
    return PostQuestionnaireContext(
        task_id=module.task_id, task_name=module.name,
        condition_id=condition_id, condition_name=condition_name,
        condition_presentation_index=presentation_index,
        condition_presentation_count=presentation_count,
        questions=tuple(PostQuestionDefinition.model_validate({
            **question.model_dump(mode="json"), "step_id": step.step_id,
            "definition_version": question_definition_version(question),
        }) for step in module.steps for question in step.questions),
    )


def validate_compiled_post_questions(module: TaskModuleSpec) -> None:
    """Verify an immutable marked context against the actual displayed compiled questions."""

    context = module.post_question_context
    if context is None:
        return
    PostQuestionnaireContext.model_validate(context.model_dump())
    validate_simple_post_questionnaire(module)
    if (module.phase != TaskPhase.POST_CONDITION or module.occurrence != TaskOccurrence.EVERY_ENTRY
            or context.task_id != module.task_id or context.task_name != module.name):
        raise ValueError(
                "Post-question context requires its original every-presentation post module."
            )
    ordered_questions = [(step.step_id, question) for step in module.steps
                         for question in step.questions]
    expected = [(question.step_id, question.question_id) for question in context.questions]
    if [(step_id, question.question_id) for step_id, question in ordered_questions] != expected:
        raise ValueError("Compiled questions do not match the original post-question context.")
    compiled = {(step_id, question.question_id): question
                for step_id, question in ordered_questions}
    for original in context.questions:
        question = compiled[(original.step_id, original.question_id)]
        authored = original.model_dump(mode="json", exclude={"step_id", "definition_version"})
        displayed = question.model_dump(mode="json")
        original_options = authored.pop("options")
        displayed_options = displayed.pop("options")
        if (authored != displayed or
                {item["option_id"]: item for item in original_options}
                != {item["option_id"]: item for item in displayed_options}):
            raise ValueError(
                "Compiled question wording or answer labels differ from its original context."
            )


def apply_post_questionnaire(
    project: ProjectFile, module: TaskModule, condition_ids: Sequence[str], *,
    scope: Literal["private", "shared"] = "private",
) -> ProjectFile:
    """Apply an explicit assignment/edit without moving unrelated condition activities."""

    if not module.simple_post_questions:
        raise ValueError("Select the marked Post-condition Questions flow.")
    validate_simple_post_questionnaire(module)
    selected = set(condition_ids)
    if not selected or selected - {condition.condition_id for condition in project.conditions}:
        raise ValueError("Select existing conditions for the questionnaire.")
    if scope not in {"private", "shared"}:
        raise ValueError("Choose private or shared questionnaire editing.")
    draft = project.model_copy(deep=True)
    existing = next((item for item in draft.task_modules if item.task_id == module.task_id), None)
    if existing is not None and not existing.simple_post_questions:
        raise ValueError("An unrelated custom task already uses this questionnaire identity.")
    outside = any(condition.condition_id not in selected and any(
        binding.task_id == module.task_id for binding in condition.post_task_bindings
    ) for condition in draft.conditions)
    target = module.model_copy(deep=True)
    if existing is not None and scope == "private" and outside:
        if any(option.image_path is not None for step in module.steps
               for question in step.questions for option in question.options):
            raise ValueError(
                "Copy questionnaire media through the advanced editor before private edits."
            )
        target.task_id = _new_id("post-questions")
    draft.task_modules = [item for item in draft.task_modules if item.task_id != target.task_id]
    draft.task_modules.append(target)
    for condition in draft.conditions:
        if condition.condition_id in selected:
            bindings = list(condition.post_task_bindings)
            if any(binding.task_id == module.task_id for binding in bindings):
                condition.post_task_bindings = [
                    TaskBinding(task_id=target.task_id)
                    if binding.task_id == module.task_id else binding
                    for binding in bindings
                ]
            else:
                condition.post_task_bindings.append(TaskBinding(task_id=target.task_id))
        elif scope == "shared":
            condition.post_task_bindings = [binding for binding in condition.post_task_bindings
                                            if binding.task_id != target.task_id]
    return type(project).model_validate(draft.model_dump())


def remove_post_questionnaire(
    project: ProjectFile, task_id: str, condition_ids: Sequence[str],
) -> ProjectFile:
    """Unassign only the selected conditions; leave shared definitions/bindings intact."""

    module = next((item for item in project.task_modules if item.task_id == task_id), None)
    if module is None or not module.simple_post_questions:
        raise ValueError("Select an existing Post-condition Questions module.")
    selected = set(condition_ids)
    if not selected or selected - {condition.condition_id for condition in project.conditions}:
        raise ValueError("Select existing conditions for questionnaire removal.")
    draft = project.model_copy(deep=True)
    for condition in draft.conditions:
        if condition.condition_id in selected:
            condition.post_task_bindings = [binding for binding in condition.post_task_bindings
                                            if binding.task_id != task_id]
    if not any(binding.task_id == task_id for condition in draft.conditions
               for binding in [*condition.pre_task_bindings, *condition.post_task_bindings]):
        draft.task_modules = [item for item in draft.task_modules if item.task_id != task_id]
    return type(project).model_validate(draft.model_dump())
