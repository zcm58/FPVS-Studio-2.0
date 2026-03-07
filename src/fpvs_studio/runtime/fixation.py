"""Runtime-side fixation response scoring helpers."""

from __future__ import annotations

from collections.abc import Sequence

from fpvs_studio.core.execution import FixationResponseRecord, ResponseRecord
from fpvs_studio.core.run_spec import FixationEvent


def score_fixation_responses(
    fixation_events: Sequence[FixationEvent],
    response_log: Sequence[ResponseRecord],
) -> tuple[list[FixationResponseRecord], list[ResponseRecord]]:
    """Score response events against compiled fixation targets."""

    matched_response_indices: dict[int, int] = {}
    fixation_results: list[FixationResponseRecord] = []

    ordered_events = sorted(fixation_events, key=lambda item: item.event_index)
    ordered_responses = list(response_log)

    for fixation_event in ordered_events:
        event_end_frame = fixation_event.start_frame + fixation_event.duration_frames
        matched_index: int | None = None
        matched_response: ResponseRecord | None = None

        for index, response in enumerate(ordered_responses):
            if index in matched_response_indices:
                continue
            if fixation_event.start_frame <= response.frame_index < event_end_frame:
                matched_index = index
                matched_response = response
                break

        if matched_response is None or matched_index is None:
            fixation_results.append(
                FixationResponseRecord(
                    event_index=fixation_event.event_index,
                    start_frame=fixation_event.start_frame,
                    duration_frames=fixation_event.duration_frames,
                    responded=False,
                    outcome="miss",
                )
            )
            continue

        matched_response_indices[matched_index] = fixation_event.event_index
        fixation_results.append(
            FixationResponseRecord(
                event_index=fixation_event.event_index,
                start_frame=fixation_event.start_frame,
                duration_frames=fixation_event.duration_frames,
                responded=True,
                first_response_key=matched_response.key,
                response_frame=matched_response.frame_index,
                response_time_s=matched_response.time_s,
                rt_frames=matched_response.frame_index - fixation_event.start_frame,
                outcome="hit",
            )
        )

    scored_responses: list[ResponseRecord] = []
    for index, response in enumerate(ordered_responses):
        matched_event_index = matched_response_indices.get(index)
        matched_event = (
            next(
                event for event in fixation_results if event.event_index == matched_event_index
            )
            if matched_event_index is not None
            else None
        )
        rt_frames = matched_event.rt_frames if matched_event is not None else None
        scored_responses.append(
            response.model_copy(
                update={
                    "response_index": index,
                    "matched_event_index": matched_event_index,
                    "rt_frames": rt_frames,
                    "correct": matched_event_index is not None,
                }
            )
        )

    return fixation_results, scored_responses
