"""Native Windows LPT trigger output through an already running InpOut driver."""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from typing import Protocol

from fpvs_studio.core.trigger_codes import validate_event_trigger_code
from fpvs_studio.triggers.base import TriggerBackend


class ParallelPortError(RuntimeError):
    """Native LPT initialization, trigger output or reset failed."""


class ParallelPortDriverUnavailableError(ParallelPortError):
    """The selected parallel transport cannot access its required driver."""


class ParallelDriver(Protocol):
    """Installed-driver boundary, injectable without touching hardware in tests."""

    def connect(self) -> None: ...
    def write(self, address: int, code: int) -> None: ...
    def close(self) -> None: ...


class ParallelPortBackend(TriggerBackend):
    """Write one byte at the flip and clear it with a connection-owned worker.

    Both the high pulse and subsequent low interval last at least pulse_width_ms.
    Sends never sleep, retry or queue. Software timing does not prove EEG receipt.
    """

    def __init__(
        self, address: int, *, pulse_width_ms: int = 10,
        driver: ParallelDriver | None = None,
    ) -> None:
        if type(address) is not int or not 1 <= address <= 65535:
            raise ValueError("Parallel-port address must be an integer from 1 to 65535.")
        if type(pulse_width_ms) is not int or not 1 <= pulse_width_ms <= 1000:
            raise ValueError("Parallel-port pulse width must be an integer from 1 to 1000 ms.")
        self._address = address
        self._pulse_s = pulse_width_ms / 1000.0
        self._injected_driver = driver
        self._driver: ParallelDriver | None = None
        self._condition = threading.Condition()
        self._worker: threading.Thread | None = None
        self._reset_at: float | None = None
        self._ready_at = 0.0
        self._stopping = False
        self._failure: ParallelPortError | None = None

    @property
    def backend_name(self) -> str:
        return "brainproducts_parallel"

    @property
    def emits_hardware_triggers(self) -> bool:
        return True

    @property
    def emits_external_markers(self) -> bool:
        return True

    def connect(self) -> None:
        with self._condition:
            if self._driver is not None:
                self._raise_failure()
                return
            driver = self._injected_driver if self._injected_driver is not None else _InpOutDriver()
            try:
                driver.connect()
                self._write(driver, 0, action="initialize zero idle")
                self._driver = driver
                self._failure = None
                self._stopping = False
                self._reset_at = None
                self._ready_at = time.monotonic() + self._pulse_s
                self._worker = threading.Thread(
                    target=self._reset_loop, name="FPVS parallel-port reset", daemon=True,
                )
                self._worker.start()
            except Exception as exc:
                self._driver = None
                self._worker = None
                try:
                    driver.close()
                except Exception as close_exc:
                    raise ParallelPortError(
                        f"Unable to initialize parallel-port output: {exc}. "
                        f"Closing the driver also failed: {close_exc}"
                    ) from exc
                raise ParallelPortError(
                    f"Unable to initialize parallel-port output: {exc}"
                ) from exc
            self._wait_until_ready()

    def send(self, code: int) -> None:
        self.send_trigger(code)

    def send_trigger(
        self, code: int, *, frame_index: int | None = None,
        label: str | None = None, time_s: float | None = None,
    ) -> None:
        self.send_prevalidated_trigger(
            validate_event_trigger_code(code), frame_index=frame_index, label=label, time_s=time_s,
        )

    def send_prevalidated_trigger(
        self, code: int, *, frame_index: int | None = None,
        label: str | None = None, time_s: float | None = None,
    ) -> None:
        """Write synchronously once; reject overlap instead of delaying a marker."""

        del frame_index, label, time_s
        with self._condition:
            driver = self._require_driver()
            self._raise_failure()
            if self._stopping:
                raise ParallelPortError("Parallel-port backend is closing.")
            self._require_worker()
            if self._reset_at is not None:
                raise ParallelPortError("Parallel-port pulse overlaps the previous event.")
            if time.monotonic() < self._ready_at:
                raise ParallelPortError(
                    "Parallel-port low interval is shorter than the pulse width."
                )
            try:
                self._write(driver, code, action="send trigger")
            except ParallelPortError as exc:
                self._failure = exc
                raise
            self._reset_at = time.monotonic() + self._pulse_s
            self._condition.notify_all()

    def reset(self) -> None:
        """Drain a pending pulse and establish zero idle outside presentation."""

        with self._condition:
            driver = self._require_driver()
            self._raise_failure()
            self._require_worker()
            deadline = time.monotonic() + self._pulse_s + 1
            while self._reset_at is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._failure = ParallelPortError("Parallel-port reset worker did not finish.")
                    raise self._failure
                self._condition.wait(timeout=remaining)
                self._raise_failure()
                self._require_worker()
            try:
                self._write(driver, 0, action="reset trigger lines")
            except ParallelPortError as exc:
                self._failure = exc
                raise
            self._ready_at = time.monotonic() + self._pulse_s
            self._wait_until_ready()

    def close(self) -> None:
        """Stop the worker, attempt zero idle and release the driver despite errors."""

        with self._condition:
            if self._driver is None:
                return
        error: Exception | None = None
        try:
            self.reset()
        except Exception as exc:
            error = exc
        with self._condition:
            self._stopping = True
            self._condition.notify_all()
            worker = self._worker
        if worker is not None:
            try:
                worker.join(timeout=1)
                if worker.is_alive():
                    raise ParallelPortError("Parallel-port reset worker did not stop.")
            except Exception as exc:
                if error is None:
                    error = exc
        with self._condition:
            driver = self._driver
            self._driver = None
            self._worker = None
            self._reset_at = None
        if driver is not None:
            try:
                self._write(driver, 0, action="clear trigger lines during close")
            except Exception as exc:
                if error is None:
                    error = exc
            try:
                driver.close()
            except Exception as exc:
                if error is None:
                    error = ParallelPortError(f"Unable to close the parallel-port driver: {exc}")
        if error is not None:
            raise error

    def _reset_loop(self) -> None:
        with self._condition:
            while not self._stopping:
                if self._reset_at is None:
                    self._condition.wait()
                    continue
                remaining = self._reset_at - time.monotonic()
                if remaining > 0:
                    self._condition.wait(timeout=remaining)
                    continue
                try:
                    self._write(self._require_driver(), 0, action="reset trigger lines")
                except ParallelPortError as exc:
                    self._failure = exc
                self._reset_at = None
                self._ready_at = time.monotonic() + self._pulse_s
                self._condition.notify_all()

    def _wait_until_ready(self) -> None:
        while (remaining := self._ready_at - time.monotonic()) > 0:
            self._condition.wait(timeout=remaining)
            self._raise_failure()

    def _raise_failure(self) -> None:
        if self._failure is not None:
            raise self._failure

    def _require_driver(self) -> ParallelDriver:
        if self._driver is None:
            raise ParallelPortError("Parallel-port backend is not connected.")
        return self._driver

    def _require_worker(self) -> None:
        if self._worker is None or not self._worker.is_alive():
            self._failure = ParallelPortError("Parallel-port reset worker has stopped.")
            raise self._failure

    def _write(self, driver: ParallelDriver, code: int, *, action: str) -> None:
        try:
            driver.write(self._address, code)
        except Exception as exc:
            raise ParallelPortError(
                f"Unable to {action} code {code} at LPT address 0x{self._address:04X}: {exc}"
            ) from exc


class _InpOutDriver:
    """Open an existing InpOut device directly, avoiding DLL auto-install/start.

    InpOut32 1.5.0.1's public Out32 protocol uses IOCTL 0x9C402008 with a
    three-byte little-endian address/value payload. Source: Highrez InpOut32,
    inpout32drv.cpp and hwinterfacedrv.h (MIT), https://www.highrez.co.uk/downloads/inpout32/.
    Unlike its void Out32 wrapper, DeviceIoControl reports failed writes.
    """

    def __init__(self) -> None:
        self._api: ctypes.WinDLL | None = None
        self._handle: int | None = None

    def connect(self) -> None:
        if sys.platform != "win32":
            raise ParallelPortError("Native parallel-port output requires Windows.")
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.GetCurrentProcess.argtypes = []
        api.GetCurrentProcess.restype = ctypes.c_void_p
        api.IsWow64Process.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
        api.IsWow64Process.restype = ctypes.c_int
        api.CreateFileW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ]
        api.CreateFileW.restype = ctypes.c_void_p
        api.DeviceIoControl.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
            ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p,
        ]
        api.DeviceIoControl.restype = ctypes.c_int
        api.CloseHandle.argtypes = [ctypes.c_void_p]
        api.CloseHandle.restype = ctypes.c_int
        is_64 = ctypes.sizeof(ctypes.c_void_p) == 8
        if not is_64:
            wow64 = ctypes.c_int()
            if not api.IsWow64Process(api.GetCurrentProcess(), ctypes.byref(wow64)):
                raise ParallelPortError("Unable to determine the Windows driver architecture.")
            is_64 = bool(wow64.value)
        device = r"\\.\inpoutx64" if is_64 else r"\\.\inpout32"
        handle = api.CreateFileW(device, 0xC0000000, 0, None, 3, 0x80, None)
        if handle in (None, ctypes.c_void_p(-1).value):
            raise ParallelPortDriverUnavailableError(
                "An already installed, running InpOut driver is required for native LPT output "
                f"(Windows error {ctypes.get_last_error()}). "
                "Studio does not install or start kernel drivers. Select TriggerBox/Plus when "
                "using the USB interface."
            )
        self._api = api
        self._handle = handle

    def write(self, address: int, code: int) -> None:
        if self._api is None or self._handle is None:
            raise ParallelPortError("The InpOut driver device is not open.")
        payload = ctypes.create_string_buffer(address.to_bytes(2, "little") + bytes([code]), 3)
        returned = ctypes.c_uint32()
        if not self._api.DeviceIoControl(
            self._handle, 0x9C402008, payload, 3, None, 0, ctypes.byref(returned), None,
        ):
            raise ParallelPortError(
                f"InpOut port write failed (Windows error {ctypes.get_last_error()})."
            )

    def close(self) -> None:
        handle, self._handle = self._handle, None
        api, self._api = self._api, None
        if api is not None and handle is not None and not api.CloseHandle(handle):
            raise ParallelPortError(
                f"Closing InpOut failed (Windows error {ctypes.get_last_error()})."
            )
