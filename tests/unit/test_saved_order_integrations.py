"""Saved arrangements persist and execute as exact orders with explicit provenance."""

from __future__ import annotations

import csv

import pytest
from tests.unit.runtime_launcher_helpers import StubEngine

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.condition_modifiers import assign_modifier
from fpvs_studio.core.enums import ExperimentCategory, ProjectSchemaVersion, StimulusModality
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.masking_presets import create_masking_modifier
from fpvs_studio.core.models import ProjectFile, SessionSettings
from fpvs_studio.core.project_bundle import export_project_bundle, import_project_bundle
from fpvs_studio.core.project_config import (
    ProjectConfigError,
    ProjectConfigFile,
    create_project_from_config,
    export_project_config,
    read_project_config,
    write_project_config,
)
from fpvs_studio.core.serialization import load_project_file, save_project_file, write_json_file
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.engines.registry import register_engine, unregister_engine
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest
from fpvs_studio.runtime.condition_recovery import (
    ConditionRecoveryRecorder,
    build_recovery_session_plan,
    query_condition_recovery,
)
from fpvs_studio.runtime.launcher import LaunchSettings, launch_session
from fpvs_studio.runtime.preflight import preflight_session_plan
from fpvs_studio.runtime.session_export import (
    SESSION_CONDITION_HISTORY_HEADER,
    append_session_condition_history,
)

ORDER = ["faces", "second", "faces", "third", "second"]
ALTERNATIVE_ORDER = ["second", "faces", "third", "faces", "second"]


def _project_with_order(project, *, mode="fixed", modality="image"):
    first = project.conditions[0].model_copy(deep=True, update={
        "presentation_count": 2, "stream_duration_seconds": 30,
    })
    project.conditions = [first, *[first.model_copy(deep=True, update={
        "condition_id": identity, "name": identity.title(), "order_index": index,
        "presentation_count": count, "trigger_code": index + 1,
    }) for identity, index, count in (("second", 1, 2), ("third", 2, 1))]]
    project.settings.session = SessionSettings(
        block_count=7, session_seed=31, randomization_mode=mode,
        stimulus_seed=72, fixation_seed=109, saved_condition_order=ORDER,
    )
    if modality == "word":
        for pool in project.stimulus_sets:
            pool.modality = StimulusModality.WORD
            pool.source_dir = None
            pool.words = [f"{pool.set_id}-{index}" for index in range(7)]
            pool.resolution = None
            pool.image_count = 0
    return ProjectFile.model_validate(project.model_dump())


def _rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


@pytest.mark.parametrize("mode", ["fixed", "new"])
def test_saved_order_config_and_public_project_roundtrip(sample_project, tmp_path, mode):
    project = _project_with_order(sample_project, mode=mode)
    config = export_project_config(project, None)
    assert config.schema_version == "1.13.0"
    path = tmp_path / "order.fpvsconfig"
    write_project_config(path, config)
    restored = create_project_from_config(tmp_path / "received", read_project_config(path))
    loaded = load_project_file(restored.project_root / "project.json")
    assert loaded.schema_version == ProjectSchemaVersion.V1_15
    assert loaded.settings.session.saved_condition_order == ORDER
    assert loaded.settings.session.randomization_mode == mode
    assert loaded.settings.session.stimulus_seed == 72
    assert loaded.settings.session.fixation_seed == 109


def test_absent_saved_order_preserves_old_source_format(sample_project, tmp_path):
    config = export_project_config(sample_project, None)
    assert config.schema_version == "1.2.0"
    assert "saved_condition_order" not in config.session.model_dump()
    path = tmp_path / "legacy.json"
    save_project_file(sample_project, path)
    before = path.read_bytes()
    assert load_project_file(path).settings.session.saved_condition_order is None
    assert path.read_bytes() == before


@pytest.mark.parametrize("order", [
    ["faces", "second", "faces", "unknown", "second"],
    ORDER[:-1], ORDER + ["faces"],
    ["faces", "faces", "second", "third", "second"],
    ["../faces", "second", "faces", "third", "second"],
])
def test_active_invalid_saved_config_rejected_before_import_io(sample_project, tmp_path, order):
    config = export_project_config(_project_with_order(sample_project), None)
    invalid = config.model_copy(update={"session": config.session.model_copy(update={
        "saved_condition_order": order,
    })})
    destination = tmp_path / "received"
    with pytest.raises(ProjectConfigError):
        create_project_from_config(destination, invalid)
    assert not destination.exists()
    path = tmp_path / "invalid.fpvsconfig"
    path.write_text(invalid.model_dump_json(), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ProjectConfigError):
        read_project_config(path)
    assert path.read_bytes() == before


def test_saved_order_config_rejects_non_string_ids(sample_project):
    payload = export_project_config(_project_with_order(sample_project), None).model_dump()
    payload["session"]["saved_condition_order"][0] = 1
    with pytest.raises(ValueError):
        ProjectConfigFile.model_validate(payload)


def test_inactive_stale_order_roundtrips_as_draft_and_new_compilation_ignores_it(
    sample_project, sample_project_root, tmp_path,
):
    project = _project_with_order(sample_project, mode="new")
    project.settings.session.saved_condition_order = ["retired-condition"]
    config = export_project_config(project, None)
    restored = create_project_from_config(tmp_path / "received", config).project
    assert restored.settings.session.saved_condition_order == ["retired-condition"]
    plan = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60)
    assert plan.ordering_policy == "pooled_no_adjacent"
    assert plan.schema_version == "1.7.0"
    assert plan.total_runs == 5
    assert "retired-condition" not in [entry.condition_id for entry in plan.ordered_entries()]


def test_saved_order_capability_rejected_before_import_writes(sample_project, tmp_path):
    config = export_project_config(_project_with_order(sample_project), None)
    invalid = config.model_copy(update={"schema_version": "1.12.0"})
    destination = tmp_path / "received"
    with pytest.raises(ProjectConfigError, match="requires config schema 1.13"):
        create_project_from_config(destination, invalid)
    assert not destination.exists()


@pytest.mark.parametrize("specialized", ["ab", "masking"])
def test_specialized_saved_order_rejected_before_import_writes(
    sample_project, tmp_path, specialized,
):
    project = (assign_modifier(sample_project, create_masking_modifier(),
                               [sample_project.conditions[0].condition_id])
               if specialized == "masking" else sample_project)
    config = export_project_config(project, None)
    invalid = config.model_copy(update={
        "schema_version": "1.13.0",
        **({"experiment_category": ExperimentCategory.ATTENTIONAL_BLINK, "conditions": []}
           if specialized == "ab" else {}),
        "session": config.session.model_copy(update={"saved_condition_order": ["faces"]}),
    })
    destination = tmp_path / "received"
    with pytest.raises(ProjectConfigError, match="unavailable for native AB or masking"):
        create_project_from_config(destination, invalid)
    assert not destination.exists()


def test_saved_order_bundle_reopens_with_exact_order(sample_project, sample_project_root, tmp_path):
    project = _project_with_order(sample_project)
    save_project_file(project, sample_project_root / "project.json")
    write_stimulus_manifest(sample_project_root, create_empty_manifest(project.meta.project_id))
    bundle = tmp_path / "saved-order.fpvsbundle"
    export_project_bundle(sample_project_root, bundle, refresh_hz=60)
    restored = import_project_bundle(bundle, tmp_path / "received")
    project = load_project_file(restored.project_root / "project.json")
    assert project.schema_version == ProjectSchemaVersion.V1_15
    plan = compile_session_plan(project, project_root=restored.project_root, refresh_hz=60)
    assert plan.ordering_policy == "saved_no_adjacent"
    assert [entry.condition_id for entry in plan.ordered_entries()] == ORDER


@pytest.mark.parametrize("modality", ["image", "word"])
def test_same_seeds_can_execute_different_saved_arrangements_without_rerolling_occurrences(
    sample_project, sample_project_root, modality,
):
    project = _project_with_order(sample_project, modality=modality)
    first = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60)
    project.settings.session.saved_condition_order = ALTERNATIVE_ORDER
    second = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60)
    assert first.randomization_seeds == second.randomization_seeds
    assert [entry.condition_id for entry in first.ordered_entries()] == ORDER
    assert [entry.condition_id for entry in second.ordered_entries()] == ALTERNATIVE_ORDER
    originals = {(entry.condition_id, entry.condition_presentation_index): entry.run_spec
                 for entry in first.ordered_entries()}
    for entry in second.ordered_entries():
        original = originals[(entry.condition_id, entry.condition_presentation_index)]
        assert entry.run_spec.stimulus_sequence == original.stimulus_sequence
        assert entry.run_spec.fixation_events == original.fixation_events
        assert entry.run_spec.randomization == original.randomization


@pytest.mark.parametrize("modality", ["image", "word"])
@pytest.mark.parametrize("export_mode", ["full", "compact"])
def test_two_participants_receive_exact_saved_order_and_policy_in_exports(
    sample_project, sample_project_root, modality, export_mode,
):
    project = _project_with_order(sample_project, modality=modality)
    plan = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60)
    register_engine("saved-order", lambda: StubEngine({}))
    settings = LaunchSettings(
        experiment_test_mode=True, serial_enabled=False, engine_name="saved-order",
        export_mode=export_mode, verify_refresh_rate=False,
    )
    before = plan.model_dump_json()
    try:
        first = launch_session(sample_project_root, plan, participant_number="001",
                               launch_settings=settings)
        second = launch_session(sample_project_root, plan, participant_number="002",
                                launch_settings=settings)
    finally:
        unregister_engine("saved-order")
    assert plan.model_dump_json() == before
    for summary in (first, second):
        assert summary.schema_version == "1.4.0"
        assert summary.ordering_policy == "saved_no_adjacent"
        assert summary.realized_block_orders == [ORDER]
        assert summary.randomization_seeds == plan.randomization_seeds
        assert [run.condition_id for run in summary.run_results] == ORDER
        assert SessionExecutionSummary.model_validate_json(summary.model_dump_json()) == summary
    rows = _rows(sample_project_root / "logs/session_condition_history.csv")
    assert len(rows) == 10
    for participant in ("001", "002"):
        participant_rows = [row for row in rows if row["participant_number"] == participant]
        assert [row["condition_id"] for row in participant_rows] == ORDER
        assert all(row["ordering_policy"] == "saved_no_adjacent" for row in participant_rows)
    if export_mode == "full":
        assert [row["condition_id"] for row in _rows(
            sample_project_root / first.output_dir / "conditions.csv",
        )] == ORDER
    else:
        assert not (sample_project_root / "runs").exists()


def test_completed_config_keeps_actual_saved_order_when_source_has_a_new_saved_choice(
    sample_project, sample_project_root,
):
    project = _project_with_order(sample_project)
    plan = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60)
    completed = sample_project_root / "runs" / "completed"
    write_json_file(completed / "session_plan.json", plan)
    project.settings.session.saved_condition_order = ALTERNATIVE_ORDER
    config = export_project_config(project, sample_project_root, completed_session_dir=completed)
    assert config.schema_version == "1.13.0"
    assert config.session.saved_condition_order == ALTERNATIVE_ORDER
    assert config.completed_session.ordering_policy == "saved_no_adjacent"
    assert config.completed_session.block_orders == [ORDER]
    assert [run.condition_id for run in config.completed_session.ordered_runs] == ORDER
    assert ProjectConfigFile.model_validate_json(config.model_dump_json()) == config


def test_saved_order_recovery_replays_original_occurrence_and_policy(
    sample_project, sample_project_root,
):
    project = _project_with_order(sample_project)
    plan = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60)
    selected = plan.ordered_entries()[-1]
    recorder = ConditionRecoveryRecorder(
        sample_project_root, plan, participant_number="001", participant_session_number=1,
    )
    recorder.start_run(selected.run_id)
    recorder.stage("playback")
    recorder.close()
    record, = query_condition_recovery(sample_project_root).records
    recovered = build_recovery_session_plan(sample_project_root, record)
    rerun, = recovered.ordered_entries()
    assert recovered.schema_version == "1.8.0"
    assert recovered.ordering_policy == "saved_no_adjacent"
    assert rerun.run_spec == selected.run_spec
    assert rerun.condition_presentation_index == selected.condition_presentation_index == 2
    preflight_session_plan(sample_project_root, recovered, engine=StubEngine({}))
    assert SessionPlan.model_validate_json(recovered.model_dump_json()) == recovered


def test_history_policy_upgrade_preserves_legacy_rows(sample_project, sample_project_root):
    plan = compile_session_plan(
        _project_with_order(sample_project), project_root=sample_project_root, refresh_hz=60,
    )
    history = sample_project_root / "logs/session_condition_history.csv"
    history.parent.mkdir(exist_ok=True)
    with history.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            field for field in SESSION_CONDITION_HISTORY_HEADER if field != "ordering_policy"
        ])
        writer.writeheader()
        writer.writerow({"project_id": plan.project_id, "participant_number": "001",
                         "session_id": "old", "run_id": "old", "participant_session_number": 1})
    summary = SessionExecutionSummary(
        project_id=plan.project_id, session_id=plan.session_id, engine_name="stub", run_mode="test",
        participant_number="002", participant_session_number=1,
    )
    append_session_condition_history(sample_project_root, plan, summary, refresh_reports=False)
    append_session_condition_history(sample_project_root, plan, summary, refresh_reports=False)
    rows = _rows(history)
    assert len(rows) == 6
    assert rows[0]["session_id"] == "old"
    assert rows[0]["ordering_policy"] == ""
    assert all(row["ordering_policy"] == "saved_no_adjacent" for row in rows[1:])
