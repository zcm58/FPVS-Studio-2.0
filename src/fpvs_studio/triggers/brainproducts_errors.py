"""Concise TriggerBox recovery based on observed serial failures, not guessed owners."""

from __future__ import annotations

import errno
import re
from typing import Literal

from fpvs_studio.triggers.serial_port_access import is_serial_access_denied


def triggerbox_failure_reason(
    error: BaseException | str,
) -> Literal["configuration", "busy", "missing", "timeout", "device_io", "close", "unknown"]:
    """Handle native errors and pyserial's serialized Windows errors alike."""

    text = str(error)
    if "Unable to close the port:" in text or "Closing the port also failed:" in text:
        return "close"
    error_number = getattr(error, "errno", None)
    if error_number is None and (match := re.search(r"\[Errno (\d+)\]", text)):
        error_number = int(match[1])
    code = getattr(error, "winerror", None)
    if code is None:
        match = re.search(
            r"\[WinError (\d+)\]|"
            r"\b(?:OSError|PermissionError|FileNotFoundError)\(\d+,[^\r\n]*?,\s*None,\s*(\d+)\)",
            text,
        )
        if match:
            code = int(match[1] or match[2])
    # Configuration context takes precedence over a generic Windows I/O error.
    # EINVAL alone is not enough: Windows device failures can map to errno 22.
    if isinstance(error, ValueError) or re.search(
        r"cannot configure port|could not configure port|not a valid baudrate", text, re.I,
    ):
        return "configuration"
    if code in (5, 32, 33, 170) or code is None and (
        is_serial_access_denied(error) or error_number in (errno.EACCES, errno.EPERM, errno.EBUSY)
    ):
        return "busy"
    if isinstance(error, FileNotFoundError) or code in (2, 3) or re.search(
        r"\[Errno 2\]|\bFileNotFoundError\(2,", text,
    ):
        return "missing"
    if isinstance(error, TimeoutError) or type(error).__name__ == "SerialTimeoutException" or (
        code in (121, 1460) or re.search(r"\b(?:write timeout|timed out)\b", text, re.I)
    ):
        return "timeout"
    if code in (6, 21, 31, 995, 1117, 1167) or error_number in (
        errno.EIO, errno.ENODEV, errno.ENXIO,
    ):
        return "device_io"
    return "unknown"


def triggerbox_port_error_message(port: str, error: BaseException | str) -> str:
    """Return actionable display text; callers retain raw diagnostics separately."""

    reason = triggerbox_failure_reason(error)
    if reason == "close":
        return (
            f"TriggerBox port {port} could not be closed. Restart Studio before retrying; "
            "see details for the original error."
        )
    if reason == "busy":
        return (
            f"TriggerBox port {port} is busy or access was denied. Close TriggerBox "
            "Configuration/Test IO or other port users, then retry."
        )
    if reason == "missing":
        return (
            f"TriggerBox port {port} was not found. Reconnect USB and check Device Manager; "
            "install/repair its driver if absent."
        )
    if reason == "configuration":
        return (
            f"TriggerBox serial settings on {port} were rejected. Select its actual COM port "
            "and repair the vendor driver (2,000,000 baud required)."
        )
    if reason == "timeout":
        return (
            f"TriggerBox port {port} did not respond in time. Check USB/power, reconnect it, "
            "then retry."
        )
    if reason == "device_io":
        return (
            f"TriggerBox communication on {port} failed. Check USB/power and reconnect it "
            "before retrying."
        )
    return (
        f"TriggerBox could not open {port}. Check USB and its COM number in Device Manager; "
        "install/repair its driver if absent."
    )
