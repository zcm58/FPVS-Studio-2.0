"""Project category labels and recoverable authoring conflicts.

Loading preserves incompatible legacy conditions. Saving and compilation call the
same guard so selecting only one condition cannot bypass a project-wide conflict.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.models import ValidationIssue


class CategoryCondition(Protocol):
    """Category-relevant fields shared by project and portable config conditions."""

    @property
    def condition_id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def attentional_blink(self) -> object | None: ...

    @property
    def t2_stimulus_set_id(self) -> str | None: ...

    @property
    def isi_stimulus_set_id(self) -> str | None: ...


class CategoryProject(Protocol):
    """Project category view used at editable and portable persistence boundaries."""

    @property
    def experiment_category(self) -> ExperimentCategory: ...

    @property
    def conditions(self) -> Sequence[CategoryCondition]: ...


def experiment_category_label(category: ExperimentCategory) -> str:
    """Return the user-facing name of an experiment category."""

    return {
        ExperimentCategory.FPVS: "FPVS",
        ExperimentCategory.FPVS_ODDBALL: "FPVS-Oddball",
        ExperimentCategory.ATTENTIONAL_BLINK: "Attentional-Blink",
    }[category]


def category_conflict_condition_ids(project: CategoryProject) -> tuple[str, ...]:
    """Identify incompatible conditions without converting or discarding them."""

    if project.experiment_category == ExperimentCategory.FPVS:
        return tuple(condition.condition_id for condition in project.conditions)
    is_ab = project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
    return tuple(
        condition.condition_id
        for condition in project.conditions
        if (
            condition.attentional_blink is None
            if is_ab
            else condition.attentional_blink is not None
            or condition.t2_stimulus_set_id is not None
            or condition.isi_stimulus_set_id is not None
        )
    )


def validate_experiment_category(project: CategoryProject) -> list[ValidationIssue]:
    """Report unsupported categories and conditions requiring explicit separation."""

    if project.experiment_category == ExperimentCategory.FPVS:
        return [ValidationIssue(
            location="experiment_category",
            message="FPVS is coming soon. Create an FPVS-Oddball or Attentional-Blink experiment.",
        )]
    conflicts = set(category_conflict_condition_ids(project))
    label = experiment_category_label(project.experiment_category)
    issues = [
        ValidationIssue(
            location=f"conditions.{condition.condition_id}.experiment_category",
            message=(
                f"Condition '{condition.name}' is incompatible with this {label} experiment. "
                "Separate it into an experiment of the matching category before saving, "
                "exporting, or running. Existing timing and image sources are preserved."
            ),
        )
        for condition in project.conditions
        if condition.condition_id in conflicts
    ]
    layouts = {
        getattr(condition.attentional_blink, "layout", "within_slot")
        for condition in project.conditions if condition.attentional_blink is not None
    }
    if len(layouts) > 1:
        issues.append(ValidationIssue(
            location="conditions.attentional_blink.layout",
            message=(
                "Letter-stream and within-slot attentional-blink designs must be in separate "
                "experiments. Existing target schedules are preserved."
            ),
        ))
    return issues


def require_valid_experiment_category(project: CategoryProject) -> None:
    """Reject unsupported or mixed projects at persistence and execution boundaries."""

    issues = validate_experiment_category(project)
    if issues:
        raise ValueError(" ".join(issue.message for issue in issues))
