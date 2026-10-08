"""Safe format spoofing fixtures, without native vulnerability payloads."""

from __future__ import annotations

import pytest
from PIL import Image, UnidentifiedImageError

from fpvs_studio.preprocessing.controls import generate_phase_scrambled_png, generate_rot180_png
from fpvs_studio.preprocessing.grayscale import generate_grayscale_png
from fpvs_studio.preprocessing.inspection import inspect_source_directory
from fpvs_studio.preprocessing.normalization import _resize_center_crop_png


@pytest.mark.parametrize("operation", ["inspect", "resize", "grayscale", "rotate", "scramble"])
def test_unsupported_decoder_is_not_selected_by_renamed_image(tmp_path, operation):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "renamed.png"
    Image.new("RGB", (8, 8)).save(source, format="TGA")
    target = tmp_path / "output.png"
    with pytest.raises(UnidentifiedImageError):
        if operation == "inspect":
            inspect_source_directory(source_dir)
        elif operation == "resize":
            _resize_center_crop_png(source, target, target_width=4, target_height=4)
        elif operation == "grayscale":
            generate_grayscale_png(source, target)
        elif operation == "rotate":
            generate_rot180_png(source, target)
        else:
            generate_phase_scrambled_png(source, target, seed=1)
    assert not target.exists()


@pytest.mark.parametrize("format,suffix", [
    ("JPEG", ".jpg"), ("PNG", ".png"), ("BMP", ".bmp"), ("TIFF", ".tif"),
])
def test_resizer_supported_formats_remain_readable(tmp_path, format, suffix):
    source = tmp_path / ("image" + suffix)
    target = tmp_path / "output.png"
    Image.new("RGB", (8, 8)).save(source, format=format)
    _resize_center_crop_png(source, target, target_width=4, target_height=4)
    with Image.open(target) as image:
        assert image.size == (4, 4)
