"""Participant research workbook projections and immutable original question labels.

These private records supplement the canonical response journals. They contain no
stimulus/frame arrays and never consult the current editable project for old labels.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from openpyxl.styles import Alignment, Font  # type: ignore[import-untyped]
from openpyxl.utils import get_column_letter  # type: ignore[import-untyped]

from fpvs_studio.core.demographics import DemographicsAnswer
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.paths import resolve_project_relative_path, to_project_relative_posix
from fpvs_studio.core.serialization import atomic_text_write
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.runtime.reporting_lock import project_reporting_lock
from fpvs_studio.runtime.workbook_layout import autofit_workbook

DEMOGRAPHIC_ANSWERS_SHEET_NAME = "Demographic Answers"

_DIRECTORY = "logs/.participant-results"
_POST_CONTEXT_DIRECTORY = "logs/post-condition-responses"
_UNAVAILABLE = "Unavailable (historical record)"
_TEST_IDS = {"0", "00"}
_RESPONSE_FIELDS = (
    "response_index", "task_id", "step_id", "phase", "condition_id", "run_id",
    "block_index", "global_order_index", "repetition_index", "step_repetition_index",
    "attempt_index", "question_id", "response_kind", "key", "selected_option_ids",
    "text_value", "numeric_value", "reaction_time_s", "valid", "correct", "score",
    "timed_out", "aborted", "realized_option_order",
)
_IDENTITY_HEADERS = [
    "PID", "Session Number", "Session ID", "Test Participant", "Test Mode", "Pilot Mode",
]
_DEMOGRAPHICS_HEADERS = [
    *_IDENTITY_HEADERS, "Age", "Sex", "Handedness", "Colorblind",
    "Manually Removed Electrodes", "Session Aborted", "Project ID", "Source",
]
_DEMOGRAPHIC_ANSWER_HEADERS = [
    *_IDENTITY_HEADERS, "Question", "Answer", "Question Position", "Question ID",
    "Session Aborted", "Project ID", "Source",
]
_FIXATION_HEADERS = [
    *_IDENTITY_HEADERS, "Condition", "Presentation", "Targets", "Hits", "Misses",
    "False Alarms", "Accuracy (%)", "Mean Reaction Time (ms)", "Run Aborted",
    "Session Aborted", "Include In Analysis", "RT Scoring Source", "Condition ID",
    "Run ID", "Project ID",
]
_ANSWER_HEADERS = [
    *_IDENTITY_HEADERS, "Condition", "Phase", "Record Type", "Task", "Question", "Answer",
    "Reaction Time (s)", "Status", "Correct", "Score", "Session Aborted",
    "Run Aborted", "Response Index", "Module Repetition", "Step Repetition", "Attempt",
    "Task ID", "Step ID", "Question ID", "Selected Option IDs", "Realized Option Order",
    "Condition ID", "Run ID", "Project ID", "Source",
]
_FIXATION_RESPONSE_HEADERS = [
    *_IDENTITY_HEADERS, "Condition", "Row Type", "Outcome", "Reaction Time (s)",
    "Reaction Time (frames)", "Key", "Target Index", "Response Index", "Response Frame",
    "RT Scoring Source", "Run Aborted", "Session Aborted", "Condition ID", "Run ID",
    "Project ID", "Source",
]


def _task_definitions(plan: SessionPlan) -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []
    for entry in plan.ordered_entries():
        tasks = []
        for module in [*entry.pre_tasks, *entry.post_tasks]:
            steps = []
            for step in module.steps:
                steps.append({
                    "step_id": step.step_id, "text": step.text, "heading": step.heading,
                    "questions": [question.model_dump(mode="json") for question in step.questions],
                    "items": [
                        {key: value for key, value in item.model_dump(mode="json").items()
                         if key in {"item_id", "text", "image_path"}}
                        for item in step.items
                    ],
                })
            tasks.append({"task_id": module.task_id, "name": module.name,
                          "phase": module.phase.value, "steps": steps})
        definitions.append({
            "run_id": entry.run_id, "condition_id": entry.condition_id,
            "condition_name": entry.condition_name, "tasks": tasks,
        })
    return definitions


def capture_participant_results(
    project_root: Path, plan: SessionPlan, summary: SessionExecutionSummary,
    *, finalized: bool = True, journal_paths: Mapping[str, Path] | None = None,
    execution_id: str | None = None,
) -> Path:
    """Atomically checkpoint original labels and accumulated answers for one visit.

    Numbered visits replace their own record on retries/checkpoints. Unnumbered
    direct callers get separate records because their execution identity is ambiguous.
    """

    if summary.project_id != plan.project_id or summary.session_id != plan.session_id:
        raise ValueError("Participant results do not match the compiled session.")
    identity = [summary.project_id, summary.participant_number,
                summary.participant_session_number, summary.session_id]
    key = (hashlib.sha256(json.dumps(identity).encode()).hexdigest()
           if summary.participant_session_number is not None else
           hashlib.sha256(execution_id.encode()).hexdigest() if execution_id else uuid4().hex)
    participant_metadata = summary.participant_metadata.model_dump(mode="json")
    payload = {
        "schema_version": 1, "project_id": summary.project_id, "execution_id": execution_id,
        "participant_number": summary.participant_number or "",
        "participant_session_number": summary.participant_session_number,
        "session_id": summary.session_id, "session_aborted": summary.aborted,
        "test_mode": summary.runtime_metadata.test_mode if summary.runtime_metadata else None,
        "pilot_mode": summary.runtime_metadata.pilot_mode if summary.runtime_metadata else None,
        "finalized": finalized,
        "journal_paths": {run_id: to_project_relative_posix(
            project_root, resolve_project_relative_path(
                project_root, to_project_relative_posix(project_root, path),
            ),
        ) for run_id, path in (journal_paths or {}).items()},
        "participant_metadata": participant_metadata,
        "definitions": _task_definitions(plan),
        "runs": [{
            "run_id": run.run_id, "condition_id": run.condition_id,
            "condition_name": run.condition_name, "aborted": run.aborted,
            "fixation_responses": [item.model_dump(mode="json") for item in run.fixation_responses],
            "response_log": [item.model_dump(mode="json") for item in run.response_log],
            "rt_scoring_source": (run.runtime_metadata.fixation_rt_scoring_source
                                  if run.runtime_metadata is not None else None),
            "responses": [{field: value for field, value in response.model_dump(mode="json").items()
                           if field in _RESPONSE_FIELDS} for response in run.task_responses],
        } for run in summary.run_results],
    }
    with project_reporting_lock(project_root):
        path = resolve_project_relative_path(project_root, f"{_DIRECTORY}/{key}.json")
        if path.is_file():
            previous = _json(path)
            if previous.get("definitions") != payload["definitions"]:
                raise ValueError("Original participant question definitions cannot be replaced.")
            previous_metadata = previous.get("participant_metadata") or {}
            before = previous_metadata.get("demographics_answers") or []
            after = participant_metadata.get("demographics_answers") or []
            if json.dumps(before, sort_keys=True) != json.dumps(after, sort_keys=True):
                raise ValueError("Original demographic answers cannot be replaced.")
        atomic_text_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object.")
    return payload


def _csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames and len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"{path.name} has duplicate column names.")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"{path.name} contains malformed rows.")
    return rows


def _number(value: object) -> int | float | None:
    if value is None or value == "":
        return None
    try:
        number = float(str(value))
    except ValueError as error:
        raise ValueError("Participant results contain an invalid numeric value.") from error
    if not math.isfinite(number):
        raise ValueError("Participant results contain a nonfinite numeric value.")
    return int(number) if number.is_integer() else number


def _boolean(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if str(value).strip().lower() in {"1", "true", "yes", "y"}:
        return True
    if str(value).strip().lower() in {"0", "false", "no", "n"}:
        return False
    return None


def _yes_no(value: object) -> str:
    parsed = _boolean(value)
    return "Yes" if parsed is True else "No" if parsed is False else "Unavailable"


def _identity(record: dict[str, Any]) -> list[object]:
    pid = str(record.get("participant_number") or "")
    return [pid, _number(record.get("participant_session_number")),
            str(record.get("session_id") or ""), "Yes" if pid in _TEST_IDS else "No",
            _yes_no(record.get("test_mode")), _yes_no(record.get("pilot_mode"))]


def _visit_key(record: dict[str, Any], source: str) -> tuple[object, ...]:
    pid, number, session = _identity(record)[:3]
    project = record.get("project_id", "")
    if number is not None:
        return project, pid, number, session
    return "ambiguous", record.get("legacy_source") or source


def _legacy_definitions(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "run_id": entry.get("run_id"), "condition_id": entry.get("condition_id"),
        "condition_name": entry.get("condition_name"),
        "tasks": [*entry.get("pre_tasks", []), *entry.get("post_tasks", [])],
    } for block in plan.get("blocks", []) for entry in block.get("entries", [])]


def _legacy_full_records(
    root: Path, history_rows: list[dict[str, str]],
) -> list[tuple[dict[str, Any], str]]:
    records = []
    directories = dict.fromkeys(row.get("output_dir", "") for row in history_rows)
    for directory in directories:
        if not directory:
            continue
        summary_path = resolve_project_relative_path(root, f"{directory}/session_summary.json")
        plan_path = resolve_project_relative_path(root, f"{directory}/session_plan.json")
        if not summary_path.is_file():
            continue
        summary = _json(summary_path)
        metadata = summary.get("runtime_metadata") or {}
        definitions = _legacy_definitions(_json(plan_path)) if plan_path.is_file() else []
        responses_path = resolve_project_relative_path(root, f"{directory}/task_responses.csv")
        responses: list[dict[str, Any]] = [
            {**row, "_csv_escaped": True} for row in _csv(responses_path)
        ]
        runs = []
        for run in summary.get("run_results", []):
            run_id = str(run.get("run_id", ""))
            selected = [row for row in responses
                        if (row.get("session_run_id") or row.get("run_id")) == run_id]
            if not responses_path.is_file():
                journal = resolve_project_relative_path(
                    root, f"{directory}/{run_id}/task_responses.jsonl",
                )
                if journal.is_file():
                    from fpvs_studio.runtime.task_runner import read_task_response_journal

                    selected = [response.model_dump(mode="json")
                                for response in read_task_response_journal(journal)]
            runs.append({
                **{key: run.get(key) for key in (
                    "run_id", "condition_id", "condition_name", "aborted",
                    "fixation_responses", "response_log", "runtime_metadata",
                ) if key in run},
                "responses": selected,
            })
        records.append(({
            "project_id": summary.get("project_id", ""),
            "participant_number": summary.get("participant_number", ""),
            "participant_session_number": summary.get("participant_session_number"),
            "session_id": summary.get("session_id", ""),
            "test_mode": metadata.get("test_mode"), "pilot_mode": metadata.get("pilot_mode"),
            "participant_metadata": summary.get("participant_metadata", {}),
            "session_aborted": summary.get("aborted"), "definitions": definitions,
            "finalized": True,
            "runs": runs,
        }, directory))
    return records


def freeze_legacy_participant_results(project_root: Path) -> list[Path]:
    """Retain original full-mode research views before authorized CSV archival.

    This explicit maintenance operation never removes source files. Normal workbook
    loading remains read-only. The original output directory proves the identity of
    unnumbered exports so freezing them does not create duplicate observations.
    """

    with project_reporting_lock(project_root):
        return _freeze_legacy_participant_results_unlocked(project_root)


def _freeze_legacy_participant_results_unlocked(project_root: Path) -> list[Path]:
    """Freeze legacy research while the caller owns the project reporting lock."""

    history = _csv(resolve_project_relative_path(
        project_root, "logs/session_condition_history.csv",
    ))
    records = _records(project_root, history)
    _answer_rows(records)
    _demographic_answer_rows(records)
    _fixation_response_rows(records)
    written = []
    for record, source in _legacy_full_records(project_root, history):
        key = hashlib.sha256(source.encode("utf-8")).hexdigest()
        path = resolve_project_relative_path(project_root, f"{_DIRECTORY}/legacy-{key}.json")
        payload = {**record, "schema_version": 1, "legacy_source": source}
        if path.is_file():
            previous = _json(path)
            if (previous.get("definitions") != payload["definitions"]
                    or previous.get("participant_metadata") != payload["participant_metadata"]):
                raise ValueError("Retained legacy participant context cannot be replaced.")
        else:
            atomic_text_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
        written.append(path)
    return written


def _records(root: Path, history_rows: list[dict[str, str]]) -> list[tuple[dict[str, Any], str]]:
    records: list[tuple[dict[str, Any], str]] = []
    directory = resolve_project_relative_path(root, _DIRECTORY)
    if directory.is_dir():
        for candidate in sorted(directory.glob("*.json")):
            path = resolve_project_relative_path(root, f"{_DIRECTORY}/{candidate.name}")
            record = _json(path)
            if record.get("schema_version") != 1:
                raise ValueError("Unsupported participant results record version.")
            _merge_pending_journals(root, record)
            records.append((record, f"{_DIRECTORY}/{candidate.name}"))
    records.extend(_legacy_full_records(root, history_rows))
    records.extend(_legacy_post_context_records(root))
    compact_rows = _csv(resolve_project_relative_path(root, "logs/task_responses.csv"))
    for index, row in enumerate(compact_rows):
        records.append(({
            **row, "definitions": [], "finalized": True,
            "runs": [{"run_id": row.get("run_id", ""), "condition_id": row.get("condition_id"),
                      "responses": [{**row, "_csv_escaped": True}]}],
        }, f"logs/task_responses.csv:row {index + 2}"))
    return records


def _legacy_post_context_records(root: Path) -> list[tuple[dict[str, Any], str]]:
    """Recover historical post answers/labels from immutable context and journals."""

    from fpvs_studio.runtime.post_condition_responses import _ExecutionContext
    from fpvs_studio.runtime.task_runner import read_task_response_journal

    records: list[tuple[dict[str, Any], str]] = []
    directory = resolve_project_relative_path(root, _POST_CONTEXT_DIRECTORY)
    if not directory.is_dir():
        return records
    journals: dict[str, list[dict[str, Any]]] = {}
    for candidate in sorted(directory.glob("*.json")):
        source = f"{_POST_CONTEXT_DIRECTORY}/{candidate.name}"
        context_path = resolve_project_relative_path(root, source)
        context = _ExecutionContext.model_validate(_json(context_path))
        definitions = []
        runs = []
        for entry in context.entries:
            tasks = []
            assigned = set()
            for task in entry.questionnaires:
                steps: dict[str, list[dict[str, Any]]] = {}
                for question in task.questions:
                    steps.setdefault(question.step_id, []).append(question.model_dump(mode="json"))
                    assigned.add((task.task_id, question.step_id, question.question_id))
                tasks.append({
                    "task_id": task.task_id, "name": task.task_name, "phase": "post_condition",
                    "steps": [{"step_id": step_id, "questions": questions}
                              for step_id, questions in steps.items()],
                })
            first = entry.questionnaires[0]
            definitions.append({"run_id": entry.run_id, "condition_id": first.condition_id,
                                "condition_name": first.condition_name, "tasks": tasks})
            journal = resolve_project_relative_path(root, entry.journal_path)
            if entry.journal_path not in journals:
                journals[entry.journal_path] = [response.model_dump(mode="json") for response in
                    read_task_response_journal(journal)] if journal.is_file() else []
            responses = [response for response in journals[entry.journal_path]
                         if response["run_id"] == entry.run_id
                         and response["phase"] == "post_condition"
                         and (response["task_id"], response["step_id"], response.get("question_id"))
                         in assigned]
            runs.append({"run_id": entry.run_id, "condition_id": first.condition_id,
                         "condition_name": first.condition_name,
                         "aborted": False if entry.playback_completed is True else None,
                         "responses": responses})
        records.append(({
            "project_id": context.project_id, "participant_number": context.participant_number,
            "participant_session_number": context.participant_session_number,
            "session_id": context.session_id, "execution_id": context.execution_id,
            "session_aborted": context.state in {"aborted", "error"},
            "session_state": context.state, "finalized": context.state != "prepared",
            "definitions": definitions, "runs": runs,
        }, source))
    return records


def _merge_pending_journals(root: Path, record: dict[str, Any]) -> None:
    if record.get("finalized", True):
        return
    from fpvs_studio.runtime.task_runner import read_task_response_journal

    runs = {run["run_id"]: run for run in record.get("runs", [])}
    definitions = {entry["run_id"]: entry for entry in record.get("definitions", [])}
    journals: dict[str, list[dict[str, Any]]] = {}
    for run_id, relative in record.get("journal_paths", {}).items():
        path = resolve_project_relative_path(root, relative)
        if not path.is_file():
            continue
        if relative not in journals:
            journals[relative] = [response.model_dump(mode="json")
                                  for response in read_task_response_journal(path)]
        if run_id not in definitions:
            raise ValueError("Task journal refers to an unknown captured run.")
        run = runs.setdefault(run_id, {
            "run_id": run_id, "condition_id": definitions[run_id]["condition_id"],
            "condition_name": definitions[run_id]["condition_name"], "responses": [],
        })
        responses = {item["response_index"]: item for item in run["responses"]}
        for response in journals[relative]:
            if response["run_id"] != run_id:
                continue
            index = response["response_index"]
            if index in responses:
                captured = {key: value for key, value in responses[index].items()
                            if key in _RESPONSE_FIELDS}
                journal = {key: value for key, value in response.items() if key in _RESPONSE_FIELDS}
                if captured != journal:
                    raise ValueError("Captured task answer conflicts with its original journal.")
            responses[index] = response
        run["responses"] = list(responses.values())
    record["runs"] = list(runs.values())


def has_captured_participant_results(project_root: Path) -> bool:
    """Whether private participant research snapshots exist, including partial visits."""

    for name in (_DIRECTORY, _POST_CONTEXT_DIRECTORY):
        directory = resolve_project_relative_path(project_root, name)
        if directory.is_dir() and next(directory.glob("*.json"), None) is not None:
            return True
    return False


def participant_results_source_paths(project_root: Path) -> list[Path]:
    """Return changing research sources used to decide workbook refresh staleness."""

    paths = []
    directory = resolve_project_relative_path(project_root, _DIRECTORY)
    if directory.is_dir():
        for candidate in sorted(directory.glob("*.json")):
            path = resolve_project_relative_path(project_root, f"{_DIRECTORY}/{candidate.name}")
            paths.append(path)
            record = _json(path)
            if not record.get("finalized", True):
                paths.extend(resolve_project_relative_path(project_root, relative)
                             for relative in record.get("journal_paths", {}).values())
    paths.append(resolve_project_relative_path(project_root, "logs/task_responses.csv"))
    context_directory = resolve_project_relative_path(project_root, _POST_CONTEXT_DIRECTORY)
    if context_directory.is_dir():
        for candidate in context_directory.glob("*.json"):
            path = resolve_project_relative_path(
                project_root, f"{_POST_CONTEXT_DIRECTORY}/{candidate.name}",
            )
            paths.append(path)
            context = _json(path)
            paths.extend(resolve_project_relative_path(project_root, entry["journal_path"])
                         for entry in context.get("entries", []))
    history = resolve_project_relative_path(project_root, "logs/session_condition_history.csv")
    for output in dict.fromkeys(row.get("output_dir", "") for row in _csv(history)):
        if not output:
            continue
        directory = resolve_project_relative_path(project_root, output)
        names = ("session_summary.json", "session_plan.json", "task_responses.csv")
        paths.extend(resolve_project_relative_path(project_root, f"{output}/{name}")
                     for name in names)
        if directory.is_dir():
            paths.extend(resolve_project_relative_path(
                project_root, f"{output}/{candidate.parent.name}/task_responses.jsonl",
            ) for candidate in directory.glob("*/task_responses.jsonl"))
    return [path for path in dict.fromkeys(paths) if path.is_file()]


def _definition(
    record: dict[str, Any], run_id: str, response: dict[str, Any],
) -> tuple[str, str, dict[str, str]]:
    for entry in record.get("definitions", []):
        if entry.get("run_id") != run_id:
            continue
        for task in entry.get("tasks", []):
            if task.get("task_id") != response.get("task_id"):
                continue
            for step in task.get("steps", []):
                if step.get("step_id") != response.get("step_id"):
                    continue
                for question in step.get("questions", []):
                    if question.get("question_id") == response.get("question_id"):
                        return str(task.get("name") or _UNAVAILABLE), str(question.get("prompt")
                            or _UNAVAILABLE), {str(option["option_id"]): str(option["label"])
                                                  for option in question.get("options", [])}
                return str(task.get("name") or _UNAVAILABLE), str(step.get("text")
                    or step.get("heading") or _UNAVAILABLE), {
                        str(item["item_id"]): str(item.get("text") or item.get("image_path")
                                                   or item["item_id"])
                        for item in step.get("items", [])
                    }
    return _UNAVAILABLE, _UNAVAILABLE, {}


def _ids(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return str(value).split(";") if value else []


def _answer(response: dict[str, Any], options: dict[str, str]) -> object:
    if (response.get("response_kind") == "rating" and response.get("numeric_value") is not None
            and response.get("numeric_value") != ""):
        return _number(response["numeric_value"])
    selected = _ids(response.get("selected_option_ids"))
    if selected:
        return "; ".join(options.get(item, f"{_UNAVAILABLE}: {item}") for item in selected)
    if response.get("numeric_value") is not None and response.get("numeric_value") != "":
        return _number(response["numeric_value"])
    text = response.get("text_value")
    if text:
        # CSV's apostrophe escape was added by Studio; typed XLSX text needs no escape.
        if (response.get("_csv_escaped") and isinstance(text, str) and text.startswith("'")
                and text[1:].lstrip().startswith(
            ("=", "+", "-", "@"),
        )):
            return text[1:]
        return text
    return response.get("key") or ""


def _status(response: dict[str, Any]) -> str:
    if _boolean(response.get("aborted")):
        return "Aborted"
    if _boolean(response.get("timed_out")):
        return "Timed out"
    if _boolean(response.get("valid")) is False:
        return "Invalid"
    if _response_type(response) == "Task activity":
        return "Completed"
    if _answer(response, {}) == "":
        return "Unanswered"
    return "Answered"


def _response_type(response: dict[str, Any]) -> str:
    if response.get("question_id"):
        return "Question answer"
    if (_ids(response.get("selected_option_ids")) or response.get("text_value") is not None
            and response.get("text_value") != ""
            or response.get("numeric_value") is not None and response.get("numeric_value") != ""
            or response.get("response_kind") in {"text", "numeric", "rating", "option_selection"}):
        return "Task response"
    return "Task activity"


def _answer_rows(records: list[tuple[dict[str, Any], str]]) -> list[list[object]]:
    rows = []
    seen: dict[tuple[object, ...], tuple[object, ...]] = {}
    original_labels = _original_question_labels(records)
    for record, source in records:
        for run in record.get("runs", []):
            run_id = str(run.get("run_id", ""))
            for response in run.get("responses", []):
                key = (*_visit_key(record, source), run_id,
                       _number(response.get("response_index")))
                # Numbered visits match canonical research-table identity. Ambiguous
                # unnumbered rows retain source identity and are never collapsed.
                signature = _response_signature(response)
                if key in seen:
                    if seen[key] != signature:
                        raise ValueError(
                            "Conflicting task answers share a participant response identity.",
                        )
                    continue
                seen[key] = signature
                task, question, options = _definition(record, run_id, response)
                label_key = (*_visit_key(record, source), run_id, response.get("task_id"),
                             response.get("phase"), response.get("step_id"),
                             response.get("question_id"))
                if label_key in original_labels:
                    task, question, options = original_labels[label_key]
                phase = response.get("phase", "")
                rows.append([
                    *_identity(record), run.get("condition_name") or _UNAVAILABLE,
                    {"pre_condition": "Before", "post_condition": "After"}.get(phase, phase),
                    _response_type(response), task, question, _answer(response, options),
                    _number(response.get("reaction_time_s")), _status(response),
                    _yes_no(response.get("correct")), _number(response.get("score")),
                    _session_status(record), _yes_no(run.get("aborted")),
                    _number(response.get("response_index")),
                    _number(response.get("repetition_index")),
                    _number(response.get("step_repetition_index")),
                    _number(response.get("attempt_index")), response.get("task_id", ""),
                    response.get("step_id", ""), response.get("question_id", ""),
                    ";".join(_ids(response.get("selected_option_ids"))),
                    ";".join(_ids(response.get("realized_option_order"))),
                    run.get("condition_id") or response.get("condition_id", ""),
                    run_id, record.get("project_id", ""), source,
                ])
    kind_column = _ANSWER_HEADERS.index("Record Type")
    return sorted(rows, key=lambda row: row[kind_column] == "Task activity")


def _original_question_labels(
    records: list[tuple[dict[str, Any], str]],
) -> dict[tuple[object, ...], tuple[str, str, dict[str, str]]]:
    labels: dict[tuple[object, ...], tuple[str, str, dict[str, str]]] = {}
    for record, source in records:
        for entry in record.get("definitions", []):
            for task in entry.get("tasks", []):
                for step in task.get("steps", []):
                    for question in step.get("questions", []):
                        key = (*_visit_key(record, source), entry.get("run_id"),
                               task.get("task_id"), task.get("phase"), step.get("step_id"),
                               question.get("question_id"))
                        value = (str(task.get("name") or _UNAVAILABLE),
                                 str(question.get("prompt") or _UNAVAILABLE),
                                 {str(option["option_id"]): str(option["label"])
                                  for option in question.get("options", [])})
                        if key in labels and labels[key] != value:
                            raise ValueError("Conflicting original participant question labels.")
                        labels[key] = value
    return labels


def _response_signature(response: dict[str, Any]) -> tuple[object, ...]:
    text_response = {**response, "selected_option_ids": [], "numeric_value": None, "key": None}
    return (
        *(response.get(key) or "" for key in ("task_id", "step_id", "question_id", "phase")),
        *(_number(response.get(key)) or 0 for key in (
            "repetition_index", "step_repetition_index", "attempt_index",
        )), tuple(_ids(response.get("selected_option_ids"))), _answer(text_response, {}),
        _number(response.get("numeric_value")), _number(response.get("reaction_time_s")),
        response.get("key") or "", _boolean(response.get("valid")),
        _boolean(response.get("correct")), _boolean(response.get("aborted")),
        _boolean(response.get("timed_out")), _number(response.get("score")),
    )


def _fixation_response_rows(records: list[tuple[dict[str, Any], str]]) -> list[list[object]]:
    rows = []
    seen: dict[tuple[object, ...], tuple[object, ...]] = {}
    for record, source in records:
        for run in record.get("runs", []):
            run_id = str(run.get("run_id", ""))
            metadata = run.get("runtime_metadata") or {}
            scoring = run.get("rt_scoring_source") or metadata.get("fixation_rt_scoring_source")
            targets = [("Target", item) for item in run.get("fixation_responses", [])]
            unmatched = [("Unmatched response", item) for item in run.get("response_log", [])
                         if item.get("matched_event_index") is None]
            for kind, item in [*targets, *unmatched]:
                index = item.get("event_index") if kind == "Target" else item.get("response_index")
                key = (*_visit_key(record, source), run_id, kind, index)
                signature = (
                    *(item.get(field) or "" for field in ("outcome", "first_response_key", "key")),
                    *(_number(item.get(field)) for field in (
                        "rt_s", "rt_frames", "response_frame", "frame_index", "time_s",
                        "response_time_s", "target_onset_time_s", "matched_event_index",
                    )), _boolean(item.get("responded")), _boolean(item.get("correct")),
                )
                if key in seen:
                    if seen[key] != signature:
                        raise ValueError(
                            "Conflicting fixation responses share a participant identity.",
                        )
                    continue
                seen[key] = signature
                rows.append([
                    *_identity(record), run.get("condition_name") or _UNAVAILABLE, kind,
                    item.get("outcome") or "Unavailable", _number(item.get("rt_s")),
                    _number(item.get("rt_frames")),
                    item.get("first_response_key") if kind == "Target" else item.get("key"),
                    item.get("event_index") if kind == "Target" else None,
                    item.get("response_index") if kind != "Target" else None,
                    item.get("response_frame") if kind == "Target" else item.get("frame_index"),
                    scoring or "Unavailable", _yes_no(run.get("aborted")),
                    _session_status(record), run.get("condition_id", ""), run_id,
                    record.get("project_id", ""), source,
                ])
    return rows


def _history_source(row: dict[str, str]) -> str:
    return row.get("output_dir") or "history:" + json.dumps([
        row.get("participant_number"), row.get("session_id"), row.get("session_started_at"),
    ])


def _session_status(record: dict[str, Any]) -> str:
    if record.get("session_state") == "error":
        return "Error"
    if not record.get("finalized", True):
        return "Not finalized"
    return _yes_no(record.get("session_aborted"))


def _demographic_rows(
    records: list[tuple[dict[str, Any], str]], history_rows: list[dict[str, str]],
) -> list[list[object]]:
    rows: dict[tuple[object, ...], list[object]] = {}
    for record, source in records:
        metadata = record.get("participant_metadata")
        if metadata is None:
            continue  # Compact answer tables contain no demographics.
        key = _visit_key(record, source)
        if key in rows:
            continue
        electrodes = metadata.get("manual_removed_electrodes")
        rows[key] = [
            *_identity(record), metadata.get("age"), metadata.get("sex") or "Unavailable",
            metadata.get("handedness") or "Unavailable", _yes_no(metadata.get("colorblind")),
            "; ".join(electrodes) if electrodes is not None else "Unavailable",
            _session_status(record), record.get("project_id", ""), source,
        ]
    for row in history_rows:
        key = _visit_key(row, _history_source(row))
        if key in rows:
            continue
        electrodes = row.get("manual_removed_electrodes", "")
        known = _boolean(row.get("manual_removed_electrodes_recorded")) or electrodes
        rows[key] = [
            *_identity(row), _number(row.get("participant_age")),
            row.get("participant_sex") or "Unavailable",
            row.get("participant_handedness") or "Unavailable",
            _yes_no(row.get("participant_colorblind")), electrodes if known else "Unavailable",
            _yes_no(row.get("session_aborted")), row.get("project_id", ""),
            "logs/session_condition_history.csv",
        ]
    return list(rows.values())


def _demographic_answer_rows(records: list[tuple[dict[str, Any], str]]) -> list[list[object]]:
    rows: list[list[object]] = []
    seen: dict[tuple[object, ...], str] = {}
    for record, source in records:
        metadata = record.get("participant_metadata") or {}
        snapshots = metadata.get("demographics_answers")
        if snapshots is None:
            continue
        if not isinstance(snapshots, list):
            raise ValueError("Demographic answers must be recorded in question order.")
        answers = [DemographicsAnswer.model_validate(snapshot) for snapshot in snapshots]
        key = _visit_key(record, source)
        snapshot_json = json.dumps([answer.model_dump(mode="json") for answer in answers])
        if key in seen:
            if seen[key] != snapshot_json:
                raise ValueError("Conflicting demographic answers share a participant visit.")
            continue
        seen[key] = snapshot_json
        rows.extend([
            *_identity(record), answer.prompt,
            "\n".join(answer.answer) if isinstance(answer.answer, list) else answer.answer,
            position, answer.question_id,
            _session_status(record), record.get("project_id", ""), source,
        ] for position, answer in enumerate(answers, 1))
    return rows


def _fixation_rows(
    history_rows: list[dict[str, str]], records: list[tuple[dict[str, Any], str]],
) -> list[list[object]]:
    modes: dict[tuple[object, ...], tuple[object, object]] = {}
    for record, source in records:
        if (_number(record.get("participant_session_number")) is not None
                and (record.get("test_mode") is not None or record.get("pilot_mode") is not None)):
            modes.setdefault(_visit_key(record, source),
                             (record.get("test_mode"), record.get("pilot_mode")))
    enriched: list[dict[str, Any]] = []
    for raw in history_rows:
        row: dict[str, Any] = dict(raw)
        mode = modes.get(_visit_key(row, _history_source(raw)))
        if mode is not None:
            row["test_mode"], row["pilot_mode"] = mode
        enriched.append(row)
    aborted = {
        _visit_key(row, _history_source(row)) for row in history_rows
        if _boolean(row.get("session_aborted")) or _boolean(row.get("run_aborted"))
    }
    return [[
        *_identity(row), row.get("condition_name", ""),
        _number(row.get("condition_presentation_index")),
        *(_number(row.get(field)) for field in (
            "total_targets", "hit_count", "miss_count", "false_alarm_count",
            "accuracy_percent", "mean_rt_ms",
        )), _yes_no(row.get("run_aborted")), _yes_no(row.get("session_aborted")),
        "No" if row.get("participant_number") in _TEST_IDS
        or _visit_key(row, _history_source(row)) in aborted else "Yes",
        row.get("fixation_rt_scoring_source") or "Unavailable",
        row.get("condition_id", ""), row.get("run_id", ""), row.get("project_id", ""),
    ] for row in enriched]


def _sheet(workbook: Any, name: str, headers: list[str], rows: list[list[object]]) -> None:
    primary = {
        "Demographics": ["PID", "Session Number", "Age", "Sex", "Handedness", "Colorblind",
                         "Session Aborted"],
        DEMOGRAPHIC_ANSWERS_SHEET_NAME: [
            "PID", "Session Number", "Question", "Answer", "Question Position",
        ],
        "Fixation by Condition": ["PID", "Session Number", "Condition", "Presentation",
                                  "Accuracy (%)", "Mean Reaction Time (ms)", "Targets", "Hits",
                                  "Misses", "False Alarms", "Run Aborted", "Session Aborted"],
        "Fixation Responses": ["PID", "Session Number", "Condition", "Outcome",
                               "Reaction Time (s)", "Row Type", "Key"],
        "Task Answers": ["PID", "Session Number", "Condition", "Phase", "Record Type",
                         "Question", "Answer",
                         "Reaction Time (s)", "Status", "Correct", "Task"],
    }.get(name, [])
    ordered = [*primary, *(header for header in headers if header not in primary)]
    indexes = [headers.index(header) for header in ordered]
    headers = ordered
    rows = [[row[index] for index in indexes] for row in rows]
    worksheet = workbook.create_sheet(name)
    worksheet.append(headers)
    for row in rows:
        worksheet.append(row)
    for row in worksheet.iter_rows():
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"  # Participant-entered text is never an Excel formula.
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            if cell.row == 1:
                cell.font = Font(bold=True)
    worksheet.freeze_panes = "C2" if name != "Results Notes" else "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    for index, header in enumerate(headers, 1):
        worksheet.column_dimensions[get_column_letter(index)].alignment = Alignment(
            horizontal="center", vertical="center", wrap_text=True,
        )
        for cell in worksheet.iter_cols(min_col=index, max_col=index, min_row=2):
            for item in cell:
                if isinstance(item.value, (int, float)):
                    if header == "Reaction Time (s)":
                        item.number_format = "0.000"
                    elif header in {"Accuracy (%)", "Mean Reaction Time (ms)"}:
                        item.number_format = "0.00"


def add_participant_results_sheets(
    workbook: Any, project_root: Path, history_rows: list[dict[str, str]],
) -> None:
    """Add research sheets, leaving the existing participant-summary sheet intact.

    Reads only retained project-local execution records. Errors propagate before
    the caller atomically saves the workbook, preserving the previous workbook.
    """

    records = _records(project_root, history_rows)
    _sheet(workbook, "Demographics", _DEMOGRAPHICS_HEADERS,
           _demographic_rows(records, history_rows))
    _sheet(workbook, DEMOGRAPHIC_ANSWERS_SHEET_NAME, _DEMOGRAPHIC_ANSWER_HEADERS,
           _demographic_answer_rows(records))
    _sheet(workbook, "Fixation by Condition", _FIXATION_HEADERS,
           _fixation_rows(history_rows, records))
    _sheet(workbook, "Fixation Responses", _FIXATION_RESPONSE_HEADERS,
           _fixation_response_rows(records))
    _sheet(workbook, "Task Answers", _ANSWER_HEADERS, _answer_rows(records))
    _sheet(workbook, "Results Notes", ["Topic", "Meaning"], [
        ["Fixation accuracy", "100 × hits / targets. False alarms are reported separately."],
        ["Condition mean fixation reaction time",
         "Milliseconds; hits only. Missing values stay blank."],
        ["Task reaction time", "Seconds; each recorded response/attempt has its own row."],
        ["Demographic answers", "One row per question and visit, in the recorded order. "
         "Checkbox selections are listed one per line. A blank answer marks a skipped question. "
         "Earlier visits without question snapshots show available fields in Demographics."],
        ["Individual fixation responses", "One row per target plus unmatched keypresses; matched "
         "hit keypresses are not duplicated. Historical compact output retains averages only, "
         "so unavailable individual responses cannot be reconstructed."],
        ["Inclusion", "Fixation summaries exclude test IDs 0/00 and whole aborted visits. "
         "Research sheets retain these records and label their status."],
        ["Question labels", "Original compiled wording and option labels are used. Historical "
         "labels without an archived definition are explicitly unavailable."],
        ["Legacy visits", "Unnumbered records with ambiguous identity remain separate. "
         "A blank value means unavailable, not zero."],
        ["Sensitive participant data", "This workbook contains demographics and raw task answers. "
         "It is participant research output."],
    ])
    workbook.active = workbook.sheetnames.index(
        "Fixation by Condition" if history_rows else "Demographics",
    )
    autofit_workbook(workbook)
