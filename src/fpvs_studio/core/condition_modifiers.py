"""Project-owned modifier groups and detached, I/O-free authoring operations."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from fpvs_studio.core.backward_counting import (
    create_backward_counting_baseline_task,
    create_backward_counting_report_task,
    create_backward_counting_start_task,
)
from fpvs_studio.core.enums import ProjectSchemaVersion
from fpvs_studio.core.masking import MaskingSettings
from fpvs_studio.core.paths import validate_project_relative_path
from fpvs_studio.core.task_models import (
    BackwardCountingRole,
    ConditionModifierKind,
    ImageMemoryConfig,
    ImageMemoryRole,
    TaskBaseModel,
    TaskBinding,
    TaskDisplayItem,
    TaskItemModality,
    TaskModule,
    TaskOccurrence,
    TaskStep,
    TaskStepKind,
    TaskSubmissionMode,
    task_requires_text_alignment_schema,
    validate_task_slug,
)

if TYPE_CHECKING:
    from fpvs_studio.core.models import ProjectFile

MEMORY_STUDY_STEP_ID = "memory-study"
MEMORY_RECOGNITION_STEP_ID = "memory-recognition"


class ConditionModifier(TaskBaseModel):
    """Ownership/group identity; condition bindings remain the execution order."""

    modifier_id: str
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    kind: ConditionModifierKind
    pre_task_ids: list[str]
    post_task_ids: list[str]
    baseline_task_id: str | None = None
    masking: MaskingSettings | None = None

    @model_serializer(mode="wrap")
    def serialize_optional_masking(
        self, handler: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = handler(self)
        if self.masking is None:
            payload.pop("masking", None)
        return payload

    @field_validator("modifier_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_task_slug(value, field_name="Modifier id")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Modifier name may not be blank.")
        return value

    @model_validator(mode="after")
    def validate_ids(self) -> ConditionModifier:
        if (self.kind == ConditionModifierKind.MASKING) != (self.masking is not None):
            raise ValueError("Masking modifiers require masking settings exclusively.")
        ids = [*self.pre_task_ids, *self.post_task_ids]
        if not self.pre_task_ids or not self.post_task_ids:
            raise ValueError("A condition modifier requires both before and after modules.")
        if self.baseline_task_id is not None:
            ids.append(self.baseline_task_id)
            if self.kind != ConditionModifierKind.BACKWARD_COUNTING:
                raise ValueError("Only backward counting may request a session baseline.")
        if len(ids) != len(set(ids)):
            raise ValueError("Modifier task identities must be unique.")
        for task_id in ids:
            validate_task_slug(task_id, field_name="Modifier task id")
        return self


class ModifierDefinition(TaskBaseModel):
    modifier: ConditionModifier
    task_modules: list[TaskModule]

    @model_validator(mode="after")
    def validate_owned_modules(self) -> ModifierDefinition:
        expected = modifier_task_ids(self.modifier)
        ids = [task.task_id for task in self.task_modules]
        if len(ids) != len(set(ids)) or set(ids) != expected:
            raise ValueError("A modifier definition must contain exactly its owned modules.")
        return self


class MemoryImage(TaskBaseModel):
    image_id: str
    image_path: str

    @field_validator("image_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_task_slug(value, field_name="Memory image id")

    @field_validator("image_path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return validate_project_relative_path(value)


def modifier_task_ids(modifier: ConditionModifier) -> set[str]:
    ids = {*modifier.pre_task_ids, *modifier.post_task_ids}
    if modifier.baseline_task_id:
        ids.add(modifier.baseline_task_id)
    return ids


def create_backward_counting_modifier(
    *,
    modifier_id: str = "backward-counting",
    name: str = "Backward counting",
    description: str = "Count backward silently while watching the FPVS images.",
    subtraction_step: int = 13,
    start_min: int = 1000,
    start_max: int = 9999,
    baseline_enabled: bool = True,
    baseline_duration_seconds: float = 120,
    instructions: str | None = None,
    endpoint_prompt: str | None = None,
    baseline_instructions: str | None = None,
    baseline_endpoint_prompt: str | None = None,
) -> ModifierDefinition:
    start = create_backward_counting_start_task(
        task_id=f"{modifier_id}-start",
        link_id=modifier_id,
        subtraction_step=subtraction_step,
        start_min=start_min,
        start_max=start_max,
    )
    report = create_backward_counting_report_task(
        task_id=f"{modifier_id}-report",
        link_id=modifier_id,
        subtraction_step=subtraction_step,
        start_min=start_min,
        start_max=start_max,
    )
    baseline = (
        create_backward_counting_baseline_task(
            task_id=f"{modifier_id}-baseline",
            link_id=f"{modifier_id}-baseline",
            duration_seconds=baseline_duration_seconds,
            subtraction_step=subtraction_step,
            start_min=start_min,
            start_max=start_max,
        )
        if baseline_enabled
        else None
    )
    tasks = ([baseline] if baseline is not None else []) + [start, report]
    for task in tasks:
        assert task.backward_counting is not None
        is_baseline = task.backward_counting.role == BackwardCountingRole.BASELINE
        task.backward_counting.instructions = baseline_instructions if is_baseline else instructions
        task.backward_counting.endpoint_prompt = (
            baseline_endpoint_prompt if is_baseline else endpoint_prompt
        )
    return ModifierDefinition(
        modifier=ConditionModifier(
            modifier_id=modifier_id,
            name=name,
            description=description,
            kind=ConditionModifierKind.BACKWARD_COUNTING,
            pre_task_ids=[start.task_id],
            post_task_ids=[report.task_id],
            baseline_task_id=baseline.task_id if baseline else None,
        ),
        task_modules=tasks,
    )


def create_image_memory_modifier(
    *,
    modifier_id: str = "image-memory",
    name: str = "Remember four images",
    description: str = "Hold four images in memory while watching FPVS, then recognize them.",
    target_images: list[MemoryImage] | None = None,
    foil_images: list[MemoryImage] | None = None,
    recognition_target_images: list[MemoryImage] | None = None,
    study_duration_seconds: float | None = None,
    study_instructions: str = "Remember these four images while watching the next image stream.",
    recognition_instructions: str = "Select the four images you studied, then press Submit.",
) -> ModifierDefinition:
    targets, foils = target_images or [], foil_images or []
    if len(targets) > 4 or len(foils) > 4:
        raise ValueError("Remember four images supports four targets and four foils.")
    study_id, report_id = f"{modifier_id}-study", f"{modifier_id}-recognition"
    report_targets = recognition_target_images
    if report_targets is None:
        report_targets = [
            MemoryImage(
                image_id=item.image_id,
                image_path=f"stimuli/task-assets/{report_id}/{PurePosixPath(item.image_path).name}",
            )
            for item in targets
        ]
    study = TaskModule(
        task_id=study_id,
        name=f"{name}: study",
        image_memory=ImageMemoryConfig(role=ImageMemoryRole.STUDY, link_id=modifier_id),
        steps=[
            TaskStep(
                step_id=MEMORY_STUDY_STEP_ID,
                kind=TaskStepKind.STUDY if targets else TaskStepKind.INSTRUCTION,
                text=study_instructions,
                columns=2,
                continue_key="space" if study_duration_seconds is None else None,
                duration_seconds=study_duration_seconds,
                items=[
                    TaskDisplayItem(
                        item_id=item.image_id,
                        modality=TaskItemModality.IMAGE,
                        image_path=item.image_path,
                    )
                    for item in targets
                ],
            )
        ],
    )
    recognition_items = [
        TaskDisplayItem(
            item_id=item.image_id,
            modality=TaskItemModality.IMAGE,
            image_path=item.image_path,
            selectable=True,
            correct=correct,
            score=float(correct),
        )
        for items, correct in ((report_targets, True), (foils, False))
        for item in items
    ]
    report = TaskModule(
        task_id=report_id,
        name=f"{name}: recognition",
        image_memory=ImageMemoryConfig(role=ImageMemoryRole.RECOGNITION, link_id=modifier_id),
        steps=[
            TaskStep(
                step_id=MEMORY_RECOGNITION_STEP_ID,
                kind=TaskStepKind.CHOICE_GRID,
                text=recognition_instructions,
                columns=4,
                items=recognition_items,
                min_selections=min(4, len(recognition_items)),
                max_selections=min(4, len(recognition_items)),
                submission_mode=TaskSubmissionMode.EXPLICIT,
            )
        ]
        if recognition_items
        else [],
    )
    return ModifierDefinition(
        modifier=ConditionModifier(
            modifier_id=modifier_id,
            name=name,
            description=description,
            kind=ConditionModifierKind.IMAGE_MEMORY,
            pre_task_ids=[study_id],
            post_task_ids=[report_id],
        ),
        task_modules=[study, report],
    )


def validate_image_memory_definition(
    definition: ModifierDefinition,
    *,
    allow_incomplete: bool = False,
) -> None:
    """Validate editable memory semantics without reading or copying image files.

    Incomplete mode permits consistent missing-media drafts, not altered response
    rules. Compilation still requires all four targets and four distinct foils.
    """
    if definition.modifier.kind != ConditionModifierKind.IMAGE_MEMORY:
        raise ValueError("This definition is not an image-memory modifier.")
    linked: dict[ImageMemoryRole, TaskModule] = {}
    for task in definition.task_modules:
        if task.image_memory is None:
            continue
        role = task.image_memory.role
        if role in linked:
            raise ValueError("Image memory requires exactly one linked study and recognition.")
        linked[role] = task
        expected_ids = (
            definition.modifier.pre_task_ids
            if role == ImageMemoryRole.STUDY
            else definition.modifier.post_task_ids
        )
        if task.task_id not in expected_ids:
            raise ValueError("Memory study and recognition must retain their before/after phases.")
    if set(linked) != {ImageMemoryRole.STUDY, ImageMemoryRole.RECOGNITION}:
        raise ValueError("Image memory requires exactly one linked study and recognition.")
    validate_image_memory_modules(
        linked[ImageMemoryRole.STUDY],
        linked[ImageMemoryRole.RECOGNITION],
        allow_incomplete=allow_incomplete,
    )


def validate_image_memory_modules(
    study_module: TaskModule,
    report_module: TaskModule,
    *,
    allow_incomplete: bool = False,
) -> None:
    """Shared structural check for authoring and linked task compilation."""
    study_config, report_config = study_module.image_memory, report_module.image_memory
    if (
        study_config is None
        or report_config is None
        or study_config.role != ImageMemoryRole.STUDY
        or report_config.role != ImageMemoryRole.RECOGNITION
        or study_config.link_id != report_config.link_id
    ):
        raise ValueError("Image memory requires matching typed study and recognition modules.")
    modules = (study_module, report_module)
    if any(task.repeat_count != 1 or task.backward_counting is not None for task in modules):
        raise ValueError("Image-memory modules have one activity and run once.")
    if any(len(task.steps) > 1 for task in modules):
        raise ValueError("Remember four images requires one study and one recognition screen.")
    if not allow_incomplete and any(len(task.steps) != 1 for task in modules):
        raise ValueError("Remember four images requires complete study and recognition screens.")
    study = study_module.steps[0] if study_module.steps else None
    report = report_module.steps[0] if report_module.steps else None
    for task in modules:
        for step in task.steps:
            if (
                step.repeat_count != 1
                or step.branch_rules
                or step.max_attempts != 1
                or step.retry_on_invalid
                or step.retry_on_incorrect
            ):
                raise ValueError("Memory screens run once without branching or response retries.")
    if study is not None:
        is_empty_draft = (
            allow_incomplete and not study.items and study.kind == TaskStepKind.INSTRUCTION
        )
        if study.kind != TaskStepKind.STUDY and not is_empty_draft:
            raise ValueError("The memory study screen must retain its study response type.")
        if study.duration_seconds is not None and study.continue_key is not None:
            raise ValueError("Timed memory study must not also allow a continue key.")
        if study.timeout_seconds is not None or any(item.selectable for item in study.items):
            raise ValueError("Memory study cannot use a response timeout or selectable images.")
    study_items = study.items if study else []
    report_items = report.items if report else []
    targets = [item.item_id for item in study_items]
    report_targets = [item.item_id for item in report_items if item.correct is True]
    foils = [item.item_id for item in report_items if item.correct is False]
    if (
        len(targets) > 4
        or len(foils) > 4
        or set(targets) != set(report_targets)
        or len(set(targets + foils)) != len(targets + foils)
        or len(report_items) != len(targets) + len(foils)
        or any(item.image_path is None for item in [*study_items, *report_items])
    ):
        raise ValueError(
            "Memory images require matching target identities and distinct foil identities."
        )
    if not allow_incomplete and (len(targets) != 4 or len(foils) != 4):
        raise ValueError("Remember four images requires four targets and four distinct foils.")
    if report is not None:
        expected_selections = min(4, len(report_items))
        if (
            report.kind != TaskStepKind.CHOICE_GRID
            or not report_items
            or any(not item.selectable for item in report_items)
            or report.min_selections != expected_selections
            or report.max_selections != expected_selections
            or report.submission_mode != TaskSubmissionMode.EXPLICIT
            or any(item.score != float(bool(item.correct)) for item in report_items)
        ):
            raise ValueError(
                "Memory recognition requires all images selectable, exactly four unique selections "
                "when complete, explicit Submit, and target-count scoring."
            )


def modifier_condition_ids(project: ProjectFile, modifier_id: str) -> list[str]:
    modifier = next(item for item in project.condition_modifiers if item.modifier_id == modifier_id)
    ids = {*modifier.pre_task_ids, *modifier.post_task_ids}
    return [
        condition.condition_id
        for condition in project.conditions
        if any(
            binding.task_id in ids
            for binding in [*condition.pre_task_bindings, *condition.post_task_bindings]
        )
    ]


def validate_condition_modifiers(project: ProjectFile) -> None:
    modules = {task.task_id: task for task in project.task_modules}
    owner_ids: set[str] = set()
    modifier_ids: set[str] = set()
    for modifier in project.condition_modifiers:
        if modifier.modifier_id in modifier_ids:
            raise ValueError("Modifier ids must be unique.")
        modifier_ids.add(modifier.modifier_id)
        owned = modifier_task_ids(modifier)
        if owned - modules.keys():
            raise ValueError(f"Modifier '{modifier.name}' references missing task modules.")
        if owner_ids & owned:
            raise ValueError("Each modifier must own separate task modules.")
        owner_ids.update(owned)
        if modifier.kind == ConditionModifierKind.BACKWARD_COUNTING:
            before = [modules[task_id].backward_counting for task_id in modifier.pre_task_ids]
            after = [modules[task_id].backward_counting for task_id in modifier.post_task_ids]
            start_links = [
                config.link_id
                for config in before
                if config is not None and config.role == BackwardCountingRole.LOAD_START
            ]
            report_links = [
                config.link_id
                for config in after
                if config is not None and config.role == BackwardCountingRole.LOAD_REPORT
            ]
        elif modifier.kind == ConditionModifierKind.IMAGE_MEMORY:
            memory_before = [modules[task_id].image_memory for task_id in modifier.pre_task_ids]
            memory_after = [modules[task_id].image_memory for task_id in modifier.post_task_ids]
            start_links = [
                config.link_id
                for config in memory_before
                if config is not None and config.role == ImageMemoryRole.STUDY
            ]
            report_links = [
                config.link_id
                for config in memory_after
                if config is not None and config.role == ImageMemoryRole.RECOGNITION
            ]
        else:
            start_links = report_links = [modifier.modifier_id]
        if len(start_links) != 1 or len(report_links) != 1 or start_links[0] != report_links[0]:
            raise ValueError(
                f"Modifier '{modifier.name}' requires one matching typed before/after pair."
            )
        if modifier.baseline_task_id:
            baseline = modules[modifier.baseline_task_id].backward_counting
            if baseline is None or baseline.role != BackwardCountingRole.BASELINE:
                raise ValueError("Modifier baseline must reference a typed counting baseline.")
        for condition in project.conditions:
            pre = [binding.task_id for binding in condition.pre_task_bindings]
            post = [binding.task_id for binding in condition.post_task_bindings]
            attached = owned.intersection([*pre, *post])
            if not attached:
                continue
            if modifier.baseline_task_id in attached:
                raise ValueError(
                    "Modifier baselines are session requirements, not condition bindings."
                )
            if not set(modifier.pre_task_ids) <= set(pre) or not set(modifier.post_task_ids) <= set(
                post
            ):
                raise ValueError(
                    f"Condition '{condition.name}' has an incomplete modifier assignment."
                )
    for condition in project.conditions:
        assigned = [
            modifier
            for modifier in project.condition_modifiers
            if condition.condition_id in modifier_condition_ids(project, modifier.modifier_id)
        ]
        if len(assigned) > 1:
            raise ValueError(f"Condition '{condition.name}' can have only one sustained activity.")


def remove_modifier(
    project: ProjectFile,
    modifier_id: str,
    condition_ids: list[str],
) -> ProjectFile:
    draft = project.model_copy(deep=True)
    modifier = next(item for item in draft.condition_modifiers if item.modifier_id == modifier_id)
    owned = modifier_task_ids(modifier)
    for condition in draft.conditions:
        if condition.condition_id in condition_ids:
            condition.pre_task_bindings = [
                b for b in condition.pre_task_bindings if b.task_id not in owned
            ]
            condition.post_task_bindings = [
                b for b in condition.post_task_bindings if b.task_id not in owned
            ]
    return draft


def assign_modifier(
    project: ProjectFile,
    definition: ModifierDefinition,
    condition_ids: list[str],
    *,
    replace: bool = False,
) -> ProjectFile:
    draft = project.model_copy(deep=True)
    if not condition_ids or set(condition_ids) - {c.condition_id for c in project.conditions}:
        raise ValueError("Select existing conditions for this modifier.")
    existing = next(
        (m for m in draft.condition_modifiers if m.modifier_id == definition.modifier.modifier_id),
        None,
    )
    if existing is not None:
        others = set(modifier_condition_ids(draft, existing.modifier_id)) - set(condition_ids)
        old_tasks = [t for t in draft.task_modules if t.task_id in modifier_task_ids(existing)]
        if others and (existing != definition.modifier or old_tasks != definition.task_modules):
            raise ValueError("Copy this shared modifier before changing only selected conditions.")
    for modifier in list(draft.condition_modifiers):
        overlap = set(modifier_condition_ids(draft, modifier.modifier_id)) & set(condition_ids)
        if overlap:
            if not replace and modifier.modifier_id != definition.modifier.modifier_id:
                raise ValueError(
                    "A selected condition already has a sustained activity; replace explicitly."
                )
            draft = remove_modifier(draft, modifier.modifier_id, list(overlap))
    old_owned = modifier_task_ids(existing) if existing else set()
    collisions = modifier_task_ids(definition.modifier) & {
        task.task_id for task in draft.task_modules if task.task_id not in old_owned
    }
    if collisions:
        raise ValueError("Modifier task ids collide; copy the definition with new identities.")
    draft.task_modules = [task for task in draft.task_modules if task.task_id not in old_owned]
    draft.task_modules.extend(task.model_copy(deep=True) for task in definition.task_modules)
    draft.condition_modifiers = [
        m for m in draft.condition_modifiers if m.modifier_id != definition.modifier.modifier_id
    ]
    draft.condition_modifiers.append(definition.modifier.model_copy(deep=True))
    for condition in draft.conditions:
        if condition.condition_id not in condition_ids:
            continue
        condition.pre_task_bindings.extend(
            TaskBinding(task_id=task_id, replaces_condition_start_gate=True,
                        occurrence=TaskOccurrence.FIRST_STREAM_GROUP_ENTRY
                        if definition.modifier.masking is not None else TaskOccurrence.EVERY_ENTRY)
            for task_id in definition.modifier.pre_task_ids
        )
        condition.post_task_bindings = [
            TaskBinding(task_id=task_id,
                        occurrence=TaskOccurrence.LAST_STREAM_GROUP_ENTRY
                        if definition.modifier.masking is not None and index == len(
                            definition.modifier.post_task_ids) - 1
                        else TaskOccurrence.EVERY_ENTRY)
            for index, task_id in enumerate(definition.modifier.post_task_ids)
        ] + condition.post_task_bindings
    draft.schema_version = (
        ProjectSchemaVersion.V1_10
        if any(item.masking is not None and item.masking.event_triggers is not None
               for item in draft.condition_modifiers)
        or project.schema_version == ProjectSchemaVersion.V1_10
        else ProjectSchemaVersion.V1_9
        if any(condition.masking_catch for condition in draft.conditions)
        or any(task_requires_text_alignment_schema(task) for task in draft.task_modules)
        or project.schema_version == ProjectSchemaVersion.V1_9
        else ProjectSchemaVersion.V1_8
        if any(item.masking is not None and item.masking.catch_trial is not None
               for item in draft.condition_modifiers)
        or project.schema_version == ProjectSchemaVersion.V1_8
        else ProjectSchemaVersion.V1_7
        if any(item.masking is not None for item in draft.condition_modifiers)
        or project.schema_version == ProjectSchemaVersion.V1_7
        else ProjectSchemaVersion.V1_6
    )
    return type(project).model_validate(draft.model_dump())


def apply_modifier_draft(
    project: ProjectFile,
    definitions: dict[str, ModifierDefinition],
    scopes: dict[str, list[str]],
) -> ProjectFile:
    """Apply a draft without rebuilding bindings for unchanged shared assignments."""
    draft = project.model_copy(deep=True)
    changed_definitions = set()
    original_scopes = {}
    for modifier in project.condition_modifiers:
        key = modifier.modifier_id
        original_scopes[key] = modifier_condition_ids(project, key)
        desired = scopes.get(key, []) if key in definitions else []
        original = ModifierDefinition(
            modifier=modifier,
            task_modules=[
                t for t in project.task_modules if t.task_id in modifier_task_ids(modifier)
            ],
        )
        if definitions.get(key) != original or (original_scopes[key] and not desired):
            changed_definitions.add(key)
            removed = original_scopes[key]
        else:
            removed = [
                condition_id for condition_id in original_scopes[key] if condition_id not in desired
            ]
        if removed:
            draft = remove_modifier(draft, key, removed)
    # Finish removals first so a replacement can occupy a condition in the same Apply.
    owned = {
        task_id
        for modifier in project.condition_modifiers
        if modifier.modifier_id in changed_definitions
        for task_id in modifier_task_ids(modifier)
    }
    draft.condition_modifiers = [
        m for m in draft.condition_modifiers if m.modifier_id not in changed_definitions
    ]
    draft.task_modules = [t for t in draft.task_modules if t.task_id not in owned]
    for key, definition in definitions.items():
        added = (
            scopes[key]
            if key in changed_definitions
            else [
                condition_id for condition_id in scopes[key]
                if condition_id not in original_scopes.get(key, [])
            ]
        )
        if added:
            draft = assign_modifier(draft, definition, added)
    return type(project).model_validate(draft.model_dump())


def adopt_backward_counting_modifier(
    project: ProjectFile,
    *,
    start_task_id: str,
    report_task_id: str,
    baseline_task_id: str | None = None,
    modifier_id: str = "backward-counting",
    name: str = "Backward counting",
) -> ProjectFile:
    """Explicitly group existing typed counting modules without rebuilding their settings."""
    draft = project.model_copy(deep=True)
    modules = {task.task_id: task for task in draft.task_modules}
    for task_id, role in (
        (start_task_id, BackwardCountingRole.LOAD_START),
        (report_task_id, BackwardCountingRole.LOAD_REPORT),
        (baseline_task_id, BackwardCountingRole.BASELINE),
    ):
        if task_id is None:
            continue
        config = modules[task_id].backward_counting
        if config is None or config.role != role:
            raise ValueError("Only explicitly typed counting modules can be grouped.")
    start, report = (
        modules[start_task_id].backward_counting,
        modules[report_task_id].backward_counting,
    )
    assert start is not None and report is not None
    if start.link_id != report.link_id:
        raise ValueError("The selected counting modules do not share a link.")
    for condition in draft.conditions:
        for phase in (condition.pre_task_bindings, condition.post_task_bindings):
            for binding in phase:
                if (
                    binding.task_id == baseline_task_id
                    and binding.occurrence != TaskOccurrence.FIRST_SESSION_ENTRY
                ):
                    raise ValueError(
                        "Only first-session baseline bindings support explicit grouping."
                    )
        condition.pre_task_bindings = [
            b for b in condition.pre_task_bindings if b.task_id != baseline_task_id
        ]
        condition.post_task_bindings = [
            b for b in condition.post_task_bindings if b.task_id != baseline_task_id
        ]
    draft.condition_modifiers.append(
        ConditionModifier(
            modifier_id=modifier_id,
            name=name,
            kind=ConditionModifierKind.BACKWARD_COUNTING,
            pre_task_ids=[start_task_id],
            post_task_ids=[report_task_id],
            baseline_task_id=baseline_task_id,
        )
    )
    if draft.schema_version != ProjectSchemaVersion.V1_10:
        draft.schema_version = ProjectSchemaVersion.V1_6
    return type(project).model_validate(draft.model_dump())
