"""Compiled single-condition execution contracts for FPVS playback. Compiler emits these
frame-based models from editable ProjectFile state and manifest-backed assets so runtime
and engines can consume a neutral plan. This module owns one-condition playback schema
only; session ordering lives in SessionPlan and machine-specific launch options stay
outside RunSpec."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, StrictInt, field_validator, model_validator

from fpvs_studio.core.enums import SchemaVersion, StimulusModality
from fpvs_studio.core.models import (
    FPVSBaseModel,
    validate_color,
    validate_project_relative_path,
    validate_slug,
)

StimulusRole = Literal["base", "oddball"]


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
    show_title_on_screen: bool = True
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

    @model_validator(mode="after")
    def validate_payload(self) -> StimulusEvent:
        if self.stimulus_modality == StimulusModality.IMAGE:
            if self.image_path is None:
                raise ValueError("Image stimulus events require image_path.")
            if self.text is not None:
                raise ValueError("Image stimulus events may not contain text.")
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
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("response_key may not be blank.")
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

    schema_version: str = SchemaVersion.V1.value
    run_id: str
    project_id: str
    project_name: str
    template_id: str
    random_seed: int = Field(ge=0)
    condition: ConditionRunSpec
    display: DisplayRunSpec
    fixation: FixationStyleSpec
    stimulus_sequence: list[StimulusEvent] = Field(default_factory=list)
    fixation_events: list[FixationEvent] = Field(default_factory=list)
    trigger_events: list[TriggerEvent] = Field(default_factory=list)
