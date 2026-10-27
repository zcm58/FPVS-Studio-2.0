"""Preprocessing inspection tests."""

from __future__ import annotations

import pytest
from PIL import Image, ImageFile

import fpvs_studio.preprocessing.inspection as inspection
from fpvs_studio.preprocessing.inspection import (
    ImageInspectionError,
    inspect_source_directory,
    validate_image_files,
)


def _write_image(path, size) -> None:
    Image.new("RGB", size, color=(255, 0, 0)).save(path)


def test_image_inspection_rejects_unsupported_extensions(tmp_path) -> None:
    _write_image(tmp_path / "face.jpg", (64, 64))
    (tmp_path / "notes.gif").write_bytes(b"GIF89a")

    with pytest.raises(ImageInspectionError, match="Unsupported source image files"):
        inspect_source_directory(tmp_path, relative_prefix="stimuli/original-images/base-set")


def test_image_inspection_rejects_mixed_resolutions(tmp_path) -> None:
    _write_image(tmp_path / "a.png", (64, 64))
    _write_image(tmp_path / "b.png", (128, 64))

    with pytest.raises(ImageInspectionError, match="identical resolution"):
        inspect_source_directory(tmp_path, relative_prefix="stimuli/original-images/base-set")


@pytest.mark.parametrize("suffix", [".png", ".jpg", ".JPEG", ".bmp", ".tif", ".tiff"])
@pytest.mark.parametrize("size", [(256, 256), (1024, 1024)])
def test_bundle_image_validation_preserves_supported_source_bytes(tmp_path, suffix, size) -> None:
    path = tmp_path / ("original" + suffix)
    _write_image(path, size)
    original = path.read_bytes()

    validate_image_files(iter([path]))

    assert path.read_bytes() == original


@pytest.mark.parametrize("content", [b"inert non-image audit data", b"\x89PNG\r\n\x1a\n"])
def test_bundle_image_validation_rejects_disguised_non_images(tmp_path, content) -> None:
    path = tmp_path / "fake.png"
    path.write_bytes(content)

    with pytest.raises(ImageInspectionError, match="unreadable, corrupt, truncated, or unsafe"):
        validate_image_files([path])


@pytest.mark.parametrize("actual_format", ["JPEG", "TIFF"])
def test_bundle_image_validation_requires_matching_format_and_suffix(
    tmp_path, monkeypatch, actual_format,
) -> None:
    path = tmp_path / "wrong.png"
    Image.new("RGB", (16, 16)).save(path, format=actual_format)
    image_open = Image.open
    requested_formats = []

    def checked_open(handle, *, formats):
        requested_formats.append(formats)
        return image_open(handle, formats=formats)

    monkeypatch.setattr(Image, "open", checked_open)
    with pytest.raises(ImageInspectionError, match="unreadable, corrupt, truncated, or unsafe"):
        validate_image_files([path])
    assert requested_formats == [["PNG"]]


@pytest.mark.parametrize("suffix", [".png", ".jpg"])
def test_bundle_image_validation_rejects_truncated_pixels(tmp_path, suffix) -> None:
    path = tmp_path / ("truncated" + suffix)
    _write_image(path, (64, 64))
    path.write_bytes(path.read_bytes()[:-16])

    with pytest.raises(ImageInspectionError, match="unreadable, corrupt, truncated, or unsafe"):
        validate_image_files([path])


def test_bundle_image_validation_checks_png_checksums(tmp_path) -> None:
    path = tmp_path / "corrupt.png"
    _write_image(path, (32, 32))
    payload = bytearray(path.read_bytes())
    payload[payload.index(b"IDAT") + 4] ^= 1
    path.write_bytes(payload)

    with pytest.raises(ImageInspectionError, match="unreadable, corrupt, truncated, or unsafe"):
        validate_image_files([path])


@pytest.mark.parametrize(
    ("limit", "maximum", "message"),
    [
        ("MAX_IMAGE_DIMENSION", 8, "dimensions exceed"),
        ("MAX_IMAGE_PIXELS", 255, "pixel or decoded-memory limit"),
        ("MAX_IMAGE_DECODED_BYTES", 1023, "pixel or decoded-memory limit"),
        ("MAX_BUNDLE_IMAGE_BYTES", 10, "encoded file size limit"),
    ],
)
def test_bundle_image_limits_reject_before_pixel_decode(
    tmp_path, monkeypatch, limit, maximum, message,
):
    path = tmp_path / "bounded.png"
    _write_image(path, (16, 16))
    monkeypatch.setattr(inspection, limit, maximum)

    def unexpected_load(_image, *args, **kwargs):
        raise AssertionError("Oversized image reached pixel decoding")

    monkeypatch.setattr(Image.Image, "load", unexpected_load)
    with pytest.raises(ImageInspectionError, match=message):
        validate_image_files([path])


@pytest.mark.parametrize("suffix", [".png", ".tiff"])
def test_bundle_image_validation_rejects_animation_and_multiple_pages(tmp_path, suffix) -> None:
    path = tmp_path / ("multiple" + suffix)
    Image.new("RGB", (16, 16), "red").save(
        path, save_all=True, append_images=[Image.new("RGB", (16, 16), "blue")],
    )

    with pytest.raises(ImageInspectionError, match="Animated or multipage"):
        validate_image_files([path])


def test_bundle_image_validation_propagates_cancellation_between_phases(tmp_path, monkeypatch):
    path = tmp_path / "cancel.png"
    _write_image(path, (16, 16))
    cancelled = ValueError("caller cancellation")
    checks = 0

    def cancel_check():
        nonlocal checks
        checks += 1
        if checks == 3:
            raise cancelled

    def unexpected_load(_image, *args, **kwargs):
        raise AssertionError("Cancelled validation reached pixel decoding")

    monkeypatch.setattr(Image.Image, "load", unexpected_load)
    with pytest.raises(ValueError) as result:
        validate_image_files([path], cancel_check=cancel_check)
    assert result.value is cancelled
    # Validation closed its handle on cancellation; replacement remains possible on Windows.
    path.replace(tmp_path / "cancelled.png")


def test_bundle_image_validation_requires_strict_decoder_configuration(tmp_path, monkeypatch):
    path = tmp_path / "strict.png"
    _write_image(path, (16, 16))
    monkeypatch.setattr(ImageFile, "LOAD_TRUNCATED_IMAGES", True)

    with pytest.raises(ImageInspectionError, match="strict truncated-image handling"):
        validate_image_files([path])


def test_bundle_image_validation_precancel_does_not_read_paths():
    def cancel_check():
        raise RuntimeError("cancel before reading")

    def unexpected_paths():
        raise AssertionError("Cancelled validation inspected its paths")
        yield

    with pytest.raises(RuntimeError, match="cancel before reading"):
        validate_image_files(unexpected_paths(), cancel_check=cancel_check)
