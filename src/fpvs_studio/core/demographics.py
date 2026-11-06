"""Authored demographics questions and the answers captured at launch."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)

DEMOGRAPHICS_PROMPT_LIMIT = 240
DEMOGRAPHICS_OPTION_LIMIT = 120
DEMOGRAPHICS_TEXT_LIMIT = 2000

DemographicsQuestionKind = Literal["text", "age", "choice", "yes_no"]
DemographicsValue = str | int | bool
_QuestionId = Annotated[str, Field(max_length=64, pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")]
_INVALID_CHARACTERS = re.compile(r"[\x00-\x1f\x7f\ud800-\udfff\ufffe\uffff]")

STUDIO_SEX_OPTIONS = ("Female", "Male")
STUDIO_HANDEDNESS_OPTIONS = ("Right handed", "Left handed", "Ambidextrous")


def _single_line(value: str) -> str:
    if _INVALID_CHARACTERS.search(value):
        raise ValueError("Use a single line without control characters.")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Enter a value.")
    return cleaned


_Prompt = Annotated[str, AfterValidator(_single_line), Field(max_length=DEMOGRAPHICS_PROMPT_LIMIT)]
_Option = Annotated[str, AfterValidator(_single_line), Field(max_length=DEMOGRAPHICS_OPTION_LIMIT)]
_TextAnswer = Annotated[
    str, AfterValidator(_single_line), Field(max_length=DEMOGRAPHICS_TEXT_LIMIT)
]


class DemographicsResponseError(ValueError):
    """A response needs correction before the visit can be launched."""

    def __init__(self, question_id: str, message: str) -> None:
        super().__init__(message)
        self.question_id = question_id


class DemographicsQuestion(BaseModel):
    """One required question in a project's ordered launch questionnaire."""

    model_config = ConfigDict(extra="forbid")

    id: _QuestionId
    prompt: _Prompt
    kind: DemographicsQuestionKind = "text"
    options: list[_Option] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_options(self) -> DemographicsQuestion:
        if self.kind == "choice":
            if not 2 <= len(self.options) <= 20:
                raise ValueError("Enter 2 to 20 answer choices.")
            if len({option.casefold() for option in self.options}) != len(self.options):
                raise ValueError("Each answer choice must be different.")
        elif self.options:
            raise ValueError("Only multiple-choice questions can define answer choices.")
        return self

    def validate_answer(self, value: DemographicsValue | None) -> DemographicsValue:
        if value is None or (isinstance(value, str) and not value.strip()):
            raise DemographicsResponseError(self.id, f"Answer ‘{self.prompt}’ to continue.")
        if self.kind == "age":
            if isinstance(value, str) and value.strip().isdecimal():
                try:
                    value = int(value)
                except ValueError:
                    pass
            if type(value) is int and 1 <= value <= 120:
                return value
            raise DemographicsResponseError(self.id, "Enter a whole age from 1 to 120.")
        if self.kind == "yes_no":
            if isinstance(value, bool):
                return value
            raise DemographicsResponseError(self.id, "Select Yes or No.")
        if self.kind == "choice":
            if isinstance(value, str) and value in self.options:
                return value
            raise DemographicsResponseError(self.id, "Select an answer from the list.")
        if isinstance(value, str):
            try:
                cleaned = _single_line(value)
            except ValueError as error:
                raise DemographicsResponseError(self.id, str(error)) from error
            if len(cleaned) <= DEMOGRAPHICS_TEXT_LIMIT:
                return cleaned
        raise DemographicsResponseError(
            self.id, f"Enter a text answer of up to {DEMOGRAPHICS_TEXT_LIMIT:,} characters."
        )


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
    answer: _TextAnswer | StrictInt | StrictBool
