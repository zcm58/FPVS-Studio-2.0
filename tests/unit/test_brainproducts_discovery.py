"""TriggerBox discovery/access checks using only synthetic device metadata and ports."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fpvs_studio.triggers import brainproducts_discovery as discovery


def _fake_ports(
    monkeypatch: pytest.MonkeyPatch, ports: list[object], *, serial_module: object | None = None,
) -> list[str]:
    calls: list[str] = []

    def _comports() -> list[object]:
        calls.append("comports")
        return ports

    module = SimpleNamespace(comports=_comports)

    def _import(name: str) -> object:
        calls.append(name)
        if name == "serial" and serial_module is not None:
            return serial_module
        assert name == "serial.tools.list_ports"
        return module

    monkeypatch.setattr(discovery.importlib, "import_module", _import)
    return calls


def test_no_ports_is_an_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _fake_ports(monkeypatch, [])

    assert discovery.discover_triggerbox_ports() == ()
    assert calls == ["serial.tools.list_ports", "comports"]


@pytest.mark.parametrize(
    "name",
    [
        "TriggerBox",
        "TriggerBox rev.02",
        "TriggerBox VirtualSerial Port (COM8)",
        "TriggerBox Virtual Serial Port (COM8)",
        "TriggerBox Plus",
        "TriggerBox Plus VirtualSerial Port (COM8)",
        "TriggerBox Plus Virtual Serial Port (COM8)",
        "Brain Products TriggerBox Plus",
        "Brain Products GmbH TriggerBox",
    ],
)
def test_recognizes_explicit_triggerbox_names(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    calls = _fake_ports(monkeypatch, [SimpleNamespace(device="COM8", description=name)])

    assert discovery.discover_triggerbox_ports() == (
        discovery.TriggerBoxPortCandidate("COM8", name),
    )
    # The fake module has no serial-open API. Discovery asks only for metadata.
    assert calls == ["serial.tools.list_ports", "comports"]


@pytest.mark.parametrize(
    "name",
    [
        "USB Serial Port (COM8)",
        "Brain Products",
        "BrainAmp",
        "Brain Products BrainAmp",
        "TriggerBox Debug Interface",
        "Not a TriggerBox",
        "OtherTriggerBox",
    ],
)
def test_does_not_guess_other_serial_devices(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    _fake_ports(
        monkeypatch,
        [SimpleNamespace(device="COM8", description=name, manufacturer="Brain Products")],
    )

    assert discovery.discover_triggerbox_ports() == ()


def test_recognizes_product_name_when_driver_description_is_generic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_ports(
        monkeypatch,
        [
            SimpleNamespace(
                device=" com8 ", description="USB Serial Device (COM8)", product="TriggerBox Plus"
            )
        ],
    )

    assert discovery.discover_triggerbox_ports() == (
        discovery.TriggerBoxPortCandidate("COM8", "TriggerBox Plus"),
    )


def test_deduplicates_ports_and_sorts_naturally(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_ports(
        monkeypatch,
        [
            SimpleNamespace(device=port, description="TriggerBox")
            for port in ["COM10", "com2", "COM1", "COM2", "COM22"]
        ],
    )

    assert [candidate.port for candidate in discovery.discover_triggerbox_ports()] == [
        "COM1", "COM2", "COM10", "COM22"
    ]


@pytest.mark.parametrize(
    "info",
    [
        None,
        SimpleNamespace(),
        SimpleNamespace(device=None, description="TriggerBox"),
        SimpleNamespace(device="COM8", description=None, product=123),
        SimpleNamespace(device=8, description="TriggerBox"),
        SimpleNamespace(device="/dev/ttyUSB0", description="TriggerBox"),
        SimpleNamespace(device="COM0", description="TriggerBox"),
        SimpleNamespace(device="COM8 invalid", description="TriggerBox"),
    ],
)
def test_ignores_incomplete_or_non_com_metadata(
    monkeypatch: pytest.MonkeyPatch, info: object
) -> None:
    _fake_ports(monkeypatch, [info])

    assert discovery.discover_triggerbox_ports() == ()


def test_candidate_is_immutable() -> None:
    candidate = discovery.TriggerBoxPortCandidate("COM8", "TriggerBox")

    with pytest.raises(FrozenInstanceError):
        candidate.port = "COM3"  # type: ignore[misc]


def test_missing_pyserial_is_an_explicit_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _missing(_name: str) -> object:
        raise ModuleNotFoundError("serial")

    monkeypatch.setattr(discovery.importlib, "import_module", _missing)

    with pytest.raises(discovery.TriggerBoxDiscoveryError, match="pyserial is required"):
        discovery.discover_triggerbox_ports()


@pytest.mark.parametrize("during_iteration", [False, True])
def test_enumeration_failure_is_an_explicit_error(
    monkeypatch: pytest.MonkeyPatch, during_iteration: bool
) -> None:
    failure = OSError("device metadata unavailable")

    def _iterator():
        yield SimpleNamespace(device="COM8", description="TriggerBox")
        raise failure

    def _comports():
        if during_iteration:
            return _iterator()
        raise failure

    monkeypatch.setattr(
        discovery.importlib, "import_module", lambda _name: SimpleNamespace(comports=_comports)
    )

    with pytest.raises(discovery.TriggerBoxDiscoveryError, match="enumerate serial ports") as error:
        discovery.discover_triggerbox_ports()
    assert error.value.__cause__ is failure


def _fake_serial_module(
    *, open_errors=None, close_errors=None, on_open=None, on_close=None, configuration_error=None,
):
    connections = []

    class Connection:
        def __init__(self, **settings):
            assert settings == {
                "port": None, "baudrate": 2_000_000, "bytesize": 8, "parity": "N",
                "stopbits": 1, "timeout": 0, "write_timeout": 0,
                "rtscts": False, "dsrdtr": False, "xonxoff": False,
            }
            self._port = None
            self.rts = True
            self.dtr = True
            self.open_attempted = False
            self.close_attempted = False
            connections.append(self)

        @property
        def port(self):
            return self._port

        @port.setter
        def port(self, value):
            self._port = value
            if configuration_error is not None:
                raise configuration_error

        def open(self):
            assert self.port is not None
            assert self.rts is False
            assert self.dtr is False
            self.open_attempted = True
            if on_open is not None:
                on_open(self.port)
            if self.port in (open_errors or {}):
                raise open_errors[self.port]

        def close(self):
            self.close_attempted = True
            if on_close is not None:
                on_close(self.port)
            if self.port in (close_errors or {}):
                raise close_errors[self.port]

        def __getattr__(self, name):
            pytest.fail(f"Access checks must not call serial {name}")

    module = SimpleNamespace(Serial=Connection, EIGHTBITS=8, PARITY_NONE="N", STOPBITS_ONE=1)
    return module, connections


def test_explicit_access_check_opens_only_recognized_deduplicated_ports(monkeypatch):
    module, connections = _fake_serial_module()
    calls = _fake_ports(monkeypatch, [
        SimpleNamespace(device="COM10", description="TriggerBox Plus"),
        SimpleNamespace(device="COM2", description="TriggerBox Virtual Serial Port"),
        SimpleNamespace(device="com2", description="TriggerBox"),
        SimpleNamespace(device="COM3", description="USB Serial Port"),
    ], serial_module=module)

    result = discovery.discover_triggerbox_ports(check_access=True)

    assert result == (
        discovery.TriggerBoxPortCandidate("COM2", "TriggerBox Virtual Serial Port", True),
        discovery.TriggerBoxPortCandidate("COM10", "TriggerBox Plus", True),
    )
    assert [connection.port for connection in connections] == ["COM2", "COM10"]
    assert all(
        connection.open_attempted and connection.close_attempted for connection in connections
    )
    assert calls == ["serial.tools.list_ports", "comports", "serial"]


def test_failed_port_is_closed_and_does_not_hide_other_candidates(monkeypatch):
    module, connections = _fake_serial_module(open_errors={"COM2": OSError("Port is busy")})
    _fake_ports(monkeypatch, [
        SimpleNamespace(device=port, description="TriggerBox") for port in ("COM2", "COM9")
    ], serial_module=module)

    result = discovery.discover_triggerbox_ports(check_access=True)

    assert result == (
        discovery.TriggerBoxPortCandidate("COM2", "TriggerBox", False, "Port is busy"),
        discovery.TriggerBoxPortCandidate("COM9", "TriggerBox", True),
    )
    assert all(connection.close_attempted for connection in connections)


@pytest.mark.parametrize("open_error", [None, OSError("Open denied")])
def test_close_failure_is_reported_instead_of_claiming_access(monkeypatch, open_error):
    module, connections = _fake_serial_module(
        open_errors={"COM8": open_error} if open_error else {},
        close_errors={"COM8": OSError("Close denied")},
    )
    _fake_ports(monkeypatch, [SimpleNamespace(device="COM8", description="TriggerBox")],
                serial_module=module)

    result, = discovery.discover_triggerbox_ports(check_access=True)

    assert result.accessible is False
    assert "Close denied" in result.access_error
    if open_error:
        assert "Open denied" in result.access_error
    assert connections[0].close_attempted


def test_configuration_failure_closes_constructed_connection_without_open(monkeypatch):
    module, connections = _fake_serial_module(configuration_error=OSError("Invalid settings"))
    _fake_ports(monkeypatch, [SimpleNamespace(device="COM8", description="TriggerBox")],
                serial_module=module)

    result, = discovery.discover_triggerbox_ports(check_access=True)

    assert result.accessible is False
    assert result.access_error == "Invalid settings"
    assert not connections[0].open_attempted
    assert connections[0].close_attempted


@pytest.mark.parametrize("stage", ["open", "close"])
def test_cancel_closes_active_candidate_and_does_not_open_next(monkeypatch, stage):
    cancel = Event()
    module, connections = _fake_serial_module(**{f"on_{stage}": lambda _port: cancel.set()})
    _fake_ports(monkeypatch, [
        SimpleNamespace(device=port, description="TriggerBox") for port in ("COM2", "COM9")
    ], serial_module=module)

    with pytest.raises(InterruptedError, match="cancelled"):
        discovery.discover_triggerbox_ports(check_access=True, cancel_event=cancel)

    assert len(connections) == 1
    assert connections[0].open_attempted
    assert connections[0].close_attempted


def test_pre_cancelled_discovery_does_not_enumerate_or_open(monkeypatch):
    cancel = Event()
    cancel.set()
    fake_import = Mock(side_effect=AssertionError("Cancelled discovery must not import serial"))
    monkeypatch.setattr(discovery.importlib, "import_module", fake_import)

    with pytest.raises(InterruptedError, match="cancelled"):
        discovery.discover_triggerbox_ports(check_access=True, cancel_event=cancel)

    fake_import.assert_not_called()


def test_empty_explicit_discovery_does_not_import_serial_or_open_ports(monkeypatch):
    calls = _fake_ports(monkeypatch, [
        SimpleNamespace(device="COM3", description="USB Serial Port"),
    ])

    assert discovery.discover_triggerbox_ports(check_access=True) == ()
    assert calls == ["serial.tools.list_ports", "comports"]


def test_serial_import_failure_is_an_explicit_access_check_error(monkeypatch):
    def fake_import(name):
        if name == "serial.tools.list_ports":
            return SimpleNamespace(comports=lambda: [
                SimpleNamespace(device="COM8", description="TriggerBox"),
            ])
        raise ModuleNotFoundError("serial")

    monkeypatch.setattr(discovery.importlib, "import_module", fake_import)

    with pytest.raises(discovery.TriggerBoxDiscoveryError, match="pyserial is required to check"):
        discovery.discover_triggerbox_ports(check_access=True)


def test_serial_construction_failure_is_reported_with_a_nonempty_error(monkeypatch):
    module = SimpleNamespace(
        Serial=Mock(side_effect=RuntimeError()),
        EIGHTBITS=8, PARITY_NONE="N", STOPBITS_ONE=1,
    )
    _fake_ports(monkeypatch, [SimpleNamespace(device="COM8", description="TriggerBox")],
                serial_module=module)

    result, = discovery.discover_triggerbox_ports(check_access=True)

    assert result.accessible is False
    assert result.access_error == "RuntimeError"
