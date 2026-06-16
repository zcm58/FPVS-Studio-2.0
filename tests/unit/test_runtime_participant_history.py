"""Participant history helpers for duplicate launch checks."""

from __future__ import annotations

import csv
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
from fpvs_studio.runtime.session_export import SESSION_CONDITION_HISTORY_HEADER


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


def _write_condition_history_rows(
    project_root: Path,
    rows: list[dict[str, str]],
) -> None:
    history_path = project_root / "logs" / "session_condition_history.csv"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SESSION_CONDITION_HISTORY_HEADER)
        writer.writeheader()
        writer.writerows(rows)


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


def test_find_completed_sessions_for_participant_reads_compact_history_rows(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    _write_condition_history_rows(
        project_root,
        [
            {
                "project_id": "project-1",
                "participant_number": "0001",
                "participant_age": "28",
                "participant_sex": "Female",
                "participant_handedness": "Right handed",
                "session_id": "session-compact",
                "session_seed": "404",
                "session_aborted": "False",
                "output_dir": "",
                "run_id": "run-a",
                "run_finished_at": "2026-01-01T00:00:01+00:00",
                "run_aborted": "False",
            },
            {
                "project_id": "project-1",
                "participant_number": "0001",
                "participant_age": "28",
                "participant_sex": "Female",
                "participant_handedness": "Right handed",
                "session_id": "session-compact",
                "session_seed": "404",
                "session_aborted": "False",
                "output_dir": "",
                "run_id": "run-b",
                "run_finished_at": "2026-01-01T00:00:02+00:00",
                "run_aborted": "False",
            },
            {
                "project_id": "project-1",
                "participant_number": "0001",
                "session_id": "session-aborted",
                "session_seed": "505",
                "session_aborted": "True",
                "output_dir": "",
                "run_id": "run-c",
                "run_finished_at": "2026-01-01T00:00:03+00:00",
                "run_aborted": "True",
            },
        ],
    )

    records = find_completed_sessions_for_participant(project_root, "0001")

    assert len(records) == 1
    assert records[0].output_label == "session-compact"
    assert records[0].summary.participant_number == "0001"
    assert records[0].summary.participant_metadata.age == 28
    assert records[0].summary.participant_metadata.sex == "Female"
    assert records[0].summary.participant_metadata.handedness == "Right handed"
    assert records[0].summary.random_seed == 404
    assert records[0].summary.total_condition_count == 2
    assert records[0].summary.completed_condition_count == 2
    assert records[0].summary.output_dir is None


def test_resolve_next_participant_output_label_uses_run_suffixes(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    runs_root = project_root / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    assert resolve_next_participant_output_label(project_root, "0001") == "P0001"

    (runs_root / "P0001").mkdir()
    assert resolve_next_participant_output_label(project_root, "0001") == "P0001_run2"

    (runs_root / "P0001_run2").mkdir()
    (runs_root / "P0001_run3").mkdir()
    assert resolve_next_participant_output_label(project_root, "0001") == "P0001_run4"


def test_resolve_next_participant_output_label_counts_legacy_digit_folders(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    runs_root = project_root / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    (runs_root / "0001").mkdir()
    (runs_root / "0001_run2").mkdir()

    assert resolve_next_participant_output_label(project_root, "0001") == "P0001_run3"


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


def test_completed_session_seeds_include_compact_history_rows(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    _write_condition_history_rows(
        project_root,
        [
            {
                "project_id": "project-1",
                "participant_number": "0001",
                "session_id": "session-compact",
                "session_seed": "404",
                "session_aborted": "False",
                "output_dir": "",
                "run_id": "run-a",
                "run_finished_at": "2026-01-01T00:00:01+00:00",
                "run_aborted": "False",
            },
            {
                "project_id": "project-1",
                "participant_number": "0002",
                "session_id": "session-aborted",
                "session_seed": "505",
                "session_aborted": "True",
                "output_dir": "",
                "run_id": "run-b",
                "run_finished_at": "2026-01-01T00:00:02+00:00",
                "run_aborted": "True",
            },
        ],
    )

    assert completed_session_seeds(project_root) == {404}


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
