"""Requested stream seconds survive interchange and govern budgets and exports."""

from __future__ import annotations

import csv
import json

import pytest

from fpvs_studio.core.attentional_blink_presets import populate_attentional_blink_stream
from fpvs_studio.core.cognitive_load_presets import populate_cognitive_load_fpvs
from fpvs_studio.core.compiler import compile_run_spec, compile_session_plan
from fpvs_studio.core.compiler_limits import CompilationLimits, validate_compilation_workload
from fpvs_studio.core.compiler_masking import compile_masking_run
from fpvs_studio.core.compiler_support import CompileError
from fpvs_studio.core.condition_modifiers import assign_modifier
from fpvs_studio.core.condition_template_profiles import (
    apply_condition_defaults_to_condition,
    apply_condition_template_profile_to_settings,
    load_condition_template_profile_library,
    upsert_condition_template_profile,
)
from fpvs_studio.core.condition_timing import resolve_condition_stream_timing
from fpvs_studio.core.enums import (
    ConditionTemplateSchemaVersion,
    ExperimentCategory,
    ProjectSchemaVersion,
    RunMode,
)
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.masking import (
    add_masking_catch_condition,
    condition_masking,
    masking_catch_source_conditions,
)
from fpvs_studio.core.masking_presets import apply_masking_timing_defaults, create_masking_modifier
from fpvs_studio.core.models import (
    ConditionDefaults,
    ConditionTemplateDefaults,
    ConditionTemplateDisplayDefaults,
    ConditionTemplateProfile,
    ProjectFile,
    ProjectMeta,
    ProjectSettings,
    ProtocolSettings,
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
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.validation import condition_stimulus_repeat_guidance
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest
from fpvs_studio.runtime.preflight import _validate_scene_timing
from fpvs_studio.runtime.session_export import (
    SESSION_CONDITION_HISTORY_HEADER,
    append_session_condition_history,
    write_session_artifacts,
)


def _rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def test_requested_seconds_config_and_public_project_roundtrip(multi_condition_project, tmp_path):
    project = multi_condition_project
    project.conditions[0].stream_duration_seconds = 120
    project.conditions[1].stream_duration_seconds = 90
    project.conditions[1].base_hz = 4
    project = ProjectFile.model_validate(project.model_dump())
    config = export_project_config(project, project_root=None)
    assert config.schema_version == "1.10.0"
    path = tmp_path / "duration.fpvsconfig"
    write_project_config(path, config)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["conditions"][0]["stream_duration_seconds"] == 120
    assert "stream_duration_seconds" not in payload["conditions"][2]
    imported = create_project_from_config(tmp_path / "received", read_project_config(path))
    reopened = load_project_file(imported.project_root / "project.json")
    assert reopened.schema_version == ProjectSchemaVersion.V1_12
    assert [item.stream_duration_seconds for item in reopened.conditions] == [120, 90, None, None]
    assert reopened.conditions[1].base_hz == 4


def test_legacy_two_sequences_keep_240_second_continuous_stream(sample_project, tmp_path):
    condition = sample_project.conditions[0]
    condition.sequence_count = 2
    condition.oddball_cycle_repeats_per_sequence = 144
    sample_project.settings.display.preferred_refresh_hz = None
    config = export_project_config(sample_project, project_root=None)
    assert config.schema_version == "1.2.0"
    assert "stream_duration_seconds" not in config.conditions[0].model_dump()
    imported = create_project_from_config(tmp_path, config).project
    assert imported.settings.display.preferred_refresh_hz is None
    assert imported.conditions[0].stream_duration_seconds is None
    assert imported.conditions[0].sequence_count == 2
    timing = resolve_condition_stream_timing(imported, imported.conditions[0], 60)
    assert timing.total_oddball_cycles == 288
    assert timing.duration_seconds == 240


def test_duration_config_requires_new_capability_before_import_writes(sample_project, tmp_path):
    sample_project.conditions[0].stream_duration_seconds = 120
    config = export_project_config(sample_project, project_root=None)
    invalid = config.model_copy(update={"schema_version": "1.9.0"})
    target = tmp_path / "received"
    with pytest.raises(ProjectConfigError, match="require config schema 1.10"):
        create_project_from_config(target, invalid)
    assert not target.exists()
    path = tmp_path / "older-capability.fpvsconfig"
    payload = invalid.model_dump_json()
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(ProjectConfigError, match="require config schema 1.10"):
        read_project_config(path)
    assert path.read_text(encoding="utf-8") == payload


def test_requested_seconds_bundle_roundtrip(sample_project, sample_project_root, tmp_path):
    sample_project.conditions[0].stream_duration_seconds = 120
    project = ProjectFile.model_validate(sample_project.model_dump())
    save_project_file(project, sample_project_root / "project.json")
    write_stimulus_manifest(sample_project_root, create_empty_manifest(project.meta.project_id))
    bundle = tmp_path / "duration.fpvsbundle"
    export_project_bundle(sample_project_root, bundle, refresh_hz=60)
    imported = import_project_bundle(bundle, tmp_path / "receiver")
    reopened = load_project_file(imported.project_root / "project.json")
    assert reopened.schema_version == ProjectSchemaVersion.V1_12
    assert reopened.conditions[0].stream_duration_seconds == 120
    timing = resolve_condition_stream_timing(reopened, reopened.conditions[0], 60)
    assert timing.total_frames == 7200


def test_duration_workload_uses_authoritative_seconds_not_stale_legacy_counts(sample_project):
    project = sample_project
    project.settings.presentation.pre_stream_fixation_seconds = 0
    project.settings.fixation_task.enabled = False
    condition = project.conditions[0]
    condition.oddball_cycle_repeats_per_sequence = 1
    condition.stream_duration_seconds = 120
    with pytest.raises(CompileError, match="total frames limit"):
        validate_compilation_workload(
            project, project.conditions, refresh_hz=60,
            limits=CompilationLimits(max_total_frames=1000),
        )
    condition.stream_duration_seconds = 1e308
    with pytest.raises(CompileError, match="total frames limit"):
        validate_compilation_workload(project, project.conditions, refresh_hz=60,
                                      limits=CompilationLimits())


def test_unknown_refresh_does_not_invent_exposure_counts(sample_project):
    sample_project.settings.display.preferred_refresh_hz = None
    sample_project.conditions[0].stream_duration_seconds = 120
    assert condition_stimulus_repeat_guidance(sample_project) == []
    rows = condition_stimulus_repeat_guidance(sample_project, refresh_hz=60)
    assert {row.role: row.presentation_count for row in rows} == {"base": 576, "oddball": 144}


def test_bundle_budget_rejects_overflowing_duration_before_resolution(sample_project):
    sample_project.conditions[0].stream_duration_seconds = 1e308
    with pytest.raises(ProjectBundleError, match="frame limit"):
        _validate_bundle_compilation_budget(sample_project, refresh_hz=240)


def test_duration_masking_contract_roundtrip_and_preflight(sample_project, tmp_path):
    project = assign_modifier(sample_project, create_masking_modifier(),
                              [sample_project.conditions[0].condition_id])
    project = apply_masking_timing_defaults(project)
    condition = project.conditions[0]
    condition.stream_duration_seconds = 120
    settings = condition_masking(project, condition)
    assert settings is not None
    run = compile_masking_run(project, condition, settings, refresh_hz=60,
                              project_root=tmp_path, random_seed=12, run_id="duration")
    assert run.schema_version == "1.6.0"
    assert run.condition.requested_duration_seconds == 120
    assert run.condition.total_oddball_cycles == 120
    assert run.display.total_frames == 7200
    restored = RunSpec.model_validate_json(run.model_dump_json())
    _validate_scene_timing(restored)
    forged = run.model_dump(mode="json")
    forged["schema_version"] = "1.4.0"
    with pytest.raises(ValueError, match="1.6"):
        RunSpec.model_validate(forged)


def test_masking_catch_compares_authoritative_duration_not_cached_cycles(sample_project):
    project = assign_modifier(sample_project, create_masking_modifier(),
                              [sample_project.conditions[0].condition_id])
    project = apply_masking_timing_defaults(project)
    project, catch_id = add_masking_catch_condition(project, project.conditions[0].condition_id)
    catch = next(item for item in project.conditions if item.condition_id == catch_id)
    catch.stream_duration_seconds = 120
    assert catch.oddball_cycle_repeats_per_sequence == 40
    with pytest.raises(ValueError, match="same stream length"):
        masking_catch_source_conditions(project, catch, refresh_hz=60)


def test_duration_profile_library_and_application_preserve_requested_seconds(
    sample_project, tmp_path,
):
    profile = ConditionTemplateProfile(
        profile_id="duration", display_name="Two minute stream",
        defaults=ConditionTemplateDefaults(
            condition=ConditionDefaults(stream_duration_seconds=120),
            display=ConditionTemplateDisplayDefaults(preferred_refresh_hz=60),
        ),
    )
    library = upsert_condition_template_profile(tmp_path, profile)
    assert library.schema_version == ConditionTemplateSchemaVersion.V1_3
    loaded = next(item for item in load_condition_template_profile_library(tmp_path).profiles
                  if item.profile_id == "duration")
    condition = apply_condition_defaults_to_condition(sample_project.conditions[0],
                                                       loaded.defaults.condition)
    assert condition.stream_duration_seconds == 120
    settings = apply_condition_template_profile_to_settings(sample_project.settings, loaded)
    project = sample_project.model_copy(deep=True)
    project.conditions = []
    project.settings = settings
    project = ProjectFile.model_validate(project.model_dump())
    config = export_project_config(project, project_root=None)
    assert config.schema_version == "1.10.0"
    assert config.condition_defaults.stream_duration_seconds == 120
    imported = create_project_from_config(tmp_path / "received", config).project
    assert imported.settings.condition_defaults.stream_duration_seconds == 120
    assert imported.schema_version == ProjectSchemaVersion.V1_12


def test_cognitive_load_factory_honors_duration_template_defaults():
    project = ProjectFile(
        experiment_category=ExperimentCategory.COGNITIVE_LOAD_FPVS,
        meta=ProjectMeta(project_id="duration-load", name="Load", template_id="fpvs_6hz_every5_v1"),
        settings=ProjectSettings(condition_defaults=ConditionDefaults(stream_duration_seconds=120)),
    )
    populated = populate_cognitive_load_fpvs(project)
    assert len(populated.conditions) == 6
    assert all(condition.stream_duration_seconds == 120 for condition in populated.conditions)
    assert all(resolve_condition_stream_timing(populated, condition, 60).duration_seconds == 120
               for condition in populated.conditions)


@pytest.mark.parametrize("placement", ["condition", "defaults"])
def test_ab_duration_config_rejected_before_import_creates_files(tmp_path, placement):
    project = populate_attentional_blink_stream(ProjectFile(
        experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
        meta=ProjectMeta(project_id="ab-duration", name="AB", template_id="fpvs_6hz_every5_v1"),
        settings=ProjectSettings(protocol=ProtocolSettings(base_hz=10)),
    ))
    original = export_project_config(project, project_root=None)
    updates = {"schema_version": "1.10.0"}
    if placement == "condition":
        updates["conditions"] = [original.conditions[0].model_copy(update={
            "stream_duration_seconds": 5,
        }), *original.conditions[1:]]
    else:
        updates["condition_defaults"] = ConditionDefaults(stream_duration_seconds=5)
    invalid = original.model_copy(update=updates)
    target = tmp_path / "received"
    with pytest.raises(ProjectConfigError, match="duration overrides are unavailable"):
        create_project_from_config(target, invalid)
    assert not target.exists()


def test_requested_and_resolved_stream_seconds_export_additively(
    sample_project, sample_project_root, tmp_path,
):
    sample_project.conditions[0].stream_duration_seconds = 120
    plan = compile_session_plan(sample_project, project_root=sample_project_root, refresh_hz=60)
    summary = SessionExecutionSummary(
        project_id=plan.project_id, session_id=plan.session_id,
        engine_name="stub", run_mode=RunMode.TEST,
        participant_number="007", participant_session_number=2,
    )
    output = tmp_path / "full"
    write_session_artifacts(output, plan, summary)
    conditions = _rows(output / "conditions.csv")
    assert all(float(row["requested_stream_duration_seconds"]) == 120 for row in conditions)
    assert all(float(row["resolved_stream_duration_seconds"]) == 120 for row in conditions)
    history = sample_project_root / "logs/session_condition_history.csv"
    history.parent.mkdir(exist_ok=True)
    old_header = [column for column in SESSION_CONDITION_HISTORY_HEADER if column not in {
        "requested_stream_duration_seconds", "resolved_stream_duration_seconds",
    }]
    with history.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=old_header)
        writer.writeheader()
        writer.writerow({
            "project_id": plan.project_id, "participant_number": "006",
            "participant_session_number": 1, "session_id": "previous", "run_id": "old",
        })
    append_session_condition_history(sample_project_root, plan, summary, refresh_reports=False)
    append_session_condition_history(sample_project_root, plan, summary, refresh_reports=False)
    rows = _rows(history)
    assert len(rows) == 1 + plan.total_runs
    assert rows[0]["session_id"] == "previous"
    assert rows[0]["requested_stream_duration_seconds"] == ""
    assert all(float(row["resolved_stream_duration_seconds"]) == 120 for row in rows[1:])


def test_duration_metadata_does_not_change_legacy_compiled_stream(
    sample_project, sample_project_root,
):
    condition = sample_project.conditions[0]
    condition.sequence_count = 2
    condition.oddball_cycle_repeats_per_sequence = 144
    run = compile_run_spec(sample_project, project_root=sample_project_root, refresh_hz=60)
    assert run.condition.requested_duration_seconds is None
    assert "requested_duration_seconds" not in run.condition.model_dump()
    assert run.display.total_frames == 14400
