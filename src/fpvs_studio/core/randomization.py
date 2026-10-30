"""Configured/resolved seed snapshots and stable independent schedule namespaces."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Sequence
from typing import TYPE_CHECKING, Final, Literal

from fpvs_studio.core.compiler_support import CompileError
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.masking import condition_masking
from fpvs_studio.core.models import Condition, ProjectFile, RandomizationSeeds, SessionSettings

if TYPE_CHECKING:
    from fpvs_studio.core.run_spec import RunRandomizationSpec

RANDOMIZATION_ALGORITHM_VERSION: Final = 1


def supports_independent_randomization(
    project: ProjectFile, conditions: Sequence[Condition] | None = None,
) -> bool:
    """Keep native AB and specialized masking controls on their existing contracts."""

    selected = project.conditions if conditions is None else conditions
    return (
        project.experiment_category != ExperimentCategory.ATTENTIONAL_BLINK
        and not any(condition_masking(project, condition) is not None
                    for condition in selected)
    )


def effective_randomization_mode(project: ProjectFile) -> Literal["fixed", "new"]:
    """Legacy absence means fresh launch resolution, without rewriting the source."""

    return project.settings.session.randomization_mode or "new"


def derive_schedule_seed(
    seed: int, *, domain: str, condition_id: str, presentation_index: int,
) -> int:
    """Hash stable scientific identities; never use Python hash or execution IDs."""

    if type(seed) is not int or seed < 0:
        raise ValueError("Schedule seed must be a nonnegative integer.")
    if type(presentation_index) is not int or presentation_index < 1:
        raise ValueError("Presentation index must be a positive integer.")
    encoded = json.dumps(
        ["fpvs-independent-randomization", RANDOMIZATION_ALGORITHM_VERSION,
         domain, seed, condition_id, presentation_index], separators=(",", ":"),
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big") % (2**31)


def configured_randomization_seeds(project: ProjectFile) -> RandomizationSeeds:
    """Read explicit seeds or derive a deterministic bridge from the old shared seed."""

    session = SessionSettings.model_validate(project.settings.session.model_dump())
    if not 0 <= session.session_seed < 2**31:
        raise ValueError(
            "Edit the condition-order seed to an integer from 0 to 2147483647 "
            "before using independent randomization."
        )
    return RandomizationSeeds(
        condition_order_seed=session.session_seed,
        stimulus_seed=(session.stimulus_seed if session.stimulus_seed is not None else
                       derive_schedule_seed(session.session_seed, domain="legacy-stimulus-root",
                                            condition_id="", presentation_index=1)),
        fixation_seed=(session.fixation_seed if session.fixation_seed is not None else
                       derive_schedule_seed(session.session_seed, domain="legacy-fixation-root",
                                            condition_id="", presentation_index=1)),
    )


def generate_randomization_seeds() -> RandomizationSeeds:
    """Resolve fresh entropy once in authoring/launch coordination, never in compilation."""

    entropy = random.SystemRandom()
    return RandomizationSeeds(
        condition_order_seed=entropy.randrange(2**31),
        stimulus_seed=entropy.randrange(2**31), fixation_seed=entropy.randrange(2**31),
    )


def resolve_randomization_seeds(
    project: ProjectFile, *, resolved_seeds: RandomizationSeeds | None,
    condition_order_seed: int | None = None,
) -> RandomizationSeeds:
    """Validate one snapshot, rejecting stale overrides of configured fixed seeds."""

    configured = configured_randomization_seeds(project)
    resolved = (RandomizationSeeds.model_validate(resolved_seeds.model_dump())
                if resolved_seeds is not None else configured)
    if condition_order_seed is not None:
        if resolved_seeds is not None and condition_order_seed != resolved.condition_order_seed:
            raise CompileError("Condition-order seed disagrees with the resolved seed snapshot.")
        resolved = RandomizationSeeds.model_validate({
            **resolved.model_dump(), "condition_order_seed": condition_order_seed,
        })
    if effective_randomization_mode(project) == "fixed" and resolved != configured:
        raise CompileError("Fixed randomization must use the configured seed triplet.")
    return resolved


def run_randomization_spec(
    project: ProjectFile, seeds: RandomizationSeeds, *, condition_id: str,
    presentation_index: int,
) -> RunRandomizationSpec:
    """Resolve stimulus, count and onset namespaces for one chronological occurrence."""

    from fpvs_studio.core.run_spec import RunRandomizationSpec

    return RunRandomizationSpec(
        mode=effective_randomization_mode(project), seeds=seeds,
        condition_presentation_index=presentation_index,
        stimulus_order_seed=derive_schedule_seed(
            seeds.stimulus_seed, domain="stimulus-order", condition_id=condition_id,
            presentation_index=presentation_index,
        ),
        fixation_count_seed=derive_schedule_seed(
            seeds.fixation_seed, domain="fixation-count", condition_id=condition_id,
            presentation_index=presentation_index,
        ),
        fixation_onset_seed=derive_schedule_seed(
            seeds.fixation_seed, domain="fixation-onset", condition_id=condition_id,
            presentation_index=presentation_index,
        ),
    )


def randomization_protocol_identity(project: ProjectFile) -> dict[str, object] | None:
    """Include fixed authored seeds; fresh seed values are execution provenance only."""

    if project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK:
        return None
    if project.conditions and all(condition_masking(project, item) is not None
                                  for item in project.conditions):
        return None
    mode = effective_randomization_mode(project)
    identity: dict[str, object] = {
        "mode": mode, "algorithm_version": RANDOMIZATION_ALGORITHM_VERSION,
    }
    if mode == "fixed":
        identity["seeds"] = configured_randomization_seeds(project).model_dump()
    return identity
