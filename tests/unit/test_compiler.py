"""Run-spec compiler tests."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from fpvs_studio.core.compiler import CompileError, compile_run_spec
from fpvs_studio.core.enums import DutyCycleMode, StimulusVariant
from fpvs_studio.preprocessing.importer import materialize_project_assets


def test_runspec_creation_at_60hz_continuous_mode(sample_project, sample_project_root) -> None:
    run_spec = compile_run_spec(sample_project, refresh_hz=60.0, project_root=sample_project_root)

    assert run_spec.display.frames_per_stimulus == 10
    assert run_spec.display.background_color == "#000000"
    assert run_spec.display.on_frames == 10
    assert run_spec.display.off_frames == 0
    assert run_spec.condition.total_stimuli == 730
    assert run_spec.display.total_frames == 7300
    assert len(run_spec.stimulus_sequence) == 730
    assert run_spec.fixation.cross_size_px == 48
    assert run_spec.fixation.line_width_px == 4
    assert run_spec.fixation.target_duration_frames == 15
    assert len(run_spec.fixation_events) == 2
    assert run_spec.trigger_events[0].frame_index == 0


def test_runspec_creation_at_120hz_blank_50_mode(sample_project, sample_project_root) -> None:
    sample_project.conditions[0].duty_cycle_mode = DutyCycleMode.BLANK_50

    run_spec = compile_run_spec(sample_project, refresh_hz=120.0, project_root=sample_project_root)

    assert run_spec.display.frames_per_stimulus == 20
    assert run_spec.display.on_frames == 10
    assert run_spec.display.off_frames == 10


def test_compiler_rejects_unsupported_refresh_rates(sample_project) -> None:
    with pytest.raises(CompileError, match="incompatible"):
        compile_run_spec(sample_project, refresh_hz=75.0)


def test_compiler_rejects_blank_mode_odd_frame_cycles(sample_project) -> None:
    sample_project.conditions[0].duty_cycle_mode = DutyCycleMode.BLANK_50

    with pytest.raises(CompileError, match="blank_50"):
        compile_run_spec(sample_project, refresh_hz=90.0)


def test_compiler_generates_deterministic_role_schedule(
    sample_project, sample_project_root
) -> None:
    run_spec = compile_run_spec(sample_project, refresh_hz=60.0, project_root=sample_project_root)
    roles = [event.role for event in run_spec.stimulus_sequence]
    role_counts = Counter(roles)

    assert role_counts["oddball"] == 146
    assert role_counts["base"] == 584
    assert all(role == "oddball" for role in roles[4::5])
    assert all(role == "base" for index, role in enumerate(roles) if (index + 1) % 5 != 0)


@pytest.mark.parametrize(
    ("refresh_hz", "expected_base_frame_step", "expected_oddball_frame_step"),
    [
        (60.0, 10, 50),
        (120.0, 20, 100),
    ],
)
def test_compiler_keeps_base_and_oddball_frame_cadence_locked(
    sample_project,
    sample_project_root,
    refresh_hz: float,
    expected_base_frame_step: int,
    expected_oddball_frame_step: int,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=refresh_hz,
        project_root=sample_project_root,
    )
    stimulus_start_frames = [event.on_start_frame for event in run_spec.stimulus_sequence]
    oddball_start_frames = [
        event.on_start_frame for event in run_spec.stimulus_sequence if event.role == "oddball"
    ]

    assert run_spec.display.frames_per_stimulus == expected_base_frame_step
    assert all(
        b - a == expected_base_frame_step
        for a, b in zip(stimulus_start_frames, stimulus_start_frames[1:], strict=False)
    )
    assert all(
        b - a == expected_oddball_frame_step
        for a, b in zip(oddball_start_frames, oddball_start_frames[1:], strict=False)
    )


def test_compiler_assigns_image_paths_deterministically(
    sample_project, sample_project_root
) -> None:
    run_spec_a = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="run-a",
    )
    run_spec_b = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="run-b",
    )
    first_five_paths = [event.image_path for event in run_spec_a.stimulus_sequence[:5]]

    assert [event.image_path for event in run_spec_a.stimulus_sequence] == [
        event.image_path for event in run_spec_b.stimulus_sequence
    ]
    assert first_five_paths == [
        "stimuli/original-images/base-set/base-set-01.png",
        "stimuli/original-images/base-set/base-set-02.png",
        "stimuli/original-images/base-set/base-set-03.png",
        "stimuli/original-images/base-set/base-set-01.png",
        "stimuli/original-images/oddball-set/oddball-set-01.png",
    ]


def test_compile_run_spec_still_requires_one_condition_when_project_has_many(
    multi_condition_project,
    multi_condition_project_root,
) -> None:
    with pytest.raises(CompileError, match="condition_id is required"):
        compile_run_spec(
            multi_condition_project,
            refresh_hz=60.0,
            project_root=multi_condition_project_root,
        )


def test_compiler_resolves_manifest_backed_variant_paths(
    sample_project,
    sample_project_root,
) -> None:
    materialize_project_assets(sample_project, project_root=sample_project_root)
    sample_project.conditions[0].stimulus_variant = StimulusVariant.GRAYSCALE

    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
    )
    first_path = run_spec.stimulus_sequence[0].image_path

    assert first_path.startswith("stimuli/generated-variants/base-set/grayscale-variants/")
    assert (sample_project_root / Path(first_path)).is_file()


def test_compile_run_spec_fixed_color_changes_per_condition_mode_uses_configured_count(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.settings.fixation_task.enabled = True
    sample_project.settings.fixation_task.target_count_mode = "fixed"
    sample_project.settings.fixation_task.changes_per_sequence = 5

    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
    )

    assert run_spec.fixation.realized_target_count == 5
    assert len(run_spec.fixation_events) == 5


def test_compile_run_spec_randomized_target_count_is_seed_deterministic(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.settings.fixation_task.enabled = True
    sample_project.settings.fixation_task.target_count_mode = "randomized"
    sample_project.settings.fixation_task.target_count_min = 2
    sample_project.settings.fixation_task.target_count_max = 4

    run_spec_a = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=2026,
        run_id="run-a",
    )
    run_spec_b = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=2026,
        run_id="run-b",
    )

    assert 2 <= run_spec_a.fixation.realized_target_count <= 4
    assert run_spec_a.fixation.realized_target_count == run_spec_b.fixation.realized_target_count
    assert [event.start_frame for event in run_spec_a.fixation_events] == [
        event.start_frame for event in run_spec_b.fixation_events
    ]


def test_compile_run_spec_reports_minimum_cycles_when_fixation_settings_do_not_fit(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.conditions[0].oddball_cycle_repeats_per_sequence = 2
    fixation = sample_project.settings.fixation_task
    fixation.enabled = True
    fixation.target_count_mode = "fixed"
    fixation.changes_per_sequence = 4
    fixation.target_duration_ms = 230
    fixation.min_gap_ms = 1000
    fixation.max_gap_ms = 3000

    with pytest.raises(CompileError) as exc_info:
        compile_run_spec(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
        )

    message = str(exc_info.value)
    assert "Condition 'Faces' duration:" in message
    assert "Required duration:" in message
    assert "Color changes are distributed across the full condition duration." in message
    assert "reduce color-change count per condition" in message
    assert "Minimum cycle count needed at 60.00 Hz: 8 total (8 per condition repeat" in message
