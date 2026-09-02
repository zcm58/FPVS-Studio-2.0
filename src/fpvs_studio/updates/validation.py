"""Shared release identity rules for downloads, offline receipts, and launch."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from urllib.parse import unquote, urlparse

from packaging.version import InvalidVersion, Version

from fpvs_studio.updates.models import InstallerAsset, UpdateError

RELEASE_REPOSITORY = "zcm58/FPVS-Studio-2.0"
INSTALLER_ASSET_PATTERN = re.compile(
    r"FPVS-Studio-Setup-(?P<version>[0-9][A-Za-z0-9.+_-]*)\.exe", re.IGNORECASE | re.ASCII
)
# This published tag used the shorter filename. Never infer other version aliases.
_PUBLISHED_FILENAME_ALIASES = {Version("0.9.9.10"): Version("0.9.10")}
MAX_INSTALLER_SIZE_BYTES = 4 * 1024 * 1024 * 1024
_LOG = logging.getLogger(__name__)


def parse_release_version(tag_name: str) -> Version:
    """Parse the application's published tag spellings into a comparable version."""

    if len(tag_name) > 200:
        raise UpdateError("The release version is too long.")
    normalized = tag_name.strip().removeprefix("v").removeprefix("V").strip()
    normalized = re.sub(r"[-_]?beta[.-]?(\d+)$", r"b\1", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"[-_]?beta$", "b0", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"[-_]?alpha[.-]?(\d+)$", r"a\1", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"[-_]?alpha$", "a0", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"[-_]?rc[.-]?(\d+)$", r"rc\1", normalized, flags=re.IGNORECASE)
    try:
        return Version(normalized)
    except InvalidVersion as error:
        raise UpdateError(f"Release tag '{tag_name}' is not a supported version.") from error


def installer_filename_version(name: str) -> Version | None:
    """Recognize only a single, versioned installer basename, not a path or stream."""

    match = INSTALLER_ASSET_PATTERN.fullmatch(name)
    if match is None or len(name) > 200:
        return None
    try:
        return parse_release_version(match.group("version"))
    except UpdateError:
        return None


def installer_matches_version(name: str, version: Version) -> bool:
    filename_version = installer_filename_version(name)
    return filename_version is not None and (
        filename_version == version or filename_version == _PUBLISHED_FILENAME_ALIASES.get(version)
    )


def validate_asset_identity(asset: InstallerAsset, *, require_digest: bool = True) -> Version:
    """Bind an asset to this repository, its exact release, size, and trusted digest."""

    filename_version = installer_filename_version(asset.name)
    if filename_version is None:
        raise UpdateError("The selected update asset has an invalid Windows installer filename.")
    parsed = urlparse(asset.download_url)
    if parsed.scheme != "https":
        raise UpdateError("Installer downloads require an HTTPS URL.")
    if (
        parsed.netloc.lower() != "github.com"
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
    ):
        raise UpdateError("The installer must be a published FPVS Studio GitHub release asset.")
    prefix = f"/{RELEASE_REPOSITORY}/releases/download/"
    if not parsed.path.startswith(prefix):
        raise UpdateError("The installer must be a published FPVS Studio GitHub release asset.")
    parts = parsed.path[len(prefix) :].split("/")
    if len(parts) != 2 or unquote(parts[1]) != asset.name:
        raise UpdateError("The installer URL does not match the selected release asset.")
    tag_version = parse_release_version(unquote(parts[0]))
    version = parse_release_version(asset.version) if asset.version is not None else tag_version
    if tag_version != version or not installer_matches_version(asset.name, version):
        raise UpdateError("The installer filename does not match the selected release version.")
    if (
        not isinstance(asset.size_bytes, int)
        or isinstance(asset.size_bytes, bool)
        or not 0 < asset.size_bytes <= MAX_INSTALLER_SIZE_BYTES
    ):
        raise UpdateError("The release has no supported, bounded installer size.")
    if require_digest and asset.sha256 is None:
        raise UpdateError(
            "This release has no valid GitHub SHA-256 digest. "
            "Use the release page instead of the in-app installer."
        )
    return version


def validate_response_url(response: object) -> None:
    """Reject insecure redirects; GitHub's signed release CDN is allowed."""

    geturl = getattr(response, "geturl", None)
    if not callable(geturl):
        raise UpdateError("GitHub returned a response without a verifiable HTTPS URL.")
    final_url = geturl()
    if not isinstance(final_url, str):
        raise UpdateError("GitHub returned an invalid response URL.")
    parsed = urlparse(final_url)
    if parsed.scheme != "https" or parsed.netloc.lower() not in {
        "github.com",
        "api.github.com",
        "release-assets.githubusercontent.com",
        "objects.githubusercontent.com",
    }:
        raise UpdateError("GitHub redirected the update request to an untrusted or non-HTTPS URL.")


@contextmanager
def managed_response(response: Any) -> Iterator[Any]:
    """Close urllib responses on every path without hiding the original operation error."""

    try:
        yield response
    except BaseException:
        try:
            response.close()
        except Exception:
            _LOG.warning("update_response_close_failed", exc_info=True)
        raise
    else:
        response.close()
