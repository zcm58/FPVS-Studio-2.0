"""Reporting boundaries: completion proof, research commits, crashes and local-only runs."""

from unittest.mock import Mock

import pytest
from tests.unit.runtime_launcher_helpers import StubEngine
from tests.unit.test_data_sharing_storage import enable

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.data_sharing.storage import list_records
from fpvs_studio.runtime import data_sharing, run_worker
from fpvs_studio.runtime.run_worker import RuntimeWorker
from fpvs_studio.runtime.triggers import LoggedNullBackend


@pytest.fixture
def execution(multi_condition_project, multi_condition_project_root, monkeypatch):
    root = multi_condition_project_root
    multi_condition_project.settings.fixation_task.accuracy_task_enabled = True
    plan = compile_session_plan(multi_condition_project, project_root=root, refresh_hz=60.0)
    enable(root)
    monkeypatch.setattr(
        run_worker,
        "_build_and_connect_trigger_backend",
        lambda options: (LoggedNullBackend(), ()),
    )
    return root, plan


def execute(execution, *, flags=None, participant="0007", captures=None):
    root, plan = execution
    return RuntimeWorker(StubEngine(captures or {})).execute_session(
        root,
        plan,
        root / "unused",
        participant_number=participant,
        participant_session_number=1,
        runtime_options={
            "export_mode": "compact",
            "sharing_protocol_sha256": "a" * 64,
            **(flags or {}),
        },
    )


def test_reports_only_completed_occurrences_and_keeps_private_fields_local(execution):
    root, plan = execution
    execute(execution)
    records = list_records(root)
    assert len(records) == 1
    report = data_sharing.SessionReport.model_validate_json(records[0].payload_json)
    assert len(report.occurrences) == plan.total_runs
    assert [item.occurrence_index for item in report.occurrences] == list(
        range(1, plan.total_runs + 1)
    )
    assert "participant_number" not in records[0].payload_json
    assert "0007" not in records[0].payload_json
    assert "project_id" not in records[0].payload_json
    assert not data_sharing.capture_errors(root)


@pytest.mark.parametrize(
    "flags,participant",
    [
        ({"experiment_test_mode": True}, "0007"),
        ({"pilot_mode": True}, "0007"),
        ({}, "0"),
        ({}, "00"),
        ({"sharing_protocol_sha256": "b" * 64}, "0007"),
    ],
)
def test_test_pilot_test_participants_and_protocol_edits_stay_local(execution, flags, participant):
    execute(execution, flags=flags, participant=participant)
    assert not list_records(execution[0])


def test_final_completion_screen_abort_cannot_queue(execution, monkeypatch):
    root, _ = execution
    monkeypatch.setattr(StubEngine, "show_completion_screen", Mock(return_value=True))
    summary = execute(execution)
    assert summary.aborted
    assert not list_records(root)


def test_derived_workbook_failure_keeps_completed_report(execution, monkeypatch):
    root, _ = execution
    monkeypatch.setattr(
        run_worker, "write_participant_summary", Mock(side_effect=PermissionError("xlsx"))
    )
    with pytest.raises(PermissionError, match="xlsx"):
        execute(execution)
    assert len(list_records(root)) == 1


def test_research_commit_failure_never_queues_or_recovers_from_rows_alone(execution, monkeypatch):
    root, _ = execution
    monkeypatch.setattr(
        run_worker, "append_compact_task_responses", Mock(side_effect=PermissionError("research"))
    )
    with pytest.raises(PermissionError, match="research"):
        execute(execution)
    assert not list_records(root)
    assert data_sharing.recover_captures(root)
    assert not list_records(root)


def test_queue_failure_recovers_same_uuid_without_duplicate(execution, monkeypatch):
    root, _ = execution
    original = data_sharing.queue_report
    monkeypatch.setattr(data_sharing, "queue_report", Mock(side_effect=PermissionError("queue")))
    summary = execute(execution)
    assert not summary.aborted
    assert not list_records(root)
    assert data_sharing.capture_errors(root)
    intent_path = next((root / "logs/data-sharing/intents").glob("*.json"))
    report_id = intent_path.stem
    monkeypatch.setattr(data_sharing, "queue_report", original)
    assert not data_sharing.recover_captures(root)
    data_sharing.recover_captures(root)
    assert [record.report_id for record in list_records(root)] == [report_id]


def test_initial_and_terminal_intent_write_failures_do_not_lose_local_results(
    execution, monkeypatch
):
    root, _ = execution
    monkeypatch.setattr(data_sharing, "_save_intent", Mock(side_effect=PermissionError("intent")))
    summary = execute(execution)
    assert not summary.aborted
    assert (root / "logs/session_condition_history.csv").exists()
    assert not list_records(root)
    assert any("capture could not be initialized" in item for item in summary.warnings)


def test_intent_exists_before_presentation_and_terminal_before_research(execution, monkeypatch):
    root, _ = execution
    original_open = StubEngine.open_session
    original_history = run_worker.append_session_condition_history

    def open_session(engine, **kwargs):
        path = next((root / "logs/data-sharing/intents").glob("*.json"))
        assert data_sharing.CaptureIntent.model_validate_json(path.read_bytes()).state == "running"
        return original_open(engine, **kwargs)

    def history(*args, **kwargs):
        path = next((root / "logs/data-sharing/intents").glob("*.json"))
        intent = data_sharing.CaptureIntent.model_validate_json(path.read_bytes())
        assert intent.state == "eligible"
        assert not intent.research_committed
        return original_history(*args, **kwargs)

    monkeypatch.setattr(StubEngine, "open_session", open_session)
    monkeypatch.setattr(run_worker, "append_session_condition_history", history)
    execute(execution)


def test_terminal_intent_failure_cannot_queue_but_research_still_commits(execution, monkeypatch):
    root, _ = execution
    original = data_sharing._save_intent

    def fail_terminal(root, intent):
        if intent.state != "running":
            raise PermissionError("terminal")
        original(root, intent)

    monkeypatch.setattr(data_sharing, "_save_intent", fail_terminal)
    summary = execute(execution)
    assert not summary.aborted
    assert not list_records(root)
    assert (root / "logs/session_condition_history.csv").exists()
    assert data_sharing.recover_captures(root)


def test_post_task_failure_never_queues_completed_stream(execution, monkeypatch):
    original = run_worker.run_task_modules
    calls = 0

    def fail_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("post task failed")
        return original(*args, **kwargs)

    monkeypatch.setattr(run_worker, "run_task_modules", fail_post)
    with pytest.raises(ValueError, match="post task failed"):
        execute(execution)
    assert not list_records(execution[0])


def test_same_compiled_plan_generates_separate_execution_uuids(execution):
    root, _ = execution
    execute(execution)
    execute(execution, participant="0008")
    records = list_records(root)
    assert len(records) == 2
    assert records[0].report_id != records[1].report_id
