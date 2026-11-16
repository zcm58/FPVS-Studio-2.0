"""Numerical, parallel and preservation contracts for standalone equalization."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path
from threading import Barrier, Event, Lock, current_thread

import numpy as np
import pytest
from PIL import Image

from fpvs_studio.preprocessing import equalization as eq


def _image(path: Path, pixels: np.ndarray | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if pixels is None:
        pixels = np.tile(np.arange(32, 224, dtype=np.uint8), (24, 1))
    Image.fromarray(pixels).save(path)


def _pair(tmp_path: Path, name: str = "base") -> eq.FolderPair:
    pair = eq.FolderPair(tmp_path / name, tmp_path / f"{name}-equalized")
    _image(pair.input_dir / "stimulus.png")
    return pair


def test_all_folders_share_targets_and_preserve_originals(tmp_path):
    base, oddball = _pair(tmp_path), _pair(tmp_path, "oddball")
    # Different means, contrast and geometry, including an RGB source.
    rgb = np.stack([np.tile(np.arange(60, 140, dtype=np.uint8), (16, 1))] * 3, axis=2)
    _image(oddball.input_dir / "stimulus.png", rgb)
    originals = {path: path.read_bytes() for pair in (base, oddball)
                 for path in pair.input_dir.iterdir()}
    result = eq.equalize_image_folders([base, oddball])
    assert len(result.images) == 2
    for image in result.images:
        assert image.after.mean == pytest.approx(128, abs=0.501)
        assert image.after.standard_deviation == pytest.approx(
            result.target_standard_deviation, abs=0.501,
        )
        assert image.source_sha256 != image.output_sha256
        with Image.open(image.destination) as saved, Image.open(image.source) as source:
            assert saved.mode == "L"
            assert saved.size == source.size
            actual = np.asarray(saved, dtype=np.float64)
            assert actual.mean() == pytest.approx(128, abs=0.501)
            assert actual.std() == pytest.approx(result.target_standard_deviation, abs=0.501)
            assert actual.std() / actual.mean() == image.after.rms_contrast
    assert all(path.read_bytes() == before for path, before in originals.items())
    reports = [json.loads(path.read_text()) for path in result.reports]
    assert reports[0] == reports[1]
    assert reports[0]["target_rms_contrast"] == result.target_standard_deviation / 128
    assert len(reports[0]["images"]) == 2


def test_outlier_reduces_common_contrast_without_clipping(tmp_path):
    pair = _pair(tmp_path)
    skewed = np.full((100, 100), 90, dtype=np.uint8)
    skewed[0, 0] = 255
    _image(pair.input_dir / "skewed.png", skewed)
    result = eq.equalize_image_folders([pair])
    assert result.contrast_reduced
    assert result.target_standard_deviation < result.requested_standard_deviation
    assert all(0 <= item.after.minimum <= item.after.maximum <= 255 for item in result.images)
    report = json.loads(result.reports[0].read_text())
    assert report["limiting_sources"] == [str(result.images[0].source)]


def test_parallel_execution_matches_serial_pngs(tmp_path, monkeypatch):
    pair = _pair(tmp_path)
    for index in range(3):
        _image(pair.input_dir / f"other-{index}.png")
    serial = eq.equalize_image_folders([pair], max_workers=1)
    parallel_pair = eq.FolderPair(pair.input_dir, tmp_path / "parallel")
    original_read = eq._read_grayscale
    gate, lock = Barrier(2), Lock()
    first_threads = []

    def read(path):
        with lock:
            synchronize = len(first_threads) < 2
            if synchronize:
                first_threads.append(current_thread().name)
        if synchronize:
            gate.wait(timeout=5)
        return original_read(path)

    monkeypatch.setattr(eq, "_read_grayscale", read)
    parallel = eq.equalize_image_folders([parallel_pair], max_workers=2)
    assert len(set(first_threads)) == 2
    assert parallel.workers == 2
    assert [item.output_sha256 for item in serial.images] == [
        item.output_sha256 for item in parallel.images
    ]


@pytest.mark.parametrize("kind", ["flat", "transparent", "corrupt", "animated", "depth", "cmyk"])
def test_invalid_image_stops_whole_batch_before_outputs(tmp_path, kind):
    pair = _pair(tmp_path)
    invalid = pair.input_dir / "invalid.png"
    if kind == "flat":
        Image.new("L", (16, 16), 100).save(invalid)
    elif kind == "transparent":
        Image.new("RGBA", (16, 16), (20, 30, 40, 128)).save(invalid)
    elif kind == "corrupt":
        invalid.write_bytes(b"not a PNG")
    elif kind == "animated":
        Image.new("L", (16, 16), 20).save(
            invalid.with_suffix(".tiff"), save_all=True,
            append_images=[Image.new("L", (16, 16), 40)],
        )
    elif kind == "depth":
        Image.new("I;16", (16, 16), 1000).save(invalid)
    else:
        Image.new("CMYK", (16, 16)).save(invalid.with_suffix(".tiff"))
    with pytest.raises(eq.ImageEqualizationError):
        eq.equalize_image_folders([pair])
    assert not pair.output_dir.exists()


def test_opaque_alpha_exif_orientation_and_nonrecursive_intake(tmp_path):
    pair = _pair(tmp_path)
    with Image.open(pair.input_dir / "stimulus.png") as image:
        rgba = image.convert("RGBA")
        exif = Image.Exif()
        exif[274] = 6
        rgba.save(pair.input_dir / "stimulus.png", exif=exif)
    (pair.input_dir / "notes.txt").write_text("keep")
    _image(pair.input_dir / "nested" / "ignored.png")
    result = eq.equalize_image_folders([pair])
    assert len(result.images) == 1
    assert len(result.skipped_files) == 2
    with Image.open(result.images[0].destination) as image:
        assert image.size == (24, 192)
        assert image.mode == "L"


@pytest.mark.parametrize("relationship", ["same", "child", "parent", "other_input"])
def test_output_cannot_overlap_any_input(tmp_path, relationship):
    first, second = _pair(tmp_path), _pair(tmp_path, "odd")
    destinations = {
        "same": first.input_dir,
        "child": first.input_dir / "outputs",
        "parent": tmp_path,
        "other_input": second.input_dir,
    }
    with pytest.raises(eq.ImageEqualizationError, match="separate from all input"):
        eq.equalize_image_folders([
            eq.FolderPair(first.input_dir, destinations[relationship]), second,
        ])


def test_destinations_cannot_overlap_and_sources_cannot_repeat(tmp_path):
    first, second = _pair(tmp_path), _pair(tmp_path, "odd")
    with pytest.raises(eq.ImageEqualizationError, match="each other"):
        eq.equalize_image_folders([
            first, eq.FolderPair(second.input_dir, first.output_dir / "nested"),
        ])
    with pytest.raises(eq.ImageEqualizationError, match="only once"):
        eq.equalize_image_folders([first, first])


def test_existing_files_and_duplicate_png_names_are_preserved(tmp_path):
    pair = _pair(tmp_path)
    pair.output_dir.mkdir()
    sentinel = pair.output_dir / "keep.txt"
    sentinel.write_text("existing")
    with pytest.raises(eq.ImageEqualizationError, match="new or empty"):
        eq.equalize_image_folders([pair])
    assert sentinel.read_text() == "existing"
    _image(pair.input_dir / "stimulus.bmp")
    with pytest.raises(eq.ImageEqualizationError, match="Duplicate output"):
        eq.equalize_image_folders([eq.FolderPair(pair.input_dir, tmp_path / "new")])


def test_cancel_after_writes_rolls_back_owned_files_only(tmp_path):
    pair = _pair(tmp_path)
    for index in range(8):
        _image(pair.input_dir / f"image-{index}.png")
    cancel = Event()

    def progress(message):
        if message.startswith("Equalized"):
            (pair.output_dir / "external.txt").write_text("external")
            cancel.set()

    with pytest.raises(eq.ImageEqualizationCancelled):
        eq.equalize_image_folders([pair], cancel_flag=cancel.is_set, progress=progress)
    assert [path.name for path in pair.output_dir.iterdir()] == ["external.txt"]


def test_cancellation_before_analysis_writes_nothing(tmp_path):
    pair = _pair(tmp_path)
    with pytest.raises(eq.ImageEqualizationCancelled):
        eq.equalize_image_folders([pair], cancel_flag=lambda: True)
    assert not pair.output_dir.exists()


def test_source_change_and_write_race_are_detected(tmp_path, monkeypatch):
    pair = _pair(tmp_path)
    original_read = eq._read_grayscale
    reads = 0

    def changed(path):
        nonlocal reads
        reads += 1
        pixels, digest = original_read(path)
        return pixels, "changed" if reads == 2 else digest

    monkeypatch.setattr(eq, "_read_grayscale", changed)
    with pytest.raises(eq.ImageEqualizationError, match="Source changed"):
        eq.equalize_image_folders([pair])
    assert list(pair.output_dir.iterdir()) == []

    def racing(path):
        if pair.output_dir.exists():
            (pair.output_dir / "stimulus.png").write_bytes(b"external")
        return original_read(path)

    # Trigger the competing write only on the transformation pass.
    pair.output_dir.rmdir()
    monkeypatch.setattr(eq, "_read_grayscale", racing)
    with pytest.raises(FileExistsError):
        eq.equalize_image_folders([pair])
    assert (pair.output_dir / "stimulus.png").read_bytes() == b"external"


def test_saved_png_verification_failure_removes_outputs(tmp_path, monkeypatch):
    pair = _pair(tmp_path)
    original_read = eq._read_grayscale

    def damaged(path):
        pixels, digest = original_read(path)
        if path.parent == eq.filesystem_path(pair.output_dir).resolve():
            pixels = np.zeros_like(pixels)
        return pixels, digest

    monkeypatch.setattr(eq, "_read_grayscale", damaged)
    with pytest.raises(eq.ImageEqualizationError, match="cannot meet"):
        eq.equalize_image_folders([pair])
    assert list(pair.output_dir.iterdir()) == []


def test_repeat_batch_requires_fresh_output_folder(tmp_path):
    pair = _pair(tmp_path)
    result = eq.equalize_image_folders([pair])
    before = {path: path.read_bytes() for path in pair.output_dir.iterdir()}
    with pytest.raises(eq.ImageEqualizationError, match="new or empty"):
        eq.equalize_image_folders([pair])
    assert all(path.read_bytes() == data for path, data in before.items())
    assert result.reports[0].exists()


@pytest.mark.parametrize("suffix", [".png", ".bmp", ".tif", ".tiff", ".jpg", ".jpeg"])
def test_supported_formats_and_color_conversion(tmp_path, suffix):
    path = tmp_path / f"color{suffix}"
    pixels = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255]]], dtype=np.uint8)
    _image(path, pixels)
    gray, digest = eq._read_grayscale(path)
    assert gray.shape == (1, 3)
    assert len(digest) == 64
    if suffix not in {".jpg", ".jpeg"}:
        assert gray.tolist() == [[76, 150, 29]]


def test_empty_missing_and_oversized_inputs_are_explicit(tmp_path, monkeypatch):
    with pytest.raises(eq.ImageEqualizationError, match="at least one"):
        eq.equalize_image_folders([])
    pair = eq.FolderPair(tmp_path / "missing", tmp_path / "output")
    with pytest.raises(eq.ImageEqualizationError, match="missing"):
        eq.equalize_image_folders([pair])
    pair.input_dir.mkdir()
    with pytest.raises(eq.ImageEqualizationError, match="No supported images"):
        eq.equalize_image_folders([pair])
    _image(pair.input_dir / "large.png")
    monkeypatch.setattr(eq, "MAX_BUNDLE_IMAGE_BYTES", 10)
    with pytest.raises(eq.ImageEqualizationError, match="file limit"):
        eq.equalize_image_folders([pair])
    assert not pair.output_dir.exists()


@pytest.mark.parametrize("format", ["png", "tiff"])
def test_high_depth_rgb_is_not_silently_downconverted(tmp_path, format):
    path = tmp_path / f"sixteen-bit.{format}"
    if format == "png":
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(
                ">I", zlib.crc32(kind + data),
            )
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 16, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\0" + b"\xff\xff" * 3))
            + chunk(b"IEND", b""),
        )
    else:
        # Minimal uncompressed RGB TIFF, three 16-bit samples per pixel.
        tags = [(256, 3, 1, 1), (257, 3, 1, 1), (258, 3, 3, 134), (259, 3, 1, 1),
                (262, 3, 1, 2), (273, 4, 1, 140), (277, 3, 1, 3), (278, 4, 1, 1),
                (279, 4, 1, 6), (284, 3, 1, 1)]
        path.write_bytes(
            b"II" + struct.pack("<HIH", 42, 8, len(tags))
            + b"".join(struct.pack("<HHII", *tag) for tag in tags)
            + struct.pack("<IHHH", 0, 16, 16, 16) + b"\xff" * 6,
        )
    with Image.open(path) as image:
        assert image.mode == "RGB"  # Mode alone cannot validate input depth.
    with pytest.raises(eq.ImageEqualizationError, match="8-bit"):
        eq._read_grayscale(path)
