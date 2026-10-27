"""Read-only TriggerBox metadata discovery without enumerating real hardware."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from fpvs_studio.triggers import brainproducts_discovery as discovery


def _fake_ports(monkeypatch: pytest.MonkeyPatch, ports: list[object]) -> list[str]:
    calls: list[str] = []

    def _comports() -> list[object]:
        calls.append("comports")
        return ports

    module = SimpleNamespace(comports=_comports)

    def _import(name: str) -> object:
        calls.append(name)
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
        "TriggerBox Plus",
        "TriggerBox Plus VirtualSerial Port (COM8)",
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
