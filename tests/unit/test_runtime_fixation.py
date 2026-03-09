"""Fixation response scoring tests."""

from __future__ import annotations

import pytest

from fpvs_studio.core.execution import ResponseRecord
from fpvs_studio.core.run_spec import FixationEvent
from fpvs_studio.runtime.fixation import build_fixation_task_summary, score_fixation_responses


def test_score_fixation_responses_counts_hit_within_one_second_window() -> None:
    fixation_events = [FixationEvent(event_index=0, start_frame=10, duration_frames=5)]
    responses = [
        ResponseRecord(response_index=0, key="space", frame_index=50, time_s=0.8),
    ]

    fixation_results, scored_responses = score_fixation_responses(
        fixation_events,
        responses,
        response_key="space",
        response_window_frames=60,
    )

    assert fixation_results[0].outcome == "hit"
    assert fixation_results[0].rt_frames == 40
    assert scored_responses[0].matched_event_index == 0
    assert scored_responses[0].outcome == "hit"


def test_score_fixation_responses_counts_miss_when_no_response_in_window() -> None:
    fixation_events = [FixationEvent(event_index=0, start_frame=10, duration_frames=5)]
    responses = [
        ResponseRecord(response_index=0, key="space", frame_index=71, time_s=1.2),
    ]

    fixation_results, scored_responses = score_fixation_responses(
        fixation_events,
        responses,
        response_key="space",
        response_window_frames=60,
    )

    assert fixation_results[0].outcome == "miss"
    assert scored_responses[0].outcome == "false_alarm"
    assert scored_responses[0].correct is False


def test_score_fixation_responses_counts_false_alarm_outside_open_window() -> None:
    fixation_events = [FixationEvent(event_index=0, start_frame=40, duration_frames=5)]
    responses = [ResponseRecord(response_index=0, key="space", frame_index=10, time_s=0.2)]

    fixation_results, scored_responses = score_fixation_responses(
        fixation_events,
        responses,
        response_key="space",
        response_window_frames=60,
    )

    assert fixation_results[0].outcome == "miss"
    assert scored_responses[0].matched_event_index is None
    assert scored_responses[0].outcome == "false_alarm"
    assert scored_responses[0].correct is False


def test_score_fixation_responses_uses_only_first_response_per_target_window() -> None:
    fixation_events = [FixationEvent(event_index=0, start_frame=20, duration_frames=4)]
    responses = [
        ResponseRecord(response_index=0, key="space", frame_index=21, time_s=0.35),
        ResponseRecord(response_index=1, key="space", frame_index=22, time_s=0.37),
    ]

    fixation_results, scored_responses = score_fixation_responses(
        fixation_events,
        responses,
        response_key="space",
        response_window_frames=60,
    )

    assert fixation_results[0].response_frame == 21
    assert scored_responses[0].outcome == "hit"
    assert scored_responses[1].outcome == "false_alarm"
    assert scored_responses[1].correct is False


def test_fixation_task_summary_computes_mean_rt_from_hits_only() -> None:
    fixation_events = [
        FixationEvent(event_index=0, start_frame=0, duration_frames=5),
        FixationEvent(event_index=1, start_frame=100, duration_frames=5),
        FixationEvent(event_index=2, start_frame=200, duration_frames=5),
    ]
    responses = [
        ResponseRecord(response_index=0, key="space", frame_index=12, time_s=0.2),
        ResponseRecord(response_index=1, key="space", frame_index=130, time_s=0.6),
        ResponseRecord(response_index=2, key="space", frame_index=270, time_s=1.2),
    ]
    fixation_results, scored_responses = score_fixation_responses(
        fixation_events,
        responses,
        response_key="space",
        response_window_frames=60,
    )
    summary = build_fixation_task_summary(
        fixation_results,
        scored_responses,
        refresh_hz=60.0,
    )

    assert summary.total_targets == 3
    assert summary.hit_count == 2
    assert summary.miss_count == 1
    assert summary.false_alarm_count == 1
    assert summary.accuracy_percent == pytest.approx((2 / 3) * 100.0)
    assert summary.mean_rt_ms == 350.0
