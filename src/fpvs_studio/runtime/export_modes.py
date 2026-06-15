"""Runtime export-mode constants for launch-time artifact writing."""

from __future__ import annotations

EXPORT_MODE_COMPACT = "compact"
EXPORT_MODE_FULL = "full"
VALID_EXPORT_MODES = frozenset({EXPORT_MODE_COMPACT, EXPORT_MODE_FULL})
