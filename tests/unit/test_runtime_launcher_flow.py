"""Runtime launcher boundary tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.unit.runtime_launcher_helpers import (
    PARTICIPANT_NUMBER,
    StubEngine,
    _read_csv_rows,
)

from fpvs_studio.core.compiler import compile_run_spec, compile_session_plan
from fpvs_studio.core.enums import InterConditionMode
from fpvs_studio.core.execution import RunExecutionSummary
from fpvs_studio.core.models import DisplayValidationReport
from fpvs_studio.core.serialization import read_json_file
from fpvs_studio.engines.registry import register_engine, unregister_engine
from fpvs_studio.runtime.launcher import (
    LaunchSettings,
    LaunchSettingsError,
    launch_run,
    launch_session,
)
from fpvs_studio.runtime.preflight import PreflightError


def test_runtime_launcher_dispatches_runspec_to_registered_engine(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub", lambda: StubEngine(captures))
    try:
        run_spec = compile_run_spec(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            run_id="faces-run",
        )

        summary = launch_run(
            sample_project_root,
            run_spec,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(
                engine_name="stub",
                test_mode=True,
                serial_port="COM9",
                serial_baudrate=57600,
            ),
        )
    finally:
        unregister_engine("stub")

    assert captures["open_count"] == 1
    assert captures["close_count"] == 1
    assert captures["run_ids"] == ["faces-run"]
    assert captures["runtime_options"] == {
        "engine_name": "stub",
        "test_mode": True,
        "fullscreen": True,
        "display_index": None,
        "serial_port": "COM9",
        "serial_baudrate": 57600,
        "strict_timing": True,
        "strict_timing_warmup": True,
        "timing_miss_threshold_multiplier": 1.5,
        "timing_warmup_frames": 240,
    }
    assert summary.output_dir == "runs/faces-run"
    assert summary.participant_number == PARTICIPANT_NUMBER
    assert summary.warnings == []
    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.test_mode is True
    assert summary.trigger_log[0].label == "condition_start"
    assert (sample_project_root / "runs" / "faces-run" / "runspec.json").is_file()
    assert (sample_project_root / "runs" / "faces-run" / "run_summary.json").is_file()
    assert (sample_project_root / "runs" / "faces-run" / "runtime_metadata.json").is_file()
    assert (sample_project_root / "runs" / "faces-run" / "fixation_events.csv").is_file()
    assert (sample_project_root / "runs" / "faces-run" / "trigger_log.csv").is_file()
    exported_run_summary = read_json_file(
        sample_project_root / "runs" / "faces-run" / "run_summary.json",
        RunExecutionSummary,
    )
    assert exported_run_summary.participant_number == PARTICIPANT_NUMBER

    exported_display_report = read_json_file(
        sample_project_root / "runs" / "faces-run" / "display_report.json",
        DisplayValidationReport,
    )
    exported_fixation_rows = _read_csv_rows(
        sample_project_root / "runs" / "faces-run" / "fixation_events.csv"
    )
    exported_response_rows = _read_csv_rows(
        sample_project_root / "runs" / "faces-run" / "responses.csv"
    )
    exported_trigger_rows = _read_csv_rows(
        sample_project_root / "runs" / "faces-run" / "trigger_log.csv"
    )

    assert exported_display_report.compatible is True
    assert exported_display_report.frames_per_cycle == run_spec.display.frames_per_stimulus
    assert len(exported_fixation_rows) == len(run_spec.fixation_events)
    assert exported_fixation_rows[0]["event_index"] == "0"
    assert exported_fixation_rows[0]["start_frame"] == str(run_spec.fixation_events[0].start_frame)
    assert exported_fixation_rows[0]["duration_frames"] == str(
        run_spec.fixation_events[0].duration_frames
    )
    assert exported_fixation_rows[0]["outcome"] == "hit"
    assert exported_response_rows[0]["matched_event_index"] == "0"
    assert exported_response_rows[0]["correct"] == "True"
    assert [row["label"] for row in exported_trigger_rows] == [
        trigger_event.label for trigger_event in run_spec.trigger_events
    ]




def test_launch_session_runs_all_entries_with_stub_engine_and_reuses_session_window(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-session", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
            random_seed=99,
        )

        summary = launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-session", test_mode=True),
        )
    finally:
        unregister_engine("stub-session")

    assert captures["open_count"] == 1
    assert captures["close_count"] == 1
    assert captures["run_ids"] == [entry.run_id for entry in session_plan.ordered_entries()]
    assert len(captures["transitions"]) == session_plan.total_runs
    assert captures["block_breaks"] == [
        {
            "completed_block_index": 0,
            "total_block_count": session_plan.block_count,
            "next_block_index": 1,
        }
    ]
    assert captures["completion_screens"] == [
        {
            "completed_condition_count": session_plan.total_runs,
            "total_condition_count": session_plan.total_runs,
            "was_aborted": False,
        }
    ]
    assert summary.completed_condition_count == session_plan.total_runs
    assert summary.output_dir == f"runs/{PARTICIPANT_NUMBER}"
    assert summary.participant_number == PARTICIPANT_NUMBER
    assert all(
        run_result.participant_number == PARTICIPANT_NUMBER for run_result in summary.run_results
    )
    assert summary.realized_block_orders == [block.condition_order for block in session_plan.blocks]
    assert summary.output_dir is not None
    session_output_dir = multi_condition_project_root / Path(summary.output_dir)
    assert (session_output_dir / "session_plan.json").is_file()
    assert (session_output_dir / "session_summary.json").is_file()
    assert (session_output_dir / "runtime_metadata.json").is_file()
    first_run_dir = session_output_dir / session_plan.ordered_entries()[0].run_id
    assert (first_run_dir / "runspec.json").is_file()
    assert (first_run_dir / "run_summary.json").is_file()




def test_launch_session_reuses_participant_number_with_incremented_output_labels(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-participant-folders", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
            random_seed=401,
        )
        summary_1 = launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-participant-folders", test_mode=True),
        )
        summary_2 = launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-participant-folders", test_mode=True),
        )
        summary_3 = launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-participant-folders", test_mode=True),
        )
    finally:
        unregister_engine("stub-participant-folders")

    assert summary_1.output_dir == f"runs/{PARTICIPANT_NUMBER}"
    assert summary_2.output_dir == f"runs/{PARTICIPANT_NUMBER}_run2"
    assert summary_3.output_dir == f"runs/{PARTICIPANT_NUMBER}_run3"
    assert summary_1.output_dir is not None
    assert summary_2.output_dir is not None
    assert summary_3.output_dir is not None
    assert (
        multi_condition_project_root / Path(summary_1.output_dir) / "session_summary.json"
    ).is_file()
    assert (
        multi_condition_project_root / Path(summary_2.output_dir) / "session_summary.json"
    ).is_file()
    assert (
        multi_condition_project_root / Path(summary_3.output_dir) / "session_summary.json"
    ).is_file()




def test_session_launch_fixed_break_transition_path_is_honored(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    captures: dict[str, object] = {}
    multi_condition_project.settings.session.inter_condition_break_seconds = 5.0
    register_engine("stub-fixed-break", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
            random_seed=13,
        )

        launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-fixed-break", test_mode=True),
        )
    finally:
        unregister_engine("stub-fixed-break")

    assert all(item["countdown_seconds"] == 5.0 for item in captures["transitions"])
    assert all(item["continue_key"] is None for item in captures["transitions"])




def test_session_launch_manual_continue_transition_path_is_honored(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    captures: dict[str, object] = {}
    multi_condition_project.settings.session.inter_condition_mode = (
        InterConditionMode.MANUAL_CONTINUE
    )
    multi_condition_project.settings.session.continue_key = "return"
    register_engine("stub-manual", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
            random_seed=14,
        )

        launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-manual", test_mode=True),
        )
    finally:
        unregister_engine("stub-manual")

    assert all(item["countdown_seconds"] is None for item in captures["transitions"])
    assert all(item["continue_key"] == "return" for item in captures["transitions"])




def test_session_launch_inserts_manual_inter_block_break_between_non_final_blocks(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-block-break", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
            random_seed=17,
        )

        launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-block-break", test_mode=True),
        )
    finally:
        unregister_engine("stub-block-break")

    assert captures["block_breaks"] == [
        {
            "completed_block_index": 0,
            "total_block_count": 2,
            "next_block_index": 1,
        }
    ]




def test_session_launch_passes_condition_instructions_to_transition_screens(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-instructions", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
            random_seed=15,
        )

        launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-instructions", test_mode=True),
        )
    finally:
        unregister_engine("stub-instructions")

    bodies = [item["body"] for item in captures["transitions"]]
    assert all("Instructions for condition" in body for body in bodies)




def test_session_launch_preserves_instruction_text_verbatim(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    captures: dict[str, object] = {}
    exact_text = "testing this, why is this happening"
    multi_condition_project.conditions[0].instructions = exact_text
    register_engine("stub-verbatim", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
            random_seed=16,
        )

        launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-verbatim", test_mode=True),
        )
    finally:
        unregister_engine("stub-verbatim")

    assert captures["condition_instructions"][0] == exact_text
    assert captures["transitions"][0]["body"].startswith(f"{exact_text}\n\n")




def test_session_launch_preflight_rejects_missing_assets_before_engine_run(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-preflight", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            random_seed=21,
        )
        missing_path = sample_project_root / Path(
            session_plan.ordered_entries()[0].run_spec.stimulus_sequence[0].image_path
        )
        missing_path.unlink()

        with pytest.raises(PreflightError, match="referenced assets are missing"):
            launch_session(
                sample_project_root,
                session_plan,
                participant_number=PARTICIPANT_NUMBER,
                launch_settings=LaunchSettings(engine_name="stub-preflight", test_mode=True),
            )
    finally:
        unregister_engine("stub-preflight")

    assert "run_ids" not in captures




def test_session_launch_preflight_rejects_invalid_timing_before_engine_run(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-invalid", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            random_seed=22,
        )
        session_plan.blocks[0].entries[0].run_spec.display.refresh_hz = 75.0

        with pytest.raises(PreflightError, match="display timing is incompatible"):
            launch_session(
                sample_project_root,
                session_plan,
                participant_number=PARTICIPANT_NUMBER,
                launch_settings=LaunchSettings(engine_name="stub-invalid", test_mode=True),
            )
    finally:
        unregister_engine("stub-invalid")

    assert "run_ids" not in captures




def test_launch_run_rejects_non_test_mode_even_with_registered_engine(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-non-test", lambda: StubEngine(captures))
    try:
        run_spec = compile_run_spec(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            run_id="faces-run",
        )

        with pytest.raises(LaunchSettingsError, match="requires test_mode=True"):
            launch_run(
                sample_project_root,
                run_spec,
                participant_number=PARTICIPANT_NUMBER,
                launch_settings=LaunchSettings(engine_name="stub-non-test", test_mode=False),
            )
    finally:
        unregister_engine("stub-non-test")

    assert captures == {}


