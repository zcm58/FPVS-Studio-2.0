"""Stimulus drawing helpers for the PsychoPy engine."""

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

from PIL import Image

from fpvs_studio.core.display_geometry import visual_angle_width_px
from fpvs_studio.core.enums import StimulusModality
from fpvs_studio.core.run_spec import DisplayRunSpec, FixationEvent, RunSpec, StimulusEvent

LOGGER = logging.getLogger(__name__)
_PSYCHOPY_TEXTURE_ID_ATTRIBUTES = ("_texID", "_maskID", "_pixBuffID")
WORD_TEXT_HEIGHT_TO_STIMULUS_WIDTH_RATIO = 0.25


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
    project_root: Path,
    run_spec: RunSpec,
) -> dict[str, Any]:
    """Create PsychoPy stimuli for one condition run."""

    stimuli: dict[str, Any] = {}
    for event in run_spec.stimulus_sequence:
        if event.stimulus_id in stimuli:
            continue
        try:
            if event.stimulus_modality == StimulusModality.IMAGE:
                if event.image_path is None:
                    raise ValueError("Image stimulus event is missing image_path.")
                absolute_path = project_root / Path(event.image_path)
                stimulus_size = _stimulus_size_px(
                    absolute_path=absolute_path,
                    window=window,
                    display=run_spec.display,
                )
                stimuli[event.stimulus_id] = visual.ImageStim(
                    window,
                    image=str(absolute_path),
                    size=stimulus_size,
                    autoLog=False,
                )
            elif event.stimulus_modality == StimulusModality.WORD:
                if event.text is None:
                    raise ValueError("Word stimulus event is missing text.")
                text_height = _word_text_height_px(window=window, display=run_spec.display)
                stimuli[event.stimulus_id] = visual.TextStim(
                    window,
                    text=event.text,
                    pos=(0, 0),
                    height=text_height,
                    color="white",
                    autoLog=False,
                )
            else:
                raise ValueError(f"Unsupported stimulus modality '{event.stimulus_modality}'.")
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
        screen_width_px=_screen_width_px(window=window, display=display),
    )
    target_height_px = max(1, round(target_width_px * (image_height_px / image_width_px)))
    return (target_width_px, target_height_px)


def _screen_width_px(*, window: Any, display: DisplayRunSpec) -> int:
    if not display.use_current_screen_resolution:
        return display.screen_width_px
    return _window_width_px(window)


def _window_width_px(window: Any) -> int:
    size = getattr(window, "size", None)
    if isinstance(size, (list, tuple)) and size:
        return max(1, int(size[0]))
    return 1920


def _word_text_height_px(*, window: Any, display: DisplayRunSpec) -> int:
    stimulus_width_px = visual_angle_width_px(
        degrees=display.stimulus_width_degrees,
        viewing_distance_cm=display.viewing_distance_cm,
        screen_width_cm=display.screen_width_cm,
        screen_width_px=_screen_width_px(window=window, display=display),
    )
    return max(1, round(stimulus_width_px * WORD_TEXT_HEIGHT_TO_STIMULUS_WIDTH_RATIO))


def release_stimuli(stimuli: MutableMapping[str, Any]) -> None:
    """Release PsychoPy stimulus textures for one condition run."""

    cleanup_error_count = 0
    last_cleanup_error: Exception | None = None
    for stimulus in list(stimuli.values()):
        try:
            clear_textures = getattr(stimulus, "clearTextures", None)
            if callable(clear_textures):
                clear_textures()
        except Exception as error:
            cleanup_error_count += 1
            last_cleanup_error = error
        finally:
            _discard_psychopy_texture_ids(stimulus)
    stimuli.clear()
    if cleanup_error_count:
        LOGGER.warning(
            "Ignored %d PsychoPy stimulus texture cleanup error(s); "
            "discarded texture ids to prevent repeated destructor cleanup failures. "
            "Last error type: %s.",
            cleanup_error_count,
            type(last_cleanup_error).__name__,
        )


def _discard_psychopy_texture_ids(stimulus: Any) -> None:
    for attribute_name in _PSYCHOPY_TEXTURE_ID_ATTRIBUTES:
        try:
            delattr(stimulus, attribute_name)
        except AttributeError:
            continue
