"""Editable, compiled, and execution contracts for modular condition tasks.

Task clocks live outside :class:`RunSpec`.  Editable modules are project-owned and
conditions bind them before or after one session entry; session compilation resolves
those bindings into neutral specs for runtime and engines.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from enum import Enum
from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from fpvs_studio.core.enums import PresentationUnit
from fpvs_studio.core.paths import validate_project_relative_path

MAX_TASK_TEXT_CHARS = 16_384
MAX_TASK_RESPONSE_TEXT_CHARS = 16_384
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_BIDI_CONTROL_CODEPOINTS = {
    codepoint: None
    for codepoint in (
        0x061C,
        0x200E,
        0x200F,
        0x202A,
        0x202B,
        0x202C,
        0x202D,
        0x202E,
        0x2066,
        0x2067,
        0x2068,
        0x2069,
    )
}


class TaskBaseModel(BaseModel):
    """Strict base for persisted and compiled task contracts."""

    model_config = ConfigDict(extra="forbid", validate_default=True)


def validate_task_slug(value: str, *, field_name: str) -> str:
    if not _SLUG_RE.fullmatch(value):
        raise ValueError(f"{field_name} must contain only lowercase letters, digits, and hyphens.")
    return value


def _validate_response_key_name(value: str) -> str:
    cleaned = value.strip().lower()
    if not cleaned:
        raise ValueError("Response key may not be blank.")
    if cleaned == "escape":
        raise ValueError("'escape' is reserved for abort and cannot be a response key.")
    return cleaned


class TaskPhase(str, Enum):
    """Where a bound module runs relative to timed FPVS playback."""

    PRE_CONDITION = "pre_condition"
    POST_CONDITION = "post_condition"


class TaskOccurrence(str, Enum):
    """Which occurrences of one condition receive a bound module."""

    EVERY_ENTRY = "every_entry"
    FIRST_OCCURRENCE = "first_occurrence"
    LAST_OCCURRENCE = "last_occurrence"


class TaskStepKind(str, Enum):
    """Reusable participant-facing task primitives."""

    INSTRUCTION = "instruction"
    STUDY = "study"
    CHOICE_GRID = "choice_grid"
    QUESTIONNAIRE = "questionnaire"
    RAW_KEY = "raw_key"
    TIMED_FEEDBACK = "timed_feedback"


class TaskItemModality(str, Enum):
    """Display payload type for a study or choice-grid item."""

    TEXT = "text"
    IMAGE = "image"


class TaskQuestionKind(str, Enum):
    """Supported questionnaire response controls."""

    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_TEXT = "short_text"
    LONG_TEXT = "long_text"
    NUMERIC = "numeric"
    RATING = "rating"


class TaskResponseKind(str, Enum):
    """Neutral participant-input payload kind returned by an engine."""

    NONE = "none"
    KEY = "key"
    OPTION_SELECTION = "option_selection"
    TEXT = "text"
    NUMERIC = "numeric"
    RATING = "rating"


class TaskLayoutMode(str, Enum):
    """How a task renderer positions display items."""

    RESPONSIVE_GRID = "responsive_grid"
    EXACT = "exact"


class TaskFontFamily(str, Enum):
    """Font families supported by the portable modular-task renderer."""

    ARIAL = "Arial"
    OPEN_SANS = "Open Sans"


class TaskSubmissionMode(str, Enum):
    """Whether a response completes immediately or waits for an explicit submit."""

    IMMEDIATE = "immediate"
    EXPLICIT = "explicit"


class TaskBranchOperator(str, Enum):
    """Bounded conditional operators; authored task data is never executable code."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    ANSWERED = "answered"


def _clean_task_text(value: str, *, field_name: str, allow_blank: bool = True) -> str:
    cleaned = value.translate(_BIDI_CONTROL_CODEPOINTS)
    if not allow_blank and not cleaned.strip():
        raise ValueError(f"{field_name} may not be blank.")
    if len(cleaned) > MAX_TASK_TEXT_CHARS:
        raise ValueError(f"{field_name} may not exceed {MAX_TASK_TEXT_CHARS} characters.")
    return cleaned


class TaskDisplayItem(TaskBaseModel):
    """One positioned image or text item in a study/choice surface."""

    item_id: str
    modality: TaskItemModality
    text: str | None = None
    image_path: str | None = None
    x: float = 0.0
    y: float = 0.0
    width: float | None = Field(default=None, gt=0)
    height: float | None = Field(default=None, gt=0)
    unit: PresentationUnit = PresentationUnit.DEGREES
    selectable: bool = False
    correct: bool | None = None
    score: float | None = None

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, value: str) -> str:
        return validate_task_slug(value, field_name="item_id")

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_task_text(value, field_name="Task item text", allow_blank=False)

    @field_validator("image_path")
    @classmethod
    def validate_image_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_project_relative_path(value)

    @field_validator("x", "y", "width", "height", "score")
    @classmethod
    def validate_finite_number(cls, value: float | None) -> float | None:
        if value is None:
            return None
        normalized = float(value)
        if not isfinite(normalized):
            raise ValueError("Task layout and score values must be finite.")
        return normalized

    @model_validator(mode="after")
    def validate_payload(self) -> TaskDisplayItem:
        if self.modality == TaskItemModality.IMAGE:
            if self.image_path is None or self.text is not None:
                raise ValueError("Image task items require image_path and may not store text.")
        elif self.modality == TaskItemModality.TEXT:
            if self.text is None or self.image_path is not None:
                raise ValueError("Text task items require text and may not store image_path.")
        if not self.selectable and (self.correct is not None or self.score is not None):
            raise ValueError("Only selectable task items may define correctness or score.")
        return self


class TaskOption(TaskBaseModel):
    """One stable questionnaire option, independent of realized display order."""

    option_id: str
    label: str
    image_path: str | None = None
    selectable: bool = True
    correct: bool | None = None
    score: float | None = None

    @field_validator("option_id")
    @classmethod
    def validate_option_id(cls, value: str) -> str:
        return validate_task_slug(value, field_name="option_id")

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        return _clean_task_text(value, field_name="Task option label", allow_blank=False)

    @field_validator("image_path")
    @classmethod
    def validate_image_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_project_relative_path(value)

    @field_validator("score")
    @classmethod
    def validate_score(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(float(value)):
            raise ValueError("Task option score must be finite.")
        return value

    @model_validator(mode="after")
    def validate_selectable_metadata(self) -> TaskOption:
        if not self.selectable and (self.correct is not None or self.score is not None):
            raise ValueError("Only selectable task options may define correctness or score.")
        return self


class TaskQuestion(TaskBaseModel):
    """One generic questionnaire question."""

    question_id: str
    kind: TaskQuestionKind
    prompt: str
    required: bool = True
    options: list[TaskOption] = Field(default_factory=list)
    randomize_options: bool = False
    min_selections: int | None = Field(default=None, ge=0)
    max_selections: int | None = Field(default=None, ge=1)
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = Field(default=None, gt=0)
    min_label: str | None = None
    max_label: str | None = None
    max_text_length: int = Field(default=2_000, ge=1, le=MAX_TASK_RESPONSE_TEXT_CHARS)

    @field_validator("question_id")
    @classmethod
    def validate_question_id(cls, value: str) -> str:
        return validate_task_slug(value, field_name="question_id")

    @field_validator("prompt", "min_label", "max_label")
    @classmethod
    def validate_text_fields(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        field_name = getattr(info, "field_name", "Question text")
        return _clean_task_text(
            value,
            field_name=field_name,
            allow_blank=field_name != "prompt",
        )

    @field_validator("min_value", "max_value", "step")
    @classmethod
    def validate_numeric_bounds(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(float(value)):
            raise ValueError("Question numeric values must be finite.")
        return value

    @model_validator(mode="after")
    def validate_question_shape(self) -> TaskQuestion:
        option_ids = [option.option_id for option in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise ValueError("Task question option ids must be unique.")
        choice_kinds = {
            TaskQuestionKind.SINGLE_CHOICE,
            TaskQuestionKind.MULTIPLE_CHOICE,
        }
        if self.kind in choice_kinds:
            if not self.options:
                raise ValueError("Choice questions require at least one option.")
            selectable_count = sum(option.selectable for option in self.options)
            minimum = self.min_selections if self.min_selections is not None else int(self.required)
            maximum = self.max_selections
            if self.kind == TaskQuestionKind.SINGLE_CHOICE:
                maximum = 1 if maximum is None else maximum
                if maximum != 1 or minimum > 1:
                    raise ValueError("Single-choice questions allow at most one selection.")
            elif maximum is None:
                maximum = selectable_count
            if minimum > maximum or maximum > selectable_count:
                raise ValueError("Question selection limits exceed selectable options.")
        elif self.options:
            raise ValueError("Only choice questions may define options.")
        if self.kind in {TaskQuestionKind.NUMERIC, TaskQuestionKind.RATING}:
            if self.min_value is None or self.max_value is None:
                raise ValueError("Numeric and rating questions require min_value and max_value.")
            if self.min_value >= self.max_value:
                raise ValueError("Question min_value must be less than max_value.")
            if self.kind == TaskQuestionKind.RATING:
                rating_step = self.step or 1.0
                span_steps = (self.max_value - self.min_value) / rating_step
                if abs(span_steps - round(span_steps)) > 1e-9:
                    raise ValueError("Rating range must align exactly to its step.")
                if int(round(span_steps)) + 1 > 100:
                    raise ValueError("Rating questions support at most 100 ticks.")
        elif any(value is not None for value in (self.min_value, self.max_value, self.step)):
            raise ValueError("Only numeric and rating questions may define numeric bounds.")
        return self


class TaskBranchRule(TaskBaseModel):
    """One validated conditional jump evaluated by runtime."""

    rule_id: str
    question_id: str
    operator: TaskBranchOperator
    expected_values: list[str] = Field(default_factory=list)
    expected_numeric: float | None = None
    next_step_id: str

    @field_validator("rule_id", "question_id", "next_step_id")
    @classmethod
    def validate_ids(cls, value: str, info: object) -> str:
        return validate_task_slug(value, field_name=getattr(info, "field_name", "task id"))

    @field_validator("expected_values")
    @classmethod
    def validate_expected_values(cls, value: list[str]) -> list[str]:
        return [
            _clean_task_text(item, field_name="Branch expected value", allow_blank=False)
            for item in value
        ]

    @field_validator("expected_numeric")
    @classmethod
    def validate_expected_numeric(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(float(value)):
            raise ValueError("Branch comparison value must be finite.")
        return value

    @model_validator(mode="after")
    def validate_comparison(self) -> TaskBranchRule:
        numeric = self.operator in {
            TaskBranchOperator.GREATER_THAN,
            TaskBranchOperator.LESS_THAN,
        }
        if numeric and self.expected_numeric is None:
            raise ValueError("Numeric branch operators require expected_numeric.")
        if (
            not numeric
            and self.operator != TaskBranchOperator.ANSWERED
            and not self.expected_values
        ):
            raise ValueError("This branch operator requires expected_values.")
        return self


class TaskStep(TaskBaseModel):
    """One editable declarative task step."""

    step_id: str
    kind: TaskStepKind
    heading: str = ""
    text: str = ""
    font_family: TaskFontFamily = TaskFontFamily.ARIAL
    prompt_x: float = 0.0
    prompt_y: float = 0.0
    prompt_unit: PresentationUnit = PresentationUnit.DEGREES
    prompt_height: float | None = Field(default=None, gt=0)
    show_footer: bool = True
    layout_mode: TaskLayoutMode = TaskLayoutMode.RESPONSIVE_GRID
    columns: int | None = Field(default=None, ge=1)
    submission_mode: TaskSubmissionMode = TaskSubmissionMode.IMMEDIATE
    items: list[TaskDisplayItem] = Field(default_factory=list)
    questions: list[TaskQuestion] = Field(default_factory=list)
    continue_key: str | None = None
    allowed_keys: list[str] = Field(default_factory=list)
    duration_seconds: float | None = Field(default=None, gt=0)
    timeout_seconds: float | None = Field(default=None, gt=0)
    repeat_count: int = Field(default=1, ge=1)
    max_attempts: int = Field(default=1, ge=1)
    retry_on_invalid: bool = False
    retry_on_incorrect: bool = False
    randomize_options: bool = False
    require_response: bool = False
    min_selections: int = Field(default=1, ge=0)
    max_selections: int = Field(default=1, ge=1)
    allow_duplicate_selections_across_repeats: bool = True
    branch_rules: list[TaskBranchRule] = Field(default_factory=list)

    @field_validator("step_id")
    @classmethod
    def validate_step_id(cls, value: str) -> str:
        return validate_task_slug(value, field_name="step_id")

    @field_validator("heading", "text")
    @classmethod
    def validate_text(cls, value: str, info: object) -> str:
        return _clean_task_text(value, field_name=getattr(info, "field_name", "Task text"))

    @field_validator("continue_key")
    @classmethod
    def validate_continue_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_response_key_name(value)

    @field_validator("allowed_keys")
    @classmethod
    def validate_allowed_keys(cls, value: list[str]) -> list[str]:
        normalized = [_validate_response_key_name(item) for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Task allowed_keys must not contain duplicates.")
        return normalized

    @field_validator("duration_seconds", "timeout_seconds")
    @classmethod
    def validate_durations(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(float(value)):
            raise ValueError("Task durations must be finite.")
        return value

    @field_validator("prompt_x", "prompt_y", "prompt_height")
    @classmethod
    def validate_prompt_geometry(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(float(value)):
            raise ValueError("Task prompt geometry must be finite.")
        return value

    @model_validator(mode="after")
    def validate_step_shape(self) -> TaskStep:
        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Task step item ids must be unique.")
        question_ids = [question.question_id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Task step question ids must be unique.")
        rule_ids = [rule.rule_id for rule in self.branch_rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("Task step branch rule ids must be unique.")
        if self.min_selections > self.max_selections:
            raise ValueError("Task min_selections must not exceed max_selections.")
        if (self.retry_on_invalid or self.retry_on_incorrect) and self.max_attempts < 2:
            raise ValueError("Retry policies require max_attempts of at least two.")
        if self.kind in {TaskStepKind.STUDY, TaskStepKind.CHOICE_GRID} and not self.items:
            raise ValueError(f"{self.kind.value} steps require display items.")
        if self.layout_mode == TaskLayoutMode.EXACT:
            if not self.items and self.prompt_height is None:
                raise ValueError(
                    "Exact task layout requires positioned display items or an authored "
                    "prompt height."
                )
            if any(
                item.height is None
                or (item.modality == TaskItemModality.IMAGE and item.width is None)
                for item in self.items
            ):
                raise ValueError(
                    "Exact task layout requires every item height and every image width."
                )
            if self.columns is not None:
                raise ValueError("Exact task layout may not define responsive grid columns.")
        if self.kind == TaskStepKind.CHOICE_GRID:
            selectable_count = sum(item.selectable for item in self.items)
            if not selectable_count:
                raise ValueError("Choice-grid steps require at least one selectable item.")
            if self.max_selections > selectable_count:
                raise ValueError("Task selection limit exceeds selectable choice-grid items.")
            if (
                self.submission_mode == TaskSubmissionMode.IMMEDIATE
                and self.min_selections != self.max_selections
            ):
                raise ValueError(
                    "Immediate choice grids require equal minimum and maximum selections; "
                    "use explicit submission for a range."
                )
        elif self.min_selections != 1 or self.max_selections != 1:
            raise ValueError("Only choice-grid steps may customize selection limits.")
        if self.kind == TaskStepKind.QUESTIONNAIRE and not self.questions:
            raise ValueError("Questionnaire steps require at least one question.")
        if self.kind == TaskStepKind.QUESTIONNAIRE:
            optional_immediate_choice = any(
                not question.required
                and question.kind
                in {
                    TaskQuestionKind.SINGLE_CHOICE,
                    TaskQuestionKind.MULTIPLE_CHOICE,
                    TaskQuestionKind.RATING,
                }
                for question in self.questions
            )
            if (
                optional_immediate_choice
                and self.submission_mode == TaskSubmissionMode.IMMEDIATE
                and self.timeout_seconds is None
            ):
                raise ValueError(
                    "Optional choice and rating questions require explicit submission "
                    "or a timeout."
                )
            ranged_immediate_multiple = any(
                question.kind == TaskQuestionKind.MULTIPLE_CHOICE
                and (question.min_selections or int(question.required))
                != (
                    question.max_selections
                    if question.max_selections is not None
                    else sum(option.selectable for option in question.options)
                )
                for question in self.questions
            )
            if (
                ranged_immediate_multiple
                and self.submission_mode == TaskSubmissionMode.IMMEDIATE
            ):
                raise ValueError(
                    "Immediate multiple-choice questions require equal minimum and "
                    "maximum selections; use explicit submission for a range."
                )
        if self.kind != TaskStepKind.QUESTIONNAIRE and self.questions:
            raise ValueError("Only questionnaire steps may define questions.")
        if self.kind == TaskStepKind.RAW_KEY and not self.allowed_keys:
            raise ValueError("Raw-key steps require allowed_keys.")
        if self.kind == TaskStepKind.TIMED_FEEDBACK and self.duration_seconds is None:
            raise ValueError("Timed-feedback steps require duration_seconds.")
        if self.kind == TaskStepKind.TIMED_FEEDBACK and (
            self.continue_key is not None or self.allowed_keys
        ):
            raise ValueError("Timed-feedback steps cannot define response keys.")
        if (
            self.submission_mode != TaskSubmissionMode.IMMEDIATE
            and self.kind
            not in {
                TaskStepKind.CHOICE_GRID,
                TaskStepKind.QUESTIONNAIRE,
            }
        ):
            raise ValueError(
                "Explicit submission is supported only for choice-grid and questionnaire steps."
            )
        if self.kind in {TaskStepKind.INSTRUCTION, TaskStepKind.STUDY}:
            if self.continue_key is None and self.duration_seconds is None:
                raise ValueError("Instruction and study steps require a continue key or duration.")
        return self


def _validate_no_duplicate_repeat_capacity(
    *,
    task_id: str,
    module_repeat_count: int,
    steps: Sequence[TaskStep],
) -> None:
    """Reject repeat plans that can exhaust a required no-duplicate response pool."""

    for step in steps:
        total_repetitions = module_repeat_count * step.repeat_count
        if step.allow_duplicate_selections_across_repeats or total_repetitions <= 1:
            continue
        if step.kind == TaskStepKind.CHOICE_GRID:
            _validate_selection_pool_capacity(
                task_id=task_id,
                step_id=step.step_id,
                response_id=None,
                available=sum(item.selectable for item in step.items),
                minimum=step.min_selections,
                maximum=step.max_selections,
                total_repetitions=total_repetitions,
            )
            continue
        if step.kind != TaskStepKind.QUESTIONNAIRE:
            continue
        for question in step.questions:
            if question.kind in {
                TaskQuestionKind.SINGLE_CHOICE,
                TaskQuestionKind.MULTIPLE_CHOICE,
            }:
                selectable_count = sum(option.selectable for option in question.options)
                minimum = question.min_selections
                if minimum is None:
                    minimum = int(question.required)
                maximum = question.max_selections
                if maximum is None:
                    maximum = (
                        1
                        if question.kind == TaskQuestionKind.SINGLE_CHOICE
                        else selectable_count
                    )
                available = selectable_count
            elif question.kind == TaskQuestionKind.RATING:
                assert question.min_value is not None
                assert question.max_value is not None
                rating_step = question.step or 1.0
                available = (
                    int(round((question.max_value - question.min_value) / rating_step)) + 1
                )
                minimum = int(question.required)
                maximum = 1
            else:
                continue
            _validate_selection_pool_capacity(
                task_id=task_id,
                step_id=step.step_id,
                response_id=question.question_id,
                available=available,
                minimum=minimum,
                maximum=maximum,
                total_repetitions=total_repetitions,
            )


def _validate_selection_pool_capacity(
    *,
    task_id: str,
    step_id: str,
    response_id: str | None,
    available: int,
    minimum: int,
    maximum: int,
    total_repetitions: int,
) -> None:
    if minimum <= 0:
        return
    response_label = (
        f"question '{response_id}' in step '{step_id}'"
        if response_id is not None
        else f"step '{step_id}'"
    )
    if minimum != maximum:
        raise ValueError(
            f"Task '{task_id}' {response_label} disables duplicate selections across "
            "repeats, so its minimum and maximum selections must be equal."
        )
    required = minimum * total_repetitions
    if available < required:
        raise ValueError(
            f"Task '{task_id}' {response_label} disables duplicate selections across "
            f"{total_repetitions} repetitions but requires {required} distinct "
            f"selections from only {available} available options."
        )


class TaskModule(TaskBaseModel):
    """Reusable project-owned ordered task definition."""

    task_id: str
    name: str
    repeat_count: int = Field(default=1, ge=1)
    steps: list[TaskStep] = Field(default_factory=list)

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, value: str) -> str:
        return validate_task_slug(value, field_name="task_id")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _clean_task_text(value, field_name="Task name", allow_blank=False)

    @model_validator(mode="after")
    def validate_steps(self) -> TaskModule:
        step_ids = [step.step_id for step in self.steps]
        if not self.steps:
            raise ValueError("Task modules require at least one step.")
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Task module step ids must be unique.")
        known_steps = set(step_ids)
        question_ids = [
            question.question_id for step in self.steps for question in step.questions
        ]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Question ids must be unique across one task module.")
        known_questions = set(question_ids)
        question_step_index = {
            question.question_id: step_index
            for step_index, step in enumerate(self.steps)
            for question in step.questions
        }
        questions_by_id = {
            question.question_id: question
            for step in self.steps
            for question in step.questions
        }
        step_index_by_id = {step.step_id: index for index, step in enumerate(self.steps)}
        for step_index, step in enumerate(self.steps):
            for rule in step.branch_rules:
                if rule.next_step_id not in known_steps:
                    raise ValueError(
                        f"Branch rule '{rule.rule_id}' references unknown step "
                        f"'{rule.next_step_id}'."
                    )
                if rule.question_id not in known_questions:
                    raise ValueError(
                        f"Branch rule '{rule.rule_id}' references unknown question "
                        f"'{rule.question_id}'."
                    )
                if step_index_by_id[rule.next_step_id] <= step_index:
                    raise ValueError(
                        f"Branch rule '{rule.rule_id}' must jump forward to keep task "
                        "flow terminating."
                    )
                if question_step_index[rule.question_id] > step_index:
                    raise ValueError(
                        f"Branch rule '{rule.rule_id}' cannot inspect a future question."
                    )
                question = questions_by_id[rule.question_id]
                numeric_operators = {
                    TaskBranchOperator.GREATER_THAN,
                    TaskBranchOperator.LESS_THAN,
                }
                if rule.operator in numeric_operators and question.kind not in {
                    TaskQuestionKind.NUMERIC,
                    TaskQuestionKind.RATING,
                }:
                    raise ValueError(
                        f"Branch rule '{rule.rule_id}' uses a numeric operator with "
                        f"non-numeric question '{question.question_id}'."
                    )
                if question.kind in {
                    TaskQuestionKind.NUMERIC,
                    TaskQuestionKind.RATING,
                } and rule.operator in {
                    TaskBranchOperator.EQUALS,
                    TaskBranchOperator.NOT_EQUALS,
                    TaskBranchOperator.CONTAINS,
                }:
                    raise ValueError(
                        f"Branch rule '{rule.rule_id}' uses a text/choice operator with "
                        f"numeric question '{question.question_id}'. Use greater-than, "
                        "less-than, or answered."
                    )
                if question.kind in {
                    TaskQuestionKind.SINGLE_CHOICE,
                    TaskQuestionKind.MULTIPLE_CHOICE,
                } and rule.operator in {
                    TaskBranchOperator.EQUALS,
                    TaskBranchOperator.NOT_EQUALS,
                    TaskBranchOperator.CONTAINS,
                }:
                    known_option_ids = {option.option_id for option in question.options}
                    unknown = set(rule.expected_values) - known_option_ids
                    if unknown:
                        raise ValueError(
                            f"Branch rule '{rule.rule_id}' references unknown option ids "
                            f"for question '{question.question_id}': "
                            + ", ".join(sorted(unknown))
                        )
        _validate_no_duplicate_repeat_capacity(
            task_id=self.task_id,
            module_repeat_count=self.repeat_count,
            steps=self.steps,
        )
        return self


class TaskBinding(TaskBaseModel):
    """Condition attachment for one reusable task module."""

    task_id: str
    occurrence: TaskOccurrence = TaskOccurrence.EVERY_ENTRY
    replaces_condition_start_gate: bool = False

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, value: str) -> str:
        return validate_task_slug(value, field_name="task_id")


class TaskStepSpec(TaskStep):
    """Compiled step with deterministic option order recorded explicitly."""

    random_seed: int = Field(ge=0)
    realized_item_order: list[str] = Field(default_factory=list)
    realized_question_option_orders: dict[str, list[str]] = Field(default_factory=dict)


class TaskModuleSpec(TaskBaseModel):
    """Compiled module attached to one concrete session entry."""

    task_id: str
    name: str
    phase: TaskPhase
    occurrence: TaskOccurrence
    random_seed: int = Field(ge=0)
    repeat_count: int = Field(default=1, ge=1)
    steps: list[TaskStepSpec]

    @model_validator(mode="after")
    def validate_repeat_capacity(self) -> TaskModuleSpec:
        validate_task_module_repeat_capacity(self)
        return self


def validate_task_module_repeat_capacity(module: TaskModule | TaskModuleSpec) -> None:
    """Validate no-duplicate capacity for normal and defensively copied modules."""

    _validate_no_duplicate_repeat_capacity(
        task_id=module.task_id,
        module_repeat_count=module.repeat_count,
        steps=module.steps,
    )


class TaskStepResult(TaskBaseModel):
    """Neutral input result returned by an engine for one rendered step."""

    aborted: bool = False
    timed_out: bool = False
    response_kind: TaskResponseKind = TaskResponseKind.NONE
    key: str | None = None
    selected_option_ids: list[str] = Field(default_factory=list)
    text_value: str | None = Field(default=None, max_length=MAX_TASK_RESPONSE_TEXT_CHARS)
    numeric_value: float | None = None
    mouse_x: float | None = None
    mouse_y: float | None = None
    mouse_button: int | None = Field(default=None, ge=0)
    reaction_time_s: float | None = Field(default=None, ge=0)
    key_reaction_time_s: float | None = Field(default=None, ge=0)
    key_duration_s: float | None = Field(default=None, ge=0)
    realized_option_order: list[str] = Field(default_factory=list)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_response_key_name(value)

    @field_validator(
        "numeric_value",
        "mouse_x",
        "mouse_y",
        "reaction_time_s",
        "key_reaction_time_s",
        "key_duration_s",
    )
    @classmethod
    def validate_numbers(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(float(value)):
            raise ValueError("Task result numeric values must be finite.")
        return value

    @model_validator(mode="after")
    def validate_abort_result(self) -> TaskStepResult:
        if self.aborted and self.timed_out:
            raise ValueError("A task step result cannot be both aborted and timed out.")
        return self


class TaskResponseRecord(TaskBaseModel):
    """Runtime-owned research record for one task step response."""

    response_index: int = Field(ge=0)
    task_id: str
    step_id: str
    phase: TaskPhase
    condition_id: str
    run_id: str
    block_index: int = Field(ge=0)
    global_order_index: int = Field(ge=0)
    repetition_index: int = Field(ge=0)
    step_repetition_index: int = Field(default=0, ge=0)
    attempt_index: int = Field(default=0, ge=0)
    question_id: str | None = None
    response_kind: TaskResponseKind = TaskResponseKind.NONE
    key: str | None = None
    selected_option_ids: list[str] = Field(default_factory=list)
    text_value: str | None = Field(default=None, max_length=MAX_TASK_RESPONSE_TEXT_CHARS)
    numeric_value: float | None = None
    mouse_x: float | None = None
    mouse_y: float | None = None
    mouse_button: int | None = Field(default=None, ge=0)
    reaction_time_s: float | None = Field(default=None, ge=0)
    key_reaction_time_s: float | None = Field(default=None, ge=0)
    key_duration_s: float | None = Field(default=None, ge=0)
    realized_option_order: list[str] = Field(default_factory=list)
    valid: bool = True
    correct: bool | None = None
    score: float | None = None
    timed_out: bool = False
    aborted: bool = False

    @field_validator("task_id", "step_id", "condition_id")
    @classmethod
    def validate_ids(cls, value: str, info: object) -> str:
        return validate_task_slug(value, field_name=getattr(info, "field_name", "task id"))

    @field_validator("question_id")
    @classmethod
    def validate_question_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_task_slug(value, field_name="question_id")

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_response_key_name(value)

    @field_validator(
        "numeric_value",
        "mouse_x",
        "mouse_y",
        "reaction_time_s",
        "key_reaction_time_s",
        "key_duration_s",
        "score",
    )
    @classmethod
    def validate_numbers(cls, value: float | None) -> float | None:
        if value is not None and not isfinite(float(value)):
            raise ValueError("Task response numeric values must be finite.")
        return value


TaskMeasureValue = str | float | list[str] | None
TaskCompletionState = Literal["completed", "timed_out", "aborted", "skipped"]
