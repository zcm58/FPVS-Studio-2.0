"""Prepared publication ownership and worker-facing access to the bundled publisher."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from packaging.version import InvalidVersion, Version

from fpvs_studio.core.library_publish import LibraryBundlePreparation, prepare_library_bundle
from fpvs_studio.core.project_bundle import ProjectBundleCancelled, ProjectBundleError
from fpvs_studio.developer import catalog_publisher

REPOSITORY = "zcm58/FPVS-Studio-Library"
_REPORT_LIMIT = 16 * 1024 * 1024


class PublisherError(Exception):
    """Safe, actionable developer error without subprocess diagnostics or credentials."""


class PublisherCancelled(PublisherError):
    """An operation was canceled; publication may already have changed remote state."""


@dataclass(frozen=True)
class PublicationRequest:
    item_id: str
    title: str
    version: str
    summary: str
    minimum_studio_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.item_id, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9-]{0,79}", self.item_id
        ):
            raise PublisherError("Item ID must use 1-80 lowercase letters, digits and hyphens.")
        if not isinstance(self.title, str) or not self.title.strip() or len(self.title) > 160:
            raise PublisherError("Enter a title of 1-160 characters.")
        if not isinstance(self.summary, str) or len(self.summary) > 4000:
            raise PublisherError("The summary must contain at most 4,000 characters.")
        if not isinstance(self.version, str) or not re.fullmatch(
            r"[0-9][A-Za-z0-9.-]{0,63}", self.version
        ):
            raise PublisherError("Enter a plain version such as 1.0.0 or 1.0.0rc1.")
        try:
            if str(Version(self.version)) != self.version:
                raise InvalidVersion(self.version)
        except InvalidVersion:
            raise PublisherError("Enter a valid version such as 1.0.0.") from None
        if (
            not isinstance(self.minimum_studio_version, str)
            or not re.fullmatch(r"\d+\.\d+\.\d+", self.minimum_studio_version)
            or len(self.minimum_studio_version) > 64
        ):
            raise PublisherError("Minimum Studio version must use major.minor.patch.")
        if len(self.release_tag) > 100:
            raise PublisherError(
                "Item ID and version must form a release tag under 101 characters."
            )

    @property
    def release_tag(self) -> str:
        return f"{self.item_id}-v{self.version}"


@dataclass(frozen=True)
class PublisherAccess:
    login: str
    repository: str


@dataclass(frozen=True)
class PreparedPublication:
    request: PublicationRequest
    directory: Path
    bundle_path: Path
    metadata_path: Path
    report: LibraryBundlePreparation


@dataclass(frozen=True)
class PublicationResult:
    repository: str
    tag: str
    catalog_commit: str


def _no_links(path: Path) -> None:
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise PublisherError("Publisher paths cannot contain links or Windows reparse points.")


def _check_cancel(cancel_event: Event | None, *, publishing: bool = False) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise PublisherCancelled(
            "Publication canceled. Remote state may have changed; the prepared files are retained "
            "for an exact retry."
            if publishing
            else "Publisher operation canceled."
        )


def _uncertain(message: str) -> str:
    return (
        message + " Remote state may have changed; prepared files are retained for an exact retry."
        if "Remote state may have changed" not in message
        else message
    )


def _api(cancel_event: Event | None) -> catalog_publisher.GitHubPublisher:
    _check_cancel(cancel_event)
    token = catalog_publisher.maintainer_token()
    _check_cancel(cancel_event)
    return catalog_publisher.GitHubPublisher(token, cancel_event=cancel_event)


def _publisher_error(error: Exception) -> str:
    if isinstance(error, catalog_publisher.PublishError):
        return " ".join(str(error).split())[:1024]
    return "Publishing could not finish. Check GitHub credentials, network and file access."


def _metadata_bytes(
    request: PublicationRequest,
    report: LibraryBundlePreparation,
    bundle_path: Path,
) -> bytes:
    metadata = {
        **report.as_dict(),
        "item_id": request.item_id,
        "version": request.version,
        "summary": request.summary,
        "asset_name": bundle_path.name,
        "title": request.title,
    }
    encoded = json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8")
    if len(encoded) > _REPORT_LIMIT:
        raise PublisherError("The preparation inventory exceeds the publisher's metadata limit.")
    return encoded


class PublisherService:
    def __init__(self) -> None:
        self._prepared: dict[Path, PreparedPublication] = {}
        self._directories: dict[Path, tuple[int, int]] = {}

    @staticmethod
    def _access(result: dict[str, object]) -> PublisherAccess:
        if (
            result.get("login") != "zcm58"
            or result.get("repository") != REPOSITORY
            or (result.get("can_publish") is not True)
        ):
            raise PublisherError(
                "Publishing requires zcm58 write access to the private Library repository."
            )
        return PublisherAccess(login="zcm58", repository=REPOSITORY)

    def check_access(self, *, cancel_event: Event | None = None) -> PublisherAccess:
        try:
            return self._access(catalog_publisher.check_access(_api(cancel_event)))
        except catalog_publisher.CatalogCancelled:
            raise PublisherCancelled("Publisher access check canceled.") from None
        except (
            catalog_publisher.PublishError,
            OSError,
            ValueError,
            subprocess.TimeoutExpired,
        ) as error:
            raise PublisherError(_publisher_error(error)) from None

    def prepare(
        self,
        project_root: Path,
        request: PublicationRequest,
        *,
        cancel_event: Event | None = None,
    ) -> PreparedPublication:
        _check_cancel(cancel_event)
        temporary_root = Path(tempfile.gettempdir()).resolve()
        source = Path(project_root).resolve()
        if temporary_root.is_relative_to(source):
            raise PublisherError("The OS temporary directory must be outside the source project.")
        directory = Path(tempfile.mkdtemp(prefix="fpub-", dir=temporary_root))
        info = directory.stat()
        self._directories[directory] = (info.st_dev, info.st_ino)
        bundle_path = directory / f"{request.item_id}-{request.version}.fpvsbundle"
        metadata_path = bundle_path.with_suffix(".json")
        try:
            report = prepare_library_bundle(
                source,
                bundle_path,
                minimum_studio_version=request.minimum_studio_version,
                cancel_event=cancel_event,
            )
            _check_cancel(cancel_event)
            metadata_path.write_bytes(_metadata_bytes(request, report, bundle_path))
            prepared = PreparedPublication(request, directory, bundle_path, metadata_path, report)
            self._prepared[directory] = prepared
            return prepared
        except Exception as error:
            self._remove_directory(directory)
            if isinstance(error, ProjectBundleCancelled):
                raise PublisherCancelled("Publisher preparation canceled.") from None
            if isinstance(error, ProjectBundleError):
                raise PublisherError(str(error)) from None
            if isinstance(error, OSError):
                raise PublisherError(
                    "Could not prepare the bundle. Check temporary storage and source access."
                ) from None
            raise

    def _owned(self, prepared: PreparedPublication) -> None:
        if self._prepared.get(prepared.directory) is not prepared:
            raise PublisherError(
                "This publication does not belong to the current publisher session."
            )
        _no_links(prepared.directory)
        _no_links(prepared.bundle_path)
        _no_links(prepared.metadata_path)
        info = prepared.directory.stat()
        if self._directories.get(prepared.directory) != (info.st_dev, info.st_ino):
            raise PublisherError("The prepared directory changed; its files have been preserved.")
        if set(prepared.directory.iterdir()) != {prepared.bundle_path, prepared.metadata_path}:
            raise PublisherError(
                "The preparation directory contains unrecognized files; it was preserved."
            )

    def _verify_prepared(self, prepared: PreparedPublication, cancel_event: Event | None) -> None:
        self._owned(prepared)
        expected = _metadata_bytes(prepared.request, prepared.report, prepared.bundle_path)
        with prepared.metadata_path.open("rb") as handle:
            if handle.read(_REPORT_LIMIT + 1) != expected:
                raise PublisherError(
                    "Prepared metadata changed. Prepare and review a new publication."
                )
        digest = hashlib.sha256()
        if prepared.bundle_path.stat().st_size != prepared.report.size_bytes:
            raise PublisherError("The prepared bundle changed. Prepare and review it again.")
        with prepared.bundle_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(256 * 1024), b""):
                _check_cancel(cancel_event)
                digest.update(chunk)
        if digest.hexdigest() != prepared.report.sha256:
            raise PublisherError("The prepared bundle changed. Prepare and review it again.")

    def publish(
        self,
        prepared: PreparedPublication,
        *,
        cancel_event: Event | None = None,
    ) -> PublicationResult:
        _check_cancel(cancel_event, publishing=True)
        self._verify_prepared(prepared, cancel_event)
        tag = prepared.request.release_tag
        try:
            bundles = catalog_publisher.load_prepared(prepared.directory, cancel_event=cancel_event)
            api = _api(cancel_event)
            _check_cancel(cancel_event, publishing=True)
            result = catalog_publisher.publish_online(api, tag, bundles, cancel_event=cancel_event)
            self._access(result)
            commit = result.get("catalog_commit")
            if (
                result.get("tag") != tag
                or not isinstance(commit, str)
                or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit)
            ):
                raise PublisherError("GitHub catalog publication was not confirmed.")
            return PublicationResult(REPOSITORY, tag, commit)
        except catalog_publisher.CatalogCancelled:
            raise PublisherCancelled(_uncertain("Publishing stopped.")) from None
        except PublisherCancelled:
            raise
        except (
            catalog_publisher.PublishError,
            OSError,
            ValueError,
            subprocess.TimeoutExpired,
        ) as error:
            raise PublisherError(_uncertain(_publisher_error(error))) from None
        except PublisherError as error:
            raise PublisherError(_uncertain(str(error))) from None

    def _remove_directory(self, directory: Path) -> None:
        _no_links(directory)
        info = directory.stat()
        if self._directories.get(directory) != (info.st_dev, info.st_ino):
            raise PublisherError(
                "Refusing to remove a directory no longer owned by this preparation."
            )
        for path in directory.rglob("*"):
            _no_links(path)
        shutil.rmtree(directory)
        del self._directories[directory]

    def discard(self, prepared: PreparedPublication) -> None:
        self._owned(prepared)
        self._remove_directory(prepared.directory)
        del self._prepared[prepared.directory]
