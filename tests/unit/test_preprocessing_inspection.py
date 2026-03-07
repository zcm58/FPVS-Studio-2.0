"""Preprocessing inspection tests."""

from __future__ import annotations

import pytest
from PIL import Image

from fpvs_studio.preprocessing.inspection import ImageInspectionError, inspect_source_directory


def _write_image(path, size) -> None:
    Image.new("RGB", size, color=(255, 0, 0)).save(path)


def test_image_inspection_rejects_unsupported_extensions(tmp_path) -> None:
    _write_image(tmp_path / "face.jpg", (64, 64))
    (tmp_path / "notes.gif").write_bytes(b"GIF89a")

    with pytest.raises(ImageInspectionError, match="Unsupported source image files"):
        inspect_source_directory(tmp_path, relative_prefix="stimuli/source/base-set/originals")


def test_image_inspection_rejects_mixed_resolutions(tmp_path) -> None:
    _write_image(tmp_path / "a.png", (64, 64))
    _write_image(tmp_path / "b.png", (128, 64))

    with pytest.raises(ImageInspectionError, match="identical resolution"):
        inspect_source_directory(tmp_path, relative_prefix="stimuli/source/base-set/originals")
