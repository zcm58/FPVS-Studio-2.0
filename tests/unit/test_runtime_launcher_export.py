"""Runtime launcher boundary tests."""

from __future__ import annotations

from pathlib import Path

from tests.unit.runtime_launcher_helpers import (
    PARTICIPANT_NUMBER,
    StubEngine,
    _read_csv_rows,
)

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.serialization import read_json_file
from fpvs_studio.engines.registry import register_engine, unregister_engine
from fpvs_studio.runtime.launcher import (
    LaunchSettings,
    launch_session,
)


def test_session_export_captures_seed_and_runtime_logs(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-export", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
            random_seed=77,
        )

        summary = launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-export", test_mode=True),
        )
    finally:
        unregister_engine("stub-export")

    assert summary.output_dir is not None
    session_output_dir = multi_condition_project_root / Path(summary.output_dir)
    exported_summary = read_json_file(
        session_output_dir / "session_summary.json",
        SessionExecutionSummary,
    )

    assert exported_summary.random_seed == 77
    assert exported_summary.participant_number == PARTICIPANT_NUMBER
    assert exported_summary.realized_block_orders == [
        block.condition_order for block in session_plan.blocks
    ]
    assert (session_output_dir / "frame_intervals.csv").is_file()
    assert (session_output_dir / "fixation_events.csv").is_file()
    assert (session_output_dir / "responses.csv").is_file()
    assert (session_output_dir / "trigger_log.csv").is_file()
    assert [run_result.run_id for run_result in exported_summary.run_results] == [
        entry.run_id for entry in session_plan.ordered_entries()
    ]
    assert all(
        run_result.participant_number == PARTICIPANT_NUMBER
        for run_result in exported_summary.run_results
    )

    conditions_rows = _read_csv_rows(session_output_dir / "conditions.csv")
    fixation_rows = _read_csv_rows(session_output_dir / "fixation_events.csv")
    response_rows = _read_csv_rows(session_output_dir / "responses.csv")
    trigger_rows = _read_csv_rows(session_output_dir / "trigger_log.csv")

    assert [row["run_id"] for row in conditions_rows] == [
        entry.run_id for entry in session_plan.ordered_entries()
    ]
    assert len(fixation_rows) == sum(
        len(run_result.fixation_responses) for run_result in exported_summary.run_results
    )
    assert len(response_rows) == sum(
        len(run_result.response_log) for run_result in exported_summary.run_results
    )
    assert len(trigger_rows) == sum(
        len(run_result.trigger_log) for run_result in exported_summary.run_results
    )


