"""Compile masking source pools onto the existing FPVS item grid."""

from __future__ import annotations

import random
from pathlib import Path

from fpvs_studio.core.compiler_support import CompileError, make_run_id
from fpvs_studio.core.enums import DutyCycleMode, StimulusModality
from fpvs_studio.core.masking import MaskingSettings, masking_frame_counts
from fpvs_studio.core.models import Condition, ProjectFile
from fpvs_studio.core.paths import resolve_project_relative_path
from fpvs_studio.core.run_spec import (
    ConditionRunSpec,
    DisplayRunSpec,
    FixationStyleSpec,
    RunSpec,
    TriggerEvent,
)
from fpvs_studio.core.scene_models import SceneEvent, SceneStreamSpec, SceneVisual
from fpvs_studio.core.task_assets import owned_image_references


def masking_visuals(settings: MaskingSettings) -> list[SceneVisual]:
    return [
        *settings.base_visuals,
        *settings.target_visuals,
        *(settings.mask_visuals or []),
        *settings.base_overlays,
        *([settings.fixation_visual] if settings.fixation_visual else []),
    ]


def validate_masking_settings(
    project: ProjectFile,
    condition: Condition,
    settings: MaskingSettings,
    refresh_hz: float,
) -> None:
    owned_image_references([], project.condition_modifiers)
    if (
        condition.attentional_blink is not None
        or condition.duty_cycle_mode != DutyCycleMode.CONTINUOUS
    ):
        raise ValueError("Masking requires ordinary continuous FPVS item slots without AB timing.")
    if not settings.base_visuals or not settings.target_visuals or settings.mask_visuals == []:
        raise ValueError("Masking needs nonempty base, target and mask visual pools.")
    visuals = masking_visuals(settings)
    ids = [item.visual_id for item in visuals]
    if len(ids) != len(set(ids)):
        raise ValueError("Masking visual identities must be unique across all pools.")
    target_ids = {item.visual_id for item in settings.target_visuals}
    if set(settings.target_answers) != target_ids:
        raise ValueError("Every masking target needs exactly one identification answer.")
    if project.settings.protocol.oddball_every_n < 2:
        raise ValueError("Masking needs at least one base slot before each target.")
    masking_frame_counts(settings, refresh_hz=refresh_hz, base_hz=project.settings.protocol.base_hz)


def compile_masking_run(
    project: ProjectFile,
    condition: Condition,
    settings: MaskingSettings,
    *,
    refresh_hz: float,
    project_root: Path | None,
    random_seed: int,
    run_id: str | None,
    previous_base_id: str | None = None,
    is_catch_trial: bool = False,
) -> RunSpec:
    try:
        validate_masking_settings(project, condition, settings, refresh_hz)
        slot, soa, target_frames, mask_frames, base_frames = masking_frame_counts(
            settings,
            refresh_hz=refresh_hz,
            base_hz=project.settings.protocol.base_hz,
        )
    except ValueError as exc:
        raise CompileError(str(exc)) from exc
    if is_catch_trial and settings.catch_trial is None:
        raise CompileError("A catch run requires enabled masking catch trial settings.")
    visuals = masking_visuals(settings)
    for visual in visuals:
        if visual.image_path is not None:
            if project_root is None:
                raise CompileError("Masking image pools require the active project root.")
            if not resolve_project_relative_path(project_root, visual.image_path).is_file():
                raise CompileError(f"Masking image is missing: {visual.image_path}")
    rng = random.Random(random_seed)
    target = rng.choice(settings.target_visuals)
    events: list[SceneEvent] = []
    protocol = project.settings.protocol
    cycles = condition.sequence_count * condition.oddball_cycle_repeats_per_sequence
    total_slots = cycles * protocol.oddball_every_n
    previous = previous_base_id
    for index in range(total_slots):
        is_target = (index + 1) % protocol.oddball_every_n == 0
        pool = (
            settings.mask_visuals if is_target and settings.mask_visuals else settings.base_visuals
        )
        choices = [item for item in pool if item.visual_id != previous] if len(pool) > 1 else pool
        selected = rng.choice(choices)
        previous = selected.visual_id
        start = index * slot
        if is_target and not is_catch_trial:
            events.append(
                SceneEvent(
                    visual_id=target.visual_id,
                    start_frame=start,
                    duration_frames=target_frames,
                    role="target",
                )
            )
        duration = mask_frames if is_target else base_frames
        for overlay in settings.base_overlays:
            events.append(
                SceneEvent(
                    visual_id=overlay.visual_id,
                    start_frame=start + soa,
                    duration_frames=duration,
                    role="decoration",
                )
            )
        events.append(
            SceneEvent(
                visual_id=selected.visual_id,
                start_frame=start + soa,
                duration_frames=duration,
                role="mask" if is_target else "base",
            )
        )
    total_frames = total_slots * slot
    if settings.fixation_visual is not None:
        events.append(
            SceneEvent(
                visual_id=settings.fixation_visual.visual_id,
                start_frame=0,
                duration_frames=total_frames,
                role="fixation",
            )
        )
    scene = SceneStreamSpec(
        visuals=visuals,
        events=events,
        background_rgb=settings.background_rgb,
        target_id=None if is_catch_trial else target.visual_id,
        is_catch_trial=True if is_catch_trial else None,
        requested_soa_ms=settings.soa_ms,
        soa_frames=soa,
    )
    display = project.settings.display
    trigger_code = (
        settings.catch_trial.trigger_code
        if is_catch_trial and settings.catch_trial is not None else condition.trigger_code
    )
    return RunSpec(
        schema_version="1.5.0" if is_catch_trial else "1.4.0",
        run_id=run_id or make_run_id(condition.condition_id),
        project_id=project.meta.project_id,
        project_name=project.meta.name,
        template_id=project.meta.template_id,
        random_seed=random_seed,
        condition=ConditionRunSpec(
            condition_id=condition.condition_id,
            name=condition.name,
            template_id=project.meta.template_id,
            base_hz=protocol.base_hz,
            oddball_every_n=protocol.oddball_every_n,
            oddball_hz=protocol.oddball_hz,
            total_oddball_cycles=cycles,
            total_stimuli=total_slots,
            stimulus_modality=StimulusModality.SCENE,
            trigger_code=trigger_code,
        ),
        display=DisplayRunSpec(
            refresh_hz=refresh_hz,
            background_color="#808080",
            stimulus_width_degrees=display.stimulus_width_degrees,
            viewing_distance_cm=display.viewing_distance_cm,
            screen_width_cm=display.screen_width_cm,
            screen_width_px=display.screen_width_px,
            screen_height_px=display.screen_height_px,
            use_current_screen_resolution=display.use_current_screen_resolution,
            duty_cycle_mode=DutyCycleMode.CONTINUOUS,
            frames_per_stimulus=slot,
            on_frames=slot,
            off_frames=0,
            duty_cycle=1,
            total_frames=total_frames,
        ),
        fixation=FixationStyleSpec(
            show_cross=False,
            default_color="#FF0000",
            target_color="#FF0000",
            response_keys=[],
            cross_size_px=1,
            line_width_px=1,
            target_duration_frames=0,
        ),
        scene_stream=scene,
        trigger_events=[
            TriggerEvent(frame_index=0, code=trigger_code, label="condition_start")
        ],
    )
