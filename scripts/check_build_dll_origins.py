"""Audit native files in Studio's Windows build and bind them to release assets."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from build_installer_inventory import (
    InventoryError,
    is_reparse_stat,
    require_safe_directory,
    sha256_file,
    validate_version,
)

TocKind = Literal["studio", "updater"]
MAX_AUDIT_INPUT_BYTES = 16 * 1024 * 1024
NATIVE_KINDS = frozenset({"BINARY", "EXTENSION"})
NATIVE_SUFFIXES = frozenset({".dll", ".pyd"})
SETUP_PREFIX = "FPVS-Studio-Setup-"


class NativeOriginError(ValueError):
    """Build evidence cannot establish approved DLL origins."""


@dataclass(frozen=True)
class TocAudit:
    native_files: int
    sha256: str


def _plain_file(path: Path) -> os.stat_result:
    details = path.lstat()
    if is_reparse_stat(details) or not stat.S_ISREG(details.st_mode):
        raise NativeOriginError(f"Expected a regular file without reparse points: {path}")
    return details


def _read_audit_input(path: Path) -> bytes:
    require_safe_directory(path.absolute().parent)
    _plain_file(path)
    with path.open("rb") as handle:
        contents = handle.read(MAX_AUDIT_INPUT_BYTES + 1)
    if len(contents) > MAX_AUDIT_INPUT_BYTES:
        raise NativeOriginError(f"Build audit input exceeds the size limit: {path}")
    return contents


def _toc_rows(path: Path, contents: bytes, kind: TocKind) -> list[object]:
    try:
        toc = ast.literal_eval(contents.decode("utf-8"))
    except (SyntaxError, ValueError, RecursionError) as error:
        raise NativeOriginError(f"Malformed PyInstaller TOC: {path}") from error
    if isinstance(toc, tuple):
        if kind == "studio" and len(toc) == 1 and isinstance(toc[0], list):
            return toc[0]
        if (
            kind == "updater"
            and len(toc) >= 5
            and isinstance(toc[0], str)
            and isinstance(toc[1], dict)
            and isinstance(toc[2], list)
            and toc[4] is False  # One-file PKG includes its own binaries.
        ):
            return toc[2]
    raise NativeOriginError(f"Unexpected {kind} PyInstaller TOC format: {path}")


def _approved_python_roots() -> tuple[Path, ...]:
    # Windows system paths can be searched during analysis. The bundle's native
    # files must come from the selected Python installation or environment.
    roots = tuple(dict.fromkeys(
        Path(prefix).resolve(strict=True) for prefix in (sys.prefix, sys.base_prefix)
    ))
    if any(root == Path(root.anchor) or not root.is_dir() for root in roots):
        raise NativeOriginError("The selected interpreter must have a specific Python directory.")
    return roots


def _native_source(source: str, destination: str, path: Path) -> Path:
    original = Path(source)
    if not original.is_absolute():
        raise NativeOriginError(
            f"{path}: Native source is not absolute for {destination}: {source!r}"
        )
    try:
        resolved = original.resolve(strict=True)
        if not resolved.is_file():
            raise OSError("Source is not a file")
    except (OSError, RuntimeError, ValueError) as error:
        raise NativeOriginError(
            f"{path}: Cannot resolve native source for {destination}: {source}"
        ) from error
    return resolved


def audit_toc(path: Path, kind: TocKind, approved_roots: tuple[Path, ...]) -> TocAudit:
    """Check native destinations and source filenames using their resolved origins."""
    contents = _read_audit_input(path)
    native_files = 0
    rejected: list[str] = []
    for row in _toc_rows(path, contents, kind):
        if not isinstance(row, tuple) or len(row) != 3:
            raise NativeOriginError(f"Malformed PyInstaller TOC row in {path}: {row!r}")
        destination, source, typecode = row
        if not (
            isinstance(destination, str) and destination
            and isinstance(typecode, str) and typecode
            and (isinstance(source, str) or (typecode == "OPTION" and source is None))
        ):
            raise NativeOriginError(f"Malformed PyInstaller TOC row in {path}: {row!r}")
        source = source or ""
        if (
            typecode not in NATIVE_KINDS
            and Path(destination).suffix.casefold() not in NATIVE_SUFFIXES
            and Path(source).suffix.casefold() not in NATIVE_SUFFIXES
        ):
            continue
        native_files += 1
        resolved = _native_source(source, destination, path)
        if not any(resolved.is_relative_to(root) for root in approved_roots):
            rejected.append(f"{destination} <- {resolved}")

    if not native_files:
        raise NativeOriginError(f"No native files were found in {kind} PyInstaller TOC: {path}")
    if rejected:
        origins = "\n  ".join(rejected[:12])
        raise NativeOriginError(
            f"{path}: {len(rejected)} native file(s) originate outside approved Python paths.\n"
            f"  {origins}"
        )
    return TocAudit(native_files, hashlib.sha256(contents).hexdigest())


def _installer_assets(installer_dir: Path) -> dict[str, dict[str, int | str]]:
    require_safe_directory(installer_dir.absolute())
    paths = sorted(installer_dir.iterdir())
    names = {path.name for path in paths}
    setups = [
        path for path in paths if path.name.startswith(SETUP_PREFIX) and path.suffix == ".exe"
    ]
    if len(setups) != 1:
        raise NativeOriginError(f"Expected one full Studio setup EXE in {installer_dir}")
    version = validate_version(setups[0].stem.removeprefix(SETUP_PREFIX))
    manifest = f"FPVS-Studio-Update-{version}.json"
    installers = {path.name for path in paths if path.suffix.casefold() == ".exe"}
    required = {manifest} | {f"{name}.sha256" for name in installers | {manifest}}
    missing = required - names
    if missing:
        raise NativeOriginError(f"Missing installer asset(s): {', '.join(sorted(missing))}")
    assets: dict[str, dict[str, int | str]] = {}
    for path in paths:
        size = _plain_file(path).st_size
        if size <= 0:
            raise NativeOriginError(f"Installer asset is empty: {path}")
        assets[path.name] = {"size_bytes": size, "sha256": sha256_file(path)}
    return assets


def _atomic_receipt(path: Path, contents: bytes) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".dll-origins-", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def check_receipt(
    path: Path, installer_dir: Path, studio: TocAudit, updater: TocAudit, *, write: bool,
) -> None:
    require_safe_directory(path.absolute().parent)
    if path.absolute().is_relative_to(installer_dir.absolute()):
        raise NativeOriginError("Keep the build receipt outside the installer assets directory.")
    contents = (json.dumps({
        "schema_version": 1,
        "toc_sha256": {"studio": studio.sha256, "updater": updater.sha256},
        "assets": _installer_assets(installer_dir),
    }, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if write:
        try:
            _plain_file(path)
        except FileNotFoundError:
            pass
        _atomic_receipt(path, contents)
    elif _read_audit_input(path) != contents:
        raise NativeOriginError(
            f"Receipt does not match the audited build and installer assets: {path}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studio-toc", type=Path, help="Studio COLLECT-00.toc")
    parser.add_argument("--updater-toc", type=Path, help="Updater PKG-00.toc")
    parser.add_argument("--installer-dir", type=Path)
    receipt = parser.add_mutually_exclusive_group()
    receipt.add_argument("--write-receipt", type=Path)
    receipt.add_argument("--verify-receipt", type=Path)
    args = parser.parse_args(argv)
    if not (args.studio_toc or args.updater_toc):
        parser.error("supply at least one TOC")
    receipt_path = args.write_receipt or args.verify_receipt
    if receipt_path and not (args.studio_toc and args.updater_toc and args.installer_dir):
        parser.error("receipt mode requires both TOCs and --installer-dir")
    if args.installer_dir and not receipt_path:
        parser.error("--installer-dir requires a receipt mode")

    try:
        roots = _approved_python_roots()
        studio = audit_toc(args.studio_toc, "studio", roots) if args.studio_toc else None
        updater = audit_toc(args.updater_toc, "updater", roots) if args.updater_toc else None
        if receipt_path:
            assert studio is not None and updater is not None
            check_receipt(receipt_path, args.installer_dir, studio, updater,
                          write=args.write_receipt is not None)
    except (OSError, InventoryError, NativeOriginError) as error:
        sys.stderr.write(f"Build DLL audit failed: {error}\n")
        return 1

    if studio is not None:
        sys.stdout.write(f"Studio native origins verified ({studio.native_files} files).\n")
    if updater is not None:
        sys.stdout.write(f"Updater native origins verified ({updater.native_files} files).\n")
    if receipt_path:
        action = "written" if args.write_receipt else "verified"
        sys.stdout.write(f"Installer build receipt {action}: {receipt_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
