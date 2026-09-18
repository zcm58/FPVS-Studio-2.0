"""Read-only authoring inputs prepared for one compilation invocation.

The context is never retained by a compiled plan or shared across launches. Random
draws and mutable execution contracts remain owned by each individual run.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from fpvs_studio.core.compiler_assets import load_manifest, resolve_stimulus_items
from fpvs_studio.core.compiler_conditions import validate_selected_condition
from fpvs_studio.core.compiler_presentation import compile_condition_presentation
from fpvs_studio.core.compiler_schedules import StimulusScheduleItem
from fpvs_studio.core.enums import StimulusVariant
from fpvs_studio.core.models import (
    Condition,
    ProjectFile,
    StimulusPresentationDefaults,
    StimulusSet,
    TemplateSpec,
)
from fpvs_studio.core.run_spec import ConditionPresentationSpec, StimulusRole
from fpvs_studio.core.template_library import get_template
from fpvs_studio.preprocessing.models import StimulusManifest


@dataclass(frozen=True)
class PreparedCondition:
    base_set: StimulusSet
    oddball_set: StimulusSet
    presentation: ConditionPresentationSpec
    role_presentations: dict[StimulusRole, StimulusPresentationDefaults]


class CompilationInputs:
    """Cache validated, deterministic inputs without caching any seeded run result."""

    def __init__(
        self, project: ProjectFile, *, refresh_hz: float,
        project_root: Path | None, manifest: StimulusManifest | None,
    ) -> None:
        self.project = project
        self.refresh_hz = refresh_hz
        self.project_root = project_root
        self._supplied_manifest = manifest
        self._stimulus_sets = {item.set_id: item for item in project.stimulus_sets}
        self._conditions: dict[str, PreparedCondition] = {}
        self._items: dict[tuple[str, StimulusVariant], list[StimulusScheduleItem]] = {}

    @cached_property
    def manifest(self) -> StimulusManifest | None:
        # cached_property also remembers an absent manifest, avoiding repeated disk probes.
        return load_manifest(self.project_root, self._supplied_manifest)

    @cached_property
    def template(self) -> TemplateSpec:
        return get_template(self.project.meta.template_id)

    def condition(self, condition: Condition) -> PreparedCondition:
        if condition.condition_id not in self._conditions:
            base_set, oddball_set = validate_selected_condition(
                self.project, condition, refresh_hz=self.refresh_hz,
                stimulus_sets=self._stimulus_sets,
            )
            presentation, roles = compile_condition_presentation(
                project_presentation=self.project.settings.presentation,
                condition=condition, base_set=base_set, oddball_set=oddball_set,
            )
            self._conditions[condition.condition_id] = PreparedCondition(
                base_set, oddball_set, presentation, roles,
            )
        return self._conditions[condition.condition_id]

    def stimulus_items(
        self, stimulus_set: StimulusSet, variant: StimulusVariant,
    ) -> list[StimulusScheduleItem]:
        key = (stimulus_set.set_id, variant)
        if key not in self._items:
            self._items[key] = resolve_stimulus_items(
                stimulus_set, variant=variant, project_root=self.project_root,
                manifest=self.manifest,
            )
        return self._items[key]
