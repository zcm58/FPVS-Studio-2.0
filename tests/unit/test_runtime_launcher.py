"""Runtime launcher boundary tests."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fpvs_studio.core.compiler import compile_run_spec, compile_session_plan
from fpvs_studio.core.enums import InterConditionMode, RunMode
from fpvs_studio.core.execution import (
    FrameIntervalRecord,
    ResponseRecord,
    RunExecutionSummary,
    RuntimeMetadata,
    SessionExecutionSummary,
)
from fpvs_studio.core.models import DisplayValidationReport
from fpvs_studio.core.serialization import read_json_file
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.engines.base import PresentationEngine
from fpvs_studio.engines.registry import register_engine, unregister_engine
from fpvs_studio.runtime.launcher import (
    LaunchSettings,
    LaunchSettingsError,
    launch_run,
    launch_session,
)
from fpvs_studio.runtime.preflight import PreflightError
from fpvs_studio.triggers.base import TriggerBackend


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class StubEngine(PresentationEngine):
    """Engine stub used to exercise the runtime launcher boundary."""

    def __init__(self, captures: dict[str, object]) -> None:
        self._captures = captures

    @property
    def engine_id(self) -> str:
        return "stub"

    def probe_displays(self) -> list[dict[str, object]]:
        return []

    def open_session(
        self,
        *,
        runtime_options: Mapping[str, object] | None = None,
    ) -> None:
        self._captures["open_count"] = int(self._captures.get("open_count", 0)) + 1
        self._captures["runtime_options"] = dict(runtime_options or {})

    def show_transition_screen(
        self,
        *,
        heading: str,
        body: str | None = None,
        countdown_seconds: float | None = None,
        continue_key: str | None = None,
    ) -> bool:
        self._captures.setdefault("transitions", []).append(
            {
                "heading": heading,
                "body": body,
                "countdown_seconds": countdown_seconds,
                "continue_key": continue_key,
            }
        )
        return False

    def run_condition(
        self,
        run_spec: RunSpec,
        project_root: Path,
        *,
        runtime_options: Mapping[str, object] | None = None,
        trigger_backend: TriggerBackend | None = None,
    ) -> RunExecutionSummary:
        self._captures.setdefault("run_ids", []).append(run_spec.run_id)
        self._captures.setdefault("project_roots", []).append(project_root)
        self._captures.setdefault("condition_instructions", []).append(
            run_spec.condition.instructions_text
        )

        if trigger_backend is not None:
            for trigger_event in run_spec.trigger_events:
                trigger_backend.send_trigger(
                    trigger_event.code,
                    frame_index=trigger_event.frame_index,
                    label=trigger_event.label,
                    time_s=0.0,
                )

        response_log = []
        if run_spec.fixation_events:
            first_event = run_spec.fixation_events[0]
            response_log.append(
                ResponseRecord(
                    response_index=0,
                    key=run_spec.fixation.response_keys[0],
                    frame_index=first_event.start_frame,
                    time_s=0.25,
                )
            )

        return RunExecutionSummary(
            project_id=run_spec.project_id,
            session_id=None,
            run_id=run_spec.run_id,
            condition_id=run_spec.condition.condition_id,
            condition_name=run_spec.condition.name,
            engine_name="stub",
            run_mode=(
                RunMode.TEST
                if bool((runtime_options or {}).get("test_mode"))
                else RunMode.SESSION
            ),
            started_at=datetime(2026, 3, 7, 12, 0, 0, tzinfo=UTC),
            finished_at=datetime(2026, 3, 7, 12, 0, 5, tzinfo=UTC),
            completed_frames=run_spec.display.total_frames,
            aborted=False,
            runtime_metadata=RuntimeMetadata(
                engine_name="stub",
                requested_refresh_hz=run_spec.display.refresh_hz,
                actual_refresh_hz=run_spec.display.refresh_hz,
                frame_interval_recording=True,
                test_mode=bool((runtime_options or {}).get("test_mode")),
            ),
            frame_intervals=[
                FrameIntervalRecord(
                    frame_index=0,
                    interval_s=1.0 / run_spec.display.refresh_hz,
                )
            ],
            response_log=response_log,
        )

    def show_completion_screen(
        self,
        *,
        completed_condition_count: int,
        total_condition_count: int,
        was_aborted: bool,
    ) -> bool:
        self._captures.setdefault("completion_screens", []).append(
            {
                "completed_condition_count": completed_condition_count,
                "total_condition_count": total_condition_count,
                "was_aborted": was_aborted,
            }
        )
        return False

    def close_session(self) -> None:
        self._captures["close_count"] = int(self._captures.get("close_count", 0)) + 1

    def abort(self) -> None:
        self._captures["abort_called"] = True


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
            launch_settings=LaunchSettings(engine_name="stub", test_mode=True, serial_port="COM9"),
        )
    finally:
        unregister_engine("stub")

    assert captures["open_count"] == 1
    assert captures["close_count"] == 1
    assert captures["run_ids"] == ["faces-run"]
    assert captures["runtime_options"] == {
        "engine_name": "stub",
        "test_mode": True,
        "display_index": None,
        "serial_port": "COM9",
    }
    assert summary.output_dir == "runs/faces-run"
    assert summary.warnings == []
    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.test_mode is True
    assert summary.trigger_log[0].label == "condition_start"
    assert (sample_project_root / "runs" / "faces-run" / "runspec.json").is_file()
    assert (sample_project_root / "runs" / "faces-run" / "run_summary.json").is_file()
    assert (sample_project_root / "runs" / "faces-run" / "runtime_metadata.json").is_file()
    assert (sample_project_root / "runs" / "faces-run" / "fixation_events.csv").is_file()
    assert (sample_project_root / "runs" / "faces-run" / "trigger_log.csv").is_file()

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
            launch_settings=LaunchSettings(engine_name="stub-session", test_mode=True),
        )
    finally:
        unregister_engine("stub-session")

    assert captures["open_count"] == 1
    assert captures["close_count"] == 1
    assert captures["run_ids"] == [
        entry.run_id for entry in session_plan.ordered_entries()
    ]
    assert len(captures["transitions"]) == session_plan.total_runs
    assert captures["completion_screens"] == [
        {
            "completed_condition_count": session_plan.total_runs,
            "total_condition_count": session_plan.total_runs,
            "was_aborted": False,
        }
    ]
    assert summary.completed_condition_count == session_plan.total_runs
    assert summary.output_dir == f"runs/{session_plan.session_id}"
    assert summary.realized_block_orders == [
        block.condition_order for block in session_plan.blocks
    ]
    assert (
        multi_condition_project_root / "runs" / session_plan.session_id / "session_plan.json"
    ).is_file()
    assert (
        multi_condition_project_root / "runs" / session_plan.session_id / "session_summary.json"
    ).is_file()
    assert (
        multi_condition_project_root / "runs" / session_plan.session_id / "runtime_metadata.json"
    ).is_file()
    first_run_dir = (
        multi_condition_project_root
        / "runs"
        / session_plan.session_id
        / session_plan.ordered_entries()[0].run_id
    )
    assert (first_run_dir / "runspec.json").is_file()
    assert (first_run_dir / "run_summary.json").is_file()


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
            launch_settings=LaunchSettings(engine_name="stub-manual", test_mode=True),
        )
    finally:
        unregister_engine("stub-manual")

    assert all(item["countdown_seconds"] is None for item in captures["transitions"])
    assert all(item["continue_key"] == "return" for item in captures["transitions"])


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
            launch_settings=LaunchSettings(engine_name="stub-instructions", test_mode=True),
        )
    finally:
        unregister_engine("stub-instructions")

    bodies = [item["body"] for item in captures["transitions"]]
    assert all("Instructions for condition" in body for body in bodies)


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

        launch_session(
            multi_condition_project_root,
            session_plan,
            launch_settings=LaunchSettings(engine_name="stub-export", test_mode=True),
        )
    finally:
        unregister_engine("stub-export")

    session_output_dir = multi_condition_project_root / "runs" / session_plan.session_id
    exported_summary = read_json_file(
        session_output_dir / "session_summary.json",
        SessionExecutionSummary,
    )

    assert exported_summary.random_seed == 77
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
                launch_settings=LaunchSettings(engine_name="stub-non-test", test_mode=False),
            )
    finally:
        unregister_engine("stub-non-test")

    assert captures == {}


def test_launch_session_rejects_invalid_display_index_before_engine_creation(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-invalid-display", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            random_seed=31,
        )

        with pytest.raises(
            LaunchSettingsError,
            match="display_index must be None or a non-negative integer",
        ):
            launch_session(
                sample_project_root,
                session_plan,
                launch_settings=LaunchSettings(
                    engine_name="stub-invalid-display",
                    test_mode=True,
                    display_index=-1,
                ),
            )
    finally:
        unregister_engine("stub-invalid-display")

    assert captures == {}
