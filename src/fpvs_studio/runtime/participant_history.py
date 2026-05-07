"""Runtime helpers for participant-session history lookup. It reads prior execution
summaries and naming conventions so launch flows can resolve stable output labels
without changing core contracts. The module owns runtime filesystem history queries
only; scoring, compilation, and export writing stay in adjacent runtime or core layers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from random import SystemRandom
from typing import Protocol

from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.paths import runs_dir
from fpvs_studio.core.serialization import read_json_file

_SESSION_SEED_UPPER_BOUND = 2**31
_MAX_SEED_GENERATION_ATTEMPTS = 10_000


class _SeedRng(Protocol):
    def randrange(self, stop: int) -> int:
        """Return a random integer in ``range(stop)``."""
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
    for output_label, summary in _iter_session_summaries(project_root):
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

    base_label = participant_number
    runs_root = runs_dir(project_root)
    if not (runs_root / base_label).exists():
        return base_label

    suffix = 2
    while (runs_root / f"{base_label}_run{suffix}").exists():
        suffix += 1
    return f"{base_label}_run{suffix}"


def completed_session_seeds(project_root: Path) -> set[int]:
    """Return seeds consumed by completed, non-aborted prior sessions."""

    seeds: set[int] = set()
    for _output_label, summary in _iter_session_summaries(project_root):
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


def _summary_consumes_seed(summary: SessionExecutionSummary) -> bool:
    if summary.aborted:
        return False
    if summary.total_condition_count <= 0:
        return False
    return summary.completed_condition_count >= summary.total_condition_count
