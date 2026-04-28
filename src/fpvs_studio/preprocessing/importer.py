"""Source-image import and derived-asset materialization pipeline. It copies supported
inputs into the project, updates manifest-backed asset records, and generates
deterministic preprocessing variants for compilation to consume. This module owns
preprocessing I/O and provenance, not ProjectFile editing semantics, RunSpec
construction, or runtime launch behavior."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path

from fpvs_studio.core.enums import StimulusVariant
from fpvs_studio.core.models import ProjectFile, StimulusSet
from fpvs_studio.core.paths import stimulus_originals_dir, to_project_relative_posix
from fpvs_studio.preprocessing.controls import (
    generate_phase_scrambled_png,
    generate_rot180_png,
)
from fpvs_studio.preprocessing.grayscale import generate_grayscale_png
from fpvs_studio.preprocessing.inspection import inspect_source_directory, summary_to_stimulus_set
from fpvs_studio.preprocessing.manifest import (
    create_empty_manifest,
    find_manifest_set,
    inspection_summary_to_manifest_set,
    read_stimulus_manifest,
    upsert_asset_derivative,
    upsert_manifest_set,
    write_stimulus_manifest,
)
from fpvs_studio.preprocessing.models import (
    DerivedImageRecord,
    StimulusAssetRecord,
    StimulusManifest,
    StimulusSetInspectionSummary,
    StimulusSetManifest,
)

PHASE_SCRAMBLE_POLICY = "fft-amplitude-preserved-noise-phase-v1"


def import_stimulus_source_directory(
    *,
    source_dir: Path,
    project_root: Path,
    set_id: str,
    set_name: str,
) -> tuple[StimulusSetInspectionSummary, StimulusSet]:
    """Copy supported source images into a project and summarize the imported set."""

    destination_dir = stimulus_originals_dir(project_root, set_id)
    destination_dir.mkdir(parents=True, exist_ok=True)

    summary = inspect_source_directory(
        source_dir,
        relative_prefix=to_project_relative_posix(project_root, destination_dir),
        strict=True,
    )
    for item in source_dir.iterdir():
        if item.is_file() and item.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            shutil.copy2(item, destination_dir / item.name)

    return summary, summary_to_stimulus_set(set_id=set_id, name=set_name, summary=summary)


def materialize_project_assets(
    project: ProjectFile,
    *,
    project_root: Path,
    manifest: StimulusManifest | None = None,
    variants: list[StimulusVariant] | None = None,
) -> StimulusManifest:
    """Inspect imported sources, generate deterministic derivatives, and persist the manifest."""

    requested_variants = variants or list(project.settings.supported_variants)
    existing_manifest = manifest or _load_or_create_manifest(project, project_root)
    working_manifest = existing_manifest

    for stimulus_set in project.stimulus_sets:
        source_dir = project_root / Path(stimulus_set.source_dir)
        inspection_summary = inspect_source_directory(
            source_dir,
            relative_prefix=stimulus_set.source_dir,
            strict=True,
        )
        inspected_manifest_set = inspection_summary_to_manifest_set(
            set_id=stimulus_set.set_id,
            summary=inspection_summary,
        )
        previous_manifest_set = find_manifest_set(
            existing_manifest,
            set_id=stimulus_set.set_id,
        )
        manifest_set = _merge_existing_derivatives(
            inspected_manifest_set,
            previous_manifest_set=previous_manifest_set,
        )
        manifest_set = _materialize_manifest_set_variants(
            manifest_set,
            project_root=project_root,
            variants=requested_variants,
        )
        working_manifest = upsert_manifest_set(working_manifest, manifest_set)

    write_stimulus_manifest(project_root, working_manifest)
    return working_manifest


def _load_or_create_manifest(project: ProjectFile, project_root: Path) -> StimulusManifest:
    """Load the current manifest or create an empty one for the project."""

    manifest_path = project_root / "stimuli" / "manifest.json"
    if manifest_path.is_file():
        return read_stimulus_manifest(project_root)
    return create_empty_manifest(project.meta.project_id)


def _merge_existing_derivatives(
    manifest_set: StimulusSetManifest,
    *,
    previous_manifest_set: StimulusSetManifest | None,
) -> StimulusSetManifest:
    """Carry forward derivative metadata for unchanged source files."""

    if previous_manifest_set is None:
        return manifest_set

    previous_assets = {
        asset.source.relative_path: asset
        for asset in previous_manifest_set.assets
        if asset.source.sha256
    }
    merged_assets: list[StimulusAssetRecord] = []

    for asset in manifest_set.assets:
        previous_asset = previous_assets.get(asset.source.relative_path)
        if previous_asset is not None and previous_asset.source.sha256 == asset.source.sha256:
            merged_assets.append(
                asset.model_copy(update={"derivatives": previous_asset.derivatives})
            )
        else:
            merged_assets.append(asset)

    available_variants = {
        StimulusVariant.ORIGINAL,
        *(derivative.variant for asset in merged_assets for derivative in asset.derivatives),
    }
    return manifest_set.model_copy(
        update={
            "assets": merged_assets,
            "available_variants": _sorted_variants(list(available_variants)),
        }
    )


def _materialize_manifest_set_variants(
    manifest_set: StimulusSetManifest,
    *,
    project_root: Path,
    variants: list[StimulusVariant],
) -> StimulusSetManifest:
    """Ensure the requested variants exist on disk and in the manifest."""

    available_variants = set(manifest_set.available_variants)
    materialized_assets: list[StimulusAssetRecord] = []

    for asset in manifest_set.assets:
        materialized_asset = asset
        for variant in variants:
            if variant == StimulusVariant.ORIGINAL:
                available_variants.add(variant)
                continue
            derivative = _ensure_derivative(
                asset=materialized_asset,
                set_id=manifest_set.set_id,
                project_root=project_root,
                variant=variant,
            )
            materialized_asset = upsert_asset_derivative(materialized_asset, derivative)
            available_variants.add(variant)
        materialized_assets.append(materialized_asset)

    return manifest_set.model_copy(
        update={
            "assets": materialized_assets,
            "available_variants": _sorted_variants(list(available_variants)),
        }
    )


def _ensure_derivative(
    *,
    asset: StimulusAssetRecord,
    set_id: str,
    project_root: Path,
    variant: StimulusVariant,
) -> DerivedImageRecord:
    """Create one deterministic derivative when needed and return its manifest record."""

    existing_derivative = next(
        (item for item in asset.derivatives if item.variant == variant),
        None,
    )
    relative_path = _derived_relative_path(
        set_id=set_id,
        source_relative_path=asset.source.relative_path,
        source_sha256=asset.source.sha256,
        variant=variant,
    )
    destination_path = project_root / Path(relative_path)

    if existing_derivative is not None and destination_path.is_file():
        return existing_derivative.model_copy(
            update={
                "relative_path": relative_path,
                "resolution": asset.source.resolution,
                "sha256": existing_derivative.sha256 or _compute_file_sha256(destination_path),
            }
        )

    source_path = project_root / Path(asset.source.relative_path)
    seed: int | None = _variant_seed(asset.source.sha256, variant=variant)
    generator = _variant_generator(variant)
    if variant == StimulusVariant.PHASE_SCRAMBLED:
        generator(source_path, destination_path, seed=seed)
        parameters = {"policy": PHASE_SCRAMBLE_POLICY}
        deterministic_policy = PHASE_SCRAMBLE_POLICY
    else:
        generator(source_path, destination_path)
        parameters = {}
        deterministic_policy = "deterministic-transform-v1"
        seed = None

    return DerivedImageRecord(
        variant=variant,
        relative_path=relative_path,
        resolution=asset.source.resolution,
        sha256=_compute_file_sha256(destination_path),
        parameters=parameters,
        seed=seed,
        deterministic_policy=deterministic_policy,
    )


def _variant_generator(variant: StimulusVariant) -> Callable[..., None]:
    """Return the generator callable for a derived variant."""

    if variant == StimulusVariant.GRAYSCALE:
        return generate_grayscale_png
    if variant == StimulusVariant.ROT180:
        return generate_rot180_png
    if variant == StimulusVariant.PHASE_SCRAMBLED:
        return generate_phase_scrambled_png
    raise ValueError(f"Unsupported derived variant '{variant.value}'.")


def _derived_relative_path(
    *,
    set_id: str,
    source_relative_path: str,
    source_sha256: str,
    variant: StimulusVariant,
) -> str:
    """Build a stable project-relative output path for one derivative."""

    source_name = Path(source_relative_path).stem
    filename = f"{source_name}-{source_sha256[:12]}.png"
    return (Path("stimuli") / "derived" / set_id / variant.value / filename).as_posix()


def _variant_seed(source_sha256: str, *, variant: StimulusVariant) -> int:
    """Build a deterministic per-asset seed for randomized preprocessing variants."""

    digest = sha256(f"{variant.value}:{source_sha256}".encode()).hexdigest()
    return int(digest[:16], 16)


def _sorted_variants(variants: list[StimulusVariant]) -> list[StimulusVariant]:
    """Return variants in stable enum-value order without duplicates."""

    return sorted(set(variants), key=lambda item: item.value)


def _compute_file_sha256(path: Path) -> str:
    """Compute a SHA-256 hex digest for a generated file."""

    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
