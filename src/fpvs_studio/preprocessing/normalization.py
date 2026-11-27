"""Image normalization helpers for condition stimulus folders.

This module owns offline resize/format conversion for selected condition images.
It reuses the FPVS Toolbox center-crop policy while keeping Studio paths and
results structured for GUI worker integration.
"""

from __future__ import annotations

import errno
import logging
import os
import shutil
import stat
import sys
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import mkdtemp

from PIL import Image, ImageOps

from fpvs_studio.core.enums import StimulusModality
from fpvs_studio.core.models import ImageResolution, StimulusSet, validate_slug
from fpvs_studio.core.paths import (
    ProjectPathResolver,
    cache_dir,
    filesystem_path,
    stimulus_normalized_dir,
    stimulus_normalized_images_root,
)
from fpvs_studio.preprocessing.source_files import generated_png_name, source_image_directory_files

NORMALIZATION_INPUT_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"})
COMPILER_READY_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})
SUPPORTED_NORMALIZATION_SIZES = (256, 512, 1024)
_LOGGER = logging.getLogger(__name__)
_LOCK_CONTENTION_ERRORS = frozenset({errno.EACCES, errno.EAGAIN, errno.EDEADLK})


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
    non_square_resolution: bool = False
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
                self.non_square_resolution,
                self.mixed_file_type,
                self.unsupported_source_type,
                any(item.unsupported_files for item in self.sets),
                any(item.missing for item in self.sets),
                any(item.empty for item in self.sets),
            )
        )

    @property
    def needs_normalization(self) -> bool:
        return (
            self.mixed_resolution
            or self.non_square_resolution
            or self.mixed_file_type
            or self.unsupported_source_type
        )

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


@dataclass(frozen=True)
class ImageFolderOptimizationIssue:
    """One skipped or failed file from a standalone folder optimization run."""

    filename: str
    reason: str


@dataclass(frozen=True)
class ImageFolderOptimizationResult:
    """Aggregate result for a standalone folder optimization run."""

    input_dir: Path
    output_dir: Path
    target_size: int
    processed_count: int
    skipped_files: tuple[ImageFolderOptimizationIssue, ...] = ()
    failed_files: tuple[ImageFolderOptimizationIssue, ...] = ()
    output_files: tuple[Path, ...] = ()


def scan_stimulus_sets_for_normalization(
    *,
    project_root: Path,
    stimulus_sets: Iterable[StimulusSet],
) -> ImageNormalizationScan:
    """Scan selected stimulus sets for resolution and file-type consistency."""

    project_root = filesystem_path(project_root)
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
        non_square_resolution=any(
            resolution.width_px != resolution.height_px
            for scan in scans
            for resolution in scan.resolutions
        ),
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

    _validate_target_size(target_size)

    project_root = filesystem_path(filesystem_path(project_root).resolve())
    selected_sets = _unique_stimulus_sets(stimulus_sets)
    with _normalization_lock(project_root):
        return _normalize_locked(
            project_root, selected_sets, target_size, cancel_flag or (lambda: False),
        )


def _normalize_locked(
    project_root: Path,
    selected_sets: tuple[StimulusSet, ...],
    target_size: int,
    cancel: Callable[[], bool],
) -> ImageNormalizationResult:
    paths = ProjectPathResolver(project_root)
    sources = {
        stimulus_set.set_id: filesystem_path(paths.resolve(_image_source_dir(stimulus_set)))
        for stimulus_set in selected_sets
    }
    scan = scan_stimulus_sets_for_normalization(
        project_root=project_root,
        stimulus_sets=selected_sets,
    )
    if not scan.can_normalize:
        raise ImageNormalizationError(_scan_blocker_message(scan))

    output_root = stimulus_normalized_images_root(project_root)
    _normalization_entry(output_root.parent, directory=True)
    root_exists = _normalization_entry(output_root, directory=True) is not None
    output_dirs: dict[str, Path] = {}
    for stimulus_set in selected_sets:
        set_id = validate_slug(stimulus_set.set_id, field_name="set_id")
        output_dir = stimulus_normalized_dir(project_root, set_id)
        if root_exists:
            _normalization_entry(output_dir, directory=True)
        output_dirs[set_id] = output_dir
    if not root_exists:
        output_root.mkdir(parents=True, exist_ok=True)
        _require_normalization_dirs(output_root.parent, output_root)
    if not selected_sets:
        return ImageNormalizationResult(sets=(), processed_count=0)

    transaction = Path(mkdtemp(prefix=".normalize-", dir=output_root))
    transaction_dirs = (output_root.parent, output_root, transaction)
    moves: list[tuple[Path, Path]] = []
    normalized_sets: list[NormalizedStimulusSetResult] = []
    retain_transaction = False
    has_backups = False
    committed = False
    processed_count = 0
    try:
        for stimulus_set in selected_sets:
            _check_normalization_cancel(cancel)
            set_id = stimulus_set.set_id
            temp_dir = transaction / f"new-{set_id}"
            temp_dir.mkdir()
            image_paths = _normalizable_image_paths(sources[set_id])
            if not image_paths:
                raise ImageNormalizationError(
                    f"Stimulus set '{stimulus_set.name}' does not contain normalizable images."
                )
            used_names: set[str] = set()
            for image_path in image_paths:
                _check_normalization_cancel(cancel)
                destination = temp_dir / generated_png_name(
                    image_path, _compute_file_sha256(image_path), used_names
                )
                _resize_center_crop_png(
                    image_path,
                    destination,
                    target_width=target_size,
                    target_height=target_size,
                    destination_prepared=True,
                )
                processed_count += 1
            normalized_sets.append(
                NormalizedStimulusSetResult(
                    set_id=set_id,
                    source_dir=output_dirs[set_id].relative_to(project_root).as_posix(),
                    image_count=len(image_paths),
                    resolution=ImageResolution(width_px=target_size, height_px=target_size),
                )
            )

        for set_id, output_dir in output_dirs.items():
            _check_normalization_cancel(cancel)
            temp_dir = transaction / f"new-{set_id}"
            _require_normalization_dirs(*transaction_dirs, temp_dir)
            if _normalization_entry(output_dir, directory=True) is not None:
                backup_dir = transaction / f"old-{set_id}"
                _move_normalization_dir(output_dir, backup_dir)
                moves.append((output_dir, backup_dir))
                has_backups = True
            _move_normalization_dir(temp_dir, output_dir)
            moves.append((temp_dir, output_dir))
        _check_normalization_cancel(cancel)
        committed = True
    except BaseException:
        # Unwind promoted folders before restoring their predecessors.
        for previous, current in reversed(moves):
            try:
                _require_normalization_dirs(*transaction_dirs, current)
                _move_normalization_dir(current, previous)
            except Exception:
                retain_transaction = True
                _LOGGER.exception(
                    "Image normalization rollback failed; recovery retained at %s", transaction,
                )
        raise
    finally:
        if not retain_transaction:
            try:
                _require_normalization_dirs(*transaction_dirs)
                if committed and not has_backups:
                    transaction.rmdir()
                else:
                    shutil.rmtree(transaction)
            except Exception:
                _LOGGER.exception("Could not remove image normalization staging at %s", transaction)

    return ImageNormalizationResult(
        sets=tuple(normalized_sets),
        processed_count=processed_count,
    )


def _normalization_entry(path: Path, *, directory: bool) -> os.stat_result | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    reparse = getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    tag = getattr(info, "st_reparse_tag", 0)
    # Cloud placeholders can be real entries. Name-surrogate tags redirect I/O.
    if stat.S_ISLNK(info.st_mode) or tag & 0x20000000 or (reparse and not tag):
        raise ImageNormalizationError(f"Image normalization cannot use a redirected path: {path}")
    if directory and not stat.S_ISDIR(info.st_mode):
        raise NotADirectoryError(f"Image normalization requires a directory: {path}")
    if not directory and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
        raise ImageNormalizationError(f"The image normalization lock is not a private file: {path}")
    return info


@contextmanager
def _normalization_lock(project_root: Path) -> Iterator[None]:
    """Serialize normalization in a project, including readers of prior outputs."""
    # Keep the lock identity under project cache, outside portable stimulus assets.
    directory = cache_dir(project_root)
    if _normalization_entry(directory, directory=True) is None:
        directory.mkdir(parents=True, exist_ok=True)
        _require_normalization_dirs(directory)
    lock_path = directory / ".normalization.lock"
    try:
        stream = lock_path.open("x+b")
    except FileExistsError:
        _normalization_entry(lock_path, directory=False)
        stream = lock_path.open("r+b")
    with stream:
        identity = _normalization_entry(lock_path, directory=False)
        if identity is None or not os.path.samestat(os.fstat(stream.fileno()), identity):
            raise ImageNormalizationError("The image normalization lock changed before it opened.")
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno not in _LOCK_CONTENTION_ERRORS:
                raise
            raise ImageNormalizationError(
                "Another image normalization is already running in this project."
            ) from error
        yield


def _check_normalization_cancel(cancel: Callable[[], bool]) -> None:
    if cancel():
        raise ImageNormalizationError("Image normalization was cancelled.")


def _require_normalization_dirs(*directories: Path) -> None:
    for directory in directories:
        if _normalization_entry(directory, directory=True) is None:
            raise FileNotFoundError(f"Image normalization directory disappeared: {directory}")


def _move_normalization_dir(source: Path, target: Path) -> None:
    if _normalization_entry(target, directory=True) is not None:
        raise FileExistsError(f"The image normalization destination already exists: {target}")
    source.replace(target)


def optimize_image_folder_for_fpvs(
    *,
    input_dir: Path,
    output_dir: Path,
    target_size: int = 512,
    cancel_flag: Callable[[], bool] | None = None,
) -> ImageFolderOptimizationResult:
    """Create square PNG copies of supported images in one folder."""

    _validate_target_size(target_size)
    source_dir = input_dir.expanduser()
    destination_dir = output_dir.expanduser()
    if not source_dir.exists() or not source_dir.is_dir():
        raise ImageNormalizationError(f"Image source folder does not exist: {source_dir}")
    if source_dir.resolve() == destination_dir.resolve(strict=False):
        raise ImageNormalizationError("Output folder must be different from the source folder.")

    files = source_image_directory_files(source_dir, sort_key=lambda item: item.name.lower())
    if not files:
        raise ImageNormalizationError("Image source folder does not contain any files.")

    try:
        destination_dir.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        message = f"Could not create output folder: {destination_dir}"
        raise ImageNormalizationError(message) from error

    cancel = cancel_flag or (lambda: False)
    processed_count = 0
    skipped_files: list[ImageFolderOptimizationIssue] = []
    failed_files: list[ImageFolderOptimizationIssue] = []
    output_files: list[Path] = []
    used_names: set[str] = set()

    for path in files:
        if cancel():
            raise ImageNormalizationError("Image optimization was cancelled.")
        suffix = path.suffix.lower()
        if suffix not in NORMALIZATION_INPUT_SUFFIXES:
            skipped_files.append(
                ImageFolderOptimizationIssue(
                    filename=path.name,
                    reason="Unsupported image format",
                )
            )
            continue
        destination_path = destination_dir / generated_png_name(
            path, _compute_file_sha256(path), used_names
        )
        if destination_path.exists():
            skipped_files.append(
                ImageFolderOptimizationIssue(
                    filename=path.name,
                    reason="Output file already exists",
                )
            )
            continue
        try:
            _resize_center_crop_png(
                path,
                destination_path,
                target_width=target_size,
                target_height=target_size,
            )
        except Exception as error:  # pragma: no cover - covered by integration paths
            failed_files.append(
                ImageFolderOptimizationIssue(filename=path.name, reason=str(error))
            )
            continue
        processed_count += 1
        output_files.append(destination_path)

    return ImageFolderOptimizationResult(
        input_dir=source_dir,
        output_dir=destination_dir,
        target_size=target_size,
        processed_count=processed_count,
        skipped_files=tuple(skipped_files),
        failed_files=tuple(failed_files),
        output_files=tuple(output_files),
    )


def _scan_stimulus_set(
    *,
    project_root: Path,
    stimulus_set: StimulusSet,
) -> StimulusSetNormalizationScan:
    source_dir_text = _image_source_dir(stimulus_set)
    source_dir = project_root / Path(source_dir_text)
    if not source_dir.exists() or not source_dir.is_dir():
        return StimulusSetNormalizationScan(
            set_id=stimulus_set.set_id,
            source_dir=source_dir_text,
            image_count=0,
            resolutions=(),
            file_types=(),
            missing=True,
        )

    unsupported_files: list[str] = []
    resolutions: set[tuple[int, int]] = set()
    file_types: set[str] = set()
    image_count = 0
    for path in source_image_directory_files(source_dir, sort_key=lambda item: item.name.lower()):
        suffix = path.suffix.lower()
        if suffix not in NORMALIZATION_INPUT_SUFFIXES:
            unsupported_files.append(path.name)
            continue
        with Image.open(path, formats=("JPEG", "PNG", "BMP", "TIFF")) as image:
            # Keep the full decode and orientation check without copying unrotated pixels.
            ImageOps.exif_transpose(image, in_place=True)
            width, height = image.size
        resolutions.add((width, height))
        file_types.add(_canonical_file_type(suffix))
        image_count += 1

    return StimulusSetNormalizationScan(
        set_id=stimulus_set.set_id,
        source_dir=source_dir_text,
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
        for path in source_image_directory_files(
            source_dir, sort_key=lambda item: item.name.lower(),
        )
        if path.suffix.lower() in NORMALIZATION_INPUT_SUFFIXES
    ]


def _resize_center_crop_png(
    source_path: Path,
    destination_path: Path,
    *,
    target_width: int,
    target_height: int,
    destination_prepared: bool = False,
) -> None:
    if not destination_prepared:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
    image: Image.Image
    with Image.open(source_path, formats=("JPEG", "PNG", "BMP", "TIFF")) as image:
        ImageOps.exif_transpose(image, in_place=True)
        if image.mode != "RGB":
            image = image.convert("RGB")
        original_width, original_height = image.size
        scale = max(target_width / original_width, target_height / original_height)
        resized_size = (round(original_width * scale), round(original_height * scale))
        resized = image.resize(resized_size, Image.Resampling.LANCZOS)
        left = (resized_size[0] - target_width) // 2
        top = (resized_size[1] - target_height) // 2
        final = resized.crop((left, top, left + target_width, top + target_height))
        final.save(destination_path, format="PNG")


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


def _image_source_dir(stimulus_set: StimulusSet) -> str:
    if stimulus_set.modality != StimulusModality.IMAGE:
        raise ImageNormalizationError(
            f"Image normalization only supports image stimulus sets: {stimulus_set.name}."
        )
    if stimulus_set.source_dir is None:
        raise ImageNormalizationError(
            f"Image stimulus set '{stimulus_set.name}' is missing source_dir."
        )
    return stimulus_set.source_dir


def _canonical_file_type(suffix: str) -> str:
    if suffix == ".jpeg":
        return ".jpg"
    return suffix


def _validate_target_size(target_size: int) -> None:
    if target_size not in SUPPORTED_NORMALIZATION_SIZES:
        raise ImageNormalizationError(
            "Normalized image size must be 256, 512, or 1024 pixels."
        )


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
