"""Session-plan compilation tests."""

from __future__ import annotations

import pytest

from fpvs_studio.core.compiler import CompileError, compile_session_plan
from fpvs_studio.core.enums import InterConditionMode


def _block_orders(session_plan) -> list[list[str]]:
    return [block.condition_order for block in session_plan.blocks]


def _realized_fixation_counts(session_plan) -> list[int]:
    return [
        entry.run_spec.fixation.realized_target_count
        for entry in session_plan.ordered_entries()
    ]


def test_session_plan_default_block_contains_all_conditions_once(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    multi_condition_project.settings.session.block_count = 1

    session_plan = compile_session_plan(
        multi_condition_project,
        refresh_hz=60.0,
        project_root=multi_condition_project_root,
        random_seed=123,
    )

    assert session_plan.block_count == 1
    assert session_plan.total_runs == 4
    assert len(session_plan.blocks) == 1
    assert sorted(session_plan.blocks[0].condition_order) == [
        "condition-1",
        "condition-2",
        "condition-3",
        "condition-4",
    ]
    assert [entry.global_order_index for entry in session_plan.ordered_entries()] == [0, 1, 2, 3]


def test_session_plan_two_block_randomization_is_deterministic_for_fixed_seed(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    plan_a = compile_session_plan(
        multi_condition_project,
        refresh_hz=60.0,
        project_root=multi_condition_project_root,
        random_seed=42,
    )
    plan_b = compile_session_plan(
        multi_condition_project,
        refresh_hz=60.0,
        project_root=multi_condition_project_root,
        random_seed=42,
    )

    assert len(plan_a.blocks) == 2
    assert plan_a.total_runs == 8
    assert _block_orders(plan_a) == _block_orders(plan_b)
    for block in plan_a.blocks:
        assert sorted(block.condition_order) == [
            "condition-1",
            "condition-2",
            "condition-3",
            "condition-4",
        ]


def test_session_plan_reproducibility_and_seed_variation(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    baseline_plan = compile_session_plan(
        multi_condition_project,
        refresh_hz=60.0,
        project_root=multi_condition_project_root,
        random_seed=100,
    )
    repeated_plan = compile_session_plan(
        multi_condition_project,
        refresh_hz=60.0,
        project_root=multi_condition_project_root,
        random_seed=100,
    )

    assert _block_orders(baseline_plan) == _block_orders(repeated_plan)
    assert any(
        _block_orders(
            compile_session_plan(
                multi_condition_project,
                refresh_hz=60.0,
                project_root=multi_condition_project_root,
                random_seed=seed,
            )
        )
        != _block_orders(baseline_plan)
        for seed in range(101, 120)
    )


def test_session_plan_transition_settings_preserve_break_and_continue_metadata(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    fixed_break_plan = compile_session_plan(
        multi_condition_project,
        refresh_hz=60.0,
        project_root=multi_condition_project_root,
        random_seed=7,
    )

    multi_condition_project.settings.session.inter_condition_mode = InterConditionMode.MANUAL_CONTINUE
    multi_condition_project.settings.session.inter_condition_break_seconds = 5.0
    multi_condition_project.settings.session.continue_key = "return"
    manual_continue_plan = compile_session_plan(
        multi_condition_project,
        refresh_hz=60.0,
        project_root=multi_condition_project_root,
        random_seed=7,
    )

    assert fixed_break_plan.transition.mode == InterConditionMode.FIXED_BREAK
    assert fixed_break_plan.transition.break_seconds == 30.0
    assert fixed_break_plan.transition.continue_key is None
    assert manual_continue_plan.transition.mode == InterConditionMode.MANUAL_CONTINUE
    assert manual_continue_plan.transition.break_seconds is None
    assert manual_continue_plan.transition.continue_key == "return"


def test_session_plan_generated_ids_avoid_redundant_prefixes(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    session_plan = compile_session_plan(
        multi_condition_project,
        refresh_hz=60.0,
        project_root=multi_condition_project_root,
        random_seed=77,
    )

    assert multi_condition_project.meta.project_id not in session_plan.session_id
    assert all(
        session_plan.session_id not in entry.run_id for entry in session_plan.ordered_entries()
    )


def test_session_plan_uses_persisted_session_seed_when_no_override_is_provided(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    multi_condition_project.settings.session.session_seed = 54321

    session_plan = compile_session_plan(
        multi_condition_project,
        refresh_hz=60.0,
        project_root=multi_condition_project_root,
    )

    assert session_plan.random_seed == 54321
    assert session_plan.session_id == "session-0000054321"


def test_session_plan_randomized_fixation_counts_are_seeded_and_non_repeating(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    fixation = multi_condition_project.settings.fixation_task
    fixation.enabled = True
    fixation.target_count_mode = "randomized"
    fixation.target_count_min = 1
    fixation.target_count_max = 3
    fixation.no_immediate_repeat_count = True

    plan_a = compile_session_plan(
        multi_condition_project,
        refresh_hz=60.0,
        project_root=multi_condition_project_root,
        random_seed=2468,
    )
    plan_b = compile_session_plan(
        multi_condition_project,
        refresh_hz=60.0,
        project_root=multi_condition_project_root,
        random_seed=2468,
    )
    counts = _realized_fixation_counts(plan_a)

    assert counts == _realized_fixation_counts(plan_b)
    assert all(1 <= count <= 3 for count in counts)
    assert all(left != right for left, right in zip(counts, counts[1:]))


def test_session_plan_fixed_color_changes_per_condition_produce_expected_realized_count(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    fixation = multi_condition_project.settings.fixation_task
    fixation.enabled = True
    fixation.target_count_mode = "fixed"
    fixation.changes_per_sequence = 4

    session_plan = compile_session_plan(
        multi_condition_project,
        refresh_hz=60.0,
        project_root=multi_condition_project_root,
        random_seed=1357,
    )

    assert _realized_fixation_counts(session_plan) == [4] * session_plan.total_runs


def test_session_plan_compile_error_identifies_the_failing_condition(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    multi_condition_project.settings.session.randomize_conditions_per_block = False
    multi_condition_project.conditions[2].oddball_cycle_repeats_per_sequence = 2
    fixation = multi_condition_project.settings.fixation_task
    fixation.enabled = True
    fixation.target_count_mode = "fixed"
    fixation.changes_per_sequence = 4
    fixation.target_duration_ms = 230
    fixation.min_gap_ms = 1000
    fixation.max_gap_ms = 3000

    with pytest.raises(CompileError) as exc_info:
        compile_session_plan(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
            random_seed=123,
        )

    message = str(exc_info.value)
    assert "Condition 'Condition 3' (id 'condition-3') failed compilation" in message
    assert "Color changes are distributed across the full condition duration." in message
    assert "Minimum cycle count needed at 60.00 Hz: 8 total (8 per condition repeat" in message
