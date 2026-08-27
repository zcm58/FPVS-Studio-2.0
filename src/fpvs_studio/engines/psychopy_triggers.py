"""Trigger helpers for the PsychoPy engine."""

from __future__ import annotations

from typing import Any

from fpvs_studio.core.run_spec import RunSpec, TriggerEvent
from fpvs_studio.core.trigger_codes import validate_event_trigger_code
from fpvs_studio.triggers.base import TriggerBackend


def build_trigger_lookup(run_spec: RunSpec) -> dict[int, tuple[TriggerEvent, ...]]:
    """Validate and index compiled trigger events before timed playback."""

    trigger_lookup: dict[int, list[TriggerEvent]] = {}
    for trigger_event in run_spec.trigger_events:
        validate_event_trigger_code(trigger_event.code, label=trigger_event.label)
        if not trigger_event.label.strip():
            raise ValueError("Trigger labels may not be blank.")
        if trigger_event.frame_index in trigger_lookup:
            raise ValueError(
                "A compiled display frame may contain at most one trigger marker."
            )
        trigger_lookup.setdefault(trigger_event.frame_index, []).append(trigger_event)
    return {frame_index: tuple(events) for frame_index, events in trigger_lookup.items()}


def emit_trigger(
    *,
    trigger_backend: TriggerBackend,
    active_run_clock: Any | None,
    code: int,
    label: str,
    frame_index: int,
) -> None:
    """Emit one trigger with the current run-clock time when available."""

    time_s = active_run_clock.getTime() if active_run_clock is not None else None
    trigger_backend.send_prevalidated_trigger(
        code,
        frame_index=frame_index,
        label=label,
        time_s=time_s,
    )
