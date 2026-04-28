"""Serial trigger backend scaffold for future lab hardware integration. It reserves the
runtime-facing adapter shape for configured serial ports while keeping serial specifics
out of core contracts and GUI code. This module owns hardware hookup scaffolding only;
trigger scheduling and export records remain in compiler and runtime."""

from __future__ import annotations

from fpvs_studio.triggers.base import TriggerBackend


class SerialBackend(TriggerBackend):
    """Placeholder for lab-specific serial trigger implementation."""

    def __init__(self, port: str, baudrate: int) -> None:
        self._port = port
        self._baudrate = baudrate

    def connect(self) -> None:
        raise NotImplementedError(
            "Serial trigger backend wiring is not implemented in this scaffold yet."
        )

    def send_trigger(
        self,
        code: int,
        *,
        frame_index: int | None = None,
        label: str | None = None,
        time_s: float | None = None,
    ) -> None:
        raise NotImplementedError(
            "Serial trigger emission is not implemented in this scaffold yet."
        )

    def reset(self) -> None:
        raise NotImplementedError("Serial trigger reset is not implemented in this scaffold yet.")

    def close(self) -> None:
        return None
