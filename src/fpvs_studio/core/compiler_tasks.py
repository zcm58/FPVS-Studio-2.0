"""Compilation helpers for project-owned condition task modules."""

from __future__ import annotations

import hashlib
import random
from pathlib import Path, PurePosixPath

from fpvs_studio.core.attentional_blink_presets import RECALL_QUESTION_PHASES, RECALL_TASK_ID
from fpvs_studio.core.backward_counting import backward_counting_steps
from fpvs_studio.core.compiler_support import CompileError
from fpvs_studio.core.condition_modifiers import (
    ConditionModifier,
    modifier_condition_ids,
    modifier_task_ids,
    validate_condition_modifiers,
    validate_image_memory_modules,
)
from fpvs_studio.core.models import Condition, ProjectFile
from fpvs_studio.core.paths import resolve_project_relative_path
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.task_models import (
    BackwardCountingConfig,
    BackwardCountingRole,
    BackwardCountingSpec,
    ImageMemoryRole,
    ImageMemorySpec,
    ModifierProvenance,
    TaskBinding,
    TaskLayoutMode,
    TaskModule,
    TaskModuleSpec,
    TaskOccurrence,
    TaskPhase,
    TaskQuestionKind,
    TaskStep,
    TaskStepSpec,
)

SUPPORTED_TASK_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})


def compile_condition_tasks(
    project: ProjectFile,
    condition: Condition,
    *,
    phase: TaskPhase,
    block_index: int,
    block_count: int,
    session_seed: int,
    run_id: str,
    project_root: Path | None,
    run_spec: RunSpec | None = None,
    global_order_index: int = 0,
) -> list[TaskModuleSpec]:
    """Compile the applicable task bindings for one concrete session entry."""

    modules = {module.task_id: module for module in project.task_modules}
    bindings = (
        condition.pre_task_bindings
        if phase == TaskPhase.PRE_CONDITION
        else condition.post_task_bindings
    )
    compiled: list[TaskModuleSpec] = []
    for binding_index, binding in enumerate(bindings):
        if not _binding_applies(
            binding,
            block_index=block_index,
            block_count=block_count,
            global_order_index=global_order_index,
        ):
            continue
        module = modules.get(binding.task_id)
        if module is None:
            raise CompileError(
                f"Condition '{condition.name}' references missing task module "
                f"'{binding.task_id}'."
            )
        task_seed = _task_seed(
            session_seed=session_seed,
            run_id=run_id,
            phase=phase,
            binding_index=binding_index,
            task_id=module.task_id,
        )
        counting_spec = _compile_backward_counting(
            module, project=project, condition=condition, phase=phase,
            block_index=block_index, block_count=block_count,
            global_order_index=global_order_index, session_seed=session_seed,
            run_id=run_id, run_spec=run_spec,
        )
        memory_spec, memory_steps = _compile_image_memory(
            module, project=project, condition=condition, phase=phase,
            block_index=block_index, block_count=block_count,
            global_order_index=global_order_index, session_seed=session_seed,
            run_id=run_id, project_root=project_root,
        )
        owner = next((modifier for modifier in project.condition_modifiers
                      if module.task_id in modifier_task_ids(modifier)), None)
        compiled.append(
            _compile_task_module(
                module,
                phase=phase,
                occurrence=binding.occurrence,
                random_seed=task_seed,
                project_root=project_root,
                counting_spec=counting_spec,
                memory_spec=memory_spec,
                source_steps=memory_steps,
                modifier=_modifier_provenance(owner) if owner else None,
            )
        )
    if phase == TaskPhase.POST_CONDITION:
        for compiled_module in compiled:
            if compiled_module.task_id == RECALL_TASK_ID:
                if run_spec is None:
                    raise CompileError("Target number recall requires the compiled burst targets.")
                _resolve_attentional_blink_recall(compiled_module, run_spec)
    return compiled


def _resolve_attentional_blink_recall(module: TaskModuleSpec, run_spec: RunSpec) -> None:
    """Score each recall question against the one target actually presented this burst."""
    targets: dict[str, str] = {}
    for phase in RECALL_QUESTION_PHASES.values():
        events = [event for event in run_spec.stimulus_sequence if event.phase == phase]
        if len(events) != 1 or events[0].text is None:
            raise CompileError("Target number recall requires exactly one T1/T2 pair per burst.")
        targets[phase] = events[0].text
    for step in module.steps:
        for question in step.questions:
            target_phase = RECALL_QUESTION_PHASES.get(question.question_id)
            if target_phase is None:
                continue
            expected = targets[target_phase]
            if question.kind == TaskQuestionKind.SHORT_TEXT:
                question.correct_text = expected
                continue
            if (question.kind != TaskQuestionKind.SINGLE_CHOICE
                    or not any(option.selectable and option.option_id == expected
                               for option in question.options)):
                raise CompileError(
                    f"Recall question '{question.question_id}' must offer the presented "
                    f"target '{expected}' as a single-choice option or use a short-text answer."
                )
            for option in question.options:
                if option.selectable:
                    option.correct = option.option_id == expected
                    option.score = float(option.correct)


def condition_tasks_replace_start_gate(
    condition: Condition,
    *,
    block_index: int,
    block_count: int,
    global_order_index: int = 0,
) -> bool:
    """Return whether an applicable pre-task explicitly serves as the start gate."""

    return any(
        binding.replaces_condition_start_gate
        and _binding_applies(
            binding,
            block_index=block_index,
            block_count=block_count,
            global_order_index=global_order_index,
        )
        for binding in condition.pre_task_bindings
    )


def _binding_applies(
    binding: TaskBinding,
    *,
    block_index: int,
    block_count: int,
    global_order_index: int = 0,
) -> bool:
    if binding.occurrence == TaskOccurrence.EVERY_ENTRY:
        return True
    if binding.occurrence == TaskOccurrence.FIRST_OCCURRENCE:
        return block_index == 0
    if binding.occurrence == TaskOccurrence.FIRST_SESSION_ENTRY:
        return global_order_index == 0
    return block_index == block_count - 1


def _compile_backward_counting(
    module: TaskModule,
    *,
    project: ProjectFile,
    condition: Condition,
    phase: TaskPhase,
    block_index: int,
    block_count: int,
    global_order_index: int,
    session_seed: int,
    run_id: str,
    run_spec: RunSpec | None,
) -> BackwardCountingSpec | None:
    config = module.backward_counting
    if config is None:
        return None
    if module.steps or module.repeat_count != 1:
        raise CompileError("Backward-counting modules generate their own steps and run once.")
    # Revalidate mutable document data before generating screens from it.
    try:
        config = BackwardCountingConfig.model_validate(config.model_dump())
    except ValueError as exc:
        raise CompileError(f"Invalid backward-counting settings: {exc}") from exc
    source = config
    if config.role != BackwardCountingRole.BASELINE:
        expected_phase = (
            TaskPhase.PRE_CONDITION if config.role == BackwardCountingRole.LOAD_START
            else TaskPhase.POST_CONDITION
        )
        if phase != expected_phase:
            raise CompileError(
                f"Backward-counting {config.role.value} requires {expected_phase.value}."
            )
        modules = {task.task_id: task for task in project.task_modules}
        matched: dict[BackwardCountingRole, list[BackwardCountingConfig]] = {
            BackwardCountingRole.LOAD_START: [], BackwardCountingRole.LOAD_REPORT: [],
        }
        for bindings, required_role in (
            (condition.pre_task_bindings, BackwardCountingRole.LOAD_START),
            (condition.post_task_bindings, BackwardCountingRole.LOAD_REPORT),
        ):
            applicable = [binding for binding in bindings if _binding_applies(
                binding, block_index=block_index, block_count=block_count,
                global_order_index=global_order_index,
            )]
            for index, binding in enumerate(applicable):
                linked_module = modules.get(binding.task_id)
                linked = linked_module.backward_counting if linked_module else None
                if linked is None or linked.link_id != config.link_id:
                    continue
                if linked.role == required_role:
                    matched[required_role].append(linked)
                    boundary_index = (
                        len(applicable) - 1
                        if required_role == BackwardCountingRole.LOAD_START else 0
                    )
                    if index != boundary_index:
                        raise CompileError(
                            "Backward-counting start must be the last pre-task and "
                            "its report must be the first post-task."
                        )
        if any(len(matches) != 1 for matches in matched.values()):
            raise CompileError(
                f"Backward-counting link '{config.link_id}' requires exactly one "
                "applicable pre-condition start and post-condition report per run."
            )
        source = matched[BackwardCountingRole.LOAD_START][0]
        try:
            source = BackwardCountingConfig.model_validate(source.model_dump())
        except ValueError as exc:
            raise CompileError(f"Invalid backward-counting start settings: {exc}") from exc
        if run_spec is None:
            raise CompileError("Concurrent backward counting requires a compiled FPVS run.")
    payload = source.model_dump()
    payload["role"] = config.role
    if config.role != BackwardCountingRole.BASELINE:
        assert run_spec is not None
        payload["duration_seconds"] = run_spec.display.total_frames / run_spec.display.refresh_hz
    seed_payload = f"backward-counting:{session_seed}:{run_id}:{config.link_id}".encode()
    seed = int.from_bytes(hashlib.sha256(seed_payload).digest()[:8], "big")
    payload["start_number"] = random.Random(seed).randint(source.start_min, source.start_max)
    try:
        return BackwardCountingSpec.model_validate(payload)
    except ValueError as exc:
        raise CompileError(f"Invalid compiled backward-counting settings: {exc}") from exc


def _modifier_provenance(modifier: ConditionModifier) -> ModifierProvenance:
    return ModifierProvenance(
        modifier_id=modifier.modifier_id, name=modifier.name, kind=modifier.kind,
    )


def resolve_modifier_baseline(
    project: ProjectFile, selected_conditions: list[Condition],
) -> list[ConditionModifier]:
    """Collect one compatible session requirement, without changing authored bindings."""
    try:
        validate_condition_modifiers(project)
    except ValueError as exc:
        raise CompileError(str(exc)) from exc
    selected = {condition.condition_id for condition in selected_conditions}
    requested = [modifier for modifier in project.condition_modifiers
                 if modifier.baseline_task_id and selected.intersection(
                     modifier_condition_ids(project, modifier.modifier_id))]
    if not requested:
        return []
    modules = {module.task_id: module for module in project.task_modules}
    signatures = set()
    for modifier in requested:
        assert modifier.baseline_task_id is not None
        baseline = modules[modifier.baseline_task_id].backward_counting
        assert baseline is not None
        signatures.add((baseline.subtraction_step, baseline.duration_seconds,
                        baseline.start_min, baseline.start_max,
                        baseline.instructions, baseline.endpoint_prompt))
        starts = [modules[task_id].backward_counting for task_id in modifier.pre_task_ids]
        if not any(config is not None and config.role == BackwardCountingRole.LOAD_START
                   and config.subtraction_step == baseline.subtraction_step for config in starts):
            raise CompileError(
                f"Modifier '{modifier.name}' baseline and load subtraction must match."
            )
    if len(signatures) != 1:
        names = ", ".join(modifier.name for modifier in requested)
        raise CompileError(
            f"Conflicting counting baseline requirements: {names}. Match their settings."
        )
    for condition in selected_conditions:
        for binding in [*condition.pre_task_bindings, *condition.post_task_bindings]:
            task = modules.get(binding.task_id)
            config = task.backward_counting if task else None
            if config is not None and config.role == BackwardCountingRole.BASELINE:
                assert task is not None
                raise CompileError(
                    f"Legacy baseline '{task.name}' overlaps the requested modifier baseline; "
                    "explicitly remove or group that baseline before running this selection."
                )
    return requested


def compile_modifier_baseline(
    project: ProjectFile, requirements: list[ConditionModifier], *, condition: Condition,
    session_seed: int, run_id: str, project_root: Path | None,
) -> TaskModuleSpec:
    owner = requirements[0]
    module = next(task for task in project.task_modules if task.task_id == owner.baseline_task_id)
    counting = _compile_backward_counting(
        module, project=project, condition=condition, phase=TaskPhase.PRE_CONDITION,
        block_index=0, block_count=1, global_order_index=0, session_seed=session_seed,
        run_id=run_id, run_spec=None,
    )
    provenance = _modifier_provenance(owner).model_copy(update={
        "session_baseline": True,
        "requested_modifier_ids": [modifier.modifier_id for modifier in requirements],
    })
    return _compile_task_module(
        module, phase=TaskPhase.PRE_CONDITION, occurrence=TaskOccurrence.FIRST_SESSION_ENTRY,
        random_seed=_task_seed(session_seed=session_seed, run_id=run_id,
                              phase=TaskPhase.PRE_CONDITION, binding_index=0,
                              task_id=module.task_id),
        project_root=project_root, counting_spec=counting, modifier=provenance,
    )


def _compile_image_memory(
    module: TaskModule, *, project: ProjectFile, condition: Condition, phase: TaskPhase,
    block_index: int, block_count: int, global_order_index: int,
    session_seed: int, run_id: str, project_root: Path | None,
) -> tuple[ImageMemorySpec | None, list[TaskStep] | None]:
    config = module.image_memory
    if config is None:
        return None, None
    expected_phase = (TaskPhase.PRE_CONDITION if config.role == ImageMemoryRole.STUDY
                      else TaskPhase.POST_CONDITION)
    if phase != expected_phase:
        raise CompileError(f"Image-memory {config.role.value} requires {expected_phase.value}.")
    modules = {task.task_id: task for task in project.task_modules}
    linked: dict[ImageMemoryRole, TaskModule] = {}
    for bindings, role in ((condition.pre_task_bindings, ImageMemoryRole.STUDY),
                           (condition.post_task_bindings, ImageMemoryRole.RECOGNITION)):
        applicable = [binding for binding in bindings if _binding_applies(
            binding, block_index=block_index, block_count=block_count,
            global_order_index=global_order_index,
        )]
        for index, binding in enumerate(applicable):
            candidate = modules.get(binding.task_id)
            if candidate is None or candidate.image_memory is None:
                continue
            if (candidate.image_memory.link_id != config.link_id
                    or candidate.image_memory.role != role):
                continue
            if role in linked:
                raise CompileError(
                    "Image memory requires exactly one linked study and recognition."
                )
            linked[role] = candidate
            expected_index = len(applicable) - 1 if role == ImageMemoryRole.STUDY else 0
            if index != expected_index:
                raise CompileError(
                    "Memory study must be the last pre-task and recognition first post-task."
                )
    if set(linked) != {ImageMemoryRole.STUDY, ImageMemoryRole.RECOGNITION}:
        raise CompileError("Image memory requires one linked study and recognition per entry.")
    study_module, report_module = linked[ImageMemoryRole.STUDY], linked[ImageMemoryRole.RECOGNITION]
    try:
        validate_image_memory_modules(study_module, report_module)
    except ValueError as exc:
        raise CompileError(str(exc)) from exc
    study, report = study_module.steps[0], report_module.steps[0]
    targets = [item.item_id for item in study.items]
    foils = [item.item_id for item in report.items if item.correct is False]
    image_paths: dict[str, str] = {}
    hashes: dict[tuple[ImageMemoryRole, str], str] = {}
    for role, task in linked.items():
        for item in task.steps[0].items:
            if item.image_path is None:
                raise CompileError("Remember four images requires actual target and foil images.")
            _validate_task_asset(task_id=task.task_id, image_path=item.image_path,
                                 project_root=project_root)
            assert project_root is not None
            path = resolve_project_relative_path(project_root, item.image_path)
            hashes[(role, item.item_id)] = hashlib.sha256(path.read_bytes()).hexdigest()
            if role == ImageMemoryRole.RECOGNITION:
                image_paths[item.item_id] = item.image_path
    if any(hashes[(ImageMemoryRole.STUDY, target)] !=
           hashes[(ImageMemoryRole.RECOGNITION, target)] for target in targets):
        raise CompileError("Memory targets must contain identical images in study and recognition.")
    if len({hashes[(ImageMemoryRole.RECOGNITION, item.item_id)] for item in report.items}) != 8:
        raise CompileError("Memory targets and foils must be eight distinct image files.")
    seed_data = f"image-memory:{session_seed}:{run_id}:{config.link_id}".encode()
    seed = int.from_bytes(hashlib.sha256(seed_data).digest()[:8], "big")
    rng = random.Random(seed)
    study_order = list(targets)
    recognition_order = [item.item_id for item in report.items]
    rng.shuffle(study_order)
    rng.shuffle(recognition_order)
    original = study if config.role == ImageMemoryRole.STUDY else report
    order = study_order if config.role == ImageMemoryRole.STUDY else recognition_order
    item_map = {item.item_id: item for item in original.items}
    realized_items = []
    for item_id, slot in zip(order, original.items, strict=True):
        geometry = (
            slot.model_dump(include={"x", "y", "width", "height", "unit"})
            if original.layout_mode == TaskLayoutMode.EXACT else {}
        )
        realized_items.append(item_map[item_id].model_copy(update=geometry, deep=True))
    realized = original.model_copy(update={
        "items": realized_items,
        "randomize_options": False,
    }, deep=True)
    return ImageMemorySpec(
        role=config.role, link_id=config.link_id, target_item_ids=targets, foil_item_ids=foils,
        study_order=study_order, recognition_order=recognition_order, image_paths=image_paths,
        random_seed=seed, study_duration_seconds=study.duration_seconds,
    ), [realized]


def _task_seed(
    *,
    session_seed: int,
    run_id: str,
    phase: TaskPhase,
    binding_index: int,
    task_id: str,
) -> int:
    payload = f"{session_seed}:{run_id}:{phase.value}:{binding_index}:{task_id}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") % (2**31)


def _compile_task_module(
    module: TaskModule,
    *,
    phase: TaskPhase,
    occurrence: TaskOccurrence,
    random_seed: int,
    project_root: Path | None,
    counting_spec: BackwardCountingSpec | None = None,
    memory_spec: ImageMemorySpec | None = None,
    source_steps: list[TaskStep] | None = None,
    modifier: ModifierProvenance | None = None,
) -> TaskModuleSpec:
    rng = random.Random(random_seed)
    if source_steps is None:
        source_steps = backward_counting_steps(counting_spec) if counting_spec else module.steps
    steps = [
        _compile_task_step(
            step,
            task_id=module.task_id,
            random_seed=rng.randrange(2**31),
            project_root=project_root,
        )
        for step in source_steps
    ]
    return TaskModuleSpec(
        task_id=module.task_id,
        name=module.name,
        phase=phase,
        occurrence=occurrence,
        random_seed=random_seed,
        repeat_count=module.repeat_count,
        steps=steps,
        backward_counting=counting_spec,
        image_memory=memory_spec,
        modifier=modifier,
    )


def _compile_task_step(
    step: TaskStep,
    *,
    task_id: str,
    random_seed: int,
    project_root: Path | None,
) -> TaskStepSpec:
    rng = random.Random(random_seed)
    items = [item.model_copy(deep=True) for item in step.items]
    for item in items:
        if item.image_path is not None:
            _validate_task_asset(
                task_id=task_id,
                image_path=item.image_path,
                project_root=project_root,
            )
    if step.randomize_options:
        rng.shuffle(items)

    questions = []
    question_option_orders: dict[str, list[str]] = {}
    for question in step.questions:
        options = [option.model_copy(deep=True) for option in question.options]
        for option in options:
            if option.image_path is not None:
                _validate_task_asset(
                    task_id=task_id,
                    image_path=option.image_path,
                    project_root=project_root,
                )
        if question.randomize_options or step.randomize_options:
            rng.shuffle(options)
        questions.append(question.model_copy(update={"options": options}, deep=True))
        question_option_orders[question.question_id] = [
            option.option_id for option in options
        ]

    payload = step.model_dump()
    payload.update(
        {
            "items": items,
            "questions": questions,
            "random_seed": random_seed,
            "realized_item_order": [item.item_id for item in items],
            "realized_question_option_orders": question_option_orders,
        }
    )
    return TaskStepSpec.model_validate(payload)


def _validate_task_asset(
    *,
    task_id: str,
    image_path: str,
    project_root: Path | None,
) -> None:
    path = PurePosixPath(image_path)
    required_prefix = ("stimuli", "task-assets", task_id)
    if path.parts[:3] != required_prefix or len(path.parts) < 4:
        raise CompileError(
            f"Task '{task_id}' image assets must live beneath "
            f"'stimuli/task-assets/{task_id}/': {image_path}"
        )
    if path.suffix.lower() not in SUPPORTED_TASK_IMAGE_SUFFIXES:
        raise CompileError(
            f"Task '{task_id}' uses unsupported image extension '{path.suffix}': {image_path}"
        )
    if project_root is None:
        raise CompileError(
            f"Task '{task_id}' contains image assets, so project_root is required for compilation."
        )
    try:
        resolved = resolve_project_relative_path(project_root, image_path)
    except ValueError as exc:
        raise CompileError(f"Unsafe task asset path '{image_path}': {exc}") from exc
    if not resolved.is_file():
        raise CompileError(f"Task asset is missing or is not a file: {image_path}")
