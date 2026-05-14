"""Unit tests for PsychoPy engine launch wiring and timing enforcement."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from fpvs_studio.core.compiler import compile_run_spec
from fpvs_studio.core.display_geometry import visual_angle_width_px
from fpvs_studio.core.run_spec import TriggerEvent
from fpvs_studio.engines.psychopy_engine import PsychoPyEngine
from fpvs_studio.engines.psychopy_stimuli import release_stimuli
from fpvs_studio.engines.psychopy_text_screens import show_text_screen
from fpvs_studio.triggers.base import TriggerBackend


class _FakeWindow:
    def __init__(
        self,
        *,
        flip_times: list[float] | None = None,
        events: list[tuple[str, object]] | None = None,
        raise_on_flip_index: int | None = None,
        **kwargs,
    ) -> None:
        self.kwargs = kwargs
        self.recordFrameIntervals = False
        self.frameIntervals: list[float] = []
        self.size = kwargs.get("size", [1920, 1080])
        self.monitor = None
        self.events = events if events is not None else []
        self.raise_on_flip_index = raise_on_flip_index
        self._flip_times = list(flip_times or [])
        self._flip_index = 0
        self._last_flip_time = 0.0
        self._call_on_flip: list[tuple[object, tuple[object, ...]]] = []

    @property
    def last_flip_time(self) -> float:
        return self._last_flip_time

    def flip(self) -> float:
        self.events.append(("flip", self._flip_index))
        if self._flip_index == self.raise_on_flip_index:
            raise RuntimeError("flip failed")
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
        return self._last_flip_time

    def callOnFlip(self, callback: object, *args: object) -> None:
        self.events.append(("callOnFlip", args))
        self._call_on_flip.append((callback, args))

    def close(self) -> None:
        return None


class _FakeClock:
    def __init__(self, window: _FakeWindow) -> None:
        self._window = window

    def reset(self) -> None:
        return None

    def getTime(self) -> float:
        return self._window.last_flip_time


class _FakeKeyboard:
    def __init__(
        self,
        window: _FakeWindow,
        key_batches: list[list[object]] | None = None,
    ) -> None:
        self.clock = _FakeClock(window)
        self._key_batches = list(key_batches or [])

    def clearEvents(self) -> None:
        return None

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
    record_psychopy_warnings: bool = False,
) -> object:
    events: list[tuple[str, object]] = []
    image_stims: list[Any] = []
    captures["events"] = events
    captures["image_stims"] = image_stims

    class _FakeImageStim(_FakeStim):
        def __init__(self, *args, image: str, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.image = image
            self.size = kwargs.get("size")
            self.clear_textures_count = 0
            image_stims.append(self)
            events.append(("image", image))

        def clearTextures(self) -> None:
            self.clear_textures_count += 1
            events.append(("clear", self.image))

    def _fake_window(**kwargs):
        captures["window_kwargs"] = kwargs
        window = _FakeWindow(
            flip_times=flip_times,
            events=events,
            raise_on_flip_index=raise_on_flip_index,
            **kwargs,
        )
        captures["window"] = window
        return window

    def _fake_keyboard():
        return _FakeKeyboard(captures["window"], key_batches=key_batches)

    fake_visual = SimpleNamespace(
        Window=_fake_window,
        ShapeStim=_FakeStim,
        ImageStim=_FakeImageStim,
        TextStim=_FakeStim,
    )
    fake_core = SimpleNamespace(Clock=lambda: _FakeClock(captures["window"]))
    fake_logging = (
        SimpleNamespace(warning=lambda message: events.append(("psychopy_warning", message)))
        if record_psychopy_warnings
        else None
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
    engine._psychopy = fake_psychopy
    engine._visual = fake_psychopy.visual
    engine._core = fake_psychopy.core
    engine._keyboard_module = fake_psychopy.hardware.keyboard
    engine._psychopy_logging = fake_psychopy.logging
    monkeypatch.setattr(engine, "_load_psychopy", lambda: fake_psychopy)


def _tiny_run_spec(sample_project, sample_project_root):
    sample_project.settings.fixation_task.enabled = False
    sample_project.settings.fixation_task.accuracy_task_enabled = False
    sample_project.conditions[0].oddball_cycle_repeats_per_sequence = 1
    return compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="timing-smoke",
    )


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
            "on_start_frame": 1,
            "on_frames": 1,
            "off_frames": 0,
        }
    )
    run_spec.stimulus_sequence = [first_event, second_event]
    run_spec.fixation_events = []
    run_spec.display.total_frames = 2
    return run_spec


def _image_stims(captures: dict[str, object]) -> list[Any]:
    image_stims = captures["image_stims"]
    assert isinstance(image_stims, list)
    return image_stims


def _events(captures: dict[str, object]) -> list[tuple[str, object]]:
    events = captures["events"]
    assert isinstance(events, list)
    return events


def test_psychopy_engine_opens_fullscreen_window_for_launched_session(monkeypatch) -> None:
    captures: dict[str, object] = {}
    fake_psychopy = _build_fake_psychopy(captures, flip_times=[])

    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake_psychopy)

    try:
        engine.open_session(
            runtime_options={
                "test_mode": True,
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
    }


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
        heading="Condition 1 of 1: Faces",
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
        engine.open_session(runtime_options={"test_mode": True, "fullscreen": False})
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
        engine.open_session(runtime_options={"test_mode": True, "fullscreen": False})
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
            runtime_options={"test_mode": True, "timing_warmup_frames": 0},
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
            runtime_options={"test_mode": True, "timing_warmup_frames": 0},
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    image_stims = _image_stims(captures)
    assert len(image_stims) == 1
    assert image_stims[0].draw_count == 2
    assert image_stims[0].clear_textures_count == 1


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
                "test_mode": True,
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
                "test_mode": True,
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
            runtime_options={"test_mode": True, "timing_warmup_frames": 0},
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
            runtime_options={"test_mode": True, "timing_warmup_frames": 0},
            trigger_backend=trigger_backend,
        )
    finally:
        engine.close_session()

    assert trigger_backend.records == [
        {"code": 1, "frame_index": 0, "label": "condition_start", "time_s": 0.1}
    ]


def test_psychopy_engine_releases_condition_stimuli_after_abort(
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
                "test_mode": True,
                "strict_timing": True,
                "timing_warmup_frames": 0,
                "timing_miss_threshold_multiplier": 1.5,
            },
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    assert summary.aborted is True
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
                runtime_options={"test_mode": True, "timing_warmup_frames": 0},
                trigger_backend=None,
            )
    finally:
        engine.close_session()

    assert [stim.clear_textures_count for stim in _image_stims(captures)] == [1, 1]
    assert engine._active_run_clock is None


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
        engine.open_session(runtime_options={"test_mode": True})
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"test_mode": True, "timing_warmup_frames": 0},
            trigger_backend=None,
        )
        first_condition_stim = _image_stims(captures)[0]
        engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"test_mode": True, "timing_warmup_frames": 0},
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
                "test_mode": True,
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
                "test_mode": True,
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
    assert summary.runtime_metadata.timing_qc_first_bad_frame_index == 18


def test_psychopy_engine_strict_timing_aborts_after_two_post_settle_warmup_misses(
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
                "test_mode": True,
                "fullscreen": True,
                "strict_timing": True,
                "timing_warmup_frames": warmup_frames,
                "timing_miss_threshold_multiplier": 1.5,
            },
            trigger_backend=None,
        )
    finally:
        engine.close_session()

    assert summary.aborted is True
    assert summary.abort_reason is not None
    assert "Strict timing aborted run during warmup" in summary.abort_reason
    assert summary.completed_frames == 0
    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.timing_qc_strict_abort is True
    assert summary.runtime_metadata.timing_qc_first_bad_frame_index == 34


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
                "test_mode": True,
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
    assert summary.runtime_metadata.timing_qc_first_bad_frame_index == 34


def test_psychopy_engine_strict_timing_aborts_on_first_run_phase_miss(
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
                "test_mode": True,
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

    assert summary.aborted is True
    assert summary.completed_frames < run_spec.display.total_frames
    assert summary.abort_reason is not None
    assert "Strict timing aborted run" in summary.abort_reason
    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.timing_qc_strict_abort is True
    assert summary.runtime_metadata.timing_qc_first_bad_frame_index is not None


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
                "test_mode": True,
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
                "test_mode": True,
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
        engine.open_session(runtime_options={"test_mode": True, "fullscreen": False})
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
