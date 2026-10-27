"""TriggerBox metadata discovery and explicit, byte-free port-access checks."""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, replace
from threading import Event
from types import ModuleType

from fpvs_studio.triggers.serial_port_access import check_serial_port_access

_TRIGGERBOX_NAME = re.compile(
    r"^(?:Brain Products(?: GmbH)?[\s:-]+)?TriggerBox"
    r"(?:\s+(?:Plus|rev\.?\s*0?2))?"
    r"(?:\s+Virtual\s*Serial Port)?(?:\s*\(COM[1-9]\d*\))?$",
    re.IGNORECASE,
)
_COM_PORT = re.compile(r"COM([1-9]\d*)", re.IGNORECASE)


class TriggerBoxDiscoveryError(RuntimeError):
    """Raised when TriggerBox discovery cannot be completed."""


@dataclass(frozen=True, slots=True)
class TriggerBoxPortCandidate:
    """A metadata match with optional access results, never marker-receipt proof."""

    port: str
    description: str
    accessible: bool | None = None
    access_error: str = ""


def discover_triggerbox_ports(
    *, check_access: bool = False, cancel_event: Event | None = None,
) -> tuple[TriggerBoxPortCandidate, ...]:
    """Find named TriggerBox ports, optionally opening/closing recognized candidates.

    Driver metadata identifies candidates only. In particular, a rev.02 port can
    remain listed after disconnection. Unrecognized devices remain manual choices.
    Default discovery reads metadata only. Explicit access checks never send bytes.
    """
    _check_cancelled(cancel_event)
    try:
        list_ports = importlib.import_module("serial.tools.list_ports")
    except ImportError as exc:
        raise TriggerBoxDiscoveryError(
            "pyserial is required to detect TriggerBox COM ports."
        ) from exc
    try:
        ports = list(list_ports.comports())
    except Exception as exc:
        raise TriggerBoxDiscoveryError("Unable to enumerate serial ports.") from exc
    _check_cancelled(cancel_event)

    candidates: dict[str, TriggerBoxPortCandidate] = {}
    for info in ports:
        _check_cancelled(cancel_event)
        device = _metadata_text(getattr(info, "device", None))
        if _COM_PORT.fullmatch(device) is None:
            continue
        description = _metadata_text(getattr(info, "description", None))
        product = _metadata_text(getattr(info, "product", None))
        matched_name = next(
            (name for name in (description, product) if _TRIGGERBOX_NAME.fullmatch(name)),
            None,
        )
        if matched_name is None:
            continue
        port = device.upper()
        candidates.setdefault(port, TriggerBoxPortCandidate(port, matched_name))
    ordered = tuple(
        candidates[port] for port in sorted(candidates, key=lambda port: int(port[3:]))
    )
    if not check_access or not ordered:
        return ordered
    try:
        serial_module = importlib.import_module("serial")
    except ImportError as exc:
        raise TriggerBoxDiscoveryError(
            "pyserial is required to check TriggerBox COM ports."
        ) from exc
    return tuple(
        _check_port_access(candidate, serial_module, cancel_event) for candidate in ordered
    )


def _check_port_access(
    candidate: TriggerBoxPortCandidate, serial_module: ModuleType, cancel_event: Event | None,
) -> TriggerBoxPortCandidate:
    result = check_serial_port_access(
        candidate.port, baudrate=2_000_000, serial_module=serial_module,
        cancel_event=cancel_event,
    )
    return replace(candidate, accessible=result.accessible, access_error=result.access_error)


def _check_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("TriggerBox port detection cancelled.")


def _metadata_text(value: object) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""
