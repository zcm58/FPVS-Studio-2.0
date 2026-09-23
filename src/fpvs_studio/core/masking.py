"""Declarative masking modifier settings and exact frame-grid validation."""

from __future__ import annotations

from math import isclose
from typing import TYPE_CHECKING, Literal

from pydantic import Field, model_validator

from fpvs_studio.core.scene_models import SceneVisual
from fpvs_studio.core.task_models import TaskBaseModel

if TYPE_CHECKING:
    from fpvs_studio.core.models import Condition, ProjectFile


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
