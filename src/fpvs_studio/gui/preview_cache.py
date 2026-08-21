"""File-aware source-pixmap caching for authoring previews."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QImage, QPixmap


@dataclass(frozen=True)
class _PixmapCacheEntry:
    signature: tuple[int, int, int]
    pixmap: QPixmap


class PreviewPixmapCache:
    """Reuse decoded preview images until their on-disk file changes."""

    def __init__(self) -> None:
        self._entries: dict[Path, _PixmapCacheEntry] = {}

    def load(self, path: Path) -> QPixmap:
        """Return the decoded image for ``path``, refreshing changed files."""

        cache_path = self._cache_path(path)
        signature = self._file_signature(cache_path)
        if signature is None:
            self._entries.pop(cache_path, None)
            return QPixmap()
        cached = self._entries.get(cache_path)
        if cached is not None and cached.signature == signature:
            return cached.pixmap
        pixmap = QPixmap.fromImage(QImage(str(cache_path)))
        self._entries[cache_path] = _PixmapCacheEntry(signature, pixmap)
        return pixmap

    def retain(self, paths: Iterable[Path]) -> None:
        """Release decoded images that are no longer part of the active preview."""

        active_paths = {self._cache_path(path) for path in paths}
        self._entries = {
            path: entry for path, entry in self._entries.items() if path in active_paths
        }

    def is_current(self, path: Path) -> bool:
        """Return whether the cached result still matches the path on disk."""

        cache_path = self._cache_path(path)
        signature = self._file_signature(cache_path)
        cached = self._entries.get(cache_path)
        if cached is None:
            return signature is None
        return cached.signature == signature

    @staticmethod
    def _cache_path(path: Path) -> Path:
        try:
            return path.resolve(strict=True)
        except (OSError, RuntimeError):
            return path.absolute()

    @staticmethod
    def _file_signature(path: Path) -> tuple[int, int, int] | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        if not path.is_file():
            return None
        return stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size
