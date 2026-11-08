"""Non-GUI coverage for the exported scientific schematic."""

from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageColor, ImageDraw

from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.preprocessing.inspection import ImageInspectionError
from fpvs_studio.tools import condition_figure
from fpvs_studio.tools.condition_figure import ConditionFigureSpec, render_condition_figure


def _write_stimuli(folder: Path) -> tuple[Path, ...]:
    paths = tuple(folder / f"stimulus {index}.png" for index in range(5))
    for path in paths:
        with Image.new("RGB", (32, 16), "green") as image:
            image.save(path)
    return paths


def test_exports_real_600_dpi_png_with_aligned_examples_and_timing(tmp_path):
    paths = _write_stimuli(tmp_path)
    output = tmp_path / "Chosen figure.PNG"
    spec = ConditionFigureSpec("Example — faces", 6.0, 5, paths[:4], paths[4])

    result = render_condition_figure(spec, output)

    assert result.path == output
    assert len(result.warnings) == 5
    with Image.open(output) as image:
        assert image.format == "PNG"
        assert image.info["dpi"] == pytest.approx((600, 600), abs=0.01)
        assert image.info["Title"] == spec.condition_name
        assert image.info["Stimulus rate (Hz)"] == "6.0"
        assert image.info["Oddball cadence"] == "5"
        assert image.info["Oddball rate (Hz)"] == "1.2"
        assert image.info["Duty cycle mode"] == "continuous"
        assert image.width == 7200
        layout = condition_figure._figure_layout(spec)
        assert layout.slots == tuple(range(12))
        assert (layout.slots[-1] + 1) / spec.base_hz == 2.0
        centers = _centers(layout)
        _assert_continuous_track(image, layout)
        # Landscape images retain their proportions. There are red outlines on
        # exactly the oddball slots, and the blue trace spans the same slots.
        for index, center in enumerate(centers):
            oddball = index in (4, 9)
            border = condition_figure._ODDBALL_FRAME if oddball else "white"
            assert image.getpixel((center, layout.strip_top + 3)) == ImageColor.getrgb(border)
            plateau = layout.contrast_top if oddball else layout.contrast_zero
            assert image.getpixel((center, plateau)) == ImageColor.getrgb(condition_figure._ODDBALL)
        assert image.getpixel((centers[0], layout.strip_top + 80)) == ImageColor.getrgb("white")
        assert image.getpixel((centers[0], layout.strip_top + 240)) == ImageColor.getrgb("green")
        for index in (4, 5, 9, 10):
            x = layout.edges[index]
            y = (layout.contrast_top + layout.contrast_zero) // 2
            assert image.getpixel((x, y)) == ImageColor.getrgb(condition_figure._ODDBALL)
        for x in layout.edges:
            assert image.getpixel((x, layout.time_axis + 20)) == ImageColor.getrgb(
                condition_figure._INK,
            )


def _centers(layout):
    return tuple(
        (left + right) // 2 for left, right in zip(layout.edges[:-1], layout.edges[1:], strict=True)
    )


def _assert_centered_title(image, layout):
    with image.crop((0, 0, image.width, layout.strip_top)) as header, Image.new(
        "RGB", header.size, "white",
    ) as blank:
        bounds = ImageChops.difference(header, blank).getbbox()
    assert bounds is not None
    left, top, right, bottom = bounds
    assert (left + right) / 2 == pytest.approx(image.width / 2, abs=8)
    assert top >= condition_figure._TITLE_TOP
    assert bottom <= condition_figure._TITLE_TOP + condition_figure._TITLE_FONT_SIZE + 16


@pytest.mark.parametrize("mode", list(DutyCycleMode))
def test_words_and_nonstandard_cadence_use_configured_oddball_positions(tmp_path, mode):
    output = tmp_path / "words.png"
    spec = ConditionFigureSpec(
        "Read words", 6.0, 3, ("chair", "tree", "book", "house"), "boat", mode,
    )

    result = render_condition_figure(spec, output)

    assert not result.warnings
    with Image.open(output) as image:
        assert image.info["Oddball rate (Hz)"] == "2.0"
        assert image.info["Duty cycle mode"] == mode.value
        layout = condition_figure._figure_layout(spec)
        assert layout.slots == tuple(range(8))
        _assert_centered_title(image, layout)
        if mode == DutyCycleMode.BLANK_50:
            _assert_square_tracks(image, layout, oddball_indices={2, 5})
            return

        for index, center in enumerate(_centers(layout)):
            y = layout.contrast_top if index in (2, 5) else layout.contrast_zero
            assert image.getpixel((center, y)) == ImageColor.getrgb(condition_figure._ODDBALL)

        left, right = layout.edges[:2]
        early = (3 * left + right) // 4
        if mode == DutyCycleMode.CONTINUOUS:
            _assert_continuous_track(image, layout)
        else:
            mid_y = (layout.contrast_top + layout.contrast_zero) // 2
            assert image.getpixel((early, mid_y)) == ImageColor.getrgb(condition_figure._BASE)
            assert image.getpixel(((left + right) // 2, layout.contrast_top)) == ImageColor.getrgb(
                condition_figure._BASE,
            )


def _assert_continuous_track(image, layout):
    blue = ImageColor.getrgb(condition_figure._ODDBALL)
    white = ImageColor.getrgb("white")
    assert layout.edges[0] == image.width - layout.edges[-1]
    assert layout.plot_height < condition_figure._PLOT_HEIGHT
    with image.crop((0, layout.contrast_top - 95, image.width, layout.time_axis - 10)) as track:
        colors = track.getcolors(maxcolors=2)
    assert colors is not None
    assert {color for _, color in colors} == {blue, white}


def test_continuous_oddball_track_preserves_axis_breaks(tmp_path):
    spec = ConditionFigureSpec(
        "Read words", 6.0, 18, ("chair", "tree", "book", "house"), "boat",
    )
    output = tmp_path / "axis-breaks.png"
    render_condition_figure(spec, output)

    layout = condition_figure._figure_layout(spec)
    blue = ImageColor.getrgb(condition_figure._ODDBALL)
    white = ImageColor.getrgb("white")
    with Image.open(output) as image:
        for slot, center in zip(layout.slots, _centers(layout), strict=True):
            if slot is None:
                assert image.getpixel((center, layout.contrast_top)) == white
                assert image.getpixel((center, layout.contrast_zero)) == white
            else:
                y = layout.contrast_top if slot in (17, 35) else layout.contrast_zero
                assert image.getpixel((center, y)) == blue


def _assert_square_tracks(image, layout, oddball_indices):
    red = ImageColor.getrgb(condition_figure._SQUARE_BASE)
    green = ImageColor.getrgb(condition_figure._SQUARE_ODDBALL)
    white = ImageColor.getrgb("white")
    height = condition_figure._SQUARE_PULSE_HEIGHT
    red_top = layout.contrast_top
    green_bottom = layout.contrast_zero
    green_top = green_bottom - height

    for index, center in enumerate(_centers(layout)):
        left, right = layout.edges[index:index + 2]
        quarter = round((right - left) / 4)
        rise, fall = left + quarter, right - quarter
        red_middle = red_top + height // 2
        green_middle = green_top + height // 2
        assert image.getpixel((center, red_top)) == red
        assert image.getpixel((rise, red_middle)) == red
        assert image.getpixel((fall, red_middle)) == red
        assert image.getpixel((rise - 15, red_top)) == white
        assert image.getpixel((fall + 15, red_top)) == white
        if index in oddball_indices:
            assert image.getpixel((center, green_top)) == green
            assert image.getpixel((rise, green_middle)) == green
            assert image.getpixel((fall, green_middle)) == green
        else:
            assert image.getpixel((center, green_top)) == white
            assert image.getpixel((center, green_bottom)) == green
        assert image.getpixel((rise - 15, green_top)) == white
        assert image.getpixel((fall + 15, green_top)) == white

    # No shared vertical axis or midline intersects the stacked traces.
    between = (layout.contrast_top + layout.contrast_zero) // 2
    assert image.getpixel((layout.edges[0], between)) == white
    assert image.getpixel((_centers(layout)[0], between)) == white
    assert image.getpixel((layout.edges[0], layout.time_axis + 20)) == ImageColor.getrgb(
        condition_figure._INK,
    )
    assert layout.edges[0] == image.width - layout.edges[-1]
    with image.crop((0, layout.time_axis + 180, image.width, layout.time_axis + 270)) as legend:
        colors = legend.getcolors(maxcolors=1024)
    assert colors is not None
    assert {red, green, ImageColor.getrgb("black")} <= {color for _, color in colors}


def test_long_time_endpoint_stays_inside_figure_edge():
    width = condition_figure._WIDTH
    with Image.new("RGB", (width, 160), "white") as figure:
        draw = ImageDraw.Draw(figure)
        font = condition_figure._font(condition_figure._TICK_FONT_SIZE)
        condition_figure._draw_time_ticks(
            draw, {condition_figure._MARGIN: 0, condition_figure._PLOT_RIGHT: 12},
            2.73737373e-120, 0, font,
        )
        with figure.crop((width // 2, 56, width, figure.height)) as label, Image.new(
            "RGB", label.size, "white",
        ) as blank:
            bounds = ImageChops.difference(label, blank).getbbox()
    assert bounds is not None
    assert bounds[2] < width // 2 - 10


def test_cycle_positions_allow_every_stimulus_and_bound_large_cadences():
    assert condition_figure._display_slots(1) == (0, 1)
    assert condition_figure._display_slots(2) == tuple(range(9))
    assert condition_figure._display_slots(1000) == (
        0, 1, 2, 3, None, 996, 997, 998, 999,
        1000, 1001, 1002, 1003, None, 1996, 1997, 1998, 1999, 2000, 2001,
    )
    roles = condition_figure.condition_figure_slot_roles(1000)
    assert len(roles) == 18
    assert tuple(index for index, oddball in enumerate(roles) if oddball) == (7, 15)


def test_explicit_examples_fill_their_own_slots_and_square_wave_omits_contrast_key(tmp_path):
    colors = tuple((10 + index * 10, 100, 50) for index in range(12))
    paths = tuple(tmp_path / f"stimulus-{index}.png" for index in range(len(colors)))
    for path, color in zip(paths, colors, strict=True):
        with Image.new("RGB", (32, 16), color) as source:
            source.save(path)
    sequence = (*paths[:8], None, *paths[9:])
    spec = ConditionFigureSpec(
        "Example", 6.0, 5, paths[:4], paths[4], DutyCycleMode.BLANK_50,
        sequence_stimuli=sequence,
    )
    output = tmp_path / "figure.png"

    result = render_condition_figure(spec, output)

    assert result.warnings[0] == "No unused examples were available for 1 of 12 stimulus slots."
    layout = condition_figure._figure_layout(spec)
    centers = _centers(layout)
    with Image.open(output) as figure:
        for index, (center, color) in enumerate(zip(centers, colors, strict=True)):
            if index == 8:
                assert figure.getpixel((center, layout.strip_top + 3)) == ImageColor.getrgb(
                    condition_figure._RULE,
                )
            else:
                assert figure.getpixel((center, layout.strip_top + layout.tile_size // 2)) == color
        for y in (layout.contrast_top, layout.contrast_zero):
            assert figure.getpixel((layout.edges[0] - 20, y)) == ImageColor.getrgb("white")

    with pytest.raises(ValueError, match="replace a selected stimulus"):
        render_condition_figure(spec, paths[-1])


def test_rejects_output_over_selected_source(tmp_path):
    paths = _write_stimuli(tmp_path)
    spec = ConditionFigureSpec("Example", 6.0, 5, paths[:4], paths[4])
    original = paths[0].read_bytes()

    with pytest.raises(ValueError, match="replace a selected stimulus"):
        render_condition_figure(spec, paths[0])

    assert paths[0].read_bytes() == original


def test_bad_source_preserves_existing_output(tmp_path):
    paths = _write_stimuli(tmp_path)
    paths[0].write_bytes(b"Invalid stimulus image")
    output = tmp_path / "existing.png"
    output.write_bytes(b"prior export")
    spec = ConditionFigureSpec("Example", 6.0, 5, paths[:4], paths[4])

    with pytest.raises(ImageInspectionError, match="unsafe"):
        render_condition_figure(spec, output)

    assert output.read_bytes() == b"prior export"


def test_failed_replacement_leaves_prior_output_and_cleans_partial_file(tmp_path, monkeypatch):
    output = tmp_path / "existing.png"
    output.write_bytes(b"prior export")
    spec = ConditionFigureSpec("Read words", 6.0, 5, ("chair", "tree", "book", "house"), "boat")

    def fail_replace(source, destination):
        assert source.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        raise PermissionError("Destination is locked")

    monkeypatch.setattr(condition_figure, "replace_file_atomically", fail_replace)
    with pytest.raises(PermissionError, match="Destination is locked"):
        render_condition_figure(spec, output)

    assert output.read_bytes() == b"prior export"
    assert list(tmp_path.iterdir()) == [output]
