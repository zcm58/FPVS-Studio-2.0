"""Host-independent filename checks for Windows/macOS project transfers.

These checks do not rename or normalize stored names. Normalization is used only
for detecting aliases and matching equivalent filesystem Unicode spellings.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from pathlib import PurePosixPath

from fpvs_studio.core.paths import validate_project_relative_path

_MAX_COMPONENT_UTF8_BYTES = 255
_MAX_COMPONENT_UTF16_UNITS = 255
_WINDOWS_RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
    *(f"{prefix}{number}" for prefix in ("COM", "LPT") for number in "123456789¹²³"),
})
_WINDOWS_INVALID_CHARACTERS = frozenset('<>:"\\|?*')


def portable_path_key(path: str) -> str:
    """Return a conservative case/normalization alias key without changing a path."""

    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", path).casefold())


def portable_path_spelling(path: str) -> str:
    """Match canonical Unicode equivalents while retaining case distinctions."""

    return unicodedata.normalize("NFC", path)


def validate_portable_relative_path(path: str) -> str:
    """Reject names that cannot retain their meaning on Windows and macOS."""

    normalized = validate_project_relative_path(path)
    parts = PurePosixPath(normalized).parts
    if not parts:
        raise ValueError(f"Unportable project path {path!r}: a filename is required.")
    for part in parts:
        reason = None
        if part.endswith((".", " ")):
            reason = "filenames may not end with a dot or space"
        elif any(ord(character) < 32 or character in _WINDOWS_INVALID_CHARACTERS
                 for character in part):
            reason = "the filename contains a character Windows cannot use"
        elif part.split(".", 1)[0].rstrip(" ").upper() in _WINDOWS_RESERVED_NAMES:
            reason = "the filename is reserved by Windows"
        try:
            utf8_bytes = len(part.encode("utf-8"))
            utf16_units = len(part.encode("utf-16-le")) // 2
        except UnicodeEncodeError as error:
            raise ValueError(
                f"Unportable project path {path!r}: the filename contains invalid Unicode."
            ) from error
        if utf8_bytes > _MAX_COMPONENT_UTF8_BYTES or utf16_units > _MAX_COMPONENT_UTF16_UNITS:
            reason = "each filename must fit 255 UTF-8 bytes and 255 UTF-16 units"
        if reason is not None:
            raise ValueError(
                f"Unportable project path {path!r}: {reason}. "
                "Rename the file or folder and update its project references before exporting."
            )
    return normalized


def validate_portable_path_inventory(
    file_paths: Iterable[str], *, directory_paths: Iterable[str] = (),
) -> None:
    """Reject aliases and file/folder conflicts before copying to another host."""

    files = set(file_paths)
    directories = set(directory_paths)
    aliases: dict[str, str] = {}
    for path in sorted(files | directories):
        normalized = validate_portable_relative_path(path)
        prefix = PurePosixPath()
        parts = PurePosixPath(normalized).parts
        for index, part in enumerate(parts):
            prefix /= part
            spelling = prefix.as_posix()
            previous = aliases.setdefault(portable_path_key(spelling), spelling)
            if previous != spelling:
                raise ValueError(
                    "Project bundle paths conflict by case or Unicode normalization on "
                    f"Windows/macOS: {previous!r}, {spelling!r}. "
                    "Rename these files or folders before exporting."
                )
            if index < len(parts) - 1:
                directories.add(spelling)
    conflicts = files & directories
    if conflicts:
        raise ValueError(
            "Project bundle path is used as both a file and a folder: "
            + ", ".join(sorted(conflicts))
        )
