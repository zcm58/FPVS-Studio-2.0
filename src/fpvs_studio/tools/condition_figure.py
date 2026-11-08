"""Render an aligned FPVS stimulus strip and contrast schematic as a publication PNG."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from math import ceil, isfinite, log10
from pathlib import Path
from textwrap import wrap
from uuid import uuid4

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps, PngImagePlugin

from fpvs_studio.assets import bundled_task_font_path
from fpvs_studio.core.contrast_modulation import sinusoidal_contrast_envelope
from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.paths import filesystem_path
from fpvs_studio.core.serialization import replace_file_atomically
from fpvs_studio.preprocessing.inspection import (
    MAX_BUNDLE_IMAGE_BYTES,
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
    ImageInspectionError,
    validate_image_files,
)

FIGURE_DPI = 600
_WIDTH = 12 * FIGURE_DPI
_MARGIN = 240
_CONTRAST_PLOT_LEFT = 1070
_PLOT_RIGHT = _WIDTH - _MARGIN
_TILE_SIZE = 480
_PLOT_HEIGHT = 580
_AXIS_OFFSET = 70
# Convert final lettering points at 183 mm double-column width to export pixels.
_PLACED_WIDTH_MM = 183
_PIXELS_PER_PLACED_POINT = _WIDTH * 25.4 / (_PLACED_WIDTH_MM * 72)
_TICK_FONT_SIZE = round(5 * _PIXELS_PER_PLACED_POINT)
_LABEL_FONT_SIZE = round(6 * _PIXELS_PER_PLACED_POINT)
_TITLE_FONT_SIZE = round(7 * _PIXELS_PER_PLACED_POINT)
_WAVE_STROKE = round(_PIXELS_PER_PLACED_POINT)
_TITLE_TOP = 116
_TITLE_LINE_HEIGHT = _TITLE_FONT_SIZE + 32
_TITLE_GAP = 64
_INK = "#000000"
_BASE = "#81868B"
_ODDBALL = "#285FA9"
_ODDBALL_FRAME = "#C9434C"
_SQUARE_BASE = "#C32B32"
_SQUARE_ODDBALL = "#237A45"
_SQUARE_PULSE_HEIGHT = 210
_RULE = "#D5DDE5"
_MAX_COMPLETE_CADENCE = 12
_BREAK_EDGE_SLOTS = 4
_IMAGE_FORMATS = ("PNG", "JPEG", "BMP", "TIFF")
_SINUSOID = (*sinusoidal_contrast_envelope(48), 0.0)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConditionFigureSpec:
    """Ordered representative stimuli and effective configured FPVS timing.

    Automatic figures use one sequence entry per visible stimulus slot. An empty
    entry marks a slot without an unused example. Manual figures use the selected
    base and oddball examples throughout the strip.
    """

    condition_name: str
    base_hz: float
    oddball_every_n: int
    base_stimuli: tuple[Path | str, ...]
    oddball_stimulus: Path | str
    duty_cycle_mode: DutyCycleMode = DutyCycleMode.CONTINUOUS
    background_color: str | tuple[int, int, int] = "#808080"
    sequence_stimuli: tuple[Path | str | None, ...] | None = None


@dataclass(frozen=True)
class ConditionFigureResult:
    """Exported PNG and any source-resolution notes."""

    path: Path
    warnings: tuple[str, ...]


def render_condition_figure(spec: ConditionFigureSpec, output_path: Path) -> ConditionFigureResult:
    """Write a 600-DPI PNG at the chosen path after a complete sibling write."""
    selected = _validate_spec(spec)
    layout = _figure_layout(spec)
    samples = _slot_samples(spec, layout.slots)
    source_paths = tuple(dict.fromkeys(item for item in selected if isinstance(item, Path)))
    destination = _validate_output(output_path, source_paths)
    validate_image_files(source_paths)

    notes: list[str] = []
    if spec.sequence_stimuli is not None and None in spec.sequence_stimuli:
        total = len(spec.sequence_stimuli)
        missing = spec.sequence_stimuli.count(None)
        notes.append(f"No unused examples were available for {missing} of {total} stimulus slots.")
    tiles: dict[Path | str, Image.Image] = {}
    for slot, sample in zip(layout.slots, samples, strict=True):
        if slot is not None and sample is not None and sample not in tiles:
            role = "Oddball" if _is_oddball(slot, spec.oddball_every_n) else "Base"
            label = f"{role} example at slot {slot + 1}"
            tiles[sample] = _stimulus_tile(sample, label, layout.tile_size - 28, notes)
    with _draw_figure(spec, layout, samples, tiles, notes) as figure:
        _write_png(figure, destination, spec)
    return ConditionFigureResult(output_path, tuple(notes))


def _validate_spec(spec: ConditionFigureSpec) -> tuple[Path | str, ...]:
    if not spec.condition_name.strip():
        raise ValueError("Choose a named FPVS condition.")
    if not isfinite(spec.base_hz) or spec.base_hz <= 0:
        raise ValueError("The condition needs a positive stimulus rate.")
    if spec.oddball_every_n < 1:
        raise ValueError("The condition needs a positive oddball cadence.")
    if spec.sequence_stimuli is None and len(spec.base_stimuli) != 4:
        raise ValueError("Choose four base stimuli and one oddball stimulus.")
    if spec.sequence_stimuli is None:
        samples = (*spec.base_stimuli, spec.oddball_stimulus)
    else:
        samples = tuple(sample for sample in spec.sequence_stimuli if sample is not None)
        if len(set(samples)) != len(samples):
            raise ValueError("Automatic examples must be distinct across the stimulus sequence.")
    if any(isinstance(sample, str) and not sample.strip() for sample in samples):
        raise ValueError("A selected word stimulus is blank.")
    return samples


def _validate_output(output_path: Path, sources: tuple[Path, ...]) -> Path:
    if output_path.suffix.casefold() != ".png":
        raise ValueError("Choose a PNG filename for the condition figure.")
    destination = filesystem_path(output_path)
    if not destination.parent.is_dir() or destination.is_dir():
        raise ValueError("Choose a PNG file in an existing folder.")
    destination_resolved = destination.resolve()
    for source in map(filesystem_path, sources):
        if source.resolve() == destination_resolved or (
            destination.exists() and source.exists() and destination.samefile(source)
        ):
            raise ValueError("Choose a filename that does not replace a selected stimulus image.")
    return destination


def _stimulus_tile(sample: Path | str, label: str, size: int, notes: list[str]) -> Image.Image:
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if isinstance(sample, str):
        font = _fit_font(sample, size - 44, 85)
        ImageDraw.Draw(tile).text(
            (size / 2, size / 2), sample, fill=_INK, font=font, anchor="mm",
        )
        return tile

    # The selected source was inspected above. Bound this second open as well,
    # since the file may have changed after inspection.
    path = filesystem_path(sample)
    try:
        with path.open("rb") as handle:
            if not 0 < os.fstat(handle.fileno()).st_size <= MAX_BUNDLE_IMAGE_BYTES:
                raise ImageInspectionError(f"Image is too large or empty: {path.name}")
            with Image.open(handle, formats=list(_IMAGE_FORMATS)) as image:
                width, height = image.size
                if max(width, height) > MAX_IMAGE_DIMENSION or width * height > MAX_IMAGE_PIXELS:
                    raise ImageInspectionError(f"Image exceeds the pixel limit: {path.name}")
                with ImageOps.exif_transpose(image) as oriented:
                    _place_image(tile, oriented, label, notes)
    except ImageInspectionError:
        raise
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as error:
        raise ImageInspectionError(f"Could not read stimulus image: {path.name}") from error
    return tile


def _place_image(
    tile: Image.Image, source: Image.Image, label: str, notes: list[str],
) -> None:
    if max(source.size) < tile.width:
        effective_dpi = round(FIGURE_DPI * max(source.size) / tile.width)
        notes.append(
            f"{label} has about {effective_dpi} DPI of source detail at its printed size."
        )
    with source.convert("RGBA") as rgba, ImageOps.contain(
        rgba, tile.size, Image.Resampling.LANCZOS,
    ) as fitted:
        tile.alpha_composite(fitted, ((tile.width - fitted.width) // 2,
                                     (tile.height - fitted.height) // 2))


def _font(size: int) -> ImageFont.FreeTypeFont:
    path = bundled_task_font_path("Open Sans")
    if path is None:
        raise RuntimeError("Open Sans is missing from the FPVS Studio installation.")
    return ImageFont.truetype(str(filesystem_path(path)), size)


def _fit_font(text: str, width: int, size: int) -> ImageFont.FreeTypeFont:
    font = _font(size)
    measured = font.getlength(text)
    if measured > width:
        return _font(max(1, int(size * width / measured)))
    return font


@dataclass(frozen=True)
class _FigureLayout:
    title: tuple[str, ...]
    slots: tuple[int | None, ...]
    edges: tuple[int, ...]
    tile_size: int
    strip_top: int
    contrast_top: int

    @property
    def contrast_zero(self) -> int:
        return self.contrast_top + _PLOT_HEIGHT

    @property
    def time_axis(self) -> int:
        return self.contrast_zero + _AXIS_OFFSET


def _display_slots(cadence: int) -> tuple[int | None, ...]:
    # Two cycles are enough to show four base examples unless each cycle only
    # has one base slot. Keep absolute indices when compressing long cycles.
    cycles = 4 if cadence == 2 else 2
    last = cycles * cadence + min(2, cadence - 1)
    if cadence <= _MAX_COMPLETE_CADENCE:
        return tuple(range(last))
    slots: list[int | None] = []
    for cycle in range(cycles):
        start, end = cycle * cadence, (cycle + 1) * cadence
        slots.extend(range(start, start + _BREAK_EDGE_SLOTS))
        slots.append(None)
        slots.extend(range(end - _BREAK_EDGE_SLOTS, end))
    slots.extend(range(cycles * cadence, last))
    return tuple(slots)


def condition_figure_slot_roles(cadence: int) -> tuple[bool, ...]:
    """Return the oddball flags for the shown slots, excluding axis breaks."""
    if cadence < 1:
        raise ValueError("The condition needs a positive oddball cadence.")
    return tuple(_is_oddball(slot, cadence) for slot in _display_slots(cadence) if slot is not None)


def _slot_samples(
    spec: ConditionFigureSpec, slots: tuple[int | None, ...],
) -> tuple[Path | str | None, ...]:
    cadence = spec.oddball_every_n
    if spec.sequence_stimuli is not None:
        if len(spec.sequence_stimuli) != sum(slot is not None for slot in slots):
            raise ValueError("Automatic examples must match the displayed stimulus slots.")
        selected = iter(spec.sequence_stimuli)
        return tuple(None if slot is None else next(selected) for slot in slots)

    samples: list[Path | str | None] = []
    for slot in slots:
        if slot is None:
            samples.append(None)
        elif _is_oddball(slot, cadence):
            samples.append(spec.oddball_stimulus)
        else:
            index = (slot - slot // cadence) % len(spec.base_stimuli)
            samples.append(spec.base_stimuli[index])
    return tuple(samples)


def _figure_layout(spec: ConditionFigureSpec) -> _FigureLayout:
    # The full condition name remains in PNG metadata.
    name = " ".join(spec.condition_name.split())
    title = tuple(wrap(name if len(name) <= 240 else name[:239].rstrip() + "…", width=55))
    slots = _display_slots(spec.oddball_every_n)
    left = _MARGIN if spec.duty_cycle_mode == DutyCycleMode.BLANK_50 else _CONTRAST_PLOT_LEFT
    step = (_PLOT_RIGHT - left) / len(slots)
    edges = tuple(round(left + index * step) for index in range(len(slots) + 1))
    size = min(_TILE_SIZE, int(step) - 24)
    strip_top = _TITLE_TOP + (len(title) - 1) * _TITLE_LINE_HEIGHT + _TITLE_FONT_SIZE + _TITLE_GAP
    return _FigureLayout(title, slots, edges, size, strip_top, strip_top + size + 145)


def _draw_figure(
    spec: ConditionFigureSpec, layout: _FigureLayout, samples: tuple[Path | str | None, ...],
    tiles: dict[Path | str, Image.Image], notes: list[str],
) -> Image.Image:
    legend_y = layout.time_axis + 223
    break_note = None in layout.slots
    bottom = legend_y + 137 + (128 if break_note else 0)
    canvas = Image.new("RGB", (_WIDTH, bottom), "white")
    draw = ImageDraw.Draw(canvas)
    label_font = _font(_LABEL_FONT_SIZE)
    note_font = _font(_TICK_FONT_SIZE)
    for index, line in enumerate(layout.title):
        title_font = _fit_font(line, _WIDTH - 2 * _MARGIN, _TITLE_FONT_SIZE)
        draw.text((_WIDTH // 2, _TITLE_TOP + index * _TITLE_LINE_HEIGHT), line,
                  font=title_font, fill=_INK, anchor="mt")

    _draw_strip(canvas, draw, spec, layout, samples, tiles)
    square_wave = spec.duty_cycle_mode == DutyCycleMode.BLANK_50
    if not square_wave:
        _draw_contrast_scale(canvas, draw, layout, label_font, note_font)
    _draw_time_axis(draw, spec, layout, note_font)
    if square_wave:
        _draw_square_tracks(draw, spec, layout)
    else:
        _draw_contrast(draw, spec, layout)
        for slot, sample in zip(layout.slots, samples, strict=True):
            if slot is not None and isinstance(sample, Path) and not _is_oddball(
                slot, spec.oddball_every_n,
            ):
                _draw_contrast_key(canvas, layout, tiles[sample], spec.background_color, notes)
                break
    _draw_legend(draw, spec, legend_y, label_font)
    draw.text((_PLOT_RIGHT, legend_y), "Time (s)", font=label_font, fill=_INK, anchor="rm")
    if break_note:
        draw.text((_WIDTH // 2, legend_y + 128), "Axis breaks omit middle slots",
                  font=note_font, fill=_INK, anchor="mm")
    return canvas


def _is_oddball(slot: int, cadence: int) -> bool:
    return (slot + 1) % cadence == 0


def _draw_strip(
    canvas: Image.Image, draw: ImageDraw.ImageDraw, spec: ConditionFigureSpec,
    layout: _FigureLayout, samples: tuple[Path | str | None, ...],
    tiles: dict[Path | str, Image.Image],
) -> None:
    for index, (slot, sample) in enumerate(zip(layout.slots, samples, strict=True)):
        if slot is None:
            continue
        center = (layout.edges[index] + layout.edges[index + 1]) // 2
        left = center - layout.tile_size // 2
        bounds = (left, layout.strip_top, left + layout.tile_size - 1,
                  layout.strip_top + layout.tile_size - 1)
        if sample is None:
            draw.rectangle(bounds, outline=_RULE, width=6)
            font = _fit_font("No unused", layout.tile_size - 24, 46)
            draw.multiline_text((center, layout.strip_top + layout.tile_size // 2),
                                "No unused\nexample", font=font,
                                fill=_INK, anchor="mm", align="center", spacing=8)
        else:
            tile = tiles[sample]
            canvas.paste(tile, (left + 14, layout.strip_top + 14), tile)
        if _is_oddball(slot, spec.oddball_every_n):
            draw.rectangle(bounds, outline=_ODDBALL_FRAME, width=12)


def _draw_contrast_scale(
    canvas: Image.Image, draw: ImageDraw.ImageDraw,
    layout: _FigureLayout, label_font: ImageFont.FreeTypeFont, note_font: ImageFont.FreeTypeFont,
) -> None:
    top, zero, axis = layout.contrast_top, layout.contrast_zero, layout.time_axis
    middle = (top + zero) // 2
    left = layout.edges[0]
    draw.line((left, top, left, axis), fill=_INK, width=10)
    for y, label in ((top, "100"), (middle, "50"), (zero, "0")):
        draw.line((left - 33, y, left, y), fill=_INK, width=8)
        draw.text((left - 62, y), label, font=note_font, fill=_INK, anchor="rm")

    title_width = ceil(label_font.getlength("Contrast (%)")) + 40
    with Image.new("RGBA", (title_width, 170), (0, 0, 0, 0)) as title:
        ImageDraw.Draw(title).text((title_width // 2, 85), "Contrast (%)", font=label_font,
                                   fill=_INK, anchor="mm")
        with title.transpose(Image.Transpose.ROTATE_90) as rotated:
            canvas.paste(rotated, (_MARGIN + 45, (top + zero - rotated.height) // 2), rotated)


def _draw_time_axis(
    draw: ImageDraw.ImageDraw, spec: ConditionFigureSpec, layout: _FigureLayout,
    note_font: ImageFont.FreeTypeFont,
) -> None:
    axis = layout.time_axis
    middle = (layout.contrast_top + layout.contrast_zero) // 2
    show_gridline = spec.duty_cycle_mode != DutyCycleMode.BLANK_50
    ticks: dict[int, int] = {}
    for index, slot in enumerate(layout.slots):
        left, right = layout.edges[index:index + 2]
        if slot is None:
            center = (left + right) // 2
            for x in (center - 19, center + 19):
                draw.line((x - 15, axis + 32, x + 15, axis - 32), fill=_INK, width=7)
            continue
        draw.line((left, axis, right, axis), fill=_INK, width=10)
        if show_gridline:
            draw.line((left, middle, right, middle), fill=_RULE, width=5)
        ticks[left], ticks[right] = slot, slot + 1
    _draw_time_ticks(draw, ticks, spec.base_hz, axis, note_font)


def _draw_time_ticks(
    draw: ImageDraw.ImageDraw, ticks: dict[int, int], rate: float, y: int,
    font: ImageFont.FreeTypeFont,
) -> None:
    places = max(3, min(9, ceil(log10(rate)) + 1))
    labels: list[tuple[int, int, str, float]] = []
    for x, slot in ticks.items():
        seconds = slot / rate
        label = (
            f"{seconds:.6g}" if seconds >= 1000 or 0 < seconds < 10 ** -places
            else f"{seconds:.{places}f}".rstrip("0").rstrip(".")
        )
        half_width = font.getlength(label) / 2
        padding = ceil(half_width) + 20
        center = min(max(x, padding), _WIDTH - padding)
        labels.append((x, center, label, half_width))
    last_x, last_center, _, last_half_width = labels[-1]
    previous_right = 0.0
    for x, center, label, half_width in labels:
        draw.line((x, y, x, y + 32), fill=_INK, width=7)
        if x != last_x and (center - half_width < previous_right + 42
                            or center + half_width + 42 > last_center - last_half_width):
            continue
        draw.text((center, y + 56), label, font=font, fill=_INK, anchor="mt")
        previous_right = center + half_width


def _envelope_points(
    mode: DutyCycleMode, left: int, right: int, top: int, zero: int,
) -> tuple[tuple[int, int], ...]:
    if mode == DutyCycleMode.CONTINUOUS:
        return ((left, top), (right, top))
    return tuple(
        (round(left + (right - left) * index / (len(_SINUSOID) - 1)),
         round(zero - (zero - top) * contrast))
        for index, contrast in enumerate(_SINUSOID)
    )


def _square_pulse(left: int, right: int, top: int, bottom: int) -> tuple[tuple[int, int], ...]:
    quarter = round((right - left) / 4)
    rise, fall = left + quarter, right - quarter
    return (
        (left, bottom), (rise, bottom), (rise, top),
        (fall, top), (fall, bottom), (right, bottom),
    )


def _draw_square_tracks(
    draw: ImageDraw.ImageDraw, spec: ConditionFigureSpec, layout: _FigureLayout,
) -> None:
    base_top = layout.contrast_top
    base_bottom = base_top + _SQUARE_PULSE_HEIGHT
    oddball_bottom = layout.contrast_zero
    oddball_top = oddball_bottom - _SQUARE_PULSE_HEIGHT
    for index, slot in enumerate(layout.slots):
        if slot is None:
            continue
        left, right = layout.edges[index:index + 2]
        draw.line(_square_pulse(left, right, base_top, base_bottom),
                  fill=_SQUARE_BASE, width=_WAVE_STROKE)
        if _is_oddball(slot, spec.oddball_every_n):
            oddball = _square_pulse(left, right, oddball_top, oddball_bottom)
        else:
            oddball = ((left, oddball_bottom), (right, oddball_bottom))
        draw.line(oddball, fill=_SQUARE_ODDBALL, width=_WAVE_STROKE)


def _draw_contrast(
    draw: ImageDraw.ImageDraw, spec: ConditionFigureSpec, layout: _FigureLayout,
) -> None:
    top, zero = layout.contrast_top, layout.contrast_zero
    mode = spec.duty_cycle_mode
    previous: int | None = None
    for index, slot in enumerate(layout.slots):
        if slot is not None:
            left, right = layout.edges[index:index + 2]
            draw.line(_envelope_points(mode, left, right, top, zero),
                      fill=_BASE, width=_WAVE_STROKE)
            if previous is not None and mode == DutyCycleMode.CONTINUOUS:
                draw.line((left, top + 8, left, top + 92), fill=_BASE, width=7)
        previous = slot

    previous_y: int | None = None
    for index, slot in enumerate(layout.slots):
        if slot is None:
            previous_y = None
            continue
        left, right = layout.edges[index:index + 2]
        y = top if _is_oddball(slot, spec.oddball_every_n) else zero
        if previous_y is not None and previous_y != y:
            draw.line((left, previous_y, left, y), fill=_ODDBALL, width=12)
        draw.line((left, y, right, y), fill=_ODDBALL, width=12)
        previous_y = y


def _draw_legend(
    draw: ImageDraw.ImageDraw, spec: ConditionFigureSpec, y: int, font: ImageFont.FreeTypeFont,
) -> None:
    square_wave = spec.duty_cycle_mode == DutyCycleMode.BLANK_50
    base_name = "Base stimulation" if square_wave else "Stimulus contrast"
    base_label = f"{base_name}  ·  {spec.base_hz:.6g} Hz"
    oddball_hz = spec.base_hz / spec.oddball_every_n
    oddball_label = f"Oddball  ·  {oddball_hz:.6g} Hz"
    swatch_width, label_offset, group_gap = 200, 240, 180
    base_width = ceil(font.getlength(base_label))
    oddball_width = ceil(font.getlength(oddball_label))
    legend_width = 2 * label_offset + base_width + group_gap + oddball_width
    first = (_WIDTH - legend_width) // 2
    second = first + label_offset + base_width + group_gap
    if square_wave:
        base_points = _square_pulse(first, first + swatch_width, y - 33, y + 33)
        base_color, oddball_color = _SQUARE_BASE, _SQUARE_ODDBALL
    else:
        base_points = _envelope_points(
            spec.duty_cycle_mode, first, first + swatch_width, y - 33, y + 33,
        )
        base_color, oddball_color = _BASE, _ODDBALL
    oddball_points = _square_pulse(second, second + swatch_width, y - 33, y + 33)
    for left, label, points, color in (
        (first, base_label, base_points, base_color),
        (second, oddball_label, oddball_points, oddball_color),
    ):
        draw.line(points, fill=color, width=13)
        draw.text((left + label_offset, y), label, font=font, fill=_INK, anchor="lm")


def _draw_contrast_key(
    canvas: Image.Image, layout: _FigureLayout, tile: Image.Image,
    background: str | tuple[int, int, int], notes: list[str],
) -> None:
    try:
        color = (
            ImageColor.getcolor(background, "RGB") if isinstance(background, str) else background
        )
    except ValueError:
        notes.append("The contrast key is unavailable for this display background color.")
        return
    side = 186
    with Image.new("RGB", (side, side), color) as blank, blank.copy() as full, tile.resize(
        (side, side), Image.Resampling.LANCZOS,
    ) as example:
        full.paste(example, (0, 0), example)
        for contrast in (1.0, 0.5, 0.0):
            y = round(layout.contrast_zero - _PLOT_HEIGHT * contrast)
            with Image.blend(blank, full, contrast) as swatch:
                canvas.paste(swatch, (548, y - side // 2))


def _write_png(figure: Image.Image, destination: Path, spec: ConditionFigureSpec) -> None:
    metadata = PngImagePlugin.PngInfo()
    metadata.add_itxt("Title", spec.condition_name)
    metadata.add_text("Stimulus rate (Hz)", str(spec.base_hz))
    metadata.add_text("Oddball cadence", str(spec.oddball_every_n))
    metadata.add_text("Oddball rate (Hz)", str(spec.base_hz / spec.oddball_every_n))
    metadata.add_text("Duty cycle mode", spec.duty_cycle_mode.value)
    temporary = destination.with_name(f".condition-figure-{uuid4().hex}.tmp")
    created = False
    try:
        with temporary.open("xb") as handle:
            created = True
            figure.save(handle, format="PNG", dpi=(FIGURE_DPI, FIGURE_DPI), pnginfo=metadata)
            handle.flush()
            os.fsync(handle.fileno())
        replace_file_atomically(temporary, destination)
    finally:
        if created:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove temporary condition figure %s", temporary,
                               exc_info=True)
