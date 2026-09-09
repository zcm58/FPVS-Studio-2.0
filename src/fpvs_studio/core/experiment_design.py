"""Requested cycle descriptions and frame previews for the visual experiment designer.

This module describes timing only. It does not compile assets, alter a project, or
produce an executable RunSpec. Masking rates refer to T1 onsets; masks are additional
images within those fixed slots. Sinusoidal previews show occupied frames, not contrast.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import floor, isclose, isfinite
from typing import Literal

from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.frame_validation import on_off_frames
from fpvs_studio.core.run_spec import StimulusRole
from fpvs_studio.core.validation import validate_display_refresh

CycleSegmentRole = Literal["base", "oddball", "blank", "mask"]
MAX_CYCLE_ROLES = 1000


@dataclass(frozen=True)
class CycleDescription:
    """Requested cycle structure and timing, without assuming a display refresh."""

    slot_count: int
    base_count: int
    requested_base_hz: float
    requested_oddball_hz: float
    requested_cycle_ms: float


@dataclass(frozen=True)
class MaskingTiming:
    """Requested T1, offset-to-onset ISI, and T2 durations in milliseconds."""

    target_duration_ms: float
    isi_ms: float
    mask_duration_ms: float

    def __post_init__(self) -> None:
        for label, value in (
            ("T1 duration", self.target_duration_ms),
            ("T2 mask duration", self.mask_duration_ms),
        ):
            if not isfinite(value) or value <= 0:
                raise ValueError(f"{label} must be finite and greater than zero.")
        if not isfinite(self.isi_ms) or self.isi_ms < 0:
            raise ValueError("ISI must be finite and greater than or equal to zero.")


@dataclass(frozen=True)
class CycleSegment:
    """One nonempty interval in a complete cycle, with a zero-based T1 slot index."""

    role: CycleSegmentRole
    start_frame: int
    duration_frames: int
    slot_index: int


@dataclass(frozen=True)
class CyclePreview:
    """Resolved timing for one repeating Base/Oddball cycle."""

    refresh_hz: float
    requested_base_hz: float
    realized_base_hz: float
    oddball_hz: float
    frames_per_slot: int
    total_frames: int
    target_frames: int
    isi_frames: int
    mask_frames: int
    remainder_frames: int
    segments: tuple[CycleSegment, ...]
    warnings: tuple[str, ...]


def describe_cycle(
    roles: Sequence[StimulusRole], *, base_hz: float
) -> CycleDescription:
    """Describe a requested terminal-oddball cycle before display validation."""

    slot_count = len(roles)
    if not 1 <= slot_count <= MAX_CYCLE_ROLES:
        raise ValueError(f"A cycle must contain between 1 and {MAX_CYCLE_ROLES} stimuli.")
    if any(role not in ("base", "oddball") for role in roles):
        raise ValueError("Cycle stimuli must be Base or Oddball.")
    if sum(role == "oddball" for role in roles) != 1:
        raise ValueError("A cycle must contain exactly one Oddball.")
    if roles[-1] != "oddball":
        raise ValueError("The Oddball must be the last stimulus in the cycle.")
    if not isfinite(base_hz) or base_hz <= 0:
        raise ValueError("Base rate must be finite and greater than zero.")
    requested_slot_ms = 1000.0 / base_hz
    requested_cycle_ms = slot_count * requested_slot_ms
    if not isfinite(requested_cycle_ms):
        raise ValueError("Base rate is too small to describe a finite cycle duration.")

    return CycleDescription(
        slot_count=slot_count,
        base_count=slot_count - 1,
        requested_base_hz=base_hz,
        requested_oddball_hz=base_hz / slot_count,
        requested_cycle_ms=requested_cycle_ms,
    )


def preview_cycle(
    roles: Sequence[StimulusRole],
    *,
    base_hz: float,
    refresh_hz: float,
    duty_cycle_mode: DutyCycleMode = DutyCycleMode.CONTINUOUS,
    masking: MaskingTiming | None = None,
) -> CyclePreview:
    """Resolve a terminal-oddball cycle without changing its fixed T1 onset cadence.

    A single oddball is permitted for compatibility with an every-one cadence.
    Masking has its own duration controls and cannot combine with blank-50 or
    sinusoidal timing. Positive masking durations round to the nearest whole frame
    (half up); values that would disappear are rejected. ISI zero remains zero.
    """

    description = describe_cycle(roles, base_hz=base_hz)
    if not isfinite(refresh_hz) or refresh_hz <= 0:
        raise ValueError("Refresh rate must be finite and greater than zero.")
    if not isfinite(refresh_hz / base_hz):
        raise ValueError("Base rate is too small to resolve to a finite frame count.")
    if masking is not None and duty_cycle_mode != DutyCycleMode.CONTINUOUS:
        raise ValueError("Masking timing cannot combine with 50% blank or sinusoidal timing.")

    report = validate_display_refresh(
        refresh_hz,
        duty_cycle_mode=duty_cycle_mode,
        base_hz=base_hz,
        oddball_every_n=description.slot_count,
    )
    if not report.compatible:
        raise ValueError(" ".join(report.errors))
    assert report.frames_per_cycle is not None
    frames_per_slot = report.frames_per_cycle
    target_frames, remainder_frames = on_off_frames(frames_per_slot, duty_cycle_mode)
    isi_frames = 0
    mask_frames = 0
    warnings = list(report.warnings)
    if masking is not None:
        target_frames = _masking_duration_frames(
            masking.target_duration_ms, refresh_hz, label="T1 duration", warnings=warnings
        )
        isi_frames = _masking_duration_frames(
            masking.isi_ms, refresh_hz, label="ISI", warnings=warnings
        )
        mask_frames = _masking_duration_frames(
            masking.mask_duration_ms, refresh_hz, label="T2 mask duration", warnings=warnings
        )
        occupied_frames = target_frames + isi_frames + mask_frames
        remainder_frames = frames_per_slot - occupied_frames
        if remainder_frames < 0:
            raise ValueError(
                f"T1 + ISI + T2 require {occupied_frames} frames, but each T1 slot has "
                f"only {frames_per_slot}. Shorten these durations or lower the base rate."
            )

    segments: list[CycleSegment] = []
    for slot_index, role in enumerate(roles):
        start_frame = slot_index * frames_per_slot
        phases: tuple[tuple[CycleSegmentRole, int], ...] = (
            (role, target_frames),
            ("blank", isi_frames),
            ("mask", mask_frames),
            ("blank", remainder_frames),
        )
        for segment_role, duration in phases:
            if duration:
                segments.append(CycleSegment(segment_role, start_frame, duration, slot_index))
                start_frame += duration

    return CyclePreview(
        refresh_hz=refresh_hz,
        requested_base_hz=base_hz,
        realized_base_hz=refresh_hz / frames_per_slot,
        oddball_hz=refresh_hz / (frames_per_slot * description.slot_count),
        frames_per_slot=frames_per_slot,
        total_frames=frames_per_slot * description.slot_count,
        target_frames=target_frames,
        isi_frames=isi_frames,
        mask_frames=mask_frames,
        remainder_frames=remainder_frames,
        segments=tuple(segments),
        warnings=tuple(warnings),
    )


def _masking_duration_frames(
    duration_ms: float, refresh_hz: float, *, label: str, warnings: list[str]
) -> int:
    if duration_ms == 0:
        return 0
    raw_frames = duration_ms / 1000.0 * refresh_hz
    resolved_frames = floor(raw_frames + 0.5)
    if resolved_frames == 0:
        raise ValueError(
            f"{label} ({duration_ms:g} ms) rounds to zero frames at {refresh_hz:g} Hz. "
            "Increase the duration to resolve to at least one frame."
        )
    if not isclose(raw_frames, resolved_frames, rel_tol=0.0, abs_tol=1e-9):
        warnings.append(
            f"{label}: requested {duration_ms:g} ms; resolves to {resolved_frames} frames "
            f"({resolved_frames / refresh_hz * 1000:g} ms)."
        )
    return resolved_frames
