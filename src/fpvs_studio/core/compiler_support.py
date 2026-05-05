"""Shared support values for compiling project models into execution contracts."""

from __future__ import annotations

from datetime import datetime, timezone

SUPPORTED_SOURCE_SUFFIXES = (".jpg", ".jpeg", ".png")
SUPPORTED_DERIVED_SUFFIXES = (".png",)
RANDOM_SEED_UPPER_BOUND = 2**31


class CompileError(ValueError):
    """Raised when editable project state cannot be compiled into a run spec."""


def make_run_id(condition_id: str, now: datetime | None = None) -> str:
    """Create a compact condition-run id."""

    timestamp = now or datetime.now(timezone.utc)
    return f"{condition_id}-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"


def make_session_id(_project_id: str, random_seed: int) -> str:
    """Create a deterministic, path-friendly session identifier."""

    return f"session-{random_seed:010d}"


def make_session_run_id(
    *,
    global_order_index: int,
    condition_id: str,
) -> str:
    """Create a deterministic, path-friendly run id for one session entry."""

    return f"run-{global_order_index + 1:03d}-{condition_id}"


def color_to_string(value: str | tuple[int, int, int]) -> str:
    """Normalize persisted color values into a runtime-friendly string form."""

    if isinstance(value, str):
        return value
    return f"rgb({value[0]},{value[1]},{value[2]})"
