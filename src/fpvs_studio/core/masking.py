"""Declarative masking modifier settings and exact frame-grid validation."""

from __future__ import annotations

from math import isclose
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, SerializerFunctionWrapHandler, model_serializer, model_validator

from fpvs_studio.core.scene_models import SceneVisual
from fpvs_studio.core.task_models import TaskBaseModel

if TYPE_CHECKING:
    from fpvs_studio.core.models import Condition, ProjectFile


class MaskingCatchTrialSettings(TaskBaseModel):
    """One extra target-absent trial in each variant block."""

    trigger_code: int = Field(ge=1, le=255, strict=True)


class MaskingSettings(TaskBaseModel):
    """A brief repeated target followed by a sampled base-pool mask."""

    variant: Literal["color", "faces", "number"] = "color"
    soa_ms: float = Field(default=50.0, gt=0, allow_inf_nan=False)
    target_duration_ms: float = Field(default=1000 / 60, gt=0, allow_inf_nan=False)
    mask_duration_ms: float = Field(default=100.0, gt=0, allow_inf_nan=False)
    base_duration_ms: float = Field(default=100.0, gt=0, allow_inf_nan=False)
    background_rgb: tuple[float, float, float] = (0.0, 0.0, 0.0)
    target_answers: dict[str, str] = Field(default_factory=dict)
    base_visuals: list[SceneVisual] = Field(default_factory=list)
    target_visuals: list[SceneVisual] = Field(default_factory=list)
    mask_visuals: list[SceneVisual] | None = None
    base_overlays: list[SceneVisual] = Field(default_factory=list)
    fixation_visual: SceneVisual | None = None
    catch_trial: MaskingCatchTrialSettings | None = None

    @model_serializer(mode="wrap")
    def serialize_optional_catch(
        self, handler: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = handler(self)
        if self.catch_trial is None:
            payload.pop("catch_trial", None)
        return payload

    @model_validator(mode="after")
    def validate_rgb(self) -> MaskingSettings:
        if any(not -1 <= value <= 1 for value in self.background_rgb):
            raise ValueError("Masking background RGB values must be between -1 and 1.")
        return self


def exact_frames(milliseconds: float, refresh_hz: float, label: str) -> int:
    """Reject timing that would change the requested interval on this display."""
    raw = milliseconds * refresh_hz / 1000
    frames = round(raw)
    if frames < 1 or not isclose(raw, frames, abs_tol=1e-6, rel_tol=0):
        raise ValueError(
            f"{label} ({milliseconds:g} ms) requires whole frames at {refresh_hz:g} Hz."
        )
    return frames


def masking_frame_counts(
    settings: MaskingSettings,
    *,
    refresh_hz: float,
    base_hz: float,
) -> tuple[int, int, int, int, int]:
    slot = exact_frames(1000 / base_hz, refresh_hz, "Item interval")
    soa = exact_frames(settings.soa_ms, refresh_hz, "Target-to-mask SOA")
    target = exact_frames(settings.target_duration_ms, refresh_hz, "Target duration")
    mask = exact_frames(settings.mask_duration_ms, refresh_hz, "Mask duration")
    base = exact_frames(settings.base_duration_ms, refresh_hz, "Base duration")
    if target > soa:
        raise ValueError("The target must finish by mask onset.")
    if max(soa + mask, soa + base) > slot:
        raise ValueError("Delayed base and mask must finish within the item interval.")
    return slot, soa, target, mask, base


def condition_masking(project: ProjectFile, condition: Condition) -> MaskingSettings | None:
    bound = {binding.task_id for binding in condition.pre_task_bindings}
    for modifier in project.condition_modifiers:
        if modifier.masking is not None and bound.intersection(modifier.pre_task_ids):
            return modifier.masking
    return None


def is_masking_project(project: ProjectFile) -> bool:
    return bool(project.conditions) and all(
        condition_masking(project, condition) is not None for condition in project.conditions
    )


def validate_masking_catch_trials(project: ProjectFile, conditions: list[Condition]) -> None:
    """Check block-wide catch agreement and unambiguous trial-start markers."""
    explicit: dict[str, Condition] = {}
    for condition in project.conditions:
        if not condition.masking_catch:
            continue
        settings = condition_masking(project, condition)
        if settings is None:
            raise ValueError("A masking catch condition requires a Masking modifier.")
        if settings.variant in explicit:
            raise ValueError(f"Only one explicit {settings.variant} catch condition is allowed.")
        explicit[settings.variant] = condition
        masking_catch_source_conditions(project, condition)
        if any(other.condition_id != condition.condition_id
               and other.trigger_code == condition.trigger_code for other in project.conditions):
            raise ValueError(
                "A catch condition trigger code must be distinct from other conditions."
            )
    if explicit:
        for modifier in project.condition_modifiers:
            settings = modifier.masking
            if settings is not None and settings.variant in explicit and settings.catch_trial:
                raise ValueError(
                    f"Disable automatic catch trials for {settings.variant} before using an "
                    "explicit catch condition."
                )
    by_variant: dict[str, MaskingCatchTrialSettings | None] = {}
    for condition in conditions:
        settings = condition_masking(project, condition)
        if settings is None:
            continue
        if settings.variant in by_variant and by_variant[settings.variant] != settings.catch_trial:
            raise ValueError(
                f"All selected {settings.variant} SOAs must use the same catch trial settings."
            )
        by_variant[settings.variant] = settings.catch_trial
    normal_codes = {condition.trigger_code for condition in project.conditions}
    catch_codes: set[int] = set()
    for variant, catch in by_variant.items():
        if catch is None:
            continue
        if catch.trigger_code in normal_codes:
            raise ValueError(
                f"The {variant} catch trigger code collides with an ordinary condition marker."
            )
        if catch.trigger_code in catch_codes:
            raise ValueError("Each masking variant needs a distinct catch trigger code.")
        catch_codes.add(catch.trigger_code)


def masking_catch_source_conditions(
    project: ProjectFile, condition: Condition, selected: list[Condition] | None = None,
) -> list[Condition]:
    """Use the selected variant's SOAs, or its project pool for a standalone catch."""
    settings = condition_masking(project, condition)
    if not condition.masking_catch or settings is None:
        raise ValueError("SOA sampling requires an explicit Masking catch condition.")

    def ordinary_variant(items: list[Condition]) -> list[Condition]:
        return [item for item in items if not item.masking_catch
                and (candidate := condition_masking(project, item)) is not None
                and candidate.variant == settings.variant]

    sources = ordinary_variant(selected) if selected is not None else []
    if not sources:
        sources = ordinary_variant(project.conditions)
    if not sources:
        raise ValueError(
            f"The {settings.variant} catch condition needs an ordinary {settings.variant} "
            "condition to supply its SOA."
        )
    return sources


def _new_masking_catch_condition(
    project: ProjectFile, source_condition_id: str, trigger_code: int | None,
) -> Condition:
    from fpvs_studio.core.trigger_codes import validate_event_trigger_code

    source = next((item for item in project.conditions
                   if item.condition_id == source_condition_id), None)
    if source is None:
        raise ValueError("Select an existing condition before adding a catch condition.")
    settings = condition_masking(project, source)
    if settings is None or source.masking_catch:
        raise ValueError("Select an ordinary Masking condition to add its catch condition.")
    variant = settings.variant
    for condition in project.conditions:
        bound = condition_masking(project, condition)
        if condition.masking_catch and bound is not None and bound.variant == variant:
            raise ValueError(f"The {variant} block already has a catch condition.")
    if any(item.masking is not None and item.masking.variant == variant
           and item.masking.catch_trial is not None for item in project.condition_modifiers):
        raise ValueError(
            f"Disable automatic catch trials for {variant} before adding a catch condition."
        )
    used_codes = {item.trigger_code for item in project.conditions}
    used_codes.update(item.masking.catch_trial.trigger_code for item in project.condition_modifiers
                      if item.masking is not None and item.masking.catch_trial is not None)
    if trigger_code is None:
        preferred = {"color": 10, "faces": 11, "number": 12}[variant]
        trigger_code = next((code for code in [*range(preferred, 256), *range(1, preferred)]
                             if code not in used_codes), None)
        if trigger_code is None:
            raise ValueError("No unused trigger code is available for a catch condition.")
    validate_event_trigger_code(trigger_code, label="catch condition")
    if trigger_code in used_codes:
        raise ValueError(f"Trigger code {trigger_code} is already used by another condition.")
    name = f"{variant.capitalize()} catch"
    if any(item.name.casefold() == name.casefold() for item in project.conditions):
        raise ValueError(f"A condition named '{name}' already exists; rename it first.")
    used_ids = {item.condition_id for item in project.conditions}
    identity = f"{variant}-catch"
    suffix = 2
    while identity in used_ids:
        identity = f"{variant}-catch-{suffix}"
        suffix += 1
    return source.model_copy(deep=True, update={
        "condition_id": identity, "name": name, "masking_catch": True,
        "trigger_code": trigger_code,
        "order_index": max((item.order_index for item in project.conditions), default=-1) + 1,
    })


def masking_catch_condition_block_reason(
    project: ProjectFile, source_condition_id: str,
) -> str | None:
    """Explain unavailable creation without changing the project or its assets."""
    try:
        _new_masking_catch_condition(project, source_condition_id, None)
    except (TypeError, ValueError) as exc:
        return str(exc)
    return None


def add_masking_catch_condition(
    project: ProjectFile, source_condition_id: str, *, trigger_code: int | None = None,
) -> tuple[ProjectFile, str]:
    """Add a visible, once-per-variant catch sharing the source's modifier and tasks."""
    from fpvs_studio.core.enums import ProjectSchemaVersion

    catch = _new_masking_catch_condition(project, source_condition_id, trigger_code)
    draft = project.model_copy(deep=True)
    settings = condition_masking(draft, catch)
    assert settings is not None
    ordered = sorted(draft.conditions, key=lambda item: item.order_index)
    last_variant_index = max(index for index, item in enumerate(ordered)
                             if (bound := condition_masking(draft, item)) is not None
                             and bound.variant == settings.variant)
    ordered.insert(last_variant_index + 1, catch)
    for index, condition in enumerate(ordered):
        condition.order_index = index
    draft.conditions = ordered
    draft.schema_version = ProjectSchemaVersion.V1_9
    validate_masking_catch_trials(draft, draft.conditions)
    return type(project).model_validate(draft.model_dump()), catch.condition_id
