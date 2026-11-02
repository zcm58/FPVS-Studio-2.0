"""Recognize Finder metadata without discarding authored dot-prefixed images."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


def is_finder_metadata_file(path: Path) -> bool:
    """Recognize metadata by its conventional name and binary format signature."""

    if path.name != ".DS_Store" and not path.name.startswith("._"):
        return False
    with path.open("rb") as handle:
        header = handle.read(26)
    if path.name == ".DS_Store":
        return header.startswith(b"\x00\x00\x00\x01Bud1")
    return (
        len(header) == 26
        and header[:4] == b"\x00\x05\x16\x07"
        and header[4:8] in {b"\x00\x01\x00\x00", b"\x00\x02\x00\x00"}
    )


def source_image_directory_files(
    source_dir: Path, *, sort_key: Callable[[Path], str] | None = None,
) -> list[Path]:
    """Return regular source entries, omitting only recognized Finder metadata."""

    return sorted(
        (path for path in source_dir.iterdir()
         if path.is_file() and not is_finder_metadata_file(path)),
        key=sort_key,
    )
