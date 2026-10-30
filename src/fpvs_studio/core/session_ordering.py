"""Resolve total presentations and arrange ordinary FPVS sessions without repeats."""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from typing import Final

from fpvs_studio.core.compiler_support import check_compilation_cancelled
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.masking import condition_masking
from fpvs_studio.core.models import Condition, ProjectFile

POOLED_ORDERING_POLICY: Final = "pooled_no_adjacent"
POOLED_ORDERING_ALGORITHM_VERSION: Final = 1


def uses_pooled_condition_order(
    project: ProjectFile, conditions: Sequence[Condition] | None = None,
) -> bool:
    """Identify fresh ordinary sessions; native AB and masking retain their grouping."""

    selected = project.conditions if conditions is None else conditions
    return (
        project.experiment_category != ExperimentCategory.ATTENTIONAL_BLINK
        and not any(condition_masking(project, condition) is not None for condition in selected)
    )


def condition_ordering_identity(project: ProjectFile) -> dict[str, str | int] | None:
    """Describe the ordinary ordering algorithm without rewriting editable projects."""

    # A mixed project may execute only its ordinary subset, so its identity must
    # describe that route even though compiling every condition together is invalid.
    if project.conditions:
        if not any(uses_pooled_condition_order(project, [condition])
                   for condition in project.conditions):
            return None
    elif not uses_pooled_condition_order(project):
        return None
    return {
        "policy": POOLED_ORDERING_POLICY,
        "algorithm_version": POOLED_ORDERING_ALGORITHM_VERSION,
    }


def effective_condition_presentation_count(project: ProjectFile, condition: Condition) -> int:
    """Return total separate presentations, retaining the legacy shared fallback."""

    count = (condition.presentation_count if condition.presentation_count is not None
             else project.settings.session.block_count)
    if type(count) is not int or count < 1:
        raise ValueError(f"{condition.name}: total presentations must be a positive integer.")
    if condition.masking_catch and condition_masking(project, condition) is not None:
        return 1
    return count


def condition_presentation_counts(
    project: ProjectFile, conditions: Sequence[Condition] | None = None,
) -> dict[str, int]:
    """Resolve each selected condition's total without multiplying by block count."""

    return {
        condition.condition_id: effective_condition_presentation_count(project, condition)
        for condition in (project.conditions if conditions is None else conditions)
    }


def session_presentation_count(
    project: ProjectFile, conditions: Sequence[Condition] | None = None,
) -> int:
    """Include implicit masking catches in the total number of separate runs."""

    selected = project.conditions if conditions is None else conditions
    automatic_catches: set[str] = set()
    explicit_catches = {
        masking.variant for condition in selected
        if (masking := condition_masking(project, condition)) is not None
        and condition.masking_catch
    }
    for condition in selected:
        masking = condition_masking(project, condition)
        if (masking is not None and masking.catch_trial is not None
                and masking.variant not in explicit_catches):
            automatic_catches.add(masking.variant)
    return sum(condition_presentation_counts(project, selected).values()) + len(automatic_catches)


def _validate_pool(counts: Mapping[str, int], names: Mapping[str, str] | None = None) -> None:
    for count in counts.values():
        if type(count) is not int or count < 1:
            raise ValueError("Total presentations must be positive integers.")
    if not counts:
        return
    total = sum(counts.values())
    condition_id = max(counts, key=lambda key: counts[key])
    maximum = counts[condition_id]
    if maximum > total - maximum + 1:
        raise ValueError(
            f"{(names or {}).get(condition_id, condition_id)} has {maximum} presentations "
            f"but only {total - maximum} "
            "other presentations to separate them. Reduce its total presentations or "
            "add presentations of another condition to avoid adjacent repeats."
        )


def validate_condition_presentation_counts(
    project: ProjectFile, conditions: Sequence[Condition] | None = None,
) -> None:
    """Reject impossible ordinary pools while preserving native AB/masking grouping."""

    selected = project.conditions if conditions is None else conditions
    for condition in selected:
        specialized = (project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
                       or condition.attentional_blink is not None
                       or condition_masking(project, condition) is not None)
        if specialized and (condition.presentation_count is not None
                            or project.settings.condition_defaults.presentation_count is not None):
            raise ValueError(
                f"{condition.name}: per-condition presentation counts are unavailable for "
                "Attentional-Blink or masking groups. Use their existing session repeat count."
            )
    counts = condition_presentation_counts(project, selected)
    if not uses_pooled_condition_order(project, selected):
        return
    _validate_pool(counts, {condition.condition_id: condition.name for condition in selected})


def constrained_condition_order(counts: Mapping[str, int], *, rng: random.Random) -> list[str]:
    """Choose seeded feasible next occurrences, with exact counts and no retry loop.

    An odd-sized remainder with a majority condition must start with that condition.
    Otherwise every available condition other than the previous one is feasible;
    choose among them weighted by their remaining multiplicities.
    """

    _validate_pool(counts)
    remaining = dict(sorted(counts.items()))
    total = sum(remaining.values())
    order: list[str] = []
    previous: str | None = None
    while total:
        check_compilation_cancelled(len(order))
        forced = next((key for key, count in remaining.items()
                       if total % 2 and count == (total + 1) // 2), None)
        choices = ([forced] if forced is not None else
                   [key for key, count in remaining.items() if count and key != previous])
        if not choices or choices[0] == previous:
            raise ValueError("The remaining presentations cannot avoid adjacent repeats.")
        draw = rng.randrange(sum(remaining[key] for key in choices))
        selected = choices[-1]
        for key in choices:
            draw -= remaining[key]
            if draw < 0:
                selected = key
                break
        order.append(selected)
        remaining[selected] -= 1
        total -= 1
        previous = selected
    return order
