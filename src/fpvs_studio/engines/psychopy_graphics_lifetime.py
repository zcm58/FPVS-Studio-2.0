"""Keep Pyglet finalizers off foreign threads without changing frame playback.

Pyglet 1.4 uses a process-global current_context, although native OpenGL contexts
are thread-local. Its texture destructor can therefore call GL from Qt's thread
when Python collects a text-layout cycle there. Use Pyglet's existing deferred
deletion queues for foreign-thread and post-close finalizers. A later activation
of the live context (or another context sharing its object space) drains them.
"""

from __future__ import annotations

from threading import current_thread
from traceback import clear_frames
from typing import Any


def release_failed_graphics_frames(error: BaseException) -> None:
    """Drop partial constructor locals while still on the live graphics thread.

    A failed TextStim constructor can retain an unmanaged display-list id in its
    traceback's ``self``. Preserve the exception/stack locations, but release the
    completed frames' locals before the GUI receives it or the context closes.
    clear_frames deliberately leaves currently executing frames alone.
    """

    clear_frames(error.__traceback__)


class GraphicsLifetime:
    """Own one window's context and retain safe finalizers after window close."""

    def __init__(self, window: Any) -> None:
        self._owner = current_thread()
        self._retired = False
        backend = getattr(window, "backend", None)
        self._handle = getattr(backend, "winHandle", None)
        if self._handle is None:
            self._handle = getattr(window, "winHandle", None)
        context = getattr(self._handle, "context", None)
        if context is None:
            # Non-Pyglet backends and synthetic windows have no Pyglet finalizers.
            return
        object_space = getattr(context, "object_space", None)
        textures = getattr(object_space, "_doomed_textures", None)
        buffers = getattr(object_space, "_doomed_buffers", None)
        delete_texture = getattr(context, "delete_texture", None)
        delete_buffer = getattr(context, "delete_buffer", None)
        if (
            not isinstance(textures, list)
            or not isinstance(buffers, list)
            or not callable(delete_texture)
            or not callable(delete_buffer)
            or not callable(getattr(self._handle, "switch_to", None))
        ):
            raise RuntimeError("Pyglet's graphics cleanup interface is unsupported.")

        def guarded_delete_texture(texture_id: int) -> None:
            if not self._retired and current_thread() is self._owner:
                delete_texture(texture_id)
            else:
                # Pyglet itself uses atomic append/slice operations on these lists.
                textures.append(texture_id)

        def guarded_delete_buffer(buffer_id: int) -> None:
            if not self._retired and current_thread() is self._owner:
                delete_buffer(buffer_id)
            else:
                buffers.append(buffer_id)

        context.delete_texture = guarded_delete_texture
        context.delete_buffer = guarded_delete_buffer

    def assert_owner(self) -> None:
        if current_thread() is not self._owner:
            raise RuntimeError("PsychoPy graphics must be used on their presentation thread.")

    def activate(self) -> None:
        """Drain queued deletion at an untimed boundary, never inside a frame loop."""

        self.assert_owner()
        if self._retired:
            raise RuntimeError("The PsychoPy graphics context has already been closed.")
        switch_to = getattr(self._handle, "switch_to", None)
        if callable(switch_to):
            # Bypass PsychoPy's cached current-window check: even an already current
            # Pyglet context needs set_current() to drain deferred resource deletion.
            switch_to()

    def retire(self) -> None:
        """Keep late traceback/GC finalizers safe after the native window closes."""

        self.assert_owner()
        self._retired = True
        self._handle = None
