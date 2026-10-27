"""Declared amplifier sampling rates and minimum trigger durations.

Brain Products' January 2025 ``Communication with the trigger port`` guide,
tables 1 (actiCHamp family), 4 (BrainAmp family), and 6 (LiveAmp):
https://www.brainproducts.com/download/communication-with-the-trigger-port-a-beginners-guide/
These requirements describe the vendor configuration, not measured hardware timing.
"""

from __future__ import annotations

from typing import Literal

BrainProductsAmplifier = Literal["actichamp", "brainamp", "liveamp"]

AMPLIFIER_LABELS = {
    "actichamp": "actiCHamp / actiCHamp Plus",
    "brainamp": "BrainAmp",
    "liveamp": "LiveAmp",
}

_MINIMUM_PULSE_WIDTHS_MS: dict[str, dict[int, float]] = {
    "actichamp": {
        100: 20, 200: 10, 250: 8, 500: 4, 1000: 2, 2500: 0.8,
        5000: 0.4, 10000: 0.2, 25000: 0.08, 50000: 0.04, 100000: 0.02,
    },
    "brainamp": {100: 10, 200: 5, 250: 4, 500: 2, 1000: 1, 2500: 0.4, 5000: 0.2},
    "liveamp": {250: 8, 500: 4, 1000: 2},
}


def supported_sampling_rates_hz(amplifier: str) -> tuple[int, ...]:
    """Return only sampling rates listed in the amplifier's vendor table."""

    try:
        return tuple(_MINIMUM_PULSE_WIDTHS_MS[amplifier])
    except KeyError as exc:
        raise ValueError("Choose a supported Brain Products amplifier family.") from exc


def minimum_pulse_width_ms(amplifier: str, sampling_rate_hz: int) -> float:
    """Return the vendor minimum without interpolating unsupported sampling rates."""

    rates = supported_sampling_rates_hz(amplifier)
    if sampling_rate_hz not in rates:
        supported = ", ".join(str(rate) for rate in rates)
        raise ValueError(
            f"{AMPLIFIER_LABELS[amplifier]} supports these EEG sampling rates: "
            f"{supported} Hz. Choose the rate configured in Recorder."
        )
    return _MINIMUM_PULSE_WIDTHS_MS[amplifier][sampling_rate_hz]
