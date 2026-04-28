"""Migration seam for persisted editable project payloads. It sits between on-disk project
JSON and current ProjectFile models so schema-version transitions can stay explicit and
engine-neutral. The module owns payload normalization only; compilation, preprocessing,
and runtime behavior remain elsewhere."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fpvs_studio.core.enums import SchemaVersion
from fpvs_studio.core.models import ProjectFile

CURRENT_SCHEMA_VERSION = SchemaVersion.V1


def migrate_project_payload(payload: Mapping[str, Any]) -> ProjectFile:
    """Validate or migrate a raw project payload into the current schema."""

    schema_version = payload.get("schema_version", CURRENT_SCHEMA_VERSION.value)
    if schema_version != CURRENT_SCHEMA_VERSION.value:
        raise NotImplementedError(
            f"Migration from schema_version '{schema_version}' is not implemented."
        )
    return ProjectFile.model_validate(payload)
