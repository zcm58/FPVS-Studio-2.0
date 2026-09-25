"""Visible catch-condition identity, SOA selection and backward-compatible authoring."""

from collections import Counter

import pytest
from tests.unit.test_masking import catch_project

from fpvs_studio.core.compiler import CompileError, compile_run_spec, compile_session_plan
from fpvs_studio.core.enums import ProjectSchemaVersion
from fpvs_studio.core.masking import (
    MaskingCatchTrialSettings,
    add_masking_catch_condition,
    condition_masking,
    masking_catch_condition_block_reason,
)
from fpvs_studio.core.masking_presets import create_masking_modifier
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.modifier_presets import ModifierPreset, save_modifier_preset
from fpvs_studio.core.project_config import (
    ProjectConfigFile,
    create_project_from_config,
    export_project_config,
)
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.core.validation import validate_project


def ordinary_project():
    project = catch_project()
    for modifier in project.condition_modifiers:
        modifier.masking.catch_trial = None
    project.schema_version = ProjectSchemaVersion.V1_7
    return project


def explicit_catch_project():
    project = ordinary_project()
    for variant in ("color", "faces", "number"):
        project, _ = add_masking_catch_condition(project, f"{variant}-1")
    return project


def test_add_catch_creates_real_conditions_without_duplicating_modifiers_or_changing_source():
    source = ordinary_project()
    original = source.model_dump()
    project = source
    for variant, code in (("color", 10), ("faces", 11), ("number", 12)):
        assert masking_catch_condition_block_reason(project, f"{variant}-1") is None
        project, identity = add_masking_catch_condition(project, f"{variant}-1")
        assert identity == f"{variant}-catch"
        catch = next(condition for condition in project.conditions
                     if condition.condition_id == identity)
        assert catch.name == f"{variant.capitalize()} catch"
        assert catch.trigger_code == code
        assert catch.masking_catch
        regular = next(item for item in project.conditions if item.condition_id == f"{variant}-1")
        assert catch.pre_task_bindings == regular.pre_task_bindings
        assert catch.post_task_bindings == regular.post_task_bindings
    assert len(project.conditions) == 12
    assert [condition.trigger_code for condition in project.conditions] == [
        1, 2, 3, 10, 4, 5, 6, 11, 7, 8, 9, 12,
    ]
    assert [condition.order_index for condition in project.conditions] == list(range(12))
    assert project.schema_version == ProjectSchemaVersion.V1_9
    assert project.task_modules == source.task_modules
    assert project.condition_modifiers == source.condition_modifiers
    assert source.model_dump() == original


def test_explicit_catch_blocks_have_30_runs_and_12_true_condition_identities(tmp_path):
    project = explicit_catch_project()
    orders, positions, catch_soas = set(), set(), set()
    authored = project.model_dump()
    for seed in range(24):
        plan = compile_session_plan(project, project_root=tmp_path, refresh_hz=60, random_seed=seed)
        assert plan.total_runs == 30
        assert Counter(entry.condition_id for entry in plan.ordered_entries()) == {
            condition.condition_id: 1 if condition.masking_catch else 3
            for condition in project.conditions
        }
        marker_counts = Counter(entry.run_spec.condition.trigger_code
                                for entry in plan.ordered_entries())
        assert marker_counts == {
            **dict.fromkeys(range(1, 10), 3), **dict.fromkeys(range(10, 13), 1),
        }
        orders.add(tuple(block.entries[0].condition_id.split("-")[0] for block in plan.blocks))
        for block in plan.blocks:
            assert len(block.entries) == 10
            assert len({entry.condition_id.split("-")[0] for entry in block.entries}) == 1
            catches = [entry for entry in block.entries
                       if entry.run_spec.scene_stream.is_catch_trial]
            catch, = catches
            positions.add(catch.index_within_block)
            catch_soas.add(catch.run_spec.scene_stream.soa_frames)
            assert catch.condition_id.endswith("-catch")
            assert catch.condition_name.endswith(" catch")
            assert catch.run_spec.scene_stream.target_id is None
            assert not any(event.role == "target" for event in catch.run_spec.scene_stream.events)
            ordinary = [entry for entry in block.entries if entry not in catches]
            for start in (0, 3, 6):
                assert {entry.run_spec.scene_stream.soa_frames
                        for entry in ordinary[start:start + 3]} == {1, 3, 6}
        assert plan == compile_session_plan(
            project, project_root=tmp_path, refresh_hz=60, random_seed=seed,
        )
    assert len(orders) == 6
    assert positions == set(range(10))
    assert catch_soas == {1, 3, 6}
    assert project.model_dump() == authored


def test_catch_uses_selected_variant_soas_and_runs_alone_from_the_project_pool(tmp_path):
    project = explicit_catch_project()
    solo_soas, direct_soas = set(), set()
    for seed in range(16):
        selected = compile_session_plan(
            project, project_root=tmp_path, refresh_hz=60, random_seed=seed,
            condition_ids=["color-2", "color-catch"],
        )
        assert selected.total_runs == 4
        assert {entry.run_spec.scene_stream.soa_frames
                for entry in selected.ordered_entries()} == {3}
        solo = compile_session_plan(
            project, project_root=tmp_path, refresh_hz=60, random_seed=seed,
            condition_ids=["color-catch"],
        )
        assert solo.total_runs == 1
        solo_soas.add(solo.ordered_entries()[0].run_spec.scene_stream.soa_frames)
        direct = compile_run_spec(
            project, project_root=tmp_path, refresh_hz=60, random_seed=seed,
            condition_id="color-catch",
        )
        assert direct.condition.condition_id == "color-catch"
        assert direct.condition.trigger_code == 10
        assert direct.scene_stream.target_id is None and direct.scene_stream.is_catch_trial
        direct_soas.add(direct.scene_stream.soa_frames)
    assert solo_soas == direct_soas == {1, 3, 6}
    ordinary_only = compile_session_plan(
        project, project_root=tmp_path, refresh_hz=60,
        condition_ids=[condition.condition_id for condition in project.conditions
                       if not condition.masking_catch],
    )
    assert ordinary_only.total_runs == 27
    assert not any(entry.run_spec.scene_stream.is_catch_trial
                   for entry in ordinary_only.ordered_entries())


def test_all_standalone_soa_choices_are_validated_before_random_selection(tmp_path):
    project = explicit_catch_project()
    condition_masking(project, project.conditions[1]).soa_ms = 25
    with pytest.raises(CompileError, match="whole frames"):
        compile_run_spec(project, project_root=tmp_path, refresh_hz=60, condition_id="color-catch")
    with pytest.raises(CompileError, match="whole frames"):
        compile_session_plan(project, project_root=tmp_path, refresh_hz=60,
                             condition_ids=["color-catch"])
    valid = compile_session_plan(project, project_root=tmp_path, refresh_hz=60,
                                 condition_ids=["color-1", "color-catch"])
    assert valid.total_runs == 4


@pytest.mark.parametrize("problem, message", [
    ("automatic", "Disable automatic catch"),
    ("duplicate", "Only one explicit"),
    ("trigger", "distinct from other conditions"),
    ("no_source", "supply its SOA"),
    ("no_modifier", "requires a Masking modifier"),
])
def test_invalid_explicit_catch_designs_are_rejected(tmp_path, problem, message):
    project = explicit_catch_project()
    catch = next(condition for condition in project.conditions
                 if condition.condition_id == "color-catch")
    if problem == "automatic":
        condition_masking(project, project.conditions[0]).catch_trial = MaskingCatchTrialSettings(
            trigger_code=20,
        )
    elif problem == "duplicate":
        project.conditions.append(catch.model_copy(deep=True, update={
            "condition_id": "other-catch", "trigger_code": 13,
        }))
    elif problem == "trigger":
        catch.trigger_code = 1
    elif problem == "no_source":
        project.conditions = [condition for condition in project.conditions
                              if not condition.condition_id.startswith("color-")
                              or condition is catch]
    elif problem == "no_modifier":
        catch.pre_task_bindings = []
    report = validate_project(project, refresh_hz=60)
    assert any(message in issue.message for issue in report.issues)
    with pytest.raises(CompileError, match=message):
        compile_run_spec(project, project_root=tmp_path, refresh_hz=60, condition_id="color-catch")


def test_creation_explains_legacy_conflict_and_allocates_only_unused_markers():
    legacy = catch_project()
    assert "Disable automatic catch" in masking_catch_condition_block_reason(legacy, "color-1")
    with pytest.raises(ValueError, match="Disable automatic catch"):
        add_masking_catch_condition(legacy, "color-1")
    project = ordinary_project()
    project.conditions[0].trigger_code = 10
    created, identity = add_masking_catch_condition(project, "color-1")
    assert next(condition for condition in created.conditions
                if condition.condition_id == identity).trigger_code == 11
    assert project.conditions[0].trigger_code == 10
    assert "already has a catch" in masking_catch_condition_block_reason(created, "color-1")
    assert "ordinary Masking" in masking_catch_condition_block_reason(created, identity)
    with pytest.raises(ValueError, match="already used"):
        add_masking_catch_condition(project, "color-1", trigger_code=10)


def test_explicit_catch_project_config_roundtrip_preserves_real_condition_map(tmp_path):
    project = explicit_catch_project()
    path = tmp_path / "project.json"
    save_project_file(project, path)
    assert load_project_file(path) == project
    config = export_project_config(project, tmp_path)
    assert config.schema_version == "1.7.0"
    assert config.toolbox.event_map == {condition.name: condition.trigger_code
                                        for condition in project.conditions}
    imported = create_project_from_config(tmp_path / "imported", config)
    assert imported.project.conditions == project.conditions
    assert imported.project.schema_version == ProjectSchemaVersion.V1_9
    payload = project.model_dump(mode="json")
    payload["schema_version"] = "1.8.0"
    with pytest.raises(ValueError, match="schema 1.9.0"):
        ProjectFile.model_validate(payload)
    payload = config.model_dump(mode="json")
    payload["schema_version"] = "1.6.0"
    with pytest.raises(ValueError, match="schema 1.7.0"):
        ProjectConfigFile.model_validate(payload)


def test_noncenter_task_alignment_requires_versioned_project_config_session_and_preset(tmp_path):
    project = ordinary_project()
    project.schema_version = ProjectSchemaVersion.V1_9
    for task in project.task_modules:
        if task.steps[0].step_id == "masking-instructions":
            task.steps[0].items[0].text_alignment = "left"
    plan = compile_session_plan(project, project_root=tmp_path, refresh_hz=60, random_seed=2)
    assert plan.schema_version == "1.5.0"
    assert SessionPlan.model_validate_json(plan.model_dump_json()) == plan
    payload = plan.model_dump(mode="json")
    payload["schema_version"] = "1.3.0"
    with pytest.raises(ValueError, match="schema 1.5.0"):
        SessionPlan.model_validate(payload)
    project.schema_version = ProjectSchemaVersion.V1_8
    with pytest.raises(ValueError, match="schema 1.9.0"):
        ProjectFile.model_validate(project.model_dump())
    project.schema_version = ProjectSchemaVersion.V1_9
    config = export_project_config(project, tmp_path)
    assert config.schema_version == "1.7.0"
    payload = config.model_dump(mode="json")
    payload["schema_version"] = "1.6.0"
    with pytest.raises(ValueError, match="schema 1.7.0"):
        ProjectConfigFile.model_validate(payload)
    definition = create_masking_modifier()
    definition.task_modules[0].steps[0].items[0].text_alignment = "left"
    saved = save_modifier_preset(tmp_path / "library", definition, tmp_path, name="Left-aligned")
    assert saved.schema_version == "1.2.0"
    payload = saved.model_dump(mode="json")
    payload["schema_version"] = "1.1.0"
    with pytest.raises(ValueError, match="schema 1.2.0"):
        ModifierPreset.model_validate(payload)
