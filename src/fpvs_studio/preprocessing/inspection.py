"""Image inspection helpers for preprocessing source directories. It measures hashes,
formats, and resolutions so stimulus-set summaries and manifest records stay
reproducible before compilation. The module owns source-asset facts only; it does not
choose session order, derive RunSpec timing, or render anything."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageFile

from fpvs_studio.core.models import ImageResolution, StimulusSet
from fpvs_studio.core.paths import filesystem_path
from fpvs_studio.preprocessing.models import InspectionFileRecord, StimulusSetInspectionSummary

SUPPORTED_SOURCE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"})
_STIMULUS_FORMATS = {
    ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG",
    ".bmp": "BMP", ".tif": "TIFF", ".tiff": "TIFF",
}
MAX_IMAGE_DIMENSION = 8192
MAX_IMAGE_PIXELS = 16_777_216
MAX_IMAGE_DECODED_BYTES = 64 * 1024 * 1024
MAX_BUNDLE_IMAGE_BYTES = 64 * 1024 * 1024


class ImageInspectionError(ValueError):
    """Raised when a stimulus image or source directory fails inspection."""


@contextmanager
def _image_errors(path: Path) -> Iterator[None]:
    try:
        yield
    except ImageInspectionError:
        raise
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as error:
        raise ImageInspectionError(
            f"Image is unreadable, corrupt, truncated, or unsafe: {path.name}"
        ) from error


def validate_image_files(
    paths: Iterable[Path], *, cancel_check: Callable[[], None] | None = None,
) -> None:
    """Fully check bounded, single-frame source images without changing their bytes.

    Restrict the decoders before opening untrusted data, then verify the structure
    and decode all pixels. Four bytes per pixel conservatively bounds Pillow's
    pixel buffer for PNG/JPEG/BMP/TIFF; decoder overhead is additional. Cancellation
    is checked between files and decoding phases, not inside Pillow's C decoder.
    This validates image content, not malware or an operating-system sandbox.
    """
    if cancel_check is not None:
        cancel_check()
    if ImageFile.LOAD_TRUNCATED_IMAGES:
        raise ImageInspectionError("Image validation requires strict truncated-image handling.")
    for source in paths:
        if cancel_check is not None:
            cancel_check()
        path = filesystem_path(source)
        expected_format = _STIMULUS_FORMATS.get(path.suffix.lower())
        if expected_format is None:
            raise ImageInspectionError(f"Unsupported stimulus image extension: {path.name}")
        with _image_errors(path):
            handle = path.open("rb")
        with handle:
            with _image_errors(path):
                size = os.fstat(handle.fileno()).st_size
                if not 0 < size <= MAX_BUNDLE_IMAGE_BYTES:
                    raise ImageInspectionError(
                        f"Image exceeds the encoded file size limit or is empty: {path.name}"
                    )
                with Image.open(handle, formats=[expected_format]) as image:
                    if image.format != expected_format:
                        raise ImageInspectionError(
                            f"Image content does not match its extension: {path.name}"
                        )
                    width, height = image.size
                    if not (0 < width <= MAX_IMAGE_DIMENSION and 0 < height <= MAX_IMAGE_DIMENSION):
                        raise ImageInspectionError(
                            f"Image dimensions exceed the {MAX_IMAGE_DIMENSION}-pixel limit: "
                            f"{path.name}"
                        )
                    pixels = width * height
                    if pixels > MAX_IMAGE_PIXELS or pixels * 4 > MAX_IMAGE_DECODED_BYTES:
                        raise ImageInspectionError(
                            f"Image exceeds the pixel or decoded-memory limit: {path.name}"
                        )
                    if expected_format == "TIFF":
                        # TIFF n_frames walks every IFD; reject as soon as page two exists.
                        try:
                            image.seek(1)
                        except EOFError:
                            multiple_frames = False
                        else:
                            multiple_frames = True
                    else:
                        multiple_frames = getattr(image, "n_frames", 1) != 1
                    if multiple_frames:
                        raise ImageInspectionError(
                            f"Animated or multipage stimulus images are unsupported: {path.name}"
                        )
                    image.verify()
            if cancel_check is not None:
                cancel_check()
            with _image_errors(path):
                handle.seek(0)
                with Image.open(handle, formats=[expected_format]) as image:
                    image.load()
            if cancel_check is not None:
                cancel_check()


def compute_file_sha256(path: Path) -> str:
    """Compute a hex SHA-256 digest for a file."""

    digest = sha256()
    with filesystem_path(path).open("rb") as handle:
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

    source_dir = filesystem_path(source_dir)
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
