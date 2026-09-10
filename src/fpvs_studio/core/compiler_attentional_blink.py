"""Compile a target pair inside each existing terminal oddball slot."""

from __future__ import annotations

import random
from pathlib import Path

from fpvs_studio.core.attentional_blink import SlotRole, preview_attentional_blink
from fpvs_studio.core.compiler_assets import resolve_stimulus_items
from fpvs_studio.core.compiler_presentation import compile_condition_presentation
from fpvs_studio.core.compiler_schedules import (
    StimulusScheduleItem,
    build_balanced_shuffled_values,
)
from fpvs_studio.core.compiler_support import CompileError, namespaced_random_seed
from fpvs_studio.core.models import AttentionalBlinkSettings, Condition, ProjectFile, StimulusSet
from fpvs_studio.core.run_spec import AttentionalBlinkRunSpec, StimulusEvent
from fpvs_studio.preprocessing.models import StimulusManifest


def compile_attentional_blink_sequence(
    project: ProjectFile,
    condition: Condition,
    sequence: list[StimulusEvent],
    *,
    base_set: StimulusSet,
    refresh_hz: float,
    project_root: Path | None,
    manifest: StimulusManifest | None,
    random_seed: int,
) -> tuple[list[StimulusEvent], AttentionalBlinkRunSpec]:
    """Keep the original role bags and add independently balanced separator/T2 bags."""
    settings = condition.attentional_blink
    assert isinstance(settings, AttentionalBlinkSettings)
    t2_set = next(
        (item for item in project.stimulus_sets if item.set_id == condition.t2_stimulus_set_id),
        None,
    )
    if t2_set is None:
        raise CompileError(f"Condition '{condition.name}' requires a T2 image source.")
    protocol = project.settings.protocol
    base_role: SlotRole = "base"
    roles: tuple[SlotRole, ...] = (base_role,) * (protocol.oddball_every_n - 1) + ("target_pair",)
    try:
        preview = preview_attentional_blink(
            roles,
            refresh_hz=refresh_hz,
            base_hz=protocol.base_hz,
            t1_ms=settings.t1_duration_ms,
            isi_ms=settings.isi_ms,
        )
    except ValueError as error:
        raise CompileError(str(error)) from error
    t2_stimuli = resolve_stimulus_items(
        t2_set,
        variant=condition.stimulus_variant,
        project_root=project_root,
        manifest=manifest,
    )
    t2_presentation, _ = compile_condition_presentation(
        project_presentation=project.settings.presentation,
        condition=condition,
        base_set=base_set,
        oddball_set=t2_set,
    )
    pair_count = sum(event.role == "oddball" for event in sequence)
    isi_presentation = None
    separators = []
    if settings.isi_mode == "image":
        isi_set = next(
            (item for item in project.stimulus_sets
             if item.set_id == condition.isi_stimulus_set_id),
            None,
        )
        if isi_set is None:
            raise CompileError(f"Condition '{condition.name}' requires an ISI image source.")
        isi_stimuli = resolve_stimulus_items(
            isi_set, variant=condition.stimulus_variant,
            project_root=project_root, manifest=manifest,
        )
        presentation, _ = compile_condition_presentation(
            project_presentation=project.settings.presentation, condition=condition,
            base_set=isi_set, oddball_set=t2_set,
        )
        isi_presentation = presentation.base
        separators = _phase_bag(isi_stimuli, pair_count, random_seed, "separator")
    t2_values = _phase_bag(t2_stimuli, pair_count, random_seed, "t2")
    expanded: list[StimulusEvent] = []
    pair_index = 0
    for slot_index, event in enumerate(sequence):
        if event.role == "base":
            expanded.append(
                event.model_copy(
                    update={
                        "sequence_index": len(expanded),
                        "slot_index": slot_index,
                        "phase": "base",
                    }
                )
            )
            continue
        expanded.append(
            event.model_copy(
                update={
                    "sequence_index": len(expanded),
                    "slot_index": slot_index,
                    "phase": "t1",
                    "on_frames": preview.t1_frames,
                    "off_frames": 0,
                }
            )
        )
        separator = separators[pair_index] if separators else None
        t2 = t2_values[pair_index]
        expanded.append(
            StimulusEvent(
                sequence_index=len(expanded),
                slot_index=slot_index,
                phase="separator",
                role="base",
                stimulus_modality=event.stimulus_modality,
                stimulus_id=separator.stimulus_id if separator else "isi-blank",
                image_path=separator.image_path if separator else None,
                is_blank=settings.isi_mode == "blank",
                on_start_frame=event.on_start_frame + preview.t1_frames,
                on_frames=preview.isi_frames,
                off_frames=0,
            )
        )
        expanded.append(
            StimulusEvent(
                sequence_index=len(expanded),
                slot_index=slot_index,
                phase="t2",
                role="oddball",
                stimulus_modality=t2.stimulus_modality,
                stimulus_id=t2.stimulus_id,
                image_path=t2.image_path,
                on_start_frame=event.on_start_frame + preview.t1_frames + preview.isi_frames,
                on_frames=preview.t2_frames,
                off_frames=0,
            )
        )
        pair_index += 1
    return expanded, AttentionalBlinkRunSpec(
        requested_t1_duration_ms=settings.t1_duration_ms,
        requested_isi_ms=settings.isi_ms,
        t1_frames=preview.t1_frames,
        isi_frames=preview.isi_frames,
        t2_frames=preview.t2_frames,
        t2_trigger_code=settings.t2_trigger_code,
        t2_presentation=t2_presentation.oddball,
        isi_mode=settings.isi_mode,
        isi_presentation=isi_presentation,
    )


def _phase_bag(
    items: list[StimulusScheduleItem], count: int, random_seed: int, phase: str
) -> list[StimulusScheduleItem]:
    return build_balanced_shuffled_values(
        items,
        count=count,
        rng=random.Random(namespaced_random_seed(random_seed, f"attentional-blink:{phase}")),
        key=lambda item: item.image_path,
    )
