"""Editable engine-neutral project schemas for FPVS Studio. These Pydantic models define
ProjectFile state, settings, conditions, validation reports, and related metadata that
feed compilation and preprocessing. They own persisted authoring truth, not compiled
RunSpec or SessionPlan artifacts and not runtime-only machine options."""

from __future__ import annotations

import random
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from math import isfinite
from typing import Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

from fpvs_studio.core.display_geometry import scaled_visual_angle_degrees
from fpvs_studio.core.enums import (
    DutyCycleMode,
    ImageGeometryMode,
    InterConditionMode,
    PresentationUnit,
    RunMode,
    SchemaVersion,
    StimulusModality,
    StimulusTransform,
    StimulusVariant,
    TextHeightMode,
    TriggerBackendKind,
    ValidationSeverity,
)
from fpvs_studio.core.paths import validate_project_relative_path
from fpvs_studio.core.task_models import TaskBinding, TaskModule
from fpvs_studio.core.trigger_codes import (
    LOCKED_ODDBALL_TRIGGER_CODE,
    validate_oddball_trigger_code_policy,
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
MAX_WORD_STIMULUS_CHARS = 64
DEFAULT_STIMULUS_WIDTH_DEGREES = 5.0
LEGACY_WORD_HEIGHT_TO_STIMULUS_WIDTH_RATIO = 0.25
DEFAULT_WORD_HEIGHT_DEGREES = scaled_visual_angle_degrees(
    degrees=DEFAULT_STIMULUS_WIDTH_DEGREES,
    scale=LEGACY_WORD_HEIGHT_TO_STIMULUS_WIDTH_RATIO,
)
RESERVED_RESPONSE_KEYS = frozenset({"escape"})
_MANUAL_REMOVED_ELECTRODE_SPLIT_RE = re.compile(r"[,;\r\n]+")

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


def validate_slug(value: str, *, field_name: str) -> str:
    """Validate a stable slug-like identifier."""

    if not SLUG_RE.fullmatch(value):
        raise ValueError(f"{field_name} must contain only lowercase letters, digits, and hyphens.")
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


def validate_response_key_name(value: str) -> str:
    """Validate a participant response key name against runtime control keys."""

    cleaned = value.strip().lower()
    if not cleaned:
        raise ValueError("response_key may not be blank.")
    if cleaned in RESERVED_RESPONSE_KEYS:
        raise ValueError(f"'{cleaned}' is reserved for abort and cannot be a response key.")
    return cleaned


def strip_bidi_controls(value: str) -> str:
    """Remove invisible bidirectional control characters from persisted text."""

    return value.translate(_BIDI_CONTROL_CODEPOINTS)


def normalize_manual_removed_electrodes(value: str | Iterable[str]) -> list[str]:
    """Return stable uppercase electrode labels from launch-time administrator input."""

    raw_values = [value] if isinstance(value, str) else value
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        if not isinstance(raw_value, str):
            raise ValueError("Manually removed electrode labels must be text values.")
        for candidate in _MANUAL_REMOVED_ELECTRODE_SPLIT_RE.split(raw_value):
            label = strip_bidi_controls(candidate).strip().upper()
            if label and label not in seen:
                normalized.append(label)
                seen.add(label)
    return normalized


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
    """Display refresh compatibility and realized frame timing."""

    refresh_hz: float = Field(gt=0)
    base_hz: float = Field(gt=0)
    duty_cycle_mode: DutyCycleMode | None = None
    frames_per_cycle_raw: float = Field(gt=0)
    frames_per_cycle: int | None = Field(default=None, ge=1)
    timing_is_exact: bool = True
    realized_base_hz: float | None = Field(default=None, gt=0)
    oddball_every_n: int | None = Field(default=None, ge=1)
    requested_oddball_hz: float | None = Field(default=None, gt=0)
    realized_oddball_hz: float | None = Field(default=None, gt=0)
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
    # Kept as a compatibility mirror for 1.0 projects and config interchange.
    # ProjectSettings.presentation is authoritative for new presentation geometry.
    stimulus_width_degrees: float = Field(default=DEFAULT_STIMULUS_WIDTH_DEGREES, gt=0)
    viewing_distance_cm: float = Field(default=80.0, gt=0)
    screen_width_cm: float = Field(default=52.03, gt=0)
    screen_width_px: int = Field(default=1920, gt=0)
    screen_height_px: int = Field(default=1080, gt=0)
    use_current_screen_resolution: bool = False

    @field_validator("background_color")
    @classmethod
    def validate_background_color(
        cls, value: str | tuple[int, int, int]
    ) -> str | tuple[int, int, int]:
        return validate_color(value)


class TextHeightScheduleSettings(FPVSBaseModel):
    """Fixed or balanced-randomized word heights for one presentation role."""

    mode: TextHeightMode = TextHeightMode.FIXED
    unit: PresentationUnit = PresentationUnit.DEGREES
    values: list[float] = Field(default_factory=lambda: [DEFAULT_WORD_HEIGHT_DEGREES])
    # Internal migration metadata preserving the v1 renderer's intermediate pixel
    # rounding. It is intentionally not exposed as an authoring unit.
    legacy_stimulus_width_fraction: float | None = None

    @field_validator("values")
    @classmethod
    def validate_values(cls, value: list[float]) -> list[float]:
        if not value:
            raise ValueError("Text height values may not be empty.")
        normalized = [float(item) for item in value]
        if any(not isfinite(item) or item <= 0 for item in normalized):
            raise ValueError("Text height values must be finite and greater than zero.")
        if len(normalized) != len(set(normalized)):
            raise ValueError("Text height values must not contain duplicates.")
        return normalized

    @model_validator(mode="after")
    def validate_mode_count(self) -> TextHeightScheduleSettings:
        if self.mode == TextHeightMode.FIXED and len(self.values) != 1:
            raise ValueError("Fixed text height requires exactly one value.")
        if self.mode == TextHeightMode.BALANCED_RANDOMIZED and len(self.values) < 2:
            raise ValueError("Balanced-randomized text height requires at least two values.")
        if self.legacy_stimulus_width_fraction is not None:
            if (
                not isfinite(self.legacy_stimulus_width_fraction)
                or self.legacy_stimulus_width_fraction <= 0
            ):
                raise ValueError(
                    "Legacy stimulus-width text-height fraction must be finite and greater "
                    "than zero."
                )
            if self.mode != TextHeightMode.FIXED or self.unit != PresentationUnit.DEGREES:
                raise ValueError(
                    "Legacy stimulus-width text-height compatibility requires fixed degree "
                    "settings."
                )
        return self


class TextPositionSettings(FPVSBaseModel):
    """Text center position in visual degrees or active-window-height fractions."""

    unit: PresentationUnit = PresentationUnit.DEGREES
    x: float = 0.0
    y: float = 0.0

    @field_validator("x", "y")
    @classmethod
    def validate_coordinate(cls, value: float) -> float:
        normalized = float(value)
        if not isfinite(normalized):
            raise ValueError("Text position values must be finite.")
        return normalized


class ImageGeometrySettings(FPVSBaseModel):
    """Authored image fit policy and visual-angle box dimensions."""

    mode: ImageGeometryMode = ImageGeometryMode.NATURAL_ASPECT
    width_degrees: float | None = DEFAULT_STIMULUS_WIDTH_DEGREES
    height_degrees: float | None = None

    @field_validator("width_degrees", "height_degrees")
    @classmethod
    def validate_dimension(cls, value: float | None) -> float | None:
        if value is None:
            return None
        normalized = float(value)
        if not isfinite(normalized) or normalized <= 0:
            raise ValueError("Image geometry dimensions must be finite and greater than zero.")
        return normalized

    @model_validator(mode="after")
    def validate_mode_dimensions(self) -> ImageGeometrySettings:
        has_width = self.width_degrees is not None
        has_height = self.height_degrees is not None
        if self.mode == ImageGeometryMode.NATURAL_ASPECT:
            if has_width == has_height:
                raise ValueError("Natural-aspect geometry requires exactly one authored dimension.")
            return self
        if not has_width or not has_height:
            raise ValueError(
                f"{self.mode.value} geometry requires both width_degrees and height_degrees."
            )
        return self


def validate_presentation_text_color(value: str) -> str:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError("Presentation text color must be an opaque hex value like '#FFFFFF'.")
    return value.upper()


class StimulusPresentationDefaults(FPVSBaseModel):
    """Fully specified project-level presentation defaults."""

    transform: StimulusTransform = StimulusTransform.NONE
    image_geometry: ImageGeometrySettings = Field(default_factory=ImageGeometrySettings)
    text_height: TextHeightScheduleSettings = Field(default_factory=TextHeightScheduleSettings)
    text_color: str = "#FFFFFF"
    text_position: TextPositionSettings = Field(default_factory=TextPositionSettings)

    @field_validator("text_color")
    @classmethod
    def validate_text_color(cls, value: str) -> str:
        return validate_presentation_text_color(value)


class StimulusPresentationOverride(FPVSBaseModel):
    """Atomic presentation groups optionally overriding inherited settings."""

    transform: StimulusTransform | None = None
    image_geometry: ImageGeometrySettings | None = None
    text_height: TextHeightScheduleSettings | None = None
    text_color: str | None = None
    text_position: TextPositionSettings | None = None

    @field_validator("text_color")
    @classmethod
    def validate_text_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_presentation_text_color(value)


class ProjectPresentationSettings(FPVSBaseModel):
    """Project presentation defaults plus the fixation-only condition lead-in."""

    pre_stream_fixation_seconds: float = Field(default=2.0, ge=0)
    defaults: StimulusPresentationDefaults = Field(default_factory=StimulusPresentationDefaults)

    @field_validator("pre_stream_fixation_seconds")
    @classmethod
    def validate_lead_in(cls, value: float) -> float:
        normalized = float(value)
        if not isfinite(normalized):
            raise ValueError("Pre-stream fixation duration must be finite.")
        return normalized


class ConditionPresentationSettings(FPVSBaseModel):
    """Condition-wide and role-specific presentation overrides."""

    common: StimulusPresentationOverride = Field(default_factory=StimulusPresentationOverride)
    base: StimulusPresentationOverride = Field(default_factory=StimulusPresentationOverride)
    oddball: StimulusPresentationOverride = Field(default_factory=StimulusPresentationOverride)
    pre_stream_fixation_seconds: float | None = Field(default=None, ge=0)

    @field_validator("pre_stream_fixation_seconds")
    @classmethod
    def validate_lead_in(cls, value: float | None) -> float | None:
        if value is None:
            return None
        normalized = float(value)
        if not isfinite(normalized):
            raise ValueError("Pre-stream fixation duration must be finite.")
        return normalized


class ProtocolSettings(FPVSBaseModel):
    """Project-wide editable FPVS presentation cadence."""

    base_hz: float = Field(default=6.0, gt=0)
    oddball_every_n: int = Field(default=5, ge=1)

    @property
    def oddball_hz(self) -> float:
        """Return the oddball rate derived from the integer stimulus cadence."""

        return self.base_hz / self.oddball_every_n


class FixationTaskSettings(FPVSBaseModel):
    """Project-level fixation-cross color-change task settings."""

    enabled: bool = False
    accuracy_task_enabled: bool = False
    participant_tutorial_enabled: bool = True
    changes_per_sequence: int = Field(
        default=0,
        ge=0,
        validation_alias=AliasChoices("changes_per_sequence", "color_changes_per_condition"),
    )
    target_count_mode: Literal["fixed", "randomized"] = "fixed"
    target_count_min: int = Field(default=1, ge=0)
    target_count_max: int = Field(default=3, ge=0)
    no_immediate_repeat_count: bool = True
    base_color: str | tuple[int, int, int] = "#0000FF"
    target_color: str | tuple[int, int, int] = "#FF0000"
    target_duration_ms: int = Field(default=250, ge=0)
    min_gap_ms: int = Field(default=1500, ge=0)
    max_gap_ms: int = Field(default=3000, ge=0)
    response_key: str = "space"
    response_window_seconds: float = Field(default=1.0, gt=0)
    response_keys: list[str] = Field(default_factory=lambda: ["space"])
    cross_size_px: int = Field(default=27, gt=0)
    line_width_px: int = Field(default=2, gt=0)

    @property
    def color_changes_per_condition(self) -> int:
        """Return the fixed color-change count per condition (legacy key compatible)."""

        return self.changes_per_sequence

    @field_validator("base_color", "target_color")
    @classmethod
    def validate_fixation_colors(
        cls, value: str | tuple[int, int, int]
    ) -> str | tuple[int, int, int]:
        return validate_color(value)

    @field_validator("response_keys")
    @classmethod
    def validate_response_keys(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("At least one response key must be provided.")
        cleaned = [validate_response_key_name(item) for item in value if item.strip()]
        if not cleaned:
            raise ValueError("Response key values may not be blank.")
        return cleaned

    @field_validator("response_key")
    @classmethod
    def validate_response_key(cls, value: str) -> str:
        return validate_response_key_name(value)

    @model_validator(mode="after")
    def validate_ranges(self) -> FixationTaskSettings:
        if self.enabled and self.target_duration_ms <= 0:
            raise ValueError("Fixation target duration must be greater than 0 ms when enabled.")
        if self.accuracy_task_enabled and not self.enabled:
            raise ValueError(
                "Fixation task must be enabled when the fixation accuracy task is enabled."
            )
        if self.target_count_mode == "randomized":
            if self.target_count_min > self.target_count_max:
                raise ValueError(
                    "Fixation target_count_min must be less than or equal to target_count_max."
                )
            if self.no_immediate_repeat_count and self.target_count_min == self.target_count_max:
                raise ValueError(
                    "Randomized color changes per condition (target counts) require "
                    "min/max to differ when no immediate repeat is enabled."
                )
        if self.response_key not in self.response_keys:
            self.response_keys = [self.response_key, *self.response_keys]
        return self


class ConditionDefaults(FPVSBaseModel):
    """Project-level default values applied to new or standardized conditions."""

    duty_cycle_mode: DutyCycleMode = DutyCycleMode.CONTINUOUS
    sequence_count: int = Field(default=1, ge=1)
    oddball_cycle_repeats_per_sequence: int = Field(default=146, ge=1)
    target_repeats_per_image: int = Field(default=7, ge=1)


class TriggerSettings(FPVSBaseModel):
    """Project-level trigger backend configuration."""

    backend: TriggerBackendKind = TriggerBackendKind.SERIAL
    enabled: bool = True
    serial_port: str | None = "COM3"
    baudrate: int = Field(default=115200, gt=0)
    oddball_trigger_code: StrictInt = Field(default=LOCKED_ODDBALL_TRIGGER_CODE, ge=1, le=255)
    allow_nonstandard_oddball_trigger_code: bool = False
    pulse_width_ms: int = Field(default=10, ge=0)
    reset_code: StrictInt | None = Field(default=None, ge=0, le=0)
    reset_delay_ms: int = Field(default=5, ge=0)

    @model_validator(mode="after")
    def validate_locked_oddball_trigger_code(self) -> TriggerSettings:
        validate_oddball_trigger_code_policy(
            self.oddball_trigger_code,
            allow_nonstandard=self.allow_nonstandard_oddball_trigger_code,
        )
        return self


class SessionSettings(FPVSBaseModel):
    """Project-level session flow settings."""

    block_count: int = Field(default=2, ge=1)
    session_seed: int = Field(default_factory=default_session_seed, ge=0)
    randomize_conditions_per_block: bool = True
    inter_condition_mode: InterConditionMode = InterConditionMode.MANUAL_CONTINUE
    inter_condition_break_seconds: float = Field(default=0.0, ge=0)
    continue_key: str = "space"
    show_condition_title_on_screen: bool = False

    @field_validator("continue_key")
    @classmethod
    def validate_continue_key(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("continue_key may not be blank.")
        return cleaned


class ProjectSettings(FPVSBaseModel):
    """Editable project-level settings."""

    condition_profile_id: str | None = None
    condition_defaults: ConditionDefaults = Field(default_factory=ConditionDefaults)
    display: DisplaySettings = Field(default_factory=DisplaySettings)
    presentation: ProjectPresentationSettings = Field(default_factory=ProjectPresentationSettings)
    protocol: ProtocolSettings = Field(default_factory=ProtocolSettings)
    fixation_task: FixationTaskSettings = Field(default_factory=FixationTaskSettings)
    triggers: TriggerSettings = Field(default_factory=TriggerSettings)
    session: SessionSettings = Field(default_factory=SessionSettings)
    supported_variants: list[StimulusVariant] = Field(
        default_factory=lambda: list(SUPPORTED_VARIANTS)
    )

    @field_validator("condition_profile_id")
    @classmethod
    def validate_condition_profile_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            return None
        return validate_slug(cleaned, field_name="condition_profile_id")


class StimulusSet(FPVSBaseModel):
    """Imported stimulus-set metadata stored in the project file."""

    set_id: str
    name: str
    modality: StimulusModality = StimulusModality.IMAGE
    source_dir: str | None = None
    resolution: ImageResolution | None = None
    image_count: int = Field(default=0, ge=0)
    available_variants: list[StimulusVariant] = Field(
        default_factory=lambda: [StimulusVariant.ORIGINAL]
    )
    manifest_tag: str | None = None
    words: list[str] = Field(default_factory=list)

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

    @property
    def word_count(self) -> int:
        """Return the number of authored word stimuli."""

        return len(self.words)

    @field_validator("source_dir")
    @classmethod
    def validate_source_dir(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_project_relative_path(value)

    @field_validator("words")
    @classmethod
    def validate_words(cls, value: list[str]) -> list[str]:
        cleaned_words: list[str] = []
        for word in value:
            cleaned = strip_bidi_controls(word.strip())
            if not cleaned:
                raise ValueError("Word stimuli may not contain blank entries.")
            if len(cleaned) > MAX_WORD_STIMULUS_CHARS:
                raise ValueError(
                    f"Word stimuli may not exceed {MAX_WORD_STIMULUS_CHARS} characters."
                )
            cleaned_words.append(cleaned)
        return cleaned_words

    @model_validator(mode="after")
    def validate_modality_payload(self) -> StimulusSet:
        if self.modality == StimulusModality.IMAGE:
            if self.source_dir is None:
                raise ValueError("Image stimulus sets require source_dir.")
            if self.words:
                raise ValueError("Image stimulus sets may not store word stimuli.")
            return self
        if self.modality == StimulusModality.WORD:
            if self.source_dir is not None:
                raise ValueError("Word stimulus sets must persist source_dir=None.")
            if self.image_count != 0:
                raise ValueError("Word stimulus sets may not store image_count.")
            if self.resolution is not None:
                raise ValueError("Word stimulus sets may not store image resolution.")
            if self.available_variants != [StimulusVariant.ORIGINAL]:
                raise ValueError("Word stimulus sets may not store image variants.")
            return self
        raise ValueError(f"Unsupported stimulus modality '{self.modality}'.")


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
    trigger_code: StrictInt = Field(default=1, ge=1, le=255)
    duty_cycle_mode: DutyCycleMode = DutyCycleMode.CONTINUOUS
    order_index: int = Field(default=0, ge=0)
    presentation: ConditionPresentationSettings = Field(
        default_factory=ConditionPresentationSettings
    )
    pre_task_bindings: list[TaskBinding] = Field(default_factory=list)
    post_task_bindings: list[TaskBinding] = Field(default_factory=list)

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

    @model_validator(mode="after")
    def validate_unique_task_bindings(self) -> Condition:
        for label, bindings in (
            ("pre", self.pre_task_bindings),
            ("post", self.post_task_bindings),
        ):
            task_ids = [binding.task_id for binding in bindings]
            if len(task_ids) != len(set(task_ids)):
                raise ValueError(f"Condition {label}-task bindings must be unique.")
        if any(binding.replaces_condition_start_gate for binding in self.post_task_bindings):
            raise ValueError(
                "Only a pre-condition task binding may replace the standard start gate."
            )
        if sum(
            binding.replaces_condition_start_gate for binding in self.pre_task_bindings
        ) > 1:
            raise ValueError(
                "At most one pre-condition task binding may replace the standard start gate."
            )
        return self


class ProjectFile(FPVSBaseModel):
    """Canonical editable project file."""

    schema_version: SchemaVersion = SchemaVersion.V1_2
    meta: ProjectMeta
    settings: ProjectSettings = Field(default_factory=ProjectSettings)
    stimulus_sets: list[StimulusSet] = Field(default_factory=list)
    conditions: list[Condition] = Field(default_factory=list)
    task_modules: list[TaskModule] = Field(default_factory=list)
    manual_removed_electrodes: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("manual_removed_electrodes", mode="before")
    @classmethod
    def normalize_manual_removed_electrode_map(
        cls,
        value: object,
    ) -> dict[str, list[str]]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("manual_removed_electrodes must be a participant map.")

        normalized: dict[str, list[str]] = {}
        for participant_number, electrodes in value.items():
            if not isinstance(participant_number, str):
                raise ValueError("Manual electrode participant numbers must be text values.")
            participant_number = participant_number.strip()
            if not participant_number or not participant_number.isdigit():
                raise ValueError("Manual electrode participant numbers must contain digits only.")
            if participant_number in normalized:
                raise ValueError(
                    "Manual electrode participant numbers must be unique after trimming."
                )
            if not isinstance(electrodes, (str, list, tuple)):
                raise ValueError("Manual electrode entries must be text or a list of text values.")
            normalized[participant_number] = normalize_manual_removed_electrodes(electrodes)
        return normalized

    @model_validator(mode="after")
    def validate_unique_ids(self) -> ProjectFile:
        set_ids = [item.set_id for item in self.stimulus_sets]
        if len(set_ids) != len(set(set_ids)):
            raise ValueError("Stimulus set ids must be unique.")
        condition_ids = [item.condition_id for item in self.conditions]
        if len(condition_ids) != len(set(condition_ids)):
            raise ValueError("Condition ids must be unique.")
        task_ids = [item.task_id for item in self.task_modules]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Task module ids must be unique.")
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


class ConditionTemplateDisplayDefaults(FPVSBaseModel):
    """Display defaults that can be snapshotted into a project from a profile."""

    preferred_refresh_hz: float | None = Field(default=None, gt=0)


class ConditionTemplateDefaults(FPVSBaseModel):
    """Condition-template profile defaults."""

    condition: ConditionDefaults = Field(default_factory=ConditionDefaults)
    display: ConditionTemplateDisplayDefaults = Field(
        default_factory=ConditionTemplateDisplayDefaults
    )
    fixation_task: FixationTaskSettings = Field(default_factory=FixationTaskSettings)
    presentation: ProjectPresentationSettings = Field(default_factory=ProjectPresentationSettings)


class ConditionTemplateProfile(FPVSBaseModel):
    """One reusable condition-template profile stored at the FPVS root."""

    profile_id: str
    display_name: str
    description: str = ""
    built_in: bool = False
    defaults: ConditionTemplateDefaults = Field(default_factory=ConditionTemplateDefaults)

    @field_validator("profile_id")
    @classmethod
    def validate_profile_id(cls, value: str) -> str:
        return validate_slug(value, field_name="profile_id")

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("display_name may not be empty.")
        return value

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, value: str) -> str:
        return strip_bidi_controls(value)


class ConditionTemplateProfileLibrary(FPVSBaseModel):
    """Persisted app-level condition-template library."""

    schema_version: SchemaVersion = SchemaVersion.V1_1
    profiles: list[ConditionTemplateProfile] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_profile_ids(self) -> ConditionTemplateProfileLibrary:
        profile_ids = [item.profile_id for item in self.profiles]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("Condition template profile ids must be unique.")
        return self


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
