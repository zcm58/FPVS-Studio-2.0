"""In-memory stand-in for the Qt settings operations used by StudioController."""

from copy import copy
from unittest.mock import Mock


class MemorySettings:
    def __init__(self, values=None, *, sync_failures=0):
        self.values = dict(values or {})
        self.mutations = []
        self.sync_calls = 0
        self.sync_failures = sync_failures
        self._status = 0
        self._fallbacks = True
        self._atomic = True
        self._group = ""
        self.constructor = Mock(side_effect=self._new_writer)
        self.constructor.Status.NoError = 0

    def _new_writer(self, filename, settings_format):
        assert (filename, settings_format) == (self.fileName(), self.format())
        writer = copy(self)
        writer._status = 0
        return writer

    def value(self, key, default=None, **_kwargs):
        return self.values.get(key, default)

    def contains(self, key):
        return key in self.values

    def setValue(self, key, value):  # noqa: N802
        self.values[key] = value
        self.mutations.append((key, value))

    def remove(self, key):
        self.values.pop(key, None)
        self.mutations.append((key, None))

    def sync(self):
        self.sync_calls += 1
        if self.sync_calls <= self.sync_failures:
            self._status = 1  # Qt retains the first error for the lifetime of this handle.

    def status(self):
        return self._status

    def fallbacksEnabled(self):  # noqa: N802
        return self._fallbacks

    def setFallbacksEnabled(self, enabled):  # noqa: N802
        self._fallbacks = enabled

    def fileName(self):  # noqa: N802
        return "memory.ini"

    def format(self):
        return "ini"

    def group(self):
        return self._group

    def beginGroup(self, group):  # noqa: N802
        self._group = group

    def isAtomicSyncRequired(self):  # noqa: N802
        return self._atomic

    def setAtomicSyncRequired(self, required):  # noqa: N802
        self._atomic = required
