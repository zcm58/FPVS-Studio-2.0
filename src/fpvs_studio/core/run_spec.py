"""Compiled single-condition execution contracts for FPVS playback. Compiler emits these
frame-based models from editable ProjectFile state and manifest-backed assets so runtime
and engines can consume a neutral plan. This module owns one-condition playback schema
only; session ordering lives in SessionPlan and machine-specific launch options stay
outside RunSpec."""

from __future__ import annotations

from math import isfinite
from typing import Literal

from pydantic import Field, StrictInt, field_validator, model_validator

from fpvs_studio.core.enums import (
    DutyCycleMode,
    ImageGeometryMode,
    PresentationUnit,
    SchemaVersion,
    StimulusModality,
    StimulusTransform,
)
from fpvs_studio.core.models import (
    FPVSBaseModel,
    ImageGeometrySettings,
    ImageResolution,
    validate_color,
    validate_presentation_text_color,
    validate_project_relative_path,
    validate_response_key_name,
    validate_slug,
)

StimulusRole = Literal["base", "oddball"]
STUDIO_WORD_FONT_NAME: Literal["Arial"] = "Arial"


class ImageGeometrySpec(FPVSBaseModel):
    """Resolved image fit geometry for one condition role."""

    mode: ImageGeometryMode
    width_degrees: float | None = None
    height_degrees: float | None = None
    source_resolution: ImageResolution

    @model_validator(mode="after")
    def validate_geometry(self) -> ImageGeometrySpec:
        ImageGeometrySettings(
            mode=self.mode,
            width_degrees=self.width_degrees,
            height_degrees=self.height_degrees,
        )
        return self


class TextPresentationSpec(FPVSBaseModel):
    """Resolved typography shared by all events in one condition role."""

    font_name: Literal["Arial"] = STUDIO_WORD_FONT_NAME
    color: str = "#FFFFFF"
    position_unit: PresentationUnit = PresentationUnit.DEGREES
    position_x: float = 0.0
    position_y: float = 0.0
    height_unit: PresentationUnit = PresentationUnit.DEGREES
    legacy_stimulus_width_fraction: float | None = None

    @field_validator("color")
    @classmethod
    def validate_text_color(cls, value: str) -> str:
        return validate_presentation_text_color(value)

    @field_validator("position_x", "position_y")
    @classmethod
    def validate_position(cls, value: float) -> float:
        normalized = float(value)
        if not isfinite(normalized):
            raise ValueError("Compiled text positions must be finite.")
        return normalized

    @field_validator("legacy_stimulus_width_fraction")
    @classmethod
    def validate_legacy_height_fraction(cls, value: float | None) -> float | None:
        if value is None:
            return None
        normalized = float(value)
        if not isfinite(normalized) or normalized <= 0:
            raise ValueError(
                "Legacy stimulus-width text-height fraction must be finite and greater than zero."
            )
        return normalized


class RolePresentationSpec(FPVSBaseModel):
    """Resolved runtime presentation for one base or oddball role."""

    transform: StimulusTransform = StimulusTransform.NONE
    image_geometry: ImageGeometrySpec | None = None
    text: TextPresentationSpec | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> RolePresentationSpec:
        if (self.image_geometry is None) == (self.text is None):
            raise ValueError("A role presentation requires exactly one of image_geometry or text.")
        return self


class ConditionPresentationSpec(FPVSBaseModel):
    """Resolved base and oddball presentation contract for one run."""

    base: RolePresentationSpec
    oddball: RolePresentationSpec


class DisplayRunSpec(FPVSBaseModel):
    """Frame-level display timing for one compiled condition run."""

    refresh_hz: float = Field(gt=0)
    background_color: str
    stimulus_width_degrees: float = Field(gt=0)
    viewing_distance_cm: float = Field(gt=0)
    screen_width_cm: float = Field(gt=0)
    screen_width_px: int = Field(gt=0)
    screen_height_px: int = Field(gt=0)
    use_current_screen_resolution: bool = False
    duty_cycle_mode: DutyCycleMode = DutyCycleMode.CONTINUOUS
    frames_per_stimulus: int = Field(gt=0)
    on_frames: int = Field(ge=0)
    off_frames: int = Field(ge=0)
    duty_cycle: float = Field(gt=0, le=1)
    total_frames: int = Field(ge=0)

    @field_validator("background_color")
    @classmethod
    def validate_background_color(cls, value: str) -> str:
        validated = validate_color(value)
        if not isinstance(validated, str):
            raise ValueError("Display background color must be stored as a string.")
        return validated


class ConditionRunSpec(FPVSBaseModel):
    """Condition metadata and fixed protocol constants for runtime execution."""

    condition_id: str
    name: str
    show_title_on_screen: bool = False
    template_id: str
    instructions_text: str | None = None
    base_hz: float = Field(gt=0)
    oddball_every_n: int = Field(gt=0)
    oddball_hz: float = Field(gt=0)
    total_oddball_cycles: int = Field(ge=0)
    total_stimuli: int = Field(ge=0)
    stimulus_modality: StimulusModality
    trigger_code: StrictInt | None = Field(default=None, ge=0, le=255)


class StimulusEvent(FPVSBaseModel):
    """One scheduled stimulus presentation in frame units."""

    sequence_index: int = Field(ge=0)
    role: StimulusRole
    stimulus_modality: StimulusModality
    stimulus_id: str
    image_path: str | None = None
    text: str | None = None
    text_height_value: float | None = None
    on_start_frame: int = Field(ge=0)
    on_frames: int = Field(ge=0)
    off_frames: int = Field(ge=0)

    @field_validator("stimulus_id")
    @classmethod
    def validate_stimulus_id(cls, value: str) -> str:
        return validate_slug(value, field_name="stimulus_id")

    @field_validator("image_path")
    @classmethod
    def validate_image_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_project_relative_path(value)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Word stimulus text may not be blank.")
        return cleaned

    @field_validator("text_height_value")
    @classmethod
    def validate_text_height_value(cls, value: float | None) -> float | None:
        if value is None:
            return None
        normalized = float(value)
        if not isfinite(normalized) or normalized <= 0:
            raise ValueError("Compiled text height must be finite and greater than zero.")
        return normalized

    @model_validator(mode="after")
    def validate_payload(self) -> StimulusEvent:
        if self.stimulus_modality == StimulusModality.IMAGE:
            if self.image_path is None:
                raise ValueError("Image stimulus events require image_path.")
            if self.text is not None:
                raise ValueError("Image stimulus events may not contain text.")
            if self.text_height_value is not None:
                raise ValueError("Image stimulus events may not contain text_height_value.")
            return self
        if self.stimulus_modality == StimulusModality.WORD:
            if self.text is None:
                raise ValueError("Word stimulus events require text.")
            if self.image_path is not None:
                raise ValueError("Word stimulus events may not contain image_path.")
            return self
        raise ValueError(f"Unsupported stimulus modality '{self.stimulus_modality}'.")


class FixationStyleSpec(FPVSBaseModel):
    """Fixation rendering and response settings used during a run."""

    accuracy_task_enabled: bool = False
    participant_tutorial_enabled: bool = False
    default_color: str
    target_color: str
    response_key: str = "space"
    response_window_frames: int = Field(default=1, gt=0)
    response_keys: list[str]
    cross_size_px: int = Field(gt=0)
    line_width_px: int = Field(gt=0)
    target_duration_frames: int = Field(ge=0)
    realized_target_count: int = Field(default=0, ge=0)

    @field_validator("default_color", "target_color")
    @classmethod
    def validate_fixation_color(cls, value: str) -> str:
        validated = validate_color(value)
        if not isinstance(validated, str):
            raise ValueError("Fixation colors must be stored as strings.")
        return validated

    @field_validator("response_key")
    @classmethod
    def validate_response_key(cls, value: str) -> str:
        return validate_response_key_name(value)

    @field_validator("response_keys")
    @classmethod
    def validate_response_keys(cls, value: list[str]) -> list[str]:
        if not value:
            return value
        cleaned = [validate_response_key_name(item) for item in value if item.strip()]
        if not cleaned:
            raise ValueError("Response key values may not be blank.")
        return cleaned


class FixationEvent(FPVSBaseModel):
    """One scheduled fixation-color target event."""

    event_index: int = Field(ge=0)
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(gt=0)


class TriggerEvent(FPVSBaseModel):
    """One trigger pulse scheduled relative to the frame clock."""

    frame_index: int = Field(ge=0)
    code: StrictInt = Field(ge=1, le=255)
    label: str


class RunSpec(FPVSBaseModel):
    """Compiled execution plan for one condition run."""

    schema_version: str = SchemaVersion.V1_1.value
    run_id: str
    project_id: str
    project_name: str
    template_id: str
    random_seed: int = Field(ge=0)
    condition: ConditionRunSpec
    display: DisplayRunSpec
    fixation: FixationStyleSpec
    presentation: ConditionPresentationSpec | None = None
    pre_stream_fixation_frames: int = Field(default=0, ge=0)
    stimulus_sequence: list[StimulusEvent] = Field(default_factory=list)
    fixation_events: list[FixationEvent] = Field(default_factory=list)
    trigger_events: list[TriggerEvent] = Field(default_factory=list)
