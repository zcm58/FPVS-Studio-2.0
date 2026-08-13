"""PsychoPy rendering for engine-neutral modular task screens.

Task screens are deliberately outside the FPVS frame clock. The helper only renders
one already-resolved screen and returns raw input; runtime owns sequencing, repeats,
branching, correctness, and response persistence.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, TypedDict

from fpvs_studio.core.paths import resolve_project_relative_path
from fpvs_studio.engines.base import ResolvedTaskItem, ResolvedTaskStep, TaskEngineInput

_TEXT_RESPONSE_KINDS = frozenset({"short_text", "long_text", "numeric"})
_CHOICE_RESPONSE_KINDS = frozenset({"single_choice", "multiple_choice", "rating"})
_EDITABLE_TEXT_RESPONSE_KINDS = frozenset({"short_text", "long_text"})


class _KeyResult(TypedDict):
    aborted: bool
    submitted_key: str | None
    response_key: str | None
    key_rt: float | None
    key_duration: float | None
    response_text: str


class _MouseClick(TypedDict):
    buttons: tuple[int, ...]
    button: int | None
    position: tuple[float, float]


def render_task_step(
    *,
    visual: Any,
    core: Any,
    event: Any,
    window: Any,
    keyboard: Any,
    project_root: Path,
    step: ResolvedTaskStep,
    is_aborted: Any,
    set_aborted: Any,
) -> TaskEngineInput:
    """Render one modular task step and collect a neutral response."""

    item_stimuli = _prepare_item_stimuli(
        visual=visual,
        window=window,
        project_root=project_root,
        items=step.items,
    )
    displayed_item_ids = tuple(item.item_id for item in step.items)
    selected_item_ids: list[str] = []
    response_text = ""
    last_response_key: str | None = None
    last_key_reaction_time_s: float | None = None
    last_key_duration_s: float | None = None
    validation_message: str | None = None
    task_clock = core.Clock()
    text_box, submitted_from_text_box = _prepare_text_box(
        visual=visual,
        window=window,
        step=step,
    )
    mouse_response_kinds = _CHOICE_RESPONSE_KINDS | _EDITABLE_TEXT_RESPONSE_KINDS
    mouse = event.Mouse(win=window) if step.response_kind in mouse_response_kinds else None
    previous_buttons = tuple(mouse.getPressed()) if mouse is not None else (0, 0, 0)
    previous_mouse_visible = getattr(window, "mouseVisible", None)
    if mouse is not None:
        window.mouseVisible = True

    call_on_flip = getattr(window, "callOnFlip", None)
    reset_task_clock = getattr(task_clock, "reset", None)
    if callable(call_on_flip):
        call_on_flip(keyboard.clearEvents)
        keyboard_clock = getattr(keyboard, "clock", None)
        reset_keyboard_clock = getattr(keyboard_clock, "reset", None)
        if callable(reset_keyboard_clock):
            call_on_flip(reset_keyboard_clock)
        if callable(reset_task_clock):
            call_on_flip(reset_task_clock)
    else:
        keyboard.clearEvents()
        keyboard_clock = getattr(keyboard, "clock", None)
        reset_keyboard_clock = getattr(keyboard_clock, "reset", None)
        if callable(reset_keyboard_clock):
            reset_keyboard_clock()
        if callable(reset_task_clock):
            reset_task_clock()

    try:
        while True:
            elapsed_s = float(task_clock.getTime())
            if is_aborted():
                return _task_input(
                    step,
                    aborted=True,
                    reaction_time_s=elapsed_s,
                    displayed_item_ids=displayed_item_ids,
                )

            _draw_step(
                visual=visual,
                window=window,
                step=step,
                item_stimuli=item_stimuli,
                selected_item_ids=selected_item_ids,
                response_text=response_text,
                validation_message=validation_message,
                text_box=text_box,
            )
            window.flip()

            key_result = _handle_keys(
                keyboard=keyboard,
                step=step,
                response_text=response_text,
                selected_item_ids=selected_item_ids,
                native_text_input=text_box is not None,
            )
            response_text = _text_box_value(text_box, fallback=str(key_result["response_text"]))
            response_text = response_text[: step.maximum_text_length]
            if text_box is not None and _text_box_value(text_box) != response_text:
                text_box.text = response_text
            submitted_key = key_result["submitted_key"]
            if submitted_from_text_box[0]:
                submitted_key = step.submit_key
                submitted_from_text_box[0] = False
            if key_result["response_key"] is not None:
                last_response_key = str(key_result["response_key"])
                last_key_reaction_time_s = _optional_float(key_result["key_rt"])
                last_key_duration_s = _optional_float(key_result["key_duration"])
            if key_result["aborted"]:
                set_aborted()
                return _task_input(
                    step,
                    aborted=True,
                    key="escape",
                    reaction_time_s=float(task_clock.getTime()),
                    displayed_item_ids=displayed_item_ids,
                )

            if mouse is not None:
                click = _new_mouse_click(mouse, previous_buttons)
                previous_buttons = click["buttons"]
                click_button = click["button"]
                click_position = click["position"]
                if click_button is not None:
                    if step.response_kind in _EDITABLE_TEXT_RESPONSE_KINDS and _point_in_box(
                        click_position,
                        box_position=_text_submit_position(window),
                        size=_text_submit_size(window),
                    ):
                        completed = _completed_input(
                            step,
                            key="mouse-submit",
                            selected_item_ids=selected_item_ids,
                            response_text=response_text,
                            reaction_time_s=float(task_clock.getTime()),
                            displayed_item_ids=displayed_item_ids,
                        )
                        if completed is not None:
                            return replace(
                                completed,
                                mouse_position_px=click_position,
                                mouse_button=click_button,
                            )
                        validation_message = _validation_message(
                            step, selected_item_ids, response_text
                        )
                        continue
                    clicked_item = _item_at_position(
                        step.items,
                        stimuli=item_stimuli,
                        x=float(click_position[0]),
                        y=float(click_position[1]),
                    )
                    if clicked_item is not None:
                        if (
                            step.response_kind in {"single_choice", "rating"}
                            and step.submission_mode == "immediate"
                        ):
                            return _task_input(
                                step,
                                key=last_response_key,
                                key_reaction_time_s=last_key_reaction_time_s,
                                key_duration_s=last_key_duration_s,
                                selected_item_ids=(clicked_item.item_id,),
                                mouse_position_px=click_position,
                                mouse_button=click_button,
                                reaction_time_s=float(task_clock.getTime()),
                                displayed_item_ids=displayed_item_ids,
                            )
                        _toggle_selection(selected_item_ids, clicked_item.item_id)
                        if (
                            step.maximum_selections is not None
                            and len(selected_item_ids) > step.maximum_selections
                        ):
                            selected_item_ids.pop(0)
                        validation_message = None
                        immediate_multiple_complete = (
                            step.response_kind == "multiple_choice"
                            and step.submission_mode == "immediate"
                            and (
                                (
                                    step.maximum_selections is None
                                    and len(selected_item_ids)
                                    >= max(1, step.minimum_selections)
                                )
                                or (
                                    step.maximum_selections is not None
                                    and len(selected_item_ids) >= step.maximum_selections
                                )
                            )
                        )
                        if immediate_multiple_complete:
                            return _task_input(
                                step,
                                key=last_response_key,
                                key_reaction_time_s=last_key_reaction_time_s,
                                key_duration_s=last_key_duration_s,
                                selected_item_ids=tuple(selected_item_ids),
                                mouse_position_px=click_position,
                                mouse_button=click_button,
                                reaction_time_s=float(task_clock.getTime()),
                                displayed_item_ids=displayed_item_ids,
                            )

            if submitted_key is not None:
                completed = _completed_input(
                    step,
                    key=last_response_key or submitted_key,
                    selected_item_ids=selected_item_ids,
                    response_text=response_text,
                    reaction_time_s=float(task_clock.getTime()),
                    displayed_item_ids=displayed_item_ids,
                )
                if completed is not None:
                    return replace(
                        completed,
                        key_reaction_time_s=last_key_reaction_time_s
                        if last_response_key is not None
                        else _optional_float(key_result["key_rt"]),
                        key_duration_s=last_key_duration_s
                        if last_response_key is not None
                        else _optional_float(key_result["key_duration"]),
                    )
                validation_message = _validation_message(step, selected_item_ids, response_text)

            elapsed_s = float(task_clock.getTime())
            if step.duration_s is not None and elapsed_s >= step.duration_s:
                return _task_input(
                    step,
                    reaction_time_s=elapsed_s,
                    displayed_item_ids=displayed_item_ids,
                )
            if step.timeout_s is not None and elapsed_s >= step.timeout_s:
                return _task_input(
                    step,
                    timed_out=True,
                    key=last_response_key,
                    selected_item_ids=tuple(selected_item_ids),
                    text_value=response_text or None,
                    reaction_time_s=elapsed_s,
                    displayed_item_ids=displayed_item_ids,
                )
    finally:
        if text_box is not None:
            if hasattr(text_box, "hasFocus"):
                text_box.hasFocus = False
            if hasattr(text_box, "editable"):
                text_box.editable = False
        if previous_mouse_visible is not None:
            window.mouseVisible = previous_mouse_visible
        for stimulus in item_stimuli.values():
            clear_textures = getattr(stimulus, "clearTextures", None)
            if callable(clear_textures):
                clear_textures()


def _prepare_item_stimuli(
    *,
    visual: Any,
    window: Any,
    project_root: Path,
    items: tuple[ResolvedTaskItem, ...],
) -> dict[str, Any]:
    stimuli: dict[str, Any] = {}
    for item in items:
        if item.image_path is not None:
            stimuli[item.item_id] = visual.ImageStim(
                window,
                image=str(resolve_project_relative_path(project_root, item.image_path)),
                units="pix",
                pos=item.position_px,
                size=item.size_px,
                autoLog=False,
            )
            continue
        stimuli[item.item_id] = visual.TextStim(
            window,
            text=item.text or "",
            font="Arial",
            units="pix",
            pos=item.position_px,
            height=item.text_height_px,
            color=item.color,
            wrapWidth=item.size_px[0] if item.size_px is not None else None,
            autoLog=False,
        )
    return stimuli


def _prepare_text_box(
    *, visual: Any, window: Any, step: ResolvedTaskStep
) -> tuple[Any | None, list[bool]]:
    submitted = [False]
    if step.response_kind not in {"short_text", "long_text"}:
        return None, submitted
    text_box_type = getattr(visual, "TextBox2", None)
    if text_box_type is None:
        return None, submitted
    window_height = _window_height(window)
    box_height = window_height * (0.25 if step.response_kind == "long_text" else 0.09)
    text_box = text_box_type(
        window,
        text="",
        font="Arial",
        units="pix",
        pos=(0, -window_height * 0.14),
        size=(_window_width(window) * 0.82, box_height),
        letterHeight=max(22.0, window_height * 0.03),
        color="white",
        borderColor="white",
        fillColor=None,
        editable=True,
        autoLog=False,
    )
    text_box.onTextCallback = lambda: _normalize_text_box_input(
        text_box,
        step=step,
        submitted=submitted,
    )
    if hasattr(text_box, "hasFocus"):
        text_box.hasFocus = True
    return text_box, submitted


def _normalize_text_box_input(
    text_box: Any,
    *,
    step: ResolvedTaskStep,
    submitted: list[bool],
) -> None:
    value = _text_box_value(text_box)
    if step.response_kind == "short_text" and value.endswith(("\n", "\r")):
        text_box.text = value.rstrip("\r\n")
        submitted[0] = True
        return
    if len(value) > step.maximum_text_length:
        text_box.text = value[: step.maximum_text_length]


def _text_box_value(text_box: Any | None, *, fallback: str = "") -> str:
    if text_box is None:
        return fallback
    value = getattr(text_box, "text", fallback)
    return str(value)


def _draw_step(
    *,
    visual: Any,
    window: Any,
    step: ResolvedTaskStep,
    item_stimuli: dict[str, Any],
    selected_item_ids: list[str],
    response_text: str,
    validation_message: str | None,
    text_box: Any | None = None,
) -> None:
    window_height = _window_height(window)
    exact_primary_text = None
    if step.prompt_position_px is not None:
        exact_primary_text = step.prompt or step.body or step.heading
    if step.heading and exact_primary_text != step.heading:
        visual.TextStim(
            window,
            text=step.heading,
            font="Arial",
            units="pix",
            height=max(28.0, window_height * 0.042),
            pos=(0, window_height * 0.38),
            wrapWidth=_window_width(window) * 0.88,
            color="white",
            autoLog=False,
        ).draw()
    body = exact_primary_text or step.body or step.prompt
    if body:
        prompt_position = step.prompt_position_px or (0, window_height * 0.27)
        visual.TextStim(
            window,
            text=body,
            font="Arial",
            units="pix",
            height=step.prompt_height_px or max(22.0, window_height * 0.031),
            pos=prompt_position,
            wrapWidth=_window_width(window) * 0.9,
            color="white",
            autoLog=False,
        ).draw()
    if (
        exact_primary_text is not None
        and step.prompt
        and step.body
        and step.prompt != step.body
    ):
        visual.TextStim(
            window,
            text=step.body,
            font="Arial",
            units="pix",
            height=max(20.0, window_height * 0.027),
            pos=(0, window_height * 0.29),
            wrapWidth=_window_width(window) * 0.9,
            color="white",
            autoLog=False,
        ).draw()
    if (
        step.prompt
        and step.body
        and exact_primary_text is None
        and step.prompt != step.body
    ):
        visual.TextStim(
            window,
            text=step.prompt,
            font="Arial",
            units="pix",
            height=step.prompt_height_px or max(22.0, window_height * 0.031),
            pos=(0, window_height * 0.18),
            wrapWidth=_window_width(window) * 0.9,
            color="white",
            autoLog=False,
        ).draw()
    for item in step.items:
        item_stimuli[item.item_id].draw()
        if item.item_id in selected_item_ids:
            visual.TextStim(
                window,
                text="[selected]",
                font="Arial",
                units="pix",
                height=max(16.0, item.text_height_px * 0.55),
                pos=(
                    item.position_px[0],
                    item.position_px[1] - (_item_hitbox(item)[1] / 2.0) - 14.0,
                ),
                color="white",
                autoLog=False,
            ).draw()
    if text_box is not None:
        text_box.draw()
        visual.TextStim(
            window,
            text="Submit",
            font="Arial",
            units="pix",
            height=max(20.0, window_height * 0.027),
            pos=_text_submit_position(window),
            color="white",
            autoLog=False,
        ).draw()
    elif step.response_kind in _TEXT_RESPONSE_KINDS:
        display_value = response_text
        if step.response_kind == "numeric" and not display_value:
            display_value = "Enter a number"
        elif not display_value:
            display_value = "Type your response"
        visual.TextStim(
            window,
            text=display_value,
            font="Arial",
            units="pix",
            height=max(22.0, window_height * 0.03),
            pos=(0, -window_height * 0.14),
            wrapWidth=_window_width(window) * 0.82,
            color="white",
            autoLog=False,
        ).draw()
    footer = _footer_text(step) if step.show_footer else ""
    if validation_message:
        footer = f"{validation_message}\n{footer}"
    if footer:
        visual.TextStim(
            window,
            text=footer,
            font="Arial",
            units="pix",
            height=max(16.0, window_height * 0.022),
            pos=(0, -window_height * 0.42),
            wrapWidth=_window_width(window) * 0.9,
            color="white",
            autoLog=False,
        ).draw()


def _handle_keys(
    *,
    keyboard: Any,
    step: ResolvedTaskStep,
    response_text: str,
    selected_item_ids: list[str],
    native_text_input: bool = False,
) -> _KeyResult:
    text_input = step.response_kind in _TEXT_RESPONSE_KINDS
    key_list = None if text_input else _key_list_for_step(step)
    keys = keyboard.getKeys(keyList=key_list, waitRelease=False, clear=True)
    submitted_key: str | None = None
    response_key: str | None = None
    key_rt: float | None = None
    key_duration: float | None = None
    for key in keys:
        key_name = str(getattr(key, "name", key)).lower()
        if key_name == "escape":
            return {
                "aborted": True,
                "submitted_key": None,
                "response_key": None,
                "key_rt": None,
                "key_duration": None,
                "response_text": response_text,
            }
        if text_input:
            if key_name in {"return", "enter", step.submit_key.lower()}:
                if not (native_text_input and step.response_kind == "long_text"):
                    submitted_key = key_name
                    key_rt = _optional_float(getattr(key, "rt", None))
                    key_duration = _optional_float(getattr(key, "duration", None))
                continue
            if native_text_input:
                continue
            response_text = _updated_text(
                response_text,
                key_name,
                maximum_length=step.maximum_text_length,
            )
            continue
        if step.response_kind == "raw_key" and key_name in step.allowed_keys:
            submitted_key = key_name
            key_rt = _optional_float(getattr(key, "rt", None))
            key_duration = _optional_float(getattr(key, "duration", None))
            continue
        continue_keys = step.allowed_keys or (step.continue_key,)
        if step.response_kind in {"continue", "none"} and key_name in continue_keys:
            submitted_key = key_name
            key_rt = _optional_float(getattr(key, "rt", None))
            key_duration = _optional_float(getattr(key, "duration", None))
            continue
        if step.response_kind in _CHOICE_RESPONSE_KINDS and key_name in step.allowed_keys:
            response_key = key_name
            key_rt = _optional_float(getattr(key, "rt", None))
            key_duration = _optional_float(getattr(key, "duration", None))
            continue
        if step.response_kind == "multiple_choice" and key_name == step.submit_key:
            submitted_key = key_name
            key_rt = _optional_float(getattr(key, "rt", None))
            key_duration = _optional_float(getattr(key, "duration", None))
            continue
        if (
            step.response_kind in _CHOICE_RESPONSE_KINDS
            and step.submission_mode == "explicit"
            and key_name == step.submit_key
        ):
            submitted_key = key_name
            key_rt = _optional_float(getattr(key, "rt", None))
            key_duration = _optional_float(getattr(key, "duration", None))
    return {
        "aborted": False,
        "submitted_key": submitted_key,
        "response_key": response_key,
        "key_rt": key_rt,
        "key_duration": key_duration,
        "response_text": response_text,
    }


def _completed_input(
    step: ResolvedTaskStep,
    *,
    key: str,
    selected_item_ids: list[str],
    response_text: str,
    reaction_time_s: float,
    displayed_item_ids: tuple[str, ...],
) -> TaskEngineInput | None:
    if step.response_kind in {"continue", "none", "raw_key"}:
        return _task_input(
            step,
            key=key,
            reaction_time_s=reaction_time_s,
            displayed_item_ids=displayed_item_ids,
        )
    if step.response_kind in _CHOICE_RESPONSE_KINDS:
        if not _selection_count_is_valid(step, selected_item_ids):
            return None
        return _task_input(
            step,
            key=key,
            selected_item_ids=tuple(selected_item_ids),
            reaction_time_s=reaction_time_s,
            displayed_item_ids=displayed_item_ids,
        )
    if step.response_kind in {"short_text", "long_text"}:
        if step.required and not response_text.strip():
            return None
        return _task_input(
            step,
            key=key,
            text_value=response_text,
            reaction_time_s=reaction_time_s,
            displayed_item_ids=displayed_item_ids,
        )
    if step.response_kind == "numeric":
        if not response_text.strip() and not step.required:
            return _task_input(
                step,
                key=key,
                reaction_time_s=reaction_time_s,
                displayed_item_ids=displayed_item_ids,
            )
        try:
            numeric_value = float(response_text)
        except ValueError:
            return None
        if step.numeric_minimum is not None and numeric_value < step.numeric_minimum:
            return None
        if step.numeric_maximum is not None and numeric_value > step.numeric_maximum:
            return None
        if (
            step.numeric_step is not None
            and step.numeric_minimum is not None
            and not _is_numeric_step_aligned(
                numeric_value,
                minimum=step.numeric_minimum,
                step=step.numeric_step,
            )
        ):
            return None
        return _task_input(
            step,
            key=key,
            text_value=response_text,
            numeric_value=numeric_value,
            reaction_time_s=reaction_time_s,
            displayed_item_ids=displayed_item_ids,
        )
    return None


def _task_input(
    step: ResolvedTaskStep,
    *,
    aborted: bool = False,
    timed_out: bool = False,
    key: str | None = None,
    selected_item_ids: tuple[str, ...] = (),
    text_value: str | None = None,
    numeric_value: float | None = None,
    mouse_position_px: tuple[float, float] | None = None,
    mouse_button: int | None = None,
    reaction_time_s: float | None = None,
    key_reaction_time_s: float | None = None,
    key_duration_s: float | None = None,
    displayed_item_ids: tuple[str, ...] = (),
) -> TaskEngineInput:
    return TaskEngineInput(
        aborted=aborted,
        timed_out=timed_out,
        key=key,
        selected_item_ids=selected_item_ids,
        text_value=text_value,
        numeric_value=numeric_value,
        mouse_position_px=mouse_position_px,
        mouse_button=mouse_button,
        reaction_time_s=reaction_time_s,
        key_reaction_time_s=key_reaction_time_s,
        key_duration_s=key_duration_s,
        displayed_item_ids=displayed_item_ids,
    )


def _new_mouse_click(mouse: Any, previous_buttons: tuple[int, ...]) -> _MouseClick:
    buttons = tuple(int(value) for value in mouse.getPressed())
    button: int | None = None
    if buttons != previous_buttons:
        button = next(
            (index for index, value in enumerate(buttons) if value and not previous_buttons[index]),
            None,
        )
    raw_position = mouse.getPos()
    position = (float(raw_position[0]), float(raw_position[1]))
    return {"buttons": buttons, "button": button, "position": position}


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _item_at_position(
    items: tuple[ResolvedTaskItem, ...],
    *,
    stimuli: dict[str, Any] | None = None,
    x: float,
    y: float,
) -> ResolvedTaskItem | None:
    for item in reversed(items):
        if not item.selectable:
            continue
        stimulus = (stimuli or {}).get(item.item_id)
        contains = getattr(stimulus, "contains", None)
        if callable(contains):
            try:
                if bool(contains((x, y), units="pix")):
                    return item
                continue
            except TypeError:
                if bool(contains((x, y))):
                    return item
                continue
        width, height = _item_hitbox(item)
        if (
            abs(x - item.position_px[0]) <= width / 2.0
            and abs(y - item.position_px[1]) <= height / 2.0
        ):
            return item
    return None


def _point_in_box(
    point: tuple[float, float],
    *,
    box_position: tuple[float, float],
    size: tuple[float, float],
) -> bool:
    return (
        abs(point[0] - box_position[0]) <= size[0] / 2.0
        and abs(point[1] - box_position[1]) <= size[1] / 2.0
    )


def _text_submit_position(window: Any) -> tuple[float, float]:
    return (0.0, -_window_height(window) * 0.32)


def _text_submit_size(window: Any) -> tuple[float, float]:
    return (_window_width(window) * 0.14, _window_height(window) * 0.07)


def _item_hitbox(item: ResolvedTaskItem) -> tuple[float, float]:
    if item.size_px is not None:
        return (max(1.0, item.size_px[0]), max(1.0, item.size_px[1]))
    text_width = max(item.text_height_px * 2.0, len(item.text or "") * item.text_height_px * 0.65)
    return (text_width, item.text_height_px * 1.8)


def _toggle_selection(selected_item_ids: list[str], item_id: str) -> None:
    if item_id in selected_item_ids:
        selected_item_ids.remove(item_id)
    else:
        selected_item_ids.append(item_id)


def _selection_count_is_valid(step: ResolvedTaskStep, selected_item_ids: list[str]) -> bool:
    if len(selected_item_ids) < step.minimum_selections:
        return False
    return step.maximum_selections is None or len(selected_item_ids) <= step.maximum_selections


def _validation_message(
    step: ResolvedTaskStep,
    selected_item_ids: list[str],
    response_text: str,
) -> str:
    if step.response_kind == "multiple_choice":
        if len(selected_item_ids) < step.minimum_selections:
            return f"Select at least {step.minimum_selections} option(s)."
        if step.maximum_selections is not None:
            return f"Select no more than {step.maximum_selections} option(s)."
    if step.response_kind == "numeric":
        try:
            numeric_value = float(response_text)
        except ValueError:
            return "Enter a valid number."
        if step.numeric_minimum is not None and numeric_value < step.numeric_minimum:
            return f"Enter a value of at least {step.numeric_minimum:g}."
        if step.numeric_maximum is not None and numeric_value > step.numeric_maximum:
            return f"Enter a value no greater than {step.numeric_maximum:g}."
        if (
            step.numeric_step is not None
            and step.numeric_minimum is not None
            and not _is_numeric_step_aligned(
                numeric_value,
                minimum=step.numeric_minimum,
                step=step.numeric_step,
            )
        ):
            return f"Enter a value in increments of {step.numeric_step:g}."
    return "A response is required."


def _key_list_for_step(step: ResolvedTaskStep) -> list[str]:
    keys = {"escape"}
    if step.duration_s is not None and step.response_kind == "none":
        return sorted(keys)
    if step.response_kind == "raw_key":
        keys.update(step.allowed_keys)
    elif step.response_kind in {"continue", "none"}:
        keys.update(step.allowed_keys or (step.continue_key,))
    elif step.response_kind in _CHOICE_RESPONSE_KINDS:
        keys.update(step.allowed_keys)
        if step.submission_mode == "explicit":
            keys.add(step.submit_key)
    return sorted(keys)


def _updated_text(value: str, key_name: str, *, maximum_length: int) -> str:
    if key_name == "backspace":
        return value[:-1]
    if key_name == "space":
        return value + " " if len(value) < maximum_length else value
    if key_name in {"tab", "escape", "return", "enter", "left", "right", "up", "down"}:
        return value
    normalized = _text_for_key(key_name)
    if normalized is None or len(value) >= maximum_length:
        return value
    return value + normalized


def _text_for_key(key_name: str) -> str | None:
    replacements = {
        "comma": ",",
        "period": ".",
        "minus": "-",
        "slash": "/",
        "apostrophe": "'",
        "semicolon": ";",
        "equal": "=",
        "num_decimal": ".",
        "num_subtract": "-",
    }
    if key_name in replacements:
        return replacements[key_name]
    if key_name.startswith("num_") and key_name[4:].isdigit():
        return key_name[4:]
    if len(key_name) == 1 and key_name.isprintable():
        return key_name
    return None


def _is_numeric_step_aligned(value: float, *, minimum: float, step: float) -> bool:
    offset_steps = (value - minimum) / step
    return abs(offset_steps - round(offset_steps)) <= 1e-9


def _footer_text(step: ResolvedTaskStep) -> str:
    if step.duration_s is not None and step.response_kind == "none":
        return "Press Escape to abort."
    if step.response_kind in {"continue", "none"} and step.duration_s is None:
        continue_keys = step.allowed_keys or (step.continue_key,)
        key_text = ", ".join(key.title() for key in continue_keys)
        return f"Press {key_text} to continue. Press Escape to abort."
    if step.response_kind == "raw_key":
        keys = ", ".join(key.title() for key in step.allowed_keys)
        return f"Respond with {keys}. Press Escape to abort."
    if step.response_kind == "multiple_choice":
        if step.submission_mode == "immediate":
            return "Select the requested option(s). Press Escape to abort."
        return f"Select option(s), then press {step.submit_key.title()}. Press Escape to abort."
    if step.response_kind == "long_text":
        return "Type your response, then select Submit. Press Escape to abort."
    if step.response_kind == "short_text":
        return "Type your response, then press Return or select Submit. Press Escape to abort."
    if step.response_kind in _TEXT_RESPONSE_KINDS:
        return f"Type your response, then press {step.submit_key.title()}. Press Escape to abort."
    if step.response_kind in _CHOICE_RESPONSE_KINDS:
        if step.submission_mode == "explicit":
            return f"Select an option, then press {step.submit_key.title()}. Press Escape to abort."
        return "Select an option. Press Escape to abort."
    return "Press Escape to abort."


def _window_width(window: Any) -> float:
    size = getattr(window, "size", (1280, 720))
    return float(size[0])


def _window_height(window: Any) -> float:
    size = getattr(window, "size", (1280, 720))
    return float(size[1])
