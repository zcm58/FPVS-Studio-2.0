"""Shared support types for the GUI project document facade."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.models import (
    FixationTaskSettings,
    ProjectValidationReport,
    SessionSettings,
    StimulusSet,
    TriggerSettings,
)
from fpvs_studio.core.paths import project_json_path

_CONDITION_REPEAT_CYCLE_MISMATCH_PREFIX = (
    "Condition repeat/cycle settings must match across all conditions."
)
_CONDITION_LENGTH_ERROR_MESSAGE = (
    "Error: All of your conditions must be the same length. Please ensure each condition "
    "contains the same number of oddball cycles before continuing."
)


class DocumentError(ValueError):
    """Raised when a GUI-facing document action cannot complete."""


LaunchSummary = SessionExecutionSummary
ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass(frozen=True)
class ConditionStimulusRow:
    """One condition-role row shown on the assets page."""

    condition_id: str
    condition_name: str
    role: str
    stimulus_set: StimulusSet


def validated_copy(model: ModelT, **updates: object) -> ModelT:
    """Return a Pydantic-validated copy with updated fields."""

    data = model.model_dump(mode="python")
    data.update(updates)
    return type(model).model_validate(data)


def format_validation_report(report: ProjectValidationReport) -> str:
    """Format validation issues for GUI-facing errors."""

    error_issues = [issue for issue in report.issues if issue.severity.value == "error"]
    if not error_issues:
        return ""

    has_condition_repeat_cycle_mismatch = any(
        issue.message.startswith(_CONDITION_REPEAT_CYCLE_MISMATCH_PREFIX) for issue in error_issues
    )
    if not has_condition_repeat_cycle_mismatch:
        return "\n".join(
            f"[{issue.severity.value}] {issue.location}: {issue.message}" for issue in error_issues
        )

    issues = [_CONDITION_LENGTH_ERROR_MESSAGE]
    issues.extend(
        f"[{issue.severity.value}] {issue.location}: {issue.message}"
        for issue in error_issues
        if not issue.message.startswith(_CONDITION_REPEAT_CYCLE_MISMATCH_PREFIX)
    )
    if not issues:
        return ""
    return "\n".join(issues)


def resolve_project_location(project_location: Path) -> Path:
    """Resolve a directory or `project.json` path to the canonical JSON path."""

    candidate = Path(project_location)
    if candidate.is_dir():
        candidate = project_json_path(candidate)
    if candidate.name != "project.json":
        raise DocumentError("Select a project directory or a project.json file.")
    if not candidate.is_file():
        raise DocumentError(f"Project file was not found: {candidate}")
    return candidate


def default_session_settings() -> SessionSettings:
    """Return a fresh validated copy of session settings."""

    return SessionSettings()


def default_fixation_settings() -> FixationTaskSettings:
    """Return a fresh validated copy of fixation settings."""

    return FixationTaskSettings()


def default_trigger_settings() -> TriggerSettings:
    """Return a fresh validated copy of trigger settings."""

    return TriggerSettings()
