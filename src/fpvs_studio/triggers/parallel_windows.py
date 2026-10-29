"""Read-only Windows prerequisites for explicitly selected native LPT output."""

from __future__ import annotations

import ctypes
from pathlib import Path


def windows_system_directory() -> Path:
    """Resolve Windows' own system directory without environment or PATH lookup."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_directory = kernel32.GetSystemDirectoryW
    get_directory.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
    get_directory.restype = ctypes.c_uint
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_directory(buffer, len(buffer))
    if not 0 < length < len(buffer):
        raise OSError("Unable to resolve the Windows system directory.")
    directory = Path(buffer.value)
    if not directory.is_absolute():
        raise OSError("Windows returned a non-absolute system directory.")
    return directory
