"""Schedule builders used by run and session compilation."""

from __future__ import annotations

from collections import Counter

from fpvs_studio.core.enums import InterConditionMode
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.run_spec import StimulusEvent, StimulusRole, TriggerEvent
from fpvs_studio.core.session_plan import InterConditionTransitionSpec


def build_stimulus_sequence(
    *,
    total_stimuli: int,
    frames_per_stimulus_value: int,
    on_frames: int,
    off_frames: int,
    base_paths: list[str],
    oddball_paths: list[str],
    oddball_every_n: int,
) -> list[StimulusEvent]:
    """Build the deterministic base/oddball schedule."""

    role_counts: Counter[str] = Counter()
    sequence: list[StimulusEvent] = []

    for index in range(total_stimuli):
        role: StimulusRole = "oddball" if (index + 1) % oddball_every_n == 0 else "base"
        pool = oddball_paths if role == "oddball" else base_paths
        image_path = pool[role_counts[role] % len(pool)]
        role_counts[role] += 1
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


def build_trigger_events(trigger_code: int | None) -> list[TriggerEvent]:
    """Generate the first-pass trigger schedule."""

    if trigger_code is None:
        return []
    return [TriggerEvent(frame_index=0, code=trigger_code, label="condition_start")]


def compile_transition_spec(project: ProjectFile) -> InterConditionTransitionSpec:
    """Compile session transition settings into an explicit transition spec."""

    return InterConditionTransitionSpec(
        mode=InterConditionMode.MANUAL_CONTINUE,
        break_seconds=None,
        continue_key="space",
    )
