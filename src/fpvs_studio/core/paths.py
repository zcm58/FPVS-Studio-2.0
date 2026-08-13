"""Project-folder path helpers shared across backend layers. They convert between
filesystem locations and project-relative POSIX paths used by ProjectFile records,
manifests, and export layouts. This module owns path conventions only; it does not
validate domain rules or perform runtime scheduling."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath, PureWindowsPath

PROJECT_FILENAME = "project.json"
STIMULI_DIRNAME = "stimuli"
RUNS_DIRNAME = "runs"
CACHE_DIRNAME = "cache"
LOGS_DIRNAME = "logs"
ORIGINAL_IMAGES_DIRNAME = "original-images"
GENERATED_VARIANTS_DIRNAME = "generated-variants"
NORMALIZED_IMAGES_DIRNAME = "normalized-images"
GRAYSCALE_VARIANTS_DIRNAME = "grayscale-variants"
ROTATED_180_VARIANTS_DIRNAME = "rotated-180-variants"
SCRAMBLED_VARIANTS_DIRNAME = "scrambled-variants"
MANIFEST_FILENAME = "manifest.json"
TASK_ASSETS_DIRNAME = "task-assets"
APP_DATA_DIRNAME = ".fpvs-studio"
TEMPLATES_DIRNAME = "templates"
CONDITION_TEMPLATE_LIBRARY_FILENAME = "condition_templates.json"
RESERVED_ROOT_ENTRY_NAMES = frozenset({APP_DATA_DIRNAME})

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def validate_project_relative_path(value: str) -> str:
    """Validate and normalize one persisted project-relative POSIX path.

    Persisted paths are interpreted consistently on every host. Windows drive,
    rooted, UNC, and alternate-data-stream syntax is rejected even when validation
    runs on a non-Windows system.
    """

    if not value:
        raise ValueError("Path may not be empty.")
    if "\\" in value:
        raise ValueError("Persisted paths must use POSIX separators ('/').")
    if ":" in value:
        raise ValueError("Persisted paths may not contain Windows drive or stream syntax.")

    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if posix_path.is_absolute() or posix_path.anchor or windows_path.anchor:
        raise ValueError("Persisted paths must be project-relative, not rooted or absolute.")
    if any(part == ".." for part in posix_path.parts):
        raise ValueError("Persisted paths may not escape the project directory.")
    return posix_path.as_posix()


def resolve_project_relative_path(project_root: Path, relative_path: str) -> Path:
    """Resolve a persisted path under ``project_root`` without requiring existence.

    Resolution follows any existing symlink or junction prefixes. A target whose
    resolved location leaves the resolved project root is rejected.
    """

    normalized = validate_project_relative_path(relative_path)
    resolved_root = project_root.resolve(strict=False)
    resolved_target = (resolved_root / Path(normalized)).resolve(strict=False)
    try:
        resolved_target.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"Project-relative path escapes the project root: {normalized}") from exc
    return resolved_target


def slugify_project_name(name: str) -> str:
    """Generate a stable slug/id from a user-facing project name."""

    normalized = _NON_ALNUM_RE.sub("-", name.strip().lower()).strip("-")
    return normalized or "fpvs-project"


def is_reserved_root_entry_name(name: str) -> bool:
    """Return whether one top-level root entry name is reserved by the app layout."""

    return name.strip().lower() in RESERVED_ROOT_ENTRY_NAMES


def validate_project_id(project_id: str) -> None:
    """Validate one project id against reserved top-level root entry names."""

    normalized = project_id.strip().lower()
    if not normalized:
        raise ValueError("Project name resolves to an empty project id.")
    if is_reserved_root_entry_name(normalized):
        raise ValueError(
            f"Project name resolves to reserved root folder '{normalized}'. "
            "Choose a different project name."
        )


def project_dir(root_dir: Path, project_id: str) -> Path:
    """Return the directory where a project should live."""

    return root_dir / project_id


def project_json_path(project_root: Path) -> Path:
    """Return the canonical project JSON path."""

    return project_root / PROJECT_FILENAME


def stimuli_dir(project_root: Path) -> Path:
    """Return the stimuli directory path."""

    return project_root / STIMULI_DIRNAME


def stimulus_original_images_root(project_root: Path) -> Path:
    """Return the root directory for imported original images."""

    return stimuli_dir(project_root) / ORIGINAL_IMAGES_DIRNAME


def stimulus_generated_variants_root(project_root: Path) -> Path:
    """Return the root directory for generated stimulus variants."""

    return stimuli_dir(project_root) / GENERATED_VARIANTS_DIRNAME


def stimulus_normalized_images_root(project_root: Path) -> Path:
    """Return the root directory for normalized image outputs."""

    return stimuli_dir(project_root) / NORMALIZED_IMAGES_DIRNAME


def stimulus_normalized_dir(project_root: Path, set_id: str) -> Path:
    """Return the normalized image directory for a stimulus set."""

    return stimulus_normalized_images_root(project_root) / set_id


def stimulus_originals_dir(project_root: Path, set_id: str) -> Path:
    """Return the original-images directory for a stimulus set."""

    return stimulus_original_images_root(project_root) / set_id


def stimulus_derived_dir(project_root: Path, set_id: str) -> Path:
    """Return the generated-variants directory for a stimulus set."""

    return stimulus_generated_variants_root(project_root) / set_id


def stimulus_variant_dirname(variant_value: str) -> str:
    """Return the user-facing folder name for a generated variant."""

    return {
        "grayscale": GRAYSCALE_VARIANTS_DIRNAME,
        "rot180": ROTATED_180_VARIANTS_DIRNAME,
        "phase_scrambled": SCRAMBLED_VARIANTS_DIRNAME,
    }.get(variant_value, variant_value)


def stimulus_manifest_path(project_root: Path) -> Path:
    """Return the preprocessing manifest path."""

    return stimuli_dir(project_root) / MANIFEST_FILENAME


def task_assets_root(project_root: Path) -> Path:
    """Return the project-local root for task media."""

    return stimuli_dir(project_root) / TASK_ASSETS_DIRNAME


def task_asset_dir(project_root: Path, task_id: str) -> Path:
    """Return one task module's media directory."""

    return task_assets_root(project_root) / task_id


def runs_dir(project_root: Path) -> Path:
    """Return the runs directory path."""

    return project_root / RUNS_DIRNAME


def cache_dir(project_root: Path) -> Path:
    """Return the cache directory path."""

    return project_root / CACHE_DIRNAME


def logs_dir(project_root: Path) -> Path:
    """Return the logs directory path."""

    return project_root / LOGS_DIRNAME


def app_data_dir(root_dir: Path) -> Path:
    """Return the app-owned metadata directory under the FPVS root."""

    return root_dir / APP_DATA_DIRNAME


def templates_dir(root_dir: Path) -> Path:
    """Return the app-level condition-template directory under app metadata."""

    return app_data_dir(root_dir) / TEMPLATES_DIRNAME


def condition_template_library_path(root_dir: Path) -> Path:
    """Return the app-level condition-template library JSON path."""

    return templates_dir(root_dir) / CONDITION_TEMPLATE_LIBRARY_FILENAME


def to_project_relative_posix(project_root: Path, target_path: Path) -> str:
    """Convert a path under a project root to a persisted POSIX relative path."""

    relative = target_path.resolve().relative_to(project_root.resolve())
    return relative.as_posix()


def from_project_relative_posix(project_root: Path, relative_path: str) -> Path:
    """Resolve a persisted POSIX relative path under a project root."""

    return resolve_project_relative_path(project_root, relative_path)
