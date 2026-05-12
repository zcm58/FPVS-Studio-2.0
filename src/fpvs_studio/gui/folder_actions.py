"""Small GUI helpers for user-selected filesystem locations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def open_folder(path: str | Path) -> bool:
    """Open a folder in the system file manager."""

    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path))))
