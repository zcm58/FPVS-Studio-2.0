"""Resolve total presentations and arrange ordinary FPVS sessions without repeats."""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Final

from fpvs_studio.core.compiler_support import check_compilation_cancelled, compilation_cancellation
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.masking import condition_masking
from fpvs_studio.core.models import Condition, ProjectFile

POOLED_ORDERING_POLICY: Final = "pooled_no_adjacent"
POOLED_ORDERING_ALGORITHM_VERSION: Final = 1
SAVED_ORDERING_POLICY: Final = "saved_no_adjacent"
SAVED_ORDERING_ALGORITHM_VERSION: Final = 1


def uses_pooled_condition_order(
    project: ProjectFile, conditions: Sequence[Condition] | None = None,
) -> bool:
    """Identify fresh ordinary sessions; native AB and masking retain their grouping."""

    selected = project.conditions if conditions is None else conditions
    return (
        project.experiment_category != ExperimentCategory.ATTENTIONAL_BLINK
        and not any(condition_masking(project, condition) is not None for condition in selected)
    )


def condition_ordering_identity(project: ProjectFile) -> dict[str, object] | None:
    """Describe the ordinary ordering algorithm without rewriting editable projects."""

    # A mixed project may execute only its ordinary subset, so its identity must
    # describe that route even though compiling every condition together is invalid.
    if project.conditions:
        if not any(uses_pooled_condition_order(project, [condition])
                   for condition in project.conditions):
            return None
    elif not uses_pooled_condition_order(project):
        return None
    saved = active_saved_condition_order(project)
    if saved is not None:
        return {
            "policy": SAVED_ORDERING_POLICY,
            "algorithm_version": SAVED_ORDERING_ALGORITHM_VERSION,
            "condition_order": saved,
        }
    return {
        "policy": POOLED_ORDERING_POLICY,
        "algorithm_version": POOLED_ORDERING_ALGORITHM_VERSION,
    }


def validate_saved_condition_order(
    order: Sequence[str], counts: Mapping[str, int],
) -> list[str]:
    """Validate an exact authored arrangement without repairing any occurrences."""

    if isinstance(order, (str, bytes)) or any(type(item) is not str for item in order):
        raise ValueError("Saved condition order must be a list of condition IDs.")
    if any(type(count) is not int or count < 1 for count in counts.values()):
        raise ValueError("Total presentations must be positive integers.")
    unknown = set(order) - set(counts)
    if unknown:
        raise ValueError(
            "Saved condition order contains unknown condition IDs: "
            f"{', '.join(sorted(unknown))}."
        )
    if not order or Counter(order) != dict(counts):
        raise ValueError(
            "Saved condition order does not match the total presentations. "
            "Open Condition order to generate an order matching the current counts."
        )
    for index, (left, right) in enumerate(zip(order, order[1:], strict=False), 1):
        if left == right:
            raise ValueError(
                f"Saved condition order repeats '{left}' in adjacent positions {index} and "
                f"{index + 1}. Move a presentation so identical conditions are separated."
            )
    return list(order)


def active_saved_condition_order(
    project: ProjectFile, conditions: Sequence[Condition] | None = None,
) -> list[str] | None:
    """Return the exact Fixed order, rejecting invalid filtered subsets rather than repairing."""

    saved = project.settings.session.saved_condition_order
    if project.settings.session.randomization_mode != "fixed" or saved is None:
        return None
    if not uses_pooled_condition_order(project):
        raise ValueError("Saved condition order is unavailable for native AB or masking groups.")
    order = validate_saved_condition_order(saved, condition_presentation_counts(project))
    if conditions is None:
        return order
    counts = condition_presentation_counts(project, conditions)
    return validate_saved_condition_order([item for item in order if item in counts], counts)


def preview_condition_order(
    project: ProjectFile, *, presentation_counts: Mapping[str, int] | None = None,
    condition_order_seed: int | None = None, cancelled: Callable[[], bool] | None = None,
) -> list[str]:
    """Generate an editable draft without assets, display timing or retained-order constraints."""

    from fpvs_studio.core.condition_timing import propose_condition_timing
    from fpvs_studio.core.randomization import (
        configured_randomization_seeds,
        supports_independent_randomization,
    )

    def check_cancelled() -> None:
        if cancelled is not None and cancelled():
            raise InterruptedError("Condition-order preview cancelled.")

    with compilation_cancellation(check_cancelled):
        if not supports_independent_randomization(project):
            raise ValueError(
                "Condition order preview is unavailable for native AB or masking groups."
            )
        draft = propose_condition_timing(
            project, presentation_counts=presentation_counts, clear_saved_condition_order=True,
        )
        counts = condition_presentation_counts(draft)
        if sum(counts.values()) > 10_000:
            raise ValueError("Condition order preview supports at most 10,000 presentations.")
        seed = (configured_randomization_seeds(project).condition_order_seed
                if condition_order_seed is None else condition_order_seed)
        if type(seed) is not int or not 0 <= seed < 2**31:
            raise ValueError("Condition-order seed must be an integer from 0 to 2147483647.")
        return constrained_condition_order(counts, rng=random.Random(seed))


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
