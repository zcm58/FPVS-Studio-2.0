"""Window and fixation-stimulus helpers for the PsychoPy engine."""

from __future__ import annotations

import logging
import sys
from collections.abc import Mapping
from importlib import import_module
from typing import Any

from fpvs_studio.core.run_spec import RunSpec

LOGGER = logging.getLogger(__name__)


def close_presentation_window(window: Any) -> None:
    """Restore the pointer while the native handle still exists, then close it."""

    cursor_error: Exception | None = None
    try:
        # PsychoPy restores visibility after backend.close(), which can fail
        # first (for example while restoring gamma). Do not leave its hidden
        # fullscreen pointer state behind when that teardown is interrupted.
        window.mouseVisible = True
    except Exception as error:
        cursor_error = error
        LOGGER.exception("Presentation pointer restoration failed before window close.")
    # A cursor error must never prevent native window cleanup. If both fail,
    # retain the close error; the cursor error is recorded above.
    window.close()
    if cursor_error is not None:
        raise cursor_error


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
    if sys.platform == "darwin":
        # Runtime already requires a bounded native/fullscreen verification. The
        # constructor's extra getActualFrameRate loop cannot be canceled or timed.
        window_kwargs.update({"useRetina": True, "winType": "pyglet", "checkTiming": False})
    if fullscreen:
        fullscreen_size = _detect_fullscreen_size_px(selected_display_index)
        if sys.platform == "darwin":
            if fullscreen_size is None:
                raise RuntimeError(
                    "PsychoPy could not determine the Mac presentation display size."
                )
            # Pyglet's Cocoa fullscreen captures the display at shielding level.
            # Use the same display-sized surface without exclusive display capture;
            # macOS must remain able to switch applications during a local test.
            window_kwargs.update({"fullscr": False, "allowGUI": False, "pos": [0, 0]})
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


def validate_macos_framebuffer(window: Any, run_spec: RunSpec) -> None:
    """Reject a Retina backing-size mismatch before uploading condition resources."""

    if sys.platform != "darwin":
        return
    try:
        size = tuple(int(value) for value in window.frameBufferSize)
    except (AttributeError, TypeError, ValueError) as exc:
        raise RuntimeError("PsychoPy could not confirm the Mac display's backing pixels.") from exc
    expected = (run_spec.display.screen_width_px, run_spec.display.screen_height_px)
    if size != expected:
        raise RuntimeError(
            f"Mac presentation uses {size} backing pixels; the local test was calibrated "
            f"for {expected}. Check the primary display and restart the local test."
        )


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
