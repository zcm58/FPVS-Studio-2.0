"""Assemble matched image conditions with modular backward-counting assignments."""

from __future__ import annotations

from fpvs_studio.core.condition_modifiers import assign_modifier, create_backward_counting_modifier
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.models import Condition, ImageResolution, ProjectFile, StimulusSet


def populate_cognitive_load_fpvs(project: ProjectFile) -> ProjectFile:
    """Populate an empty Cognitive Load FPVS project with three matched image pairs."""
    if project.experiment_category != ExperimentCategory.COGNITIVE_LOAD_FPVS:
        raise ValueError("The cognitive-load preset requires a Cognitive Load FPVS experiment.")
    if project.conditions or project.stimulus_sets or project.task_modules:
        raise ValueError("The cognitive-load preset requires a new, empty project.")
    sets = [
        StimulusSet(
            set_id=f"placeholder-{index}-{role}",
            name=f"Placeholder {index} {role}",
            source_dir=f"stimuli/original-images/placeholder-{index}-{role}",
            resolution=ImageResolution(width_px=512, height_px=512),
            image_count=1,
        )
        for index in range(1, 4) for role in ("base", "oddball")
    ]
    settings = project.settings.model_copy(deep=True)
    settings.session.block_count = 1
    settings.session.randomize_conditions_per_block = True
    conditions: list[Condition] = []
    for index in range(1, 4):
        for load in (False, True):
            conditions.append(Condition(
                condition_id=f"condition-{index}-{'load' if load else 'no-load'}",
                name=f"Condition {index} — {'Cognitive load' if load else 'No load'}",
                instructions=(
                    "Watch the images and keep looking at the central cross. "
                    + ("You will receive a backward-counting assignment before the images begin."
                       if load else "You do not need to count backwards during this condition.")
                ),
                base_stimulus_set_id=f"placeholder-{index}-base",
                oddball_stimulus_set_id=f"placeholder-{index}-oddball",
                sequence_count=settings.condition_defaults.sequence_count,
                oddball_cycle_repeats_per_sequence=(
                    settings.condition_defaults.oddball_cycle_repeats_per_sequence
                ),
                duty_cycle_mode=settings.condition_defaults.duty_cycle_mode,
                trigger_code=(index - 1) * 2 + (2 if load else 1),
                order_index=len(conditions),
            ))
    populated = project.model_copy(update={
        "settings": settings, "stimulus_sets": sets,
        "conditions": conditions,
    })
    return assign_modifier(populated, create_backward_counting_modifier(),
                           [condition.condition_id for condition in conditions
                            if condition.condition_id.endswith("-load")
                            and not condition.condition_id.endswith("-no-load")])
