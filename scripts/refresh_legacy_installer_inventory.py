"""Inventory authenticated published installers without running their setup programs.

This opt-in developer utility downloads release artifacts with gh, validates GitHub's
SHA-256 metadata, and runs a separately authenticated portable innounp extractor. Only
installed {app} payload paths/content hashes are emitted; no installation is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import stat
import subprocess
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

from packaging.version import InvalidVersion, Version

REPOSITORY = "zcm58/FPVS-Studio-2.0"
INSTALLER_PATTERN = re.compile(r"FPVS-Studio-Setup-([A-Za-z0-9.!+_-]+)\.exe\Z")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class PublishedInstaller:
    tag: str
    asset_name: str
    asset_id: int
    sha256: str
    size_bytes: int

    def provenance(self) -> dict[str, str | int]:
        return {
            "tag": self.tag,
            "asset_name": self.asset_name,
            "asset_id": self.asset_id,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_plain_path(path: Path) -> None:
    """Reject symlinks/junctions in an existing path or any existing ancestor."""
    if not path.is_absolute():
        raise ValueError(f"Expected an absolute path: {path}")
    for component in (path, *path.parents):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & REPARSE_POINT:
            raise ValueError(f"Links/reparse points are not inventory inputs: {component}")


def validate_payload_path(raw: str) -> str:
    """Validate a file path from an archive before allowing the extractor to run."""
    normalized = raw.replace("\\", "/")
    components = normalized.split("/")
    if (
        not normalized
        or PureWindowsPath(raw).is_absolute()
        or PureWindowsPath(raw).drive
        or any(part in ("", ".", "..") for part in components)
        or any(part.endswith((" ", ".")) for part in components)
        or any(PureWindowsPath(part).is_reserved() for part in components)
        or any(ord(char) < 32 or char in '<>:"|?*{}' for char in normalized)
    ):
        raise ValueError(f"Unsafe installed payload path: {raw!r}")
    return normalized


def parse_payload_listing(listing: str) -> set[str]:
    paths: set[str] = set()
    seen: set[str] = set()
    for line in listing.splitlines():
        line = line.strip()
        if not line.startswith("{app}\\"):
            continue
        path = validate_payload_path(line[len("{app}\\") :])
        if path.casefold() in seen:
            raise ValueError(f"Duplicate/case-aliased installed path: {path}")
        seen.add(path.casefold())
        paths.add(path)
    if "fpvs studio.exe" not in seen:
        raise ValueError("Published installer has no FPVS Studio.exe app payload.")
    return paths


def published_installers(
    releases: Iterable[dict[str, Any]], through_version: str
) -> list[PublishedInstaller]:
    latest = Version(through_version)
    result: list[PublishedInstaller] = []
    names: set[str] = set()
    for release in releases:
        if release.get("draft"):
            continue
        tag = str(release.get("tag_name", ""))
        try:
            version = Version(tag.removeprefix("v"))
        except InvalidVersion:
            continue
        if version > latest:
            continue
        for asset in release.get("assets", []):
            name = str(asset.get("name", ""))
            match = INSTALLER_PATTERN.fullmatch(name)
            if match is None:
                continue
            Version(match.group(1))
            digest = str(asset.get("digest", "")).removeprefix("sha256:")
            size = asset.get("size")
            identity = asset.get("id")
            if (
                not str(asset.get("digest", "")).startswith("sha256:")
                or SHA256_PATTERN.fullmatch(digest) is None
                or type(size) is not int
                or size <= 0
                or type(identity) is not int
                or identity <= 0
            ):
                raise ValueError(f"Missing trusted asset metadata for {tag}/{name}.")
            if name.casefold() in names:
                raise ValueError(f"Installer asset names are not unique: {name}")
            names.add(name.casefold())
            result.append(PublishedInstaller(tag, name, identity, digest, size))
    if not result:
        raise ValueError("No published installers were selected.")
    return sorted(result, key=lambda item: Version(item.tag.removeprefix("v")))


def _run(command: Sequence[str]) -> str:
    result = subprocess.run(
        list(command), check=True, capture_output=True, encoding="utf-8", timeout=600
    )
    return result.stdout


def authenticate_installer(installer: PublishedInstaller, path: Path) -> None:
    assert_plain_path(path)
    if path.stat().st_size != installer.size_bytes or file_sha256(path) != installer.sha256:
        raise ValueError(f"Published installer failed authentication: {installer.asset_name}")


def inventory_extracted_payload(root: Path, expected: set[str]) -> dict[str, str]:
    assert_plain_path(root)
    if not root.is_dir():
        raise ValueError("Extractor did not create the expected {app} payload directory.")
    result: dict[str, str] = {}
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in directories:
            assert_plain_path(current_path / name)
        for name in filenames:
            path = current_path / name
            assert_plain_path(path)
            if not stat.S_ISREG(path.lstat().st_mode):
                raise ValueError(f"Non-regular extracted payload: {path}")
            relative = validate_payload_path(path.relative_to(root).as_posix())
            result[relative] = file_sha256(path)
    if result.keys() != expected:
        raise ValueError("Extracted files do not match the validated archive listing.")
    return result


def merge_payloads(payloads: Iterable[dict[str, str]]) -> list[dict[str, Any]]:
    names: dict[str, str] = {}
    hashes: dict[str, set[str]] = {}
    for payload in payloads:
        for raw, digest in payload.items():
            path = validate_payload_path(raw)
            if SHA256_PATTERN.fullmatch(digest) is None:
                raise ValueError(f"Invalid content hash for {path}")
            key = path.casefold()
            if "/" not in key and re.fullmatch(r"unins[0-9]*\.(exe|dat|msg)", key):
                continue
            names[key] = min(names.get(key, path), path)
            hashes.setdefault(key, set()).add(digest)
    return [
        {"path": names[key], "sha256": sorted(hashes[key])}
        for key in sorted(hashes)
    ]


def collect_inventory(
    installers: Sequence[PublishedInstaller], extractor: Path, work_dir: Path
) -> dict[str, Any]:
    payloads: list[dict[str, str]] = []
    for index, installer in enumerate(installers, start=1):
        _LOG.info(
            "Authenticating/extracting release %s (%s/%s)", installer.tag, index, len(installers),
            extra={"release_tag": installer.tag, "asset_id": installer.asset_id},
        )
        archive = work_dir / installer.asset_name
        if not archive.exists():
            _run([
                "gh", "release", "download", installer.tag, "--repo", REPOSITORY,
                "--pattern", installer.asset_name, "--dir", str(work_dir),
            ])
        authenticate_installer(installer, archive)
        listing = _run([str(extractor), "-s", "-h", "-b", "-o", "-u", str(archive)])
        expected = parse_payload_listing(listing)
        # TemporaryDirectory owns only this new extraction tree, never the work root
        # or an installed application. The authenticated EXE is an input, not executed.
        with tempfile.TemporaryDirectory(prefix="payload-", dir=work_dir) as directory:
            extraction = Path(directory)
            assert_plain_path(extraction)
            if extraction.resolve().parent != work_dir.resolve():
                raise ValueError("Extraction directory escaped the chosen work root.")
            _run([
                str(extractor), "-x", "-b", "-q", "-o", "-u", f"-d{extraction}",
                str(archive), "{app}\\*",
            ])
            payload = inventory_extracted_payload(extraction / "{app}", expected)
        payloads.append(payload)
        _LOG.info(
            "Verified %s installed files", len(payload),
            extra={"release_tag": installer.tag, "installed_file_count": len(payload)},
        )
    return {
        "schema_version": 1,
        "application": "fpvs-studio",
        "releases": [installer.provenance() for installer in installers],
        "files": merge_payloads(payloads),
    }


def write_inventory(output: Path, inventory: dict[str, Any]) -> None:
    """Commit a complete inventory, removing only this attempt's staging file."""
    staged: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=output.parent,
            prefix="inventory-", suffix=".tmp", delete=False,
        ) as stream:
            staged = Path(stream.name)
            json.dump(inventory, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        staged.replace(output)
        staged = None
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extractor", type=Path, required=True)
    parser.add_argument("--extractor-sha256", required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--through-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    for path in (args.extractor, args.work_dir, args.output):
        assert_plain_path(path)
    if not args.work_dir.is_dir() or args.work_dir == Path(args.work_dir.anchor):
        parser.error("--work-dir must be an existing dedicated absolute work directory")
    if (
        SHA256_PATTERN.fullmatch(args.extractor_sha256) is None
        or file_sha256(args.extractor) != args.extractor_sha256
    ):
        parser.error("portable extractor SHA-256 does not match")
    if args.output.exists() and not args.replace:
        parser.error("output exists; inspect it first and explicitly use --replace")
    pages = json.loads(_run([
        "gh", "api", "--paginate", "--slurp", f"repos/{REPOSITORY}/releases?per_page=100"
    ]))
    selected = published_installers(
        (release for page in pages for release in page), args.through_version
    )
    inventory = collect_inventory(selected, args.extractor, args.work_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    assert_plain_path(args.output)
    write_inventory(args.output, inventory)
    _LOG.info(
        "Wrote %s known installed paths to %s", len(inventory["files"]), args.output,
        extra={"inventory_path": str(args.output), "installed_path_count": len(inventory["files"])},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
