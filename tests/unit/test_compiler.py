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


def test_compiler_generates_deterministic_role_schedule(sample_project, sample_project_root) -> None:
    run_spec = compile_run_spec(sample_project, refresh_hz=60.0, project_root=sample_project_root)
    roles = [event.role for event in run_spec.stimulus_sequence]
    role_counts = Counter(roles)

    assert role_counts["oddball"] == 146
    assert role_counts["base"] == 584
    assert all(role == "oddball" for role in roles[4::5])
    assert all(role == "base" for index, role in enumerate(roles) if (index + 1) % 5 != 0)


def test_compiler_assigns_image_paths_deterministically(sample_project, sample_project_root) -> None:
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
        "stimuli/source/base-set/originals/base-set-01.png",
        "stimuli/source/base-set/originals/base-set-02.png",
        "stimuli/source/base-set/originals/base-set-03.png",
        "stimuli/source/base-set/originals/base-set-01.png",
        "stimuli/source/oddball-set/originals/oddball-set-01.png",
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

    assert first_path.startswith("stimuli/derived/base-set/grayscale/")
    assert (sample_project_root / Path(first_path)).is_file()
