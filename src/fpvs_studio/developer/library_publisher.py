"""Source-only adapter to the private repository's authoritative publisher script."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from packaging.version import InvalidVersion, Version

from fpvs_studio.core.library_publish import LibraryBundlePreparation, prepare_library_bundle
from fpvs_studio.core.project_bundle import ProjectBundleCancelled, ProjectBundleError

REPOSITORY = "zcm58/FPVS-Studio-Library"
PUBLISHER_ENV = "FPVS_LIBRARY_PUBLISHER_REPO"
_SCRIPT = Path("scripts/publish-catalog.py")
_OUTPUT_LIMIT = 64 * 1024
_REPORT_LIMIT = 16 * 1024 * 1024
_ACCESS_TIMEOUT = 60.0
_PUBLISH_TIMEOUT = 30 * 60.0


class PublisherError(Exception):
    """Safe, actionable developer error without subprocess diagnostics or credentials."""


class PublisherCancelled(PublisherError):
    """An operation was canceled; publication may already have changed remote state."""


@dataclass(frozen=True)
class PublisherConfig:
    repository_root: Path


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


def _source_checkout() -> bool:
    root = Path(__file__).resolve().parents[3]
    return (
        not getattr(sys, "frozen", False)
        and (root / "pyproject.toml").is_file()
        and (root / ".git").exists()
    )


def _no_links(path: Path) -> None:
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise PublisherError("Publisher paths cannot contain links or Windows reparse points.")


def _validate_config(config: PublisherConfig) -> Path:
    root = config.repository_root
    if not root.is_absolute():
        raise PublisherError(f"{PUBLISHER_ENV} must be an absolute private repository path.")
    try:
        _no_links(root)
        _no_links(root / _SCRIPT)
        if not root.is_dir() or not (root / ".git").exists() or not (root / _SCRIPT).is_file():
            raise PublisherError("The configured publisher must be a Library service Git checkout.")
    except OSError:
        raise PublisherError(
            f"Set {PUBLISHER_ENV} to the private Library checkout containing {_SCRIPT.as_posix()}."
        ) from None
    return root


def get_publisher_config() -> PublisherConfig | None:
    """Cheap source gate and local path validation only; never run a process on the GUI thread."""
    if not _source_checkout():
        return None
    configured = os.environ.get(PUBLISHER_ENV, "").strip()
    if not configured:
        return None
    config = PublisherConfig(Path(configured))
    _validate_config(config)
    return config


def _check_cancel(cancel_event: Event | None, *, publishing: bool = False) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise PublisherCancelled(
            "Publication canceled. Remote state may have changed; the prepared files are retained "
            "for an exact retry."
            if publishing
            else "Publisher operation canceled."
        )


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def _uncertain(message: str) -> str:
    return (
        message + " Remote state may have changed; prepared files are retained for an exact retry."
        if "Remote state may have changed" not in message
        else message
    )


def _run(
    command: list[str],
    root: Path,
    *,
    cancel_event: Event | None,
    timeout: float,
    publishing: bool = False,
) -> bytes:
    """Capture helper output in temporary handles; no pipes, reader threads or raw logging."""
    _check_cancel(cancel_event, publishing=publishing)
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            process = subprocess.Popen(
                command,
                cwd=root,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            raise PublisherError(
                "Could not start the publisher. Check Python, Git and the configured checkout."
            ) from None
        deadline = time.monotonic() + timeout
        pause = Event()
        try:
            while True:
                _check_cancel(cancel_event, publishing=publishing)
                if any(
                    os.fstat(handle.fileno()).st_size > _OUTPUT_LIMIT for handle in (stdout, stderr)
                ):
                    raise PublisherError("Publisher output exceeded its safe limit.")
                if time.monotonic() >= deadline:
                    raise PublisherError(
                        "Publisher timed out; retry after checking repository access."
                    )
                if process.poll() is not None:
                    break
                pause.wait(0.05)
            _check_cancel(cancel_event, publishing=publishing)
            stdout.seek(0)
            output = stdout.read(_OUTPUT_LIMIT + 1)
            if len(output) > _OUTPUT_LIMIT:
                raise PublisherError("Publisher output exceeded its safe limit.")
            if process.returncode != 0:
                raise PublisherError(
                    _failure_message(
                        output,
                        "Publishing was not confirmed."
                        if publishing
                        else "Publisher access check failed. Configure noninteractive "
                        "GitHub credentials with private repository write access.",
                    )
                )
            return output
        except PublisherCancelled:
            raise
        except (PublisherError, OSError) as error:
            message = (
                str(error) if isinstance(error, PublisherError) else "Publisher storage failed."
            )
            raise PublisherError(_uncertain(message) if publishing else message) from None
        finally:
            try:
                _stop(process)
            except (OSError, subprocess.TimeoutExpired):
                message = "The publisher helper could not be stopped. Check it before retrying."
                raise PublisherError(_uncertain(message) if publishing else message) from None


def _failure_message(raw: bytes, fallback: str) -> str:
    """Only the private helper's bounded error contract may become UI text."""
    try:
        result = json.loads(raw)
        message = result.get("error") if isinstance(result, dict) else None
        if (
            isinstance(message, str)
            and 0 < len(message) <= 1024
            and message.strip()
            and all(ord(character) >= 32 for character in message)
        ):
            return message
    except (ValueError, UnicodeError, RecursionError):
        pass
    return fallback


def _json_result(raw: bytes) -> dict[str, object]:
    try:
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("not an object")
        return result
    except (ValueError, UnicodeError, RecursionError):
        raise PublisherError(
            "The publisher returned invalid confirmation data. No success was confirmed."
        ) from None


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
    def __init__(self, config: PublisherConfig) -> None:
        if not _source_checkout():
            raise PublisherError(
                "Developer publishing is available only from a Studio source checkout."
            )
        self.config = config
        _validate_config(config)
        self._prepared: dict[Path, PreparedPublication] = {}
        self._directories: dict[Path, tuple[int, int]] = {}

    def _validated_root(self, cancel_event: Event | None) -> Path:
        root = _validate_config(self.config)
        remote = _run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            root,
            cancel_event=cancel_event,
            timeout=_ACCESS_TIMEOUT,
        )
        try:
            url = remote.decode("utf-8").strip().lower()
        except UnicodeError:
            raise PublisherError("The publisher checkout has an invalid GitHub remote.") from None
        expected = REPOSITORY.lower()
        allowed = {
            f"https://github.com/{expected}",
            f"https://github.com/{expected}.git",
            f"git@github.com:{expected}",
            f"git@github.com:{expected}.git",
            f"ssh://git@github.com/{expected}",
            f"ssh://git@github.com/{expected}.git",
        }
        if url not in allowed:
            raise PublisherError(
                f"Publisher origin must point to the private {REPOSITORY} repository."
            )
        return root

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
        root = self._validated_root(cancel_event)
        raw = _run(
            [sys.executable, str(root / _SCRIPT), "--check-access"],
            root,
            cancel_event=cancel_event,
            timeout=_ACCESS_TIMEOUT,
        )
        return self._access(_json_result(raw))

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
        root = self._validated_root(cancel_event)
        tag = prepared.request.release_tag
        try:
            raw = _run(
                [
                    sys.executable,
                    str(root / _SCRIPT),
                    "--publish-online",
                    "--tag",
                    tag,
                    "--bundle-directory",
                    str(prepared.directory),
                ],
                root,
                cancel_event=cancel_event,
                timeout=_PUBLISH_TIMEOUT,
                publishing=True,
            )
            result = _json_result(raw)
            self._access(result)
            commit = result.get("catalog_commit")
            if (
                result.get("tag") != tag
                or not isinstance(commit, str)
                or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit)
            ):
                raise PublisherError("GitHub catalog publication was not confirmed.")
            return PublicationResult(REPOSITORY, tag, commit)
        except PublisherCancelled:
            raise
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
