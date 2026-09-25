"""Runtime preflight validation before execution begins. It checks compiled RunSpec and
SessionPlan artifacts against asset availability and conservative display-timing
expectations before engine launch. This module is a launch gatekeeper only; session
ordering stays in SessionPlan and playback stays with runtime orchestration plus the
engine."""

from __future__ import annotations

from collections.abc import Mapping
from math import isclose
from pathlib import Path

from PIL import Image

from fpvs_studio.core.attentional_blink_stream import (
    GRID_TOLERANCE,
    preview_attentional_blink_stream,
)
from fpvs_studio.core.contrast_modulation import is_sinusoidal_neutral_background
from fpvs_studio.core.enums import DutyCycleMode, StimulusModality
from fpvs_studio.core.experiment_categories import RETIRED_IMAGE_PAIR_MESSAGE
from fpvs_studio.core.paths import resolve_project_relative_path
from fpvs_studio.core.run_spec import (
    AttentionalBlinkRunSpec,
    AttentionalBlinkStreamRunSpec,
    RunSpec,
    event_presentation,
)
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
        display_mode = verification.display_mode
        raise PreflightError(
            f"Run preflight failed because {display_mode.platform_name} reports display mode "
            f"{display_mode.mode_text}, verified by "
            f"PsychoPy at {verification.psychopy_measured_hz:.3f} Hz, but the compiled "
            f"session expects {configured_text}. "
            "Return to Experiment settings and detect the display refresh rate again."
        )


def _validate_display_refresh_timing(run_spec: RunSpec) -> None:
    display_report = validate_display_refresh(
        run_spec.display.refresh_hz,
        duty_cycle_mode=run_spec.display.duty_cycle_mode,
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


def _validate_sinusoidal_presentation(run_spec: RunSpec) -> None:
    if run_spec.display.duty_cycle_mode != DutyCycleMode.SINUSOIDAL:
        return
    if run_spec.condition.stimulus_modality != StimulusModality.IMAGE or any(
        event.stimulus_modality != StimulusModality.IMAGE
        for event in run_spec.stimulus_sequence
    ):
        raise PreflightError(
            "Run preflight failed because Contrast Modulation supports image stimuli only."
        )
    if not is_sinusoidal_neutral_background(run_spec.display.background_color):
        raise PreflightError(
            "Run preflight failed because Contrast Modulation requires the presentation "
            "background to be Neutral Gray (#808080)."
        )
    if (
        run_spec.display.on_frames != run_spec.display.frames_per_stimulus
        or run_spec.display.off_frames != 0
        or not isclose(run_spec.display.duty_cycle, 1.0, rel_tol=0.0, abs_tol=1e-9)
    ):
        raise PreflightError(
            "Run preflight failed because Contrast Modulation must retain the image for "
            "the full stimulus cycle (on_frames=frames_per_stimulus, off_frames=0)."
        )


def _validate_stimulus_timing(run_spec: RunSpec) -> None:
    if run_spec.scene_stream is not None:
        _validate_scene_timing(run_spec)
        return
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

    if run_spec.attentional_blink is not None:
        _validate_attentional_blink_timing(run_spec)
        return
    if any(event.phase is not None or event.slot_index is not None for event in stimulus_sequence):
        raise PreflightError("Attentional-blink event phases require compiled target-pair timing.")

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


def _validate_attentional_blink_timing(run_spec: RunSpec) -> None:
    timing = run_spec.attentional_blink
    assert timing is not None
    if isinstance(timing, AttentionalBlinkStreamRunSpec):
        _validate_attentional_blink_stream_timing(run_spec, timing)
        return
    raise PreflightError(RETIRED_IMAGE_PAIR_MESSAGE)


def _validate_attentional_blink_stream_timing(
    run_spec: RunSpec, timing: AttentionalBlinkStreamRunSpec,
) -> None:
    """Reject malformed character streams before preparing any display resources."""

    display = run_spec.display
    condition = run_spec.condition
    frames = timing.frames_per_item
    slots = timing.cycle_slots
    try:
        preview = preview_attentional_blink_stream(
            refresh_hz=display.refresh_hz, base_hz=condition.base_hz,
            cycle_slots=slots, soa_ms=timing.requested_soa_ms,
            t2_slot_index=timing.t2_slot_index,
        )
    except ValueError as exc:
        raise PreflightError(f"Attentional-blink letter-stream timing is invalid: {exc}") from exc
    if (
        condition.stimulus_modality != StimulusModality.WORD
        or display.duty_cycle_mode != DutyCycleMode.CONTINUOUS
        or run_spec.presentation is None
        or display.on_frames != frames
        or display.frames_per_stimulus != frames
        or display.off_frames != 0
        or not isclose(display.duty_cycle, 1.0, rel_tol=0.0, abs_tol=1e-9)
    ):
        raise PreflightError(
            "Attentional-blink letter streams require continuous text presentation."
        )
    if (
        condition.oddball_every_n != slots
        or frames != preview.frames_per_item
        or timing.t1_slot_index != preview.description.t1_slot_index
        or timing.lag != preview.description.lag
        or not isclose(timing.achieved_soa_ms, preview.achieved_soa_ms,
                       rel_tol=0.0, abs_tol=GRID_TOLERANCE)
    ):
        raise PreflightError(
            "Attentional-blink SOA and item timing must match the exact frame grid."
        )
    repeats = condition.total_oddball_cycles
    if (
        repeats < 1
        or len(run_spec.stimulus_sequence) != repeats * slots
        or display.total_frames != repeats * slots * frames
    ):
        raise PreflightError("Attentional-blink letter streams must cover every complete cycle.")
    first_symbol = run_spec.stimulus_sequence[0].text or ""
    letter_distractors = len(first_symbol) == 1 and "A" <= first_symbol <= "Z"
    base_symbols = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if letter_distractors else "0123456789"
    target_symbols = "0123456789" if letter_distractors else "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    previous_distractor: str | None = None
    t1_symbol: str | None = None
    for index, event in enumerate(run_spec.stimulus_sequence):
        cycle_index, slot_index = divmod(index, slots)
        phase = preview.description.roles[slot_index]
        if (
            event.sequence_index != index
            or event.slot_index != index
            or event.cycle_index != cycle_index
            or event.phase != phase
            or event.role != ("base" if phase == "base" else "oddball")
            or event.stimulus_modality != StimulusModality.WORD
            or event.is_blank
            or event.on_start_frame != index * frames
            or event.on_frames != frames
            or event.off_frames != 0
        ):
            raise PreflightError(
                f"Attentional-blink stream event {index} has invalid phase, slot, or frame timing."
            )
        symbol = event.text or ""
        allowed_symbols = base_symbols if phase == "base" else target_symbols
        if len(symbol) != 1 or symbol not in allowed_symbols:
            raise PreflightError(
                "Attentional-blink streams require single digits and uppercase letters."
            )
        if phase == "base":
            if symbol == previous_distractor:
                raise PreflightError(
                    "Attentional-blink streams cannot repeat adjacent distractors."
                )
            previous_distractor = symbol
        else:
            previous_distractor = None
            if phase == "t1":
                t1_symbol = symbol
            elif symbol == t1_symbol:
                raise PreflightError(
                    "Attentional-blink T1 and T2 symbols must differ within each cycle."
                )
    _validate_attentional_blink_markers(run_spec, timing.t2_trigger_code)
    starts = [event for event in run_spec.trigger_events if event.label == "condition_start"]
    t1_codes = {event.code for event in run_spec.trigger_events if event.label == "t1_onset"}
    if (
        len(starts) != 1
        or starts[0].frame_index != 0
        or starts[0].code != condition.trigger_code
        or len(t1_codes) != 1
        or starts[0].code in t1_codes
        or len({event.frame_index for event in run_spec.trigger_events})
        != len(run_spec.trigger_events)
        or any(event.label not in ("condition_start", "t1_onset", "t2_onset")
               for event in run_spec.trigger_events)
    ):
        raise PreflightError(
            "Attentional-blink stream markers need one condition start and distinct target codes."
        )


def _validate_attentional_blink_markers(run_spec: RunSpec, t2_trigger_code: int) -> None:
    for phase, label in (("t1", "t1_onset"), ("t2", "t2_onset")):
        expected_frames = [
            event.on_start_frame for event in run_spec.stimulus_sequence if event.phase == phase
        ]
        markers = [event for event in run_spec.trigger_events if event.label == label]
        if sorted(event.frame_index for event in markers) != expected_frames:
            raise PreflightError(f"Attentional-blink {label} markers do not match target onsets.")
        if any(
            (event.code != t2_trigger_code if phase == "t2"
             else event.code == t2_trigger_code)
            for event in markers
        ):
            raise PreflightError("Attentional-blink T1 and T2 marker codes must remain distinct.")
    if any(
        event.label == "condition_start" and event.code == t2_trigger_code
        for event in run_spec.trigger_events
    ):
        raise PreflightError("The T2 marker code must differ from the condition-start marker.")


def _validate_stimulus_payloads(run_spec: RunSpec) -> None:
    stimulus_payloads: dict[str, tuple[StimulusModality, str | None, str | None]] = {}
    for event in run_spec.stimulus_sequence:
        if event.is_blank:
            if (not isinstance(run_spec.attentional_blink, AttentionalBlinkRunSpec)
                    or event.phase != "separator"
                    or event.image_path is not None or event.text is not None):
                raise PreflightError("Invalid blank ISI payload.")
            continue
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

        role_presentation = event_presentation(run_spec, event)
        if role_presentation is None:
            continue
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
    if not run_spec.trigger_events:
        raise PreflightError("Run preflight failed because the compiled trigger schedule is empty.")
    for trigger_event in run_spec.trigger_events:
        if trigger_event.frame_index >= run_spec.display.total_frames:
            raise PreflightError(
                "Run preflight failed because a trigger event falls outside "
                "the compiled run duration."
            )


def _validate_scene_timing(run_spec: RunSpec) -> None:
    scene = run_spec.scene_stream
    assert scene is not None
    try:
        scene.validate_frame_bounds(run_spec.display.total_frames)
    except ValueError as exc:
        raise PreflightError(str(exc)) from exc
    slot = run_spec.display.frames_per_stimulus
    every = run_spec.condition.oddball_every_n
    slots = run_spec.condition.total_stimuli
    bases = [event for event in scene.events if event.role in {"base", "mask"}]
    targets = [event for event in scene.events if event.role == "target"]
    catch = scene.is_catch_trial is True
    expected_targets = 0 if catch else run_spec.condition.total_oddball_cycles
    if (run_spec.schema_version != ("1.5.0" if catch else "1.4.0")
            or run_spec.condition.stimulus_modality != StimulusModality.SCENE
            or run_spec.stimulus_sequence or run_spec.attentional_blink is not None
            or (scene.target_id is not None if catch else not scene.target_id)
            or every < 2 or slots < 1
            or slots != run_spec.condition.total_oddball_cycles * every
            or len(bases) != slots or len(targets) != expected_targets
            or run_spec.display.total_frames != slots * slot
            or not isclose(scene.requested_soa_ms * run_spec.display.refresh_hz / 1000,
                           scene.soa_frames, rel_tol=0, abs_tol=1e-6)):
        raise PreflightError(
            "Compiled masking scene metadata or item-grid coverage is inconsistent."
        )
    for index, event in enumerate(bases):
        expected_role = "mask" if (index + 1) % every == 0 else "base"
        if (event.role != expected_role or event.start_frame != index * slot + scene.soa_frames
                or scene.soa_frames + event.duration_frames > slot):
            raise PreflightError("Compiled masking base/mask windows do not match the item grid.")
    for index, event in enumerate(targets):
        if (event.visual_id != scene.target_id
                or event.start_frame != ((index + 1) * every - 1) * slot
                or event.duration_frames > scene.soa_frames):
            raise PreflightError("Compiled masking target windows do not match the item grid.")


def _resolve_project_image_path(project_root: Path, image_path: str) -> Path:
    relative_path = Path(image_path)
    if relative_path.is_absolute():
        raise PreflightError(
            "Run preflight failed because an image stimulus path is not project-relative: "
            f"{image_path}"
        )
    try:
        return resolve_project_relative_path(project_root, image_path)
    except ValueError as exc:
        raise PreflightError(
            "Run preflight failed because an image stimulus path is invalid or "
            "escapes the project root: "
            f"{image_path}"
        ) from exc


def _validate_image_assets(
    project_root: Path,
    run_spec: RunSpec,
    *,
    decode: bool,
) -> None:
    image_references: dict[str, set[tuple[str, int, int]]] = {}
    if run_spec.scene_stream is not None:
        for visual in run_spec.scene_stream.visuals:
            if visual.image_path is not None:
                image_references.setdefault(visual.image_path, set())
    for event in run_spec.stimulus_sequence:
        if event.stimulus_modality != StimulusModality.IMAGE or event.image_path is None:
            continue
        expected_resolutions = image_references.setdefault(event.image_path, set())
        role_presentation = event_presentation(run_spec, event)
        if role_presentation is None:
            continue
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

    if isinstance(run_spec.attentional_blink, AttentionalBlinkRunSpec):
        raise PreflightError(RETIRED_IMAGE_PAIR_MESSAGE)
    strict_timing = _strict_timing_enabled(runtime_options)
    if strict_timing and not bool((runtime_options or {}).get("fullscreen", True)):
        raise PreflightError(
            "Run preflight failed because strict timing requires fullscreen presentation."
        )
    if strict_timing and bool((runtime_options or {}).get("variable_refresh_enabled", False)):
        raise PreflightError(
            "Run preflight failed because strict timing does not support variable-refresh displays."
        )

    _validate_sinusoidal_presentation(run_spec)
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
