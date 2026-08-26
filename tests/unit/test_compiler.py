"""Run-spec compiler tests."""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

import pytest

from fpvs_studio.core import compiler_schedules
from fpvs_studio.core.compiler import CompileError, compile_run_spec
from fpvs_studio.core.compiler_presentation import build_interleaved_text_height_values
from fpvs_studio.core.compiler_schedules import (
    StimulusScheduleItem,
    boundary_aware_shuffled_bag,
    build_stimulus_sequence,
    build_trigger_events,
)
from fpvs_studio.core.display_geometry import visual_angle_width_px
from fpvs_studio.core.enums import (
    DutyCycleMode,
    ImageGeometryMode,
    PresentationUnit,
    StimulusModality,
    StimulusTransform,
    StimulusVariant,
    TextHeightMode,
)
from fpvs_studio.core.migrations import migrate_project_payload
from fpvs_studio.core.models import (
    ImageGeometrySettings,
    StimulusPresentationOverride,
    TextHeightScheduleSettings,
    TextPositionSettings,
)
from fpvs_studio.core.run_spec import StimulusEvent, TriggerEvent
from fpvs_studio.preprocessing.importer import materialize_project_assets


def test_runspec_creation_at_60hz_continuous_mode(sample_project, sample_project_root) -> None:
    run_spec = compile_run_spec(sample_project, refresh_hz=60.0, project_root=sample_project_root)

    assert run_spec.display.frames_per_stimulus == 10
    assert run_spec.display.background_color == "#000000"
    assert run_spec.display.stimulus_width_degrees == 5.0
    assert run_spec.display.viewing_distance_cm == 80.0
    assert run_spec.display.screen_width_cm == 52.0
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
def test_compiler_accepts_uniform_rectangular_source_resolutions(
    sample_project,
    sample_project_root,
    role_index: int,
    width_px: int,
    height_px: int,
    message: str,  # noqa: ARG001
) -> None:
    sample_project.stimulus_sets[role_index].resolution = sample_project.stimulus_sets[
        role_index
    ].resolution.model_copy(update={"width_px": width_px, "height_px": height_px})

    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
    )

    role = "base" if role_index == 0 else "oddball"
    role_spec = getattr(run_spec.presentation, role)
    assert role_spec.image_geometry.source_resolution.width_px == width_px
    assert role_spec.image_geometry.source_resolution.height_px == height_px


def test_compiler_rejects_unresolved_mixed_source_resolution(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.stimulus_sets[0].resolution = None

    with pytest.raises(CompileError, match="known uniform image resolution"):
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


def test_compiler_image_schedule_has_no_immediate_displayed_repeats(
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
    paths = [event.image_path for event in run_spec.stimulus_sequence]

    assert all(previous != current for previous, current in zip(paths, paths[1:], strict=False))
    assert paths[:4] == [
        "stimuli/original-images/base-set/base-set-03.png",
        "stimuli/original-images/base-set/base-set-01.png",
        "stimuli/original-images/base-set/base-set-02.png",
        "stimuli/original-images/base-set/base-set-01.png",
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
        event.stimulus_modality == StimulusModality.WORD for event in run_spec.stimulus_sequence
    )
    assert all(event.image_path is None for event in run_spec.stimulus_sequence)
    assert {"base-set-word-0001", "base-set-word-0003"}.issubset(
        {event.stimulus_id for event in run_spec.stimulus_sequence if event.text == "cat"}
    )


@pytest.mark.parametrize(
    ("stimulus_width_degrees", "viewing_distance_cm", "screen_width_cm", "screen_width_px"),
    [
        (5.0, 80.0, 52.03, 1920),
        (8.0, 57.0, 50.0, 1920),
        (5.0, 70.0, 34.5, 1366),
        (10.0, 100.0, 60.0, 2560),
    ],
)
def test_compiled_v1_word_height_preserves_legacy_intermediate_pixel_rounding(
    sample_project,
    stimulus_width_degrees: float,
    viewing_distance_cm: float,
    screen_width_cm: float,
    screen_width_px: int,
) -> None:
    payload = sample_project.model_dump(mode="json")
    payload["schema_version"] = "1.0.0"
    payload["settings"].pop("presentation")
    display = payload["settings"]["display"]
    display.update(
        {
            "stimulus_width_degrees": stimulus_width_degrees,
            "viewing_distance_cm": viewing_distance_cm,
            "screen_width_cm": screen_width_cm,
            "screen_width_px": screen_width_px,
        }
    )
    for condition in payload["conditions"]:
        condition.pop("presentation")
    for stimulus_set in payload["stimulus_sets"]:
        stimulus_set.update(
            {
                "modality": StimulusModality.WORD.value,
                "source_dir": None,
                "resolution": None,
                "image_count": 0,
                "words": ["word-a", "word-b"],
            }
        )
    project = migrate_project_payload(payload)

    run_spec = compile_run_spec(project, refresh_hz=60.0, random_seed=2026)

    assert run_spec.presentation is not None
    text_spec = run_spec.presentation.base.text
    assert text_spec is not None
    assert text_spec.legacy_stimulus_width_fraction == 0.25
    legacy_stimulus_width_px = visual_angle_width_px(
        degrees=run_spec.display.stimulus_width_degrees,
        viewing_distance_cm=run_spec.display.viewing_distance_cm,
        screen_width_cm=run_spec.display.screen_width_cm,
        screen_width_px=run_spec.display.screen_width_px,
    )
    old_renderer_height_px = max(1, round(legacy_stimulus_width_px * 0.25))
    compiled_compatibility_height_px = max(
        1,
        round(legacy_stimulus_width_px * text_spec.legacy_stimulus_width_fraction),
    )
    assert compiled_compatibility_height_px == old_renderer_height_px


def test_compiler_resolves_role_presentation_inheritance_and_lead_in(sample_project) -> None:
    sample_project.settings.fixation_task.enabled = False
    sample_project.settings.presentation.pre_stream_fixation_seconds = 2.0
    sample_project.settings.presentation.defaults.text_color = "#112233"
    sample_project.conditions[0].presentation.common = StimulusPresentationOverride(
        transform=StimulusTransform.MIRROR_VERTICAL,
        image_geometry=ImageGeometrySettings(
            mode=ImageGeometryMode.EXACT_BOX,
            width_degrees=5.0,
            height_degrees=6.25,
        ),
    )
    sample_project.conditions[0].presentation.oddball = StimulusPresentationOverride(
        transform=StimulusTransform.MIRROR_HORIZONTAL,
    )

    run_spec = compile_run_spec(sample_project, refresh_hz=60.0, random_seed=9)

    assert run_spec.pre_stream_fixation_frames == 120
    assert run_spec.presentation.base.transform == StimulusTransform.MIRROR_VERTICAL
    assert run_spec.presentation.oddball.transform == StimulusTransform.MIRROR_HORIZONTAL
    assert run_spec.presentation.base.image_geometry.mode == ImageGeometryMode.EXACT_BOX
    assert run_spec.presentation.base.image_geometry.width_degrees == 5.0
    assert run_spec.presentation.base.image_geometry.height_degrees == 6.25


def test_compiler_balances_random_word_heights_without_perturbing_stimulus_order(
    sample_project,
) -> None:
    sample_project.settings.fixation_task.enabled = False
    sample_project.conditions[0].oddball_cycle_repeats_per_sequence = 8
    sample_project.stimulus_sets[0] = sample_project.stimulus_sets[0].model_copy(
        update={
            "modality": StimulusModality.WORD,
            "source_dir": None,
            "resolution": None,
            "image_count": 0,
            "words": ["cat", "dog", "bird"],
        }
    )
    sample_project.stimulus_sets[1] = sample_project.stimulus_sets[1].model_copy(
        update={
            "modality": StimulusModality.WORD,
            "source_dir": None,
            "resolution": None,
            "image_count": 0,
            "words": ["tool", "chair", "table"],
        }
    )
    baseline = compile_run_spec(sample_project, refresh_hz=60.0, random_seed=2026)
    schedule = TextHeightScheduleSettings(
        mode=TextHeightMode.BALANCED_RANDOMIZED,
        unit=PresentationUnit.WINDOW_HEIGHT_FRACTION,
        values=[0.03, 0.05, 0.07],
    )
    sample_project.conditions[0].presentation.base = StimulusPresentationOverride(
        text_height=schedule,
        text_position=TextPositionSettings(
            unit=PresentationUnit.WINDOW_HEIGHT_FRACTION,
            x=0.0,
            y=0.02,
        ),
    )
    sample_project.conditions[0].presentation.oddball = StimulusPresentationOverride(
        transform=StimulusTransform.MIRROR_HORIZONTAL,
        text_height=schedule,
    )

    styled = compile_run_spec(sample_project, refresh_hz=60.0, random_seed=2026)

    assert [event.text for event in styled.stimulus_sequence] == [
        event.text for event in baseline.stimulus_sequence
    ]
    heights = [event.text_height_value for event in styled.stimulus_sequence]
    assert all(previous != current for previous, current in zip(heights, heights[1:], strict=False))
    assert styled.presentation.base.text.font_name == "Arial"
    assert styled.presentation.base.text.height_unit == PresentationUnit.WINDOW_HEIGHT_FRACTION
    assert styled.presentation.base.text.position_y == 0.02
    assert styled.presentation.oddball.transform == StimulusTransform.MIRROR_HORIZONTAL

    per_role = {
        role: [event.text_height_value for event in styled.stimulus_sequence if event.role == role]
        for role in ("base", "oddball")
    }
    for values in per_role.values():
        counts = Counter(values)
        assert max(counts.values()) - min(counts.values()) <= 1


def test_compiler_avoids_cross_role_repeat_for_overlapping_word_pools(sample_project) -> None:
    sample_project.settings.fixation_task.enabled = False
    sample_project.conditions[0].oddball_cycle_repeats_per_sequence = 8
    for stimulus_set in sample_project.stimulus_sets:
        replacement_words = ["shared", "alternative", "third"]
        updated = stimulus_set.model_copy(
            update={
                "modality": StimulusModality.WORD,
                "source_dir": None,
                "resolution": None,
                "image_count": 0,
                "words": replacement_words,
            }
        )
        sample_project.stimulus_sets[sample_project.stimulus_sets.index(stimulus_set)] = updated

    run_spec = compile_run_spec(sample_project, refresh_hz=60.0, random_seed=7)
    words = [event.text for event in run_spec.stimulus_sequence]

    assert all(previous != current for previous, current in zip(words, words[1:], strict=False))


def test_stimulus_schedule_looks_ahead_to_singleton_oddball_pool() -> None:
    sequence = build_stimulus_sequence(
        total_stimuli=2,
        frames_per_stimulus_value=10,
        on_frames=10,
        off_frames=0,
        base_stimuli=[
            StimulusScheduleItem(
                stimulus_modality=StimulusModality.WORD,
                stimulus_id="base-a",
                text="A",
            ),
            StimulusScheduleItem(
                stimulus_modality=StimulusModality.WORD,
                stimulus_id="base-b",
                text="B",
            ),
        ],
        oddball_stimuli=[
            StimulusScheduleItem(
                stimulus_modality=StimulusModality.WORD,
                stimulus_id="oddball-a",
                text="A",
            )
        ],
        oddball_every_n=2,
        random_seed=2,
    )

    assert [event.text for event in sequence] == ["B", "A"]


def test_stimulus_role_bags_use_independent_namespaced_random_streams() -> None:
    def item(role: str, value: str) -> StimulusScheduleItem:
        return StimulusScheduleItem(
            stimulus_modality=StimulusModality.WORD,
            stimulus_id=f"{role}-{value.lower()}",
            text=f"{role}-{value}",
        )

    base = [item("base", value) for value in ("A", "B", "C")]
    initial = build_stimulus_sequence(
        total_stimuli=30,
        frames_per_stimulus_value=10,
        on_frames=10,
        off_frames=0,
        base_stimuli=base,
        oddball_stimuli=[item("oddball", value) for value in ("A", "B")],
        oddball_every_n=5,
        random_seed=17,
    )
    changed_oddballs = build_stimulus_sequence(
        total_stimuli=30,
        frames_per_stimulus_value=10,
        on_frames=10,
        off_frames=0,
        base_stimuli=base,
        oddball_stimuli=[item("oddball", value) for value in ("A", "B", "C", "D")],
        oddball_every_n=5,
        random_seed=17,
    )

    assert [event.text for event in initial if event.role == "base"] == [
        event.text for event in changed_oddballs if event.role == "base"
    ]


def test_boundary_aware_bag_avoids_repeats_with_duplicate_payloads() -> None:
    first = boundary_aware_shuffled_bag(
        ["A", "A", "A", "B", "B"],
        rng=random.Random(1),
        previous_key=None,
        key=str,
    )
    second = boundary_aware_shuffled_bag(
        ["A", "A", "A", "B", "B"],
        rng=random.Random(1),
        previous_key=None,
        key=str,
    )

    assert first == second
    assert Counter(first) == Counter({"A": 3, "B": 2})
    assert all(previous != current for previous, current in zip(first, first[1:], strict=False))


def test_boundary_aware_bag_scales_to_large_unique_pool() -> None:
    values = [f"stimulus-{index:05d}" for index in range(10_000)]

    result = boundary_aware_shuffled_bag(
        values,
        rng=random.Random(42),
        previous_key=values[0],
        key=str,
    )

    assert len(result) == len(values)
    assert set(result) == set(values)
    assert result[0] != values[0]
    assert all(previous != current for previous, current in zip(result, result[1:], strict=False))


@pytest.mark.parametrize("duplicate_payloads", [False, True])
def test_stimulus_sequence_scales_linearly_to_large_role_pools(
    monkeypatch: pytest.MonkeyPatch,
    duplicate_payloads: bool,
) -> None:
    base_count = 10_000
    total_stimuli = base_count * 5 // 4

    def make_item(role: str, index: int) -> StimulusScheduleItem:
        displayed_value = (
            ("A" if index % 2 == 0 else "B") if duplicate_payloads else f"{role}-{index:05d}"
        )
        return StimulusScheduleItem(
            stimulus_modality=StimulusModality.WORD,
            stimulus_id=f"{role}-id-{index:05d}",
            text=displayed_value,
        )

    base_items = [make_item("base", index) for index in range(base_count)]
    oddball_items = [make_item("oddball", index) for index in range(total_stimuli // 5)]
    display_key_calls = 0
    original_display_key = compiler_schedules._stimulus_display_key

    def counted_display_key(item: StimulusScheduleItem):
        nonlocal display_key_calls
        display_key_calls += 1
        return original_display_key(item)

    monkeypatch.setattr(
        compiler_schedules,
        "_stimulus_display_key",
        counted_display_key,
    )

    sequence = build_stimulus_sequence(
        total_stimuli=total_stimuli,
        frames_per_stimulus_value=10,
        on_frames=10,
        off_frames=0,
        base_stimuli=base_items,
        oddball_stimuli=oddball_items,
        oddball_every_n=5,
        random_seed=2026,
    )
    displayed_values = [event.text for event in sequence]

    assert len(sequence) == total_stimuli
    assert display_key_calls <= 5 * (len(base_items) + len(oddball_items)) + 10
    assert all(
        previous != current
        for previous, current in zip(displayed_values, displayed_values[1:], strict=False)
    )


def test_stimulus_sequence_uses_global_exact_cycle_counts_to_avoid_end_repeat() -> None:
    def make_item(role: str, index: int) -> StimulusScheduleItem:
        return StimulusScheduleItem(
            stimulus_modality=StimulusModality.WORD,
            stimulus_id=f"{role}-{index:02d}",
            text="A" if index % 2 == 0 else "B",
        )

    base_items = [make_item("base", index) for index in range(20)]
    oddball_items = [make_item("oddball", index) for index in range(5)]

    sequence = build_stimulus_sequence(
        total_stimuli=25,
        frames_per_stimulus_value=10,
        on_frames=10,
        off_frames=0,
        base_stimuli=base_items,
        oddball_stimuli=oddball_items,
        oddball_every_n=5,
        random_seed=2026,
    )
    displayed_values = [event.text for event in sequence]

    assert Counter(event.stimulus_id for event in sequence if event.role == "base") == Counter(
        item.stimulus_id for item in base_items
    )
    assert Counter(event.stimulus_id for event in sequence if event.role == "oddball") == Counter(
        item.stimulus_id for item in oddball_items
    )
    assert all(
        previous != current
        for previous, current in zip(displayed_values, displayed_values[1:], strict=False)
    )


def test_stimulus_sequence_exactly_resolves_small_feasible_cross_role_pool() -> None:
    def item(role: str, value: str) -> StimulusScheduleItem:
        return StimulusScheduleItem(
            stimulus_modality=StimulusModality.WORD,
            stimulus_id=f"{role}-{value.lower()}",
            text=value,
        )

    sequence = build_stimulus_sequence(
        total_stimuli=4,
        frames_per_stimulus_value=10,
        on_frames=10,
        off_frames=0,
        base_stimuli=[item("base", "B"), item("base", "C")],
        oddball_stimuli=[item("oddball", "A"), item("oddball", "B")],
        oddball_every_n=2,
        random_seed=0,
    )
    displayed_values = [event.text for event in sequence]

    assert all(
        previous != current
        for previous, current in zip(displayed_values, displayed_values[1:], strict=False)
    )


def test_stimulus_sequence_resolves_long_feasible_cross_role_bags() -> None:
    def item(role: str, value: str) -> StimulusScheduleItem:
        return StimulusScheduleItem(
            stimulus_modality=StimulusModality.WORD,
            stimulus_id=f"{role}-{value.lower()}",
            text=value,
        )

    authored_by_role = {
        "base": [item("base", "A"), item("base", "B")],
        "oddball": [item("oddball", "A"), item("oddball", "C")],
    }
    sequence = build_stimulus_sequence(
        total_stimuli=735,
        frames_per_stimulus_value=10,
        on_frames=10,
        off_frames=0,
        base_stimuli=authored_by_role["base"],
        oddball_stimuli=authored_by_role["oddball"],
        oddball_every_n=5,
        random_seed=0,
    )
    displayed_values = [event.text for event in sequence]

    assert all(
        previous != current
        for previous, current in zip(displayed_values, displayed_values[1:], strict=False)
    )
    for role, authored_items in authored_by_role.items():
        role_values = [event.text for event in sequence if event.role == role]
        bag_size = len(authored_items)
        authored_values = Counter(item.text for item in authored_items)
        assert all(
            Counter(role_values[start : start + bag_size]) == authored_values
            for start in range(0, len(role_values) - bag_size + 1, bag_size)
        )


def test_stimulus_sequence_exact_planner_uses_state_budget_not_key_cutoff() -> None:
    def item(role: str, value: str) -> StimulusScheduleItem:
        return StimulusScheduleItem(
            stimulus_modality=StimulusModality.WORD,
            stimulus_id=f"{role}-{value.lower()}",
            text=value,
        )

    authored_by_role = {
        "base": [item("base", value) for value in ("C", "E", "J", "A", "K")],
        "oddball": [item("oddball", value) for value in ("G", "D", "L", "B", "E")],
    }
    sequence = build_stimulus_sequence(
        total_stimuli=50,
        frames_per_stimulus_value=10,
        on_frames=10,
        off_frames=0,
        base_stimuli=authored_by_role["base"],
        oddball_stimuli=authored_by_role["oddball"],
        oddball_every_n=2,
        random_seed=2,
    )
    displayed_values = [event.text for event in sequence]

    assert all(
        previous != current
        for previous, current in zip(displayed_values, displayed_values[1:], strict=False)
    )
    for role, authored_items in authored_by_role.items():
        role_values = [event.text for event in sequence if event.role == role]
        bag_size = len(authored_items)
        authored_values = Counter(item.text for item in authored_items)
        assert all(
            Counter(role_values[start : start + bag_size]) == authored_values
            for start in range(0, len(role_values), bag_size)
        )


@pytest.mark.parametrize("random_seed", [0, 2, 28, 71, 97])
def test_stimulus_sequence_repairs_long_fallback_bag_conflicts(random_seed: int) -> None:
    def item(role: str, value: str) -> StimulusScheduleItem:
        return StimulusScheduleItem(
            stimulus_modality=StimulusModality.WORD,
            stimulus_id=f"{role}-{value}",
            text=value,
        )

    authored_by_role = {
        "base": [
            item("base", value) for value in ("v11", "v18", "v26", "v1", "v29", "v13", "v27", "v15")
        ],
        "oddball": [
            item("oddball", value)
            for value in ("v9", "v23", "v26", "v21", "v17", "v2", "v15", "v6")
        ],
    }
    sequence = build_stimulus_sequence(
        total_stimuli=735,
        frames_per_stimulus_value=10,
        on_frames=10,
        off_frames=0,
        base_stimuli=authored_by_role["base"],
        oddball_stimuli=authored_by_role["oddball"],
        oddball_every_n=2,
        random_seed=random_seed,
    )
    displayed_values = [event.text for event in sequence]

    assert all(
        previous != current
        for previous, current in zip(displayed_values, displayed_values[1:], strict=False)
    )
    for role, authored_items in authored_by_role.items():
        role_values = [event.text for event in sequence if event.role == role]
        bag_size = len(authored_items)
        authored_values = Counter(item.text for item in authored_items)
        complete_count = len(role_values) // bag_size * bag_size
        assert all(
            Counter(role_values[start : start + bag_size]) == authored_values
            for start in range(0, complete_count, bag_size)
        )
        assert not (Counter(role_values[complete_count:]) - authored_values)


def test_stimulus_sequence_preserves_bags_when_cross_role_repeat_is_unavoidable() -> None:
    def item(role: str, value: str) -> StimulusScheduleItem:
        return StimulusScheduleItem(
            stimulus_modality=StimulusModality.WORD,
            stimulus_id=f"{role}-{value.lower()}",
            text=value,
        )

    authored_by_role = {
        "base": [item("base", "A"), item("base", "B")],
        "oddball": [item("oddball", "A"), item("oddball", "C")],
    }
    sequence = build_stimulus_sequence(
        total_stimuli=8,
        frames_per_stimulus_value=10,
        on_frames=10,
        off_frames=0,
        base_stimuli=authored_by_role["base"],
        oddball_stimuli=authored_by_role["oddball"],
        oddball_every_n=2,
        random_seed=0,
    )
    displayed_values = [event.text for event in sequence]

    # With fixed base/oddball alternation and complete {A, B}/{A, C} bags,
    # every possible ordering of these four role bags has at least one repeat.
    assert any(
        previous == current
        for previous, current in zip(displayed_values, displayed_values[1:], strict=False)
    )
    for role, authored_items in authored_by_role.items():
        role_values = [event.text for event in sequence if event.role == role]
        bag_size = len(authored_items)
        authored_values = Counter(item.text for item in authored_items)
        assert all(
            Counter(role_values[start : start + bag_size]) == authored_values
            for start in range(0, len(role_values), bag_size)
        )


def test_stimulus_sequence_preserves_each_role_bag_across_multiple_cycles() -> None:
    def item(role: str, value: str) -> StimulusScheduleItem:
        return StimulusScheduleItem(
            stimulus_modality=StimulusModality.WORD,
            stimulus_id=f"{role}-{value.lower()}",
            text=value,
        )

    base_items = [item("base", value) for value in ("A", "B", "C", "D")]
    oddball_items = [item("oddball", value) for value in ("A", "E")]

    sequence = build_stimulus_sequence(
        total_stimuli=20,
        frames_per_stimulus_value=10,
        on_frames=10,
        off_frames=0,
        base_stimuli=base_items,
        oddball_stimuli=oddball_items,
        oddball_every_n=5,
        random_seed=0,
    )
    values_by_role = {
        role: [event.text for event in sequence if event.role == role]
        for role in ("base", "oddball")
    }

    for role, authored_items in (("base", base_items), ("oddball", oddball_items)):
        authored_values = Counter(item.text for item in authored_items)
        bag_size = len(authored_items)
        role_values = values_by_role[role]
        assert all(
            Counter(role_values[start : start + bag_size]) == authored_values
            for start in range(0, len(role_values), bag_size)
        )


def test_text_height_schedule_looks_ahead_to_fixed_oddball_height() -> None:
    values = build_interleaved_text_height_values(
        {
            "base": TextHeightScheduleSettings(
                mode=TextHeightMode.BALANCED_RANDOMIZED,
                unit=PresentationUnit.DEGREES,
                values=[1.0, 2.0],
            ),
            "oddball": TextHeightScheduleSettings(
                mode=TextHeightMode.FIXED,
                unit=PresentationUnit.DEGREES,
                values=[1.0],
            ),
        },
        total_stimuli=2,
        oddball_every_n=2,
        random_seed=2,
    )

    assert values == {"base": [2.0], "oddball": [1.0]}


@pytest.mark.parametrize(
    ("total_stimuli", "oddball_every_n"),
    [(4, 2), (735, 5)],
)
def test_text_height_schedule_globally_resolves_overlapping_role_bags(
    total_stimuli: int,
    oddball_every_n: int,
) -> None:
    settings_by_role = {
        "base": TextHeightScheduleSettings(
            mode=TextHeightMode.BALANCED_RANDOMIZED,
            unit=PresentationUnit.DEGREES,
            values=[1.0, 2.0],
        ),
        "oddball": TextHeightScheduleSettings(
            mode=TextHeightMode.BALANCED_RANDOMIZED,
            unit=PresentationUnit.DEGREES,
            values=[1.0, 3.0],
        ),
    }

    values_by_role = build_interleaved_text_height_values(
        settings_by_role,
        total_stimuli=total_stimuli,
        oddball_every_n=oddball_every_n,
        random_seed=1,
    )
    role_offsets = {"base": 0, "oddball": 0}
    interleaved: list[float] = []
    for index in range(total_stimuli):
        role = "oddball" if (index + 1) % oddball_every_n == 0 else "base"
        interleaved.append(values_by_role[role][role_offsets[role]])
        role_offsets[role] += 1

    assert all(
        previous != current for previous, current in zip(interleaved, interleaved[1:], strict=False)
    )
    for role, values in values_by_role.items():
        authored = Counter(settings_by_role[role].values)
        bag_size = len(settings_by_role[role].values)
        assert all(
            Counter(values[start : start + bag_size]) == authored
            for start in range(0, len(values) - bag_size + 1, bag_size)
        )


def test_text_height_schedule_repairs_long_scalable_fallback() -> None:
    settings_by_role = {
        "base": TextHeightScheduleSettings(
            mode=TextHeightMode.BALANCED_RANDOMIZED,
            unit=PresentationUnit.DEGREES,
            values=[11.0, 18.0, 26.0, 1.0, 29.0, 13.0, 27.0, 15.0],
        ),
        "oddball": TextHeightScheduleSettings(
            mode=TextHeightMode.BALANCED_RANDOMIZED,
            unit=PresentationUnit.DEGREES,
            values=[9.0, 23.0, 26.0, 21.0, 17.0, 2.0, 15.0, 6.0],
        ),
    }
    values_by_role = build_interleaved_text_height_values(
        settings_by_role,
        total_stimuli=735,
        oddball_every_n=2,
        random_seed=0,
    )
    offsets = {"base": 0, "oddball": 0}
    interleaved: list[float] = []
    for index in range(735):
        role = "oddball" if (index + 1) % 2 == 0 else "base"
        interleaved.append(values_by_role[role][offsets[role]])
        offsets[role] += 1

    assert all(
        previous != current for previous, current in zip(interleaved, interleaved[1:], strict=False)
    )
    for role, values in values_by_role.items():
        authored = Counter(settings_by_role[role].values)
        bag_size = len(settings_by_role[role].values)
        complete_count = len(values) // bag_size * bag_size
        assert all(
            Counter(values[start : start + bag_size]) == authored
            for start in range(0, complete_count, bag_size)
        )
        assert not (Counter(values[complete_count:]) - authored)


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
