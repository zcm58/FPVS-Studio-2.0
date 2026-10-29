"""Effective condition rates survive interchange and govern downstream timing."""

from __future__ import annotations

import json

import pytest

from fpvs_studio.core.attentional_blink_presets import populate_attentional_blink_stream
from fpvs_studio.core.compiler_conditions import validate_selected_condition
from fpvs_studio.core.compiler_limits import CompilationLimits, validate_compilation_workload
from fpvs_studio.core.compiler_masking import compile_masking_run
from fpvs_studio.core.compiler_support import CompileError
from fpvs_studio.core.condition_modifiers import assign_modifier
from fpvs_studio.core.enums import DutyCycleMode, ExperimentCategory, ProjectSchemaVersion
from fpvs_studio.core.masking import (
    add_masking_catch_condition,
    condition_masking,
    masking_catch_source_conditions,
)
from fpvs_studio.core.masking_presets import apply_masking_timing_defaults, create_masking_modifier
from fpvs_studio.core.models import ProjectFile, ProjectMeta, ProjectSettings, ProtocolSettings
from fpvs_studio.core.project_bundle import export_project_bundle, import_project_bundle
from fpvs_studio.core.project_config import (
    ProjectConfigError,
    create_project_from_config,
    export_project_config,
    read_project_config,
    write_project_config,
)
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest


def test_config_roundtrip_retains_shared_rate_and_explicit_override(
    multi_condition_project, tmp_path,
) -> None:
    project = multi_condition_project
    project.settings.protocol.base_hz = 6
    project.conditions[1].base_hz = 4
    project = ProjectFile.model_validate(project.model_dump())
    config = export_project_config(project, project_root=None)
    path = tmp_path / "frequency.fpvsconfig"
    write_project_config(path, config)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.9.0"
    assert payload["protocol"]["base_hz"] == 6
    assert "base_hz" not in payload["conditions"][0]
    assert payload["conditions"][1]["base_hz"] == 4
    scaffold = create_project_from_config(tmp_path / "imported", read_project_config(path))
    restored = scaffold.project
    assert restored.schema_version == ProjectSchemaVersion.V1_11
    assert restored.settings.protocol.base_hz == 6
    assert [condition.base_hz for condition in restored.conditions] == [None, 4, None, None]
    reopened = load_project_file(scaffold.project_root / "project.json")
    assert reopened.schema_version == ProjectSchemaVersion.V1_11
    assert [condition.base_hz for condition in reopened.conditions] == [None, 4, None, None]


def test_inherited_config_keeps_legacy_version_and_payload_shape(sample_project) -> None:
    config = export_project_config(sample_project, project_root=None)
    assert config.schema_version == "1.2.0"
    assert all("base_hz" not in row for row in config.model_dump()["conditions"])


def test_config_override_requires_new_schema_without_rewriting_original(
    sample_project, tmp_path,
) -> None:
    sample_project.conditions[0].base_hz = 4
    config = export_project_config(sample_project, project_root=None)
    payload = config.model_dump(mode="json")
    payload["schema_version"] = "1.8.0"
    path = tmp_path / "wrong-version.fpvsconfig"
    original = json.dumps(payload)
    path.write_text(original, encoding="utf-8")
    with pytest.raises(ProjectConfigError, match="frequency overrides require config schema 1.9"):
        read_project_config(path)
    assert path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("has_stream_settings", [False, True])
def test_config_rejects_ab_override_before_creating_import_files(tmp_path, has_stream_settings):
    project = populate_attentional_blink_stream(ProjectFile(
        experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
        meta=ProjectMeta(project_id="ab-frequency", name="AB", template_id="fpvs_6hz_every5_v1"),
        settings=ProjectSettings(protocol=ProtocolSettings(base_hz=10)),
    ))
    original = export_project_config(project, project_root=None)
    condition = original.conditions[0].model_copy(update={
        "base_hz": 8,
        "attentional_blink": original.conditions[0].attentional_blink
        if has_stream_settings else None,
    })
    invalid = original.model_copy(update={
        "schema_version": "1.9.0", "conditions": [condition, *original.conditions[1:]],
    })
    parent = tmp_path / "receiving-root"
    with pytest.raises(ProjectConfigError, match="unavailable for Attentional-Blink"):
        create_project_from_config(parent, invalid)
    assert not parent.exists()
    path = tmp_path / "unsupported-ab.fpvsconfig"
    payload = invalid.model_dump_json()
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(ProjectConfigError, match="unavailable for Attentional-Blink"):
        read_project_config(path)
    assert path.read_text(encoding="utf-8") == payload


@pytest.mark.parametrize("rate", [0, -1, float("inf"), float("nan")])
def test_config_rejects_invalid_condition_frequency(sample_project, tmp_path, rate) -> None:
    config = export_project_config(sample_project, project_root=None)
    payload = config.model_dump(mode="json")
    payload["schema_version"] = "1.9.0"
    payload["conditions"][0]["base_hz"] = rate
    path = tmp_path / "invalid-frequency.fpvsconfig"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ProjectConfigError):
        read_project_config(path)


def test_bundle_roundtrip_preserves_condition_override(
    sample_project, sample_project_root, tmp_path,
) -> None:
    sample_project.conditions[0].base_hz = 4
    project = ProjectFile.model_validate(sample_project.model_dump())
    save_project_file(project, sample_project_root / "project.json")
    write_stimulus_manifest(sample_project_root, create_empty_manifest(project.meta.project_id))
    bundle = tmp_path / "frequency.fpvsbundle"
    export_project_bundle(sample_project_root, bundle)
    imported = import_project_bundle(bundle, tmp_path / "receiver")
    restored = load_project_file(imported.project_root / "project.json")
    assert restored.schema_version == ProjectSchemaVersion.V1_11
    assert restored.conditions[0].base_hz == 4
    assert restored.settings.protocol.base_hz == 6


def test_workload_frame_budget_uses_each_conditions_effective_rate(sample_project) -> None:
    project = sample_project
    project.settings.presentation.pre_stream_fixation_seconds = 0
    project.settings.fixation_task.enabled = False
    project.conditions[0].oddball_cycle_repeats_per_sequence = 1
    limits = CompilationLimits(max_total_frames=150)
    validate_compilation_workload(project, project.conditions, refresh_hz=60, limits=limits)
    project.conditions[0].base_hz = 3
    with pytest.raises(CompileError, match="total frames limit"):
        validate_compilation_workload(project, project.conditions, refresh_hz=60, limits=limits)


def test_workload_override_overflow_fails_before_integer_conversion(sample_project) -> None:
    sample_project.conditions[0].base_hz = 5e-324
    with pytest.raises(CompileError, match="total frames limit"):
        validate_compilation_workload(
            sample_project, sample_project.conditions, refresh_hz=60, limits=CompilationLimits(),
        )


def test_selected_condition_mode_validation_uses_override(sample_project) -> None:
    condition = sample_project.conditions[0]
    condition.duty_cycle_mode = DutyCycleMode.BLANK_50
    sample_project.settings.protocol.base_hz = 4
    condition.base_hz = 5
    validate_selected_condition(sample_project, condition, refresh_hz=60)
    sample_project.settings.protocol.base_hz = 6
    condition.base_hz = 4
    with pytest.raises(CompileError, match="even"):
        validate_selected_condition(sample_project, condition, refresh_hz=60)


def test_masking_compile_and_config_retain_effective_condition_rate(
    sample_project, tmp_path,
) -> None:
    project = assign_modifier(
        sample_project, create_masking_modifier(), [sample_project.conditions[0].condition_id],
    )
    project = apply_masking_timing_defaults(project)
    project.conditions[0].base_hz = 4
    project = ProjectFile.model_validate(project.model_dump())
    condition = project.conditions[0]
    settings = condition_masking(project, condition)
    assert settings is not None
    run = compile_masking_run(
        project, condition, settings, refresh_hz=60, project_root=tmp_path,
        random_seed=12, run_id="rate-test",
    )
    assert run.condition.base_hz == 4
    assert run.condition.oddball_hz == 0.8
    assert run.display.frames_per_stimulus == 15
    config = export_project_config(project, project_root=None)
    assert config.schema_version == "1.9.0"
    assert config.conditions[0].base_hz == 4


def test_masking_catch_rejects_source_frequency_mismatch(sample_project) -> None:
    project = assign_modifier(
        sample_project, create_masking_modifier(), [sample_project.conditions[0].condition_id],
    )
    project = apply_masking_timing_defaults(project)
    project, catch_id = add_masking_catch_condition(project, project.conditions[0].condition_id)
    catch = next(item for item in project.conditions if item.condition_id == catch_id)
    catch.base_hz = 4
    with pytest.raises(ValueError, match="same stimulus presentation frequency"):
        masking_catch_source_conditions(project, catch)
