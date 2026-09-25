"""Compile editable project state into neutral execution contracts.

This module keeps the public compiler entry points stable. Focused helper modules own
condition validation, asset resolution, schedule construction, fixation planning, and
shared compiler support.
"""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

from fpvs_studio.core.attentional_blink_presets import RECALL_TASK_ID
from fpvs_studio.core.compiler_attentional_blink_stream import (
    compile_attentional_blink_stream_sequence,
)
from fpvs_studio.core.compiler_conditions import (
    select_condition,
    select_conditions,
)
from fpvs_studio.core.compiler_fixation import (
    build_fixation_events,
    resolve_realized_target_count,
)
from fpvs_studio.core.compiler_inputs import CompilationInputs
from fpvs_studio.core.compiler_masking import compile_masking_run, validate_masking_settings
from fpvs_studio.core.compiler_presentation import (
    build_interleaved_text_height_values,
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
from fpvs_studio.core.compiler_tasks import (
    TaskCompilationInputs,
    compile_condition_tasks,
    compile_modifier_baseline,
    condition_tasks_replace_start_gate,
    relocate_masking_lead_ins,
    resolve_modifier_baseline,
)
from fpvs_studio.core.enums import SchemaVersion
from fpvs_studio.core.experiment_categories import require_valid_experiment_category
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
from fpvs_studio.core.masking import (
    condition_masking,
    masking_catch_source_conditions,
    validate_masking_catch_trials,
)
from fpvs_studio.core.models import AttentionalBlinkStreamSettings, Condition, ProjectFile
from fpvs_studio.core.presentation import resolve_pre_stream_fixation_seconds
from fpvs_studio.core.run_spec import (
    AttentionalBlinkStreamRunSpec,
    ConditionRunSpec,
    DisplayRunSpec,
    FixationStyleSpec,
    RunSpec,
)
from fpvs_studio.core.session_plan import SessionBlock, SessionEntry, SessionPlan
from fpvs_studio.core.task_models import TaskPhase, task_requires_text_alignment_schema
from fpvs_studio.core.trigger_codes import validate_oddball_trigger_code_policy
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

    try:
        require_valid_experiment_category(project)
    except ValueError as exc:
        raise CompileError(str(exc)) from exc
    condition = select_condition(project, condition_id)
    return _compile_prepared_run(
        CompilationInputs(project, refresh_hz=refresh_hz, project_root=project_root,
                          manifest=manifest),
        condition, random_seed=random_seed, run_id=run_id,
        realized_target_count=realized_target_count,
    )


def _compile_prepared_run(
    inputs: CompilationInputs, condition: Condition, *, random_seed: int,
    run_id: str | None, realized_target_count: int | None,
    previous_base_id: str | None = None,
    is_catch_trial: bool = False,
    masking_source_condition: Condition | None = None,
) -> RunSpec:
    project, refresh_hz = inputs.project, inputs.refresh_hz
    masking = condition_masking(project, condition)
    if condition.masking_catch:
        try:
            validate_masking_catch_trials(project, [condition])
            sources = (
                [masking_source_condition] if masking_source_condition is not None
                else masking_catch_source_conditions(project, condition)
            )
            _validate_masking_catch_sources(project, sources, refresh_hz)
        except ValueError as exc:
            raise CompileError(str(exc)) from exc
        source = random.Random(random_seed).choice(sources)
        masking = condition_masking(project, source)
        is_catch_trial = True
    if masking is not None:
        return compile_masking_run(
            project, condition, masking, refresh_hz=refresh_hz,
            project_root=inputs.project_root, random_seed=random_seed, run_id=run_id,
            previous_base_id=previous_base_id,
            is_catch_trial=is_catch_trial,
        )
    prepared = inputs.condition(condition)
    base_set, oddball_set = prepared.base_set, prepared.oddball_set
    # Resolve even word-only launches once, preserving manifest errors at this boundary.
    _ = inputs.manifest
    template = inputs.template
    protocol = project.settings.protocol
    frames_per_stimulus_value = frames_per_stimulus(refresh_hz, protocol.base_hz)
    on_frames, off_frames = on_off_frames(
        frames_per_stimulus_value,
        condition.duty_cycle_mode,
    )
    total_oddball_cycles = condition.oddball_cycle_repeats_per_sequence * condition.sequence_count
    total_stimuli = total_oddball_cycles * protocol.oddball_every_n
    total_frames = total_stimuli * frames_per_stimulus_value
    presentation = prepared.presentation.model_copy(deep=True)
    resolved_role_presentations = prepared.role_presentations
    attentional_blink: AttentionalBlinkStreamRunSpec | None = None
    if isinstance(condition.attentional_blink, AttentionalBlinkStreamSettings):
        stimulus_sequence, attentional_blink, presentation = (
            compile_attentional_blink_stream_sequence(
                project, condition, base_set=base_set, t1_set=oddball_set,
                presentation=presentation, refresh_hz=refresh_hz,
                total_cycles=total_oddball_cycles, random_seed=random_seed,
            )
        )
    else:
        text_height_values_by_role = None
        if base_set.modality.value == "word":
            text_height_values_by_role = build_interleaved_text_height_values(
                {
                    "base": resolved_role_presentations["base"].text_height,
                    "oddball": resolved_role_presentations["oddball"].text_height,
                },
                total_stimuli=total_stimuli,
                oddball_every_n=protocol.oddball_every_n,
                random_seed=random_seed,
            )
        base_stimuli = inputs.stimulus_items(base_set, condition.stimulus_variant)
        oddball_stimuli = inputs.stimulus_items(oddball_set, condition.stimulus_variant)
        stimulus_sequence = build_stimulus_sequence(
            total_stimuli=total_stimuli,
            frames_per_stimulus_value=frames_per_stimulus_value,
            on_frames=on_frames, off_frames=off_frames,
            base_stimuli=base_stimuli, oddball_stimuli=oddball_stimuli,
            oddball_every_n=protocol.oddball_every_n, random_seed=random_seed,
            text_height_values_by_role=text_height_values_by_role,
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
            oddball_every_n=protocol.oddball_every_n,
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
            rng=run_rng,
        )
        if fixation_settings.enabled
        else []
    )

    return RunSpec(
        schema_version=(
            "1.3.0"
            if isinstance(attentional_blink, AttentionalBlinkStreamRunSpec)
            else SchemaVersion.V1_1.value
        ),
        run_id=run_id or make_run_id(condition.condition_id),
        project_id=project.meta.project_id,
        project_name=project.meta.name,
        template_id=template.template_id,
        random_seed=random_seed,
        condition=ConditionRunSpec(
            condition_id=condition.condition_id,
            name=condition.name,
            show_title_on_screen=project.settings.session.show_condition_title_on_screen,
            template_id=template.template_id,
            instructions_text=condition.instructions or None,
            base_hz=protocol.base_hz,
            oddball_every_n=protocol.oddball_every_n,
            oddball_hz=protocol.oddball_hz,
            total_oddball_cycles=total_oddball_cycles,
            total_stimuli=len(stimulus_sequence),
            stimulus_modality=base_set.modality,
            trigger_code=condition.trigger_code,
        ),
        display=DisplayRunSpec(
            refresh_hz=refresh_hz,
            background_color=color_to_string(project.settings.display.background_color),
            stimulus_width_degrees=project.settings.display.stimulus_width_degrees,
            viewing_distance_cm=project.settings.display.viewing_distance_cm,
            screen_width_cm=project.settings.display.screen_width_cm,
            screen_width_px=project.settings.display.screen_width_px,
            screen_height_px=project.settings.display.screen_height_px,
            use_current_screen_resolution=project.settings.display.use_current_screen_resolution,
            duty_cycle_mode=condition.duty_cycle_mode,
            frames_per_stimulus=frames_per_stimulus_value,
            on_frames=on_frames,
            off_frames=off_frames,
            duty_cycle=on_frames / frames_per_stimulus_value,
            total_frames=total_frames,
        ),
        fixation=FixationStyleSpec(
            show_cross=fixation_settings.show_cross,
            accuracy_task_enabled=fixation_settings.accuracy_task_enabled,
            participant_tutorial_enabled=(
                fixation_settings.accuracy_task_enabled
                and fixation_settings.participant_tutorial_enabled
            ),
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
        presentation=presentation,
        attentional_blink=attentional_blink,
        pre_stream_fixation_frames=seconds_to_frames(
            resolve_pre_stream_fixation_seconds(
                project.settings.presentation,
                condition.presentation,
            ),
            refresh_hz,
        ),
        stimulus_sequence=stimulus_sequence,
        fixation_events=fixation_events,
        trigger_events=build_trigger_events(
            stimulus_sequence=stimulus_sequence,
            condition_trigger_code=condition.trigger_code,
            oddball_trigger_code=_project_oddball_trigger_code(project),
            t2_trigger_code=(attentional_blink.t2_trigger_code if attentional_blink else None),
        ),
    )


def _validate_masking_catch_sources(
    project: ProjectFile, sources: list[Condition], refresh_hz: float,
) -> None:
    for source in sources:
        settings = condition_masking(project, source)
        assert settings is not None
        validate_masking_settings(project, source, settings, refresh_hz)


def _project_oddball_trigger_code(project: ProjectFile) -> int:
    triggers = project.settings.triggers
    try:
        return validate_oddball_trigger_code_policy(
            triggers.oddball_trigger_code,
            allow_nonstandard=triggers.allow_nonstandard_oddball_trigger_code,
        )
    except (TypeError, ValueError) as exc:
        raise CompileError(str(exc)) from exc


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
    """Compile repeated conditions with blockwise or session-wide seeded randomization."""

    try:
        require_valid_experiment_category(project)
    except ValueError as exc:
        raise CompileError(str(exc)) from exc
    selected_conditions = select_conditions(project, condition_ids)
    baseline_requirements = resolve_modifier_baseline(project, selected_conditions)
    if random_seed is None:
        random_seed = project.settings.session.session_seed
    session_identifier = session_id or make_session_id(project.meta.project_id, random_seed)
    inputs = CompilationInputs(project, refresh_hz=refresh_hz, project_root=project_root,
                               manifest=manifest)
    _ = inputs.manifest
    session_rng = random.Random(random_seed)
    task_inputs = TaskCompilationInputs(project, project_root)
    fixation_settings = project.settings.fixation_task
    protocol = project.settings.protocol
    try:
        frames_per_stimulus_value = frames_per_stimulus(refresh_hz, protocol.base_hz)
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
    repetition_count = project.settings.session.block_count
    shuffle_all = project.settings.session.randomize_across_blocks
    compiled_block_count = 1 if shuffle_all else repetition_count
    masking_groups = all(
        condition_masking(project, item) is not None for item in selected_conditions
    )
    group_conditions: list[list[tuple[Condition, bool, Condition | None]]] = []
    if masking_groups:
        try:
            validate_masking_catch_trials(project, selected_conditions)
        except ValueError as exc:
            raise CompileError(str(exc)) from exc
        grouped: dict[str, list[Condition]] = {}
        for item in selected_conditions:
            settings = condition_masking(project, item)
            assert settings is not None
            grouped.setdefault(settings.variant, []).append(item)
        for pool in grouped.values():
            ordinary = [condition for condition in pool if not condition.masking_catch]
            catches = [condition for condition in pool if condition.masking_catch]
            ordered: list[tuple[Condition, bool, Condition | None]] = []
            for _ in range(repetition_count):
                triplet = list(ordinary)
                session_rng.shuffle(triplet)
                ordered.extend((condition, False, None) for condition in triplet)
            settings = condition_masking(project, pool[0])
            assert settings is not None
            if catches:
                catch_condition = catches[0]
                sources = masking_catch_source_conditions(project, catch_condition, pool)
                try:
                    _validate_masking_catch_sources(project, sources, refresh_hz)
                except ValueError as exc:
                    raise CompileError(str(exc)) from exc
                source = session_rng.choice(sources)
                ordered.insert(
                    session_rng.randrange(len(ordered) + 1), (catch_condition, True, source),
                )
            elif settings.catch_trial is not None:
                catch_condition = session_rng.choice(pool)
                ordered.insert(
                    session_rng.randrange(len(ordered) + 1), (catch_condition, True, None),
                )
            group_conditions.append(ordered)
        session_rng.shuffle(group_conditions)
        compiled_block_count = len(group_conditions)
    elif any(condition_masking(project, item) is not None for item in selected_conditions):
        raise CompileError(
            "Run masking variants separately from conditions without masking modifiers."
        )
    previous_masking_base: dict[str, str] = {}
    masking_occurrence_counts = Counter(
        condition.condition_id for group in group_conditions for condition, _, _ in group
    )
    occurrences: dict[str, int] = {}
    for block_index in range(compiled_block_count):
        if masking_groups:
            block_trials = group_conditions[block_index]
        else:
            block_conditions = list(selected_conditions)
            if shuffle_all:
                block_conditions *= repetition_count
            session_rng.shuffle(block_conditions)
            block_trials = [(condition, False, None) for condition in block_conditions]

        entries: list[SessionEntry] = []
        for index_within_block, trial in enumerate(block_trials):
            condition, is_catch_trial, masking_source = trial
            masking = condition_masking(project, condition)
            occurrence_index = occurrences.get(condition.condition_id, 0)
            occurrences[condition.condition_id] = occurrence_index + 1
            condition_occurrence_count = (
                masking_occurrence_counts[condition.condition_id] if masking else repetition_count
            )
            run_id = make_session_run_id(
                global_order_index=global_order_index,
                condition_id=condition.condition_id,
            )
            run_random_seed = session_rng.randrange(RANDOM_SEED_UPPER_BOUND)
            condition_total_oddball_cycles = (
                condition.oddball_cycle_repeats_per_sequence * condition.sequence_count
            )
            condition_total_stimuli = condition_total_oddball_cycles * protocol.oddball_every_n
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
                run_spec = _compile_prepared_run(
                    inputs, condition,
                    random_seed=run_random_seed,
                    run_id=run_id,
                    realized_target_count=realized_target_count,
                    previous_base_id=(
                        previous_masking_base.get(masking.variant) if masking else None
                    ),
                    is_catch_trial=is_catch_trial,
                    masking_source_condition=masking_source,
                )
                if masking is not None and run_spec.scene_stream is not None:
                    base_events = [event for event in run_spec.scene_stream.events
                                   if event.role in {"base", "mask"}]
                    previous_masking_base[masking.variant] = base_events[-1].visual_id
                # Only the current entry shares a linked pre/post realization.
                task_inputs.memory_pairs.clear()
                pre_tasks = compile_condition_tasks(
                    project,
                    condition,
                    phase=TaskPhase.PRE_CONDITION,
                    block_index=occurrence_index,
                    block_count=condition_occurrence_count,
                    session_seed=random_seed,
                    run_id=run_id,
                    project_root=project_root,
                    run_spec=run_spec,
                    global_order_index=global_order_index,
                    inputs=task_inputs,
                    stream_group_index=index_within_block if masking else None,
                    stream_group_count=len(block_trials) if masking else None,
                )
                post_tasks = compile_condition_tasks(
                    project,
                    condition,
                    phase=TaskPhase.POST_CONDITION,
                    block_index=occurrence_index,
                    block_count=condition_occurrence_count,
                    session_seed=random_seed,
                    run_id=run_id,
                    project_root=project_root,
                    run_spec=run_spec,
                    global_order_index=global_order_index,
                    inputs=task_inputs,
                    stream_group_index=index_within_block if masking else None,
                    stream_group_count=len(block_trials) if masking else None,
                )
                if global_order_index == 0 and baseline_requirements:
                    pre_tasks.insert(0, compile_modifier_baseline(
                        project, baseline_requirements, condition=condition,
                        session_seed=random_seed, run_id=run_id, project_root=project_root,
                        inputs=task_inputs,
                    ))
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
                    pre_tasks=pre_tasks,
                    post_tasks=post_tasks,
                    show_condition_start_gate=(
                        False if masking is not None else
                        any(task.task_id == RECALL_TASK_ID for task in post_tasks)
                        or not condition_tasks_replace_start_gate(
                            condition,
                            block_index=occurrence_index,
                            block_count=repetition_count,
                            global_order_index=global_order_index,
                        )
                    ),
                )
            )
            if fixation_settings.enabled and fixation_settings.target_count_mode == "randomized":
                previous_realized_target_count = realized_target_count
            global_order_index += 1

        if masking_groups:
            relocate_masking_lead_ins(entries)
        blocks.append(
            SessionBlock(
                block_index=block_index,
                condition_order=[condition.condition_id for condition, _, _ in block_trials],
                entries=entries,
            )
        )

    return SessionPlan(
        schema_version=(
            "1.5.0" if any(task_requires_text_alignment_schema(task)
                           for block in blocks for entry in block.entries
                           for task in [*entry.pre_tasks, *entry.post_tasks])
            else "1.4.0" if any(is_catch for group in group_conditions for _, is_catch, _ in group)
            else "1.3.0" if masking_groups else SchemaVersion.V1_2.value
        ),
        authored_task_flow=True if masking_groups else None,
        session_id=session_identifier,
        project_id=project.meta.project_id,
        project_name=project.meta.name,
        random_seed=random_seed,
        refresh_hz=refresh_hz,
        block_count=compiled_block_count,
        transition=compile_transition_spec(project),
        blocks=blocks,
        total_runs=global_order_index,
    )
