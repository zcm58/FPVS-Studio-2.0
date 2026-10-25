"""Typed recall input and participant gates exercised without a real display."""

from types import SimpleNamespace

import pytest

from fpvs_studio.engines import psychopy_stimuli
from fpvs_studio.engines.base import ResolvedTaskItem, ResolvedTaskStep
from fpvs_studio.engines.psychopy_stimuli import ConditionResourceCleanupError
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
        self.created_text = []
        self.created_rects = []
        self.selected_draws = []
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
        stimulus = SimpleNamespace(**kwargs)

        def draw():
            self.text_draws.append(stimulus.text)
            if stimulus.text == "[selected]":
                self.selected_draws.append((self.flips, stimulus.pos))

        stimulus.draw = draw
        self.created_text.append(stimulus)
        return stimulus

    def _rect(self, *args, **kwargs):
        stimulus = SimpleNamespace(**kwargs)
        stimulus.draw = lambda: self.rect_draws.append(dict(vars(stimulus)))
        self.created_rects.append(stimulus)
        return stimulus

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


def test_long_static_task_reuses_one_stimulus_per_text_slot(tmp_path):
    screen = _Screen()
    screen.actions = [None] * 120
    render_task_step(
        visual=screen.visual, core=screen.core, event=screen.event,
        window=screen, keyboard=screen.keyboard, project_root=tmp_path,
        step=ResolvedTaskStep(
            task_id="study", step_id="page", kind="study", duration_frames=120,
            heading="Heading", body="Body",
        ),
        is_aborted=lambda: False, set_aborted=lambda: None,
    )
    assert screen.flips == 120
    assert len(screen.created_text) == 3
    assert screen.text_draws.count("Heading") == 120
    assert screen.text_draws.count("Body") == 120


def test_changing_numeric_task_reuses_response_and_validation_text(tmp_path):
    screen = _Screen()
    screen.actions = [("key", "return"), *[("key", "1")] * 100, ("key", "return")]
    result = render_task_step(
        visual=screen.visual, core=screen.core, event=screen.event,
        window=screen, keyboard=screen.keyboard, project_root=tmp_path,
        step=ResolvedTaskStep(
            task_id="study", step_id="number", kind="questionnaire", response_kind="numeric",
        ),
        is_aborted=lambda: False, set_aborted=lambda: None,
    )
    assert result.text_value == "1" * 100
    assert len(screen.created_text) == 2
    assert screen.created_text[0].text == "1" * 100
    assert any("Enter a valid number." in text for text in screen.text_draws)
    assert screen.flips == 102


def test_long_text_task_reuses_submit_control(tmp_path):
    screen = _Screen()
    screen.actions = [*[("type", str(index)) for index in range(100)], ("key", "return")]
    result = screen.recall(tmp_path)
    assert result.text_value == "99"
    assert len(screen.created_rects) == 1
    assert len(screen.created_text) == 3
    assert len(screen.rect_draws) == 101
    assert screen.text_draws.count("Next") == 101


def test_cached_selection_labels_only_draw_for_current_selection(tmp_path):
    screen = _Screen()
    screen.actions = [
        ("click", None), None, ("click", None), None,
        ("click", None), None, ("click", None),
    ]
    click_positions = {1: (-200, 0), 3: (-200, 0), 5: (200, 0), 7: (0, -720 * 0.32)}
    screen.event.Mouse = lambda **kwargs: SimpleNamespace(
        getPressed=lambda: screen.buttons,
        getPos=lambda: click_positions.get(screen.flips, (0, 0)),
    )
    result = render_task_step(
        visual=screen.visual, core=screen.core, event=screen.event,
        window=screen, keyboard=screen.keyboard, project_root=tmp_path,
        step=ResolvedTaskStep(
            task_id="study", step_id="choices", kind="questionnaire",
            response_kind="multiple_choice", submission_mode="explicit", maximum_selections=2,
            items=(ResolvedTaskItem("a", text="A", position_px=(-200, 0), selectable=True),
                   ResolvedTaskItem("b", text="B", position_px=(200, 0), selectable=True)),
        ),
        is_aborted=lambda: False, set_aborted=lambda: None,
    )
    assert result.selected_item_ids == ("b",)
    assert [(frame, pos[0]) for frame, pos in screen.selected_draws] == [
        (1, -200), (2, -200), (5, 200), (6, 200),
    ]
    assert sum(item.text == "[selected]" for item in screen.created_text) == 2
    assert len(screen.created_rects) == 1


def test_partial_screen_text_construction_releases_prior_stimuli(monkeypatch, tmp_path):
    screen = _Screen()
    cleared = []
    released_buffers = []
    monkeypatch.setattr(psychopy_stimuli, "_delete_psychopy_pixel_buffer", released_buffers.append)

    def text_stim(*args, **kwargs):
        if kwargs["text"] == "Body":
            raise RuntimeError("body construction failed")
        return SimpleNamespace(
            draw=lambda: None, _pixbuffID=1, clearTextures=lambda: cleared.append("heading"),
        )

    screen.visual.TextStim = text_stim
    with pytest.raises(RuntimeError, match="body construction failed"):
        render_task_step(
            visual=screen.visual, core=screen.core, event=screen.event,
            window=screen, keyboard=screen.keyboard, project_root=tmp_path,
            step=ResolvedTaskStep(
                task_id="study", step_id="page", kind="study", duration_frames=1,
                heading="Heading", body="Body",
            ),
            is_aborted=lambda: False, set_aborted=lambda: None,
        )
    assert cleared == ["heading"]
    assert released_buffers == [1]
    assert screen.flips == 0


@pytest.mark.parametrize("exit_path", ["complete", "abort", "draw_error"])
def test_cached_screen_text_releases_native_resources_on_every_exit(
    monkeypatch, tmp_path, exit_path,
):
    screen = _Screen()
    screen.actions = [None]
    created = []
    cleared = []
    released_buffers = []
    monkeypatch.setattr(psychopy_stimuli, "_delete_psychopy_pixel_buffer", released_buffers.append)

    def text_stim(*args, **kwargs):
        def draw():
            if exit_path == "draw_error" and kwargs["text"] == "Body":
                raise ValueError("body draw failed")

        stimulus = SimpleNamespace(
            draw=draw, _pixbuffID=len(created) + 1,
            clearTextures=lambda: cleared.append(kwargs["text"]),
        )
        created.append(stimulus)
        return stimulus

    screen.visual.TextStim = text_stim

    def render():
        return render_task_step(
            visual=screen.visual, core=screen.core, event=screen.event,
            window=screen, keyboard=screen.keyboard, project_root=tmp_path,
            step=ResolvedTaskStep(
                task_id="study", step_id="page", kind="study",
                duration_frames=2 if exit_path == "abort" else 1,
                heading="Heading", body="Body",
            ),
            is_aborted=lambda: exit_path == "abort" and screen.flips == 1,
            set_aborted=lambda: None,
        )

    if exit_path == "draw_error":
        with pytest.raises(ValueError, match="body draw failed"):
            render()
    else:
        assert render().aborted is (exit_path == "abort")
    assert len(cleared) == len(created) == (2 if exit_path == "draw_error" else 3)
    assert released_buffers == list(range(1, len(created) + 1))
    assert all(not hasattr(stimulus, "_pixbuffID") for stimulus in created)


@pytest.mark.parametrize("exit_path", ["complete", "abort", "draw_error", "setup_error"])
def test_task_images_release_native_buffers_on_every_exit(monkeypatch, tmp_path, exit_path):
    screen = _Screen()
    screen.actions = [None]
    created = []
    released_buffers = []
    released_lists = []
    monkeypatch.setattr(psychopy_stimuli, "_delete_psychopy_pixel_buffer", released_buffers.append)
    monkeypatch.setattr(psychopy_stimuli, "_delete_psychopy_display_list", released_lists.append)

    class ImageStim:
        def __init__(self, *args, **kwargs):
            self._pixbuffID = len(created) + 1
            self._listID = len(created) + 11
            self.clear_count = 0
            created.append(self)

        def draw(self):
            if exit_path == "draw_error":
                raise RuntimeError("image draw failed")

        def clearTextures(self):  # noqa: N802 - PsychoPy API
            self.clear_count += 1

    def fail_setup():
        raise RuntimeError("task clock failed")

    screen.visual.ImageStim = ImageStim
    if exit_path == "setup_error":
        screen.core.Clock = fail_setup

    def render():
        return render_task_step(
            visual=screen.visual, core=screen.core, event=screen.event,
            window=screen, keyboard=screen.keyboard, project_root=tmp_path,
            step=ResolvedTaskStep(
                task_id="study", step_id="images", kind="study", duration_frames=1,
                items=(ResolvedTaskItem("a", image_path="a.png"),
                       ResolvedTaskItem("b", image_path="b.png")),
            ),
            is_aborted=lambda: exit_path == "abort", set_aborted=lambda: None,
        )

    if exit_path in {"draw_error", "setup_error"}:
        with pytest.raises(RuntimeError, match="image draw failed|task clock failed"):
            render()
    else:
        result = render()
        assert result.aborted is (exit_path == "abort")
    assert released_buffers == [1, 2]
    assert released_lists == [11, 12]
    assert [item.clear_count for item in created] == [1, 1]
    assert all(not hasattr(item, "_pixbuffID") and item._listID == 0 for item in created)


@pytest.mark.parametrize("setup_error", ["mouse", "buttons", "flip_registration"])
@pytest.mark.parametrize("restore_error", [None, "keyboard", "focus"])
def test_text_task_setup_failure_restores_input_without_masking_original(
    tmp_path, setup_error, restore_error,
):
    screen = _Screen()
    original_error = RuntimeError("task setup failed")

    def fail_setup(*args, **kwargs):
        raise original_error

    if setup_error == "mouse":
        screen.event.Mouse = fail_setup
    elif setup_error == "buttons":
        screen.event.Mouse = lambda **kwargs: SimpleNamespace(getPressed=fail_setup)
    else:
        screen.callOnFlip = fail_setup

    if restore_error == "keyboard":
        def fail_keyboard_clear():
            raise OSError("keyboard cleanup failed")

        screen.keyboard.clearEvents = fail_keyboard_clear
    elif restore_error == "focus":
        class FailingFocus(SimpleNamespace):
            def __setattr__(self, name, value):
                if name == "hasFocus" and not value:
                    raise OSError("focus cleanup failed")
                super().__setattr__(name, value)

        def text_box(*args, **kwargs):
            screen.text_box = FailingFocus(text="", hasFocus=False, editable=True)
            return screen.text_box

        screen.visual.TextBox2 = text_box

    with pytest.raises(RuntimeError) as caught:
        screen.recall(tmp_path)
    assert caught.value is original_error
    assert not screen.text_box.editable
    if restore_error != "focus":
        assert not screen.text_box.hasFocus
    assert not screen.mouseVisible
    assert screen.flips == 0


def test_text_task_cleanup_failure_still_disables_input_and_restores_mouse(tmp_path):
    screen = _Screen()
    screen.actions = [("type", "answer"), ("key", "return")]

    def clear_keyboard():
        if screen.flips > 1:
            raise OSError("keyboard cleanup failed")
        screen.clear_events()

    screen.keyboard.clearEvents = clear_keyboard
    with pytest.raises(OSError, match="keyboard cleanup failed"):
        screen.recall(tmp_path)
    assert not screen.text_box.editable
    assert not screen.text_box.hasFocus
    assert not screen.mouseVisible
    assert screen.flips == 2


def test_task_image_preparation_rolls_back_before_later_constructor_failure(monkeypatch, tmp_path):
    screen = _Screen()
    released_buffers = []
    cleared = []
    monkeypatch.setattr(psychopy_stimuli, "_delete_psychopy_pixel_buffer", released_buffers.append)

    def image_stim(*args, **kwargs):
        if kwargs["image"].endswith("b.png"):
            raise RuntimeError("second image failed")
        return SimpleNamespace(_pixbuffID=1, clearTextures=lambda: cleared.append("a"))

    screen.visual.ImageStim = image_stim
    with pytest.raises(RuntimeError, match="second image failed"):
        render_task_step(
            visual=screen.visual, core=screen.core, event=screen.event,
            window=screen, keyboard=screen.keyboard, project_root=tmp_path,
            step=ResolvedTaskStep(
                task_id="study", step_id="images", kind="study", duration_frames=1,
                items=(ResolvedTaskItem("a", image_path="a.png"),
                       ResolvedTaskItem("b", image_path="b.png")),
            ),
            is_aborted=lambda: False, set_aborted=lambda: None,
        )
    assert released_buffers == [1]
    assert cleared == ["a"]
    assert screen.flips == 0


@pytest.mark.parametrize("draw_fails", [False, True])
def test_task_cleanup_attempts_every_item_and_reports_failures(monkeypatch, tmp_path, draw_fails):
    screen = _Screen()
    screen.actions = [None]
    released_buffers = []
    cleared = []
    monkeypatch.setattr(psychopy_stimuli, "_delete_psychopy_pixel_buffer", released_buffers.append)

    def image_stim(*args, **kwargs):
        name = "a" if kwargs["image"].endswith("a.png") else "b"

        def draw():
            if draw_fails:
                raise ValueError("image draw failed")

        def clear_textures():
            cleared.append(name)
            if name == "a":
                raise OSError("texture release failed")

        return SimpleNamespace(
            _pixbuffID=1 if name == "a" else 2, draw=draw,
            clearTextures=clear_textures,
        )

    screen.visual.ImageStim = image_stim
    with pytest.raises(ValueError if draw_fails else ConditionResourceCleanupError):
        render_task_step(
            visual=screen.visual, core=screen.core, event=screen.event,
            window=screen, keyboard=screen.keyboard, project_root=tmp_path,
            step=ResolvedTaskStep(
                task_id="study", step_id="images", kind="study", duration_frames=1,
                items=(ResolvedTaskItem("a", image_path="a.png"),
                       ResolvedTaskItem("b", image_path="b.png")),
            ),
            is_aborted=lambda: False, set_aborted=lambda: None,
        )
    assert released_buffers == [1, 2]
    assert cleared == ["a", "b"]


@pytest.mark.parametrize("numeric_step", [None, 0.5])
@pytest.mark.parametrize("invalid_text", ["nan", "inf", "-inf", "1e309"])
def test_numeric_question_rejects_nonfinite_values_and_allows_correction(
    tmp_path, numeric_step, invalid_text,
):
    screen = _Screen()
    typed_keys = ["minus" if letter == "-" else letter for letter in invalid_text]
    keys = [*typed_keys, "return", *["backspace"] * len(invalid_text), "2", "return"]
    screen.actions = [("key", key) for key in keys]
    result = render_task_step(
        visual=screen.visual, core=screen.core, event=screen.event,
        window=screen, keyboard=screen.keyboard, project_root=tmp_path,
        step=ResolvedTaskStep(
            task_id="questionnaire", step_id="number", kind="questionnaire",
            response_kind="numeric", numeric_minimum=0.0, numeric_maximum=10.0,
            numeric_step=numeric_step,
        ),
        is_aborted=lambda: False, set_aborted=lambda: None,
    )
    assert result.numeric_value == 2.0
    assert result.text_value == "2"
    assert screen.flips == len(keys)
    assert any("Enter a valid number." in text for text in screen.text_draws)


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
    screen.text_draws.clear()
    screen.actions = [None, ("type", "9"), ("click", None)]
    second = screen.recall(tmp_path, step_id="t2-recall", submit_label="Done")
    assert first.text_value == "3"
    assert second.text_value == "9"
    assert second.key == "mouse-submit"
    assert second.mouse_button == 0
    assert first_box is not screen.text_box
    assert not first_box.editable
    assert "Done" in screen.text_draws
    assert "Next" not in screen.text_draws
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
