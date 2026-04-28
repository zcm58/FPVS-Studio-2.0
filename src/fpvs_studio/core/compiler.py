"""Compile editable project state into neutral execution contracts. This module transforms
ProjectFile and manifest-backed assets into single-condition RunSpec and ordered
SessionPlan artifacts with frame-based timing. It owns schedule derivation and fixation
target realization, while runtime-only launch options and engine behavior stay out of
compiled output."""

from __future__ import annotations

import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from fpvs_studio.core.enums import DutyCycleMode, InterConditionMode, StimulusVariant
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
from fpvs_studio.core.models import (
    Condition,
    FixationTaskSettings,
    ProjectFile,
    StimulusSet,
    validate_project_relative_path,
)
from fpvs_studio.core.paths import (
    stimulus_derived_dir,
    stimulus_manifest_path,
    to_project_relative_posix,
)
from fpvs_studio.core.run_spec import (
    ConditionRunSpec,
    DisplayRunSpec,
    FixationEvent,
    FixationStyleSpec,
    RunSpec,
    StimulusEvent,
    StimulusRole,
    TriggerEvent,
)
from fpvs_studio.core.serialization import read_json_file
from fpvs_studio.core.session_plan import (
    InterConditionTransitionSpec,
    SessionBlock,
    SessionEntry,
    SessionPlan,
)
from fpvs_studio.core.template_library import get_template
from fpvs_studio.preprocessing.models import (
    StimulusAssetRecord,
    StimulusManifest,
    StimulusSetManifest,
)

SUPPORTED_SOURCE_SUFFIXES = (".jpg", ".jpeg", ".png")
SUPPORTED_DERIVED_SUFFIXES = (".png",)
RANDOM_SEED_UPPER_BOUND = 2**31


class CompileError(ValueError):
    """Raised when editable project state cannot be compiled into a run spec."""


def _make_run_id(condition_id: str, now: datetime | None = None) -> str:
    """Create a compact condition-run id."""

    timestamp = now or datetime.now(timezone.utc)
    return f"{condition_id}-{timestamp.strftime('%Y%m%dT%H%M%SZ')}"


def _make_session_id(_project_id: str, random_seed: int) -> str:
    """Create a deterministic, path-friendly session identifier."""

    return f"session-{random_seed:010d}"


def _make_session_run_id(
    *,
    global_order_index: int,
    condition_id: str,
) -> str:
    """Create a deterministic, path-friendly run id for one session entry."""

    return f"run-{global_order_index + 1:03d}-{condition_id}"


def _color_to_string(value: str | tuple[int, int, int]) -> str:
    """Normalize persisted color values into a runtime-friendly string form."""

    if isinstance(value, str):
        return value
    return f"rgb({value[0]},{value[1]},{value[2]})"


def _ordered_conditions(project: ProjectFile) -> list[Condition]:
    """Return project conditions in stable project order."""

    return sorted(project.conditions, key=lambda item: item.order_index)


def _select_condition(project: ProjectFile, condition_id: str | None) -> Condition:
    """Select one condition to compile."""

    ordered_conditions = _ordered_conditions(project)
    if not ordered_conditions:
        raise CompileError("Project has no conditions to compile.")
    if condition_id is None:
        if len(ordered_conditions) > 1:
            raise CompileError(
                "condition_id is required when the project contains more than one condition."
            )
        return ordered_conditions[0]
    for condition in ordered_conditions:
        if condition.condition_id == condition_id:
            return condition
    raise CompileError(f"Unknown condition_id '{condition_id}'.")


def _select_conditions(
    project: ProjectFile,
    condition_ids: list[str] | None,
) -> list[Condition]:
    """Select the condition pool for session compilation."""

    ordered_conditions = _ordered_conditions(project)
    if not ordered_conditions:
        raise CompileError("Project has no conditions to compile.")
    if condition_ids is None:
        return ordered_conditions

    if len(condition_ids) != len(set(condition_ids)):
        raise CompileError("condition_ids must not contain duplicates.")

    selected_ids = set(condition_ids)
    selected_conditions = [
        condition for condition in ordered_conditions if condition.condition_id in selected_ids
    ]
    if len(selected_conditions) != len(condition_ids):
        known_ids = {condition.condition_id for condition in ordered_conditions}
        missing_ids = sorted(selected_ids - known_ids)
        raise CompileError(
            "Unknown condition_ids requested for session compilation: " + ", ".join(missing_ids)
        )
    return selected_conditions


def _validate_selected_condition(
    project: ProjectFile,
    condition: Condition,
    *,
    refresh_hz: float,
) -> tuple[StimulusSet, StimulusSet]:
    """Validate the specific condition being compiled."""

    template = get_template(project.meta.template_id)
    stimulus_sets = {item.set_id: item for item in project.stimulus_sets}

    try:
        frames_per_stimulus(refresh_hz, template.base_hz)
    except FrameValidationError as exc:
        raise CompileError(str(exc)) from exc

    base_set = stimulus_sets.get(condition.base_stimulus_set_id)
    oddball_set = stimulus_sets.get(condition.oddball_stimulus_set_id)
    if base_set is None:
        raise CompileError(
            f"Condition '{condition.name}' references missing base stimulus set "
            f"'{condition.base_stimulus_set_id}'."
        )
    if oddball_set is None:
        raise CompileError(
            f"Condition '{condition.name}' references missing oddball stimulus set "
            f"'{condition.oddball_stimulus_set_id}'."
        )
    if base_set.image_count <= 0:
        raise CompileError(f"Stimulus set '{base_set.name}' does not contain any imported images.")
    if oddball_set.image_count <= 0:
        raise CompileError(
            f"Stimulus set '{oddball_set.name}' does not contain any imported images."
        )
    if (
        base_set.resolution is not None
        and oddball_set.resolution is not None
        and base_set.resolution != oddball_set.resolution
    ):
        raise CompileError(
            f"Condition '{condition.name}' uses stimulus sets with mismatched resolutions."
        )
    if condition.duty_cycle_mode == DutyCycleMode.BLANK_50:
        try:
            on_off_frames(
                frames_per_stimulus(refresh_hz, template.base_hz), condition.duty_cycle_mode
            )
        except FrameValidationError as exc:
            raise CompileError(str(exc)) from exc
    return base_set, oddball_set


def _load_manifest(
    project_root: Path | None,
    manifest: StimulusManifest | None,
) -> StimulusManifest | None:
    """Load the preprocessing manifest when available."""

    if manifest is not None:
        return manifest
    if project_root is None:
        return None
    manifest_path = stimulus_manifest_path(project_root)
    if not manifest_path.is_file():
        return None
    return read_json_file(manifest_path, StimulusManifest)


def _resolve_manifest_set(
    stimulus_set: StimulusSet,
    *,
    manifest: StimulusManifest | None,
) -> StimulusSetManifest | None:
    """Return the matching manifest set when present."""

    if manifest is None:
        return None
    for manifest_set in manifest.sets:
        if manifest_set.set_id == stimulus_set.set_id:
            return manifest_set
    return None


def _resolve_manifest_asset_path(
    asset: StimulusAssetRecord,
    *,
    variant: StimulusVariant,
) -> str | None:
    """Resolve one asset path from the manifest for the requested variant."""

    if variant == StimulusVariant.ORIGINAL:
        return asset.source.relative_path
    for derivative in asset.derivatives:
        if derivative.variant == variant:
            return derivative.relative_path
    return None


def _resolve_manifest_image_paths(
    stimulus_set: StimulusSet,
    *,
    variant: StimulusVariant,
    project_root: Path,
    manifest: StimulusManifest | None,
) -> list[str] | None:
    """Resolve ordered asset paths from the preprocessing manifest."""

    manifest_set = _resolve_manifest_set(stimulus_set, manifest=manifest)
    if manifest_set is None or not manifest_set.assets:
        return None

    resolved: list[str] = []
    for asset in sorted(manifest_set.assets, key=lambda item: item.source.relative_path.lower()):
        relative_path = _resolve_manifest_asset_path(asset, variant=variant)
        if relative_path is None:
            raise CompileError(
                f"Stimulus variant '{variant.value}' is missing from the manifest for set "
                f"'{stimulus_set.name}'."
            )
        candidate_path = project_root / Path(relative_path)
        if not candidate_path.is_file():
            raise CompileError(
                f"Manifest path '{relative_path}' for set '{stimulus_set.name}' does not exist."
            )
        resolved.append(validate_project_relative_path(relative_path))

    return resolved


def _synthetic_image_paths(
    stimulus_set: StimulusSet,
    *,
    variant: StimulusVariant,
) -> list[str]:
    """Create deterministic placeholder image paths when the project root is unavailable."""

    if variant == StimulusVariant.ORIGINAL:
        base_dir = stimulus_set.source_dir
    else:
        base_dir = f"stimuli/derived/{stimulus_set.set_id}/{variant.value}"
    return [
        validate_project_relative_path(f"{base_dir}/image_{index:04d}.png")
        for index in range(1, stimulus_set.image_count + 1)
    ]


def _resolve_filesystem_image_paths(
    stimulus_set: StimulusSet,
    *,
    variant: StimulusVariant,
    project_root: Path,
) -> list[str]:
    """Resolve sorted project-relative image paths directly from the filesystem."""

    allowed_suffixes: tuple[str, ...]
    if variant == StimulusVariant.ORIGINAL:
        source_dir = project_root / Path(stimulus_set.source_dir)
        allowed_suffixes = SUPPORTED_SOURCE_SUFFIXES
    else:
        source_dir = stimulus_derived_dir(project_root, stimulus_set.set_id) / variant.value
        allowed_suffixes = SUPPORTED_DERIVED_SUFFIXES

    if source_dir.exists() and source_dir.is_dir():
        resolved = [
            to_project_relative_posix(project_root, path)
            for path in sorted(source_dir.iterdir(), key=lambda item: item.name.lower())
            if path.is_file() and path.suffix.lower() in allowed_suffixes
        ]
        if resolved:
            return resolved
    raise CompileError(f"Stimulus set '{stimulus_set.name}' has no resolvable image paths.")


def _resolve_image_paths(
    stimulus_set: StimulusSet,
    *,
    variant: StimulusVariant,
    project_root: Path | None,
    manifest: StimulusManifest | None,
) -> list[str]:
    """Resolve sorted project-relative image paths for a stimulus set."""

    if project_root is not None:
        manifest_paths = _resolve_manifest_image_paths(
            stimulus_set,
            variant=variant,
            project_root=project_root,
            manifest=manifest,
        )
        if manifest_paths:
            return manifest_paths
        return _resolve_filesystem_image_paths(
            stimulus_set,
            variant=variant,
            project_root=project_root,
        )

    synthetic_paths = _synthetic_image_paths(stimulus_set, variant=variant)
    if synthetic_paths:
        return synthetic_paths
    raise CompileError(f"Stimulus set '{stimulus_set.name}' has no resolvable image paths.")


def _build_stimulus_sequence(
    *,
    total_stimuli: int,
    frames_per_stimulus_value: int,
    on_frames: int,
    off_frames: int,
    base_paths: list[str],
    oddball_paths: list[str],
    oddball_every_n: int,
) -> list[StimulusEvent]:
    """Build the deterministic base/oddball schedule."""

    role_counts: Counter[str] = Counter()
    sequence: list[StimulusEvent] = []

    for index in range(total_stimuli):
        role: StimulusRole = "oddball" if (index + 1) % oddball_every_n == 0 else "base"
        pool = oddball_paths if role == "oddball" else base_paths
        image_path = pool[role_counts[role] % len(pool)]
        role_counts[role] += 1
        sequence.append(
            StimulusEvent(
                sequence_index=index,
                role=role,
                image_path=image_path,
                on_start_frame=index * frames_per_stimulus_value,
                on_frames=on_frames,
                off_frames=off_frames,
            )
        )
    return sequence


def _build_fixation_events(
    *,
    total_frames: int,
    total_event_count: int,
    target_duration_frames: int,
    min_gap_frames: int,
    max_gap_frames: int,
) -> list[FixationEvent]:
    """Generate deterministic, non-overlapping fixation events for one run."""

    if total_event_count <= 0 or target_duration_frames <= 0 or total_frames <= 0:
        return []

    available_gap_space = total_frames - (total_event_count * target_duration_frames)
    required_minimum = (total_event_count + 1) * min_gap_frames
    if available_gap_space < required_minimum:
        raise CompileError(
            "Fixation settings do not fit within one condition run at the selected refresh rate. "
            f"Need at least {required_minimum} gap frames but only "
            f"{available_gap_space} are available "
            "after allocating fixation target durations."
        )

    preferred_gap = available_gap_space // (total_event_count + 1)
    gap_frames = min(max_gap_frames, max(min_gap_frames, preferred_gap))
    fixation_events: list[FixationEvent] = []
    current_start = gap_frames
    for event_index in range(total_event_count):
        if current_start + target_duration_frames > total_frames:
            raise CompileError(
                "Fixation event scheduling exceeded the condition duration after "
                "applying spacing constraints."
            )
        fixation_events.append(
            FixationEvent(
                event_index=event_index,
                start_frame=current_start,
                duration_frames=target_duration_frames,
            )
        )
        current_start += target_duration_frames + gap_frames

    return fixation_events


def _resolve_realized_target_count(
    fixation_settings: FixationTaskSettings,
    *,
    rng: random.Random,
    previous_count: int | None,
    max_supported_count: int | None = None,
) -> int:
    """Resolve a deterministic realized fixation target count for one run."""

    if not fixation_settings.enabled:
        return 0
    if fixation_settings.target_count_mode == "fixed":
        # Backward-compatible key name; interpreted as color changes per condition.
        return fixation_settings.changes_per_sequence

    candidate_counts = list(
        range(fixation_settings.target_count_min, fixation_settings.target_count_max + 1)
    )
    if max_supported_count is not None:
        candidate_counts = [count for count in candidate_counts if count <= max_supported_count]
    if (
        fixation_settings.no_immediate_repeat_count
        and previous_count is not None
        and previous_count in candidate_counts
    ):
        candidate_counts = [count for count in candidate_counts if count != previous_count]
    if not candidate_counts:
        raise CompileError(
            "Randomized fixation target count range cannot satisfy feasibility/no-immediate-repeat "
            "constraints for this condition duration."
        )
    return rng.choice(candidate_counts)


def _build_trigger_events(trigger_code: int | None) -> list[TriggerEvent]:
    """Generate the first-pass trigger schedule."""

    if trigger_code is None:
        return []
    return [TriggerEvent(frame_index=0, code=trigger_code, label="condition_start")]


def _compile_transition_spec(project: ProjectFile) -> InterConditionTransitionSpec:
    """Compile session transition settings into an explicit transition spec."""

    session_settings = project.settings.session
    if session_settings.inter_condition_mode == InterConditionMode.FIXED_BREAK:
        return InterConditionTransitionSpec(
            mode=session_settings.inter_condition_mode,
            break_seconds=session_settings.inter_condition_break_seconds,
            continue_key=None,
        )
    return InterConditionTransitionSpec(
        mode=session_settings.inter_condition_mode,
        break_seconds=None,
        continue_key=session_settings.continue_key,
    )


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

    condition = _select_condition(project, condition_id)
    base_set, oddball_set = _validate_selected_condition(
        project,
        condition,
        refresh_hz=refresh_hz,
    )

    resolved_manifest = _load_manifest(project_root, manifest)
    template = get_template(project.meta.template_id)
    frames_per_stimulus_value = frames_per_stimulus(refresh_hz, template.base_hz)
    on_frames, off_frames = on_off_frames(
        frames_per_stimulus_value,
        condition.duty_cycle_mode,
    )
    total_oddball_cycles = condition.oddball_cycle_repeats_per_sequence * condition.sequence_count
    total_stimuli = total_oddball_cycles * template.oddball_every_n
    total_frames = total_stimuli * frames_per_stimulus_value

    base_paths = _resolve_image_paths(
        base_set,
        variant=condition.stimulus_variant,
        project_root=project_root,
        manifest=resolved_manifest,
    )
    oddball_paths = _resolve_image_paths(
        oddball_set,
        variant=condition.stimulus_variant,
        project_root=project_root,
        manifest=resolved_manifest,
    )
    stimulus_sequence = _build_stimulus_sequence(
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
        else _resolve_realized_target_count(
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
        _build_fixation_events(
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
        run_id=run_id or _make_run_id(condition.condition_id),
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
            background_color=_color_to_string(project.settings.display.background_color),
            frames_per_stimulus=frames_per_stimulus_value,
            on_frames=on_frames,
            off_frames=off_frames,
            duty_cycle=on_frames / frames_per_stimulus_value,
            total_frames=total_frames,
        ),
        fixation=FixationStyleSpec(
            accuracy_task_enabled=fixation_settings.accuracy_task_enabled,
            default_color=_color_to_string(fixation_settings.base_color),
            target_color=_color_to_string(fixation_settings.target_color),
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
        trigger_events=_build_trigger_events(condition.trigger_code),
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

    selected_conditions = _select_conditions(project, condition_ids)
    if random_seed is None:
        random_seed = project.settings.session.session_seed
    session_identifier = session_id or _make_session_id(project.meta.project_id, random_seed)
    resolved_manifest = _load_manifest(project_root, manifest)
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
            run_id = _make_session_run_id(
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
                realized_target_count = _resolve_realized_target_count(
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
        transition=_compile_transition_spec(project),
        blocks=blocks,
        total_runs=global_order_index,
    )
