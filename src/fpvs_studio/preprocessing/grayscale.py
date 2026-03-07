"""Grayscale derivative generation."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def generate_grayscale_png(source_path: Path, destination_path: Path) -> None:
    """Generate a grayscale PNG derivative from a source image."""

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        image.convert("L").save(destination_path, format="PNG")
