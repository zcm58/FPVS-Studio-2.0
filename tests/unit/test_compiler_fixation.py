"""Fixation-event scheduling tests."""

from __future__ import annotations

import random

import pytest
from pydantic import ValidationError

from fpvs_studio.core.compiler_fixation import build_fixation_events
from fpvs_studio.core.compiler_support import CompileError
from fpvs_studio.core.models import FixationTargetOnsetWindow, FixationTaskSettings


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


def _windowed_events(seed: int, *, bounds: tuple[int, int] = (1800, 2220)):
    return build_fixation_events(
        total_frames=2400,
        total_event_count=1,
        target_duration_frames=18,
        min_gap_frames=90,
        rng=random.Random(seed),
        onset_window_frames=bounds,
    )


def test_windowed_single_target_is_seeded_and_spans_requested_late_window() -> None:
    starts = []
    for seed in range(100):
        events = _windowed_events(seed)
        assert events == _windowed_events(seed)
        assert len(events) == 1
        assert events[0].duration_frames == 18
        starts.append(events[0].start_frame)
    assert all(1800 <= start <= 2220 for start in starts)
    assert min(starts) < 1842
    assert max(starts) > 2178
    assert len(set(starts)) > 50


@pytest.mark.parametrize("start", [90, 1800, 2220, 2292])
def test_windowed_single_target_accepts_exact_inclusive_bounds(start: int) -> None:
    assert _windowed_events(42, bounds=(start, start))[0].start_frame == start


@pytest.mark.parametrize("bounds", [(89, 2220), (1800, 2293), (2220, 1800)])
def test_windowed_single_target_rejects_window_outside_available_run(bounds) -> None:
    with pytest.raises(CompileError, match="onset window does not fit"):
        _windowed_events(42, bounds=bounds)


@pytest.mark.parametrize("count", [0, 2])
def test_windowed_fixation_rejects_non_single_target_count(count: int) -> None:
    with pytest.raises(CompileError, match="requires exactly one"):
        build_fixation_events(
            total_frames=2400, total_event_count=count, target_duration_frames=18,
            min_gap_frames=90, rng=random.Random(42), onset_window_frames=(1800, 2220),
        )


def test_fixation_window_is_opt_in_and_survives_json_round_trip() -> None:
    assert FixationTaskSettings().target_onset_window is None
    assert "target_onset_window" not in FixationTaskSettings().model_dump()
    assert "target_onset_window" not in FixationTaskSettings().model_dump(mode="json")
    settings = FixationTaskSettings(
        changes_per_sequence=1,
        target_onset_window=FixationTargetOnsetWindow(
            earliest_seconds_before_end=10, latest_seconds_before_end=3,
        ),
    )
    assert settings.model_dump(mode="json")["target_onset_window"] == {
        "earliest_seconds_before_end": 10, "latest_seconds_before_end": 3,
    }
    assert FixationTaskSettings.model_validate_json(settings.model_dump_json()) == settings


@pytest.mark.parametrize("earliest,latest", [
    (3, 10), (0, 0), (10, -1), (float("inf"), 3), (10, float("inf")),
    (float("nan"), 3), (10, float("nan")),
])
def test_fixation_window_rejects_invalid_relative_bounds(earliest, latest) -> None:
    with pytest.raises(ValidationError):
        FixationTargetOnsetWindow(
            earliest_seconds_before_end=earliest, latest_seconds_before_end=latest,
        )


@pytest.mark.parametrize("overrides", [
    {"changes_per_sequence": 0},
    {"changes_per_sequence": 2},
    {"target_count_mode": "randomized"},
    {"enabled": False, "accuracy_task_enabled": False},
    {"show_cross": False, "enabled": False, "accuracy_task_enabled": False,
     "participant_tutorial_enabled": False},
])
def test_fixation_window_requires_enabled_visible_single_fixed_target(overrides) -> None:
    with pytest.raises(ValidationError, match="onset window requires"):
        FixationTaskSettings.model_validate({
            "changes_per_sequence": 1,
            "target_onset_window": {
                "earliest_seconds_before_end": 10, "latest_seconds_before_end": 3,
            },
            **overrides,
        })
