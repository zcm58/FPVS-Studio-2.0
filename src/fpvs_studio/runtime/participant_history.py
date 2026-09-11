"""Runtime helpers for participant-session history lookup. It reads prior execution
summaries and naming conventions so launch flows can resolve stable output labels
without changing core contracts. The module owns runtime filesystem history queries
only; scoring, compilation, and export writing stay in adjacent runtime or core layers."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from random import SystemRandom
from typing import Protocol

from fpvs_studio.core.enums import RunMode
from fpvs_studio.core.execution import ParticipantMetadata, SessionExecutionSummary
from fpvs_studio.core.paths import logs_dir, runs_dir
from fpvs_studio.core.serialization import read_json_file

_SESSION_CONDITION_HISTORY_FILENAME = "session_condition_history.csv"
_PARTICIPANT_OUTPUT_PREFIX = "P"

_SESSION_SEED_UPPER_BOUND = 2**31
_MAX_SEED_GENERATION_ATTEMPTS = 10_000


class _SeedRng(Protocol):
    def randrange(self, start: int, stop: int | None = None, step: int = 1) -> int:
        """Return a random integer from the requested range."""
        ...


@dataclass(frozen=True)
class CompletedParticipantSessionRecord:
    """One completed participant session discovered from run exports."""

    output_label: str
    summary: SessionExecutionSummary


@dataclass(frozen=True)
class ParticipantSessionNumberSource:
    """Evidence for one participant visit, including unnumbered historical exports."""

    participant_number: str
    output_label: str
    occurred_at: str = ""
    participant_session_number: int | None = None


def infer_participant_session_numbers(sources: list[ParticipantSessionNumberSource]) -> list[int]:
    """Assign deterministic legacy numbers while retaining explicit recorded numbers.

    Legacy folder suffixes are evidence, not a unique identity: both ``1`` and
    ``P1`` can hold separate sessions. Date order breaks those historical collisions.
    """

    assigned = [0] * len(sources)
    occupied: dict[str, set[int]] = {}
    for index, source in enumerate(sources):
        if source.participant_session_number is not None:
            assigned[index] = source.participant_session_number
            occupied.setdefault(source.participant_number, set()).add(assigned[index])
    unnumbered = sorted(
        (index for index, number in enumerate(assigned) if not number),
        key=lambda index: (
            sources[index].occurred_at,
            participant_session_number_from_output_label(
                sources[index].output_label, sources[index].participant_number
            ) or 1,
            sources[index].output_label,
            index,
        ),
    )
    for index in unnumbered:
        source = sources[index]
        used = occupied.setdefault(source.participant_number, set())
        number = participant_session_number_from_output_label(
            source.output_label, source.participant_number
        ) or 1
        while number in used:
            number += 1
        assigned[index] = number
        used.add(number)
    return assigned


def participant_session_history_identity(row: dict[str, str]) -> tuple[str, str, str, str]:
    """Identify numbered visits and recover separate legacy compact export batches."""

    output_dir = row.get("output_dir", "")
    session_number = row.get("participant_session_number", "")
    if not session_number and not output_dir and row.get("logged_at_utc"):
        session_number = f"legacy-export:{row['logged_at_utc']}"
    return (
        row.get("participant_number", ""),
        row.get("session_id", ""),
        output_dir,
        session_number,
    )


def find_completed_sessions_for_participant(
    project_root: Path,
    participant_number: str,
) -> list[CompletedParticipantSessionRecord]:
    """Return completed prior session summaries for one participant number."""

    completed_records: list[CompletedParticipantSessionRecord] = []
    for output_label, summary in _iter_session_history_summaries(project_root):
        if summary.participant_number != participant_number:
            continue
        if summary.aborted:
            continue
        if summary.completed_condition_count <= 0:
            continue
        completed_records.append(
            CompletedParticipantSessionRecord(
                output_label=output_label,
                summary=summary,
            )
        )
    return completed_records


def resolve_next_participant_output_label(
    project_root: Path,
    participant_number: str,
) -> str:
    """Return the next available participant-labeled output directory name."""

    base_label = _participant_output_label(participant_number)
    runs_root = runs_dir(project_root)
    if not _participant_output_label_exists(runs_root, participant_number):
        return base_label

    suffix = 2
    while _participant_output_label_exists(runs_root, participant_number, suffix=suffix):
        suffix += 1
    return f"{base_label}_run{suffix}"


def _participant_output_label(participant_number: str) -> str:
    return f"{_PARTICIPANT_OUTPUT_PREFIX}{participant_number}"


def participant_session_number_from_output_label(
    output_label: str, participant_number: str
) -> int | None:
    """Read a visit number from current or legacy participant folder names."""

    match = re.fullmatch(
        rf"P?{re.escape(participant_number)}(?:(?:_run|_session)([0-9]+))?",
        output_label,
    )
    if match is None:
        return None
    number = int(match.group(1) or "1")
    return number if number > 0 else None


def _participant_output_label_exists(
    runs_root: Path,
    participant_number: str,
    *,
    suffix: int | None = None,
) -> bool:
    current_label = _participant_output_label(participant_number)
    legacy_label = participant_number
    if suffix is not None:
        current_label = f"{current_label}_run{suffix}"
        legacy_label = f"{legacy_label}_run{suffix}"
    return (runs_root / current_label).exists() or (runs_root / legacy_label).exists()


def completed_session_seeds(project_root: Path) -> set[int]:
    """Return seeds consumed by completed, non-aborted prior sessions."""

    seeds: set[int] = set()
    for _output_label, summary in _iter_session_history_summaries(project_root):
        if not _summary_consumes_seed(summary):
            continue
        if summary.random_seed is not None:
            seeds.add(summary.random_seed)
    return seeds


def generate_unused_session_seed(
    project_root: Path,
    *,
    rng: _SeedRng | None = None,
    upper_bound: int = _SESSION_SEED_UPPER_BOUND,
) -> int:
    """Generate a session seed that has not been used by a completed session."""

    consumed_seeds = completed_session_seeds(project_root)
    generator = rng or SystemRandom()
    for _attempt in range(_MAX_SEED_GENERATION_ATTEMPTS):
        candidate = generator.randrange(upper_bound)
        if candidate not in consumed_seeds:
            return candidate
    raise RuntimeError("Unable to generate an unused session seed for this project.")


def _iter_session_history_summaries(
    project_root: Path,
    *,
    strict: bool = False,
) -> list[tuple[str, SessionExecutionSummary]]:
    discovered: list[tuple[str, SessionExecutionSummary]] = []
    seen_sessions: set[tuple[str | None, str, str | None, int | None]] = set()
    for output_label, summary in _iter_session_summaries(project_root, strict=strict):
        discovered.append((output_label, summary))
        seen_sessions.add(_session_identity(summary))
    for output_label, summary in _iter_session_condition_history_summaries(project_root):
        if summary.output_dir and _session_identity(summary) in seen_sessions:
            continue
        discovered.append((output_label, summary))
    return discovered


def _session_identity(
    summary: SessionExecutionSummary,
) -> tuple[str | None, str, str | None, int | None]:
    return (
        summary.participant_number,
        summary.session_id,
        summary.output_dir,
        summary.participant_session_number,
    )


def _iter_session_summaries(
    project_root: Path,
    *,
    strict: bool = False,
) -> list[tuple[str, SessionExecutionSummary]]:
    runs_root = runs_dir(project_root)
    if not runs_root.is_dir():
        return []

    discovered: list[tuple[str, SessionExecutionSummary]] = []
    for entry in runs_root.iterdir():
        if not entry.is_dir():
            continue
        summary_path = entry / "session_summary.json"
        if not summary_path.is_file():
            continue
        try:
            summary = read_json_file(summary_path, SessionExecutionSummary)
        except Exception as exc:
            if strict:
                raise ValueError(
                    f"Could not read session history in '{entry.name}'. "
                    "Repair or restore the history before launching another session."
                ) from exc
            continue
        discovered.append((entry.name, summary))
    return discovered


def _iter_session_condition_history_summaries(
    project_root: Path,
) -> list[tuple[str, SessionExecutionSummary]]:
    history_path = logs_dir(project_root) / _SESSION_CONDITION_HISTORY_FILENAME
    if not history_path.is_file():
        return []

    with history_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"session_id", "participant_number"}.issubset(
            reader.fieldnames
        ):
            raise ValueError("Participant session history has an incompatible header.")
        if len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("Participant session history contains duplicate column names.")
        raw_rows = list(reader)
        if any(None in row for row in raw_rows):
            raise ValueError("Participant session history contains malformed rows.")
        rows = [
            {str(key): "" if value is None else value for key, value in row.items() if key}
            for row in raw_rows
        ]

    grouped_rows: dict[tuple[str, str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        session_id = row.get("session_id", "")
        participant_number = row.get("participant_number", "")
        if not session_id:
            raise ValueError("Participant session history contains a row without a session ID.")
        if not participant_number:
            raise ValueError("Participant session history contains a row without a participant ID.")
        number_text = row.get("participant_session_number", "").strip()
        if number_text and (
            not number_text.isascii() or not number_text.isdigit() or int(number_text) < 1
        ):
            raise ValueError("Participant session history contains an invalid session number.")
        grouped_rows.setdefault(participant_session_history_identity(row), []).append(row)

    summaries: list[tuple[str, SessionExecutionSummary]] = []
    for (
        participant_number, session_id, output_dir, _visit_identity
    ), session_rows in grouped_rows.items():
        first_row = session_rows[0]
        session_aborted = any(_csv_bool(row.get("session_aborted")) for row in session_rows)
        total_condition_count = len(session_rows)
        completed_condition_count = sum(
            1
            for row in session_rows
            if not _csv_bool(row.get("run_aborted")) and bool(row.get("run_finished_at", ""))
        )
        if not session_aborted and completed_condition_count == 0:
            completed_condition_count = total_condition_count
        output_label = Path(output_dir).name if output_dir else session_id
        summaries.append(
            (
                output_label,
                SessionExecutionSummary(
                    project_id=first_row.get("project_id", ""),
                    session_id=session_id,
                    engine_name="history",
                    run_mode=RunMode.SESSION,
                    participant_number=participant_number or None,
                    participant_session_number=_csv_int(first_row.get("participant_session_number")),
                    started_at=_csv_datetime(
                        first_row.get("session_started_at") or first_row.get("logged_at_utc")
                    ),
                    finished_at=_csv_datetime(first_row.get("session_finished_at")),
                    participant_metadata=ParticipantMetadata(
                        age=_csv_int(first_row.get("participant_age")),
                        sex=first_row.get("participant_sex") or None,
                        handedness=first_row.get("participant_handedness") or None,
                        colorblind=_csv_bool_or_none(
                            first_row.get("participant_colorblind")
                        ),
                        manual_removed_electrodes=(
                            first_row["manual_removed_electrodes"].split(";")
                            if first_row.get("manual_removed_electrodes") else None
                        ),
                    ),
                    random_seed=_csv_int(first_row.get("session_seed")),
                    total_condition_count=total_condition_count,
                    completed_condition_count=completed_condition_count,
                    aborted=session_aborted,
                    abort_reason=first_row.get("session_abort_reason") or None,
                    output_dir=output_dir or None,
                ),
            )
        )
    return summaries


def _summary_consumes_seed(summary: SessionExecutionSummary) -> bool:
    if summary.aborted:
        return False
    if summary.total_condition_count <= 0:
        return False
    return summary.completed_condition_count >= summary.total_condition_count


def _csv_bool(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "y"}


def _csv_bool_or_none(value: str | None) -> bool | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if cleaned in {"1", "true", "yes", "y"}:
        return True
    if cleaned in {"0", "false", "no", "n"}:
        return False
    return None


def _csv_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _csv_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
