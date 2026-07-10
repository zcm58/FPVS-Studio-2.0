"""Portable FPVS Studio project bundle import/export contracts.

Project bundles are ZIP-backed `.fpvsbundle` files that carry the editable project
source of truth plus stimulus assets. The bundle manifest validates archive integrity;
`project.json` and `stimuli/manifest.json` remain the canonical project contracts.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import uuid
import zipfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import Field, ValidationError, field_validator

from fpvs_studio import __version__
from fpvs_studio.core.compiler import CompileError, compile_session_plan
from fpvs_studio.core.models import FPVSBaseModel, ProjectFile, validate_project_relative_path
from fpvs_studio.core.paths import (
    MANIFEST_FILENAME,
    PROJECT_FILENAME,
    STIMULI_DIRNAME,
    app_data_dir,
    cache_dir,
    logs_dir,
    project_dir,
    project_json_path,
    runs_dir,
    slugify_project_name,
    stimuli_dir,
    stimulus_generated_variants_root,
    stimulus_manifest_path,
    stimulus_original_images_root,
    to_project_relative_posix,
    validate_project_id,
)
from fpvs_studio.core.project_service import ProjectScaffold
from fpvs_studio.core.serialization import (
    load_project_file,
    model_to_json,
    read_json_file,
    save_project_file,
)
from fpvs_studio.preprocessing.manifest import read_stimulus_manifest, write_stimulus_manifest
from fpvs_studio.preprocessing.models import StimulusManifest

BUNDLE_SCHEMA_VERSION = "1.0.0"
PROJECT_BUNDLE_SUFFIX = ".fpvsbundle"
BUNDLE_MANIFEST_FILENAME = "fpvs_bundle.json"
IMPORT_STAGING_DIRNAME = "import-staging"
_BUNDLE_FILENAME_RE = re.compile(r"[^a-z0-9]+")
_DEFAULT_VALIDATION_REFRESH_HZ = 60.0

BundleExportStage = Literal["validate", "stimuli", "write", "complete"]
BundleExportProgressCallback = Callable[[BundleExportStage], None]
BundleImportStage = Literal["verify", "base", "oddball", "project", "complete"]
BundleImportProgressCallback = Callable[[BundleImportStage], None]


class ProjectBundleError(ValueError):
    """Raised when a project bundle cannot be created, read, or imported safely."""


def project_bundle_filename(project_name: str) -> str:
    """Return the default user-facing bundle filename for a project title."""

    normalized = _BUNDLE_FILENAME_RE.sub("", project_name.strip().lower())
    stem = normalized or "fpvsproject"
    return f"{stem}{PROJECT_BUNDLE_SUFFIX}"


class ProjectBundleProducer(FPVSBaseModel):
    """Application metadata for the bundle producer."""

    application: str = "FPVS Studio"
    version: str = __version__
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectBundleProject(FPVSBaseModel):
    """Project identity snapshot stored in bundle metadata."""

    project_id: str
    name: str
    template_id: str


class ProjectBundleFileRecord(FPVSBaseModel):
    """One payload file included in a project bundle."""

    path: str
    size_bytes: int = Field(ge=0)
    sha256: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return validate_project_relative_path(value)

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("sha256 must be a 64-character lowercase hex digest.")
        return value


class ProjectBundleValidation(FPVSBaseModel):
    """Export-side validation summary captured in the bundle."""

    status: Literal["passed"] = "passed"
    validated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    refresh_hz: float = Field(gt=0)
    checks: list[str] = Field(default_factory=list)


class ProjectBundleManifest(FPVSBaseModel):
    """Top-level manifest stored as `fpvs_bundle.json` inside a bundle."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    producer: ProjectBundleProducer = Field(default_factory=ProjectBundleProducer)
    project: ProjectBundleProject
    validation: ProjectBundleValidation
    files: list[ProjectBundleFileRecord]


def export_project_bundle(
    project_root: Path,
    bundle_path: Path,
    *,
    project_name: str | None = None,
    refresh_hz: float | None = None,
    progress_callback: BundleExportProgressCallback | None = None,
) -> ProjectBundleManifest:
    """Validate and write a portable `.fpvsbundle` for one saved project."""

    project_root = Path(project_root)
    bundle_path = Path(bundle_path)
    _notify_export_progress(progress_callback, "validate")
    project = _load_project_for_bundle(project_root)
    manifest = _load_manifest_for_bundle(project_root)
    payload_overrides: dict[str, bytes] = {}
    if project_name is not None:
        project, manifest = _bundle_identity_override(
            project,
            manifest,
            project_name=project_name,
        )
        payload_overrides = _bundle_contract_payloads(project, manifest)
    validation_refresh_hz = refresh_hz or project.settings.display.preferred_refresh_hz
    if validation_refresh_hz is None:
        validation_refresh_hz = _DEFAULT_VALIDATION_REFRESH_HZ

    _validate_bundle_source(
        project_root,
        project=project,
        manifest=manifest,
        refresh_hz=validation_refresh_hz,
    )
    _notify_export_progress(progress_callback, "stimuli")
    relative_paths = _collect_bundle_file_paths(project_root)
    records = [
        _file_record(
            project_root,
            relative_path,
            payload_override=payload_overrides.get(relative_path),
        )
        for relative_path in relative_paths
    ]
    bundle_manifest = ProjectBundleManifest(
        project=ProjectBundleProject(
            project_id=project.meta.project_id,
            name=project.meta.name,
            template_id=project.meta.template_id,
        ),
        validation=ProjectBundleValidation(
            refresh_hz=validation_refresh_hz,
            checks=[
                "project_json_loaded",
                "stimulus_manifest_loaded",
                "stimulus_paths_resolved",
                "session_compile_dry_run_passed",
                "payload_files_hashed",
            ],
        ),
        files=records,
    )
    _notify_export_progress(progress_callback, "write")
    _write_bundle_archive(
        project_root,
        bundle_path,
        bundle_manifest,
        payload_overrides=payload_overrides,
    )
    _notify_export_progress(progress_callback, "complete")
    return bundle_manifest


def _notify_export_progress(
    progress_callback: BundleExportProgressCallback | None,
    stage: BundleExportStage,
) -> None:
    if progress_callback is not None:
        progress_callback(stage)


def _bundle_identity_override(
    project: ProjectFile,
    manifest: StimulusManifest,
    *,
    project_name: str,
) -> tuple[ProjectFile, StimulusManifest]:
    normalized_name = project_name.strip()
    if not normalized_name:
        raise ProjectBundleError("Export project name may not be empty.")
    project_id = slugify_project_name(normalized_name)
    try:
        validate_project_id(project_id)
    except ValueError as exc:
        raise ProjectBundleError(str(exc)) from exc
    updated_meta = project.meta.model_copy(
        update={"name": normalized_name, "project_id": project_id}
    )
    updated_project = project.model_copy(update={"meta": updated_meta})
    updated_manifest = manifest.model_copy(update={"project_id": project_id})
    return updated_project, updated_manifest


def _bundle_contract_payloads(
    project: ProjectFile,
    manifest: StimulusManifest,
) -> dict[str, bytes]:
    return {
        PROJECT_FILENAME: model_to_json(project).encode("utf-8"),
        f"{STIMULI_DIRNAME}/{MANIFEST_FILENAME}": model_to_json(manifest).encode("utf-8"),
    }


def read_project_bundle_manifest(bundle_path: Path) -> ProjectBundleManifest:
    """Read and validate `fpvs_bundle.json` from a `.fpvsbundle` archive."""

    try:
        with zipfile.ZipFile(bundle_path, mode="r") as archive:
            raw_payload = archive.read(BUNDLE_MANIFEST_FILENAME)
    except KeyError as exc:
        raise ProjectBundleError("Project bundle is missing fpvs_bundle.json.") from exc
    except (OSError, zipfile.BadZipFile) as exc:
        raise ProjectBundleError(f"Unable to read project bundle: {bundle_path}") from exc
    try:
        return ProjectBundleManifest.model_validate_json(raw_payload)
    except ValidationError as exc:
        raise ProjectBundleError(f"Project bundle manifest failed validation: {exc}") from exc


def import_project_bundle(
    bundle_path: Path,
    fpvs_root_dir: Path,
    *,
    progress_callback: BundleImportProgressCallback | None = None,
) -> ProjectScaffold:
    """Import a `.fpvsbundle` into a new project folder under the FPVS Studio root."""

    bundle_path = Path(bundle_path)
    fpvs_root_dir = Path(fpvs_root_dir)
    staging_parent = app_data_dir(fpvs_root_dir) / IMPORT_STAGING_DIRNAME
    stage_dir = staging_parent / f"bundle-{uuid.uuid4().hex}"
    staged_project_root = stage_dir / "project"
    try:
        _notify_import_progress(progress_callback, "verify")
        staged_project_root.mkdir(parents=True, exist_ok=False)
        bundle_manifest = _extract_bundle_to_staging(bundle_path, staged_project_root)
        project = _load_project_for_bundle(staged_project_root)
        manifest = read_stimulus_manifest(staged_project_root)
        _notify_import_progress(progress_callback, "base")
        _validate_condition_role_source_dirs(
            staged_project_root,
            project=project,
            role="base",
        )
        _notify_import_progress(progress_callback, "oddball")
        _validate_condition_role_source_dirs(
            staged_project_root,
            project=project,
            role="oddball",
        )
        _validate_bundle_source(
            staged_project_root,
            project=project,
            manifest=manifest,
            refresh_hz=bundle_manifest.validation.refresh_hz,
        )
        _notify_import_progress(progress_callback, "project")
        target_dir, project_id = _unique_import_project_dir(
            fpvs_root_dir,
            project.meta.project_id,
        )
        if project_id != project.meta.project_id:
            project, manifest = _rewrite_imported_project_id(
                staged_project_root,
                project=project,
                manifest=manifest,
                project_id=project_id,
            )
        _ensure_import_project_structure(staged_project_root)
        if target_dir.exists():
            raise ProjectBundleError(f"Imported project target already exists: {target_dir}")
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staged_project_root), str(target_dir))
        _notify_import_progress(progress_callback, "complete")
        return ProjectScaffold(project_root=target_dir, project=project)
    except ProjectBundleError:
        raise
    except Exception as exc:
        raise ProjectBundleError(f"Unable to import project bundle: {bundle_path}") from exc
    finally:
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)


def _notify_import_progress(
    progress_callback: BundleImportProgressCallback | None,
    stage: BundleImportStage,
) -> None:
    if progress_callback is not None:
        progress_callback(stage)


def _load_project_for_bundle(project_root: Path) -> ProjectFile:
    path = project_json_path(project_root)
    if not path.is_file():
        raise ProjectBundleError(f"Project bundle export requires {PROJECT_FILENAME}.")
    try:
        return load_project_file(path)
    except Exception as exc:
        raise ProjectBundleError(f"Unable to load project file for bundle: {path}") from exc


def _load_manifest_for_bundle(project_root: Path) -> StimulusManifest:
    path = stimulus_manifest_path(project_root)
    if not path.is_file():
        raise ProjectBundleError("Project bundle export requires stimuli/manifest.json.")
    try:
        return read_json_file(path, StimulusManifest)
    except Exception as exc:
        raise ProjectBundleError(f"Unable to load stimulus manifest for bundle: {path}") from exc


def _extract_bundle_to_staging(
    bundle_path: Path,
    staged_project_root: Path,
) -> ProjectBundleManifest:
    try:
        with zipfile.ZipFile(bundle_path, mode="r") as archive:
            archive_paths = _validated_archive_file_paths(archive)
            bundle_manifest = _read_bundle_manifest_from_archive(archive)
            expected_paths = {
                BUNDLE_MANIFEST_FILENAME,
                *(record.path for record in bundle_manifest.files),
            }
            if archive_paths != expected_paths:
                missing = sorted(expected_paths - archive_paths)
                unexpected = sorted(archive_paths - expected_paths)
                details: list[str] = []
                if missing:
                    details.append("missing: " + ", ".join(missing))
                if unexpected:
                    details.append("unexpected: " + ", ".join(unexpected))
                raise ProjectBundleError(
                    "Project bundle contents do not match fpvs_bundle.json"
                    + (f" ({'; '.join(details)})" if details else ".")
                )
            for record in bundle_manifest.files:
                _extract_verified_record(archive, record, staged_project_root)
            return bundle_manifest
    except ProjectBundleError:
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        raise ProjectBundleError(f"Unable to read project bundle: {bundle_path}") from exc


def _read_bundle_manifest_from_archive(
    archive: zipfile.ZipFile,
) -> ProjectBundleManifest:
    try:
        raw_payload = archive.read(BUNDLE_MANIFEST_FILENAME)
    except KeyError as exc:
        raise ProjectBundleError("Project bundle is missing fpvs_bundle.json.") from exc
    try:
        return ProjectBundleManifest.model_validate_json(raw_payload)
    except ValidationError as exc:
        raise ProjectBundleError(f"Project bundle manifest failed validation: {exc}") from exc


def _validated_archive_file_paths(archive: zipfile.ZipFile) -> set[str]:
    paths: set[str] = set()
    for info in archive.infolist():
        normalized = _validate_archive_member_name(info.filename)
        if info.is_dir():
            continue
        if normalized in paths:
            raise ProjectBundleError(f"Project bundle contains duplicate file: {normalized}")
        paths.add(normalized)
    return paths


def _validate_archive_member_name(name: str) -> str:
    if "\\" in name:
        raise ProjectBundleError(f"Project bundle contains unsafe member path: {name}")
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(":" in part for part in path.parts)
    ):
        raise ProjectBundleError(f"Project bundle contains unsafe member path: {name}")
    normalized = path.as_posix()
    if normalized == BUNDLE_MANIFEST_FILENAME:
        return normalized
    validate_project_relative_path(normalized)
    if normalized != PROJECT_FILENAME and not normalized.startswith("stimuli/"):
        raise ProjectBundleError(f"Project bundle contains unsupported member: {name}")
    return normalized


def _extract_verified_record(
    archive: zipfile.ZipFile,
    record: ProjectBundleFileRecord,
    staged_project_root: Path,
) -> None:
    destination_path = _staged_destination_path(staged_project_root, record.path)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    with archive.open(record.path, mode="r") as source, destination_path.open("wb") as target:
        for chunk in iter(lambda: source.read(65536), b""):
            size += len(chunk)
            digest.update(chunk)
            target.write(chunk)
    if size != record.size_bytes:
        raise ProjectBundleError(f"Project bundle file size mismatch: {record.path}")
    if digest.hexdigest() != record.sha256:
        raise ProjectBundleError(f"Project bundle checksum mismatch: {record.path}")


def _staged_destination_path(staged_project_root: Path, relative_path: str) -> Path:
    normalized = validate_project_relative_path(relative_path)
    destination_path = (staged_project_root / Path(normalized)).resolve()
    try:
        destination_path.relative_to(staged_project_root.resolve())
    except ValueError as exc:
        raise ProjectBundleError(f"Project bundle path escapes staging: {relative_path}") from exc
    return destination_path


def _validate_bundle_source(
    project_root: Path,
    *,
    project: ProjectFile,
    manifest: StimulusManifest,
    refresh_hz: float,
) -> None:
    if not project_root.is_dir():
        raise ProjectBundleError(f"Project root does not exist: {project_root}")
    if manifest.project_id != project.meta.project_id:
        raise ProjectBundleError(
            "Stimulus manifest project_id does not match project.json project_id."
        )
    for stimulus_set in project.stimulus_sets:
        if stimulus_set.source_dir is None:
            continue
        source_dir = _resolve_existing_relative_dir(project_root, stimulus_set.source_dir)
        if not any(path.is_file() for path in source_dir.iterdir()):
            raise ProjectBundleError(
                f"Stimulus set '{stimulus_set.name}' does not contain any files."
            )
    for manifest_set in manifest.sets:
        _resolve_existing_relative_dir(project_root, manifest_set.source_dir)
        for asset in manifest_set.assets:
            _resolve_existing_relative_file(project_root, asset.source.relative_path)
            for derivative in asset.derivatives:
                _resolve_existing_relative_file(project_root, derivative.relative_path)
    try:
        compile_session_plan(
            project,
            refresh_hz=refresh_hz,
            project_root=project_root,
            manifest=manifest,
        )
    except CompileError as exc:
        raise ProjectBundleError(f"Project did not pass bundle compile validation: {exc}") from exc


def _validate_condition_role_source_dirs(
    project_root: Path,
    *,
    project: ProjectFile,
    role: Literal["base", "oddball"],
) -> None:
    stimulus_sets_by_id = {
        stimulus_set.set_id: stimulus_set for stimulus_set in project.stimulus_sets
    }
    set_ids = {
        condition.base_stimulus_set_id
        if role == "base"
        else condition.oddball_stimulus_set_id
        for condition in project.conditions
    }
    for set_id in sorted(set_ids):
        stimulus_set = stimulus_sets_by_id.get(set_id)
        if stimulus_set is None or stimulus_set.source_dir is None:
            continue
        _resolve_existing_relative_dir(project_root, stimulus_set.source_dir)


def _resolve_existing_relative_dir(project_root: Path, relative_path: str) -> Path:
    normalized = validate_project_relative_path(relative_path)
    resolved = (project_root / Path(normalized)).resolve()
    _require_path_under_project(project_root, resolved, normalized)
    if not resolved.is_dir():
        raise ProjectBundleError(f"Required project folder is missing: {normalized}")
    return resolved


def _resolve_existing_relative_file(project_root: Path, relative_path: str) -> Path:
    normalized = validate_project_relative_path(relative_path)
    resolved = (project_root / Path(normalized)).resolve()
    _require_path_under_project(project_root, resolved, normalized)
    if not resolved.is_file():
        raise ProjectBundleError(f"Required project file is missing: {normalized}")
    return resolved


def _require_path_under_project(project_root: Path, resolved_path: Path, label: str) -> None:
    try:
        resolved_path.relative_to(project_root.resolve())
    except ValueError as exc:
        raise ProjectBundleError(f"Project path escapes the project root: {label}") from exc


def _collect_bundle_file_paths(project_root: Path) -> list[str]:
    project_file = project_json_path(project_root)
    stimuli_root = stimuli_dir(project_root)
    if not stimuli_root.is_dir():
        raise ProjectBundleError("Project bundle export requires a stimuli folder.")

    paths = [to_project_relative_posix(project_root, project_file)]
    for path in sorted(stimuli_root.rglob("*"), key=lambda item: item.as_posix().lower()):
        if path.is_file():
            paths.append(to_project_relative_posix(project_root, path))
    return sorted(set(paths), key=str.lower)


def _file_record(
    project_root: Path,
    relative_path: str,
    *,
    payload_override: bytes | None = None,
) -> ProjectBundleFileRecord:
    if payload_override is not None:
        return ProjectBundleFileRecord(
            path=relative_path,
            size_bytes=len(payload_override),
            sha256=hashlib.sha256(payload_override).hexdigest(),
        )
    path = _resolve_existing_relative_file(project_root, relative_path)
    return ProjectBundleFileRecord(
        path=relative_path,
        size_bytes=path.stat().st_size,
        sha256=_sha256_file(path),
    )


def _write_bundle_archive(
    project_root: Path,
    bundle_path: Path,
    bundle_manifest: ProjectBundleManifest,
    *,
    payload_overrides: dict[str, bytes],
) -> None:
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = bundle_path.with_name(f".{bundle_path.name}.tmp")
    if temp_path.exists():
        temp_path.unlink()
    try:
        with zipfile.ZipFile(temp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                BUNDLE_MANIFEST_FILENAME,
                bundle_manifest.model_dump_json(indent=2, exclude_none=True),
            )
            for record in bundle_manifest.files:
                payload_override = payload_overrides.get(record.path)
                if payload_override is None:
                    archive.write(project_root / Path(record.path), arcname=record.path)
                else:
                    archive.writestr(record.path, payload_override)
        temp_path.replace(bundle_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_import_project_dir(parent_dir: Path, source_project_id: str) -> tuple[Path, str]:
    candidate_id = source_project_id
    candidate_dir = project_dir(parent_dir, candidate_id)
    if not candidate_dir.exists():
        return candidate_dir, candidate_id

    base_id = f"{source_project_id}-from-bundle"
    candidate_id = base_id
    candidate_dir = project_dir(parent_dir, candidate_id)
    suffix = 2
    while candidate_dir.exists():
        candidate_id = f"{base_id}-{suffix}"
        candidate_dir = project_dir(parent_dir, candidate_id)
        suffix += 1
    return candidate_dir, candidate_id


def _rewrite_imported_project_id(
    staged_project_root: Path,
    *,
    project: ProjectFile,
    manifest: StimulusManifest,
    project_id: str,
) -> tuple[ProjectFile, StimulusManifest]:
    meta = project.meta.model_copy(update={"project_id": project_id})
    updated_project = project.model_copy(update={"meta": meta})
    updated_manifest = manifest.model_copy(update={"project_id": project_id})
    save_project_file(updated_project, project_json_path(staged_project_root))
    write_stimulus_manifest(staged_project_root, updated_manifest)
    return updated_project, updated_manifest


def _ensure_import_project_structure(project_root: Path) -> None:
    for folder in (
        stimuli_dir(project_root),
        stimulus_original_images_root(project_root),
        stimulus_generated_variants_root(project_root),
        runs_dir(project_root),
        cache_dir(project_root),
        logs_dir(project_root),
    ):
        folder.mkdir(parents=True, exist_ok=True)
