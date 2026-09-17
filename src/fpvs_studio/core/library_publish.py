"""Prepare a clean, ordinary whole-project bundle for the private library.

This explicit publishing path never changes normal project exports or the source
experiment. The compiler's source resolver and manifest remain the asset owners.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path, PureWindowsPath
from threading import Event
from typing import Any

from fpvs_studio import __version__
from fpvs_studio.core.compiler_assets import resolve_image_paths
from fpvs_studio.core.enums import StimulusModality, StimulusVariant
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.paths import (
    filesystem_path,
    resolve_project_relative_path,
    to_project_relative_posix,
)
from fpvs_studio.core.project_bundle import (
    ProjectBundleCancelled,
    ProjectBundleError,
    export_project_bundle,
    import_project_bundle,
)
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.task_assets import SUPPORTED_TASK_ASSET_SUFFIXES, task_image_references
from fpvs_studio.preprocessing.manifest import read_stimulus_manifest, write_stimulus_manifest
from fpvs_studio.preprocessing.models import StimulusManifest

# GitHub requires each Release asset to be strictly smaller than 2 GiB.
GITHUB_RELEASE_ASSET_LIMIT = 2 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class LibraryBundlePreparation:
    """Reviewable inventory and content facts, without remote publishing authority."""

    project_id: str
    title: str
    category: str
    minimum_studio_version: str
    bundle_schema_version: str
    project_schema_version: str
    condition_count: int
    stimulus_set_count: int
    task_count: int
    file_count: int
    size_bytes: int
    sha256: str
    included_paths: tuple[str, ...]
    excluded_paths: tuple[str, ...]
    sanitized_fields: tuple[str, ...]
    dry_run: bool

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-ready metadata for the publisher's explicit catalog review."""
        return asdict(self)


def _check_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise ProjectBundleCancelled("Library bundle preparation cancelled.")


def _validate_provenance(value: object) -> None:
    """Refuse untyped manifest provenance that carries local paths or credentials."""
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in {
                "password",
                "token",
                "access_token",
                "api_key",
                "secret",
                "private_key",
            }:
                raise ProjectBundleError(
                    "Remove credentials from derivative provenance before publishing."
                )
            _validate_provenance(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _validate_provenance(child)
    elif isinstance(value, str) and (Path(value).is_absolute() or PureWindowsPath(value).anchor):
        raise ProjectBundleError(
            "Remove machine-local paths from derivative provenance before publishing."
        )


def _clean_inventory(
    source_root: Path,
    project: ProjectFile,
    manifest: StimulusManifest,
) -> tuple[ProjectFile, StimulusManifest, set[str]]:
    if manifest.project_id != project.meta.project_id:
        raise ProjectBundleError("Stimulus manifest does not belong to this project.")
    clean = project.model_copy(deep=True)
    clean.manual_removed_electrodes = {}
    clean.settings.display.monitor_name = None
    # Library experiments use COM3 until local serial-port editing is available.
    clean.settings.triggers.serial_port = "COM3"
    clean.settings.condition_profile_id = None
    referenced_sets = {
        set_id
        for condition in clean.conditions
        for set_id in (
            condition.base_stimulus_set_id,
            condition.oddball_stimulus_set_id,
            condition.t2_stimulus_set_id,
            condition.isi_stimulus_set_id,
        )
        if set_id is not None
    }
    clean.stimulus_sets = [item for item in clean.stimulus_sets if item.set_id in referenced_sets]
    clean_manifest = manifest.model_copy(deep=True)
    clean_manifest.sets = [item for item in clean_manifest.sets if item.set_id in referenced_sets]
    paths: set[str] = set()
    for stimulus_set in clean.stimulus_sets:
        if stimulus_set.modality != StimulusModality.IMAGE:
            continue
        condition_variants = {
            condition.stimulus_variant
            for condition in clean.conditions
            if stimulus_set.set_id
            in {
                condition.base_stimulus_set_id,
                condition.oddball_stimulus_set_id,
                condition.t2_stimulus_set_id,
                condition.isi_stimulus_set_id,
            }
        }
        for variant in {
            StimulusVariant.ORIGINAL,
            *stimulus_set.available_variants,
            *condition_variants,
        }:
            paths.update(
                resolve_image_paths(
                    stimulus_set,
                    variant=variant,
                    project_root=source_root,
                    manifest=clean_manifest,
                )
            )
    for manifest_set in clean_manifest.sets:
        for asset in manifest_set.assets:
            paths.add(asset.source.relative_path)
            for derivative in asset.derivatives:
                _validate_provenance(derivative.parameters)
                paths.add(derivative.relative_path)
    for task in clean.task_modules:
        for relative in task_image_references(task):
            if not relative.startswith(f"stimuli/task-assets/{task.task_id}/"):
                raise ProjectBundleError(f"Task image is outside its task folder: {relative}")
            paths.add(relative)
    for relative in paths:
        if (
            not relative.startswith("stimuli/")
            or Path(relative).suffix.lower() not in SUPPORTED_TASK_ASSET_SUFFIXES
        ):
            raise ProjectBundleError(f"Unsupported library stimulus asset: {relative}")
        if not resolve_project_relative_path(source_root, relative).is_file():
            raise ProjectBundleError(f"Required library stimulus asset is missing: {relative}")
    # Revalidate copied models, including task/modifier references, before writing them.
    return ProjectFile.model_validate(clean.model_dump()), clean_manifest, paths


def prepare_library_bundle(
    source: Path,
    bundle_path: Path,
    *,
    minimum_studio_version: str = __version__,
    dry_run: bool = False,
    cancel_event: Event | None = None,
) -> LibraryBundlePreparation:
    """Validate a sanitized copy and optionally publish its local bundle atomically.

    ``source`` may be a saved project directory or an existing ordinary bundle.
    Dry-run still compiles and hashes a temporary bundle, then removes the copy.
    Inspect the inventory and authored text/images before uploading any real study.
    """
    if not re.fullmatch(r"\d+\.\d+\.\d+", minimum_studio_version):
        raise ProjectBundleError("Minimum Studio version must use major.minor.patch.")
    _check_cancelled(cancel_event)
    source = filesystem_path(Path(source))
    destination = filesystem_path(Path(bundle_path))
    if destination.suffix.lower() != ".fpvsbundle":
        raise ProjectBundleError("Library output must use the .fpvsbundle extension.")
    if source.resolve() == destination.resolve() or (
        source.is_dir() and destination.resolve().is_relative_to(source.resolve())
    ):
        raise ProjectBundleError("Library output must be outside the source project or bundle.")
    if destination.exists():
        raise ProjectBundleError("Library output already exists; choose a new versioned filename.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".library-publish-", dir=destination.parent
    ) as temporary:
        staging = filesystem_path(Path(temporary))
        if source.is_dir():
            source_root = source
        elif source.is_file() and source.suffix.lower() == ".fpvsbundle":
            source_root = import_project_bundle(
                source,
                staging / "unpacked",
                cancel_event=cancel_event,
            ).project_root
        else:
            raise ProjectBundleError(
                "Library source must be a saved project folder or .fpvsbundle."
            )
        source_root = filesystem_path(source_root)
        original_project = (source_root / "project.json").read_bytes()
        original_manifest = (source_root / "stimuli" / "manifest.json").read_bytes()
        project = load_project_file(source_root / "project.json")
        manifest = read_stimulus_manifest(source_root)
        clean, clean_manifest, paths = _clean_inventory(source_root, project, manifest)
        clean_root = staging / "project"
        clean_root.mkdir()
        for relative in sorted(paths):
            _check_cancelled(cancel_event)
            source_path = resolve_project_relative_path(source_root, relative)
            target = resolve_project_relative_path(clean_root, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            with source_path.open("rb") as handle, target.open("xb") as output:
                for chunk in iter(lambda: handle.read(65536), b""):
                    _check_cancelled(cancel_event)
                    output.write(chunk)
        if original_project != (source_root / "project.json").read_bytes() or (
            original_manifest != (source_root / "stimuli" / "manifest.json").read_bytes()
        ):
            raise ProjectBundleError("Source project changed during preparation; save and retry.")
        save_project_file(clean, clean_root / "project.json")
        write_stimulus_manifest(clean_root, clean_manifest)
        temporary_bundle = staging / destination.name
        bundle_manifest = export_project_bundle(
            clean_root, temporary_bundle, cancel_event=cancel_event
        )
        size_bytes = temporary_bundle.stat().st_size
        if size_bytes >= GITHUB_RELEASE_ASSET_LIMIT:
            raise ProjectBundleError("GitHub library bundles must be smaller than 2 GiB.")
        # Exercise the ordinary integrity/extraction/compile contract before publication.
        import_project_bundle(temporary_bundle, staging / "verified", cancel_event=cancel_event)
        digest = hashlib.sha256()
        with temporary_bundle.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                _check_cancelled(cancel_event)
                digest.update(chunk)
        included = tuple(record.path for record in bundle_manifest.files)
        excluded = tuple(
            sorted(
                to_project_relative_posix(source_root, path)
                for path in source_root.rglob("*")
                if path.is_file() and to_project_relative_posix(source_root, path) not in included
            )
        )
        result = LibraryBundlePreparation(
            project_id=clean.meta.project_id,
            title=clean.meta.name,
            category=clean.experiment_category.value,
            minimum_studio_version=minimum_studio_version,
            bundle_schema_version=bundle_manifest.schema_version,
            project_schema_version=clean.schema_version.value,
            condition_count=len(clean.conditions),
            stimulus_set_count=len(clean.stimulus_sets),
            task_count=len(clean.task_modules),
            file_count=len(included),
            size_bytes=size_bytes,
            sha256=digest.hexdigest(),
            included_paths=included,
            excluded_paths=excluded,
            sanitized_fields=(
                "manual_removed_electrodes",
                "settings.display.monitor_name",
                "settings.triggers.serial_port",
                "settings.condition_profile_id",
            ),
            dry_run=dry_run,
        )
        _check_cancelled(cancel_event)
        if not dry_run:
            # Same-volume, exclusive publication: readers never see a partial bundle.
            os.link(temporary_bundle, destination)
        return result
