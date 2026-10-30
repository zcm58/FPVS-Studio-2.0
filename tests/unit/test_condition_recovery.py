"""Read-only interruption discovery and exact occurrence reruns without presentation."""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from tests.unit.runtime_launcher_helpers import StubEngine

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.enums import StimulusModality
from fpvs_studio.core.execution import RunExecutionSummary
from fpvs_studio.core.paths import filesystem_path
from fpvs_studio.core.scene_models import SceneEvent, SceneStreamSpec, SceneVisual
from fpvs_studio.core.serialization import read_json_file, write_json_file
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.core.task_models import TaskModuleSpec, TaskStepSpec
from fpvs_studio.engines.base import TaskEngineInput
from fpvs_studio.runtime import condition_recovery
from fpvs_studio.runtime.acquisition_evidence import AcquisitionEvidenceRecorder
from fpvs_studio.runtime.condition_recovery import (
    ConditionRecoveryRecorder,
    acknowledge_condition_recovery,
    build_recovery_session_plan,
    build_replacement_session_plan,
    query_condition_recovery,
)
from fpvs_studio.runtime.run_worker import RuntimeWorker
from fpvs_studio.runtime.triggers import TriggerEmissionError


@pytest.fixture
def execution(multi_condition_project, multi_condition_project_root):
    plan = compile_session_plan(
        multi_condition_project,
        project_root=multi_condition_project_root,
        refresh_hz=60.0,
        random_seed=77,
    )
    return multi_condition_project_root, plan


def _record(root, plan):
    return ConditionRecoveryRecorder(
        root,
        plan,
        participant_number="0012",
        participant_session_number=3,
    )


def _files(root):
    root = filesystem_path(root)
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_query_empty_project_creates_nothing(tmp_path):
    assert not query_condition_recovery(tmp_path).records
    assert list(tmp_path.iterdir()) == []


def test_live_execution_is_hidden_and_dead_owner_is_discovered_read_only(execution):
    root, plan = execution
    recorder = _record(root, plan)
    recorder.start_run(plan.ordered_entries()[1].run_id)
    recorder.stage("playback")
    assert not query_condition_recovery(root).records
    recorder.close()  # Abrupt exit leaves the running checkpoint; the OS releases its lock.
    before = _files(root)
    report = query_condition_recovery(root)
    assert not report.warnings
    (record,) = report.records
    assert record.stage == "playback"
    assert record.status == "interrupted"
    assert record.run_ordinal == 2
    assert record.participant_number == "0012"
    assert not record.playback_completed
    assert record.can_rerun
    assert _files(root) == before


@pytest.mark.parametrize("state", ["completed", "cancelled"])
def test_terminal_execution_is_not_reported_as_crashed(execution, state):
    root, plan = execution
    recorder = _record(root, plan)
    recorder.start_run(plan.ordered_entries()[0].run_id)
    recorder.finish(state)
    recorder.close()
    assert not query_condition_recovery(root).records
    assert not list((root / "logs" / ".condition-recovery").glob("*.plan.json"))


def test_explicit_replacement_selects_one_occurrence_and_uses_new_plan(execution):
    _root, plan = execution
    first = plan.ordered_entries()[0]
    before = plan.model_dump_json()
    replacement = build_replacement_session_plan(plan, first.condition_id)
    assert replacement.total_runs == 1
    assert replacement.session_id != plan.session_id
    (selected,) = replacement.ordered_entries()
    assert selected.run_spec == first.run_spec
    assert selected.pre_tasks == first.pre_tasks
    assert selected.post_tasks == first.post_tasks
    assert replacement.random_seed == plan.random_seed
    assert plan.model_dump_json() == before
    with pytest.raises(ValueError, match="no longer present"):
        build_replacement_session_plan(plan, "deleted-condition")


def test_full_playback_artifacts_exist_before_later_task_failure(execution, monkeypatch):
    root, plan = execution
    worker = RuntimeWorker(StubEngine({}))
    first = plan.ordered_entries()[0]

    class SimulatedProcessLoss(BaseException):
        pass

    def fail_after_playback(*_args, **_kwargs):
        path = root / "runs" / "visit" / first.run_id / "run_summary.json"
        saved = read_json_file(path, RunExecutionSummary)
        assert saved.completed_frames > 0
        assert not saved.aborted
        raise SimulatedProcessLoss

    monkeypatch.setattr(worker, "_show_condition_feedback", fail_after_playback)
    with pytest.raises(SimulatedProcessLoss):
        worker.execute_session(
            root,
            plan,
            root / "runs" / "visit",
            participant_number="0012",
            runtime_options={"export_mode": "full", "experiment_test_mode": True},
        )
    assert not (root / "runs" / "visit" / "session_summary.json").exists()
    (record,) = query_condition_recovery(root).records
    assert record.playback_completed
    assert record.stage == "feedback"


def test_rerun_preserves_exact_occurrence_and_never_changes_original(execution):
    root, plan = execution
    selected = plan.ordered_entries()[-1]
    recorder = _record(root, plan)
    for entry in plan.ordered_entries()[:-1]:
        recorder.start_run(entry.run_id)
        recorder.playback_finished(entry.run_id, aborted=False)
    recorder.start_run(selected.run_id)
    recorder.stage("transition")
    recorder.close()
    (record,) = query_condition_recovery(root).records
    before = _files(root)
    recovered = build_recovery_session_plan(root, record)
    assert recovered.session_id != plan.session_id
    assert recovered.total_runs == recovered.block_count == 1
    (entry,) = recovered.ordered_entries()
    assert entry.run_id == selected.run_id
    assert entry.run_spec == selected.run_spec
    assert entry.pre_tasks == selected.pre_tasks
    assert entry.post_tasks == selected.post_tasks
    assert recovered.random_seed == plan.random_seed
    assert entry.global_order_index == entry.block_index == entry.index_within_block == 0
    assert record.run_ordinal == plan.total_runs
    assert len(record.completed_run_ids) == plan.total_runs - 1
    assert record.not_started_run_ids == ()
    assert _files(root) == before


@pytest.mark.parametrize("export_mode", ["compact", "full"])
def test_feedback_failure_preserves_completed_playback_and_reports_distinct_stage(
    execution,
    monkeypatch,
    export_mode,
):
    root, plan = execution
    worker = RuntimeWorker(StubEngine({}))
    monkeypatch.setattr(
        worker, "_show_condition_feedback", Mock(side_effect=RuntimeError("feedback"))
    )
    with pytest.raises(RuntimeError, match="feedback"):
        worker.execute_session(
            root,
            plan,
            root / "runs" / "visit",
            participant_number="0012",
            participant_session_number=3,
            relative_output_dir="runs/visit",
            runtime_options={"export_mode": export_mode, "experiment_test_mode": True},
        )
    (record,) = query_condition_recovery(root).records
    first = plan.ordered_entries()[0]
    assert record.run_id == first.run_id
    assert record.playback_completed
    assert record.stage == "feedback"
    assert record.completed_run_ids == (first.run_id,)
    assert len(record.not_started_run_ids) == plan.total_runs - 1
    if export_mode == "full":
        summary = read_json_file(
            root / "runs" / "visit" / first.run_id / "run_summary.json",
            RunExecutionSummary,
        )
        assert summary.completed_frames > 0
        assert not summary.aborted
    else:
        assert not (root / "runs").exists()


def test_playback_failure_identifies_current_run_without_repeating_completed_runs(
    execution, monkeypatch
):
    root, plan = execution
    engine = StubEngine({})
    original = engine.run_condition
    calls = 0

    def run(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("playback")
        return original(*args, **kwargs)

    monkeypatch.setattr(engine, "run_condition", run)
    with pytest.raises(RuntimeError, match="playback"):
        RuntimeWorker(engine).execute_session(
            root,
            plan,
            root / "unused",
            participant_number="0012",
            runtime_options={"export_mode": "compact", "experiment_test_mode": True},
        )
    (record,) = query_condition_recovery(root).records
    assert record.run_ordinal == 2
    assert record.stage == "playback"
    assert not record.playback_completed
    assert record.completed_run_ids == (plan.ordered_entries()[0].run_id,)
    rerun = build_recovery_session_plan(root, record)
    assert [entry.run_id for entry in rerun.ordered_entries()] == [record.run_id]


def test_normal_escape_does_not_create_interruption_notice(execution):
    root, plan = execution
    summary = RuntimeWorker(StubEngine({"abort_on_transition": True})).execute_session(
        root,
        plan,
        root / "unused",
        participant_number="0012",
        runtime_options={"export_mode": "compact", "experiment_test_mode": True},
    )
    assert summary.aborted
    assert not query_condition_recovery(root).records


@pytest.mark.parametrize("export_mode", ["full", "compact"])
def test_trigger_failure_keeps_exact_interrupted_occurrence_available(
    execution, monkeypatch, export_mode,
):
    root, plan = execution
    engine = StubEngine({})
    original = engine.run_condition
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise TriggerEmissionError("fake transport write failed")
        return original(*args, **kwargs)

    monkeypatch.setattr(engine, "run_condition", fail_second)
    result = RuntimeWorker(engine).execute_session(
        root, plan, root / "runs" / "visit", participant_number="0012",
        runtime_options={"export_mode": export_mode, "experiment_test_mode": True},
    )
    assert result.aborted
    assert "fake transport write failed" in result.abort_reason
    (record,) = query_condition_recovery(root).records
    assert record.status == "interrupted"
    assert record.stage == "playback"
    assert record.run_ordinal == 2
    assert not record.playback_completed
    assert record.completed_run_ids == (plan.ordered_entries()[0].run_id,)
    assert record.can_rerun
    assert build_recovery_session_plan(root, record).ordered_entries()[0] == (
        plan.ordered_entries()[1].model_copy(
            update={"global_order_index": 0, "block_index": 0, "index_within_block": 0},
        )
    )


@pytest.mark.parametrize("export_mode", ["compact", "full"])
@pytest.mark.parametrize("interrupted", [False, True])
def test_native_timed_pre_task_to_playback_has_no_recovery_writes(
    execution, monkeypatch, export_mode, interrupted
):
    root, original = execution
    plan = build_replacement_session_plan(original, original.ordered_entries()[0].condition_id)
    entry = plan.ordered_entries()[0]
    entry.run_spec = entry.run_spec.model_copy(
        update={
            "schema_version": "1.4.0",
                "randomization": None,
            "condition": entry.run_spec.condition.model_copy(
                update={"stimulus_modality": StimulusModality.SCENE}
            ),
            "stimulus_sequence": [],
            "scene_stream": SceneStreamSpec(
                visuals=[SceneVisual(visual_id="base", kind="circle", size=(5, 5))],
                events=[SceneEvent(visual_id="base", start_frame=0, duration_frames=1)],
                requested_soa_ms=50,
                soa_frames=3,
            ),
        }
    )
    entry.pre_tasks = [
        TaskModuleSpec(
            task_id="lead-in",
            name="Lead-in",
            phase="pre_condition",
            occurrence="every_entry",
            random_seed=1,
            steps=[
                TaskStepSpec(
                    step_id="fixation",
                    kind="timed_feedback",
                    text="+",
                    duration_seconds=1.0,
                    random_seed=1,
                )
            ],
        )
    ]
    entry.show_condition_start_gate = False
    entry.condition_presentation_index = entry.condition_presentation_count = None
    plan = SessionPlan.model_validate(
        plan.model_copy(update={
            "schema_version": "1.4.0", "authored_task_flow": True, "ordering_policy": None,
            "randomization_mode": None, "randomization_seeds": None,
            "randomization_algorithm_version": None,
        }).model_dump()
    )
    timing_active = False
    task_shown = False
    original_write = condition_recovery.write_json_file

    class SimulatedProcessLoss(BaseException):
        pass

    def checked_write(*args, **kwargs):
        assert not timing_active, "Recovery I/O entered the timed pre-task/playback interval."
        return original_write(*args, **kwargs)

    class TimedEngine(StubEngine):
        def render_task_step(self, step, _project_root):
            nonlocal timing_active, task_shown
            assert step.duration_frames == 60
            checkpoint = next((root / "logs" / ".condition-recovery").glob("*.lock"))
            assert json.loads(checkpoint.with_suffix(".json").read_text())["stage"] == "armed"
            task_shown = timing_active = True
            return TaskEngineInput(reaction_time_s=1.0)

        def run_condition(self, *args, **kwargs):
            nonlocal timing_active
            assert timing_active
            if interrupted:
                raise SimulatedProcessLoss
            result = super().run_condition(*args, **kwargs)
            timing_active = False
            return result

    monkeypatch.setattr(condition_recovery, "write_json_file", checked_write)
    worker = RuntimeWorker(TimedEngine({}))

    def execute():
        return worker.execute_session(
            root,
            plan,
            root / "runs" / "visit",
            participant_number="0012",
            runtime_options={"export_mode": export_mode, "experiment_test_mode": True},
        )

    if interrupted:
        with pytest.raises(SimulatedProcessLoss):
            execute()
        (record,) = query_condition_recovery(root).records
        assert record.stage == "armed"
        assert not record.playback_completed
        assert record.can_rerun
    else:
        assert not execute().aborted
        assert not query_condition_recovery(root).records
    assert task_shown


def test_historical_acquisition_identifies_sixth_occurrence_and_requires_confirmation(execution):
    root, original = execution
    # Repeated conditions retain occurrence identity; a condition-name match is insufficient.
    entries = original.ordered_entries()
    runs = [
        entries[index % len(entries)].run_spec.model_copy(
            deep=True,
            update={"run_id": f"run_{index + 1:03d}"},
        )
        for index in range(8)
    ]
    recorder = AcquisitionEvidenceRecorder(
        root,
        runs,
        project_id=original.project_id,
        session_id=original.session_id,
        participant_number="0012",
        participant_session_number=1,
        runtime_options={"experiment_test_mode": True},
    )
    evidence = recorder.evidence
    assert evidence is not None and recorder.path is not None
    evidence.state = "running"
    for run in evidence.runs[:5]:
        run.state = "completed"
    evidence.runs[5].state = "started"
    write_json_file(recorder.path, evidence)
    before = _files(root)
    report = query_condition_recovery(root)
    (record,) = report.records
    assert record.status == "unverified"
    assert record.run_id == "run_006"
    assert record.run_ordinal == 6
    assert len(record.completed_run_ids) == 5
    assert record.not_started_run_ids == ("run_007", "run_008")
    assert not record.playback_completed
    assert not record.can_rerun
    assert "Original compiled plan unavailable" in report.warnings[0]
    assert _files(root) == before


def test_legacy_plan_requires_operator_confirmation(execution):
    root, plan = execution
    recorder = AcquisitionEvidenceRecorder(
        root,
        [entry.run_spec for entry in plan.ordered_entries()],
        project_id=plan.project_id,
        session_id=plan.session_id,
        participant_number="0012",
        runtime_options={},
    )
    recorder.start_run(plan.ordered_entries()[0].run_id, 0)
    write_json_file(root / "runs" / "old" / "session_plan.json", plan)
    (record,) = query_condition_recovery(root).records
    assert record.can_rerun
    with pytest.raises(ValueError, match="Confirm"):
        build_recovery_session_plan(root, record)
    assert build_recovery_session_plan(root, record, allow_unverified=True).total_runs == 1


def test_malformed_record_is_visible_as_warning_and_never_modified(tmp_path):
    folder = tmp_path / "logs" / ".condition-recovery"
    folder.mkdir(parents=True)
    path = folder / "bad.json"
    path.write_text("{unfinished", encoding="utf-8")
    report = query_condition_recovery(tmp_path)
    assert not report.records
    assert report.warnings == ("Could not inspect recovery record bad.json.",)
    assert path.read_text() == "{unfinished"


@pytest.mark.parametrize(
    "invalid_field",
    [
        "unknown_current",
        "duplicate_runs",
        "unknown_started",
        "unknown_completed",
        "duplicate_started",
        "duplicate_completed",
        "completed_not_started",
        "current_not_started",
        "missing_current",
        "execution_id",
    ],
)
def test_incoherent_checkpoint_never_selects_a_different_run(execution, invalid_field):
    root, plan = execution
    recorder = _record(root, plan)
    first, second = plan.ordered_entries()[:2]
    recorder.start_run(first.run_id)
    recorder.playback_finished(first.run_id, aborted=False)
    recorder.start_run(second.run_id)
    recorder.close()
    path = root / "logs" / ".condition-recovery" / f"{recorder.execution_id}.json"
    payload = json.loads(path.read_text())
    if invalid_field == "unknown_current":
        payload["current_run_id"] = "nonexistent-run"
    elif invalid_field == "duplicate_runs":
        payload["runs"].append(payload["runs"][0])
    elif invalid_field == "unknown_started":
        payload["started_run_ids"].append("nonexistent-run")
    elif invalid_field == "unknown_completed":
        payload["completed_run_ids"].append("nonexistent-run")
    elif invalid_field == "duplicate_started":
        payload["started_run_ids"].append(first.run_id)
    elif invalid_field == "duplicate_completed":
        payload["completed_run_ids"].append(first.run_id)
    elif invalid_field == "completed_not_started":
        payload["started_run_ids"].remove(first.run_id)
    elif invalid_field == "current_not_started":
        payload["started_run_ids"].remove(second.run_id)
    elif invalid_field == "missing_current":
        payload["current_run_id"] = None
    else:
        payload["execution_id"] = "different-execution"
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = _files(root)
    report = query_condition_recovery(root)
    assert not report.records
    assert report.warnings == (f"Could not inspect recovery record {path.name}.",)
    assert _files(root) == before


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize(
    "mismatch", ["project_id", "session_id", "run_id", "condition_id", "run_project_id", "order"]
)
def test_original_plan_must_match_entire_recorded_identity(execution, legacy, mismatch):
    root, plan = execution
    first = plan.ordered_entries()[0]
    if legacy:
        recorder = AcquisitionEvidenceRecorder(
            root,
            [entry.run_spec for entry in plan.ordered_entries()],
            project_id=plan.project_id,
            session_id=plan.session_id,
            participant_number="0012",
            runtime_options={},
        )
        recorder.start_run(first.run_id, 0)
        path = root / "runs" / "old" / "session_plan.json"
    else:
        recorder = _record(root, plan)
        recorder.start_run(first.run_id)
        recorder.close()
        path = root / "logs" / ".condition-recovery" / f"{recorder.execution_id}.plan.json"
    payload = plan.model_dump(mode="json")
    entry = payload["blocks"][0]["entries"][0]
    if mismatch in {"project_id", "session_id"}:
        payload[mismatch] = "another-identity"
    elif mismatch == "run_id":
        entry["run_id"] = entry["run_spec"]["run_id"] = "another-run"
    elif mismatch == "condition_id":
        entry["condition_id"] = entry["run_spec"]["condition"]["condition_id"] = "another-condition"
    elif mismatch == "run_project_id":
        entry["run_spec"]["project_id"] = "another-project"
    else:
        entries = payload["blocks"][0]["entries"]
        entries[0]["index_within_block"], entries[1]["index_within_block"] = 1, 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = _files(root)
    report = query_condition_recovery(root)
    (record,) = report.records
    assert record.run_id == first.run_id
    assert not record.can_rerun
    assert report.warnings
    with pytest.raises(ValueError, match="unavailable"):
        build_recovery_session_plan(root, record, allow_unverified=True)
    assert _files(root) == before


def test_missing_lock_does_not_claim_owner_has_exited(execution):
    root, plan = execution
    recorder = _record(root, plan)
    recorder.close()
    path = root / "logs" / ".condition-recovery" / f"{recorder.execution_id}.lock"
    path.unlink()
    report = query_condition_recovery(root)
    assert not report.records
    assert report.warnings


def test_terminal_marker_suppresses_legacy_running_receipt(execution):
    root, plan = execution
    recorder = _record(root, plan)
    acquisition = AcquisitionEvidenceRecorder(
        root,
        [entry.run_spec for entry in plan.ordered_entries()],
        project_id=plan.project_id,
        session_id=plan.session_id,
        participant_number="0012",
        runtime_options={},
        execution_id=recorder.execution_id,
    )
    acquisition.start_run(plan.ordered_entries()[0].run_id, 0)
    recorder.finish("cancelled")
    recorder.close()
    assert not query_condition_recovery(root).records


def test_query_rejects_redirected_record(execution, tmp_path):
    root, plan = execution
    recorder = _record(root, plan)
    recorder.close()
    path = root / "logs" / ".condition-recovery" / f"{recorder.execution_id}.json"
    outside = tmp_path / "outside.json"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"File symlinks unavailable: {error}")
    report = query_condition_recovery(root)
    assert not report.records
    assert report.warnings
    assert json.loads(outside.read_text())["state"] == "running"


def _interrupted_record(root, plan):
    recorder = _record(root, plan)
    recorder.start_run(plan.ordered_entries()[0].run_id)
    recorder.close()
    return next(
        record for record in query_condition_recovery(root).records
        if record.execution_id == recorder.execution_id
    )


def _acknowledgement_file(root):
    return next(
        (filesystem_path(root) / "logs" / ".condition-recovery" / "acknowledgements").glob("*.json")
    )


def test_acknowledgement_persists_without_rewriting_incomplete_evidence(execution, tmp_path):
    root, plan = execution
    record = _interrupted_record(root, plan)
    before = _files(root)
    acknowledge_condition_recovery(root, (record,))
    after = _files(root)
    assert all(after[path] == payload for path, payload in before.items())
    (new_path,) = after.keys() - before.keys()
    assert new_path.parent == Path("logs/.condition-recovery/acknowledgements")
    saved = json.loads(after[new_path])
    assert saved["schema_version"] == "1"
    assert saved["project_id"] == plan.project_id
    assert saved["execution_id"] == record.execution_id
    assert saved["run_id"] == record.run_id
    assert saved["participant_number"] == record.participant_number
    assert not query_condition_recovery(root, include_acknowledged=False).records
    (reviewed,) = query_condition_recovery(root).records
    assert reviewed.acknowledged_at is not None
    assert reviewed.status == record.status
    assert not reviewed.playback_completed
    assert build_recovery_session_plan(root, reviewed).total_runs == 1
    assert build_recovery_session_plan(root, record).ordered_entries()[0].run_id == record.run_id
    assert _files(root) == after  # Both query modes and manual review stay read-only.
    copied = tmp_path / "copied-project"
    shutil.copytree(filesystem_path(root), filesystem_path(copied))
    assert not query_condition_recovery(copied, include_acknowledged=False).records
    assert query_condition_recovery(copied).records[0].acknowledged_at == reviewed.acknowledged_at


def test_acknowledgement_is_idempotent_and_does_not_need_original_plan(execution, monkeypatch):
    root, plan = execution
    record = _interrupted_record(root, plan)
    acknowledge_condition_recovery(root, (record,))
    before = _files(root)
    acknowledge_condition_recovery(root, (record, record))
    assert _files(root) == before
    (root / "logs" / ".condition-recovery" / f"{record.execution_id}.plan.json").unlink()
    with monkeypatch.context() as patch:
        patch.setattr(
            condition_recovery, "_original_plan", Mock(side_effect=AssertionError("No plan read")),
        )
        report = query_condition_recovery(root, include_acknowledged=False)
    assert report.records == report.warnings == ()
    (reviewed,) = query_condition_recovery(root).records
    assert reviewed.acknowledged_at is not None
    assert not reviewed.can_rerun


def test_plan_removed_after_display_does_not_block_acknowledgement(execution):
    root, plan = execution
    record = _interrupted_record(root, plan)
    assert record.can_rerun
    (root / "logs" / ".condition-recovery" / f"{record.execution_id}.plan.json").unlink()
    acknowledge_condition_recovery(root, (record,))
    report = query_condition_recovery(root, include_acknowledged=False)
    assert report.records == report.warnings == ()


@pytest.mark.parametrize("session_known", [False, True])
def test_acknowledgement_legacy_receipt_hides_its_missing_plan_notice(execution, session_known):
    root, plan = execution
    recorder = AcquisitionEvidenceRecorder(
        root, [entry.run_spec for entry in plan.ordered_entries()],
        project_id=plan.project_id, session_id=plan.session_id if session_known else None,
        participant_number="0012", runtime_options={},
    )
    recorder.start_run(plan.ordered_entries()[0].run_id, 0)
    (record,) = query_condition_recovery(root).records
    assert record.status == "unverified"
    assert query_condition_recovery(root).warnings
    before = _files(root)
    acknowledge_condition_recovery(root, (record,))
    report = query_condition_recovery(root, include_acknowledged=False)
    assert report.records == report.warnings == ()
    assert query_condition_recovery(root).records[0].acknowledged_at is not None
    assert all(_files(root)[path] == value for path, value in before.items())


def test_new_execution_for_same_participant_remains_pending(execution):
    root, plan = execution
    first = _interrupted_record(root, plan)
    acknowledge_condition_recovery(root, (first,))
    second = _interrupted_record(root, plan)
    assert second.execution_id != first.execution_id
    (pending,) = query_condition_recovery(root, include_acknowledged=False).records
    assert pending.execution_id == second.execution_id
    assert pending.acknowledged_at is None


def test_new_occurrence_and_snapshot_require_new_acknowledgement(execution):
    root, plan = execution
    recorder = _record(root, plan)
    first, second = plan.ordered_entries()[:2]
    recorder.start_run(first.run_id)
    recorder.close()
    (record,) = query_condition_recovery(root).records
    acknowledge_condition_recovery(root, (record,))
    path = root / record.evidence_path
    payload = json.loads(path.read_text())
    payload["current_run_id"] = second.run_id
    payload["started_run_ids"].append(second.run_id)
    path.write_text(json.dumps(payload))
    (pending,) = query_condition_recovery(root, include_acknowledged=False).records
    assert pending.run_id == second.run_id
    acknowledge_condition_recovery(root, (pending,))
    assert len(list(_acknowledgement_file(root).parent.glob("*.json"))) == 2
    payload["stage"] = "playback"
    payload["updated_at"] = "2099-01-01T00:00:00+00:00"
    path.write_text(json.dumps(payload))
    (new_snapshot,) = query_condition_recovery(root, include_acknowledged=False).records
    assert new_snapshot.stage == "playback"
    acknowledge_condition_recovery(root, (new_snapshot,))
    assert not query_condition_recovery(root, include_acknowledged=False).records


def test_acknowledgement_rejects_live_stale_and_foreign_records(execution, tmp_path):
    root, plan = execution
    recorder = _record(root, plan)
    recorder.start_run(plan.ordered_entries()[0].run_id)
    live = replace(
        _interrupted_record(tmp_path / "other-project", plan),
        execution_id=recorder.execution_id,
    )
    with pytest.raises(ValueError, match="changed"):
        acknowledge_condition_recovery(root, (live,))
    recorder.close()
    (record,) = query_condition_recovery(root).records
    for stale in (replace(record, stage="playback"), replace(record, evidence_path="../outside")):
        with pytest.raises(ValueError, match="changed"):
            acknowledge_condition_recovery(root, (stale,))
    with pytest.raises(ValueError, match="changed"):
        acknowledge_condition_recovery(tmp_path / "other-project", (record,))
    assert not (root / "logs" / ".condition-recovery" / "acknowledgements").exists()


def test_acknowledgement_validates_whole_batch_before_writing(execution):
    root, plan = execution
    first = _interrupted_record(root, plan)
    second = _interrupted_record(root, plan)
    before = _files(root)
    with pytest.raises(ValueError, match="changed"):
        acknowledge_condition_recovery(root, (first, replace(second, participant_number="9999")))
    assert _files(root) == before


def test_acknowledgement_write_failure_is_reported_and_retry_preserves_first_stamp(
    execution, monkeypatch,
):
    root, plan = execution
    records = (_interrupted_record(root, plan), _interrupted_record(root, plan))
    original = condition_recovery.write_json_file
    count = 0

    def fail_second(path, model):
        nonlocal count
        count += 1
        if count == 2:
            raise PermissionError("Synthetic acknowledgement denial")
        return original(path, model)

    with monkeypatch.context() as patch:
        patch.setattr(condition_recovery, "write_json_file", fail_second)
        with pytest.raises(PermissionError, match="denial"):
            acknowledge_condition_recovery(root, records)
    first = next(
        record for record in query_condition_recovery(root).records
        if record.execution_id == records[0].execution_id
    )
    assert first.acknowledged_at is not None
    assert len(query_condition_recovery(root, include_acknowledged=False).records) == 1
    acknowledge_condition_recovery(root, records)
    assert not query_condition_recovery(root, include_acknowledged=False).records
    assert next(
        record for record in query_condition_recovery(root).records
        if record.execution_id == first.execution_id
    ).acknowledged_at == first.acknowledged_at


@pytest.mark.parametrize(
    "tamper", ["malformed", "oversized", "project_id", "run_id", "evidence_path"],
)
def test_invalid_acknowledgement_never_hides_evidence(execution, tamper):
    root, plan = execution
    record = _interrupted_record(root, plan)
    acknowledge_condition_recovery(root, (record,))
    path = _acknowledgement_file(root)
    if tamper == "malformed":
        path.write_text("{unfinished")
    elif tamper == "oversized":
        path.write_text(" " * (64 * 1024 + 1))
    else:
        payload = json.loads(path.read_text())
        payload[tamper] = "unrelated"
        path.write_text(json.dumps(payload))
    before = _files(root)
    report = query_condition_recovery(root, include_acknowledged=False)
    assert report.records[0].execution_id == record.execution_id
    assert report.records[0].acknowledged_at is None
    assert any("acknowledgement" in warning for warning in report.warnings)
    assert _files(root) == before
    with pytest.raises(ValueError):
        acknowledge_condition_recovery(root, (record,))
    assert _files(root) == before


def test_linked_acknowledgement_is_rejected_without_changing_its_target(execution):
    root, plan = execution
    record = _interrupted_record(root, plan)
    acknowledge_condition_recovery(root, (record,))
    path = _acknowledgement_file(root)
    target = root / "saved-acknowledgement.json"
    path.rename(target)
    path.hardlink_to(target)
    before = target.read_bytes()
    report = query_condition_recovery(root, include_acknowledged=False)
    assert report.records[0].acknowledged_at is None
    assert any("acknowledgement" in warning for warning in report.warnings)
    with pytest.raises(ValueError, match="regular file"):
        acknowledge_condition_recovery(root, (record,))
    assert target.read_bytes() == before


def test_acknowledgement_does_not_hide_unrelated_corruption(execution):
    root, plan = execution
    record = _interrupted_record(root, plan)
    acknowledge_condition_recovery(root, (record,))
    bad = root / "logs" / ".condition-recovery" / "corrupted.json"
    bad.write_text("{unfinished")
    report = query_condition_recovery(root, include_acknowledged=False)
    assert not report.records
    assert report.warnings == ("Could not inspect recovery record corrupted.json.",)


@pytest.mark.parametrize("tag, blocked", [(0x9000001A, False), (0xA0000003, True), (0, True)])
def test_acknowledgement_accepts_cloud_placeholders_but_not_redirects(
    execution, monkeypatch, tag, blocked,
):
    root, plan = execution
    record = _interrupted_record(root, plan)
    folder = root / "logs" / ".condition-recovery" / "acknowledgements"
    folder.mkdir()
    original = Path.lstat

    def reparse_info(path):
        info = original(path)
        if path.name != "acknowledgements":
            return info
        return SimpleNamespace(
            st_mode=info.st_mode, st_nlink=info.st_nlink,
            st_file_attributes=getattr(info, "st_file_attributes", 0) | 0x400,
            st_reparse_tag=tag,
        )

    monkeypatch.setattr(Path, "lstat", reparse_info)
    if blocked:
        with pytest.raises(ValueError, match="links"):
            acknowledge_condition_recovery(root, (record,))
        report = query_condition_recovery(root, include_acknowledged=False)
        assert report.records[0].acknowledged_at is None
        assert any("acknowledgement" in warning for warning in report.warnings)
    else:
        acknowledge_condition_recovery(root, (record,))
        assert not query_condition_recovery(root, include_acknowledged=False).records
