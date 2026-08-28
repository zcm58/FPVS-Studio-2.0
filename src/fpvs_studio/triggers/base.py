"""Abstract trigger backend contract used at runtime. It defines the minimal
send/open/close behavior that runtime and engines can depend on without embedding
serial-library details in core contracts. The module owns hardware interface shape only;
trigger event planning and logging stay in compiler and runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod


class TriggerBackend(ABC):
    """Minimal trigger backend interface."""

    @abstractmethod
    def connect(self) -> None:
        """Open or initialize backend resources."""

    @abstractmethod
    def send_trigger(
        self,
        code: int,
        *,
        frame_index: int | None = None,
        label: str | None = None,
        time_s: float | None = None,
    ) -> None:
        """Emit a trigger code."""

    def send_prevalidated_trigger(
        self,
        code: int,
        *,
        frame_index: int | None = None,
        label: str | None = None,
        time_s: float | None = None,
    ) -> None:
        """Emit a marker whose payload was validated before timed playback.

        Backends may override this narrow hot-path method to avoid repeating validation
        in a display-flip callback. The default preserves compatibility for custom
        backends by delegating to :meth:`send_trigger`.
        """

        self.send_trigger(
            code,
            frame_index=frame_index,
            label=label,
            time_s=time_s,
        )

    @abstractmethod
    def reset(self) -> None:
        """Reset the trigger line if supported."""

    @abstractmethod
    def close(self) -> None:
        """Release backend resources."""
