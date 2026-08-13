"""Stimulus drawing and condition-local preparation for the PsychoPy engine."""

from __future__ import annotations

import logging
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from fpvs_studio.core.display_geometry import visual_angle_width_px
from fpvs_studio.core.enums import (
    ImageGeometryMode,
    PresentationUnit,
    StimulusModality,
    StimulusTransform,
)
from fpvs_studio.core.run_spec import (
    STUDIO_WORD_FONT_NAME,
    DisplayRunSpec,
    FixationEvent,
    ImageGeometrySpec,
    RolePresentationSpec,
    RunSpec,
    StimulusEvent,
    TextPresentationSpec,
)

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
) -> dict[tuple[object, ...], Any]:
    """Create every unique render variant before timed condition playback."""

    stimuli: dict[tuple[object, ...], Any] = {}
    for event in run_spec.stimulus_sequence:
        render_key = stimulus_render_key(event, run_spec=run_spec)
        if render_key in stimuli:
            continue
        try:
            stimuli[render_key] = _prepare_stimulus(
                visual=visual,
                window=window,
                project_root=project_root,
                run_spec=run_spec,
                event=event,
            )
        except Exception:
            release_stimuli(stimuli)
            raise
    try:
        _prime_stimuli(stimuli, window=window)
    except Exception:
        release_stimuli(stimuli)
        raise
    return stimuli


def _prime_stimuli(stimuli: dict[tuple[object, ...], Any], *, window: Any) -> None:
    """Force deferred texture/glyph work before any timed presentation flip."""

    for stimulus in stimuli.values():
        stimulus.draw()
    clear_buffer = getattr(window, "clearBuffer", None)
    if not callable(clear_buffer):
        raise RuntimeError("PsychoPy window cannot clear its back buffer after preload.")
    clear_buffer()


def stimulus_render_key(event: StimulusEvent, *, run_spec: RunSpec) -> tuple[object, ...]:
    """Return the full immutable identity of one prepared render variant."""

    role_spec = _role_presentation(run_spec, event)
    if event.stimulus_modality == StimulusModality.IMAGE:
        geometry = role_spec.image_geometry if role_spec is not None else None
        return (
            "image",
            event.image_path,
            _transform_value(role_spec),
            geometry.mode.value if geometry is not None else "legacy_natural_aspect",
            geometry.width_degrees
            if geometry is not None
            else run_spec.display.stimulus_width_degrees,
            geometry.height_degrees if geometry is not None else None,
            geometry.source_resolution.width_px if geometry is not None else None,
            geometry.source_resolution.height_px if geometry is not None else None,
        )

    text_spec = role_spec.text if role_spec is not None else None
    return (
        "word",
        event.text,
        event.text_height_value,
        _transform_value(role_spec),
        text_spec.font_name if text_spec is not None else STUDIO_WORD_FONT_NAME,
        text_spec.color if text_spec is not None else "#FFFFFF",
        text_spec.position_unit.value if text_spec is not None else "legacy_pixels",
        text_spec.position_x if text_spec is not None else 0.0,
        text_spec.position_y if text_spec is not None else 0.0,
        text_spec.height_unit.value if text_spec is not None else "legacy_width_ratio",
        text_spec.legacy_stimulus_width_fraction if text_spec is not None else None,
    )


def _prepare_stimulus(
    *,
    visual: Any,
    window: Any,
    project_root: Path,
    run_spec: RunSpec,
    event: StimulusEvent,
) -> Any:
    role_spec = _role_presentation(run_spec, event)
    flip_horiz, flip_vert, orientation = _transform_kwargs(role_spec)
    if event.stimulus_modality == StimulusModality.IMAGE:
        if event.image_path is None:
            raise ValueError("Image stimulus event is missing image_path.")
        absolute_path = project_root / Path(event.image_path)
        image_source, stimulus_size = _prepared_image_source_and_size(
            absolute_path=absolute_path,
            window=window,
            display=run_spec.display,
            geometry=role_spec.image_geometry if role_spec is not None else None,
        )
        return visual.ImageStim(
            window,
            image=image_source,
            size=stimulus_size,
            flipHoriz=flip_horiz,
            flipVert=flip_vert,
            ori=orientation,
            autoLog=False,
        )

    if event.stimulus_modality == StimulusModality.WORD:
        if event.text is None:
            raise ValueError("Word stimulus event is missing text.")
        text_spec = role_spec.text if role_spec is not None else None
        return visual.TextStim(
            window,
            text=event.text,
            font=text_spec.font_name if text_spec is not None else STUDIO_WORD_FONT_NAME,
            pos=_word_position_px(window=window, display=run_spec.display, spec=text_spec),
            height=_word_text_height_px(
                window=window,
                display=run_spec.display,
                spec=text_spec,
                value=event.text_height_value,
            ),
            color=text_spec.color if text_spec is not None else "#FFFFFF",
            flipHoriz=flip_horiz,
            flipVert=flip_vert,
            ori=orientation,
            autoLog=False,
        )

    raise ValueError(f"Unsupported stimulus modality '{event.stimulus_modality}'.")


def _role_presentation(run_spec: RunSpec, event: StimulusEvent) -> RolePresentationSpec | None:
    presentation = run_spec.presentation
    return getattr(presentation, event.role) if presentation is not None else None


def _transform_value(role_spec: RolePresentationSpec | None) -> str:
    return role_spec.transform.value if role_spec is not None else StimulusTransform.NONE.value


def _transform_kwargs(role_spec: RolePresentationSpec | None) -> tuple[bool, bool, float]:
    transform = role_spec.transform if role_spec is not None else StimulusTransform.NONE
    return (
        transform == StimulusTransform.MIRROR_HORIZONTAL,
        transform == StimulusTransform.MIRROR_VERTICAL,
        180.0 if transform == StimulusTransform.ROT180 else 0.0,
    )


def _prepared_image_source_and_size(
    *,
    absolute_path: Path,
    window: Any,
    display: DisplayRunSpec,
    geometry: ImageGeometrySpec | None,
) -> tuple[str | Any, tuple[int, int]]:
    with Image.open(absolute_path) as image:
        source_width_px, source_height_px = image.size

        if geometry is None:
            target_width_px = _degrees_to_pixels(
                geometry_degrees=display.stimulus_width_degrees,
                window=window,
                display=display,
            )
            target_height_px = max(
                1,
                round(target_width_px * (source_height_px / source_width_px)),
            )
            return str(absolute_path), (target_width_px, target_height_px)

        expected_resolution = geometry.source_resolution.as_tuple()
        if image.size != expected_resolution:
            raise ValueError(
                f"Image stimulus '{absolute_path}' decoded as "
                f"{source_width_px}x{source_height_px}, but its compiled source "
                f"resolution is {expected_resolution[0]}x{expected_resolution[1]}."
            )

        box_width_px = (
            _degrees_to_pixels(
                geometry_degrees=geometry.width_degrees,
                window=window,
                display=display,
            )
            if geometry.width_degrees is not None
            else None
        )
        box_height_px = (
            _degrees_to_pixels(
                geometry_degrees=geometry.height_degrees,
                window=window,
                display=display,
            )
            if geometry.height_degrees is not None
            else None
        )

        if geometry.mode == ImageGeometryMode.NATURAL_ASPECT:
            if box_width_px is not None:
                return str(absolute_path), (
                    box_width_px,
                    max(1, round(box_width_px * source_height_px / source_width_px)),
                )
            if box_height_px is None:
                raise ValueError("Natural Aspect geometry requires width or height.")
            return str(absolute_path), (
                max(1, round(box_height_px * source_width_px / source_height_px)),
                box_height_px,
            )

        if box_width_px is None or box_height_px is None:
            raise ValueError(f"{geometry.mode.value} image geometry requires width and height.")

        if geometry.mode == ImageGeometryMode.EXACT_BOX:
            return str(absolute_path), (box_width_px, box_height_px)

        if geometry.mode == ImageGeometryMode.CONTAIN:
            scale = min(box_width_px / source_width_px, box_height_px / source_height_px)
            return str(absolute_path), (
                max(1, round(source_width_px * scale)),
                max(1, round(source_height_px * scale)),
            )

        if geometry.mode == ImageGeometryMode.COVER:
            cropped = _central_cover_crop(
                image=image,
                target_width_px=box_width_px,
                target_height_px=box_height_px,
            )
            return cropped, (box_width_px, box_height_px)

    raise ValueError(f"Unsupported image geometry mode '{geometry.mode.value}'.")


def _central_cover_crop(
    *,
    image: Image.Image,
    target_width_px: int,
    target_height_px: int,
) -> Any:
    source_width_px, source_height_px = image.size
    target_ratio = target_width_px / target_height_px
    source_ratio = source_width_px / source_height_px
    if source_ratio > target_ratio:
        crop_width = max(1, round(source_height_px * target_ratio))
        left = (source_width_px - crop_width) // 2
        box = (left, 0, left + crop_width, source_height_px)
    else:
        crop_height = max(1, round(source_width_px / target_ratio))
        top = (source_height_px - crop_height) // 2
        box = (0, top, source_width_px, top + crop_height)
    cropped = image.crop(box)
    if "A" in image.getbands() or "transparency" in image.info:
        cropped = cropped.convert("RGBA")
    else:
        cropped = cropped.convert("RGB")
    # PsychoPy's signed texture shader expects in-memory RGB channels in -1..1,
    # while the shader consumes alpha in 0..1.
    # PsychoPy applies this top-to-bottom texture conversion for file/PIL inputs,
    # but not for ndarray inputs. Cover uses an ndarray to avoid derived files, so
    # mirror the conversion here to retain the source's displayed orientation.
    source = np.flipud(np.asarray(cropped, dtype=np.float32))
    prepared = np.empty(source.shape, dtype=np.float32)
    prepared[..., :3] = source[..., :3] / 127.5 - 1.0
    if source.shape[2] == 4:
        prepared[..., 3] = source[..., 3] / 255.0
    return np.ascontiguousarray(prepared)


def _degrees_to_pixels(
    *,
    geometry_degrees: float,
    window: Any,
    display: DisplayRunSpec,
) -> int:
    return visual_angle_width_px(
        degrees=geometry_degrees,
        viewing_distance_cm=display.viewing_distance_cm,
        screen_width_cm=display.screen_width_cm,
        screen_width_px=_screen_width_px(window=window, display=display),
    )


def _signed_degrees_to_pixels(
    value: float,
    *,
    window: Any,
    display: DisplayRunSpec,
) -> int:
    if value == 0:
        return 0
    magnitude = _degrees_to_pixels(
        geometry_degrees=abs(value),
        window=window,
        display=display,
    )
    return magnitude if value > 0 else -magnitude


def _screen_width_px(*, window: Any, display: DisplayRunSpec) -> int:
    if not display.use_current_screen_resolution:
        return display.screen_width_px
    return _window_size_px(window)[0]


def _window_size_px(window: Any) -> tuple[int, int]:
    size = getattr(window, "size", None)
    if isinstance(size, (list, tuple)) and len(size) >= 2:
        return (max(1, int(size[0])), max(1, int(size[1])))
    return (1920, 1080)


def _word_position_px(
    *,
    window: Any,
    display: DisplayRunSpec,
    spec: TextPresentationSpec | None,
) -> tuple[int, int]:
    if spec is None:
        return (0, 0)
    if spec.position_unit == PresentationUnit.WINDOW_HEIGHT_FRACTION:
        window_height_px = _window_size_px(window)[1]
        return (
            round(spec.position_x * window_height_px),
            round(spec.position_y * window_height_px),
        )
    return (
        _signed_degrees_to_pixels(spec.position_x, window=window, display=display),
        _signed_degrees_to_pixels(spec.position_y, window=window, display=display),
    )


def _word_text_height_px(
    *,
    window: Any,
    display: DisplayRunSpec,
    spec: TextPresentationSpec | None,
    value: float | None,
) -> int:
    if spec is not None and spec.legacy_stimulus_width_fraction is not None:
        stimulus_width_px = _degrees_to_pixels(
            geometry_degrees=display.stimulus_width_degrees,
            window=window,
            display=display,
        )
        return max(1, round(stimulus_width_px * spec.legacy_stimulus_width_fraction))
    if spec is None or value is None:
        stimulus_width_px = _degrees_to_pixels(
            geometry_degrees=display.stimulus_width_degrees,
            window=window,
            display=display,
        )
        return max(1, round(stimulus_width_px * WORD_TEXT_HEIGHT_TO_STIMULUS_WIDTH_RATIO))
    if spec.height_unit == PresentationUnit.WINDOW_HEIGHT_FRACTION:
        return max(1, round(value * _window_size_px(window)[1]))
    return _degrees_to_pixels(
        geometry_degrees=value,
        window=window,
        display=display,
    )


def release_stimuli(stimuli: MutableMapping[Any, Any]) -> None:
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
