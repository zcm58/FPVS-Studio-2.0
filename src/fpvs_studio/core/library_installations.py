"""Read-only discovery and duplicate decisions for local Library experiments."""

from __future__ import annotations

import json
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Literal

from packaging.version import Version

from fpvs_studio.core.library_origin import (
    LibraryOriginError,
    LibraryProjectOrigin,
    load_library_origin,
)
from fpvs_studio.core.models import ProjectMeta
from fpvs_studio.core.paths import filesystem_path, is_reserved_root_entry_name


@dataclass(frozen=True)
class InstalledLibraryProject:
    root: Path
    meta: ProjectMeta
    origin: LibraryProjectOrigin | None


@dataclass(frozen=True)
class LibraryInstallStatus:
    state: Literal["new", "installed", "update", "review"]
    project: InstalledLibraryProject | None = None

    @property
    def message(self) -> str:
        if self.project is None:
            return "This experiment is not installed in the Studio Root Folder."
        prefix = {
            "installed": "This version or a newer version is already installed.",
            "update": "An older version is installed. Review its update before downloading.",
            "review": "A possible existing copy has no Library version. Review its link first.",
        }[self.state]
        return f"{prefix}\n{self.project.root}"


def scan_library_projects(
    studio_root: Path, *, cancel_event: Event | None = None,
) -> tuple[InstalledLibraryProject, ...]:
    """Visit project metadata only; never descend into stimuli, runs or app storage."""
    root = Path(studio_root).resolve()
    if not filesystem_path(root).is_dir():
        raise LibraryOriginError("The Studio Root Folder is unavailable. Choose it in Settings.")
    pending = [root]
    projects = []
    while pending:
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("Installed-project check canceled.")
        folder = pending.pop()
        try:
            info = filesystem_path(folder).lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise LibraryOriginError(f"Cannot check a linked project directory: {folder}")
            if not folder.resolve().is_relative_to(root):
                raise LibraryOriginError(f"Project directory escapes the Studio Root: {folder}")
            path = filesystem_path(folder / "project.json")
            if path.exists():
                if path.is_symlink() or not path.resolve().is_relative_to(
                    filesystem_path(folder).resolve(),
                ):
                    raise LibraryOriginError(f"Cannot check linked project metadata: {folder}")
                with path.open(encoding="utf-8-sig") as stream:
                    payload = json.load(stream)
                meta = ProjectMeta.model_validate(payload["meta"])
                origin = load_library_origin(folder)
                if origin is not None and origin.local_project_id != meta.project_id:
                    raise LibraryOriginError(f"Library record belongs to another project: {folder}")
                projects.append(InstalledLibraryProject(folder, meta, origin))
                continue
            pending.extend(
                folder / child.name for child in filesystem_path(folder).iterdir()
                if not is_reserved_root_entry_name(child.name)
                and not child.name.startswith(".") and child.is_dir()
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise LibraryOriginError(
                f"Could not verify installed projects at {folder}: {error}"
            ) from error
    return tuple(sorted(projects, key=lambda project: str(project.root).casefold()))


def library_install_status(
    projects: tuple[InstalledLibraryProject, ...], *, service_url: str,
    item_id: str, version: str, title: str = "",
) -> LibraryInstallStatus:
    """Names identify review candidates only; they never create a Library association."""
    linked = [
        project for project in projects if project.origin is not None
        and project.origin.service_url == service_url and project.origin.item_id == item_id
    ]
    known = [
        (Version(project.origin.installed_version), project) for project in linked
        if project.origin is not None and project.origin.installed_version is not None
    ]
    if known:
        newest_version, newest = max(known, key=lambda pair: pair[0])
        if newest_version >= Version(version):
            return LibraryInstallStatus("installed", newest)
    unknown = [
        project for project in linked if project.origin and not project.origin.installed_version
    ]
    if unknown:
        return LibraryInstallStatus("review", unknown[0])
    if known:
        return LibraryInstallStatus("update", newest)
    for project in projects:
        if project.origin is not None:
            continue
        original_id = re.sub(r"(?:-from-bundle(?:-\d+)?)+$", "", project.meta.project_id)
        if original_id == item_id or (
            title and project.meta.name.strip().casefold() == title.strip().casefold()
        ):
            return LibraryInstallStatus("review", project)
    return LibraryInstallStatus("new")
