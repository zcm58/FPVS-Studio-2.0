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

    @abstractmethod
    def reset(self) -> None:
        """Reset the trigger line if supported."""

    @abstractmethod
    def close(self) -> None:
        """Release backend resources."""
