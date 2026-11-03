"""Per-window protection for PsychoPy's macOS display-link synchronization."""

from __future__ import annotations

import logging
import sys
import time
from typing import Any

DISPLAY_LINK_TIMEOUT_SECONDS = 1.0
LOGGER = logging.getLogger(__name__)


def create_macos_test_keyboard(keyboard_module: Any) -> Any:
    """Use foreground input for secondary Mac Test/Pilot, never a HID fallback."""
    keyboard = keyboard_module.Keyboard(backend="event")
    if keyboard.getBackend() != "event":
        raise RuntimeError("Mac Test/Pilot requires the foreground-window keyboard backend.")
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
