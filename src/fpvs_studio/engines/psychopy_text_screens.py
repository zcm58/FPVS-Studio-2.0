"""Text-screen rendering helper for the PsychoPy engine."""

from __future__ import annotations

from math import isfinite
from typing import Any

from fpvs_studio.engines.psychopy_graphics_lifetime import release_failed_graphics_frames
from fpvs_studio.engines.psychopy_stimuli import (
    ConditionResourceCleanupError,
    release_stimuli,
)

_TEXT_HEIGHTS = {"heading": 36.0, "body": 28.0, "footer": 24.0}


def _screen_size(window: Any) -> tuple[float, float]:
    width, height = (float(value) for value in window.size[:2])
    if not all(isfinite(value) and value > 0 for value in (width, height)):
        raise RuntimeError("Participant instructions require a valid presentation window size.")
    return width, height


def _layout_text_screen(stimuli: dict[str, Any], size: tuple[float, float]) -> None:
    """Flow measured text blocks without changing their wording or input behavior."""
    width, height = size
    wrap_width = min(1200.0, width * 0.9)
    available_height = height * 0.9
    gap = min(28.0, height * 0.03)
    for scale in (1.0, 0.9, 0.8, 0.7, 2.0 / 3.0):
        bounds = {}
        for name, stimulus in stimuli.items():
            text_height = _TEXT_HEIGHTS[name] * scale
            changed = False
            if stimulus.height != text_height:
                stimulus.height = text_height
                changed = True
            if stimulus.wrapWidth != wrap_width:
                stimulus.wrapWidth = wrap_width
                changed = True
            if changed:
                # Height/wrapping updates leave PsychoPy's metrics stale. Passing
                # no text forces a refresh; assigning the same string is a no-op.
                stimulus.setText(log=False)
            text_width, block_height = (float(value) for value in stimulus.boundingBox)
            if not all(isfinite(value) and value >= 0 for value in (text_width, block_height)):
                raise RuntimeError("Cannot measure the rendered participant instructions.")
            bounds[name] = (text_width, block_height)
        total_height = sum(value[1] for value in bounds.values()) + gap * (len(bounds) - 1)
        if total_height <= available_height and all(
            value[0] <= wrap_width for value in bounds.values()
        ):
            top = total_height / 2.0
            for name, stimulus in stimuli.items():
                stimulus.pos = (0, top)
                top -= bounds[name][1] + gap
            return
    raise RuntimeError(
        "Participant instructions do not fit this display at a readable text size. "
        "Use a larger presentation window or shorten the instructions."
    )


def show_text_screen(
    *,
    visual: Any,
    core: Any,
    window: Any,
    keyboard: Any,
    is_aborted: Any,
    set_aborted: Any,
    heading: str,
    body: str | None,
    countdown_seconds: float | None,
    continue_key: str | None,
    continue_prompt: str | None = None,
) -> bool:
    """Render one transition-style text screen."""

    keyboard.clearEvents()
    screen_clock = core.Clock()

    def footer_text() -> str:
        if continue_key is not None:
            prompt = continue_prompt or f"Press '{continue_key}' to continue."
            return f"{prompt} Press Escape to abort."
        if countdown_seconds is not None:
            remaining = max(0.0, countdown_seconds - screen_clock.getTime())
            return f"Starting automatically in {remaining:0.1f} s. Press Escape to abort."
        return "Press Escape to abort."

    stimuli: dict[str, Any] = {}
    failed = False
    try:
        if is_aborted():
            return True
        stimuli["heading"] = visual.TextStim(
            window,
            text=heading,
            units="pix",
            height=36,
            anchorHoriz="center",
            anchorVert="top",
            wrapWidth=1200,
            color="white",
            autoLog=False,
        )
        if body:
            stimuli["body"] = visual.TextStim(
                window,
                text=body,
                units="pix",
                height=28,
                anchorHoriz="center",
                anchorVert="top",
                wrapWidth=1200,
                color="white",
                autoLog=False,
            )
        footer = footer_text()
        stimuli["footer"] = visual.TextStim(
            window,
            text=footer,
            units="pix",
            height=24,
            anchorHoriz="center",
            anchorVert="top",
            wrapWidth=1200,
            color="white",
            autoLog=False,
        )
        layout_size = _screen_size(window)
        _layout_text_screen(stimuli, layout_size)
        while True:
            if is_aborted():
                return True
            next_footer = footer_text() if countdown_seconds is not None else footer
            layout_changed = False
            if next_footer != footer:
                stimuli["footer"].text = next_footer
                footer = next_footer
                layout_changed = True
            next_size = _screen_size(window)
            if layout_changed or next_size != layout_size:
                _layout_text_screen(stimuli, next_size)
                layout_size = next_size
            for stimulus in stimuli.values():
                stimulus.draw()
            window.flip()

            keys = keyboard.getKeys(
                keyList=[key for key in [continue_key, "escape"] if key is not None],
                waitRelease=False,
                clear=True,
            )
            for key in keys:
                key_name = getattr(key, "name", str(key))
                if key_name == "escape":
                    set_aborted()
                    return True
                if continue_key is not None and key_name == continue_key:
                    return False

            if countdown_seconds is not None and screen_clock.getTime() >= countdown_seconds:
                return False
    except BaseException as error:
        failed = True
        release_failed_graphics_frames(error)
        raise
    finally:
        report = release_stimuli(stimuli)
        if not report.succeeded and not failed:
            raise ConditionResourceCleanupError(report)
