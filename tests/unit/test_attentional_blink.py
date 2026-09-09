"""Timing and slot ownership for the custom attentional-blink designer."""

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from fpvs_studio.core.attentional_blink import (
    DEFAULT_CYCLE,
    SlotRole,
    describe_attentional_blink,
    preview_attentional_blink,
)


def test_default_requested_slot_needs_no_display() -> None:
    result = describe_attentional_blink()

    assert result.roles == DEFAULT_CYCLE
    assert result.slot_count == 4
    assert result.base_count == 3
    assert result.base_hz == 4.0
    assert result.slot_ms == 250.0
    assert (result.t1_ms, result.isi_ms, result.t2_ms) == (50.0, 50.0, 150.0)
    assert result.soa_ms == 100.0
    assert result.cycle_ms == 1000.0
    assert result.pair_hz == 1.0
    assert [(s.role, s.start_ms, s.duration_ms, s.slot_index) for s in result.segments] == [
        ("base", 0.0, 250.0, 0),
        ("base", 250.0, 250.0, 1),
        ("base", 500.0, 250.0, 2),
        ("t1", 750.0, 50.0, 3),
        ("separator", 800.0, 50.0, 3),
        ("t2", 850.0, 150.0, 3),
    ]


@pytest.mark.parametrize("refresh, scale", [(60.0, 1), (120.0, 2)])
def test_default_pair_preserves_every_frame(refresh: float, scale: int) -> None:
    result = preview_attentional_blink(refresh_hz=refresh)

    assert result.frames_per_slot == 15 * scale
    assert (result.t1_frames, result.isi_frames, result.t2_frames) == tuple(
        n * scale for n in (3, 3, 9)
    )
    assert (result.t1_ms, result.isi_ms, result.t2_ms) == (50.0, 50.0, 150.0)
    assert result.realized_base_hz == 4.0
    assert result.pair_hz == 1.0
    assert result.soa_ms == 100.0
    assert result.slot_ms == 250.0
    assert result.cycle_ms == 1000.0
    assert result.warnings == ()
    frames = [
        frame
        for segment in result.segments
        for frame in range(segment.start_frame, segment.start_frame + segment.duration_frames)
    ]
    assert frames == list(range(result.total_frames))
    assert [s.role for s in result.segments] == ["base", "base", "base", "t1", "separator", "t2"]
    assert [s.slot_index for s in result.segments] == [0, 1, 2, 3, 3, 3]


def test_isi_edit_changes_t2_without_stretching_slot() -> None:
    result = preview_attentional_blink(refresh_hz=60.0, isi_ms=100.0)

    assert result.t1_ms == 50.0
    assert result.isi_ms == result.t2_ms == 100.0
    assert result.frames_per_slot == 15
    assert result.total_frames == 60
    assert result.soa_ms == 150.0


def test_rounding_is_half_up_and_t2_takes_remaining_frames() -> None:
    result = preview_attentional_blink(refresh_hz=60.0, t1_ms=25.0, isi_ms=25.0)

    assert result.t1_frames == result.isi_frames == 2
    assert result.t2_frames == 11
    assert result.t2_ms == pytest.approx(1000.0 * 11 / 60)
    assert result.description.t2_ms == 200.0
    assert len(result.warnings) == 3
    assert sum(s.duration_frames for s in result.segments[-3:]) == result.frames_per_slot


def test_nonintegral_refresh_uses_resolved_slot_and_reports_achieved_values() -> None:
    result = preview_attentional_blink(refresh_hz=59.94)

    assert result.frames_per_slot == 15
    assert result.realized_base_hz == pytest.approx(3.996)
    assert result.cycle_ms == pytest.approx(1000.0 * 60 / 59.94)
    assert result.t1_ms == pytest.approx(1000.0 * 3 / 59.94)
    assert any("Approximate frame timing" in warning for warning in result.warnings)


@pytest.mark.parametrize("field", ["base_hz", "t1_ms", "isi_ms"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), 0.0, -1.0])
def test_requested_values_must_be_finite_and_positive(field: str, value: float) -> None:
    with pytest.raises(ValueError, match="finite and greater than zero"):
        describe_attentional_blink(**{field: value})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), 0.0, -1.0])
def test_preview_refresh_must_be_finite_and_positive(value: float) -> None:
    with pytest.raises(ValueError, match="Refresh rate must be finite and greater than zero"):
        preview_attentional_blink(refresh_hz=value)


@pytest.mark.parametrize("t1, isi", [(200.0, 50.0), (201.0, 50.0), (1e308, 1e308)])
def test_requested_t1_and_isi_must_leave_time_for_t2(t1: float, isi: float) -> None:
    with pytest.raises(ValueError, match="leave time for T2"):
        describe_attentional_blink(t1_ms=t1, isi_ms=isi)


@pytest.mark.parametrize("field", ["t1_ms", "isi_ms"])
def test_positive_images_cannot_round_to_zero_frames(field: str) -> None:
    with pytest.raises(ValueError, match="rounds to zero frames"):
        preview_attentional_blink(refresh_hz=60.0, **{field: 1.0})


def test_requested_fit_cannot_consume_t2_through_frame_rounding() -> None:
    description = describe_attentional_blink(t1_ms=120.0, isi_ms=129.0)
    assert description.t2_ms == 1.0
    with pytest.raises(ValueError, match="leaving no frame for T2"):
        preview_attentional_blink(refresh_hz=60.0, t1_ms=120.0, isi_ms=129.0)


@pytest.mark.parametrize(
    "roles, message",
    [
        ((), "between 1 and 1000"),
        (("base",), "exactly one Target pair"),
        (("target_pair", "target_pair"), "exactly one Target pair"),
        (("target_pair", "base"), "last slot"),
        (("oddball", "target_pair"), "Base or Target pair"),
        (("base",) * 1000 + ("target_pair",), "between 1 and 1000"),
    ],
)
def test_cycle_has_one_terminal_pair(roles: tuple[str, ...], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        describe_attentional_blink(cast(tuple[SlotRole, ...], roles))


def test_single_pair_and_maximum_cycle_are_supported() -> None:
    one = describe_attentional_blink(("target_pair",))
    assert one.base_count == 0
    assert one.pair_hz == 4.0
    maximum = describe_attentional_blink(("base",) * 999 + ("target_pair",))
    assert maximum.slot_count == 1000
    assert maximum.cycle_ms == 250000.0


def test_invalid_display_and_unrepresentable_rate_fail_explicitly() -> None:
    with pytest.raises(ValueError, match="approved value"):
        preview_attentional_blink(refresh_hz=75.0)
    with pytest.raises(ValueError, match="faster than"):
        preview_attentional_blink(refresh_hz=60.0, base_hz=61.0, t1_ms=1.0, isi_ms=1.0)
    with pytest.raises(ValueError, match="too small"):
        describe_attentional_blink(base_hz=1e-320)


def test_description_snapshots_roles_and_is_immutable() -> None:
    roles: list[SlotRole] = list(DEFAULT_CYCLE)
    result = describe_attentional_blink(roles)
    roles.clear()
    assert result.roles == DEFAULT_CYCLE
    with pytest.raises(FrozenInstanceError):
        result.t1_ms = 100.0  # type: ignore[misc]
