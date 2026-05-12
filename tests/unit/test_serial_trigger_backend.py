"""Serial trigger backend and runtime trigger-selection tests."""

from __future__ import annotations

import importlib

import pytest

from fpvs_studio.runtime.triggers import build_trigger_backend
from fpvs_studio.triggers.base import TriggerBackend
from fpvs_studio.triggers.serial_backend import SerialBackend


class _FakePort:
    def __init__(self, *, fail_writes: bool = False, bytes_written: int = 1) -> None:
        self.fail_writes = fail_writes
        self.bytes_written = bytes_written
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, payload: bytes) -> int:
        if self.fail_writes:
            raise OSError("write failed")
        self.writes.append(payload)
        return self.bytes_written

    def close(self) -> None:
        self.closed = True


class _FakeSerialModule:
    EIGHTBITS = 8
    PARITY_NONE = "N"
    STOPBITS_ONE = 1

    def __init__(
        self,
        *,
        fail_open: bool = False,
        fail_writes: bool = False,
        bytes_written: int = 1,
    ) -> None:
        self.fail_open = fail_open
        self.fail_writes = fail_writes
        self.open_calls: list[dict[str, object]] = []
        self.port = _FakePort(fail_writes=fail_writes, bytes_written=bytes_written)

    def Serial(self, **kwargs: object) -> _FakePort:  # noqa: N802
        self.open_calls.append(dict(kwargs))
        if self.fail_open:
            raise OSError("open failed")
        return self.port


def test_serial_backend_opens_with_biosemi_serial_parameters() -> None:
    serial_module = _FakeSerialModule()
    backend = SerialBackend("COM4", 57600, serial_module=serial_module)

    backend.connect()

    assert serial_module.open_calls == [
        {
            "port": "COM4",
            "baudrate": 57600,
            "bytesize": _FakeSerialModule.EIGHTBITS,
            "parity": _FakeSerialModule.PARITY_NONE,
            "stopbits": _FakeSerialModule.STOPBITS_ONE,
            "timeout": 0,
            "write_timeout": 0,
            "rtscts": False,
            "dsrdtr": False,
            "xonxoff": False,
        }
    ]


@pytest.mark.parametrize("code", [1, 55, 127, 128, 255])
def test_serial_backend_writes_exactly_one_byte_for_event_codes(code: int) -> None:
    serial_module = _FakeSerialModule()
    backend = SerialBackend("COM3", 115200, serial_module=serial_module)

    backend.connect()
    backend.send(code)

    assert serial_module.port.writes == [bytes([code])]


def test_serial_backend_reset_is_noop_by_default_and_manual_reset_writes_zero() -> None:
    serial_module = _FakeSerialModule()
    backend = SerialBackend("COM3", 115200, serial_module=serial_module)

    backend.connect()
    backend.reset()

    assert serial_module.port.writes == []

    manual_reset_backend = SerialBackend(
        "COM3",
        115200,
        reset_code=0,
        serial_module=serial_module,
    )
    manual_reset_backend.connect()
    manual_reset_backend.reset()

    assert serial_module.port.writes == [bytes([0])]


def test_serial_backend_close_is_idempotent() -> None:
    serial_module = _FakeSerialModule()
    backend = SerialBackend("COM3", 115200, serial_module=serial_module)

    backend.connect()
    backend.close()
    backend.close()

    assert serial_module.port.closed is True


def test_serial_backend_reports_missing_pyserial(monkeypatch) -> None:
    def _missing_serial(_name: str) -> object:
        raise ModuleNotFoundError("serial")

    monkeypatch.setattr(importlib, "import_module", _missing_serial)
    backend = SerialBackend("COM3", 115200)

    with pytest.raises(RuntimeError, match="pyserial is required"):
        backend.connect()


def test_serial_backend_reports_open_and_write_failures() -> None:
    open_failure_backend = SerialBackend(
        "COM3",
        115200,
        serial_module=_FakeSerialModule(fail_open=True),
    )
    with pytest.raises(RuntimeError, match="Unable to open serial trigger port"):
        open_failure_backend.connect()

    write_failure_backend = SerialBackend(
        "COM3",
        115200,
        serial_module=_FakeSerialModule(fail_writes=True),
    )
    write_failure_backend.connect()
    with pytest.raises(RuntimeError, match="Unable to send trigger code 8"):
        write_failure_backend.send_trigger(8)


@pytest.mark.parametrize("bytes_written", [0, 2])
def test_serial_backend_reports_short_or_extra_writes(bytes_written: int) -> None:
    backend = SerialBackend(
        "COM3",
        115200,
        serial_module=_FakeSerialModule(bytes_written=bytes_written),
    )
    backend.connect()

    with pytest.raises(RuntimeError, match="expected 1"):
        backend.send_trigger(8)


@pytest.mark.parametrize("code", [-1, 0, 256, None, "55"])
def test_serial_backend_rejects_invalid_event_codes(code: object) -> None:
    backend = SerialBackend("COM3", 115200, serial_module=_FakeSerialModule())
    backend.connect()

    with pytest.raises((TypeError, ValueError), match="1 to 255"):
        backend.send_trigger(code)  # type: ignore[arg-type]


def test_runtime_selects_logged_serial_backend_when_port_is_configured(monkeypatch) -> None:
    created: dict[str, object] = {}

    class _FakeSerialBackend(TriggerBackend):
        def __init__(
            self,
            port: str = "COM3",
            baudrate: int = 115200,
            *,
            pulse_width_ms: int,
            reset_code: int | None,
            reset_delay_ms: int,
        ) -> None:
            created.update(
                {
                    "port": port,
                    "baudrate": baudrate,
                    "pulse_width_ms": pulse_width_ms,
                    "reset_code": reset_code,
                    "reset_delay_ms": reset_delay_ms,
                }
            )

        def connect(self) -> None:
            created["connected"] = True

        def send_trigger(
            self,
            code: int,
            *,
            frame_index: int | None = None,
            label: str | None = None,
            time_s: float | None = None,
        ) -> None:
            created["sent"] = (code, frame_index, label, time_s)

        def reset(self) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr("fpvs_studio.runtime.triggers.SerialBackend", _FakeSerialBackend)

    backend, warnings = build_trigger_backend(
        {
            "serial_enabled": True,
            "serial_port": " COM3 ",
            "serial_baudrate": 57600,
            "serial_pulse_width_ms": 2,
            "serial_reset_code": None,
            "serial_reset_delay_ms": 0,
        }
    )
    backend.connect()
    backend.send_trigger(21, frame_index=5, label="oddball_onset", time_s=0.25)

    assert warnings == []
    assert backend.backend_name == "serial"
    assert created == {
        "port": "COM3",
        "baudrate": 57600,
        "pulse_width_ms": 2,
        "reset_code": None,
        "reset_delay_ms": 0,
        "connected": True,
        "sent": (21, 5, "oddball_onset", 0.25),
    }
    assert backend.records[0].backend_name == "serial"
    assert backend.records[0].status == "sent"


def test_runtime_uses_null_backend_when_serial_output_is_disabled() -> None:
    backend, warnings = build_trigger_backend({"serial_enabled": False, "serial_port": "COM3"})

    backend.connect()
    backend.send_trigger(1, frame_index=0, label="condition_start", time_s=0.0)

    assert warnings == []
    assert backend.backend_name == "null"
    assert backend.records[0].backend_name == "null"
    assert backend.records[0].status == "skipped_disabled"


def test_runtime_uses_default_serial_port_when_enabled_without_explicit_port(monkeypatch) -> None:
    created: dict[str, object] = {}

    class _FakeSerialBackend(TriggerBackend):
        def __init__(
            self,
            port: str = "COM3",
            baudrate: int = 115200,
            **_kwargs: object,
        ) -> None:
            created.update({"port": port, "baudrate": baudrate})

        def connect(self) -> None:
            return None

        def send_trigger(
            self,
            code: int,
            *,
            frame_index: int | None = None,
            label: str | None = None,
            time_s: float | None = None,
        ) -> None:
            return None

        def reset(self) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr("fpvs_studio.runtime.triggers.SerialBackend", _FakeSerialBackend)

    backend, _warnings = build_trigger_backend({"serial_enabled": True, "serial_port": None})

    assert backend.backend_name == "serial"
    assert created == {"port": "COM3", "baudrate": 115200}


def test_runtime_records_error_and_reraises_serial_write_failures() -> None:
    class _FailingBackend(TriggerBackend):
        def connect(self) -> None:
            return None

        def send_trigger(
            self,
            code: int,
            *,
            frame_index: int | None = None,
            label: str | None = None,
            time_s: float | None = None,
        ) -> None:
            raise RuntimeError("write failed")

        def reset(self) -> None:
            return None

        def close(self) -> None:
            return None

    from fpvs_studio.runtime.triggers import LoggedTriggerBackend

    backend = LoggedTriggerBackend(_FailingBackend(), backend_name="serial")

    with pytest.raises(RuntimeError, match="write failed"):
        backend.send_trigger(55, frame_index=10, label="oddball_onset", time_s=0.5)

    assert backend.records[0].status == "error"
    assert backend.records[0].message == "write failed"
