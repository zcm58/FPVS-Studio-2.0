"""Completion ownership for pyserial's nonblocking Windows overlapped writes.

pyserial 3.x returns the requested length for ERROR_IO_PENDING. Its single
OVERLAPPED must not be reused, or its payload released, until native completion.
This helper never waits; the TriggerBox and BioSemi backends own polling and deadlines.
"""

from __future__ import annotations

import ctypes
import importlib
import sys
from typing import Any

# A broken driver may never acknowledge cancellation. Keep its connection,
# OVERLAPPED, event and payload alive until process exit rather than free storage
# still owned by the kernel. Only this exceptional path requires Studio restart.
_RETAINED_WRITES: list[WindowsSerialWrite] = []


class WindowsSerialWrite:
    """Own at most one native write, including its exact immutable bytes buffer."""

    def __init__(self, connection: Any, win32: Any) -> None:
        self._connection = connection
        self._win32 = win32
        self._payload: bytes | None = None

    @property
    def pending(self) -> bool:
        return self._payload is not None

    def write(self, payload: bytes) -> int:
        if self.pending:
            raise RuntimeError("The previous Windows serial write is still pending.")
        self._payload = payload
        try:
            count = self._connection.write(payload)
        except Exception:
            # pyserial raises only for immediate WriteFile submission failures.
            self._payload = None
            raise
        if count != len(payload):
            self._payload = None
        return int(count)

    def poll(self) -> bool:
        """Observe native completion without waiting or consuming serial input."""

        if self._payload is None:
            return True
        count = self._win32.DWORD()
        completed = self._win32.GetOverlappedResult(
            self._connection._port_handle,
            ctypes.byref(self._connection._overlapped_write),
            ctypes.byref(count),
            False,
        )
        if not completed:
            error = self._win32.GetLastError()
            if error in (self._win32.ERROR_IO_PENDING, self._win32.ERROR_IO_INCOMPLETE):
                return False
            # Invalid handle/arguments reject the query itself, so they cannot
            # establish that Windows has finished using the operation storage.
            if error in (6, 87):
                raise ctypes.WinError(error)
            self._payload = None
            raise ctypes.WinError(error)
        expected = len(self._payload)
        self._payload = None
        if count.value != expected:
            raise OSError(
                f"Windows serial write completed with {count.value} bytes, expected {expected}."
            )
        return True

    def cancel(self) -> None:
        """Request cancellation; ownership remains until poll observes completion."""

        if self.pending and not self._win32.CancelIoEx(
            self._connection._port_handle,
            ctypes.byref(self._connection._overlapped_write),
        ):
            error = self._win32.GetLastError()
            # ERROR_NOT_FOUND means the write may already have completed.
            if error != 1168:
                raise ctypes.WinError(error)

    def retain_until_exit(self) -> bool:
        if self not in _RETAINED_WRITES:
            _RETAINED_WRITES.append(self)
            return True
        return False


def windows_serial_write(connection: Any) -> WindowsSerialWrite | None:
    """Select native completion only for the real Windows pyserial transport."""

    if sys.platform != "win32":
        return None
    native = importlib.import_module("serial.serialwin32")
    if not isinstance(connection, native.Serial):
        return None
    return WindowsSerialWrite(connection, native.win32)
