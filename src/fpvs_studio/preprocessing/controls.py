"""Derived-control image generation for preprocessing manifests. It materializes
deterministic rot180 and phase-scrambled PNG variants that preprocessing records before
core compilation consumes manifest paths. This module owns offline asset transforms
only; it must not take on runtime presentation or scheduling concerns."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def generate_rot180_png(source_path: Path, destination_path: Path) -> None:
    """Generate a 180-degree orientation-inverted PNG derivative."""

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        image.transpose(Image.Transpose.ROTATE_180).save(destination_path, format="PNG")


def generate_phase_scrambled_png(source_path: Path, destination_path: Path, *, seed: int) -> None:
    """Generate a deterministic Fourier phase-scrambled PNG derivative."""

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    with Image.open(source_path) as image:
        rgb_image = image.convert("RGB")
        image_array = np.asarray(rgb_image, dtype=np.float64)

    scrambled_channels = [
        _phase_scramble_channel(image_array[:, :, channel_index], rng)
        for channel_index in range(image_array.shape[2])
    ]
    scrambled_array = np.stack(scrambled_channels, axis=2)
    Image.fromarray(scrambled_array).save(destination_path, format="PNG")


def _phase_scramble_channel(channel: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Preserve the amplitude spectrum while replacing phase deterministically."""

    amplitude = np.abs(np.fft.fft2(channel))
    noise = rng.standard_normal(channel.shape)
    noise_phase = np.angle(np.fft.fft2(noise))
    scrambled = np.fft.ifft2(amplitude * np.exp(1j * noise_phase)).real
    scrambled -= scrambled.min()
    max_value = scrambled.max()
    if max_value > 0:
        scrambled = scrambled / max_value
    return np.rint(scrambled * 255.0).astype(np.uint8)
