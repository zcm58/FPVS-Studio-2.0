"""Engine-neutral sinusoidal contrast-modulation helpers.

The editable project stores only the presentation mode and requested frequency. The
compiler resolves frequency to ``frames_per_stimulus``; this module then derives the
one-cycle contrast envelope from that compiled frame count without consulting a
refresh rate, project model, GUI, or presentation engine.
"""

from __future__ import annotations

import math

SINUSOIDAL_NEUTRAL_BACKGROUND_COLOR = "#808080"
MIN_SINUSOIDAL_FRAMES_PER_STIMULUS = 4


def sinusoidal_contrast_envelope(frames_per_stimulus: int) -> tuple[float, ...]:
    """Return one raised-cosine contrast cycle for a compiled frame count.

    Samples use ``0.5 * (1 - cos(2*pi*k/N))`` for ``k`` in ``[0, N)``. Odd
    sample counts do not land on the continuous peak, so only those envelopes are
    normalized to reach exactly ``1.0``. At least four samples are required to
    represent a background-to-peak-to-return cycle.
    """

    if isinstance(frames_per_stimulus, bool) or not isinstance(frames_per_stimulus, int):
        raise TypeError("frames_per_stimulus must be an integer.")
    if frames_per_stimulus < MIN_SINUSOIDAL_FRAMES_PER_STIMULUS:
        raise ValueError(
            "Sinusoidal contrast modulation requires at least "
            f"{MIN_SINUSOIDAL_FRAMES_PER_STIMULUS} frames per stimulus cycle."
        )

    envelope = tuple(
        0.5 * (1.0 - math.cos(math.tau * frame_index / frames_per_stimulus))
        for frame_index in range(frames_per_stimulus)
    )
    if frames_per_stimulus % 2 == 0:
        return envelope

    sampled_peak = max(envelope)
    return tuple(value / sampled_peak for value in envelope)


def is_sinusoidal_neutral_background(
    value: str | tuple[int, int, int],
) -> bool:
    """Return whether a persisted or compiled color is neutral gray ``#808080``."""

    if isinstance(value, tuple):
        return value == (128, 128, 128)
    compact = "".join(value.strip().lower().split())
    return compact in {SINUSOIDAL_NEUTRAL_BACKGROUND_COLOR.lower(), "rgb(128,128,128)"}
