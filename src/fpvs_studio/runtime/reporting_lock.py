"""Serialize project report migrations and writes across runtime processes."""

from __future__ import annotations

import errno
import math
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from fpvs_studio.core.paths import resolve_project_relative_path

_REPORTING_LOCK_RELATIVE_PATH = "logs/.reporting.lock"
_LOCK_CONTENTION_ERRORS = frozenset({errno.EACCES, errno.EAGAIN, errno.EDEADLK})


@contextmanager
def project_reporting_lock(
    project_root: Path,
    *,
    timeout_seconds: float = 30.0,
    poll_interval_seconds: float = 0.05,
) -> Iterator[None]:
    """Hold a project-contained OS lock while migrating, appending or summarizing.

    Each call opens an independent handle so threads also exclude one another.
    The lock file remains in place: closing the handle, including on process death,
    releases the OS lock without leaving a stale ownership marker. This lock is
    deliberately non-reentrant; a caller already holding it must use unlocked helpers.
    """

    if not math.isfinite(timeout_seconds) or timeout_seconds < 0:
        raise ValueError("Reporting lock timeout must be finite and non-negative.")
    if not math.isfinite(poll_interval_seconds) or poll_interval_seconds <= 0:
        raise ValueError("Reporting lock polling interval must be finite and positive.")
    lock_path = resolve_project_relative_path(project_root, _REPORTING_LOCK_RELATIVE_PATH)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    with lock_path.open("a+b") as stream:
        while True:
            try:
                _acquire_lock(stream)
                break
            except OSError as exc:
                if exc.errno not in _LOCK_CONTENTION_ERRORS:
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        "Another FPVS Studio process is updating this project's reports. "
                        "The reporting lock wait timed out."
                    ) from exc
                time.sleep(min(poll_interval_seconds, remaining))
        try:
            yield
        finally:
            _release_lock(stream)


def _acquire_lock(stream: BinaryIO) -> None:
    if sys.platform == "win32":
        import msvcrt

        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_lock(stream: BinaryIO) -> None:
    if sys.platform == "win32":
        import msvcrt

        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
