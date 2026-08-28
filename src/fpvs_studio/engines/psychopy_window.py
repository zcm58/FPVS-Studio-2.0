"""Window and fixation-stimulus helpers for the PsychoPy engine."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from importlib import import_module
from typing import Any

from fpvs_studio.core.run_spec import RunSpec

LOGGER = logging.getLogger(__name__)


def _detect_fullscreen_size_px(display_index: int) -> tuple[int, int] | None:
    """Return the selected Pyglet screen size without making it a launch gate."""

    try:
        try:
            display_module = import_module("pyglet.display")
        except ImportError:
            display_module = import_module("pyglet.canvas")
        display = display_module.get_display()
        screens = display.get_screens()
        screen = screens[display_index]
        width = int(screen.width)
        height = int(screen.height)
        if width <= 0 or height <= 0:
            raise ValueError("Pyglet returned non-positive screen dimensions.")
    except Exception as exc:
        LOGGER.warning(
            "Could not determine fullscreen size for display %d before PsychoPy "
            "window creation; PsychoPy will determine the actual fullscreen size: %s",
            display_index,
            exc,
        )
        return None
    return (width, height)


def build_window_kwargs(runtime_options: Mapping[str, object]) -> dict[str, object]:
    """Build PsychoPy window keyword arguments from runtime options."""

    fullscreen = bool(runtime_options.get("fullscreen", True))
    display_index = runtime_options.get("display_index")
    selected_display_index = display_index if isinstance(display_index, int) else 0
    window_kwargs: dict[str, object] = {
        "fullscr": fullscreen,
        "screen": selected_display_index,
        "allowGUI": not fullscreen,
        "waitBlanking": True,
        "color": "black",
        "units": "pix",
    }
    if fullscreen:
        fullscreen_size = _detect_fullscreen_size_px(selected_display_index)
        if fullscreen_size is not None:
            window_kwargs["size"] = list(fullscreen_size)
    else:
        windowed_size = runtime_options.get("windowed_size_px", (1280, 720))
        if (
            isinstance(windowed_size, (tuple, list))
            and len(windowed_size) == 2
            and all(
                isinstance(value, int) and not isinstance(value, bool) and value > 0
                for value in windowed_size
            )
        ):
            window_kwargs["size"] = list(windowed_size)
        else:
            window_kwargs["size"] = [1280, 720]
    return window_kwargs


def build_refresh_probe_window_kwargs(
    runtime_options: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build a fullscreen PsychoPy window for an explicit refresh measurement."""

    probe_options = dict(runtime_options or {})
    probe_options["fullscreen"] = True
    window_kwargs = build_window_kwargs(probe_options)
    window_kwargs["checkTiming"] = False
    return window_kwargs


def create_fixation_stim(
    *,
    visual: Any,
    window: Any,
    run_spec: RunSpec,
    color: str | None = None,
) -> Any:
    """Create the fixation cross stimulus for one run."""

    return visual.ShapeStim(
        window,
        vertices=(
            (0, -(run_spec.fixation.cross_size_px // 2)),
            (0, run_spec.fixation.cross_size_px // 2),
            (0, 0),
            (-(run_spec.fixation.cross_size_px // 2), 0),
            (run_spec.fixation.cross_size_px // 2, 0),
        ),
        closeShape=False,
        lineWidth=run_spec.fixation.line_width_px,
        lineColor=color or run_spec.fixation.default_color,
        fillColor=None,
        autoLog=False,
    )
