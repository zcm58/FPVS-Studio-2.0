"""Schema migration placeholders for persisted project files."""

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
