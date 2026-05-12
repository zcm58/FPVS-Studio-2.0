"""Shared BioSemi trigger-code validation helpers."""

from __future__ import annotations


def validate_event_trigger_code(code: object, *, label: str = "trigger") -> int:
    """Return a normal event marker code, constrained to BioSemi's one-byte range."""

    if not isinstance(code, int) or isinstance(code, bool):
        raise TypeError(f"{label} trigger code must be an integer from 1 to 255.")
    if code < 1 or code > 255:
        raise ValueError(f"{label} trigger code must be an integer from 1 to 255.")
    return code


def validate_reset_trigger_code(code: object, *, label: str = "reset") -> int:
    """Return a reset marker code; BioSemi reserves 0 for reset."""

    if not isinstance(code, int) or isinstance(code, bool):
        raise TypeError(f"{label} trigger code must be the integer 0.")
    if code != 0:
        raise ValueError(f"{label} trigger code must be 0.")
    return code
