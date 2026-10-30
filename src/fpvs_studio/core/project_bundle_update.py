"""Explicit Library updates of authored files, with local data and a recoverable backup."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import stat
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event

from packaging.version import Version

from fpvs_studio.core.library_origin import (
    ORIGIN_DIRECTORY,
    ORIGIN_FILENAME,
    LibraryOriginError,
    LibraryProjectOrigin,
    canonical_library_service_url,
    load_library_origin,
    origin_for_import,
    save_library_origin,
)
from fpvs_studio.core.models import ProjectFile, utc_now
from fpvs_studio.core.paths import app_data_dir, filesystem_path
from fpvs_studio.core.project_bundle import (
    MAX_BUNDLE_PROJECT_JSON_BYTES,
    ProjectBundleCancelled,
    ProjectBundleError,
    _extract_bundle_to_staging,
    _load_manifest_for_bundle,
    _load_project_for_bundle,
    _validate_bundle_source,
)
from fpvs_studio.core.project_service import ProjectScaffold
from fpvs_studio.core.serialization import atomic_text_write, load_project_file, save_project_file
from fpvs_studio.preprocessing.manifest import read_stimulus_manifest, write_stimulus_manifest
from fpvs_studio.preprocessing.models import StimulusManifest

_LOGGER = logging.getLogger(__name__)
_OWNED = ("project.json", "stimuli", f"{ORIGIN_DIRECTORY}/{ORIGIN_FILENAME}")
_LOCAL_DISPLAY = (
    "fullscreen",
    "monitor_name",
    "preferred_refresh_hz",
    "viewing_distance_cm",
    "screen_width_cm",
    "screen_width_px",
    "screen_height_px",
    "use_current_screen_resolution",
)
_LOCAL_TRIGGERS = (
    "backend",
    "enabled",
    "serial_port",
    "baudrate",
    "pulse_width_ms",
    "reset_code",
    "reset_delay_ms",
)


class ProjectBundleRecoveryError(ProjectBundleError):
    """A blocked rollback requires restoring retained authored files before editing."""

    def __init__(self, backup_path: Path) -> None:
        self.backup_path = backup_path
        super().__init__(
            "Project update could not restore every file. Close the project "
            f"and restore its backup at {backup_path}."
        )


@dataclass(frozen=True)
class ProjectUpdateSnapshot:
    """A reviewed saved authoring state; participant/output files are outside this token."""

    project_root: Path
    project_id: str
    origin: LibraryProjectOrigin
    fingerprint: str


@dataclass(frozen=True)
class ProjectBundleUpdateResult:
    scaffold: ProjectScaffold
    backup_path: Path
    manifest: StimulusManifest


def _cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise ProjectBundleCancelled("Project update cancelled before installation.")


def _regular(path: Path, *, directory: bool) -> None:
    info = filesystem_path(path).lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ProjectBundleError("Project update paths cannot contain links or reparse points.")
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ProjectBundleError("Project update paths must be ordinary files and directories.")
    if not directory and info.st_nlink != 1:
        raise ProjectBundleError("Project update files cannot have additional hard links.")


def _root(path: Path) -> Path:
    root = Path(path).expanduser().absolute()
    for candidate in (root, *root.parents):
        _regular(candidate, directory=True)
    return root.resolve()


def _fingerprint(root: Path, cancel_event: Event | None) -> str:
    digest = hashlib.sha256()
    observed: dict[Path, tuple[int, int, int, int]] = {}
    for relative in _OWNED:
        base = filesystem_path(root / relative)
        paths = [base]
        if not base.exists():
            digest.update((relative + "\0missing\0").encode())
            continue
        if base.is_dir():
            pending = [base]
            paths = []
            while pending:
                _cancelled(cancel_event)
                directory = pending.pop()
                _regular(directory, directory=True)
                info = directory.stat()
                observed[directory] = (
                    info.st_ino,
                    info.st_size,
                    info.st_mtime_ns,
                    info.st_ctime_ns,
                )
                children = sorted(directory.iterdir(), key=lambda item: item.name)
                folded = [child.name.casefold() for child in children]
                if len(folded) != len(set(folded)):
                    raise ProjectBundleError("Project update found paths differing only by case.")
                paths.append(directory)
                for child in children:
                    _regular(child, directory=child.is_dir())
                    if child.is_dir():
                        pending.append(child)
                    else:
                        paths.append(child)
        for path in paths:
            _cancelled(cancel_event)
            is_directory = path.is_dir()
            _regular(path, directory=is_directory)
            digest.update(path.relative_to(filesystem_path(root)).as_posix().encode("utf-8"))
            digest.update(b"\0directory\0" if is_directory else b"\0file\0")
            if is_directory:
                continue
            before = path.stat()
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(65536), b""):
                    _cancelled(cancel_event)
                    digest.update(block)
            after = path.stat()
            if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise ProjectBundleError(
                    "Project changed during update review. Save and try again."
                )
            observed[path] = (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            digest.update(b"\0end\0")
    for path, previous_stamp in observed.items():
        _cancelled(cancel_event)
        info = path.stat()
        if previous_stamp != (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns):
            raise ProjectBundleError("Project changed during update review. Save and try again.")
    return digest.hexdigest()


def capture_project_update_snapshot(
    project_root: Path,
    *,
    cancel_event: Event | None = None,
) -> ProjectUpdateSnapshot:
    """Capture saved authored bytes before downloading, without reading participant data."""
    try:
        root = _root(project_root)
        _cancelled(cancel_event)
        project = load_project_file(
            root / "project.json", maximum_bytes=MAX_BUNDLE_PROJECT_JSON_BYTES
        )
        origin = load_library_origin(root)
        if origin is None or origin.installed_version is None:
            raise ProjectBundleError(
                "Review and link the installed Library version before updating."
            )
        if origin.local_project_id != project.meta.project_id:
            raise ProjectBundleError("Project identity does not match its Library link.")
        return ProjectUpdateSnapshot(
            root, project.meta.project_id, origin, _fingerprint(root, cancel_event)
        )
    except ProjectBundleError:
        raise
    except (OSError, ValueError) as error:
        raise ProjectBundleError(
            "Project update could not read the saved project safely."
        ) from error


def _mkdirs(root: Path, parts: tuple[str, ...]) -> Path:
    """Create only contained real directories, checking existing ancestors before use."""
    current = root
    _regular(current, directory=True)
    for part in parts:
        current /= part
        try:
            _regular(current, directory=True)
        except FileNotFoundError:
            filesystem_path(current).mkdir()
            _regular(current, directory=True)
    return current


def _local_project(incoming: ProjectFile, current: ProjectFile) -> ProjectFile:
    updated = incoming.model_copy(deep=True)
    updated.meta = updated.meta.model_copy(
        update={
            "project_id": current.meta.project_id,
            "name": current.meta.name,
            "created_at": current.meta.created_at,
            "updated_at": utc_now(),
        }
    )
    updated.settings.display = updated.settings.display.model_copy(
        update={field: getattr(current.settings.display, field) for field in _LOCAL_DISPLAY}
    )
    updated.settings.triggers = updated.settings.triggers.model_copy(
        update={field: getattr(current.settings.triggers, field) for field in _LOCAL_TRIGGERS}
    )
    updated.settings.recording = (
        current.settings.recording.model_copy(deep=True) if current.settings.recording else None
    )
    updated.settings.condition_profile_id = current.settings.condition_profile_id
    updated.settings.allow_repeated_participant_sessions = (
        current.settings.allow_repeated_participant_sessions
    )
    updated.manual_removed_electrodes = {
        key: list(value) for key, value in current.manual_removed_electrodes.items()
    }
    return ProjectFile.model_validate(updated.model_dump())


def _move(source: Path, target: Path) -> None:
    if filesystem_path(target).exists():
        raise ProjectBundleError(
            "Project update destination changed. Close other editors and retry."
        )
    filesystem_path(source).rename(filesystem_path(target))


def _check_bundle_digest(path: Path, expected: str, cancel_event: Event | None) -> None:
    _regular(path, directory=False)
    digest = hashlib.sha256()
    with filesystem_path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            _cancelled(cancel_event)
            digest.update(block)
    if digest.hexdigest() != expected:
        raise ProjectBundleError("Library bundle does not match its origin checksum.")


def _cleanup(path: Path, owner: Path) -> None:
    """Remove only this transaction's contained staging tree; never follow links."""
    if not filesystem_path(path).exists():
        return
    if path.resolve().parent != owner.resolve():
        raise ProjectBundleError("Project update cleanup escaped its staging owner.")
    for item in [filesystem_path(path), *filesystem_path(path).rglob("*")]:
        _regular(item, directory=item.is_dir())
    shutil.rmtree(filesystem_path(path))


def update_project_bundle(
    bundle_path: Path,
    project_root: Path,
    studio_root: Path,
    *,
    library_origin: LibraryProjectOrigin,
    expected_snapshot: ProjectUpdateSnapshot,
    cancel_event: Event | None = None,
    progress_callback: Callable[[str], None] | None = None,
    precommit_check: Callable[[], None] | None = None,
) -> ProjectBundleUpdateResult:
    """Replace explicitly reviewed authored files; preserve local data and exact old assets.

    Ordinary imports keep their no-replacement contract. Once the rename transaction
    begins, late cancellation is ignored so a completed update is returned as success.
    """
    stage: Path | None = None
    staging_parent: Path | None = None
    backup: Path | None = None
    backup_parent: Path | None = None
    retain_recovery = False
    committed = False
    try:
        root = _root(project_root)
        studio = _root(studio_root)
        try:
            relative = root.relative_to(studio)
        except ValueError as error:
            raise ProjectBundleError(
                "The project must be under the configured Studio Root Folder to update."
            ) from error
        if (
            not relative.parts
            or relative.parts[0].casefold() == app_data_dir(studio).name.casefold()
        ):
            raise ProjectBundleError(
                "Choose an active project folder, not the Studio root or a backup."
            )
        current_path = studio
        for component in relative.parts:
            current_path /= component
            _regular(current_path, directory=True)
        snapshot = capture_project_update_snapshot(root, cancel_event=cancel_event)
        if snapshot != expected_snapshot:
            raise ProjectBundleError(
                "Project changed after update review. Save and check the version again."
            )
        previous = snapshot.origin
        if (
            canonical_library_service_url(previous.service_url)
            != canonical_library_service_url(library_origin.service_url)
            or previous.item_id != library_origin.item_id
            or library_origin.installed_version is None
            or library_origin.bundle_sha256 is None
            or Version(library_origin.installed_version)
            <= Version(previous.installed_version or "0")
        ):
            raise ProjectBundleError(
                "Select a newer version of this project's linked Library experiment."
            )
        current = load_project_file(
            root / "project.json", maximum_bytes=MAX_BUNDLE_PROJECT_JSON_BYTES
        )
        staging_parent = _mkdirs(studio, (app_data_dir(studio).name, "project-update-staging"))
        stage = _mkdirs(staging_parent, (f"update-{uuid.uuid4().hex}",))
        if progress_callback:
            progress_callback("verify")
        _check_bundle_digest(bundle_path, library_origin.bundle_sha256, cancel_event)
        staged_project = _mkdirs(stage, ("project",))
        bundle_manifest = _extract_bundle_to_staging(
            bundle_path,
            filesystem_path(staged_project),
            library_safe=True,
            cancel_event=cancel_event,
        )
        incoming = _load_project_for_bundle(staged_project)
        incoming_manifest = _load_manifest_for_bundle(staged_project)
        _validate_bundle_source(
            staged_project,
            project=incoming,
            manifest=incoming_manifest,
            refresh_hz=bundle_manifest.validation.refresh_hz,
            cancel_event=cancel_event,
        )
        imported = ProjectScaffold(staged_project, incoming)
        if imported.project.experiment_category != current.experiment_category:
            raise ProjectBundleError(
                "The new Library version changes this project's experiment category."
            )
        updated = _local_project(imported.project, current)
        manifest = read_stimulus_manifest(imported.project_root).model_copy(
            update={"project_id": snapshot.project_id}
        )
        save_project_file(updated, imported.project_root / "project.json")
        write_stimulus_manifest(imported.project_root, manifest)
        new_origin = origin_for_import(library_origin, snapshot.project_id).model_copy(
            update={"auto_check": previous.auto_check}
        )
        save_library_origin(imported.project_root, new_origin)
        refresh = (
            updated.settings.display.preferred_refresh_hz or bundle_manifest.validation.refresh_hz
        )
        try:
            _validate_bundle_source(
                imported.project_root,
                project=updated,
                manifest=manifest,
                refresh_hz=refresh,
                cancel_event=cancel_event,
            )
        except ProjectBundleCancelled:
            raise
        except ProjectBundleError as error:
            raise ProjectBundleError(
                "The new version cannot use this project's local display setup. "
                "Download separately to review its setup. " + str(error)
            ) from error
        if capture_project_update_snapshot(root, cancel_event=cancel_event) != expected_snapshot:
            raise ProjectBundleError(
                "Project changed during download. Save and check the version again."
            )
        backup_parent = _mkdirs(
            studio, (app_data_dir(studio).name, "project-backups", snapshot.project_id)
        )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = _mkdirs(backup_parent, (f"{stamp}-{uuid.uuid4().hex[:12]}",))
        _mkdirs(backup, (ORIGIN_DIRECTORY,))
        journal = {
            "schema_version": "1.0",
            "project_root": str(root),
            "status": "prepared",
            "previous_origin": previous.model_dump(),
            "new_origin": new_origin.model_dump(),
        }
        atomic_text_write(backup / "update.json", json.dumps(journal, indent=2))
        atomic_text_write(
            backup / "RESTORE.txt",
            "Authored project backup before a Library update.\n"
            f"Project folder: {root}\nPrevious version: {previous.installed_version}\n\n"
            "To restore, close this project in Studio. Preserve its current authored files, "
            "then copy project.json, stimuli, and .fpvs-library/project-origin.json from "
            "this backup to the project folder. Participant data, runs, logs, and other "
            "local files were left in place and are not part of this backup.\n",
        )
        _cancelled(cancel_event)
        if progress_callback:
            progress_callback("commit")
        _cancelled(cancel_event)
        if capture_project_update_snapshot(root, cancel_event=cancel_event) != expected_snapshot:
            raise ProjectBundleError(
                "Project changed during update review. Save and check its version again."
            )
        if precommit_check is not None:
            precommit_check()
        _cancelled(cancel_event)
        moves: list[tuple[Path, Path]] = []
        try:
            for name in _OWNED:
                source = root / name
                if filesystem_path(source).exists():
                    target = backup / name
                    _move(source, target)
                    moves.append((source, target))
            for name in ("stimuli", "project.json", f"{ORIGIN_DIRECTORY}/{ORIGIN_FILENAME}"):
                source, target = imported.project_root / name, root / name
                _move(source, target)
                moves.append((source, target))
            journal["status"] = "complete"
            atomic_text_write(backup / "update.json", json.dumps(journal, indent=2))
            committed = True
        except Exception as error:
            try:
                for source, target in reversed(moves):
                    _move(target, source)
            except Exception as rollback_error:
                retain_recovery = True
                _LOGGER.exception("Project update rollback failed; recovery retained at %s", backup)
                raise ProjectBundleRecoveryError(backup) from rollback_error
            raise ProjectBundleError(
                "Project update failed; the original project was restored. "
                "Close other applications using its files and retry."
            ) from error
        return ProjectBundleUpdateResult(ProjectScaffold(root, updated), backup, manifest)
    except (OSError, LibraryOriginError) as error:
        raise ProjectBundleError(
            "Project update could not access its files. Close other applications "
            "and check free space, then retry."
        ) from error
    finally:
        for cleanup_target, owner in (
            (stage, staging_parent),
            (backup if not committed else None, backup_parent),
        ):
            if cleanup_target is not None and owner is not None and not retain_recovery:
                try:
                    _cleanup(cleanup_target, owner)
                except (OSError, ProjectBundleError):
                    _LOGGER.warning(
                        "Could not clean project update staging at %s",
                        cleanup_target,
                        exc_info=True,
                    )
