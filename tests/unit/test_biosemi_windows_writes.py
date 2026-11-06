"""Real pyserial BioSemi Windows writes with intercepted API calls, never COM I/O."""

from __future__ import annotations

import sys
import time

import pytest
from tests.unit.test_brainproducts_windows_writes import _run_in_thread
from tests.unit.test_brainproducts_windows_writes import native_driver as native_driver

from fpvs_studio.triggers import brainproducts_windows as windows_module
from fpvs_studio.triggers import serial_backend as backend_module
from fpvs_studio.triggers.base import TriggerCompletionError, TriggerSubmissionBlockedError
from fpvs_studio.triggers.serial_backend import SerialBackend, SerialBackendError

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Native pyserial Windows path")


def test_biosemi_pending_write_is_not_overwritten_by_next_marker(native_driver):
    driver = native_driver
    driver.blocked.add(1)
    backend = SerialBackend("COM3", serial_module=driver.module)
    backend.connect()
    try:
        backend.send(55)
        with pytest.raises(SerialBackendError) as failure:
            backend.send(128)
        assert not isinstance(failure.value, TriggerCompletionError)
        assert isinstance(failure.value, TriggerSubmissionBlockedError)
        assert not driver.reused_pending
        assert [payload for payload, _when in driver.writes] == [b"7"]
    finally:
        driver.blocked.clear()
        with pytest.raises(SerialBackendError, match="previous marker") as closing:
            backend.close()
        assert not isinstance(closing.value, TriggerCompletionError)


def test_biosemi_close_reports_unobserved_native_completion_error(native_driver):
    driver = native_driver
    driver.blocked.add(1)
    backend = SerialBackend("COM3", serial_module=driver.module)
    backend.connect()
    backend.send(55)
    driver.blocked.clear()
    driver.errors[1] = 1117
    with pytest.raises(SerialBackendError, match="1117") as failure:
        backend.close()
    assert isinstance(failure.value, TriggerCompletionError)
    assert failure.value.__cause__.winerror == 1117
    assert driver.closed


def test_biosemi_close_waits_for_pending_marker_before_releasing_port(native_driver):
    driver = native_driver
    driver.blocked.add(1)
    backend = SerialBackend("COM3", serial_module=driver.module)
    backend.connect()
    backend.send(255)
    thread, errors = _run_in_thread(backend.close)
    try:
        time.sleep(.02)
        assert thread.is_alive()
        assert not driver.closed
    finally:
        driver.blocked.clear()
        thread.join(timeout=2)
    assert not thread.is_alive()
    assert not errors
    assert driver.closed


@pytest.mark.parametrize("reset_code", [None, 0])
def test_biosemi_finish_waits_for_final_marker_without_reset(native_driver, reset_code):
    driver = native_driver
    driver.blocked.add(1)
    backend = SerialBackend("COM3", reset_code=reset_code, serial_module=driver.module)
    backend.connect()
    backend.send(255)
    thread, errors = _run_in_thread(backend.finish_pending_output)
    try:
        time.sleep(.02)
        assert thread.is_alive()
        assert not driver.closed
        assert len(driver.writes) == 1
    finally:
        driver.blocked.clear()
        thread.join(timeout=2)
    assert not thread.is_alive()
    assert not errors
    assert not driver.closed
    backend.send(128)
    backend.finish_pending_output()
    backend.close()
    assert [payload for payload, _when in driver.writes] == [b"\xff", b"\x80"]
    assert not driver.reused_pending


def test_biosemi_finish_reports_deferred_failure_before_feedback(native_driver):
    driver = native_driver
    driver.blocked.add(1)
    backend = SerialBackend("COM3", serial_module=driver.module)
    backend.connect()
    backend.send(255)
    driver.errors[1] = 1117
    driver.blocked.clear()
    with pytest.raises(SerialBackendError, match="1117") as failure:
        backend.finish_pending_output()
    assert failure.value.__cause__.winerror == 1117
    assert isinstance(failure.value, TriggerCompletionError)
    for attempt in (
        backend.finish_pending_output, lambda: backend.send(128), backend.connect, backend.close,
    ):
        with pytest.raises(SerialBackendError) as repeated:
            attempt()
        assert repeated.value is failure.value
    assert len(driver.writes) == 1
    assert driver.closed


@pytest.mark.parametrize("operation", ["finish", "close", "send"])
def test_biosemi_manual_reset_completion_failure_is_not_an_event_failure(native_driver, operation):
    driver = native_driver
    backend = SerialBackend("COM3", reset_code=0, serial_module=driver.module)
    backend.connect()
    backend.send(55)
    driver.blocked.add(2)
    backend.reset()
    driver.errors[2] = 1117
    driver.blocked.clear()
    attempt = {
        "finish": backend.finish_pending_output,
        "close": backend.close,
        "send": lambda: backend.send(128),
    }[operation]
    with pytest.raises(SerialBackendError, match="1117") as failure:
        attempt()
    assert not isinstance(failure.value, TriggerCompletionError)
    assert failure.value.__cause__.winerror == 1117
    with pytest.raises(SerialBackendError):
        backend.close()
    assert [payload for payload, _when in driver.writes] == [b"7", b"\x00"]
    assert driver.closed


def test_biosemi_finish_timeout_preserves_pending_ownership_until_close(native_driver, monkeypatch):
    driver = native_driver
    driver.blocked.add(1)
    monkeypatch.setattr(backend_module, "_WRITE_TIMEOUT_S", .01)
    backend = SerialBackend("COM3", serial_module=driver.module)
    backend.connect()
    backend.send(255)
    with pytest.raises(SerialBackendError, match="timed out") as failure:
        backend.finish_pending_output()
    assert isinstance(failure.value.__cause__, TimeoutError)
    assert backend._native_write.pending
    assert not driver.closed and not driver.cancelled
    for attempt in (backend.finish_pending_output, lambda: backend.send(55), backend.connect):
        with pytest.raises(SerialBackendError) as repeated:
            attempt()
        assert repeated.value is failure.value
    with pytest.raises(SerialBackendError, match="timed out") as failure:
        backend.close()
    assert isinstance(failure.value, TriggerCompletionError)
    assert driver.cancelled and driver.closed
    assert len(driver.writes) == 1


def test_biosemi_completed_native_markers_preserve_all_bytes_without_reset(native_driver):
    driver = native_driver
    backend = SerialBackend("COM3", serial_module=driver.module)
    backend.connect()
    for code in (*range(1, 256), 55, 55, 128, 255):
        backend.send_prevalidated_trigger(code)
    backend.reset()
    backend.close()
    assert b"".join(payload for payload, _when in driver.writes) == (
        bytes(range(1, 256)) + b"\x37\x37\x80\xff"
    )
    assert not driver.reused_pending
    assert driver.closed


@pytest.mark.parametrize("failure_kind", ["completion", "submission", "short"])
def test_biosemi_native_failure_stays_failed_without_resending(native_driver, failure_kind):
    driver = native_driver
    if failure_kind == "completion":
        driver.errors[1] = 1117
    elif failure_kind == "submission":
        driver.submission_errors[1] = 1117
    else:
        driver.short.add(1)
    backend = SerialBackend("COM3", serial_module=driver.module)
    backend.connect()
    with pytest.raises(SerialBackendError) as failure:
        backend.send(55)
    assert failure.value.__cause__ is not None
    assert not isinstance(failure.value, TriggerCompletionError)
    for attempt in (lambda: backend.send(55), backend.connect, backend.close, backend.connect):
        with pytest.raises(SerialBackendError) as repeated:
            attempt()
        assert repeated.value is failure.value
    assert len(driver.writes) == 1
    assert driver.closed


def test_biosemi_delayed_failure_is_seen_before_submitting_another_marker(native_driver):
    driver = native_driver
    driver.blocked.add(1)
    backend = SerialBackend("COM3", serial_module=driver.module)
    backend.connect()
    backend.send(55)
    driver.errors[1] = 1117
    driver.blocked.clear()
    with pytest.raises(SerialBackendError, match="1117") as failure:
        backend.send(128)
    assert isinstance(failure.value, TriggerCompletionError)
    assert failure.value.__cause__.winerror == 1117
    with pytest.raises(SerialBackendError) as closing:
        backend.close()
    assert closing.value is failure.value
    assert len(driver.writes) == 1
    assert not driver.reused_pending
    assert driver.closed


def test_biosemi_pending_write_has_no_hot_path_wait(native_driver, monkeypatch):
    driver = native_driver
    driver.blocked.add(1)
    backend = SerialBackend("COM3", serial_module=driver.module)
    backend.connect()

    def forbidden_sleep(_seconds):
        raise AssertionError("Flip callbacks must not wait for serial completion")

    with monkeypatch.context() as patch:
        patch.setattr(backend_module.time, "sleep", forbidden_sleep)
        backend.send_prevalidated_trigger(55)
        with pytest.raises(SerialBackendError, match="next marker was not sent"):
            backend.send_prevalidated_trigger(128)
    driver.blocked.clear()
    with pytest.raises(SerialBackendError):
        backend.close()
    assert len(driver.writes) == 1


def test_biosemi_shutdown_timeout_observes_cancellation_before_release(native_driver, monkeypatch):
    driver = native_driver
    driver.blocked.add(1)
    monkeypatch.setattr(backend_module, "_WRITE_TIMEOUT_S", .01)
    backend = SerialBackend("COM3", serial_module=driver.module)
    backend.connect()
    backend.send(255)
    with pytest.raises(SerialBackendError, match="timed out"):
        backend.close()
    assert driver.cancelled and driver.closed
    assert backend._native_write is None
    assert len(driver.writes) == 1


@pytest.mark.parametrize("query_error", [None, 6, 87])
def test_biosemi_unconfirmed_cancellation_retains_port_and_storage(
    native_driver, monkeypatch, query_error,
):
    driver = native_driver
    driver.blocked.add(1)
    driver.cancel_completes = False
    monkeypatch.setattr(backend_module, "_WRITE_TIMEOUT_S", .01)
    monkeypatch.setattr(windows_module, "_RETAINED_WRITES", [])
    backend = SerialBackend("COM3", serial_module=driver.module)
    backend.connect()
    backend.send(55)
    driver.query_error = query_error
    with pytest.raises(SerialBackendError, match="Restart Studio") as failure:
        backend.close()
    native = backend._native_write
    assert native is not None and native.pending
    assert windows_module._RETAINED_WRITES == [native]
    assert backend._connection is driver.port
    assert not driver.closed
    for attempt in (backend.connect, backend.close, lambda: backend.send(128)):
        with pytest.raises(SerialBackendError) as repeated:
            attempt()
        assert repeated.value is failure.value
    assert len(driver.writes) == 1
    assert not driver.closed


def test_biosemi_cancellation_failure_is_retained_even_if_write_finishes(
    native_driver, monkeypatch,
):
    driver = native_driver
    driver.blocked.add(1)
    driver.cancel_error = 5
    monkeypatch.setattr(backend_module, "_WRITE_TIMEOUT_S", .01)
    backend = SerialBackend("COM3", serial_module=driver.module)
    backend.connect()
    backend.send(55)
    with pytest.raises(SerialBackendError, match="cancellation failed"):
        backend.close()
    assert driver.closed
    assert len(driver.writes) == 1
