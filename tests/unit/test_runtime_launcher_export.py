"""Runtime launcher boundary tests."""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import load_workbook
from tests.unit.runtime_launcher_helpers import (
    PARTICIPANT_NUMBER,
    StubEngine,
    _read_csv_rows,
)

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.execution import ParticipantMetadata, SessionExecutionSummary
from fpvs_studio.core.serialization import read_json_file, write_json_file
from fpvs_studio.engines.registry import register_engine, unregister_engine
from fpvs_studio.runtime.launcher import (
    LaunchSettings,
    launch_session,
)
from fpvs_studio.runtime.session_export import (
    SESSION_CONDITION_HISTORY_HEADER,
    write_participant_summary,
)


def test_session_export_captures_seed_and_runtime_logs(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    multi_condition_project.settings.fixation_task.accuracy_task_enabled = True
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
            participant_metadata=ParticipantMetadata(
                age=72,
                sex="Female",
                handedness="Right handed",
            ),
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
    assert exported_summary.participant_metadata == ParticipantMetadata(
        age=72,
        sex="Female",
        handedness="Right handed",
    )
    assert exported_summary.realized_block_orders == [
        block.condition_order for block in session_plan.blocks
    ]
    assert (session_output_dir / "frame_intervals.csv").is_file()
    assert (session_output_dir / "fixation_events.csv").is_file()
    assert (session_output_dir / "responses.csv").is_file()
    assert (session_output_dir / "trigger_log.csv").is_file()
    assert (multi_condition_project_root / "logs" / "session_condition_history.csv").is_file()
    assert (multi_condition_project_root / "logs" / "participant_summary.csv").is_file()
    assert (multi_condition_project_root / "logs" / "participant_summary.xlsx").is_file()
    assert [run_result.run_id for run_result in exported_summary.run_results] == [
        entry.run_id for entry in session_plan.ordered_entries()
    ]
    assert all(
        run_result.participant_number == PARTICIPANT_NUMBER
        for run_result in exported_summary.run_results
    )

    conditions_rows = _read_csv_rows(session_output_dir / "conditions.csv")
    event_rows = _read_csv_rows(session_output_dir / "events.csv")
    fixation_rows = _read_csv_rows(session_output_dir / "fixation_events.csv")
    response_rows = _read_csv_rows(session_output_dir / "responses.csv")
    trigger_rows = _read_csv_rows(session_output_dir / "trigger_log.csv")
    participant_metadata_rows = _read_csv_rows(session_output_dir / "participant_metadata.csv")
    condition_history_rows = _read_csv_rows(
        multi_condition_project_root / "logs" / "session_condition_history.csv"
    )
    participant_summary_rows = _read_csv_rows(
        multi_condition_project_root / "logs" / "participant_summary.csv"
    )

    assert [row["run_id"] for row in conditions_rows] == [
        entry.run_id for entry in session_plan.ordered_entries()
    ]
    assert [row["run_id"] for row in condition_history_rows] == [
        entry.run_id for entry in session_plan.ordered_entries()
    ]
    assert [row["run_seed"] for row in condition_history_rows] == [
        str(entry.run_spec.random_seed) for entry in session_plan.ordered_entries()
    ]
    assert event_rows
    assert {
        "stimulus_modality",
        "stimulus_id",
        "stimulus_value",
        "image_path",
        "text",
    }.issubset(event_rows[0])
    assert event_rows[0]["stimulus_modality"] == "image"
    assert event_rows[0]["stimulus_value"] == event_rows[0]["image_path"]
    assert event_rows[0]["text"] == ""
    assert all(row["participant_number"] == PARTICIPANT_NUMBER for row in condition_history_rows)
    assert participant_metadata_rows == [
        {
            "participant_number": PARTICIPANT_NUMBER,
            "participant_age": "72",
            "participant_sex": "Female",
            "participant_handedness": "Right handed",
        }
    ]
    assert all(row["participant_age"] == "72" for row in condition_history_rows)
    assert all(row["participant_sex"] == "Female" for row in condition_history_rows)
    assert all(
        row["participant_handedness"] == "Right handed"
        for row in condition_history_rows
    )
    assert all(row["session_seed"] == "77" for row in condition_history_rows)
    assert all(row["output_dir"] == summary.output_dir for row in condition_history_rows)
    assert all(row["block_accuracy_percent"] for row in condition_history_rows)
    fixation_summaries = [
        run_result.fixation_task_summary for run_result in exported_summary.run_results
    ]
    assert all(fixation_summary is not None for fixation_summary in fixation_summaries)
    total_targets = sum(
        fixation_summary.total_targets
        for fixation_summary in fixation_summaries
        if fixation_summary is not None
    )
    hit_count = sum(
        fixation_summary.hit_count
        for fixation_summary in fixation_summaries
        if fixation_summary is not None
    )
    false_alarm_count = sum(
        fixation_summary.false_alarm_count
        for fixation_summary in fixation_summaries
        if fixation_summary is not None
    )
    weighted_rt_ms = (
        sum(
            fixation_summary.mean_rt_ms * fixation_summary.hit_count
            for fixation_summary in fixation_summaries
            if fixation_summary is not None and fixation_summary.mean_rt_ms is not None
        )
        / hit_count
    )
    participant_summary_row = participant_summary_rows[0]
    assert participant_summary_rows == [participant_summary_row]
    assert participant_summary_row["PID"] == PARTICIPANT_NUMBER
    assert participant_summary_row["Age"] == "72"
    assert participant_summary_row["Sex"] == "Female"
    assert participant_summary_row["Handedness"] == "Right handed"
    assert participant_summary_row["Session ID"] == session_plan.session_id
    assert participant_summary_row["Condition Display Order Seed"] == "77"
    assert participant_summary_row["Image Display Order Seeds"] == "; ".join(
        f"{entry.run_id}={entry.run_spec.random_seed}"
        for entry in session_plan.ordered_entries()
    )
    assert participant_summary_row["Total Targets"] == str(total_targets)
    assert participant_summary_row["Hits"] == str(hit_count)
    assert participant_summary_row["False Alarms"] == str(false_alarm_count)
    assert participant_summary_row["Aborted Y/N"] == "N"
    assert participant_summary_row["Include In Analysis"] == "Y"
    assert participant_summary_row["Mean Accuracy Across All Conditions (%)"] == (
        f"{(hit_count / total_targets) * 100.0:.2f}"
    )
    assert participant_summary_row[
        "Mean Reaction Time Across All Conditions (ms)"
    ] == f"{weighted_rt_ms:.2f}"
    assert len(fixation_rows) == sum(
        len(run_result.fixation_responses) for run_result in exported_summary.run_results
    )
    assert len(response_rows) == sum(
        len(run_result.response_log) for run_result in exported_summary.run_results
    )
    assert len(trigger_rows) == sum(
        len(run_result.trigger_log) for run_result in exported_summary.run_results
    )

    workbook = load_workbook(multi_condition_project_root / "logs" / "participant_summary.xlsx")
    worksheet = workbook["Participant Summary"]
    assert worksheet.freeze_panes == "A2"
    assert worksheet.auto_filter.ref == worksheet.dimensions
    workbook_header = [cell.value for cell in worksheet[1]]
    assert workbook_header == list(participant_summary_row)
    workbook_values = [cell.value for cell in worksheet[2]]
    assert workbook_values[0] == PARTICIPANT_NUMBER
    assert workbook_values[7] == total_targets
    assert workbook_values[8] == hit_count
    assert workbook_values[9] == false_alarm_count
    assert workbook_values[10] == "N"
    assert workbook_values[11] == "Y"
    assert workbook_values[12] == float(participant_summary_row[
        "Mean Accuracy Across All Conditions (%)"
    ])
    assert workbook_values[13] == float(participant_summary_row[
        "Mean Reaction Time Across All Conditions (ms)"
    ])
    for row in worksheet.iter_rows():
        for cell in row:
            assert cell.alignment.horizontal == "center"
            assert cell.alignment.vertical == "center"
    for column_index in range(1, worksheet.max_column + 1):
        letter = worksheet.cell(row=1, column=column_index).column_letter
        expected_width = min(
            max(
                len(str(worksheet.cell(row=row_index, column=column_index).value))
                for row_index in range(1, worksheet.max_row + 1)
                if worksheet.cell(row=row_index, column=column_index).value is not None
            )
            + 2,
            255,
        )
        assert worksheet.column_dimensions[letter].width == expected_width


def test_participant_summary_backfills_run_seeds_from_session_plan_for_legacy_history(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    session_plan = compile_session_plan(
        multi_condition_project,
        refresh_hz=60.0,
        project_root=multi_condition_project_root,
        random_seed=77,
    )
    output_dir = "runs/0040"
    write_json_file(multi_condition_project_root / output_dir / "session_plan.json", session_plan)
    history_path = multi_condition_project_root / "logs" / "session_condition_history.csv"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SESSION_CONDITION_HISTORY_HEADER)
        writer.writeheader()
        for entry in session_plan.ordered_entries():
            writer.writerow(
                {
                    "participant_number": "0040",
                    "participant_age": "15",
                    "participant_sex": "Female",
                    "participant_handedness": "Right handed",
                    "session_id": session_plan.session_id,
                    "session_seed": "77",
                    "session_aborted": "False",
                    "output_dir": output_dir,
                    "global_order_index": str(entry.global_order_index + 1),
                    "run_id": entry.run_id,
                    "run_seed": "",
                    "total_targets": "10",
                    "hit_count": "9",
                    "false_alarm_count": "1",
                    "mean_rt_ms": "200.00",
                    "run_aborted": "False",
                }
            )

    summary_path = write_participant_summary(multi_condition_project_root)
    participant_summary_rows = _read_csv_rows(summary_path)

    assert participant_summary_rows[0]["PID"] == "0040"
    assert participant_summary_rows[0]["Condition Display Order Seed"] == "77"
    assert participant_summary_rows[0]["Image Display Order Seeds"] == "; ".join(
        f"{entry.run_id}={entry.run_spec.random_seed}"
        for entry in session_plan.ordered_entries()
    )
    assert participant_summary_rows[0]["Total Targets"] == str(session_plan.total_runs * 10)
    assert participant_summary_rows[0]["Hits"] == str(session_plan.total_runs * 9)
    assert participant_summary_rows[0]["False Alarms"] == str(session_plan.total_runs)
    assert participant_summary_rows[0]["Aborted Y/N"] == "N"
    assert participant_summary_rows[0]["Include In Analysis"] == "Y"
    assert participant_summary_rows[0]["Mean Accuracy Across All Conditions (%)"] == "90.00"
    assert participant_summary_rows[0]["Mean Reaction Time Across All Conditions (ms)"] == "200.00"
    workbook = load_workbook(summary_path.with_suffix(".xlsx"))
    worksheet = workbook["Participant Summary"]
    assert worksheet["A2"].value == "0040"
    assert worksheet["K2"].value == "N"
    assert worksheet["L2"].value == "Y"


