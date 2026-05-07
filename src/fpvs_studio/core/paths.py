"""Project-folder path helpers shared across backend layers. They convert between
filesystem locations and project-relative POSIX paths used by ProjectFile records,
manifests, and export layouts. This module owns path conventions only; it does not
validate domain rules or perform runtime scheduling."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_FILENAME = "project.json"
STIMULI_DIRNAME = "stimuli"
RUNS_DIRNAME = "runs"
CACHE_DIRNAME = "cache"
LOGS_DIRNAME = "logs"
ORIGINAL_IMAGES_DIRNAME = "original-images"
GENERATED_VARIANTS_DIRNAME = "generated-variants"
GRAYSCALE_VARIANTS_DIRNAME = "grayscale-variants"
ROTATED_180_VARIANTS_DIRNAME = "rotated-180-variants"
SCRAMBLED_VARIANTS_DIRNAME = "scrambled-variants"
MANIFEST_FILENAME = "manifest.json"
TEMPLATES_DIRNAME = "templates"
CONDITION_TEMPLATE_LIBRARY_FILENAME = "condition_templates.json"
RESERVED_ROOT_ENTRY_NAMES = frozenset({TEMPLATES_DIRNAME})

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


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


def runs_dir(project_root: Path) -> Path:
    """Return the runs directory path."""

    return project_root / RUNS_DIRNAME


def cache_dir(project_root: Path) -> Path:
    """Return the cache directory path."""

    return project_root / CACHE_DIRNAME


def logs_dir(project_root: Path) -> Path:
    """Return the logs directory path."""

    return project_root / LOGS_DIRNAME


def templates_dir(root_dir: Path) -> Path:
    """Return the app-level templates directory path under the FPVS root."""

    return root_dir / TEMPLATES_DIRNAME


def condition_template_library_path(root_dir: Path) -> Path:
    """Return the app-level condition-template library JSON path."""

    return templates_dir(root_dir) / CONDITION_TEMPLATE_LIBRARY_FILENAME


def to_project_relative_posix(project_root: Path, target_path: Path) -> str:
    """Convert a path under a project root to a persisted POSIX relative path."""

    relative = target_path.resolve().relative_to(project_root.resolve())
    return relative.as_posix()


def from_project_relative_posix(project_root: Path, relative_path: str) -> Path:
    """Resolve a persisted POSIX relative path under a project root."""

    return project_root / Path(relative_path)
