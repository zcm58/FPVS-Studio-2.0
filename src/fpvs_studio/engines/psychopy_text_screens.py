"""Text-screen rendering helper for the PsychoPy engine."""

from __future__ import annotations

from typing import Any


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
) -> bool:
    """Render one transition-style text screen."""

    keyboard.clearEvents()
    screen_clock = core.Clock()

    while True:
        if is_aborted():
            return True

        footer = ""
        if continue_key is not None:
            footer = f"Press '{continue_key}' to continue. Press Escape to abort."
        elif countdown_seconds is not None:
            remaining = max(0.0, countdown_seconds - screen_clock.getTime())
            footer = f"Starting automatically in {remaining:0.1f} s. Press Escape to abort."
        else:
            footer = "Press Escape to abort."

        visual.TextStim(
            window,
            text=heading,
            height=36,
            pos=(0, 140),
            wrapWidth=1200,
            color="white",
            autoLog=False,
        ).draw()
        if body:
            visual.TextStim(
                window,
                text=body,
                height=28,
                pos=(0, 10),
                wrapWidth=1200,
                color="white",
                autoLog=False,
            ).draw()
        visual.TextStim(
            window,
            text=footer,
            height=24,
            pos=(0, -220),
            wrapWidth=1200,
            color="white",
            autoLog=False,
        ).draw()
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
