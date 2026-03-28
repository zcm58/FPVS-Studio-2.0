"""Runtime fixation-response scoring helpers.
It turns raw response logs and compiled FixationEvent data from RunSpec playback into neutral fixation summaries stored in execution contracts.
The module owns scoring math and summary derivation, not fixation scheduling, participant feedback rendering, or engine input handling."""

from __future__ import annotations

from collections.abc import Sequence
import math

from fpvs_studio.core.execution import (
    FixationResponseRecord,
    FixationTaskSummary,
    ResponseRecord,
)
from fpvs_studio.core.run_spec import FixationEvent


def score_fixation_responses(
    fixation_events: Sequence[FixationEvent],
    response_log: Sequence[ResponseRecord],
    *,
    response_key: str,
    response_window_frames: int,
) -> tuple[list[FixationResponseRecord], list[ResponseRecord]]:
    """Score response events against compiled fixation targets."""

    ordered_events = sorted(
        fixation_events,
        key=lambda item: (item.start_frame, item.event_index),
    )
    ordered_responses = list(response_log)
    event_lookup = {event.event_index: event for event in ordered_events}
    matched_response_indices: dict[int, int] = {}
    matched_event_indices: set[int] = set()

    for response_index, response in enumerate(ordered_responses):
        if response.key != response_key:
            continue
        for event in ordered_events:
            if event.event_index in matched_event_indices:
                continue
            window_end_frame = event.start_frame + response_window_frames
            if event.start_frame <= response.frame_index < window_end_frame:
                matched_response_indices[response_index] = event.event_index
                matched_event_indices.add(event.event_index)
                break

    fixation_results: list[FixationResponseRecord] = []
    for event in sorted(fixation_events, key=lambda item: item.event_index):
        matched_index = next(
            (index for index, event_index in matched_response_indices.items() if event_index == event.event_index),
            None,
        )
        if matched_index is None:
            fixation_results.append(
                FixationResponseRecord(
                    event_index=event.event_index,
                    start_frame=event.start_frame,
                    duration_frames=event.duration_frames,
                    responded=False,
                    outcome="miss",
                )
            )
            continue

        matched_response = ordered_responses[matched_index]
        fixation_results.append(
            FixationResponseRecord(
                event_index=event.event_index,
                start_frame=event.start_frame,
                duration_frames=event.duration_frames,
                responded=True,
                first_response_key=matched_response.key,
                response_frame=matched_response.frame_index,
                response_time_s=matched_response.time_s,
                rt_frames=matched_response.frame_index - event.start_frame,
                outcome="hit",
            )
        )

    scored_responses: list[ResponseRecord] = []
    for index, response in enumerate(ordered_responses):
        matched_event_index = matched_response_indices.get(index)
        matched_event = event_lookup.get(matched_event_index) if matched_event_index is not None else None
        rt_frames = (
            response.frame_index - matched_event.start_frame
            if matched_event is not None
            else None
        )
        is_false_alarm = matched_event_index is None and response.key == response_key
        scored_responses.append(
            response.model_copy(
                update={
                    "response_index": index,
                    "matched_event_index": matched_event_index,
                    "rt_frames": rt_frames,
                    "correct": (matched_event_index is not None) if response.key == response_key else None,
                    "outcome": "hit" if matched_event_index is not None else ("false_alarm" if is_false_alarm else None),
                }
            )
        )

    return fixation_results, scored_responses


def build_fixation_task_summary(
    fixation_results: Sequence[FixationResponseRecord],
    scored_responses: Sequence[ResponseRecord],
    *,
    refresh_hz: float,
) -> FixationTaskSummary:
    """Aggregate condition-level fixation-task metrics for feedback and export."""

    total_targets = len(fixation_results)
    hit_count = sum(1 for event in fixation_results if event.outcome == "hit")
    miss_count = total_targets - hit_count
    false_alarm_count = sum(1 for response in scored_responses if response.outcome == "false_alarm")
    accuracy_percent = (hit_count / total_targets * 100.0) if total_targets > 0 else 0.0
    hit_rt_ms = [
        (event.rt_frames / refresh_hz) * 1000.0
        for event in fixation_results
        if event.outcome == "hit" and event.rt_frames is not None
    ]
    mean_rt_ms = (
        math.fsum(hit_rt_ms) / len(hit_rt_ms)
        if hit_rt_ms
        else None
    )
    return FixationTaskSummary(
        total_targets=total_targets,
        hit_count=hit_count,
        miss_count=miss_count,
        false_alarm_count=false_alarm_count,
        accuracy_percent=accuracy_percent,
        mean_rt_ms=mean_rt_ms,
    )
