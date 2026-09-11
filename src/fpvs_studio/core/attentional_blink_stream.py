"""One canonical character-grid description for AB authoring and compilation.

SOA always measures target onset to onset. Numerical exactness uses an absolute
1e-9 tolerance in grid/frame units, independently of physical display tolerance.
"""

from __future__ import annotations

import random
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from math import isclose, isfinite
from typing import Literal

from fpvs_studio.core.compiler_support import namespaced_random_seed

STREAM_BASE_HZ = 10.0
STREAM_CYCLE_SLOTS = 20
DEFAULT_STREAM_SOAS = (100.0, 300.0, 500.0)
GRID_TOLERANCE = 1e-9
StreamSlotRole = Literal["base", "t1", "t2"]


def validate_attentional_blink_stream_symbols(
    base_words: Sequence[str], t1_words: Sequence[str], t2_words: Sequence[str]
) -> None:
    """Reject ambiguous source pools before a preview or executable schedule."""

    if len(set(base_words)) < 2 or any(
        len(value) != 1 or value not in "0123456789" for value in base_words
    ):
        raise ValueError("The base stream needs at least two different single digits (0-9).")
    for label, words in (("T1", t1_words), ("T2", t2_words)):
        if not words or any(len(value) != 1 or not "A" <= value <= "Z" for value in words):
            raise ValueError(f"{label} needs a pool of single uppercase letters (A-Z).")
    for label, words in (("Base", base_words), ("T1", t1_words), ("T2", t2_words)):
        if len(set(words)) != len(words):
            raise ValueError(f"{label} character pools must not contain duplicate entries.")
    if any(not any(t2 != t1 for t2 in t2_words) for t1 in t1_words):
        raise ValueError("Every T1 letter needs a different available T2 letter.")


@dataclass(frozen=True)
class AttentionalBlinkStreamDescription:
    """Requested equal-duration characters with two independent target positions."""

    roles: tuple[StreamSlotRole, ...]
    base_hz: float
    soa_ms: float
    lag: int
    t1_slot_index: int
    t2_slot_index: int

    @property
    def cycle_slots(self) -> int:
        return len(self.roles)

    @property
    def intervening_digits(self) -> int:
        return self.lag - 1

    @property
    def item_ms(self) -> float:
        return 1000.0 / self.base_hz

    @property
    def cycle_ms(self) -> float:
        return self.cycle_slots * self.item_ms

    @property
    def pair_hz(self) -> float:
        return self.base_hz / self.cycle_slots


def iter_attentional_blink_stream_cycles(
    description: AttentionalBlinkStreamDescription,
    *,
    base_words: Sequence[str],
    t1_words: Sequence[str],
    t2_words: Sequence[str],
    random_seed: int,
) -> Iterator[tuple[str, ...]]:
    """Sample reproducible cycles without adjacent repeated digits or matching targets.

    Sampling continues across cycle boundaries. Character pools specify available
    symbols, not presentation order; each draw uses the remaining eligible symbols.
    """

    validate_attentional_blink_stream_symbols(base_words, t1_words, t2_words)
    rngs = {
        phase: random.Random(namespaced_random_seed(random_seed, f"ab-letter-stream:{phase}"))
        for phase in ("base", "t1", "t2")
    }
    previous_digit: str | None = None
    while True:
        t1 = rngs["t1"].choice(t1_words)
        t2 = rngs["t2"].choice([letter for letter in t2_words if letter != t1])
        symbols: list[str] = []
        for phase in description.roles:
            if phase == "base":
                symbol = rngs["base"].choice([
                    digit for digit in base_words if digit != previous_digit
                ])
                previous_digit = symbol
            else:
                symbol = t1 if phase == "t1" else t2
                previous_digit = None
            symbols.append(symbol)
        yield tuple(symbols)


@dataclass(frozen=True)
class AttentionalBlinkStreamPreview:
    """Exact whole-frame realization, with no rounded or alternating items."""

    description: AttentionalBlinkStreamDescription
    refresh_hz: float
    frames_per_item: int

    @property
    def achieved_base_hz(self) -> float:
        return self.refresh_hz / self.frames_per_item

    @property
    def item_ms(self) -> float:
        return self.frames_per_item * 1000.0 / self.refresh_hz

    @property
    def achieved_soa_ms(self) -> float:
        return self.description.lag * self.item_ms

    @property
    def total_frames(self) -> int:
        return self.description.cycle_slots * self.frames_per_item

    @property
    def cycle_ms(self) -> float:
        return self.description.cycle_slots * self.item_ms

    @property
    def pair_hz(self) -> float:
        return self.achieved_base_hz / self.description.cycle_slots


def describe_attentional_blink_stream(
    *,
    base_hz: float = STREAM_BASE_HZ,
    cycle_slots: int = STREAM_CYCLE_SLOTS,
    soa_ms: float = 300.0,
    t2_slot_index: int = 15,
) -> AttentionalBlinkStreamDescription:
    """Validate the onset grid and retain digits both before T1 and after T2."""

    if not isfinite(base_hz) or base_hz <= 0:
        raise ValueError("Stream rate must be finite and greater than zero.")
    if not isfinite(soa_ms) or soa_ms <= 0:
        raise ValueError("SOA must be finite and greater than zero.")
    if not isinstance(cycle_slots, int) or not 4 <= cycle_slots <= 1000:
        raise ValueError("A letter-stream cycle must contain 4 to 1000 characters.")
    lag_value = soa_ms / 1000.0 * base_hz
    if not isfinite(lag_value):
        raise ValueError("SOA is too large to describe a finite target lag.")
    lag = round(lag_value)
    if lag < 1 or not isclose(lag_value, lag, rel_tol=0, abs_tol=GRID_TOLERANCE):
        raise ValueError(
            f"SOA must be a whole multiple of {1000.0 / base_hz:.15g} ms at {base_hz:g} Hz. "
            "Targets cannot fall between character onsets."
        )
    if not isinstance(t2_slot_index, int) or not 1 <= t2_slot_index < cycle_slots - 1:
        raise ValueError("T2 must leave at least one digit after it in each cycle.")
    t1_slot_index = t2_slot_index - lag
    if t1_slot_index < 1:
        raise ValueError("SOA must leave at least one digit before T1 in each cycle.")
    roles: list[StreamSlotRole] = ["base"] * cycle_slots
    roles[t1_slot_index] = "t1"
    roles[t2_slot_index] = "t2"
    return AttentionalBlinkStreamDescription(
        tuple(roles), base_hz, soa_ms, lag, t1_slot_index, t2_slot_index
    )


def preview_attentional_blink_stream(
    *,
    refresh_hz: float,
    base_hz: float = STREAM_BASE_HZ,
    cycle_slots: int = STREAM_CYCLE_SLOTS,
    soa_ms: float = 300.0,
    t2_slot_index: int = 15,
) -> AttentionalBlinkStreamPreview:
    """Require exact character durations rather than changing requested timing."""

    description = describe_attentional_blink_stream(
        base_hz=base_hz, cycle_slots=cycle_slots, soa_ms=soa_ms, t2_slot_index=t2_slot_index
    )
    if not isfinite(refresh_hz) or refresh_hz <= 0:
        raise ValueError("Refresh rate must be finite and greater than zero.")
    frame_value = refresh_hz / base_hz
    if not isfinite(frame_value):
        raise ValueError("Stream rate is too small to resolve a finite frame count.")
    frames = round(frame_value)
    if frames < 1 or not isclose(frame_value, frames, rel_tol=0, abs_tol=GRID_TOLERANCE):
        raise ValueError(
            f"{refresh_hz:g} Hz cannot display exact {description.item_ms:g} ms characters "
            f"at {base_hz:g} Hz. Select a compatible display rate; timing will not be rounded."
        )
    return AttentionalBlinkStreamPreview(description, refresh_hz, frames)
