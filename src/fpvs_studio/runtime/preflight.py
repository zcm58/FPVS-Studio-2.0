"""Runtime preflight validation before execution begins. It checks compiled RunSpec and
SessionPlan artifacts against asset availability and conservative display-timing
expectations before engine launch. This module is a launch gatekeeper only; session
ordering stays in SessionPlan and playback stays with runtime orchestration plus the
engine."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from PIL import Image

from fpvs_studio.core.enums import DutyCycleMode, StimulusModality
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.core.task_models import (
    TaskItemModality,
    TaskModuleSpec,
    validate_task_module_repeat_capacity,
)
from fpvs_studio.core.validation import (
    approved_monitor_refresh_rate,
    validate_display_refresh,
)
from fpvs_studio.engines.base import PresentationEngine
from fpvs_studio.runtime.display_refresh import (
    DisplayRefreshVerificationError,
    verify_primary_display_refresh,
)


class PreflightError(ValueError):
    """Raised when runtime prerequisites are not satisfied."""


def _strict_timing_enabled(runtime_options: Mapping[str, object] | None) -> bool:
    return bool((runtime_options or {}).get("strict_timing", True))


def _refresh_verification_enabled(runtime_options: Mapping[str, object] | None) -> bool:
    return bool((runtime_options or {}).get("verify_refresh_rate", False))


def _verify_connected_refresh_rate(
    run_specs: list[RunSpec],
    *,
    engine: PresentationEngine,
    runtime_options: Mapping[str, object] | None,
) -> None:
    if not run_specs or not _refresh_verification_enabled(runtime_options):
        return
    try:
        verification = verify_primary_display_refresh(
            engine,
            runtime_options=runtime_options,
        )
    except DisplayRefreshVerificationError as exc:
        raise PreflightError(
            f"Run preflight failed because display refresh verification did not pass: {exc}"
        ) from exc

    mismatched_rates = sorted(
        {
            run_spec.display.refresh_hz
            for run_spec in run_specs
            if approved_monitor_refresh_rate(run_spec.display.refresh_hz)
            != verification.approved_hz
        }
    )
    if mismatched_rates:
        configured_text = ", ".join(f"{refresh_hz:g} Hz" for refresh_hz in mismatched_rates)
        windows_mode = verification.windows_mode
        raise PreflightError(
            "Run preflight failed because Windows reports display mode "
            f"{windows_mode.hz:.6f} Hz ({windows_mode.fraction_text}), verified by "
            f"PsychoPy at {verification.psychopy_measured_hz:.3f} Hz, but the compiled "
            f"session expects {configured_text}. "
            "Return to Experiment settings and detect the display refresh rate again."
        )


def _validate_display_refresh_timing(run_spec: RunSpec) -> None:
    duty_cycle_mode = (
        DutyCycleMode.BLANK_50 if run_spec.display.off_frames > 0 else DutyCycleMode.CONTINUOUS
    )
    display_report = validate_display_refresh(
        run_spec.display.refresh_hz,
        duty_cycle_mode=duty_cycle_mode,
        base_hz=run_spec.condition.base_hz,
        oddball_every_n=run_spec.condition.oddball_every_n,
    )
    if not display_report.compatible:
        raise PreflightError(
            "Run preflight failed because display timing is incompatible: "
            f"{'; '.join(display_report.errors)}"
        )
    if (
        display_report.frames_per_cycle is not None
        and display_report.frames_per_cycle != run_spec.display.frames_per_stimulus
    ):
        raise PreflightError(
            "Run preflight failed because compiled frames_per_stimulus does not match "
            "the requested refresh rate and base frequency."
        )


def _validate_stimulus_timing(run_spec: RunSpec) -> None:
    stimulus_sequence = run_spec.stimulus_sequence
    if len(stimulus_sequence) != run_spec.condition.total_stimuli:
        raise PreflightError(
            "Run preflight failed because compiled stimulus event count does not "
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
                "Run preflight failed because stimulus event indices are not contiguous."
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


def _validate_stimulus_payloads(run_spec: RunSpec) -> None:
    stimulus_payloads: dict[str, tuple[StimulusModality, str | None, str | None]] = {}
    for event in run_spec.stimulus_sequence:
        if event.stimulus_modality == StimulusModality.IMAGE:
            if event.image_path is None or event.text is not None:
                raise PreflightError(
                    "Run preflight failed because an image stimulus event has an "
                    "inconsistent payload."
                )
        elif event.stimulus_modality == StimulusModality.WORD:
            if event.text is None or not event.text.strip() or event.image_path is not None:
                raise PreflightError(
                    "Run preflight failed because a word stimulus event has an "
                    "inconsistent payload."
                )
        else:
            raise PreflightError(
                "Run preflight failed because a stimulus event has an unknown modality."
            )
        payload = (event.stimulus_modality, event.image_path, event.text)
        previous_payload = stimulus_payloads.setdefault(event.stimulus_id, payload)
        if previous_payload != payload:
            raise PreflightError(
                "Run preflight failed because a compiled stimulus id maps to multiple payloads."
            )

        if run_spec.presentation is None:
            continue
        role_presentation = getattr(run_spec.presentation, event.role)
        if event.stimulus_modality == StimulusModality.IMAGE:
            if role_presentation.image_geometry is None or role_presentation.text is not None:
                raise PreflightError(
                    "Run preflight failed because an image event has non-image "
                    "presentation settings."
                )
            if event.text_height_value is not None:
                raise PreflightError(
                    "Run preflight failed because an image event contains a word height."
                )
        elif (
            role_presentation.text is None
            or role_presentation.image_geometry is not None
            or event.text_height_value is None
        ):
            raise PreflightError(
                "Run preflight failed because a word event is missing resolved text "
                "presentation settings or height."
            )


def _validate_fixation_timing(run_spec: RunSpec) -> None:
    previous_end_frame = -1
    ordered_events = sorted(run_spec.fixation_events, key=lambda item: item.event_index)
    for expected_index, event in enumerate(ordered_events):
        if event.event_index != expected_index:
            raise PreflightError(
                "Run preflight failed because fixation event indices are not contiguous."
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
                "Run preflight failed because fixation events overlap or are out of order."
            )
        previous_end_frame = event_end_frame


def _validate_trigger_timing(run_spec: RunSpec) -> None:
    for trigger_event in run_spec.trigger_events:
        if trigger_event.frame_index >= run_spec.display.total_frames:
            raise PreflightError(
                "Run preflight failed because a trigger event falls outside "
                "the compiled run duration."
            )


def _resolve_project_image_path(project_root: Path, image_path: str) -> Path:
    relative_path = Path(image_path)
    if relative_path.is_absolute():
        raise PreflightError(
            "Run preflight failed because an image stimulus path is not project-relative: "
            f"{image_path}"
        )
    root = project_root.resolve()
    absolute_path = (project_root / relative_path).resolve()
    try:
        absolute_path.relative_to(root)
    except ValueError as exc:
        raise PreflightError(
            "Run preflight failed because an image stimulus path escapes the project root: "
            f"{image_path}"
        ) from exc
    return absolute_path


def _validate_image_assets(
    project_root: Path,
    run_spec: RunSpec,
    *,
    decode: bool,
) -> None:
    image_references: dict[str, set[tuple[str, int, int]]] = {}
    for event in run_spec.stimulus_sequence:
        if event.stimulus_modality != StimulusModality.IMAGE or event.image_path is None:
            continue
        expected_resolutions = image_references.setdefault(event.image_path, set())
        if run_spec.presentation is None:
            continue
        role_presentation = getattr(run_spec.presentation, event.role)
        if role_presentation.image_geometry is None:
            continue
        source_resolution = role_presentation.image_geometry.source_resolution
        expected_resolutions.add(
            (event.role, source_resolution.width_px, source_resolution.height_px)
        )
    missing_assets: list[str] = []
    unloadable_assets: list[str] = []
    resolution_mismatches: list[str] = []
    for image_path in sorted(image_references):
        absolute_path = _resolve_project_image_path(project_root, image_path)
        if not absolute_path.is_file():
            missing_assets.append(image_path)
            continue
        if not decode:
            continue
        try:
            with Image.open(absolute_path) as image:
                image.load()
                decoded_width_px, decoded_height_px = image.size
        except (OSError, ValueError) as exc:
            unloadable_assets.append(f"{image_path} ({exc})")
            continue
        for role, expected_width_px, expected_height_px in sorted(
            image_references[image_path]
        ):
            if (decoded_width_px, decoded_height_px) == (
                expected_width_px,
                expected_height_px,
            ):
                continue
            resolution_mismatches.append(
                f"{image_path} ({role}: decoded {decoded_width_px}x{decoded_height_px}, "
                f"compiled {expected_width_px}x{expected_height_px})"
            )

    if missing_assets:
        raise PreflightError(
            "Run preflight failed because referenced assets are missing: "
            + ", ".join(missing_assets[:5])
        )
    if unloadable_assets:
        raise PreflightError(
            "Run preflight failed because referenced image assets could not be "
            "decoded: " + ", ".join(unloadable_assets[:5])
        )
    if resolution_mismatches:
        raise PreflightError(
            "Run preflight failed because decoded image dimensions do not match "
            "compiled role source resolutions: " + ", ".join(resolution_mismatches[:5])
        )


def _task_image_paths(modules: list[TaskModuleSpec]) -> set[str]:
    paths: set[str] = set()
    for module in modules:
        for step in module.steps:
            paths.update(
                item.image_path
                for item in step.items
                if item.modality == TaskItemModality.IMAGE and item.image_path is not None
            )
            paths.update(
                option.image_path
                for question in step.questions
                for option in question.options
                if option.image_path is not None
            )
    return paths


def _validate_task_assets(
    project_root: Path,
    modules: list[TaskModuleSpec],
    *,
    decode: bool,
) -> None:
    missing_assets: list[str] = []
    unloadable_assets: list[str] = []
    for module in modules:
        try:
            validate_task_module_repeat_capacity(module)
        except ValueError as exc:
            raise PreflightError(
                "Session preflight failed because task repeat capacity is invalid: "
                f"{exc}"
            ) from exc
    for image_path in sorted(_task_image_paths(modules)):
        absolute_path = _resolve_project_image_path(project_root, image_path)
        if not absolute_path.is_file():
            missing_assets.append(image_path)
            continue
        if not decode:
            continue
        try:
            with Image.open(absolute_path) as image:
                image.load()
        except (OSError, ValueError) as exc:
            unloadable_assets.append(f"{image_path} ({exc})")
    if missing_assets:
        raise PreflightError(
            "Session preflight failed because referenced task assets are missing: "
            + ", ".join(missing_assets[:5])
        )
    if unloadable_assets:
        raise PreflightError(
            "Session preflight failed because referenced task image assets could not be "
            "decoded: " + ", ".join(unloadable_assets[:5])
        )


def _validate_task_engine_support(
    engine: PresentationEngine,
    modules: list[TaskModuleSpec],
) -> None:
    if modules and type(engine).render_task_step is PresentationEngine.render_task_step:
        raise PreflightError(
            f"Session preflight failed because presentation engine '{engine.engine_id}' "
            "does not support modular condition tasks."
        )


def preflight_run_spec(
    project_root: Path,
    run_spec: RunSpec,
    *,
    engine: PresentationEngine,
    runtime_options: Mapping[str, object] | None = None,
    decode_image_assets: bool = False,
    verify_connected_refresh: bool = True,
) -> None:
    """Validate one run spec before execution starts."""

    strict_timing = _strict_timing_enabled(runtime_options)
    if strict_timing and not bool((runtime_options or {}).get("fullscreen", True)):
        raise PreflightError(
            "Run preflight failed because strict timing requires fullscreen presentation."
        )
    if strict_timing and bool((runtime_options or {}).get("variable_refresh_enabled", False)):
        raise PreflightError(
            "Run preflight failed because strict timing does not support variable-refresh displays."
        )

    _validate_image_assets(project_root, run_spec, decode=decode_image_assets)
    if (
        run_spec.display.on_frames + run_spec.display.off_frames
        != run_spec.display.frames_per_stimulus
    ):
        raise PreflightError(
            "Run preflight failed because on/off frame timing does not match frames_per_stimulus."
        )
    _validate_display_refresh_timing(run_spec)
    _validate_stimulus_timing(run_spec)
    _validate_stimulus_payloads(run_spec)
    _validate_fixation_timing(run_spec)
    _validate_trigger_timing(run_spec)
    display_report = engine.validate_run_spec(run_spec)
    if not display_report.compatible:
        raise PreflightError(
            "Run preflight failed because display timing is incompatible: "
            f"{'; '.join(display_report.errors)}"
        )
    blocking_display_warnings = [
        warning
        for warning in display_report.warnings
        if not (
            not display_report.timing_is_exact and warning.startswith("Approximate frame timing:")
        )
    ]
    if strict_timing and blocking_display_warnings:
        raise PreflightError(
            "Run preflight failed because strict timing does not allow display warnings: "
            f"{'; '.join(blocking_display_warnings)}"
        )
    if verify_connected_refresh:
        _verify_connected_refresh_rate(
            [run_spec],
            engine=engine,
            runtime_options=runtime_options,
        )


def preflight_session_plan(
    project_root: Path,
    session_plan: SessionPlan,
    *,
    engine: PresentationEngine,
    runtime_options: Mapping[str, object] | None = None,
    decode_image_assets: bool = False,
) -> None:
    """Validate every run in a session plan before execution starts."""

    ordered_entries = session_plan.ordered_entries()
    expected_indices = list(range(len(ordered_entries)))
    actual_indices = [entry.global_order_index for entry in ordered_entries]
    if actual_indices != expected_indices:
        raise PreflightError("Session preflight failed because session entry ordering is invalid.")
    for entry in ordered_entries:
        preflight_run_spec(
            project_root,
            entry.run_spec,
            engine=engine,
            runtime_options=runtime_options,
            decode_image_assets=decode_image_assets,
            verify_connected_refresh=False,
        )
        task_modules = [*entry.pre_tasks, *entry.post_tasks]
        _validate_task_assets(
            project_root,
            task_modules,
            decode=decode_image_assets,
        )
        _validate_task_engine_support(engine, task_modules)
    _verify_connected_refresh_rate(
        [entry.run_spec for entry in ordered_entries],
        engine=engine,
        runtime_options=runtime_options,
    )
