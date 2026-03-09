"""Engine-neutral Pydantic models for FPVS Studio."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
import random
import re
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from fpvs_studio.core.enums import (
    DutyCycleMode,
    InterConditionMode,
    RunMode,
    SchemaVersion,
    StimulusVariant,
    TriggerBackendKind,
    ValidationSeverity,
)

HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
NAMED_COLOR_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

SUPPORTED_VARIANTS = [
    StimulusVariant.ORIGINAL,
    StimulusVariant.GRAYSCALE,
    StimulusVariant.ROT180,
    StimulusVariant.PHASE_SCRAMBLED,
]

_BIDI_CONTROL_CODEPOINTS = {
    ord("\u061c"): None,  # Arabic Letter Mark
    ord("\u200e"): None,  # Left-to-Right Mark
    ord("\u200f"): None,  # Right-to-Left Mark
    ord("\u202a"): None,  # Left-to-Right Embedding
    ord("\u202b"): None,  # Right-to-Left Embedding
    ord("\u202c"): None,  # Pop Directional Formatting
    ord("\u202d"): None,  # Left-to-Right Override
    ord("\u202e"): None,  # Right-to-Left Override
    ord("\u2066"): None,  # Left-to-Right Isolate
    ord("\u2067"): None,  # Right-to-Left Isolate
    ord("\u2068"): None,  # First Strong Isolate
    ord("\u2069"): None,  # Pop Directional Isolate
}


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def default_session_seed() -> int:
    """Return a persisted default seed for reproducible session compilation."""

    return random.SystemRandom().randrange(2**31)


def validate_project_relative_path(value: str) -> str:
    """Validate a persisted project-relative POSIX path."""

    if not value:
        raise ValueError("Path may not be empty.")
    if "\\" in value:
        raise ValueError("Persisted paths must use POSIX separators ('/').")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise ValueError("Persisted paths must be project-relative, not absolute.")
    if any(part == ".." for part in path.parts):
        raise ValueError("Persisted paths may not escape the project directory.")
    return path.as_posix()


def validate_slug(value: str, *, field_name: str) -> str:
    """Validate a stable slug-like identifier."""

    if not SLUG_RE.fullmatch(value):
        raise ValueError(
            f"{field_name} must contain only lowercase letters, digits, and hyphens."
        )
    return value


def validate_color(value: str | tuple[int, int, int]) -> str | tuple[int, int, int]:
    """Validate a color value represented as a string or RGB triplet."""

    if isinstance(value, str):
        if HEX_COLOR_RE.fullmatch(value) or NAMED_COLOR_RE.fullmatch(value):
            return value
        raise ValueError("Color must be a named color or hex string like '#RRGGBB'.")
    if len(value) != 3:
        raise ValueError("RGB colors must contain exactly three channel values.")
    if any(channel < 0 or channel > 255 for channel in value):
        raise ValueError("RGB channel values must be between 0 and 255.")
    return value


def strip_bidi_controls(value: str) -> str:
    """Remove invisible bidirectional control characters from persisted text."""

    return value.translate(_BIDI_CONTROL_CODEPOINTS)


class FPVSBaseModel(BaseModel):
    """Base model configuration for persisted FPVS Studio data."""

    model_config = ConfigDict(extra="forbid", validate_default=True)


class ImageResolution(FPVSBaseModel):
    """Shared image-resolution model."""

    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)

    def as_tuple(self) -> tuple[int, int]:
        """Return the resolution as a plain tuple."""

        return (self.width_px, self.height_px)


class ValidationIssue(FPVSBaseModel):
    """User-facing validation issue."""

    location: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR


class ProjectValidationReport(FPVSBaseModel):
    """Aggregate validation result for a project model."""

    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return whether the report contains any errors."""

        return not any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)


class DisplayValidationReport(FPVSBaseModel):
    """Display refresh compatibility result for the fixed v1 protocol."""

    refresh_hz: float = Field(gt=0)
    base_hz: float = Field(gt=0)
    duty_cycle_mode: DutyCycleMode | None = None
    frames_per_cycle_raw: float = Field(gt=0)
    frames_per_cycle: int | None = Field(default=None, ge=1)
    compatible: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProjectMeta(FPVSBaseModel):
    """Top-level project metadata."""

    project_id: str
    name: str
    template_id: str
    description: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, value: str) -> str:
        return validate_slug(value, field_name="project_id")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Project name may not be empty.")
        return value

    @field_validator("template_id")
    @classmethod
    def validate_template_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("template_id may not be empty.")
        return value


class DisplaySettings(FPVSBaseModel):
    """Editable display preferences."""

    fullscreen: bool = True
    background_color: str | tuple[int, int, int] = "#000000"
    monitor_name: str | None = None
    preferred_refresh_hz: float | None = Field(default=None, gt=0)

    @field_validator("background_color")
    @classmethod
    def validate_background_color(cls, value: str | tuple[int, int, int]) -> str | tuple[int, int, int]:
        return validate_color(value)


class FixationTaskSettings(FPVSBaseModel):
    """Project-level fixation-cross color-change task settings."""

    enabled: bool = False
    accuracy_task_enabled: bool = False
    changes_per_sequence: int = Field(
        default=0,
        ge=0,
        validation_alias=AliasChoices("changes_per_sequence", "color_changes_per_condition"),
    )
    target_count_mode: Literal["fixed", "randomized"] = "fixed"
    target_count_min: int = Field(default=1, ge=0)
    target_count_max: int = Field(default=3, ge=0)
    no_immediate_repeat_count: bool = True
    base_color: str | tuple[int, int, int] = "#FFFFFF"
    target_color: str | tuple[int, int, int] = "#FF0000"
    target_duration_ms: int = Field(default=250, ge=0)
    min_gap_ms: int = Field(default=1500, ge=0)
    max_gap_ms: int = Field(default=3000, ge=0)
    response_key: str = "space"
    response_window_seconds: float = Field(default=1.0, gt=0)
    response_keys: list[str] = Field(default_factory=lambda: ["space"])
    cross_size_px: int = Field(default=48, gt=0)
    line_width_px: int = Field(default=4, gt=0)

    @property
    def color_changes_per_condition(self) -> int:
        """Return the fixed color-change count per condition (legacy key compatible)."""

        return self.changes_per_sequence

    @field_validator("base_color", "target_color")
    @classmethod
    def validate_fixation_colors(cls, value: str | tuple[int, int, int]) -> str | tuple[int, int, int]:
        return validate_color(value)

    @field_validator("response_keys")
    @classmethod
    def validate_response_keys(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("At least one response key must be provided.")
        cleaned = [item.strip().lower() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("Response key values may not be blank.")
        return cleaned

    @field_validator("response_key")
    @classmethod
    def validate_response_key(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("response_key may not be blank.")
        return cleaned

    @model_validator(mode="after")
    def validate_ranges(self) -> "FixationTaskSettings":
        if self.enabled and self.target_duration_ms <= 0:
            raise ValueError("Fixation target duration must be greater than 0 ms when enabled.")
        if self.min_gap_ms > self.max_gap_ms:
            raise ValueError("Fixation min_gap_ms must be less than or equal to max_gap_ms.")
        if self.accuracy_task_enabled and not self.enabled:
            raise ValueError("Fixation task must be enabled when the fixation accuracy task is enabled.")
        if self.target_count_mode == "randomized":
            if self.target_count_min > self.target_count_max:
                raise ValueError("Fixation target_count_min must be less than or equal to target_count_max.")
            if self.no_immediate_repeat_count and self.target_count_min == self.target_count_max:
                raise ValueError(
                    "Randomized color changes per condition (target counts) require min/max to differ when no immediate repeat is enabled."
                )
        if self.response_key not in self.response_keys:
            self.response_keys = [self.response_key, *self.response_keys]
        return self


class TriggerSettings(FPVSBaseModel):
    """Project-level trigger backend configuration."""

    backend: TriggerBackendKind = TriggerBackendKind.NULL
    enabled: bool = False
    serial_port: str | None = None
    baudrate: int = Field(default=115200, gt=0)
    pulse_width_ms: int = Field(default=10, ge=0)
    reset_code: int | None = 0
    reset_delay_ms: int = Field(default=5, ge=0)


class SessionSettings(FPVSBaseModel):
    """Project-level session flow settings."""

    block_count: int = Field(default=1, ge=1)
    session_seed: int = Field(default_factory=default_session_seed, ge=0)
    randomize_conditions_per_block: bool = True
    inter_condition_mode: InterConditionMode = InterConditionMode.FIXED_BREAK
    inter_condition_break_seconds: float = Field(default=30.0, ge=0)
    continue_key: str = "space"

    @field_validator("continue_key")
    @classmethod
    def validate_continue_key(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("continue_key may not be blank.")
        return cleaned


class ProjectSettings(FPVSBaseModel):
    """Editable project-level settings."""

    display: DisplaySettings = Field(default_factory=DisplaySettings)
    fixation_task: FixationTaskSettings = Field(default_factory=FixationTaskSettings)
    triggers: TriggerSettings = Field(default_factory=TriggerSettings)
    session: SessionSettings = Field(default_factory=SessionSettings)
    supported_variants: list[StimulusVariant] = Field(default_factory=lambda: list(SUPPORTED_VARIANTS))


class StimulusSet(FPVSBaseModel):
    """Imported stimulus-set metadata stored in the project file."""

    set_id: str
    name: str
    source_dir: str
    resolution: ImageResolution | None = None
    image_count: int = Field(default=0, ge=0)
    available_variants: list[StimulusVariant] = Field(
        default_factory=lambda: [StimulusVariant.ORIGINAL]
    )
    manifest_tag: str | None = None

    @field_validator("set_id")
    @classmethod
    def validate_set_id(cls, value: str) -> str:
        return validate_slug(value, field_name="set_id")

    @field_validator("name")
    @classmethod
    def validate_set_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Stimulus set name may not be empty.")
        return value

    @field_validator("source_dir")
    @classmethod
    def validate_source_dir(cls, value: str) -> str:
        return validate_project_relative_path(value)


class Condition(FPVSBaseModel):
    """Editable condition definition."""

    condition_id: str
    name: str
    instructions: str = ""
    base_stimulus_set_id: str
    oddball_stimulus_set_id: str
    stimulus_variant: StimulusVariant = StimulusVariant.ORIGINAL
    sequence_count: int = Field(gt=0)
    oddball_cycle_repeats_per_sequence: int = Field(default=146, ge=1)
    trigger_code: int = Field(default=1, ge=0)
    duty_cycle_mode: DutyCycleMode = DutyCycleMode.CONTINUOUS
    order_index: int = Field(default=0, ge=0)

    @field_validator("condition_id")
    @classmethod
    def validate_condition_id(cls, value: str) -> str:
        return validate_slug(value, field_name="condition_id")

    @field_validator("name")
    @classmethod
    def validate_condition_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Condition name may not be empty.")
        return value

    @field_validator("instructions")
    @classmethod
    def sanitize_instructions(cls, value: str) -> str:
        return strip_bidi_controls(value)

    @field_validator("base_stimulus_set_id", "oddball_stimulus_set_id")
    @classmethod
    def validate_set_reference(cls, value: str) -> str:
        return validate_slug(value, field_name="stimulus set reference")


class ProjectFile(FPVSBaseModel):
    """Canonical editable project file."""

    schema_version: SchemaVersion = SchemaVersion.V1
    meta: ProjectMeta
    settings: ProjectSettings = Field(default_factory=ProjectSettings)
    stimulus_sets: list[StimulusSet] = Field(default_factory=list)
    conditions: list[Condition] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "ProjectFile":
        set_ids = [item.set_id for item in self.stimulus_sets]
        if len(set_ids) != len(set(set_ids)):
            raise ValueError("Stimulus set ids must be unique.")
        condition_ids = [item.condition_id for item in self.conditions]
        if len(condition_ids) != len(set(condition_ids)):
            raise ValueError("Condition ids must be unique.")
        return self


class TemplateSpec(FPVSBaseModel):
    """Built-in protocol template metadata."""

    template_id: str
    display_name: str
    description: str
    base_hz: float = Field(gt=0)
    oddball_every_n: int = Field(gt=0)
    oddball_hz: float = Field(gt=0)
    supported_duty_cycle_modes: tuple[DutyCycleMode, ...]
    default_oddball_cycle_repeats_per_sequence: int = Field(ge=1)


class RunParticipant(FPVSBaseModel):
    """Participant/session metadata attached to a compiled run."""

    participant_id: str | None = None
    session_label: str | None = None
    notes: str = ""


class SessionSummary(FPVSBaseModel):
    """Neutral session summary written by runtime/export layers."""

    schema_version: SchemaVersion = SchemaVersion.V1
    project_id: str
    session_id: str
    engine_name: str
    run_mode: RunMode
    started_at: datetime | None = None
    finished_at: datetime | None = None
    completed_condition_count: int = Field(default=0, ge=0)
    aborted: bool = False
    warnings: list[str] = Field(default_factory=list)
    output_dir: str | None = None

    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_project_relative_path(value)


class TemplateLibraryRecord(FPVSBaseModel):
    """Internal helper model for static template registration."""

    templates: dict[str, TemplateSpec]

    model_config = ConfigDict(extra="forbid", frozen=True)
