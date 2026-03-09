"""Preprocessing manifest and inspection models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import Field, field_validator

from fpvs_studio.core.enums import SchemaVersion, StimulusVariant
from fpvs_studio.core.models import FPVSBaseModel, ImageResolution, validate_project_relative_path


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class InspectionFileRecord(FPVSBaseModel):
    """Source-image inspection result for a single file."""

    relative_path: str
    sha256: str
    source_format: str
    resolution: ImageResolution

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        return validate_project_relative_path(value)


class StimulusSetInspectionSummary(FPVSBaseModel):
    """Inspection summary for a source image directory."""

    source_dir: str
    image_count: int = Field(ge=0)
    resolution: ImageResolution | None = None
    mixed_resolution: bool = False
    unsupported_files: list[str] = Field(default_factory=list)
    files: list[InspectionFileRecord] = Field(default_factory=list)

    @field_validator("source_dir")
    @classmethod
    def validate_source_dir(cls, value: str) -> str:
        return validate_project_relative_path(value)


class SourceImageRecord(FPVSBaseModel):
    """Manifest record for an imported source image."""

    relative_path: str
    sha256: str
    source_format: str
    resolution: ImageResolution
    imported_at: datetime = Field(default_factory=utc_now)

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        return validate_project_relative_path(value)


class DerivedImageRecord(FPVSBaseModel):
    """Manifest record for a derived stimulus variant."""

    variant: StimulusVariant
    relative_path: str
    resolution: ImageResolution
    file_format: str = "png"
    sha256: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = None
    deterministic_policy: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        return validate_project_relative_path(value)


class StimulusAssetRecord(FPVSBaseModel):
    """Source image plus any derived variants."""

    source: SourceImageRecord
    derivatives: list[DerivedImageRecord] = Field(default_factory=list)


class StimulusSetManifest(FPVSBaseModel):
    """Manifest section for one stimulus set."""

    set_id: str
    source_dir: str
    available_variants: list[StimulusVariant] = Field(
        default_factory=lambda: [StimulusVariant.ORIGINAL]
    )
    assets: list[StimulusAssetRecord] = Field(default_factory=list)

    @field_validator("source_dir")
    @classmethod
    def validate_source_dir(cls, value: str) -> str:
        return validate_project_relative_path(value)


class StimulusManifest(FPVSBaseModel):
    """Project-level preprocessing manifest."""

    schema_version: SchemaVersion = SchemaVersion.V1
    preprocessing_version: str = "1.0.0"
    project_id: str
    generated_at: datetime = Field(default_factory=utc_now)
    sets: list[StimulusSetManifest] = Field(default_factory=list)
