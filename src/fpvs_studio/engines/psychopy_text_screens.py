"""Text-screen rendering helper for the PsychoPy engine."""

from __future__ import annotations

from typing import Any

from fpvs_studio.engines.psychopy_graphics_lifetime import release_failed_graphics_frames
from fpvs_studio.engines.psychopy_stimuli import (
    ConditionResourceCleanupError,
    release_stimuli,
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
            height=36,
            pos=(0, 140),
            wrapWidth=1200,
            color="white",
            autoLog=False,
        )
        if body:
            stimuli["body"] = visual.TextStim(
                window,
                text=body,
                height=28,
                pos=(0, 10),
                wrapWidth=1200,
                color="white",
                autoLog=False,
            )
        footer = footer_text()
        stimuli["footer"] = visual.TextStim(
            window,
            text=footer,
            height=24,
            pos=(0, -220),
            wrapWidth=1200,
            color="white",
            autoLog=False,
        )
        while True:
            if is_aborted():
                return True
            next_footer = footer_text() if countdown_seconds is not None else footer
            if next_footer != footer:
                stimuli["footer"].text = next_footer
                footer = next_footer
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
