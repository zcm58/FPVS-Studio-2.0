"""Dedicated execution-plan schemas for compiled FPVS runs."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from fpvs_studio.core.enums import SchemaVersion
from fpvs_studio.core.models import (
    FPVSBaseModel,
    validate_color,
    validate_project_relative_path,
)

StimulusRole = Literal["base", "oddball"]


class DisplayRunSpec(FPVSBaseModel):
    """Frame-level display timing for one compiled condition run."""

    refresh_hz: float = Field(gt=0)
    background_color: str
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
    template_id: str
    instructions_text: str | None = None
    base_hz: float = Field(gt=0)
    oddball_every_n: int = Field(gt=0)
    oddball_hz: float = Field(gt=0)
    total_oddball_cycles: int = Field(ge=0)
    total_stimuli: int = Field(ge=0)
    trigger_code: int | None = None


class StimulusEvent(FPVSBaseModel):
    """One scheduled stimulus presentation in frame units."""

    sequence_index: int = Field(ge=0)
    role: StimulusRole
    image_path: str
    on_start_frame: int = Field(ge=0)
    on_frames: int = Field(ge=0)
    off_frames: int = Field(ge=0)

    @field_validator("image_path")
    @classmethod
    def validate_image_path(cls, value: str) -> str:
        return validate_project_relative_path(value)


class FixationStyleSpec(FPVSBaseModel):
    """Fixation rendering and response settings used during a run."""

    default_color: str
    target_color: str
    response_keys: list[str]
    cross_size_px: int = Field(gt=0)
    line_width_px: int = Field(gt=0)
    target_duration_frames: int = Field(ge=0)

    @field_validator("default_color", "target_color")
    @classmethod
    def validate_fixation_color(cls, value: str) -> str:
        validated = validate_color(value)
        if not isinstance(validated, str):
            raise ValueError("Fixation colors must be stored as strings.")
        return validated


class FixationEvent(FPVSBaseModel):
    """One scheduled fixation-color target event."""

    event_index: int = Field(ge=0)
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(gt=0)


class TriggerEvent(FPVSBaseModel):
    """One trigger pulse scheduled relative to the frame clock."""

    frame_index: int = Field(ge=0)
    code: int
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
