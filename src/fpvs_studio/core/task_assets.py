"""Project-local intake helpers for modular task media."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path

from fpvs_studio.core.paths import (
    resolve_project_relative_path,
    validate_project_relative_path,
)
from fpvs_studio.core.task_models import validate_task_slug

SUPPORTED_TASK_ASSET_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})


class TaskAssetError(ValueError):
    """Raised when task media cannot be copied safely into a project."""


def copy_task_asset(
    project_root: Path,
    task_id: str,
    source_path: Path,
    *,
    filename: str | None = None,
) -> str:
    """Copy one task image beneath its module folder and return its stored path.

    Existing byte-identical assets are reused. Name collisions with different bytes
    are explicit errors so authoring never silently replaces experiment media.
    """

    validate_task_slug(task_id, field_name="task_id")
    project_root = Path(project_root).resolve(strict=False)
    if not project_root.is_dir():
        raise TaskAssetError(f"Project root is missing or is not a directory: {project_root}")
    source_path = Path(source_path)
    if not source_path.is_file():
        raise TaskAssetError(f"Task asset source is missing or is not a file: {source_path}")
    requested_name = filename or source_path.name
    if Path(requested_name).name != requested_name or requested_name in {".", ".."}:
        raise TaskAssetError("Task asset filename must be one plain filename.")
    suffix = Path(requested_name).suffix.lower()
    if suffix not in SUPPORTED_TASK_ASSET_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_TASK_ASSET_SUFFIXES))
        raise TaskAssetError(f"Unsupported task asset extension '{suffix}'. Expected: {supported}.")

    relative_path = validate_project_relative_path(
        f"stimuli/task-assets/{task_id}/{requested_name}"
    )
    try:
        destination = resolve_project_relative_path(project_root, relative_path)
    except ValueError as exc:
        raise TaskAssetError(
            f"Task asset destination escapes the project: {relative_path}"
        ) from exc
    destination_dir = destination.parent
    destination_dir.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not destination.is_file():
            raise TaskAssetError(f"Task asset destination is not a file: {relative_path}")
        if _sha256(destination) == _sha256(source_path):
            return relative_path
        raise TaskAssetError(
            f"A different task asset already uses destination path: {relative_path}"
        )

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{requested_name}.",
            suffix=".tmp",
            dir=destination_dir,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        shutil.copy2(source_path, temporary_path)
        temporary_path.replace(destination)
    except OSError as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise TaskAssetError(f"Unable to copy task asset to: {relative_path}") from exc
    return relative_path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()
