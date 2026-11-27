"""Image normalization preprocessing tests."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from PIL import Image

from fpvs_studio.core.models import StimulusSet
from fpvs_studio.preprocessing import normalization
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


def _file_contents(folder: Path) -> dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes()
        for path in folder.rglob("*")
        if path.is_file()
    }


def _redirect_directory(link: Path, target: Path) -> None:
    try:
        if os.name == "nt":
            from _winapi import CreateJunction

            CreateJunction(str(target), str(link))
        else:
            link.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Directory redirection is unavailable: {error}")


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


def test_normalization_scan_detects_uniform_non_square_images(tmp_path: Path) -> None:
    source_dir = tmp_path / "stimuli" / "original-images" / "base-set"
    _write_image(source_dir / "a.png", (128, 96))
    _write_image(source_dir / "b.png", (128, 96))

    scan = scan_stimulus_sets_for_normalization(
        project_root=tmp_path,
        stimulus_sets=[_stimulus_set("base-set", "stimuli/original-images/base-set")],
    )

    assert scan.needs_normalization is True
    assert scan.non_square_resolution is True
    assert scan.mixed_resolution is False


def test_normalization_scan_uses_exif_oriented_dimensions(tmp_path: Path) -> None:
    source_dir = tmp_path / "images"
    _write_image(source_dir / "landscape.jpg", (96, 64))
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (64, 96)).save(source_dir / "portrait.jpg", exif=exif)

    scan = scan_stimulus_sets_for_normalization(
        project_root=tmp_path,
        stimulus_sets=[_stimulus_set("base-set", "images")],
    )

    assert scan.image_count == 2
    assert scan.mixed_resolution is False
    assert [resolution.as_tuple() for resolution in scan.sets[0].resolutions] == [(96, 64)]


def test_normalization_scan_rejects_truncated_pixel_data(tmp_path: Path) -> None:
    source_dir = tmp_path / "images"
    path = source_dir / "truncated.jpg"
    _write_image(path, (64, 96))
    path.write_bytes(path.read_bytes()[:-25])
    with Image.open(path) as image:
        assert image.size == (64, 96)

    with pytest.raises(OSError, match="image file is truncated"):
        scan_stimulus_sets_for_normalization(
            project_root=tmp_path,
            stimulus_sets=[_stimulus_set("base-set", "images")],
        )


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


@pytest.mark.parametrize("metadata_name,metadata", [
    (".DS_Store", b"\x00\x00\x00\x01Bud1"),
    ("._a.jpg", b"\x00\x05\x16\x07\x00\x02\x00\x00" + bytes(18)),
])
def test_normalization_ignores_finder_metadata_and_retains_authored_dot_images(
    tmp_path: Path, metadata_name: str, metadata: bytes,
) -> None:
    source_dir = tmp_path / "stimuli/original-images/base-set"
    _write_image(source_dir / "a.jpg", (64, 96))
    _write_image(source_dir / "._authored.png", (64, 96))
    (source_dir / metadata_name).write_bytes(metadata)
    original = {path.name: path.read_bytes() for path in source_dir.iterdir()}
    stimulus_sets = [_stimulus_set("base-set", "stimuli/original-images/base-set")]

    scan = scan_stimulus_sets_for_normalization(
        project_root=tmp_path, stimulus_sets=stimulus_sets,
    )
    assert scan.can_normalize is True
    assert scan.image_count == 2
    assert scan.sets[0].unsupported_files == ()
    result = normalize_stimulus_sets(
        project_root=tmp_path, stimulus_sets=stimulus_sets, target_size=256,
    )
    assert result.processed_count == 2
    assert result.sets[0].image_count == 2
    outputs = list((tmp_path / result.sets[0].source_dir).iterdir())
    assert len(outputs) == 2
    assert any(path.name.startswith("._authored-") for path in outputs)
    assert {path.name: path.read_bytes() for path in source_dir.iterdir()} == original


def test_folder_optimizer_ignores_finder_metadata_without_reporting_image_failures(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "raw-images"
    _write_image(source_dir / "a.jpg", (64, 96))
    _write_image(source_dir / "._authored.png", (64, 96))
    (source_dir / ".DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1")
    (source_dir / "._a.jpg").write_bytes(
        b"\x00\x05\x16\x07\x00\x02\x00\x00" + bytes(18),
    )

    result = optimize_image_folder_for_fpvs(
        input_dir=source_dir, output_dir=tmp_path / "optimized", target_size=256,
    )

    assert result.processed_count == 2
    assert result.failed_files == ()
    assert result.skipped_files == ()
    assert result.output_files[0].name.startswith("._authored-")
    assert result.output_files[1].name.startswith("a-")


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


@pytest.mark.parametrize(
    ("interruption", "converted_count"), [("cancel", 1), ("cancel", 2), ("decode", 1), ("save", 1)],
)
def test_normalization_cleans_interrupted_staging_and_preserves_previous_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interruption: str, converted_count: int,
) -> None:
    source = tmp_path / "originals"
    _write_image(source / "a.jpg", (64, 96))
    _write_image(source / "b.png", (96, 64))
    source_bytes = _file_contents(source)
    output_root = tmp_path / "stimuli/normalized-images"
    previous = output_root / "base"
    _write_image(previous / "existing.png", (256, 256))
    unrelated = output_root / ".tmp-base"
    unrelated.mkdir()
    (unrelated / "keep.txt").write_bytes(b"unrelated staging directory")
    previous_bytes = _file_contents(previous)
    sets = [_stimulus_set("base", "originals")]
    converted: list[Path] = []
    original_resize = normalization._resize_center_crop_png
    conversion_error = OSError(f"simulated {interruption} failure")

    def convert_with_possible_failure(image_path: Path, destination: Path, **sizes: int) -> None:
        if interruption != "cancel" and converted:
            if interruption == "save":
                destination.write_bytes(b"partially written PNG")
            raise conversion_error
        original_resize(image_path, destination, **sizes)
        assert destination.is_file()
        converted.append(destination)

    with monkeypatch.context() as injected:
        injected.setattr(normalization, "_resize_center_crop_png", convert_with_possible_failure)
        if interruption == "cancel":
            with pytest.raises(ImageNormalizationError, match="cancelled"):
                normalize_stimulus_sets(
                    project_root=tmp_path, stimulus_sets=sets, target_size=512,
                    cancel_flag=lambda: len(converted) == converted_count,
                )
        else:
            with pytest.raises(OSError) as error:
                normalize_stimulus_sets(project_root=tmp_path, stimulus_sets=sets, target_size=512)
            assert error.value is conversion_error

    assert len(converted) == converted_count
    assert {path.name for path in output_root.iterdir() if path.is_dir()} == {"base", ".tmp-base"}
    assert _file_contents(previous) == previous_bytes
    assert _file_contents(unrelated) == {"keep.txt": b"unrelated staging directory"}
    assert _file_contents(source) == source_bytes

    first = normalize_stimulus_sets(project_root=tmp_path, stimulus_sets=sets, target_size=512)
    first_bytes = _file_contents(previous)
    repeated = normalize_stimulus_sets(project_root=tmp_path, stimulus_sets=sets, target_size=512)
    assert first == repeated
    assert first.processed_count == 2
    assert first.sets[0].source_dir == "stimuli/normalized-images/base"
    assert "existing.png" not in first_bytes
    assert _file_contents(previous) == first_bytes
    assert _file_contents(source) == source_bytes


@pytest.mark.parametrize("deny_restore", [False, True])
def test_normalization_unwinds_partial_promotion_and_keeps_unrestored_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, deny_restore: bool,
) -> None:
    set_ids = ("first", "new-set", "last")
    for set_id in set_ids:
        _write_image(tmp_path / f"originals/{set_id}/source.png", (64, 96))
    sets = [_stimulus_set(set_id, f"originals/{set_id}") for set_id in set_ids]
    output_root = tmp_path / "stimuli/normalized-images"
    first = output_root / "first"
    last = output_root / "last"
    _write_image(first / "previous-first.png", (256, 256))
    _write_image(last / "previous-last.png", (512, 512))
    first_bytes = _file_contents(first)
    last_bytes = _file_contents(last)
    source_bytes = _file_contents(tmp_path / "originals")
    original_replace = Path.replace
    promotion_error = PermissionError("simulated last-set promotion failure")
    failures: list[str] = []

    def replace_with_failure(path: Path, target: Path) -> Path:
        destination = Path(target)
        if path.name == "new-last" and destination.name == "last":
            assert first.is_dir() and _file_contents(first) != first_bytes
            assert (output_root / "new-set").is_dir()
            assert not last.exists()
            failures.append("promote")
            raise promotion_error
        if deny_restore and path.name == "old-first" and destination.name == "first":
            failures.append("restore")
            raise PermissionError("simulated first-set restoration failure")
        return original_replace(path, target)

    with monkeypatch.context() as injected:
        injected.setattr(Path, "replace", replace_with_failure)
        with pytest.raises(PermissionError) as error:
            normalize_stimulus_sets(project_root=tmp_path, stimulus_sets=sets, target_size=512)

    assert error.value is promotion_error
    assert failures == (["promote", "restore"] if deny_restore else ["promote"])
    assert not (output_root / "new-set").exists()
    assert _file_contents(last) == last_bytes
    assert _file_contents(tmp_path / "originals") == source_bytes
    if deny_restore:
        retained = list(output_root.rglob("previous-first.png"))
        assert len(retained) == 1
        assert retained[0].parent != first
        assert _file_contents(retained[0].parent) == first_bytes
    else:
        assert {path.name for path in output_root.iterdir() if path.is_dir()} == {"first", "last"}
        assert _file_contents(first) == first_bytes
        result = normalize_stimulus_sets(project_root=tmp_path, stimulus_sets=sets, target_size=512)
        assert tuple(item.set_id for item in result.sets) == set_ids
        assert result.processed_count == 3
        assert _file_contents(tmp_path / "originals") == source_bytes


def test_normalization_rejects_overlapping_calls_for_the_same_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_image(tmp_path / "source/a.png", (64, 96))
    sets = [_stimulus_set("base", "source")]
    entered, resume = Event(), Event()
    original_resize = normalization._resize_center_crop_png

    def wait_to_resize(image_path: Path, destination: Path, **sizes: int) -> None:
        entered.set()
        assert resume.wait(10), "First normalization did not resume"
        original_resize(image_path, destination, **sizes)

    monkeypatch.setattr(normalization, "_resize_center_crop_png", wait_to_resize)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            normalize_stimulus_sets, project_root=tmp_path, stimulus_sets=sets, target_size=256,
        )
        try:
            assert entered.wait(5), "First normalization did not reach staging"
            overlapping = executor.submit(
                normalize_stimulus_sets, project_root=tmp_path, stimulus_sets=sets, target_size=512,
            )
            with pytest.raises(ImageNormalizationError, match="already running in this project"):
                overlapping.result(timeout=5)
        finally:
            resume.set()
        result = first.result(timeout=5)

    output_dir = tmp_path / result.sets[0].source_dir
    assert result.processed_count == 1
    with Image.open(next(output_dir.iterdir())) as image:
        assert image.size == (256, 256)


def test_normalization_can_reuse_its_existing_output_as_the_source(tmp_path: Path) -> None:
    source = tmp_path / "originals"
    _write_image(source / "a.jpg", (64, 96))
    source_bytes = _file_contents(source)
    initial = normalize_stimulus_sets(
        project_root=tmp_path, stimulus_sets=[_stimulus_set("base", "originals")], target_size=256,
    )
    normalized_path = initial.sets[0].source_dir

    resized = normalize_stimulus_sets(
        project_root=tmp_path, stimulus_sets=[_stimulus_set("base", normalized_path)],
        target_size=512,
    )

    assert resized.sets[0].source_dir == normalized_path
    assert resized.processed_count == 1
    (output_file,) = (tmp_path / normalized_path).iterdir()
    with Image.open(output_file) as image:
        assert image.size == (512, 512)
    assert _file_contents(source) == source_bytes


def test_normalization_accepts_a_source_redirect_within_the_project(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _write_image(source / "a.jpg", (64, 96))
    source_bytes = _file_contents(source)
    _redirect_directory(tmp_path / "source-link", source)

    result = normalize_stimulus_sets(
        project_root=tmp_path, stimulus_sets=[_stimulus_set("base", "source-link")],
        target_size=256,
    )

    assert result.processed_count == 1
    assert result.sets[0].source_dir == "stimuli/normalized-images/base"
    assert _file_contents(source) == source_bytes


@pytest.mark.parametrize("redirected_path", ["source", "output-root", "destination"])
def test_normalization_rejects_redirected_paths_outside_the_project(
    tmp_path: Path, redirected_path: str,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    outside = tmp_path / "outside"
    _write_image(outside / "keep.png", (64, 96))
    outside_bytes = _file_contents(outside)
    links = {
        "source": project_root / "source",
        "output-root": project_root / "stimuli/normalized-images",
        "destination": project_root / "stimuli/normalized-images/base",
    }
    link = links[redirected_path]
    if redirected_path != "source":
        _write_image(project_root / "source/a.png", (64, 96))
    link.parent.mkdir(parents=True, exist_ok=True)
    _redirect_directory(link, outside)

    message = "escapes the project root" if redirected_path == "source" else "redirected path"
    with pytest.raises(ValueError, match=message):
        normalize_stimulus_sets(
            project_root=project_root, stimulus_sets=[_stimulus_set("base", "source")],
            target_size=256,
        )

    assert link.resolve() == outside.resolve()
    assert _file_contents(outside) == outside_bytes


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


def test_same_image_with_two_valid_extensions_retains_both_pool_entries(tmp_path: Path) -> None:
    source = tmp_path / "raw-images"
    _write_image(source / "photo.jpg", (64, 96))
    (source / "photo.jpeg").write_bytes((source / "photo.jpg").read_bytes())
    original = _file_contents(source)
    stimulus_sets = [_stimulus_set("base-set", "raw-images")]
    result = normalize_stimulus_sets(
        project_root=tmp_path, stimulus_sets=stimulus_sets, target_size=256
    )
    normalized = _file_contents(tmp_path / result.sets[0].source_dir)
    assert len(normalized) == result.sets[0].image_count == result.processed_count == 2
    assert len(set(normalized.values())) == 1

    output = tmp_path / "resized"
    for expected_count in (2, 0):
        resized = optimize_image_folder_for_fpvs(
            input_dir=source, output_dir=output, target_size=256
        )
        assert resized.processed_count == expected_count
        assert _file_contents(output) == normalized
    assert _file_contents(source) == original


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
