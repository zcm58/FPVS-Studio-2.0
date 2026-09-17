"""Bounded, versioned library service metadata, independent of GUI and runtime."""

from __future__ import annotations

import re
from typing import Literal

from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from fpvs_studio import __version__

MAX_DOWNLOAD_BYTES = 2 * 1024**3 - 1
MAX_CATALOG_BYTES = 1024 * 1024
MAX_CATALOG_ITEMS = 500
MAX_UNCOMPRESSED_BYTES = 20 * 1024**3
MAX_FILE_COUNT = 50_000


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class LibraryItem(_Contract):
    item_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    kind: Literal["experiment"] = "experiment"
    version: str = Field(min_length=1, max_length=64, pattern=r"^[0-9][A-Za-z0-9.+-]*$")
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(max_length=4000)
    experiment_category: Literal["fpvs_oddball", "cognitive_load_fpvs", "attentional_blink"]
    filename: str = Field(min_length=12, max_length=160)
    size_bytes: int = Field(gt=0, le=MAX_DOWNLOAD_BYTES)
    uncompressed_size_bytes: int = Field(gt=0, le=MAX_UNCOMPRESSED_BYTES)
    file_count: int = Field(gt=0, le=MAX_FILE_COUNT)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    min_studio_version: str = Field(min_length=1, max_length=64)

    @field_validator("version", "min_studio_version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        try:
            Version(value)
        except InvalidVersion:
            raise ValueError("Invalid library version.") from None
        return value

    @field_validator("filename")
    @classmethod
    def safe_filename(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.fpvsbundle", value):
            raise ValueError("Expected a plain .fpvsbundle filename.")
        if value.split(".")[0].upper() in {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }:
            raise ValueError("Reserved filename.")
        return value

    @property
    def compatible(self) -> bool:
        return Version(__version__) >= Version(self.min_studio_version)

    @property
    def compatibility_message(self) -> str:
        return (
            "" if self.compatible else f"Requires FPVS Studio {self.min_studio_version} or later."
        )


class LibraryCatalog(_Contract):
    schema_version: Literal["1.0"]
    library_name: str = Field(min_length=1, max_length=120)
    items: list[LibraryItem] = Field(max_length=MAX_CATALOG_ITEMS)

    @model_validator(mode="after")
    def unique_versions(self) -> LibraryCatalog:
        identities = {(item.item_id, item.version) for item in self.items}
        if len(identities) != len(self.items):
            raise ValueError("Duplicate library item/version.")
        return self


class LibraryConnection(_Contract):
    device_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    library_name: str = Field(min_length=1, max_length=120)
    device_name: str = Field(min_length=1, max_length=100)


class EnrollmentResponse(_Contract):
    schema_version: Literal["1.0"]
    device_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    library_name: str = Field(min_length=1, max_length=120)


class DeviceCredential(_Contract):
    """Stored only in an OS credential store, including the pending enrollment state."""

    token: str = Field(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9_-]+$", repr=False)
    device_name: str = Field(min_length=1, max_length=100)
    connection: LibraryConnection | None = None
