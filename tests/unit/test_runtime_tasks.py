"""Focused runtime and engine-neutral modular task tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from PIL import ImageFont
from pydantic import ValidationError
from tests.unit.runtime_launcher_helpers import StubEngine
from tests.unit.test_runtime_preflight import _PreflightEngine

from fpvs_studio.assets import bundled_task_font_path
from fpvs_studio.core.compiler import compile_run_spec, compile_session_plan
from fpvs_studio.core.enums import PresentationUnit
from fpvs_studio.core.task_models import (
    TaskBranchOperator,
    TaskDisplayItem,
    TaskFontFamily,
    TaskItemModality,
    TaskLayoutMode,
    TaskModule,
    TaskModuleSpec,
    TaskOccurrence,
    TaskOption,
    TaskPhase,
    TaskQuestion,
    TaskQuestionKind,
    TaskStepKind,
    TaskStepSpec,
    task_requires_scene_schema,
    task_requires_text_alignment_schema,
)
from fpvs_studio.engines import psychopy_tasks
from fpvs_studio.engines.base import ResolvedTaskItem, ResolvedTaskStep, TaskEngineInput
from fpvs_studio.engines.psychopy_tasks import (
    _completed_input,
    _draw_step,
    _handle_keys,
    _key_list_for_step,
    _prepare_item_stimuli,
    _prepare_text_box,
    _register_bundled_task_font,
    render_task_step,
)
from fpvs_studio.runtime.preflight import PreflightError, preflight_session_plan
from fpvs_studio.runtime.run_worker import RuntimeWorker
from fpvs_studio.runtime.task_runner import (
    TaskResponseCheckpoint,
    _branch_matches,
    run_task_modules,
)


class _TaskEngine(StubEngine):
    def __init__(
        self,
        queued_inputs: list[TaskEngineInput],
        captures: dict[str, object] | None = None,
    ) -> None:
        super().__init__(captures or {})
        self.queued_inputs = queued_inputs
        self.rendered_steps: list[ResolvedTaskStep] = []

    def render_task_step(
        self,
        step: ResolvedTaskStep,
        project_root: Path,
    ) -> TaskEngineInput:
        self.rendered_steps.append(step)
        assert project_root.is_absolute()
        return self.queued_inputs.pop(0)


def _compiled_run(sample_project, sample_project_root):
    return compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="task-test-run",
    )


def test_native_circle_task_preserves_signed_rgb_and_rejects_invalid_shapes() -> None:
    item = TaskDisplayItem(
        item_id="red", modality=TaskItemModality.CIRCLE,
        width=5.0, height=5.0, color_rgb=(0.91, -0.4387, -0.602),
        line_color_rgb=(1.0, 1.0, 1.0), selectable=True,
    )
    assert TaskDisplayItem.model_validate_json(item.model_dump_json()) == item
    assert item.color_rgb == (0.91, -0.4387, -0.602)
    assert item.circle_edges is None
    for color in ((1.01, 0, 0), (0, float("nan"), 0), (0, 0, float("inf"))):
        with pytest.raises(ValidationError, match="RGB channels"):
            TaskDisplayItem.model_validate({**item.model_dump(), "color_rgb": color})
    for update, message in (
        ({"width": None}, "require width and height"),
        ({"text": "circle"}, "may not store text"),
        ({"circle_edges": 2}, "greater than or equal to 3"),
        ({"line_width_px": float("inf")}, "must be finite"),
    ):
        with pytest.raises(ValidationError, match=message):
            TaskDisplayItem.model_validate({**item.model_dump(), **update})
    with pytest.raises(ValidationError, match="Only circle"):
        TaskDisplayItem(
            item_id="text", modality=TaskItemModality.TEXT, text="Text",
            line_color_rgb=(1, 1, 1),
        )


def test_legacy_task_serialization_omits_unused_native_visual_fields() -> None:
    step = TaskStepSpec(
        step_id="study", kind=TaskStepKind.STUDY, random_seed=1, continue_key="space",
        items=[TaskDisplayItem(item_id="word", modality="text", text="Word")],
    )
    serialized = step.model_dump()
    assert "prompt_width" not in serialized
    assert "randomize_positions" not in serialized
    assert "degree_geometry" not in serialized
    assert not {"color_rgb", "line_color_rgb", "line_width_px", "circle_edges",
                "text_alignment"}.intersection(
        serialized["items"][0]
    )
    module = TaskModule(task_id="study", name="Study", steps=[step])
    assert not task_requires_scene_schema(module)
    module.steps[0].items[0].color_rgb = (1, -1, -1)
    assert task_requires_scene_schema(module)
    assert module.model_dump()["steps"][0]["items"][0]["color_rgb"] == (1, -1, -1)


@pytest.mark.parametrize("alignment", ["left", "center", "right"])
def test_instruction_text_alignment_survives_resolution_without_moving_anchor(
    alignment, sample_project, sample_project_root,
) -> None:
    run = _compiled_run(sample_project, sample_project_root)
    item = TaskDisplayItem(
        item_id="instructions", modality="text", text="Identify the target.\nKeep looking at +.",
        text_alignment=alignment, x=0.12, y=0.2, width=0.8, height=0.03,
        unit=PresentationUnit.WINDOW_HEIGHT_FRACTION,
    )
    assert TaskDisplayItem.model_validate_json(item.model_dump_json()) == item
    assert ("text_alignment" in item.model_dump()) == (alignment != "center")
    step = TaskStepSpec(
        step_id="instructions", kind=TaskStepKind.INSTRUCTION, random_seed=1,
        layout_mode=TaskLayoutMode.EXACT, continue_key="space", items=[item],
    )
    module = _module(step)
    assert task_requires_text_alignment_schema(module) == (alignment != "center")
    engine = _TaskEngine([TaskEngineInput(key="space")])
    run_task_modules(
        engine, [module], project_root=sample_project_root, run_spec=run,
        block_index=0, global_order_index=0,
    )
    resolved, = engine.rendered_steps[0].items
    height = run.display.screen_height_px
    assert resolved.text_alignment == alignment
    assert resolved.position_px == pytest.approx((0.12 * height, 0.2 * height))
    assert resolved.size_px == pytest.approx((0.8 * height, 0.03 * height))
    calls = []

    class _Visual:
        @staticmethod
        def TextStim(*args, **kwargs):
            calls.append(kwargs)
            return object()

    _prepare_item_stimuli(
        visual=_Visual, window=object(), project_root=sample_project_root, items=(resolved,),
    )
    call, = calls
    assert call["pos"] == resolved.position_px
    assert call["wrapWidth"] == pytest.approx(0.8 * height)
    assert call["height"] == pytest.approx(0.03 * height)
    assert call["text"] == item.text
    if alignment == "center":
        assert "alignText" not in call and "anchorHoriz" not in call
    else:
        assert call["alignText"] == alignment
        assert call["anchorHoriz"] == "center"


def test_task_text_alignment_rejects_unknown_values_and_nontext_items() -> None:
    with pytest.raises(ValidationError, match="text_alignment"):
        TaskDisplayItem(item_id="label", modality="text", text="Text", text_alignment="justify")
    with pytest.raises(ValidationError, match="Only text"):
        TaskDisplayItem(item_id="circle", modality="circle", width=5, height=5,
                        text_alignment="left")


def test_task_position_randomization_requires_explicit_exact_choice_grid() -> None:
    payload = {
        "step_id": "choice", "kind": "choice_grid", "random_seed": 1,
        "layout_mode": "exact", "randomize_positions": True,
        "items": [TaskDisplayItem(
            item_id="red", modality=TaskItemModality.CIRCLE, width=5, height=5,
            selectable=True,
        )],
    }
    assert TaskStepSpec.model_validate(payload).randomize_positions
    for update in (
        {"layout_mode": "responsive_grid"}, {"randomize_options": True}, {"kind": "study"},
    ):
        with pytest.raises(ValidationError, match="Position randomization"):
            TaskStepSpec.model_validate({**payload, **update})


@pytest.mark.parametrize("degree_geometry", ["visual_angle", "linear"])
def test_runtime_resolves_native_task_color_geometry_and_prompt_wrap(
    sample_project, sample_project_root, degree_geometry,
) -> None:
    from fpvs_studio.core.display_geometry import visual_angle_width_px
    from fpvs_studio.core.scene_models import SceneEvent, SceneStreamSpec, SceneVisual

    run = _compiled_run(sample_project, sample_project_root)
    if degree_geometry == "linear":
        run = run.model_copy(update={"scene_stream": SceneStreamSpec(
            visuals=[SceneVisual(
                visual_id="base", kind="circle", units="deg", size=(5, 5),
            )],
            events=[SceneEvent(visual_id="base", start_frame=0, duration_frames=1)],
            background_rgb=(0.1234, 0.2345, 0.3456), requested_soa_ms=50, soa_frames=3,
        )})
    step = TaskStepSpec(
        step_id="target-choice", kind=TaskStepKind.CHOICE_GRID,
        layout_mode=TaskLayoutMode.EXACT, text="What target color did you see?",
        degree_geometry=degree_geometry,
        prompt_y=10, prompt_height=2.5, prompt_width=40,
        show_footer=False, require_response=True, random_seed=1,
        items=[
            TaskDisplayItem(
                item_id="color", modality=TaskItemModality.CIRCLE,
                x=-5, y=5, width=5, height=5,
                color_rgb=(0.91, -0.4387, -0.602), line_color_rgb=(1, 1, 1),
                line_width_px=1.5, circle_edges=64, selectable=True, correct=True,
            ),
            TaskDisplayItem(
                item_id="cross", modality=TaskItemModality.TEXT, text="+",
                height=0.025, unit=PresentationUnit.WINDOW_HEIGHT_FRACTION,
                color_rgb=(1, -1, -1),
            ),
        ],
    )
    engine = _TaskEngine([TaskEngineInput(selected_item_ids=("color",))])
    outcome = run_task_modules(
        engine, [_module(step)], project_root=sample_project_root, run_spec=run,
        block_index=0, global_order_index=0,
    )
    resolved = engine.rendered_steps[0]
    assert resolved.background_rgb == (
        (0.1234, 0.2345, 0.3456) if degree_geometry == "linear" else None
    )
    circle, cross = resolved.items
    assert circle.shape == "circle"
    assert circle.color == (0.91, -0.4387, -0.602)
    assert circle.line_color_rgb == (1, 1, 1)
    assert (circle.line_width_px, circle.circle_edges) == (1.5, 64)
    assert cross.color == (1, -1, -1)
    assert cross.text_height_px == pytest.approx(run.display.screen_height_px * 0.025)
    if degree_geometry == "linear":
        pixels_per_degree = (
            0.017455 * run.display.viewing_distance_cm
            * run.display.screen_width_px / run.display.screen_width_cm
        )
        width = 40 * pixels_per_degree
        assert circle.position_px == pytest.approx((-5 * pixels_per_degree,
                                                    5 * pixels_per_degree))
        assert circle.size_px == pytest.approx((5 * pixels_per_degree, 5 * pixels_per_degree))
        assert resolved.prompt_position_px == pytest.approx((0, 10 * pixels_per_degree))
        assert resolved.prompt_height_px == pytest.approx(2.5 * pixels_per_degree)
    else:
        width = visual_angle_width_px(
            degrees=40, viewing_distance_cm=run.display.viewing_distance_cm,
            screen_width_cm=run.display.screen_width_cm,
            screen_width_px=run.display.screen_width_px,
        )
    assert resolved.prompt_width_px == pytest.approx(width)
    assert outcome.responses[0].correct is True


def test_native_task_rendering_uses_source_circle_and_unquantized_rgb(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    class _Stim:
        def __init__(self, *args, **kwargs) -> None:
            calls.append(kwargs)

    class _Visual:
        ShapeStim = _Stim
        TextStim = _Stim

    _prepare_item_stimuli(
        visual=_Visual, window=object(), project_root=tmp_path,
        items=(
            ResolvedTaskItem(
                item_id="circle", shape="circle", size_px=(100, 100),
                color=(0.91, -0.4387, -0.602), line_color_rgb=(1, 1, 1),
            ),
            ResolvedTaskItem(
                item_id="cross", text="+", color=(1, -1, -1), text_height_px=20,
            ),
        ),
        font_family="Open Sans",
    )
    assert calls[0]["vertices"] == "circle"
    assert calls[0]["colorSpace"] == "rgb"
    assert calls[0]["fillColor"] == (0.91, -0.4387, -0.602)
    assert calls[0]["lineColor"] == (1, 1, 1)
    assert calls[0]["lineWidth"] == 1.0
    assert calls[0]["interpolate"] is True
    assert calls[1]["color"] == (1, -1, -1)
    assert calls[1]["font"] == "Open Sans"


def test_native_circle_rejects_corner_click_and_accepts_valid_right_click(tmp_path: Path) -> None:
    class _Window:
        size = (1280, 720)
        mouseVisible = False
        flip_count = 0
        colorSpace = "rgb255"
        color = (0, 0, 0)

        def flip(self) -> None:
            assert self.colorSpace == "rgb"
            assert self.color == (0.0, 0.0, 0.0)
            self.flip_count += 1

    window = _Window()
    hit_tests: list[tuple[float, float]] = []

    class _Shape:
        def __init__(self, *args, **kwargs) -> None:
            assert kwargs["vertices"] == "circle"

        def draw(self) -> None:
            pass

        def contains(self, position, *, units) -> bool:
            assert units == "pix"
            hit_tests.append(position)
            return position[0] ** 2 + position[1] ** 2 <= 50 ** 2

    class _Visual:
        ShapeStim = _Shape

    class _Clock:
        def getTime(self) -> float:
            return window.flip_count * 0.1

    class _Core:
        Clock = _Clock

    class _Keyboard:
        def clearEvents(self) -> None:
            pass

        def getKeys(self, **kwargs) -> list[object]:
            return []

    class _Mouse:
        def getPressed(self):
            return ((0, 0, 0), (1, 0, 0), (0, 0, 0), (0, 0, 1))[window.flip_count]

        def getPos(self):
            return (40.0, 40.0) if window.flip_count == 1 else (0.0, 0.0)

    class _Event:
        @staticmethod
        def Mouse(**kwargs):
            return _Mouse()

    result = render_task_step(
        visual=_Visual, core=_Core, event=_Event, window=window, keyboard=_Keyboard(),
        project_root=tmp_path, is_aborted=lambda: False, set_aborted=lambda: None,
        step=ResolvedTaskStep(
            task_id="masking", step_id="choice", kind="choice_grid",
            response_kind="single_choice", show_footer=False,
            background_rgb=(0.0, 0.0, 0.0),
            items=(ResolvedTaskItem(
                item_id="color", shape="circle", size_px=(100, 100), selectable=True,
            ),),
        ),
    )
    assert hit_tests == [(40.0, 40.0), (0.0, 0.0)]
    assert result.selected_item_ids == ("color",)
    assert result.mouse_button == 2
    assert result.reaction_time_s == pytest.approx(0.3)
    assert window.colorSpace == "rgb255"
    assert window.color == (0, 0, 0)


@pytest.mark.parametrize("duration_seconds", [1.0, 2.0])
@pytest.mark.parametrize("native_scene", [False, True])
@pytest.mark.parametrize("terminal", [False, True])
def test_only_scene_backed_timed_tasks_resolve_frame_duration(
    sample_project, sample_project_root, duration_seconds, native_scene, terminal,
) -> None:
    from fpvs_studio.core.scene_models import SceneEvent, SceneStreamSpec, SceneVisual

    run = _compiled_run(sample_project, sample_project_root)
    if native_scene:
        run = run.model_copy(update={"scene_stream": SceneStreamSpec(
            visuals=[SceneVisual(visual_id="base", kind="circle", size=(5, 5))],
            events=[SceneEvent(visual_id="base", start_frame=0, duration_frames=1)],
            requested_soa_ms=50, soa_frames=3,
        )})
    engine = _TaskEngine([TaskEngineInput()])
    run_task_modules(
        engine, [_module(TaskStepSpec(
            step_id="fixation", kind=TaskStepKind.TIMED_FEEDBACK,
            duration_seconds=duration_seconds, text="+", random_seed=1,
        ))],
        project_root=sample_project_root, run_spec=run, block_index=0, global_order_index=0,
        terminal=terminal,
    )
    resolved = engine.rendered_steps[0]
    assert resolved.duration_s == duration_seconds
    assert resolved.duration_frames == (int(duration_seconds * 60) if native_scene else None)
    assert resolved.clear_after_duration is (native_scene and terminal)


@pytest.mark.parametrize("duration_seconds", [1.0, 2.0])
@pytest.mark.parametrize("frame_duration", [False, True])
@pytest.mark.parametrize("terminal", [False, True])
def test_timed_scene_screen_presents_exact_frames_without_changing_ordinary_tasks(
    tmp_path, monkeypatch, duration_seconds, frame_duration, terminal,
) -> None:
    from types import SimpleNamespace

    draws = []
    monkeypatch.setattr(psychopy_tasks, "_draw_step", lambda **kwargs: draws.append(kwargs))

    class Window:
        flip_count = 0

        def __init__(self):
            self.callbacks = []

        def callOnFlip(self, callback):
            self.callbacks.append(callback)

        def flip(self):
            self.flip_count += 1
            assert self.flip_count < 180, "Timed screen did not finish"
            callbacks, self.callbacks = self.callbacks, []
            for callback in callbacks:
                callback()

    window = Window()

    class Clock:
        onset_frame = 0

        def reset(self):
            self.onset_frame = window.flip_count

        def getTime(self):
            return (window.flip_count - self.onset_frame) / 60

    keyboard = SimpleNamespace(clock=Clock(), clearEvents=lambda: None, getKeys=lambda **_: [])
    frame_count = int(duration_seconds * 60)
    result = render_task_step(
        visual=object(), core=SimpleNamespace(Clock=Clock), event=object(),
        window=window, keyboard=keyboard, project_root=tmp_path,
        is_aborted=lambda: False, set_aborted=lambda: None,
        step=ResolvedTaskStep(
            task_id="masking", step_id="timed", kind="timed_feedback", response_kind="none",
            duration_s=duration_seconds,
            duration_frames=frame_count if frame_duration else None,
            clear_after_duration=frame_duration and terminal,
        ),
    )
    expected_flips = frame_count if frame_duration else frame_count + 1
    assert window.flip_count == expected_flips + int(frame_duration and terminal)
    assert len(draws) == expected_flips
    assert result.reaction_time_s == pytest.approx((expected_flips - 1) / 60)
    assert not result.timed_out
    assert not result.aborted


@pytest.mark.parametrize("native_scene, aborted", [(True, False), (True, True), (False, False)])
def test_timed_scene_records_defer_io_until_flush_but_aborts_persist_immediately(
    sample_project, sample_project_root, tmp_path, native_scene, aborted,
) -> None:
    from fpvs_studio.core.scene_models import SceneEvent, SceneStreamSpec, SceneVisual

    run = _compiled_run(sample_project, sample_project_root)
    if native_scene:
        run = run.model_copy(update={"scene_stream": SceneStreamSpec(
            visuals=[SceneVisual(visual_id="base", kind="circle", size=(5, 5))],
            events=[SceneEvent(visual_id="base", start_frame=0, duration_frames=1)],
            requested_soa_ms=50, soa_frames=3,
        )})
    path = tmp_path / "task_responses.jsonl"
    notified = []
    checkpoint = TaskResponseCheckpoint(path, on_response=notified.append)
    outcome = run_task_modules(
        _TaskEngine([TaskEngineInput(aborted=aborted)]), [_module(_feedback_step())],
        project_root=sample_project_root, run_spec=run, block_index=0, global_order_index=0,
        checkpoint=checkpoint,
    )
    deferred = native_scene and not aborted
    assert path.exists() is not deferred
    assert notified == ([] if deferred else list(outcome.responses))
    checkpoint.flush()
    assert notified == list(outcome.responses)
    assert len(path.read_text().splitlines()) == 1
    checkpoint.flush()
    assert len(path.read_text().splitlines()) == 1


def test_next_input_flushes_deferred_timing_record_first(
    sample_project, sample_project_root, tmp_path,
) -> None:
    from fpvs_studio.core.scene_models import SceneEvent, SceneStreamSpec, SceneVisual

    run = _compiled_run(sample_project, sample_project_root).model_copy(update={
        "scene_stream": SceneStreamSpec(
            visuals=[SceneVisual(visual_id="base", kind="circle", size=(5, 5))],
            events=[SceneEvent(visual_id="base", start_frame=0, duration_frames=1)],
            requested_soa_ms=50, soa_frames=3,
        ),
    })
    path = tmp_path / "responses.jsonl"
    notified = []
    checkpoint = TaskResponseCheckpoint(path, on_response=notified.append)
    run_task_modules(
        _TaskEngine([TaskEngineInput()]), [_module(_feedback_step())],
        project_root=sample_project_root, run_spec=run, block_index=0, global_order_index=0,
        checkpoint=checkpoint,
    )
    assert not path.exists()
    run_task_modules(
        _TaskEngine([TaskEngineInput(selected_item_ids=("apple",))]), [_module(_choice_step())],
        project_root=sample_project_root, run_spec=run, block_index=0, global_order_index=0,
        checkpoint=checkpoint,
    )
    assert [record.step_id for record in notified] == ["correct-feedback", "recognition-grid"]
    assert [json.loads(line)["step_id"] for line in path.read_text().splitlines()] == [
        "correct-feedback", "recognition-grid",
    ]


def _choice_step(*, retry: bool = False) -> TaskStepSpec:
    items = [
        TaskDisplayItem(
            item_id=item_id,
            modality=TaskItemModality.TEXT,
            text=label,
            x=x,
            y=0,
            width=4,
            height=2,
            unit=PresentationUnit.DEGREES,
            selectable=selectable,
            correct=True if selectable else None,
        )
        for item_id, label, x, selectable in (
            ("apple", "Apple", -6, True),
            ("calculator", "Calculator", -2, True),
            ("foil-a", "Bowl", 2, False),
            ("foil-b", "Notebook", 6, False),
        )
    ]
    return TaskStepSpec(
        step_id="recognition-grid",
        kind=TaskStepKind.CHOICE_GRID,
        heading="Select all four",
        prompt_y=6,
        prompt_height=1,
        layout_mode=TaskLayoutMode.EXACT,
        items=items,
        require_response=True,
        max_attempts=2 if retry else 1,
        retry_on_invalid=retry,
        random_seed=1,
        realized_item_order=[item.item_id for item in items],
    )


def _feedback_step() -> TaskStepSpec:
    return TaskStepSpec(
        step_id="correct-feedback",
        kind=TaskStepKind.TIMED_FEEDBACK,
        text="correct",
        duration_seconds=1.0,
        random_seed=2,
    )


def _module(*steps: TaskStepSpec, repeat_count: int = 1) -> TaskModuleSpec:
    return TaskModuleSpec(
        task_id="recognition",
        name="Recognition",
        phase=TaskPhase.PRE_CONDITION,
        occurrence=TaskOccurrence.EVERY_ENTRY,
        random_seed=9,
        repeat_count=repeat_count,
        steps=list(steps),
    )


def test_module_repeat_interleaves_choice_and_timed_feedback(
    sample_project,
    sample_project_root,
) -> None:
    queued: list[TaskEngineInput] = []
    for _ in range(4):
        queued.extend(
            [
                TaskEngineInput(
                    selected_item_ids=("apple",),
                    mouse_position_px=(-100.0, 20.0),
                    mouse_button=0,
                    reaction_time_s=0.3,
                    displayed_item_ids=("apple", "calculator", "foil-a", "foil-b"),
                ),
                TaskEngineInput(reaction_time_s=1.0),
            ]
        )
    engine = _TaskEngine(queued)

    outcome = run_task_modules(
        engine,
        [_module(_choice_step(), _feedback_step(), repeat_count=4)],
        project_root=sample_project_root,
        run_spec=_compiled_run(sample_project, sample_project_root),
        block_index=0,
        global_order_index=0,
    )

    assert outcome.aborted is False
    assert [step.kind for step in engine.rendered_steps] == [
        "choice_grid",
        "timed_feedback",
    ] * 4
    assert [record.repetition_index for record in outcome.responses] == [
        0,
        0,
        1,
        1,
        2,
        2,
        3,
        3,
    ]
    choice_records = [record for record in outcome.responses if record.selected_option_ids]
    assert all(record.selected_option_ids == ["apple"] for record in choice_records)
    assert all(record.mouse_button == 0 for record in choice_records)
    assert all(record.correct is True for record in choice_records)


def test_invalid_external_engine_selection_retries_then_records_valid_response(
    sample_project,
    sample_project_root,
) -> None:
    engine = _TaskEngine(
        [
            TaskEngineInput(selected_item_ids=("foil-a",)),
            TaskEngineInput(selected_item_ids=("calculator",)),
        ]
    )

    outcome = run_task_modules(
        engine,
        [_module(_choice_step(retry=True))],
        project_root=sample_project_root,
        run_spec=_compiled_run(sample_project, sample_project_root),
        block_index=0,
        global_order_index=0,
    )

    assert outcome.aborted is False
    assert [record.valid for record in outcome.responses] == [False, True]
    assert [record.attempt_index for record in outcome.responses] == [0, 1]


def test_required_invalid_response_aborts_and_checkpoint_preserves_partial_record(
    sample_project,
    sample_project_root,
    tmp_path: Path,
) -> None:
    checkpoint_path = tmp_path / "runs" / "P001" / "task_responses.jsonl"
    engine = _TaskEngine([TaskEngineInput(selected_item_ids=("foil-a",))])

    outcome = run_task_modules(
        engine,
        [_module(_choice_step())],
        project_root=sample_project_root,
        run_spec=_compiled_run(sample_project, sample_project_root),
        block_index=0,
        global_order_index=0,
        checkpoint=TaskResponseCheckpoint(checkpoint_path),
    )

    assert outcome.aborted is True
    assert "Required task response" in (outcome.abort_reason or "")
    payloads = [json.loads(line) for line in checkpoint_path.read_text().splitlines()]
    assert payloads[0]["selected_option_ids"] == ["foil-a"]
    assert payloads[0]["valid"] is False


def test_questionnaire_uses_authored_text_limit_and_rating_endpoint_labels(
    sample_project,
    sample_project_root,
) -> None:
    questions = [
        TaskQuestion(
            question_id="recall",
            kind=TaskQuestionKind.SHORT_TEXT,
            prompt="What did you remember?",
            max_text_length=37,
        ),
        TaskQuestion(
            question_id="confidence",
            kind=TaskQuestionKind.RATING,
            prompt="How confident are you?",
            min_value=1,
            max_value=5,
            step=1,
            min_label="Not confident",
            max_label="Very confident",
        ),
    ]
    step = TaskStepSpec(
        step_id="questionnaire",
        kind=TaskStepKind.QUESTIONNAIRE,
        font_family=TaskFontFamily.OPEN_SANS,
        questions=questions,
        random_seed=4,
        realized_question_option_orders={},
    )
    engine = _TaskEngine(
        [
            TaskEngineInput(text_value="Apple", reaction_time_s=1.2),
            TaskEngineInput(
                selected_item_ids=("rating-4",),
                reaction_time_s=0.4,
            ),
        ]
    )

    outcome = run_task_modules(
        engine,
        [_module(step)],
        project_root=sample_project_root,
        run_spec=_compiled_run(sample_project, sample_project_root),
        block_index=0,
        global_order_index=0,
    )

    assert outcome.aborted is False
    assert all(
        rendered.font_family == TaskFontFamily.OPEN_SANS.value
        for rendered in engine.rendered_steps
    )
    assert engine.rendered_steps[0].maximum_text_length == 37
    assert {item.text for item in engine.rendered_steps[1].items} >= {
        "Not confident",
        "Very confident",
    }
    assert outcome.responses[1].numeric_value == 4


def test_exact_prompt_and_item_geometry_resolve_from_degrees(
    sample_project,
    sample_project_root,
) -> None:
    engine = _TaskEngine([TaskEngineInput(selected_item_ids=("apple",))])

    step = _choice_step().model_copy(
        update={"font_family": TaskFontFamily.OPEN_SANS}
    )
    run_task_modules(
        engine,
        [_module(step)],
        project_root=sample_project_root,
        run_spec=_compiled_run(sample_project, sample_project_root),
        block_index=0,
        global_order_index=0,
    )

    rendered = engine.rendered_steps[0]
    assert rendered.font_family == TaskFontFamily.OPEN_SANS.value
    assert rendered.prompt_position_px is not None
    assert rendered.prompt_position_px[0] == 0
    assert rendered.prompt_position_px[1] > 0
    apple = rendered.items[0]
    assert apple.position_px[0] < 0
    assert apple.size_px is not None
    assert apple.size_px[0] > apple.size_px[1]


def test_timed_feedback_accepts_escape_only() -> None:
    step = ResolvedTaskStep(
        task_id="recognition",
        step_id="feedback",
        kind="timed_feedback",
        duration_s=1.0,
    )

    assert _key_list_for_step(step) == ["escape"]


def test_psychopy_task_text_uses_one_font_and_rejects_escaping_image_path(
    tmp_path: Path,
) -> None:
    text_calls: list[dict[str, object]] = []

    class _Stim:
        def __init__(self, *args, **kwargs) -> None:
            text_calls.append(kwargs)

        def draw(self) -> None:
            return None

    class _Visual:
        TextStim = _Stim
        ImageStim = _Stim

    class _Window:
        size = (1280, 720)

    text_item = ResolvedTaskItem(item_id="label", text="Apple")
    prepared = _prepare_item_stimuli(
        visual=_Visual,
        window=_Window(),
        project_root=tmp_path,
        items=(text_item,),
    )
    _draw_step(
        visual=_Visual,
        window=_Window(),
        step=ResolvedTaskStep(
            task_id="task",
            step_id="step",
            kind="instruction",
            response_kind="continue",
            heading="Heading",
            body="Body",
            items=(text_item,),
        ),
        item_stimuli=prepared,
        selected_item_ids=[],
        response_text="",
        validation_message=None,
    )

    assert text_calls
    assert all(call.get("font") == "Arial" for call in text_calls)
    with pytest.raises(ValueError, match="escape"):
        _prepare_item_stimuli(
            visual=_Visual,
            window=_Window(),
            project_root=tmp_path,
            items=(
                ResolvedTaskItem(
                    item_id="unsafe",
                    image_path="../outside.png",
                ),
            ),
        )


def test_psychopy_task_text_uses_bundled_open_sans(tmp_path: Path) -> None:
    text_calls: list[dict[str, object]] = []

    class _Stim:
        def __init__(self, *args, **kwargs) -> None:
            text_calls.append(kwargs)

        def draw(self) -> None:
            return None

    class _Visual:
        TextStim = _Stim
        ImageStim = _Stim

    class _Window:
        size = (1280, 720)

    text_item = ResolvedTaskItem(item_id="label", text="Pen")
    prepared = _prepare_item_stimuli(
        visual=_Visual,
        window=_Window(),
        project_root=tmp_path,
        items=(text_item,),
        font_family=TaskFontFamily.OPEN_SANS.value,
    )
    _draw_step(
        visual=_Visual,
        window=_Window(),
        step=ResolvedTaskStep(
            task_id="word-recognition",
            step_id="study",
            kind="study",
            font_family=TaskFontFamily.OPEN_SANS.value,
            response_kind="continue",
            heading="Remember",
            body="Study these words",
            items=(text_item,),
        ),
        item_stimuli=prepared,
        selected_item_ids=[],
        response_text="",
        validation_message=None,
    )

    assert text_calls
    assert all(call.get("font") == TaskFontFamily.OPEN_SANS.value for call in text_calls)
    font_path = bundled_task_font_path(TaskFontFamily.OPEN_SANS.value)
    assert font_path is not None and font_path.is_file()
    assert ImageFont.truetype(str(font_path), size=12).getname()[0] == "Open Sans"
    license_path = font_path.with_name("OpenSans-OFL.txt")
    assert "SIL OPEN FONT LICENSE Version 1.1" in license_path.read_text(encoding="utf-8")


def test_bundled_open_sans_registers_once_with_both_psychopy_renderers(
    monkeypatch,
) -> None:
    registrations: list[tuple[str, str]] = []
    font_path = bundled_task_font_path(TaskFontFamily.OPEN_SANS.value)
    assert font_path is not None

    class _FontInfo:
        path = str(font_path)

    class _PygletFont:
        @staticmethod
        def add_file(path: str) -> None:
            registrations.append(("pyglet", path))

        @staticmethod
        def have_font(font_family: str) -> bool:
            return font_family == TaskFontFamily.OPEN_SANS.value

    class _AllFonts:
        @staticmethod
        def addFontFile(path: str) -> set[_FontInfo]:
            registrations.append(("textbox2", path))
            return {_FontInfo()}

        @staticmethod
        def getFontsMatching(font_family: str, *, fallback: bool) -> list[_FontInfo]:
            assert fallback is False
            return [_FontInfo()] if font_family == TaskFontFamily.OPEN_SANS.value else []

    class _TextBoxModule:
        allFonts = _AllFonts()

    modules = {
        "pyglet.font": _PygletFont(),
        "psychopy.visual.textbox2": _TextBoxModule(),
    }
    monkeypatch.setattr(psychopy_tasks, "import_module", modules.__getitem__)
    monkeypatch.setattr(psychopy_tasks, "_REGISTERED_BUNDLED_TASK_FONTS", set())

    _register_bundled_task_font(TaskFontFamily.ARIAL.value)
    _register_bundled_task_font(TaskFontFamily.OPEN_SANS.value)
    _register_bundled_task_font(TaskFontFamily.OPEN_SANS.value)

    assert registrations == [
        ("pyglet", str(font_path)),
        ("textbox2", str(font_path)),
    ]
    assert psychopy_tasks._REGISTERED_BUNDLED_TASK_FONTS == {
        TaskFontFamily.OPEN_SANS.value
    }


def test_bundled_open_sans_registration_rejects_renderer_fallback(monkeypatch) -> None:
    class _PygletFont:
        @staticmethod
        def add_file(_path: str) -> None:
            return None

        @staticmethod
        def have_font(_font_family: str) -> bool:
            return True

    class _AllFonts:
        @staticmethod
        def addFontFile(_path: str) -> None:
            return None

        @staticmethod
        def getFontsMatching(_font_family: str, *, fallback: bool) -> None:
            assert fallback is False
            return None

    class _TextBoxModule:
        allFonts = _AllFonts()

    modules = {
        "pyglet.font": _PygletFont(),
        "psychopy.visual.textbox2": _TextBoxModule(),
    }
    monkeypatch.setattr(psychopy_tasks, "import_module", modules.__getitem__)
    monkeypatch.setattr(psychopy_tasks, "_REGISTERED_BUNDLED_TASK_FONTS", set())

    with pytest.raises(RuntimeError, match="could not be registered with PsychoPy"):
        _register_bundled_task_font(TaskFontFamily.OPEN_SANS.value)

    assert not psychopy_tasks._REGISTERED_BUNDLED_TASK_FONTS


def test_psychopy_text_box_uses_resolved_open_sans() -> None:
    text_box_calls: list[dict[str, object]] = []

    class _TextBox:
        def __init__(self, *args, **kwargs) -> None:
            text_box_calls.append(kwargs)
            self.text = ""
            self.hasFocus = False

    class _Visual:
        TextBox2 = _TextBox

    class _Window:
        size = (1280, 720)

    text_box, submitted = _prepare_text_box(
        visual=_Visual,
        window=_Window(),
        step=ResolvedTaskStep(
            task_id="word-recognition",
            step_id="recall-prompt",
            kind="questionnaire",
            response_kind="long_text",
            font_family=TaskFontFamily.OPEN_SANS.value,
        ),
    )

    assert text_box is not None
    assert submitted == [False]
    assert text_box_calls[0]["font"] == TaskFontFamily.OPEN_SANS.value
    assert text_box.hasFocus is True


def test_questionnaire_choice_unknown_or_nonselectable_ids_are_invalid(
    sample_project,
    sample_project_root,
) -> None:
    question = TaskQuestion(
        question_id="favorite",
        kind=TaskQuestionKind.SINGLE_CHOICE,
        prompt="Choose one",
        options=[
            TaskOption(option_id="valid", label="Valid"),
            TaskOption(option_id="display-only", label="Display only", selectable=False),
        ],
    )
    step = TaskStepSpec(
        step_id="questions",
        kind=TaskStepKind.QUESTIONNAIRE,
        questions=[question],
        random_seed=1,
        realized_question_option_orders={
            "favorite": ["valid", "display-only"],
        },
    )
    engine = _TaskEngine([TaskEngineInput(selected_item_ids=("display-only",))])

    outcome = run_task_modules(
        engine,
        [_module(step)],
        project_root=sample_project_root,
        run_spec=_compiled_run(sample_project, sample_project_root),
        block_index=0,
        global_order_index=0,
    )

    assert outcome.aborted is True
    assert outcome.responses[0].valid is False


def _session_with_pre_task(session_plan, module: TaskModuleSpec):
    block = session_plan.blocks[0]
    entry = block.entries[0].model_copy(update={"pre_tasks": [module]})
    updated_block = block.model_copy(update={"entries": [entry, *block.entries[1:]]})
    return session_plan.model_copy(
        update={"blocks": [updated_block, *session_plan.blocks[1:]]}
    )


def _session_with_tasks(
    session_plan,
    *,
    pre: TaskModuleSpec | None = None,
    post: TaskModuleSpec | None = None,
):
    block = session_plan.blocks[0]
    entry = block.entries[0].model_copy(
        update={
            "pre_tasks": [] if pre is None else [pre],
            "post_tasks": [] if post is None else [post],
        }
    )
    updated_block = block.model_copy(update={"entries": [entry]})
    return session_plan.model_copy(
        update={"blocks": [updated_block], "block_count": 1, "total_runs": 1}
    )


def test_preflight_rejects_missing_task_asset(
    sample_project,
    sample_project_root,
) -> None:
    plan = compile_session_plan(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=12,
    )
    image_step = TaskStepSpec(
        step_id="study",
        kind=TaskStepKind.STUDY,
        continue_key="space",
        layout_mode=TaskLayoutMode.EXACT,
        items=[
            TaskDisplayItem(
                item_id="missing",
                modality=TaskItemModality.IMAGE,
                image_path="stimuli/task-assets/memory/missing.png",
                width=5,
                height=4,
            )
        ],
        random_seed=1,
        realized_item_order=["missing"],
    )
    plan = _session_with_pre_task(plan, _module(image_step))

    with pytest.raises(PreflightError, match="task assets are missing"):
        preflight_session_plan(
            sample_project_root,
            plan,
            engine=_TaskEngine([]),
            runtime_options={"verify_refresh_rate": False},
        )


def test_preflight_rejects_engine_without_modular_task_capability(
    sample_project,
    sample_project_root,
) -> None:
    plan = compile_session_plan(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=12,
    )
    instruction = TaskStepSpec(
        step_id="intro",
        kind=TaskStepKind.INSTRUCTION,
        continue_key="space",
        text="Remember the items.",
        random_seed=1,
    )
    plan = _session_with_pre_task(plan, _module(instruction))

    with pytest.raises(PreflightError, match="does not support modular condition tasks"):
        preflight_session_plan(
            sample_project_root,
            plan,
            engine=_PreflightEngine(),
            runtime_options={"verify_refresh_rate": False},
        )


def test_duplicate_selection_policy_is_enforced_across_step_repetitions(
    sample_project,
    sample_project_root,
) -> None:
    step = _choice_step().model_copy(
        update={
            "repeat_count": 2,
            "allow_duplicate_selections_across_repeats": False,
        }
    )
    engine = _TaskEngine(
        [
            TaskEngineInput(selected_item_ids=("apple",)),
            TaskEngineInput(selected_item_ids=("apple",)),
        ]
    )

    outcome = run_task_modules(
        engine,
        [_module(step)],
        project_root=sample_project_root,
        run_spec=_compiled_run(sample_project, sample_project_root),
        block_index=0,
        global_order_index=0,
    )

    assert outcome.aborted is True
    assert [record.step_repetition_index for record in outcome.responses] == [0, 1]
    assert [record.valid for record in outcome.responses] == [True, False]
    second_apple = next(item for item in engine.rendered_steps[1].items if item.item_id == "apple")
    assert second_apple.selectable is False


def test_malformed_no_duplicate_repeat_capacity_fails_before_rendering(
    sample_project,
    sample_project_root,
) -> None:
    step = _choice_step().model_copy(
        update={"allow_duplicate_selections_across_repeats": False}
    )
    valid_module = _module(step, repeat_count=2)
    exhausted_module = valid_module.model_copy(update={"repeat_count": 3})
    plan = compile_session_plan(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=12,
    )
    plan = _session_with_pre_task(plan, exhausted_module)
    engine = _TaskEngine([])

    with pytest.raises(PreflightError, match="task repeat capacity is invalid"):
        preflight_session_plan(
            sample_project_root,
            plan,
            engine=engine,
            runtime_options={"verify_refresh_rate": False},
        )

    with pytest.raises(ValueError, match="only 2 available options"):
        run_task_modules(
            engine,
            [exhausted_module],
            project_root=sample_project_root,
            run_spec=_compiled_run(sample_project, sample_project_root),
            block_index=0,
            global_order_index=0,
        )
    assert engine.rendered_steps == []


def test_psychopy_choice_returns_stable_id_mouse_details_and_rt(tmp_path: Path) -> None:
    class _Stim:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def draw(self) -> None:
            return None

    class _Window:
        size = (1280, 720)
        mouseVisible = False

        def __init__(self) -> None:
            self.flip_count = 0

        def flip(self) -> None:
            self.flip_count += 1

    window = _Window()

    class _Clock:
        def getTime(self) -> float:
            return window.flip_count * 0.1

    class _Core:
        Clock = _Clock

    class _Keyboard:
        def clearEvents(self) -> None:
            return None

        def getKeys(self, **kwargs) -> list[object]:
            return []

    class _Mouse:
        def __init__(self) -> None:
            self.calls = 0

        def getPressed(self) -> tuple[int, int, int]:
            self.calls += 1
            return (0, 0, 0) if self.calls == 1 else (1, 0, 0)

        def getPos(self) -> tuple[float, float]:
            return (-50.0, 12.0)

    mouse = _Mouse()

    class _Event:
        @staticmethod
        def Mouse(*, win) -> _Mouse:
            assert win is window
            return mouse

    class _Visual:
        TextStim = _Stim
        ImageStim = _Stim

    result = render_task_step(
        visual=_Visual,
        core=_Core,
        event=_Event,
        window=window,
        keyboard=_Keyboard(),
        project_root=tmp_path,
        step=ResolvedTaskStep(
            task_id="memory",
            step_id="grid",
            kind="choice_grid",
            response_kind="single_choice",
            items=(
                ResolvedTaskItem(
                    item_id="apple",
                    text="Apple",
                    position_px=(-50.0, 12.0),
                    size_px=(100.0, 80.0),
                    selectable=True,
                ),
            ),
        ),
        is_aborted=lambda: False,
        set_aborted=lambda: None,
    )

    assert result.selected_item_ids == ("apple",)
    assert result.mouse_position_px == (-50.0, 12.0)
    assert result.mouse_button == 0
    assert result.reaction_time_s == pytest.approx(0.1)
    assert window.mouseVisible is False


def test_responsive_grid_uses_authored_columns_without_overlap(
    sample_project,
    sample_project_root,
) -> None:
    step = TaskStepSpec(
        step_id="responsive-study",
        kind=TaskStepKind.STUDY,
        continue_key="space",
        columns=2,
        items=[
            TaskDisplayItem(
                item_id=f"item-{index}",
                modality=TaskItemModality.TEXT,
                text=f"Item {index}",
            )
            for index in range(4)
        ],
        random_seed=1,
        realized_item_order=[f"item-{index}" for index in range(4)],
    )
    engine = _TaskEngine([TaskEngineInput(key="space")])

    outcome = run_task_modules(
        engine,
        [_module(step)],
        project_root=sample_project_root,
        run_spec=_compiled_run(sample_project, sample_project_root),
        block_index=0,
        global_order_index=0,
    )

    assert outcome.aborted is False
    positions = [item.position_px for item in engine.rendered_steps[0].items]
    assert len(set(positions)) == 4
    assert positions[0][0] == positions[2][0]
    assert positions[0][1] != positions[2][1]


def test_explicit_single_choice_and_rating_submit_selected_item() -> None:
    for response_kind in ("single_choice", "rating"):
        step = ResolvedTaskStep(
            task_id="questions",
            step_id="question",
            kind="questionnaire",
            response_kind=response_kind,
            submission_mode="explicit",
        )
        result = _completed_input(
            step,
            key="return",
            selected_item_ids=["answer"],
            response_text="",
            reaction_time_s=0.5,
            displayed_item_ids=("answer",),
        )

        assert result is not None
        assert result.selected_item_ids == ("answer",)


def test_numeric_off_step_value_is_invalid(
    sample_project,
    sample_project_root,
) -> None:
    questions = [
        TaskQuestion(
            question_id="amount",
            kind=TaskQuestionKind.NUMERIC,
            prompt="Amount",
            min_value=0,
            max_value=10,
            step=2,
        )
    ]
    step = TaskStepSpec(
        step_id="questions",
        kind=TaskStepKind.QUESTIONNAIRE,
        questions=questions,
        random_seed=1,
    )
    engine = _TaskEngine(
        [
            TaskEngineInput(numeric_value=3),
        ]
    )

    outcome = run_task_modules(
        engine,
        [_module(step)],
        project_root=sample_project_root,
        run_spec=_compiled_run(sample_project, sample_project_root),
        block_index=0,
        global_order_index=0,
    )

    assert outcome.aborted is True
    assert [record.valid for record in outcome.responses] == [False]


def test_external_text_over_authored_limit_is_invalid(
    sample_project,
    sample_project_root,
) -> None:
    question = TaskQuestion(
        question_id="note",
        kind=TaskQuestionKind.SHORT_TEXT,
        prompt="Note",
        max_text_length=3,
    )
    step = TaskStepSpec(
        step_id="questions",
        kind=TaskStepKind.QUESTIONNAIRE,
        questions=[question],
        random_seed=1,
    )
    outcome = run_task_modules(
        _TaskEngine([TaskEngineInput(text_value="too long")]),
        [_module(step)],
        project_root=sample_project_root,
        run_spec=_compiled_run(sample_project, sample_project_root),
        block_index=0,
        global_order_index=0,
    )

    assert outcome.aborted is True
    assert outcome.responses[0].valid is False


def test_external_rating_selection_id_must_be_a_known_tick(
    sample_project,
    sample_project_root,
) -> None:
    question = TaskQuestion(
        question_id="rating",
        kind=TaskQuestionKind.RATING,
        prompt="Rate it",
        min_value=1,
        max_value=5,
        step=1,
    )
    step = TaskStepSpec(
        step_id="questions",
        kind=TaskStepKind.QUESTIONNAIRE,
        questions=[question],
        random_seed=1,
    )
    outcome = run_task_modules(
        _TaskEngine(
            [
                TaskEngineInput(
                    selected_item_ids=("not-a-rating",),
                    numeric_value=3,
                )
            ]
        ),
        [_module(step)],
        project_root=sample_project_root,
        run_spec=_compiled_run(sample_project, sample_project_root),
        block_index=0,
        global_order_index=0,
    )

    assert outcome.aborted is True
    assert outcome.responses[0].valid is False


def test_choice_grid_records_last_allowed_key_without_ending_mouse_screen(
    tmp_path: Path,
) -> None:
    class _Stim:
        def __init__(self, *args, **kwargs) -> None:
            return None

        def draw(self) -> None:
            return None

    class _Window:
        size = (1280, 720)
        mouseVisible = False

        def __init__(self) -> None:
            self.flip_count = 0
            self._on_flip: list[tuple[object, tuple[object, ...]]] = []

        def callOnFlip(self, callback, *args) -> None:
            self._on_flip.append((callback, args))

        def flip(self) -> None:
            self.flip_count += 1
            queued, self._on_flip = self._on_flip, []
            for callback, args in queued:
                callback(*args)

    window = _Window()

    class _Clock:
        def __init__(self) -> None:
            self.start_flip = 0

        def reset(self) -> None:
            self.start_flip = window.flip_count

        def getTime(self) -> float:
            return (window.flip_count - self.start_flip) * 0.1

    class _Core:
        Clock = _Clock

    class _Key:
        name = "y"
        rt = 0.04
        duration = 0.02

    class _Keyboard:
        def clearEvents(self) -> None:
            return None

        def getKeys(self, **kwargs) -> list[object]:
            return [_Key()] if window.flip_count == 1 else []

    class _Mouse:
        def __init__(self) -> None:
            self.calls = 0

        def getPressed(self) -> tuple[int, int, int]:
            self.calls += 1
            return (0, 0, 0) if self.calls < 3 else (1, 0, 0)

        def getPos(self) -> tuple[float, float]:
            return (0.0, 0.0)

    mouse = _Mouse()

    class _Event:
        @staticmethod
        def Mouse(*, win) -> _Mouse:
            assert win is window
            return mouse

    class _Visual:
        TextStim = _Stim
        ImageStim = _Stim

    result = render_task_step(
        visual=_Visual,
        core=_Core,
        event=_Event,
        window=window,
        keyboard=_Keyboard(),
        project_root=tmp_path,
        step=ResolvedTaskStep(
            task_id="memory",
            step_id="grid",
            kind="choice_grid",
            response_kind="single_choice",
            allowed_keys=("y", "n", "left", "right", "space"),
            items=(
                ResolvedTaskItem(
                    item_id="target",
                    text="Target",
                    size_px=(100.0, 80.0),
                    selectable=True,
                ),
            ),
        ),
        is_aborted=lambda: False,
        set_aborted=lambda: None,
    )

    assert result.selected_item_ids == ("target",)
    assert result.key == "y"
    assert result.reaction_time_s == pytest.approx(0.1)
    assert result.key_reaction_time_s == pytest.approx(0.04)
    assert result.key_duration_s == pytest.approx(0.02)


def test_branch_contains_and_multi_value_equality_have_stable_semantics() -> None:
    assert _branch_matches(
        TaskBranchOperator.CONTAINS,
        "participant remembers apple and purse",
        ["apple"],
        None,
    )
    assert _branch_matches(
        TaskBranchOperator.CONTAINS,
        ["apple", "purse"],
        ["purse"],
        None,
    )
    assert _branch_matches(
        TaskBranchOperator.EQUALS,
        ["purse", "apple"],
        ["apple", "purse"],
        None,
    )


def test_optional_numeric_can_submit_blank() -> None:
    result = _completed_input(
        ResolvedTaskStep(
            task_id="questionnaire",
            step_id="numeric",
            kind="questionnaire",
            response_kind="numeric",
            required=False,
            numeric_minimum=0,
            numeric_maximum=10,
        ),
        key="return",
        selected_item_ids=[],
        response_text="",
        reaction_time_s=0.5,
        displayed_item_ids=(),
    )

    assert result is not None
    assert result.numeric_value is None


def test_continue_key_preserves_step_relative_rt_and_duration() -> None:
    class _Key:
        name = "space"
        rt = 0.25
        duration = 0.08

    class _Keyboard:
        def getKeys(self, **kwargs) -> list[object]:
            return [_Key()]

    result = _handle_keys(
        keyboard=_Keyboard(),
        step=ResolvedTaskStep(
            task_id="task",
            step_id="intro",
            kind="instruction",
            response_kind="continue",
        ),
        response_text="",
        selected_item_ids=[],
    )

    assert result["submitted_key"] == "space"
    assert result["key_rt"] == pytest.approx(0.25)
    assert result["key_duration"] == pytest.approx(0.08)


def test_exact_step_can_suppress_generic_footer() -> None:
    text_calls: list[dict[str, object]] = []

    class _Stim:
        def __init__(self, *args, **kwargs) -> None:
            text_calls.append(kwargs)

        def draw(self) -> None:
            return None

    class _Visual:
        TextStim = _Stim

    class _Window:
        size = (1280, 720)

    _draw_step(
        visual=_Visual,
        window=_Window(),
        step=ResolvedTaskStep(
            task_id="creatine",
            step_id="intro",
            kind="instruction",
            response_kind="continue",
            body="Study these items.",
            prompt_position_px=(0, 0),
            prompt_width_px=600.25,
            show_footer=False,
        ),
        item_stimuli={},
        selected_item_ids=[],
        response_text="",
        validation_message=None,
    )

    assert [call["text"] for call in text_calls] == ["Study these items."]
    assert text_calls[0]["wrapWidth"] == 600.25


def test_compact_session_persists_task_answers_under_logs_without_runs_folder(
    sample_project,
    sample_project_root,
    tmp_path: Path,
) -> None:
    plan = compile_session_plan(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=30,
    )
    question = TaskQuestion(
        question_id="note",
        kind=TaskQuestionKind.SHORT_TEXT,
        prompt="Note",
    )
    post = _module(
        TaskStepSpec(
            step_id="questions",
            kind=TaskStepKind.QUESTIONNAIRE,
            questions=[question],
            random_seed=1,
        )
    ).model_copy(update={"phase": TaskPhase.POST_CONDITION})
    plan = _session_with_tasks(plan, post=post)
    project_root = tmp_path / "project"
    project_root.mkdir()
    output_dir = project_root / "runs" / "P009"
    engine = _TaskEngine([TaskEngineInput(text_value="=private answer")])

    summary = RuntimeWorker(engine).execute_session(
        project_root,
        plan,
        output_dir,
        participant_number="009",
        runtime_options={
            "export_mode": "compact", "serial_enabled": False,
            "experiment_test_mode": True,
        },
    )

    assert summary.aborted is False
    assert summary.run_results[0].task_responses[0].text_value == "=private answer"
    assert not (project_root / "runs").exists()
    response_path = project_root / "logs" / "task_responses.csv"
    with response_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["participant_number"] == "009"
    assert rows[0]["session_id"] == plan.session_id
    assert rows[0]["text_value"] == "'=private answer"
    assert not (project_root / "logs" / ".task-response-checkpoints").exists()


def test_repeated_compact_plan_keeps_numbered_answers_and_legacy_checkpoint(
    sample_project, sample_project_root, tmp_path: Path,
) -> None:
    from fpvs_studio.runtime.session_export import compact_task_checkpoint_path

    plan = compile_session_plan(
        sample_project, refresh_hz=60.0, project_root=sample_project_root, random_seed=30,
    )
    post = _module(TaskStepSpec(
        step_id="questions", kind=TaskStepKind.QUESTIONNAIRE,
        questions=[TaskQuestion(
            question_id="note", kind=TaskQuestionKind.SHORT_TEXT, prompt="Note",
        )], random_seed=1,
    )).model_copy(update={"phase": TaskPhase.POST_CONDITION})
    plan = _session_with_tasks(plan, post=post)
    root = tmp_path / "project"
    legacy = compact_task_checkpoint_path(
        root, participant_number="009", session_id=plan.session_id,
    )
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"preserved legacy partial answers")
    for number in (1, 2):
        worker = RuntimeWorker(_TaskEngine([TaskEngineInput(text_value=f"answer {number}")]))
        worker.execute_session(
            root, plan, root / "runs" / "unused",
            participant_number="009", participant_session_number=number,
            runtime_options={
                "export_mode": "compact", "serial_enabled": False,
                "experiment_test_mode": True,
            },
        )
    with (root / "logs" / "task_responses.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [(row["participant_session_number"], row["text_value"]) for row in rows] == [
        ("1", "answer 1"), ("2", "answer 2"),
    ]
    assert legacy.read_bytes() == b"preserved legacy partial answers"
    assert not (root / "runs").exists()


def test_session_task_order_and_full_exports_preserve_raw_checkpoint(
    sample_project,
    sample_project_root,
    tmp_path: Path,
) -> None:
    plan = compile_session_plan(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=31,
    )
    pre = _module(
        TaskStepSpec(
            step_id="intro",
            kind=TaskStepKind.INSTRUCTION,
            continue_key="space",
            text="Study the items.",
            random_seed=1,
        )
    )
    post = _module(
        TaskStepSpec(
            step_id="advance",
            kind=TaskStepKind.RAW_KEY,
            allowed_keys=["y", "n", "left", "right", "space"],
            random_seed=2,
        )
    ).model_copy(update={"phase": TaskPhase.POST_CONDITION})
    plan = _session_with_tasks(plan, pre=pre, post=post)
    event_log: list[str] = []

    class _FlowEngine(_TaskEngine):
        def render_task_step(self, step, project_root):
            event_log.append(f"task:{step.step_id}")
            return super().render_task_step(step, project_root)

        def show_transition_screen(self, **kwargs) -> bool:
            event_log.append("transition")
            return super().show_transition_screen(**kwargs)

        def run_condition(self, run_spec, project_root, **kwargs):
            event_log.append("stream")
            return super().run_condition(run_spec, project_root, **kwargs)

    project_root = tmp_path / "project"
    project_root.mkdir()
    output_dir = project_root / "runs" / "P010"
    engine = _FlowEngine(
        [TaskEngineInput(key="space"), TaskEngineInput(key="left")],
        {"flow": True},
    )

    summary = RuntimeWorker(engine).execute_session(
        project_root,
        plan,
        output_dir,
        participant_number="010",
        runtime_options={
            "export_mode": "full", "serial_enabled": False,
            "experiment_test_mode": True,
        },
        relative_output_dir="runs/P010",
    )

    assert event_log[:4] == ["task:intro", "transition", "stream", "task:advance"]
    assert summary.aborted is False
    assert [response.key for response in summary.run_results[0].task_responses] == [
        "space",
        "left",
    ]
    run_dir = output_dir / plan.ordered_entries()[0].run_id
    assert (run_dir / "task_responses.jsonl").is_file()
    assert len((run_dir / "task_responses.jsonl").read_text().splitlines()) == 2
    assert (run_dir / "task_responses.csv").is_file()
    assert (output_dir / "task_responses.csv").is_file()
    run_summary_payload = json.loads((run_dir / "run_summary.json").read_text())
    session_summary_payload = json.loads((output_dir / "session_summary.json").read_text())
    assert "task_responses" not in run_summary_payload
    assert all("task_responses" not in run for run in session_summary_payload["run_results"])
    assert "Study the items." not in (run_dir / "run_summary.json").read_text()


def test_pre_task_can_serve_as_condition_gate_without_duplicate_transition(
    sample_project,
    sample_project_root,
    tmp_path: Path,
) -> None:
    plan = compile_session_plan(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=33,
    )
    pre = _module(
        TaskStepSpec(
            step_id="reminder",
            kind=TaskStepKind.RAW_KEY,
            text="Fixate and press Space to begin.",
            allowed_keys=["space"],
            random_seed=1,
        )
    )
    plan = _session_with_tasks(plan, pre=pre)
    block = plan.blocks[0]
    entry = block.entries[0].model_copy(update={"show_condition_start_gate": False})
    plan = plan.model_copy(
        update={"blocks": [block.model_copy(update={"entries": [entry]})]}
    )
    captures: dict[str, object] = {}
    engine = _TaskEngine([TaskEngineInput(key="space")], captures)
    project_root = tmp_path / "project"
    project_root.mkdir()

    summary = RuntimeWorker(engine).execute_session(
        project_root,
        plan,
        project_root / "runs" / "P012",
        participant_number="012",
        runtime_options={
            "export_mode": "compact", "serial_enabled": False,
            "experiment_test_mode": True,
        },
    )

    assert summary.aborted is False
    assert captures.get("transitions", []) == []
    assert engine._captures["run_ids"] == [entry.run_id]


def test_transition_abort_after_pre_task_preserves_compact_response(
    sample_project,
    sample_project_root,
    tmp_path: Path,
) -> None:
    plan = compile_session_plan(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=32,
    )
    pre = _module(
        TaskStepSpec(
            step_id="intro",
            kind=TaskStepKind.INSTRUCTION,
            continue_key="space",
            random_seed=1,
        )
    )
    plan = _session_with_tasks(plan, pre=pre)
    project_root = tmp_path / "project"
    project_root.mkdir()
    engine = _TaskEngine(
        [TaskEngineInput(key="space")],
        {"abort_on_transition": True},
    )

    summary = RuntimeWorker(engine).execute_session(
        project_root,
        plan,
        project_root / "runs" / "P011",
        participant_number="011",
        runtime_options={
            "export_mode": "compact", "serial_enabled": False,
            "experiment_test_mode": True,
        },
    )

    assert summary.aborted is True
    assert len(summary.run_results) == 1
    run_summary = summary.run_results[0]
    assert run_summary.task_flow_aborted is False
    assert run_summary.task_flow_completed is False
    assert run_summary.task_abort_stage is None
    assert run_summary.task_responses[0].key == "space"
    assert not (project_root / "runs").exists()
    with (project_root / "logs" / "task_responses.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["session_aborted"] == "True"


def test_post_task_abort_preserves_completed_fpvs_run_and_partial_full_exports(
    sample_project,
    sample_project_root,
    tmp_path: Path,
) -> None:
    plan = compile_session_plan(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=33,
    )
    post = _module(
        TaskStepSpec(
            step_id="advance",
            kind=TaskStepKind.RAW_KEY,
            allowed_keys=["y", "n", "left", "right", "space"],
            random_seed=1,
        )
    ).model_copy(update={"phase": TaskPhase.POST_CONDITION})
    plan = _session_with_tasks(plan, post=post)
    project_root = tmp_path / "project"
    project_root.mkdir()
    output_dir = project_root / "runs" / "P012"
    engine = _TaskEngine([TaskEngineInput(aborted=True)], {"flow": True})

    summary = RuntimeWorker(engine).execute_session(
        project_root,
        plan,
        output_dir,
        participant_number="012",
        runtime_options={
            "export_mode": "full", "serial_enabled": False,
            "experiment_test_mode": True,
        },
        relative_output_dir="runs/P012",
    )

    assert summary.aborted is True
    assert summary.completed_condition_count == 1
    run_summary = summary.run_results[0]
    assert run_summary.aborted is False
    assert run_summary.completed_frames == plan.ordered_entries()[0].run_spec.display.total_frames
    assert run_summary.task_flow_completed is False
    assert run_summary.task_flow_aborted is True
    assert run_summary.task_abort_stage == "post_condition"
    assert run_summary.task_responses[0].aborted is True
    run_dir = output_dir / plan.ordered_entries()[0].run_id
    assert (run_dir / "task_responses.jsonl").is_file()
    with (run_dir / "task_responses.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["aborted"] == "True"
