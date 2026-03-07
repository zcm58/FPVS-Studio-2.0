"""Runtime-side preflight validation for run and session execution."""

from __future__ import annotations

from pathlib import Path

from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.engines.base import PresentationEngine


class PreflightError(ValueError):
    """Raised when runtime prerequisites are not satisfied."""


def _validate_stimulus_timing(run_spec: RunSpec) -> None:
    stimulus_sequence = run_spec.stimulus_sequence
    if len(stimulus_sequence) != run_spec.condition.total_stimuli:
        raise PreflightError(
            "Run preflight failed because stimulus_sequence length does not "
            "match condition.total_stimuli."
        )
    if not stimulus_sequence:
        raise PreflightError(
            "Run preflight failed because the compiled run contains no stimulus events."
        )

    expected_start_frame = 0
    for expected_index, event in enumerate(stimulus_sequence):
        if event.sequence_index != expected_index:
            raise PreflightError(
                "Run preflight failed because stimulus sequence_index values are not contiguous."
            )
        if event.on_start_frame != expected_start_frame:
            raise PreflightError(
                "Run preflight failed because stimulus on_start_frame values "
                "do not align with frames_per_stimulus."
            )
        if (
            event.on_frames != run_spec.display.on_frames
            or event.off_frames != run_spec.display.off_frames
        ):
            raise PreflightError(
                "Run preflight failed because stimulus event timing does not "
                "match the compiled display timing."
            )
        expected_start_frame += run_spec.display.frames_per_stimulus

    if expected_start_frame != run_spec.display.total_frames:
        raise PreflightError(
            "Run preflight failed because stimulus timing does not cover the "
            "compiled total frame count."
        )


def _validate_fixation_timing(run_spec: RunSpec) -> None:
    previous_end_frame = -1
    ordered_events = sorted(run_spec.fixation_events, key=lambda item: item.event_index)
    for expected_index, event in enumerate(ordered_events):
        if event.event_index != expected_index:
            raise PreflightError(
                "Run preflight failed because fixation event indices are not "
                "contiguous."
            )
        if (
            run_spec.fixation.target_duration_frames > 0
            and event.duration_frames != run_spec.fixation.target_duration_frames
        ):
            raise PreflightError(
                "Run preflight failed because fixation event duration does not "
                "match fixation.target_duration_frames."
            )
        event_end_frame = event.start_frame + event.duration_frames
        if event_end_frame > run_spec.display.total_frames:
            raise PreflightError(
                "Run preflight failed because a fixation event extends beyond "
                "the compiled run duration."
            )
        if event.start_frame < previous_end_frame:
            raise PreflightError(
                "Run preflight failed because fixation events overlap or are "
                "out of order."
            )
        previous_end_frame = event_end_frame


def _validate_trigger_timing(run_spec: RunSpec) -> None:
    for trigger_event in run_spec.trigger_events:
        if trigger_event.frame_index >= run_spec.display.total_frames:
            raise PreflightError(
                "Run preflight failed because a trigger event falls outside "
                "the compiled run duration."
            )


def preflight_run_spec(
    project_root: Path,
    run_spec: RunSpec,
    *,
    engine: PresentationEngine,
) -> None:
    """Validate one run spec before execution starts."""

    missing_assets = sorted(
        {
            event.image_path
            for event in run_spec.stimulus_sequence
            if not (project_root / Path(event.image_path)).is_file()
        }
    )
    if missing_assets:
        raise PreflightError(
            "Run preflight failed because referenced assets are missing: "
            + ", ".join(missing_assets[:5])
        )
    if (
        run_spec.display.on_frames + run_spec.display.off_frames
        != run_spec.display.frames_per_stimulus
    ):
        raise PreflightError(
            "Run preflight failed because on/off frame timing does not match "
            "frames_per_stimulus."
        )
    _validate_stimulus_timing(run_spec)
    _validate_fixation_timing(run_spec)
    _validate_trigger_timing(run_spec)
    display_report = engine.validate_run_spec(run_spec)
    if not display_report.compatible:
        raise PreflightError(
            "Run preflight failed because display timing is incompatible: "
            f"{'; '.join(display_report.errors)}"
        )


def preflight_session_plan(
    project_root: Path,
    session_plan: SessionPlan,
    *,
    engine: PresentationEngine,
) -> None:
    """Validate every run in a session plan before execution starts."""

    ordered_entries = session_plan.ordered_entries()
    expected_indices = list(range(len(ordered_entries)))
    actual_indices = [entry.global_order_index for entry in ordered_entries]
    if actual_indices != expected_indices:
        raise PreflightError(
            "Session preflight failed because session entry ordering is invalid."
        )
    for entry in ordered_entries:
        preflight_run_spec(project_root, entry.run_spec, engine=engine)
