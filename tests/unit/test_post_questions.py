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
    compile_post_question_context,
    make_post_questionnaire,
    make_yes_no_question,
    question_definition_version,
    remove_post_questionnaire,
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
    TaskModule,
    TaskModuleSpec,
    TaskOccurrence,
    TaskOption,
    TaskPhase,
    TaskQuestion,
    TaskStep,
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
