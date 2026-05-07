"""Image normalization preprocessing tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from fpvs_studio.core.models import StimulusSet
from fpvs_studio.preprocessing.normalization import (
    ImageNormalizationError,
    normalize_stimulus_sets,
    optimize_image_folder_for_fpvs,
    scan_stimulus_sets_for_normalization,
)


def _write_image(path: Path, size: tuple[int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color=(120, 20, 40)).save(path)


def _stimulus_set(set_id: str, source_dir: str) -> StimulusSet:
    return StimulusSet(
        set_id=set_id,
        name=set_id,
        source_dir=source_dir,
        image_count=2,
    )


def test_normalization_scan_detects_uniform_images(tmp_path: Path) -> None:
    source_dir = tmp_path / "stimuli" / "original-images" / "base-set"
    _write_image(source_dir / "a.png", (64, 64))
    _write_image(source_dir / "b.png", (64, 64))

    scan = scan_stimulus_sets_for_normalization(
        project_root=tmp_path,
        stimulus_sets=[_stimulus_set("base-set", "stimuli/original-images/base-set")],
    )

    assert scan.needs_normalization is False
    assert scan.can_normalize is True
    assert scan.image_count == 2


def test_normalization_scan_detects_mixed_resolution_and_file_types(tmp_path: Path) -> None:
    source_dir = tmp_path / "stimuli" / "original-images" / "base-set"
    _write_image(source_dir / "a.png", (64, 64))
    _write_image(source_dir / "b.jpg", (128, 64))

    scan = scan_stimulus_sets_for_normalization(
        project_root=tmp_path,
        stimulus_sets=[_stimulus_set("base-set", "stimuli/original-images/base-set")],
    )

    assert scan.needs_normalization is True
    assert scan.mixed_resolution is True
    assert scan.mixed_file_type is True


def test_normalization_scan_detects_unsupported_and_empty_folders(tmp_path: Path) -> None:
    source_dir = tmp_path / "stimuli" / "original-images" / "base-set"
    source_dir.mkdir(parents=True)
    (source_dir / "notes.gif").write_bytes(b"GIF89a")

    scan = scan_stimulus_sets_for_normalization(
        project_root=tmp_path,
        stimulus_sets=[_stimulus_set("base-set", "stimuli/original-images/base-set")],
    )

    assert scan.can_normalize is False
    assert scan.sets[0].unsupported_files == ("notes.gif",)
    assert scan.sets[0].empty is True


def test_normalization_writes_square_png_outputs_and_project_relative_paths(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "stimuli" / "original-images" / "base-set"
    _write_image(source_dir / "a.jpg", (64, 96))
    _write_image(source_dir / "b.bmp", (128, 64))

    result = normalize_stimulus_sets(
        project_root=tmp_path,
        stimulus_sets=[_stimulus_set("base-set", "stimuli/original-images/base-set")],
        target_size=512,
    )

    assert result.processed_count == 2
    normalized = result.sets[0]
    assert normalized.source_dir == "stimuli/normalized-images/base-set"
    output_dir = tmp_path / normalized.source_dir
    output_paths = sorted(output_dir.iterdir())
    assert len(output_paths) == 2
    assert {path.suffix for path in output_paths} == {".png"}
    with Image.open(output_paths[0]) as image:
        assert image.size == (512, 512)


def test_normalization_supports_256_outputs(tmp_path: Path) -> None:
    source_dir = tmp_path / "stimuli" / "original-images" / "base-set"
    _write_image(source_dir / "a.png", (64, 96))

    result = normalize_stimulus_sets(
        project_root=tmp_path,
        stimulus_sets=[_stimulus_set("base-set", "stimuli/original-images/base-set")],
        target_size=256,
    )

    output_path = next((tmp_path / result.sets[0].source_dir).iterdir())
    with Image.open(output_path) as image:
        assert image.size == (256, 256)


def test_normalization_supports_1024_outputs(tmp_path: Path) -> None:
    source_dir = tmp_path / "stimuli" / "original-images" / "base-set"
    _write_image(source_dir / "a.png", (64, 96))

    result = normalize_stimulus_sets(
        project_root=tmp_path,
        stimulus_sets=[_stimulus_set("base-set", "stimuli/original-images/base-set")],
        target_size=1024,
    )

    output_path = next((tmp_path / result.sets[0].source_dir).iterdir())
    with Image.open(output_path) as image:
        assert image.size == (1024, 1024)


def test_normalization_rejects_invalid_sizes_without_writing_outputs(tmp_path: Path) -> None:
    source_dir = tmp_path / "stimuli" / "original-images" / "base-set"
    _write_image(source_dir / "a.png", (64, 96))

    with pytest.raises(ImageNormalizationError, match="256, 512, or 1024"):
        normalize_stimulus_sets(
            project_root=tmp_path,
            stimulus_sets=[_stimulus_set("base-set", "stimuli/original-images/base-set")],
            target_size=128,
        )

    assert not (tmp_path / "stimuli" / "normalized-images").exists()


@pytest.mark.parametrize("target_size", [256, 512, 1024])
def test_folder_optimizer_writes_square_png_outputs(
    tmp_path: Path,
    target_size: int,
) -> None:
    source_dir = tmp_path / "raw-images"
    output_dir = tmp_path / "raw-images-fpvs-optimized"
    _write_image(source_dir / "a.jpg", (64, 96))
    _write_image(source_dir / "b.tiff", (128, 64))
    (source_dir / "notes.txt").write_text("metadata", encoding="utf-8")

    result = optimize_image_folder_for_fpvs(
        input_dir=source_dir,
        output_dir=output_dir,
        target_size=target_size,
    )

    assert result.processed_count == 2
    assert [issue.filename for issue in result.skipped_files] == ["notes.txt"]
    assert result.failed_files == ()
    assert {path.suffix for path in result.output_files} == {".png"}
    assert (source_dir / "a.jpg").exists()
    for output_path in result.output_files:
        with Image.open(output_path) as image:
            assert image.size == (target_size, target_size)


def test_folder_optimizer_reports_existing_outputs_without_overwriting(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "raw-images"
    output_dir = tmp_path / "optimized"
    _write_image(source_dir / "a.png", (64, 96))

    first = optimize_image_folder_for_fpvs(input_dir=source_dir, output_dir=output_dir)
    second = optimize_image_folder_for_fpvs(input_dir=source_dir, output_dir=output_dir)

    assert first.processed_count == 1
    assert second.processed_count == 0
    assert second.skipped_files[0].filename == "a.png"
    assert second.skipped_files[0].reason == "Output file already exists"


def test_folder_optimizer_rejects_missing_empty_and_same_output_folders(
    tmp_path: Path,
) -> None:
    with pytest.raises(ImageNormalizationError, match="does not exist"):
        optimize_image_folder_for_fpvs(
            input_dir=tmp_path / "missing",
            output_dir=tmp_path / "out",
        )

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(ImageNormalizationError, match="does not contain any files"):
        optimize_image_folder_for_fpvs(input_dir=empty_dir, output_dir=tmp_path / "out")

    source_dir = tmp_path / "raw-images"
    _write_image(source_dir / "a.png", (64, 96))
    with pytest.raises(ImageNormalizationError, match="different from the source"):
        optimize_image_folder_for_fpvs(input_dir=source_dir, output_dir=source_dir)
