"""Exact presentation pools, atomic count edits and chronological task occurrence identity."""

import random
from collections import Counter
from itertools import product

import pytest
from pydantic import ValidationError

from fpvs_studio.core.compiler import CompileError, compile_session_plan
from fpvs_studio.core.compiler_support import compilation_cancellation
from fpvs_studio.core.condition_modifiers import assign_modifier
from fpvs_studio.core.condition_timing import propose_condition_timing
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.masking_presets import create_masking_modifier
from fpvs_studio.core.models import Condition, ConditionDefaults, ProjectFile
from fpvs_studio.core.session_ordering import (
    condition_presentation_counts,
    constrained_condition_order,
    effective_condition_presentation_count,
    session_presentation_count,
    validate_condition_presentation_counts,
)
from fpvs_studio.core.session_plan import SessionEntry, SessionPlan
from fpvs_studio.core.task_models import TaskBinding, TaskModule, TaskOccurrence, TaskStep
from fpvs_studio.core.validation import validate_project


@pytest.fixture
def presentation_project(sample_project):
    project = sample_project.model_copy(deep=True)
    project.settings.fixation_task.enabled = False
    project.conditions.append(project.conditions[0].model_copy(update={
        "condition_id": "houses", "name": "Houses", "order_index": 1,
    }))
    return project


@pytest.mark.parametrize("count", [0, -1, 1.5, "3", True, False, float("inf")])
def test_counts_are_strict_positive_integers_in_conditions_defaults_and_proposals(
    presentation_project, count,
):
    condition = presentation_project.conditions[0]
    with pytest.raises(ValidationError):
        Condition.model_validate({**condition.model_dump(), "presentation_count": count})
    with pytest.raises(ValidationError):
        ConditionDefaults(presentation_count=count)
    before = presentation_project.model_dump()
    with pytest.raises(ValueError, match="positive integer"):
        propose_condition_timing(
            presentation_project, presentation_counts={condition.condition_id: count},
        )
    assert presentation_project.model_dump() == before


def test_legacy_counts_are_preserved_and_explicit_totals_are_not_multiplied(presentation_project):
    project = presentation_project
    project.settings.session.block_count = 4
    condition = project.conditions[0]
    assert effective_condition_presentation_count(project, condition) == 4
    assert "presentation_count" not in condition.model_dump()
    assert "presentation_count" not in ConditionDefaults().model_dump()
    draft = propose_condition_timing(project, presentation_counts={condition.condition_id: 3})
    assert condition_presentation_counts(draft) == {condition.condition_id: 3, "houses": 4}


def test_count_only_edits_need_no_refresh_and_are_atomic(presentation_project):
    project = presentation_project
    first, second = project.conditions
    project.settings.display.preferred_refresh_hz = None
    before = project.model_dump()
    with pytest.raises(ValueError, match="Faces.*3 presentations.*only 1"):
        propose_condition_timing(project, presentation_counts={first.condition_id: 3})
    assert project.model_dump() == before
    draft = propose_condition_timing(
        project, presentation_counts={first.condition_id: 3, second.condition_id: 2},
    )
    assert draft.schema_version.value == "1.13.0"
    assert session_presentation_count(draft) == 5
    assert all(condition.stream_duration_seconds is None for condition in draft.conditions)
    assert project.model_dump() == before


def test_count_and_duration_changes_are_one_atomic_draft(presentation_project):
    project = presentation_project
    first, second = project.conditions
    before = project.model_dump()
    with pytest.raises(ValueError, match="complete oddball cycles"):
        propose_condition_timing(
            project, presentation_counts={first.condition_id: 3, second.condition_id: 2},
            durations={first.condition_id: 1}, refresh_hz=60,
        )
    assert project.model_dump() == before


def test_constraint_arrangement_exact_multiplicities_and_seed_reproducibility():
    for values in product(range(1, 4), repeat=4):
        counts = dict(zip("abcd", values, strict=True))
        for seed in range(10):
            order = constrained_condition_order(counts, rng=random.Random(seed))
            assert Counter(order) == counts
            assert all(left != right for left, right in zip(order, order[1:], strict=False))
            assert order == constrained_condition_order(counts, rng=random.Random(seed))
    assert constrained_condition_order({"a": 3, "b": 2}, rng=random.Random(42)) == list("ababa")
    for counts in ({"a": 3, "b": 1}, {"a": 2}):
        with pytest.raises(ValueError, match="avoid adjacent repeats"):
            constrained_condition_order(counts, rng=random.Random(42))


def test_pooled_order_can_mix_rounds_and_vary_by_seed():
    counts = {"a": 3, "b": 3, "c": 3}
    orders = [constrained_condition_order(counts, rng=random.Random(seed)) for seed in range(20)]
    assert len({tuple(order) for order in orders}) > 1
    assert any(len(set(order[:3])) < 3 for order in orders)


def test_arrangement_honors_compilation_cancellation():
    calls = 0

    def cancel():
        nonlocal calls
        calls += 1
        if calls == 3:
            raise InterruptedError("Cancelled while arranging presentations.")

    with pytest.raises(InterruptedError, match="arranging presentations"):
        with compilation_cancellation(cancel):
            constrained_condition_order({"a": 1000, "b": 1000}, rng=random.Random(42))
    assert calls == 3


def test_unequal_presentations_compile_separate_durations_tasks_and_occurrence_identity(
    presentation_project, sample_project_root,
):
    project = presentation_project
    project.settings.session.block_count = 9
    first, second = project.conditions
    project = propose_condition_timing(
        project, presentation_counts={first.condition_id: 3, second.condition_id: 2},
        durations={first.condition_id: 60, second.condition_id: 60}, refresh_hz=60,
    )
    for identity in ("first", "every", "last"):
        project.task_modules.append(TaskModule(
            task_id=identity, name=identity,
            steps=[TaskStep(step_id="instructions", kind="instruction", text=identity,
                            continue_key="space")],
        ))
    for condition in project.conditions:
        condition.pre_task_bindings = [
            TaskBinding(task_id="first", occurrence=TaskOccurrence.FIRST_OCCURRENCE,
                        replaces_condition_start_gate=True),
            TaskBinding(task_id="every"),
        ]
        condition.post_task_bindings = [
            TaskBinding(task_id="last", occurrence=TaskOccurrence.LAST_OCCURRENCE),
        ]
    plan = compile_session_plan(project, refresh_hz=60, project_root=sample_project_root,
                                random_seed=42)
    assert plan.schema_version == "1.6.0"
    assert plan.ordering_policy == "pooled_no_adjacent"
    assert plan.block_count == 1
    assert plan.total_runs == 5
    assert [entry.condition_id for entry in plan.ordered_entries()] == [
        first.condition_id, second.condition_id, first.condition_id,
        second.condition_id, first.condition_id,
    ]
    for condition in project.conditions:
        entries = [entry for entry in plan.ordered_entries()
                   if entry.condition_id == condition.condition_id]
        count = condition.presentation_count
        assert [entry.condition_presentation_index for entry in entries] == list(
            range(1, count + 1),
        )
        assert all(entry.condition_presentation_count == count for entry in entries)
        assert sum(entry.run_spec.display.total_frames / 60 for entry in entries) == count * 60
        assert [task.task_id for task in entries[0].pre_tasks] == ["first", "every"]
        assert not entries[0].show_condition_start_gate
        assert all([task.task_id for task in entry.pre_tasks] == ["every"] for entry in entries[1:])
        assert all(entry.show_condition_start_gate for entry in entries[1:])
        assert [len(entry.post_tasks) for entry in entries] == [0] * (count - 1) + [1]
        assert len({entry.run_spec.random_seed for entry in entries}) == count


def test_infeasible_legacy_single_condition_is_reported_before_manifest_work(
    sample_project, monkeypatch,
):
    sample_project.settings.session.block_count = 2
    monkeypatch.setattr("fpvs_studio.core.compiler.CompilationInputs", lambda *args, **kwargs:
                        pytest.fail("Infeasible session must fail before asset preparation."))
    with pytest.raises(CompileError, match="Faces.*2 presentations.*another condition"):
        compile_session_plan(sample_project, refresh_hz=60)
    report = validate_project(sample_project)
    assert any(issue.location == "conditions.presentation_count" for issue in report.issues)


def test_native_ab_rejects_presentation_fields_at_project_and_condition_boundaries(sample_project):
    payload = sample_project.model_dump()
    payload["experiment_category"] = ExperimentCategory.ATTENTIONAL_BLINK
    payload["conditions"][0]["presentation_count"] = 1
    with pytest.raises(ValidationError, match="Attentional-Blink"):
        ProjectFile.model_validate(payload)
    payload["conditions"][0].pop("presentation_count")
    payload["settings"]["condition_defaults"]["presentation_count"] = 1
    with pytest.raises(ValidationError, match="Attentional-Blink"):
        ProjectFile.model_validate(payload)


def test_historical_and_filtered_recovery_plans_keep_their_order_and_metadata(
    presentation_project, sample_project_root,
):
    project = propose_condition_timing(
        presentation_project, presentation_counts={"faces": 3, "houses": 2},
    )
    plan = compile_session_plan(project, refresh_hz=60, project_root=sample_project_root)
    payload = plan.model_dump()
    # Exact-occurrence recovery may remove intervening completed runs and indices.
    entries = [payload["blocks"][0]["entries"][index] for index in (0, 4)]
    payload["blocks"][0]["entries"] = entries
    payload["blocks"][0]["condition_order"] = [entry["condition_id"] for entry in entries]
    payload["total_runs"] = 2
    recovered = SessionPlan.model_validate(payload)
    assert [entry.condition_presentation_index for entry in recovered.ordered_entries()] == [1, 3]
    assert [entry.condition_presentation_count for entry in recovered.ordered_entries()] == [3, 3]
    payload["schema_version"] = "1.2.0"
    with pytest.raises(ValidationError, match="schema 1.6.0"):
        SessionPlan.model_validate(payload)
    payload.pop("ordering_policy")
    for entry in entries:
        entry.pop("condition_presentation_index")
        entry.pop("condition_presentation_count")
    historical = SessionPlan.model_validate(payload)
    assert [entry.condition_id for entry in historical.ordered_entries()] == ["faces", "faces"]
    assert "ordering_policy" not in historical.model_dump()
    assert "condition_presentation_index" not in historical.ordered_entries()[0].model_dump()
    invalid = {**recovered.ordered_entries()[0].model_dump(), "condition_presentation_index": 4}
    with pytest.raises(ValidationError, match="may not exceed"):
        SessionEntry.model_validate(invalid)


def test_source_defaults_promote_without_changing_legacy_continuous_counts(sample_project):
    sample_project.settings.condition_defaults.presentation_count = 3
    restored = ProjectFile.model_validate(sample_project.model_dump())
    assert restored.schema_version.value == "1.13.0"
    assert restored.conditions[0].sequence_count == sample_project.conditions[0].sequence_count
    assert restored.conditions[0].presentation_count is None
    validate_condition_presentation_counts(restored)


def test_masking_group_rejects_overrides_without_changing_its_legacy_repeat_count(sample_project):
    project = assign_modifier(
        sample_project, create_masking_modifier(variant="color"), ["faces"],
    )
    project.settings.session.block_count = 3
    validate_condition_presentation_counts(project)
    assert effective_condition_presentation_count(project, project.conditions[0]) == 3
    before = project.model_dump()
    with pytest.raises(ValueError, match="masking groups"):
        propose_condition_timing(project, presentation_counts={"faces": 3})
    assert project.model_dump() == before
    project.conditions[0].presentation_count = 3
    with pytest.raises(ValueError, match="masking groups"):
        validate_condition_presentation_counts(project)
    with pytest.raises(ValidationError, match="masking groups"):
        ProjectFile.model_validate(project.model_dump())
