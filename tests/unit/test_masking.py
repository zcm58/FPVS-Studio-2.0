"""Independent source-design invariants for masking compilation and task linkage."""

import json
from collections import Counter

import pytest
from PIL import Image

from fpvs_studio.core.compiler import CompileError, compile_run_spec, compile_session_plan
from fpvs_studio.core.condition_modifiers import assign_modifier
from fpvs_studio.core.enums import PresentationUnit
from fpvs_studio.core.masking_presets import apply_masking_timing_defaults, create_masking_modifier
from fpvs_studio.core.models import Condition, ProjectFile, ProjectMeta
from fpvs_studio.core.project_config import export_project_config
from fpvs_studio.core.scene_models import SceneVisual
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.validation import validate_display_refresh, validate_project
from fpvs_studio.runtime.masking_report import write_masking_plan_checkpoint
from fpvs_studio.runtime.preflight import PreflightError, preflight_session_plan


def masking_project(variants=("color", "number")):
    project = ProjectFile(
        meta=ProjectMeta(project_id="masking", name="Masking", template_id="fpvs_6hz_every5_v1")
    )
    for variant in variants:
        for index, soa in enumerate((1000 / 60, 50, 100)):
            identity = f"{variant}-{index + 1}"
            project.conditions.append(
                Condition(
                    condition_id=identity,
                    name=identity,
                    base_stimulus_set_id="modifier-owned-base",
                    oddball_stimulus_set_id="modifier-owned-target",
                    sequence_count=1,
                    order_index=len(project.conditions),
                    trigger_code=1 if variant == "color" else 3,
                )
            )
            project = assign_modifier(
                project,
                create_masking_modifier(
                    variant=variant,
                    modifier_id=identity,
                    soa_ms=soa,
                ),
                [identity],
            )
    return apply_masking_timing_defaults(project)


class ValidationEngine:
    def render_task_step(self, step, project_root):
        raise AssertionError("Preflight must not render participant tasks.")

    def validate_run_spec(self, run_spec):
        return validate_display_refresh(run_spec.display.refresh_hz, base_hz=5, oddball_every_n=5)


def test_nominal_source_frames_questions_and_independent_triplet_randomization(tmp_path):
    project = masking_project()
    report = validate_project(project, refresh_hz=60)
    assert not [issue for issue in report.issues if issue.severity.value == "error"]
    plan = compile_session_plan(project, project_root=tmp_path, refresh_hz=60, random_seed=124)
    assert plan.authored_task_flow is True
    assert len(plan.blocks) == 2
    assert plan.total_runs == 18
    preflight_session_plan(
        tmp_path, plan, engine=ValidationEngine(), runtime_options={"strict_timing": False}
    )
    for block, variant in zip(plan.blocks, ("color", "number"), strict=True):
        assert len(block.entries) == 9
        for start in (0, 3, 6):
            assert {
                entry.run_spec.scene_stream.soa_frames for entry in block.entries[start : start + 3]
            } == {1, 3, 6}
        assert [len(entry.pre_tasks) for entry in block.entries] == [1] * 9
        assert [len(entry.post_tasks) for entry in block.entries] == [1] * 8 + [2]
        previous_base = None
        for entry in block.entries:
            run, scene = entry.run_spec, entry.run_spec.scene_stream
            assert not entry.show_condition_start_gate
            assert run.display.total_frames == 2400
            assert run.condition.total_stimuli == 200
            assert [(event.frame_index, event.code) for event in run.trigger_events] == [
                (0, 1 if variant == "color" else 3)
            ]
            roles = Counter(event.role for event in scene.events)
            assert roles["base"] == 160 and roles["target"] == roles["mask"] == 40
            assert roles["fixation"] == 1
            bases = [event for event in scene.events if event.role in {"base", "mask"}]
            for index, event in enumerate(bases):
                assert event.start_frame == 12 * index + scene.soa_frames
                assert event.duration_frames == 6
                if variant == "number":
                    assert event.visual_id != previous_base
                previous_base = event.visual_id
            targets = [event for event in scene.events if event.role == "target"]
            assert [event.start_frame for event in targets] == list(range(48, 2400, 60))
            assert all(
                event.duration_frames == 1 and event.visual_id == scene.target_id
                for event in targets
            )
            question = entry.post_tasks[0].steps[1]
            assert {item.item_id for item in question.items if item.correct} == {scene.target_id}
            assert [step.step_id for step in entry.post_tasks[0].steps] == [
                "masking-pas",
                "masking-identification",
                "masking-frequency",
                "masking-break",
            ] + (["masking-break-fixation"] if entry is block.entries[-1] else [])
    assert plan == compile_session_plan(
        project, project_root=tmp_path, refresh_hz=60, random_seed=124
    )


@pytest.mark.parametrize("random_seed", [7, 124])
def test_nine_condition_markers_survive_shuffled_repeats_and_exports(tmp_path, random_seed):
    project = masking_project(("color", "faces", "number"))
    expected_codes = {
        f"{variant}-{soa_index + 1}": variant_index * 3 + soa_index + 1
        for variant_index, variant in enumerate(("color", "faces", "number"))
        for soa_index in range(3)
    }
    for condition in project.conditions:
        condition.trigger_code = expected_codes[condition.condition_id]
    for modifier in project.condition_modifiers:
        settings = modifier.masking
        if settings.variant != "faces":
            continue
        visuals = []
        for index, identity in enumerate(("object-a", "object-b", "face")):
            relative = f"stimuli/task-assets/{modifier.pre_task_ids[0]}/{identity}.png"
            path = tmp_path / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (12, 10), color=(40 + 50 * index, 60, 20)).save(path)
            visuals.append(SceneVisual(
                kind="image", visual_id=identity, image_path=relative,
                units="deg", size=(5, 5),
            ))
        settings.base_visuals = visuals[:2]
        settings.target_visuals = visuals[2:]
        settings.target_answers = {"face": "angry"}

    plan = compile_session_plan(
        project, project_root=tmp_path, refresh_hz=60, random_seed=random_seed,
    )
    preflight_session_plan(
        tmp_path, plan, engine=ValidationEngine(), runtime_options={"strict_timing": False},
    )
    assert plan.total_runs == 27
    assert Counter(entry.run_spec.condition.trigger_code for entry in plan.ordered_entries()) == {
        code: 3 for code in range(1, 10)
    }
    for block_index, block in enumerate(plan.blocks):
        expected_group_codes = set(range(3 * block_index + 1, 3 * block_index + 4))
        for start in (0, 3, 6):
            assert {
                entry.run_spec.condition.trigger_code for entry in block.entries[start:start + 3]
            } == expected_group_codes
        for entry in block.entries:
            expected = expected_codes[entry.condition_id]
            assert entry.run_spec.condition.trigger_code == expected
            assert entry.run_spec.scene_stream.soa_frames == (1, 3, 6)[(expected - 1) % 3]
            assert [
                (event.frame_index, event.code, event.label)
                for event in entry.run_spec.trigger_events
            ] == [(0, expected, "condition_start")]

    config = export_project_config(project, tmp_path)
    assert {condition.condition_id: condition.trigger_code for condition in config.conditions} == (
        expected_codes
    )
    assert config.toolbox.event_map == expected_codes
    checkpoint = write_masking_plan_checkpoint(
        tmp_path, plan, participant_number="synthetic", participant_session_number=1,
    )
    assert checkpoint is not None
    saved = json.loads(checkpoint.read_text(encoding="utf-8"))["session_plan"]
    for block in saved["blocks"]:
        for entry in block["entries"]:
            expected = expected_codes[entry["condition_id"]]
            assert entry["run_spec"]["condition"]["trigger_code"] == expected
            assert entry["run_spec"]["trigger_events"] == [
                {"frame_index": 0, "code": expected, "label": "condition_start"},
            ]


def test_inter_run_fixation_moves_only_in_compiled_plan_preserving_visual_order(tmp_path):
    project = masking_project(("color",))
    for module in project.task_modules:
        for step in module.steps:
            if step.step_id == "masking-break-fixation":
                step.duration_seconds = 3.25
                step.items[0].height = 0.035
    authored = project.model_dump()
    plan = compile_session_plan(project, project_root=tmp_path, refresh_hz=60, random_seed=5)
    entries = plan.blocks[0].entries
    visual_order = []
    for entry in entries:
        visual_order.extend(step.step_id for task in entry.pre_tasks for step in task.steps)
        visual_order.append("stream")
        visual_order.extend(step.step_id for task in entry.post_tasks for step in task.steps)
    assert visual_order[:3] == ["masking-instructions", "masking-start-fixation", "stream"]
    for stream_index in [index for index, item in enumerate(visual_order) if item == "stream"][1:]:
        assert visual_order[stream_index - 2:stream_index] == [
            "masking-break", "masking-break-fixation",
        ]
    assert visual_order[-3:] == ["masking-break", "masking-break-fixation", "masking-thanks"]
    for previous, current in zip(entries, entries[1:], strict=False):
        moved = current.pre_tasks[0]
        assert moved.phase.value == "pre_condition"
        assert moved.task_id == previous.post_tasks[-1].task_id
        assert moved.modifier == previous.post_tasks[-1].modifier
        assert moved.steps[0].duration_seconds == 3.25
        assert moved.steps[0].items[0].height == 0.035
    assert project.model_dump() == authored


@pytest.mark.parametrize("customization", ["repeat", "reorder"])
def test_incompatible_masking_fixation_relocation_is_rejected(tmp_path, customization):
    project = masking_project(("color",))
    for module in project.task_modules:
        if any(step.step_id == "masking-break-fixation" for step in module.steps):
            if customization == "repeat":
                module.repeat_count = 2
            else:
                module.steps[-2:] = reversed(module.steps[-2:])
    with pytest.raises(CompileError, match="final, timed non-response screen"):
        compile_session_plan(project, project_root=tmp_path, refresh_hz=60, random_seed=5)


def test_exact_palette_and_source_geometry():
    color = create_masking_modifier().modifier.masking
    for visual in [*color.base_visuals, *color.target_visuals, *color.mask_visuals]:
        assert visual.units == "deg"
        assert visual.size == (5, 5)
    assert color.target_visuals[0].rgb == (0.97, 0.36, 0.37)
    assert color.target_visuals[0].line_rgb == color.target_visuals[0].rgb
    assert color.target_visuals[0].edges is None
    assert color.fixation_visual.font == "Open Sans"
    number = create_masking_modifier(variant="number").modifier.masking
    assert [visual.text for visual in number.base_visuals] == list("CEFHKMNPRTVWXA")
    assert all(visual.font == "Arial Black" for visual in number.base_visuals)
    assert number.base_overlays[0].position == (0, -0.5)
    assert number.base_overlays[0].rgb == (0.4, 0.4, 0.4)


@pytest.mark.parametrize("variant", ["color", "faces", "number"])
def test_source_implicit_text_wrapping_is_explicit_before_pixel_conversion(variant):
    definition = create_masking_modifier(variant=variant)
    for task in definition.task_modules:
        for step in task.steps:
            for item in step.items:
                if item.modality.value == "text":
                    expected = 1 if item.unit == PresentationUnit.WINDOW_HEIGHT_FRACTION else 15
                    assert item.width == expected


def test_rejects_unrepresentable_refresh_missing_sources_and_old_schema(tmp_path):
    project = masking_project(("color",))
    with pytest.raises(CompileError, match="whole frames"):
        compile_run_spec(project, refresh_hz=144, condition_id="color-1", project_root=tmp_path)
    project.condition_modifiers[0].masking.base_visuals = []
    with pytest.raises(CompileError, match="nonempty"):
        compile_run_spec(project, refresh_hz=60, condition_id="color-1", project_root=tmp_path)
    payload = masking_project().model_dump()
    payload["schema_version"] = "1.6.0"
    with pytest.raises(ValueError, match="1.7.0"):
        ProjectFile.model_validate(payload)


def test_roundtrip_and_preflight_reject_changed_mask_onset(tmp_path):
    project = masking_project(("color",))
    path = tmp_path / "project.json"
    save_project_file(project, path)
    assert load_project_file(path) == project
    plan = compile_session_plan(project, project_root=tmp_path, refresh_hz=60, random_seed=5)
    scene = plan.blocks[0].entries[0].run_spec.scene_stream
    next(event for event in scene.events if event.role == "mask").start_frame += 1
    with pytest.raises(PreflightError, match="windows"):
        preflight_session_plan(
            tmp_path, plan, engine=ValidationEngine(), runtime_options={"strict_timing": False}
        )
