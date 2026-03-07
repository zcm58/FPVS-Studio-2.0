"""Session-plan compilation tests."""

from __future__ import annotations

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.enums import InterConditionMode


def _block_orders(session_plan) -> list[list[str]]:
    return [block.condition_order for block in session_plan.blocks]


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
