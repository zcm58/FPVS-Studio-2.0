"""Locked project categories, non-destructive legacy loading, and boundary guards."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from fpvs_studio.core.compiler import CompileError, compile_run_spec, compile_session_plan
from fpvs_studio.core.condition_template_profiles import (
    ATTENTIONAL_BLINK_PROFILE_ID,
    apply_condition_template_profile_to_settings,
    built_in_condition_template_profiles,
    list_condition_template_profiles,
    require_profile_category,
)
from fpvs_studio.core.enums import DutyCycleMode, ExperimentCategory, ProjectSchemaVersion
from fpvs_studio.core.experiment_categories import (
    category_conflict_condition_ids,
    experiment_category_label,
    require_valid_experiment_category,
)
from fpvs_studio.core.migrations import migrate_project_payload
from fpvs_studio.core.models import AttentionalBlinkSettings, ProjectFile
from fpvs_studio.core.project_bundle import ProjectBundleError, export_project_bundle
from fpvs_studio.core.project_config import (
    ProjectConfigError,
    ProjectConfigFile,
    create_project_from_config,
    export_project_config,
    read_project_config,
    write_project_config,
)
from fpvs_studio.core.project_service import build_starter_project, create_project
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.validation import validate_project
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest


def _legacy_payload(project, *, mixed=False, dormant_t2=False):
    payload = project.model_dump(mode="json")
    payload.pop("experiment_category")
    payload["schema_version"] = "1.3.0"
    if mixed:
        standard = dict(payload["conditions"][0])
        standard.update(condition_id="standard", name="Standard", order_index=1)
        payload["conditions"].append(standard)
    if mixed or dormant_t2:
        payload["conditions"][0]["t2_stimulus_set_id"] = "preserved-t2"
    if mixed:
        payload["conditions"][0]["attentional_blink"] = {"isi_ms": 75.0}
    return payload


@pytest.mark.parametrize("category", list(ExperimentCategory))
def test_project_category_is_frozen(sample_project, category):
    with pytest.raises(ValidationError, match="frozen"):
        sample_project.experiment_category = category


@pytest.mark.parametrize(
    ("category", "label"),
    [(ExperimentCategory.FPVS, "FPVS"),
     (ExperimentCategory.FPVS_ODDBALL, "FPVS-Oddball"),
     (ExperimentCategory.ATTENTIONAL_BLINK, "Attentional-Blink")],
)
def test_category_names(category, label):
    assert experiment_category_label(category) == label


def test_legacy_classification_uses_timing_and_preserves_scientific_settings(sample_project):
    payload = _legacy_payload(sample_project, mixed=True)
    payload["settings"]["fixation_task"]["enabled"] = False
    original = json.loads(json.dumps(payload))
    project = migrate_project_payload(payload)
    assert payload == original
    assert project.schema_version == ProjectSchemaVersion.V1_4
    assert project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
    assert category_conflict_condition_ids(project) == ("standard",)
    assert project.conditions[0].attentional_blink.isi_ms == 75
    assert project.conditions[0].t2_stimulus_set_id == "preserved-t2"
    assert not project.settings.fixation_task.enabled
    assert project.meta.template_id == sample_project.meta.template_id
    assert project.stimulus_sets == sample_project.stimulus_sets
    assert project.conditions[1].attentional_blink is None


def test_legacy_empty_timing_object_counts_as_ab(sample_project):
    payload = _legacy_payload(sample_project)
    payload["conditions"][0]["attentional_blink"] = {}
    project = migrate_project_payload(payload)
    assert project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
    assert project.conditions[0].attentional_blink == AttentionalBlinkSettings()
    assert not category_conflict_condition_ids(project)


def test_legacy_dormant_t2_is_preserved_and_explicitly_conflicting(sample_project):
    project = migrate_project_payload(_legacy_payload(sample_project, dormant_t2=True))
    assert project.experiment_category == ExperimentCategory.FPVS_ODDBALL
    assert project.conditions[0].t2_stimulus_set_id == "preserved-t2"
    assert category_conflict_condition_ids(project) == (project.conditions[0].condition_id,)
    with pytest.raises(ValueError, match="Separate"):
        require_valid_experiment_category(project)


def test_explicit_category_is_never_reclassified(sample_project):
    sample_project.conditions[0].attentional_blink = AttentionalBlinkSettings()
    restored = ProjectFile.model_validate(sample_project.model_dump())
    assert restored.experiment_category == ExperimentCategory.FPVS_ODDBALL
    assert category_conflict_condition_ids(restored) == (restored.conditions[0].condition_id,)


def test_mixed_legacy_loads_but_cannot_save_export_or_compile_a_subset(
    sample_project, sample_project_root, tmp_path
):
    payload = _legacy_payload(sample_project, mixed=True)
    source = sample_project_root / "project.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    project = load_project_file(source)
    original = source.read_bytes()
    for path in (source, tmp_path / "new-parent" / "project.json"):
        with pytest.raises(ValueError, match="Separate"):
            save_project_file(project, path)
    assert source.read_bytes() == original
    assert not (tmp_path / "new-parent").exists()
    for selected in (project.conditions[0].condition_id, "standard"):
        with pytest.raises(CompileError, match="Separate"):
            compile_run_spec(project, refresh_hz=60, condition_id=selected)
        with pytest.raises(CompileError, match="Separate"):
            compile_session_plan(project, refresh_hz=60, condition_ids=[selected])
    assert any("Separate" in issue.message for issue in validate_project(project).issues)
    with pytest.raises(ProjectConfigError, match="Separate"):
        export_project_config(project, None)
    write_stimulus_manifest(sample_project_root, create_empty_manifest(project.meta.project_id))
    bundle = tmp_path / "mixed.fpvsbundle"
    with pytest.raises(ProjectBundleError, match="Separate"):
        export_project_bundle(sample_project_root, bundle)
    assert not bundle.exists()


@pytest.mark.parametrize("category", [ExperimentCategory.FPVS_ODDBALL,
                                     ExperimentCategory.ATTENTIONAL_BLINK])
def test_new_category_projects_persist_defaults_and_roundtrip_config(tmp_path, category):
    scaffold = create_project(tmp_path / "projects", "Created", experiment_category=category)
    project = scaffold.project
    assert load_project_file(scaffold.project_root / "project.json").experiment_category == category
    is_ab = category == ExperimentCategory.ATTENTIONAL_BLINK
    assert project.settings.protocol.base_hz == (10 if is_ab else 6)
    assert project.settings.protocol.oddball_every_n == (20 if is_ab else 5)
    assert project.settings.condition_defaults.oddball_cycle_repeats_per_sequence == 146
    assert project.settings.condition_defaults.duty_cycle_mode == DutyCycleMode.CONTINUOUS
    config = export_project_config(project, None)
    config_path = tmp_path / "portable.fpvsconfig"
    write_project_config(config_path, config)
    imported = create_project_from_config(tmp_path / "imports", read_project_config(config_path))
    assert imported.project.experiment_category == category
    assert imported.project.settings.protocol == project.settings.protocol


def test_placeholder_creation_and_compilation_are_blocked_before_writes(tmp_path):
    with pytest.raises(ValueError, match="coming soon"):
        create_project(tmp_path / "absent", "FPVS", experiment_category=ExperimentCategory.FPVS)
    assert not (tmp_path / "absent").exists()
    placeholder = build_starter_project("Draft").model_copy(
        update={"experiment_category": ExperimentCategory.FPVS}
    )
    with pytest.raises(CompileError, match="coming soon"):
        compile_run_spec(placeholder, refresh_hz=60)
    with pytest.raises(ValueError, match="coming soon"):
        save_project_file(placeholder, tmp_path / "placeholder.json")


def test_legacy_config_classification_and_mixed_import_guard(sample_project, tmp_path):
    payload = export_project_config(sample_project, None).model_dump(mode="json")
    payload.pop("experiment_category")
    payload["conditions"][0]["attentional_blink"] = {}
    config = ProjectConfigFile.model_validate(payload)
    assert config.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
    standard = config.conditions[0].model_copy(
        update={"condition_id": "other", "attentional_blink": None}
    )
    config.conditions.append(standard)
    with pytest.raises(ProjectConfigError, match="Separate"):
        create_project_from_config(tmp_path / "absent", config)
    with pytest.raises(ProjectConfigError, match="Separate"):
        write_project_config(tmp_path / "absent" / "mixed.fpvsconfig", config)
    assert not (tmp_path / "absent").exists()


def test_templates_filter_and_refuse_cross_category_application(tmp_path):
    profiles = built_in_condition_template_profiles()
    ab_profile = next(
        profile for profile in profiles if profile.profile_id == ATTENTIONAL_BLINK_PROFILE_ID
    )
    assert list_condition_template_profiles(
        tmp_path, experiment_category=ExperimentCategory.ATTENTIONAL_BLINK
    ) == [p for p in profiles if p.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK]
    oddball = build_starter_project("Oddball")
    with pytest.raises(ValueError, match="belongs to"):
        apply_condition_template_profile_to_settings(
            oddball.settings, ab_profile, experiment_category=oddball.experiment_category
        )
    with pytest.raises(ValueError, match="belongs to"):
        build_starter_project("Wrong", condition_template_profile=ab_profile)
    with pytest.raises(ValueError, match="belongs to"):
        build_starter_project("Wrong", condition_template_profile=profiles[0],
                              experiment_category=ExperimentCategory.ATTENTIONAL_BLINK)
    require_profile_category(ab_profile, ExperimentCategory.ATTENTIONAL_BLINK)
