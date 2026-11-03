"""Per-window protection for PsychoPy's macOS display-link synchronization."""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable
from importlib import import_module
from numbers import Integral
from typing import Any

DISPLAY_LINK_TIMEOUT_SECONDS = 1.0
LOGGER = logging.getLogger(__name__)


def prepare_macos_fullscreen_presentation(
) -> tuple[Callable[[], None], Callable[[], None]] | None:
    """Prepare activation and restoration before changing app presentation options.

    The caller owns closing the window before restoring options, including when
    activation fails. Pyglet's native close itself resets presentation options.
    """
    if sys.platform != "darwin":
        return None
    appkit = import_module("AppKit")
    application = appkit.NSApplication.sharedApplication()
    previous = application.presentationOptions()
    restored = False

    def restore() -> None:
        nonlocal restored
        if not restored:
            application.setPresentationOptions_(previous)
            restored = True

    def activate() -> None:
        application.setPresentationOptions_(
            appkit.NSApplicationPresentationHideDock | appkit.NSApplicationPresentationHideMenuBar
        )
        application.activateIgnoringOtherApps_(True)

    return activate, restore


def use_macos_framebuffer_pixels(window: Any) -> None:
    """Use physical pixels after PsychoPy has realized the Retina framebuffer.

    Pyglet must create the window with ``useRetina=True`` to discover its backing
    size. PsychoPy's legacy coordinate conversions also use that flag to double
    pixel geometry, even though ``window.size`` already contains backing pixels.
    Change only that coordinate flag before constructing any stimuli. Native
    backing storage, viewport, client size and content scale remain unchanged.
    """
    if sys.platform != "darwin":
        return
    try:
        framebuffer = tuple(window.frameBufferSize)
        viewport_size = tuple(window.size)
        valid = (
            len(framebuffer) == 2
            and all(isinstance(value, Integral) and not isinstance(value, bool) and int(value) > 0
                    for value in framebuffer)
            and viewport_size == framebuffer
        )
    except (AttributeError, TypeError, ValueError):
        valid = False
    if not valid:
        raise RuntimeError(
            "PsychoPy could not confirm the Mac display's backing pixels. "
            "Window and framebuffer dimensions must match before selecting pixel coordinates."
        )
    window.useRetina = False


def create_macos_test_keyboard(keyboard_module: Any) -> Any:
    """Use foreground input for secondary Mac Test/Pilot, never a HID fallback."""
    keyboard = keyboard_module.Keyboard(backend="event")
    if keyboard.getBackend() != "event":
        raise RuntimeError("Mac Test/Pilot requires the foreground-window keyboard backend.")
    device = getattr(keyboard, "device", None)
    get_event_keys = getattr(getattr(keyboard_module, "event", None), "getKeys", None)
    if device is None or not callable(get_event_keys) or not all(callable(value) for value in (
        getattr(device, "dispatchMessages", None),
        getattr(device, "parseMessage", None), getattr(device, "receiveMessage", None),
    )):
        raise RuntimeError(
            "Mac Test/Pilot requires the foreground-window keyboard event interface."
        )

    def dispatch_foreground_messages() -> None:
        # PsychoPy's event dispatcher passes a timestamped pair as the key name
        # and consumes only the first event. Preserve its parser, focus guard and
        # response filtering, while delivering every foreground key as a string.
        for name in get_event_keys(modifiers=False, timeStamped=False):
            response = device.parseMessage(name)
            if response is not None:
                device.receiveMessage(response)

    device.dispatchMessages = dispatch_foreground_messages
    LOGGER.info("Mac Test/Pilot keyboard uses foreground-window events (not acquisition timing)")
    return keyboard


class _BoundedDisplayLink:
    """Keep the native callback target while bounding its Python polling loop."""

    def __init__(self, handler: Any) -> None:
        self._handler = handler
        self._deadline: float | None = None

    @property
    def frameLock(self) -> Any:
        locked = self._handler.frameLock
        if not locked:
            self._deadline = None
            return locked
        if self._deadline is not None and time.monotonic() >= self._deadline:
            raise RuntimeError(
                "macOS display refresh callback did not arrive within 1 second. "
                "Presentation was stopped because frame synchronization could not be verified."
            )
        return locked

    @frameLock.setter
    def frameLock(self, value: Any) -> None:
        self._deadline = time.monotonic() + DISPLAY_LINK_TIMEOUT_SECONDS if value else None
        self._handler.frameLock = value

    def __getattr__(self, name: str) -> Any:
        return getattr(self._handler, name)


def guard_macos_display_link(window: Any) -> None:
    """Fail closed on a lost callback without bypassing native frame synchronization.

    Install after constructing a ``checkTiming=False`` window and before its first
    flip. The display link retains its original Objective-C callback target; only
    the backend's polling reference is wrapped. Windows and Linux stay untouched.
    """
    if sys.platform != "darwin":
        return
    backend = getattr(window, "backend", None)
    handler = getattr(backend, "refreshEventHandlerMacOS", None)
    if backend is None or handler is None or not hasattr(handler, "frameLock"):
        raise RuntimeError(
            "macOS display refresh callback support is unavailable. "
            "Presentation cannot start without verified frame synchronization."
        )
    if not isinstance(handler, _BoundedDisplayLink):
        backend.refreshEventHandlerMacOS = _BoundedDisplayLink(handler)
