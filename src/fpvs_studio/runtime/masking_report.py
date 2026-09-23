"""Durable compiled masking provenance and explicitly planned event exports."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from uuid import uuid4

from fpvs_studio.core.execution import RunExecutionSummary
from fpvs_studio.core.paths import logs_dir
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.serialization import atomic_text_write
from fpvs_studio.core.session_plan import SessionEntry, SessionPlan
from fpvs_studio.runtime.reporting_lock import project_reporting_lock

MASKING_SCENE_EVENTS_FILENAME = "masking_scene_events_v1.csv"
MASKING_PLAN_DIRNAME = "masking-scene-plans"
MASKING_SCENE_EVENTS_HEADER = [
    "schema_version", "project_id", "project_name", "session_id", "run_id", "condition_id",
    "condition_name", "participant_number", "participant_session_number", "block_index",
    "global_order_index", "run_seed", "target_id", "requested_soa_ms", "soa_frames",
    "planned_soa_ms", "refresh_hz", "event_index", "role", "visual_id", "visual_kind",
    "image_path", "text", "units", "position_x", "position_y", "width", "height",
    "text_height", "font", "rgb", "line_rgb", "line_width", "opacity", "circle_edges",
    "wrap_width", "interpolate", "background_rgb", "planned_onset_frame", "duration_frames",
    "planned_onset_s", "planned_duration_ms", "onset_frame_completed", "completed_frames",
    "run_aborted", "observed_onset_s", "observed_onset_source",
]


def write_masking_plan_checkpoint(
    project_root: Path, session_plan: SessionPlan, *, participant_number: str,
    participant_session_number: int | None = None,
) -> Path | None:
    """Save the compiled plan before participant input; retain it in both export modes.

    This is intended presentation, never evidence that stimuli were displayed. The
    ordinary task journals retain responses separately. Numbered visits are idempotent;
    unnumbered direct callers receive a new file so previous execution plans survive.
    """
    if not any(entry.run_spec.scene_stream is not None for entry in session_plan.ordered_entries()):
        return None
    payload = json.dumps({
        "schema_version": "1.0.0",
        "record_kind": "compiled_masking_plan",
        "planned_only": True,
        "participant_number": participant_number,
        "participant_session_number": participant_session_number,
        "session_plan": session_plan.model_dump(mode="json"),
    }, ensure_ascii=False, indent=2)
    identity = f"{participant_number}\0{participant_session_number}\0{session_plan.session_id}"
    key = (hashlib.sha256(identity.encode()).hexdigest()[:24]
           if participant_session_number is not None else uuid4().hex)
    path = logs_dir(project_root) / MASKING_PLAN_DIRNAME / f"{key}.json"
    with project_reporting_lock(project_root):
        if path.is_file():
            if path.read_text(encoding="utf-8") != payload:
                raise ValueError(
                    "A different masking plan already belongs to this participant visit."
                )
        else:
            atomic_text_write(path, payload)
    return path


def _safe_csv_text(value: object) -> object:
    if not isinstance(value, str):
        return value
    return f"'{value}" if value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")) else value


def masking_scene_event_rows(
    run_spec: RunSpec, summary: RunExecutionSummary, *, entry: SessionEntry | None = None,
) -> Iterable[tuple[object, ...]]:
    """Emit native appearance and frame plans without fabricating observed timestamps.

    Completed-frame evidence identifies whether playback reached an event's onset;
    it does not establish light onset. The engine currently records no per-scene
    flip timestamps, so observed columns remain explicitly unavailable. Frame interval
    accumulation is not substituted for an observed stimulus onset.
    """
    scene = run_spec.scene_stream
    if scene is None:
        return
    visuals = {visual.visual_id: visual for visual in scene.visuals}
    refresh_hz = run_spec.display.refresh_hz
    for event_index, event in enumerate(scene.events):
        visual = visuals[event.visual_id]
        yield tuple(_safe_csv_text(value) for value in (
            "1.0.0", run_spec.project_id, run_spec.project_name, summary.session_id or "",
            run_spec.run_id, run_spec.condition.condition_id, run_spec.condition.name,
            summary.participant_number or "", summary.participant_session_number,
            entry.block_index if entry is not None else None,
            entry.global_order_index if entry is not None else None,
            run_spec.random_seed, scene.target_id, scene.requested_soa_ms, scene.soa_frames,
            scene.soa_frames * 1000.0 / refresh_hz, refresh_hz, event_index, event.role,
            visual.visual_id, visual.kind, visual.image_path, visual.text, visual.units,
            *visual.position, visual.size[0] if visual.size is not None else None,
            visual.size[1] if visual.size is not None else None,
            visual.text_height, visual.font, json.dumps(visual.rgb),
            json.dumps(visual.line_rgb) if visual.line_rgb is not None else None,
            visual.line_width, visual.opacity, visual.edges, visual.wrap_width,
            visual.interpolate, json.dumps(scene.background_rgb), event.start_frame,
            event.duration_frames, event.start_frame / refresh_hz,
            event.duration_frames * 1000.0 / refresh_hz,
            event.start_frame < summary.completed_frames, summary.completed_frames,
            summary.aborted, None, "not_recorded",
        ))
