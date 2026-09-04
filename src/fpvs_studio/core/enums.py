"""Shared enumerations for editable models, compiled contracts, and runtime coordination.
These values keep ProjectFile, RunSpec, SessionPlan, manifests, and execution summaries
speaking the same engine-neutral vocabulary. The module owns stable symbolic choices
only; validation rules and behavioral decisions live in the layers that consume them."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """String-backed enum base class."""


class SchemaVersion(StrEnum):
    """Supported schema versions shared by unchanged persisted contracts."""

    V1 = "1.0.0"
    V1_1 = "1.1.0"
    V1_2 = "1.2.0"


class ProjectSchemaVersion(StrEnum):
    """Supported editable project-file schema versions."""

    V1 = "1.0.0"
    V1_1 = "1.1.0"
    V1_2 = "1.2.0"
    V1_3 = "1.3.0"


class DutyCycleMode(StrEnum):
    """Presentation duty-cycle choices for v1."""

    CONTINUOUS = "continuous"
    BLANK_50 = "blank_50"
    SINUSOIDAL = "sinusoidal"


class InterConditionMode(StrEnum):
    """Supported transition policies between condition runs."""

    FIXED_BREAK = "fixed_break"
    MANUAL_CONTINUE = "manual_continue"


class StimulusVariant(StrEnum):
    """Supported source/derived stimulus variants."""

    ORIGINAL = "original"
    GRAYSCALE = "grayscale"
    ROT180 = "rot180"
    PHASE_SCRAMBLED = "phase_scrambled"


class StimulusModality(StrEnum):
    """Supported authored stimulus payload types."""

    IMAGE = "image"
    WORD = "word"


class StimulusTransform(StrEnum):
    """Runtime-only visual transforms applied without creating derived files."""

    NONE = "none"
    MIRROR_HORIZONTAL = "mirror_horizontal"
    MIRROR_VERTICAL = "mirror_vertical"
    ROT180 = "rot180"


class PresentationUnit(StrEnum):
    """Authoring units supported by text presentation settings."""

    DEGREES = "degrees"
    WINDOW_HEIGHT_FRACTION = "window_height_fraction"


class TextHeightMode(StrEnum):
    """How word height values are selected for a condition role."""

    FIXED = "fixed"
    BALANCED_RANDOMIZED = "balanced_randomized"


class ImageGeometryMode(StrEnum):
    """How an image is fitted to its authored visual-angle geometry."""

    EXACT_BOX = "exact_box"
    CONTAIN = "contain"
    COVER = "cover"
    NATURAL_ASPECT = "natural_aspect"


class TriggerBackendKind(StrEnum):
    """Supported trigger backend kinds."""

    NULL = "null"
    SERIAL = "serial"


class RunMode(StrEnum):
    """Runtime modes exposed by the neutral run spec."""

    TEST = "test"
    SESSION = "session"


class EngineName(StrEnum):
    """Presentation engines that can consume a run spec."""

    PSYCHOPY = "psychopy"


class ValidationSeverity(StrEnum):
    """Severity levels for user-facing validation issues."""

    ERROR = "error"
    WARNING = "warning"
