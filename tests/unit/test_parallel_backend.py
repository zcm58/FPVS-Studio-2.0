"""Native LPT output tests with synthetic drivers and Windows API handles only."""

from __future__ import annotations

import ctypes
import threading
import time
from types import SimpleNamespace

import pytest

from fpvs_studio.triggers import parallel_backend as backend_module
from fpvs_studio.triggers.parallel_backend import (
    ParallelPortBackend,
    ParallelPortDriverUnavailableError,
    ParallelPortError,
)


class FakeDriver:
    def __init__(self) -> None:
        self.attempts: list[tuple[int, int, float]] = []
        self.fail_at: set[int] = set()
        self.closed = False
        self.open_count = 0
        self.fail_open = False
        self.fail_close = False
        self.changed = threading.Condition()

    def connect(self) -> None:
        self.open_count += 1
        if self.fail_open:
            raise OSError("driver unavailable")

    def write(self, address: int, code: int) -> None:
        with self.changed:
            self.attempts.append((address, code, time.monotonic()))
            count = len(self.attempts)
            self.changed.notify_all()
        if count in self.fail_at:
            raise OSError("driver write failed")

    def close(self) -> None:
        self.closed = True
        if self.fail_close:
            raise OSError("driver close failed")

    def wait_for_attempts(self, count: int) -> None:
        with self.changed:
            assert self.changed.wait_for(lambda: len(self.attempts) >= count, timeout=2)

    @property
    def codes(self) -> list[int]:
        return [code for _address, code, _when in self.attempts]


def test_connect_is_explicit_idempotent_and_initializes_selected_address_only() -> None:
    driver = FakeDriver()
    backend = ParallelPortBackend(0xDC00, driver=driver)
    assert driver.open_count == 0 and driver.codes == []
    with pytest.raises(ParallelPortError, match="not connected"):
        backend.send(55)
    try:
        backend.connect()
        backend.connect()
        assert driver.open_count == 1
        assert driver.codes == [0]
        assert driver.attempts[0][0] == 0xDC00
        assert backend.backend_name == "brainproducts_parallel"
        assert backend.emits_external_markers and backend.emits_hardware_triggers
    finally:
        backend.close()


@pytest.mark.parametrize("address", [0, -1, 65536, True, None, 888.0, "0x378"])
def test_address_is_required_and_strictly_validated(address: object) -> None:
    with pytest.raises(ValueError, match="1 to 65535"):
        ParallelPortBackend(address)  # type: ignore[arg-type]


@pytest.mark.parametrize("width", [0, -1, 1001, True, None, 10.0, "10"])
def test_pulse_width_is_strictly_validated(width: object) -> None:
    with pytest.raises(ValueError, match="1 to 1000"):
        ParallelPortBackend(0x378, pulse_width_ms=width)  # type: ignore[arg-type]


@pytest.mark.parametrize("code", [1, 55, 127, 128, 255])
def test_full_eight_bit_codes_and_pulse_are_preserved(code: int) -> None:
    driver = FakeDriver()
    backend = ParallelPortBackend(0x378, pulse_width_ms=5, driver=driver)
    try:
        backend.connect()
        backend.send_trigger(code)
        driver.wait_for_attempts(3)
        assert driver.codes == [0, code, 0]
        assert driver.attempts[2][2] - driver.attempts[1][2] >= 0.005
        assert {address for address, _code, _when in driver.attempts} == {0x378}
    finally:
        backend.close()


@pytest.mark.parametrize("code", [0, -1, 256, None, True, "55"])
def test_invalid_event_codes_never_reach_driver(code: object) -> None:
    driver = FakeDriver()
    backend = ParallelPortBackend(0x378, driver=driver)
    try:
        backend.connect()
        with pytest.raises((TypeError, ValueError), match="1 to 255"):
            backend.send_trigger(code)  # type: ignore[arg-type]
        assert driver.codes == [0]
    finally:
        backend.close()


def test_prevalidated_callback_does_not_validate_again(monkeypatch) -> None:
    driver = FakeDriver()
    backend = ParallelPortBackend(0x378, driver=driver)
    try:
        backend.connect()

        def unexpected(_code):
            raise AssertionError("validation must precede presentation")

        monkeypatch.setattr(backend_module, "validate_event_trigger_code", unexpected)
        backend.send_prevalidated_trigger(255, frame_index=10, label="oddball", time_s=0.5)
        assert driver.codes[:2] == [0, 255]
    finally:
        backend.close()


def test_overlap_is_rejected_synchronously_without_queue_or_sleep() -> None:
    driver = FakeDriver()
    backend = ParallelPortBackend(0x378, driver=driver)
    try:
        backend.connect()
        with backend._condition:
            backend.send(55)
            with pytest.raises(ParallelPortError, match="overlaps"):
                backend.send(55)
            assert driver.codes == [0, 55]
    finally:
        backend.close()


def test_repeated_codes_require_complete_low_interval(monkeypatch) -> None:
    driver = FakeDriver()
    backend = ParallelPortBackend(0x378, driver=driver)
    backend.connect()
    clock = SimpleNamespace(now=time.monotonic())

    def advance():
        with backend._condition:
            clock.now += 0.011
            backend._condition.notify_all()

    try:
        with monkeypatch.context() as patch:
            patch.setattr(backend_module, "time", SimpleNamespace(monotonic=lambda: clock.now))
            backend.send(55)
            advance()
            driver.wait_for_attempts(3)
            with pytest.raises(ParallelPortError, match="low interval"):
                backend.send(55)
            advance()
            backend.send(55)
            advance()
            driver.wait_for_attempts(5)
            assert driver.codes == [0, 55, 0, 55, 0]
    finally:
        backend.close()


def test_close_drains_pending_pulse_and_stops_worker() -> None:
    driver = FakeDriver()
    backend = ParallelPortBackend(0x378, pulse_width_ms=5, driver=driver)
    backend.connect()
    worker = backend._worker
    backend.send(255)
    backend.close()
    backend.close()
    assert worker is not None and not worker.is_alive()
    assert driver.closed
    assert driver.codes == [0, 255, 0, 0, 0]
    assert driver.attempts[2][2] - driver.attempts[1][2] >= 0.005


@pytest.mark.parametrize("failure_at", [2, 3])
def test_sync_and_async_write_failures_remain_visible_through_cleanup(failure_at: int) -> None:
    driver = FakeDriver()
    driver.fail_at.add(failure_at)
    backend = ParallelPortBackend(0x378, pulse_width_ms=5, driver=driver)
    backend.connect()
    worker = backend._worker
    if failure_at == 2:
        with pytest.raises(ParallelPortError, match="send trigger") as error:
            backend.send(55)
    else:
        backend.send(55)
        with backend._condition:
            assert backend._condition.wait_for(lambda: backend._failure is not None, timeout=2)
        with pytest.raises(ParallelPortError, match="reset trigger") as error:
            backend.send(55)
    with pytest.raises(ParallelPortError) as close_error:
        backend.close()
    assert close_error.value is error.value
    assert driver.closed and driver.codes[-1] == 0
    assert worker is not None and not worker.is_alive()


@pytest.mark.parametrize("fail_open", [False, True])
def test_failed_connection_releases_driver_without_worker(fail_open: bool) -> None:
    driver = FakeDriver()
    driver.fail_open = fail_open
    driver.fail_at.add(1)
    backend = ParallelPortBackend(0x378, driver=driver)
    with pytest.raises(ParallelPortError, match="initialize parallel-port"):
        backend.connect()
    assert driver.closed and backend._worker is None and backend._driver is None
    backend.close()


def test_worker_start_failure_and_cleanup_error_are_reported(monkeypatch) -> None:
    driver = FakeDriver()
    driver.fail_close = True
    backend = ParallelPortBackend(0x378, driver=driver)

    def fail_start(_worker):
        raise RuntimeError("worker unavailable")

    monkeypatch.setattr(threading.Thread, "start", fail_start)
    with pytest.raises(ParallelPortError, match="worker unavailable.*Closing.*driver close failed"):
        backend.connect()
    assert driver.closed and backend._worker is None and backend._driver is None


def test_dead_worker_is_detected_and_cleanup_still_closes(monkeypatch) -> None:
    driver = FakeDriver()
    backend = ParallelPortBackend(0x378, driver=driver)
    stop = threading.Event()
    monkeypatch.setattr(backend, "_reset_loop", lambda: stop.wait(timeout=2))
    backend.connect()
    worker = backend._worker
    assert worker is not None
    stop.set()
    worker.join(timeout=1)
    with pytest.raises(ParallelPortError, match="worker has stopped"):
        backend.send(55)
    with pytest.raises(ParallelPortError, match="worker has stopped"):
        backend.close()
    assert driver.closed and driver.codes == [0, 0]


class FakeFunction:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


def _windows_api(monkeypatch, *, open_result=123, write_result=1, close_result=1):
    calls = []
    api = SimpleNamespace(
        GetCurrentProcess=FakeFunction(lambda: 50),
        IsWow64Process=FakeFunction(lambda *_args: 1),
        CreateFileW=FakeFunction(lambda *args: calls.append(("open", args)) or open_result),
        DeviceIoControl=FakeFunction(lambda *args: calls.append(("write", args)) or write_result),
        CloseHandle=FakeFunction(lambda *args: calls.append(("close", args)) or close_result),
    )

    def load(name, **kwargs):
        assert name == "kernel32" and kwargs == {"use_last_error": True}
        return api

    monkeypatch.setattr(backend_module, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(ctypes, "WinDLL", load, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 5, raising=False)
    return calls, api


def test_native_driver_uses_existing_device_and_checked_write_protocol(monkeypatch) -> None:
    calls, _api = _windows_api(monkeypatch)
    driver = backend_module._InpOutDriver()
    driver.connect()
    driver.write(0xDC00, 255)
    driver.close()
    driver.close()
    assert calls[0] == ("open", (r"\\.\inpoutx64", 0xC0000000, 0, None, 3, 0x80, None))
    name, args = calls[1]
    assert name == "write"
    assert args[:2] == (123, 0x9C402008)
    assert ctypes.string_at(args[2], 3) == b"\x00\xdc\xff"
    assert args[3:6] == (3, None, 0)
    assert calls[-1] == ("close", (123,))
    assert len(calls) == 3


def test_native_driver_missing_platform_and_device_fail_without_port_writes(monkeypatch) -> None:
    calls, _api = _windows_api(monkeypatch, open_result=ctypes.c_void_p(-1).value)
    driver = backend_module._InpOutDriver()
    with pytest.raises(
        ParallelPortDriverUnavailableError, match="already installed, running InpOut",
    ):
        driver.connect()
    driver.close()
    assert [name for name, _args in calls] == ["open"]
    monkeypatch.setattr(backend_module, "sys", SimpleNamespace(platform="linux"))
    with pytest.raises(ParallelPortError, match="requires Windows"):
        driver.connect()
    assert len(calls) == 1


def test_native_driver_reports_failed_write_and_close(monkeypatch) -> None:
    _windows_api(monkeypatch, write_result=0, close_result=0)
    driver = backend_module._InpOutDriver()
    with pytest.raises(ParallelPortError, match="not open"):
        driver.write(0x378, 55)
    driver.connect()
    with pytest.raises(ParallelPortError, match="port write failed"):
        driver.write(0x378, 55)
    with pytest.raises(ParallelPortError, match="Closing InpOut failed"):
        driver.close()


@pytest.mark.parametrize("wow64", [False, True])
def test_32_bit_process_selects_driver_for_windows_architecture(monkeypatch, wow64) -> None:
    calls, api = _windows_api(monkeypatch)
    monkeypatch.setattr(ctypes, "sizeof", lambda _value: 4)

    def query(_process, value):
        value._obj.value = wow64
        return 1

    api.IsWow64Process.callback = query
    driver = backend_module._InpOutDriver()
    driver.connect()
    driver.close()
    assert calls[0][1][0] == (r"\\.\inpoutx64" if wow64 else r"\\.\inpout32")


def test_failed_architecture_query_never_opens_driver(monkeypatch) -> None:
    calls, api = _windows_api(monkeypatch)
    monkeypatch.setattr(ctypes, "sizeof", lambda _value: 4)
    api.IsWow64Process.callback = lambda *_args: 0
    with pytest.raises(ParallelPortError, match="driver architecture"):
        backend_module._InpOutDriver().connect()
    assert calls == []
