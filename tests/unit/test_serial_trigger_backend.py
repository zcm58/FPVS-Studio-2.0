"""Serial trigger backend and runtime trigger-selection tests."""

from __future__ import annotations

import importlib

import pytest

from fpvs_studio.runtime.triggers import build_trigger_backend
from fpvs_studio.triggers.base import TriggerBackend
from fpvs_studio.triggers.serial_backend import SerialBackend
from fpvs_studio.triggers.serial_port_access import check_serial_port_access


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
    with pytest.raises(RuntimeError) as error:
        open_failure_backend.connect()
    assert str(error.value) == (
        "FPVS Studio cannot detect the COM3 Serial Port. "
        "Please make sure that your BioSemi system is properly plugged in. "
        "If you would like to run the experiment without being connected to "
        "BioSemi, please navigate to the settings menu and enable test mode."
    )

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
        emits_hardware_triggers = True

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
    backend, warnings = build_trigger_backend(
        {"serial_enabled": False, "serial_port": "COM3", "experiment_test_mode": True},
    )

    backend.connect()
    backend.send_trigger(1, frame_index=0, label="condition_start", time_s=0.0)

    assert warnings == []
    assert backend.backend_name == "null"
    assert backend.records[0].backend_name == "null"
    assert backend.records[0].status == "skipped_disabled"


def test_runtime_uses_default_serial_port_when_enabled_without_explicit_port(monkeypatch) -> None:
    created: dict[str, object] = {}

    class _FakeSerialBackend(TriggerBackend):
        emits_hardware_triggers = True

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
        emits_hardware_triggers = True

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


def test_serial_prevalidated_hot_path_skips_revalidation(monkeypatch) -> None:
    serial_module = _FakeSerialModule()
    backend = SerialBackend("COM3", 115200, serial_module=serial_module)
    backend.connect()

    monkeypatch.setattr(
        "fpvs_studio.triggers.serial_backend.validate_event_trigger_code",
        lambda _code: (_ for _ in ()).throw(AssertionError("unexpected validation")),
    )

    backend.send_prevalidated_trigger(
        55,
        frame_index=10,
        label="oddball_onset",
        time_s=0.5,
    )

    assert serial_module.port.writes == [bytes([55])]


def test_logged_prevalidated_hot_path_defers_model_materialization(monkeypatch) -> None:
    class _RecordingBackend(TriggerBackend):
        emits_hardware_triggers = True

        def __init__(self) -> None:
            self.sent: list[tuple[int, int | None, str | None, float | None]] = []

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
            self.sent.append((code, frame_index, label, time_s))

        def reset(self) -> None:
            return None

        def close(self) -> None:
            return None

    from fpvs_studio.runtime.triggers import LoggedTriggerBackend

    physical_backend = _RecordingBackend()
    backend = LoggedTriggerBackend(physical_backend, backend_name="serial")

    def _unexpected_model_construction(**_kwargs):
        raise AssertionError("validated trigger models belong outside the flip callback")

    monkeypatch.setattr(
        "fpvs_studio.runtime.triggers.TriggerRecord",
        _unexpected_model_construction,
    )

    backend.send_prevalidated_trigger(
        55,
        frame_index=10,
        label="oddball_onset",
        time_s=0.5,
    )

    assert physical_backend.sent == [(55, 10, "oddball_onset", 0.5)]
    with pytest.raises(AssertionError, match="outside the flip callback"):
        _ = backend.records


@pytest.mark.parametrize("selected_backend", ["serial", "biosemi_active_three"])
@pytest.mark.parametrize("prevalidated", [False, True])
def test_biosemi_runtime_preserves_all_byte_values_order_and_repeated_codes(
    monkeypatch, selected_backend, prevalidated,
) -> None:
    """Exercise the real runtime wrapper and byte writer, never a physical port."""

    serial_module = _FakeSerialModule()
    monkeypatch.setattr(
        "fpvs_studio.triggers.serial_backend._load_serial_module", lambda: serial_module,
    )
    backend, warnings = build_trigger_backend({
        "recording_backend": selected_backend,
        "serial_enabled": False,  # Obsolete flags cannot silence explicit normal recording.
        "serial_port": "COM193",
    })
    assert not warnings
    assert backend.backend_name == "serial" and backend.emits_external_markers
    backend.connect()
    assert not serial_module.port.writes
    backend.reset()

    codes = (*range(1, 256), 55, 55, 128, 128, 255, 255)
    send = backend.send_prevalidated_trigger if prevalidated else backend.send_trigger
    for frame, code in enumerate(codes):
        send(code, frame_index=frame, label="wire_regression", time_s=frame / 60)
    backend.reset()
    backend.close()

    # Include the high bit and repeated 55/128/255 markers explicitly. Neither
    # decimal ASCII, a bit shift/mask nor an inserted reset byte is equivalent.
    expected = bytes(range(1, 256)) + b"\x37\x37\x80\x80\xff\xff"
    assert b"".join(serial_module.port.writes) == expected
    assert all(len(payload) == 1 for payload in serial_module.port.writes)
    assert tuple(record.code for record in backend.records) == codes
    assert all(record.status == "sent" for record in backend.records)
    assert serial_module.port.closed


class _ExclusiveSerialPort:
    def __init__(self, module, options):
        self.module = module
        self.port = options["port"]
        self.rts = True
        self.dtr = True
        self.is_open = False
        self.writes = []
        if self.port is not None:
            self.open()

    def open(self):
        if self.port in self.module.active_ports:
            raise OSError("The serial port is already in use")
        self.module.active_ports.add(self.port)
        self.is_open = True

    def write(self, payload):
        assert self.is_open
        self.writes.append(payload)
        return len(payload)

    def close(self):
        self.module.active_ports.discard(self.port)
        self.is_open = False


class _ExclusiveSerialModule:
    EIGHTBITS = 8
    PARITY_NONE = "N"
    STOPBITS_ONE = 1

    def __init__(self):
        self.active_ports = set()
        self.open_calls = []
        self.connections = []

    def Serial(self, **options):  # noqa: N802
        self.open_calls.append(options)
        connection = _ExclusiveSerialPort(self, options)
        self.connections.append(connection)
        return connection


@pytest.mark.parametrize("selected_backend", ["serial", "biosemi_active_three"])
@pytest.mark.parametrize("baudrate", [115200, 57600])
def test_biosemi_port_check_releases_port_before_runtime_byte_output(
    monkeypatch, selected_backend, baudrate,
) -> None:
    """A port availability probe cannot retain the port or mutate marker output."""

    serial_module = _ExclusiveSerialModule()
    result = check_serial_port_access(
        "COM193", baudrate=baudrate, serial_module=serial_module,
    )
    assert result.accessible and not result.access_error
    probe = serial_module.connections[0]
    assert not probe.is_open and not serial_module.active_ports
    assert not probe.writes
    assert probe.rts is False and probe.dtr is False
    assert serial_module.open_calls[0]["port"] is None

    monkeypatch.setattr(
        "fpvs_studio.triggers.serial_backend._load_serial_module", lambda: serial_module,
    )
    backend, warnings = build_trigger_backend({
        "recording_backend": selected_backend,
        "serial_port": " COM193 ",
        "serial_baudrate": baudrate,
    })
    assert not warnings
    backend.connect()  # Fails if the probe did not release its exclusive connection.
    runtime = serial_module.connections[1]
    assert runtime is not probe
    assert serial_module.open_calls[1] == {
        "port": "COM193", "baudrate": baudrate,
        "bytesize": 8, "parity": "N", "stopbits": 1,
        "timeout": 0, "write_timeout": 0,
        "rtscts": False, "dsrdtr": False, "xonxoff": False,
    }
    assert not runtime.writes
    backend.reset()
    for code in (1, 2, 4, 8, 16, 32, 64, 128, 55, 55, 255, 255):
        backend.send_prevalidated_trigger(code, label="wire_regression")
    backend.reset()
    backend.close()

    assert b"".join(runtime.writes) == b"\x01\x02\x04\x08\x10\x20\x40\x80\x37\x37\xff\xff"
    assert all(len(payload) == 1 for payload in runtime.writes)
    assert not serial_module.active_ports and not runtime.is_open
    assert not probe.writes
