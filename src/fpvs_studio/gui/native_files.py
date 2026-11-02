"""Lazy macOS desktop file operations; callers own project-root validation and consent."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any


def _macos_framework(name: str) -> Any:
    if sys.platform != "darwin":
        raise OSError("macOS file operations require a macOS desktop.")
    try:
        return importlib.import_module(name)
    except Exception:
        raise OSError(
            "macOS desktop file services are unavailable. Install the macOS Cocoa support package."
        ) from None


def move_to_macos_trash(path: Path) -> None:
    """Move exactly this item to Trash; never substitute permanent deletion.

    Do not resolve symlinks: Trash should receive the selected directory entry,
    not a linked destination. The authorizing caller validates its active root.
    """
    if sys.platform != "darwin":
        raise OSError("macOS Trash requires a macOS desktop.")
    item = Path(path).absolute()
    if item == Path(item.anchor):
        raise OSError("A filesystem root cannot be moved to Trash.")
    item.lstat()
    foundation = _macos_framework("Foundation")
    try:
        url = foundation.NSURL.fileURLWithPath_(str(item))
        succeeded, _result_url, _error = (
            foundation.NSFileManager.defaultManager().trashItemAtURL_resultingItemURL_error_(
                url, None, None,
            )
        )
    except Exception:
        raise OSError("macOS could not confirm moving this item to Trash.") from None
    if not succeeded:
        raise OSError("macOS could not move this item to Trash.")


def open_macos_folder(path: Path) -> None:
    """Ask Finder to open a local folder using a native file URL."""
    if sys.platform != "darwin":
        raise OSError("Opening a folder with Finder requires a macOS desktop.")
    folder = Path(path).absolute()
    if not folder.is_dir():
        raise NotADirectoryError(f"Folder is unavailable: {folder}")
    foundation = _macos_framework("Foundation")
    appkit = _macos_framework("AppKit")
    try:
        url = foundation.NSURL.fileURLWithPath_(str(folder))
        succeeded = appkit.NSWorkspace.sharedWorkspace().openURL_(url)
    except Exception:
        raise OSError("macOS could not open this folder in Finder.") from None
    if not succeeded:
        raise OSError("macOS could not open this folder in Finder.")
