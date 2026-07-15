"""Run-spec compiler tests."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from fpvs_studio.core.compiler import CompileError, compile_run_spec
from fpvs_studio.core.compiler_schedules import build_trigger_events
from fpvs_studio.core.enums import DutyCycleMode, StimulusModality, StimulusVariant
from fpvs_studio.core.run_spec import StimulusEvent, TriggerEvent
from fpvs_studio.preprocessing.importer import materialize_project_assets


def test_runspec_creation_at_60hz_continuous_mode(sample_project, sample_project_root) -> None:
    run_spec = compile_run_spec(sample_project, refresh_hz=60.0, project_root=sample_project_root)

    assert run_spec.display.frames_per_stimulus == 10
    assert run_spec.display.background_color == "#000000"
    assert run_spec.display.stimulus_width_degrees == 5.0
    assert run_spec.display.viewing_distance_cm == 80.0
    assert run_spec.display.screen_width_cm == 52.03
    assert run_spec.display.screen_width_px == 1920
    assert run_spec.display.screen_height_px == 1080
    assert run_spec.display.use_current_screen_resolution is False
    assert run_spec.display.on_frames == 10
    assert run_spec.display.off_frames == 0
    assert run_spec.condition.total_stimuli == 730
    assert run_spec.condition.show_title_on_screen is False
    assert run_spec.display.total_frames == 7300
    assert len(run_spec.stimulus_sequence) == 730
    assert run_spec.fixation.cross_size_px == 27
    assert run_spec.fixation.line_width_px == 2
    assert run_spec.fixation.target_duration_frames == 15
    assert len(run_spec.fixation_events) == 2
    assert run_spec.trigger_events[0].frame_index == 0


def test_compiler_carries_configured_image_display_geometry(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.settings.display.stimulus_width_degrees = 6.5
    sample_project.settings.display.viewing_distance_cm = 75.0
    sample_project.settings.display.screen_width_cm = 60.0
    sample_project.settings.display.screen_width_px = 1920
    sample_project.settings.display.screen_height_px = 1080
    sample_project.settings.display.use_current_screen_resolution = True

    run_spec = compile_run_spec(sample_project, refresh_hz=60.0, project_root=sample_project_root)

    assert run_spec.display.stimulus_width_degrees == 6.5
    assert run_spec.display.viewing_distance_cm == 75.0
    assert run_spec.display.screen_width_cm == 60.0
    assert run_spec.display.screen_width_px == 1920
    assert run_spec.display.screen_height_px == 1080
    assert run_spec.display.use_current_screen_resolution is True


def test_compiler_accepts_different_square_source_resolutions(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.stimulus_sets[0].resolution = sample_project.stimulus_sets[
        0
    ].resolution.model_copy(update={"width_px": 512, "height_px": 512})
    sample_project.stimulus_sets[1].resolution = sample_project.stimulus_sets[
        1
    ].resolution.model_copy(update={"width_px": 1024, "height_px": 1024})

    run_spec = compile_run_spec(sample_project, refresh_hz=60.0, project_root=sample_project_root)

    assert run_spec.condition.total_stimuli == 730


@pytest.mark.parametrize(
    ("role_index", "width_px", "height_px", "message"),
    [
        (0, 512, 384, "Base stimulus set"),
        (1, 1024, 768, "Oddball stimulus set"),
    ],
)
def test_compiler_rejects_non_square_source_resolutions(
    sample_project,
    sample_project_root,
    role_index: int,
    width_px: int,
    height_px: int,
    message: str,
) -> None:
    sample_project.stimulus_sets[role_index].resolution = sample_project.stimulus_sets[
        role_index
    ].resolution.model_copy(update={"width_px": width_px, "height_px": height_px})

    with pytest.raises(CompileError, match=message):
        compile_run_spec(sample_project, refresh_hz=60.0, project_root=sample_project_root)


def test_compiler_rejects_unresolved_mixed_source_resolution(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.stimulus_sets[0].resolution = None

    with pytest.raises(CompileError, match="must be normalized to square images"):
        compile_run_spec(sample_project, refresh_hz=60.0, project_root=sample_project_root)


def test_compiler_schedules_condition_and_oddball_triggers_from_stimulus_onsets(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.settings.fixation_task.enabled = False
    sample_project.conditions[0].oddball_cycle_repeats_per_sequence = 2

    run_spec = compile_run_spec(sample_project, refresh_hz=60.0, project_root=sample_project_root)
    oddball_start_frames = [
        event.on_start_frame for event in run_spec.stimulus_sequence if event.role == "oddball"
    ]

    assert [(event.frame_index, event.code, event.label) for event in run_spec.trigger_events] == [
        (run_spec.stimulus_sequence[0].on_start_frame, 1, "condition_start"),
        *[(frame_index, 55, "oddball_onset") for frame_index in oddball_start_frames],
    ]


def test_compiler_uses_configured_oddball_trigger_code(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.settings.fixation_task.enabled = False
    sample_project.settings.triggers.oddball_trigger_code = 88
    sample_project.settings.triggers.allow_nonstandard_oddball_trigger_code = True
    sample_project.conditions[0].oddball_cycle_repeats_per_sequence = 1

    run_spec = compile_run_spec(sample_project, refresh_hz=60.0, project_root=sample_project_root)

    assert [event.code for event in run_spec.trigger_events if event.label == "oddball_onset"] == [
        88
    ]


def test_compiler_carries_condition_title_display_setting(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.settings.session.show_condition_title_on_screen = True

    run_spec = compile_run_spec(sample_project, refresh_hz=60.0, project_root=sample_project_root)

    assert run_spec.condition.show_title_on_screen is True


def test_compiler_rejects_nonstandard_oddball_trigger_code_without_explicit_override(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.settings.fixation_task.enabled = False
    sample_project.settings.triggers.oddball_trigger_code = 88
    sample_project.conditions[0].oddball_cycle_repeats_per_sequence = 1

    with pytest.raises(CompileError, match="locked to 55"):
        compile_run_spec(sample_project, refresh_hz=60.0, project_root=sample_project_root)


def test_compiler_trigger_schedule_is_deterministic(sample_project, sample_project_root) -> None:
    sample_project.settings.fixation_task.enabled = False
    sample_project.conditions[0].oddball_cycle_repeats_per_sequence = 2

    run_spec_a = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=42,
        run_id="run-a",
    )
    run_spec_b = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=42,
        run_id="run-b",
    )

    assert [event.model_dump() for event in run_spec_a.trigger_events] == [
        event.model_dump() for event in run_spec_b.trigger_events
    ]


def test_compiler_rejects_same_frame_trigger_collisions() -> None:
    oddball_first_sequence = [
        StimulusEvent(
            sequence_index=0,
            role="oddball",
            stimulus_modality=StimulusModality.IMAGE,
            stimulus_id="oddball-set-original-0001",
            image_path="stimuli/original-images/oddball-set/oddball-set-01.png",
            on_start_frame=0,
            on_frames=1,
            off_frames=0,
        )
    ]

    with pytest.raises(CompileError, match="Frame 0 contains condition_start=12 and"):
        build_trigger_events(
            stimulus_sequence=oddball_first_sequence,
            condition_trigger_code=12,
            oddball_trigger_code=55,
        )

    with pytest.raises(CompileError, match="Frame 0 contains condition_start=55 and"):
        build_trigger_events(
            stimulus_sequence=oddball_first_sequence,
            condition_trigger_code=55,
            oddball_trigger_code=55,
        )


def test_trigger_schedule_rejects_exact_duplicate_events() -> None:
    from fpvs_studio.core.compiler_schedules import _validate_and_sort_trigger_events

    with pytest.raises(CompileError, match="Frame 12 contains oddball_onset=55 and"):
        _validate_and_sort_trigger_events(
            [
                TriggerEvent(frame_index=12, code=55, label="oddball_onset"),
                TriggerEvent(frame_index=12, code=55, label="oddball_onset"),
            ]
        )


def test_compiler_rejects_missing_or_reset_condition_trigger_code() -> None:
    sequence = [
        StimulusEvent(
            sequence_index=0,
            role="base",
            stimulus_modality=StimulusModality.IMAGE,
            stimulus_id="base-set-original-0001",
            image_path="stimuli/original-images/base-set/base-set-01.png",
            on_start_frame=0,
            on_frames=1,
            off_frames=0,
        )
    ]

    with pytest.raises(TypeError, match="condition_start trigger code must be an integer"):
        build_trigger_events(
            stimulus_sequence=sequence,
            condition_trigger_code=None,  # type: ignore[arg-type]
            oddball_trigger_code=55,
        )

    with pytest.raises(ValueError, match="condition_start trigger code must be an integer"):
        build_trigger_events(
            stimulus_sequence=sequence,
            condition_trigger_code=0,
            oddball_trigger_code=55,
        )


def test_trigger_event_rejects_reset_code_for_normal_events() -> None:
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        TriggerEvent(frame_index=0, code=0, label="condition_start")


def test_runspec_creation_at_120hz_blank_50_mode(sample_project, sample_project_root) -> None:
    sample_project.conditions[0].duty_cycle_mode = DutyCycleMode.BLANK_50

    run_spec = compile_run_spec(sample_project, refresh_hz=120.0, project_root=sample_project_root)

    assert run_spec.display.frames_per_stimulus == 20
    assert run_spec.display.on_frames == 10
    assert run_spec.display.off_frames == 10


def test_compiler_accepts_approximate_refresh_with_whole_frame_timing(
    sample_project,
    sample_project_root,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=59.94,
        project_root=sample_project_root,
    )

    assert run_spec.display.frames_per_stimulus == 10
    assert run_spec.condition.base_hz == 6.0
    assert all(event.on_frames == 10 for event in run_spec.stimulus_sequence)


def test_compiler_rejects_blank_mode_odd_frame_cycles(sample_project) -> None:
    sample_project.conditions[0].duty_cycle_mode = DutyCycleMode.BLANK_50
    sample_project.settings.protocol.base_hz = 4.0

    with pytest.raises(CompileError, match="blank_50"):
        compile_run_spec(sample_project, refresh_hz=60.0)


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


@pytest.mark.parametrize(
    ("refresh_hz", "expected_base_frame_step", "expected_oddball_frame_step"),
    [
        (60.0, 10, 60),
        (120.0, 20, 120),
        (144.0, 24, 144),
        (240.0, 40, 240),
    ],
)
def test_compiler_supports_configured_6hz_base_with_1hz_oddball(
    sample_project,
    sample_project_root,
    refresh_hz: float,
    expected_base_frame_step: int,
    expected_oddball_frame_step: int,
) -> None:
    sample_project.settings.protocol.oddball_every_n = 6

    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=refresh_hz,
        project_root=sample_project_root,
    )
    oddball_start_frames = [
        event.on_start_frame for event in run_spec.stimulus_sequence if event.role == "oddball"
    ]

    assert run_spec.condition.base_hz == 6.0
    assert run_spec.condition.oddball_every_n == 6
    assert run_spec.condition.oddball_hz == 1.0
    assert run_spec.condition.total_stimuli == 876
    assert run_spec.display.frames_per_stimulus == expected_base_frame_step
    assert all(
        b - a == expected_oddball_frame_step
        for a, b in zip(oddball_start_frames, oddball_start_frames[1:], strict=False)
    )


def test_compiler_assigns_image_paths_with_seeded_full_pool_shuffle(
    sample_project, sample_project_root
) -> None:
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
    run_spec_c = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=2027,
        run_id="run-c",
    )
    base_paths = [
        event.image_path for event in run_spec_a.stimulus_sequence if event.role == "base"
    ]
    oddball_paths = [
        event.image_path for event in run_spec_a.stimulus_sequence if event.role == "oddball"
    ]

    assert [event.image_path for event in run_spec_a.stimulus_sequence] == [
        event.image_path for event in run_spec_b.stimulus_sequence
    ]
    assert [event.image_path for event in run_spec_a.stimulus_sequence] != [
        event.image_path for event in run_spec_c.stimulus_sequence
    ]
    assert set(base_paths[:3]) == {
        "stimuli/original-images/base-set/base-set-01.png",
        "stimuli/original-images/base-set/base-set-02.png",
        "stimuli/original-images/base-set/base-set-03.png",
    }
    assert set(oddball_paths[:3]) == {
        "stimuli/original-images/oddball-set/oddball-set-01.png",
        "stimuli/original-images/oddball-set/oddball-set-02.png",
        "stimuli/original-images/oddball-set/oddball-set-03.png",
    }


def test_compiler_preserves_current_image_schedule_contract(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.settings.fixation_task.enabled = False
    sample_project.conditions[0].oddball_cycle_repeats_per_sequence = 2

    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=2026,
    )
    first_events = run_spec.stimulus_sequence[:10]

    assert [
        (
            event.sequence_index,
            event.role,
            event.stimulus_modality,
            event.stimulus_id,
            event.image_path,
            event.text,
            event.on_start_frame,
            event.on_frames,
            event.off_frames,
        )
        for event in first_events
    ] == [
        (
            0,
            "base",
            StimulusModality.IMAGE,
            "base-set-original-0003",
            "stimuli/original-images/base-set/base-set-03.png",
            None,
            0,
            10,
            0,
        ),
        (
            1,
            "base",
            StimulusModality.IMAGE,
            "base-set-original-0002",
            "stimuli/original-images/base-set/base-set-02.png",
            None,
            10,
            10,
            0,
        ),
        (
            2,
            "base",
            StimulusModality.IMAGE,
            "base-set-original-0001",
            "stimuli/original-images/base-set/base-set-01.png",
            None,
            20,
            10,
            0,
        ),
        (
            3,
            "base",
            StimulusModality.IMAGE,
            "base-set-original-0001",
            "stimuli/original-images/base-set/base-set-01.png",
            None,
            30,
            10,
            0,
        ),
        (
            4,
            "oddball",
            StimulusModality.IMAGE,
            "oddball-set-original-0002",
            "stimuli/original-images/oddball-set/oddball-set-02.png",
            None,
            40,
            10,
            0,
        ),
        (
            5,
            "base",
            StimulusModality.IMAGE,
            "base-set-original-0002",
            "stimuli/original-images/base-set/base-set-02.png",
            None,
            50,
            10,
            0,
        ),
        (
            6,
            "base",
            StimulusModality.IMAGE,
            "base-set-original-0003",
            "stimuli/original-images/base-set/base-set-03.png",
            None,
            60,
            10,
            0,
        ),
        (
            7,
            "base",
            StimulusModality.IMAGE,
            "base-set-original-0001",
            "stimuli/original-images/base-set/base-set-01.png",
            None,
            70,
            10,
            0,
        ),
        (
            8,
            "base",
            StimulusModality.IMAGE,
            "base-set-original-0002",
            "stimuli/original-images/base-set/base-set-02.png",
            None,
            80,
            10,
            0,
        ),
        (
            9,
            "oddball",
            StimulusModality.IMAGE,
            "oddball-set-original-0001",
            "stimuli/original-images/oddball-set/oddball-set-01.png",
            None,
            90,
            10,
            0,
        ),
    ]


def test_compiler_schedules_word_stimuli_with_identical_timing(
    sample_project,
) -> None:
    sample_project.settings.fixation_task.enabled = False
    sample_project.conditions[0].oddball_cycle_repeats_per_sequence = 2
    sample_project.stimulus_sets[0] = sample_project.stimulus_sets[0].model_copy(
        update={
            "modality": StimulusModality.WORD,
            "source_dir": None,
            "resolution": None,
            "image_count": 0,
            "words": ["cat", "dog", "cat"],
        }
    )
    sample_project.stimulus_sets[1] = sample_project.stimulus_sets[1].model_copy(
        update={
            "modality": StimulusModality.WORD,
            "source_dir": None,
            "resolution": None,
            "image_count": 0,
            "words": ["tool", "chair"],
        }
    )

    run_spec = compile_run_spec(sample_project, refresh_hz=60.0, random_seed=2026)

    assert run_spec.condition.stimulus_modality == StimulusModality.WORD
    assert [
        (event.sequence_index, event.role, event.on_start_frame, event.on_frames, event.off_frames)
        for event in run_spec.stimulus_sequence[:10]
    ] == [
        (0, "base", 0, 10, 0),
        (1, "base", 10, 10, 0),
        (2, "base", 20, 10, 0),
        (3, "base", 30, 10, 0),
        (4, "oddball", 40, 10, 0),
        (5, "base", 50, 10, 0),
        (6, "base", 60, 10, 0),
        (7, "base", 70, 10, 0),
        (8, "base", 80, 10, 0),
        (9, "oddball", 90, 10, 0),
    ]
    assert all(
        event.stimulus_modality == StimulusModality.WORD
        for event in run_spec.stimulus_sequence
    )
    assert all(event.image_path is None for event in run_spec.stimulus_sequence)
    assert {"base-set-word-0001", "base-set-word-0003"}.issubset(
        {event.stimulus_id for event in run_spec.stimulus_sequence if event.text == "cat"}
    )


def test_compiler_rejects_mixed_modality_condition(sample_project) -> None:
    sample_project.stimulus_sets[1] = sample_project.stimulus_sets[1].model_copy(
        update={
            "modality": StimulusModality.WORD,
            "source_dir": None,
            "resolution": None,
            "image_count": 0,
            "words": ["tool"],
        }
    )

    with pytest.raises(CompileError, match="cannot mix base image stimuli with oddball word"):
        compile_run_spec(sample_project, refresh_hz=60.0)


def test_compiler_rejects_same_base_and_oddball_folder(sample_project) -> None:
    sample_project.stimulus_sets[1] = sample_project.stimulus_sets[1].model_copy(
        update={"source_dir": sample_project.stimulus_sets[0].source_dir}
    )

    with pytest.raises(CompileError, match="same folder for base and oddball images"):
        compile_run_spec(sample_project, refresh_hz=60.0)


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


def test_compile_run_spec_carries_participant_tutorial_flag_only_when_accuracy_enabled(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.settings.fixation_task.enabled = True
    sample_project.settings.fixation_task.accuracy_task_enabled = True
    sample_project.settings.fixation_task.participant_tutorial_enabled = True

    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
    )

    assert run_spec.fixation.participant_tutorial_enabled is True

    sample_project.settings.fixation_task.accuracy_task_enabled = False
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
    )

    assert run_spec.fixation.participant_tutorial_enabled is False


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
    run_spec_c = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=2027,
        run_id="run-c",
    )

    assert 2 <= run_spec_a.fixation.realized_target_count <= 4
    assert run_spec_a.fixation.realized_target_count == run_spec_b.fixation.realized_target_count
    assert [event.start_frame for event in run_spec_a.fixation_events] == [
        event.start_frame for event in run_spec_b.fixation_events
    ]
    assert [event.start_frame for event in run_spec_a.fixation_events] != [
        event.start_frame for event in run_spec_c.fixation_events
    ]
    assert [event.start_frame for event in run_spec_a.fixation_events] == sorted(
        event.start_frame for event in run_spec_a.fixation_events
    )


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
