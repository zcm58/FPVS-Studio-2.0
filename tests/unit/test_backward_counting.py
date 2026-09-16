"""Counting modules stay reproducible and outside the FPVS frame schedule."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fpvs_studio.core.backward_counting import (
    create_backward_counting_baseline_task,
    create_backward_counting_report_task,
    create_backward_counting_start_task,
)
from fpvs_studio.core.compiler import CompileError, compile_session_plan
from fpvs_studio.core.task_models import (
    BackwardCountingConfig,
    BackwardCountingRole,
    TaskBinding,
    TaskModule,
    TaskModuleSpec,
    TaskOccurrence,
    TaskPhase,
    TaskStep,
    TaskStepKind,
)


def _attach_counting(project) -> None:
    baseline = create_backward_counting_baseline_task()
    start = create_backward_counting_start_task(subtraction_step=7, start_min=1500, start_max=4000)
    report = create_backward_counting_report_task()
    project.task_modules = [baseline, start, report]
    for condition in project.conditions:
        condition.pre_task_bindings = [
            TaskBinding(task_id=baseline.task_id, occurrence=TaskOccurrence.FIRST_SESSION_ENTRY),
            TaskBinding(task_id=start.task_id, replaces_condition_start_gate=True),
        ]
        condition.post_task_bindings = [TaskBinding(task_id=report.task_id)]


@pytest.mark.parametrize("changes", [
    {"subtraction_step": 0}, {"subtraction_step": -7}, {"subtraction_step": 7.5},
    {"subtraction_step": True}, {"duration_seconds": 0}, {"duration_seconds": float("inf")},
    {"duration_seconds": float("nan")}, {"start_min": 0},
    {"start_min": 100, "start_max": 99}, {"start_max": 100.5}, {"link_id": "not a slug"},
])
def test_counting_rejects_invalid_settings(changes) -> None:
    with pytest.raises(ValidationError):
        BackwardCountingConfig(role=BackwardCountingRole.BASELINE, **changes)


def test_counting_modules_generate_steps_and_reject_silent_ignored_edits() -> None:
    task = create_backward_counting_baseline_task()
    assert task.steps == []
    assert task.backward_counting is not None
    assert task.backward_counting.duration_seconds == 120
    assert task.backward_counting.subtraction_step == 13
    assert TaskModule.model_validate_json(task.model_dump_json()) == task
    for changes in ({"repeat_count": 2}, {"steps": [TaskStep(
        step_id="ignored", kind=TaskStepKind.INSTRUCTION, continue_key="space",
    )]}):
        with pytest.raises(ValidationError, match="generate their own steps"):
            TaskModule.model_validate({**task.model_dump(), **changes})


@pytest.mark.parametrize("shuffle_all", [False, True])
def test_counting_baseline_occurs_once_after_randomization_and_subset(
    multi_condition_project, multi_condition_project_root, shuffle_all,
) -> None:
    _attach_counting(multi_condition_project)
    multi_condition_project.settings.session.randomize_across_blocks = shuffle_all
    for subset in (None, [multi_condition_project.conditions[-1].condition_id]):
        plan = compile_session_plan(
            multi_condition_project, refresh_hz=60, project_root=multi_condition_project_root,
            random_seed=43, condition_ids=subset,
        )
        entries = plan.ordered_entries()
        baseline_locations = [
            entry.global_order_index for entry in entries for task in entry.pre_tasks
            if task.backward_counting.role == BackwardCountingRole.BASELINE
        ]
        assert baseline_locations == [0]
        baseline = entries[0].pre_tasks[0]
        assert [step.kind for step in baseline.steps] == [
            TaskStepKind.INSTRUCTION, TaskStepKind.TIMED_FEEDBACK, TaskStepKind.QUESTIONNAIRE,
        ]
        assert baseline.steps[1].duration_seconds == 120
        endpoint = baseline.steps[-1].questions[0]
        assert endpoint.min_value < 0 < endpoint.max_value
        assert endpoint.step == 1
        assert baseline.steps[-1].retry_on_invalid


def test_linked_counting_metadata_replays_and_uses_start_settings(
    multi_condition_project, multi_condition_project_root,
) -> None:
    _attach_counting(multi_condition_project)
    plans = [compile_session_plan(
        multi_condition_project, refresh_hz=60, project_root=multi_condition_project_root,
        random_seed=seed,
    ) for seed in [57, 57, 58]]
    all_starts = []
    for plan in plans:
        starts = []
        for entry in plan.ordered_entries():
            start = entry.pre_tasks[-1].backward_counting
            report = entry.post_tasks[0].backward_counting
            assert start is not None and report is not None
            assert start.model_dump(exclude={"role"}) == report.model_dump(exclude={"role"})
            assert start.subtraction_step == 7
            assert 1500 <= start.start_number <= 4000
            assert start.duration_seconds == (
                entry.run_spec.display.total_frames / entry.run_spec.display.refresh_hz
            )
            assert "Start counting only when the images appear" in entry.pre_tasks[-1].steps[0].text
            assert not entry.show_condition_start_gate
            restored = TaskModuleSpec.model_validate_json(entry.pre_tasks[-1].model_dump_json())
            assert restored == entry.pre_tasks[-1]
            starts.append(start.start_number)
        all_starts.append(starts)
    assert all_starts[0] == all_starts[1]
    assert all_starts[0] != all_starts[2]
    assert len(set(all_starts[0])) > 1


def test_counting_does_not_change_stream_schedules_or_task_binding_seed(
    sample_project, sample_project_root,
) -> None:
    stream_only = compile_session_plan(
        sample_project, refresh_hz=60, project_root=sample_project_root, random_seed=77,
    )
    _attach_counting(sample_project)
    with_baseline = compile_session_plan(
        sample_project, refresh_hz=60, project_root=sample_project_root, random_seed=77,
    )
    sample_project.conditions[0].pre_task_bindings.pop(0)
    no_baseline = compile_session_plan(
        sample_project, refresh_hz=60, project_root=sample_project_root, random_seed=77,
    )
    for ordinary, counted, shifted in zip(
        stream_only.ordered_entries(), with_baseline.ordered_entries(),
        no_baseline.ordered_entries(),
        strict=True,
    ):
        assert ordinary.run_spec == counted.run_spec == shifted.run_spec
        assert counted.pre_tasks[-1].backward_counting == shifted.pre_tasks[-1].backward_counting


@pytest.mark.parametrize("missing", ["start", "report"])
def test_counting_rejects_unpaired_load_modules(
    sample_project, sample_project_root, missing,
) -> None:
    _attach_counting(sample_project)
    if missing == "start":
        sample_project.conditions[0].pre_task_bindings.pop()
    else:
        sample_project.conditions[0].post_task_bindings.clear()
    with pytest.raises(CompileError, match="exactly one"):
        compile_session_plan(sample_project, refresh_hz=60, project_root=sample_project_root)


def test_counting_rejects_mismatched_link_and_intervening_tasks(
    sample_project, sample_project_root,
) -> None:
    _attach_counting(sample_project)
    sample_project.task_modules[-1].backward_counting.link_id = "different-link"
    with pytest.raises(CompileError, match="exactly one"):
        compile_session_plan(sample_project, refresh_hz=60, project_root=sample_project_root)
    sample_project.task_modules[-1].backward_counting.link_id = "backward-counting-load"
    sample_project.conditions[0].pre_task_bindings.reverse()
    with pytest.raises(CompileError, match="last pre-task"):
        compile_session_plan(sample_project, refresh_hz=60, project_root=sample_project_root)


def test_legacy_task_payloads_keep_ordinary_behavior() -> None:
    legacy = {"task_id": "legacy", "name": "Legacy", "steps": [
        {"step_id": "ready", "kind": "instruction", "continue_key": "space"},
    ]}
    module = TaskModule.model_validate(legacy)
    assert module.backward_counting is None
    spec = TaskModuleSpec.model_validate({
        **legacy, "phase": TaskPhase.PRE_CONDITION, "occurrence": TaskOccurrence.EVERY_ENTRY,
        "random_seed": 0, "steps": [{**legacy["steps"][0], "random_seed": 0}],
    })
    assert spec.backward_counting is None
