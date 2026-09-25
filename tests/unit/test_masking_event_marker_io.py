"""Versioned opt-in Masking markers survive authoring and portable project copies."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.unit.test_masking import masking_project

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.condition_modifiers import (
    adopt_backward_counting_modifier,
    assign_modifier,
    create_backward_counting_modifier,
)
from fpvs_studio.core.enums import ProjectSchemaVersion
from fpvs_studio.core.masking import MaskingEventTriggers, add_masking_catch_condition
from fpvs_studio.core.masking_presets import create_masking_modifier
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.modifier_presets import (
    ModifierPreset,
    import_modifier_definition,
    load_modifier_preset,
    modifier_preset_root,
    save_modifier_preset,
)
from fpvs_studio.core.project_bundle import export_project_bundle, import_project_bundle
from fpvs_studio.core.project_config import (
    ProjectConfigFile,
    create_project_from_config,
    export_project_config,
    read_project_config,
    write_project_config,
)
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.task_models import task_requires_text_alignment_schema
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest


def marker_project(*, catch=False, alignment=False):
    project = masking_project(("color",))
    for index, condition in enumerate(project.conditions, 1):
        condition.trigger_code = index
    for modifier in project.condition_modifiers:
        modifier.masking.event_triggers = MaskingEventTriggers(
            mask_onset_code=156, catch_slot_onset_code=157,
        )
    project.schema_version = ProjectSchemaVersion.V1_10
    if catch:
        project, _ = add_masking_catch_condition(project, "color-1")
    if alignment:
        for task in project.task_modules:
            if task.steps[0].step_id == "masking-instructions":
                task.steps[0].items[0].text_alignment = "left"
    return ProjectFile.model_validate(project.model_dump())


def assert_markers(project):
    assert project.schema_version == ProjectSchemaVersion.V1_10
    assert all(modifier.masking.event_triggers == MaskingEventTriggers(
        mask_onset_code=156, catch_slot_onset_code=157,
    ) for modifier in project.condition_modifiers if modifier.masking is not None)


@pytest.mark.parametrize("catch,alignment", [(False, False), (True, True)])
def test_project_config_and_bundle_preserve_marker_settings(tmp_path, catch, alignment):
    project = marker_project(catch=catch, alignment=alignment)
    root = tmp_path / "source"
    root.mkdir()
    save_project_file(project, root / "project.json")
    write_stimulus_manifest(root, create_empty_manifest(project.meta.project_id))
    assert load_project_file(root / "project.json") == project
    config = export_project_config(project, root)
    assert config.schema_version == "1.8.0"
    assert config.toolbox.event_map == {
        condition.name: condition.trigger_code for condition in project.conditions
    }
    assert not {55, 156, 157} & set(config.toolbox.event_map.values())
    config_path = tmp_path / "masking.fpvsconfig"
    write_project_config(config_path, config)
    assert read_project_config(config_path) == config
    imported_config = create_project_from_config(tmp_path / "config-import", config)
    assert_markers(imported_config.project)
    assert imported_config.project.condition_modifiers == project.condition_modifiers
    bundle_path = tmp_path / "masking.fpvsbundle"
    export_project_bundle(root, bundle_path)
    imported_bundle = import_project_bundle(bundle_path, tmp_path / "bundle-import")
    assert imported_bundle.project == project
    assert_markers(imported_bundle.project)
    original_plan = compile_session_plan(project, project_root=root, refresh_hz=60, random_seed=8)
    imported_plan = compile_session_plan(
        imported_bundle.project, project_root=imported_bundle.project_root,
        refresh_hz=60, random_seed=8,
    )
    assert original_plan == imported_plan
    assert original_plan.schema_version == ("1.5.0" if alignment else "1.3.0")


@pytest.mark.parametrize("version", ["1.7.0", "1.8.0", "1.9.0"])
def test_event_markers_reject_older_project_schema(version):
    payload = marker_project().model_dump(mode="json")
    payload["schema_version"] = version
    with pytest.raises(ValueError, match="event triggers require project schema 1.10.0"):
        ProjectFile.model_validate(payload)


@pytest.mark.parametrize("version", ["1.5.0", "1.6.0", "1.7.0"])
def test_event_markers_reject_older_config_schema(tmp_path, version):
    payload = export_project_config(marker_project(), tmp_path).model_dump(mode="json")
    payload["schema_version"] = version
    with pytest.raises(ValueError, match="event triggers require config schema 1.8.0"):
        ProjectConfigFile.model_validate(payload)


@pytest.mark.parametrize("alignment", [False, True])
def test_presets_copy_markers_and_reject_downversion(tmp_path, alignment):
    definition = create_masking_modifier()
    definition.modifier.masking.event_triggers = MaskingEventTriggers(
        mask_onset_code=156, catch_slot_onset_code=157,
    )
    if alignment:
        definition.task_modules[0].steps[0].items[0].text_alignment = "right"
    library = tmp_path / "library"
    saved = save_modifier_preset(library, definition, tmp_path, name="Marker-enabled Masking")
    assert saved.schema_version == "1.3.0"
    loaded = load_modifier_preset(library, saved.preset_id)
    assert loaded == saved
    (tmp_path / "recipient").mkdir()
    copied = import_modifier_definition(
        tmp_path / "recipient", loaded.definition, modifier_preset_root(library, saved.preset_id),
    )
    assert copied.modifier.modifier_id != definition.modifier.modifier_id
    assert copied.modifier.masking == definition.modifier.masking
    payload = saved.model_dump(mode="json")
    payload["schema_version"] = "1.2.0"
    with pytest.raises(ValueError, match="event triggers require modifier preset schema 1.3.0"):
        ModifierPreset.model_validate(payload)


def test_marker_assignment_upgrades_and_later_edits_preserve_project_schema():
    project = masking_project(("color",))
    definition = create_masking_modifier(modifier_id="color-1")
    definition.modifier.masking.event_triggers = MaskingEventTriggers()
    changed = assign_modifier(project, definition, ["color-1"])
    assert changed.schema_version == ProjectSchemaVersion.V1_10
    definition.modifier.masking.event_triggers = None
    disabled = assign_modifier(changed, definition, ["color-1"])
    assert disabled.schema_version == ProjectSchemaVersion.V1_10
    assert disabled.condition_modifiers[0].masking.event_triggers is None
    assert project.schema_version == ProjectSchemaVersion.V1_7


def test_legacy_counting_adoption_cannot_downgrade_marker_project():
    project = marker_project()
    definition = create_backward_counting_modifier()
    project.task_modules.extend(definition.task_modules)
    modifier = definition.modifier
    adopted = adopt_backward_counting_modifier(
        project, start_task_id=modifier.pre_task_ids[0],
        report_task_id=modifier.post_task_ids[0], baseline_task_id=modifier.baseline_task_id,
    )
    assert_markers(adopted)


def test_task_flow_edit_preserves_newer_schema_without_importing_qt():
    # Execute only the real document method and pure validation helper. No Qt import
    # or application is needed to exercise this model-only authoring transaction.
    repository = Path(__file__).resolve().parents[2]
    nodes = []
    for relative, name in (
        ("src/fpvs_studio/gui/document_conditions.py", "set_condition_task_flow"),
        ("src/fpvs_studio/gui/document_support.py", "validated_copy"),
    ):
        parsed = ast.parse((repository / relative).read_text("utf-8"))
        nodes.append(next(node for node in ast.walk(parsed)
                          if isinstance(node, ast.FunctionDef) and node.name == name))
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *nodes,
    ], type_ignores=[])
    namespace = {
        "ProjectSchemaVersion": ProjectSchemaVersion,
        "task_requires_text_alignment_schema": task_requires_text_alignment_schema,
    }
    code = compile(ast.fix_missing_locations(module), "document-model-transaction", "exec")
    exec(code, namespace)
    project = marker_project(alignment=True)
    condition = project.conditions[0]
    modules = [task.model_copy(deep=True) for task in project.task_modules]
    modules[0].steps[0].items[0].text = "Edited instructions"
    replaced = []
    document = SimpleNamespace(
        _project=project, get_condition=lambda _identity: condition,
        ordered_conditions=lambda: project.conditions,
        _reindex_conditions=lambda conditions: conditions,
        _replace_project=replaced.append,
    )
    namespace["set_condition_task_flow"](
        document, condition.condition_id, modules=modules,
        pre_bindings=condition.pre_task_bindings, post_bindings=condition.post_task_bindings,
        update_shared_modules=True,
    )
    saved, = replaced
    assert_markers(saved)
    assert saved.task_modules[0].steps[0].items[0].text == "Edited instructions"


def test_legacy_payloads_remain_opted_out_and_keep_existing_versions(tmp_path):
    project = masking_project(("color",))
    original = project.model_dump_json()
    assert "event_triggers" not in original
    path = tmp_path / "project.json"
    save_project_file(project, path)
    assert load_project_file(path).model_dump_json() == original
    assert project.schema_version == ProjectSchemaVersion.V1_7
    config = export_project_config(project, tmp_path)
    assert config.schema_version == "1.5.0" and "event_triggers" not in config.model_dump_json()
    definition = create_masking_modifier()
    preset = save_modifier_preset(tmp_path / "library", definition, tmp_path, name="Legacy")
    assert preset.schema_version == "1.1.0" and "event_triggers" not in preset.model_dump_json()
    plan = compile_session_plan(project, project_root=tmp_path, refresh_hz=60)
    assert plan.schema_version == "1.3.0"
    assert all(entry.run_spec.schema_version == "1.4.0"
               and len(entry.run_spec.trigger_events) == 1 for entry in plan.ordered_entries())
