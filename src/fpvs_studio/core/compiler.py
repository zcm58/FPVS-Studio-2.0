"""Compile editable project state into neutral execution contracts.

This module keeps the public compiler entry points stable. Focused helper modules own
condition validation, asset resolution, schedule construction, fixation planning, and
shared compiler support.
"""

from __future__ import annotations

import random
from pathlib import Path

from fpvs_studio.core.compiler_assets import load_manifest, resolve_image_paths
from fpvs_studio.core.compiler_conditions import (
    select_condition,
    select_conditions,
    validate_selected_condition,
)
from fpvs_studio.core.compiler_fixation import (
    build_fixation_events,
    resolve_realized_target_count,
)
from fpvs_studio.core.compiler_schedules import (
    build_stimulus_sequence,
    build_trigger_events,
    compile_transition_spec,
)
from fpvs_studio.core.compiler_support import (
    RANDOM_SEED_UPPER_BOUND,
    CompileError,
    color_to_string,
    make_run_id,
    make_session_id,
    make_session_run_id,
)
from fpvs_studio.core.fixation_planning import (
    max_supported_color_changes,
    milliseconds_to_frames,
    minimum_cycles_required,
    required_fixation_frames,
    seconds_to_frames,
)
from fpvs_studio.core.frame_validation import (
    FrameValidationError,
    frames_per_stimulus,
    on_off_frames,
)
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.run_spec import (
    ConditionRunSpec,
    DisplayRunSpec,
    FixationStyleSpec,
    RunSpec,
)
from fpvs_studio.core.session_plan import SessionBlock, SessionEntry, SessionPlan
from fpvs_studio.core.template_library import get_template
from fpvs_studio.preprocessing.models import StimulusManifest

__all__ = ["CompileError", "compile_run_spec", "compile_session_plan"]


def compile_run_spec(
    project: ProjectFile,
    *,
    refresh_hz: float,
    condition_id: str | None = None,
    project_root: Path | None = None,
    random_seed: int = 0,
    run_id: str | None = None,
    realized_target_count: int | None = None,
    manifest: StimulusManifest | None = None,
) -> RunSpec:
    """Compile one project condition into a dedicated frame-based RunSpec."""

    condition = select_condition(project, condition_id)
    base_set, oddball_set = validate_selected_condition(
        project,
        condition,
        refresh_hz=refresh_hz,
    )

    resolved_manifest = load_manifest(project_root, manifest)
    template = get_template(project.meta.template_id)
    frames_per_stimulus_value = frames_per_stimulus(refresh_hz, template.base_hz)
    on_frames, off_frames = on_off_frames(
        frames_per_stimulus_value,
        condition.duty_cycle_mode,
    )
    total_oddball_cycles = condition.oddball_cycle_repeats_per_sequence * condition.sequence_count
    total_stimuli = total_oddball_cycles * template.oddball_every_n
    total_frames = total_stimuli * frames_per_stimulus_value

    base_paths = resolve_image_paths(
        base_set,
        variant=condition.stimulus_variant,
        project_root=project_root,
        manifest=resolved_manifest,
    )
    oddball_paths = resolve_image_paths(
        oddball_set,
        variant=condition.stimulus_variant,
        project_root=project_root,
        manifest=resolved_manifest,
    )
    stimulus_sequence = build_stimulus_sequence(
        total_stimuli=total_stimuli,
        frames_per_stimulus_value=frames_per_stimulus_value,
        on_frames=on_frames,
        off_frames=off_frames,
        base_paths=base_paths,
        oddball_paths=oddball_paths,
        oddball_every_n=template.oddball_every_n,
    )

    fixation_settings = project.settings.fixation_task
    target_duration_frames = milliseconds_to_frames(
        fixation_settings.target_duration_ms,
        refresh_hz,
    )
    response_window_frames = seconds_to_frames(
        fixation_settings.response_window_seconds,
        refresh_hz,
    )
    min_gap_frames = milliseconds_to_frames(fixation_settings.min_gap_ms, refresh_hz)
    max_gap_frames = milliseconds_to_frames(fixation_settings.max_gap_ms, refresh_hz)
    max_supported_count = max_supported_color_changes(
        total_frames=total_frames,
        target_duration_frames=target_duration_frames,
        min_gap_frames=min_gap_frames,
    )
    run_rng = random.Random(random_seed)
    resolved_target_count = (
        realized_target_count
        if realized_target_count is not None
        else resolve_realized_target_count(
            fixation_settings,
            rng=run_rng,
            previous_count=None,
            max_supported_count=max_supported_count,
        )
    )
    required_frames = required_fixation_frames(
        color_change_count=resolved_target_count,
        target_duration_frames=target_duration_frames,
        min_gap_frames=min_gap_frames,
    )
    if fixation_settings.enabled and total_frames < required_frames:
        minimum_total_cycles, minimum_cycles_per_repeat = minimum_cycles_required(
            required_frames=required_frames,
            frames_per_stimulus=frames_per_stimulus_value,
            oddball_every_n=template.oddball_every_n,
            condition_repeat_count=condition.sequence_count,
        )
        raise CompileError(
            "Fixation color-change settings do not fit this condition at the "
            "selected refresh rate. "
            f"Condition '{condition.name}' duration: {total_frames} frames / "
            f"{total_frames / refresh_hz:.2f} s at {refresh_hz:.2f} Hz across "
            f"{total_oddball_cycles} cycle(s). "
            f"Required duration: {required_frames} frames / "
            f"{required_frames / refresh_hz:.2f} s for "
            f"{resolved_target_count} color changes (targets), "
            f"{fixation_settings.target_duration_ms} ms target duration, and "
            f"{fixation_settings.min_gap_ms} ms minimum gap. "
            "Color changes are distributed across the full condition duration. "
            "Adjust one of these settings: reduce color-change count per condition, "
            "reduce minimum gap, "
            "reduce target duration, or increase cycle count. "
            f"Minimum cycle count needed at {refresh_hz:.2f} Hz: {minimum_total_cycles} total "
            f"({minimum_cycles_per_repeat} per condition repeat with "
            f"{condition.sequence_count} repeat(s))."
        )
    fixation_events = (
        build_fixation_events(
            total_frames=total_frames,
            total_event_count=resolved_target_count,
            target_duration_frames=target_duration_frames,
            min_gap_frames=min_gap_frames,
            max_gap_frames=max_gap_frames,
        )
        if fixation_settings.enabled
        else []
    )

    return RunSpec(
        run_id=run_id or make_run_id(condition.condition_id),
        project_id=project.meta.project_id,
        project_name=project.meta.name,
        template_id=template.template_id,
        random_seed=random_seed,
        condition=ConditionRunSpec(
            condition_id=condition.condition_id,
            name=condition.name,
            template_id=template.template_id,
            instructions_text=condition.instructions or None,
            base_hz=template.base_hz,
            oddball_every_n=template.oddball_every_n,
            oddball_hz=template.oddball_hz,
            total_oddball_cycles=total_oddball_cycles,
            total_stimuli=total_stimuli,
            trigger_code=condition.trigger_code,
        ),
        display=DisplayRunSpec(
            refresh_hz=refresh_hz,
            background_color=color_to_string(project.settings.display.background_color),
            frames_per_stimulus=frames_per_stimulus_value,
            on_frames=on_frames,
            off_frames=off_frames,
            duty_cycle=on_frames / frames_per_stimulus_value,
            total_frames=total_frames,
        ),
        fixation=FixationStyleSpec(
            accuracy_task_enabled=fixation_settings.accuracy_task_enabled,
            default_color=color_to_string(fixation_settings.base_color),
            target_color=color_to_string(fixation_settings.target_color),
            response_key=fixation_settings.response_key,
            response_window_frames=response_window_frames,
            response_keys=[fixation_settings.response_key]
            if fixation_settings.accuracy_task_enabled
            else [],
            cross_size_px=fixation_settings.cross_size_px,
            line_width_px=fixation_settings.line_width_px,
            target_duration_frames=target_duration_frames,
            realized_target_count=resolved_target_count if fixation_settings.enabled else 0,
        ),
        stimulus_sequence=stimulus_sequence,
        fixation_events=fixation_events,
        trigger_events=build_trigger_events(condition.trigger_code),
    )


def compile_session_plan(
    project: ProjectFile,
    *,
    refresh_hz: float,
    project_root: Path | None = None,
    random_seed: int | None = None,
    session_id: str | None = None,
    condition_ids: list[str] | None = None,
    manifest: StimulusManifest | None = None,
) -> SessionPlan:
    """Compile a multi-condition block-randomized session plan."""

    selected_conditions = select_conditions(project, condition_ids)
    if random_seed is None:
        random_seed = project.settings.session.session_seed
    session_identifier = session_id or make_session_id(project.meta.project_id, random_seed)
    resolved_manifest = load_manifest(project_root, manifest)
    session_rng = random.Random(random_seed)
    fixation_settings = project.settings.fixation_task
    template = get_template(project.meta.template_id)
    try:
        frames_per_stimulus_value = frames_per_stimulus(refresh_hz, template.base_hz)
    except FrameValidationError as exc:
        raise CompileError(str(exc)) from exc
    target_duration_frames = milliseconds_to_frames(
        fixation_settings.target_duration_ms,
        refresh_hz,
    )
    min_gap_frames = milliseconds_to_frames(fixation_settings.min_gap_ms, refresh_hz)
    previous_realized_target_count: int | None = None

    blocks: list[SessionBlock] = []
    global_order_index = 0
    for block_index in range(project.settings.session.block_count):
        block_conditions = list(selected_conditions)
        if project.settings.session.randomize_conditions_per_block:
            session_rng.shuffle(block_conditions)

        entries: list[SessionEntry] = []
        for index_within_block, condition in enumerate(block_conditions):
            run_id = make_session_run_id(
                global_order_index=global_order_index,
                condition_id=condition.condition_id,
            )
            run_random_seed = session_rng.randrange(RANDOM_SEED_UPPER_BOUND)
            condition_total_oddball_cycles = (
                condition.oddball_cycle_repeats_per_sequence * condition.sequence_count
            )
            condition_total_stimuli = condition_total_oddball_cycles * template.oddball_every_n
            condition_total_frames = condition_total_stimuli * frames_per_stimulus_value
            max_supported_count = max_supported_color_changes(
                total_frames=condition_total_frames,
                target_duration_frames=target_duration_frames,
                min_gap_frames=min_gap_frames,
            )
            try:
                realized_target_count = resolve_realized_target_count(
                    fixation_settings,
                    rng=session_rng,
                    previous_count=previous_realized_target_count,
                    max_supported_count=max_supported_count,
                )
                run_spec = compile_run_spec(
                    project,
                    refresh_hz=refresh_hz,
                    condition_id=condition.condition_id,
                    project_root=project_root,
                    random_seed=run_random_seed,
                    run_id=run_id,
                    realized_target_count=realized_target_count,
                    manifest=resolved_manifest,
                )
            except CompileError as exc:
                raise CompileError(
                    f"Condition '{condition.name}' (id '{condition.condition_id}') "
                    f"failed compilation: {exc}"
                ) from exc
            entries.append(
                SessionEntry(
                    global_order_index=global_order_index,
                    block_index=block_index,
                    index_within_block=index_within_block,
                    condition_id=condition.condition_id,
                    condition_name=condition.name,
                    run_id=run_id,
                    run_spec=run_spec,
                )
            )
            if fixation_settings.enabled and fixation_settings.target_count_mode == "randomized":
                previous_realized_target_count = realized_target_count
            global_order_index += 1

        blocks.append(
            SessionBlock(
                block_index=block_index,
                condition_order=[condition.condition_id for condition in block_conditions],
                entries=entries,
            )
        )

    return SessionPlan(
        session_id=session_identifier,
        project_id=project.meta.project_id,
        project_name=project.meta.name,
        random_seed=random_seed,
        refresh_hz=refresh_hz,
        block_count=project.settings.session.block_count,
        transition=compile_transition_spec(project),
        blocks=blocks,
        total_runs=global_order_index,
    )
