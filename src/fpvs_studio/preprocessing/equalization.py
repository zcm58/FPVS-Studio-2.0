"""Standalone, deterministic matching of grayscale image intensity and RMS contrast."""

from __future__ import annotations

import io
import json
import os
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from threading import Event, Lock

import numpy as np
from PIL import Image, ImageFile, ImageOps
from PIL import __version__ as pillow_version
from PIL.TiffImagePlugin import TiffImageFile

from fpvs_studio import __version__ as studio_version
from fpvs_studio.core.paths import filesystem_path
from fpvs_studio.preprocessing.inspection import (
    MAX_BUNDLE_IMAGE_BYTES,
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
)
from fpvs_studio.preprocessing.normalization import NORMALIZATION_INPUT_SUFFIXES

TARGET_MEAN = 128.0
REPORT_NAME = "image-equalizer-report.json"
QUANTIZATION_TOLERANCE = 0.501


class ImageEqualizationError(ValueError):
    """A batch cannot be completed without changing its scientific or file contract."""


class ImageEqualizationCancelled(ImageEqualizationError):
    """The caller cancelled processing; owned outputs have been removed."""


@dataclass(frozen=True)
class FolderPair:
    input_dir: Path
    output_dir: Path


@dataclass(frozen=True)
class ImageStatistics:
    mean: float
    standard_deviation: float
    minimum: float
    maximum: float

    @property
    def rms_contrast(self) -> float:
        return self.standard_deviation / self.mean if self.mean else 0.0


@dataclass(frozen=True)
class EqualizedImage:
    source: Path
    destination: Path
    source_sha256: str
    output_sha256: str
    before: ImageStatistics
    after: ImageStatistics


@dataclass(frozen=True)
class ImageEqualizationResult:
    images: tuple[EqualizedImage, ...]
    reports: tuple[Path, ...]
    target_standard_deviation: float
    requested_standard_deviation: float
    skipped_files: tuple[Path, ...]
    workers: int

    @property
    def contrast_reduced(self) -> bool:
        return self.target_standard_deviation < self.requested_standard_deviation - 1e-8


def _statistics(pixels: np.ndarray) -> ImageStatistics:
    return ImageStatistics(
        float(np.mean(pixels, dtype=np.float64)),
        float(np.std(pixels, dtype=np.float64)),
        float(pixels.min()),
        float(pixels.max()),
    )


def _read_grayscale(path: Path) -> tuple[np.ndarray, str]:
    """Decode one bounded, opaque 8-bit image without monitor/profile assumptions."""
    try:
        if ImageFile.LOAD_TRUNCATED_IMAGES:
            raise ImageEqualizationError("Image Equalizer requires strict image decoding.")
        with path.open("rb") as stream:
            data = stream.read(MAX_BUNDLE_IMAGE_BYTES + 1)
        if len(data) > MAX_BUNDLE_IMAGE_BYTES:
            raise ImageEqualizationError("Image exceeds the 64 MiB file limit.")
        with Image.open(io.BytesIO(data), formats=("JPEG", "PNG", "BMP", "TIFF")) as image:
            width, height = image.size
            if (max(width, height) > MAX_IMAGE_DIMENSION
                    or width * height > MAX_IMAGE_PIXELS):
                raise ImageEqualizationError("Image exceeds the 8192-axis / 16-megapixel limit.")
            if isinstance(image, TiffImageFile):
                # Seeking only the second page avoids walking every TIFF directory.
                try:
                    image.seek(1)
                except EOFError:
                    multiple_frames = False
                else:
                    multiple_frames = True
            else:
                multiple_frames = getattr(image, "n_frames", 1) != 1
            if multiple_frames:
                raise ImageEqualizationError("Use a single-frame image.")
            # Pillow can expose 16-bit RGB files as mode RGB after down-conversion.
            high_depth = image.format == "PNG" and data[24] > 8
            if isinstance(image, TiffImageFile):
                bits = image.tag_v2.get(258, (1,))
                high_depth = any(bit > 8 for bit in (bits if isinstance(bits, tuple) else (bits,)))
            if high_depth:
                raise ImageEqualizationError("Convert this image to 8-bit RGB or grayscale first.")
            if image.mode not in {"1", "L", "LA", "P", "RGB", "RGBA"}:
                raise ImageEqualizationError("Convert this image to 8-bit RGB or grayscale first.")
            image.verify()
        with Image.open(io.BytesIO(data), formats=("JPEG", "PNG", "BMP", "TIFF")) as image:
            image.load()
            if "A" in image.getbands() or "transparency" in image.info:
                if image.convert("RGBA").getchannel("A").getextrema() != (255, 255):
                    raise ImageEqualizationError(
                        "Flatten transparency onto your experiment background first."
                    )
            pixels = np.asarray(ImageOps.exif_transpose(image).convert("L"), dtype=np.float32)
        return pixels, sha256(data).hexdigest()
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise ImageEqualizationError(f"{path.name}: {error}") from error


def _overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def _preflight(
    pairs: Iterable[FolderPair],
) -> tuple[tuple[FolderPair, ...], list[tuple[Path, Path]], tuple[Path, ...]]:
    resolved = tuple(FolderPair(
        filesystem_path(pair.input_dir).resolve(),
        filesystem_path(pair.output_dir).resolve(),
    ) for pair in pairs)
    if not resolved:
        raise ImageEqualizationError("Add at least one input/output folder pair.")
    inputs = [pair.input_dir for pair in resolved]
    outputs = [pair.output_dir for pair in resolved]
    if len(set(inputs)) != len(inputs):
        raise ImageEqualizationError("Each input folder may appear only once.")
    if any(_overlap(source, output) for source in inputs for output in outputs):
        raise ImageEqualizationError("Output folders must be separate from all input folders.")
    if any(_overlap(output, other) for index, output in enumerate(outputs)
           for other in outputs[index + 1:]):
        raise ImageEqualizationError("Output folders must be separate from each other.")
    jobs: list[tuple[Path, Path]] = []
    skipped: list[Path] = []
    for pair in resolved:
        if not pair.input_dir.is_dir():
            raise ImageEqualizationError(f"Input folder is missing: {pair.input_dir}")
        if pair.output_dir.exists() and (
            not pair.output_dir.is_dir() or any(pair.output_dir.iterdir())
        ):
            raise ImageEqualizationError(f"Choose a new or empty output folder: {pair.output_dir}")
        sources = []
        for path in sorted(pair.input_dir.iterdir(), key=lambda p: (p.name.casefold(), p.name)):
            if path.is_file() and path.suffix.lower() in NORMALIZATION_INPUT_SUFFIXES:
                sources.append(path)
            else:
                skipped.append(path)
        if not sources:
            raise ImageEqualizationError(f"No supported images in: {pair.input_dir}")
        names: set[str] = set()
        for source in sources:
            name = f"{source.stem}.png"
            if name.casefold() in names:
                raise ImageEqualizationError(
                    f"Duplicate output name '{name}' in {pair.input_dir}. Rename a source first."
                )
            names.add(name.casefold())
            jobs.append((source, pair.output_dir / name))
    return resolved, jobs, tuple(skipped)


def equalize_image_folders(
    pairs: Iterable[FolderPair],
    *,
    cancel_flag: Callable[[], bool] | None = None,
    progress: Callable[[str], None] | None = None,
    max_workers: int | None = None,
) -> ImageEqualizationResult:
    """Match every image to one batch target; never overwrite existing files.

    Input folders are nonrecursive. Images are analyzed before any outputs are
    written. Up to four threads decode/transform independently; only scalar stats
    survive the first pass. A failed/cancelled batch removes only files it created.
    Empty output directories may remain. Reports are written only after all PNGs
    have been decoded again and checked within 0.501 code levels of the targets.
    """
    selected, jobs, skipped = _preflight(pairs)
    if max_workers is not None and max_workers < 1:
        raise ImageEqualizationError("Worker count must be positive.")
    workers = min(4, max_workers or os.cpu_count() or 1, len(jobs))
    stop = Event()
    created: list[Path] = []
    created_lock = Lock()

    def check_cancel() -> None:
        if stop.is_set() or (cancel_flag is not None and cancel_flag()):
            raise ImageEqualizationCancelled("Equalization cancelled. No batch outputs retained.")

    def announce(message: str) -> None:
        if progress is not None:
            progress(message)

    def analyze(job: tuple[Path, Path]) -> tuple[ImageStatistics, str]:
        check_cancel()
        pixels, digest = _read_grayscale(job[0])
        stats = _statistics(pixels)
        if stats.standard_deviation == 0:
            raise ImageEqualizationError(
                f"{job[0].name}: Flat images cannot be contrast-matched. Remove this image."
            )
        return stats, digest

    def write_new(path: Path, data: bytes) -> None:
        check_cancel()
        with path.open("xb") as stream:
            with created_lock:
                created.append(path)
            stream.write(data)

    announce(f"Analyzing {len(jobs)} images…")
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="image-equalizer") as pool:
        try:
            measurements = []
            for index, measured in enumerate(pool.map(analyze, jobs), 1):
                measurements.append(measured)
                check_cancel()
                announce(f"Analyzed {index} of {len(jobs)} images…")
        except Exception:
            stop.set()
            raise

    requested_std = float(np.median([stats.standard_deviation for stats, _ in measurements]))
    feasible_limits = [min(
        TARGET_MEAN * stats.standard_deviation / (stats.mean - stats.minimum),
        (255.0 - TARGET_MEAN) * stats.standard_deviation / (stats.maximum - stats.mean),
    ) for stats, _ in measurements]
    target_std = min(requested_std, *feasible_limits)

    def transform(index: int) -> EqualizedImage:
        check_cancel()
        source, destination = jobs[index]
        before, digest = measurements[index]
        pixels, current_digest = _read_grayscale(source)
        if current_digest != digest:
            raise ImageEqualizationError(f"Source changed during processing: {source}")
        pixels -= before.mean
        pixels *= target_std / before.standard_deviation
        pixels += TARGET_MEAN
        # The analytical bound prevents clipping. Round into the private float32 array.
        np.rint(pixels, out=pixels)
        if pixels.min() < 0 or pixels.max() > 255:
            raise ImageEqualizationError(f"Calculated intensity is out of range: {source}")
        buffer = io.BytesIO()
        Image.fromarray(pixels.astype(np.uint8)).save(buffer, format="PNG")
        write_new(destination, buffer.getvalue())
        saved_pixels, output_digest = _read_grayscale(destination)
        after = _statistics(saved_pixels)
        if (abs(after.mean - TARGET_MEAN) > QUANTIZATION_TOLERANCE
                or abs(after.standard_deviation - target_std) > QUANTIZATION_TOLERANCE
                or after.standard_deviation == 0):
            raise ImageEqualizationError(
                f"{source.name}: 8-bit output cannot meet the matching target. "
                "Review images with very low contrast or isolated extreme pixels."
            )
        return EqualizedImage(source, destination, digest, output_digest, before, after)

    try:
        check_cancel()
        for pair in selected:
            pair.output_dir.mkdir(parents=True, exist_ok=True)
            if any(pair.output_dir.iterdir()):
                raise ImageEqualizationError(f"Output folder is no longer empty: {pair.output_dir}")
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="image-equalizer") as pool:
            try:
                completed = []
                for index, image_result in enumerate(pool.map(transform, range(len(jobs))), 1):
                    completed.append(image_result)
                    check_cancel()
                    announce(f"Equalized {index} of {len(jobs)} images…")
            except Exception:
                stop.set()
                raise
        reports = tuple(pair.output_dir / REPORT_NAME for pair in selected)
        result = ImageEqualizationResult(
            tuple(completed), reports, target_std, requested_std, skipped, workers,
        )
        report = {
            "algorithm": "studio-grayscale-mean-rms-v1",
            "software": {"studio": studio_version, "pillow": pillow_version,
                         "numpy": np.__version__},
            "grayscale": "Pillow L: 0.299 R + 0.587 G + 0.114 B, rounded to 8-bit",
            "domain": "stored code values; no ICC transform, gamma correction or photometry",
            "region": "whole image, after EXIF orientation; no cropping or resizing",
            "target_mean": TARGET_MEAN,
            "target_standard_deviation": target_std,
            "target_rms_contrast": target_std / TARGET_MEAN,
            "rms_definition": "population standard deviation / mean",
            "quantization_tolerance_code_levels": QUANTIZATION_TOLERANCE,
            "requested_standard_deviation": requested_std,
            "contrast_reduced_to_avoid_clipping": result.contrast_reduced,
            "limiting_sources": [str(jobs[i][0]) for i, limit in enumerate(feasible_limits)
                                 if abs(limit - target_std) < 1e-8],
            "folder_pairs": [asdict(pair) for pair in selected],
            "skipped_entries": skipped,
            "workers": workers,
            "images": [dict(asdict(item), output_rms_contrast=item.after.rms_contrast)
                       for item in completed],
        }
        data = (json.dumps(report, indent=2, default=str) + "\n").encode("utf-8")
        for path in reports:
            write_new(path, data)
        check_cancel()
        return result
    except Exception as error:
        cleanup_errors = []
        for path in reversed(created):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                cleanup_errors.append(str(path))
        if cleanup_errors:
            raise ImageEqualizationError(
                f"{error}\nCould not remove incomplete outputs: " + ", ".join(cleanup_errors)
            ) from error
        raise
