"""Reporting boundaries: completion proof, research commits, crashes and local-only runs."""

from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from tests.unit.runtime_launcher_helpers import StubEngine
from tests.unit.test_data_sharing_storage import enable

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.library_origin import LibraryProjectOrigin, save_library_origin
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
    ],
)
def test_test_pilot_and_test_participants_do_not_create_captures(execution, flags, participant):
    execute(execution, flags=flags, participant=participant)
    assert not list_records(execution[0])
    assert not tuple((execution[0] / "logs/data-sharing/intents").glob("*.json"))


def test_protocol_edits_stay_local_and_retain_review_evidence(execution):
    execute(execution, flags={"sharing_protocol_sha256": "b" * 64})
    root, _ = execution
    assert not list_records(root)
    intent_path = next((root / "logs/data-sharing/intents").glob("*.json"))
    intent = data_sharing.CaptureIntent.model_validate_json(intent_path.read_bytes())
    assert intent.state == "ineligible" and intent.reason == "protocol_mismatch"


def test_local_testing_does_not_exhaust_capture_capacity(execution, monkeypatch):
    root, _ = execution
    monkeypatch.setattr(data_sharing, "MAX_RECORDS", 1)
    execute(execution, flags={"experiment_test_mode": True})
    summary = execute(execution, participant="0008")
    assert len(list_records(root)) == 1
    assert not any("capture could not be initialized" in warning for warning in summary.warnings)


def test_local_testing_with_full_capture_history_preserves_existing_capture(
    execution, monkeypatch,
):
    root, _ = execution
    monkeypatch.setattr(data_sharing, "MAX_RECORDS", 1)
    execute(execution)
    intent_path = next((root / "logs/data-sharing/intents").glob("*.json"))
    before = intent_path.read_bytes()
    summary = execute(execution, flags={"pilot_mode": True}, participant="0008")
    assert intent_path.read_bytes() == before
    assert len(tuple((root / "logs/data-sharing/intents").glob("*.json"))) == 1
    assert not any("capture could not be initialized" in warning for warning in summary.warnings)


def test_aborted_capture_capacity_is_actionable_and_review_restores_new_reporting(
    execution, monkeypatch,
):
    from fpvs_studio.data_sharing.service import (
        archive_captures_project,
        load_view,
        review_captures_project,
    )

    root, plan = execution
    monkeypatch.setattr(data_sharing, "MAX_RECORDS", 1)
    capture = data_sharing.SharingCapture.begin(
        root, plan, participant_number="0007", participant_session_number=1,
        runtime_options={"sharing_protocol_sha256": "a" * 64},
    )
    capture.terminal(SimpleNamespace(aborted=True))
    original = next((root / "logs/data-sharing/intents").glob("*.json")).read_bytes()
    view = load_view(root, "a" * 64, Event())
    assert view.settings.enabled and view.status == "failed"
    assert view.capture_count == view.capture_limit == view.reviewable_capture_count == 1
    assert "history is full" in view.error and "Review captures" in view.error
    before_archive = execute(execution, participant="0008")
    assert not before_archive.aborted and not list_records(root)
    assert any("capture could not be initialized" in warning for warning in before_archive.warnings)
    review = review_captures_project(root, "a" * 64, Event()).capture_review
    assert review is not None
    restored = archive_captures_project(root, "a" * 64, Event(), review=review)
    assert restored.capture_count == 0 and restored.reviewable_capture_count == 0
    archived = root / "logs/data-sharing/archive" / capture.intent.report_id / "capture.json"
    assert archived.read_bytes() == original
    after_archive = execute(execution, participant="0009")
    assert not after_archive.aborted and len(list_records(root)) == 1
    assert not any(
        "capture could not be initialized" in warning for warning in after_archive.warnings
    )


@pytest.mark.parametrize(
    "item_id,version", [("study", "2.0"), ("different-study", "1.0"), ("study", None)],
)
def test_library_scope_mismatch_holds_capture_and_preserves_local_results(
    execution, item_id, version, caplog,
):
    root, plan = execution
    save_library_origin(root, LibraryProjectOrigin(
        service_url="https://library.example.invalid", item_id=item_id,
        installed_version=version, local_project_id=plan.project_id,
    ))
    summary = execute(execution)
    assert not summary.aborted
    assert (root / "logs/session_condition_history.csv").exists()
    assert not list_records(root)
    assert not tuple((root / "logs/data-sharing/intents").glob("*.json"))
    assert any("capture could not be initialized" in warning for warning in summary.warnings)
    assert "Library" in caplog.text


def test_matching_library_scope_can_capture(execution):
    root, plan = execution
    save_library_origin(root, LibraryProjectOrigin(
        service_url="https://library.example.invalid", item_id="study",
        installed_version="1.0", local_project_id=plan.project_id,
    ))
    execute(execution)
    assert len(list_records(root)) == 1


def test_local_testing_skips_library_scope_validation(execution):
    root, plan = execution
    save_library_origin(root, LibraryProjectOrigin(
        service_url="https://library.example.invalid", item_id="study",
        installed_version="2.0", local_project_id=plan.project_id,
    ))
    summary = execute(execution, flags={"experiment_test_mode": True})
    assert not summary.aborted
    assert not any("capture could not be initialized" in warning for warning in summary.warnings)
    assert not tuple((root / "logs/data-sharing/intents").glob("*.json"))


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
