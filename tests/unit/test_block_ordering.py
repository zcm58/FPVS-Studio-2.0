"""Opt-in randomized rounds, partial blocks and stable occurrence schedules."""

from collections import Counter
from itertools import product

import pytest

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.condition_timing import propose_condition_timing
from fpvs_studio.core.models import (
    ProjectFile,
    RandomizationModes,
    RandomizationSeeds,
    SessionSettings,
)
from fpvs_studio.core.session_ordering import (
    condition_order_blocks,
    condition_ordering_identity,
    preview_condition_order,
    randomized_condition_blocks,
    validate_condition_presentation_counts,
    validate_saved_condition_order,
)


@pytest.mark.parametrize("values", [
    values for length in range(1, 5) for values in product(range(1, 4), repeat=length)
])
def test_seeded_blocks_preserve_round_membership_and_boundary_constraints(values):
    counts = {f"condition-{index}": count for index, count in enumerate(values)}
    before = dict(counts)
    largest = sorted(values, reverse=True)
    feasible = len(values) == 1 or largest[0] <= largest[1] + 1
    for seed in (0, 19, 2**31 - 1):
        if not feasible:
            with pytest.raises(ValueError, match="single-condition blocks|separate"):
                randomized_condition_blocks(counts, seed=seed)
            continue
        blocks = randomized_condition_blocks(counts, seed=seed)
        assert blocks == randomized_condition_blocks(
            dict(reversed(list(counts.items()))), seed=seed,
        )
        order = [identity for block in blocks for identity in block]
        assert Counter(order) == counts
        assert len(blocks) == max(values)
        for index, block in enumerate(blocks):
            assert set(block) == {identity for identity, count in counts.items() if count > index}
            assert len(block) == len(set(block))
        if len(counts) > 1:
            assert all(left != right for left, right in zip(order, order[1:], strict=False))
        assert condition_order_blocks(order, counts) == blocks
        assert validate_saved_condition_order(order, counts, randomized_blocks=True) == order
    assert counts == before


def test_forced_partial_tail_is_planned_before_earlier_randomized_blocks():
    counts = {"a": 4, "b": 3}
    for seed in range(20):
        assert randomized_condition_blocks(counts, seed=seed) == [
            ["a", "b"], ["a", "b"], ["a", "b"], ["a"],
        ]


def test_round_validation_does_not_reinterpret_historical_pooled_lists():
    counts = {"a": 2, "b": 2, "c": 2}
    pooled = ["a", "b", "a", "c", "b", "c"]
    assert validate_saved_condition_order(pooled, counts) == pooled
    with pytest.raises(ValueError, match="Block 1"):
        validate_saved_condition_order(pooled, counts, randomized_blocks=True)
    with pytest.raises(ValueError, match="Block 1"):
        condition_order_blocks(pooled, counts)


@pytest.mark.parametrize("seed", [True, -1, 2**31, 2.5, "1"])
def test_block_seed_requires_strict_bounded_integer(seed):
    with pytest.raises(ValueError, match="seed"):
        randomized_condition_blocks({"a": 2, "b": 2}, seed=seed)


def test_block_generation_honors_cancellation_without_mutating_counts():
    counts = {"a": 1000, "b": 1000, "c": 1000}
    checks = []

    def cancelled():
        checks.append(True)
        return len(checks) == 3

    with pytest.raises(InterruptedError, match="cancelled"):
        randomized_condition_blocks(counts, seed=4, cancelled=cancelled)
    assert len(checks) == 3
    assert counts == {"a": 1000, "b": 1000, "c": 1000}


def _blocked_project(project, *, counts=(3, 2, 2)):
    project = project.model_copy(deep=True)
    project.conditions = project.conditions[:len(counts)]
    project.settings.session = SessionSettings.model_validate({
        **project.settings.session.model_dump(), "condition_ordering": "randomized_blocks",
        "randomization_mode": "fixed", "session_seed": 101,
        "stimulus_seed": 202, "fixation_seed": 303,
    })
    for condition, count in zip(project.conditions, counts, strict=True):
        condition.presentation_count = count
    project.settings.fixation_task.enabled = True
    project.settings.fixation_task.changes_per_sequence = 2
    project.settings.fixation_task.min_gap_ms = 100
    return ProjectFile.model_validate(project.model_dump())


def _streams(plan):
    return {(entry.condition_id, entry.condition_presentation_index): (
        entry.run_spec.stimulus_sequence, entry.run_spec.fixation_events,
    ) for entry in plan.ordered_entries()}


def test_preview_and_compiler_share_seeded_partial_block_structure(
    multi_condition_project, multi_condition_project_root,
):
    project = _blocked_project(multi_condition_project)
    before = project.model_dump_json()
    expected = randomized_condition_blocks(
        {item.condition_id: item.presentation_count for item in project.conditions}, seed=101,
    )
    assert preview_condition_order(project) == [
        identity for block in expected for identity in block
    ]
    plan = compile_session_plan(project, refresh_hz=60, project_root=multi_condition_project_root)
    assert plan.schema_version == "1.10.0"
    assert plan.ordering_policy == "randomized_blocks"
    assert plan.block_count == 3
    assert [block.condition_order for block in plan.blocks] == expected
    assert [len(block.entries) for block in plan.blocks] == [3, 3, 1]
    for index, block in enumerate(plan.blocks):
        assert block.block_index == index
        for position, entry in enumerate(block.entries):
            assert entry.block_index == index
            assert entry.index_within_block == position
            assert entry.condition_presentation_index == index + 1
    assert project.model_dump_json() == before


def test_exact_saved_block_order_preserves_occurrence_streams_and_protocol_identity(
    multi_condition_project, multi_condition_project_root,
):
    project = _blocked_project(multi_condition_project)
    generated = compile_session_plan(project, refresh_hz=60,
                                     project_root=multi_condition_project_root)
    first, second, third = [condition.condition_id for condition in project.conditions]
    chosen = [second, first, third, first, second, third, first]
    saved = propose_condition_timing(project, saved_condition_order=chosen)
    plan = compile_session_plan(saved, refresh_hz=60, project_root=multi_condition_project_root)
    assert plan.ordering_policy == "saved_randomized_blocks"
    assert plan.schema_version == "1.10.0"
    assert [block.condition_order for block in plan.blocks] == [
        [second, first, third], [first, second, third], [first],
    ]
    assert _streams(plan) == _streams(generated)
    assert condition_ordering_identity(project)["policy"] == "randomized_blocks"
    assert condition_ordering_identity(saved)["policy"] == "saved_randomized_blocks"
    assert condition_ordering_identity(saved)["condition_order"] == chosen
    decoded = type(plan).model_validate_json(plan.model_dump_json())
    assert decoded == plan


def test_new_condition_order_policy_changes_blocks_without_changing_stimulus_or_fixation(
    multi_condition_project, multi_condition_project_root,
):
    project = _blocked_project(multi_condition_project, counts=(2, 2, 2, 2))
    project.settings.session.randomization_mode = "new"
    project.settings.session.randomization_modes = RandomizationModes(
        condition_order="new", stimulus="fixed", fixation="fixed",
    )
    project = ProjectFile.model_validate(project.model_dump())
    plans = [compile_session_plan(
        project, refresh_hz=60, project_root=multi_condition_project_root,
        resolved_seeds=RandomizationSeeds(
            condition_order_seed=seed, stimulus_seed=202, fixation_seed=303,
        ),
    ) for seed in (1, 2)]
    assert [block.condition_order for block in plans[0].blocks] != [
        block.condition_order for block in plans[1].blocks
    ]
    assert _streams(plans[0]) == _streams(plans[1])


def test_legacy_compilation_remains_a_single_pooled_block(
    multi_condition_project, multi_condition_project_root,
):
    legacy = multi_condition_project
    assert legacy.settings.session.condition_ordering is None
    before = legacy.model_dump_json()
    plan = compile_session_plan(legacy, refresh_hz=60, project_root=multi_condition_project_root)
    assert plan.ordering_policy == "pooled_no_adjacent"
    assert plan.block_count == 1
    assert legacy.model_dump_json() == before


def test_single_condition_keeps_all_presentations_as_separate_blocks(
    sample_project, sample_project_root,
):
    project = _blocked_project(sample_project, counts=(4,))
    plan = compile_session_plan(project, refresh_hz=60, project_root=sample_project_root)
    assert plan.block_count == 4
    assert [block.condition_order for block in plan.blocks] == [["faces"]] * 4
    assert [entry.condition_presentation_index for entry in plan.ordered_entries()] == [1, 2, 3, 4]


def test_block_count_guard_rejects_impossible_partial_tail_but_legacy_counts_still_work(
    multi_condition_project,
):
    project = _blocked_project(multi_condition_project, counts=(3, 1, 1))
    with pytest.raises(ValueError, match="single-condition blocks"):
        validate_condition_presentation_counts(project)
    project.settings.session.condition_ordering = None
    validate_condition_presentation_counts(project)
