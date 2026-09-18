"""Bounded thumbnail decoding and fresh source intake for the visual designer."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QImageReader

from fpvs_studio.core.models import StimulusSet
from fpvs_studio.core.paths import (
    filesystem_path,
    resolve_project_relative_path,
    to_project_relative_posix,
)
from fpvs_studio.preprocessing.importer import import_fresh_stimulus_source_directory
from fpvs_studio.preprocessing.models import StimulusSetInspectionSummary


def import_designer_source(
    project_root: Path,
    condition_id: str,
    role: str,
    source_dir: Path,
) -> tuple[StimulusSetInspectionSummary, StimulusSet]:
    """Import to a fresh owned set so changing folders never merges image pools."""
    return import_fresh_stimulus_source_directory(
        source_dir=source_dir,
        project_root=project_root,
        set_id_prefix=f"{condition_id}-{role}",
        set_name=f"{condition_id} {role.upper()}",
        strict=False,
    )


def load_designer_thumbnails(
    project_root: Path,
    sources: dict[str, tuple[str, tuple[str, ...]]],
) -> dict[str, list[QImage]]:
    """Decode at most four thumbnails per pool on a worker; never create QPixmaps here."""
    images: dict[str, list[QImage]] = {}
    for role, (directory, relative_paths) in sources.items():
        limit = 4 if role == "base" else 1
        paths = [
            resolve_project_relative_path(project_root, path) for path in relative_paths[:limit]
        ]
        if not paths and directory:
            source_dir = resolve_project_relative_path(project_root, directory)
            if not source_dir.is_dir():
                raise ValueError(f"The {role.upper()} source folder is unavailable: {source_dir}")
            paths = sorted(
                path
                for path in filesystem_path(source_dir).iterdir()
                if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}
            )[:limit]
        images[role] = []
        for path in paths:
            path = resolve_project_relative_path(
                project_root, to_project_relative_posix(project_root, path)
            )
            reader = QImageReader(str(path))
            reader.setAutoTransform(True)
            size = reader.size()
            if size.isValid():
                reader.setScaledSize(
                    size.scaled(QSize(360, 240), Qt.AspectRatioMode.KeepAspectRatio)
                )
            image = reader.read()
            if image.isNull():
                raise ValueError(f"Cannot preview {path.name}: {reader.errorString()}")
            images[role].append(image)
    return images
