"""Shared BioSemi trigger-code validation helpers."""

from __future__ import annotations

LOCKED_ODDBALL_TRIGGER_CODE = 55


def validate_event_trigger_code(code: object, *, label: str = "trigger") -> int:
    """Return a normal event marker code, constrained to BioSemi's one-byte range."""

    if not isinstance(code, int) or isinstance(code, bool):
        raise TypeError(f"{label} trigger code must be an integer from 1 to 255.")
    if code < 1 or code > 255:
        raise ValueError(f"{label} trigger code must be an integer from 1 to 255.")
    return code


def validate_oddball_trigger_code_policy(
    code: object,
    *,
    allow_nonstandard: bool = False,
) -> int:
    """Return an oddball marker code only when it satisfies the locked Studio policy."""

    resolved_code = validate_event_trigger_code(code, label="oddball_onset")
    if resolved_code != LOCKED_ODDBALL_TRIGGER_CODE and not allow_nonstandard:
        raise ValueError(
            "oddball_onset trigger code is locked to 55 unless "
            "allow_nonstandard_oddball_trigger_code is explicitly set."
        )
    return resolved_code


def validate_reset_trigger_code(code: object, *, label: str = "reset") -> int:
    """Return a reset marker code; BioSemi reserves 0 for reset."""

    if not isinstance(code, int) or isinstance(code, bool):
        raise TypeError(f"{label} trigger code must be the integer 0.")
    if code != 0:
        raise ValueError(f"{label} trigger code must be 0.")
    return code
