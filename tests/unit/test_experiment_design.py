"""Scientific timing boundaries of the visual cycle preview."""

import pytest

from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.experiment_design import MaskingTiming, describe_cycle, preview_cycle
from fpvs_studio.core.run_spec import StimulusRole

STANDARD_ROLES: tuple[StimulusRole, ...] = ("base", "base", "base", "base", "oddball")


def test_three_base_one_oddball_description_needs_no_monitor() -> None:
    result = describe_cycle(STANDARD_ROLES[1:], base_hz=4.0)

    assert result.slot_count == 4
    assert result.base_count == 3
    assert result.requested_base_hz == 4.0
    assert result.requested_oddball_hz == 1.0
    assert result.requested_cycle_ms == 1000.0


def test_description_preserves_requested_rate_before_display_validation() -> None:
    result = describe_cycle(STANDARD_ROLES, base_hz=61.0)

    assert result.requested_base_hz == 61.0
    assert result.requested_oddball_hz == pytest.approx(12.2)
    assert result.requested_cycle_ms == pytest.approx(5000.0 / 61.0)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), 0.0, -1.0])
def test_description_rejects_invalid_requested_rates(value: float) -> None:
    with pytest.raises(ValueError, match="finite and greater than zero"):
        describe_cycle(STANDARD_ROLES, base_hz=value)


@pytest.mark.parametrize("value", [1e-320, 1e-305])
def test_description_rejects_nonfinite_requested_durations(value: float) -> None:
    with pytest.raises(ValueError, match="too small"):
        describe_cycle(STANDARD_ROLES, base_hz=value)


def test_three_base_one_oddball_at_four_hz() -> None:
    result = preview_cycle(STANDARD_ROLES[1:], base_hz=4.0, refresh_hz=60.0)

    assert result.frames_per_slot == 15
    assert result.total_frames == 60
    assert result.realized_base_hz == 4.0
    assert result.oddball_hz == 1.0
    assert [(item.role, item.start_frame, item.duration_frames) for item in result.segments] == [
        ("base", 0, 15),
        ("base", 15, 15),
        ("base", 30, 15),
        ("oddball", 45, 15),
    ]


def test_standard_six_hz_every_five() -> None:
    result = preview_cycle(STANDARD_ROLES, base_hz=6.0, refresh_hz=60.0)

    assert result.frames_per_slot == result.target_frames == 10
    assert result.total_frames == 50
    assert result.oddball_hz == 1.2
    assert result.isi_frames == result.mask_frames == result.remainder_frames == 0
    assert result.warnings == ()


def test_quantized_rates_use_realized_target_onsets() -> None:
    result = preview_cycle(STANDARD_ROLES, base_hz=6.0, refresh_hz=59.94)

    assert result.requested_base_hz == 6.0
    assert result.frames_per_slot == 10
    assert result.realized_base_hz == pytest.approx(5.994)
    assert result.oddball_hz == pytest.approx(1.1988)
    assert any("Approximate frame timing" in warning for warning in result.warnings)


@pytest.mark.parametrize("isi_ms, expected_isi_frames", [(0.0, 0), (50.0, 3)])
def test_masking_preserves_target_cadence_and_covers_each_frame(
    isi_ms: float, expected_isi_frames: int
) -> None:
    result = preview_cycle(
        STANDARD_ROLES,
        base_hz=6.0,
        refresh_hz=60.0,
        masking=MaskingTiming(50.0, isi_ms, 50.0),
    )

    assert result.target_frames == result.mask_frames == 3
    assert result.isi_frames == expected_isi_frames
    assert result.remainder_frames == 4 - expected_isi_frames
    assert result.realized_base_hz == 6.0
    assert result.oddball_hz == 1.2
    assert [item.start_frame for item in result.segments if item.role in ("base", "oddball")] == [
        0, 10, 20, 30, 40
    ]
    assert [item.start_frame for item in result.segments if item.role == "mask"] == [
        offset + 3 + expected_isi_frames for offset in (0, 10, 20, 30, 40)
    ]
    covered_frames = [
        frame
        for item in result.segments
        for frame in range(item.start_frame, item.start_frame + item.duration_frames)
    ]
    assert covered_frames == list(range(result.total_frames))
    assert all(item.duration_frames > 0 for item in result.segments)


def test_masking_duration_rounding_is_half_up_and_reported() -> None:
    result = preview_cycle(
        STANDARD_ROLES,
        base_hz=6.0,
        refresh_hz=60.0,
        masking=MaskingTiming(25.0, 25.0, 25.0),
    )

    assert result.target_frames == result.isi_frames == result.mask_frames == 2
    assert len(result.warnings) == 3
    assert "33.3333 ms" in result.warnings[0]


@pytest.mark.parametrize("durations", [(1.0, 0.0, 50.0), (50.0, 1.0, 50.0), (50.0, 0.0, 1.0)])
def test_positive_duration_cannot_silently_vanish(durations: tuple[float, float, float]) -> None:
    with pytest.raises(ValueError, match="rounds to zero frames"):
        preview_cycle(
            STANDARD_ROLES,
            base_hz=6.0,
            refresh_hz=60.0,
            masking=MaskingTiming(*durations),
        )


def test_masking_must_fit_its_target_period() -> None:
    with pytest.raises(ValueError, match="require 12 frames.*only 10"):
        preview_cycle(
            STANDARD_ROLES,
            base_hz=6.0,
            refresh_hz=60.0,
            masking=MaskingTiming(100.0, 50.0, 50.0),
        )


def test_masking_can_fill_the_entire_target_period() -> None:
    result = preview_cycle(
        STANDARD_ROLES,
        base_hz=6.0,
        refresh_hz=60.0,
        masking=MaskingTiming(50.0, 0.0, 1000.0 * 7 / 60),
    )

    assert result.remainder_frames == 0
    assert all(segment.role != "blank" for segment in result.segments)


def test_blank_50_and_sinusoidal_keep_existing_frame_rules() -> None:
    blank = preview_cycle(
        STANDARD_ROLES, base_hz=6.0, refresh_hz=60.0, duty_cycle_mode=DutyCycleMode.BLANK_50
    )
    contrast = preview_cycle(
        STANDARD_ROLES, base_hz=6.0, refresh_hz=60.0, duty_cycle_mode=DutyCycleMode.SINUSOIDAL
    )

    assert blank.target_frames == blank.remainder_frames == 5
    assert [item.role for item in blank.segments[:2]] == ["base", "blank"]
    assert contrast.target_frames == 10
    assert contrast.remainder_frames == 0
    with pytest.raises(ValueError, match="even number"):
        preview_cycle(
            STANDARD_ROLES, base_hz=4.0, refresh_hz=60.0, duty_cycle_mode=DutyCycleMode.BLANK_50
        )
    with pytest.raises(ValueError, match="at least"):
        preview_cycle(
            STANDARD_ROLES, base_hz=60.0, refresh_hz=60.0, duty_cycle_mode=DutyCycleMode.SINUSOIDAL
        )


@pytest.mark.parametrize("mode", [DutyCycleMode.BLANK_50, DutyCycleMode.SINUSOIDAL])
def test_masking_does_not_silently_replace_another_mode(mode: DutyCycleMode) -> None:
    with pytest.raises(ValueError, match="cannot combine"):
        preview_cycle(
            STANDARD_ROLES,
            base_hz=6.0,
            refresh_hz=60.0,
            duty_cycle_mode=mode,
            masking=MaskingTiming(50.0, 0.0, 50.0),
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), 0.0, -1.0])
@pytest.mark.parametrize("field", ["base_hz", "refresh_hz"])
def test_invalid_rates_fail_clearly(value: float, field: str) -> None:
    rates = {"base_hz": 6.0, "refresh_hz": 60.0}
    rates[field] = value
    with pytest.raises(ValueError, match="finite and greater than zero"):
        preview_cycle(STANDARD_ROLES, base_hz=rates["base_hz"], refresh_hz=rates["refresh_hz"])


@pytest.mark.parametrize("field", ["target_duration_ms", "isi_ms", "mask_duration_ms"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), -1.0])
def test_invalid_masking_durations_fail_clearly(field: str, value: float) -> None:
    durations = {"target_duration_ms": 50.0, "isi_ms": 0.0, "mask_duration_ms": 50.0}
    durations[field] = value
    with pytest.raises(ValueError, match="finite"):
        MaskingTiming(**durations)


@pytest.mark.parametrize("durations", [(0.0, 0.0, 50.0), (50.0, 0.0, 0.0)])
def test_target_and_mask_must_have_positive_duration(durations: tuple[float, float, float]) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        MaskingTiming(*durations)


@pytest.mark.parametrize(
    "roles, message",
    [
        ((), "between 1 and 1000"),
        (("base",), "exactly one Oddball"),
        (("oddball", "oddball"), "exactly one Oddball"),
        (("oddball", "base"), "last stimulus"),
        (("mask", "oddball"), "Base or Oddball"),
        (("base",) * 1000 + ("oddball",), "between 1 and 1000"),
    ],
)
def test_invalid_cycle_roles(roles: tuple[StimulusRole, ...], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        describe_cycle(roles, base_hz=6.0)
    with pytest.raises(ValueError, match=message):
        preview_cycle(roles, base_hz=6.0, refresh_hz=60.0)


def test_single_oddball_preserves_every_one_compatibility() -> None:
    description = describe_cycle(("oddball",), base_hz=6.0)
    assert description.base_count == 0
    assert description.requested_oddball_hz == description.requested_base_hz == 6.0
    result = preview_cycle(("oddball",), base_hz=6.0, refresh_hz=60.0)
    assert result.oddball_hz == result.realized_base_hz == 6.0


def test_unapproved_refresh_and_impossible_base_rate() -> None:
    with pytest.raises(ValueError, match="approved value"):
        preview_cycle(STANDARD_ROLES, base_hz=6.0, refresh_hz=75.0)
    with pytest.raises(ValueError, match="faster than"):
        preview_cycle(STANDARD_ROLES, base_hz=61.0, refresh_hz=60.0)
    with pytest.raises(ValueError, match="too small"):
        preview_cycle(STANDARD_ROLES, base_hz=1e-320, refresh_hz=60.0)
