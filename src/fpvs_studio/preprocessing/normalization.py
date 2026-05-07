"""Image normalization helpers for condition stimulus folders.

This module owns offline resize/format conversion for selected condition images.
It reuses the FPVS Toolbox center-crop policy while keeping Studio paths and
results structured for GUI worker integration.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageOps

from fpvs_studio.core.models import ImageResolution, StimulusSet
from fpvs_studio.core.paths import (
    stimulus_normalized_dir,
    stimulus_normalized_images_root,
    to_project_relative_posix,
)

NORMALIZATION_INPUT_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"})
COMPILER_READY_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})
NORMALIZED_OUTPUT_SUFFIX = ".png"
SUPPORTED_NORMALIZATION_SIZES = (256, 512)


class ImageNormalizationError(ValueError):
    """Raised when selected images cannot be normalized."""


@dataclass(frozen=True)
class StimulusSetNormalizationScan:
    """Scan facts for one selected stimulus set."""

    set_id: str
    source_dir: str
    image_count: int
    resolutions: tuple[ImageResolution, ...]
    file_types: tuple[str, ...]
    unsupported_files: tuple[str, ...] = ()
    missing: bool = False
    empty: bool = False


@dataclass(frozen=True)
class ImageNormalizationScan:
    """Aggregate normalization scan for selected condition stimulus sets."""

    sets: tuple[StimulusSetNormalizationScan, ...]
    mixed_resolution: bool = False
    mixed_file_type: bool = False
    unsupported_source_type: bool = False

    @property
    def image_count(self) -> int:
        return sum(item.image_count for item in self.sets)

    @property
    def issue_count(self) -> int:
        return sum(
            bool(value)
            for value in (
                self.mixed_resolution,
                self.mixed_file_type,
                self.unsupported_source_type,
                any(item.unsupported_files for item in self.sets),
                any(item.missing for item in self.sets),
                any(item.empty for item in self.sets),
            )
        )

    @property
    def needs_normalization(self) -> bool:
        return self.mixed_resolution or self.mixed_file_type or self.unsupported_source_type

    @property
    def can_normalize(self) -> bool:
        return not any(
            item.missing or item.empty or item.unsupported_files for item in self.sets
        )


@dataclass(frozen=True)
class NormalizedStimulusSetResult:
    """Output metadata for one normalized stimulus set."""

    set_id: str
    source_dir: str
    image_count: int
    resolution: ImageResolution


@dataclass(frozen=True)
class ImageNormalizationResult:
    """Aggregate result for a normalization run."""

    sets: tuple[NormalizedStimulusSetResult, ...]
    processed_count: int


def scan_stimulus_sets_for_normalization(
    *,
    project_root: Path,
    stimulus_sets: Iterable[StimulusSet],
) -> ImageNormalizationScan:
    """Scan selected stimulus sets for resolution and file-type consistency."""

    scans = tuple(
        _scan_stimulus_set(project_root=project_root, stimulus_set=stimulus_set)
        for stimulus_set in _unique_stimulus_sets(stimulus_sets)
    )
    all_resolutions = {
        resolution.as_tuple() for scan in scans for resolution in scan.resolutions
    }
    all_file_types = {file_type for scan in scans for file_type in scan.file_types}
    return ImageNormalizationScan(
        sets=scans,
        mixed_resolution=len(all_resolutions) > 1,
        mixed_file_type=len(all_file_types) > 1,
        unsupported_source_type=any(
            any(file_type not in COMPILER_READY_SUFFIXES for file_type in scan.file_types)
            for scan in scans
        ),
    )


def normalize_stimulus_sets(
    *,
    project_root: Path,
    stimulus_sets: Iterable[StimulusSet],
    target_size: int,
    cancel_flag: Callable[[], bool] | None = None,
) -> ImageNormalizationResult:
    """Resize selected stimulus sets to square PNG folders under the project root."""

    if target_size not in SUPPORTED_NORMALIZATION_SIZES:
        raise ImageNormalizationError("Normalized image size must be 256 or 512 pixels.")

    selected_sets = _unique_stimulus_sets(stimulus_sets)
    scan = scan_stimulus_sets_for_normalization(
        project_root=project_root,
        stimulus_sets=selected_sets,
    )
    if not scan.can_normalize:
        raise ImageNormalizationError(_scan_blocker_message(scan))

    output_root = stimulus_normalized_images_root(project_root)
    output_root.mkdir(parents=True, exist_ok=True)
    temporary_results: list[tuple[StimulusSet, Path, Path, int]] = []
    processed_count = 0
    cancel = cancel_flag or (lambda: False)

    try:
        for stimulus_set in selected_sets:
            if cancel():
                raise ImageNormalizationError("Image normalization was cancelled.")
            source_dir = project_root / Path(stimulus_set.source_dir)
            temp_dir = output_root / f".tmp-{stimulus_set.set_id}"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
            image_paths = _normalizable_image_paths(source_dir)
            if not image_paths:
                raise ImageNormalizationError(
                    f"Stimulus set '{stimulus_set.name}' does not contain normalizable images."
                )
            for image_path in image_paths:
                if cancel():
                    raise ImageNormalizationError("Image normalization was cancelled.")
                destination = temp_dir / _normalized_filename(image_path)
                _resize_center_crop_png(
                    image_path,
                    destination,
                    target_width=target_size,
                    target_height=target_size,
                )
                processed_count += 1
            temporary_results.append(
                (
                    stimulus_set,
                    temp_dir,
                    stimulus_normalized_dir(project_root, stimulus_set.set_id),
                    len(image_paths),
                )
            )

        normalized_sets: list[NormalizedStimulusSetResult] = []
        for stimulus_set, temp_dir, output_dir, image_count in temporary_results:
            if output_dir.exists():
                shutil.rmtree(output_dir)
            temp_dir.replace(output_dir)
            normalized_sets.append(
                NormalizedStimulusSetResult(
                    set_id=stimulus_set.set_id,
                    source_dir=to_project_relative_posix(project_root, output_dir),
                    image_count=image_count,
                    resolution=ImageResolution(width_px=target_size, height_px=target_size),
                )
            )
    except Exception:
        for _stimulus_set, temp_dir, _output_dir, _image_count in temporary_results:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
        raise

    return ImageNormalizationResult(
        sets=tuple(normalized_sets),
        processed_count=processed_count,
    )


def _scan_stimulus_set(
    *,
    project_root: Path,
    stimulus_set: StimulusSet,
) -> StimulusSetNormalizationScan:
    source_dir = project_root / Path(stimulus_set.source_dir)
    if not source_dir.exists() or not source_dir.is_dir():
        return StimulusSetNormalizationScan(
            set_id=stimulus_set.set_id,
            source_dir=stimulus_set.source_dir,
            image_count=0,
            resolutions=(),
            file_types=(),
            missing=True,
        )

    unsupported_files: list[str] = []
    resolutions: set[tuple[int, int]] = set()
    file_types: set[str] = set()
    image_count = 0
    for path in sorted(source_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in NORMALIZATION_INPUT_SUFFIXES:
            unsupported_files.append(path.name)
            continue
        with Image.open(path) as image:
            width, height = ImageOps.exif_transpose(image).size
        resolutions.add((width, height))
        file_types.add(_canonical_file_type(suffix))
        image_count += 1

    return StimulusSetNormalizationScan(
        set_id=stimulus_set.set_id,
        source_dir=stimulus_set.source_dir,
        image_count=image_count,
        resolutions=tuple(
            ImageResolution(width_px=width, height_px=height)
            for width, height in sorted(resolutions)
        ),
        file_types=tuple(sorted(file_types)),
        unsupported_files=tuple(sorted(unsupported_files)),
        empty=image_count == 0,
    )


def _normalizable_image_paths(source_dir: Path) -> list[Path]:
    return [
        path
        for path in sorted(source_dir.iterdir(), key=lambda item: item.name.lower())
        if path.is_file() and path.suffix.lower() in NORMALIZATION_INPUT_SUFFIXES
    ]


def _resize_center_crop_png(
    source_path: Path,
    destination_path: Path,
    *,
    target_width: int,
    target_height: int,
) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        original_width, original_height = image.size
        scale = max(target_width / original_width, target_height / original_height)
        resized_size = (round(original_width * scale), round(original_height * scale))
        resized = image.resize(resized_size, Image.Resampling.LANCZOS)
        left = (resized_size[0] - target_width) // 2
        top = (resized_size[1] - target_height) // 2
        final = resized.crop((left, top, left + target_width, top + target_height))
        final.save(destination_path, format="PNG")


def _normalized_filename(source_path: Path) -> str:
    return f"{source_path.stem}-{_compute_file_sha256(source_path)[:12]}.png"


def _compute_file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_stimulus_sets(stimulus_sets: Iterable[StimulusSet]) -> tuple[StimulusSet, ...]:
    unique: dict[str, StimulusSet] = {}
    for stimulus_set in stimulus_sets:
        unique.setdefault(stimulus_set.set_id, stimulus_set)
    return tuple(unique.values())


def _canonical_file_type(suffix: str) -> str:
    if suffix == ".jpeg":
        return ".jpg"
    return suffix


def _scan_blocker_message(scan: ImageNormalizationScan) -> str:
    missing = [item.set_id for item in scan.sets if item.missing]
    empty = [item.set_id for item in scan.sets if item.empty]
    unsupported = [
        item.set_id for item in scan.sets if item.unsupported_files
    ]
    if missing:
        return "Image normalization could not find folders for: " + ", ".join(missing)
    if empty:
        return "Image normalization found no images for: " + ", ".join(empty)
    if unsupported:
        return "Image normalization found unsupported files in: " + ", ".join(unsupported)
    return "Image normalization cannot continue with the selected folders."
