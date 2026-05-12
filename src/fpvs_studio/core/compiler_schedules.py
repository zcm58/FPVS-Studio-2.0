"""Schedule builders used by run and session compilation."""

from __future__ import annotations

import random
from collections import Counter

from fpvs_studio.core.compiler_support import CompileError
from fpvs_studio.core.enums import InterConditionMode
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.run_spec import StimulusEvent, StimulusRole, TriggerEvent
from fpvs_studio.core.session_plan import InterConditionTransitionSpec
from fpvs_studio.core.trigger_codes import validate_event_trigger_code


def build_stimulus_sequence(
    *,
    total_stimuli: int,
    frames_per_stimulus_value: int,
    on_frames: int,
    off_frames: int,
    base_paths: list[str],
    oddball_paths: list[str],
    oddball_every_n: int,
    rng: random.Random,
) -> list[StimulusEvent]:
    """Build the base/oddball schedule with seeded per-role image shuffles."""

    role_counts: Counter[str] = Counter()
    sequence: list[StimulusEvent] = []
    shuffled_pools = {
        "base": _shuffled_pool(base_paths, rng=rng),
        "oddball": _shuffled_pool(oddball_paths, rng=rng),
    }

    for index in range(total_stimuli):
        role: StimulusRole = "oddball" if (index + 1) % oddball_every_n == 0 else "base"
        pool = shuffled_pools[role]
        image_path = pool[role_counts[role] % len(pool)]
        role_counts[role] += 1
        if role_counts[role] % len(pool) == 0:
            shuffled_pools[role] = _shuffled_pool(pool, rng=rng)
        sequence.append(
            StimulusEvent(
                sequence_index=index,
                role=role,
                image_path=image_path,
                on_start_frame=index * frames_per_stimulus_value,
                on_frames=on_frames,
                off_frames=off_frames,
            )
        )
    return sequence


def _shuffled_pool(paths: list[str], *, rng: random.Random) -> list[str]:
    """Return a shuffled copy while keeping callers' resolved path lists immutable."""

    shuffled = list(paths)
    rng.shuffle(shuffled)
    return shuffled


def build_trigger_events(
    *,
    stimulus_sequence: list[StimulusEvent],
    condition_trigger_code: int,
    oddball_trigger_code: int,
) -> list[TriggerEvent]:
    """Build frame-accurate condition and oddball trigger events."""

    if not stimulus_sequence:
        return []

    trigger_events: list[TriggerEvent] = [
        TriggerEvent(
            frame_index=stimulus_sequence[0].on_start_frame,
            code=validate_event_trigger_code(
                condition_trigger_code,
                label="condition_start",
            ),
            label="condition_start",
        )
    ]
    trigger_events.extend(
        TriggerEvent(
            frame_index=event.on_start_frame,
            code=validate_event_trigger_code(oddball_trigger_code, label="oddball_onset"),
            label="oddball_onset",
        )
        for event in stimulus_sequence
        if event.role == "oddball"
    )
    return _validate_and_sort_trigger_events(trigger_events)


def _validate_and_sort_trigger_events(trigger_events: list[TriggerEvent]) -> list[TriggerEvent]:
    indexed_events = list(enumerate(trigger_events))
    events_by_frame: dict[int, list[TriggerEvent]] = {}
    for _, trigger_event in indexed_events:
        events_by_frame.setdefault(trigger_event.frame_index, []).append(trigger_event)

    for frame_index, frame_events in events_by_frame.items():
        if len(frame_events) > 1:
            details = " and ".join(
                f"{event.label}={event.code}" for event in frame_events
            )
            raise CompileError(
                f"Frame {frame_index} contains {details}. BioSemi serial output "
                "cannot emit multiple marker bytes on one flip."
            )

    return [
        event
        for _, event in sorted(indexed_events, key=lambda item: (item[1].frame_index, item[0]))
    ]


def compile_transition_spec(project: ProjectFile) -> InterConditionTransitionSpec:
    """Compile session transition settings into an explicit transition spec."""

    return InterConditionTransitionSpec(
        mode=InterConditionMode.MANUAL_CONTINUE,
        break_seconds=None,
        continue_key="space",
    )
