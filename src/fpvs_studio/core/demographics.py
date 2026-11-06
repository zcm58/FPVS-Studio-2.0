"""Authored demographics questions and the answers captured at launch."""

from __future__ import annotations

import re
from datetime import date, time
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StrictBool,
    StrictInt,
    field_validator,
    model_serializer,
    model_validator,
)

DEMOGRAPHICS_PROMPT_LIMIT = 240
DEMOGRAPHICS_OPTION_LIMIT = 120
DEMOGRAPHICS_TEXT_LIMIT = 2000
DEMOGRAPHICS_SCALE_LABEL_LIMIT = 80
DEMOGRAPHICS_OPTION_COUNT_LIMIT = 20

DemographicsQuestionKind = Literal[
    "text", "paragraph", "choice", "checkboxes", "dropdown", "scale", "rating", "date", "time",
    "age", "yes_no",
]
DemographicsValue = str | int | bool | list[str]
DEMOGRAPHICS_OPTION_KINDS = frozenset({"choice", "checkboxes", "dropdown"})
DEMOGRAPHICS_OTHER_KINDS = frozenset({"choice", "checkboxes"})
_QuestionId = Annotated[str, Field(max_length=64, pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")]
_INVALID_CHARACTERS = re.compile(r"[\x00-\x1f\x7f\x85\u2028\u2029\ud800-\udfff\ufffe\uffff]")
_INVALID_PARAGRAPH_CHARACTERS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff\ufffe\uffff]"
)
_OPTIONAL_QUESTION_FIELDS = (
    "required", "allow_other", "scale_min", "scale_max", "scale_min_label", "scale_max_label",
)

STUDIO_SEX_OPTIONS = ("Female", "Male")
STUDIO_HANDEDNESS_OPTIONS = ("Right handed", "Left handed", "Ambidextrous")


def _single_line(value: str) -> str:
    if _INVALID_CHARACTERS.search(value):
        raise ValueError("Use a single line without control characters.")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Enter a value.")
    return cleaned


def _paragraph(value: str) -> str:
    if _INVALID_PARAGRAPH_CHARACTERS.search(value):
        raise ValueError("Remove control characters from the answer.")
    cleaned = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not cleaned:
        raise ValueError("Enter a value.")
    return cleaned


def _text_answer(value: str, *, multiline: bool = False) -> str:
    cleaned = _paragraph(value) if multiline else _single_line(value)
    if len(cleaned) > DEMOGRAPHICS_TEXT_LIMIT:
        raise ValueError(f"Enter a text answer of up to {DEMOGRAPHICS_TEXT_LIMIT:,} characters.")
    return cleaned


_Prompt = Annotated[str, AfterValidator(_single_line), Field(max_length=DEMOGRAPHICS_PROMPT_LIMIT)]
_Option = Annotated[str, AfterValidator(_single_line), Field(max_length=DEMOGRAPHICS_OPTION_LIMIT)]
_TextAnswer = Annotated[
    str, AfterValidator(_paragraph), Field(max_length=DEMOGRAPHICS_TEXT_LIMIT)
]
_SelectedAnswer = Annotated[
    str, AfterValidator(_single_line), Field(max_length=DEMOGRAPHICS_TEXT_LIMIT)
]
_SelectedAnswers = Annotated[
    list[_SelectedAnswer], Field(min_length=1, max_length=DEMOGRAPHICS_OPTION_COUNT_LIMIT + 1)
]


class DemographicsResponseError(ValueError):
    """A response needs correction before the visit can be launched."""

    def __init__(self, question_id: str, message: str) -> None:
        super().__init__(message)
        self.question_id = question_id


class DemographicsQuestion(BaseModel):
    """One question in a project's ordered launch questionnaire."""

    model_config = ConfigDict(extra="forbid")

    id: _QuestionId
    prompt: _Prompt
    kind: DemographicsQuestionKind = "text"
    options: list[_Option] = Field(default_factory=list)
    required: StrictBool = True
    allow_other: StrictBool = False
    scale_min: StrictInt = Field(default=1, ge=0, le=1)
    scale_max: StrictInt = Field(default=5, ge=2, le=10)
    scale_min_label: str = Field(default="", max_length=DEMOGRAPHICS_SCALE_LABEL_LIMIT)
    scale_max_label: str = Field(default="", max_length=DEMOGRAPHICS_SCALE_LABEL_LIMIT)

    @field_validator("scale_min_label", "scale_max_label")
    @classmethod
    def validate_scale_label(cls, value: str) -> str:
        return _single_line(value) if value.strip() else ""

    @model_serializer(mode="wrap")
    def serialize_question(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        for name in _OPTIONAL_QUESTION_FIELDS:
            if data.get(name) == type(self).model_fields[name].default:
                data.pop(name, None)
        return data

    @model_validator(mode="after")
    def validate_question_type(self) -> DemographicsQuestion:
        if self.kind in DEMOGRAPHICS_OPTION_KINDS:
            if not 2 <= len(self.options) <= DEMOGRAPHICS_OPTION_COUNT_LIMIT:
                raise ValueError("Enter 2 to 20 answer choices.")
            if len({option.casefold() for option in self.options}) != len(self.options):
                raise ValueError("Each answer choice must be different.")
        elif self.options:
            raise ValueError("Only multiple choice, checkboxes, and dropdowns use answer choices.")
        if self.allow_other and self.kind not in DEMOGRAPHICS_OTHER_KINDS:
            raise ValueError("Other is available for multiple choice and checkboxes.")
        if self.kind != "scale" and (self.scale_min != 1 or self.scale_min_label
                                     or self.scale_max_label):
            raise ValueError("Only linear scales can set the start value and endpoint labels.")
        if self.kind == "rating" and self.scale_max < 3:
            raise ValueError("Choose a rating maximum from 3 to 10.")
        if self.kind not in {"scale", "rating"} and self.scale_max != 5:
            raise ValueError("Only linear scales and ratings can set the maximum value.")
        return self

    def validate_answer(self, value: DemographicsValue | None) -> DemographicsValue | None:
        if value is None or (isinstance(value, str) and not value.strip()) or value == []:
            if self.required:
                raise DemographicsResponseError(self.id, f"Answer ‘{self.prompt}’ to continue.")
            return None
        try:
            return self._validate_nonblank_answer(value)
        except ValueError as error:
            raise DemographicsResponseError(self.id, str(error)) from error

    def _validate_nonblank_answer(self, value: DemographicsValue) -> DemographicsValue:
        if self.kind == "age":
            if isinstance(value, str) and value.strip().isdecimal():
                try:
                    value = int(value)
                except ValueError:
                    pass
            if type(value) is int and 1 <= value <= 120:
                return value
            raise ValueError("Enter a whole age from 1 to 120.")
        if self.kind == "yes_no":
            if isinstance(value, bool):
                return value
            raise ValueError("Select Yes or No.")
        if self.kind in {"choice", "dropdown"}:
            if isinstance(value, str):
                if value in self.options:
                    return value
                if self.allow_other:
                    return _text_answer(value)
            raise ValueError("Select an answer from the list.")
        if self.kind == "checkboxes":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError("Select one or more choices.")
            selected = [_text_answer(item) for item in value]
            other_count = sum(item not in self.options for item in selected)
            if len(set(selected)) != len(selected) or other_count > int(self.allow_other):
                raise ValueError("Select distinct choices and enter at most one Other answer.")
            return selected
        if self.kind in {"scale", "rating"}:
            if type(value) is int and self.scale_min <= value <= self.scale_max:
                return value
            raise ValueError(f"Select a value from {self.scale_min} to {self.scale_max}.")
        if self.kind in {"date", "time"}:
            date_answer = self.kind == "date"
            try:
                if isinstance(value, str) and len(value) == (10 if date_answer else 5):
                    formatted = (date.fromisoformat(value).isoformat() if date_answer else
                                 time.fromisoformat(value).isoformat(timespec="minutes"))
                    if value == formatted:
                        return value
            except ValueError:
                pass
            raise ValueError("Enter a valid date." if date_answer else "Enter a valid time.")
        if isinstance(value, str):
            return _text_answer(value, multiline=self.kind == "paragraph")
        raise ValueError("Enter a text answer.")


def _unique_questions(questions: list[DemographicsQuestion]) -> list[DemographicsQuestion]:
    if len({question.id for question in questions}) != len(questions):
        raise ValueError("Demographics question IDs must be unique.")
    return questions


DemographicsQuestions = Annotated[list[DemographicsQuestion], AfterValidator(_unique_questions)]


def default_demographics_questions() -> list[DemographicsQuestion]:
    """Return an independent copy of the original Studio questionnaire in order."""
    return [
        DemographicsQuestion(id="age", prompt="Age", kind="age"),
        DemographicsQuestion(
            id="sex", prompt="Sex", kind="choice", options=list(STUDIO_SEX_OPTIONS),
        ),
        DemographicsQuestion(
            id="handedness", prompt="Handedness", kind="choice",
            options=list(STUDIO_HANDEDNESS_OPTIONS),
        ),
        DemographicsQuestion(id="colorblind", prompt="Are you colorblind?", kind="yes_no"),
    ]


class DemographicsAnswer(BaseModel):
    """Original wording and typed answer in the order collected for a visit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question_id: _QuestionId
    prompt: _Prompt
    answer: _TextAnswer | StrictInt | StrictBool | _SelectedAnswers | None = None

    @field_validator("answer")
    @classmethod
    def validate_selection_snapshot(
        cls, value: DemographicsValue | None,
    ) -> DemographicsValue | None:
        if isinstance(value, list):
            if len(set(value)) != len(value):
                raise ValueError("Checkbox answers must be distinct.")
            if sum(len(label) > DEMOGRAPHICS_OPTION_LIMIT for label in value) > 1:
                raise ValueError("Only one checkbox answer can exceed the option length limit.")
        return value
