"""Serial trigger backend for BioSemi-compatible marker output."""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any

from fpvs_studio.core.trigger_codes import validate_event_trigger_code, validate_reset_trigger_code
from fpvs_studio.triggers.base import TriggerBackend


class SerialBackendError(RuntimeError):
    """Raised when BioSemi serial trigger output cannot be performed."""


class SerialBackend(TriggerBackend):
    """Write single-byte trigger markers to a configured serial port."""

    def __init__(
        self,
        port: str = "COM3",
        baudrate: int = 115200,
        *,
        pulse_width_ms: int = 10,
        reset_code: int | None = None,
        reset_delay_ms: int = 5,
        serial_module: ModuleType | Any | None = None,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._pulse_width_ms = pulse_width_ms
        self._reset_code = reset_code
        self._reset_delay_ms = reset_delay_ms
        self._serial_module = serial_module
        self._connection: Any | None = None

    def connect(self) -> None:
        if self._connection is not None:
            return
        serial_module = self._serial_module or _load_serial_module()
        try:
            self._connection = serial_module.Serial(
                port=self._port,
                baudrate=self._baudrate,
                bytesize=serial_module.EIGHTBITS,
                parity=serial_module.PARITY_NONE,
                stopbits=serial_module.STOPBITS_ONE,
                timeout=0,
                write_timeout=0,
                rtscts=False,
                dsrdtr=False,
                xonxoff=False,
            )
        except Exception as exc:
            raise SerialBackendError(
                f"Unable to open serial trigger port {self._port!r} at "
                f"{self._baudrate} baud: {exc}"
            ) from exc

    def send(self, code: int) -> None:
        """Emit one normal trigger event marker."""

        self.send_trigger(code)

    def send_trigger(
        self,
        code: int,
        *,
        frame_index: int | None = None,
        label: str | None = None,
        time_s: float | None = None,
    ) -> None:
        del frame_index, label, time_s
        self._write_marker(
            validate_event_trigger_code(code),
            action="send trigger",
        )

    def reset(self) -> None:
        if self._reset_code is None:
            return
        self._write_marker(
            validate_reset_trigger_code(self._reset_code),
            action="reset trigger line",
        )

    def close(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is not None:
            connection.close()

    def _write_marker(self, code: int, *, action: str) -> None:
        if self._connection is None:
            raise SerialBackendError("Serial trigger backend is not connected.")
        try:
            bytes_written = self._connection.write(bytes([code]))
        except Exception as exc:
            raise SerialBackendError(
                f"Unable to {action} code {code} on {self._port!r}: {exc}"
            ) from exc
        if bytes_written != 1:
            raise SerialBackendError(
                f"Unable to {action} code {code} on {self._port!r}: serial write "
                f"returned {bytes_written!r}, expected 1."
            )


def _load_serial_module() -> ModuleType:
    try:
        return importlib.import_module("serial")
    except ModuleNotFoundError as exc:
        raise SerialBackendError(
            "pyserial is required for serial trigger output but is not installed."
        ) from exc
