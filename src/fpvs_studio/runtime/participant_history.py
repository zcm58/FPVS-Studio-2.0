"""Runtime helpers for participant-session history lookup. It reads prior execution
summaries and naming conventions so launch flows can resolve stable output labels
without changing core contracts. The module owns runtime filesystem history queries
only; scoring, compilation, and export writing stay in adjacent runtime or core layers."""

from __future__ import annotations

import csv
from dataclasses import dataclass
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
) -> list[tuple[str, SessionExecutionSummary]]:
    discovered: list[tuple[str, SessionExecutionSummary]] = []
    seen_session_ids: set[str] = set()
    for output_label, summary in _iter_session_summaries(project_root):
        discovered.append((output_label, summary))
        seen_session_ids.add(summary.session_id)
    for output_label, summary in _iter_session_condition_history_summaries(project_root):
        if summary.session_id in seen_session_ids:
            continue
        discovered.append((output_label, summary))
        seen_session_ids.add(summary.session_id)
    return discovered


def _iter_session_summaries(
    project_root: Path,
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
        except Exception:
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
        rows = [
            {str(key): "" if value is None else value for key, value in row.items() if key}
            for row in csv.DictReader(handle)
        ]

    grouped_rows: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        session_id = row.get("session_id", "")
        participant_number = row.get("participant_number", "")
        output_dir = row.get("output_dir", "")
        if not session_id:
            continue
        grouped_rows.setdefault((participant_number, session_id, output_dir), []).append(row)

    summaries: list[tuple[str, SessionExecutionSummary]] = []
    for (participant_number, session_id, output_dir), session_rows in grouped_rows.items():
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
                    participant_metadata=ParticipantMetadata(
                        age=_csv_int(first_row.get("participant_age")),
                        sex=first_row.get("participant_sex") or None,
                        handedness=first_row.get("participant_handedness") or None,
                        colorblind=_csv_bool_or_none(
                            first_row.get("participant_colorblind")
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
