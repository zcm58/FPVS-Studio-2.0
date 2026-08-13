"""Migration seam for persisted editable project payloads. It sits between on-disk project
JSON and current ProjectFile models so schema-version transitions can stay explicit and
engine-neutral. The module owns payload normalization only; compilation, preprocessing,
and runtime behavior remain elsewhere."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from fpvs_studio.core.enums import SchemaVersion
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.presentation import legacy_project_presentation_settings

CURRENT_SCHEMA_VERSION = SchemaVersion.V1_2


def migrate_project_payload(payload: Mapping[str, Any]) -> ProjectFile:
    """Validate or migrate a raw project payload into the current schema."""

    schema_version = payload.get("schema_version", SchemaVersion.V1.value)
    if isinstance(schema_version, SchemaVersion):
        schema_version = schema_version.value
    if schema_version == CURRENT_SCHEMA_VERSION.value:
        return ProjectFile.model_validate(payload)
    if schema_version not in {SchemaVersion.V1.value, SchemaVersion.V1_1.value}:
        raise NotImplementedError(
            f"Migration from schema_version '{schema_version}' is not implemented."
        )

    migrated = deepcopy(dict(payload))
    settings = migrated.setdefault("settings", {})
    if schema_version == SchemaVersion.V1.value:
        display = settings.get("display", {})
        stimulus_width_degrees = float(display.get("stimulus_width_degrees", 5.0))
        settings.setdefault(
            "presentation",
            legacy_project_presentation_settings(
                stimulus_width_degrees,
                pre_stream_fixation_seconds=0.0,
            ).model_dump(mode="json"),
        )
    for condition in migrated.get("conditions", []):
        if isinstance(condition, dict):
            condition.setdefault("presentation", {})
            condition.setdefault("pre_task_bindings", [])
            condition.setdefault("post_task_bindings", [])
    migrated.setdefault("task_modules", [])
    migrated["schema_version"] = CURRENT_SCHEMA_VERSION.value
    return ProjectFile.model_validate(migrated)
