"""Participant visit identity, historical compatibility, and non-overwriting exports."""

from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from openpyxl import load_workbook
from pydantic import ValidationError
from tests.unit.runtime_launcher_helpers import StubEngine, _read_csv_rows
from tests.unit.test_runtime_participant_history import (
    _write_condition_history_rows,
    _write_session_summary,
)

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.enums import RunMode
from fpvs_studio.core.execution import ParticipantMetadata, SessionExecutionSummary
from fpvs_studio.engines.registry import register_engine, unregister_engine
from fpvs_studio.runtime.fixation_report import load_fixation_cross_data
from fpvs_studio.runtime.launcher import LaunchSettings, launch_session
from fpvs_studio.runtime.participant_history import find_completed_sessions_for_participant
from fpvs_studio.runtime.participant_sessions import (
    ParticipantSessionConflictError,
    reserve_participant_session,
    resolve_next_participant_session_number,
)
from fpvs_studio.runtime.session_export import (
    PARTICIPANT_SUMMARY_HEADER,
    SESSION_CONDITION_HISTORY_HEADER,
    _upgrade_csv_header,
    append_session_condition_history,
    compact_task_checkpoint_path,
    refresh_participant_summary_if_stale,
    write_group_summary,
    write_participant_summary,
)


def test_visit_preview_is_read_only_and_preserves_leading_zeros(tmp_path: Path) -> None:
    root = tmp_path / "missing-project"
    assert resolve_next_participant_session_number(root, "001") == 1
    assert not root.exists()
    reserve_participant_session(root, "001", session_id="plan", create_output_directory=False)
    assert resolve_next_participant_session_number(root, "001") == 2
    assert resolve_next_participant_session_number(root, "1") == 1
    assert not (root / "runs").exists()


@pytest.mark.parametrize("participant_number", ["../1", "1/2", "", " 1", "C:\\1"])
def test_visit_paths_reject_invalid_participant_ids(
    tmp_path: Path, participant_number: str
) -> None:
    with pytest.raises(ValueError, match="digits"):
        resolve_next_participant_session_number(tmp_path, participant_number)
    assert list(tmp_path.iterdir()) == []


def test_distinct_bare_and_prefixed_legacy_folders_each_consume_a_visit(tmp_path: Path) -> None:
    for label in ("001", "P001"):
        _write_session_summary(
            tmp_path,
            label,
            participant_number="001",
            aborted=False,
            completed_condition_count=1,
        )
    (tmp_path / "runs" / "P001_run3").mkdir()
    assert resolve_next_participant_session_number(tmp_path, "001") == 4


def test_compact_aborted_and_crashed_sessions_are_never_reused(tmp_path: Path) -> None:
    _write_condition_history_rows(
        tmp_path,
        [
            {"participant_number": "001", "session_id": "old-compact", "session_aborted": "True"},
        ],
    )
    assert resolve_next_participant_session_number(tmp_path, "001") == 2
    reservation = reserve_participant_session(
        tmp_path,
        "001",
        session_id="crashed",
        create_output_directory=False,
    )
    assert reservation.participant_session_number == 2
    assert resolve_next_participant_session_number(tmp_path, "001") == 3
    full = reserve_participant_session(
        tmp_path,
        "001",
        session_id="later-full",
        create_output_directory=True,
    )
    assert full.output_label == "P001_session03"
    assert (tmp_path / "runs" / full.output_label).is_dir()


def test_stale_preview_rejects_launch_without_reusing_reserved_number(tmp_path: Path) -> None:
    first = reserve_participant_session(
        tmp_path,
        "001",
        session_id="one",
        participant_session_number=1,
        create_output_directory=False,
    )
    assert first.participant_session_number == 1
    with pytest.raises(ParticipantSessionConflictError, match="Session 2"):
        reserve_participant_session(
            tmp_path,
            "001",
            session_id="two",
            participant_session_number=1,
            create_output_directory=True,
        )
    assert not (tmp_path / "runs").exists()


def test_simultaneous_reservations_claim_distinct_visits(tmp_path: Path) -> None:
    def claim(_index: int) -> int:
        return reserve_participant_session(
            tmp_path,
            "001",
            session_id="same-plan",
            create_output_directory=False,
        ).participant_session_number

    with ThreadPoolExecutor(max_workers=4) as pool:
        numbers = list(pool.map(claim, range(4)))
    assert sorted(numbers) == [1, 2, 3, 4]
    assert resolve_next_participant_session_number(tmp_path, "001") == 5


def test_directory_race_preserves_existing_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_mkdir = Path.mkdir
    output_path = tmp_path / "runs" / "P001_session01"

    def conflicting_mkdir(path: Path, *args, **kwargs) -> None:
        if path == output_path and not output_path.exists():
            real_mkdir(path, parents=True)
            (path / "recording.bin").write_bytes(b"existing participant data")
        real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", conflicting_mkdir)
    reservation = reserve_participant_session(
        tmp_path,
        "001",
        session_id="plan",
        create_output_directory=True,
    )
    assert reservation.participant_session_number == 2
    assert (output_path / "recording.bin").read_bytes() == b"existing participant data"


@pytest.mark.parametrize("export_mode", ["full", "compact"])
def test_same_compiled_plan_produces_distinct_visits_and_preserves_first_session(
    multi_condition_project,
    multi_condition_project_root: Path,
    export_mode: str,
) -> None:
    root = multi_condition_project_root
    multi_condition_project.settings.fixation_task.accuracy_task_enabled = True
    plan = compile_session_plan(
        multi_condition_project, refresh_hz=60, project_root=root, random_seed=3
    )
    plan_before = plan.model_dump(mode="json")
    captures: dict[str, object] = {}
    register_engine("stub-visits", lambda: StubEngine(captures))
    settings = LaunchSettings(
        engine_name="stub-visits", export_mode=export_mode, verify_refresh_rate=False
    )
    try:
        first = launch_session(
            root,
            plan,
            participant_number="001",
            launch_settings=settings,
            participant_metadata=ParticipantMetadata(manual_removed_electrodes=[" a1 ", "A1"]),
        )
        first_files = (
            {
                path: path.read_bytes()
                for path in (root / first.output_dir).rglob("*")
                if path.is_file()
            }
            if first.output_dir
            else {}
        )
        second = launch_session(
            root,
            plan,
            participant_number="001",
            participant_session_number=2,
            launch_settings=settings,
            participant_metadata=ParticipantMetadata(manual_removed_electrodes=["B2"]),
        )
    finally:
        unregister_engine("stub-visits")
    assert plan.model_dump(mode="json") == plan_before
    assert first.session_id == second.session_id == plan.session_id
    assert [first.participant_session_number, second.participant_session_number] == [1, 2]
    assert all(run.participant_session_number == 2 for run in second.run_results)
    assert all(path.read_bytes() == data for path, data in first_files.items())
    if export_mode == "compact":
        assert first.output_dir is second.output_dir is None
        assert not (root / "runs").exists()
    else:
        assert first.output_dir == "runs/P001_session01"
        assert second.output_dir == "runs/P001_session02"
    history = _read_csv_rows(root / "logs" / "session_condition_history.csv")
    assert {row["participant_session_number"] for row in history} == {"1", "2"}
    assert {row["manual_removed_electrodes"] for row in history} == {"A1", "B2"}
    rows = _read_csv_rows(root / "logs" / "participant_summary.csv")
    assert [(row["PID"], row["Session Number"]) for row in rows] == [("001", "1"), ("001", "2")]
    assert len(find_completed_sessions_for_participant(root, "001")) == 2
    fixation = load_fixation_cross_data(root)
    assert fixation is not None and fixation.included_session_count == 2
    workbook = load_workbook(write_group_summary(root, root / "group.xlsx"))
    group_rows = list(workbook.active.values)
    session_column = group_rows[0].index("Session Number")
    assert [row[session_column] for row in group_rows[2:]] == [1, 2]
    workbook.close()


def test_failed_preflight_does_not_reserve_a_visit(
    multi_condition_project,
    multi_condition_project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = multi_condition_project_root
    plan = compile_session_plan(multi_condition_project, refresh_hz=60, project_root=root)

    def fail_preflight(*args, **kwargs) -> None:
        raise RuntimeError("preflight failed")

    monkeypatch.setattr("fpvs_studio.runtime.launcher.preflight_session_plan", fail_preflight)
    register_engine("stub-visits", lambda: StubEngine({}))
    try:
        with pytest.raises(RuntimeError, match="preflight failed"):
            launch_session(
                root,
                plan,
                participant_number="001",
                launch_settings=LaunchSettings(engine_name="stub-visits"),
            )
    finally:
        unregister_engine("stub-visits")
    assert resolve_next_participant_session_number(root, "001") == 1
    assert not (root / "logs").exists()


def test_numbered_compact_checkpoints_do_not_reuse_old_journals(tmp_path: Path) -> None:
    old = compact_task_checkpoint_path(tmp_path, participant_number="001", session_id="plan")
    old.parent.mkdir(parents=True)
    old.write_bytes(b"unfinalized legacy answers")
    first = compact_task_checkpoint_path(
        tmp_path, participant_number="001", session_id="plan", participant_session_number=1
    )
    second = compact_task_checkpoint_path(
        tmp_path, participant_number="001", session_id="plan", participant_session_number=2
    )
    assert len({old, first, second}) == 3
    assert old.read_bytes() == b"unfinalized legacy answers"


def test_legacy_summary_upgrade_numbers_visits_without_rewriting_history(tmp_path: Path) -> None:
    header = [
        column
        for column in SESSION_CONDITION_HISTORY_HEADER
        if column not in {"participant_session_number", "manual_removed_electrodes"}
    ]
    path = tmp_path / "logs" / "session_condition_history.csv"
    path.parent.mkdir()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(
            [
                {
                    "participant_number": "001",
                    "session_id": "late",
                    "output_dir": "runs/P001",
                    "session_started_at": "2026-02-01",
                },
                {
                    "participant_number": "001",
                    "session_id": "early",
                    "output_dir": "runs/001",
                    "session_started_at": "2026-01-01",
                },
            ]
        )
    before = path.read_bytes()
    summary = write_participant_summary(tmp_path)
    rows = _read_csv_rows(summary)
    assert {row["Session ID"]: row["Session Number"] for row in rows} == {"early": "1", "late": "2"}
    assert path.read_bytes() == before
    summary.write_text("PID,Session ID\n001,old\n", encoding="utf-8")
    assert refresh_participant_summary_if_stale(tmp_path) == summary
    assert list(_read_csv_rows(summary)[0]) == PARTICIPANT_SUMMARY_HEADER
    assert path.read_bytes() == before


def test_csv_header_migration_keeps_old_values_and_failed_replace_keeps_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "history.csv"
    path.write_text('pid,value\n001,"literal, value"\n', encoding="utf-8")
    before = path.read_bytes()

    def denied_replace(*args) -> None:
        raise PermissionError("busy")

    with monkeypatch.context() as context:
        context.setattr("fpvs_studio.runtime.session_export.os.replace", denied_replace)
        with pytest.raises(PermissionError):
            _upgrade_csv_header(path, ["pid", "value", "visit"])
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
    _upgrade_csv_header(path, ["pid", "value", "visit"])
    assert _read_csv_rows(path) == [{"pid": "001", "value": "literal, value", "visit": ""}]


def test_corrupt_history_blocks_session_allocation(tmp_path: Path) -> None:
    _write_condition_history_rows(tmp_path, [{"participant_number": "001", "session_id": ""}])
    with pytest.raises(ValueError, match="without a session ID"):
        resolve_next_participant_session_number(tmp_path, "001")
    assert not (tmp_path / "logs" / ".participant-sessions").exists()


def test_concurrent_export_upgrades_legacy_history_without_losing_rows(
    multi_condition_project,
    multi_condition_project_root: Path,
) -> None:
    root = multi_condition_project_root
    plan = compile_session_plan(multi_condition_project, refresh_hz=60, project_root=root)
    path = root / "logs" / "session_condition_history.csv"
    path.parent.mkdir()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SESSION_CONDITION_HISTORY_HEADER[:-2])
        writer.writeheader()
        writer.writerow({"participant_number": "001", "session_id": "legacy-session"})

    def export(number: int) -> None:
        append_session_condition_history(
            root,
            plan,
            SessionExecutionSummary(
                project_id=plan.project_id,
                session_id=plan.session_id,
                engine_name="stub",
                run_mode=RunMode.SESSION,
                participant_number="001",
                participant_session_number=number,
            ),
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(export, range(2, 6)))
    history = _read_csv_rows(path)
    assert len(history) == 1 + 4 * plan.total_runs
    assert history[0]["session_id"] == "legacy-session"
    for number in range(2, 6):
        assert (
            sum(row["participant_session_number"] == str(number) for row in history)
            == plan.total_runs
        )
    rows = _read_csv_rows(root / "logs" / "participant_summary.csv")
    assert sorted(int(row["Session Number"]) for row in rows) == [1, 2, 3, 4, 5]


def test_duplicate_csv_columns_never_lose_values_during_migration(tmp_path: Path) -> None:
    path = tmp_path / "history.csv"
    path.write_text("pid,pid\n001,002\n", encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="duplicate column names"):
        _upgrade_csv_header(path, ["pid", "visit"])
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "content",
    [
        "participant_number,session_id,participant_number\n001,plan,002\n",
        "participant_number,session_id\n001,plan,unexpected\n",
        "participant_number,session_id,participant_session_number\n001,plan,unknown\n",
    ],
)
def test_malformed_history_cannot_silently_change_visit_identity(
    tmp_path: Path, content: str
) -> None:
    path = tmp_path / "logs" / "session_condition_history.csv"
    path.parent.mkdir()
    path.write_text(content, encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError):
        resolve_next_participant_session_number(tmp_path, "001")
    assert path.read_bytes() == before


def test_legacy_compact_reused_plan_is_separated_by_original_export_timestamp(
    tmp_path: Path,
) -> None:
    _write_condition_history_rows(
        tmp_path,
        [
            {
                "participant_number": "001",
                "session_id": "reused-plan",
                "logged_at_utc": f"2026-01-0{number}T12:00:00+00:00",
                "session_aborted": "False",
                "run_aborted": "False",
                "condition_id": "condition",
                "condition_name": "Faces",
                "total_targets": "10",
                "hit_count": "5",
                "mean_rt_ms": "400",
            }
            for number in (1, 2)
        ],
    )
    assert resolve_next_participant_session_number(tmp_path, "001") == 3
    assert len(find_completed_sessions_for_participant(tmp_path, "001")) == 2
    assert [
        row["Session Number"] for row in _read_csv_rows(write_participant_summary(tmp_path))
    ] == [
        "1",
        "2",
    ]
    fixation = load_fixation_cross_data(tmp_path)
    assert fixation is not None and fixation.included_session_count == 2


@pytest.mark.parametrize("number", [0, -1, True, "2", 1.5])
def test_execution_visit_number_is_strict_positive_integer(number: object) -> None:
    with pytest.raises(ValidationError):
        SessionExecutionSummary(
            project_id="project",
            session_id="plan",
            engine_name="stub",
            run_mode=RunMode.SESSION,
            participant_session_number=number,
        )
