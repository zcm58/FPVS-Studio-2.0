"""Classify observed serial failures without inferring a device or port owner."""

from __future__ import annotations

import errno
import re
from typing import Literal


def serial_failure_reason(
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
        isinstance(error, PermissionError)
        or re.search(r"\bPermissionError\(13\s*,", text) is not None
        or error_number in (errno.EACCES, errno.EPERM, errno.EBUSY)
    ):
        return "busy"
    if isinstance(error, FileNotFoundError) or code in (2, 3) or re.search(
        r"\[Errno 2\]|\bFileNotFoundError\(2,", text,
    ):
        return "missing"
    if isinstance(error, TimeoutError) or type(error).__name__ == "SerialTimeoutException" or (
        code in (121, 1460) or code is None and error_number == errno.ETIMEDOUT
        or re.search(r"\b(?:write timeout|timed out)\b", text, re.I)
    ):
        return "timeout"
    if code in (6, 21, 31, 995, 1117, 1167) or error_number in (
        errno.EIO, errno.ENODEV, errno.ENXIO,
    ):
        return "device_io"
    return "unknown"
