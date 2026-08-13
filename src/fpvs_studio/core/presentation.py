"""Presentation inheritance and legacy-default helpers.

Editable project models store fully specified project defaults plus atomic condition
overrides. This module resolves those groups without importing GUI or engine code.
"""

from __future__ import annotations

from typing import Literal

from fpvs_studio.core.display_geometry import scaled_visual_angle_degrees
from fpvs_studio.core.enums import ImageGeometryMode, PresentationUnit, TextHeightMode
from fpvs_studio.core.models import (
    LEGACY_WORD_HEIGHT_TO_STIMULUS_WIDTH_RATIO,
    ConditionPresentationSettings,
    ImageGeometrySettings,
    ProjectPresentationSettings,
    StimulusPresentationDefaults,
    StimulusPresentationOverride,
    TextHeightScheduleSettings,
)

PresentationRole = Literal["base", "oddball"]
_PRESENTATION_GROUP_NAMES = (
    "transform",
    "image_geometry",
    "text_height",
    "text_color",
    "text_position",
)


def resolve_role_presentation(
    project_presentation: ProjectPresentationSettings,
    condition_presentation: ConditionPresentationSettings,
    role: PresentationRole,
) -> StimulusPresentationDefaults:
    """Resolve project, condition-common, and role-specific presentation groups."""

    resolved = project_presentation.defaults.model_copy(deep=True)
    resolved = _apply_override(resolved, condition_presentation.common)
    return _apply_override(resolved, getattr(condition_presentation, role))


def resolve_pre_stream_fixation_seconds(
    project_presentation: ProjectPresentationSettings,
    condition_presentation: ConditionPresentationSettings,
) -> float:
    """Resolve a condition lead-in override against its project default."""

    condition_value = condition_presentation.pre_stream_fixation_seconds
    if condition_value is not None:
        return condition_value
    return project_presentation.pre_stream_fixation_seconds


def legacy_project_presentation_settings(
    stimulus_width_degrees: float,
    *,
    pre_stream_fixation_seconds: float = 0.0,
) -> ProjectPresentationSettings:
    """Return native settings visually equivalent to the 1.0 renderer."""

    word_height_degrees = scaled_visual_angle_degrees(
        degrees=stimulus_width_degrees,
        scale=LEGACY_WORD_HEIGHT_TO_STIMULUS_WIDTH_RATIO,
    )
    return ProjectPresentationSettings(
        pre_stream_fixation_seconds=pre_stream_fixation_seconds,
        defaults=StimulusPresentationDefaults(
            image_geometry=ImageGeometrySettings(
                mode=ImageGeometryMode.NATURAL_ASPECT,
                width_degrees=stimulus_width_degrees,
                height_degrees=None,
            ),
            text_height=TextHeightScheduleSettings(
                mode=TextHeightMode.FIXED,
                unit=PresentationUnit.DEGREES,
                values=[word_height_degrees],
                legacy_stimulus_width_fraction=(LEGACY_WORD_HEIGHT_TO_STIMULUS_WIDTH_RATIO),
            ),
        ),
    )


def _apply_override(
    inherited: StimulusPresentationDefaults,
    override: StimulusPresentationOverride,
) -> StimulusPresentationDefaults:
    updates = {
        name: value.model_copy(deep=True) if hasattr(value, "model_copy") else value
        for name in _PRESENTATION_GROUP_NAMES
        if (value := getattr(override, name)) is not None
    }
    return inherited.model_copy(update=updates, deep=True)
