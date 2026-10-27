"""Read-only TriggerBox COM-port discovery from operating-system metadata."""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass

_TRIGGERBOX_NAME = re.compile(
    r"^(?:Brain Products(?: GmbH)?[\s:-]+)?TriggerBox"
    r"(?:\s+(?:Plus|rev\.?\s*0?2))?"
    r"(?:\s+VirtualSerial Port)?(?:\s*\(COM[1-9]\d*\))?$",
    re.IGNORECASE,
)
_COM_PORT = re.compile(r"COM([1-9]\d*)", re.IGNORECASE)


class TriggerBoxDiscoveryError(RuntimeError):
    """Raised when serial-port metadata cannot be enumerated."""


@dataclass(frozen=True, slots=True)
class TriggerBoxPortCandidate:
    """A metadata match, without confirming connection or trigger delivery."""

    port: str
    description: str


def discover_triggerbox_ports() -> tuple[TriggerBoxPortCandidate, ...]:
    """Return named TriggerBox ports without opening a port or sending bytes.

    Driver metadata identifies candidates only. In particular, a rev.02 port can
    remain listed after disconnection. Unrecognized devices remain manual choices.
    """
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

    candidates: dict[str, TriggerBoxPortCandidate] = {}
    for info in ports:
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
    return tuple(candidates[port] for port in sorted(candidates, key=lambda port: int(port[3:])))


def _metadata_text(value: object) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""
