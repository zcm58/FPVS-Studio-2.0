"""Compile seeded distractors and independent character targets onto the shared frame grid."""

from __future__ import annotations

from fpvs_studio.core.attentional_blink_stream import (
    iter_attentional_blink_stream_cycles,
    preview_attentional_blink_stream,
)
from fpvs_studio.core.enums import StimulusModality
from fpvs_studio.core.models import (
    AttentionalBlinkStreamSettings,
    Condition,
    ProjectFile,
    StimulusSet,
)
from fpvs_studio.core.presentation import resolve_role_presentation
from fpvs_studio.core.run_spec import (
    AttentionalBlinkStreamRunSpec,
    ConditionPresentationSpec,
    StimulusEvent,
)


def compile_attentional_blink_stream_sequence(
    project: ProjectFile,
    condition: Condition,
    *,
    base_set: StimulusSet,
    t1_set: StimulusSet,
    presentation: ConditionPresentationSpec,
    refresh_hz: float,
    total_cycles: int,
    random_seed: int,
) -> tuple[list[StimulusEvent], AttentionalBlinkStreamRunSpec, ConditionPresentationSpec]:
    """Use equal character durations, distinct targets, and no repeated adjacent distractors."""

    settings = condition.attentional_blink
    assert isinstance(settings, AttentionalBlinkStreamSettings)
    t2_set = next(
        item for item in project.stimulus_sets if item.set_id == condition.t2_stimulus_set_id
    )
    protocol = project.settings.protocol
    preview = preview_attentional_blink_stream(
        refresh_hz=refresh_hz, base_hz=protocol.base_hz,
        cycle_slots=protocol.oddball_every_n, soa_ms=settings.soa_ms,
        t2_slot_index=settings.t2_slot_index,
    )
    description = preview.description
    t1_presentation = presentation.oddball.model_copy(deep=True)
    assert t1_presentation.text is not None
    t1_presentation.text.color = settings.t1_color
    t2_presentation = presentation.oddball.model_copy(deep=True)
    assert t2_presentation.text is not None
    t2_presentation.text.color = settings.t2_color
    presentation = presentation.model_copy(update={"oddball": t1_presentation})
    height = resolve_role_presentation(
        project.settings.presentation, condition.presentation, "base"
    ).text_height.values[0]
    cycles = iter_attentional_blink_stream_cycles(
        description, base_words=base_set.words, t1_words=t1_set.words,
        t2_words=t2_set.words, random_seed=random_seed,
    )
    events: list[StimulusEvent] = []
    for cycle_index, symbols in zip(range(total_cycles), cycles, strict=False):
        for cycle_slot, (phase, symbol) in enumerate(zip(description.roles, symbols, strict=True)):
            if phase == "base":
                source_id = base_set.set_id
            else:
                source_id = t1_set.set_id if phase == "t1" else t2_set.set_id
            slot_index = cycle_index * description.cycle_slots + cycle_slot
            events.append(StimulusEvent(
                sequence_index=slot_index,
                slot_index=slot_index,
                cycle_index=cycle_index,
                phase=phase,
                role="base" if phase == "base" else "oddball",
                stimulus_modality=StimulusModality.WORD,
                stimulus_id=f"{source_id}-{symbol.lower()}",
                text=symbol,
                text_height_value=height,
                on_start_frame=slot_index * preview.frames_per_item,
                on_frames=preview.frames_per_item,
                off_frames=0,
            ))
    return events, AttentionalBlinkStreamRunSpec(
        requested_soa_ms=settings.soa_ms,
        achieved_soa_ms=preview.achieved_soa_ms,
        lag=description.lag,
        frames_per_item=preview.frames_per_item,
        cycle_slots=description.cycle_slots,
        t1_slot_index=description.t1_slot_index,
        t2_slot_index=description.t2_slot_index,
        t2_trigger_code=settings.t2_trigger_code,
        t2_presentation=t2_presentation,
    ), presentation
