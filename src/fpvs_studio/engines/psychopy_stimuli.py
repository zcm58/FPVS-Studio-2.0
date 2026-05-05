"""Stimulus drawing helpers for the PsychoPy engine."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fpvs_studio.core.run_spec import FixationEvent, StimulusEvent


def fixation_color_for_frame(
    fixation_events: list[FixationEvent],
    default_color: str,
    target_color: str,
    fixation_index: int,
    frame_index: int,
) -> str:
    """Return the fixation color active on one frame."""

    if not fixation_events:
        return default_color
    fixation_event = fixation_events[fixation_index]
    if (
        fixation_event.start_frame
        <= frame_index
        < (fixation_event.start_frame + fixation_event.duration_frames)
    ):
        return target_color
    return default_color


def should_draw_stimulus(
    stimulus_event: StimulusEvent | None,
    frame_index: int,
) -> bool:
    """Return whether one stimulus event should draw on the current frame."""

    if stimulus_event is None:
        return False
    local_frame = frame_index - stimulus_event.on_start_frame
    return 0 <= local_frame < stimulus_event.on_frames


def prepare_stimuli(
    *,
    visual: Any,
    window: Any,
    image_stim_cache: dict[str, Any],
    absolute_paths: Mapping[str, Path],
) -> dict[str, Any]:
    """Create or reuse PsychoPy image stimuli for one run."""

    for relative_path, absolute_path in absolute_paths.items():
        if relative_path not in image_stim_cache:
            image_stim_cache[relative_path] = visual.ImageStim(
                window,
                image=str(absolute_path),
                autoLog=False,
            )
    return {path: image_stim_cache[path] for path in absolute_paths}
