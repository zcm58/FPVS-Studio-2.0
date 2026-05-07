"""Participant history helpers for duplicate launch checks."""

from __future__ import annotations

from pathlib import Path

from fpvs_studio.core.enums import RunMode
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.serialization import write_json_file
from fpvs_studio.runtime.participant_history import (
    completed_session_seeds,
    find_completed_sessions_for_participant,
    generate_unused_session_seed,
    resolve_next_participant_output_label,
)


def _write_session_summary(
    project_root: Path,
    output_label: str,
    *,
    participant_number: str | None,
    aborted: bool,
    completed_condition_count: int,
    random_seed: int | None = None,
    total_condition_count: int = 4,
) -> None:
    summary = SessionExecutionSummary(
        project_id="project-1",
        session_id=f"{output_label}-session",
        engine_name="stub",
        run_mode=RunMode.TEST,
        participant_number=participant_number,
        random_seed=random_seed,
        total_condition_count=total_condition_count,
        completed_condition_count=completed_condition_count,
        aborted=aborted,
        output_dir=f"runs/{output_label}",
    )
    write_json_file(project_root / "runs" / output_label / "session_summary.json", summary)


def test_find_completed_sessions_for_participant_ignores_aborted_and_incomplete(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_session_summary(
        project_root,
        "0001",
        participant_number="0001",
        aborted=False,
        completed_condition_count=4,
    )
    _write_session_summary(
        project_root,
        "0001_run2",
        participant_number="0001",
        aborted=False,
        completed_condition_count=0,
    )
    _write_session_summary(
        project_root,
        "0001_run3",
        participant_number="0001",
        aborted=True,
        completed_condition_count=2,
    )
    _write_session_summary(
        project_root,
        "legacy-session-folder",
        participant_number="0002",
        aborted=False,
        completed_condition_count=3,
    )

    records = find_completed_sessions_for_participant(project_root, "0001")

    assert len(records) == 1
    assert records[0].output_label == "0001"
    assert records[0].summary.participant_number == "0001"
    assert records[0].summary.aborted is False
    assert records[0].summary.completed_condition_count == 4


def test_resolve_next_participant_output_label_uses_run_suffixes(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    runs_root = project_root / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    assert resolve_next_participant_output_label(project_root, "0001") == "0001"

    (runs_root / "0001").mkdir()
    assert resolve_next_participant_output_label(project_root, "0001") == "0001_run2"

    (runs_root / "0001_run2").mkdir()
    (runs_root / "0001_run3").mkdir()
    assert resolve_next_participant_output_label(project_root, "0001") == "0001_run4"


def test_completed_session_seeds_include_only_completed_non_aborted_sessions(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_session_summary(
        project_root,
        "0001",
        participant_number="0001",
        aborted=False,
        completed_condition_count=4,
        random_seed=101,
    )
    _write_session_summary(
        project_root,
        "0002",
        participant_number="0002",
        aborted=True,
        completed_condition_count=4,
        random_seed=202,
    )
    _write_session_summary(
        project_root,
        "0003",
        participant_number="0003",
        aborted=False,
        completed_condition_count=2,
        random_seed=303,
    )

    assert completed_session_seeds(project_root) == {101}


def test_generate_unused_session_seed_skips_consumed_seed(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _write_session_summary(
        project_root,
        "0001",
        participant_number="0001",
        aborted=False,
        completed_condition_count=4,
        random_seed=101,
    )
    returned_values = iter((101, 202))

    class _DeterministicRng:
        def randrange(self, _upper_bound: int) -> int:
            return next(returned_values)

    assert generate_unused_session_seed(project_root, rng=_DeterministicRng()) == 202
