from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from fpvs_studio.core.compiler import CompileError, compile_run_spec, compile_session_plan
from fpvs_studio.core.enums import PresentationUnit
from fpvs_studio.core.execution import RunExecutionSummary
from fpvs_studio.core.migrations import migrate_project_payload
from fpvs_studio.core.project_config import (
    create_project_from_config,
    export_project_config,
    read_project_config,
    write_project_config,
)
from fpvs_studio.core.task_assets import TaskAssetError, copy_task_asset
from fpvs_studio.core.task_models import (
    TaskBinding,
    TaskBranchOperator,
    TaskBranchRule,
    TaskDisplayItem,
    TaskItemModality,
    TaskLayoutMode,
    TaskModule,
    TaskOccurrence,
    TaskOption,
    TaskPhase,
    TaskQuestion,
    TaskQuestionKind,
    TaskResponseKind,
    TaskResponseRecord,
    TaskStep,
    TaskStepKind,
    TaskSubmissionMode,
)
from fpvs_studio.core.validation import validate_project


def _instruction_module(task_id: str = "memory-intro") -> TaskModule:
    return TaskModule(
        task_id=task_id,
        name="Memory introduction",
        steps=[
            TaskStep(
                step_id="intro",
                kind=TaskStepKind.INSTRUCTION,
                text="Remember these items.",
                continue_key="space",
            )
        ],
    )


def test_task_models_support_exact_creatine_geometry_and_questionnaire() -> None:
    module = TaskModule(
        task_id="creatine-images",
        name="Creatine image memory",
        repeat_count=4,
        steps=[
            TaskStep(
                step_id="recognition",
                kind=TaskStepKind.CHOICE_GRID,
                text="Select all 4",
                layout_mode=TaskLayoutMode.EXACT,
                items=[
                    TaskDisplayItem(
                        item_id="apple",
                        modality=TaskItemModality.IMAGE,
                        image_path="stimuli/task-assets/creatine-images/apple.png",
                        x=-10,
                        y=0,
                        width=5,
                        height=4,
                        unit=PresentationUnit.DEGREES,
                        selectable=True,
                        correct=True,
                    ),
                    TaskDisplayItem(
                        item_id="foil",
                        modality=TaskItemModality.IMAGE,
                        image_path="stimuli/task-assets/creatine-images/foil.jpg",
                        x=-4,
                        y=0,
                        width=5,
                        height=4,
                        selectable=False,
                    ),
                ],
            ),
            TaskStep(
                step_id="feedback",
                kind=TaskStepKind.TIMED_FEEDBACK,
                text="correct",
                duration_seconds=1,
            ),
            TaskStep(
                step_id="questionnaire",
                kind=TaskStepKind.QUESTIONNAIRE,
                questions=[
                    TaskQuestion(
                        question_id="confidence",
                        kind=TaskQuestionKind.RATING,
                        prompt="How confident are you?",
                        min_value=1,
                        max_value=5,
                        min_label="Not confident",
                        max_label="Very confident",
                    ),
                    TaskQuestion(
                        question_id="recall",
                        kind=TaskQuestionKind.LONG_TEXT,
                        prompt="Which items do you remember?",
                    ),
                    TaskQuestion(
                        question_id="recognized",
                        kind=TaskQuestionKind.MULTIPLE_CHOICE,
                        prompt="Choose remembered items.",
                        options=[
                            TaskOption(option_id="apple", label="Apple"),
                            TaskOption(option_id="purse", label="Purse"),
                        ],
                        min_selections=0,
                        max_selections=2,
                    ),
                ],
                submission_mode=TaskSubmissionMode.EXPLICIT,
            ),
        ],
    )

    assert module.repeat_count == 4
    assert module.steps[0].items[0].x == -10
    assert module.steps[0].items[1].selectable is False
    assert [question.kind for question in module.steps[2].questions] == [
        TaskQuestionKind.RATING,
        TaskQuestionKind.LONG_TEXT,
        TaskQuestionKind.MULTIPLE_CHOICE,
    ]


def test_exact_prompt_only_step_supports_psychopy_text_geometry() -> None:
    step = TaskStep(
        step_id="recall-prompt",
        kind=TaskStepKind.RAW_KEY,
        text="What were the items you remembered?",
        layout_mode=TaskLayoutMode.EXACT,
        prompt_x=0.0,
        prompt_y=0.0,
        prompt_unit=PresentationUnit.WINDOW_HEIGHT_FRACTION,
        prompt_height=0.05,
        allowed_keys=["space"],
    )

    assert step.items == []
    assert step.prompt_height == 0.05


def test_exact_prompt_only_step_requires_authored_height() -> None:
    with pytest.raises(ValidationError, match="prompt height"):
        TaskStep(
            step_id="invalid-exact-prompt",
            kind=TaskStepKind.RAW_KEY,
            text="Prompt",
            layout_mode=TaskLayoutMode.EXACT,
            allowed_keys=["space"],
        )


def test_task_module_rejects_backward_branch_and_duplicate_question_ids() -> None:
    with pytest.raises(ValidationError, match="unique across one task module"):
        TaskModule(
            task_id="bad-questions",
            name="Bad",
            steps=[
                TaskStep(
                    step_id="first",
                    kind=TaskStepKind.QUESTIONNAIRE,
                    questions=[
                        TaskQuestion(
                            question_id="same",
                            kind=TaskQuestionKind.SHORT_TEXT,
                            prompt="First",
                        )
                    ],
                ),
                TaskStep(
                    step_id="second",
                    kind=TaskStepKind.QUESTIONNAIRE,
                    questions=[
                        TaskQuestion(
                            question_id="same",
                            kind=TaskQuestionKind.SHORT_TEXT,
                            prompt="Second",
                        )
                    ],
                ),
            ],
        )


def test_task_module_validates_branch_operator_and_choice_option_ids() -> None:
    text_question = TaskQuestion(
        question_id="note",
        kind=TaskQuestionKind.SHORT_TEXT,
        prompt="Note",
    )
    with pytest.raises(ValidationError, match="numeric operator"):
        TaskModule(
            task_id="typed-branch",
            name="Typed branch",
            steps=[
                TaskStep(
                    step_id="question",
                    kind=TaskStepKind.QUESTIONNAIRE,
                    questions=[text_question],
                    branch_rules=[
                        TaskBranchRule(
                            rule_id="invalid-numeric",
                            question_id="note",
                            operator=TaskBranchOperator.GREATER_THAN,
                            expected_numeric=1,
                            next_step_id="finish",
                        )
                    ],
                ),
                TaskStep(
                    step_id="finish",
                    kind=TaskStepKind.RAW_KEY,
                    allowed_keys=["space"],
                ),
            ],
        )

    choice = TaskQuestion(
        question_id="choice",
        kind=TaskQuestionKind.SINGLE_CHOICE,
        prompt="Choose",
        options=[TaskOption(option_id="apple", label="Apple")],
    )
    with pytest.raises(ValidationError, match="unknown option ids"):
        TaskModule(
            task_id="option-branch",
            name="Option branch",
            steps=[
                TaskStep(
                    step_id="question",
                    kind=TaskStepKind.QUESTIONNAIRE,
                    questions=[choice],
                    branch_rules=[
                        TaskBranchRule(
                            rule_id="misspelled",
                            question_id="choice",
                            operator=TaskBranchOperator.EQUALS,
                            expected_values=["appl"],
                            next_step_id="finish",
                        )
                    ],
                ),
                TaskStep(
                    step_id="finish",
                    kind=TaskStepKind.RAW_KEY,
                    allowed_keys=["space"],
                ),
            ],
        )

    numeric = TaskQuestion(
        question_id="rating",
        kind=TaskQuestionKind.RATING,
        prompt="Rate",
        min_value=1,
        max_value=5,
    )
    with pytest.raises(ValidationError, match="text/choice operator"):
        TaskModule(
            task_id="numeric-equality",
            name="Numeric equality",
            steps=[
                TaskStep(
                    step_id="question",
                    kind=TaskStepKind.QUESTIONNAIRE,
                    questions=[numeric],
                    branch_rules=[
                        TaskBranchRule(
                            rule_id="ambiguous-equality",
                            question_id="rating",
                            operator=TaskBranchOperator.EQUALS,
                            expected_values=["5"],
                            next_step_id="finish",
                        )
                    ],
                ),
                TaskStep(
                    step_id="finish",
                    kind=TaskStepKind.RAW_KEY,
                    allowed_keys=["space"],
                ),
            ],
        )

    with pytest.raises(ValidationError, match="jump forward"):
        TaskModule(
            task_id="bad-branch",
            name="Bad",
            steps=[
                TaskStep(
                    step_id="question",
                    kind=TaskStepKind.QUESTIONNAIRE,
                    questions=[
                        TaskQuestion(
                            question_id="answer",
                            kind=TaskQuestionKind.SHORT_TEXT,
                            prompt="Answer",
                        )
                    ],
                ),
                TaskStep(
                    step_id="branch",
                    kind=TaskStepKind.RAW_KEY,
                    allowed_keys=["space"],
                    branch_rules=[
                        TaskBranchRule(
                            rule_id="back",
                            question_id="answer",
                            operator=TaskBranchOperator.ANSWERED,
                            next_step_id="question",
                        )
                    ],
                ),
            ],
        )


def test_rating_scale_rejects_unaligned_or_oversized_ticks() -> None:
    with pytest.raises(ValidationError, match="align exactly"):
        TaskQuestion(
            question_id="unaligned",
            kind=TaskQuestionKind.RATING,
            prompt="Rate",
            min_value=0,
            max_value=1,
            step=0.3,
        )

    with pytest.raises(ValidationError, match="at most 100"):
        TaskQuestion(
            question_id="too-many",
            kind=TaskQuestionKind.RATING,
            prompt="Rate",
            min_value=0,
            max_value=100,
            step=1,
        )


def test_optional_choice_requires_explicit_submission_or_timeout() -> None:
    optional_question = TaskQuestion(
        question_id="optional",
        kind=TaskQuestionKind.SINGLE_CHOICE,
        prompt="Choose or skip",
        required=False,
        options=[TaskOption(option_id="one", label="One")],
    )
    with pytest.raises(ValidationError, match="explicit submission or a timeout"):
        TaskStep(
            step_id="invalid-optional",
            kind=TaskStepKind.QUESTIONNAIRE,
            questions=[optional_question],
        )

    assert TaskStep(
        step_id="explicit-optional",
        kind=TaskStepKind.QUESTIONNAIRE,
        questions=[optional_question],
        submission_mode=TaskSubmissionMode.EXPLICIT,
    ).submission_mode == TaskSubmissionMode.EXPLICIT
    assert TaskStep(
        step_id="timed-optional",
        kind=TaskStepKind.QUESTIONNAIRE,
        questions=[optional_question],
        timeout_seconds=5,
    ).timeout_seconds == 5


def test_timed_feedback_rejects_response_keys() -> None:
    with pytest.raises(ValidationError, match="cannot define response keys"):
        TaskStep(
            step_id="feedback",
            kind=TaskStepKind.TIMED_FEEDBACK,
            duration_seconds=1,
            continue_key="space",
        )


def test_ranged_multiple_choice_requires_explicit_submission() -> None:
    question = TaskQuestion(
        question_id="multiple",
        kind=TaskQuestionKind.MULTIPLE_CHOICE,
        prompt="Select up to two",
        options=[
            TaskOption(option_id="one", label="One"),
            TaskOption(option_id="two", label="Two"),
        ],
        min_selections=1,
        max_selections=2,
    )
    with pytest.raises(ValidationError, match="equal minimum and maximum"):
        TaskStep(
            step_id="invalid-multiple",
            kind=TaskStepKind.QUESTIONNAIRE,
            questions=[question],
        )

    assert TaskStep(
        step_id="explicit-multiple",
        kind=TaskStepKind.QUESTIONNAIRE,
        questions=[question],
        submission_mode=TaskSubmissionMode.EXPLICIT,
    ).submission_mode == TaskSubmissionMode.EXPLICIT


def test_no_duplicate_choice_grid_repeats_require_sufficient_fixed_capacity() -> None:
    items = [
        TaskDisplayItem(
            item_id=f"item-{index}",
            modality=TaskItemModality.TEXT,
            text=f"Item {index}",
            selectable=True,
        )
        for index in range(4)
    ]
    fixed_step = TaskStep(
        step_id="fixed-grid",
        kind=TaskStepKind.CHOICE_GRID,
        items=items,
        min_selections=2,
        max_selections=2,
        allow_duplicate_selections_across_repeats=False,
    )

    assert TaskModule(
        task_id="enough-grid-options",
        name="Enough grid options",
        repeat_count=2,
        steps=[fixed_step],
    ).repeat_count == 2

    with pytest.raises(ValidationError, match="only 4 available options"):
        TaskModule(
            task_id="exhausted-grid-options",
            name="Exhausted grid options",
            repeat_count=2,
            steps=[fixed_step.model_copy(update={"repeat_count": 2})],
        )

    with pytest.raises(ValidationError, match="minimum and maximum selections must be equal"):
        TaskModule(
            task_id="ranged-grid-options",
            name="Ranged grid options",
            repeat_count=2,
            steps=[
                fixed_step.model_copy(
                    update={
                        "submission_mode": TaskSubmissionMode.EXPLICIT,
                        "min_selections": 1,
                    }
                )
            ],
        )


def test_no_duplicate_questionnaire_repeats_validate_choice_and_rating_capacity() -> None:
    choice_question = TaskQuestion(
        question_id="pick-two",
        kind=TaskQuestionKind.MULTIPLE_CHOICE,
        prompt="Pick two",
        options=[
            TaskOption(option_id=f"choice-{index}", label=f"Choice {index}")
            for index in range(4)
        ],
        min_selections=2,
        max_selections=2,
    )
    choice_step = TaskStep(
        step_id="choice-question",
        kind=TaskStepKind.QUESTIONNAIRE,
        questions=[choice_question],
        allow_duplicate_selections_across_repeats=False,
    )
    assert TaskModule(
        task_id="enough-question-options",
        name="Enough question options",
        repeat_count=2,
        steps=[choice_step],
    ).repeat_count == 2

    rating_step = TaskStep(
        step_id="rating-question",
        kind=TaskStepKind.QUESTIONNAIRE,
        questions=[
            TaskQuestion(
                question_id="rating",
                kind=TaskQuestionKind.RATING,
                prompt="Rate",
                min_value=1,
                max_value=2,
            )
        ],
        allow_duplicate_selections_across_repeats=False,
    )
    with pytest.raises(ValidationError, match="only 2 available options"):
        TaskModule(
            task_id="exhausted-rating-options",
            name="Exhausted rating options",
            repeat_count=3,
            steps=[rating_step],
        )


def test_schema_1_1_migrates_to_empty_task_collections(sample_project) -> None:
    payload = sample_project.model_dump(mode="json")
    payload["schema_version"] = "1.1.0"
    payload.pop("task_modules")
    for condition in payload["conditions"]:
        condition.pop("pre_task_bindings")
        condition.pop("post_task_bindings")

    migrated = migrate_project_payload(payload)

    assert migrated.schema_version.value == "1.2.0"
    assert migrated.task_modules == []
    assert migrated.conditions[0].pre_task_bindings == []
    assert migrated.conditions[0].post_task_bindings == []


def test_project_validation_reports_missing_task_binding(sample_project) -> None:
    sample_project.conditions[0].pre_task_bindings = [TaskBinding(task_id="missing-task")]

    report = validate_project(sample_project, refresh_hz=60)

    assert any(
        issue.location.endswith("pre_task_bindings.missing-task")
        and "missing task module" in issue.message
        for issue in report.issues
    )


def test_session_compiles_occurrence_scopes_and_deterministic_options(
    multi_condition_project,
    multi_condition_project_root: Path,
) -> None:
    project = multi_condition_project
    project.settings.session.block_count = 3
    module = TaskModule(
        task_id="recognition",
        name="Recognition",
        repeat_count=4,
        steps=[
            TaskStep(
                step_id="choices",
                kind=TaskStepKind.QUESTIONNAIRE,
                randomize_options=True,
                questions=[
                    TaskQuestion(
                        question_id="choice",
                        kind=TaskQuestionKind.SINGLE_CHOICE,
                        prompt="Choose",
                        options=[
                            TaskOption(option_id="a", label="A"),
                            TaskOption(option_id="b", label="B"),
                            TaskOption(option_id="c", label="C"),
                        ],
                    )
                ],
            )
        ],
    )
    project.task_modules = [module]
    condition = project.conditions[0]
    condition.pre_task_bindings = [
        TaskBinding(task_id="recognition", occurrence=TaskOccurrence.FIRST_OCCURRENCE)
    ]
    condition.post_task_bindings = [
        TaskBinding(task_id="recognition", occurrence=TaskOccurrence.LAST_OCCURRENCE)
    ]

    first = compile_session_plan(
        project,
        refresh_hz=60,
        project_root=multi_condition_project_root,
        random_seed=4242,
    )
    second = compile_session_plan(
        project,
        refresh_hz=60,
        project_root=multi_condition_project_root,
        random_seed=4242,
    )
    condition_entries = [
        entry for entry in first.ordered_entries() if entry.condition_id == condition.condition_id
    ]

    assert [len(entry.pre_tasks) for entry in condition_entries] == [1, 0, 0]
    assert [len(entry.post_tasks) for entry in condition_entries] == [0, 0, 1]
    assert condition_entries[0].pre_tasks[0].phase == TaskPhase.PRE_CONDITION
    assert condition_entries[0].pre_tasks[0].repeat_count == 4
    first_order = condition_entries[0].pre_tasks[0].steps[0].realized_question_option_orders
    second_entry = next(
        entry
        for entry in second.ordered_entries()
        if entry.condition_id == condition.condition_id and entry.block_index == 0
    )
    assert first_order == second_entry.pre_tasks[0].steps[0].realized_question_option_orders


def test_task_authoring_does_not_change_run_spec(
    sample_project,
    sample_project_root: Path,
) -> None:
    before = compile_run_spec(
        sample_project,
        condition_id="faces",
        refresh_hz=60,
        project_root=sample_project_root,
        random_seed=77,
        run_id="fixed-run",
    )
    sample_project.task_modules = [_instruction_module()]
    sample_project.conditions[0].pre_task_bindings = [TaskBinding(task_id="memory-intro")]

    after = compile_run_spec(
        sample_project,
        condition_id="faces",
        refresh_hz=60,
        project_root=sample_project_root,
        random_seed=77,
        run_id="fixed-run",
    )

    assert after == before


def test_compile_rejects_missing_and_misplaced_task_assets(
    multi_condition_project,
    multi_condition_project_root: Path,
) -> None:
    project = multi_condition_project
    project.settings.session.block_count = 1
    project.task_modules = [
        TaskModule(
            task_id="images",
            name="Images",
            steps=[
                TaskStep(
                    step_id="study",
                    kind=TaskStepKind.STUDY,
                    continue_key="space",
                    items=[
                        TaskDisplayItem(
                            item_id="image",
                            modality=TaskItemModality.IMAGE,
                            image_path="stimuli/task-assets/images/missing.png",
                        )
                    ],
                )
            ],
        )
    ]
    project.conditions[0].pre_task_bindings = [TaskBinding(task_id="images")]

    with pytest.raises(CompileError, match="missing"):
        compile_session_plan(
            project,
            refresh_hz=60,
            project_root=multi_condition_project_root,
            random_seed=1,
        )


def test_task_response_record_is_separate_from_timed_response_log(sample_project) -> None:
    record = TaskResponseRecord(
        response_index=0,
        task_id="recall",
        step_id="prompt",
        phase=TaskPhase.POST_CONDITION,
        condition_id="condition-1",
        run_id="run-1",
        block_index=0,
        global_order_index=0,
        repetition_index=0,
        question_id="free-recall",
        response_kind=TaskResponseKind.TEXT,
        text_value="Apple, purse",
        reaction_time_s=1.25,
    )
    summary_fields = RunExecutionSummary.model_fields

    assert "task_responses" in summary_fields
    assert record.text_value == "Apple, purse"


def test_post_task_abort_metadata_does_not_require_fpvs_run_abort() -> None:
    summary = RunExecutionSummary(
        project_id="project",
        session_id="session",
        run_id="run",
        condition_id="condition",
        condition_name="Condition",
        engine_name="fake",
        run_mode="session",
        completed_frames=100,
        aborted=False,
        task_flow_completed=False,
        task_flow_aborted=True,
        task_abort_stage="post_condition",
        task_abort_id="recall",
        task_abort_reason="Participant aborted recall.",
    )

    assert summary.aborted is False
    assert summary.task_flow_aborted is True


def test_copy_task_asset_is_portable_and_does_not_overwrite(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source = tmp_path / "apple.png"
    source.write_bytes(b"png-one")

    stored_path = copy_task_asset(project_root, "memory", source)

    assert stored_path == "stimuli/task-assets/memory/apple.png"
    assert (project_root / Path(stored_path)).read_bytes() == b"png-one"
    assert copy_task_asset(project_root, "memory", source) == stored_path

    source.write_bytes(b"png-two")
    with pytest.raises(TaskAssetError, match="different task asset"):
        copy_task_asset(project_root, "memory", source)


def test_task_definitions_round_trip_through_project_config(
    tmp_path: Path,
    sample_project,
) -> None:
    sample_project.task_modules = [_instruction_module()]
    sample_project.conditions[0].pre_task_bindings = [TaskBinding(task_id="memory-intro")]
    config = export_project_config(sample_project, None)
    config_path = tmp_path / "task.fpvsconfig"
    write_project_config(config_path, config)

    loaded = read_project_config(config_path)
    scaffold = create_project_from_config(tmp_path / "imports", loaded)

    assert loaded.schema_version == "1.2.0"
    assert loaded.task_modules[0].task_id == "memory-intro"
    assert scaffold.project.task_modules[0] == sample_project.task_modules[0]
    assert scaffold.project.conditions[0].pre_task_bindings[0].task_id == "memory-intro"
    assert (scaffold.project_root / "stimuli" / "task-assets").is_dir()


def test_pre_task_can_replace_standard_condition_start_gate(
    sample_project,
    sample_project_root: Path,
) -> None:
    sample_project.task_modules = [_instruction_module()]
    sample_project.conditions[0].pre_task_bindings = [
        TaskBinding(
            task_id="memory-intro",
            replaces_condition_start_gate=True,
        )
    ]

    plan = compile_session_plan(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=44,
    )

    assert plan.ordered_entries()[0].show_condition_start_gate is False


def test_post_task_cannot_replace_standard_condition_start_gate(sample_project) -> None:
    payload = sample_project.conditions[0].model_dump(mode="json")
    payload["post_task_bindings"] = [
        {
            "task_id": "memory-intro",
            "replaces_condition_start_gate": True,
        }
    ]
    with pytest.raises(ValidationError, match="Only a pre-condition task"):
        type(sample_project.conditions[0]).model_validate(payload)


def test_image_task_assets_round_trip_inside_portable_project_config(
    tmp_path: Path,
    sample_project,
) -> None:
    source_root = tmp_path / "source-project"
    asset_path = source_root / "stimuli" / "task-assets" / "memory-images" / "apple.png"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"portable-task-image")
    module = TaskModule(
        task_id="memory-images",
        name="Image study",
        steps=[
            TaskStep(
                step_id="study",
                kind=TaskStepKind.STUDY,
                continue_key="space",
                items=[
                    TaskDisplayItem(
                        item_id="apple",
                        modality=TaskItemModality.IMAGE,
                        image_path="stimuli/task-assets/memory-images/apple.png",
                    )
                ],
            )
        ],
    )
    sample_project.task_modules = [module]
    sample_project.conditions[0].pre_task_bindings = [TaskBinding(task_id=module.task_id)]

    config = export_project_config(sample_project, source_root)
    config_path = tmp_path / "portable.fpvsconfig"
    write_project_config(config_path, config)
    loaded = read_project_config(config_path)
    scaffold = create_project_from_config(tmp_path / "imports", loaded)

    assert len(loaded.task_assets) == 1
    imported = scaffold.project_root / "stimuli" / "task-assets" / "memory-images" / "apple.png"
    assert imported.read_bytes() == b"portable-task-image"


def test_image_task_config_export_requires_project_root(sample_project) -> None:
    sample_project.task_modules = [
        TaskModule(
            task_id="memory-images",
            name="Image study",
            steps=[
                TaskStep(
                    step_id="study",
                    kind=TaskStepKind.STUDY,
                    continue_key="space",
                    items=[
                        TaskDisplayItem(
                            item_id="apple",
                            modality=TaskItemModality.IMAGE,
                            image_path="stimuli/task-assets/memory-images/apple.png",
                        )
                    ],
                )
            ],
        )
    ]

    with pytest.raises(ValueError, match="project root is required"):
        export_project_config(sample_project, None)
