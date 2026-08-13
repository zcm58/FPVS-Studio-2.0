"""Compile editable presentation settings into role-specific runtime contracts."""

from __future__ import annotations

import random

from fpvs_studio.core.compiler_schedules import (
    boundary_aware_shuffled_bag,
    build_balanced_shuffled_values,
    plan_no_repeat_role_bag_keys,
    pop_preferred_bag_item,
    repair_no_repeat_role_bag_sequence,
)
from fpvs_studio.core.compiler_support import CompileError, namespaced_random_seed
from fpvs_studio.core.enums import StimulusModality, TextHeightMode
from fpvs_studio.core.models import (
    Condition,
    ImageResolution,
    ProjectPresentationSettings,
    StimulusPresentationDefaults,
    StimulusSet,
    TextHeightScheduleSettings,
)
from fpvs_studio.core.presentation import resolve_role_presentation
from fpvs_studio.core.run_spec import (
    STUDIO_WORD_FONT_NAME,
    ConditionPresentationSpec,
    ImageGeometrySpec,
    RolePresentationSpec,
    StimulusRole,
    TextPresentationSpec,
)


def compile_condition_presentation(
    *,
    project_presentation: ProjectPresentationSettings,
    condition: Condition,
    base_set: StimulusSet,
    oddball_set: StimulusSet,
) -> tuple[
    ConditionPresentationSpec,
    dict[StimulusRole, StimulusPresentationDefaults],
]:
    """Resolve both condition roles into engine-neutral presentation specs."""

    resolved_roles: dict[StimulusRole, StimulusPresentationDefaults] = {
        "base": resolve_role_presentation(
            project_presentation,
            condition.presentation,
            "base",
        ),
        "oddball": resolve_role_presentation(
            project_presentation,
            condition.presentation,
            "oddball",
        ),
    }
    return (
        ConditionPresentationSpec(
            base=_compile_role_presentation(
                resolved_roles["base"],
                modality=base_set.modality,
                source_resolution=base_set.resolution,
            ),
            oddball=_compile_role_presentation(
                resolved_roles["oddball"],
                modality=oddball_set.modality,
                source_resolution=oddball_set.resolution,
            ),
        ),
        resolved_roles,
    )


def build_role_text_height_values(
    settings: TextHeightScheduleSettings,
    *,
    count: int,
    random_seed: int,
    role: StimulusRole,
) -> list[float]:
    """Realize one role's text-height schedule using an isolated stable seed."""

    if settings.mode == TextHeightMode.FIXED:
        return [settings.values[0]] * count
    rng = random.Random(namespaced_random_seed(random_seed, f"presentation:text-height:{role}"))
    return build_balanced_shuffled_values(
        settings.values,
        count=count,
        rng=rng,
        key=float,
    )


def build_interleaved_text_height_values(
    settings_by_role: dict[StimulusRole, TextHeightScheduleSettings],
    *,
    total_stimuli: int,
    oddball_every_n: int,
    random_seed: int,
) -> dict[StimulusRole, list[float]]:
    """Realize independent role bags while avoiding cross-role adjacent repeats."""

    exact_schedule = plan_no_repeat_role_bag_keys(
        {role: settings.values for role, settings in settings_by_role.items()},
        total_stimuli=total_stimuli,
        oddball_every_n=oddball_every_n,
        random_seed=random_seed,
        random_namespace="presentation:text-height",
        key=float,
    )
    if exact_schedule is not None:
        exact_results: dict[StimulusRole, list[float]] = {"base": [], "oddball": []}
        for index, selected in enumerate(exact_schedule):
            exact_role: StimulusRole = "oddball" if (index + 1) % oddball_every_n == 0 else "base"
            exact_results[exact_role].append(selected)
        return exact_results

    rng_by_role = {
        role: random.Random(namespaced_random_seed(random_seed, f"presentation:text-height:{role}"))
        for role in ("base", "oddball")
    }
    active_bags: dict[StimulusRole, list[float]] = {"base": [], "oddball": []}
    results: dict[StimulusRole, list[float]] = {"base": [], "oddball": []}
    interleaved_results: list[float] = []
    previous_height: float | None = None

    for index in range(total_stimuli):
        role: StimulusRole = "oddball" if (index + 1) % oddball_every_n == 0 else "base"
        settings = settings_by_role[role]
        next_role_change_index = next(
            (
                candidate_index
                for candidate_index in range(index + 1, total_stimuli)
                if ("oddball" if (candidate_index + 1) % oddball_every_n == 0 else "base") != role
            ),
            None,
        )
        next_role: StimulusRole = (
            ("oddball" if (next_role_change_index + 1) % oddball_every_n == 0 else "base")
            if next_role_change_index is not None
            else role
        )
        next_forced_height = (
            _forced_next_height(
                settings_by_role[next_role],
                active_bags[next_role],
            )
            if next_role_change_index is not None
            else None
        )
        if settings.mode == TextHeightMode.FIXED:
            selected = settings.values[0]
        else:
            if not active_bags[role]:
                active_bags[role] = boundary_aware_shuffled_bag(
                    settings.values,
                    rng=rng_by_role[role],
                    previous_key=previous_height,
                    key=float,
                )
            selected = pop_preferred_bag_item(
                active_bags[role],
                previous_key=previous_height,
                next_forced_key=next_forced_height,
                key=float,
                draws_before_forced=(
                    next_role_change_index - index - 1 if next_role_change_index is not None else 0
                ),
            )
        results[role].append(selected)
        interleaved_results.append(selected)
        previous_height = selected

    repaired = repair_no_repeat_role_bag_sequence(
        interleaved_results,
        interleaved_results,
        bag_sizes={role: len(settings.values) for role, settings in settings_by_role.items()},
        oddball_every_n=oddball_every_n,
    )
    repaired_by_role: dict[StimulusRole, list[float]] = {"base": [], "oddball": []}
    for index, selected in enumerate(repaired):
        role = "oddball" if (index + 1) % oddball_every_n == 0 else "base"
        repaired_by_role[role].append(selected)
    return repaired_by_role


def _forced_next_height(
    settings: TextHeightScheduleSettings,
    active_bag: list[float],
) -> float | None:
    if settings.mode == TextHeightMode.FIXED:
        return settings.values[0]
    candidates = active_bag if active_bag else settings.values
    unique_values = set(candidates)
    if len(unique_values) == 1:
        return next(iter(unique_values))
    return None


def _compile_role_presentation(
    settings: StimulusPresentationDefaults,
    *,
    modality: StimulusModality,
    source_resolution: ImageResolution | None,
) -> RolePresentationSpec:
    if modality == StimulusModality.IMAGE:
        if source_resolution is None:
            raise CompileError(
                "Image presentation geometry requires a known uniform source resolution."
            )
        geometry = settings.image_geometry
        return RolePresentationSpec(
            transform=settings.transform,
            image_geometry=ImageGeometrySpec(
                mode=geometry.mode,
                width_degrees=geometry.width_degrees,
                height_degrees=geometry.height_degrees,
                source_resolution=source_resolution,
            ),
        )
    if modality == StimulusModality.WORD:
        position = settings.text_position
        return RolePresentationSpec(
            transform=settings.transform,
            text=TextPresentationSpec(
                font_name=STUDIO_WORD_FONT_NAME,
                color=settings.text_color,
                position_unit=position.unit,
                position_x=position.x,
                position_y=position.y,
                height_unit=settings.text_height.unit,
                legacy_stimulus_width_fraction=(
                    settings.text_height.legacy_stimulus_width_fraction
                ),
            ),
        )
    raise CompileError(f"Unsupported stimulus modality '{modality}'.")
