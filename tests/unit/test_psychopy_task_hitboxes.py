"""Visible aligned labels must remain clickable without creating native graphics."""

from __future__ import annotations

from dataclasses import replace

import pytest

from fpvs_studio.engines.base import ResolvedTaskItem
from fpvs_studio.engines.psychopy_tasks import _item_at_position


class _WrappedText:
    """Model PsychoPy TextStim's centered contains and rendered text metrics.

    Pyglet centers the 500-pixel wrapping frame at x=200. A 100-pixel line
    therefore occupies [-50, 50] when left aligned and [350, 450] when right
    aligned. PsychoPy's native contains instead centers content_width on posPix.
    """

    pos = (200, 100)
    posPix = (200, 100)
    units = "pix"

    def __init__(self, *, content_width=100, content_height=40, wrap_width=500):
        self.boundingBox = (content_width, content_height)
        self._wrapWidthPix = self.wrapWidth = wrap_width

    def contains(self, position, *, units):
        assert units == "pix"
        width, height = self.boundingBox
        return (
            200 - width / 2 <= position[0] <= 200 + width / 2
            and 100 - height / 2 <= position[1] <= 100 + height / 2
        )


def _label(alignment):
    return ResolvedTaskItem(
        item_id="label", text="Remembered object", text_alignment=alignment,
        position_px=(200, 100), size_px=(500, 40), selectable=True,
    )


@pytest.mark.parametrize(("alignment", "visible_x"), [
    ("left", -25), ("left", 25), ("center", 200), ("right", 375), ("right", 425),
])
def test_selectable_text_uses_visible_aligned_content(alignment, visible_x):
    item = _label(alignment)

    assert _item_at_position(
        (item,), stimuli={"label": _WrappedText()}, x=visible_x, y=100,
    ) is item


@pytest.mark.parametrize("alignment", ["left", "right"])
def test_empty_center_of_wrapping_frame_is_not_the_aligned_label(alignment):
    item = _label(alignment)

    assert _item_at_position(
        (item,), stimuli={"label": _WrappedText()}, x=200, y=100,
    ) is None


@pytest.mark.parametrize("alignment", ["left", "center", "right"])
def test_text_content_vertical_bounds_stay_limited(alignment):
    item = _label(alignment)
    visible_x = {"left": 0, "center": 200, "right": 400}[alignment]

    assert _item_at_position(
        (item,), stimuli={"label": _WrappedText()}, x=visible_x, y=150,
    ) is None


@pytest.mark.parametrize(("alignment", "visible_x"), [("left", -60), ("right", 460)])
def test_default_wrap_width_comes_from_rendered_text(alignment, visible_x):
    item = replace(_label(alignment), size_px=None)
    stimulus = _WrappedText(content_width=120, wrap_width=640)

    assert _item_at_position(
        (item,), stimuli={"label": stimulus}, x=visible_x, y=100,
    ) is item


@pytest.mark.parametrize(("alignment", "visible_x"), [("left", 40), ("right", 360)])
@pytest.mark.parametrize("visible_y", [60, 100, 140])
def test_multiline_text_uses_widest_line_and_keeps_centered_vertical_anchor(
    alignment, visible_x, visible_y,
):
    item = replace(_label(alignment), text="A wider target\nShort")
    stimulus = _WrappedText(content_width=180, content_height=90)

    assert _item_at_position(
        (item,), stimuli={"label": stimulus}, x=visible_x, y=visible_y,
    ) is item
    assert _item_at_position(
        (item,), stimuli={"label": stimulus}, x=visible_x, y=146,
    ) is None


@pytest.mark.parametrize("alignment", ["left", "center", "right"])
def test_an_overflowing_line_uses_pyglets_left_alignment(alignment):
    item = _label(alignment)
    stimulus = _WrappedText(content_width=600)

    assert _item_at_position((item,), stimuli={"label": stimulus}, x=525, y=100) is item
    assert _item_at_position((item,), stimuli={"label": stimulus}, x=-75, y=100) is None


def test_centered_native_containment_without_wrapping_metrics_stays_supported():
    class NativeText:
        def contains(self, position, *, units):
            assert units == "pix"
            return position == (200, 100)

    item = _label("center")
    assert _item_at_position((item,), stimuli={"label": NativeText()}, x=200, y=100) is item


@pytest.mark.parametrize("alignment", ["left", "right"])
def test_aligned_text_without_rendered_metrics_raises_instead_of_guessing(alignment):
    class NativeText:
        def contains(self, position, *, units):
            raise AssertionError("No guessed text point should reach native containment")

    with pytest.raises(RuntimeError, match="requires rendered wrapping-frame metrics"):
        _item_at_position((_label(alignment),), stimuli={"label": NativeText()}, x=0, y=100)


@pytest.mark.parametrize(("alignment", "visible_x"), [("left", 0), ("right", 401)])
def test_odd_wrapping_width_respects_native_integer_anchor(alignment, visible_x):
    item = _label(alignment)
    stimulus = _WrappedText(wrap_width=501)

    assert _item_at_position(
        (item,), stimuli={"label": stimulus}, x=visible_x, y=100,
    ) is item


@pytest.mark.parametrize("kind", ["image", "circle"])
def test_image_and_shape_containment_is_never_shifted_by_text_alignment(kind):
    item = replace(
        _label("left"), text=None,
        image_path="stimuli/target.png" if kind == "image" else None,
        shape="circle" if kind == "circle" else None,
    )
    stimulus = _WrappedText()

    assert _item_at_position((item,), stimuli={"label": stimulus}, x=200, y=100) is item
    assert _item_at_position((item,), stimuli={"label": stimulus}, x=0, y=100) is None


@pytest.mark.parametrize(("alignment", "visible_x"), [("left", 0), ("right", 400)])
def test_nonselectable_text_is_not_activated_at_its_visible_position(alignment, visible_x):
    item = replace(_label(alignment), selectable=False)

    assert _item_at_position(
        (item,), stimuli={"label": _WrappedText()}, x=visible_x, y=100,
    ) is None
