"""Typed recall input and participant gates exercised without a real display."""

from types import SimpleNamespace

import pytest

from fpvs_studio.engines.base import ResolvedTaskStep
from fpvs_studio.engines.psychopy_tasks import _footer_text, render_task_step
from fpvs_studio.engines.psychopy_text_screens import show_text_screen


class _Screen:
    size = (1280, 720)
    mouseVisible = False

    def __init__(self):
        self.flips = 0
        self.callbacks = []
        self.actions = []
        self.keys = ["return"]
        self.clear_count = 0
        self.text_box = None
        self.buttons = (0, 0, 0)
        self.text_draws = []
        self.rect_draws = []
        self.visual = SimpleNamespace(
            TextStim=self._text_stim, TextBox2=self._text_box, Rect=self._rect,
        )
        self.keyboard = SimpleNamespace(clearEvents=self.clear_events, getKeys=self.get_keys)
        self.event = SimpleNamespace(Mouse=lambda **kwargs: SimpleNamespace(
            getPressed=lambda: self.buttons, getPos=lambda: (0, -720 * 0.32),
        ))
        self.core = SimpleNamespace(Clock=lambda: SimpleNamespace(
            getTime=lambda: self.flips * 0.1, reset=lambda: None,
        ))

    def _text_stim(self, *args, **kwargs):
        return SimpleNamespace(draw=lambda: self.text_draws.append(kwargs["text"]))

    def _rect(self, *args, **kwargs):
        return SimpleNamespace(draw=lambda: self.rect_draws.append(kwargs))

    def _text_box(self, *args, **kwargs):
        self.text_box = SimpleNamespace(text="", hasFocus=False, editable=True, draw=lambda: None)
        return self.text_box

    def clear_events(self):
        self.keys.clear()
        self.clear_count += 1

    def get_keys(self, *, keyList, **kwargs):  # noqa: N803
        keys, self.keys = self.keys, []
        return [SimpleNamespace(name=key, rt=0.1, duration=0.01) for key in keys
                if keyList is None or key in keyList]

    def callOnFlip(self, callback, *args):  # noqa: N802
        self.callbacks.append((callback, args))

    def flip(self):
        self.flips += 1
        callbacks, self.callbacks = self.callbacks, []
        for callback, args in callbacks:
            callback(*args)
        assert self.actions, "The task did not finish from the scripted participant input."
        action = self.actions.pop(0)
        self.buttons = (0, 0, 0)
        if action is None:
            return
        kind, value = action
        if kind == "type":
            self.text_box.text = value
            self.text_box.onTextCallback()
        elif kind == "key":
            self.keys.append(value)
        elif kind == "click":
            self.buttons = (1, 0, 0)

    def recall(self, tmp_path, *, step_id="t1-recall", submit_label="Next"):
        return render_task_step(
            visual=self.visual, core=self.core, event=self.event,
            window=self, keyboard=self.keyboard, project_root=tmp_path,
            step=ResolvedTaskStep(
                task_id="ab-recall", step_id=step_id, kind="questionnaire",
                response_kind="short_text", question_id=step_id,
                prompt="What was the green number?", submit_label=submit_label,
                required=True, maximum_text_length=32,
            ),
            is_aborted=lambda: False, set_aborted=lambda: None,
        )


@pytest.mark.parametrize("key", ["return", "enter"])
def test_typed_digit_submits_on_enter_with_next_button(tmp_path, key):
    screen = _Screen()
    screen.actions = [("type", "3"), ("key", key)]
    result = screen.recall(tmp_path)
    assert result.text_value == "3"
    assert result.key == key
    assert screen.flips == 2
    assert "Next" in screen.text_draws
    assert any("press Enter or select Next" in text for text in screen.text_draws)
    assert screen.rect_draws[-1]["pos"] == (0, -720 * 0.32)
    assert screen.clear_count == 2
    assert not screen.text_box.hasFocus
    assert not screen.text_box.editable


def test_textbox_newline_and_next_button_record_separate_questions(tmp_path):
    screen = _Screen()
    screen.actions = [("type", "3\n")]
    first = screen.recall(tmp_path)
    first_box = screen.text_box
    screen.keys = ["return", "space"]
    screen.actions = [None, ("type", "9"), ("click", None)]
    second = screen.recall(tmp_path, step_id="t2-recall")
    assert first.text_value == "3"
    assert second.text_value == "9"
    assert second.key == "mouse-submit"
    assert second.mouse_button == 0
    assert first_box is not screen.text_box
    assert not first_box.editable
    assert screen.flips == 4
    assert screen.clear_count == 4


def test_blank_answer_requires_input_and_non_digit_answer_is_retained(tmp_path):
    screen = _Screen()
    screen.actions = [("key", "enter"), ("type", "unsure"), ("click", None)]
    result = screen.recall(tmp_path)
    assert result.text_value == "unsure"
    assert any("A response is required." in text for text in screen.text_draws)
    assert screen.flips == 3


def test_stale_answer_keys_cannot_start_the_next_burst(tmp_path):
    screen = _Screen()
    screen.actions = [("type", "4"), ("key", "enter")]
    assert screen.recall(tmp_path).text_value == "4"
    screen.keys = ["return", "space"]
    screen.actions = [("key", "return"), ("key", "space")]
    aborted = show_text_screen(
        visual=screen.visual, core=screen.core, window=screen, keyboard=screen.keyboard,
        is_aborted=lambda: False, set_aborted=lambda: None,
        heading="Ready for the next burst", body=None,
        countdown_seconds=None, continue_key="space", continue_prompt="Press Space to begin.",
    )
    assert not aborted
    assert screen.flips == 4
    assert screen.clear_count == 3


def test_ordinary_text_tasks_retain_submit_label(tmp_path):
    screen = _Screen()
    screen.actions = [("type", "answer"), ("click", None)]
    assert screen.recall(tmp_path, submit_label="Submit").text_value == "answer"
    assert "Submit" in screen.text_draws
    assert "Next" not in screen.text_draws
    assert "select Submit" in _footer_text(ResolvedTaskStep(
        task_id="ordinary", step_id="text", kind="questionnaire", response_kind="long_text",
    ))


@pytest.mark.parametrize("submit_action", [("click", None), ("key", "enter")])
def test_supported_keyboard_text_input_also_has_visible_next_button(tmp_path, submit_action):
    screen = _Screen()
    del screen.visual.TextBox2
    screen.actions = [("key", "5"), submit_action]
    result = screen.recall(tmp_path)
    assert result.text_value == "5"
    assert "Next" in screen.text_draws
    assert "5" in screen.text_draws
    assert screen.rect_draws
    assert screen.clear_count == 2
