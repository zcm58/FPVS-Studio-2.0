"""Track actual outbound Studio exports across worker threads."""

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock

_lock = Lock()
_active: Counter[str] = Counter()


def active_website_exports() -> tuple[str, ...]:
    with _lock:
        return tuple(sorted(_active))


@contextmanager
def website_export(label: str) -> Iterator[None]:
    with _lock:
        _active[label] += 1
    try:
        yield
    finally:
        with _lock:
            _active[label] -= 1
            if not _active[label]:
                del _active[label]
