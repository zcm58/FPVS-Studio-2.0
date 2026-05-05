"""Stimulus asset path resolution for run-spec compilation."""

from __future__ import annotations

from pathlib import Path

from fpvs_studio.core.compiler_support import (
    SUPPORTED_DERIVED_SUFFIXES,
    SUPPORTED_SOURCE_SUFFIXES,
    CompileError,
)
from fpvs_studio.core.enums import StimulusVariant
from fpvs_studio.core.models import StimulusSet, validate_project_relative_path
from fpvs_studio.core.paths import (
    stimulus_derived_dir,
    stimulus_manifest_path,
    to_project_relative_posix,
)
from fpvs_studio.core.serialization import read_json_file
from fpvs_studio.preprocessing.models import (
    StimulusAssetRecord,
    StimulusManifest,
    StimulusSetManifest,
)


def load_manifest(
    project_root: Path | None,
    manifest: StimulusManifest | None,
) -> StimulusManifest | None:
    """Load the preprocessing manifest when available."""

    if manifest is not None:
        return manifest
    if project_root is None:
        return None
    manifest_path = stimulus_manifest_path(project_root)
    if not manifest_path.is_file():
        return None
    return read_json_file(manifest_path, StimulusManifest)


def _resolve_manifest_set(
    stimulus_set: StimulusSet,
    *,
    manifest: StimulusManifest | None,
) -> StimulusSetManifest | None:
    """Return the matching manifest set when present."""

    if manifest is None:
        return None
    for manifest_set in manifest.sets:
        if manifest_set.set_id == stimulus_set.set_id:
            return manifest_set
    return None


def _resolve_manifest_asset_path(
    asset: StimulusAssetRecord,
    *,
    variant: StimulusVariant,
) -> str | None:
    """Resolve one asset path from the manifest for the requested variant."""

    if variant == StimulusVariant.ORIGINAL:
        return asset.source.relative_path
    for derivative in asset.derivatives:
        if derivative.variant == variant:
            return derivative.relative_path
    return None


def _resolve_manifest_image_paths(
    stimulus_set: StimulusSet,
    *,
    variant: StimulusVariant,
    project_root: Path,
    manifest: StimulusManifest | None,
) -> list[str] | None:
    """Resolve ordered asset paths from the preprocessing manifest."""

    manifest_set = _resolve_manifest_set(stimulus_set, manifest=manifest)
    if manifest_set is None or not manifest_set.assets:
        return None

    resolved: list[str] = []
    for asset in sorted(manifest_set.assets, key=lambda item: item.source.relative_path.lower()):
        relative_path = _resolve_manifest_asset_path(asset, variant=variant)
        if relative_path is None:
            raise CompileError(
                f"Stimulus variant '{variant.value}' is missing from the manifest for set "
                f"'{stimulus_set.name}'."
            )
        candidate_path = project_root / Path(relative_path)
        if not candidate_path.is_file():
            raise CompileError(
                f"Manifest path '{relative_path}' for set '{stimulus_set.name}' does not exist."
            )
        resolved.append(validate_project_relative_path(relative_path))

    return resolved


def _synthetic_image_paths(
    stimulus_set: StimulusSet,
    *,
    variant: StimulusVariant,
) -> list[str]:
    """Create deterministic placeholder image paths when the project root is unavailable."""

    if variant == StimulusVariant.ORIGINAL:
        base_dir = stimulus_set.source_dir
    else:
        base_dir = f"stimuli/derived/{stimulus_set.set_id}/{variant.value}"
    return [
        validate_project_relative_path(f"{base_dir}/image_{index:04d}.png")
        for index in range(1, stimulus_set.image_count + 1)
    ]


def _resolve_filesystem_image_paths(
    stimulus_set: StimulusSet,
    *,
    variant: StimulusVariant,
    project_root: Path,
) -> list[str]:
    """Resolve sorted project-relative image paths directly from the filesystem."""

    allowed_suffixes: tuple[str, ...]
    if variant == StimulusVariant.ORIGINAL:
        source_dir = project_root / Path(stimulus_set.source_dir)
        allowed_suffixes = SUPPORTED_SOURCE_SUFFIXES
    else:
        source_dir = stimulus_derived_dir(project_root, stimulus_set.set_id) / variant.value
        allowed_suffixes = SUPPORTED_DERIVED_SUFFIXES

    if source_dir.exists() and source_dir.is_dir():
        resolved = [
            to_project_relative_posix(project_root, path)
            for path in sorted(source_dir.iterdir(), key=lambda item: item.name.lower())
            if path.is_file() and path.suffix.lower() in allowed_suffixes
        ]
        if resolved:
            return resolved
    raise CompileError(f"Stimulus set '{stimulus_set.name}' has no resolvable image paths.")


def resolve_image_paths(
    stimulus_set: StimulusSet,
    *,
    variant: StimulusVariant,
    project_root: Path | None,
    manifest: StimulusManifest | None,
) -> list[str]:
    """Resolve sorted project-relative image paths for a stimulus set."""

    if project_root is not None:
        manifest_paths = _resolve_manifest_image_paths(
            stimulus_set,
            variant=variant,
            project_root=project_root,
            manifest=manifest,
        )
        if manifest_paths:
            return manifest_paths
        return _resolve_filesystem_image_paths(
            stimulus_set,
            variant=variant,
            project_root=project_root,
        )

    synthetic_paths = _synthetic_image_paths(stimulus_set, variant=variant)
    if synthetic_paths:
        return synthetic_paths
    raise CompileError(f"Stimulus set '{stimulus_set.name}' has no resolvable image paths.")
