"""Exact, opt-in target/mask/omitted-target markers without scene or RNG changes."""

import pytest
from tests.unit.test_masking import catch_project
from tests.unit.test_masking_catch_conditions import explicit_catch_project, ordinary_project

from fpvs_studio.core.compiler import CompileError, compile_run_spec, compile_session_plan
from fpvs_studio.core.compiler_masking import compile_masking_run
from fpvs_studio.core.enums import ProjectSchemaVersion
from fpvs_studio.core.masking import (
    MaskingEventTriggers,
    MaskingSettings,
    add_masking_catch_condition,
    condition_masking,
)
from fpvs_studio.core.validation import validate_project


def enable_markers(project):
    project.schema_version = ProjectSchemaVersion.V1_10
    for modifier in project.condition_modifiers:
        modifier.masking.event_triggers = MaskingEventTriggers()
    return project


@pytest.mark.parametrize("variant", ["color", "faces", "number"])
@pytest.mark.parametrize("soa_index, soa_frames", [(1, 1), (2, 3), (3, 6)])
@pytest.mark.parametrize("kind", ["ordinary", "explicit", "automatic"])
def test_exact_target_mask_and_catch_slot_markers_preserve_every_scene_field(
    tmp_path, variant, soa_index, soa_frames, kind,
):
    factory = {"ordinary": ordinary_project, "explicit": explicit_catch_project,
               "automatic": catch_project}[kind]
    project = factory()
    source = next(item for item in project.conditions
                  if item.condition_id == f"{variant}-{soa_index}")
    condition = next(item for item in project.conditions
                     if item.condition_id == f"{variant}-catch") if kind == "explicit" else source
    condition.oddball_cycle_repeats_per_sequence = 40
    settings = condition_masking(project, source)
    arguments = dict(refresh_hz=60, project_root=tmp_path, random_seed=79, run_id="markers",
                     is_catch_trial=kind != "ordinary")
    original = compile_masking_run(project, condition, settings, **arguments)
    assert len(original.trigger_events) == 1
    enable_markers(project)
    compiled = compile_masking_run(project, condition, settings, **arguments)
    assert compiled.model_copy(update={"trigger_events": original.trigger_events}) == original
    expected = [(0, compiled.condition.trigger_code, "condition_start")]
    target_code, target_label = ((55, "oddball_onset") if kind == "ordinary"
                                 else (57, "catch_slot_onset"))
    for onset in range(48, 2400, 60):
        expected.extend([(onset, target_code, target_label),
                         (onset + soa_frames, 56, "mask_onset")])
    assert [(event.frame_index, event.code, event.label)
            for event in compiled.trigger_events] == expected
    frames = [event.frame_index for event in compiled.trigger_events]
    assert frames == sorted(frames) and len(frames) == len(set(frames)) == 81
    assert all(0 <= frame < compiled.display.total_frames for frame in frames)
    mask_frames = [event.start_frame for event in compiled.scene_stream.events
                   if event.role == "mask"]
    assert mask_frames == [event.frame_index for event in compiled.trigger_events
                           if event.label == "mask_onset"]
    if kind != "ordinary":
        assert not any(event.code == 55 for event in compiled.trigger_events)
        assert compiled.scene_stream.target_id is None


@pytest.mark.parametrize("factory", [ordinary_project, explicit_catch_project, catch_project])
def test_marker_opt_in_does_not_change_session_order_seeds_tasks_or_scenes(tmp_path, factory):
    project = factory()
    original = compile_session_plan(project, project_root=tmp_path, refresh_hz=60, random_seed=923)
    enable_markers(project)
    compiled = compile_session_plan(project, project_root=tmp_path, refresh_hz=60, random_seed=923)
    for before, after in zip(original.ordered_entries(), compiled.ordered_entries(), strict=True):
        assert len(after.run_spec.trigger_events) == 3
        after.run_spec.trigger_events = before.run_spec.trigger_events
    assert compiled == original


def test_optional_marker_settings_serialize_only_when_enabled():
    settings = MaskingSettings()
    assert "event_triggers" not in settings.model_dump()
    assert MaskingSettings.model_validate_json(settings.model_dump_json()) == settings
    settings.event_triggers = MaskingEventTriggers()
    assert settings.model_dump()["event_triggers"] == {
        "mask_onset_code": 56, "catch_slot_onset_code": 57,
    }
    assert MaskingSettings.model_validate_json(settings.model_dump_json()) == settings


@pytest.mark.parametrize("field", ["mask_onset_code", "catch_slot_onset_code"])
@pytest.mark.parametrize("value", [0, 256, True, 56.0, "56"])
def test_marker_codes_are_strict_byte_event_codes(field, value):
    with pytest.raises(ValueError):
        MaskingEventTriggers(**{field: value})


def test_marker_codes_must_be_distinct():
    with pytest.raises(ValueError, match="must be distinct"):
        MaskingEventTriggers(mask_onset_code=57, catch_slot_onset_code=57)


@pytest.mark.parametrize("collision", ["target", "mask", "catch_slot", "automatic"])
def test_markers_cannot_collide_with_condition_or_automatic_catch_codes(tmp_path, collision):
    project = enable_markers(catch_project())
    if collision == "automatic":
        for modifier in project.condition_modifiers:
            if modifier.masking.variant == "color":
                modifier.masking.catch_trial.trigger_code = 56
    else:
        project.conditions[0].trigger_code = {"target": 55, "mask": 56, "catch_slot": 57}[collision]
    with pytest.raises(CompileError, match="condition-start and automatic catch"):
        compile_run_spec(project, project_root=tmp_path, refresh_hz=60, condition_id="color-1")
    assert any("condition-start and automatic catch" in issue.message
               for issue in validate_project(project, refresh_hz=60).issues)


@pytest.mark.parametrize("code", [55, 57, 0, 256, True])
def test_mutated_marker_models_are_revalidated_before_compilation(tmp_path, code):
    project = enable_markers(ordinary_project())
    condition_masking(project, project.conditions[0]).event_triggers.mask_onset_code = code
    with pytest.raises(CompileError):
        compile_run_spec(project, project_root=tmp_path, refresh_hz=60, condition_id="color-1")


def test_target_marker_reuses_project_policy_and_nonstandard_override(tmp_path):
    project = enable_markers(ordinary_project())
    project.settings.triggers.oddball_trigger_code = 60
    with pytest.raises(CompileError, match="locked to 55"):
        compile_run_spec(project, project_root=tmp_path, refresh_hz=60, condition_id="color-1")
    project.settings.triggers.allow_nonstandard_oddball_trigger_code = True
    compiled = compile_run_spec(project, project_root=tmp_path, refresh_hz=60,
                                condition_id="color-1")
    assert [event.code for event in compiled.trigger_events] == [1, 60, 56]
    project.settings.triggers.oddball_trigger_code = True
    with pytest.raises(CompileError, match="integer"):
        compile_run_spec(project, project_root=tmp_path, refresh_hz=60, condition_id="color-1")


@pytest.mark.parametrize("factory", [explicit_catch_project, catch_project])
@pytest.mark.parametrize("mismatch", [None, MaskingEventTriggers(mask_onset_code=58)])
def test_sampled_catch_soa_sources_cannot_silently_change_marker_intent(
    tmp_path, factory, mismatch,
):
    project = enable_markers(factory())
    source = next(item for item in project.conditions if item.condition_id == "color-2")
    condition_masking(project, source).event_triggers = mismatch
    catch_id = "color-catch" if factory is explicit_catch_project else "color-1"
    with pytest.raises(CompileError, match="same event trigger settings"):
        compile_run_spec(project, project_root=tmp_path, refresh_hz=60, condition_id=catch_id)
    with pytest.raises(CompileError, match="same event trigger settings"):
        compile_session_plan(project, project_root=tmp_path, refresh_hz=60, random_seed=3)


def test_disabled_sampled_source_cannot_drop_the_explicit_catch_marker_request(tmp_path):
    project = enable_markers(explicit_catch_project())
    condition_masking(project, project.conditions[1]).event_triggers = None
    with pytest.raises(CompileError, match="same event trigger settings"):
        compile_session_plan(project, project_root=tmp_path, refresh_hz=60,
                             condition_ids=["color-2", "color-catch"], random_seed=6)


def test_add_catch_preserves_marker_schema_and_reserves_active_event_codes():
    project = enable_markers(ordinary_project())
    added, identity = add_masking_catch_condition(project, "color-1")
    assert added.schema_version == ProjectSchemaVersion.V1_10
    catch = next(item for item in added.conditions if item.condition_id == identity)
    assert condition_masking(added, catch).event_triggers is not None
    for code in (55, 56, 57):
        with pytest.raises(ValueError, match="already used"):
            add_masking_catch_condition(project, "color-1", trigger_code=code)
