"""Independent resolved seeds persist through interchange, visits, and exact recovery."""

from __future__ import annotations

import csv

import pytest
from tests.unit.runtime_launcher_helpers import StubEngine

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.condition_modifiers import assign_modifier
from fpvs_studio.core.enums import ExperimentCategory, ProjectSchemaVersion, StimulusModality
from fpvs_studio.core.execution import RunExecutionSummary, SessionExecutionSummary
from fpvs_studio.core.masking_presets import create_masking_modifier
from fpvs_studio.core.models import ProjectFile, RandomizationSeeds, SessionSettings
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
from fpvs_studio.runtime.condition_recovery import (
    ConditionRecoveryRecorder,
    build_recovery_session_plan,
    query_condition_recovery,
)
from fpvs_studio.runtime.launcher import LaunchSettings, launch_session
from fpvs_studio.runtime.preflight import PreflightError, preflight_session_plan
from fpvs_studio.runtime.session_export import (
    RANDOMIZATION_PROVENANCE_HEADER,
    SESSION_CONDITION_HISTORY_HEADER,
    append_session_condition_history,
    compact_task_checkpoint_path,
)


def _fixed_project(project, *, modality="image"):
    project.settings.session = SessionSettings(
        block_count=1, session_seed=31, randomization_mode="fixed",
        stimulus_seed=72, fixation_seed=109,
    )
    first = project.conditions[0].model_copy(deep=True, update={
        "presentation_count": 2, "stream_duration_seconds": 30,
    })
    second = first.model_copy(deep=True, update={
        "condition_id": "second", "name": "Second", "order_index": 1,
        "presentation_count": 1, "trigger_code": 2,
    })
    project.conditions = [first, second]
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
def test_seed_policy_config_and_public_project_roundtrip(sample_project, tmp_path, mode):
    project = _fixed_project(sample_project)
    project.settings.session.randomization_mode = mode
    config = export_project_config(project, None)
    assert config.schema_version == "1.12.0"
    path = tmp_path / "seeds.fpvsconfig"
    write_project_config(path, config)
    restored = create_project_from_config(tmp_path / "received", read_project_config(path))
    loaded = load_project_file(restored.project_root / "project.json")
    assert loaded.schema_version == ProjectSchemaVersion.V1_14
    session = loaded.settings.session
    assert session.randomization_mode == mode
    assert (session.session_seed, session.stimulus_seed, session.fixation_seed) == (31, 72, 109)
    assert "condition_order_seed" not in session.model_dump()


def test_legacy_seed_config_omits_optional_fields_and_does_not_rewrite_source(
    sample_project, tmp_path,
):
    path = tmp_path / "project.json"
    save_project_file(sample_project, path)
    before = path.read_bytes()
    loaded = load_project_file(path)
    assert path.read_bytes() == before
    config = export_project_config(loaded, None)
    assert config.schema_version == "1.2.0"
    assert not {"randomization_mode", "stimulus_seed", "fixation_seed"}.intersection(
        config.session.model_dump(),
    )


@pytest.mark.parametrize("field,value", [
    ("session_seed", True), ("session_seed", "31"), ("session_seed", 2**31),
    ("stimulus_seed", 72.0), ("fixation_seed", -1), ("fixation_seed", None),
])
def test_config_rejects_invalid_seed_snapshots(sample_project, field, value):
    payload = export_project_config(_fixed_project(sample_project), None).model_dump()
    payload["session"][field] = value
    with pytest.raises(ValueError):
        ProjectConfigFile.model_validate(payload)


def test_config_seed_capability_rejected_before_import_io(sample_project, tmp_path):
    config = export_project_config(_fixed_project(sample_project), None)
    invalid = config.model_copy(update={"schema_version": "1.11.0"})
    target = tmp_path / "received"
    with pytest.raises(ProjectConfigError, match="controls require config schema 1.12"):
        create_project_from_config(target, invalid)
    assert not target.exists()


@pytest.mark.parametrize("specialized", ["ab", "masking"])
def test_specialized_configs_reject_controls_before_io(sample_project, tmp_path, specialized):
    if specialized == "masking":
        project = assign_modifier(
            sample_project, create_masking_modifier(), [sample_project.conditions[0].condition_id],
        )
    else:
        project = sample_project
    config = export_project_config(project, None)
    updates = {"schema_version": "1.12.0", "session": config.session.model_copy(update={
        "randomization_mode": "fixed", "stimulus_seed": 72, "fixation_seed": 109,
    })}
    if specialized == "ab":
        updates["experiment_category"] = ExperimentCategory.ATTENTIONAL_BLINK
        updates["conditions"] = []
    invalid = config.model_copy(update=updates)
    target = tmp_path / "received"
    with pytest.raises(ProjectConfigError, match="unavailable for native AB or masking"):
        create_project_from_config(target, invalid)
    assert not target.exists()


@pytest.mark.parametrize("modality", ["image", "word"])
@pytest.mark.parametrize("export_mode", ["full", "compact"])
def test_fixed_same_plan_preserves_schedules_and_rows_across_participants_and_visits(
    sample_project, sample_project_root, modality, export_mode,
):
    project = _fixed_project(sample_project, modality=modality)
    plan = compile_session_plan(project, refresh_hz=60, project_root=sample_project_root)
    before = plan.model_dump_json()
    captures = {}
    register_engine("fixed-visits", lambda: StubEngine(captures))
    settings = LaunchSettings(
        experiment_test_mode=True, serial_enabled=False, engine_name="fixed-visits",
        export_mode=export_mode, verify_refresh_rate=False,
    )
    try:
        first = launch_session(sample_project_root, plan, participant_number="001",
                               launch_settings=settings)
        first_files = {
            path: path.read_bytes()
            for path in (sample_project_root / first.output_dir).rglob("*") if path.is_file()
        } if first.output_dir else {}
        second = launch_session(sample_project_root, plan, participant_number="002",
                                launch_settings=settings)
        repeated = launch_session(sample_project_root, plan, participant_number="001",
                                  launch_settings=settings)
    finally:
        unregister_engine("fixed-visits")
    assert plan.model_dump_json() == before
    assert len({first.session_id, second.session_id, repeated.session_id}) == 1
    assert [first.participant_session_number, second.participant_session_number,
            repeated.participant_session_number] == [1, 1, 2]
    assert all(path.read_bytes() == data for path, data in first_files.items())
    for result in (first, second, repeated):
        assert result.schema_version == "1.4.0"
        assert result.ordering_policy == "pooled_no_adjacent"
        assert result.randomization_mode == "fixed"
        assert result.randomization_seeds == plan.randomization_seeds
        assert result.randomization_algorithm_version == 1
        assert SessionExecutionSummary.model_validate_json(result.model_dump_json()) == result
        for run, entry in zip(result.run_results, plan.ordered_entries(), strict=True):
            assert run.randomization == entry.run_spec.randomization
            assert run.schema_version == "1.3.0"
            assert RunExecutionSummary.model_validate_json(run.model_dump_json()) == run
    history = _rows(sample_project_root / "logs/session_condition_history.csv")
    assert len(history) == 9
    assert {(row["participant_number"], row["participant_session_number"]) for row in history} == {
        ("001", "1"), ("002", "1"), ("001", "2"),
    }
    assert all(row["randomization_mode"] == "fixed" for row in history)
    assert all((row["condition_order_seed"], row["stimulus_seed"], row["fixation_seed"])
               == ("31", "72", "109") for row in history)
    assert len(list((sample_project_root / "logs/acquisition").glob("*.acquisition-v1.json"))) == 3
    if export_mode == "full":
        rows = _rows(sample_project_root / first.output_dir / "conditions.csv")
        assert all(row["randomization_mode"] == "fixed" for row in rows)
    else:
        assert not (sample_project_root / "runs").exists()
    paths = [compact_task_checkpoint_path(
        sample_project_root, participant_number=pid, session_id=plan.session_id,
        participant_session_number=visit,
    ) for pid, visit in (("001", 1), ("002", 1), ("001", 2))]
    assert len(set(paths)) == 3


def test_completed_config_uses_compiled_snapshot_instead_of_current_editable_seeds(
    sample_project, sample_project_root,
):
    project = _fixed_project(sample_project)
    plan = compile_session_plan(project, refresh_hz=60, project_root=sample_project_root)
    completed = sample_project_root / "runs" / "saved"
    write_json_file(completed / "session_plan.json", plan)
    project.settings.session.stimulus_seed = 999
    config = export_project_config(project, sample_project_root, completed_session_dir=completed)
    assert config.schema_version == "1.13.0"
    assert config.completed_session.ordering_policy == "pooled_no_adjacent"
    assert config.session.stimulus_seed == 999
    assert config.completed_session.randomization_seeds == RandomizationSeeds(
        condition_order_seed=31, stimulus_seed=72, fixation_seed=109,
    )
    assert all(run.randomization.seeds.stimulus_seed == 72
               for run in config.completed_session.ordered_runs)
    assert ProjectConfigFile.model_validate_json(config.model_dump_json()) == config


def test_exact_recovery_preserves_seed_triplet_and_per_occurrence_namespaces(
    sample_project, sample_project_root,
):
    plan = compile_session_plan(_fixed_project(sample_project), refresh_hz=60,
                                project_root=sample_project_root)
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
    assert recovered.session_id != plan.session_id
    assert recovered.randomization_mode == plan.randomization_mode
    assert recovered.randomization_seeds == plan.randomization_seeds
    assert rerun.condition_presentation_index == 2
    assert rerun.run_spec == selected.run_spec
    preflight_session_plan(sample_project_root, recovered, engine=StubEngine({}))
    assert SessionPlan.model_validate_json(recovered.model_dump_json()) == recovered


def test_history_adds_seed_fields_without_replacing_old_rows(sample_project, sample_project_root):
    plan = compile_session_plan(_fixed_project(sample_project), refresh_hz=60,
                                project_root=sample_project_root)
    path = sample_project_root / "logs/session_condition_history.csv"
    path.parent.mkdir(exist_ok=True)
    old_header = [field for field in SESSION_CONDITION_HISTORY_HEADER
                  if field not in RANDOMIZATION_PROVENANCE_HEADER]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=old_header)
        writer.writeheader()
        writer.writerow({"project_id": plan.project_id, "participant_number": "001",
                         "session_id": "old", "run_id": "old", "participant_session_number": 1})
    summary = SessionExecutionSummary(
        project_id=plan.project_id, session_id=plan.session_id, engine_name="stub", run_mode="test",
        participant_number="002", participant_session_number=1,
    )
    append_session_condition_history(sample_project_root, plan, summary, refresh_reports=False)
    append_session_condition_history(sample_project_root, plan, summary, refresh_reports=False)
    rows = _rows(path)
    assert len(rows) == 4
    assert rows[0]["session_id"] == "old"
    assert all(rows[0][field] == "" for field in RANDOMIZATION_PROVENANCE_HEADER)
    assert all(row["randomization_mode"] == "fixed" for row in rows[1:])


@pytest.mark.parametrize("modality", ["image", "word"])
def test_fixed_cohort_compilations_retain_corresponding_repeat_schedules(
    sample_project, sample_project_root, modality,
):
    project = _fixed_project(sample_project, modality=modality)
    first = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60,
                                 session_id="cohort-one")
    second = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60,
                                  session_id="cohort-two")
    assert first.session_id != second.session_id
    for left, right in zip(first.ordered_entries(), second.ordered_entries(), strict=True):
        assert left.condition_id == right.condition_id
        assert left.condition_presentation_index == right.condition_presentation_index
        assert left.run_spec.stimulus_sequence == right.run_spec.stimulus_sequence
        assert left.run_spec.fixation_events == right.run_spec.fixation_events
        assert left.run_spec.randomization == right.run_spec.randomization
    repeated = [entry.run_spec for entry in first.ordered_entries()
                if entry.condition_presentation_count == 2]
    assert len(repeated) == 2
    assert repeated[0].stimulus_sequence != repeated[1].stimulus_sequence
    assert repeated[0].fixation_events != repeated[1].fixation_events


@pytest.mark.parametrize("export_mode", ["full", "compact"])
def test_new_mode_records_one_resolved_snapshot_without_mutating_configured_values(
    sample_project, sample_project_root, export_mode,
):
    project = _fixed_project(sample_project)
    project.settings.session.randomization_mode = "new"
    snapshot = RandomizationSeeds(condition_order_seed=101, stimulus_seed=102, fixation_seed=103)
    plan = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60,
                                resolved_seeds=snapshot)
    register_engine("new-snapshot", lambda: StubEngine({}))
    try:
        summary = launch_session(
            sample_project_root, plan, participant_number="001",
            launch_settings=LaunchSettings(
                experiment_test_mode=True, serial_enabled=False, engine_name="new-snapshot",
                export_mode=export_mode, verify_refresh_rate=False,
            ),
        )
    finally:
        unregister_engine("new-snapshot")
    assert summary.randomization_mode == "new"
    assert summary.randomization_seeds == snapshot
    assert (project.settings.session.session_seed, project.settings.session.stimulus_seed,
            project.settings.session.fixation_seed) == (31, 72, 109)
    history = _rows(sample_project_root / "logs/session_condition_history.csv")
    assert all((row["condition_order_seed"], row["stimulus_seed"], row["fixation_seed"])
               == ("101", "102", "103") for row in history)


@pytest.mark.parametrize("forgery", ["derived_seed", "session_roots", "presentation_index"])
def test_preflight_checks_compiled_seed_provenance_without_repairing_it(
    sample_project, sample_project_root, forgery,
):
    plan = compile_session_plan(_fixed_project(sample_project), refresh_hz=60,
                                project_root=sample_project_root)
    entry = plan.ordered_entries()[0]
    if forgery == "derived_seed":
        provenance = entry.run_spec.randomization
        entry.run_spec.randomization = provenance.model_copy(update={
            "fixation_onset_seed": (provenance.fixation_onset_seed + 1) % 2**31,
        })
    elif forgery == "session_roots":
        plan.randomization_seeds = plan.randomization_seeds.model_copy(update={"fixation_seed": 0})
    else:
        entry.condition_presentation_index = 2
    before = plan.model_dump_json()
    with pytest.raises(PreflightError, match="randomization provenance"):
        preflight_session_plan(sample_project_root, plan, engine=StubEngine({}))
    assert plan.model_dump_json() == before


@pytest.mark.parametrize("version", [True, 1.0])
def test_result_and_completed_config_algorithm_version_are_strict_integers(
    sample_project, sample_project_root, version,
):
    project = _fixed_project(sample_project)
    plan = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60)
    with pytest.raises(ValueError):
        SessionExecutionSummary(
            schema_version="1.3.0", project_id=plan.project_id, session_id=plan.session_id,
            engine_name="stub", run_mode="test", random_seed=plan.random_seed,
            randomization_mode=plan.randomization_mode,
            randomization_seeds=plan.randomization_seeds,
            randomization_algorithm_version=version,
        )
    output = sample_project_root / "runs" / "saved"
    write_json_file(output / "session_plan.json", plan)
    config = export_project_config(project, sample_project_root, completed_session_dir=output)
    payload = config.model_dump(mode="json")
    payload["completed_session"]["randomization_algorithm_version"] = version
    with pytest.raises(ValueError):
        ProjectConfigFile.model_validate(payload)
