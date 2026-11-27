"""Enumerate authored source images and name their generated PNGs."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from hashlib import sha256
from itertools import chain, islice
from operator import methodcaller
from pathlib import Path, WindowsPath

from fpvs_studio.core.portable_paths import portable_path_key

_WINDOWS_INVENTORY_MIN_ENTRIES = 64


def generated_png_name(
    source: Path, digest: str, used_paths: set[str], *, prefix: str = "",
) -> str:
    """Keep the original stem/hash name unless another input already claimed it."""

    stem = source.stem
    filename = f"{stem}-{digest[:12]}.png"
    key = portable_path_key(prefix + filename)
    attempt = 0
    while key in used_paths:
        # JPEG/JPG and TIFF/TIF copies can share both their stem and their bytes.
        # A separate delimiter keeps the alternative disjoint from ordinary names.
        attempt += 1
        identity = f"{source.name}\0{digest}\0{attempt}".encode()
        filename = f"{stem}.{sha256(identity).hexdigest()[:12]}.png"
        key = portable_path_key(prefix + filename)
    used_paths.add(key)
    return filename


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

    paths: Iterable[Path] = source_dir.iterdir()
    is_file: Callable[[Path], bool] = methodcaller("is_file")
    if type(source_dir) is WindowsPath:
        # Avoid native initialization for the small authoring pools Studio commonly scans.
        start = list(islice(paths, _WINDOWS_INVENTORY_MIN_ENTRIES))
        if len(start) == _WINDOWS_INVENTORY_MIN_ENTRIES:
            from fpvs_studio.preprocessing.windows_source_files import source_file_probe

            is_file = source_file_probe(source_dir)
            paths = chain(start, paths)
        else:
            paths = start
    return sorted(
        (path for path in paths if is_file(path) and not is_finder_metadata_file(path)),
        key=sort_key,
    )
