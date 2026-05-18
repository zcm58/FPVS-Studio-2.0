"""Condition selection and validation helpers for run/session compilation."""

from __future__ import annotations

from fpvs_studio.core.compiler_support import CompileError
from fpvs_studio.core.enums import DutyCycleMode, StimulusModality
from fpvs_studio.core.frame_validation import (
    FrameValidationError,
    frames_per_stimulus,
    on_off_frames,
)
from fpvs_studio.core.models import Condition, ProjectFile, StimulusSet
from fpvs_studio.core.template_library import get_template


def ordered_conditions(project: ProjectFile) -> list[Condition]:
    """Return project conditions in stable project order."""

    return sorted(project.conditions, key=lambda item: item.order_index)


def select_condition(project: ProjectFile, condition_id: str | None) -> Condition:
    """Select one condition to compile."""

    project_conditions = ordered_conditions(project)
    if not project_conditions:
        raise CompileError("Project has no conditions to compile.")
    if condition_id is None:
        if len(project_conditions) > 1:
            raise CompileError(
                "condition_id is required when the project contains more than one condition."
            )
        return project_conditions[0]
    for condition in project_conditions:
        if condition.condition_id == condition_id:
            return condition
    raise CompileError(f"Unknown condition_id '{condition_id}'.")


def select_conditions(
    project: ProjectFile,
    condition_ids: list[str] | None,
) -> list[Condition]:
    """Select the condition pool for session compilation."""

    project_conditions = ordered_conditions(project)
    if not project_conditions:
        raise CompileError("Project has no conditions to compile.")
    if condition_ids is None:
        return project_conditions

    if len(condition_ids) != len(set(condition_ids)):
        raise CompileError("condition_ids must not contain duplicates.")

    selected_ids = set(condition_ids)
    selected_conditions = [
        condition for condition in project_conditions if condition.condition_id in selected_ids
    ]
    if len(selected_conditions) != len(condition_ids):
        known_ids = {condition.condition_id for condition in project_conditions}
        missing_ids = sorted(selected_ids - known_ids)
        raise CompileError(
            "Unknown condition_ids requested for session compilation: " + ", ".join(missing_ids)
        )
    return selected_conditions


def validate_selected_condition(
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
    if base_set.modality != oddball_set.modality:
        raise CompileError(
            f"Condition '{condition.name}' cannot mix base {base_set.modality.value} "
            f"stimuli with oddball {oddball_set.modality.value} stimuli."
        )
    if base_set.modality == StimulusModality.IMAGE:
        if base_set.image_count <= 0:
            raise CompileError(
                f"Stimulus set '{base_set.name}' does not contain any imported images."
            )
        if oddball_set.image_count <= 0:
            raise CompileError(
                f"Stimulus set '{oddball_set.name}' does not contain any imported images."
            )
        if base_set.source_dir == oddball_set.source_dir:
            raise CompileError(
                f"Condition '{condition.name}' cannot use the same folder for base "
                "and oddball images."
            )
        for role_label, stimulus_set in (("Base", base_set), ("Oddball", oddball_set)):
            if stimulus_set.resolution is None:
                raise CompileError(
                    f"{role_label} stimulus set '{stimulus_set.name}' must be normalized "
                    "to square images before launch."
                )
            if stimulus_set.resolution.width_px != stimulus_set.resolution.height_px:
                raise CompileError(
                    f"{role_label} stimulus set '{stimulus_set.name}' uses non-square "
                    f"{stimulus_set.resolution.width_px}x{stimulus_set.resolution.height_px} "
                    "images. Normalize the selected images to square PNG copies before launch."
                )
    elif base_set.modality == StimulusModality.WORD:
        if not base_set.words:
            raise CompileError(f"Stimulus set '{base_set.name}' does not contain any words.")
        if not oddball_set.words:
            raise CompileError(f"Stimulus set '{oddball_set.name}' does not contain any words.")
    else:
        raise CompileError(
            f"Condition '{condition.name}' uses unsupported stimulus modality "
            f"'{base_set.modality}'."
        )
    if condition.duty_cycle_mode == DutyCycleMode.BLANK_50:
        try:
            on_off_frames(
                frames_per_stimulus(refresh_hz, template.base_hz), condition.duty_cycle_mode
            )
        except FrameValidationError as exc:
            raise CompileError(str(exc)) from exc
    return base_set, oddball_set
