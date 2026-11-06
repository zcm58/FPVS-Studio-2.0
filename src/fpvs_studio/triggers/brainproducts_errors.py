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
            f"TriggerBox port {port} could not be closed. Windows may not have released it. "
            "Restart Studio before retrying."
        )
    if reason == "busy":
        return (
            f"The {port} port is occupied or access was denied. Fully exit the TriggerBox "
            f"software (Configuration/Test IO) and other apps using {port}, then try again. "
            "Pressing Stop can leave the port occupied."
        )
    if reason == "missing":
        return (
            f"TriggerBox port {port} was not found. It may be unplugged or need its driver. "
            "Reconnect USB; check Device Manager and install its driver if needed."
        )
    if reason == "configuration":
        return (
            f"TriggerBox serial settings on {port} were rejected. The port or driver may be "
            "incorrect. Check the selected port and repair the TriggerBox driver if needed."
        )
    if reason == "timeout":
        return (
            f"TriggerBox port {port} did not respond in time. The USB connection may be "
            "unavailable. Reconnect the USB cable, then try again."
        )
    if reason == "device_io":
        return (
            f"TriggerBox communication on {port} failed. The USB connection may have been "
            "interrupted. Reconnect the USB cable, then try again."
        )
    return (
        f"TriggerBox could not open {port}. The USB connection or driver may be unavailable. "
        "Reconnect USB and check its port in Device Manager."
    )
