"""Vendor trigger-duration requirements, without hardware or GUI imports."""

from math import ceil

import pytest

from fpvs_studio.core.brainproducts import minimum_pulse_width_ms, supported_sampling_rates_hz
from fpvs_studio.runtime.recording import validate_recording_configuration


@pytest.mark.parametrize("amplifier,rate,minimum", [
    ("actichamp", 100, 20), ("actichamp", 200, 10), ("actichamp", 250, 8),
    ("actichamp", 500, 4), ("actichamp", 1000, 2), ("actichamp", 2500, 0.8),
    ("actichamp", 5000, 0.4), ("actichamp", 10000, 0.2), ("actichamp", 25000, 0.08),
    ("actichamp", 50000, 0.04), ("actichamp", 100000, 0.02),
    ("brainamp", 100, 10), ("brainamp", 200, 5), ("brainamp", 250, 4),
    ("brainamp", 500, 2), ("brainamp", 1000, 1), ("brainamp", 2500, 0.4),
    ("brainamp", 5000, 0.2),
    ("liveamp", 250, 8), ("liveamp", 500, 4), ("liveamp", 1000, 2),
])
def test_vendor_minimum_tables_and_supported_integer_pulses(amplifier, rate, minimum):
    assert minimum_pulse_width_ms(amplifier, rate) == minimum
    assert rate in supported_sampling_rates_hz(amplifier)
    assert validate_recording_configuration({
        "recording_backend": "brainproducts_triggerbox", "brainproducts_amplifier": amplifier,
        "brainproducts_sampling_rate_hz": rate, "brainproducts_pulse_width_ms": ceil(minimum),
    }) == "brainproducts_triggerbox"


@pytest.mark.parametrize("amplifier,rates", [
    ("actichamp", (100, 200, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000)),
    ("brainamp", (100, 200, 250, 500, 1000, 2500, 5000)),
    ("liveamp", (250, 500, 1000)),
])
def test_supported_rates_do_not_invent_or_interpolate_vendor_settings(amplifier, rates):
    assert supported_sampling_rates_hz(amplifier) == rates
    with pytest.raises(ValueError, match="Choose the rate configured in Recorder"):
        minimum_pulse_width_ms(amplifier, 300)


def test_unknown_amplifier_has_no_default_timing_profile():
    with pytest.raises(ValueError, match="supported Brain Products amplifier"):
        supported_sampling_rates_hz("unknown")
