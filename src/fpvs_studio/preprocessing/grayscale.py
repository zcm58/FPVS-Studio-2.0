"""Grayscale derivative generation for imported stimulus assets. Preprocessing uses this
helper to materialize reproducible PNG variants that become manifest-backed inputs to
later compilation. The module owns offline image conversion only; validation policy,
session planning, and runtime rendering stay elsewhere."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def generate_grayscale_png(source_path: Path, destination_path: Path) -> None:
    """Generate a grayscale PNG derivative from a source image."""

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        image.convert("L").save(destination_path, format="PNG")
