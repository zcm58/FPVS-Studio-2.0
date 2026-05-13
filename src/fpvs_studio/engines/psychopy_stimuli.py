"""Stimulus drawing helpers for the PsychoPy engine."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from PIL import Image

from fpvs_studio.core.display_geometry import visual_angle_width_px
from fpvs_studio.core.run_spec import DisplayRunSpec, FixationEvent, StimulusEvent


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
    absolute_paths: Mapping[str, Path],
    display: DisplayRunSpec,
) -> dict[str, Any]:
    """Create PsychoPy image stimuli for one condition run."""

    stimuli: dict[str, Any] = {}
    for relative_path, absolute_path in absolute_paths.items():
        try:
            stimulus_size = _stimulus_size_px(
                absolute_path=absolute_path,
                window=window,
                display=display,
            )
            stimuli[relative_path] = visual.ImageStim(
                window,
                image=str(absolute_path),
                size=stimulus_size,
                autoLog=False,
            )
        except Exception:
            release_stimuli(stimuli)
            raise
    return stimuli


def _stimulus_size_px(
    *,
    absolute_path: Path,
    window: Any,
    display: DisplayRunSpec,
) -> tuple[int, int]:
    with Image.open(absolute_path) as image:
        image_width_px, image_height_px = image.size
    target_width_px = visual_angle_width_px(
        degrees=display.stimulus_width_degrees,
        viewing_distance_cm=display.viewing_distance_cm,
        screen_width_cm=display.screen_width_cm,
        screen_width_px=_window_width_px(window),
    )
    target_height_px = max(1, round(target_width_px * (image_height_px / image_width_px)))
    return (target_width_px, target_height_px)


def _window_width_px(window: Any) -> int:
    size = getattr(window, "size", None)
    if isinstance(size, (list, tuple)) and size:
        return max(1, int(size[0]))
    return 1920


def release_stimuli(stimuli: Mapping[str, Any]) -> None:
    """Release PsychoPy stimulus textures for one condition run."""

    for stimulus in stimuli.values():
        clear_textures = getattr(stimulus, "clearTextures", None)
        if callable(clear_textures):
            clear_textures()
