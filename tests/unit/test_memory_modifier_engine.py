"""Exercise the recognition renderer without importing or launching PsychoPy."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from fpvs_studio.engines.base import ResolvedTaskItem, ResolvedTaskStep
from fpvs_studio.engines.psychopy_tasks import _completed_input, render_task_step


def _recognition_step():
    return ResolvedTaskStep(
        task_id="memory-recognition", step_id="memory-recognition", kind="choice_grid",
        response_kind="multiple_choice", minimum_selections=4, maximum_selections=4,
        submission_mode="explicit", submit_label="Submit",
        items=tuple(ResolvedTaskItem(
            item_id=f"image-{index}", image_path=f"stimuli/task-assets/memory/{index}.png",
            position_px=((index % 4 - 1.5) * 180, (0.5 - index // 4) * 140),
            size_px=(100, 100), selectable=True,
        ) for index in range(8)),
    )


@pytest.mark.parametrize("abort", [False, True])
def test_recognition_clicks_allow_revision_and_explicit_submit(tmp_path, abort):
    text_calls = []
    rect_calls = []

    class Stim:
        def __init__(self, *args, **kwargs):
            if "text" in kwargs:
                text_calls.append(kwargs["text"])
        def draw(self):
            pass

    class Rect(Stim):
        def __init__(self, *args, **kwargs):
            rect_calls.append(kwargs)

    class Window:
        size = (1280, 720)
        mouseVisible = False
        flip_count = 0
        callbacks = []
        def callOnFlip(self, callback):
            self.callbacks.append(callback)
        def flip(self):
            self.flip_count += 1
            callbacks, self.callbacks = self.callbacks, []
            for callback in callbacks:
                callback()

    window = Window()

    class Clock:
        start = 0
        def reset(self):
            self.start = window.flip_count
        def getTime(self):
            return (window.flip_count - self.start) / 10

    class Keyboard:
        def clearEvents(self):
            pass
        def getKeys(self, **kwargs):
            assert window.flip_count <= 15
            return ["escape"] if abort and window.flip_count == 15 else []

    # An early Submit with two choices is refused. Then revise the first choice.
    clicks = {1: 0, 3: 1, 5: "submit", 7: 2, 9: 3, 11: 0, 13: 4, 15: "submit"}
    step = _recognition_step()

    class Mouse:
        def getPressed(self):
            return (int(window.flip_count in clicks), 0, 0)
        def getPos(self):
            item = clicks.get(window.flip_count)
            if item == "submit":
                return (0, -window.size[1] * 0.32)
            return step.items[item].position_px if isinstance(item, int) else (0, 0)

    aborted = []
    result = render_task_step(
        visual=SimpleNamespace(TextStim=Stim, ImageStim=Stim, Rect=Rect),
        core=SimpleNamespace(Clock=Clock), event=SimpleNamespace(Mouse=lambda **kwargs: Mouse()),
        window=window, keyboard=Keyboard(), project_root=tmp_path, step=step,
        is_aborted=lambda: False, set_aborted=lambda: aborted.append(True),
    )

    assert result.selected_item_ids == ("image-1", "image-2", "image-3", "image-4")
    assert result.reaction_time_s == pytest.approx(1.4)
    assert result.aborted is abort
    assert "Submit" in text_calls and rect_calls
    assert "Select at least 4 option(s).\n" in next(
        text for text in text_calls if text.startswith("Select at least")
    )
    if not abort:
        assert result.key == "mouse-submit"
        assert result.mouse_button == 0


def test_recognition_rejects_all_eight_selected_images():
    step = _recognition_step()
    assert _completed_input(
        step, key="return", selected_item_ids=[item.item_id for item in step.items],
        response_text="", reaction_time_s=1.2,
        displayed_item_ids=tuple(item.item_id for item in step.items),
    ) is None
