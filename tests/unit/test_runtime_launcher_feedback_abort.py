"""Runtime launcher boundary tests."""

from __future__ import annotations

from pathlib import Path

from tests.unit.runtime_launcher_helpers import (
    PARTICIPANT_NUMBER,
    StubEngine,
)

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.execution import RunExecutionSummary, SessionExecutionSummary
from fpvs_studio.core.serialization import read_json_file
from fpvs_studio.engines.registry import register_engine, unregister_engine
from fpvs_studio.runtime.launcher import (
    LaunchSettings,
    launch_session,
)


def test_session_launch_shows_condition_feedback_with_accuracy_and_mean_rt_when_enabled(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    captures: dict[str, object] = {}
    multi_condition_project.settings.fixation_task.accuracy_task_enabled = True
    register_engine("stub-feedback", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
            random_seed=123,
        )
        summary = launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-feedback", test_mode=True),
        )
    finally:
        unregister_engine("stub-feedback")

    assert all(run_result.fixation_task_summary is not None for run_result in summary.run_results)
    first_summary = summary.run_results[0].fixation_task_summary
    assert first_summary is not None
    assert first_summary.total_targets == len(
        session_plan.ordered_entries()[0].run_spec.fixation_events
    )
    assert first_summary.hit_count == 1
    assert first_summary.mean_rt_ms == 0.0
    assert len(captures["condition_feedback"]) == session_plan.total_runs
    assert "You successfully detected" in captures["condition_feedback"][0]["body"]
    assert "Your average reaction time was" in captures["condition_feedback"][0]["body"]
    if session_plan.total_runs > 1:
        assert "Compared with the previous condition" in captures["condition_feedback"][1]["body"]




def test_session_launch_skips_condition_feedback_when_accuracy_task_disabled(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    captures: dict[str, object] = {}
    multi_condition_project.settings.fixation_task.accuracy_task_enabled = False
    register_engine("stub-no-feedback", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
            random_seed=124,
        )
        summary = launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-no-feedback", test_mode=True),
        )
    finally:
        unregister_engine("stub-no-feedback")

    assert all(run_result.fixation_task_summary is None for run_result in summary.run_results)
    assert captures.get("condition_feedback") is None




def test_session_launch_aborts_cleanly_when_inter_block_break_is_cancelled(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    captures: dict[str, object] = {"abort_on_block_break": True}
    register_engine("stub-block-break-abort", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
            random_seed=18,
        )

        summary = launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(
                engine_name="stub-block-break-abort",
                test_mode=True,
            ),
        )
    finally:
        unregister_engine("stub-block-break-abort")

    assert summary.aborted is True
    assert summary.completed_condition_count == len(session_plan.blocks[0].entries)
    assert summary.abort_reason == "Session aborted during the inter-block break after block 1."
    assert captures["block_breaks"] == [
        {
            "completed_block_index": 0,
            "total_block_count": 2,
            "next_block_index": 1,
        }
    ]
    assert captures.get("completion_screens") is None




def test_session_launch_exports_timing_aborted_status_from_run_result(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {"timing_abort_on_first_run": True}
    register_engine("stub-timing-abort", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            random_seed=37,
        )

        summary = launch_session(
            sample_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-timing-abort", test_mode=True),
        )
    finally:
        unregister_engine("stub-timing-abort")

    assert summary.aborted is True
    assert summary.completed_condition_count == 0
    assert len(summary.run_results) == 1
    assert summary.run_results[0].aborted is True
    assert "Strict timing aborted run" in (summary.abort_reason or "")
    assert summary.run_results[0].runtime_metadata is not None
    assert summary.run_results[0].runtime_metadata.timing_qc_strict_abort is True
    assert captures["run_ids"] == [session_plan.ordered_entries()[0].run_id]
    assert summary.output_dir is not None
    session_output_dir = sample_project_root / Path(summary.output_dir)
    exported_summary = read_json_file(
        session_output_dir / "session_summary.json",
        SessionExecutionSummary,
    )
    exported_run_summary = read_json_file(
        session_output_dir / session_plan.ordered_entries()[0].run_id / "run_summary.json",
        RunExecutionSummary,
    )

    assert exported_summary.aborted is True
    assert exported_summary.completed_condition_count == 0
    assert exported_summary.run_results[0].runtime_metadata is not None
    assert exported_summary.run_results[0].runtime_metadata.timing_qc_strict_abort is True
    assert exported_run_summary.aborted is True
    assert exported_run_summary.runtime_metadata is not None
    assert exported_run_summary.runtime_metadata.timing_qc_first_bad_frame_index == 1


