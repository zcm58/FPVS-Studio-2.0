"""Identify named BioSemi interfaces or a port added during an operator reconnect."""

from __future__ import annotations

import re

from fpvs_studio.triggers.serial_port_access import SerialPortAccessError, enumerate_serial_ports

_COM_PATTERN = r"COM[1-9][0-9]*"
_COM_PORT = re.compile(_COM_PATTERN, re.IGNORECASE)
_INTERFACE_NAME = re.compile(
    rf"BioSemi USB Trigger Interface(?: \({_COM_PATTERN}\))?", re.IGNORECASE,
)


def discover_biosemi_ports() -> tuple[str, ...]:
    """Read Windows port names. Generic USB serial labels do not identify BioSemi."""
    return tuple(
        info.port for info in enumerate_serial_ports()
        if _COM_PORT.fullmatch(info.port) and _INTERFACE_NAME.fullmatch(info.description)
    )


def enumerate_com_ports() -> frozenset[str]:
    """Take a Windows COM-port snapshot without opening any device."""
    return frozenset(
        info.port for info in enumerate_serial_ports() if _COM_PORT.fullmatch(info.port)
    )


def biosemi_reconnected_port(disconnected: frozenset[str], connected: frozenset[str]) -> str:
    """Select the only addition after the operator reconnects the trigger interface."""
    added = connected - disconnected
    if disconnected - connected or len(added) > 1:
        raise SerialPortAccessError(
            "Other serial ports changed during detection. Start again and reconnect only "
            "the BioSemi USB Trigger Interface.",
        )
    if not added:
        raise SerialPortAccessError(
            "No new serial port appeared. Reconnect the BioSemi USB Trigger Interface "
            "and try again.",
        )
    return next(iter(added))
