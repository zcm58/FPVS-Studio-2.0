"""Unit tests for PsychoPy engine launch wiring and timing enforcement."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from PIL import Image

from fpvs_studio.core.compiler import compile_run_spec
from fpvs_studio.core.display_geometry import visual_angle_width_px
from fpvs_studio.core.enums import (
    ImageGeometryMode,
    PresentationUnit,
    StimulusModality,
    StimulusTransform,
)
from fpvs_studio.core.run_spec import FixationEvent, TriggerEvent
from fpvs_studio.engines import psychopy_window as psychopy_window_module
from fpvs_studio.engines.graphics_readiness import (
    BudgetObservationStatus,
    GraphicsReadinessStatus,
)
from fpvs_studio.engines.psychopy_engine import PsychoPyEngine
from fpvs_studio.engines.psychopy_stimuli import (
    ConditionResourceCleanupError,
    release_stimuli,
)
from fpvs_studio.engines.psychopy_text_screens import show_text_screen
from fpvs_studio.triggers.base import TriggerBackend


class _FakeWindow:
    def __init__(
        self,
        *,
        flip_times: list[float] | None = None,
        events: list[tuple[str, object]] | None = None,
        raise_on_flip_index: int | None = None,
        flip_return_none_indices: set[int] | None = None,
        actual_frame_rate: float | None = 60.0,
        **kwargs,
    ) -> None:
        self.kwargs = kwargs
        self.recordFrameIntervals = False
        self.frameIntervals: list[float] = []
        self.size = kwargs.get("size", [1920, 1080])
        self.monitor = None
        self.events = events if events is not None else []
        self.raise_on_flip_index = raise_on_flip_index
        self.flip_return_none_indices = flip_return_none_indices or set()
        self._flip_times = list(flip_times or [])
        self._flip_index = 0
        self._last_flip_time = 0.0
        self._call_on_flip: list[tuple[object, tuple[object, ...]]] = []
        self.callback_names: list[str] = []
        self.actual_frame_rate = actual_frame_rate
        self.actual_frame_rate_kwargs: dict[str, object] | None = None
        self.closed = False

    @property
    def last_flip_time(self) -> float:
        return self._last_flip_time

    def flip(self) -> float | None:
        self.events.append(("flip", self._flip_index))
        if self._flip_index == self.raise_on_flip_index:
            raise RuntimeError("flip failed")
        completed_flip_index = self._flip_index
        previous_flip_time = self._last_flip_time
        if self._flip_index < len(self._flip_times):
            self._last_flip_time = self._flip_times[self._flip_index]
        else:
            self._last_flip_time += 1.0 / 60.0
        if self.recordFrameIntervals and self._flip_index > 0:
            self.frameIntervals.append(self._last_flip_time - previous_flip_time)
        self._flip_index += 1
        pending_callbacks = list(self._call_on_flip)
        self._call_on_flip.clear()
        for callback, args in pending_callbacks:
            callback(*args)
        if completed_flip_index in self.flip_return_none_indices:
            return None
        return self._last_flip_time

    def callOnFlip(self, callback: object, *args: object) -> None:
        self.events.append(("callOnFlip", args))
        self.callback_names.append(getattr(callback, "__name__", type(callback).__name__))
        self._call_on_flip.append((callback, args))

    def clearBuffer(self) -> None:
        self.events.append(("clearBuffer", self._flip_index))

    def close(self) -> None:
        self.closed = True
        self._call_on_flip.clear()

    def getActualFrameRate(self, **kwargs) -> float | None:  # noqa: N802
        self.actual_frame_rate_kwargs = kwargs
        return self.actual_frame_rate


class _FakeClock:
    def __init__(self, window: _FakeWindow) -> None:
        self._window = window
        self._offset = window.last_flip_time

    def reset(self) -> None:
        self._offset = self._window.last_flip_time
        return None

    def getTime(self) -> float:
        return self._window.last_flip_time - self._offset

    def getLastResetTime(self) -> float:  # noqa: N802
        return self._offset


class _FakeKeyboard:
    def __init__(
        self,
        window: _FakeWindow,
        key_batches: list[list[object]] | None = None,
        backend: str = "ptb",
    ) -> None:
        self.clock = _FakeClock(window)
        self._key_batches = list(key_batches or [])
        self._backend = backend

    def clearEvents(self) -> None:
        return None

    def getBackend(self) -> str:  # noqa: N802
        return self._backend

    def getKeys(
        self,
        *,
        keyList: list[str] | None = None,
        waitRelease: bool = False,
        clear: bool = True,
    ) -> list[object]:
        if not self._key_batches:
            return []
        keys = self._key_batches.pop(0)
        if keyList is None:
            return keys
        return [key for key in keys if getattr(key, "name", str(key)) in keyList]


class _FakeStim:
    def __init__(self, *args, **kwargs) -> None:
        self.lineColor = kwargs.get("lineColor")
        self.draw_count = 0

    def draw(self) -> None:
        self.draw_count += 1
        return None


class _RecordingTriggerBackend(TriggerBackend):
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def connect(self) -> None:
        return None

    def send_trigger(
        self,
        code: int,
        *,
        frame_index: int | None = None,
        label: str | None = None,
        time_s: float | None = None,
    ) -> None:
        self.records.append(
            {
                "code": code,
                "frame_index": frame_index,
                "label": label,
                "time_s": time_s,
            }
        )

    def reset(self) -> None:
        return None

    def close(self) -> None:
        return None


def _build_fake_psychopy(
    captures: dict[str, object],
    *,
    flip_times: list[float],
    key_batches: list[list[object]] | None = None,
    raise_on_flip_index: int | None = None,
    flip_return_none_indices: set[int] | None = None,
    record_psychopy_warnings: bool = False,
    actual_frame_rate: float | None = 60.0,
    keyboard_backend: str = "ptb",
) -> object:
    events: list[tuple[str, object]] = []
    image_stims: list[Any] = []
    text_stims: list[Any] = []
    shape_stims: list[Any] = []
    captures["events"] = events
    captures["image_stims"] = image_stims
    captures["text_stims"] = text_stims
    captures["shape_stims"] = shape_stims

    class _FakeShapeStim(_FakeStim):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            shape_stims.append(self)

    class _FakeImageStim(_FakeStim):
        def __init__(self, *args, image: str, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.image = image
            self.size = kwargs.get("size")
            self.flipHoriz = kwargs.get("flipHoriz")
            self.flipVert = kwargs.get("flipVert")
            self.ori = kwargs.get("ori")
            self.clear_textures_count = 0
            image_stims.append(self)
            events.append(("image", image))

        def clearTextures(self) -> None:
            self.clear_textures_count += 1
            events.append(("clear", self.image))

    class _FakeTextStim(_FakeStim):
        def __init__(self, *args, text: str, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.text = text
            self.font = kwargs.get("font")
            self.pos = kwargs.get("pos")
            self.height = kwargs.get("height")
            self.color = kwargs.get("color")
            self.flipHoriz = kwargs.get("flipHoriz")
            self.flipVert = kwargs.get("flipVert")
            self.ori = kwargs.get("ori")
            text_stims.append(self)
            events.append(("text", text))

    def _fake_window(**kwargs):
        captures["window_kwargs"] = kwargs
        window = _FakeWindow(
            flip_times=flip_times,
            events=events,
            raise_on_flip_index=raise_on_flip_index,
            flip_return_none_indices=flip_return_none_indices,
            actual_frame_rate=actual_frame_rate,
            **kwargs,
        )
        captures["window"] = window
        return window

    def _fake_keyboard():
        keyboard = _FakeKeyboard(
            captures["window"],
            key_batches=key_batches,
            backend=keyboard_backend,
        )
        captures["keyboard"] = keyboard
        return keyboard

    fake_visual = SimpleNamespace(
        Window=_fake_window,
        ShapeStim=_FakeShapeStim,
        ImageStim=_FakeImageStim,
        TextStim=_FakeTextStim,
    )
    fake_core = SimpleNamespace(Clock=lambda: _FakeClock(captures["window"]))
    fake_logging = SimpleNamespace(
        defaultClock=SimpleNamespace(getLastResetTime=lambda: 0.0),
        warning=(
            (lambda message: events.append(("psychopy_warning", message)))
            if record_psychopy_warnings
            else logging.warning
        ),
    )
    return SimpleNamespace(
        visual=fake_visual,
        core=fake_core,
        hardware=SimpleNamespace(keyboard=SimpleNamespace(Keyboard=_fake_keyboard)),
        logging=fake_logging,
        __version__="fake-psychopy",
    )


def _build_flip_times(
    *,
    total_flips: int,
    interval_s: float,
    long_interval_flip_indices: set[int] | None = None,
    long_interval_s: float = 0.05,
) -> list[float]:
    flip_times: list[float] = []
    current = 0.0
    long_interval_set = long_interval_flip_indices or set()
    for flip_index in range(total_flips):
        step = long_interval_s if flip_index in long_interval_set else interval_s
        current += step
        flip_times.append(current)
    return flip_times


def _patch_fake_psychopy(monkeypatch, engine: PsychoPyEngine, fake_psychopy: object) -> None:
    monkeypatch.setattr(
        psychopy_window_module,
        "_detect_fullscreen_size_px",
        lambda _display_index: (1920, 1080),
    )
    engine._psychopy = fake_psychopy
    engine._visual = fake_psychopy.visual
    engine._core = fake_psychopy.core
    engine._keyboard_module = fake_psychopy.hardware.keyboard
    engine._psychopy_logging = fake_psychopy.logging
    monkeypatch.setattr(engine, "_load_psychopy", lambda: fake_psychopy)


def test_measure_refresh_hz_uses_fullscreen_psychopy_probe_and_closes_window(monkeypatch) -> None:
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(
        captures,
        flip_times=[],
        actual_frame_rate=143.92,
    )
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    measured_hz = engine.measure_refresh_hz(runtime_options={"display_index": 1})

    assert measured_hz == pytest.approx(143.92)
    assert captures["window_kwargs"] == {
        "fullscr": True,
        "screen": 1,
        "allowGUI": False,
        "waitBlanking": True,
        "color": "black",
        "units": "pix",
        "size": [1920, 1080],
        "checkTiming": False,
    }
    window = captures["window"]
    assert isinstance(window, _FakeWindow)
    assert window.actual_frame_rate_kwargs == {
        "nIdentical": 20,
        "nMaxFrames": 240,
        "nWarmUpFrames": 60,
        "threshold": 0.5,
        "infoMsg": "FPVS Studio is measuring this display's refresh rate...",
    }
    assert window.closed is True


def test_measure_refresh_hz_rejects_unstable_measurement_and_closes_window(monkeypatch) -> None:
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(
        captures,
        flip_times=[],
        actual_frame_rate=None,
    )
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    with pytest.raises(RuntimeError, match="could not obtain a stable"):
        engine.measure_refresh_hz()

    window = captures["window"]
    assert isinstance(window, _FakeWindow)
    assert window.closed is True


def _tiny_run_spec(sample_project, sample_project_root):
    sample_project.settings.fixation_task.enabled = False
    sample_project.settings.fixation_task.accuracy_task_enabled = False
    sample_project.conditions[0].oddball_cycle_repeats_per_sequence = 1
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="timing-smoke",
    )
    return run_spec.model_copy(update={"pre_stream_fixation_frames": 0})


def _two_event_run_spec(sample_project, sample_project_root, *, duplicate_image: bool):
    run_spec = _tiny_run_spec(sample_project, sample_project_root)
    first_event = run_spec.stimulus_sequence[0].model_copy(
        update={"sequence_index": 0, "on_start_frame": 0, "on_frames": 1, "off_frames": 0}
    )
    second_source = next(
        event
        for event in run_spec.stimulus_sequence
        if duplicate_image or event.image_path != first_event.image_path
    )
    second_event = second_source.model_copy(
        update={
            "sequence_index": 1,
            "image_path": first_event.image_path if duplicate_image else second_source.image_path,
            "stimulus_id": first_event.stimulus_id
            if duplicate_image
            else second_source.stimulus_id,
            "on_start_frame": 1,
            "on_frames": 1,
            "off_frames": 0,
        }
    )
    run_spec.stimulus_sequence = [first_event, second_event]
    run_spec.fixation_events = []
    run_spec.display.total_frames = 2
    return run_spec


def _two_word_event_run_spec(sample_project):
    sample_project.settings.fixation_task.enabled = False
    sample_project.settings.fixation_task.accuracy_task_enabled = False
    sample_project.conditions[0].oddball_cycle_repeats_per_sequence = 1
    sample_project.stimulus_sets[0] = sample_project.stimulus_sets[0].model_copy(
        update={
            "modality": StimulusModality.WORD,
            "source_dir": None,
            "resolution": None,
            "image_count": 0,
            "words": ["cat", "dog"],
        }
    )
    sample_project.stimulus_sets[1] = sample_project.stimulus_sets[1].model_copy(
        update={
            "modality": StimulusModality.WORD,
            "source_dir": None,
            "resolution": None,
            "image_count": 0,
            "words": ["tool"],
        }
    )
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        run_id="word-timing-smoke",
    )
    run_spec.stimulus_sequence = [
        run_spec.stimulus_sequence[0].model_copy(
            update={"sequence_index": 0, "on_start_frame": 0, "on_frames": 1, "off_frames": 0}
        ),
        run_spec.stimulus_sequence[1].model_copy(
            update={"sequence_index": 1, "on_start_frame": 1, "on_frames": 1, "off_frames": 0}
        ),
    ]
    run_spec.fixation_events = []
    run_spec.display.total_frames = 2
    return run_spec


def _image_stims(captures: dict[str, object]) -> list[Any]:
    image_stims = captures["image_stims"]
    assert isinstance(image_stims, list)
    return image_stims


def _text_stims(captures: dict[str, object]) -> list[Any]:
    text_stims = captures["text_stims"]
    assert isinstance(text_stims, list)
    return text_stims


def _events(captures: dict[str, object]) -> list[tuple[str, object]]:
    events = captures["events"]
    assert isinstance(events, list)
    return events


def _graphics_readiness_result(
    status: GraphicsReadinessStatus,
    *reasons: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        reasons=reasons,
        renderer=SimpleNamespace(
            vendor="NVIDIA Corporation",
            renderer="NVIDIA GeForce GTX 1660 Ti/PCIe/SSE2",
            version="4.6",
            classification=SimpleNamespace(value="hardware"),
        ),
        estimate=SimpleNamespace(
            estimated_gpu_bytes=1_000,
            conservative_gpu_bytes=1_500,
        ),
        budget_status=BudgetObservationStatus.VERIFIED,
        adapter_assessments=(),
        system_memory_assessment=None,
    )


def test_psychopy_engine_opens_fullscreen_window_for_launched_session(monkeypatch) -> None:
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])

    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.open_session(
            runtime_options={
                "fullscreen": True,
                "display_index": 2,
            }
        )
    finally:
        engine.close_session()

    assert captures["window_kwargs"] == {
        "fullscr": True,
        "screen": 2,
        "allowGUI": False,
        "waitBlanking": True,
        "color": "black",
        "units": "pix",
        "size": [1920, 1080],
    }


def test_psychopy_engine_preserves_windowed_session_size(monkeypatch) -> None:
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])

    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.open_session(
            runtime_options={
                "fullscreen": False,
                "windowed_size_px": (1280, 720),
            }
        )
    finally:
        engine.close_session()

    assert captures["window_kwargs"] == {
        "fullscr": False,
        "screen": 0,
        "allowGUI": True,
        "waitBlanking": True,
        "color": "black",
        "units": "pix",
        "size": [1280, 720],
    }


@pytest.mark.parametrize("display_api_module", ["pyglet.display", "pyglet.canvas"])
def test_fullscreen_window_uses_selected_pyglet_screen_size(
    monkeypatch,
    display_api_module: str,
) -> None:
    screens = [
        SimpleNamespace(width=1920, height=1080),
        SimpleNamespace(width=2560, height=1440),
    ]
    fake_display_module = SimpleNamespace(
        get_display=lambda: SimpleNamespace(get_screens=lambda: screens)
    )

    def _fake_import(module_name: str) -> object:
        if module_name == display_api_module:
            return fake_display_module
        raise ModuleNotFoundError(module_name)

    monkeypatch.setattr(psychopy_window_module, "import_module", _fake_import)

    window_kwargs = psychopy_window_module.build_window_kwargs(
        {"fullscreen": True, "display_index": 1}
    )

    assert window_kwargs["screen"] == 1
    assert window_kwargs["size"] == [2560, 1440]


def test_fullscreen_window_falls_back_to_psychopy_when_screen_query_fails(
    monkeypatch,
    caplog,
) -> None:
    def _fail_import(_module_name: str) -> object:
        raise RuntimeError("display enumeration failed")

    monkeypatch.setattr(psychopy_window_module, "import_module", _fail_import)

    with caplog.at_level(logging.WARNING, logger=psychopy_window_module.__name__):
        window_kwargs = psychopy_window_module.build_window_kwargs(
            {"fullscreen": True, "display_index": 1}
        )

    assert "size" not in window_kwargs
    assert "PsychoPy will determine the actual fullscreen size" in caplog.text


def test_refresh_probe_uses_fullscreen_size_when_launch_is_windowed(monkeypatch) -> None:
    monkeypatch.setattr(
        psychopy_window_module,
        "_detect_fullscreen_size_px",
        lambda display_index: (2560, 1440) if display_index == 1 else None,
    )

    window_kwargs = psychopy_window_module.build_refresh_probe_window_kwargs(
        {
            "fullscreen": False,
            "display_index": 1,
            "windowed_size_px": (1280, 720),
        }
    )

    assert window_kwargs["fullscr"] is True
    assert window_kwargs["allowGUI"] is False
    assert window_kwargs["size"] == [2560, 1440]


def test_psychopy_engine_closes_partial_session_when_keyboard_creation_fails(monkeypatch) -> None:
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])

    def _fail_keyboard_creation():
        raise RuntimeError("keyboard creation failed")

    fake_psychopy.hardware.keyboard.Keyboard = _fail_keyboard_creation
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    with pytest.raises(RuntimeError, match="keyboard creation failed"):
        engine.open_session(runtime_options={"fullscreen": False})

    window = captures["window"]
    assert isinstance(window, _FakeWindow)
    assert window.closed is True
    assert engine._window is None
    assert engine._keyboard is None


def test_psychopy_engine_uses_final_thanks_copy_and_preserves_duration(monkeypatch) -> None:
    captures: dict[str, object] = {}
    engine = PsychoPyEngine()

    def _capture_text_screen(**kwargs) -> bool:
        captures.update(kwargs)
        return False

    monkeypatch.setattr(engine, "_show_text_screen", _capture_text_screen)
    engine._runtime_options = {"completion_screen_seconds": 0.5}

    aborted = engine.show_completion_screen(
        completed_condition_count=2,
        total_condition_count=2,
        was_aborted=False,
    )

    assert aborted is False
    assert captures["heading"] == "All done!"
    assert captures["body"] == "Thanks for your time!\n\nCompleted all 2 conditions."
    assert captures["countdown_seconds"] == 0.5


def test_text_screen_uses_custom_space_begin_prompt() -> None:
    captured_text: list[str] = []

    class _PromptStim:
        def __init__(self, *args, text: str, **kwargs) -> None:
            captured_text.append(text)

        def draw(self) -> None:
            return None

    class _PromptKeyboard:
        def clearEvents(self) -> None:
            return None

        def getKeys(self, **kwargs) -> list[object]:
            return [SimpleNamespace(name="space")]

    window = _FakeWindow()
    aborted = show_text_screen(
        visual=SimpleNamespace(TextStim=_PromptStim),
        core=SimpleNamespace(Clock=lambda: _FakeClock(window)),
        window=window,
        keyboard=_PromptKeyboard(),
        is_aborted=lambda: False,
        set_aborted=lambda: None,
        heading="Condition 1 of 1",
        body=None,
        countdown_seconds=None,
        continue_key="space",
        continue_prompt="Press Space to begin.",
    )

    assert aborted is False
    assert "Press Space to begin. Press Escape to abort." in captured_text


def test_psychopy_engine_fixation_tutorial_attempt_returns_hit_with_rt(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _tiny_run_spec(sample_project, sample_project_root)
    run_spec = run_spec.model_copy(
        update={
            "fixation": run_spec.fixation.model_copy(
                update={
                    "accuracy_task_enabled": True,
                    "participant_tutorial_enabled": True,
                    "response_key": "space",
                    "response_window_frames": 60,
                    "response_keys": ["space"],
                }
            )
        }
    )
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(
        captures,
        flip_times=[],
        key_batches=[[], [SimpleNamespace(name="space", rt=0.22)]],
    )
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.open_session(runtime_options={"fullscreen": False})
        result = engine.run_fixation_tutorial_attempt(run_spec, target_delay_seconds=0.0)
    finally:
        engine.close_session()

    assert result.hit is True
    assert result.reaction_time_s == pytest.approx(0.22)
    assert result.aborted is False


def test_psychopy_engine_fixation_tutorial_attempt_returns_miss(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _tiny_run_spec(sample_project, sample_project_root)
    run_spec = run_spec.model_copy(
        update={
            "fixation": run_spec.fixation.model_copy(
                update={
                    "accuracy_task_enabled": True,
                    "participant_tutorial_enabled": True,
                    "response_key": "space",
                    "response_window_frames": 2,
                    "response_keys": ["space"],
                }
            )
        }
    )
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[], key_batches=[[], [], []])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.open_session(runtime_options={"fullscreen": False})
        result = engine.run_fixation_tutorial_attempt(run_spec, target_delay_seconds=0.0)
    finally:
        engine.close_session()

    assert result.hit is False
    assert result.reaction_time_s is None
    assert result.aborted is False


def test_psychopy_engine_preloads_unique_images_before_playback_flip(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=False)
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    events = _events(captures)
    first_flip_index = next(index for index, event in enumerate(events) if event[0] == "flip")
    image_indices = [index for index, event in enumerate(events) if event[0] == "image"]

    assert len(_image_stims(captures)) == 2
    assert image_indices
    assert max(image_indices) < first_flip_index
    window = captures["window"]
    assert isinstance(window, _FakeWindow)
    assert window._flip_index == run_spec.display.total_frames + 1
    assert ("clearBuffer", 0) in events


def test_psychopy_engine_blocks_on_post_upload_gate_before_first_condition_flip(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=False)
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)
    calls: list[str] = []
    context = object()

    def _before(_project_root, _run_spec):
        calls.append("before")
        return context

    def _after(received_context):
        assert received_context is context
        calls.append("after")
        assert len(_image_stims(captures)) == 2
        assert not any(event[0] == "flip" for event in _events(captures))
        raise RuntimeError("post-upload graphics gate rejected")

    monkeypatch.setattr(engine, "_graphics_readiness_before_preparation", _before)
    monkeypatch.setattr(engine, "_graphics_readiness_after_preparation", _after)

    try:
        with pytest.raises(RuntimeError, match="post-upload graphics gate rejected"):
            engine.run_condition(
                run_spec,
                sample_project_root,
                runtime_options={
                    "timing_warmup_frames": 0,
                    "verify_graphics_memory": True,
                },
                trigger_backend=None,
            )
    finally:
        engine.close_session()

    window = captures["window"]
    assert isinstance(window, _FakeWindow)
    assert window._flip_index == 0
    assert calls == ["before", "after"]
    assert [stim.clear_textures_count for stim in _image_stims(captures)] == [1, 1]


def test_psychopy_engine_runs_and_reports_when_graphics_telemetry_is_unverified(
    monkeypatch,
    caplog,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=False)
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)
    readiness = _graphics_readiness_result(
        GraphicsReadinessStatus.UNVERIFIED,
        "No active DXGI adapter budget was identified.",
    )
    context = object()

    monkeypatch.setattr(
        engine,
        "_graphics_readiness_before_preparation",
        lambda _project_root, _run_spec: context,
    )

    def _after(received_context):
        assert received_context is context
        engine._require_graphics_readiness(readiness, phase="after image upload")
        return readiness

    monkeypatch.setattr(engine, "_graphics_readiness_after_preparation", _after)

    try:
        with caplog.at_level(logging.WARNING):
            summary = engine.run_condition(
                run_spec,
                sample_project_root,
                runtime_options={
                    "timing_warmup_frames": 0,
                    "verify_graphics_memory": True,
                },
                trigger_backend=None,
            )
    finally:
        engine.close_session()

    window = captures["window"]
    assert isinstance(window, _FakeWindow)
    assert window._flip_index == run_spec.display.total_frames + 1
    assert summary.aborted is False
    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.graphics_readiness_status == "unverified"
    assert "could not be fully verified" in summary.warnings[0]
    assert "playback will proceed" in caplog.text


def test_psychopy_engine_still_rejects_known_graphics_resource_failure() -> None:
    engine = PsychoPyEngine()
    readiness = _graphics_readiness_result(
        GraphicsReadinessStatus.REJECTED,
        "Measured graphics-memory headroom is insufficient.",
    )

    with pytest.raises(RuntimeError, match="graphics readiness rejected"):
        engine._require_graphics_readiness(readiness, phase="before image upload")


@pytest.mark.parametrize("unverified_phase", ["before", "after"])
def test_psychopy_engine_preserves_unverified_status_across_both_memory_checks(
    unverified_phase: str,
) -> None:
    ready = _graphics_readiness_result(
        GraphicsReadinessStatus.READY,
        "Hardware renderer and memory budgets meet policy.",
    )
    unverified = _graphics_readiness_result(
        GraphicsReadinessStatus.UNVERIFIED,
        f"{unverified_phase} upload telemetry was unavailable.",
    )
    before = unverified if unverified_phase == "before" else ready
    after = unverified if unverified_phase == "after" else ready

    merged = PsychoPyEngine._merge_graphics_readiness(before, after)

    assert merged.status == GraphicsReadinessStatus.UNVERIFIED
    assert merged.reasons == unverified.reasons


def test_psychopy_engine_reuses_prepared_stimulus_within_condition(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    image_stims = _image_stims(captures)
    assert len(image_stims) == 1
    assert image_stims[0].draw_count == 3
    assert image_stims[0].clear_textures_count == 1


def test_psychopy_engine_prepares_and_draws_word_stimuli(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_word_event_run_spec(sample_project)
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    text_stims = _text_stims(captures)
    assert [stim.text for stim in text_stims] == [
        event.text for event in run_spec.stimulus_sequence
    ]
    assert [stim.draw_count for stim in text_stims] == [2, 2]
    assert all(stim.color == "#FFFFFF" for stim in text_stims)
    assert all(stim.font == "Arial" for stim in text_stims)
    assert not _image_stims(captures)


def test_psychopy_engine_releases_word_stimuli_after_playback_error(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_word_event_run_spec(sample_project)
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[], raise_on_flip_index=0)
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        with pytest.raises(RuntimeError, match="flip failed"):
            engine.run_condition(
                run_spec,
                sample_project_root,
                runtime_options={"timing_warmup_frames": 0},
                trigger_backend=None,
            )
    finally:
        engine.close_session()

    assert len(_text_stims(captures)) == 2
    assert engine._active_run_clock is None


def test_psychopy_engine_releases_prepared_stimuli_when_priming_fails(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=False)
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)
    engine.open_session(runtime_options={"fullscreen": False})
    window = captures["window"]
    assert isinstance(window, _FakeWindow)

    def _fail_clear_buffer() -> None:
        raise RuntimeError("clear buffer failed")

    monkeypatch.setattr(window, "clearBuffer", _fail_clear_buffer)

    try:
        with pytest.raises(RuntimeError, match="clear buffer failed"):
            engine.run_condition(
                run_spec,
                sample_project_root,
                runtime_options={"timing_warmup_frames": 0},
                trigger_backend=None,
            )
    finally:
        engine.close_session()

    assert len(_image_stims(captures)) == 2
    assert all(stimulus.clear_textures_count == 1 for stimulus in _image_stims(captures))


def test_psychopy_engine_invalidates_session_when_stimulus_construction_fails(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=False)
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    def _fail_image_stimulus(*args, **kwargs):
        raise RuntimeError("image construction failed")

    monkeypatch.setattr(fake_psychopy.visual, "ImageStim", _fail_image_stimulus)

    with pytest.raises(RuntimeError, match="image construction failed"):
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=None,
        )

    window = captures["window"]
    assert isinstance(window, _FakeWindow)
    assert window.closed is True
    assert engine._window is None


def test_psychopy_engine_sizes_images_from_visual_angle_without_changing_aspect_ratio(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    run_spec.display.stimulus_width_degrees = 8.0
    run_spec.display.viewing_distance_cm = 80.0
    run_spec.display.screen_width_cm = 53.0
    run_spec.display.screen_width_px = 1920
    run_spec.display.use_current_screen_resolution = False
    run_spec = run_spec.model_copy(update={"presentation": None})
    wide_image_path = sample_project_root / "stimuli" / "original-images" / "base-set" / "wide.png"
    wide_image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (200, 100), color=(20, 40, 80)).save(wide_image_path)
    run_spec.stimulus_sequence[0] = run_spec.stimulus_sequence[0].model_copy(
        update={"image_path": "stimuli/original-images/base-set/wide.png"}
    )
    run_spec.stimulus_sequence = [run_spec.stimulus_sequence[0]]
    run_spec.display.total_frames = 1
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={
                "fullscreen": False,
                "timing_warmup_frames": 0,
            },
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    expected_width = visual_angle_width_px(
        degrees=8.0,
        viewing_distance_cm=80.0,
        screen_width_cm=53.0,
        screen_width_px=1920,
    )
    assert _image_stims(captures)[0].size == (expected_width, round(expected_width / 2))


@pytest.mark.parametrize(
    ("transform", "expected_flip_horiz", "expected_flip_vert", "expected_orientation"),
    [
        (StimulusTransform.NONE, False, False, 0.0),
        (StimulusTransform.MIRROR_HORIZONTAL, True, False, 0.0),
        (StimulusTransform.MIRROR_VERTICAL, False, True, 0.0),
        (StimulusTransform.ROT180, False, False, 180.0),
    ],
)
def test_psychopy_engine_applies_runtime_image_transforms_at_preload(
    monkeypatch,
    sample_project,
    sample_project_root,
    transform,
    expected_flip_horiz,
    expected_flip_vert,
    expected_orientation,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    assert run_spec.presentation is not None
    base_presentation = run_spec.presentation.base.model_copy(update={"transform": transform})
    run_spec.presentation = run_spec.presentation.model_copy(update={"base": base_presentation})
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    stimulus = _image_stims(captures)[0]
    assert stimulus.flipHoriz is expected_flip_horiz
    assert stimulus.flipVert is expected_flip_vert
    assert stimulus.ori == expected_orientation
    events = _events(captures)
    assert events.index(("clearBuffer", 0)) < next(
        index for index, event in enumerate(events) if event[0] == "flip"
    )


@pytest.mark.parametrize(
    ("transform", "expected_flip_horiz", "expected_flip_vert", "expected_orientation"),
    [
        (StimulusTransform.NONE, False, False, 0.0),
        (StimulusTransform.MIRROR_HORIZONTAL, True, False, 0.0),
        (StimulusTransform.MIRROR_VERTICAL, False, True, 0.0),
        (StimulusTransform.ROT180, False, False, 180.0),
    ],
)
def test_psychopy_engine_applies_word_transform_and_resolves_height_fraction(
    monkeypatch,
    sample_project,
    transform,
    expected_flip_horiz,
    expected_flip_vert,
    expected_orientation,
) -> None:
    run_spec = _two_word_event_run_spec(sample_project)
    assert run_spec.presentation is not None
    text_spec = run_spec.presentation.base.text
    assert text_spec is not None
    text_spec = text_spec.model_copy(
        update={
            "color": "#12AB34",
            "position_unit": PresentationUnit.WINDOW_HEIGHT_FRACTION,
            "position_x": 0.1,
            "position_y": 0.02,
            "height_unit": PresentationUnit.WINDOW_HEIGHT_FRACTION,
        }
    )
    base_presentation = run_spec.presentation.base.model_copy(
        update={
            "transform": transform,
            "text": text_spec,
        }
    )
    run_spec.presentation = run_spec.presentation.model_copy(update={"base": base_presentation})
    run_spec.stimulus_sequence = [
        event.model_copy(update={"text_height_value": 0.05}) for event in run_spec.stimulus_sequence
    ]
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            Path.cwd(),
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    stimuli = _text_stims(captures)
    assert [stimulus.text for stimulus in stimuli] == [
        event.text for event in run_spec.stimulus_sequence
    ]
    assert all(stimulus.flipHoriz is expected_flip_horiz for stimulus in stimuli)
    assert all(stimulus.flipVert is expected_flip_vert for stimulus in stimuli)
    assert all(stimulus.ori == expected_orientation for stimulus in stimuli)
    assert all(stimulus.font == "Arial" for stimulus in stimuli)
    assert all(stimulus.color == "#12AB34" for stimulus in stimuli)
    assert all(stimulus.height == 54 for stimulus in stimuli)
    assert all(stimulus.pos == (108, 22) for stimulus in stimuli)


def test_psychopy_engine_preloads_distinct_text_height_render_variants(
    monkeypatch,
    sample_project,
) -> None:
    run_spec = _two_word_event_run_spec(sample_project)
    first_event = run_spec.stimulus_sequence[0]
    run_spec.stimulus_sequence = [
        first_event.model_copy(update={"sequence_index": 0, "text_height_value": 1.0}),
        first_event.model_copy(
            update={
                "sequence_index": 1,
                "on_start_frame": 1,
                "text_height_value": 2.0,
            }
        ),
    ]
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            Path.cwd(),
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    stimuli = _text_stims(captures)
    assert len(stimuli) == 2
    assert [stimulus.height for stimulus in stimuli] == [
        visual_angle_width_px(
            degrees=value,
            viewing_distance_cm=run_spec.display.viewing_distance_cm,
            screen_width_cm=run_spec.display.screen_width_cm,
            screen_width_px=run_spec.display.screen_width_px,
        )
        for value in (1.0, 2.0)
    ]
    assert [stimulus.draw_count for stimulus in stimuli] == [2, 2]


def test_psychopy_engine_prioritizes_legacy_width_fraction_for_word_height(
    monkeypatch,
    sample_project,
) -> None:
    run_spec = _two_word_event_run_spec(sample_project)
    assert run_spec.presentation is not None
    text_spec = run_spec.presentation.base.text
    assert text_spec is not None
    text_spec = text_spec.model_copy(update={"legacy_stimulus_width_fraction": 0.25})
    run_spec.presentation = run_spec.presentation.model_copy(
        update={"base": run_spec.presentation.base.model_copy(update={"text": text_spec})}
    )
    run_spec.stimulus_sequence = [
        run_spec.stimulus_sequence[0].model_copy(
            update={"on_frames": 1, "off_frames": 0, "text_height_value": 99.0}
        )
    ]
    run_spec.display.total_frames = 1
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            Path.cwd(),
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    stimulus_width_px = visual_angle_width_px(
        degrees=run_spec.display.stimulus_width_degrees,
        viewing_distance_cm=run_spec.display.viewing_distance_cm,
        screen_width_cm=run_spec.display.screen_width_cm,
        screen_width_px=run_spec.display.screen_width_px,
    )
    assert _text_stims(captures)[0].height == max(1, round(stimulus_width_px * 0.25))


def test_psychopy_engine_resolves_text_degrees_for_height_and_signed_position(
    monkeypatch,
    sample_project,
) -> None:
    run_spec = _two_word_event_run_spec(sample_project)
    assert run_spec.presentation is not None
    text_spec = run_spec.presentation.base.text
    assert text_spec is not None
    text_spec = text_spec.model_copy(
        update={
            "position_unit": PresentationUnit.DEGREES,
            "position_x": 1.0,
            "position_y": -2.0,
            "height_unit": PresentationUnit.DEGREES,
        }
    )
    run_spec.presentation = run_spec.presentation.model_copy(
        update={"base": run_spec.presentation.base.model_copy(update={"text": text_spec})}
    )
    run_spec.stimulus_sequence = [
        run_spec.stimulus_sequence[0].model_copy(
            update={"on_frames": 1, "off_frames": 0, "text_height_value": 1.5}
        )
    ]
    run_spec.display.total_frames = 1
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            Path.cwd(),
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    stimulus = _text_stims(captures)[0]

    def convert(degrees: float) -> int:
        return visual_angle_width_px(
            degrees=degrees,
            viewing_distance_cm=run_spec.display.viewing_distance_cm,
            screen_width_cm=run_spec.display.screen_width_cm,
            screen_width_px=run_spec.display.screen_width_px,
        )

    assert stimulus.height == convert(1.5)
    assert stimulus.pos == (convert(1.0), -convert(2.0))


def test_release_stimuli_discards_texture_ids_and_clears_mapping() -> None:
    class _Stimulus:
        def __init__(self) -> None:
            self._texID = object()
            self._maskID = object()
            self._pixBuffID = object()
            self.clear_textures_count = 0

        def clearTextures(self) -> None:
            self.clear_textures_count += 1

    stimulus = _Stimulus()
    stimuli = {"stimulus": stimulus}

    release_stimuli(stimuli)

    assert stimuli == {}
    assert stimulus.clear_textures_count == 1
    assert not hasattr(stimulus, "_texID")
    assert not hasattr(stimulus, "_maskID")
    assert not hasattr(stimulus, "_pixBuffID")


def test_release_stimuli_suppresses_texture_cleanup_errors(caplog) -> None:
    class _Stimulus:
        def __init__(self) -> None:
            self._texID = object()
            self._maskID = object()
            self._pixBuffID = object()

        def clearTextures(self) -> None:
            raise OSError("OpenGL texture cleanup failed")

    stimulus = _Stimulus()
    stimuli = {"stimulus": stimulus}

    release_stimuli(stimuli)

    assert stimuli == {}
    assert not hasattr(stimulus, "_texID")
    assert not hasattr(stimulus, "_maskID")
    assert not hasattr(stimulus, "_pixBuffID")
    assert "Ignored 1 PsychoPy stimulus texture cleanup error" in caplog.text


def test_psychopy_engine_uses_same_display_size_for_different_square_resolutions(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=False)
    run_spec.display.stimulus_width_degrees = 8.0
    run_spec.display.viewing_distance_cm = 80.0
    run_spec.display.screen_width_cm = 53.0
    run_spec.display.screen_width_px = 1920
    run_spec.display.use_current_screen_resolution = False
    run_spec = run_spec.model_copy(update={"presentation": None})
    base_dir = sample_project_root / "stimuli" / "original-images" / "base-set"
    high_res_path = base_dir / "square-1024.png"
    low_res_path = base_dir / "square-512.png"
    Image.new("RGB", (1024, 1024), color=(20, 40, 80)).save(high_res_path)
    Image.new("RGB", (512, 512), color=(80, 40, 20)).save(low_res_path)
    run_spec.stimulus_sequence[0] = run_spec.stimulus_sequence[0].model_copy(
        update={"image_path": "stimuli/original-images/base-set/square-1024.png"}
    )
    run_spec.stimulus_sequence[1] = run_spec.stimulus_sequence[1].model_copy(
        update={"image_path": "stimuli/original-images/base-set/square-512.png"}
    )
    run_spec.stimulus_sequence = run_spec.stimulus_sequence[:2]
    run_spec.display.total_frames = 2
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={
                "fullscreen": False,
                "timing_warmup_frames": 0,
            },
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    expected_width = visual_angle_width_px(
        degrees=8.0,
        viewing_distance_cm=80.0,
        screen_width_cm=53.0,
        screen_width_px=1920,
    )
    assert [stim.size for stim in _image_stims(captures)] == [
        (expected_width, expected_width),
        (expected_width, expected_width),
    ]


@pytest.mark.parametrize(
    ("mode", "height_degrees", "expected_height_from_width"),
    [
        (ImageGeometryMode.EXACT_BOX, 6.0, False),
        (ImageGeometryMode.CONTAIN, 6.0, True),
        (ImageGeometryMode.NATURAL_ASPECT, None, True),
    ],
)
def test_psychopy_engine_resolves_native_image_geometry_modes(
    monkeypatch,
    sample_project,
    sample_project_root,
    mode,
    height_degrees,
    expected_height_from_width,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    run_spec.display.viewing_distance_cm = 80.0
    run_spec.display.screen_width_cm = 53.0
    run_spec.display.screen_width_px = 1920
    run_spec.display.use_current_screen_resolution = False
    wide_image_path = sample_project_root / "stimuli" / "original-images" / "base-set" / "wide.png"
    wide_image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (200, 100), color=(20, 40, 80)).save(wide_image_path)
    run_spec.stimulus_sequence = [
        run_spec.stimulus_sequence[0].model_copy(
            update={
                "image_path": "stimuli/original-images/base-set/wide.png",
                "on_frames": 1,
                "off_frames": 0,
            }
        )
    ]
    run_spec.display.total_frames = 1
    assert run_spec.presentation is not None
    geometry = run_spec.presentation.base.image_geometry
    assert geometry is not None
    geometry = geometry.model_copy(
        update={
            "mode": mode,
            "width_degrees": 8.0,
            "height_degrees": height_degrees,
            "source_resolution": geometry.source_resolution.model_copy(
                update={"width_px": 200, "height_px": 100}
            ),
        }
    )
    run_spec.presentation = run_spec.presentation.model_copy(
        update={"base": run_spec.presentation.base.model_copy(update={"image_geometry": geometry})}
    )
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    expected_width = visual_angle_width_px(
        degrees=8.0,
        viewing_distance_cm=80.0,
        screen_width_cm=53.0,
        screen_width_px=1920,
    )
    expected_height = (
        round(expected_width / 2)
        if expected_height_from_width
        else visual_angle_width_px(
            degrees=6.0,
            viewing_distance_cm=80.0,
            screen_width_cm=53.0,
            screen_width_px=1920,
        )
    )
    assert _image_stims(captures)[0].size == (expected_width, expected_height)


def test_psychopy_engine_rejects_compiled_source_resolution_drift(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    source_path = sample_project_root / "stimuli" / "original-images" / "base-set" / "wide.png"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (200, 100), color=(20, 40, 80)).save(source_path)
    run_spec.stimulus_sequence = [
        run_spec.stimulus_sequence[0].model_copy(
            update={"image_path": "stimuli/original-images/base-set/wide.png"}
        )
    ]
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        with pytest.raises(
            ValueError,
            match="decoded as 200x100, but its compiled source resolution is 256x256",
        ):
            engine.run_condition(
                run_spec,
                sample_project_root,
                runtime_options={"timing_warmup_frames": 0},
                trigger_backend=None,
            )
    finally:
        engine.close_session()


def test_psychopy_engine_cover_crops_centrally_in_memory_and_preserves_alpha(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    source_path = sample_project_root / "stimuli" / "original-images" / "base-set" / "rgba.png"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source = np.zeros((100, 200, 4), dtype=np.uint8)
    source[:, :, 0] = np.arange(200, dtype=np.uint8)
    source[:, :, 1] = np.arange(100, dtype=np.uint8)[:, np.newaxis]
    source[:, :, 3] = 127
    Image.fromarray(source).save(source_path)
    files_before = sorted(path.name for path in source_path.parent.iterdir())
    run_spec.stimulus_sequence = [
        run_spec.stimulus_sequence[0].model_copy(
            update={
                "image_path": "stimuli/original-images/base-set/rgba.png",
                "on_frames": 1,
                "off_frames": 0,
            }
        )
    ]
    run_spec.display.total_frames = 1
    assert run_spec.presentation is not None
    geometry = run_spec.presentation.base.image_geometry
    assert geometry is not None
    geometry = geometry.model_copy(
        update={
            "mode": ImageGeometryMode.COVER,
            "width_degrees": 6.0,
            "height_degrees": 6.0,
            "source_resolution": geometry.source_resolution.model_copy(
                update={"width_px": 200, "height_px": 100}
            ),
        }
    )
    run_spec.presentation = run_spec.presentation.model_copy(
        update={"base": run_spec.presentation.base.model_copy(update={"image_geometry": geometry})}
    )
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    rendered_source = _image_stims(captures)[0].image
    assert isinstance(rendered_source, Image.Image)
    assert rendered_source.mode == "RGBA"
    assert rendered_source.size == (100, 100)
    assert rendered_source.getpixel((0, 0)) == (50, 0, 0, 127)
    assert rendered_source.getpixel((99, 0)) == (149, 0, 0, 127)
    assert rendered_source.getpixel((0, 99)) == (50, 99, 0, 127)
    assert sorted(path.name for path in source_path.parent.iterdir()) == files_before


def test_psychopy_engine_emits_compiled_triggers_on_presentation_flip(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=False)
    run_spec.trigger_events = [
        TriggerEvent(frame_index=0, code=1, label="condition_start"),
        TriggerEvent(frame_index=1, code=55, label="oddball_onset"),
    ]
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[0.1, 0.2])
    trigger_backend = _RecordingTriggerBackend()
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=trigger_backend,
        )
    finally:
        engine.close_session()

    assert trigger_backend.records == [
        {"code": 1, "frame_index": 0, "label": "condition_start", "time_s": 0.1},
        {"code": 55, "frame_index": 1, "label": "oddball_onset", "time_s": 0.2},
    ]
    call_on_flip_events = [event for event in _events(captures) if event[0] == "callOnFlip"]
    assert len(call_on_flip_events) == 2


@pytest.mark.parametrize(
    ("last_frame_is_blank", "expected_image_draw_count"),
    [(False, 3), (True, 2)],
)
def test_psychopy_engine_terminal_offset_closes_continuous_and_blank_final_frames(
    monkeypatch,
    sample_project,
    sample_project_root,
    last_frame_is_blank,
    expected_image_draw_count,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    run_spec.stimulus_sequence = [
        run_spec.stimulus_sequence[0].model_copy(
            update={
                "on_start_frame": 0,
                "on_frames": 1 if last_frame_is_blank else 2,
                "off_frames": 1 if last_frame_is_blank else 0,
            }
        )
    ]
    run_spec.display.total_frames = 2
    run_spec.trigger_events = [TriggerEvent(frame_index=0, code=1, label="condition_start")]
    interval_s = 1.0 / run_spec.display.refresh_hz
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(
        captures,
        flip_times=[interval_s, interval_s * 2, interval_s * 3],
    )
    trigger_backend = _RecordingTriggerBackend()
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=trigger_backend,
        )
    finally:
        engine.close_session()

    window = captures["window"]
    assert isinstance(window, _FakeWindow)
    assert window._flip_index == 3
    assert summary.completed_frames == 2
    assert [record.frame_index for record in summary.frame_intervals] == [0, 1]
    assert [record.interval_s for record in summary.frame_intervals] == pytest.approx(
        [interval_s, interval_s]
    )
    assert _image_stims(captures)[0].draw_count == expected_image_draw_count
    assert [record["frame_index"] for record in trigger_backend.records] == [0]
    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.condition_cache_gpu_synchronized is True
    assert summary.runtime_metadata.condition_cache_cleanup_succeeded is True
    assert summary.runtime_metadata.condition_cache_unique_variant_count == 1


def test_psychopy_engine_terminal_offset_captures_final_frame_response(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    run_spec.fixation = run_spec.fixation.model_copy(
        update={"response_key": "space", "response_keys": ["space"]}
    )
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(
        captures,
        flip_times=[0.1, 0.2, 0.3],
        key_batches=[[], [], [SimpleNamespace(name="space", rt=0.25)]],
    )
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    assert len(summary.response_log) == 1
    assert summary.response_log[0].frame_index == 1
    assert summary.response_log[0].time_s == pytest.approx(0.25)


def test_psychopy_engine_keeps_trigger_flip_callback_exclusive_and_records_fixation_onset(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    run_spec.fixation_events = [FixationEvent(event_index=0, start_frame=1, duration_frames=1)]
    run_spec.trigger_events = [TriggerEvent(frame_index=1, code=55, label="oddball_onset")]
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(
        captures,
        flip_times=[0.1, 0.2, 0.3],
    )
    trigger_backend = _RecordingTriggerBackend()
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=trigger_backend,
        )
    finally:
        engine.close_session()

    window = captures["window"]
    assert isinstance(window, _FakeWindow)
    assert window.callback_names == ["_emit_trigger"]
    assert trigger_backend.records[0]["frame_index"] == 1
    assert trigger_backend.records[0]["time_s"] == pytest.approx(0.2)
    assert len(summary.fixation_target_onsets) == 1
    assert summary.fixation_target_onsets[0].event_index == 0
    assert summary.fixation_target_onsets[0].frame_index == 1
    assert summary.fixation_target_onsets[0].time_s == pytest.approx(0.2)
    shape_stims = captures["shape_stims"]
    assert isinstance(shape_stims, list)
    assert [stim.lineColor for stim in shape_stims] == [
        run_spec.fixation.default_color,
        run_spec.fixation.target_color,
    ]
    assert [stim.draw_count for stim in shape_stims] == [3, 2]


def test_psychopy_engine_converts_flip_time_into_keyboard_clock_time_base() -> None:
    engine = PsychoPyEngine()
    engine._psychopy_logging = SimpleNamespace(
        defaultClock=SimpleNamespace(getLastResetTime=lambda: 100.0)
    )
    keyboard_clock = SimpleNamespace(getLastResetTime=lambda: 99.25)

    assert engine._keyboard_flip_time_offset(keyboard_clock) == pytest.approx(0.75)


def test_psychopy_engine_does_not_invent_fixation_onset_when_clock_conversion_is_missing(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    run_spec.fixation_events = [FixationEvent(event_index=0, start_frame=1, duration_frames=1)]
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[0.1, 0.2, 0.3])
    fake_psychopy.logging = None
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
        )
    finally:
        engine.close_session()

    assert summary.fixation_target_onsets == []


def test_psychopy_engine_event_keyboard_backend_forces_frame_timestamp_fallback(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    run_spec.fixation = run_spec.fixation.model_copy(
        update={"response_key": "space", "response_keys": ["space"]}
    )
    run_spec.fixation_events = [FixationEvent(event_index=0, start_frame=1, duration_frames=1)]
    key = SimpleNamespace(name="space", rt=0.2)
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(
        captures,
        flip_times=[0.1, 0.2, 0.3],
        key_batches=[[], [key], []],
        keyboard_backend="event",
    )
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
        )
    finally:
        engine.close_session()

    assert summary.fixation_target_onsets == []
    assert len(summary.response_log) == 1
    assert summary.response_log[0].time_s is None


def test_psychopy_engine_trigger_timestamps_exclude_warmup_period(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=False)
    run_spec.trigger_events = [
        TriggerEvent(frame_index=0, code=1, label="condition_start"),
        TriggerEvent(frame_index=1, code=55, label="oddball_onset"),
    ]
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(
        captures,
        flip_times=[0.1, 0.2, 0.3, 0.4, 0.5],
    )
    trigger_backend = _RecordingTriggerBackend()
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={
                "timing_warmup_frames": 3,
                "strict_timing": False,
            },
            trigger_backend=trigger_backend,
        )
    finally:
        engine.close_session()

    assert [
        {key: value for key, value in record.items() if key != "time_s"}
        for record in trigger_backend.records
    ] == [
        {"code": 1, "frame_index": 0, "label": "condition_start"},
        {"code": 55, "frame_index": 1, "label": "oddball_onset"},
    ]
    assert trigger_backend.records[0]["time_s"] == pytest.approx(0.1)
    assert trigger_backend.records[1]["time_s"] == pytest.approx(0.2)


def test_psychopy_engine_omits_mixed_clock_domain_warmup_intervals(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(
        captures,
        flip_times=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
        flip_return_none_indices={1},
    )
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)
    evaluate_timing_qc = engine._evaluate_timing_qc
    captured_warmup_intervals: list[float] = []

    def _capture_timing_qc(**kwargs):
        captured_warmup_intervals.extend(kwargs["warmup_intervals"])
        return evaluate_timing_qc(**kwargs)

    monkeypatch.setattr(engine, "_evaluate_timing_qc", _capture_timing_qc)

    try:
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 3, "strict_timing": False},
        )
    finally:
        engine.close_session()

    assert captured_warmup_intervals == []


def test_psychopy_engine_uses_final_warmup_frames_for_fixation_lead_in(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=False)
    run_spec = run_spec.model_copy(update={"pre_stream_fixation_frames": 2})
    run_spec.trigger_events = [
        TriggerEvent(frame_index=0, code=1, label="condition_start"),
        TriggerEvent(frame_index=1, code=55, label="oddball_onset"),
    ]
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(
        captures,
        flip_times=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
    )
    trigger_backend = _RecordingTriggerBackend()
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 4, "strict_timing": False},
            trigger_backend=trigger_backend,
        )
    finally:
        engine.close_session()

    window = captures["window"]
    assert isinstance(window, _FakeWindow)
    assert window._flip_index == 7
    shape_stims = captures["shape_stims"]
    assert isinstance(shape_stims, list)
    assert len(shape_stims) == 2
    assert [stim.draw_count for stim in shape_stims] == [6, 1]
    assert summary.completed_frames == 2
    assert [record["frame_index"] for record in trigger_backend.records] == [0, 1]
    assert trigger_backend.records[0]["time_s"] == pytest.approx(0.1)
    assert trigger_backend.records[1]["time_s"] == pytest.approx(0.2)


def test_two_second_lead_in_uses_final_half_of_default_warmup_at_sixty_hz(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=False)
    run_spec = run_spec.model_copy(update={"pre_stream_fixation_frames": 120})
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 240, "strict_timing": False},
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    window = captures["window"]
    assert isinstance(window, _FakeWindow)
    assert window._flip_index == 240 + run_spec.display.total_frames + 1
    shape_stims = captures["shape_stims"]
    assert isinstance(shape_stims, list)
    assert [stim.draw_count for stim in shape_stims] == [
        120 + run_spec.display.total_frames + 2,
        1,
    ]
    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.timing_qc_warmup_frames == 240


def test_psychopy_engine_reports_long_lead_in_as_actual_pre_stream_qc_frames(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=False)
    run_spec.display.refresh_hz = 240.0
    run_spec = run_spec.model_copy(update={"pre_stream_fixation_frames": 480})
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 240, "strict_timing": False},
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.timing_qc_warmup_frames == 480
    window = captures["window"]
    assert isinstance(window, _FakeWindow)
    assert window._flip_index == 483


def test_psychopy_engine_blank_warmup_escape_aborts_before_stream_and_triggers(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=False)
    run_spec = run_spec.model_copy(update={"pre_stream_fixation_frames": 2})
    run_spec.trigger_events = [
        TriggerEvent(frame_index=0, code=1, label="condition_start"),
    ]
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(
        captures,
        flip_times=[0.1],
        key_batches=[[SimpleNamespace(name="escape")]],
    )
    trigger_backend = _RecordingTriggerBackend()
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 4, "strict_timing": False},
            trigger_backend=trigger_backend,
        )
    finally:
        engine.close_session()

    assert summary.aborted is True
    assert summary.abort_reason == "Escape pressed before condition playback."
    assert summary.completed_frames == 0
    assert trigger_backend.records == []
    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.timing_qc_warmup_frames == 1
    shape_stims = captures["shape_stims"]
    assert isinstance(shape_stims, list)
    assert [stim.draw_count for stim in shape_stims] == [1, 1]


def test_psychopy_engine_uses_compiled_trigger_events_not_stimulus_roles(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=False)
    run_spec.stimulus_sequence[1] = run_spec.stimulus_sequence[1].model_copy(
        update={"role": "oddball"}
    )
    run_spec.trigger_events = [TriggerEvent(frame_index=0, code=1, label="condition_start")]
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[0.1, 0.2])
    trigger_backend = _RecordingTriggerBackend()
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=trigger_backend,
        )
    finally:
        engine.close_session()

    assert trigger_backend.records == [
        {"code": 1, "frame_index": 0, "label": "condition_start", "time_s": 0.1}
    ]


def test_psychopy_engine_releases_condition_stimuli_after_timing_violation(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=False)
    expected_interval_s = 1.0 / run_spec.display.refresh_hz
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(
        captures,
        flip_times=[expected_interval_s, expected_interval_s + 0.05],
    )
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={
                "strict_timing": True,
                "timing_warmup_frames": 0,
                "timing_miss_threshold_multiplier": 1.5,
            },
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    assert summary.aborted is False
    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.timing_qc_strict_violation is True
    assert [stim.clear_textures_count for stim in _image_stims(captures)] == [1, 1]


def test_psychopy_engine_releases_condition_stimuli_after_playback_error(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=False)
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[], raise_on_flip_index=0)
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        with pytest.raises(RuntimeError, match="flip failed"):
            engine.run_condition(
                run_spec,
                sample_project_root,
                runtime_options={"timing_warmup_frames": 0},
                trigger_backend=None,
            )
    finally:
        engine.close_session()

    assert [stim.clear_textures_count for stim in _image_stims(captures)] == [1, 1]
    assert engine._active_run_clock is None


def test_psychopy_engine_invalidates_session_after_flip_failure_with_queued_trigger(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    run_spec.trigger_events = [TriggerEvent(frame_index=0, code=1, label="condition_start")]
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[], raise_on_flip_index=0)
    trigger_backend = _RecordingTriggerBackend()
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    with pytest.raises(RuntimeError, match="flip failed"):
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=trigger_backend,
        )

    window = captures["window"]
    assert isinstance(window, _FakeWindow)
    assert window.closed is True
    assert window._call_on_flip == []
    assert trigger_backend.records == []
    assert engine._window is None


def test_psychopy_engine_rejects_multiple_trigger_bytes_on_one_flip_before_frame_zero(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    run_spec.trigger_events = [
        TriggerEvent(frame_index=0, code=1, label="condition_start"),
        TriggerEvent(frame_index=0, code=55, label="oddball_onset"),
    ]
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    trigger_backend = _RecordingTriggerBackend()
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    with pytest.raises(ValueError, match="at most one trigger marker"):
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=trigger_backend,
        )

    assert [event for event in _events(captures) if event[0] == "flip"] == []
    assert trigger_backend.records == []


def test_psychopy_engine_invalidates_session_after_trigger_callback_failure(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    class _FailingTriggerBackend(_RecordingTriggerBackend):
        def send_trigger(self, *args, **kwargs) -> None:
            raise RuntimeError("trigger write failed")

    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    run_spec.trigger_events = [TriggerEvent(frame_index=0, code=1, label="condition_start")]
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[0.1])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    with pytest.raises(RuntimeError, match="trigger write failed"):
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=_FailingTriggerBackend(),
        )

    window = captures["window"]
    assert isinstance(window, _FakeWindow)
    assert window.closed is True
    assert len([event for event in _events(captures) if event[0] == "flip"]) == 1
    assert engine._window is None


def test_psychopy_engine_closes_session_when_cleanup_barrier_fails(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[0.1, 0.2, 0.3])
    sync_count = 0

    def _sync() -> None:
        nonlocal sync_count
        sync_count += 1
        if sync_count == 2:
            raise OSError("cleanup barrier failed")

    monkeypatch.setattr("fpvs_studio.engines.psychopy_stimuli.synchronize_gpu", _sync)
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    with pytest.raises(ConditionResourceCleanupError) as error_info:
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
        )

    window = captures["window"]
    assert isinstance(window, _FakeWindow)
    assert sync_count == 2
    assert [failure.operation for failure in error_info.value.report.failures] == [
        "synchronize_cleanup"
    ]
    assert window.closed is True
    assert engine._window is None


def test_psychopy_engine_does_not_reuse_stimuli_between_condition_runs(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _two_event_run_spec(sample_project, sample_project_root, duplicate_image=True)
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.open_session(runtime_options={})
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=None,
        )
        first_condition_stim = _image_stims(captures)[0]
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"timing_warmup_frames": 0},
            trigger_backend=None,
        )
        second_condition_stim = _image_stims(captures)[1]
    finally:
        engine.close_session()

    assert first_condition_stim is not second_condition_stim
    assert first_condition_stim.clear_textures_count == 1
    assert second_condition_stim.clear_textures_count == 1
    assert not hasattr(engine, "_image_stim_cache")


def test_psychopy_engine_strict_timing_keeps_stable_intervals_running(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _tiny_run_spec(sample_project, sample_project_root)
    warmup_frames = 4
    expected_interval_s = 1.0 / run_spec.display.refresh_hz
    flip_times = _build_flip_times(
        total_flips=warmup_frames + run_spec.display.total_frames,
        interval_s=expected_interval_s,
    )
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=flip_times)
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={
                "fullscreen": True,
                "strict_timing": True,
                "strict_timing_warmup": True,
                "timing_warmup_frames": warmup_frames,
                "timing_miss_threshold_multiplier": 1.5,
            },
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    assert summary.aborted is False
    assert summary.abort_reason is None
    assert summary.completed_frames == run_spec.display.total_frames
    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.timing_qc_strict_abort is False
    assert summary.runtime_metadata.timing_qc_strict_violation is False
    assert summary.runtime_metadata.timing_qc_first_bad_frame_index is None


def test_psychopy_engine_strict_timing_tolerates_single_early_warmup_miss(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _tiny_run_spec(sample_project, sample_project_root)
    warmup_frames = 40
    expected_interval_s = 1.0 / run_spec.display.refresh_hz
    flip_times = _build_flip_times(
        total_flips=warmup_frames + run_spec.display.total_frames,
        interval_s=expected_interval_s,
        long_interval_flip_indices={19},
        long_interval_s=0.03,
    )
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=flip_times)
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={
                "fullscreen": True,
                "strict_timing": True,
                "strict_timing_warmup": True,
                "timing_warmup_frames": warmup_frames,
                "timing_miss_threshold_multiplier": 1.5,
            },
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    assert summary.aborted is False
    assert summary.completed_frames == run_spec.display.total_frames
    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.timing_qc_strict_abort is False
    assert summary.runtime_metadata.timing_qc_strict_violation is False
    assert summary.runtime_metadata.timing_qc_first_bad_phase == "warmup"
    assert summary.runtime_metadata.timing_qc_first_bad_frame_index == 18


def test_psychopy_engine_strict_timing_flags_post_settle_warmup_misses(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _tiny_run_spec(sample_project, sample_project_root)
    warmup_frames = 60
    expected_interval_s = 1.0 / run_spec.display.refresh_hz
    flip_times = _build_flip_times(
        total_flips=warmup_frames + run_spec.display.total_frames,
        interval_s=expected_interval_s,
        long_interval_flip_indices={35, 38},
        long_interval_s=0.03,
    )
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=flip_times)
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={
                "fullscreen": True,
                "strict_timing": True,
                "timing_warmup_frames": warmup_frames,
                "timing_miss_threshold_multiplier": 1.5,
            },
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    assert summary.aborted is False
    assert summary.abort_reason is None
    assert summary.completed_frames == run_spec.display.total_frames
    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.timing_qc_strict_abort is False
    assert summary.runtime_metadata.timing_qc_strict_violation is True
    assert summary.runtime_metadata.timing_qc_first_bad_phase == "warmup"
    assert summary.runtime_metadata.timing_qc_first_bad_frame_index == 34
    assert summary.runtime_metadata.timing_qc_strict_violation_reason is not None
    assert "Strict timing QC flagged playback during warmup" in (
        summary.runtime_metadata.timing_qc_strict_violation_reason
    )


def test_psychopy_engine_softened_warmup_does_not_abort_before_run_phase(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _tiny_run_spec(sample_project, sample_project_root)
    warmup_frames = 60
    expected_interval_s = 1.0 / run_spec.display.refresh_hz
    flip_times = _build_flip_times(
        total_flips=warmup_frames + run_spec.display.total_frames,
        interval_s=expected_interval_s,
        long_interval_flip_indices={35, 38},
        long_interval_s=0.03,
    )
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=flip_times)
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={
                "fullscreen": True,
                "strict_timing": True,
                "strict_timing_warmup": False,
                "timing_warmup_frames": warmup_frames,
                "timing_miss_threshold_multiplier": 1.5,
            },
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    assert summary.aborted is False
    assert summary.abort_reason is None
    assert summary.completed_frames == run_spec.display.total_frames
    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.timing_qc_strict_abort is False
    assert summary.runtime_metadata.timing_qc_strict_violation is False
    assert summary.runtime_metadata.timing_qc_first_bad_phase == "warmup"
    assert summary.runtime_metadata.timing_qc_first_bad_frame_index == 34


def test_psychopy_engine_strict_timing_flags_run_phase_miss_without_aborting(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _tiny_run_spec(sample_project, sample_project_root)
    warmup_frames = 4
    expected_interval_s = 1.0 / run_spec.display.refresh_hz
    long_interval_flip_index = warmup_frames + 2
    flip_times = _build_flip_times(
        total_flips=warmup_frames + run_spec.display.total_frames,
        interval_s=expected_interval_s,
        long_interval_flip_indices={long_interval_flip_index},
        long_interval_s=0.05,
    )
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=flip_times)
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={
                "fullscreen": True,
                "strict_timing": True,
                "strict_timing_warmup": False,
                "timing_warmup_frames": warmup_frames,
                "timing_miss_threshold_multiplier": 1.5,
            },
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    assert summary.aborted is False
    assert summary.completed_frames == run_spec.display.total_frames
    assert summary.abort_reason is None
    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.timing_qc_strict_abort is False
    assert summary.runtime_metadata.timing_qc_strict_violation is True
    assert summary.runtime_metadata.timing_qc_first_bad_phase == "run"
    assert summary.runtime_metadata.timing_qc_first_bad_frame_index is not None
    assert summary.runtime_metadata.timing_qc_strict_violation_reason is not None
    assert "Strict timing QC flagged playback during run" in (
        summary.runtime_metadata.timing_qc_strict_violation_reason
    )


def test_psychopy_engine_logs_playback_timing_diagnostic(
    monkeypatch,
    caplog,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _tiny_run_spec(sample_project, sample_project_root)
    warmup_frames = 0
    expected_interval_s = 1.0 / run_spec.display.refresh_hz
    flip_times = _build_flip_times(
        total_flips=run_spec.display.total_frames,
        interval_s=expected_interval_s,
        long_interval_flip_indices={2},
        long_interval_s=0.05,
    )
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=flip_times)
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)
    caplog.set_level(logging.WARNING, logger="fpvs_studio.engines.psychopy_engine")

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={
                "fullscreen": False,
                "strict_timing": False,
                "timing_warmup_frames": warmup_frames,
            },
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    assert summary.aborted is False
    assert "PsychoPy timing diagnostic" in caplog.text
    assert "phase=playback" in caplog.text
    assert "long_interval_count=1" in caplog.text
    assert "max_long_interval_ms=50.00" in caplog.text


def test_psychopy_engine_uses_psychopy_warning_channel_for_timing_diagnostic(
    monkeypatch,
    sample_project,
    sample_project_root,
) -> None:
    run_spec = _tiny_run_spec(sample_project, sample_project_root)
    expected_interval_s = 1.0 / run_spec.display.refresh_hz
    flip_times = _build_flip_times(
        total_flips=run_spec.display.total_frames,
        interval_s=expected_interval_s,
        long_interval_flip_indices={2},
        long_interval_s=0.05,
    )
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(
        captures,
        flip_times=flip_times,
        record_psychopy_warnings=True,
    )
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={
                "fullscreen": False,
                "strict_timing": False,
                "timing_warmup_frames": 0,
            },
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    events = captures["events"]
    assert any(
        event_name == "psychopy_warning"
        and "PsychoPy timing diagnostic" in str(message)
        and "phase=playback" in str(message)
        for event_name, message in events
    )


def test_psychopy_engine_disables_frame_interval_recording_for_text_screens(
    monkeypatch,
) -> None:
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(
        captures,
        flip_times=[0.0, 0.04],
        record_psychopy_warnings=True,
    )
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.open_session(runtime_options={"fullscreen": False})
        window = captures["window"]
        window.recordFrameIntervals = True
        engine._show_text_screen(
            heading="Instruction Screen",
            body=None,
            countdown_seconds=0.01,
            continue_key=None,
            continue_prompt=None,
        )
    finally:
        engine.close_session()

    events = captures["events"]
    assert not any(event_name == "psychopy_warning" for event_name, _message in events)
    assert window.recordFrameIntervals is True
    assert window.frameIntervals == []
