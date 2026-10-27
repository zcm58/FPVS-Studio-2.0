"""Shared support values for compiling project models into execution contracts."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone

SUPPORTED_SOURCE_SUFFIXES = (".jpg", ".jpeg", ".png")
SUPPORTED_DERIVED_SUFFIXES = (".png",)
RANDOM_SEED_UPPER_BOUND = 2**31
_CANCEL_CHECK: ContextVar[Callable[[], None] | None] = ContextVar(
    "compilation_cancel_check", default=None,
)


@dataclass
class _CompilationWork:
    maximum: int
    used: int = 0


_COMPILATION_WORK: ContextVar[_CompilationWork | None] = ContextVar(
    "compilation_work", default=None,
)


class CompileError(ValueError):
    """Raised when editable project state cannot be compiled into a run spec."""


@contextmanager
def compilation_cancellation(
    check: Callable[[], None] | None, *, max_work_units: int | None = None,
) -> Iterator[None]:
    """Keep cancellation and optional search work local to this invocation and thread."""
    token = _CANCEL_CHECK.set(check)
    work_token = _COMPILATION_WORK.set(
        _CompilationWork(max_work_units) if max_work_units is not None else None,
    )
    try:
        check_compilation_cancelled()
        yield
        check_compilation_cancelled()
    finally:
        _COMPILATION_WORK.reset(work_token)
        _CANCEL_CHECK.reset(token)


def check_compilation_cancelled(iteration: int = 0) -> None:
    """Check between operations and every 256 iterations of large compiler loops."""
    if iteration % 256 == 0:
        check = _CANCEL_CHECK.get()
        if check is not None:
            check()


def consume_compilation_work(units: int = 1) -> None:
    """Fail before untrusted search or repeated pool scans exceed their work budget."""
    work = _COMPILATION_WORK.get()
    if work is not None:
        work.used += units
        if work.used > work.maximum:
            raise CompileError(
                "Bundle compilation exceeds the schedule work limit "
                f"({work.maximum:,} units). Reduce repeated words or stimulus pool complexity."
            )


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


def namespaced_random_seed(random_seed: int, namespace: str) -> int:
    """Derive a stable independent seed without relying on process hash state."""

    payload = f"fpvs-studio:{random_seed}:{namespace}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
