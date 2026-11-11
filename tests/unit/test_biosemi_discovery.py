"""Identify BioSemi ports from metadata or a single controlled reconnect."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fpvs_studio.triggers import serial_port_access
from fpvs_studio.triggers.biosemi_discovery import (
    biosemi_reconnected_port,
    discover_biosemi_ports,
    enumerate_com_ports,
)
from fpvs_studio.triggers.serial_port_access import SerialPortAccessError


def test_named_discovery_filters_generic_ports_and_receivers_without_opening(monkeypatch):
    ports = [
        SimpleNamespace(device="COM40", product="BioSemi USB Trigger Interface"),
        SimpleNamespace(device="COM3", description="USB Serial Port (COM3)",
                        vid=0x0403, pid=0x6001),
        SimpleNamespace(device="COM4", description="USB Serial Converter"),
        SimpleNamespace(device="COM5", description="BioSemi USB Receiver (COM5)"),
        SimpleNamespace(device="COM6", description="BioSemi USB Trigger Interface Diagnostics"),
        SimpleNamespace(device="com7", description="BIOSEMI USB Trigger Interface (com7)"),
        SimpleNamespace(device="/dev/ttyUSB0", description="BioSemi USB Trigger Interface"),
    ]
    importer = Mock(return_value=SimpleNamespace(comports=lambda: ports))
    monkeypatch.setattr(serial_port_access.importlib, "import_module", importer)

    assert discover_biosemi_ports() == ("COM7", "COM40")
    assert enumerate_com_ports() == frozenset({"COM3", "COM4", "COM5", "COM6", "COM7", "COM40"})
    assert [call.args for call in importer.call_args_list] == [
        ("serial.tools.list_ports",), ("serial.tools.list_ports",),
    ]


def test_reconnect_returns_only_added_port():
    assert biosemi_reconnected_port(frozenset({"COM3"}), frozenset({"COM3", "COM9"})) == "COM9"


def test_reconnect_requires_new_port():
    ports = frozenset({"COM3"})
    with pytest.raises(SerialPortAccessError, match="No new serial port appeared"):
        biosemi_reconnected_port(ports, ports)


@pytest.mark.parametrize("connected", [{"COM3", "COM8", "COM9"}, {"COM8"}, set()])
def test_reconnect_refuses_unrelated_additions_and_removals(connected):
    with pytest.raises(SerialPortAccessError, match="Other serial ports changed"):
        biosemi_reconnected_port(frozenset({"COM3"}), frozenset(connected))
