"""Live Windows file classification for source folder inventories."""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from ctypes import wintypes
from functools import lru_cache
from pathlib import Path
from stat import (
    FILE_ATTRIBUTE_ARCHIVE,
    FILE_ATTRIBUTE_COMPRESSED,
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_ENCRYPTED,
    FILE_ATTRIBUTE_HIDDEN,
    FILE_ATTRIBUTE_NORMAL,
    FILE_ATTRIBUTE_NOT_CONTENT_INDEXED,
    FILE_ATTRIBUTE_READONLY,
    FILE_ATTRIBUTE_REPARSE_POINT,
    FILE_ATTRIBUTE_SYSTEM,
)

_FILE_STAT_BASIC_BY_NAME = 3
_FILE_DEVICE_DISK = 0x0007
_FILE_REMOTE_DEVICE = 0x0010
_REGULAR_FILE_ATTRIBUTES = (
    FILE_ATTRIBUTE_ARCHIVE | FILE_ATTRIBUTE_COMPRESSED | FILE_ATTRIBUTE_ENCRYPTED
    | FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_NORMAL | FILE_ATTRIBUTE_NOT_CONTENT_INDEXED
    | FILE_ATTRIBUTE_READONLY | FILE_ATTRIBUTE_SYSTEM
)


class _FileStatBasicInformation(ctypes.Structure):
    # FILE_STAT_BASIC_INFORMATION from the Windows SDK.
    _fields_ = [
        ("file_id", ctypes.c_int64),
        ("creation_time", ctypes.c_int64),
        ("access_time", ctypes.c_int64),
        ("write_time", ctypes.c_int64),
        ("change_time", ctypes.c_int64),
        ("allocation_size", ctypes.c_int64),
        ("end_of_file", ctypes.c_int64),
        ("attributes", wintypes.ULONG),
        ("reparse_tag", wintypes.ULONG),
        ("number_of_links", wintypes.ULONG),
        ("device_type", wintypes.ULONG),
        ("device_characteristics", wintypes.ULONG),
        ("reserved", wintypes.ULONG),
        ("volume_serial_number", ctypes.c_int64),
        ("file_id_128", ctypes.c_ubyte * 16),
    ]


@lru_cache(maxsize=1)
def _file_information_query() -> Callable[..., int] | None:
    try:
        query = ctypes.WinDLL("api-ms-win-core-file-l2-1-4").GetFileInformationByName
    except (AttributeError, OSError):
        return None
    query.argtypes = [wintypes.LPCWSTR, ctypes.c_int, ctypes.c_void_p, wintypes.ULONG]
    query.restype = wintypes.BOOL
    return query


def source_file_probe(directory: Path) -> Callable[[Path], bool]:
    """Use fresh by-name metadata for ordinary disk files, as newer Python stat does."""

    query = _file_information_query()
    if query is None:
        return Path.is_file

    info = _FileStatBasicInformation()
    buffer = ctypes.byref(info)
    buffer_size = ctypes.sizeof(info)

    def query_local_disk(path: Path) -> bool:
        return (
            bool(query(str(path), _FILE_STAT_BASIC_BY_NAME, buffer, buffer_size))
            and info.device_type == _FILE_DEVICE_DISK
            and not info.device_characteristics & _FILE_REMOTE_DEVICE
            and not info.reparse_tag
            and not info.attributes & FILE_ATTRIBUTE_REPARSE_POINT
        )

    # Check the information class and source volume once. Unsupported Windows builds,
    # remote folders and redirected source roots use the original file probe throughout.
    if not query_local_disk(directory) or not info.attributes & FILE_ATTRIBUTE_DIRECTORY:
        return Path.is_file

    def is_file(path: Path) -> bool:
        if (
            query_local_disk(path)
            and info.number_of_links > 0
            and info.attributes
            and not info.attributes & ~_REGULAR_FILE_ATTRIBUTES
        ):
            return True
        return path.is_file()

    return is_file
