"""Modifier assignment, session baseline requirements and linked memory compilation."""

from __future__ import annotations

import pytest

from fpvs_studio.core.backward_counting import create_backward_counting_baseline_task
from fpvs_studio.core.compiler import CompileError, compile_session_plan
from fpvs_studio.core.condition_modifiers import (
    MemoryImage,
    adopt_backward_counting_modifier,
    apply_modifier_draft,
    assign_modifier,
    create_backward_counting_modifier,
    create_image_memory_modifier,
    modifier_condition_ids,
    remove_modifier,
    validate_image_memory_definition,
)
from fpvs_studio.core.enums import PresentationUnit, ProjectSchemaVersion
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.task_models import (
    BackwardCountingRole,
    ImageMemoryRole,
    TaskBinding,
    TaskFontFamily,
    TaskLayoutMode,
    TaskModule,
    TaskOccurrence,
    TaskStep,
    TaskStepKind,
)
from fpvs_studio.runtime.task_runner import _resolved_display_items


def _compile(project, root, **kwargs):
    return compile_session_plan(project, refresh_hz=60, project_root=root, **kwargs)


def _baselines(plan):
    return [
        task
        for entry in plan.ordered_entries()
        for task in entry.pre_tasks
        if task.backward_counting is not None
        and task.backward_counting.role == BackwardCountingRole.BASELINE
    ]


def _memory(root, modifier_id="image-memory"):
    targets, foils = [], []
    for index in range(8):
        image_id = f"image-{index}"
        roles = ["study", "recognition"] if index < 4 else ["recognition"]
        for role in roles:
            path = f"stimuli/task-assets/{modifier_id}-{role}/{image_id}.png"
            absolute = root / path
            absolute.parent.mkdir(parents=True, exist_ok=True)
            absolute.write_bytes(f"unique-image-content-{index}".encode())
            if role == "study":
                targets.append(MemoryImage(image_id=image_id, image_path=path))
            elif index >= 4:
                foils.append(MemoryImage(image_id=image_id, image_path=path))
    return create_image_memory_modifier(
        modifier_id=modifier_id, target_images=targets, foil_images=foils
    )


def test_modifiers_are_schema_gated_and_preserve_unrelated_conditions(multi_condition_project):
    project = multi_condition_project
    before = project.model_dump_json()
    definition = create_backward_counting_modifier(baseline_duration_seconds=30)
    assigned = assign_modifier(project, definition, [project.conditions[1].condition_id])
    assert assigned.schema_version == ProjectSchemaVersion.V1_6
    assert project.model_dump_json() == before
    assert assigned.conditions[0] == project.conditions[0]
    assert modifier_condition_ids(assigned, definition.modifier.modifier_id) == [
        project.conditions[1].condition_id
    ]
    assert assigned.task_modules[0].backward_counting.duration_seconds == 30
    assert ProjectFile.model_validate_json(assigned.model_dump_json()) == assigned
    payload = assigned.model_dump()
    payload["schema_version"] = "1.4.0"
    with pytest.raises(ValueError, match="1.6.0"):
        ProjectFile.model_validate(payload)


def test_counting_phase_instructions_are_independent():
    definition = create_backward_counting_modifier(
        instructions="Count only while images appear.",
        endpoint_prompt="Image stream endpoint?",
        baseline_instructions="Count until the baseline screen ends.",
        baseline_endpoint_prompt="Baseline endpoint?",
    )
    baseline, start, report = definition.task_modules
    assert baseline.backward_counting.instructions == "Count until the baseline screen ends."
    assert baseline.backward_counting.endpoint_prompt == "Baseline endpoint?"
    assert start.backward_counting.instructions == "Count only while images appear."
    assert report.backward_counting.endpoint_prompt == "Image stream endpoint?"


@pytest.mark.parametrize("shuffle_all", [False, True])
def test_requested_baseline_runs_before_randomized_no_load_entry_once(
    multi_condition_project,
    multi_condition_project_root,
    shuffle_all,
):
    project = multi_condition_project
    project.settings.session.randomize_across_blocks = shuffle_all
    no_load_id = (
        _compile(project, multi_condition_project_root, random_seed=83)
        .ordered_entries()[0]
        .condition_id
    )
    load_id = next(c.condition_id for c in project.conditions if c.condition_id != no_load_id)
    project = assign_modifier(
        project, create_backward_counting_modifier(baseline_duration_seconds=30), [load_id]
    )
    plan = _compile(project, multi_condition_project_root, random_seed=83)
    assert plan.ordered_entries()[0].condition_id == no_load_id
    baseline = _baselines(plan)
    assert len(baseline) == 1
    assert plan.ordered_entries()[0].pre_tasks == baseline
    assert baseline[0].backward_counting.duration_seconds == 30
    assert baseline[0].modifier.session_baseline
    assert baseline[0].modifier.requested_modifier_ids == ["backward-counting"]
    assert not _baselines(
        _compile(project, multi_condition_project_root, condition_ids=[no_load_id])
    )
    assert (
        len(_baselines(_compile(project, multi_condition_project_root, condition_ids=[load_id])))
        == 1
    )


def test_baseline_disabled_and_compatible_requirements_deduplicate(
    multi_condition_project,
    multi_condition_project_root,
):
    ids = [c.condition_id for c in multi_condition_project.conditions]
    disabled = assign_modifier(
        multi_condition_project, create_backward_counting_modifier(baseline_enabled=False), [ids[0]]
    )
    assert not _baselines(_compile(disabled, multi_condition_project_root))
    project = assign_modifier(
        multi_condition_project, create_backward_counting_modifier(modifier_id="count-a"), [ids[0]]
    )
    project = assign_modifier(
        project, create_backward_counting_modifier(modifier_id="count-b"), [ids[1]]
    )
    baseline = _baselines(_compile(project, multi_condition_project_root))
    assert len(baseline) == 1
    assert baseline[0].modifier.requested_modifier_ids == ["count-a", "count-b"]


@pytest.mark.parametrize(
    "changes",
    [
        {"subtraction_step": 7},
        {"baseline_duration_seconds": 30},
        {"start_min": 2000},
    ],
)
def test_conflicting_baselines_are_named_and_rejected(
    multi_condition_project,
    multi_condition_project_root,
    changes,
):
    project = assign_modifier(
        multi_condition_project,
        create_backward_counting_modifier(modifier_id="first", name="First counting"),
        [multi_condition_project.conditions[0].condition_id],
    )
    project = assign_modifier(
        project,
        create_backward_counting_modifier(modifier_id="second", name="Second counting", **changes),
        [multi_condition_project.conditions[1].condition_id],
    )
    with pytest.raises(CompileError, match="First counting, Second counting"):
        _compile(project, multi_condition_project_root)


def test_legacy_baseline_binding_keeps_selected_no_load_behavior_and_rejects_overlap(
    multi_condition_project,
    multi_condition_project_root,
):
    project = multi_condition_project
    baseline = create_backward_counting_baseline_task(duration_seconds=30)
    project.task_modules = [baseline]
    for condition in project.conditions:
        condition.pre_task_bindings = [
            TaskBinding(task_id=baseline.task_id, occurrence=TaskOccurrence.FIRST_SESSION_ENTRY)
        ]
    assert (
        len(
            _baselines(
                _compile(
                    project,
                    multi_condition_project_root,
                    condition_ids=[project.conditions[-1].condition_id],
                )
            )
        )
        == 1
    )
    project = assign_modifier(
        project,
        create_backward_counting_modifier(modifier_id="new-count"),
        [project.conditions[0].condition_id],
    )
    with pytest.raises(CompileError, match="Legacy baseline.*overlaps"):
        _compile(project, multi_condition_project_root)


def test_explicit_typed_legacy_adoption_preserves_saved30_and_modules(sample_project):
    definition = create_backward_counting_modifier(baseline_duration_seconds=30)
    project = sample_project.model_copy(deep=True)
    project.task_modules = definition.task_modules
    modifier = definition.modifier
    project.conditions[0].pre_task_bindings = [
        TaskBinding(
            task_id=modifier.baseline_task_id, occurrence=TaskOccurrence.FIRST_SESSION_ENTRY
        ),
        TaskBinding(task_id=modifier.pre_task_ids[0], replaces_condition_start_gate=True),
    ]
    project.conditions[0].post_task_bindings = [TaskBinding(task_id=modifier.post_task_ids[0])]
    adopted = adopt_backward_counting_modifier(
        project,
        start_task_id=modifier.pre_task_ids[0],
        report_task_id=modifier.post_task_ids[0],
        baseline_task_id=modifier.baseline_task_id,
    )
    assert adopted.task_modules == project.task_modules
    assert adopted.task_modules[0].backward_counting.duration_seconds == 30
    assert len(project.conditions[0].pre_task_bindings) == 2
    assert len(adopted.conditions[0].pre_task_bindings) == 1


def test_assignment_conflict_replacement_and_shared_scope_are_explicit(multi_condition_project):
    ids = [c.condition_id for c in multi_condition_project.conditions[:2]]
    project = assign_modifier(multi_condition_project, create_backward_counting_modifier(), ids)
    with pytest.raises(ValueError, match="already has a sustained activity"):
        assign_modifier(project, create_image_memory_modifier(), [ids[0]])
    with pytest.raises(ValueError, match="Copy this shared modifier"):
        assign_modifier(project, create_backward_counting_modifier(subtraction_step=7), [ids[0]])
    replaced = assign_modifier(project, create_image_memory_modifier(), [ids[0]], replace=True)
    assert modifier_condition_ids(replaced, "backward-counting") == [ids[1]]
    assert modifier_condition_ids(replaced, "image-memory") == [ids[0]]
    removed = remove_modifier(replaced, "image-memory", [ids[0]])
    assert removed.conditions[0].pre_task_bindings == []
    assert removed.conditions[1] == project.conditions[1]


@pytest.mark.parametrize(
    "factory", [create_backward_counting_modifier, create_image_memory_modifier]
)
@pytest.mark.parametrize("replace", [False, True])
def test_draft_detaches_only_selected_condition_and_preserves_shared_bindings(
    multi_condition_project, factory, replace,
):
    ids = [condition.condition_id for condition in multi_condition_project.conditions[:2]]
    shared = factory()
    project = assign_modifier(multi_condition_project, shared, ids)
    other = project.conditions[1]
    other.pre_task_bindings[0].occurrence = TaskOccurrence.FIRST_SESSION_ENTRY
    other.pre_task_bindings[0].replaces_condition_start_gate = False
    custom = TaskModule(
        task_id="custom", name="Custom",
        steps=[TaskStep(
            step_id="instructions", kind=TaskStepKind.INSTRUCTION,
            text="Keep me.", continue_key="space",
        )],
    )
    project.task_modules.append(custom)
    other.pre_task_bindings.append(TaskBinding(task_id=custom.task_id))
    other.post_task_bindings.insert(0, TaskBinding(task_id=custom.task_id))
    original = project.model_dump_json()
    key = shared.modifier.modifier_id
    definitions = {key: shared}
    scopes = {key: [ids[1]]}
    if replace:
        replacement = create_backward_counting_modifier(modifier_id="replacement")
        definitions[replacement.modifier.modifier_id] = replacement
        scopes[replacement.modifier.modifier_id] = [ids[0]]

    result = apply_modifier_draft(project, definitions, scopes)

    assert modifier_condition_ids(result, key) == [ids[1]]
    assert result.conditions[1] == other
    assert result.conditions[2:] == project.conditions[2:]
    assert project.model_dump_json() == original
    assert all(task in result.task_modules for task in shared.task_modules)
    if replace:
        assert modifier_condition_ids(result, "replacement") == [ids[0]]
    else:
        assert not result.conditions[0].pre_task_bindings
        assert not result.conditions[0].post_task_bindings
        assert result.task_modules == project.task_modules
        assert result.condition_modifiers == project.condition_modifiers
    assert ProjectFile.model_validate_json(result.model_dump_json()) == result


def test_draft_can_add_shared_modifier_without_rebuilding_existing_binding(multi_condition_project):
    ids = [condition.condition_id for condition in multi_condition_project.conditions[:2]]
    definition = create_backward_counting_modifier()
    key = definition.modifier.modifier_id
    project = assign_modifier(multi_condition_project, definition, [ids[0]])
    project.conditions[0].pre_task_bindings[0].occurrence = TaskOccurrence.FIRST_SESSION_ENTRY

    result = apply_modifier_draft(project, {key: definition}, {key: ids})

    assert modifier_condition_ids(result, key) == ids
    assert result.conditions[0] == project.conditions[0]


def test_draft_last_removal_keeps_custom_tasks_and_other_conditions(multi_condition_project):
    definition = create_backward_counting_modifier()
    ids = [condition.condition_id for condition in multi_condition_project.conditions[:2]]
    project = assign_modifier(multi_condition_project, definition, [ids[0]])
    custom = TaskModule(
        task_id="custom", name="Custom",
        steps=[TaskStep(
            step_id="instructions", kind=TaskStepKind.INSTRUCTION,
            text="Keep me.", continue_key="space",
        )],
    )
    project.task_modules.append(custom)
    project.conditions[0].pre_task_bindings.insert(0, TaskBinding(task_id=custom.task_id))
    other = create_image_memory_modifier()
    project = assign_modifier(project, other, [ids[1]])
    key = other.modifier.modifier_id

    result = apply_modifier_draft(project, {key: other}, {key: [ids[1]]})

    assert result.conditions[0].pre_task_bindings == [TaskBinding(task_id=custom.task_id)]
    assert not result.conditions[0].post_task_bindings
    assert result.conditions[1:] == project.conditions[1:]
    assert result.task_modules == [custom, *other.task_modules]
    assert result.condition_modifiers == [other.modifier]


def test_draft_noop_and_explicit_shared_settings_edit(multi_condition_project):
    ids = [condition.condition_id for condition in multi_condition_project.conditions[:2]]
    definition = create_backward_counting_modifier()
    key = definition.modifier.modifier_id
    project = assign_modifier(multi_condition_project, definition, ids)
    assert apply_modifier_draft(project, {key: definition}, {key: ids}) == project

    edited = create_backward_counting_modifier(subtraction_step=7)
    result = apply_modifier_draft(project, {key: edited}, {key: ids})
    assert modifier_condition_ids(result, key) == ids
    assert result.task_modules == edited.task_modules
    assert project.task_modules == definition.task_modules


def test_memory_requires_real_complete_media(sample_project, sample_project_root):
    project = assign_modifier(
        sample_project, create_image_memory_modifier(), [sample_project.conditions[0].condition_id]
    )
    with pytest.raises(CompileError, match="complete study and recognition"):
        _compile(project, sample_project_root)


def test_memory_structural_validation_accepts_only_consistent_incomplete_drafts():
    definition = create_image_memory_modifier()
    validate_image_memory_definition(definition, allow_incomplete=True)
    with pytest.raises(ValueError, match="complete study and recognition"):
        validate_image_memory_definition(definition)
    partial = create_image_memory_modifier(
        target_images=[
            MemoryImage(
                image_id="one",
                image_path="stimuli/task-assets/image-memory-study/one.png",
            )
        ]
    )
    validate_image_memory_definition(partial, allow_incomplete=True)
    with pytest.raises(ValueError, match="four targets"):
        validate_image_memory_definition(partial)
    partial.task_modules[1].steps[0].max_selections = 4
    with pytest.raises(ValueError, match="recognition requires"):
        validate_image_memory_definition(partial, allow_incomplete=True)


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_selections", 8),
        ("repeat_count", 2),
        ("max_attempts", 2),
        ("submission_mode", "immediate"),
    ],
)
def test_memory_advanced_response_edits_use_the_compiler_structural_rules(
    sample_project,
    sample_project_root,
    field,
    value,
):
    definition = _memory(sample_project_root)
    validate_image_memory_definition(definition)
    setattr(definition.task_modules[1].steps[0], field, value)
    with pytest.raises(ValueError):
        validate_image_memory_definition(definition)
    project = assign_modifier(
        sample_project, _memory(sample_project_root), [sample_project.conditions[0].condition_id]
    )
    setattr(project.task_modules[1].steps[0], field, value)
    with pytest.raises(CompileError):
        _compile(project, sample_project_root)


def test_memory_structural_validation_reads_no_assets_and_preserves_layout_settings(
    sample_project_root,
):
    definition = _memory(sample_project_root)
    definition.task_modules[0].steps[0].text = "Retain authored study instructions."
    definition.task_modules[0].steps[0].columns = 4
    definition.task_modules[1].steps[0].columns = 2
    before = definition.model_dump_json()
    for task in definition.task_modules:
        for step in task.steps:
            for item in step.items:
                (sample_project_root / item.image_path).unlink()
    validate_image_memory_definition(definition)
    assert definition.model_dump_json() == before


def test_memory_compiles_linked_orders_and_never_changes_run_schedule(
    sample_project,
    sample_project_root,
):
    ordinary = _compile(sample_project, sample_project_root, random_seed=21)
    definition = _memory(sample_project_root)
    project = assign_modifier(
        sample_project, definition, [sample_project.conditions[0].condition_id]
    )
    first = _compile(project, sample_project_root, random_seed=21)
    repeated = _compile(project, sample_project_root, random_seed=21)
    different = _compile(project, sample_project_root, random_seed=22)
    assert first == repeated
    for original, entry in zip(ordinary.ordered_entries(), first.ordered_entries(), strict=True):
        assert original.run_spec == entry.run_spec
        study, report = entry.pre_tasks[-1], entry.post_tasks[0]
        assert study.image_memory.role == ImageMemoryRole.STUDY
        assert report.image_memory.role == ImageMemoryRole.RECOGNITION
        assert study.image_memory.model_dump(exclude={"role"}) == report.image_memory.model_dump(
            exclude={"role"}
        )
        assert [i.item_id for i in study.steps[0].items] == study.image_memory.study_order
        assert [i.item_id for i in report.steps[0].items] == study.image_memory.recognition_order
        assert all(i.selectable for i in report.steps[0].items)
        assert report.steps[0].min_selections == report.steps[0].max_selections == 4
        assert not entry.show_condition_start_gate
    assert first.ordered_entries()[0].post_tasks[0].image_memory.recognition_order != (
        different.ordered_entries()[0].post_tasks[0].image_memory.recognition_order
    )


def test_memory_rejects_target_mismatch_and_nonunique_foils(sample_project, sample_project_root):
    definition = _memory(sample_project_root)
    project = assign_modifier(
        sample_project, definition, [sample_project.conditions[0].condition_id]
    )
    report_items = project.task_modules[1].steps[0].items
    target = sample_project_root / report_items[0].image_path
    target.write_bytes(b"wrong-target")
    with pytest.raises(CompileError, match="identical images"):
        _compile(project, sample_project_root)
    target.write_bytes(b"unique-image-content-0")
    (sample_project_root / report_items[-1].image_path).write_bytes(target.read_bytes())
    with pytest.raises(CompileError, match="eight distinct"):
        _compile(project, sample_project_root)


def test_memory_exact_layout_randomizes_identities_across_preserved_display_slots(
    sample_project,
    sample_project_root,
):
    definition = _memory(sample_project_root)
    for task in definition.task_modules:
        step = task.steps[0]
        step.layout_mode = TaskLayoutMode.EXACT
        step.columns = None
        step.font_family = TaskFontFamily.OPEN_SANS
        for index, item in enumerate(step.items):
            item.x = -0.3 + (index % 4) * 0.2
            item.y = 0.15 - (index // 4) * 0.3
            item.width = 0.1 + index * 0.001
            item.height = 0.08 + index * 0.001
            item.unit = PresentationUnit.WINDOW_HEIGHT_FRACTION
    project = assign_modifier(
        sample_project, definition, [sample_project.conditions[0].condition_id]
    )
    before = project.model_dump_json()
    entries = [
        _compile(project, sample_project_root, random_seed=seed).ordered_entries()[0]
        for seed in (21, 22)
    ]
    for phase_index in (0, 1):
        source = definition.task_modules[phase_index].steps[0]
        identity_positions = []
        for entry in entries:
            module = entry.pre_tasks[0] if phase_index == 0 else entry.post_tasks[0]
            compiled = module.steps[0]
            resolved = _resolved_display_items(compiled, compiled.items, run_spec=entry.run_spec)
            height = entry.run_spec.display.screen_height_px
            assert [item.position_px for item in resolved] == [
                (slot.x * height, slot.y * height) for slot in source.items
            ]
            assert [item.size_px for item in resolved] == [
                (slot.width * height, slot.height * height) for slot in source.items
            ]
            assert compiled.font_family == source.font_family
            assert compiled.text == source.text
            expected_order = (
                module.image_memory.study_order
                if phase_index == 0
                else module.image_memory.recognition_order
            )
            assert [item.item_id for item in resolved] == expected_order
            identity_positions.append({item.item_id: item.position_px for item in resolved})
        assert identity_positions[0] != identity_positions[1]
    assert project.model_dump_json() == before

    legacy = project.model_copy(deep=True)
    legacy.condition_modifiers = []
    for task in legacy.task_modules:
        task.image_memory = None
        task.steps[0].randomize_options = True
    legacy_entry = _compile(legacy, sample_project_root, random_seed=21).ordered_entries()[0]
    for source_task, compiled_module in zip(
        legacy.task_modules,
        [*legacy_entry.pre_tasks, *legacy_entry.post_tasks],
        strict=True,
    ):
        assert {
            item.item_id: (item.x, item.y, item.width, item.height)
            for item in compiled_module.steps[0].items
        } == {
            item.item_id: (item.x, item.y, item.width, item.height)
            for item in source_task.steps[0].items
        }


def test_generic_surrounding_steps_are_preserved_and_illegal_order_rejected(
    sample_project,
    sample_project_root,
):
    generic = TaskModule(
        task_id="custom",
        name="Existing custom instructions",
        steps=[
            TaskStep(
                step_id="custom",
                kind=TaskStepKind.INSTRUCTION,
                text="Keep my wording.",
                continue_key="space",
            )
        ],
    )
    sample_project.task_modules = [generic]
    sample_project.conditions[0].pre_task_bindings = [TaskBinding(task_id=generic.task_id)]
    project = assign_modifier(
        sample_project,
        create_backward_counting_modifier(),
        [sample_project.conditions[0].condition_id],
    )
    plan = _compile(project, sample_project_root)
    assert plan.ordered_entries()[0].pre_tasks[1].steps[0].text == "Keep my wording."
    project.conditions[0].pre_task_bindings.reverse()
    with pytest.raises(CompileError, match="last pre-task"):
        _compile(project, sample_project_root)
