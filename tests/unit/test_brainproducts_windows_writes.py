"""Real pyserial Windows write/close paths with intercepted WinAPI, never COM I/O."""

from __future__ import annotations

import ctypes
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from fpvs_studio.triggers import brainproducts_backend as backend_module
from fpvs_studio.triggers import brainproducts_windows as windows_module
from fpvs_studio.triggers.brainproducts_backend import (
    BrainProductsTriggerBoxBackend,
    BrainProductsTriggerBoxError,
)

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Native pyserial Windows path")


class _NativeDriver:
    def __init__(self, monkeypatch):
        import serial
        from serial import serialwin32

        self.win32 = serialwin32.win32
        self.changed = threading.Condition()
        self.local = threading.local()
        self.writes = []
        self.blocked = set()
        self.errors = {}
        self.query_error = None
        self.short = set()
        self.reused_pending = False
        self.cancelled = False
        self.cancel_completes = True
        self.closed = False
        self.port = serialwin32.Serial(port=None, timeout=0, write_timeout=0)
        self.port._port_handle = 123456
        self.port._overlapped_read = None
        self.port._overlapped_write = self.win32.OVERLAPPED()
        self.port._overlapped_write.hEvent = 234567
        self.port._orgTimeouts = self.win32.COMMTIMEOUTS()
        self.port.is_open = True
        self.module = SimpleNamespace(
            Serial=lambda **kwargs: self.port, EIGHTBITS=serial.EIGHTBITS,
            PARITY_NONE=serial.PARITY_NONE, STOPBITS_ONE=serial.STOPBITS_ONE,
        )
        monkeypatch.setattr(self.win32, "CreateFile", self._forbid_open)
        monkeypatch.setattr(self.win32, "WriteFile", self._write)
        monkeypatch.setattr(self.win32, "GetLastError", lambda: getattr(self.local, "error", 0))
        monkeypatch.setattr(self.win32, "GetOverlappedResult", self._result)
        monkeypatch.setattr(self.win32, "CancelIoEx", self._cancel)
        monkeypatch.setattr(self.win32, "SetCommTimeouts", lambda *args: True)
        monkeypatch.setattr(self.win32, "CloseHandle", self._close)

    @staticmethod
    def _forbid_open(*args):
        raise AssertionError("These tests must never open a native handle")

    def _write(self, handle, payload, size, count, overlapped):
        with self.changed:
            self.reused_pending |= len(self.writes) in self.blocked
            self.writes.append((bytes(payload), time.monotonic()))
            index = len(self.writes)
            self.changed.notify_all()
        ctypes.cast(count, ctypes.POINTER(self.win32.DWORD))[0] = size
        self.local.error = self.win32.ERROR_IO_PENDING if index in self.blocked else 0
        return index not in self.blocked

    def _result(self, handle, overlapped, count, wait):
        assert wait is False, "No native blocking wait is allowed"
        if self.query_error is not None:
            self.local.error = self.query_error
            return False
        index = len(self.writes)
        if index in self.blocked:
            self.local.error = self.win32.ERROR_IO_INCOMPLETE
            return False
        if index in self.errors:
            self.local.error = self.errors[index]
            return False
        ctypes.cast(count, ctypes.POINTER(self.win32.DWORD))[0] = 0 if index in self.short else 1
        self.local.error = 0
        return True

    def _cancel(self, handle, overlapped):
        self.cancelled = True
        if self.cancel_completes:
            self.blocked.discard(len(self.writes))
            self.errors[len(self.writes)] = self.win32.ERROR_OPERATION_ABORTED
        return True

    def _close(self, handle):
        if handle == 123456:
            self.closed = True
        return True

    def wait_for_writes(self, count):
        with self.changed:
            assert self.changed.wait_for(lambda: len(self.writes) >= count, timeout=2)


@pytest.fixture
def native_driver(monkeypatch):
    driver = _NativeDriver(monkeypatch)
    yield driver
    # Synthetic handles must never reach native finalizers after patches are undone.
    driver.port.is_open = False
    driver.port._port_handle = None


def test_pending_event_completes_before_pulse_timer_and_reset(native_driver):
    driver = native_driver
    driver.blocked.add(2)
    backend = BrainProductsTriggerBoxBackend("COM4", pulse_width_ms=5, serial_module=driver.module)
    backend.connect()
    try:
        backend.send(55)
        time.sleep(.02)
        assert len(driver.writes) == 2, "Reset must not overwrite a pending event"
        assert not driver.reused_pending
        completed_at = time.monotonic()
        driver.blocked.remove(2)
        driver.wait_for_writes(3)
        assert driver.writes[2][1] - completed_at >= .005
        backend.reset()
    finally:
        driver.blocked.clear()
        backend.close()


def test_native_write_completion_error_is_retained_and_aborts(native_driver):
    driver = native_driver
    driver.blocked.add(2)
    backend = BrainProductsTriggerBoxBackend("COM4", pulse_width_ms=5, serial_module=driver.module)
    backend.connect()
    backend.send(55)
    driver.errors[2] = 1117
    driver.blocked.remove(2)
    try:
        with pytest.raises(BrainProductsTriggerBoxError, match="1117"):
            backend.reset()
        with pytest.raises(BrainProductsTriggerBoxError, match="1117"):
            backend.send(55)
    finally:
        with pytest.raises(BrainProductsTriggerBoxError, match="1117"):
            backend.close()
    assert driver.closed
    assert not driver.reused_pending


def _run_in_thread(action):
    errors = []

    def run():
        try:
            action()
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, errors


def test_connect_waits_for_initial_zero_completion(native_driver):
    driver = native_driver
    driver.blocked.add(1)
    backend = BrainProductsTriggerBoxBackend("COM4", serial_module=driver.module)
    thread, errors = _run_in_thread(backend.connect)
    driver.wait_for_writes(1)
    try:
        time.sleep(.02)
        assert thread.is_alive()
        assert backend._worker is None
    finally:
        driver.blocked.clear()
        thread.join(timeout=2)
        backend.close()
    assert not thread.is_alive()
    assert not errors


def test_connect_preserves_native_initial_zero_failure_cause(native_driver):
    driver = native_driver
    driver.errors[1] = 1117
    backend = BrainProductsTriggerBoxBackend("COM4", serial_module=driver.module)
    with pytest.raises(BrainProductsTriggerBoxError, match="1117") as failure:
        backend.connect()
    assert isinstance(failure.value.__cause__, OSError)
    assert failure.value.__cause__.winerror == 1117
    assert driver.closed


def test_pending_zero_prevents_next_event_and_starts_low_interval_on_completion(native_driver):
    driver = native_driver
    driver.blocked.add(3)
    backend = BrainProductsTriggerBoxBackend("COM4", pulse_width_ms=30, serial_module=driver.module)
    backend.connect()
    try:
        backend.send(55)
        driver.wait_for_writes(3)
        time.sleep(.04)
        with pytest.raises(BrainProductsTriggerBoxError, match="overlaps"):
            backend.send(55)
        driver.blocked.remove(3)
        with backend._condition:
            assert backend._condition.wait_for(lambda: not backend._pulse_active, timeout=2)
            with pytest.raises(BrainProductsTriggerBoxError, match="low interval"):
                backend.send(55)
        backend.reset()
        backend.send(55)
    finally:
        driver.blocked.clear()
        backend.close()
    assert not driver.reused_pending


def test_close_drains_final_zero_before_releasing_handle(native_driver):
    driver = native_driver
    driver.blocked.add(3)
    backend = BrainProductsTriggerBoxBackend("COM4", serial_module=driver.module)
    backend.connect()
    thread, errors = _run_in_thread(backend.close)
    driver.wait_for_writes(3)
    try:
        time.sleep(.02)
        assert thread.is_alive()
        assert not driver.closed
        assert backend._native_write._payload == b"\x00"
    finally:
        driver.blocked.clear()
        thread.join(timeout=2)
    assert not thread.is_alive()
    assert not errors
    assert driver.closed
    assert not driver.cancelled


def test_close_surfaces_final_zero_completion_failure(native_driver):
    driver = native_driver
    driver.errors[3] = 1117
    backend = BrainProductsTriggerBoxBackend("COM4", serial_module=driver.module)
    backend.connect()
    with pytest.raises(BrainProductsTriggerBoxError, match="1117"):
        backend.close()
    assert driver.closed


def test_native_short_completion_rejects_event(native_driver):
    driver = native_driver
    driver.short.add(2)
    backend = BrainProductsTriggerBoxBackend("COM4", serial_module=driver.module)
    backend.connect()
    with pytest.raises(BrainProductsTriggerBoxError, match="completed with 0 bytes"):
        backend.send(55)
    with pytest.raises(BrainProductsTriggerBoxError, match="completed with 0 bytes"):
        backend.close()
    assert driver.closed


@pytest.mark.parametrize("cancel_completes", [True, False])
def test_timed_out_native_write_cancellation_preserves_storage_until_terminal(
    native_driver, monkeypatch, cancel_completes,
):
    driver = native_driver
    driver.blocked.add(2)
    driver.cancel_completes = cancel_completes
    retained = []
    monkeypatch.setattr(backend_module, "_WRITE_TIMEOUT_S", .04)
    monkeypatch.setattr(windows_module, "_RETAINED_WRITES", retained)
    backend = BrainProductsTriggerBoxBackend("COM4", serial_module=driver.module)
    backend.connect()
    backend.send(55)
    with pytest.raises(BrainProductsTriggerBoxError, match="timed out while sending"):
        backend.reset()
    started = time.monotonic()
    with pytest.raises(BrainProductsTriggerBoxError) as failure:
        backend.close()
    assert time.monotonic() - started < 1
    assert driver.cancelled
    assert not driver.reused_pending
    if cancel_completes:
        assert driver.closed
        assert not retained
    else:
        assert "retained until process exit" in str(failure.value)
        assert not driver.closed
        assert driver.port.is_open
        assert len(driver.writes) == 2
        assert len(retained) == 1
        assert retained[0]._connection is driver.port
        assert retained[0]._payload == b"7"


@pytest.mark.parametrize("query_error", [6, 87])
def test_invalid_completion_query_retains_unconfirmed_native_storage(
    native_driver, monkeypatch, query_error,
):
    driver = native_driver
    retained = []
    monkeypatch.setattr(windows_module, "_RETAINED_WRITES", retained)
    backend = BrainProductsTriggerBoxBackend("COM4", serial_module=driver.module)
    backend.connect()
    driver.query_error = query_error
    with pytest.raises(BrainProductsTriggerBoxError, match=f"WinError {query_error}"):
        backend.send(55)
    with pytest.raises(BrainProductsTriggerBoxError, match="retained until process exit"):
        backend.close()
    assert not driver.closed
    assert driver.port.is_open
    assert len(driver.writes) == 2
    assert len(retained) == 1
    assert retained[0]._connection is driver.port
    assert retained[0]._payload == b"7"
