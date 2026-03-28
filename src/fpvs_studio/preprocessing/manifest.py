"""Manifest persistence and query helpers for preprocessing outputs.
It converts inspected and materialized assets into deterministic records that core compilation can resolve into project-relative source and derivative paths.
This module owns preprocessing provenance, not presentation scheduling, runtime execution, or engine-specific data."""

from __future__ import annotations

from pathlib import Path

from fpvs_studio.core.enums import StimulusVariant
from fpvs_studio.core.paths import stimulus_manifest_path
from fpvs_studio.core.serialization import read_json_file, write_json_file
from fpvs_studio.preprocessing.models import (
    DerivedImageRecord,
    SourceImageRecord,
    StimulusAssetRecord,
    StimulusManifest,
    StimulusSetInspectionSummary,
    StimulusSetManifest,
)


def create_empty_manifest(project_id: str) -> StimulusManifest:
    """Create an empty project preprocessing manifest."""

    return StimulusManifest(project_id=project_id)


def read_stimulus_manifest(project_root: Path) -> StimulusManifest:
    """Load a project preprocessing manifest."""

    return read_json_file(stimulus_manifest_path(project_root), StimulusManifest)


def write_stimulus_manifest(project_root: Path, manifest: StimulusManifest) -> None:
    """Persist a project preprocessing manifest."""

    write_json_file(stimulus_manifest_path(project_root), manifest)


def inspection_summary_to_manifest_set(
    *,
    set_id: str,
    summary: StimulusSetInspectionSummary,
) -> StimulusSetManifest:
    """Convert an inspection summary into a manifest section."""

    assets = [
        StimulusAssetRecord(
            source=SourceImageRecord(
                relative_path=item.relative_path,
                sha256=item.sha256,
                source_format=item.source_format,
                resolution=item.resolution,
            )
        )
        for item in summary.files
    ]
    return StimulusSetManifest(
        set_id=set_id,
        source_dir=summary.source_dir,
        available_variants=[StimulusVariant.ORIGINAL],
        assets=assets,
    )


def upsert_manifest_set(manifest: StimulusManifest, manifest_set: StimulusSetManifest) -> StimulusManifest:
    """Insert or replace a manifest set entry."""

    sets = [item for item in manifest.sets if item.set_id != manifest_set.set_id]
    sets.append(manifest_set)
    return manifest.model_copy(update={"sets": sets})


def find_manifest_set(
    manifest: StimulusManifest,
    *,
    set_id: str,
) -> StimulusSetManifest | None:
    """Return one stimulus-set manifest section by id."""

    for manifest_set in manifest.sets:
        if manifest_set.set_id == set_id:
            return manifest_set
    return None


def asset_variant_path(
    asset: StimulusAssetRecord,
    *,
    variant: StimulusVariant,
) -> str | None:
    """Resolve the persisted path for a requested source or derived variant."""

    if variant == StimulusVariant.ORIGINAL:
        return asset.source.relative_path
    for derivative in asset.derivatives:
        if derivative.variant == variant:
            return derivative.relative_path
    return None


def upsert_asset_derivative(
    asset: StimulusAssetRecord,
    derivative: DerivedImageRecord,
) -> StimulusAssetRecord:
    """Insert or replace one derivative record on an asset."""

    derivatives = [item for item in asset.derivatives if item.variant != derivative.variant]
    derivatives.append(derivative)
    derivatives.sort(key=lambda item: item.variant.value)
    return asset.model_copy(update={"derivatives": derivatives})
