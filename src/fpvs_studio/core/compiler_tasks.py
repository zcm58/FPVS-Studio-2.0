"""Compilation helpers for project-owned condition task modules."""

from __future__ import annotations

import hashlib
import random
from pathlib import Path, PurePosixPath

from fpvs_studio.core.compiler_support import CompileError
from fpvs_studio.core.models import Condition, ProjectFile
from fpvs_studio.core.paths import resolve_project_relative_path
from fpvs_studio.core.task_models import (
    TaskBinding,
    TaskModule,
    TaskModuleSpec,
    TaskOccurrence,
    TaskPhase,
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
        compiled.append(
            _compile_task_module(
                module,
                phase=phase,
                occurrence=binding.occurrence,
                random_seed=task_seed,
                project_root=project_root,
            )
        )
    return compiled


def condition_tasks_replace_start_gate(
    condition: Condition,
    *,
    block_index: int,
    block_count: int,
) -> bool:
    """Return whether an applicable pre-task explicitly serves as the start gate."""

    return any(
        binding.replaces_condition_start_gate
        and _binding_applies(
            binding,
            block_index=block_index,
            block_count=block_count,
        )
        for binding in condition.pre_task_bindings
    )


def _binding_applies(
    binding: TaskBinding,
    *,
    block_index: int,
    block_count: int,
) -> bool:
    if binding.occurrence == TaskOccurrence.EVERY_ENTRY:
        return True
    if binding.occurrence == TaskOccurrence.FIRST_OCCURRENCE:
        return block_index == 0
    return block_index == block_count - 1


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
) -> TaskModuleSpec:
    rng = random.Random(random_seed)
    steps = [
        _compile_task_step(
            step,
            task_id=module.task_id,
            random_seed=rng.randrange(2**31),
            project_root=project_root,
        )
        for step in module.steps
    ]
    return TaskModuleSpec(
        task_id=module.task_id,
        name=module.name,
        phase=phase,
        occurrence=occurrence,
        random_seed=random_seed,
        repeat_count=module.repeat_count,
        steps=steps,
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
