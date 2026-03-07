"""Fixation response scoring tests."""

from __future__ import annotations

from fpvs_studio.core.execution import ResponseRecord
from fpvs_studio.core.run_spec import FixationEvent
from fpvs_studio.runtime.fixation import score_fixation_responses


def test_score_fixation_responses_marks_hits_and_misses() -> None:
    fixation_events = [
        FixationEvent(event_index=0, start_frame=10, duration_frames=5),
        FixationEvent(event_index=1, start_frame=30, duration_frames=5),
    ]
    responses = [
        ResponseRecord(response_index=0, key="space", frame_index=12, time_s=0.2),
        ResponseRecord(response_index=1, key="space", frame_index=40, time_s=0.6),
    ]

    fixation_results, scored_responses = score_fixation_responses(fixation_events, responses)

    assert fixation_results[0].outcome == "hit"
    assert fixation_results[0].rt_frames == 2
    assert fixation_results[1].outcome == "miss"
    assert scored_responses[0].matched_event_index == 0
    assert scored_responses[0].correct is True
    assert scored_responses[1].matched_event_index is None
    assert scored_responses[1].correct is False


def test_score_fixation_responses_uses_only_first_response_per_event() -> None:
    fixation_events = [FixationEvent(event_index=0, start_frame=20, duration_frames=4)]
    responses = [
        ResponseRecord(response_index=0, key="space", frame_index=21, time_s=0.35),
        ResponseRecord(response_index=1, key="space", frame_index=22, time_s=0.37),
    ]

    fixation_results, scored_responses = score_fixation_responses(fixation_events, responses)

    assert fixation_results[0].response_frame == 21
    assert scored_responses[0].correct is True
    assert scored_responses[1].correct is False


def test_score_fixation_responses_records_miss_when_no_response_occurs() -> None:
    fixation_events = [FixationEvent(event_index=0, start_frame=10, duration_frames=5)]

    fixation_results, scored_responses = score_fixation_responses(fixation_events, [])

    assert len(fixation_results) == 1
    assert fixation_results[0].event_index == 0
    assert fixation_results[0].start_frame == 10
    assert fixation_results[0].duration_frames == 5
    assert fixation_results[0].responded is False
    assert fixation_results[0].outcome == "miss"
    assert scored_responses == []


def test_score_fixation_responses_leaves_out_of_window_response_unmatched() -> None:
    fixation_events = [FixationEvent(event_index=0, start_frame=10, duration_frames=5)]
    responses = [
        ResponseRecord(response_index=0, key="space", frame_index=15, time_s=0.25),
    ]

    fixation_results, scored_responses = score_fixation_responses(fixation_events, responses)

    assert fixation_results[0].outcome == "miss"
    assert scored_responses[0].matched_event_index is None
    assert scored_responses[0].correct is False
