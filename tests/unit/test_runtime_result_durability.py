"""Fault-injection coverage for completed results and retry-safe report commits."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest
from tests.unit.runtime_launcher_helpers import StubEngine, _read_csv_rows

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.serialization import read_json_file
from fpvs_studio.core.task_models import TaskPhase, TaskResponseRecord
from fpvs_studio.runtime import session_export
from fpvs_studio.runtime.run_worker import RuntimeWorker


@pytest.fixture
def execution(multi_condition_project, multi_condition_project_root):
    plan = compile_session_plan(
        multi_condition_project, project_root=multi_condition_project_root,
        refresh_hz=60.0, random_seed=77,
    )
    return multi_condition_project_root, plan


def _execute(root, plan, worker):
    return worker.execute_session(
        root, plan, root / "unused", participant_number="0007", participant_session_number=1,
        runtime_options={
            "export_mode": "compact", "serial_enabled": False, "experiment_test_mode": True,
        },
    )


@pytest.mark.parametrize("failure", ["feedback", "next_condition", "cleanup", "feedback_cleanup"])
def test_compact_completed_results_survive_later_failure(execution, monkeypatch, failure):
    root, plan = execution
    engine = StubEngine({})
    worker = RuntimeWorker(engine)
    original = RuntimeError(failure)
    if failure.startswith("feedback"):
        monkeypatch.setattr(worker, "_show_condition_feedback", Mock(side_effect=original))
    if failure == "next_condition":
        run = engine.run_condition
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise original
            return run(*args, **kwargs)

        monkeypatch.setattr(engine, "run_condition", fail_second)
    if "cleanup" in failure:
        monkeypatch.setattr(
            engine, "close_session",
            Mock(side_effect=original if failure == "cleanup" else ValueError("cleanup")),
        )
    with pytest.raises(RuntimeError) as caught:
        _execute(root, plan, worker)
    assert caught.value is original
    paths = list((root / "logs" / session_export.TASK_CHECKPOINT_DIRNAME).glob("*.session.json"))
    assert len(paths) == 1
    checkpoint = read_json_file(paths[0], SessionExecutionSummary)
    assert checkpoint.aborted
    assert checkpoint.completed_condition_count >= 1
    assert checkpoint.run_results[0].completed_frames > 0
    assert "Session interrupted" in checkpoint.abort_reason
    assert not (root / "runs").exists()
    rows = _read_csv_rows(root / "logs" / session_export.SESSION_CONDITION_HISTORY_FILENAME)
    assert rows[0]["session_aborted"] == "True"


def test_report_failure_retains_checkpoint_and_retry_does_not_duplicate(execution, monkeypatch):
    root, plan = execution
    original_writer = session_export._write_participant_summary_xlsx
    monkeypatch.setattr(
        session_export, "_write_participant_summary_xlsx",
        Mock(side_effect=PermissionError("workbook open")),
    )
    with pytest.raises(PermissionError, match="workbook open"):
        _execute(root, plan, RuntimeWorker(StubEngine({})))
    checkpoint_path = next(
        (root / "logs" / session_export.TASK_CHECKPOINT_DIRNAME).glob("*.session.json")
    )
    summary = read_json_file(checkpoint_path, SessionExecutionSummary)
    assert not summary.aborted
    assert summary.completed_condition_count == plan.total_runs
    monkeypatch.setattr(session_export, "_write_participant_summary_xlsx", original_writer)
    session_export.append_session_condition_history(root, plan, summary)
    session_export.append_session_condition_history(root, plan, summary)
    rows = _read_csv_rows(root / "logs" / session_export.SESSION_CONDITION_HISTORY_FILENAME)
    assert len(rows) == plan.total_runs


def test_concurrent_history_retries_keep_separate_visits(execution):
    root, plan = execution
    summary = _execute(root, plan, RuntimeWorker(StubEngine({})))
    second = summary.model_copy(update={"participant_session_number": 2})
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(
            lambda result: session_export.append_session_condition_history(
                root, plan, result, refresh_reports=False,
            ),
            [summary, second, summary, second],
        ))
    rows = _read_csv_rows(root / "logs" / session_export.SESSION_CONDITION_HISTORY_FILENAME)
    assert len(rows) == plan.total_runs * 2
    assert {row["participant_session_number"] for row in rows} == {"1", "2"}
    assert not list((root / "logs" / session_export.TASK_CHECKPOINT_DIRNAME).glob("*.session.json"))


def test_task_response_commit_is_retry_safe_and_preserves_visits(execution):
    root, plan = execution
    summary = _execute(root, plan, RuntimeWorker(StubEngine({})))
    run = summary.run_results[0]
    response = TaskResponseRecord(
        response_index=0, task_id="test", step_id="answer", phase=TaskPhase.POST_CONDITION,
        condition_id=run.condition_id, run_id=run.run_id, block_index=0, global_order_index=0,
        repetition_index=0, text_value="raw answer",
    )
    run.task_responses.append(response)
    for visit in [1, 1, 2, 2]:
        session_export.append_compact_task_responses(
            root, plan, summary.model_copy(update={"participant_session_number": visit}),
        )
    rows = _read_csv_rows(root / "logs" / session_export.TASK_RESPONSES_FILENAME)
    assert len(rows) == 2
    assert {row["participant_session_number"] for row in rows} == {"1", "2"}


def test_complete_history_does_not_load_legacy_plan(tmp_path, monkeypatch):
    lookup = Mock(side_effect=AssertionError("unnecessary historical plan read"))
    monkeypatch.setattr(session_export, "_session_plan_run_seed_lookup", lookup)
    assert session_export._image_display_order_seed_text(
        tmp_path, [{"run_id": "r1", "run_seed": "77", "output_dir": "runs/old"}],
    ) == "r1=77"
    lookup.assert_not_called()


def test_incomplete_history_loads_one_legacy_plan(tmp_path, monkeypatch):
    lookup = Mock(return_value={"r1": "11", "r2": "22", "r3": "33"})
    monkeypatch.setattr(session_export, "_session_plan_run_seed_lookup", lookup)
    assert session_export._image_display_order_seed_text(tmp_path, [
        {"run_id": "r1", "run_seed": "77", "output_dir": "runs/old"},
        {"run_id": "r2", "run_seed": ""}, {"run_id": "r3"},
    ]) == "r1=77; r2=22; r3=33"
    lookup.assert_called_once_with(tmp_path, "runs/old")


def test_atomic_workbook_failure_preserves_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "summary.xlsx"
    session_export._write_participant_summary_xlsx(path, [])
    original = path.read_bytes()
    monkeypatch.setattr(session_export.os, "replace", Mock(side_effect=PermissionError("locked")))
    with pytest.raises(PermissionError, match="locked"):
        session_export._write_participant_summary_xlsx(path, [])
    assert path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [path]


def test_post_task_failure_preserves_completed_stream(execution, monkeypatch):
    from fpvs_studio.runtime import run_worker

    root, plan = execution
    original_runner = run_worker.run_task_modules
    calls = 0

    def fail_post_task(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            run = kwargs["run_spec"]
            kwargs["checkpoint"].append(TaskResponseRecord(
                response_index=0, task_id="test", step_id="partial",
                phase=TaskPhase.POST_CONDITION, condition_id=run.condition.condition_id,
                run_id=run.run_id, block_index=0, global_order_index=0, repetition_index=0,
                text_value="partial private answer",
            ))
            raise ValueError("post task rendering failed")
        return original_runner(*args, **kwargs)

    monkeypatch.setattr(run_worker, "run_task_modules", fail_post_task)
    with pytest.raises(ValueError, match="post task rendering failed"):
        _execute(root, plan, RuntimeWorker(StubEngine({})))
    checkpoint_path = next(
        (root / "logs" / session_export.TASK_CHECKPOINT_DIRNAME).glob("*.session.json")
    )
    summary = read_json_file(checkpoint_path, SessionExecutionSummary)
    assert summary.completed_condition_count == 1
    assert summary.run_results[0].completed_frames > 0
    assert summary.run_results[0].task_flow_aborted
    assert not summary.run_results[0].task_flow_completed
    assert "partial private answer" not in checkpoint_path.read_text(encoding="utf-8")
    journal_path = session_export.compact_task_checkpoint_path(
        root, participant_number="0007", participant_session_number=1, session_id=plan.session_id,
    )
    assert "partial private answer" in journal_path.read_text(encoding="utf-8")


def test_original_presentation_error_survives_finalization_failure(execution, monkeypatch):
    root, plan = execution
    worker = RuntimeWorker(StubEngine({}))
    original = RuntimeError("feedback failed")
    monkeypatch.setattr(worker, "_show_condition_feedback", Mock(side_effect=original))
    monkeypatch.setattr(
        session_export, "_write_participant_summary_xlsx",
        Mock(side_effect=PermissionError("workbook locked")),
    )
    with pytest.raises(RuntimeError) as caught:
        _execute(root, plan, worker)
    assert caught.value is original
    assert isinstance(caught.value.__cause__, PermissionError)


def test_run_checkpoint_excludes_raw_task_answers(execution):
    root, plan = execution
    summary = _execute(root, plan, RuntimeWorker(StubEngine({})))
    run = summary.run_results[0]
    run.task_responses.append(TaskResponseRecord(
        response_index=0, task_id="test", step_id="answer", phase=TaskPhase.POST_CONDITION,
        condition_id=run.condition_id, run_id=run.run_id, block_index=0, global_order_index=0,
        repetition_index=0, text_value="private raw answer",
    ))
    path = session_export.write_compact_run_checkpoint(root, run)
    assert "private raw answer" not in path.read_text(encoding="utf-8")
    assert "task_responses" not in path.read_text(encoding="utf-8")


def test_csv_generator_failure_preserves_previous_export(tmp_path):
    path = tmp_path / "events.csv"
    path.write_bytes(b"previous complete export")

    def interrupted_rows():
        yield [1]
        raise OSError("source failed mid-export")

    with pytest.raises(OSError, match="source failed mid-export"):
        session_export._write_csv(path, ["event"], interrupted_rows())
    assert path.read_bytes() == b"previous complete export"
    assert list(tmp_path.iterdir()) == [path]


def test_numbered_retry_preserves_legacy_rows_and_existing_order(tmp_path):
    path = tmp_path / "history.csv"
    header = ["participant_session_number", "run_id", "value"]
    session_export._write_csv(path, header, [["", "legacy", "original"], ["1", "r1", "old"]])
    for rows in ([[2, "r1", "second"]], [[1, "r1", "corrected"]]):
        session_export._commit_numbered_rows(
            path, header, rows, identity=("participant_session_number", "run_id"),
        )
    assert _read_csv_rows(path) == [
        {"participant_session_number": "", "run_id": "legacy", "value": "original"},
        {"participant_session_number": "1", "run_id": "r1", "value": "corrected"},
        {"participant_session_number": "2", "run_id": "r1", "value": "second"},
    ]
