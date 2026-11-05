"""Own a framebuffer-drawn pointer for Windows Pyglet response screens.

Hardware cursor visibility does not establish that the participant sees a pointer.
Pyglet's drawable cursor is composited just before the native buffer swap, using its
existing pointer coordinates without changing task input handling.
"""

from __future__ import annotations

import logging
from importlib import import_module
from threading import current_thread
from typing import Any

LOGGER = logging.getLogger(__name__)
_CURSOR_SIZE = 32
_CURSOR_HOTSPOT = (1, 30)
_CURSOR_ROWS = (
    "X",
    "XX",
    "XWX",
    "XWWX",
    "XWWWX",
    "XWWWWX",
    "XWWWWWX",
    "XWWWWWWX",
    "XWWWWWWWX",
    "XWWWWWWWWX",
    "XWWWWWWWWWX",
    "XWWWWWWWWWWX",
    "XWWWWWWWWWWWX",
    "XWWWWWWWWWWWWX",
    "XWWWWWWWWWWWWWX",
    "XWWWWWWWWWWWWWWX",
    "XWWWWWWWXXXXXXXX",
    "XWWWXWWWX",
    "XWWX XWWWX",
    "XWX  XWWWX",
    "XX    XWWWX",
    "X     XWWWX",
    "       XWWWX",
    "        XWWX",
    "         XX",
)


def _cursor_rgba() -> bytes:
    """Return a fixed white arrow with a black outline, ordered top to bottom."""

    pixels = bytearray(_CURSOR_SIZE * _CURSOR_SIZE * 4)
    for y, row in enumerate(_CURSOR_ROWS, start=1):
        for x, color in enumerate(row, start=1):
            if color == " ":
                continue
            offset = (y * _CURSOR_SIZE + x) * 4
            pixels[offset:offset + 4] = (
                b"\xff\xff\xff\xff" if color == "W" else b"\x00\x00\x00\xff"
            )
    return bytes(pixels)


class TaskCursor:
    """Install one drawable cursor and release it on its presentation thread."""

    def __init__(self, window: Any) -> None:
        self._owner = current_thread()
        self._closed = False
        self._installation_attempted = False
        self._texture: Any = None
        self._handle: Any = getattr(window, "winHandle", None)
        if (
            self._handle is None
            or getattr(window, "winType", None) != "pyglet"
            or not callable(getattr(self._handle, "set_mouse_cursor", None))
            or not hasattr(self._handle, "_mouse_cursor")
        ):
            raise RuntimeError("Pyglet's drawable response-cursor interface is unavailable.")
        # Pyglet exposes a public setter but no corresponding cursor getter.
        self._previous_cursor = self._handle._mouse_cursor
        try:
            image_module = import_module("pyglet.image")
            window_module = import_module("pyglet.window")
            image = image_module.ImageData(
                _CURSOR_SIZE, _CURSOR_SIZE, "RGBA", _cursor_rgba(), pitch=-_CURSOR_SIZE * 4,
            )
            # Power-of-two dimensions produce an owned Texture, not a shared region.
            texture = image.get_texture()
            if getattr(texture, "owner", None) is not None:
                raise RuntimeError("Pyglet's owned response-cursor texture is unsupported.")
            self._texture = texture
            if (
                not isinstance(getattr(self._texture, "id", None), int)
                or self._texture.id <= 0
                or not callable(getattr(
                    getattr(self._texture, "_context", None), "delete_texture", None,
                ))
            ):
                raise RuntimeError("Pyglet's owned response-cursor texture is unsupported.")
            cursor = window_module.ImageMouseCursor(
                image, hot_x=_CURSOR_HOTSPOT[0], hot_y=_CURSOR_HOTSPOT[1],
            )
            if not cursor.drawable or cursor.texture is not self._texture:
                raise RuntimeError("Pyglet did not create a framebuffer-drawn response cursor.")
            self._installation_attempted = True
            self._handle.set_mouse_cursor(cursor)
        except BaseException:
            try:
                self.close()
            except Exception:
                LOGGER.exception("Response-cursor setup rollback also failed.")
            raise

    def close(self) -> None:
        """Attempt cursor restoration and texture deletion independently, once."""

        if current_thread() is not self._owner:
            raise RuntimeError("Response cursors must be released on their presentation thread.")
        if self._closed:
            return
        self._closed = True
        cleanup_error: Exception | None = None
        if self._installation_attempted:
            try:
                self._handle.set_mouse_cursor(self._previous_cursor)
            except Exception as error:
                cleanup_error = error
                LOGGER.exception("Response-cursor restoration failed.")
        if self._texture is not None:
            try:
                texture_id = self._texture.id
                if texture_id:
                    # Pyglet 1.4 Texture has no delete() method. Use its owning
                    # context's deletion API, guarded by GraphicsLifetime, then
                    # disarm the Texture finalizer against a later reused GL name.
                    self._texture._context.delete_texture(texture_id)
                    self._texture.id = 0
            except Exception as error:
                cleanup_error = cleanup_error or error
                LOGGER.exception("Response-cursor texture deletion failed.")
        self._texture = None
        if cleanup_error is not None:
            raise cleanup_error


def create_task_cursor(window: Any) -> TaskCursor:
    """Create the required software response pointer on the active graphics thread."""

    return TaskCursor(window)
