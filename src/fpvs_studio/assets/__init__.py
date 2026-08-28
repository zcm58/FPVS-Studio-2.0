"""Paths for packaged FPVS Studio release assets."""

from __future__ import annotations

from pathlib import Path

_ASSET_ROOT = Path(__file__).resolve().parent
_BUNDLED_TASK_FONTS = {
    "Open Sans": _ASSET_ROOT / "fonts" / "OpenSans-Regular.ttf",
}


def bundled_task_font_path(font_family: str) -> Path | None:
    """Return the packaged font file for a supported non-system task font."""

    return _BUNDLED_TASK_FONTS.get(font_family)
