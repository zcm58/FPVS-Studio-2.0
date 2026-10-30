"""Separate presentation totals survive interchange, execution, and recovery."""

from __future__ import annotations

import csv
import json

import pytest
from pydantic import ValidationError
from tests.unit.runtime_launcher_helpers import StubEngine

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.compiler_limits import CompilationLimits, validate_compilation_workload
from fpvs_studio.core.compiler_support import CompileError
from fpvs_studio.core.condition_modifiers import assign_modifier
from fpvs_studio.core.condition_template_profiles import (
    apply_condition_defaults_to_condition,
    load_condition_template_profile_library,
    upsert_condition_template_profile,
)
from fpvs_studio.core.enums import (
    ConditionTemplateSchemaVersion,
    ExperimentCategory,
    ProjectSchemaVersion,
    RunMode,
)
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.masking_presets import create_masking_modifier
from fpvs_studio.core.models import (
    ConditionDefaults,
    ConditionTemplateDefaults,
    ConditionTemplateProfile,
    ProjectFile,
)
from fpvs_studio.core.project_bundle import (
    ProjectBundleError,
    _validate_bundle_compilation_budget,
    export_project_bundle,
    import_project_bundle,
)
from fpvs_studio.core.project_config import (
    ProjectConfigError,
    create_project_from_config,
    export_project_config,
    read_project_config,
    write_project_config,
)
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.core.task_models import (
    TaskBinding,
    TaskModule,
    TaskOccurrence,
    TaskStep,
    TaskStepKind,
)
from fpvs_studio.engines.base import TaskEngineInput
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest
from fpvs_studio.runtime.condition_recovery import (
    ConditionRecoveryRecorder,
    build_recovery_session_plan,
    query_condition_recovery,
)
from fpvs_studio.runtime.preflight import (
    PreflightError,
    _validate_session_presentation_identity,
    preflight_session_plan,
)
from fpvs_studio.runtime.run_worker import RuntimeWorker
from fpvs_studio.runtime.session_export import (
    SESSION_CONDITION_HISTORY_HEADER,
    append_session_condition_history,
    write_session_artifacts,
)


def _two_conditions(project, counts=(3, 2)):
    first = project.conditions[0].model_copy(deep=True, update={
        "presentation_count": counts[0], "stream_duration_seconds": 60,
    })
    second = first.model_copy(deep=True, update={
        "condition_id": "second", "name": "Second", "order_index": 1,
        "presentation_count": counts[1], "trigger_code": 2,
    })
    project.conditions = [first, second]
    project.settings.session.block_count = 17
    project.settings.fixation_task.enabled = False
    project.settings.fixation_task.accuracy_task_enabled = False
    return ProjectFile.model_validate(project.model_dump())


def _rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_presentation_counts_config_public_project_roundtrip(sample_project, tmp_path):
    project = _two_conditions(sample_project)
    project.conditions[1].base_hz = 4
    project.settings.condition_defaults.presentation_count = 2
    config = export_project_config(project, project_root=None)
    assert config.schema_version == "1.11.0"
    path = tmp_path / "presentations.fpvsconfig"
    write_project_config(path, config)
    imported = create_project_from_config(tmp_path / "received", read_project_config(path))
    reopened = load_project_file(imported.project_root / "project.json")
    assert reopened.schema_version == ProjectSchemaVersion.V1_13
    assert [condition.presentation_count for condition in reopened.conditions] == [3, 2]
    assert reopened.settings.session.block_count == 17
    assert reopened.settings.condition_defaults.presentation_count == 2
    assert reopened.conditions[1].base_hz == 4
    assert all(condition.stream_duration_seconds == 60 for condition in reopened.conditions)


def test_legacy_config_omits_count_and_keeps_continuous_sequence_semantics(
    sample_project, tmp_path,
):
    sample_project.settings.session.block_count = 2
    sample_project.conditions[0].sequence_count = 2
    sample_project.conditions[0].oddball_cycle_repeats_per_sequence = 144
    config = export_project_config(sample_project, project_root=None)
    assert config.schema_version == "1.2.0"
    assert "presentation_count" not in config.conditions[0].model_dump()
    restored = create_project_from_config(tmp_path, config).project
    assert restored.conditions[0].presentation_count is None
    assert restored.conditions[0].sequence_count == 2
    assert restored.settings.session.block_count == 2


@pytest.mark.parametrize("value", [0, -1, True, 2.0, "2"])
def test_config_counts_reject_non_positive_or_non_integer_values(sample_project, value):
    payload = export_project_config(sample_project, None).model_dump()
    payload["schema_version"] = "1.11.0"
    payload["conditions"][0]["presentation_count"] = value
    from fpvs_studio.core.project_config import ProjectConfigFile
    with pytest.raises(ValidationError):
        ProjectConfigFile.model_validate(payload)


@pytest.mark.parametrize("placement", ["condition", "defaults"])
def test_presentation_capability_rejected_before_import_writes(sample_project, tmp_path, placement):
    project = _two_conditions(sample_project)
    if placement == "defaults":
        project.conditions = []
        project.settings.condition_defaults.presentation_count = 3
    config = export_project_config(project, None).model_copy(update={"schema_version": "1.10.0"})
    target = tmp_path / "received"
    with pytest.raises(ProjectConfigError, match="counts require config schema 1.11"):
        create_project_from_config(target, config)
    assert not target.exists()
    path = tmp_path / "unsupported.fpvsconfig"
    path.write_text(config.model_dump_json(), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ProjectConfigError, match="counts require config schema 1.11"):
        read_project_config(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("placement", ["condition", "defaults"])
def test_ab_count_config_rejected_before_import_writes(sample_project, tmp_path, placement):
    config = export_project_config(sample_project, None)
    updates = {
        "schema_version": "1.11.0", "experiment_category": ExperimentCategory.ATTENTIONAL_BLINK,
    }
    if placement == "condition":
        updates["conditions"] = [config.conditions[0].model_copy(update={"presentation_count": 3})]
    else:
        updates["conditions"] = []
        updates["condition_defaults"] = ConditionDefaults(presentation_count=3)
    invalid = config.model_copy(update=updates)
    target = tmp_path / "received"
    with pytest.raises(ProjectConfigError, match="counts are unavailable for Attentional-Blink"):
        create_project_from_config(target, invalid)
    assert not target.exists()


@pytest.mark.parametrize("placement", ["condition", "defaults"])
def test_masking_count_config_rejected_before_import_writes(sample_project, tmp_path, placement):
    project = assign_modifier(
        sample_project, create_masking_modifier(), [sample_project.conditions[0].condition_id],
    )
    config = export_project_config(project, None)
    updates = {"schema_version": "1.11.0"}
    if placement == "condition":
        updates["conditions"] = [config.conditions[0].model_copy(update={"presentation_count": 3})]
    else:
        updates["condition_defaults"] = ConditionDefaults(presentation_count=3)
    invalid = config.model_copy(update=updates)
    target = tmp_path / "received"
    with pytest.raises(ProjectConfigError, match="counts are unavailable for masking"):
        create_project_from_config(target, invalid)
    assert not target.exists()


def test_count_template_library_uses_narrow_capability_and_preserves_legacy(
    sample_project, tmp_path,
):
    profile = ConditionTemplateProfile(
        profile_id="three-presentations", display_name="Three presentations",
        defaults=ConditionTemplateDefaults(condition=ConditionDefaults(presentation_count=3)),
    )
    upsert_condition_template_profile(tmp_path, profile)
    library = load_condition_template_profile_library(tmp_path)
    assert library.schema_version == ConditionTemplateSchemaVersion.V1_4
    restored = next(item for item in library.profiles if item.profile_id == profile.profile_id)
    condition = apply_condition_defaults_to_condition(
        sample_project.conditions[0], restored.defaults.condition,
    )
    assert condition.presentation_count == 3
    assert condition.sequence_count == 1
    reset = apply_condition_defaults_to_condition(condition, ConditionDefaults())
    assert reset.presentation_count is None


def test_bundle_retains_exact_unequal_counts(sample_project, sample_project_root, tmp_path):
    project = _two_conditions(sample_project)
    save_project_file(project, sample_project_root / "project.json")
    write_stimulus_manifest(sample_project_root, create_empty_manifest(project.meta.project_id))
    path = tmp_path / "presentation.fpvsbundle"
    export_project_bundle(sample_project_root, path, refresh_hz=60)
    imported = import_project_bundle(path, tmp_path / "received")
    reopened = load_project_file(imported.project_root / "project.json")
    assert reopened.schema_version == ProjectSchemaVersion.V1_13
    plan = compile_session_plan(reopened, project_root=imported.project_root, refresh_hz=60)
    assert plan.total_runs == 5
    assert [entry.condition_presentation_count for entry in plan.ordered_entries()] == [
        3, 2, 3, 2, 3,
    ]


def test_workload_budgets_use_counts_once_not_global_multiplier(sample_project):
    project = _two_conditions(sample_project)
    project.settings.session.block_count = 1_000_000
    validate_compilation_workload(
        project, project.conditions, refresh_hz=60,
        limits=CompilationLimits(max_session_entries=5, max_total_frames=18600),
    )
    _validate_bundle_compilation_budget(project, refresh_hz=60)
    with pytest.raises(CompileError, match="session entries"):
        validate_compilation_workload(
            project, project.conditions, refresh_hz=60,
            limits=CompilationLimits(max_session_entries=4),
        )
    project.conditions[0].presentation_count = 10001
    with pytest.raises(ProjectBundleError, match="run limit"):
        _validate_bundle_compilation_budget(project, refresh_hz=60)


class _InstructionEngine(StubEngine):
    def render_task_step(self, step, project_root):
        self._captures.setdefault("task_steps", []).append(step.step_id)
        return TaskEngineInput(key="space")


@pytest.mark.parametrize("export_mode", ["compact", "full"])
@pytest.mark.parametrize("counts", [(3, 2), (2, 1)])
def test_unequal_presentations_execute_separately_with_normal_task_and_export_flow(
    sample_project, sample_project_root, export_mode, counts,
):
    project = _two_conditions(sample_project, counts)
    project.task_modules = [TaskModule(
        task_id=identity, name=identity,
        steps=[TaskStep(step_id=identity, kind=TaskStepKind.INSTRUCTION, text=identity,
                        continue_key="space")],
    ) for identity in ("first", "each", "last")]
    project.conditions[0].pre_task_bindings = [
        TaskBinding(task_id="first", occurrence=TaskOccurrence.FIRST_OCCURRENCE),
        TaskBinding(task_id="each"),
    ]
    project.conditions[0].post_task_bindings = [
        TaskBinding(task_id="last", occurrence=TaskOccurrence.LAST_OCCURRENCE),
    ]
    plan = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60)
    entries = plan.ordered_entries()
    assert len(entries) == sum(counts)
    assert all(entry.run_spec.display.total_frames == 3600 for entry in entries)
    captures = {}
    engine = _InstructionEngine(captures)
    preflight_session_plan(sample_project_root, plan, engine=engine)
    summary = RuntimeWorker(engine).execute_session(
        sample_project_root, plan, sample_project_root / "runs" / "visit",
        participant_number="007", participant_session_number=2,
        runtime_options={"experiment_test_mode": True, "export_mode": export_mode},
    )
    assert not summary.aborted
    assert captures["run_ids"] == [entry.run_id for entry in entries]
    assert len(captures["transitions"]) == sum(counts)
    assert captures["task_steps"] == ["first", *["each"] * counts[0], "last"]
    assert len(summary.run_results) == sum(counts)
    assert all(result.completed_frames == 3600 for result in summary.run_results)


def test_abort_preserves_planned_occurrence_identity_and_prior_completed_presentations(
    sample_project, sample_project_root,
):
    project = _two_conditions(sample_project)
    plan = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60)
    captures = {}

    class _AbortingEngine(StubEngine):
        def run_condition(self, run_spec, project_root, **kwargs):
            result = super().run_condition(run_spec, project_root, **kwargs)
            if len(self._captures["run_ids"]) == 3:
                return result.model_copy(update={
                    "aborted": True, "abort_reason": "Test interruption", "completed_frames": 17,
                })
            return result

    summary = RuntimeWorker(_AbortingEngine(captures)).execute_session(
        sample_project_root, plan, sample_project_root / "runs" / "abort",
        participant_number="007", participant_session_number=2,
        runtime_options={"experiment_test_mode": True, "export_mode": "compact"},
    )
    assert summary.aborted
    assert len(summary.run_results) == 3
    assert [result.completed_frames for result in summary.run_results] == [3600, 3600, 17]
    append_session_condition_history(sample_project_root, plan, summary, refresh_reports=False)
    rows = _rows(sample_project_root / "logs" / "session_condition_history.csv")
    assert [row["condition_presentation_index"] for row in rows] == ["1", "1", "2", "2", "3"]
    assert rows[2]["run_aborted"] == "True"
    assert rows[2]["completed_frames"] == "17"
    assert rows[3]["completed_frames"] == rows[4]["completed_frames"] == ""
    assert all(row["participant_session_number"] == "2" for row in rows)


def test_history_appends_occurrence_identity_preserves_old_rows_and_is_idempotent(
    sample_project, sample_project_root, tmp_path,
):
    project = _two_conditions(sample_project)
    plan = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60)
    summary = SessionExecutionSummary(
        project_id=plan.project_id, session_id=plan.session_id, engine_name="stub",
        run_mode=RunMode.TEST, participant_number="007", participant_session_number=2,
    )
    output = tmp_path / "full"
    write_session_artifacts(output, plan, summary)
    rows = _rows(output / "conditions.csv")
    assert [row["condition_presentation_index"] for row in rows] == ["1", "1", "2", "2", "3"]
    assert [row["condition_presentation_count"] for row in rows] == ["3", "2", "3", "2", "3"]
    history = sample_project_root / "logs" / "session_condition_history.csv"
    history.parent.mkdir(exist_ok=True)
    old_header = [column for column in SESSION_CONDITION_HISTORY_HEADER
                  if not column.startswith("condition_presentation_")]
    with history.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=old_header)
        writer.writeheader()
        writer.writerow({"project_id": plan.project_id, "participant_number": "006",
                         "session_id": "old", "run_id": "old-run", "participant_session_number": 1})
    append_session_condition_history(sample_project_root, plan, summary, refresh_reports=False)
    append_session_condition_history(sample_project_root, plan, summary, refresh_reports=False)
    rows = _rows(history)
    assert len(rows) == 6
    assert rows[0]["session_id"] == "old"
    assert rows[0]["condition_presentation_index"] == ""
    assert [row["condition_presentation_index"] for row in rows[1:]] == ["1", "1", "2", "2", "3"]
    assert all(row["participant_session_number"] == "2" for row in rows[1:])


def test_exact_recovery_retains_original_presentation_index_count_and_tasks(
    sample_project, sample_project_root,
):
    project = _two_conditions(sample_project)
    plan = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60)
    selected = plan.ordered_entries()[-1]
    recorder = ConditionRecoveryRecorder(
        sample_project_root, plan, participant_number="007", participant_session_number=2,
    )
    for entry in plan.ordered_entries()[:-1]:
        recorder.start_run(entry.run_id)
        recorder.playback_finished(entry.run_id, aborted=False)
    recorder.start_run(selected.run_id)
    recorder.stage("playback")
    recorder.close()
    record, = query_condition_recovery(sample_project_root).records
    recovered = build_recovery_session_plan(sample_project_root, record)
    rerun, = recovered.ordered_entries()
    assert recovered.total_runs == 1
    assert rerun.condition_presentation_index == 3
    assert rerun.condition_presentation_count == 3
    assert rerun.run_spec == selected.run_spec
    assert rerun.run_id == selected.run_id
    assert rerun.pre_tasks == selected.pre_tasks
    assert rerun.post_tasks == selected.post_tasks
    _validate_session_presentation_identity(recovered)
    assert SessionPlan.model_validate_json(recovered.model_dump_json()) == recovered


def test_preflight_rejects_forged_occurrence_identity_and_reads_legacy_plans(
    sample_project, sample_project_root,
):
    plan = compile_session_plan(
        _two_conditions(sample_project), project_root=sample_project_root, refresh_hz=60,
    )
    plan.ordered_entries()[2].condition_presentation_index = 1
    with pytest.raises(PreflightError, match="indices or counts"):
        _validate_session_presentation_identity(plan)
    payload = json.loads(plan.model_dump_json())
    payload.pop("ordering_policy")
    payload["schema_version"] = "1.2.0"
    for block in payload["blocks"]:
        for entry in block["entries"]:
            entry.pop("condition_presentation_index")
            entry.pop("condition_presentation_count")
    legacy = SessionPlan.model_validate(payload)
    _validate_session_presentation_identity(legacy)
