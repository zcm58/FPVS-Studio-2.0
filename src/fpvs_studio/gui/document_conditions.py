"""Condition editing helpers for the GUI project document facade."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fpvs_studio.core.condition_template_profiles import (
    apply_condition_defaults_to_condition,
    apply_condition_template_profile_to_settings,
)
from fpvs_studio.core.models import (
    Condition,
    ConditionDefaults,
    ConditionTemplateProfile,
    ProjectFile,
    StimulusSet,
)
from fpvs_studio.core.paths import (
    slugify_project_name,
    stimulus_originals_dir,
    to_project_relative_posix,
)
from fpvs_studio.gui.document_support import (
    ConditionStimulusRow,
    DocumentError,
    validated_copy,
)

if TYPE_CHECKING:
    from fpvs_studio.core.enums import StimulusVariant


class DocumentConditionMixin:
    """Condition and stimulus-set mutation methods for `ProjectDocument`."""

    if TYPE_CHECKING:
        _project: ProjectFile
        _project_root: Path

        def _apply_project_update(self, **updates: object) -> None: ...
        def _replace_project(self, project: ProjectFile) -> None: ...

    def condition_rows(self) -> list[ConditionStimulusRow]:
        """Return condition-role rows for the assets page."""

        rows: list[ConditionStimulusRow] = []
        for condition in self.ordered_conditions():
            base_set = self.get_stimulus_set(condition.base_stimulus_set_id)
            oddball_set = self.get_stimulus_set(condition.oddball_stimulus_set_id)
            if base_set is not None:
                rows.append(
                    ConditionStimulusRow(
                        condition_id=condition.condition_id,
                        condition_name=condition.name,
                        role="base",
                        stimulus_set=base_set,
                    )
                )
            if oddball_set is not None:
                rows.append(
                    ConditionStimulusRow(
                        condition_id=condition.condition_id,
                        condition_name=condition.name,
                        role="oddball",
                        stimulus_set=oddball_set,
                    )
                )
        return rows

    def ordered_conditions(self) -> list[Condition]:
        """Return conditions in stored project order."""

        return sorted(self._project.conditions, key=lambda item: item.order_index)

    def get_condition(self, condition_id: str) -> Condition | None:
        """Return one condition by id."""

        for condition in self._project.conditions:
            if condition.condition_id == condition_id:
                return condition
        return None

    def get_stimulus_set(self, set_id: str) -> StimulusSet | None:
        """Return one stimulus set by id."""

        for stimulus_set in self._project.stimulus_sets:
            if stimulus_set.set_id == set_id:
                return stimulus_set
        return None

    def get_condition_stimulus_set(self, condition_id: str, role: str) -> StimulusSet:
        """Return the base or oddball stimulus set for one condition."""

        condition = self.get_condition(condition_id)
        if condition is None:
            raise DocumentError(f"Unknown condition '{condition_id}'.")
        set_id = (
            condition.base_stimulus_set_id if role == "base" else condition.oddball_stimulus_set_id
        )
        stimulus_set = self.get_stimulus_set(set_id)
        if stimulus_set is None:
            raise DocumentError(f"Condition '{condition.name}' is missing its {role} stimulus set.")
        return stimulus_set

    def set_supported_variants(self, variants: list[StimulusVariant]) -> None:
        """Persist the project-level supported materialization variants."""

        from fpvs_studio.core.enums import StimulusVariant

        ordered_variants = list(dict.fromkeys([StimulusVariant.ORIGINAL, *variants]))
        settings = validated_copy(self._project.settings, supported_variants=ordered_variants)
        self._apply_project_update(settings=settings)

    def apply_condition_template_profile(
        self,
        profile: ConditionTemplateProfile,
        *,
        apply_to_existing_conditions: bool = False,
    ) -> None:
        """Snapshot one condition-template profile into project settings."""

        settings = apply_condition_template_profile_to_settings(self._project.settings, profile)
        project = validated_copy(self._project, settings=settings)
        if apply_to_existing_conditions:
            defaults = project.settings.condition_defaults
            conditions = [
                apply_condition_defaults_to_condition(condition, defaults)
                for condition in self.ordered_conditions()
            ]
            project = validated_copy(
                project,
                conditions=self._reindex_conditions(conditions),
            )
        self._replace_project(project)

    def apply_condition_defaults_to_all_conditions(
        self,
        *,
        defaults: ConditionDefaults | None = None,
    ) -> None:
        """Apply one condition-default snapshot to all conditions in project order."""

        resolved_defaults = defaults or self._project.settings.condition_defaults
        conditions = [
            apply_condition_defaults_to_condition(condition, resolved_defaults)
            for condition in self.ordered_conditions()
        ]
        project = validated_copy(
            self._project,
            conditions=self._reindex_conditions(conditions),
        )
        self._replace_project(project)

    def create_condition(self, *, name: str | None = None) -> str:
        """Create one new condition plus dedicated base/oddball stimulus sets."""

        ordered_conditions = self.ordered_conditions()
        defaults = self._project.settings.condition_defaults
        display_name = name or f"Condition {len(ordered_conditions) + 1}"
        existing_condition_ids = {condition.condition_id for condition in self._project.conditions}
        existing_set_ids = {stimulus_set.set_id for stimulus_set in self._project.stimulus_sets}
        condition_id = self._unique_slug(display_name, existing_condition_ids)
        base_set_id = self._unique_slug(f"{condition_id}-base", existing_set_ids)
        oddball_set_id = self._unique_slug(
            f"{condition_id}-oddball", existing_set_ids | {base_set_id}
        )

        new_condition = Condition(
            condition_id=condition_id,
            name=display_name,
            base_stimulus_set_id=base_set_id,
            oddball_stimulus_set_id=oddball_set_id,
            sequence_count=defaults.sequence_count,
            oddball_cycle_repeats_per_sequence=defaults.oddball_cycle_repeats_per_sequence,
            duty_cycle_mode=defaults.duty_cycle_mode,
            trigger_code=len(ordered_conditions) + 1,
            order_index=len(ordered_conditions),
        )
        new_sets = [
            self._make_empty_stimulus_set(base_set_id, f"{display_name} Base"),
            self._make_empty_stimulus_set(oddball_set_id, f"{display_name} Oddball"),
        ]
        conditions = [*ordered_conditions, new_condition]
        project = validated_copy(
            self._project,
            conditions=self._reindex_conditions(conditions),
            stimulus_sets=[*self._project.stimulus_sets, *new_sets],
        )
        self._replace_project(project)
        return condition_id

    def remove_condition(self, condition_id: str) -> None:
        """Remove one condition and any unreferenced stimulus sets."""

        condition = self.get_condition(condition_id)
        if condition is None:
            raise DocumentError(f"Unknown condition '{condition_id}'.")
        remaining_conditions = [
            item for item in self.ordered_conditions() if item.condition_id != condition_id
        ]
        referenced_set_ids = {
            set_id
            for item in remaining_conditions
            for set_id in (item.base_stimulus_set_id, item.oddball_stimulus_set_id)
        }
        remaining_sets = [
            stimulus_set
            for stimulus_set in self._project.stimulus_sets
            if stimulus_set.set_id in referenced_set_ids
        ]
        project = validated_copy(
            self._project,
            conditions=self._reindex_conditions(remaining_conditions),
            stimulus_sets=remaining_sets,
        )
        self._replace_project(project)

    def move_condition(self, condition_id: str, *, offset: int) -> None:
        """Move one condition up or down within the ordered condition list."""

        ordered_conditions = self.ordered_conditions()
        current_index = next(
            (
                index
                for index, item in enumerate(ordered_conditions)
                if item.condition_id == condition_id
            ),
            None,
        )
        if current_index is None:
            raise DocumentError(f"Unknown condition '{condition_id}'.")
        target_index = current_index + offset
        if target_index < 0 or target_index >= len(ordered_conditions):
            return
        ordered_conditions[current_index], ordered_conditions[target_index] = (
            ordered_conditions[target_index],
            ordered_conditions[current_index],
        )
        project = validated_copy(
            self._project,
            conditions=self._reindex_conditions(ordered_conditions),
        )
        self._replace_project(project)

    def update_condition(self, condition_id: str, **updates: object) -> None:
        """Update one condition by id through Pydantic validation."""

        conditions: list[Condition] = []
        found = False
        for condition in self.ordered_conditions():
            if condition.condition_id == condition_id:
                condition = validated_copy(condition, **updates)
                found = True
            conditions.append(condition)
        if not found:
            raise DocumentError(f"Unknown condition '{condition_id}'.")
        project = validated_copy(
            self._project,
            conditions=self._reindex_conditions(conditions),
        )
        self._replace_project(project)

    def _make_empty_stimulus_set(self, set_id: str, name: str) -> StimulusSet:
        source_dir = to_project_relative_posix(
            self._project_root,
            stimulus_originals_dir(self._project_root, set_id),
        )
        return StimulusSet(
            set_id=set_id,
            name=name,
            source_dir=source_dir,
            image_count=0,
        )

    def _reindex_conditions(self, conditions: list[Condition]) -> list[Condition]:
        return [
            condition.model_copy(update={"order_index": index})
            for index, condition in enumerate(conditions)
        ]

    def _unique_slug(self, preferred_name: str, existing_ids: set[str]) -> str:
        base = slugify_project_name(preferred_name)
        candidate = base
        suffix = 2
        while candidate in existing_ids:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate
