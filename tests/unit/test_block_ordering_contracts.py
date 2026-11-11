"""Versioned block ordering preserves interchange, exact recovery and runtime flow."""

from __future__ import annotations

import csv

import pytest
from pydantic import ValidationError
from tests.platform_adapters import windows_runtime
from tests.unit.runtime_launcher_helpers import StubEngine
from tests.unit.studio_handoff_fixtures import read_legacy_config

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.condition_modifiers import assign_modifier
from fpvs_studio.core.condition_timing import propose_condition_timing
from fpvs_studio.core.data_sharing import protocol_fingerprint
from fpvs_studio.core.enums import ExperimentCategory, ProjectSchemaVersion
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.masking_presets import apply_masking_timing_defaults, create_masking_modifier
from fpvs_studio.core.models import ProjectFile, SessionSettings
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

ORDER = ["faces", "second", "third", "faces", "second"]


@pytest.fixture(autouse=True)
def _windows_acquisition_contract(monkeypatch):
    windows_runtime(monkeypatch)


def _project(project, *, saved=False):
    first = project.conditions[0].model_copy(deep=True, update={
        "presentation_count": 2, "stream_duration_seconds": 30,
    })
    project.conditions = [first, *[first.model_copy(deep=True, update={
        "condition_id": identity, "name": identity.title(), "order_index": index,
        "presentation_count": count, "trigger_code": index + 1,
    }) for identity, index, count in (("second", 1, 2), ("third", 2, 1))]]
    project.settings.session = SessionSettings(
        block_count=7, session_seed=31, randomization_mode="fixed",
        stimulus_seed=72, fixation_seed=109, condition_ordering="randomized_blocks",
        saved_condition_order=ORDER if saved else None,
    )
    fixation = project.settings.fixation_task
    fixation.enabled = True
    fixation.changes_per_sequence = 2
    fixation.target_duration_ms = 100
    fixation.min_gap_ms = 2000
    return ProjectFile.model_validate(project.model_dump())


@pytest.mark.parametrize("saved", [False, True])
def test_block_ordering_project_and_config_roundtrip(sample_project, tmp_path, saved):
    project = _project(sample_project, saved=saved)
    assert project.schema_version == ProjectSchemaVersion.V1_17
    path = tmp_path / "project.json"
    save_project_file(project, path)
    assert load_project_file(path) == project
    config = export_project_config(project, None)
    assert config.format_version == 2
    assert config.session.condition_ordering == "randomized_blocks"
    config_path = tmp_path / "design.fpvsconfig"
    write_project_config(config_path, config)
    restored = create_project_from_config(tmp_path / "received", read_project_config(config_path))
    loaded = load_project_file(restored.project_root / "project.json")
    assert loaded.schema_version == ProjectSchemaVersion.V1_17
    assert loaded.settings.session.condition_ordering == "randomized_blocks"
    assert loaded.settings.session.saved_condition_order == (ORDER if saved else None)
    assert loaded.settings.session.fixation_seed == 109


def test_absent_block_setting_preserves_legacy_payload_and_fingerprint(
    sample_project, sample_project_root, tmp_path,
):
    before = sample_project.model_dump_json()
    assert "condition_ordering" not in sample_project.settings.session.model_dump()
    legacy_config = export_project_config(sample_project, None)
    assert "condition_ordering" not in legacy_config.session.model_dump()
    path = tmp_path / "legacy.json"
    save_project_file(sample_project, path)
    saved = path.read_bytes()
    assert load_project_file(path).settings.session.condition_ordering is None
    assert path.read_bytes() == saved
    assert sample_project.model_dump_json() == before
    block = _project(sample_project.model_copy(deep=True))
    legacy = block.model_copy(deep=True)
    legacy.settings.session.condition_ordering = None
    assert protocol_fingerprint(block, sample_project_root) != protocol_fingerprint(
        legacy, sample_project_root,
    )


def test_block_ordering_capability_is_strict_and_rejected_before_import_io(
    sample_project, tmp_path,
):
    with pytest.raises(ValidationError):
        SessionSettings(condition_ordering="pooled_no_adjacent")
    project = _project(sample_project)
    invalid_ab = project.model_dump()
    invalid_ab["experiment_category"] = ExperimentCategory.ATTENTIONAL_BLINK
    with pytest.raises(ValidationError, match="blocks are unavailable"):
        ProjectFile.model_validate(invalid_ab)
    config = export_project_config(project, None)

    destination = tmp_path / "received"
    with pytest.raises(ProjectConfigError):
        create_project_from_config(destination, read_legacy_config(config, "1.14.0", tmp_path))
    assert not destination.exists()


def test_block_ordering_proposal_and_clear_keep_the_explicit_design(sample_project):
    original = _project(sample_project, saved=True)
    old = original.model_copy(deep=True)
    old.settings.session.condition_ordering = None
    selected = propose_condition_timing(old, condition_ordering="randomized_blocks")
    assert selected.settings.session.condition_ordering == "randomized_blocks"
    assert old.settings.session.condition_ordering is None
    cleared = propose_condition_timing(selected, clear_saved_condition_order=True)
    assert cleared.settings.session.saved_condition_order is None
    assert cleared.settings.session.condition_ordering == "randomized_blocks"
    assert original.settings.session.saved_condition_order == ORDER


@pytest.mark.parametrize("saved", [False, True])
def test_block_plan_completed_config_and_single_occurrence_recovery(
    sample_project, sample_project_root, saved,
):
    project = _project(sample_project, saved=saved)
    plan = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60)
    policy = "saved_randomized_blocks" if saved else "randomized_blocks"
    assert plan.ordering_policy == policy
    assert plan.schema_version == "1.10.0"
    assert len(plan.blocks) == 2
    assert SessionPlan.model_validate_json(plan.model_dump_json()) == plan
    invalid = plan.model_dump()
    invalid["schema_version"] = "1.7.0"
    with pytest.raises(ValidationError, match="1.10.0"):
        SessionPlan.model_validate(invalid)
    completed = sample_project_root / "runs" / "completed"
    write_json_file(completed / "session_plan.json", plan)
    config = export_project_config(project, sample_project_root, completed_session_dir=completed)
    assert config.format_version == 2
    assert config.completed_session.ordering_policy == policy
    assert config.completed_session.block_orders == [block.condition_order for block in plan.blocks]
    assert ProjectConfigFile.model_validate_json(config.model_dump_json()) == config
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
    assert recovered.ordering_policy == policy
    assert recovered.schema_version == "1.10.0"
    assert rerun.run_spec == selected.run_spec
    assert rerun.condition_presentation_index == selected.condition_presentation_index == 2
    preflight_session_plan(sample_project_root, recovered, engine=StubEngine({}))


@pytest.mark.parametrize("saved", [False, True])
@pytest.mark.parametrize("export_mode", ["full", "compact"])
def test_block_ordering_runtime_records_blocks_without_adding_break_screens(
    sample_project, sample_project_root, saved, export_mode,
):
    plan = compile_session_plan(_project(sample_project, saved=saved),
                                project_root=sample_project_root, refresh_hz=60)
    captures = {}
    register_engine("block-contract", lambda: StubEngine(captures))
    settings = LaunchSettings(
        experiment_test_mode=True, serial_enabled=False, engine_name="block-contract",
        export_mode=export_mode, verify_refresh_rate=False,
    )
    before = plan.model_dump_json()
    try:
        summary = launch_session(sample_project_root, plan, participant_number="001",
                                 launch_settings=settings)
    finally:
        unregister_engine("block-contract")
    assert summary.schema_version == "1.5.0"
    assert summary.ordering_policy == plan.ordering_policy
    assert summary.realized_block_orders == [block.condition_order for block in plan.blocks]
    assert len(summary.run_results) == 5
    assert not summary.aborted
    assert captures.get("block_breaks", []) == []
    assert SessionExecutionSummary.model_validate_json(summary.model_dump_json()) == summary
    assert plan.model_dump_json() == before
    with (sample_project_root / "logs/session_condition_history.csv").open(
        encoding="utf-8", newline="",
    ) as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 5
    assert all(row["ordering_policy"] == plan.ordering_policy for row in rows)


def test_ordinary_block_design_stays_dormant_after_masking_assignment_and_interchange(
    sample_project, sample_project_root, tmp_path,
):
    sample_project.settings.session.condition_ordering = "randomized_blocks"
    ordinary = ProjectFile.model_validate(sample_project.model_dump())
    condition_id = ordinary.conditions[0].condition_id
    masked = assign_modifier(ordinary, create_masking_modifier(variant="color"), [condition_id])
    masked = apply_masking_timing_defaults(masked)
    assert masked.settings.session.condition_ordering == "randomized_blocks"
    assert masked.settings.session.saved_condition_order is None
    assert ordinary.condition_modifiers == []
    plan = compile_session_plan(masked, project_root=sample_project_root, refresh_hz=60)
    assert plan.ordering_policy is None
    assert plan.randomization_seeds is None
    assert plan.total_runs == 3
    assert plan.authored_task_flow is True
    assert len(plan.blocks) == 1
    config = export_project_config(masked, None)
    assert config.format_version == 2
    assert config.session.condition_ordering == "randomized_blocks"
    restored = create_project_from_config(tmp_path / "masked", config)
    reopened = load_project_file(restored.project_root / "project.json")
    assert reopened.settings.session.condition_ordering == "randomized_blocks"
    rebuilt = compile_session_plan(reopened, project_root=restored.project_root, refresh_hz=60)
    assert rebuilt.ordering_policy is None
    assert rebuilt.total_runs == 3
    assert rebuilt.authored_task_flow is True
    invalid = masked.model_dump()
    invalid["settings"]["session"]["saved_condition_order"] = [condition_id] * 3
    with pytest.raises(ValidationError, match="Saved condition order is unavailable for masking"):
        ProjectFile.model_validate(invalid)


def test_block_preflight_rejects_removed_session_seed_snapshot(sample_project, sample_project_root):
    plan = compile_session_plan(_project(sample_project),
                                project_root=sample_project_root, refresh_hz=60)
    assert plan.schema_version == "1.10.0"
    tampered = plan.model_copy(deep=True, update={"randomization_seeds": None})
    with pytest.raises(PreflightError, match="resolved seed triplet"):
        preflight_session_plan(sample_project_root, tampered, engine=StubEngine({}))
