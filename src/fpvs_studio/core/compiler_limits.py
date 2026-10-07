"""Pre-allocation budgets for compiling untrusted, portable project data.

These are opt-in import limits, not persisted experiment settings. The ordinary
compiler retains its authored behavior. Estimates deliberately include all task
bindings/retries and the largest possible randomly selected masking catch.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from fpvs_studio.core.compiler_support import CompileError, check_compilation_cancelled
from fpvs_studio.core.fixation_planning import seconds_to_frames
from fpvs_studio.core.frame_validation import FrameValidationError, frames_per_stimulus
from fpvs_studio.core.masking import MaskingSettings, condition_masking
from fpvs_studio.core.models import AttentionalBlinkStreamSettings, Condition, ProjectFile
from fpvs_studio.core.presentation import resolve_pre_stream_fixation_seconds
from fpvs_studio.core.task_models import TaskModule
from fpvs_studio.core.validation import (
    approved_monitor_refresh_rate,
    approved_monitor_refresh_rates_text,
)


@dataclass(frozen=True)
class CompilationLimits:
    """Generous bundle budgets above 730-event oddball and 72-burst AB presets.

    A run may have 100,000 weighted presentation/marker/fixation events; the
    retained session may have 500,000. The frame budget represents 24 hours at
    the highest supported 240 Hz. Tasks count content, repeats and retry attempts.
    Ten million schedule work units bound search states and repeated masking pool scans.
    """

    max_session_entries: int = 10_000
    max_events_per_run: int = 100_000
    max_total_events: int = 500_000
    max_task_work_units: int = 1_000_000
    max_schedule_work: int = 10_000_000
    max_total_frames: int = 24 * 60 * 60 * 240


def _require_budget(label: str, requested: int, maximum: int) -> None:
    if requested > maximum:
        raise CompileError(
            f"Bundle compilation exceeds the {label} limit "
            f"({requested:,}; limit {maximum:,}). Reduce the experiment workload before sharing."
        )


def _task_work(module: TaskModule) -> int:
    if module.backward_counting is not None:
        # At most three generated screens, including an endpoint question with retries.
        return 16
    work = 1
    for index, step in enumerate(module.steps):
        check_compilation_cancelled(index)
        content = 1 + len(step.items) + len(step.branch_rules)
        content += sum(1 + len(question.options) for question in step.questions)
        work += content * step.repeat_count * step.max_attempts
    # Authored branches only jump forward, so visiting every step bounds their expansion.
    return work * module.repeat_count


def validate_compilation_workload(
    project: ProjectFile, conditions: list[Condition], *, refresh_hz: float,
    limits: CompilationLimits,
) -> None:
    """Reject excessive counts using arithmetic before schedules or task copies exist."""
    check_compilation_cancelled()
    if approved_monitor_refresh_rate(refresh_hz) is None:
        raise CompileError(
            "Bundle validation refresh rate must be an approved value: "
            f"{approved_monitor_refresh_rates_text()}."
        )
    base_hz = project.settings.protocol.base_hz
    if not isfinite(base_hz) or base_hz <= 0:
        raise CompileError("Bundle base rate must be a positive finite number.")
    raw_frames = refresh_hz / base_hz
    if not isfinite(raw_frames) or raw_frames > limits.max_total_frames:
        raise CompileError(
            "Bundle compilation exceeds the total frames limit at the requested base rate."
        )
    try:
        frame_count = frames_per_stimulus(refresh_hz, base_hz)
    except FrameValidationError as exc:
        raise CompileError(str(exc)) from exc
    repetitions = project.settings.session.block_count
    masking = {item.condition_id: condition_masking(project, item) for item in conditions}
    all_masking = bool(conditions) and all(value is not None for value in masking.values())
    occurrences = {
        item.condition_id: 1 if all_masking and item.masking_catch else repetitions
        for item in conditions
    }
    groups: dict[str, list[Condition]] = {}
    if all_masking:
        for item in conditions:
            settings = masking[item.condition_id]
            assert settings is not None
            groups.setdefault(settings.variant, []).append(item)
    automatic_catches = [
        group for group in groups.values()
        if not any(item.masking_catch for item in group)
        and any((settings := masking[item.condition_id]) is not None
                and settings.catch_trial is not None for item in group)
    ]
    entries = sum(occurrences.values()) + len(automatic_catches)
    _require_budget("session entries", entries, limits.max_session_entries)
    # Even a selected catch-only masking group iterates the configured repetitions.
    _require_budget("session repetitions", repetitions, limits.max_session_entries)

    fixation = project.settings.fixation_task
    fixation_events = 0
    if fixation.enabled:
        fixation_events = (
            fixation.target_count_max if fixation.target_count_mode == "randomized"
            else fixation.changes_per_sequence
        )
        # Randomized realization currently constructs its full candidate-count range.
        if fixation.target_count_mode == "randomized":
            _require_budget(
                "fixation count candidates",
                fixation.target_count_max - fixation.target_count_min + 1,
                limits.max_events_per_run,
            )
        _require_budget("fixation events per run", fixation_events, limits.max_events_per_run)

    module_work = {module.task_id: _task_work(module) for module in project.task_modules}
    # Session-first baselines can be injected by modifiers instead of explicit bindings.
    baseline_ids = {
        modifier.baseline_task_id for modifier in project.condition_modifiers
        if modifier.baseline_task_id is not None
    }
    total_tasks = sum(module_work.get(identity, 0) for identity in baseline_ids)
    total_events = total_frames = total_scans = 0
    work_by_condition: dict[str, tuple[int, int, int, int]] = {}
    cadence = project.settings.protocol.oddball_every_n
    for condition in conditions:
        check_compilation_cancelled()
        cycles = condition.sequence_count * condition.oddball_cycle_repeats_per_sequence
        slots = cycles * cadence
        settings = masking[condition.condition_id]
        scans = 0
        if settings is None:
            markers = slots if isinstance(
                condition.attentional_blink, AttentionalBlinkStreamSettings,
            ) else cycles
            events = slots + markers + fixation_events + 1
        else:
            candidates = [settings]
            if condition.masking_catch:
                candidates = [
                    candidate for candidate in masking.values()
                    if candidate is not None and candidate.variant == settings.variant
                ]
            events = max(_masking_events(candidate, slots, cycles) for candidate in candidates)
            scans = max(_masking_scan_work(candidate, slots, cycles) for candidate in candidates)
        _require_budget("events per run", events, limits.max_events_per_run)
        lead_in = resolve_pre_stream_fixation_seconds(
            project.settings.presentation, condition.presentation,
        )
        if not isfinite(lead_in) or lead_in > limits.max_total_frames / refresh_hz:
            raise CompileError(
                "Bundle compilation exceeds the total frames limit in the fixation lead-in."
            )
        frames = slots * frame_count + seconds_to_frames(lead_in, refresh_hz)
        tasks = sum(
            module_work.get(binding.task_id, 0)
            for binding in (*condition.pre_task_bindings, *condition.post_task_bindings)
        )
        work_by_condition[condition.condition_id] = (events, frames, tasks, scans)
        count = occurrences[condition.condition_id]
        total_events += count * events
        total_frames += count * frames
        total_tasks += count * tasks
        total_scans += count * scans
    for group in automatic_catches:
        # The compiler selects one source at random; bound each dimension independently.
        candidates_work = [work_by_condition[item.condition_id] for item in group]
        total_events += max(item[0] for item in candidates_work)
        total_frames += max(item[1] for item in candidates_work)
        total_tasks += max(item[2] for item in candidates_work)
        total_scans += max(item[3] for item in candidates_work)
    _require_budget("total events", total_events, limits.max_total_events)
    _require_budget("task expansion", total_tasks, limits.max_task_work_units)
    _require_budget("total frames", total_frames, limits.max_total_frames)
    _require_budget("schedule work", total_scans, limits.max_schedule_work)


def _masking_events(settings: MaskingSettings, slots: int, cycles: int) -> int:
    # One base/mask per slot, authored decorations, a target per oddball slot, and
    # optional target/mask markers. Counting targets also safely bounds catch runs.
    return (
        slots * (1 + len(settings.base_overlays)) + cycles
        + (2 * cycles if settings.event_triggers is not None else 0)
        + int(settings.fixation_visual is not None) + 1
    )


def _masking_scan_work(settings: MaskingSettings, slots: int, cycles: int) -> int:
    """Every randomized slot scans its candidate pool to avoid repeating the prior visual."""
    base_count = len(settings.base_visuals)
    mask_count = len(settings.mask_visuals or settings.base_visuals)
    return (
        (slots - cycles) * (base_count if base_count > 1 else 0)
        + cycles * (mask_count if mask_count > 1 else 0)
        + base_count + len(settings.target_visuals) + len(settings.mask_visuals or [])
        + len(settings.base_overlays) + int(settings.fixation_visual is not None)
    )
