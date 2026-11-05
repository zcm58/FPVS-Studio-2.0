"""TriggerBox protocol, pulse lifecycle and explicit failure tests without hardware."""

from __future__ import annotations

import importlib
import threading
import time
from types import SimpleNamespace

import pytest

from fpvs_studio.triggers import brainproducts_backend as backend_module
from fpvs_studio.triggers.brainproducts_backend import (
    BrainProductsTriggerBoxBackend,
    BrainProductsTriggerBoxError,
)
from fpvs_studio.triggers.brainproducts_errors import (
    triggerbox_failure_reason,
    triggerbox_port_error_message,
)


class _FakePort:
    def __init__(self) -> None:
        self.attempts: list[tuple[bytes, float]] = []
        self.fail_at: set[int] = set()
        self.short_at: dict[int, int] = {}
        self.closed = False
        self.fail_close = False
        self._changed = threading.Condition()

    def write(self, payload: bytes) -> int:
        with self._changed:
            self.attempts.append((payload, time.monotonic()))
            count = len(self.attempts)
            self._changed.notify_all()
        if count in self.fail_at:
            raise OSError("write failed")
        return self.short_at.get(count, 1)

    def wait_for_attempts(self, count: int) -> None:
        with self._changed:
            assert self._changed.wait_for(lambda: len(self.attempts) >= count, timeout=2)

    @property
    def writes(self) -> list[bytes]:
        return [payload for payload, _when in self.attempts]

    def close(self) -> None:
        self.closed = True
        if self.fail_close:
            raise OSError("close failed")


class _FakeSerialModule:
    EIGHTBITS = 8
    PARITY_NONE = "N"
    STOPBITS_ONE = 1

    def __init__(self) -> None:
        self.port = _FakePort()
        self.open_calls: list[dict[str, object]] = []
        self.fail_open = False

    def Serial(self, **kwargs: object) -> _FakePort:  # noqa: N802
        self.open_calls.append(dict(kwargs))
        if self.fail_open:
            raise OSError("open failed")
        return self.port


class _Clock:
    def __init__(self) -> None:
        self.now = time.monotonic()

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float, backend: BrainProductsTriggerBoxBackend) -> None:
        with backend._condition:
            self.now += seconds
            backend._condition.notify_all()


def test_triggerbox_protocol_and_initial_zero() -> None:
    serial_module = _FakeSerialModule()
    backend = BrainProductsTriggerBoxBackend(" COM22 ", serial_module=serial_module)
    try:
        backend.connect()
        backend.connect()

        assert serial_module.open_calls == [
            {
                "port": "COM22",
                "baudrate": 2_000_000,
                "bytesize": 8,
                "parity": "N",
                "stopbits": 1,
                "timeout": 0,
                "write_timeout": 0,
                "rtscts": False,
                "dsrdtr": False,
                "xonxoff": False,
            }
        ]
        assert serial_module.port.writes == [b"\x00"]
        assert backend.backend_name == "brainproducts_triggerbox"
        assert backend.emits_external_markers is True
        assert backend.emits_hardware_triggers is True
    finally:
        backend.close()


@pytest.mark.parametrize("port", [None, "", "   "])
def test_triggerbox_default_port(port: str | None) -> None:
    serial_module = _FakeSerialModule()
    backend = BrainProductsTriggerBoxBackend(port, serial_module=serial_module)
    try:
        backend.connect()
        assert serial_module.open_calls[0]["port"] == "COM3"
    finally:
        backend.close()


@pytest.mark.parametrize("width", [None, True, 0, -1, 1001, 10.5, "10"])
def test_triggerbox_rejects_invalid_pulse_width(width: object) -> None:
    with pytest.raises(ValueError, match="1 to 1000"):
        BrainProductsTriggerBoxBackend(pulse_width_ms=width)  # type: ignore[arg-type]


@pytest.mark.parametrize("code", [1, 55, 127, 128, 255])
def test_triggerbox_writes_one_raw_byte_then_resets_automatically(code: int) -> None:
    serial_module = _FakeSerialModule()
    backend = BrainProductsTriggerBoxBackend(pulse_width_ms=10, serial_module=serial_module)
    try:
        backend.connect()
        backend.send_trigger(code)
        serial_module.port.wait_for_attempts(3)

        assert serial_module.port.writes == [b"\x00", bytes([code]), b"\x00"]
        event_at = serial_module.port.attempts[1][1]
        reset_at = serial_module.port.attempts[2][1]
        assert reset_at - event_at >= 0.01
    finally:
        backend.close()


@pytest.mark.parametrize("code", [-1, 0, 256, None, True, "55"])
def test_triggerbox_rejects_invalid_event_codes(code: object) -> None:
    serial_module = _FakeSerialModule()
    backend = BrainProductsTriggerBoxBackend(serial_module=serial_module)
    try:
        backend.connect()
        with pytest.raises((TypeError, ValueError), match="1 to 255"):
            backend.send_trigger(code)  # type: ignore[arg-type]
        assert serial_module.port.writes == [b"\x00"]
    finally:
        backend.close()


def test_triggerbox_prevalidated_path_skips_validation(monkeypatch) -> None:
    serial_module = _FakeSerialModule()
    backend = BrainProductsTriggerBoxBackend(serial_module=serial_module)
    try:
        backend.connect()

        def unexpected_validation(_code: object) -> int:
            raise AssertionError("validation must precede the flip callback")

        monkeypatch.setattr(backend_module, "validate_event_trigger_code", unexpected_validation)
        backend.send_prevalidated_trigger(55, frame_index=10, label="oddball", time_s=0.5)
        assert serial_module.port.writes[:2] == [b"\x00", b"\x37"]
    finally:
        backend.close()


def test_triggerbox_rejects_overlap_without_queueing() -> None:
    serial_module = _FakeSerialModule()
    backend = BrainProductsTriggerBoxBackend(pulse_width_ms=25, serial_module=serial_module)
    try:
        backend.connect()
        with backend._condition:
            backend.send(55)
            with pytest.raises(BrainProductsTriggerBoxError, match="overlaps") as caught:
                backend.send(55)
            assert str(caught.value).startswith("Two triggers are too close together.")
            assert "amplifier's minimum at the chosen sampling rate" in str(caught.value)
            assert serial_module.port.writes == [b"\x00", b"\x37"]
        backend.reset()
        assert serial_module.port.writes == [b"\x00", b"\x37", b"\x00", b"\x00"]
    finally:
        backend.close()


def test_triggerbox_repeats_require_a_complete_low_interval(monkeypatch) -> None:
    serial_module = _FakeSerialModule()
    backend = BrainProductsTriggerBoxBackend(pulse_width_ms=10, serial_module=serial_module)
    backend.connect()
    try:
        clock = _Clock()
        with monkeypatch.context() as patch:
            patch.setattr(backend_module, "time", SimpleNamespace(monotonic=clock.monotonic))
            backend.send(55)
            clock.advance(0.011, backend)
            serial_module.port.wait_for_attempts(3)
            with pytest.raises(BrainProductsTriggerBoxError, match="low interval") as caught:
                backend.send(55)
            assert str(caught.value).startswith("Two triggers are too close together.")
            assert "amplifier's minimum at the chosen sampling rate" in str(caught.value)
            clock.advance(0.011, backend)
            backend.send(55)
            clock.advance(0.011, backend)
            serial_module.port.wait_for_attempts(5)
            assert serial_module.port.writes == [b"\x00", b"\x37", b"\x00", b"\x37", b"\x00"]
    finally:
        backend.close()


def test_triggerbox_reset_and_close_preserve_pending_pulse_and_stop_worker() -> None:
    serial_module = _FakeSerialModule()
    backend = BrainProductsTriggerBoxBackend(pulse_width_ms=20, serial_module=serial_module)
    backend.connect()
    worker = backend._worker
    backend.send(55)

    backend.reset()
    backend.send(55)
    backend.close()
    backend.close()

    assert worker is not None and not worker.is_alive()
    assert serial_module.port.closed is True
    for index in (1, 4):
        payload, event_at = serial_module.port.attempts[index]
        reset_payload, reset_at = serial_module.port.attempts[index + 1]
        assert payload == b"\x37"
        assert reset_payload == b"\x00"
        assert reset_at - event_at >= 0.02


def test_triggerbox_reports_open_and_missing_dependency_errors(monkeypatch) -> None:
    serial_module = _FakeSerialModule()
    serial_module.fail_open = True
    backend = BrainProductsTriggerBoxBackend(serial_module=serial_module)
    with pytest.raises(BrainProductsTriggerBoxError, match="Unable to open.*COM3") as caught:
        backend.connect()
    message = str(caught.value)
    assert message.startswith("TriggerBox could not open COM3.")
    assert "Check USB" in message
    assert "Device Manager" in message
    assert "Details:" in message and "open failed" in message
    backend.close()

    def missing_serial(_name: str) -> object:
        raise ModuleNotFoundError("serial")

    monkeypatch.setattr(importlib, "import_module", missing_serial)
    with pytest.raises(BrainProductsTriggerBoxError, match="pyserial is required"):
        BrainProductsTriggerBoxBackend().connect()


def test_triggerbox_access_denied_explains_exclusive_port_and_can_retry(monkeypatch) -> None:
    serial_module = _FakeSerialModule()
    original_open = serial_module.Serial
    failure = OSError(
        "could not open port 'COM4': PermissionError(13, 'Access is denied.', None, 5)"
    )

    def occupied(**kwargs):
        serial_module.open_calls.append(kwargs)
        raise failure

    monkeypatch.setattr(serial_module, "Serial", occupied)
    backend = BrainProductsTriggerBoxBackend("COM4", serial_module=serial_module)
    with pytest.raises(BrainProductsTriggerBoxError) as caught:
        backend.connect()
    assert "COM4 is busy or access was denied" in str(caught.value)
    assert "Close TriggerBox Configuration/Test IO" in str(caught.value)
    assert "retry" in str(caught.value)
    assert caught.value.__cause__ is failure
    assert len(serial_module.open_calls) == 1
    assert serial_module.port.writes == []
    assert backend._worker is None

    monkeypatch.setattr(serial_module, "Serial", original_open)
    try:
        backend.connect()
        assert serial_module.open_calls[-1]["port"] == "COM4"
        assert serial_module.port.writes == [b"\x00"]
    finally:
        backend.close()


@pytest.mark.parametrize("failure, expected, action", [
    (FileNotFoundError(2, "Missing"), "TriggerBox port COM4 was not found.", "Device Manager"),
    (OSError("could not open port 'COM4': FileNotFoundError(2, 'Absent', None, 3)"),
     "TriggerBox port COM4 was not found.", "driver if absent"),
    (PermissionError(13, "Denied"), "TriggerBox port COM4 is busy or access was denied.",
     "Close TriggerBox Configuration/Test IO"),
    (OSError("[WinError 32] Sharing violation"),
     "TriggerBox port COM4 is busy or access was denied.", "other port users"),
    (ValueError("Not a valid baudrate"), "TriggerBox serial settings on COM4 were rejected.",
     "2,000,000 baud"),
    (OSError("Cannot configure port: OSError(22, 'Driver error', None, 31)"),
     "TriggerBox serial settings on COM4 were rejected.", "vendor driver"),
    (OSError("could not open port 'COM4': OSError(22, 'Device unavailable', None, 1167)"),
     "TriggerBox communication on COM4 failed.", "USB/power"),
    (OSError("[WinError 21] Not ready"), "TriggerBox communication on COM4 failed.",
     "reconnect"),
    (TimeoutError("Timed out"), "TriggerBox port COM4 did not respond in time.", "USB/power"),
    (OSError("[WinError 121] Timeout"), "TriggerBox port COM4 did not respond in time.", "retry"),
    (OSError(22, "Unspecified error"), "TriggerBox could not open COM4.", "Device Manager"),
])
def test_connection_failure_has_specific_recovery_and_retains_details(
    monkeypatch, failure, expected, action,
) -> None:
    serial_module = _FakeSerialModule()

    def reject(**kwargs):
        serial_module.open_calls.append(kwargs)
        raise failure

    monkeypatch.setattr(serial_module, "Serial", reject)
    backend = BrainProductsTriggerBoxBackend("COM4", serial_module=serial_module)
    with pytest.raises(BrainProductsTriggerBoxError) as caught:
        backend.connect()
    message = str(caught.value)
    assert message.startswith(expected)
    assert action in message.partition("Details:")[0]
    assert str(failure) in message.partition("Details:")[2]
    assert caught.value.__cause__ is failure
    assert len(serial_module.open_calls) == 1
    assert serial_module.port.writes == []
    assert backend._worker is None


@pytest.mark.parametrize("code", [0, 55])
def test_write_timeout_names_the_failed_operation_and_does_not_resend(monkeypatch, code):
    serial_module = _FakeSerialModule()
    backend = BrainProductsTriggerBoxBackend("COM4", serial_module=serial_module)
    failure = type("SerialTimeoutException", (OSError,), {})("Write timeout")
    calls = []

    def timeout(payload):
        calls.append(payload)
        raise failure

    monkeypatch.setattr(serial_module.port, "write", timeout)
    with pytest.raises(BrainProductsTriggerBoxError) as caught:
        backend._write(serial_module.port, code, action="reset" if code == 0 else "send")
    message = str(caught.value)
    assert "TriggerBox timed out while" in message
    assert ("clearing the trigger signal" if code == 0 else "sending a marker") in message
    assert "saved EEG markers" in message
    assert caught.value.__cause__ is failure
    assert calls == [bytes([code])]


@pytest.mark.parametrize("failure, reason", [
    (PermissionError(13, "Permission denied"), "busy"),
    (FileNotFoundError(2, "Missing"), "missing"),
    (OSError(5, "Input/output error"), "device_io"),
    (OSError(16, "Device or resource busy"), "busy"),
    (OSError("[WinError 1117] I/O device error"), "device_io"),
    (OSError("Cannot configure port: PermissionError(13, 'Denied', None, 5)"), "configuration"),
    (OSError("could not open: PermissionError(13, 'Zugriff verweigert', None, 5)"), "busy"),
    (OSError("Unable to close the port: [WinError 5] Denied"), "close"),
    (OSError("[WinError 2] Missing. Closing the port also failed: close failed"), "close"),
    (OSError(22, "Unknown error"), "unknown"),
])
def test_detection_and_launch_show_same_recovery_for_native_or_serialized_errors(failure, reason):
    assert triggerbox_failure_reason(failure) == reason
    assert triggerbox_failure_reason(str(failure)) == reason
    assert triggerbox_port_error_message("COM3", failure) == triggerbox_port_error_message(
        "COM3", str(failure),
    )


@pytest.mark.parametrize("result", [0, 2])
def test_triggerbox_failed_initial_zero_closes_port(result: int) -> None:
    serial_module = _FakeSerialModule()
    serial_module.port.short_at[1] = result
    backend = BrainProductsTriggerBoxBackend(serial_module=serial_module)

    with pytest.raises(BrainProductsTriggerBoxError, match="initialize zero.*expected 1"):
        backend.connect()

    assert serial_module.port.closed is True
    assert backend._worker is None
    backend.close()


def test_triggerbox_initial_zero_error_retains_failed_close_evidence() -> None:
    serial_module = _FakeSerialModule()
    serial_module.port.fail_at.add(1)
    serial_module.port.fail_close = True
    backend = BrainProductsTriggerBoxBackend(serial_module=serial_module)

    with pytest.raises(BrainProductsTriggerBoxError, match="initialize zero.*Closing.*also failed"):
        backend.connect()

    assert serial_module.port.closed is True
    assert backend._worker is None


def test_triggerbox_worker_start_error_releases_port(monkeypatch) -> None:
    serial_module = _FakeSerialModule()
    backend = BrainProductsTriggerBoxBackend(serial_module=serial_module)

    def failed_start(_worker: threading.Thread) -> None:
        raise RuntimeError("thread unavailable")

    monkeypatch.setattr(threading.Thread, "start", failed_start)
    with pytest.raises(BrainProductsTriggerBoxError, match="start TriggerBox reset worker"):
        backend.connect()

    assert serial_module.port.closed is True
    assert backend._worker is None
    backend.close()


def test_triggerbox_stopped_worker_fails_before_another_event(monkeypatch) -> None:
    serial_module = _FakeSerialModule()
    backend = BrainProductsTriggerBoxBackend(serial_module=serial_module)
    stop = threading.Event()
    monkeypatch.setattr(backend, "_reset_loop", lambda: stop.wait(timeout=2))
    backend.connect()
    worker = backend._worker
    assert worker is not None
    stop.set()
    worker.join(timeout=1)

    with pytest.raises(BrainProductsTriggerBoxError, match="reset worker has stopped"):
        backend.send(55)
    with pytest.raises(BrainProductsTriggerBoxError, match="reset worker has stopped"):
        backend.close()

    assert serial_module.port.writes == [b"\x00", b"\x00"]
    assert serial_module.port.closed is True


@pytest.mark.parametrize("short_write", [False, True])
def test_triggerbox_sync_write_failure_is_explicit_and_cleanup_still_closes(
    short_write: bool,
) -> None:
    serial_module = _FakeSerialModule()
    if short_write:
        serial_module.port.short_at[2] = 0
    else:
        serial_module.port.fail_at.add(2)
    backend = BrainProductsTriggerBoxBackend(serial_module=serial_module)
    backend.connect()

    with pytest.raises(BrainProductsTriggerBoxError, match="send trigger code 55") as caught:
        backend.send(55)
    assert str(caught.value).startswith(
        "TriggerBox did not accept the full marker byte." if short_write
        else "TriggerBox could not send a marker."
    )
    assert "Reconnect TriggerBox and check any saved EEG markers before retrying." in str(
        caught.value
    )
    assert "Details:" in str(caught.value) and "COM3" in str(caught.value)
    with pytest.raises(BrainProductsTriggerBoxError, match="send trigger code 55"):
        backend.close()

    assert serial_module.port.closed is True
    assert serial_module.port.writes[-1] == b"\x00"


@pytest.mark.parametrize("short_write", [False, True])
def test_triggerbox_async_reset_failure_surfaces_on_send_reset_and_close(short_write: bool) -> None:
    serial_module = _FakeSerialModule()
    if short_write:
        serial_module.port.short_at[3] = 0
    else:
        serial_module.port.fail_at.add(3)
    backend = BrainProductsTriggerBoxBackend(serial_module=serial_module)
    backend.connect()
    worker = backend._worker
    backend.send(55)
    serial_module.port.wait_for_attempts(3)

    for action in (lambda: backend.send(55), backend.reset, backend.close):
        with pytest.raises(
            BrainProductsTriggerBoxError, match="reset trigger lines code 0"
        ) as caught:
            action()
        assert str(caught.value).startswith(
            "TriggerBox did not accept the zero reset byte." if short_write
            else "TriggerBox could not clear the trigger signal."
        )
        assert "check any saved EEG markers before retrying" in str(caught.value)

    assert worker is not None and not worker.is_alive()
    assert serial_module.port.closed is True
    assert serial_module.port.writes == [b"\x00", b"\x37", b"\x00", b"\x00"]


def test_triggerbox_final_zero_failure_still_releases_port() -> None:
    serial_module = _FakeSerialModule()
    serial_module.port.fail_at.add(3)
    backend = BrainProductsTriggerBoxBackend(serial_module=serial_module)
    backend.connect()
    worker = backend._worker

    with pytest.raises(BrainProductsTriggerBoxError, match="clear trigger lines during close"):
        backend.close()

    assert worker is not None and not worker.is_alive()
    assert serial_module.port.closed is True


def test_triggerbox_close_error_and_disconnected_send_are_explicit() -> None:
    serial_module = _FakeSerialModule()
    serial_module.port.fail_close = True
    backend = BrainProductsTriggerBoxBackend(serial_module=serial_module)
    with pytest.raises(BrainProductsTriggerBoxError, match="not connected"):
        backend.send(55)
    backend.connect()

    with pytest.raises(BrainProductsTriggerBoxError, match="Unable to close.*close failed"):
        backend.close()

    assert serial_module.port.closed is True
    with pytest.raises(BrainProductsTriggerBoxError, match="not connected"):
        backend.send(55)
    backend.close()


def test_triggerbox_close_retains_send_and_cleanup_failures() -> None:
    serial_module = _FakeSerialModule()
    serial_module.port.fail_at.update((2, 3))
    serial_module.port.fail_close = True
    backend = BrainProductsTriggerBoxBackend(serial_module=serial_module)
    backend.connect()

    with pytest.raises(BrainProductsTriggerBoxError, match="send trigger code 55"):
        backend.send(55)
    with pytest.raises(BrainProductsTriggerBoxError) as caught:
        backend.close()

    assert "send trigger code 55" in str(caught.value)
    assert str(caught.value).startswith("TriggerBox cleanup did not finish.")
    assert "Restart FPVS Studio and reconnect TriggerBox before retrying." in str(caught.value)
    assert "clear trigger lines during close" in str(caught.value)
    assert "close failed" in str(caught.value)
    assert serial_module.port.closed is True
    assert backend._worker is None
