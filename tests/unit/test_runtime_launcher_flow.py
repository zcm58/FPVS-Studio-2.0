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
from fpvs_studio.engines.base import FixationTutorialAttemptResult
from fpvs_studio.engines.registry import register_engine, unregister_engine
from fpvs_studio.runtime.launcher import (
    LaunchSettings,
    LaunchSettingsError,
    launch_run,
    launch_session,
)
from fpvs_studio.runtime.preflight import PreflightError
from fpvs_studio.triggers.base import TriggerBackend


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
            ),
        )
    finally:
        unregister_engine("stub")

    assert captures["open_count"] == 1
    assert captures["close_count"] == 1
    assert captures["transitions"] == [
        {
            "heading": "Condition 1 of 1",
            "body": None,
            "countdown_seconds": None,
            "continue_key": "space",
            "continue_prompt": "Press Space to begin.",
        }
    ]
    assert captures["run_ids"] == ["faces-run"]
    assert captures["runtime_options"] == {
        "engine_name": "stub",
        "test_mode": True,
        "fullscreen": True,
        "display_index": None,
        "serial_enabled": False,
        "serial_port": "COM3",
        "serial_baudrate": 115200,
        "serial_pulse_width_ms": 10,
        "serial_reset_code": None,
        "serial_reset_delay_ms": 5,
        "strict_timing": True,
        "strict_timing_warmup": True,
        "timing_miss_threshold_multiplier": 1.5,
        "timing_warmup_frames": 240,
        "export_mode": "full",
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
    assert all(row["status"] == "skipped_disabled" for row in exported_trigger_rows)




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
    assert all(item["countdown_seconds"] is None for item in captures["transitions"])
    assert all(item["continue_key"] == "space" for item in captures["transitions"])
    assert all(
        item["continue_prompt"] == "Press Space to begin." for item in captures["transitions"]
    )
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


def test_launch_session_keeps_condition_titles_internal_on_transition_screens(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    multi_condition_project.settings.session.show_condition_title_on_screen = True
    captures: dict[str, object] = {}
    register_engine("stub-hidden-condition-titles", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
            random_seed=99,
        )

        launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(
                engine_name="stub-hidden-condition-titles",
                test_mode=True,
            ),
        )
    finally:
        unregister_engine("stub-hidden-condition-titles")

    headings = [item["heading"] for item in captures["transitions"]]
    assert headings == [
        f"Condition {index + 1} of {session_plan.total_runs}"
        for index in range(session_plan.total_runs)
    ]
    assert all(": " not in heading for heading in headings)


def test_launch_session_runs_participant_tutorial_once_before_first_transition(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    multi_condition_project.settings.fixation_task.enabled = True
    multi_condition_project.settings.fixation_task.accuracy_task_enabled = True
    multi_condition_project.settings.fixation_task.participant_tutorial_enabled = True
    captures: dict[str, object] = {
        "tutorial_attempt_results": [
            FixationTutorialAttemptResult(hit=True, reaction_time_s=0.31),
            FixationTutorialAttemptResult(hit=True, reaction_time_s=0.29),
            FixationTutorialAttemptResult(hit=True, reaction_time_s=0.27),
        ]
    }
    register_engine("stub-tutorial", lambda: StubEngine(captures))
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
            launch_settings=LaunchSettings(engine_name="stub-tutorial", test_mode=True),
        )
    finally:
        unregister_engine("stub-tutorial")

    ordered_entries = session_plan.ordered_entries()
    assert summary.aborted is False
    assert captures["tutorial_attempts"] == [
        {
            "run_id": ordered_entries[0].run_id,
            "target_delay_seconds": 1.0,
        },
        {
            "run_id": ordered_entries[0].run_id,
            "target_delay_seconds": 1.0,
        },
        {
            "run_id": ordered_entries[0].run_id,
            "target_delay_seconds": 1.0,
        },
    ]
    assert captures["run_ids"] == [entry.run_id for entry in ordered_entries]
    transitions = captures["transitions"]
    assert transitions[0]["heading"] == "Participant tutorial"
    assert transitions[1]["heading"] == "Great job! Let's try this again."
    assert transitions[2]["heading"].startswith("Great! Let's practice one more time")
    assert transitions[3]["heading"] == "Tutorial complete."
    assert transitions[4]["heading"].startswith("Condition 1 of")


def test_launch_session_skips_participant_tutorial_when_disabled(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    multi_condition_project.settings.fixation_task.enabled = True
    multi_condition_project.settings.fixation_task.accuracy_task_enabled = True
    multi_condition_project.settings.fixation_task.participant_tutorial_enabled = False
    captures: dict[str, object] = {}
    register_engine("stub-no-tutorial", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
            random_seed=99,
        )

        launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-no-tutorial", test_mode=True),
        )
    finally:
        unregister_engine("stub-no-tutorial")

    assert captures.get("tutorial_attempts") is None
    assert captures["transitions"][0]["heading"].startswith("Condition 1 of")


def test_launch_session_tutorial_miss_resets_success_count_before_condition_start(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    multi_condition_project.settings.fixation_task.enabled = True
    multi_condition_project.settings.fixation_task.accuracy_task_enabled = True
    multi_condition_project.settings.fixation_task.participant_tutorial_enabled = True
    captures: dict[str, object] = {
        "tutorial_attempt_results": [
            FixationTutorialAttemptResult(hit=True, reaction_time_s=0.30),
            FixationTutorialAttemptResult(hit=False),
            FixationTutorialAttemptResult(hit=True, reaction_time_s=0.28),
            FixationTutorialAttemptResult(hit=True, reaction_time_s=0.26),
            FixationTutorialAttemptResult(hit=True, reaction_time_s=0.24),
        ]
    }
    register_engine("stub-tutorial-miss", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
            random_seed=99,
        )

        launch_session(
            multi_condition_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-tutorial-miss", test_mode=True),
        )
    finally:
        unregister_engine("stub-tutorial-miss")

    transitions = captures["transitions"]
    correction = [
        transition
        for transition in transitions
        if transition["heading"].startswith("Please press the response key")
    ]
    assert len(correction) == 1
    assert correction[0]["countdown_seconds"] == 5.0
    final_screen = next(
        transition for transition in transitions if transition["heading"] == "Tutorial complete."
    )
    assert "Your tutorial accuracy was 80% (4/5)." in final_screen["body"]
    assert transitions[-session_plan.total_runs]["heading"].startswith("Condition 1 of")


def test_launch_session_aborts_before_playback_when_tutorial_attempt_aborts(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    multi_condition_project.settings.fixation_task.enabled = True
    multi_condition_project.settings.fixation_task.accuracy_task_enabled = True
    multi_condition_project.settings.fixation_task.participant_tutorial_enabled = True
    captures: dict[str, object] = {
        "tutorial_attempt_results": [FixationTutorialAttemptResult(hit=False, aborted=True)]
    }
    register_engine("stub-tutorial-abort", lambda: StubEngine(captures))
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
            launch_settings=LaunchSettings(engine_name="stub-tutorial-abort", test_mode=True),
        )
    finally:
        unregister_engine("stub-tutorial-abort")

    assert summary.aborted is True
    assert summary.abort_reason == "Session aborted during the participant tutorial."
    assert captures.get("run_ids") is None




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




def test_session_launch_ignores_legacy_fixed_break_transition_path(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    captures: dict[str, object] = {}
    multi_condition_project.settings.session.inter_condition_mode = InterConditionMode.FIXED_BREAK
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

    assert all(item["countdown_seconds"] is None for item in captures["transitions"])
    assert all(item["continue_key"] == "space" for item in captures["transitions"])
    assert all(
        item["continue_prompt"] == "Press Space to begin." for item in captures["transitions"]
    )




def test_session_launch_forces_space_transition_key(
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
    assert all(item["continue_key"] == "space" for item in captures["transitions"])
    assert all(
        item["continue_prompt"] == "Press Space to begin." for item in captures["transitions"]
    )


def test_single_run_launch_aborts_before_playback_when_start_screen_is_cancelled(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {"abort_on_transition": True}
    register_engine("stub-start-abort", lambda: StubEngine(captures))
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
            launch_settings=LaunchSettings(engine_name="stub-start-abort", test_mode=True),
        )
    finally:
        unregister_engine("stub-start-abort")

    assert summary.aborted is True
    assert summary.abort_reason == "Run aborted during the start screen."
    assert summary.completed_frames == 0
    assert "run_ids" not in captures
    assert (sample_project_root / "runs" / "faces-run" / "run_summary.json").is_file()




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


def test_session_launch_blocks_when_detected_resolution_differs_from_project_settings(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {"current_display_size_px": (3440, 1440)}
    register_engine("stub-resolution-mismatch", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            random_seed=23,
        )
        session_plan.blocks[0].entries[0].run_spec.display.screen_width_px = 1920
        session_plan.blocks[0].entries[0].run_spec.display.screen_height_px = 1080
        session_plan.blocks[0].entries[0].run_spec.display.use_current_screen_resolution = False

        with pytest.raises(PreflightError, match="3440x1440 resolution"):
            launch_session(
                sample_project_root,
                session_plan,
                participant_number=PARTICIPANT_NUMBER,
                launch_settings=LaunchSettings(
                    engine_name="stub-resolution-mismatch",
                    test_mode=True,
                ),
            )
    finally:
        unregister_engine("stub-resolution-mismatch")

    assert captures["open_count"] == 1
    assert captures["close_count"] == 1
    assert "run_ids" not in captures


def test_launch_run_checks_serial_port_before_engine_session(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    class _UnavailableSerialBackend(TriggerBackend):
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        def connect(self) -> None:
            raise RuntimeError("port unavailable")

        def send_trigger(self, code: int, **_kwargs: object) -> None:
            return None

        def reset(self) -> None:
            return None

        def close(self) -> None:
            return None

    captures: dict[str, object] = {}
    monkeypatch.setattr("fpvs_studio.runtime.triggers.SerialBackend", _UnavailableSerialBackend)
    register_engine("stub-serial-preflight", lambda: StubEngine(captures))
    try:
        run_spec = compile_run_spec(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            run_id="faces-run",
        )

        with pytest.raises(PreflightError, match="Trigger preflight failed before launch"):
            launch_run(
                sample_project_root,
                run_spec,
                participant_number=PARTICIPANT_NUMBER,
                launch_settings=LaunchSettings(
                    engine_name="stub-serial-preflight",
                    test_mode=True,
                    serial_enabled=True,
                    serial_port="COM9",
                ),
            )
    finally:
        unregister_engine("stub-serial-preflight")

    assert "open_count" not in captures
    assert "run_ids" not in captures


def test_launch_run_exports_aborted_summary_when_serial_write_fails(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    class _FailingWriteSerialBackend(TriggerBackend):
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        def connect(self) -> None:
            return None

        def send_trigger(self, code: int, **_kwargs: object) -> None:
            raise RuntimeError("write failed")

        def reset(self) -> None:
            return None

        def close(self) -> None:
            return None

    captures: dict[str, object] = {}
    monkeypatch.setattr("fpvs_studio.runtime.triggers.SerialBackend", _FailingWriteSerialBackend)
    register_engine("stub-serial-write-failure", lambda: StubEngine(captures))
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
                engine_name="stub-serial-write-failure",
                test_mode=True,
                serial_enabled=True,
                serial_port="COM3",
            ),
        )
    finally:
        unregister_engine("stub-serial-write-failure")

    assert summary.aborted is True
    assert summary.abort_reason == "Trigger output failed during condition playback: write failed"
    assert summary.trigger_log[0].status == "error"
    assert summary.trigger_log[0].message == "write failed"
    assert (sample_project_root / "runs" / "faces-run" / "run_summary.json").is_file()
    exported_trigger_rows = _read_csv_rows(
        sample_project_root / "runs" / "faces-run" / "trigger_log.csv"
    )
    assert exported_trigger_rows[0]["status"] == "error"
    assert exported_trigger_rows[0]["message"] == "write failed"


def test_session_launch_allows_detected_resolution_when_project_uses_current_screen(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {"current_display_size_px": (3440, 1440)}
    register_engine("stub-current-resolution", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            random_seed=24,
        )
        for entry in session_plan.ordered_entries():
            entry.run_spec.display.screen_width_px = 1920
            entry.run_spec.display.screen_height_px = 1080
            entry.run_spec.display.use_current_screen_resolution = True

        summary = launch_session(
            sample_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(engine_name="stub-current-resolution", test_mode=True),
        )
    finally:
        unregister_engine("stub-current-resolution")

    assert captures["run_ids"] == [entry.run_id for entry in session_plan.ordered_entries()]
    assert summary.aborted is False


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


