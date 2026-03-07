"""Enums shared by engine-neutral project and run models."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """String-backed enum base class."""


class SchemaVersion(StrEnum):
    """Supported persisted schema versions."""

    V1 = "1.0.0"


class DutyCycleMode(StrEnum):
    """Presentation duty-cycle choices for v1."""

    CONTINUOUS = "continuous"
    BLANK_50 = "blank_50"


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
