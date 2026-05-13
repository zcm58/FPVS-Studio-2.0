"""Fixation-event scheduling tests."""

from __future__ import annotations

import random

import pytest

from fpvs_studio.core.compiler_fixation import build_fixation_events
from fpvs_studio.core.compiler_support import CompileError


def _starts(total_event_count: int, *, seed: int = 42) -> list[int]:
    return [
        event.start_frame
        for event in build_fixation_events(
            total_frames=7200,
            total_event_count=total_event_count,
            target_duration_frames=15,
            min_gap_frames=60,
            rng=random.Random(seed),
        )
    ]


def test_balanced_fixation_events_span_full_condition() -> None:
    starts = _starts(12, seed=2026)

    assert starts == sorted(starts)
    assert starts[0] < 7200 * 0.25
    assert starts[-1] > 7200 * 0.75


def test_balanced_fixation_events_respect_minimum_gap_and_duration_at_higher_counts() -> None:
    events = build_fixation_events(
        total_frames=7200,
        total_event_count=30,
        target_duration_frames=15,
        min_gap_frames=60,
        rng=random.Random(123),
    )

    assert len(events) == 30
    assert all(event.duration_frames == 15 for event in events)
    assert events[0].start_frame >= 60
    assert events[-1].start_frame + events[-1].duration_frames <= 7200 - 60
    assert all(
        right.start_frame - (left.start_frame + left.duration_frames) >= 60
        for left, right in zip(events, events[1:], strict=False)
    )


def test_balanced_fixation_events_are_seed_deterministic() -> None:
    starts_a = _starts(10, seed=2026)
    starts_b = _starts(10, seed=2026)
    starts_c = _starts(10, seed=2027)

    assert starts_a == starts_b
    assert starts_a != starts_c


def test_single_fixation_event_is_placed_away_from_condition_edges() -> None:
    starts = _starts(1, seed=99)

    assert len(starts) == 1
    assert 7200 * 0.25 < starts[0] < 7200 * 0.75


def test_balanced_fixation_events_report_impossible_settings() -> None:
    with pytest.raises(CompileError, match="do not fit within one condition run"):
        build_fixation_events(
            total_frames=100,
            total_event_count=2,
            target_duration_frames=30,
            min_gap_frames=30,
            rng=random.Random(1),
        )
