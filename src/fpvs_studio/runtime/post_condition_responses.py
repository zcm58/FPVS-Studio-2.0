"""Readable post-question responses derived from original task journals and context."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from fpvs_studio.core.paths import resolve_project_relative_path
from fpvs_studio.core.serialization import read_json_file, write_json_file
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.core.task_models import (
    PostQuestionDefinition,
    PostQuestionnaireContext,
    TaskQuestionKind,
    TaskResponseRecord,
)
from fpvs_studio.runtime.reporting_lock import project_reporting_lock
from fpvs_studio.runtime.session_export import _task_csv_value, _write_csv

POST_CONDITION_RESPONSES_FILENAME = "post_condition_responses.csv"
_CONTEXT_DIRECTORY = "logs/post-condition-responses"
_STREAM_COMPLETED_COLUMN = "FPVS stream completed"
_METADATA = [
    "Participant", "Session / visit", "Condition", "Presentation", "Presentations planned",
    "Presentation status", "Session status", "Project ID", "Execution ID", "Session ID",
    "Run ID", "Condition ID", "Global order",
]
_TerminalState = Literal["completed", "aborted", "error"]


class _EntryContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    global_order_index: int
    journal_path: str
    questionnaires: list[PostQuestionnaireContext]
    state: Literal["pending", "running", "completed", "aborted", "error"] = "pending"
    started_tasks: list[str] = Field(default_factory=list)
    playback_completed: StrictBool | None = None


class _ExecutionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    project_id: str
    execution_id: str
    session_id: str
    participant_number: str
    participant_session_number: int | None = None
    created_at_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    state: Literal["prepared", "completed", "aborted", "error"] = "prepared"
    entries: list[_EntryContext]


def post_condition_responses_path(project_root: Path) -> Path:
    """Resolve the response view against the active project, rejecting redirection."""

    path = resolve_project_relative_path(project_root, POST_CONDITION_RESPONSES_FILENAME)
    if (project_root / POST_CONDITION_RESPONSES_FILENAME).is_symlink():
        raise ValueError("The response CSV path is redirected; use a regular project-local file.")
    return path


class PostConditionResponseRecorder:
    """Persist original question context and safe stage boundaries, never answers."""

    def __init__(
        self, project_root: Path, session_plan: SessionPlan, *, participant_number: str,
        participant_session_number: int | None, execution_id: str,
        journal_paths: dict[str, Path],
    ) -> None:
        self._root = project_root.resolve()
        self._context: _ExecutionContext | None = None
        entries = []
        root = project_root.resolve()
        for entry in session_plan.ordered_entries():
            questionnaires = [
                task.post_question_context for task in entry.post_tasks
                if task.post_question_context is not None
            ]
            if not questionnaires:
                continue
            relative_journal = journal_paths[entry.run_id].resolve().relative_to(root).as_posix()
            resolve_project_relative_path(project_root, relative_journal)
            entries.append(_EntryContext(
                run_id=entry.run_id, global_order_index=entry.global_order_index,
                journal_path=relative_journal, questionnaires=questionnaires,
            ))
        self._path: Path | None = None
        if entries:
            self._path = resolve_project_relative_path(
                project_root, f"{_CONTEXT_DIRECTORY}/{UUID(execution_id).hex}.json",
            )
            if self._path.exists():
                raise FileExistsError(
                    "Question execution context already exists; use a new execution ID.",
                )
            self._context = _ExecutionContext(
                project_id=session_plan.project_id, execution_id=execution_id,
                session_id=session_plan.session_id, participant_number=participant_number,
                participant_session_number=participant_session_number, entries=entries,
            )
            self._write()

    @property
    def enabled(self) -> bool:
        return self._context is not None

    def _write(self) -> None:
        if self._context is not None and self._path is not None:
            write_json_file(self._path, self._context)

    def _entry(self, run_id: str) -> _EntryContext | None:
        if self._context is None:
            return None
        return next((entry for entry in self._context.entries if entry.run_id == run_id), None)

    def start_entry(self, run_id: str) -> None:
        entry = self._entry(run_id)
        if entry is not None:
            entry.state = "running"
            self._write()

    def start_module(self, run_id: str, task_id: str) -> None:
        entry = self._entry(run_id)
        if entry is not None and task_id not in entry.started_tasks:
            if task_id not in {task.task_id for task in entry.questionnaires}:
                raise ValueError("Question task does not match the original execution context.")
            entry.started_tasks.append(task_id)
            self._write()

    def playback_finished(self, run_id: str, *, completed: bool) -> None:
        """Record observed playback completion outside the FPVS frame loop."""
        entry = self._entry(run_id)
        if entry is not None:
            entry.playback_completed = completed
            self._write()

    def finish_entry(self, run_id: str, *, state: _TerminalState) -> None:
        entry = self._entry(run_id)
        if entry is not None:
            entry.state = state
            self._write()

    def finish_session(self, *, state: _TerminalState) -> None:
        if self._context is not None:
            self._context.state = state
            for entry in self._context.entries:
                if entry.state == "running":
                    entry.state = "error" if state == "error" else "aborted"
            self._write()

    def write_csv(self) -> Path | None:
        return rebuild_post_condition_responses(self._root) if self.enabled else None


def _question_columns(task_id: str, question: PostQuestionDefinition) -> tuple[str, str, str]:
    # The suffix prevents equal prompts, private copies and edited definitions merging.
    identity = f"{task_id}/{question.question_id}@{question.definition_version[:12]}"
    answer = str(_task_csv_value(f"{question.prompt} [{identity}]"))
    return answer, f"RT (s): {answer}", f"Status: {answer}"


def _answer(
    question: PostQuestionDefinition, records: list[TaskResponseRecord], *, fallback: str,
) -> tuple[object, object, str]:
    if len(records) > 1 or any(
        record.repetition_index or record.step_repetition_index or record.attempt_index
        for record in records
    ):
        raise ValueError("Repeated question attempts cannot be flattened into this response view.")
    accepted = [record for record in records if record.valid and not record.aborted
                and not record.timed_out]
    record = accepted[-1] if accepted else records[-1] if records else None
    if record is None:
        return "", "", fallback
    if record.aborted:
        return "", record.reaction_time_s, "aborted"
    if record.timed_out:
        return "", record.reaction_time_s, "timed_out"
    if not record.valid:
        return "", record.reaction_time_s, "invalid"
    if question.kind == TaskQuestionKind.RATING and record.numeric_value is not None:
        value: object = record.numeric_value
    elif record.selected_option_ids:
        options = {option.option_id: option.label for option in question.options}
        if any(option_id not in options for option_id in record.selected_option_ids):
            raise ValueError("Recorded option is absent from the original question definition.")
        value = "; ".join(options[option_id] for option_id in record.selected_option_ids)
    elif record.numeric_value is not None:
        value = record.numeric_value
    elif record.text_value is not None:
        value = record.text_value
        if not record.text_value.strip():
            return _task_csv_value(value), record.reaction_time_s, "unanswered"
    else:
        return "", record.reaction_time_s, "unanswered"
    return _task_csv_value(value), record.reaction_time_s, "answered"


def _project_execution(
    root: Path, context: _ExecutionContext, question_columns: dict[tuple[str, str, str],
                                                               tuple[str, str, str]],
) -> list[dict[str, object]]:
    # Imported here so the existing task runner remains the sole journal parser.
    from fpvs_studio.runtime.task_runner import read_task_response_journal

    rows: list[dict[str, object]] = []
    journals: dict[str, list[TaskResponseRecord]] = {}
    for entry in context.entries:
        if entry.state == "pending":
            continue
        first = entry.questionnaires[0]
        row: dict[str, object] = dict(zip(_METADATA, [
            context.participant_number, context.participant_session_number, first.condition_name,
            first.condition_presentation_index, first.condition_presentation_count, entry.state,
            "not_finalized" if context.state == "prepared" else context.state, context.project_id,
            context.execution_id, context.session_id, entry.run_id, first.condition_id,
            entry.global_order_index + 1,
        ], strict=True))
        row = {key: _task_csv_value(value) for key, value in row.items()}
        row[_STREAM_COMPLETED_COLUMN] = (
            "Unknown" if entry.playback_completed is None else
            "Yes" if entry.playback_completed else "No"
        )
        for columns in question_columns.values():
            row[columns[2]] = "not_assigned"
        if entry.journal_path not in journals:
            journals[entry.journal_path] = read_task_response_journal(
                resolve_project_relative_path(root, entry.journal_path),
            )
        records = journals[entry.journal_path]
        for task in entry.questionnaires:
            stopped = False
            fallback = (
                "not_presented" if entry.state != "running"
                and task.task_id not in entry.started_tasks
                else "interrupted" if entry.state in {"running", "error"}
                else "unanswered" if entry.state == "completed" else "aborted"
            )
            for question in task.questions:
                selected = [
                    record for record in records if record.run_id == entry.run_id
                    and record.task_id == task.task_id and record.step_id == question.step_id
                    and record.question_id == question.question_id
                ]
                if stopped and selected:
                    raise ValueError(
                        "Question journal contains answers after a terminal response; "
                        "the response view was not changed."
                    )
                if (not selected and not stopped and entry.state == "completed"
                        and task.task_id in entry.started_tasks):
                    raise ValueError(
                        "Submitted question records are missing from a completed presentation. "
                        "Restore the original task journal before rebuilding responses; "
                        "the response view was not changed."
                    )
                columns = question_columns[(task.task_id, question.question_id,
                                            question.definition_version)]
                values = _answer(
                    question, selected, fallback="not_presented" if stopped else fallback,
                )
                row.update(zip(columns, values, strict=True))
                if selected and (
                    selected[-1].aborted or (question.required and not selected[-1].valid)
                ):
                    stopped = True
        rows.append(row)
    return rows


def rebuild_post_condition_responses(project_root: Path) -> Path | None:
    """Atomically rebuild the wide CSV from retained context and original journals.

    An Excel lock raises without replacing the prior view. Raw records and context
    remain untouched, so the same operation is safe to retry after closing Excel.
    """

    with project_reporting_lock(project_root):
        project_root = project_root.resolve()
        directory = resolve_project_relative_path(project_root, _CONTEXT_DIRECTORY)
        contexts = [
            read_json_file(
                resolve_project_relative_path(project_root, f"{_CONTEXT_DIRECTORY}/{path.name}"),
                _ExecutionContext,
            ) for path in directory.glob("*.json")
        ] if directory.is_dir() else []
        contexts.sort(key=lambda item: (item.created_at_utc, item.execution_id))
        columns: dict[tuple[str, str, str], tuple[str, str, str]] = {}
        definitions: dict[tuple[str, str, str], PostQuestionDefinition] = {}
        used_headers: set[str] = {*_METADATA, _STREAM_COMPLETED_COLUMN}
        for context in contexts:
            for entry in context.entries:
                for task in entry.questionnaires:
                    for question in task.questions:
                        key = task.task_id, question.question_id, question.definition_version
                        if key in definitions:
                            if (definitions[key].model_dump(exclude={"step_id"})
                                    != question.model_dump(exclude={"step_id"})):
                                raise ValueError(
                                    "Conflicting original question definitions; view not changed.",
                                )
                            continue
                        headers = _question_columns(task.task_id, question)
                        if used_headers.intersection(headers):
                            raise ValueError(
                                "Question column identity collision; view not changed.",
                            )
                        used_headers.update(headers)
                        columns[key], definitions[key] = headers, question
        rows = [row for context in contexts
                for row in _project_execution(project_root, context, columns)]
        if not rows:
            return None
        path = post_condition_responses_path(project_root)
        header = [*_METADATA, _STREAM_COMPLETED_COLUMN]
        for index in range(3):  # All answers first, then time and status columns.
            header.extend(values[index] for values in columns.values())
        if path.is_file() and path.stat().st_size:
            with path.open(encoding="utf-8", newline="") as handle:
                existing = next(csv.reader(handle), [])
            if (existing[:len(_METADATA)] != _METADATA
                    or len(set(existing)) != len(existing) or set(existing) - set(header)):
                raise ValueError(
                    "The response CSV header was changed; preserve it before rebuilding.",
                )
            header = existing + [column for column in header if column not in existing]
        _write_csv(path, header, ([row.get(column, "") for column in header] for row in rows))
        return path
