"""Generic serial selection/access checks with fake metadata and connections only."""

from __future__ import annotations

import errno
import logging
import sys
from dataclasses import FrozenInstanceError
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fpvs_studio.triggers import serial_port_access as access
from fpvs_studio.triggers.serial_errors import serial_failure_reason


@pytest.mark.parametrize("error", [
    PermissionError(13, "Access is denied."),
    OSError("could not open port 'COM4': PermissionError(13, 'Access is denied.', None, 5)"),
    "could not open port 'COM4': PermissionError(13, 'Zugriff verweigert', None, 5)",
    "[WinError 5] Access is denied.",
    "[Errno 13] Permission denied",
    "[Errno 1] Operation not permitted",
    "[Errno 16] Device or resource busy",
    "[WinError 32] Sharing violation",
])
def test_recognizes_native_and_pyserial_access_denied_errors(error):
    assert access.is_serial_access_denied(error)


@pytest.mark.parametrize("error", [
    FileNotFoundError(2, "The system cannot find the file specified."),
    "could not open port 'COM4': FileNotFoundError(2, 'Missing', None, 2)",
    "[WinError 50] Not supported", "Invalid baudrate", "close failed",
])
def test_other_serial_failures_are_not_reported_as_access_denied(error):
    assert not access.is_serial_access_denied(error)


@pytest.mark.parametrize("error, expected", [
    (TimeoutError(errno.ETIMEDOUT, "Zeitlimit erreicht"), "timeout"),
    (OSError(errno.ENODEV, "Device unavailable"), "device_io"),
    (OSError(errno.ENXIO, "Device unavailable"), "device_io"),
    ("could not open: PermissionError(13, 'Zugriff verweigert', None, 5)", "busy"),
    ("could not open: FileNotFoundError(2, 'Nicht gefunden', None, 3)", "missing"),
    ("Cannot configure port: PermissionError(13, 'Denied', None, 5)", "configuration"),
    ("[WinError 2] Missing. Closing the port also failed: [WinError 5] Denied", "close"),
    ("[WinError 170] Device in use", "busy"),
    ("[WinError 33] Lock violation", "busy"),
    ("[WinError 1460] Zeitlimit erreicht", "timeout"),
    ("[WinError 995] Operation aborted", "device_io"),
    (OSError(errno.EINVAL, "Unknown argument failure"), "unknown"),
])
def test_serial_failure_reasons_survive_access_check_serialization(error, expected):
    assert serial_failure_reason(error) == expected
    assert serial_failure_reason(str(error)) == expected


def _metadata(monkeypatch, ports):
    calls = []

    def import_module(name):
        calls.append(name)
        assert name == "serial.tools.list_ports"
        return SimpleNamespace(comports=lambda: ports)

    monkeypatch.setattr(access.importlib, "import_module", import_module)
    return calls


def test_enumeration_keeps_generic_names_and_non_com_ports_without_opening(monkeypatch):
    calls = _metadata(monkeypatch, [
        SimpleNamespace(device="COM193", description="USB Serial Port (COM193)"),
        SimpleNamespace(device=" com2 ", description="  USB   Serial Converter "),
        SimpleNamespace(device="/dev/ttyUSB0", product="Generic USB interface"),
        SimpleNamespace(device="COM10", description=None),
        SimpleNamespace(device="COM2", description="Duplicate driver entry"),
    ])

    assert access.enumerate_serial_ports() == (
        access.SerialPortInfo("COM2", "USB Serial Converter"),
        access.SerialPortInfo("COM10", ""),
        access.SerialPortInfo("COM193", "USB Serial Port (COM193)"),
        access.SerialPortInfo("/dev/ttyUSB0", "Generic USB interface"),
    )
    assert calls == ["serial.tools.list_ports"]


def test_enumeration_preserves_case_sensitive_device_paths(monkeypatch):
    _metadata(monkeypatch, [
        SimpleNamespace(device=name) for name in ("/dev/ttyUSB0", "/dev/ttyusb0")
    ])

    assert [info.port for info in access.enumerate_serial_ports()] == [
        "/dev/ttyUSB0", "/dev/ttyusb0",
    ]


@pytest.mark.parametrize("info", [None, SimpleNamespace(), SimpleNamespace(device=None),
                                        SimpleNamespace(device=3), SimpleNamespace(device=" \t ")])
def test_enumeration_ignores_missing_device_names(monkeypatch, info):
    _metadata(monkeypatch, [info])

    assert access.enumerate_serial_ports() == ()


def test_no_ports_is_an_empty_result(monkeypatch):
    calls = _metadata(monkeypatch, [])

    assert access.enumerate_serial_ports() == ()
    assert calls == ["serial.tools.list_ports"]


@pytest.mark.parametrize("operation", [access.enumerate_serial_ports,
                                       lambda: access.check_serial_port_access("COM193")])
@pytest.mark.parametrize("error_type", [ModuleNotFoundError, ImportError])
def test_missing_pyserial_has_an_explicit_dependency_error(monkeypatch, operation, error_type):
    monkeypatch.setattr(access.importlib, "import_module", Mock(side_effect=error_type()))

    with pytest.raises(access.SerialPortAccessError, match="pyserial is required"):
        operation()


@pytest.mark.parametrize("injected", [False, True])
@pytest.mark.parametrize("defect", ["Serial", "EIGHTBITS", "PARITY_NONE", "STOPBITS_ONE",
                                    "noncallable Serial"])
def test_incomplete_serial_support_is_a_dependency_failure_before_port_access(
    monkeypatch, injected, defect,
):
    factory = Mock(side_effect=AssertionError("Incomplete serial support must not open a port"))
    attributes = {"Serial": factory, "EIGHTBITS": 8, "PARITY_NONE": "N", "STOPBITS_ONE": 1}
    if defect == "noncallable Serial":
        attributes["Serial"] = None
    else:
        del attributes[defect]
    module = SimpleNamespace(**attributes)
    load = Mock(return_value=module)
    monkeypatch.setattr(access.importlib, "import_module", load)

    with pytest.raises(access.SerialPortAccessError, match="pyserial is required") as failure:
        access.check_serial_port_access("COM4", serial_module=module if injected else None)

    assert isinstance(failure.value.__cause__, (AttributeError, ImportError))
    factory.assert_not_called()
    assert load.call_count == (0 if injected else 1)


@pytest.mark.parametrize("during_iteration", [False, True])
def test_enumeration_failure_does_not_return_partial_choices(monkeypatch, during_iteration):
    failure = OSError("Driver metadata unavailable")

    def records():
        yield SimpleNamespace(device="COM3")
        raise failure

    def comports():
        if during_iteration:
            return records()
        raise failure

    monkeypatch.setattr(
        access.importlib, "import_module", lambda _: SimpleNamespace(comports=comports),
    )

    with pytest.raises(access.SerialPortAccessError, match="enumerate serial ports") as caught:
        access.enumerate_serial_ports()
    assert caught.value.__cause__ is failure


def test_cancelled_enumeration_stops_between_choices(monkeypatch):
    cancel = Event()

    def records():
        yield SimpleNamespace(device="COM2")
        cancel.set()
        yield SimpleNamespace(device="COM3")
        pytest.fail("Enumeration continued after cancellation")

    _metadata(monkeypatch, records())

    with pytest.raises(InterruptedError, match="cancelled"):
        access.enumerate_serial_ports(cancel_event=cancel)


def _serial(monkeypatch, *, baudrate=115200, open_error=None, close_error=None,
            configuration_error=None, cancel=None, cancel_stage=None):
    connections = []
    imports = []

    class Connection:
        def __init__(self, **settings):
            assert settings == {
                "port": None, "baudrate": baudrate, "bytesize": 8, "parity": "N",
                "stopbits": 1, "timeout": 0, "write_timeout": 0, "rtscts": False,
                "dsrdtr": False, "xonxoff": False,
            }
            self._port = None
            self.rts = True
            self.dtr = True
            self.open_attempted = False
            self.close_attempted = False
            connections.append(self)
            if cancel_stage == "construct":
                cancel.set()

        @property
        def port(self):
            return self._port

        @port.setter
        def port(self, value):
            self._port = value
            if configuration_error:
                raise configuration_error

        def open(self):
            assert self.port is not None and self.rts is False and self.dtr is False
            self.open_attempted = True
            if cancel_stage == "open":
                cancel.set()
            if open_error:
                raise open_error

        def close(self):
            self.close_attempted = True
            if cancel_stage == "close":
                cancel.set()
            if close_error:
                raise close_error

        def __getattr__(self, name):
            pytest.fail(f"Access checks must not use serial {name}")

    module = SimpleNamespace(Serial=Connection, EIGHTBITS=8, PARITY_NONE="N", STOPBITS_ONE=1)

    def import_module(name):
        imports.append(name)
        assert name == "serial", "A selected-port check must not enumerate or probe other ports"
        return module

    monkeypatch.setattr(access.importlib, "import_module", import_module)
    return connections, imports


@pytest.mark.parametrize("baudrate", [115200, 9600])
def test_check_opens_only_the_selected_manual_port_at_configured_baud(monkeypatch, baudrate):
    connections, imports = _serial(monkeypatch, baudrate=baudrate)

    result = access.check_serial_port_access(" COM193 ", baudrate=baudrate)

    assert result == access.SerialPortAccessResult("COM193", True)
    assert imports == ["serial"]
    assert len(connections) == 1 and connections[0].port == "COM193"
    assert connections[0].open_attempted and connections[0].close_attempted


def test_failed_open_is_closed_and_reported_without_trying_another_port(monkeypatch):
    connections, _ = _serial(monkeypatch, open_error=OSError("Port is busy"))

    result = access.check_serial_port_access("COM193")

    assert result == access.SerialPortAccessResult("COM193", False, "Port is busy")
    assert len(connections) == 1 and connections[0].close_attempted


def test_configuration_failure_closes_constructed_connection_without_open(monkeypatch):
    connections, _ = _serial(monkeypatch, configuration_error=OSError("Cannot configure port"))

    result = access.check_serial_port_access("COM193")

    assert result.accessible is False and "Cannot configure port" in result.access_error
    assert not connections[0].open_attempted and connections[0].close_attempted


def test_value_error_configuration_context_survives_access_result(monkeypatch):
    connections, _ = _serial(monkeypatch, configuration_error=ValueError("Unsupported setting"))

    result = access.check_serial_port_access("COM193")

    assert not result.accessible
    assert result.access_error == "Cannot configure port: Unsupported setting"
    assert serial_failure_reason(result.access_error) == "configuration"
    assert not connections[0].open_attempted and connections[0].close_attempted


@pytest.mark.skipif(sys.platform != "win32", reason="Native pyserial Windows configuration")
@pytest.mark.parametrize("error_code", [5, 87])
def test_native_configuration_rejection_closes_handles_without_port_or_marker_io(
    monkeypatch, error_code,
):
    import ctypes

    import serial
    from serial import serialwin32

    native_error = ctypes.WinError(error_code)
    open_port = Mock(return_value=123456)
    events = Mock(side_effect=[234567, 345678])
    close_handle = Mock(return_value=True)
    write = Mock(side_effect=AssertionError("Access checks must not send marker bytes"))
    purge = Mock(side_effect=AssertionError("Rejected configuration must not reach buffer setup"))
    monkeypatch.setattr(serialwin32.win32, "CreateFile", open_port)
    monkeypatch.setattr(serialwin32.win32, "CreateEvent", events)
    monkeypatch.setattr(serialwin32.win32, "CloseHandle", close_handle)
    for name in ("SetupComm", "GetCommTimeouts", "SetCommTimeouts", "SetCommMask",
                 "GetCommState", "CancelIoEx"):
        monkeypatch.setattr(serialwin32.win32, name, Mock(return_value=True))
    monkeypatch.setattr(serialwin32.win32, "SetCommState", Mock(return_value=False))
    monkeypatch.setattr(serialwin32.win32, "WriteFile", write)
    monkeypatch.setattr(serialwin32.win32, "PurgeComm", purge)
    monkeypatch.setattr(serialwin32, "ctypes", SimpleNamespace(
        WinError=lambda: native_error, byref=ctypes.byref,
    ))

    result = access.check_serial_port_access("COM193", serial_module=serial)

    assert not result.accessible
    assert "Cannot configure port" in result.access_error
    assert repr(native_error) in result.access_error
    assert serial_failure_reason(result.access_error) == "configuration"
    assert not access.is_serial_access_denied(result.access_error)
    open_port.assert_called_once()
    assert open_port.call_args.args[0] == r"\\.\COM193"
    assert [call.args[0] for call in close_handle.call_args_list] == [234567, 345678, 123456]
    write.assert_not_called()
    purge.assert_not_called()


@pytest.mark.parametrize("open_error", [None, OSError("Open denied")])
def test_close_failure_cannot_report_accessible_and_preserves_open_error(monkeypatch, open_error):
    connections, _ = _serial(
        monkeypatch, open_error=open_error, close_error=OSError("Close denied"),
    )

    result = access.check_serial_port_access("COM193")

    assert result.accessible is False and "Close denied" in result.access_error
    if open_error:
        assert "Open denied" in result.access_error
    assert connections[0].close_attempted


def test_empty_construction_error_remains_actionable(monkeypatch):
    monkeypatch.setattr(access.importlib, "import_module", lambda _: SimpleNamespace(
        Serial=Mock(side_effect=RuntimeError()), EIGHTBITS=8, PARITY_NONE="N", STOPBITS_ONE=1,
    ))

    assert access.check_serial_port_access("COM193") == access.SerialPortAccessResult(
        "COM193", False, "RuntimeError",
    )


@pytest.mark.parametrize("stage", ["construct", "open", "close"])
def test_cancellation_always_closes_constructed_connection(monkeypatch, stage):
    cancel = Event()
    connections, _ = _serial(monkeypatch, cancel=cancel, cancel_stage=stage)

    with pytest.raises(InterruptedError, match="cancelled"):
        access.check_serial_port_access("COM193", cancel_event=cancel)
    assert connections[0].close_attempted
    assert connections[0].open_attempted is (stage != "construct")


@pytest.mark.parametrize("stage", ["construct", "open", "close"])
def test_cancelled_access_check_retains_close_failure_in_log(monkeypatch, caplog, stage):
    cancel = Event()
    close_error = OSError("Driver refused to close")
    connections, _ = _serial(
        monkeypatch, cancel=cancel, cancel_stage=stage,
        open_error=PermissionError(13, "Access denied"), close_error=close_error,
    )

    with caplog.at_level(logging.ERROR), pytest.raises(InterruptedError, match="cancelled"):
        access.check_serial_port_access("COM193", cancel_event=cancel)

    assert connections[0].close_attempted
    record, = [record for record in caplog.records if record.name == access.__name__]
    assert "COM193" in record.getMessage()
    assert "access check" in record.getMessage()
    assert record.exc_info[1] is close_error
    if stage != "construct":
        assert "Access denied" in record.getMessage()


@pytest.mark.parametrize("operation", [
    access.enumerate_serial_ports,
    lambda **kw: access.check_serial_port_access("COM193", **kw),
])
def test_pre_cancelled_operations_do_not_import_or_access_serial(monkeypatch, operation):
    cancel = Event()
    cancel.set()
    load = Mock(side_effect=AssertionError("Cancelled work must not load serial"))
    monkeypatch.setattr(access.importlib, "import_module", load)

    with pytest.raises(InterruptedError, match="cancelled"):
        operation(cancel_event=cancel)
    load.assert_not_called()


@pytest.mark.parametrize("port", [None, "", " \t ", 193])
def test_invalid_port_fails_before_import_or_access(monkeypatch, port):
    load = Mock(side_effect=AssertionError("Invalid work must not load serial"))
    monkeypatch.setattr(access.importlib, "import_module", load)

    with pytest.raises(ValueError, match="nonblank text"):
        access.check_serial_port_access(port)
    load.assert_not_called()


@pytest.mark.parametrize("baudrate", [0, -1, True, "115200", 115200.0])
def test_invalid_baud_fails_before_import_or_access(monkeypatch, baudrate):
    load = Mock(side_effect=AssertionError("Invalid work must not load serial"))
    monkeypatch.setattr(access.importlib, "import_module", load)

    with pytest.raises(ValueError, match="positive integer"):
        access.check_serial_port_access("COM193", baudrate=baudrate)
    load.assert_not_called()


@pytest.mark.parametrize("result", [access.SerialPortInfo("COM3", "USB Serial Port"),
                                   access.SerialPortAccessResult("COM3", True)])
def test_results_are_immutable(result):
    with pytest.raises(FrozenInstanceError):
        result.port = "COM193"
