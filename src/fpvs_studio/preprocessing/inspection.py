"""Image inspection helpers for preprocessing source directories. It measures hashes,
formats, and resolutions so stimulus-set summaries and manifest records stay
reproducible before compilation. The module owns source-asset facts only; it does not
choose session order, derive RunSpec timing, or render anything."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from PIL import Image

from fpvs_studio.core.models import ImageResolution, StimulusSet
from fpvs_studio.preprocessing.models import InspectionFileRecord, StimulusSetInspectionSummary

SUPPORTED_SOURCE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"})


class ImageInspectionError(ValueError):
    """Raised when a stimulus source directory fails inspection."""


def compute_file_sha256(path: Path) -> str:
    """Compute a hex SHA-256 digest for a file."""

    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_source_directory(
    source_dir: Path,
    *,
    relative_prefix: str = ".",
    strict: bool = True,
) -> StimulusSetInspectionSummary:
    """Inspect source images, enforcing supported extensions and uniform resolution."""

    if not source_dir.exists():
        raise ImageInspectionError(f"Source directory does not exist: {source_dir}")
    if not source_dir.is_dir():
        raise ImageInspectionError(f"Source path is not a directory: {source_dir}")

    files = sorted(path for path in source_dir.iterdir() if path.is_file())
    unsupported_files = [
        path.name for path in files if path.suffix.lower() not in SUPPORTED_SOURCE_SUFFIXES
    ]
    supported_files = [path for path in files if path.suffix.lower() in SUPPORTED_SOURCE_SUFFIXES]

    if strict and unsupported_files:
        raise ImageInspectionError(
            "Unsupported source image files found: " + ", ".join(sorted(unsupported_files))
        )
    if not supported_files:
        raise ImageInspectionError(
            f"Source directory '{source_dir}' does not contain any supported images."
        )

    inspected_files: list[InspectionFileRecord] = []
    resolutions: set[tuple[int, int]] = set()

    for path in supported_files:
        with Image.open(path) as image:
            width, height = image.size
        resolution = ImageResolution(width_px=width, height_px=height)
        resolutions.add(resolution.as_tuple())
        relative_path = (Path(relative_prefix) / path.name).as_posix()
        inspected_files.append(
            InspectionFileRecord(
                relative_path=relative_path,
                sha256=compute_file_sha256(path),
                source_format=path.suffix.lower().lstrip("."),
                resolution=resolution,
            )
        )

    mixed_resolution = len(resolutions) > 1
    if strict and mixed_resolution:
        raise ImageInspectionError("Stimulus sets must contain images with identical resolution.")

    first_resolution = (
        inspected_files[0].resolution if inspected_files and not mixed_resolution else None
    )
    return StimulusSetInspectionSummary(
        source_dir=Path(relative_prefix).as_posix(),
        image_count=len(inspected_files),
        resolution=first_resolution,
        mixed_resolution=mixed_resolution,
        unsupported_files=sorted(unsupported_files),
        files=inspected_files,
    )


def summary_to_stimulus_set(
    *,
    set_id: str,
    name: str,
    summary: StimulusSetInspectionSummary,
) -> StimulusSet:
    """Convert an inspection summary into a project stimulus-set model."""

    return StimulusSet(
        set_id=set_id,
        name=name,
        source_dir=summary.source_dir,
        resolution=summary.resolution,
        image_count=summary.image_count,
    )
