"""Trigger helpers for the PsychoPy engine."""

from __future__ import annotations

from typing import Any

from fpvs_studio.core.run_spec import RunSpec, TriggerEvent
from fpvs_studio.triggers.base import TriggerBackend


def build_trigger_lookup(run_spec: RunSpec) -> dict[int, tuple[TriggerEvent, ...]]:
    """Index compiled trigger events by frame."""

    trigger_lookup: dict[int, list[TriggerEvent]] = {}
    for trigger_event in run_spec.trigger_events:
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
    trigger_backend.send_trigger(
        code,
        frame_index=frame_index,
        label=label,
        time_s=time_s,
    )
