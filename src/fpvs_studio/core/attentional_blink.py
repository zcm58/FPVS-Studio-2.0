"""Neutral descriptions of the designer's custom within-slot target pair.

One target-pair slot contains T1, an image or blank interval during the ISI, and
T2 filling the remainder. These descriptions are not executable experiment specs
and do not imply a conventional attentional-blink lag or participant response task.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import floor, isclose, isfinite
from typing import Literal

from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.validation import validate_display_refresh

SlotRole = Literal["base", "target_pair"]
SegmentRole = Literal["base", "t1", "separator", "t2"]
DEFAULT_CYCLE: tuple[SlotRole, ...] = ("base", "base", "base", "target_pair")
MAX_CYCLE_SLOTS = 1000


@dataclass(frozen=True)
class RequestedSegment:
    """One image in the requested cycle, useful for a slowed illustration."""

    role: SegmentRole
    start_ms: float
    duration_ms: float
    slot_index: int


@dataclass(frozen=True)
class FrameSegment:
    """One image's contiguous frame interval within the complete cycle."""

    role: SegmentRole
    start_frame: int
    duration_frames: int
    slot_index: int


@dataclass(frozen=True)
class AttentionalBlinkDescription:
    """Requested timing before selecting or measuring a display."""

    roles: tuple[SlotRole, ...]
    base_hz: float
    t1_ms: float
    isi_ms: float
    segments: tuple[RequestedSegment, ...]

    @property
    def slot_count(self) -> int:
        return len(self.roles)

    @property
    def base_count(self) -> int:
        return self.slot_count - 1

    @property
    def slot_ms(self) -> float:
        return 1000.0 / self.base_hz

    @property
    def t2_ms(self) -> float:
        return self.slot_ms - self.t1_ms - self.isi_ms

    @property
    def soa_ms(self) -> float:
        """T1 onset to T2 onset; ISI alone is offset to onset."""
        return self.t1_ms + self.isi_ms

    @property
    def cycle_ms(self) -> float:
        return self.slot_ms * self.slot_count

    @property
    def pair_hz(self) -> float:
        return self.base_hz / self.slot_count


@dataclass(frozen=True)
class AttentionalBlinkPreview:
    """Whole-frame preview with T2 occupying all remaining slot frames."""

    description: AttentionalBlinkDescription
    refresh_hz: float
    frames_per_slot: int
    t1_frames: int
    isi_frames: int
    t2_frames: int
    segments: tuple[FrameSegment, ...]
    warnings: tuple[str, ...]

    @property
    def realized_base_hz(self) -> float:
        return self.refresh_hz / self.frames_per_slot

    @property
    def pair_hz(self) -> float:
        return self.realized_base_hz / self.description.slot_count

    @property
    def total_frames(self) -> int:
        return self.frames_per_slot * self.description.slot_count

    @property
    def slot_ms(self) -> float:
        return self.frames_per_slot / self.refresh_hz * 1000.0

    @property
    def t1_ms(self) -> float:
        return self.t1_frames / self.refresh_hz * 1000.0

    @property
    def isi_ms(self) -> float:
        return self.isi_frames / self.refresh_hz * 1000.0

    @property
    def t2_ms(self) -> float:
        return self.t2_frames / self.refresh_hz * 1000.0

    @property
    def soa_ms(self) -> float:
        return (self.t1_frames + self.isi_frames) / self.refresh_hz * 1000.0

    @property
    def cycle_ms(self) -> float:
        return self.total_frames / self.refresh_hz * 1000.0


def describe_attentional_blink(
    roles: Sequence[SlotRole] = DEFAULT_CYCLE,
    *,
    base_hz: float = 4.0,
    t1_ms: float = 50.0,
    isi_ms: float = 50.0,
) -> AttentionalBlinkDescription:
    """Validate one terminal pair and describe requested timing without a display."""

    slot_count = len(roles)
    if not 1 <= slot_count <= MAX_CYCLE_SLOTS:
        raise ValueError(f"A cycle must contain between 1 and {MAX_CYCLE_SLOTS} slots.")
    if any(role not in ("base", "target_pair") for role in roles):
        raise ValueError("Cycle slots must be Base or Target pair.")
    if sum(role == "target_pair" for role in roles) != 1:
        raise ValueError("A cycle must contain exactly one Target pair.")
    if roles[-1] != "target_pair":
        raise ValueError("The Target pair must be the last slot in the cycle.")
    for label, value in (("Stream rate", base_hz), ("T1 duration", t1_ms), ("ISI", isi_ms)):
        if not isfinite(value) or value <= 0:
            raise ValueError(f"{label} must be finite and greater than zero.")
    slot_ms = 1000.0 / base_hz
    if not isfinite(slot_ms * slot_count):
        raise ValueError("Stream rate is too small to describe a finite cycle duration.")
    t2_ms = slot_ms - t1_ms - isi_ms
    if t2_ms <= 0:
        raise ValueError(
            f"T1 and ISI must leave time for T2 within the {slot_ms:g} ms slot. "
            "Shorten T1 or ISI, or lower the stream rate."
        )

    phases: tuple[tuple[SegmentRole, float], ...] = (
        ("t1", t1_ms),
        ("separator", isi_ms),
        ("t2", t2_ms),
    )
    segments: list[RequestedSegment] = []
    for slot_index, role in enumerate(roles):
        start_ms = slot_index * slot_ms
        if role == "base":
            segments.append(RequestedSegment("base", start_ms, slot_ms, slot_index))
        else:
            for segment_role, duration in phases:
                segments.append(RequestedSegment(segment_role, start_ms, duration, slot_index))
                start_ms += duration
    return AttentionalBlinkDescription(tuple(roles), base_hz, t1_ms, isi_ms, tuple(segments))


def preview_attentional_blink(
    roles: Sequence[SlotRole] = DEFAULT_CYCLE,
    *,
    refresh_hz: float,
    base_hz: float = 4.0,
    t1_ms: float = 50.0,
    isi_ms: float = 50.0,
) -> AttentionalBlinkPreview:
    """Round T1 and ISI half up and reserve the unchanged slot remainder for T2.

    The separator is an image, so it must occupy at least one frame. Durations
    rounding to zero and combinations leaving no T2 frame are explicit errors.
    """

    description = describe_attentional_blink(roles, base_hz=base_hz, t1_ms=t1_ms, isi_ms=isi_ms)
    if not isfinite(refresh_hz) or refresh_hz <= 0:
        raise ValueError("Refresh rate must be finite and greater than zero.")
    if not isfinite(refresh_hz / base_hz):
        raise ValueError("Stream rate is too small to resolve to a finite frame count.")
    report = validate_display_refresh(
        refresh_hz,
        duty_cycle_mode=DutyCycleMode.CONTINUOUS,
        base_hz=base_hz,
        oddball_every_n=description.slot_count,
    )
    if not report.compatible:
        raise ValueError(" ".join(report.errors))
    assert report.frames_per_cycle is not None
    frames_per_slot = report.frames_per_cycle
    t1_frames = _duration_frames(t1_ms, refresh_hz, label="T1 duration")
    isi_frames = _duration_frames(isi_ms, refresh_hz, label="ISI")
    t2_frames = frames_per_slot - t1_frames - isi_frames
    if t2_frames < 1:
        raise ValueError(
            f"T1 and ISI use {t1_frames + isi_frames} of the slot's {frames_per_slot} frames, "
            "leaving no frame for T2. Shorten T1 or ISI, or lower the stream rate."
        )

    phases: tuple[tuple[SegmentRole, int], ...] = (
        ("t1", t1_frames),
        ("separator", isi_frames),
        ("t2", t2_frames),
    )
    segments: list[FrameSegment] = []
    for slot_index, role in enumerate(roles):
        start_frame = slot_index * frames_per_slot
        if role == "base":
            segments.append(FrameSegment("base", start_frame, frames_per_slot, slot_index))
        else:
            for segment_role, frames in phases:
                segments.append(FrameSegment(segment_role, start_frame, frames, slot_index))
                start_frame += frames
    warnings = list(report.warnings)
    for label, requested, frames in (
        ("T1", t1_ms, t1_frames),
        ("ISI", isi_ms, isi_frames),
        ("T2", description.t2_ms, t2_frames),
    ):
        achieved_ms = frames / refresh_hz * 1000.0
        if not isclose(requested, achieved_ms, rel_tol=0.0, abs_tol=1e-9):
            warnings.append(
                f"{label}: requested {requested:g} ms; resolves to {frames} frames "
                f"({achieved_ms:g} ms)."
            )
    return AttentionalBlinkPreview(
        description,
        refresh_hz,
        frames_per_slot,
        t1_frames,
        isi_frames,
        t2_frames,
        tuple(segments),
        tuple(warnings),
    )


def _duration_frames(duration_ms: float, refresh_hz: float, *, label: str) -> int:
    frames = floor(duration_ms / 1000.0 * refresh_hz + 0.5)
    if frames == 0:
        raise ValueError(
            f"{label} ({duration_ms:g} ms) rounds to zero frames at {refresh_hz:g} Hz. "
            "Increase the duration to resolve to at least one frame."
        )
    return frames
