"""Read-only adapters for historical feature-versioned Studio config files.

New features belong to the current handoff model, not this frozen compatibility
matrix. Historical declarations keep their original validation and defaults.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from fpvs_studio.core.models import AttentionalBlinkStreamSettings
from fpvs_studio.core.presentation import legacy_project_presentation_settings
from fpvs_studio.core.task_models import (
    task_requires_scene_schema,
    task_requires_text_alignment_schema,
)

if TYPE_CHECKING:
    from fpvs_studio.core.project_config import ProjectConfigFile


LEGACY_CONFIG_VERSIONS = tuple(f"1.{minor}.0" for minor in range(16))


def normalize_legacy_config_payload(value: Any) -> tuple[Any, str | None]:
    """Normalize an old envelope without mutating the caller's dictionary."""

    if not isinstance(value, dict) or "schema_version" not in value:
        return value, None
    if any(key in value for key in ("format", "format_version", "kind", "metadata")):
        raise ValueError("A handoff cannot mix legacy schema_version with format revision 2.")
    version = value["schema_version"]
    if version not in LEGACY_CONFIG_VERSIONS:
        raise ValueError(f"Unsupported project config schema version: {version!r}.")
    payload = deepcopy(value)
    del payload["schema_version"]
    conditions = payload.get("conditions")
    condition_entries = conditions if isinstance(conditions, list) else []
    if version == "1.0.0":
        display = payload.get("display", {})
        if not isinstance(display, dict):
            raise ValueError("Legacy project config display must be an object.")
        payload["presentation"] = legacy_project_presentation_settings(
            float(display.get("stimulus_width_degrees", 5.0)),
            pre_stream_fixation_seconds=0.0,
        ).model_dump(mode="json")
        for condition in condition_entries:
            if isinstance(condition, dict):
                condition.setdefault("presentation", {})
    if version in {"1.0.0", "1.1.0"}:
        for condition in condition_entries:
            if isinstance(condition, dict):
                condition.setdefault("pre_task_bindings", [])
                condition.setdefault("post_task_bindings", [])
        payload.setdefault("task_modules", [])
        payload.setdefault("task_assets", [])
    # Historical readers supplied this default. Current handoffs require it.
    payload.setdefault("protocol", {"base_hz": 6.0, "oddball_every_n": 5})
    producer = payload.setdefault("producer", {})
    if isinstance(producer, dict):
        producer.setdefault("version", "unknown")
        producer.setdefault("exported_at", None)
    payload.update(
        format="fpvs-handoff", format_version=2,
        kind="completed_session" if payload.get("completed_session") is not None else "setup",
    )
    return payload, version


def validate_legacy_config_revision(config: ProjectConfigFile, version: str) -> None:
    """Keep old feature declarations honest after canonical semantic validation."""

    revision = max(2, int(version.split(".")[1]))
    completed = config.completed_session
    defaults = config.condition_defaults
    rules = (
        (3, "Letter-stream configs", any(
            isinstance(item.attentional_blink, AttentionalBlinkStreamSettings)
            for item in config.conditions
        )),
        (4, "Condition modifiers", bool(config.condition_modifiers) or any(
            task.image_memory for task in config.task_modules
        )),
        (5, "Native scene workflows", any(
            modifier.masking is not None for modifier in config.condition_modifiers
        ) or any(task_requires_scene_schema(task) for task in config.task_modules)),
        (6, "Masking catch trials", any(
            modifier.masking is not None and modifier.masking.catch_trial is not None
            for modifier in config.condition_modifiers
        )),
        (7, "Catch conditions and task text alignment", any(
            condition.masking_catch for condition in config.conditions
        ) or any(task_requires_text_alignment_schema(task) for task in config.task_modules)),
        (8, "Masking event triggers", any(
            modifier.masking is not None and modifier.masking.event_triggers is not None
            for modifier in config.condition_modifiers
        )),
        (9, "Condition frequency overrides", any(
            condition.base_hz is not None for condition in config.conditions
        )),
        (10, "Stream duration overrides", any(
            condition.stream_duration_seconds is not None for condition in config.conditions
        ) or (defaults is not None and defaults.stream_duration_seconds is not None)),
        (11, "Presentation counts", any(
            condition.presentation_count is not None for condition in config.conditions
        ) or (defaults is not None and defaults.presentation_count is not None)),
        (12, "Randomization controls", config.session.randomization_mode is not None or (
            completed is not None and completed.randomization_seeds is not None
        )),
        (13, "Saved order/provenance", config.session.saved_condition_order is not None or (
            completed is not None and completed.ordering_policy is not None
        )),
        (14, "Post-condition Questions", any(
            task.simple_post_questions for task in config.task_modules
        )),
        (15, "Randomized condition blocks", config.session.condition_ordering is not None or (
            completed is not None
            and completed.ordering_policy in {"randomized_blocks", "saved_randomized_blocks"}
        )),
    )
    for minimum, feature, present in rules:
        if present and revision < minimum:
            raise ValueError(f"{feature} require config schema 1.{minimum}.0.")
