"""Runtime fixation-response scoring helpers. It turns raw response logs and compiled
FixationEvent data from RunSpec playback into neutral fixation summaries stored in
execution contracts. The module owns scoring math and summary derivation, not fixation
scheduling, participant feedback rendering, or engine input handling."""

from __future__ import annotations

import math
from collections.abc import Sequence

from fpvs_studio.core.execution import (
    FixationResponseRecord,
    FixationTargetOnsetRecord,
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
    fixation_target_onsets: Sequence[FixationTargetOnsetRecord] = (),
    refresh_hz: float | None = None,
    completed_frames: int | None = None,
) -> tuple[list[FixationResponseRecord], list[ResponseRecord]]:
    """Score responses against actual target times, with a frame-only fallback.

    Timestamp scoring is deliberately all-or-nothing for a run. It is used only when
    every target has one matching actual onset, every task-key response has a hardware
    timestamp, and the refresh rate needed to convert the compiled response window is
    available. Otherwise the legacy frame-index behavior is preserved.
    """

    attempted_events = [
        event
        for event in fixation_events
        if completed_frames is None or event.start_frame < completed_frames
    ]
    ordered_events = sorted(
        attempted_events,
        key=lambda item: (item.start_frame, item.event_index),
    )
    ordered_responses = list(response_log)
    event_lookup = {event.event_index: event for event in ordered_events}
    onset_lookup = _complete_timestamp_onset_lookup(
        attempted_events,
        ordered_responses,
        response_key=response_key,
        fixation_target_onsets=fixation_target_onsets,
        refresh_hz=refresh_hz,
    )
    if onset_lookup is not None:
        assert refresh_hz is not None
        ordered_events = sorted(
            ordered_events,
            key=lambda item: (onset_lookup[item.event_index].time_s, item.event_index),
        )
        response_indices = sorted(
            range(len(ordered_responses)),
            key=lambda index: (
                ordered_responses[index].time_s
                if ordered_responses[index].time_s is not None
                else math.inf,
                index,
            ),
        )
        response_window_s = response_window_frames / refresh_hz
    else:
        response_indices = list(range(len(ordered_responses)))
        response_window_s = None
    matched_response_indices: dict[int, int] = {}
    matched_event_indices: set[int] = set()

    for response_index in response_indices:
        response = ordered_responses[response_index]
        if response.key != response_key:
            continue
        for event in ordered_events:
            if event.event_index in matched_event_indices:
                continue
            if onset_lookup is not None:
                assert response.time_s is not None
                assert response_window_s is not None
                onset_time_s = onset_lookup[event.event_index].time_s
                matches = onset_time_s <= response.time_s < onset_time_s + response_window_s
            else:
                window_end_frame = event.start_frame + response_window_frames
                matches = event.start_frame <= response.frame_index < window_end_frame
            if matches:
                matched_response_indices[response_index] = event.event_index
                matched_event_indices.add(event.event_index)
                break

    matched_event_to_response = {
        event_index: response_index
        for response_index, event_index in matched_response_indices.items()
    }
    fixation_results: list[FixationResponseRecord] = []
    for event in sorted(attempted_events, key=lambda item: item.event_index):
        matched_index = matched_event_to_response.get(event.event_index)
        target_onset_time_s = (
            onset_lookup[event.event_index].time_s if onset_lookup is not None else None
        )
        if matched_index is None:
            fixation_results.append(
                FixationResponseRecord(
                    event_index=event.event_index,
                    start_frame=event.start_frame,
                    duration_frames=event.duration_frames,
                    responded=False,
                    target_onset_time_s=target_onset_time_s,
                    outcome="miss",
                )
            )
            continue

        matched_response = ordered_responses[matched_index]
        rt_frames = _nonnegative_frame_rt(
            response_frame=matched_response.frame_index,
            target_frame=event.start_frame,
        )
        if onset_lookup is not None:
            assert matched_response.time_s is not None
            assert target_onset_time_s is not None
            rt_s = matched_response.time_s - target_onset_time_s
        else:
            rt_s = None
        fixation_results.append(
            FixationResponseRecord(
                event_index=event.event_index,
                start_frame=event.start_frame,
                duration_frames=event.duration_frames,
                responded=True,
                first_response_key=matched_response.key,
                response_frame=matched_response.frame_index,
                response_time_s=matched_response.time_s,
                target_onset_time_s=target_onset_time_s,
                rt_frames=rt_frames,
                rt_s=rt_s,
                outcome="hit",
            )
        )

    scored_responses: list[ResponseRecord] = []
    for index, response in enumerate(ordered_responses):
        matched_event_index = matched_response_indices.get(index)
        matched_event = (
            event_lookup.get(matched_event_index) if matched_event_index is not None else None
        )
        if matched_event is not None:
            rt_frames = _nonnegative_frame_rt(
                response_frame=response.frame_index,
                target_frame=matched_event.start_frame,
            )
            if onset_lookup is not None:
                assert response.time_s is not None
                rt_s = response.time_s - onset_lookup[matched_event.event_index].time_s
            else:
                rt_s = None
        else:
            rt_frames = None
            rt_s = None
        is_false_alarm = matched_event_index is None and response.key == response_key
        scored_responses.append(
            response.model_copy(
                update={
                    "response_index": index,
                    "matched_event_index": matched_event_index,
                    "rt_frames": rt_frames,
                    "rt_s": rt_s,
                    "correct": (matched_event_index is not None)
                    if response.key == response_key
                    else None,
                    "outcome": "hit"
                    if matched_event_index is not None
                    else ("false_alarm" if is_false_alarm else None),
                }
            )
        )

    return fixation_results, scored_responses


def _nonnegative_frame_rt(*, response_frame: int, target_frame: int) -> int | None:
    rt_frames = response_frame - target_frame
    return rt_frames if rt_frames >= 0 else None


def _complete_timestamp_onset_lookup(
    fixation_events: Sequence[FixationEvent],
    response_log: Sequence[ResponseRecord],
    *,
    response_key: str,
    fixation_target_onsets: Sequence[FixationTargetOnsetRecord],
    refresh_hz: float | None,
) -> dict[int, FixationTargetOnsetRecord] | None:
    """Return the complete actual-onset map required for timestamp scoring."""

    if refresh_hz is None or refresh_hz <= 0:
        return None
    event_lookup = {event.event_index: event for event in fixation_events}
    if len(event_lookup) != len(fixation_events):
        return None
    if len(fixation_target_onsets) != len(fixation_events):
        return None
    onset_lookup = {onset.event_index: onset for onset in fixation_target_onsets}
    if len(onset_lookup) != len(fixation_target_onsets):
        return None
    if onset_lookup.keys() != event_lookup.keys():
        return None
    if any(
        onset_lookup[event.event_index].frame_index != event.start_frame
        for event in fixation_events
    ):
        return None
    if any(response.key == response_key and response.time_s is None for response in response_log):
        return None
    return onset_lookup


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
    hit_rt_ms: list[float] = []
    for event in fixation_results:
        if event.outcome != "hit":
            continue
        if event.rt_s is not None:
            hit_rt_ms.append(event.rt_s * 1000.0)
        elif event.rt_frames is not None:
            hit_rt_ms.append((event.rt_frames / refresh_hz) * 1000.0)
    mean_rt_ms = math.fsum(hit_rt_ms) / len(hit_rt_ms) if hit_rt_ms else None
    return FixationTaskSummary(
        total_targets=total_targets,
        hit_count=hit_count,
        miss_count=miss_count,
        false_alarm_count=false_alarm_count,
        accuracy_percent=accuracy_percent,
        mean_rt_ms=mean_rt_ms,
    )
