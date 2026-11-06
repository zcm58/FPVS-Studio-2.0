"""Serial-port metadata and explicit access checks without device-byte probes."""

from __future__ import annotations

import importlib
import logging
import re
from dataclasses import dataclass
from threading import Event
from types import ModuleType

from fpvs_studio.triggers.serial_errors import serial_failure_reason

_COM_PORT = re.compile(r"COM([1-9]\d*)", re.IGNORECASE)
_LOGGER = logging.getLogger(__name__)


class SerialPortAccessError(RuntimeError):
    """Port enumeration or its optional serial dependency is unavailable."""


@dataclass(frozen=True, slots=True)
class SerialPortInfo:
    """Driver metadata for a choice, without asserting the connected device identity."""

    port: str
    description: str


@dataclass(frozen=True, slots=True)
class SerialPortAccessResult:
    """Whether one selected port could be opened and closed, never marker proof."""

    port: str
    accessible: bool
    access_error: str = ""


def is_serial_access_denied(error: BaseException | str) -> bool:
    """Recognize denied or occupied access, without claiming a particular owner.

    On Windows pyserial embeds repr(PermissionError) inside SerialException text,
    losing its errno. Match the numeric form too, independent of localized wording.
    """

    return serial_failure_reason(error) == "busy"


def enumerate_serial_ports(*, cancel_event: Event | None = None) -> tuple[SerialPortInfo, ...]:
    """List named driver ports without opening them or identifying vendor hardware."""

    _check_cancelled(cancel_event)
    try:
        list_ports = importlib.import_module("serial.tools.list_ports")
    except ImportError as exc:
        raise SerialPortAccessError("pyserial is required to list serial ports.") from exc
    candidates: dict[str, SerialPortInfo] = {}
    try:
        for info in list_ports.comports():
            _check_cancelled(cancel_event)
            value = getattr(info, "device", None)
            if not isinstance(value, str) or not value.strip():
                continue
            port = value.strip()
            if _COM_PORT.fullmatch(port):
                port = port.upper()
            description = _metadata_text(getattr(info, "description", None))
            if not description:
                description = _metadata_text(getattr(info, "product", None))
            candidates.setdefault(port, SerialPortInfo(port, description))
    except InterruptedError:
        raise
    except Exception as exc:
        raise SerialPortAccessError("Unable to enumerate serial ports.") from exc
    _check_cancelled(cancel_event)
    return tuple(candidates[port] for port in sorted(candidates, key=_port_sort_key))


def check_serial_port_access(
    port: str,
    *,
    baudrate: int = 115200,
    cancel_event: Event | None = None,
    serial_module: ModuleType | None = None,
) -> SerialPortAccessResult:
    """Open and close only the requested port, with no explicit byte or buffer I/O.

    This checks OS access rather than hardware identity, wiring or marker receipt.
    Adapters may inject their already-loaded serial module to share the same probe.
    """

    if not isinstance(port, str) or not port.strip():
        raise ValueError("Serial port must be nonblank text.")
    if type(baudrate) is not int or baudrate < 1:
        raise ValueError("Serial baudrate must be a positive integer.")
    port = port.strip()
    _check_cancelled(cancel_event)
    if serial_module is None:
        try:
            serial_module = importlib.import_module("serial")
        except ImportError as exc:
            raise SerialPortAccessError(
                "pyserial is required to check serial port access.",
            ) from exc
    try:
        serial_factory = serial_module.Serial
        bytesize = serial_module.EIGHTBITS
        parity = serial_module.PARITY_NONE
        stopbits = serial_module.STOPBITS_ONE
        if not callable(serial_factory):
            raise ImportError("The serial transport is unavailable.")
    except (ImportError, AttributeError) as exc:
        raise SerialPortAccessError(
            "Studio serial support is unavailable. Repair or reinstall Studio, then try again. "
            "Details: pyserial is required to check serial port access.",
        ) from exc
    connection = None
    error = ""
    try:
        # Set line preferences while closed. The OS/driver may still change those
        # lines during open(), which can also perform its own buffer initialization.
        connection = serial_factory(
            port=None, baudrate=baudrate, bytesize=bytesize,
            parity=parity, stopbits=stopbits,
            timeout=0, write_timeout=0, rtscts=False, dsrdtr=False, xonxoff=False,
        )
        connection.port = port
        connection.rts = False
        connection.dtr = False
        _check_cancelled(cancel_event)
        connection.open()
        _check_cancelled(cancel_event)
    except Exception as exc:
        error = str(exc) or type(exc).__name__
        if isinstance(exc, ValueError):
            error = f"Cannot configure port: {error}"
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception as exc:
                # A dismissed/cancelled GUI job can discard its result. Retain
                # actual cleanup failures here before cancellation supersedes it.
                _LOGGER.exception(
                    "Serial port %s could not be closed after its access check. "
                    "Earlier check error: %s", port, error or "none",
                )
                close_error = str(exc) or type(exc).__name__
                error = (
                    f"{error} Closing the port also failed: {close_error}"
                    if error else f"Unable to close the port: {close_error}"
                )
    _check_cancelled(cancel_event)
    return SerialPortAccessResult(port, accessible=not error, access_error=error)


def _check_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("Serial port operation cancelled.")


def _metadata_text(value: object) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _port_sort_key(port: str) -> tuple[int, int, str, str]:
    match = _COM_PORT.fullmatch(port)
    return (0, int(match[1]), "", "") if match else (1, 0, port.casefold(), port)
