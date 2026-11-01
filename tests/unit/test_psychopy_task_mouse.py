"""Native task clicks exercised without importing PsychoPy or opening a window."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from fpvs_studio.engines.base import ResolvedTaskItem, ResolvedTaskStep
from fpvs_studio.engines.psychopy_tasks import render_task_step


class _Handle:
    def __init__(self):
        self.handlers = []
        self.added = []
        self.removed = []
        self.callback_results = []
        self.downstream_presses = []
        self.dispatches = 0

    def dispatch_events(self):
        self.dispatches += 1

    def push_handlers(self, **handlers):
        self.handlers.append(handlers)
        self.added.append(handlers)

    def remove_handlers(self, **handlers):
        self.handlers.remove(handlers)
        self.removed.append(handlers)

    def press(self, x, y, button):
        for handlers in reversed(self.handlers):
            callback = handlers.get("on_mouse_press")
            if callback is not None:
                result = callback(x, y, button, 0)
                self.callback_results.append(result)
                if result:
                    return
        self.downstream_presses.append((x, y, button))


class _Stimulus:
    def __init__(self, window, **properties):
        self.pos = properties.get("pos", (0, 0))

    def draw(self):
        pass

    def contains(self, position, *, units):
        assert units == "pix"
        return (
            abs(position[0] - self.pos[0]) <= 80
            and abs(position[1] - self.pos[1]) <= 30
        )


class _Screen:
    size = (1280, 720)
    winType = "pyglet"
    mouseVisible = False

    def __init__(self, *, scale=1):
        self.scale = scale
        self.winHandle = _Handle()
        self.flips = 0
        self.callbacks = []
        self.actions = []
        self.keys = []
        self.buttons = (0, 0, 0)
        self.visual = SimpleNamespace(TextStim=_Stimulus, ImageStim=_Stimulus, Rect=_Stimulus)
        self.event = SimpleNamespace(Mouse=lambda **kwargs: SimpleNamespace(
            getPressed=lambda: self.buttons,
            # A queued click must retain its own location, even after movement.
            getPos=lambda: (600, 300),
        ))
        self.keyboard = SimpleNamespace(
            clearEvents=self.keys.clear, getKeys=self.get_keys,
        )
        screen = self

        class Clock:
            def __init__(self):
                self.start = screen.flips

            def reset(self):
                self.start = screen.flips

            def getTime(self):
                return (screen.flips - self.start) * 0.1

        self.core = SimpleNamespace(Clock=Clock)

    def getContentScaleFactor(self):  # noqa: N802
        return self.scale

    def callOnFlip(self, callback, *args):  # noqa: N802
        self.callbacks.append((callback, args))

    def get_keys(self, **kwargs):
        keys, self.keys = self.keys, []
        return keys

    def flip(self):
        self.flips += 1
        action = self.actions.pop(0) if self.actions else "escape"
        # PsychoPy pumps native input before running its flip callbacks.
        if action == "escape":
            self.keys.append("escape")
        elif action == "error":
            raise RuntimeError("display failed")
        elif action is not None:
            kind, position, button = action
            if kind == "geometry":
                self.size = position
                self.scale = button
            if kind in {"click", "press"}:
                self.buttons = tuple(int(bool(button & mask)) for mask in (1, 2, 4))
                x = (position[0] + self.size[0] / 2) / self.scale
                y = (position[1] + self.size[1] / 2) / self.scale
                self.winHandle.press(x, y, button)
            if kind in {"click", "release"}:
                self.buttons = (0, 0, 0)
        callbacks, self.callbacks = self.callbacks, []
        for callback, args in callbacks:
            callback(*args)

    def render(self, tmp_path, *, step=None):
        return render_task_step(
            visual=self.visual, core=self.core, event=self.event, window=self,
            keyboard=self.keyboard, project_root=tmp_path, step=step or _recognition_step(),
            is_aborted=lambda: False, set_aborted=lambda: None,
        )


class _CursorScreen(_Screen):
    """Model PsychoPy's visibility property forwarding to its native backend."""

    def __init__(self, *, initially_visible=False):
        super().__init__()
        self.native_cursor_visible = initially_visible
        self.cursor_changes = []
        self.visible_frames = []

    @property
    def mouseVisible(self):  # noqa: N802
        return self.native_cursor_visible

    @mouseVisible.setter
    def mouseVisible(self, visible):  # noqa: N802
        self.native_cursor_visible = visible
        self.cursor_changes.append(visible)

    def flip(self):
        self.visible_frames.append(self.native_cursor_visible)
        super().flip()


def _recognition_step():
    return ResolvedTaskStep(
        task_id="custom-recognition",
        step_id="recognition-grid", kind="choice_grid", response_kind="single_choice",
        show_footer=False,
        items=(
            ResolvedTaskItem(
                "pen-target", text="Pen", position_px=(-200, -120), selectable=True,
            ),
            ResolvedTaskItem(
                "lamp-target", text="Lamp", position_px=(200, -120), selectable=True,
            ),
            ResolvedTaskItem(
                "bowl-foil", text="Bowl", position_px=(0, 120), selectable=False,
            ),
        ),
    )


def _assert_handlers_released(screen):
    assert len(screen.winHandle.added) == len(screen.winHandle.removed) > 0
    assert screen.winHandle.handlers == []
    assert screen.winHandle.callback_results
    assert all(result is None for result in screen.winHandle.callback_results)
    assert not screen.mouseVisible


@pytest.mark.parametrize("scale", [1, 2])
@pytest.mark.parametrize(("native_button", "button_index"), [(1, 0), (2, 1), (4, 2)])
def test_complete_native_click_between_polls_selects_text_at_scaled_position(
    tmp_path, scale, native_button, button_index,
):
    screen = _Screen(scale=scale)
    screen.actions = [
        None,
        ("click", (0, 120), native_button),  # Imported foils remain nonselectable.
        ("click", (200, -120), native_button),
    ]

    result = screen.render(tmp_path)

    assert result.selected_item_ids == ("lamp-target",)
    assert result.mouse_position_px == (200, -120)
    assert result.mouse_button == button_index
    assert result.reaction_time_s == pytest.approx(0.2)
    assert screen.buttons == (0, 0, 0)
    assert len(screen.winHandle.downstream_presses) == 2
    _assert_handlers_released(screen)


def test_held_click_from_prior_screen_is_ignored_until_new_press(tmp_path):
    screen = _Screen()
    screen.buttons = (1, 0, 0)
    screen.actions = [
        ("press", (-200, -120), 1),
        ("release", (-200, -120), 1),
        ("click", (200, -120), 1),
    ]

    result = screen.render(tmp_path)

    assert result.selected_item_ids == ("lamp-target",)
    assert screen.flips == 3
    _assert_handlers_released(screen)


def test_repeated_recognition_screens_do_not_replay_previous_click(tmp_path):
    screen = _Screen()
    screen.actions = [None, ("click", (-200, -120), 1)]
    first = screen.render(tmp_path)
    screen.actions = [None, ("click", (200, -120), 1)]
    second = screen.render(tmp_path)

    assert first.selected_item_ids == ("pen-target",)
    assert second.selected_item_ids == ("lamp-target",)
    assert screen.flips == 4
    assert len(screen.winHandle.added) == 2
    _assert_handlers_released(screen)


@pytest.mark.parametrize("exit_action", ["escape", "error"])
def test_native_click_handler_removed_on_abort_and_display_error(tmp_path, exit_action):
    screen = _Screen()
    screen.actions = [None, ("click", (0, 120), 1), exit_action]

    if exit_action == "error":
        with pytest.raises(RuntimeError, match="display failed"):
            screen.render(tmp_path)
    else:
        assert screen.render(tmp_path).aborted

    _assert_handlers_released(screen)


def test_short_native_click_submits_editable_response(tmp_path):
    screen = _Screen()
    screen.actions = [None, ("click", (0, -720 * 0.32), 1)]
    step = replace(
        _recognition_step(), kind="questionnaire", response_kind="short_text",
        items=(), required=False,
    )

    result = screen.render(tmp_path, step=step)

    assert result.key == "mouse-submit"
    assert result.mouse_position_px == (0, -720 * 0.32)
    assert result.mouse_button == 0
    _assert_handlers_released(screen)


def test_native_capture_does_not_construct_or_poll_legacy_mouse(tmp_path):
    screen = _Screen()
    screen.actions = [None, ("click", (200, -120), 1)]

    def legacy_mouse(**kwargs):
        raise AssertionError("Native choices must not depend on the legacy mouse device")

    screen.event.Mouse = legacy_mouse

    result = screen.render(tmp_path)

    assert result.selected_item_ids == ("lamp-target",)
    assert screen.winHandle.dispatches == 2
    _assert_handlers_released(screen)


def test_click_mapping_tracks_current_window_size_and_scale(tmp_path):
    screen = _Screen()
    screen.actions = [
        None, ("geometry", (1600, 1000), 1.5), ("click", (200, -120), 1),
    ]

    result = screen.render(tmp_path)

    assert result.selected_item_ids == ("lamp-target",)
    assert result.mouse_position_px == pytest.approx((200, -120))
    _assert_handlers_released(screen)


@pytest.mark.parametrize("modality", ["text", "image"])
@pytest.mark.parametrize("response_kind", ["single_choice", "multiple_choice", "rating"])
def test_shared_choice_modes_accept_native_clicks_from_arbitrary_modifiers(
    tmp_path, modality, response_kind,
):
    screen = _Screen()
    step = _recognition_step()
    if modality == "image":
        step = replace(step, items=tuple(
            replace(item, text=None, image_path=f"stimuli/task-assets/custom/{item.item_id}.png")
            for item in step.items
        ))
    step = replace(step, response_kind=response_kind)
    screen.actions = [None, ("click", (-200, -120), 1)]
    if response_kind == "multiple_choice":
        step = replace(
            step, submission_mode="explicit", minimum_selections=2, maximum_selections=2,
        )
        screen.actions.extend([
            ("click", (200, -120), 1), ("click", (0, -720 * 0.32), 1),
        ])

    result = screen.render(tmp_path, step=step)

    expected = (
        ("pen-target", "lamp-target") if response_kind == "multiple_choice" else ("pen-target",)
    )
    assert result.selected_item_ids == expected
    if response_kind == "multiple_choice":
        assert result.key == "mouse-submit"
    _assert_handlers_released(screen)


@pytest.mark.parametrize("initially_visible", [False, True])
@pytest.mark.parametrize(("response_kind", "modality"), [
    (kind, modality)
    for kind in ("single_choice", "multiple_choice", "rating")
    for modality in ("image", "text")
] + [("short_text", "text"), ("long_text", "text")])
@pytest.mark.parametrize("exit_kind", ["submit", "abort", "display_error"])
def test_mouse_task_cursor_is_visible_throughout_screen_and_restored(
    tmp_path, initially_visible, response_kind, modality, exit_kind,
):
    screen = _CursorScreen(initially_visible=initially_visible)
    step = replace(_recognition_step(), response_kind=response_kind)
    if modality == "image":
        step = replace(step, items=tuple(
            replace(item, text=None, image_path=f"stimuli/task-assets/custom/{item.item_id}.png")
            for item in step.items
        ))
    click_position = (-200, -120)
    if response_kind in {"short_text", "long_text"}:
        step = replace(step, kind="questionnaire", items=(), required=False)
        click_position = (0, -720 * 0.32)
    screen.actions = [None, ("click", click_position, 1)]
    if exit_kind != "submit":
        screen.actions = [None, "escape" if exit_kind == "abort" else "error"]

    if exit_kind == "display_error":
        with pytest.raises(RuntimeError, match="display failed"):
            screen.render(tmp_path, step=step)
    else:
        result = screen.render(tmp_path, step=step)
        assert result.aborted is (exit_kind == "abort")

    assert len(screen.visible_frames) >= 2
    assert all(screen.visible_frames)
    assert screen.cursor_changes == [True, initially_visible]
    assert screen.native_cursor_visible is initially_visible
    assert screen.winHandle.handlers == []


def test_four_recognition_repeats_each_enable_cursor_and_accept_a_short_click(tmp_path):
    screen = _CursorScreen()
    step = replace(_recognition_step(), items=tuple(
        ResolvedTaskItem(
            f"target-{index}", image_path=f"stimuli/task-assets/recognition/{index}.png",
            position_px=((index - 1.5) * 200, -120), size_px=(100, 100), selectable=True,
        ) for index in range(4)
    ))

    for item in step.items:
        screen.actions = [None, ("click", item.position_px, 1)]
        result = screen.render(tmp_path, step=step)
        assert result.selected_item_ids == (item.item_id,)
        assert not result.aborted
        assert not screen.native_cursor_visible
        assert screen.winHandle.handlers == []

    assert screen.visible_frames == [True] * 8
    assert screen.cursor_changes == [True, False] * 4


@pytest.mark.parametrize("initially_visible", [False, True])
def test_mouse_setup_failure_restores_native_cursor_without_opening_a_screen(
    tmp_path, initially_visible,
):
    screen = _CursorScreen(initially_visible=initially_visible)

    def reject_handler(**handlers):
        raise RuntimeError("native input unavailable")

    screen.winHandle.push_handlers = reject_handler

    with pytest.raises(RuntimeError, match="native input unavailable"):
        screen.render(tmp_path)

    assert screen.cursor_changes == [True, initially_visible]
    assert screen.native_cursor_visible is initially_visible
    assert screen.visible_frames == []


@pytest.mark.parametrize("modality", ["image", "text"])
@pytest.mark.parametrize("scale", [1, 2])
@pytest.mark.parametrize("carried_click", [False, True])
def test_first_visible_flip_keeps_clicks_pumped_by_keyboard_clear(
    tmp_path, modality, scale, carried_click,
):
    screen = _Screen(scale=scale)
    step = _recognition_step()
    if modality == "image":
        step = replace(step, items=tuple(
            replace(item, text=None, image_path=f"stimuli/task-assets/choice/{item.item_id}.png")
            for item in step.items
        ))
    # PsychoPy pumps carried events before swapping buffers. Its first-flip
    # keyboard clear then pumps events again, after the choices become visible.
    screen.actions = [
        ("click", (-200, -120), 1) if carried_click else None,
        "escape",
    ]
    cleared_at = []

    def clear_keyboard_events():
        screen.keys.clear()
        cleared_at.append(screen.flips)
        screen.buttons = (1, 0, 0)
        screen.winHandle.press(
            (200 + screen.size[0] / 2) / scale,
            (-120 + screen.size[1] / 2) / scale,
            1,
        )
        screen.buttons = (0, 0, 0)

    screen.keyboard.clearEvents = clear_keyboard_events

    result = screen.render(tmp_path, step=step)

    assert cleared_at == [1]
    assert result.selected_item_ids == ("lamp-target",)
    assert not result.aborted
    assert screen.flips == 1
    assert result.mouse_position_px == (200, -120)
    _assert_handlers_released(screen)
