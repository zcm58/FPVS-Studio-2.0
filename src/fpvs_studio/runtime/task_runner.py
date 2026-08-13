"""Runtime-owned orchestration for compiled pre/post condition task modules."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from fpvs_studio.core.display_geometry import visual_angle_width_px
from fpvs_studio.core.enums import PresentationUnit
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.task_models import (
    TaskBranchOperator,
    TaskDisplayItem,
    TaskModuleSpec,
    TaskOption,
    TaskQuestion,
    TaskQuestionKind,
    TaskResponseKind,
    TaskResponseRecord,
    TaskStepKind,
    TaskStepResult,
    TaskStepSpec,
    validate_task_module_repeat_capacity,
)
from fpvs_studio.engines.base import (
    PresentationEngine,
    ResolvedTaskItem,
    ResolvedTaskResponseKind,
    ResolvedTaskStep,
    TaskEngineInput,
)
from fpvs_studio.runtime.session_export import append_task_response_checkpoint

_MAX_BRANCH_TRANSITIONS_MULTIPLIER = 20


@dataclass(frozen=True)
class TaskFlowOutcome:
    """Result of running one entry's pre- or post-condition task modules."""

    responses: tuple[TaskResponseRecord, ...] = ()
    aborted: bool = False
    abort_reason: str | None = None


class TaskResponseCheckpoint:
    """Append-only response journal that preserves partial data on abort or failure."""

    def __init__(self, path: Path | None) -> None:
        self._path = path

    @property
    def path(self) -> Path | None:
        return self._path

    def append(self, record: TaskResponseRecord) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        append_task_response_checkpoint(self._path, record)

    def discard(self) -> None:
        """Remove a finalized temporary journal and its empty private directory."""

        if self._path is None:
            return
        self._path.unlink(missing_ok=True)
        try:
            self._path.parent.rmdir()
        except OSError:
            pass


def run_task_modules(
    engine: PresentationEngine,
    modules: list[TaskModuleSpec],
    *,
    project_root: Path,
    run_spec: RunSpec,
    block_index: int,
    global_order_index: int,
    response_start_index: int = 0,
    checkpoint: TaskResponseCheckpoint | None = None,
) -> TaskFlowOutcome:
    """Execute compiled modules in order, preserving module-level repeat semantics."""

    responses: list[TaskResponseRecord] = []
    checkpoint = checkpoint or TaskResponseCheckpoint(None)
    for module in modules:
        validate_task_module_repeat_capacity(module)
        selection_history: dict[tuple[str, str, str | None], set[str]] = {}
        for module_repeat_index in range(module.repeat_count):
            outcome = _run_module_once(
                engine,
                module,
                project_root=project_root,
                run_spec=run_spec,
                block_index=block_index,
                global_order_index=global_order_index,
                module_repeat_index=module_repeat_index,
                response_start_index=response_start_index + len(responses),
                checkpoint=checkpoint,
                selection_history=selection_history,
            )
            responses.extend(outcome.responses)
            if outcome.aborted:
                return TaskFlowOutcome(
                    responses=tuple(responses),
                    aborted=True,
                    abort_reason=outcome.abort_reason,
                )
    return TaskFlowOutcome(responses=tuple(responses))


def _run_module_once(
    engine: PresentationEngine,
    module: TaskModuleSpec,
    *,
    project_root: Path,
    run_spec: RunSpec,
    block_index: int,
    global_order_index: int,
    module_repeat_index: int,
    response_start_index: int,
    checkpoint: TaskResponseCheckpoint,
    selection_history: dict[tuple[str, str, str | None], set[str]],
) -> TaskFlowOutcome:
    responses: list[TaskResponseRecord] = []
    answer_lookup: dict[str, object] = {}
    step_index_by_id = {step.step_id: index for index, step in enumerate(module.steps)}
    step_index = 0
    transition_count = 0
    maximum_transitions = max(1, len(module.steps) * _MAX_BRANCH_TRANSITIONS_MULTIPLIER)

    while step_index < len(module.steps):
        transition_count += 1
        if transition_count > maximum_transitions:
            raise RuntimeError(
                f"Task module '{module.task_id}' exceeded its validated branching limit."
            )
        step = module.steps[step_index]
        for step_repeat_index in range(step.repeat_count):
            rendered = _run_step(
                engine,
                module,
                step,
                project_root=project_root,
                run_spec=run_spec,
                block_index=block_index,
                global_order_index=global_order_index,
                module_repetition_index=module_repeat_index,
                step_repetition_index=step_repeat_index,
                response_start_index=response_start_index + len(responses),
                selection_history=selection_history,
            )
            for record in rendered:
                responses.append(record)
                checkpoint.append(record)
                if record.valid and record.question_id is not None:
                    answer_lookup[record.question_id] = _measure_value(record)
                if record.aborted:
                    return TaskFlowOutcome(
                        responses=tuple(responses),
                        aborted=True,
                        abort_reason=(
                            f"Task '{module.name}' was aborted during step '{step.step_id}'."
                        ),
                    )
            final_records: list[TaskResponseRecord] = []
            for rendered_record in rendered:
                if rendered_record.question_id is None:
                    final_records = [rendered_record]
                else:
                    final_records = [
                        existing
                        for existing in final_records
                        if existing.question_id != rendered_record.question_id
                    ]
                    final_records.append(rendered_record)
            for final_record in final_records:
                if final_record.valid and final_record.selected_option_ids:
                    history_key = (
                        module.task_id,
                        step.step_id,
                        final_record.question_id,
                    )
                    selection_history.setdefault(history_key, set()).update(
                        final_record.selected_option_ids
                    )
            if any(
                _exhausted_required_response(step, final_record)
                for final_record in final_records
            ):
                return TaskFlowOutcome(
                    responses=tuple(responses),
                    aborted=True,
                    abort_reason=(
                        f"Required task response was not completed for task "
                        f"'{module.name}', step '{step.step_id}'."
                    ),
                )
        next_step_id = _branch_target(step, answer_lookup)
        step_index = (
            step_index_by_id[next_step_id]
            if next_step_id is not None
            else step_index + 1
        )
    return TaskFlowOutcome(responses=tuple(responses))


def _exhausted_required_response(
    step: TaskStepSpec,
    record: TaskResponseRecord,
) -> bool:
    if record.aborted:
        return True
    if record.question_id is not None:
        question = next(
            (item for item in step.questions if item.question_id == record.question_id),
            None,
        )
        return bool(question is not None and question.required and not record.valid)
    return bool(step.require_response and not record.valid)


def _run_step(
    engine: PresentationEngine,
    module: TaskModuleSpec,
    step: TaskStepSpec,
    *,
    project_root: Path,
    run_spec: RunSpec,
    block_index: int,
    global_order_index: int,
    module_repetition_index: int,
    step_repetition_index: int,
    response_start_index: int,
    selection_history: dict[tuple[str, str, str | None], set[str]],
) -> list[TaskResponseRecord]:
    if step.kind == TaskStepKind.QUESTIONNAIRE:
        records: list[TaskResponseRecord] = []
        for question in step.questions:
            forbidden_ids = (
                set()
                if step.allow_duplicate_selections_across_repeats
                else selection_history.get(
                    (module.task_id, step.step_id, question.question_id),
                    set(),
                )
            )
            for attempt_index in range(step.max_attempts):
                result = engine.render_task_step(
                    _resolved_question_step(
                        module,
                        step,
                        question,
                        run_spec=run_spec,
                        forbidden_ids=forbidden_ids,
                    ),
                    project_root,
                )
                record = _response_record(
                    module,
                    step,
                    _core_step_result(result, question=question),
                    run_spec=run_spec,
                    block_index=block_index,
                    global_order_index=global_order_index,
                    module_repetition_index=module_repetition_index,
                    step_repetition_index=step_repetition_index,
                    attempt_index=attempt_index,
                    response_index=response_start_index + len(records),
                    question=question,
                    forbidden_ids=forbidden_ids,
                )
                records.append(record)
                if record.aborted or not _should_retry(step, record, attempt_index):
                    break
            if records[-1].aborted or (question.required and not records[-1].valid):
                break
        return records

    records = []
    forbidden_ids = (
        set()
        if step.allow_duplicate_selections_across_repeats
        else selection_history.get((module.task_id, step.step_id, None), set())
    )
    for attempt_index in range(step.max_attempts):
        result = engine.render_task_step(
            _resolved_step(
                module,
                step,
                run_spec=run_spec,
                forbidden_ids=forbidden_ids,
            ),
            project_root,
        )
        record = _response_record(
            module,
            step,
            _core_step_result(result, step=step),
            run_spec=run_spec,
            block_index=block_index,
            global_order_index=global_order_index,
            module_repetition_index=module_repetition_index,
            step_repetition_index=step_repetition_index,
            attempt_index=attempt_index,
            response_index=response_start_index + len(records),
            forbidden_ids=forbidden_ids,
        )
        records.append(record)
        if record.aborted or not _should_retry(step, record, attempt_index):
            break
    return records


def _should_retry(
    step: TaskStepSpec,
    record: TaskResponseRecord,
    attempt_index: int,
) -> bool:
    if attempt_index + 1 >= step.max_attempts:
        return False
    if step.retry_on_invalid and not record.valid:
        return True
    return step.retry_on_incorrect and record.correct is False


def _resolved_step(
    module: TaskModuleSpec,
    step: TaskStepSpec,
    *,
    run_spec: RunSpec,
    forbidden_ids: set[str] | None = None,
) -> ResolvedTaskStep:
    items_by_id = {item.item_id: item for item in step.items}
    ordered_ids = step.realized_item_order or [item.item_id for item in step.items]
    ordered_items = [items_by_id[item_id] for item_id in ordered_ids]
    resolved_items = _resolved_display_items(
        step,
        ordered_items,
        run_spec=run_spec,
        forbidden_ids=forbidden_ids,
    )
    return ResolvedTaskStep(
        task_id=module.task_id,
        step_id=step.step_id,
        kind=step.kind.value,
        response_kind=_step_response_kind(step),
        heading=step.heading or None,
        body=step.text or None,
        items=resolved_items,
        allowed_keys=tuple(step.allowed_keys),
        continue_key=step.continue_key or "space",
        duration_s=step.duration_seconds,
        timeout_s=step.timeout_seconds,
        required=step.require_response,
        minimum_selections=step.min_selections,
        maximum_selections=step.max_selections,
        submission_mode=step.submission_mode.value,
        prompt_position_px=_prompt_position_px(step, run_spec=run_spec),
        prompt_height_px=_prompt_height_px(step, run_spec=run_spec),
        show_footer=step.show_footer,
    )


def _resolved_question_step(
    module: TaskModuleSpec,
    step: TaskStepSpec,
    question: TaskQuestion,
    *,
    run_spec: RunSpec,
    forbidden_ids: set[str] | None = None,
) -> ResolvedTaskStep:
    if question.kind == TaskQuestionKind.RATING:
        items, _rating_values = _rating_items(
            question,
            run_spec=run_spec,
            forbidden_ids=forbidden_ids,
        )
    else:
        order = step.realized_question_option_orders.get(
            question.question_id,
            [option.option_id for option in question.options],
        )
        options_by_id = {option.option_id: option for option in question.options}
        ordered_options = [options_by_id[option_id] for option_id in order]
        items = _question_option_items(
            ordered_options,
            run_spec=run_spec,
            forbidden_ids=forbidden_ids,
            columns=step.columns,
        )
    minimum = question.min_selections
    if minimum is None:
        minimum = 1 if question.required else 0
    maximum = question.max_selections
    if question.kind == TaskQuestionKind.SINGLE_CHOICE:
        maximum = 1
    return ResolvedTaskStep(
        task_id=module.task_id,
        step_id=step.step_id,
        kind=step.kind.value,
        response_kind=_question_response_kind(question),
        heading=step.heading or None,
        body=step.text or None,
        prompt=question.prompt,
        items=items,
        duration_s=step.duration_seconds,
        timeout_s=step.timeout_seconds,
        required=question.required,
        minimum_selections=minimum,
        maximum_selections=maximum,
        numeric_minimum=question.min_value,
        numeric_maximum=question.max_value,
        numeric_step=question.step,
        maximum_text_length=question.max_text_length,
        submission_mode=step.submission_mode.value,
        question_id=question.question_id,
        prompt_position_px=_prompt_position_px(step, run_spec=run_spec),
        prompt_height_px=_prompt_height_px(step, run_spec=run_spec),
        show_footer=step.show_footer,
    )


def _prompt_position_px(
    step: TaskStepSpec,
    *,
    run_spec: RunSpec,
) -> tuple[float, float] | None:
    if step.layout_mode.value != "exact":
        return None
    return (
        _layout_value_px(step.prompt_x, step.prompt_unit, run_spec=run_spec, signed=True),
        _layout_value_px(step.prompt_y, step.prompt_unit, run_spec=run_spec, signed=True),
    )


def _prompt_height_px(step: TaskStepSpec, *, run_spec: RunSpec) -> float | None:
    if step.prompt_height is None:
        return None
    return _layout_value_px(step.prompt_height, step.prompt_unit, run_spec=run_spec)


def _resolved_display_item(
    item: TaskDisplayItem,
    *,
    run_spec: RunSpec,
    selectable: bool | None = None,
) -> ResolvedTaskItem:
    x_px = _layout_value_px(item.x, item.unit, run_spec=run_spec, signed=True)
    y_px = _layout_value_px(item.y, item.unit, run_spec=run_spec, signed=True)
    width_px = (
        _layout_value_px(item.width, item.unit, run_spec=run_spec)
        if item.width is not None
        else None
    )
    height_px = (
        _layout_value_px(item.height, item.unit, run_spec=run_spec)
        if item.height is not None
        else None
    )
    size_px = (
        (width_px, height_px)
        if width_px is not None and height_px is not None
        else None
    )
    return ResolvedTaskItem(
        item_id=item.item_id,
        text=item.text,
        image_path=item.image_path,
        position_px=(x_px, y_px),
        size_px=size_px,
        text_height_px=height_px
        or _layout_value_px(
            1.0,
            PresentationUnit.DEGREES,
            run_spec=run_spec,
        ),
        selectable=item.selectable if selectable is None else selectable,
    )


def _resolved_display_items(
    step: TaskStepSpec,
    items: list[TaskDisplayItem],
    *,
    run_spec: RunSpec,
    forbidden_ids: set[str] | None = None,
) -> tuple[ResolvedTaskItem, ...]:
    """Resolve exact coordinates or place authored items in a responsive grid."""

    resolved = [
        _resolved_display_item(
            item,
            run_spec=run_spec,
            selectable=item.selectable and item.item_id not in (forbidden_ids or set()),
        )
        for item in items
    ]
    if step.layout_mode.value == "exact" or not resolved:
        return tuple(resolved)

    column_count = min(step.columns or min(4, len(resolved)), len(resolved))
    row_count = (len(resolved) + column_count - 1) // column_count
    x_spacing = run_spec.display.screen_width_px * 0.2
    y_spacing = run_spec.display.screen_height_px * 0.18
    default_image_size = min(x_spacing * 0.72, y_spacing * 0.72)
    placed: list[ResolvedTaskItem] = []
    for index, (authored, item) in enumerate(zip(items, resolved, strict=True)):
        column = index % column_count
        row = index // column_count
        position_px = (
            (column - (column_count - 1) / 2.0) * x_spacing,
            ((row_count - 1) / 2.0 - row) * y_spacing,
        )
        size_px = item.size_px
        if authored.modality.value == "image" and size_px is None:
            size_px = (default_image_size, default_image_size)
        placed.append(replace(item, position_px=position_px, size_px=size_px))
    return tuple(placed)


def _question_option_items(
    options: list[TaskOption],
    *,
    run_spec: RunSpec,
    forbidden_ids: set[str] | None = None,
    columns: int | None = None,
) -> tuple[ResolvedTaskItem, ...]:
    count = len(options)
    if count == 0:
        return ()
    column_count = min(columns or min(4, count), count)
    rows = (count + column_count - 1) // column_count
    x_spacing = run_spec.display.screen_width_px * 0.2
    y_spacing = run_spec.display.screen_height_px * 0.16
    image_size = min(x_spacing * 0.72, y_spacing * 0.72)
    text_height = max(20.0, run_spec.display.screen_height_px * 0.032)
    resolved: list[ResolvedTaskItem] = []
    for index, option in enumerate(options):
        column = index % column_count
        row = index // column_count
        x_px = (column - (column_count - 1) / 2.0) * x_spacing
        y_px = ((rows - 1) / 2.0 - row) * y_spacing
        resolved.append(
            ResolvedTaskItem(
                item_id=option.option_id,
                text=None if option.image_path is not None else option.label,
                image_path=option.image_path,
                position_px=(x_px, y_px),
                size_px=(image_size, image_size) if option.image_path is not None else None,
                text_height_px=text_height,
                selectable=(
                    option.selectable and option.option_id not in (forbidden_ids or set())
                ),
            )
        )
        if option.image_path is not None:
            resolved.append(
                ResolvedTaskItem(
                    item_id=f"__fpvs-label-{option.option_id}",
                    text=option.label,
                    position_px=(x_px, y_px - image_size * 0.66),
                    text_height_px=max(16.0, text_height * 0.72),
                )
            )
    return tuple(resolved)


def _rating_items(
    question: TaskQuestion,
    *,
    run_spec: RunSpec,
    forbidden_ids: set[str] | None = None,
) -> tuple[tuple[ResolvedTaskItem, ...], dict[str, float]]:
    assert question.min_value is not None
    assert question.max_value is not None
    step = question.step or 1.0
    span_steps = (question.max_value - question.min_value) / step
    if abs(span_steps - round(span_steps)) > 1e-9:
        raise RuntimeError(
            f"Rating question '{question.question_id}' range is not aligned to its step."
        )
    tick_count = int(round(span_steps)) + 1
    if tick_count > 100:
        raise RuntimeError(
            f"Rating question '{question.question_id}' has more than 100 response ticks."
        )
    values = [round(question.min_value + index * step, 10) for index in range(tick_count)]
    x_spacing = min(
        run_spec.display.screen_width_px * 0.11,
        run_spec.display.screen_width_px * 0.75 / max(1, len(values)),
    )
    text_height = max(20.0, run_spec.display.screen_height_px * 0.032)
    items: list[ResolvedTaskItem] = []
    mapping: dict[str, float] = {}
    for index, numeric_value in enumerate(values):
        item_id = f"rating-{index + 1}"
        mapping[item_id] = numeric_value
        items.append(
            ResolvedTaskItem(
                item_id=item_id,
                text=f"{numeric_value:g}",
                position_px=((index - (len(values) - 1) / 2.0) * x_spacing, 0.0),
                text_height_px=text_height,
                selectable=item_id not in (forbidden_ids or set()),
            )
        )
    if question.min_label:
        items.append(
            ResolvedTaskItem(
                item_id=f"__fpvs-label-{question.question_id}-minimum",
                text=question.min_label,
                position_px=(-((len(values) - 1) / 2.0) * x_spacing, -text_height * 1.8),
                text_height_px=max(16.0, text_height * 0.75),
            )
        )
    if question.max_label:
        items.append(
            ResolvedTaskItem(
                item_id=f"__fpvs-label-{question.question_id}-maximum",
                text=question.max_label,
                position_px=(((len(values) - 1) / 2.0) * x_spacing, -text_height * 1.8),
                text_height_px=max(16.0, text_height * 0.75),
            )
        )
    return tuple(items), mapping


def _layout_value_px(
    value: float,
    unit: PresentationUnit,
    *,
    run_spec: RunSpec,
    signed: bool = False,
) -> float:
    if unit == PresentationUnit.WINDOW_HEIGHT_FRACTION:
        return float(value) * float(run_spec.display.screen_height_px)
    if signed and value == 0:
        return 0.0
    magnitude = float(
        visual_angle_width_px(
            degrees=abs(float(value)),
            viewing_distance_cm=run_spec.display.viewing_distance_cm,
            screen_width_cm=run_spec.display.screen_width_cm,
            screen_width_px=run_spec.display.screen_width_px,
        )
    )
    if not signed or value >= 0:
        return magnitude
    return -magnitude


def _step_response_kind(step: TaskStepSpec) -> ResolvedTaskResponseKind:
    if step.kind == TaskStepKind.TIMED_FEEDBACK:
        return "none"
    if step.kind == TaskStepKind.CHOICE_GRID:
        return "single_choice" if step.max_selections == 1 else "multiple_choice"
    if step.kind == TaskStepKind.RAW_KEY:
        return "raw_key"
    if step.continue_key is not None:
        return "continue"
    return "none"


def _question_response_kind(question: TaskQuestion) -> ResolvedTaskResponseKind:
    mapping: dict[TaskQuestionKind, ResolvedTaskResponseKind] = {
        TaskQuestionKind.SINGLE_CHOICE: "single_choice",
        TaskQuestionKind.MULTIPLE_CHOICE: "multiple_choice",
        TaskQuestionKind.SHORT_TEXT: "short_text",
        TaskQuestionKind.LONG_TEXT: "long_text",
        TaskQuestionKind.NUMERIC: "numeric",
        TaskQuestionKind.RATING: "rating",
    }
    return mapping[question.kind]


def _core_step_result(
    result: TaskEngineInput,
    *,
    step: TaskStepSpec | None = None,
    question: TaskQuestion | None = None,
) -> TaskStepResult:
    response_kind = TaskResponseKind.NONE
    numeric_value = result.numeric_value
    selected_option_ids = list(result.selected_item_ids)
    if question is not None:
        response_kind = {
            TaskQuestionKind.SINGLE_CHOICE: TaskResponseKind.OPTION_SELECTION,
            TaskQuestionKind.MULTIPLE_CHOICE: TaskResponseKind.OPTION_SELECTION,
            TaskQuestionKind.SHORT_TEXT: TaskResponseKind.TEXT,
            TaskQuestionKind.LONG_TEXT: TaskResponseKind.TEXT,
            TaskQuestionKind.NUMERIC: TaskResponseKind.NUMERIC,
            TaskQuestionKind.RATING: TaskResponseKind.RATING,
        }[question.kind]
        if question.kind == TaskQuestionKind.RATING and selected_option_ids:
            try:
                rating_index = int(selected_option_ids[0].removeprefix("rating-")) - 1
            except ValueError:
                rating_index = -1
            if rating_index >= 0 and question.min_value is not None:
                numeric_value = question.min_value + rating_index * (question.step or 1.0)
    elif step is not None:
        if step.kind == TaskStepKind.CHOICE_GRID:
            response_kind = TaskResponseKind.OPTION_SELECTION
        elif step.kind == TaskStepKind.RAW_KEY or step.continue_key is not None:
            response_kind = TaskResponseKind.KEY
    return TaskStepResult(
        aborted=result.aborted,
        timed_out=result.timed_out,
        response_kind=response_kind,
        key=None if result.aborted else result.key,
        selected_option_ids=selected_option_ids,
        text_value=result.text_value,
        numeric_value=numeric_value,
        mouse_x=result.mouse_position_px[0] if result.mouse_position_px is not None else None,
        mouse_y=result.mouse_position_px[1] if result.mouse_position_px is not None else None,
        mouse_button=result.mouse_button,
        reaction_time_s=result.reaction_time_s,
        key_reaction_time_s=result.key_reaction_time_s,
        key_duration_s=result.key_duration_s,
        realized_option_order=list(result.displayed_item_ids),
    )


def _response_record(
    module: TaskModuleSpec,
    step: TaskStepSpec,
    result: TaskStepResult,
    *,
    run_spec: RunSpec,
    block_index: int,
    global_order_index: int,
    module_repetition_index: int,
    step_repetition_index: int,
    attempt_index: int,
    response_index: int,
    question: TaskQuestion | None = None,
    forbidden_ids: set[str] | None = None,
) -> TaskResponseRecord:
    valid = _response_is_valid(
        step,
        result,
        question=question,
        forbidden_ids=forbidden_ids,
    )
    correct, score = _score_response(step, result, question=question)
    return TaskResponseRecord(
        response_index=response_index,
        task_id=module.task_id,
        step_id=step.step_id,
        phase=module.phase,
        condition_id=run_spec.condition.condition_id,
        run_id=run_spec.run_id,
        block_index=block_index,
        global_order_index=global_order_index,
        repetition_index=module_repetition_index,
        step_repetition_index=step_repetition_index,
        attempt_index=attempt_index,
        question_id=question.question_id if question is not None else None,
        response_kind=result.response_kind,
        key=result.key,
        selected_option_ids=result.selected_option_ids,
        text_value=result.text_value,
        numeric_value=result.numeric_value,
        mouse_x=result.mouse_x,
        mouse_y=result.mouse_y,
        mouse_button=result.mouse_button,
        reaction_time_s=result.reaction_time_s,
        key_reaction_time_s=result.key_reaction_time_s,
        key_duration_s=result.key_duration_s,
        realized_option_order=_realized_option_order(step, question=question),
        valid=valid,
        correct=correct,
        score=score,
        timed_out=result.timed_out,
        aborted=result.aborted,
    )


def _realized_option_order(
    step: TaskStepSpec,
    *,
    question: TaskQuestion | None,
) -> list[str]:
    if question is not None:
        if question.kind == TaskQuestionKind.RATING:
            return _rating_option_ids(question)
        return list(
            step.realized_question_option_orders.get(
                question.question_id,
                [option.option_id for option in question.options],
            )
        )
    return list(step.realized_item_order or [item.item_id for item in step.items])


def _response_is_valid(
    step: TaskStepSpec,
    result: TaskStepResult,
    *,
    question: TaskQuestion | None,
    forbidden_ids: set[str] | None = None,
) -> bool:
    if result.aborted or result.timed_out:
        return False
    if question is None:
        if step.kind == TaskStepKind.CHOICE_GRID:
            selectable_ids = {item.item_id for item in step.items if item.selectable}
            selected_ids = set(result.selected_option_ids)
            return (
                selected_ids <= selectable_ids
                and not selected_ids.intersection(forbidden_ids or set())
                and len(selected_ids) == len(result.selected_option_ids)
                and step.min_selections <= len(selected_ids) <= step.max_selections
            )
        if result.selected_option_ids:
            return False
        if step.kind == TaskStepKind.RAW_KEY:
            return result.key in step.allowed_keys
        if step.kind in {TaskStepKind.INSTRUCTION, TaskStepKind.STUDY}:
            if result.key is None:
                return step.duration_seconds is not None
            accepted_keys = step.allowed_keys or [step.continue_key or "space"]
            return result.key in accepted_keys
        if step.require_response and result.response_kind == TaskResponseKind.NONE:
            return False
        return True
    if question.kind in {TaskQuestionKind.SINGLE_CHOICE, TaskQuestionKind.MULTIPLE_CHOICE}:
        selectable_ids = {option.option_id for option in question.options if option.selectable}
        selected_ids = set(result.selected_option_ids)
        minimum = question.min_selections
        if minimum is None:
            minimum = 1 if question.required else 0
        maximum = question.max_selections
        if maximum is None:
            maximum = (
                1
                if question.kind == TaskQuestionKind.SINGLE_CHOICE
                else len(question.options)
            )
        return (
            selected_ids <= selectable_ids
            and not selected_ids.intersection(forbidden_ids or set())
            and len(selected_ids) == len(result.selected_option_ids)
            and minimum <= len(selected_ids) <= maximum
        )
    if question.kind == TaskQuestionKind.RATING:
        selected_ids = set(result.selected_option_ids)
        if selected_ids:
            rating_ids = set(_rating_option_ids(question))
            if (
                len(selected_ids) != len(result.selected_option_ids)
                or len(selected_ids) != 1
                or not selected_ids <= rating_ids
                or selected_ids.intersection(forbidden_ids or set())
            ):
                return False
    elif result.selected_option_ids:
        return False
    if question.kind in {TaskQuestionKind.SHORT_TEXT, TaskQuestionKind.LONG_TEXT}:
        if result.text_value is not None and len(result.text_value) > question.max_text_length:
            return False
        return bool(result.text_value and result.text_value.strip()) or not question.required
    if question.kind in {TaskQuestionKind.NUMERIC, TaskQuestionKind.RATING}:
        if result.numeric_value is None:
            return not question.required
        return (
            question.min_value is not None
            and question.max_value is not None
            and question.min_value <= result.numeric_value <= question.max_value
            and (
                question.step is None
                or _numeric_step_aligned(
                    result.numeric_value,
                    minimum=question.min_value,
                    step=question.step,
                )
            )
        )
    return True


def _numeric_step_aligned(value: float, *, minimum: float, step: float) -> bool:
    offset_steps = (value - minimum) / step
    return abs(offset_steps - round(offset_steps)) <= 1e-9


def _rating_option_ids(question: TaskQuestion) -> list[str]:
    assert question.min_value is not None
    assert question.max_value is not None
    step = question.step or 1.0
    tick_count = int(round((question.max_value - question.min_value) / step)) + 1
    return [f"rating-{index + 1}" for index in range(tick_count)]


def _score_response(
    step: TaskStepSpec,
    result: TaskStepResult,
    *,
    question: TaskQuestion | None,
) -> tuple[bool | None, float | None]:
    if question is None:
        candidates: list[Any] = [item for item in step.items if item.selectable]
        selected_ids = set(result.selected_option_ids)
        candidate_ids = {id(candidate): candidate.item_id for candidate in candidates}
    else:
        candidates = [option for option in question.options if option.selectable]
        selected_ids = set(result.selected_option_ids)
        candidate_ids = {id(candidate): candidate.option_id for candidate in candidates}
    authored_correctness = any(candidate.correct is not None for candidate in candidates)
    authored_scores = any(candidate.score is not None for candidate in candidates)
    correct = None
    if authored_correctness:
        expected = {
            candidate_ids[id(candidate)] for candidate in candidates if candidate.correct
        }
        single_response = (
            (question is None and step.max_selections == 1)
            or (
                question is not None
                and question.kind == TaskQuestionKind.SINGLE_CHOICE
            )
        )
        correct = (
            bool(selected_ids) and selected_ids <= expected
            if single_response
            else selected_ids == expected
        )
    score = None
    if authored_scores:
        score = sum(
            float(candidate.score or 0.0)
            for candidate in candidates
            if candidate_ids[id(candidate)] in selected_ids
        )
    return correct, score


def _measure_value(record: TaskResponseRecord) -> object:
    if record.selected_option_ids:
        return list(record.selected_option_ids)
    if record.numeric_value is not None:
        return record.numeric_value
    if record.text_value is not None:
        return record.text_value
    return record.key


def _branch_target(step: TaskStepSpec, answers: dict[str, object]) -> str | None:
    for rule in step.branch_rules:
        value = answers.get(rule.question_id)
        if _branch_matches(rule.operator, value, rule.expected_values, rule.expected_numeric):
            return rule.next_step_id
    return None


def _branch_matches(
    operator: TaskBranchOperator,
    value: object,
    expected_values: list[str],
    expected_numeric: float | None,
) -> bool:
    if operator == TaskBranchOperator.ANSWERED:
        return value is not None and value != "" and value != () and value != []
    if operator in {TaskBranchOperator.GREATER_THAN, TaskBranchOperator.LESS_THAN}:
        if not isinstance(value, (int, float)) or expected_numeric is None:
            return False
        return (
            value > expected_numeric
            if operator == TaskBranchOperator.GREATER_THAN
            else value < expected_numeric
        )
    if isinstance(value, list):
        values = [str(item) for item in value]
    elif value is None:
        values = []
    else:
        values = [str(value)]
    if operator == TaskBranchOperator.EQUALS:
        if isinstance(value, list):
            return len(values) == len(expected_values) and set(values) == set(expected_values)
        return len(values) == 1 and values[0] in expected_values
    if operator == TaskBranchOperator.NOT_EQUALS:
        return not _branch_matches(TaskBranchOperator.EQUALS, value, expected_values, None)
    if operator == TaskBranchOperator.CONTAINS:
        if isinstance(value, list):
            return any(expected in values for expected in expected_values)
        return any(expected in values[0] for expected in expected_values) if values else False
    return False
