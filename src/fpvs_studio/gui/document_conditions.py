"""Condition editing helpers for the GUI project document facade."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from fpvs_studio.core.attentional_blink_presets import (
    is_attentional_blink_stream_project,
    populate_attentional_blink_stream,
)
from fpvs_studio.core.attentional_blink_stream import validate_attentional_blink_stream_symbols
from fpvs_studio.core.condition_template_profiles import (
    apply_condition_defaults_to_condition,
    apply_condition_template_profile_to_settings,
    require_profile_category,
)
from fpvs_studio.core.enums import (
    DutyCycleMode,
    ExperimentCategory,
    StimulusModality,
    StimulusTransform,
    StimulusVariant,
)
from fpvs_studio.core.experiment_categories import (
    RETIRED_IMAGE_PAIR_MESSAGE,
    has_retired_image_pair_design,
)
from fpvs_studio.core.models import (
    AttentionalBlinkSettings,
    AttentionalBlinkStreamSettings,
    Condition,
    ConditionDefaults,
    ConditionPresentationSettings,
    ConditionTemplateProfile,
    ProjectFile,
    StimulusSet,
)
from fpvs_studio.core.paths import (
    slugify_project_name,
    stimulus_originals_dir,
    to_project_relative_posix,
)
from fpvs_studio.core.task_assets import copy_task_asset
from fpvs_studio.core.task_models import TaskBinding, TaskModule
from fpvs_studio.core.validation import validate_attentional_blink_condition
from fpvs_studio.gui.document_support import (
    ConditionStimulusRow,
    DocumentError,
    validated_copy,
)


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
        """Return a condition's named image source, including its independent T2 pool."""

        condition = self.get_condition(condition_id)
        if condition is None:
            raise DocumentError(f"Unknown condition '{condition_id}'.")
        set_id: str | None
        if role == "base":
            set_id = condition.base_stimulus_set_id
        elif role in ("oddball", "t1"):
            set_id = condition.oddball_stimulus_set_id
        elif role in ("isi", "separator"):
            set_id = condition.isi_stimulus_set_id
        elif role == "t2":
            set_id = condition.t2_stimulus_set_id
        else:
            raise DocumentError(f"Unknown stimulus role '{role}'.")
        if set_id is None:
            raise DocumentError(f"Choose the {role.upper()} image folder first.")
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

        require_profile_category(profile, self._project.experiment_category)
        if self._project.conditions and (
            is_attentional_blink_stream_project(self._project)
            != (profile.defaults.attentional_blink_layout == "letter_stream")
        ):
            raise DocumentError("Choose a template for this experiment's existing design layout.")
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
        if (
            self._project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
            and resolved_defaults.duty_cycle_mode != DutyCycleMode.CONTINUOUS
        ):
            raise DocumentError("Attentional-Blink requires continuous target-pair presentation.")
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
        """Create a condition with the sources required by its locked experiment type."""

        if self._project.experiment_category == ExperimentCategory.FPVS:
            raise DocumentError("Standard FPVS is coming soon.")
        if is_attentional_blink_stream_project(self._project):
            return self._create_stream_condition(name=name)
        if self._project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK:
            raise DocumentError(RETIRED_IMAGE_PAIR_MESSAGE)
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
            self._make_empty_stimulus_set(
                oddball_set_id, f"{display_name} Oddball"
            ),
        ]
        conditions = [*ordered_conditions, new_condition]
        project = validated_copy(
            self._project,
            conditions=self._reindex_conditions(conditions),
            stimulus_sets=[*self._project.stimulus_sets, *new_sets],
        )
        self._replace_project(project)
        return condition_id

    def _create_stream_condition(self, *, name: str | None) -> str:
        """Add an SOA condition sharing the study's digit and target pools."""
        project = self._project
        ordered = self.ordered_conditions()
        if ordered:
            prototype = ordered[0]
        else:
            seeded = populate_attentional_blink_stream(
                validated_copy(project, stimulus_sets=[], task_modules=[])
            )
            prototype = seeded.conditions[0]
            existing_tasks = {task.task_id for task in project.task_modules}
            project = validated_copy(
                project, stimulus_sets=seeded.stimulus_sets,
                task_modules=[*project.task_modules, *[
                    task for task in seeded.task_modules if task.task_id not in existing_tasks
                ]],
            )
        display_name = name or f"Condition {len(ordered) + 1}"
        condition_id = self._unique_slug(display_name, {c.condition_id for c in ordered})
        defaults = project.settings.condition_defaults
        condition = validated_copy(
            prototype, condition_id=condition_id, name=display_name,
            sequence_count=defaults.sequence_count,
            oddball_cycle_repeats_per_sequence=defaults.oddball_cycle_repeats_per_sequence,
            order_index=len(ordered), trigger_code=self._next_stream_condition_trigger(),
        )
        self._replace_project(validated_copy(project, conditions=[*ordered, condition]))
        return condition_id

    def _next_stream_condition_trigger(self) -> int:
        used = {c.trigger_code for c in self._project.conditions}
        used.add(self._project.settings.triggers.oddball_trigger_code)
        used.update(
            c.attentional_blink.t2_trigger_code for c in self._project.conditions
            if c.attentional_blink is not None
        )
        for code in range(1, 256):
            if code not in used:
                return code
        raise DocumentError("No unused condition marker is available.")

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
            for set_id in (
                item.base_stimulus_set_id,
                item.oddball_stimulus_set_id,
                item.t2_stimulus_set_id,
                item.isi_stimulus_set_id,
            )
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

    def duplicate_condition(self, condition_id: str) -> str:
        """Duplicate condition metadata with new empty base/oddball stimulus sets."""

        if has_retired_image_pair_design(self._project):
            raise DocumentError(RETIRED_IMAGE_PAIR_MESSAGE)

        source_condition = self.get_condition(condition_id)
        if source_condition is None:
            raise DocumentError(f"Unknown condition '{condition_id}'.")

        ordered_conditions = self.ordered_conditions()
        existing_condition_ids = {condition.condition_id for condition in self._project.conditions}
        existing_set_ids = {stimulus_set.set_id for stimulus_set in self._project.stimulus_sets}
        copy_name = f"{source_condition.name} Copy"
        existing_names = {condition.name for condition in ordered_conditions}
        suffix = 2
        while copy_name in existing_names:
            copy_name = f"{source_condition.name} Copy {suffix}"
            suffix += 1
        new_condition_id = self._unique_slug(copy_name, existing_condition_ids)
        if isinstance(source_condition.attentional_blink, AttentionalBlinkStreamSettings):
            duplicate = validated_copy(
                source_condition, condition_id=new_condition_id, name=copy_name,
                trigger_code=self._next_stream_condition_trigger(),
                order_index=len(ordered_conditions),
            )
            self._replace_project(validated_copy(
                self._project, conditions=[*ordered_conditions, duplicate],
            ))
            return new_condition_id
        base_set_id = self._unique_slug(f"{new_condition_id}-base", existing_set_ids)
        oddball_set_id = self._unique_slug(
            f"{new_condition_id}-oddball", existing_set_ids | {base_set_id}
        )
        t2_set_id = (
            self._unique_slug(
                f"{new_condition_id}-t2", existing_set_ids | {base_set_id, oddball_set_id}
            )
            if source_condition.t2_stimulus_set_id is not None
            else None
        )
        isi_set_id = (
            self._unique_slug(f"{new_condition_id}-isi", existing_set_ids)
            if source_condition.isi_stimulus_set_id is not None else None
        )
        duplicated_condition = source_condition.model_copy(
            deep=True,
            update={
                "condition_id": new_condition_id,
                "name": copy_name,
                "base_stimulus_set_id": base_set_id,
                "oddball_stimulus_set_id": oddball_set_id,
                "t2_stimulus_set_id": t2_set_id,
                "isi_stimulus_set_id": isi_set_id,
                "trigger_code": len(ordered_conditions) + 1,
                "order_index": len(ordered_conditions),
            }
        )
        source_base_set = self.get_condition_stimulus_set(condition_id, "base")
        source_oddball_set = self.get_condition_stimulus_set(condition_id, "oddball")
        if source_base_set.modality == StimulusModality.WORD:
            new_sets = [
                StimulusSet(
                    set_id=base_set_id,
                    name=f"{copy_name} Base",
                    modality=StimulusModality.WORD,
                    source_dir=None,
                    words=list(source_base_set.words),
                ),
                StimulusSet(
                    set_id=oddball_set_id,
                    name=f"{copy_name} Oddball",
                    modality=StimulusModality.WORD,
                    source_dir=None,
                    words=list(source_oddball_set.words),
                ),
            ]
        else:
            new_sets = [
                self._make_empty_stimulus_set(base_set_id, f"{copy_name} Base"),
                self._make_empty_stimulus_set(oddball_set_id, f"{copy_name} Oddball"),
            ]
        if t2_set_id is not None:
            new_sets.append(self._make_empty_stimulus_set(t2_set_id, f"{copy_name} T2"))
        if isi_set_id is not None:
            new_sets.append(self._make_empty_stimulus_set(isi_set_id, f"{copy_name} ISI"))
        project = validated_copy(
            self._project,
            conditions=self._reindex_conditions([*ordered_conditions, duplicated_condition]),
            stimulus_sets=[*self._project.stimulus_sets, *new_sets],
        )
        self._replace_project(project)
        return new_condition_id

    def create_control_condition(
        self,
        source_condition_id: str,
        *,
        variant: StimulusVariant,
        transform: StimulusTransform | None = None,
        name: str | None = None,
    ) -> str:
        """Create a file-backed or runtime-transformed control condition."""

        if has_retired_image_pair_design(self._project):
            raise DocumentError(RETIRED_IMAGE_PAIR_MESSAGE)

        if variant == StimulusVariant.ORIGINAL and transform in {
            None,
            StimulusTransform.NONE,
        }:
            raise DocumentError(
                "Control conditions must use a derived stimulus variant or runtime transform."
            )

        source_condition = self.get_condition(source_condition_id)
        if source_condition is None:
            raise DocumentError(f"Unknown condition '{source_condition_id}'.")
        source_base_set = self.get_condition_stimulus_set(source_condition_id, "base")
        if source_base_set.modality != StimulusModality.IMAGE:
            raise DocumentError("Control conditions are only available for image conditions.")

        ordered_conditions = self.ordered_conditions()
        existing_condition_ids = {condition.condition_id for condition in self._project.conditions}
        control_name = self._unique_condition_name(
            name
            or self._default_control_condition_name(
                source_condition.name,
                variant,
                transform=transform,
            ),
            {condition.name for condition in ordered_conditions},
        )
        new_condition_id = self._unique_slug(control_name, existing_condition_ids)
        presentation = source_condition.presentation
        if transform is not None:
            presentation = presentation.model_copy(
                update={
                    "common": presentation.common.model_copy(
                        update={"transform": transform},
                        deep=True,
                    ),
                    "base": presentation.base.model_copy(
                        update={"transform": None},
                        deep=True,
                    ),
                    "oddball": presentation.oddball.model_copy(
                        update={"transform": None},
                        deep=True,
                    ),
                },
                deep=True,
            )
        control_condition = source_condition.model_copy(
            deep=True,
            update={
                "condition_id": new_condition_id,
                "name": control_name,
                "stimulus_variant": variant,
                "presentation": presentation,
                "trigger_code": len(ordered_conditions) + 1,
                "order_index": len(ordered_conditions),
            }
        )
        project = validated_copy(
            self._project,
            conditions=self._reindex_conditions([*ordered_conditions, control_condition]),
        )
        self._replace_project(project)
        return new_condition_id

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

        ab = self._project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
        if "attentional_blink" in updates and (updates["attentional_blink"] is not None) != ab:
            raise DocumentError("The design must match the locked experiment type.")
        existing = self.get_condition(condition_id)
        if (
            ab and existing is not None and existing.attentional_blink is None
            and updates.get("attentional_blink") is not None
        ):
            raise DocumentError(
                "Separate this legacy FPVS Oddball Paradigm condition before continuing."
            )
        if existing is not None and existing.attentional_blink is not None:
            updated_ab = updates.get("attentional_blink", existing.attentional_blink)
            layout = (
                updated_ab.get("layout", "within_slot") if isinstance(updated_ab, dict)
                else getattr(updated_ab, "layout", None)
            )
            if layout != existing.attentional_blink.layout:
                raise DocumentError("The attentional-blink layout is fixed for this experiment.")
        if not ab and any(updates.get(field) is not None for field in (
            "t2_stimulus_set_id", "isi_stimulus_set_id",
        )):
            raise DocumentError("T2 images are only available in Attentional-Blink experiments.")
        if (
            ab and updates.get("duty_cycle_mode", DutyCycleMode.CONTINUOUS)
            != DutyCycleMode.CONTINUOUS
        ):
            raise DocumentError("Attentional-Blink uses continuous images with target-pair timing.")
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

    def apply_experiment_design(
        self,
        condition_id: str,
        *,
        base_hz: float,
        slot_count: int,
        attentional_blink: AttentionalBlinkSettings | None,
    ) -> None:
        """Apply one validated design and its project-wide cadence atomically."""
        if self._project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK:
            raise DocumentError(RETIRED_IMAGE_PAIR_MESSAGE)
        condition = self.get_condition(condition_id)
        if condition is None:
            raise DocumentError(f"Unknown condition '{condition_id}'.")
        if isinstance(condition.attentional_blink, AttentionalBlinkStreamSettings):
            raise DocumentError("Edit this study in the letter-stream designer.")
        ab = self._project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
        if (attentional_blink is not None) != ab:
            raise DocumentError("The design must match the locked experiment type.")
        if ab and condition.attentional_blink is None:
            raise DocumentError(
                "Separate this FPVS Oddball Paradigm condition into its own experiment first."
            )
        protocol = validated_copy(
            self._project.settings.protocol, base_hz=base_hz, oddball_every_n=slot_count
        )
        updated_condition = validated_copy(
            condition,
            attentional_blink=attentional_blink,
            duty_cycle_mode=DutyCycleMode.CONTINUOUS
            if attentional_blink
            else condition.duty_cycle_mode,
        )
        project = validated_copy(
            self._project,
            settings=validated_copy(self._project.settings, protocol=protocol),
            conditions=[
                updated_condition if item.condition_id == condition_id else item
                for item in self._project.conditions
            ],
        )
        for candidate in project.conditions:
            problems = validate_attentional_blink_condition(
                project,
                candidate,
                refresh_hz=project.settings.display.preferred_refresh_hz,
                require_ready_sources=False,
            )
            if problems:
                raise DocumentError(f"{candidate.name}: {' '.join(problems)}")
        self._replace_project(project)

    def apply_attentional_blink_stream_design(
        self,
        base_words: list[str],
        t1_words: list[str],
        t2_words: list[str],
        soa_by_condition: dict[str, float],
        *,
        t1_color: str,
        t2_color: str,
    ) -> bool:
        """Validate and save shared character pools and every SOA as one edit."""
        conditions = self.ordered_conditions()
        if not conditions or any(
            not isinstance(c.attentional_blink, AttentionalBlinkStreamSettings) for c in conditions
        ):
            raise ValueError("This design requires an Attentional-Blink letter-stream study.")
        if set(soa_by_condition) != {c.condition_id for c in conditions}:
            raise ValueError("Provide an SOA for every condition in this study.")
        validate_attentional_blink_stream_symbols(base_words, t1_words, t2_words)
        words_by_set: dict[str, list[str]] = {}
        updated_conditions: list[Condition] = []
        for condition in conditions:
            ab = condition.attentional_blink
            assert isinstance(ab, AttentionalBlinkStreamSettings)
            for set_id, words in (
                (condition.base_stimulus_set_id, base_words),
                (condition.oddball_stimulus_set_id, t1_words),
                (condition.t2_stimulus_set_id, t2_words),
            ):
                if set_id is None or self.get_stimulus_set(set_id) is None:
                    raise ValueError(f"{condition.name} is missing a character pool.")
                if set_id in words_by_set and words_by_set[set_id] != words:
                    raise ValueError("Use separate stimulus sets for different character roles.")
                words_by_set[set_id] = words
            updated_conditions.append(validated_copy(
                condition,
                name=(f"SOA {soa_by_condition[condition.condition_id]:g} ms"
                      if condition.name == f"SOA {ab.soa_ms:g} ms" else condition.name),
                attentional_blink=validated_copy(
                    ab, soa_ms=soa_by_condition[condition.condition_id],
                    t1_color=t1_color, t2_color=t2_color,
                ),
            ))
        project = validated_copy(
            self._project,
            conditions=updated_conditions,
            stimulus_sets=[
                validated_copy(source, words=words_by_set[source.set_id])
                if source.set_id in words_by_set else source
                for source in self._project.stimulus_sets
            ],
        )
        for candidate in project.conditions:
            problems = validate_attentional_blink_condition(
                project, candidate, refresh_hz=project.settings.display.preferred_refresh_hz,
                require_ready_sources=True,
            )
            if problems:
                raise ValueError(f"{candidate.name}: {' '.join(problems)}")
        if project == self._project:
            return False
        self._replace_project(project)
        return True

    def set_condition_task_flow(
        self,
        condition_id: str,
        *,
        modules: list[TaskModule],
        pre_bindings: list[TaskBinding],
        post_bindings: list[TaskBinding],
        asset_copies: list[tuple[Path, str]] | None = None,
    ) -> None:
        """Apply one condition's task flow and deferred media intake atomically.

        The dialog validates a complete draft before calling this method. Media is
        copied only during Apply; if an intake fails, newly created files are removed
        and the live project model remains unchanged.
        """

        condition = self.get_condition(condition_id)
        if condition is None:
            raise DocumentError(f"Unknown condition '{condition_id}'.")
        module_by_id = {module.task_id: module for module in modules}
        if len(module_by_id) != len(modules):
            raise DocumentError("Task module ids must be unique.")
        bound_ids = {binding.task_id for binding in [*pre_bindings, *post_bindings]}
        if not bound_ids.issubset(module_by_id):
            missing = ", ".join(sorted(bound_ids - set(module_by_id)))
            raise DocumentError(f"Task bindings reference missing modules: {missing}")

        old_bound_ids = {
            binding.task_id
            for binding in [
                *condition.pre_task_bindings,
                *condition.post_task_bindings,
            ]
        }
        other_bound_ids = {
            binding.task_id
            for other in self._project.conditions
            if other.condition_id != condition_id
            for binding in [*other.pre_task_bindings, *other.post_task_bindings]
        }
        existing_by_id = {existing.task_id: existing for existing in self._project.task_modules}
        conflicting_shared_ids = sorted(
            task_id
            for task_id in other_bound_ids
            if task_id in module_by_id
            and task_id in existing_by_id
            and module_by_id[task_id] != existing_by_id[task_id]
        )
        if conflicting_shared_ids:
            shared = ", ".join(conflicting_shared_ids)
            raise DocumentError(
                "These reusable task module IDs are also bound to another condition "
                f"and cannot be changed here: {shared}. Use a new module ID to make "
                "a condition-specific copy."
            )
        updated_modules: list[TaskModule] = []
        consumed: set[str] = set()
        for existing in self._project.task_modules:
            replacement = module_by_id.get(existing.task_id)
            if replacement is not None:
                updated_modules.append(replacement)
                consumed.add(existing.task_id)
            elif existing.task_id not in old_bound_ids or existing.task_id in other_bound_ids:
                updated_modules.append(existing)
        updated_modules.extend(module for module in modules if module.task_id not in consumed)
        updated_conditions = [
            validated_copy(
                item,
                pre_task_bindings=pre_bindings,
                post_task_bindings=post_bindings,
            )
            if item.condition_id == condition_id
            else item
            for item in self.ordered_conditions()
        ]
        updated_project = validated_copy(
            self._project,
            conditions=self._reindex_conditions(updated_conditions),
            task_modules=updated_modules,
        )

        created_paths: list[Path] = []
        try:
            for source_path, relative_target in asset_copies or []:
                parts = PurePosixPath(relative_target).parts
                if len(parts) != 4 or parts[:2] != ("stimuli", "task-assets"):
                    raise DocumentError(
                        "Task assets must target stimuli/task-assets/<task-id>/<file>."
                    )
                target_path = self._project_root.joinpath(*parts)
                existed = target_path.exists()
                copied_relative = copy_task_asset(
                    self._project_root,
                    parts[2],
                    source_path,
                    filename=parts[3],
                )
                if copied_relative != relative_target:
                    raise DocumentError("Task asset intake returned an unexpected project path.")
                if not existed:
                    created_paths.append(target_path)
            self._replace_project(updated_project)
        except Exception:
            for created_path in reversed(created_paths):
                created_path.unlink(missing_ok=True)
                parent = created_path.parent
                try:
                    parent.rmdir()
                except OSError:
                    pass
            raise

    def set_condition_presentation(
        self,
        condition_id: str,
        presentation: ConditionPresentationSettings,
    ) -> None:
        """Replace one condition's presentation overrides atomically."""

        self.update_condition(condition_id, presentation=presentation)

    def update_condition_timing_template(
        self,
        condition_id: str,
        duty_cycle_mode: DutyCycleMode,
    ) -> None:
        """Update one condition's timing-template choice only."""

        self.update_condition(condition_id, duty_cycle_mode=duty_cycle_mode)

    def set_condition_stimulus_modality(
        self,
        condition_id: str,
        *,
        modality: StimulusModality,
    ) -> None:
        """Switch an empty condition between image and word authoring modes."""

        condition = self.get_condition(condition_id)
        if condition is None:
            raise DocumentError(f"Unknown condition '{condition_id}'.")
        if self._project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK:
            required = (
                StimulusModality.WORD
                if isinstance(condition.attentional_blink, AttentionalBlinkStreamSettings)
                else StimulusModality.IMAGE
            )
            if modality != required:
                raise DocumentError(
                    f"This attentional-blink layout requires {required.value} sources."
                )
        base_set = self.get_condition_stimulus_set(condition_id, "base")
        oddball_set = self.get_condition_stimulus_set(condition_id, "oddball")
        if base_set.modality == modality and oddball_set.modality == modality:
            return
        if condition.attentional_blink is not None or (
            condition.t2_stimulus_set_id is not None
            and self.get_condition_stimulus_set(condition_id, "t2").image_count > 0
        ):
            raise DocumentError("Attentional-blink designs use image sources.")
        if not self._condition_stimulus_sets_empty(base_set, oddball_set):
            raise DocumentError(
                "Condition stimulus type can only be changed before images or words are added."
            )
        updated_sets: list[StimulusSet] = []
        for stimulus_set in self._project.stimulus_sets:
            if stimulus_set.set_id not in {
                condition.base_stimulus_set_id,
                condition.oddball_stimulus_set_id,
            }:
                updated_sets.append(stimulus_set)
                continue
            if modality == StimulusModality.IMAGE:
                updated_sets.append(
                    self._make_empty_stimulus_set(stimulus_set.set_id, stimulus_set.name)
                )
            else:
                updated_sets.append(
                    StimulusSet(
                        set_id=stimulus_set.set_id,
                        name=stimulus_set.name,
                        modality=StimulusModality.WORD,
                        source_dir=None,
                        words=[],
                    )
                )
        updated_conditions = self._project.conditions
        if (
            modality == StimulusModality.WORD
            and condition.duty_cycle_mode == DutyCycleMode.SINUSOIDAL
        ):
            continuous_condition = condition.model_copy(
                update={"duty_cycle_mode": DutyCycleMode.CONTINUOUS}
            )
            updated_conditions = [
                continuous_condition if item.condition_id == condition_id else item
                for item in self._project.conditions
            ]
        project = validated_copy(
            self._project,
            conditions=updated_conditions,
            stimulus_sets=updated_sets,
        )
        self._replace_project(project)

    def update_condition_words(self, condition_id: str, *, role: str, words: list[str]) -> None:
        """Update one word stimulus list for a word-based condition role."""

        condition = self.get_condition(condition_id)
        if condition is None:
            raise DocumentError(f"Unknown condition '{condition_id}'.")
        stimulus_set = self.get_condition_stimulus_set(condition_id, role)
        if stimulus_set.modality != StimulusModality.WORD:
            raise DocumentError("Words can only be edited for word-based conditions.")
        updated_set = stimulus_set.model_copy(update={"words": words})
        updated_sets = [
            updated_set if item.set_id == stimulus_set.set_id else item
            for item in self._project.stimulus_sets
        ]
        project = validated_copy(self._project, stimulus_sets=updated_sets)
        self._replace_project(project)

    def _make_empty_stimulus_set(self, set_id: str, name: str) -> StimulusSet:
        source_dir = to_project_relative_posix(
            self._project_root,
            stimulus_originals_dir(self._project_root, set_id),
        )
        return StimulusSet(
            set_id=set_id,
            name=name,
            modality=StimulusModality.IMAGE,
            source_dir=source_dir,
            image_count=0,
        )

    @staticmethod
    def _condition_stimulus_sets_empty(*stimulus_sets: StimulusSet) -> bool:
        return all(
            (
                stimulus_set.image_count <= 0
                if stimulus_set.modality == StimulusModality.IMAGE
                else stimulus_set.word_count <= 0
            )
            for stimulus_set in stimulus_sets
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

    def _unique_condition_name(self, preferred_name: str, existing_names: set[str]) -> str:
        candidate = preferred_name.strip() or "Control Condition"
        base = candidate
        suffix = 2
        while candidate in existing_names:
            candidate = f"{base} {suffix}"
            suffix += 1
        return candidate

    def _default_control_condition_name(
        self,
        source_name: str,
        variant: StimulusVariant,
        *,
        transform: StimulusTransform | None = None,
    ) -> str:
        variant_label = {
            StimulusVariant.GRAYSCALE: "Grayscale",
            StimulusVariant.ROT180: "180 Degree Rotated",
            StimulusVariant.PHASE_SCRAMBLED: "Phase-Scrambled",
            StimulusVariant.ORIGINAL: "Original",
        }[variant]
        if transform is not None:
            variant_label = {
                StimulusTransform.NONE: "Original",
                StimulusTransform.MIRROR_HORIZONTAL: "Horizontally Mirrored",
                StimulusTransform.MIRROR_VERTICAL: "Vertically Mirrored",
                StimulusTransform.ROT180: "180 Degree Rotated",
            }[transform]
        return f"{source_name} {variant_label} Control"
