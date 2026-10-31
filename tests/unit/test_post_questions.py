"""Simple post-question authoring, immutable execution definitions and compatibility."""

import random

import pytest
from pydantic import ValidationError

from fpvs_studio.core.compiler import CompileError, compile_session_plan
from fpvs_studio.core.compiler_tasks import compile_condition_tasks
from fpvs_studio.core.migrations import migrate_project_payload
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.post_questions import (
    apply_post_questionnaire,
    apply_pre_questionnaire,
    compile_post_question_context,
    make_post_questionnaire,
    make_pre_questionnaire,
    make_yes_no_question,
    pre_questionnaires_for_condition,
    question_definition_version,
    remove_post_questionnaire,
    remove_pre_questionnaire,
    validate_simple_pre_questionnaire,
)
from fpvs_studio.core.project_config import (
    ProjectConfigError,
    create_project_from_config,
    export_project_config,
)
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.core.task_models import (
    PostQuestionnaireContext,
    TaskBinding,
    TaskBranchRule,
    TaskFontFamily,
    TaskModule,
    TaskModuleSpec,
    TaskOccurrence,
    TaskOption,
    TaskPhase,
    TaskQuestion,
    TaskStep,
    TaskSubmissionMode,
)


@pytest.fixture
def question_project(sample_project):
    project = sample_project.model_copy(deep=True)
    project.settings.fixation_task.enabled = False
    project.conditions.append(project.conditions[0].model_copy(deep=True, update={
        "condition_id": "houses", "name": "Houses", "order_index": 1,
    }))
    project.conditions[0].presentation_count = 3
    project.conditions[1].presentation_count = 2
    return project


def _module():
    return make_post_questionnaire([
        make_yes_no_question('Did you see a fearful face, "even briefly"?\n恐怖',
                             question_id="fearful-face"),
    ], task_id="post-questions")


def _pre_module():
    return make_pre_questionnaire([
        make_yes_no_question("Ready to begin?", question_id="ready"),
    ], task_id="pre-questions")


def test_before_questions_preserve_existing_project_schema(sample_project):
    changed = apply_pre_questionnaire(sample_project, _pre_module(), ["faces"])
    assert changed.schema_version == sample_project.schema_version
    assert ProjectFile.model_validate_json(changed.model_dump_json()) == changed
    assert "simple_post_questions" not in changed.task_modules[0].model_dump()


def test_before_questions_compile_each_presentation_without_after_export_marker(
    question_project, sample_project_root,
):
    question_project = ProjectFile.model_validate(question_project.model_dump())
    original = question_project.model_dump_json()
    baseline = compile_session_plan(
        question_project, refresh_hz=60, project_root=sample_project_root, random_seed=31,
    )
    before = apply_pre_questionnaire(question_project, _pre_module(), ["faces", "houses"])
    assert before.schema_version == question_project.schema_version
    assert question_project.model_dump_json() == original
    assert not before.task_modules[0].simple_post_questions
    assert "simple_post_questions" not in before.task_modules[0].model_dump()
    project = apply_post_questionnaire(before, _module(), ["faces"])
    plan = compile_session_plan(
        project, refresh_hz=60, project_root=sample_project_root, random_seed=31,
    )
    for entry, ordinary in zip(plan.ordered_entries(), baseline.ordered_entries(), strict=True):
        assert entry.run_spec == ordinary.run_spec
        assert [task.task_id for task in entry.pre_tasks] == ["pre-questions"]
        assert entry.pre_tasks[0].phase == TaskPhase.PRE_CONDITION
        assert entry.pre_tasks[0].post_question_context is None
        assert entry.show_condition_start_gate
        assert bool(entry.post_tasks) is (entry.condition_id == "faces")
        if entry.post_tasks:
            assert entry.post_tasks[0].post_question_context is not None
    assert SessionPlan.model_validate_json(plan.model_dump_json()) == plan
    assert ProjectFile.model_validate_json(before.model_dump_json()) == before


def test_multiple_before_and_after_question_orders_survive_apply_save_and_compile(
    sample_project, sample_project_root,
):
    before = make_pre_questionnaire([
        make_yes_no_question(f"Before {suffix}?", question_id=f"before-{suffix}")
        for suffix in ("a", "b", "c")
    ], task_id="before-survey", name="Before survey")
    after = make_post_questionnaire([
        make_yes_no_question(f"After {suffix}?", question_id=f"after-{suffix}")
        for suffix in ("a", "b", "c")
    ], task_id="after-survey", name="After survey")
    for module in (before, after):
        module.steps[0].heading = module.name
        module.steps[0].text = "Keep these participant instructions."
        module.steps[0].font_family = TaskFontFamily.OPEN_SANS
        module.steps[0].prompt_height = 0.8
        for index, question in enumerate(module.steps[0].questions):
            question.randomize_options = True
            question.required = index != 1
            question.max_text_length = 100 + index
    project = apply_pre_questionnaire(sample_project, before, ["faces"])
    project = apply_post_questionnaire(project, after, ["faces"])
    before.steps[0].questions = [before.steps[0].questions[index] for index in (2, 0, 1)]
    after.steps[0].questions = [after.steps[0].questions[index] for index in (1, 2, 0)]
    project = apply_pre_questionnaire(project, before, ["faces"])
    project = apply_post_questionnaire(project, after, ["faces"])
    path = sample_project_root / "ordered-questions.json"
    save_project_file(project, path)
    restored = load_project_file(path)
    assert restored == project
    assert {module.task_id: module for module in restored.task_modules} == {
        before.task_id: before, after.task_id: after,
    }
    baseline = compile_session_plan(
        sample_project, refresh_hz=60, project_root=sample_project_root, random_seed=31,
    )
    plan = compile_session_plan(
        restored, refresh_hz=60, project_root=sample_project_root, random_seed=31,
    )
    expected_before = ["before-c", "before-a", "before-b"]
    expected_after = ["after-b", "after-c", "after-a"]
    for entry, ordinary in zip(plan.ordered_entries(), baseline.ordered_entries(), strict=True):
        assert entry.run_spec == ordinary.run_spec
        for compiled, authored, expected_ids in (
            (entry.pre_tasks[0], before, expected_before),
            (entry.post_tasks[0], after, expected_after),
        ):
            assert compiled.task_id == authored.task_id
            assert compiled.name == authored.name
            step = compiled.steps[0]
            assert [question.question_id for question in step.questions] == expected_ids
            assert step.model_dump(exclude={
                "questions", "random_seed", "realized_item_order",
                "realized_question_option_orders",
            }) == authored.steps[0].model_dump(exclude={"questions"})
            for question, original in zip(step.questions, authored.steps[0].questions, strict=True):
                assert question.model_dump(exclude={"options"}) == original.model_dump(
                    exclude={"options"},
                )
                assert {option.option_id: option for option in question.options} == {
                    option.option_id: option for option in original.options
                }
        assert [question.question_id for question
                in entry.post_tasks[0].post_question_context.questions] == expected_after


@pytest.mark.parametrize("kind", ["counting", "memory"])
@pytest.mark.parametrize("legacy", [False, True])
def test_new_before_questions_preserve_activity_boundary_and_other_task_order(
    sample_project, sample_project_root, kind, legacy,
):
    from fpvs_studio.core.condition_modifiers import (
        assign_modifier,
        create_backward_counting_modifier,
        create_image_memory_modifier,
    )

    definition = (create_backward_counting_modifier(baseline_enabled=False) if kind == "counting"
                  else create_image_memory_modifier())
    project = assign_modifier(sample_project, definition, ["faces"])
    if legacy:
        project.condition_modifiers = []
    custom = TaskModule(task_id="custom-before", name="Existing instructions", steps=[TaskStep(
        step_id="intro", kind="instruction", text="Keep this order.", continue_key="space",
    )])
    project.task_modules.append(custom)
    project.conditions[0].pre_task_bindings.insert(0, TaskBinding(task_id=custom.task_id))
    original_post = project.conditions[0].post_task_bindings.copy()
    changed = apply_pre_questionnaire(project, _pre_module(), ["faces"])
    assert [binding.task_id for binding in changed.conditions[0].pre_task_bindings] == [
        "custom-before", "pre-questions", *definition.modifier.pre_task_ids,
    ]
    assert changed.conditions[0].post_task_bindings == original_post
    if kind == "counting":
        plan = compile_session_plan(changed, refresh_hz=60, project_root=sample_project_root)
        assert all(entry.pre_tasks[-1].backward_counting.role == "load_start"
                   for entry in plan.ordered_entries())


def test_private_before_edit_preserves_metadata_order_and_other_condition(question_project):
    module = _pre_module()
    step = module.steps[0]
    step.heading = "Original heading"
    step.text = "Original participant instructions"
    step.font_family = TaskFontFamily.OPEN_SANS
    step.prompt_x = 1.25
    step.prompt_height = 0.8
    step.submit_label = "Begin"
    step.show_footer = False
    shared = apply_pre_questionnaire(question_project, module, ["faces", "houses"])
    original = shared.model_dump_json()
    edited = module.model_copy(deep=True)
    edited.steps[0].questions[0].prompt = "Edited question?"
    private = apply_pre_questionnaire(shared, edited, ["faces"])
    assert shared.model_dump_json() == original
    first, other = private.conditions
    copy_id = first.pre_task_bindings[0].task_id
    assert copy_id != module.task_id
    assert other == shared.conditions[1]
    copied = next(item for item in private.task_modules if item.task_id == copy_id)
    expected = edited.model_copy(update={"task_id": copy_id}, deep=True)
    assert copied == expected
    assert pre_questionnaires_for_condition(private, "faces") == [copied]
    removed = remove_pre_questionnaire(private, copy_id, ["faces"])
    assert removed.conditions[0].pre_task_bindings == []
    assert removed.conditions[1] == other
    assert all(item.task_id != copy_id for item in removed.task_modules)


def test_shared_before_edit_and_removal_change_only_selected_assignments(question_project):
    shared = apply_pre_questionnaire(question_project, _pre_module(), ["faces", "houses"])
    edited = shared.task_modules[0].model_copy(deep=True)
    edited.steps[0].questions[0].prompt = "Shared change?"
    changed = apply_pre_questionnaire(shared, edited, ["faces"], scope="shared")
    assert changed.conditions[1].pre_task_bindings == []
    assert changed.conditions[0].pre_task_bindings == shared.conditions[0].pre_task_bindings
    assert changed.task_modules == [edited]
    removed = remove_pre_questionnaire(shared, "pre-questions", ["faces"])
    assert removed.conditions[0].pre_task_bindings == []
    assert removed.conditions[1] == shared.conditions[1]
    assert removed.task_modules == shared.task_modules


@pytest.mark.parametrize("change", [
    "repeat", "steps", "timeout", "retry", "branch", "image", "immediate", "occurrence",
    "gate", "cross_phase",
])
def test_before_discovery_leaves_complex_or_special_bindings_in_advanced(question_project, change):
    module = _pre_module()
    binding = TaskBinding(task_id=module.task_id)
    if change == "repeat":
        module.repeat_count = 2
    elif change == "steps":
        module.steps.append(module.steps[0].model_copy(update={"step_id": "second"}, deep=True))
    elif change == "timeout":
        module.steps[0].timeout_seconds = 3
    elif change == "retry":
        module.steps[0].max_attempts = 2
        module.steps[0].retry_on_invalid = True
    elif change == "branch":
        module.steps.append(TaskStep(
            step_id="after", kind="instruction", text="Next", continue_key="space",
        ))
        module.steps[0].branch_rules = [TaskBranchRule(
            rule_id="skip", question_id="ready", operator="answered", next_step_id="after",
        )]
    elif change == "image":
        module.steps[0].questions[0].options[0].image_path = (
            "stimuli/task-assets/pre-questions/yes.png"
        )
    elif change == "immediate":
        module.steps[0].submission_mode = TaskSubmissionMode.IMMEDIATE
    elif change == "occurrence":
        binding.occurrence = TaskOccurrence.FIRST_OCCURRENCE
    elif change == "gate":
        binding.replaces_condition_start_gate = True
    elif change == "cross_phase":
        question_project.conditions[1].post_task_bindings = [binding.model_copy()]
    question_project.task_modules.append(module)
    question_project.conditions[0].pre_task_bindings = [binding]
    original = question_project.model_dump_json()
    assert pre_questionnaires_for_condition(question_project, "faces") == []
    with pytest.raises(ValueError):
        validate_simple_pre_questionnaire(question_project, module)
    with pytest.raises(ValueError):
        apply_pre_questionnaire(question_project, _pre_module(), ["faces"])
    assert question_project.model_dump_json() == original


def test_before_discovery_excludes_modifier_owned_untyped_questionnaire(sample_project):
    from fpvs_studio.core.condition_modifiers import assign_modifier
    from fpvs_studio.core.masking_presets import create_masking_modifier

    project = assign_modifier(sample_project, create_masking_modifier(), ["faces"])
    owned_id = project.condition_modifiers[0].pre_task_ids[0]
    module = _pre_module().model_copy(update={"task_id": owned_id}, deep=True)
    project.task_modules = [module if item.task_id == owned_id else item
                            for item in project.task_modules]
    assert pre_questionnaires_for_condition(project, "faces") == []
    with pytest.raises(ValueError, match="modifier-owned"):
        validate_simple_pre_questionnaire(project, module)


def test_yes_no_factory_is_required_unscored_explicit_and_consumes_no_schedule_rng():
    before = random.getstate()
    module = _module()
    question = module.steps[0].questions[0]
    assert module.simple_post_questions
    assert module.repeat_count == 1
    assert module.steps[0].submission_mode == "explicit"
    assert module.steps[0].submit_label == "Continue"
    assert module.steps[0].timeout_seconds is None
    assert module.steps[0].duration_seconds is None
    assert question.required
    assert [(option.option_id, option.label) for option in question.options] == [
        ("yes", "Yes"), ("no", "No"),
    ]
    assert all(option.correct is None and option.score is None for option in question.options)
    assert question.correct_text is None
    assert random.getstate() == before


@pytest.mark.parametrize("kind,fields", [
    ("single_choice", {"options": [TaskOption(option_id="a", label="A")]}),
    ("multiple_choice", {"options": [TaskOption(option_id="a", label="A"),
                                      TaskOption(option_id="b", label="B")]}),
    ("short_text", {}), ("long_text", {}),
    ("numeric", {"min_value": -10, "max_value": 10, "step": 1}),
    ("rating", {"min_value": 1, "max_value": 7, "min_label": "Never", "max_label": "Always"}),
])
def test_all_existing_question_types_have_original_immutable_context(kind, fields):
    question = TaskQuestion(question_id="answer", prompt="Your answer?", kind=kind, **fields)
    module = make_post_questionnaire([question], task_id="question-types")
    context = compile_post_question_context(module, condition_id="faces", condition_name="Faces",
                                            presentation_index=2, presentation_count=3)
    assert context.questions[0].kind == kind
    assert context.questions[0].definition_version == question_definition_version(question)
    restored = PostQuestionnaireContext.model_validate_json(context.model_dump_json())
    assert restored == context
    with pytest.raises(ValidationError, match="frozen"):
        restored.condition_name = "Changed"
    with pytest.raises(ValidationError, match="frozen"):
        restored.questions[0].prompt = "Changed"


def test_each_presentation_has_original_question_context_and_no_dummy_pre_task(
    question_project, sample_project_root,
):
    project = apply_post_questionnaire(question_project, _module(), ["faces", "houses"])
    plan = compile_session_plan(project, refresh_hz=60, project_root=sample_project_root)
    assert plan.schema_version == "1.9.0"
    assert project.schema_version.value == "1.16.0"
    assert all(not condition.pre_task_bindings for condition in project.conditions)
    assert all(not entry.pre_tasks for entry in plan.ordered_entries())
    for entry in plan.ordered_entries():
        context = entry.post_tasks[0].post_question_context
        assert context.condition_name == entry.condition_name
        assert context.condition_presentation_index == entry.condition_presentation_index
        assert context.condition_presentation_count == entry.condition_presentation_count
        assert entry.post_tasks[0].repeat_count == 1
    faces = [entry for entry in plan.ordered_entries() if entry.condition_id == "faces"]
    assert [entry.post_tasks[0].post_question_context.condition_presentation_index
            for entry in faces] == [1, 2, 3]
    original = faces[0].post_tasks[0].post_question_context
    project.conditions[0].name = "Renamed condition"
    project.task_modules[0].steps[0].questions[0].prompt = "Edited after collection"
    project.task_modules[0].steps[0].questions[0].options[1].label = "Different label"
    assert original.condition_name == "Faces"
    assert original.questions[0].prompt.startswith("Did you see")
    assert original.questions[0].options[1].label == "No"
    with pytest.raises(ValidationError, match="frozen"):
        original.questions[0].options[1].label = "Changed"
    assert SessionPlan.model_validate_json(plan.model_dump_json()) == plan


def test_version_is_before_shuffle_and_only_changed_definitions_create_new_versions(sample_project):
    first = make_yes_no_question("Seen?", question_id="seen")
    first.randomize_options = True
    second = make_yes_no_question("Certain?", question_id="certain")
    module = make_post_questionnaire([first, second], task_id="survey")
    project = apply_post_questionnaire(sample_project, module, ["faces"])
    orders = set()
    for seed in range(8):
        spec = compile_condition_tasks(
            project, project.conditions[0], phase=TaskPhase.POST_CONDITION,
                                       block_index=0, block_count=1, session_seed=seed,
                                       run_id="run", project_root=None)[0]
        original = spec.post_question_context.questions[0]
        assert [option.option_id for option in original.options] == ["yes", "no"]
        assert original.definition_version == question_definition_version(first)
        orders.add(tuple(option.option_id for option in spec.steps[0].questions[0].options))
    assert len(orders) > 1
    reordered = make_post_questionnaire([second, first], task_id="survey")
    context = compile_post_question_context(reordered, condition_id="faces", condition_name="Faces",
                                            presentation_index=1, presentation_count=1)
    versions = {question.question_id: question.definition_version for question in context.questions}
    assert versions["seen"] == question_definition_version(first)
    first.options[1].label = "Not seen"
    assert question_definition_version(first) != versions["seen"]
    assert question_definition_version(second) == versions["certain"]


def test_private_edit_copies_shared_identity_and_preserves_other_tasks_and_assignments(
    question_project,
):
    custom = TaskModule(task_id="custom", name="Existing task", steps=[TaskStep(
        step_id="instructions", kind="instruction", text="Keep this", continue_key="space",
    )])
    question_project.task_modules.append(custom)
    for condition in question_project.conditions:
        condition.post_task_bindings.append(TaskBinding(task_id="custom"))
    shared = apply_post_questionnaire(question_project, _module(), ["faces", "houses"])
    before = shared.model_dump()
    edited = shared.task_modules[-1].model_copy(deep=True)
    edited.steps[0].questions[0].prompt = "Private question?"
    private = apply_post_questionnaire(shared, edited, ["faces"], scope="private")
    assert shared.model_dump() == before
    first, other = private.conditions
    assert first.post_task_bindings[0].task_id == other.post_task_bindings[0].task_id == "custom"
    assert first.post_task_bindings[1].task_id != other.post_task_bindings[1].task_id
    assert other.post_task_bindings[1].task_id == "post-questions"
    original = next(module for module in private.task_modules if module.task_id == "post-questions")
    copy = next(module for module in private.task_modules
                if module.task_id == first.post_task_bindings[1].task_id)
    assert original.steps[0].questions[0].prompt.startswith("Did you see")
    assert copy.steps[0].questions[0].question_id == original.steps[0].questions[0].question_id
    assert copy.steps[0].questions[0].prompt == "Private question?"
    unassigned = remove_post_questionnaire(private, copy.task_id, ["faces"])
    assert [binding.task_id for binding in unassigned.conditions[0].post_task_bindings] == [
        "custom",
    ]
    assert unassigned.conditions[1].post_task_bindings == other.post_task_bindings
    assert all(module.task_id != copy.task_id for module in unassigned.task_modules)


def test_explicit_shared_edit_applies_final_assignment_without_changing_unrelated_order(
    question_project,
):
    shared = apply_post_questionnaire(question_project, _module(), ["faces", "houses"])
    edited = shared.task_modules[0].model_copy(deep=True)
    edited.steps[0].questions[0].prompt = "Shared edit?"
    changed = apply_post_questionnaire(shared, edited, ["faces", "houses"], scope="shared")
    assert len(changed.task_modules) == 1
    assert changed.task_modules[0].steps[0].questions[0].prompt == "Shared edit?"
    assert all(condition.post_task_bindings[0].task_id == "post-questions"
               for condition in changed.conditions)


@pytest.mark.parametrize("change", ["module_repeat", "step_repeat", "retry", "branch", "immediate"])
def test_advanced_incompatible_new_flows_fail_clearly_without_flattening(change):
    payload = _module().model_dump()
    if change == "module_repeat":
        payload["repeat_count"] = 2
    elif change == "step_repeat":
        payload["steps"][0]["repeat_count"] = 2
    elif change == "retry":
        payload["steps"][0].update(max_attempts=2, retry_on_invalid=True)
    elif change == "branch":
        payload["steps"][0]["branch_rules"] = [{
            "rule_id": "skip", "question_id": "fearful-face", "operator": "answered",
            "next_step_id": "questions",
        }]
    else:
        payload["steps"][0]["submission_mode"] = "immediate"
    with pytest.raises(ValidationError, match="Post-condition Questions"):
        TaskModule.model_validate(payload)


def test_source_and_mutable_compiler_reject_pre_or_not_every_bindings(sample_project):
    project = apply_post_questionnaire(sample_project, _module(), ["faces"])
    payload = project.model_dump()
    payload["conditions"][0]["pre_task_bindings"] = [{"task_id": "post-questions"}]
    with pytest.raises(ValidationError, match="only run after"):
        ProjectFile.model_validate(payload)
    project.conditions[0].post_task_bindings[0].occurrence = TaskOccurrence.FIRST_OCCURRENCE
    with pytest.raises(CompileError, match="every condition presentation"):
        compile_session_plan(project, refresh_hz=60)


def test_persistence_and_portable_config_preserve_only_new_conditional_capabilities(
    sample_project, sample_project_root, tmp_path,
):
    before = sample_project.model_dump()
    project = apply_post_questionnaire(sample_project, _module(), ["faces"])
    save_project_file(project, sample_project_root / "project.json")
    restored = load_project_file(sample_project_root / "project.json")
    assert restored.task_modules[0].simple_post_questions
    assert migrate_project_payload(restored.model_dump()).schema_version.value == "1.16.0"
    config = export_project_config(restored, sample_project_root)
    assert config.schema_version == "1.14.0"
    imported = create_project_from_config(tmp_path / "imported", config)
    loaded = load_project_file(imported.project_root / "project.json")
    assert loaded.task_modules[0].simple_post_questions
    assert loaded.conditions[0].pre_task_bindings == []
    assert loaded.conditions[0].post_task_bindings[0].task_id == "post-questions"
    assert sample_project.model_dump() == before


def test_duplicate_marked_bindings_reject_source_and_config_before_import_io(
    sample_project, sample_project_root, tmp_path,
):
    project = apply_post_questionnaire(sample_project, _module(), ["faces"])
    payload = project.model_dump()
    payload["conditions"][0]["post_task_bindings"] *= 2
    with pytest.raises(ValidationError, match="bindings must be unique"):
        ProjectFile.model_validate(payload)

    config = export_project_config(project, sample_project_root)
    config.conditions[0].post_task_bindings *= 2
    target = tmp_path / "invalid-import"
    with pytest.raises(ProjectConfigError, match="once per condition presentation"):
        create_project_from_config(target, config)
    assert not target.exists()


def test_unmarked_advanced_flow_is_not_automatically_assimilated(
    sample_project, sample_project_root,
):
    module = _module()
    module.simple_post_questions = False
    module.repeat_count = 2
    sample_project.task_modules.append(module)
    sample_project.conditions[0].post_task_bindings = [TaskBinding(task_id=module.task_id)]
    plan = compile_session_plan(sample_project, refresh_hz=60, project_root=sample_project_root)
    assert plan.schema_version == "1.7.0"
    spec = plan.ordered_entries()[0].post_tasks[0]
    assert spec.post_question_context is None
    assert "post_question_context" not in spec.model_dump()
    assert "simple_post_questions" not in module.model_dump()
    assert TaskModuleSpec.model_validate_json(spec.model_dump_json()) == spec


def test_explicit_questions_coexist_with_masking_without_assimilating_modifier_answers(
    sample_project, sample_project_root,
):
    from fpvs_studio.core.condition_modifiers import assign_modifier
    from fpvs_studio.core.masking_presets import (
        apply_masking_timing_defaults,
        create_masking_modifier,
    )

    masked = apply_masking_timing_defaults(assign_modifier(
        sample_project, create_masking_modifier(), ["faces"],
    ))
    original_bindings = masked.conditions[0].post_task_bindings.copy()
    project = apply_post_questionnaire(masked, _module(), ["faces"])
    assert project.conditions[0].post_task_bindings[:-1] == original_bindings
    plan = compile_session_plan(project, refresh_hz=60, project_root=sample_project_root)
    assert plan.schema_version == "1.9.0"
    assert plan.randomization_seeds is None
    assert plan.ordering_policy is None
    for entry in plan.ordered_entries():
        marked = [task for task in entry.post_tasks if task.post_question_context is not None]
        assert [task.task_id for task in marked] == ["post-questions"]
        assert all(task.post_question_context is None for task in entry.post_tasks if task.modifier)


def test_explicit_native_ab_questions_do_not_change_recall_or_require_fpvs_seed_contract(
    sample_project, sample_project_root,
):
    from fpvs_studio.core.attentional_blink_presets import populate_attentional_blink_stream
    from fpvs_studio.core.enums import ExperimentCategory

    draft = ProjectFile(
        meta=sample_project.meta, experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
    )
    draft.settings.protocol.base_hz = 10
    native = populate_attentional_blink_stream(draft)
    native.settings.session.block_count = 1
    condition_id = native.conditions[0].condition_id
    original = native.conditions[0].post_task_bindings.copy()
    project = apply_post_questionnaire(native, _module(), [condition_id])
    assert project.conditions[0].post_task_bindings[:-1] == original
    plan = compile_session_plan(project, refresh_hz=60, project_root=sample_project_root)
    assert plan.schema_version == "1.9.0"
    assert plan.randomization_seeds is None
    assert sum(task.post_question_context is not None for entry in plan.ordered_entries()
               for task in entry.post_tasks) == 1
    assert all(task.post_question_context is None for entry in plan.ordered_entries()
               for task in entry.post_tasks if task.task_id != "post-questions")


def test_compiled_context_rejects_reinterpreted_labels_or_wrong_definition_version(sample_project):
    project = apply_post_questionnaire(sample_project, _module(), ["faces"])
    spec = compile_condition_tasks(project, project.conditions[0], phase=TaskPhase.POST_CONDITION,
                                   block_index=0, block_count=1, session_seed=3,
                                   run_id="run", project_root=None)[0]
    payload = spec.model_dump()
    payload["steps"][0]["questions"][0]["options"][1]["label"] = "Changed"
    with pytest.raises(ValidationError, match="differ from its original context"):
        TaskModuleSpec.model_validate(payload)
    payload = spec.model_dump()
    payload["post_question_context"]["questions"][0]["definition_version"] = "0" * 64
    with pytest.raises(ValidationError, match="version does not match"):
        TaskModuleSpec.model_validate(payload)


def test_compiled_simple_context_cannot_be_moved_before_the_stream(
    sample_project, sample_project_root,
):
    project = apply_post_questionnaire(sample_project, _module(), ["faces"])
    plan = compile_session_plan(project, refresh_hz=60, project_root=sample_project_root)
    payload = plan.model_dump()
    entry = payload["blocks"][0]["entries"][0]
    entry["pre_tasks"] = entry.pop("post_tasks")
    with pytest.raises(ValidationError, match="post-condition task list"):
        SessionPlan.model_validate(payload)


def test_compiled_original_question_sequence_cannot_be_reordered_without_its_context(
    sample_project,
):
    module = make_post_questionnaire([
        make_yes_no_question("First?", question_id="first"),
        make_yes_no_question("Second?", question_id="second"),
    ], task_id="survey")
    project = apply_post_questionnaire(sample_project, module, ["faces"])
    spec = compile_condition_tasks(
        project, project.conditions[0], phase=TaskPhase.POST_CONDITION,
        block_index=0, block_count=1, session_seed=3, run_id="run", project_root=None,
    )[0]
    payload = spec.model_dump()
    payload["steps"][0]["questions"].reverse()
    with pytest.raises(ValidationError, match="do not match the original"):
        TaskModuleSpec.model_validate(payload)
