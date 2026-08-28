"""Stimulus drawing and condition-local preparation for the PsychoPy engine."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from PIL import Image

from fpvs_studio.core.display_geometry import visual_angle_width_px
from fpvs_studio.core.enums import (
    ImageGeometryMode,
    PresentationUnit,
    StimulusModality,
    StimulusTransform,
)
from fpvs_studio.core.paths import resolve_project_relative_path
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
_PSYCHOPY_TEXTURE_ID_ATTRIBUTES = (
    "_texID",
    "_maskID",
    "_pixbuffID",
    "_pixBuffID",
)
WORD_TEXT_HEIGHT_TO_STIMULUS_WIDTH_RATIO = 0.25


@dataclass(frozen=True)
class StimulusCleanupFailure:
    """One graphics-resource operation that failed during condition cleanup."""

    stimulus_index: int | None
    operation: str
    error_type: str
    message: str


@dataclass(frozen=True)
class StimulusCleanupReport:
    """Result of one deterministic, condition-local cleanup attempt."""

    stimulus_count: int
    failures: tuple[StimulusCleanupFailure, ...] = ()

    @property
    def succeeded(self) -> bool:
        return not self.failures

    def raise_for_failure(self) -> None:
        if self.failures:
            raise ConditionResourceCleanupError(self)


class ConditionResourceCleanupError(RuntimeError):
    """Raised when one or more prepared graphics resources could not be deleted."""

    def __init__(self, report: StimulusCleanupReport) -> None:
        self.report = report
        super().__init__(
            "Failed to release "
            f"{len(report.failures)} PsychoPy condition graphics resource operation(s)."
        )


class ConditionResourcePreparationError(RuntimeError):
    """Preparation failed and its partial-build rollback also had cleanup failures."""

    def __init__(self, cleanup_report: StimulusCleanupReport) -> None:
        self.cleanup_report = cleanup_report
        super().__init__(
            "PsychoPy condition preparation failed and rollback could not release "
            f"{len(cleanup_report.failures)} graphics resource operation(s)."
        )


class PreparedConditionResources:
    """Own all drawables and graphics resources for exactly one condition.

    Instances are created through :func:`prepare_condition_resources`. The prepared
    sequence is a shared list so releasing the owner also clears an engine-held
    reference to that same sequence. A resource owner never becomes ready until all
    unique drawables and all fixation variants have been primed and queued GPU work
    has completed.
    """

    def __init__(
        self,
        *,
        gpu_sync: Callable[[], None],
        fixation_stimuli: Sequence[Any] = (),
        delete_pixel_buffer: Callable[[Any], None] | None = None,
        delete_display_list: Callable[[Any], None] | None = None,
    ) -> None:
        self._stimuli: dict[tuple[object, ...], Any] = {}
        self._prepared_sequence: list[Any] = []
        self._fixation_stimuli: list[Any] = list(fixation_stimuli)
        self._delete_pixel_buffer = delete_pixel_buffer
        self._delete_display_list = delete_display_list
        self._gpu_sync: Callable[[], None] | None = gpu_sync
        self._gpu_synchronized = False
        self._ready = False
        self._released = False
        self._cleanup_report: StimulusCleanupReport | None = None

    @property
    def stimuli(self) -> Mapping[tuple[object, ...], Any]:
        """Return the prepared render variants while this owner is live."""

        return self._stimuli

    @property
    def prepared_sequence(self) -> Sequence[Any]:
        """Return the event-indexed draw sequence cleared in-place on release."""

        return self._prepared_sequence

    @property
    def fixation_stim(self) -> Any | None:
        """Return the first/default fixation drawable for compatibility."""

        return self._fixation_stimuli[0] if self._fixation_stimuli else None

    @property
    def fixation_stimuli(self) -> Sequence[Any]:
        """Return all immutable fixation-color variants, cleared on release."""

        return self._fixation_stimuli

    @property
    def gpu_synchronized(self) -> bool:
        return self._gpu_synchronized

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def released(self) -> bool:
        return self._released

    @property
    def cleanup_report(self) -> StimulusCleanupReport | None:
        return self._cleanup_report

    def release(self, *, raise_on_error: bool = False) -> StimulusCleanupReport:
        """Release owned graphics resources once and clear all strong references.

        Repeated calls return the original report without attempting a second OpenGL
        deletion. Callers can inspect the report or request an exception explicitly;
        this keeps a cleanup failure from accidentally masking an active playback
        exception in a ``finally`` block.
        """

        if self._cleanup_report is None:
            cleanup_report = release_stimuli(
                self._stimuli,
                additional_stimuli=self._fixation_stimuli,
                delete_pixel_buffer=self._delete_pixel_buffer,
                delete_display_list=self._delete_display_list,
            )
            gpu_sync = self._gpu_sync
            if gpu_sync is not None:
                try:
                    gpu_sync()
                except Exception as error:
                    cleanup_report = StimulusCleanupReport(
                        stimulus_count=cleanup_report.stimulus_count,
                        failures=(
                            *cleanup_report.failures,
                            _cleanup_failure(
                                stimulus_index=None,
                                operation="synchronize_cleanup",
                                error=error,
                            ),
                        ),
                    )
            self._cleanup_report = cleanup_report
            self._prepared_sequence.clear()
            self._fixation_stimuli.clear()
            self._gpu_sync = None
            self._gpu_synchronized = False
            self._ready = False
            self._released = True
        if raise_on_error:
            self._cleanup_report.raise_for_failure()
        return self._cleanup_report

    def _prime_and_synchronize(
        self,
        *,
        window: Any,
        gpu_sync: Callable[[], None],
    ) -> None:
        if self._released:
            raise RuntimeError("Released condition resources cannot be prepared again.")
        if self._ready or self._gpu_synchronized:
            raise RuntimeError("Condition resources have already been synchronized.")
        _prime_stimuli(
            self._stimuli,
            window=window,
            fixation_stimuli=self._fixation_stimuli,
        )
        gpu_sync()
        self._gpu_synchronized = True
        self._ready = True


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
    """Create and prime every unique render variant.

    This compatibility helper does not perform the explicit GPU-ready barrier because
    it has no fixation drawable to prime. New condition playback should use
    :func:`prepare_condition_resources`.
    """

    stimuli: dict[tuple[object, ...], Any] = {}
    try:
        _populate_prepared_stimuli(
            stimuli=stimuli,
            prepared_sequence=None,
            visual=visual,
            window=window,
            project_root=project_root,
            run_spec=run_spec,
        )
        _prime_stimuli(stimuli, window=window)
    except BaseException:
        release_stimuli(stimuli)
        raise
    return stimuli


def prepare_condition_resources(
    *,
    visual: Any,
    window: Any,
    project_root: Path,
    run_spec: RunSpec,
    fixation_stim: Any | None = None,
    fixation_stimuli: Sequence[Any] | None = None,
    gpu_sync: Callable[[], None] | None = None,
    delete_pixel_buffer: Callable[[Any], None] | None = None,
    delete_display_list: Callable[[Any], None] | None = None,
) -> PreparedConditionResources:
    """Build, prime, synchronize, and return one condition-local resource owner.

    Pass either one compatibility ``fixation_stim`` or the immutable color variants
    in ``fixation_stimuli``. Any failure before readiness rolls back every resource
    that was already created. If rollback itself is incomplete, the raised preparation
    error retains the original exception as its cause and exposes the structured
    cleanup report.
    """

    prepared_fixation_stimuli = _normalize_fixation_stimuli(
        fixation_stim=fixation_stim,
        fixation_stimuli=fixation_stimuli,
    )
    resolved_gpu_sync = gpu_sync or synchronize_gpu
    resources = PreparedConditionResources(
        gpu_sync=resolved_gpu_sync,
        fixation_stimuli=prepared_fixation_stimuli,
        delete_pixel_buffer=delete_pixel_buffer,
        delete_display_list=delete_display_list,
    )
    try:
        _populate_prepared_stimuli(
            stimuli=resources._stimuli,
            prepared_sequence=resources._prepared_sequence,
            visual=visual,
            window=window,
            project_root=project_root,
            run_spec=run_spec,
        )
        resources._prime_and_synchronize(
            window=window,
            gpu_sync=resolved_gpu_sync,
        )
    except BaseException as error:
        cleanup_report = resources.release()
        if cleanup_report.failures and isinstance(error, Exception):
            raise ConditionResourcePreparationError(cleanup_report) from error
        raise
    return resources


def synchronize_gpu() -> None:
    """Wait once for all previously submitted PsychoPy/OpenGL work to complete."""

    gl_module = _load_psychopy_gl()
    finish = getattr(gl_module, "glFinish", None)
    if not callable(finish):
        raise RuntimeError("PsychoPy's OpenGL module does not expose glFinish().")
    finish()


def _normalize_fixation_stimuli(
    *,
    fixation_stim: Any | None,
    fixation_stimuli: Sequence[Any] | None,
) -> tuple[Any, ...]:
    if fixation_stim is not None and fixation_stimuli is not None:
        raise ValueError("Pass fixation_stim or fixation_stimuli, not both.")
    normalized = tuple(fixation_stimuli or ())
    if fixation_stim is not None:
        normalized = (fixation_stim,)
    if not normalized:
        raise ValueError("Condition preparation requires at least one fixation stimulus.")
    return normalized


def _populate_prepared_stimuli(
    *,
    stimuli: dict[tuple[object, ...], Any],
    prepared_sequence: list[Any] | None,
    visual: Any,
    window: Any,
    project_root: Path,
    run_spec: RunSpec,
) -> None:
    for event in run_spec.stimulus_sequence:
        render_key = stimulus_render_key(event, run_spec=run_spec)
        stimulus = stimuli.get(render_key)
        if stimulus is None:
            stimulus = _prepare_stimulus(
                visual=visual,
                window=window,
                project_root=project_root,
                run_spec=run_spec,
                event=event,
            )
            stimuli[render_key] = stimulus
        if prepared_sequence is not None:
            prepared_sequence.append(stimulus)


def _prime_stimuli(
    stimuli: Mapping[tuple[object, ...], Any],
    *,
    window: Any,
    fixation_stimuli: Sequence[Any] = (),
) -> None:
    """Force deferred texture/glyph work before any timed presentation flip."""

    for stimulus in stimuli.values():
        stimulus.draw()
    for fixation_stim in fixation_stimuli:
        fixation_stim.draw()
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
        absolute_path = resolve_project_relative_path(project_root, event.image_path)
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
) -> Image.Image:
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
        return cropped.convert("RGBA")
    return cropped.convert("RGB")


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


def release_stimuli(
    stimuli: MutableMapping[Any, Any],
    *,
    additional_stimuli: Sequence[Any] = (),
    delete_pixel_buffer: Callable[[Any], None] | None = None,
    delete_display_list: Callable[[Any], None] | None = None,
) -> StimulusCleanupReport:
    """Release PsychoPy resources and return a structured cleanup report.

    PsychoPy 2026 creates ``_pixbuffID`` but its cleanup method checks the differently
    cased ``_pixBuffID``. Delete the real lowercase pixel buffer explicitly before
    calling ``clearTextures``. All Python-side IDs are then discarded so a destructor
    cannot repeat a failed GL operation; a caller that sees failures can recover by
    closing and recreating the graphics context.
    """

    failures: list[StimulusCleanupFailure] = []
    unique_stimuli: list[Any] = []
    seen_stimulus_ids: set[int] = set()
    for stimulus in (*stimuli.values(), *additional_stimuli):
        stimulus_identity = id(stimulus)
        if stimulus_identity in seen_stimulus_ids:
            continue
        seen_stimulus_ids.add(stimulus_identity)
        unique_stimuli.append(stimulus)

    for stimulus_index, stimulus in enumerate(unique_stimuli):
        display_list_id = getattr(stimulus, "_listID", None)
        if display_list_id is not None:
            try:
                (delete_display_list or _delete_psychopy_display_list)(display_list_id)
            except Exception as error:
                failures.append(
                    _cleanup_failure(
                        stimulus_index=stimulus_index,
                        operation="delete_display_list",
                        error=error,
                    )
                )
            else:
                _neutralize_psychopy_display_list_id(stimulus)

        pixel_buffer_id = getattr(stimulus, "_pixbuffID", None)
        if pixel_buffer_id is not None:
            try:
                (delete_pixel_buffer or _delete_psychopy_pixel_buffer)(pixel_buffer_id)
            except Exception as error:
                failures.append(
                    _cleanup_failure(
                        stimulus_index=stimulus_index,
                        operation="delete_pixel_buffer",
                        error=error,
                    )
                )
            else:
                _discard_psychopy_texture_id(stimulus, "_pixbuffID")

        try:
            clear_textures = getattr(stimulus, "clearTextures", None)
            if callable(clear_textures):
                clear_textures()
        except Exception as error:
            failures.append(
                _cleanup_failure(
                    stimulus_index=stimulus_index,
                    operation="clear_textures",
                    error=error,
                )
            )
        finally:
            _discard_psychopy_texture_ids(stimulus)
            _neutralize_psychopy_display_list_id(stimulus)
    stimuli.clear()

    report = StimulusCleanupReport(
        stimulus_count=len(unique_stimuli),
        failures=tuple(failures),
    )
    if failures:
        LOGGER.warning(
            "Ignored %d PsychoPy stimulus texture cleanup error(s); "
            "discarded texture ids to prevent repeated destructor cleanup failures. "
            "Last error type: %s.",
            len(failures),
            failures[-1].error_type,
        )
    return report


def _load_psychopy_gl() -> Any:
    """Load PsychoPy's active OpenGL module only inside the engine call path."""

    return import_module("psychopy.visual.basevisual").GL


def _delete_psychopy_pixel_buffer(pixel_buffer_id: Any) -> None:
    gl_module = _load_psychopy_gl()
    delete_buffers = getattr(gl_module, "glDeleteBuffers", None)
    if not callable(delete_buffers):
        raise RuntimeError("PsychoPy's OpenGL module does not expose glDeleteBuffers().")
    delete_buffers(1, pixel_buffer_id)


def _delete_psychopy_display_list(display_list_id: Any) -> None:
    gl_module = _load_psychopy_gl()
    delete_lists = getattr(gl_module, "glDeleteLists", None)
    if not callable(delete_lists):
        raise RuntimeError("PsychoPy's OpenGL module does not expose glDeleteLists().")
    delete_lists(display_list_id, 1)


def _cleanup_failure(
    *,
    stimulus_index: int | None,
    operation: str,
    error: Exception,
) -> StimulusCleanupFailure:
    return StimulusCleanupFailure(
        stimulus_index=stimulus_index,
        operation=operation,
        error_type=type(error).__name__,
        message=str(error),
    )


def _discard_psychopy_texture_ids(stimulus: Any) -> None:
    for attribute_name in _PSYCHOPY_TEXTURE_ID_ATTRIBUTES:
        _discard_psychopy_texture_id(stimulus, attribute_name)


def _neutralize_psychopy_display_list_id(stimulus: Any) -> None:
    """Prevent TextStim's destructor from deleting an already-released list again."""

    if hasattr(stimulus, "_listID"):
        stimulus._listID = 0


def _discard_psychopy_texture_id(stimulus: Any, attribute_name: str) -> None:
    try:
        delattr(stimulus, attribute_name)
    except AttributeError:
        return
