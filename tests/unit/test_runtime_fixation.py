"""Fixation response scoring tests."""

from __future__ import annotations

import pytest

from fpvs_studio.core.execution import FixationTargetOnsetRecord, ResponseRecord
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


def test_timestamp_scoring_uses_actual_onset_and_response_times_after_dropped_frames() -> None:
    fixation_events = [FixationEvent(event_index=0, start_frame=10, duration_frames=5)]
    responses = [
        ResponseRecord(response_index=0, key="space", frame_index=80, time_s=1.4),
    ]

    fixation_results, scored_responses = score_fixation_responses(
        fixation_events,
        responses,
        response_key="space",
        response_window_frames=60,
        fixation_target_onsets=[
            FixationTargetOnsetRecord(event_index=0, frame_index=10, time_s=1.0)
        ],
        refresh_hz=60.0,
    )
    summary = build_fixation_task_summary(
        fixation_results,
        scored_responses,
        refresh_hz=60.0,
    )

    assert fixation_results[0].outcome == "hit"
    assert fixation_results[0].target_onset_time_s == 1.0
    assert fixation_results[0].rt_frames == 70
    assert fixation_results[0].rt_s == pytest.approx(0.4)
    assert scored_responses[0].rt_s == pytest.approx(0.4)
    assert summary.mean_rt_ms == pytest.approx(400.0)


def test_timestamp_scoring_marks_time_outside_window_as_false_alarm() -> None:
    fixation_events = [FixationEvent(event_index=0, start_frame=10, duration_frames=5)]
    responses = [
        ResponseRecord(response_index=0, key="space", frame_index=20, time_s=3.1),
    ]

    fixation_results, scored_responses = score_fixation_responses(
        fixation_events,
        responses,
        response_key="space",
        response_window_frames=60,
        fixation_target_onsets=[
            FixationTargetOnsetRecord(event_index=0, frame_index=10, time_s=2.0)
        ],
        refresh_hz=60.0,
    )

    assert fixation_results[0].outcome == "miss"
    assert fixation_results[0].target_onset_time_s == 2.0
    assert scored_responses[0].outcome == "false_alarm"
    assert scored_responses[0].rt_s is None


def test_timestamp_scoring_uses_earliest_hardware_response_per_target() -> None:
    fixation_events = [FixationEvent(event_index=0, start_frame=10, duration_frames=5)]
    responses = [
        ResponseRecord(response_index=0, key="space", frame_index=24, time_s=0.4),
        ResponseRecord(response_index=1, key="space", frame_index=23, time_s=0.3),
    ]

    fixation_results, scored_responses = score_fixation_responses(
        fixation_events,
        responses,
        response_key="space",
        response_window_frames=60,
        fixation_target_onsets=[
            FixationTargetOnsetRecord(event_index=0, frame_index=10, time_s=0.1)
        ],
        refresh_hz=60.0,
    )

    assert fixation_results[0].response_time_s == 0.3
    assert scored_responses[0].outcome == "false_alarm"
    assert scored_responses[1].outcome == "hit"


def test_timestamp_scoring_accepts_final_response_captured_after_last_stimulus_frame() -> None:
    fixation_events = [FixationEvent(event_index=0, start_frame=590, duration_frames=5)]
    responses = [
        ResponseRecord(response_index=0, key="space", frame_index=660, time_s=10.2),
    ]

    fixation_results, scored_responses = score_fixation_responses(
        fixation_events,
        responses,
        response_key="space",
        response_window_frames=60,
        fixation_target_onsets=[
            FixationTargetOnsetRecord(event_index=0, frame_index=590, time_s=9.9)
        ],
        refresh_hz=60.0,
    )

    assert fixation_results[0].outcome == "hit"
    assert fixation_results[0].rt_s == pytest.approx(0.3)
    assert scored_responses[0].outcome == "hit"


def test_timestamp_scoring_falls_back_atomically_when_an_onset_is_missing() -> None:
    fixation_events = [
        FixationEvent(event_index=0, start_frame=10, duration_frames=5),
        FixationEvent(event_index=1, start_frame=100, duration_frames=5),
    ]
    responses = [
        ResponseRecord(response_index=0, key="space", frame_index=80, time_s=1.4),
    ]

    fixation_results, scored_responses = score_fixation_responses(
        fixation_events,
        responses,
        response_key="space",
        response_window_frames=60,
        fixation_target_onsets=[
            FixationTargetOnsetRecord(event_index=0, frame_index=10, time_s=1.0)
        ],
        refresh_hz=60.0,
    )

    assert [result.outcome for result in fixation_results] == ["miss", "miss"]
    assert all(result.target_onset_time_s is None for result in fixation_results)
    assert scored_responses[0].outcome == "false_alarm"
    assert scored_responses[0].rt_s is None


def test_aborted_run_excludes_unpresented_targets_and_keeps_presented_timestamp_scoring() -> None:
    fixation_events = [
        FixationEvent(event_index=0, start_frame=10, duration_frames=5),
        FixationEvent(event_index=1, start_frame=100, duration_frames=5),
    ]
    responses = [
        ResponseRecord(response_index=0, key="space", frame_index=20, time_s=1.25),
    ]

    fixation_results, scored_responses = score_fixation_responses(
        fixation_events,
        responses,
        response_key="space",
        response_window_frames=60,
        fixation_target_onsets=[
            FixationTargetOnsetRecord(event_index=0, frame_index=10, time_s=1.0)
        ],
        refresh_hz=60.0,
        completed_frames=50,
    )

    assert [result.event_index for result in fixation_results] == [0]
    assert fixation_results[0].outcome == "hit"
    assert fixation_results[0].rt_s == pytest.approx(0.25)
    assert scored_responses[0].outcome == "hit"


def test_timestamp_scoring_falls_back_when_task_response_time_is_missing() -> None:
    fixation_events = [FixationEvent(event_index=0, start_frame=10, duration_frames=5)]
    responses = [
        ResponseRecord(response_index=0, key="space", frame_index=20, time_s=None),
    ]

    fixation_results, scored_responses = score_fixation_responses(
        fixation_events,
        responses,
        response_key="space",
        response_window_frames=60,
        fixation_target_onsets=[
            FixationTargetOnsetRecord(event_index=0, frame_index=10, time_s=1.0)
        ],
        refresh_hz=60.0,
    )

    assert fixation_results[0].outcome == "hit"
    assert fixation_results[0].rt_frames == 10
    assert fixation_results[0].target_onset_time_s is None
    assert fixation_results[0].rt_s is None
    assert scored_responses[0].outcome == "hit"
