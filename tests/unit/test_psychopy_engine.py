"""Unit tests for PsychoPy engine launch wiring and timing enforcement."""

from __future__ import annotations

from types import SimpleNamespace

from fpvs_studio.core.compiler import compile_run_spec
from fpvs_studio.engines.psychopy_engine import PsychoPyEngine
from fpvs_studio.engines.psychopy_text_screens import show_text_screen


class _FakeWindow:
    def __init__(self, *, flip_times: list[float] | None = None, **kwargs) -> None:
        self.kwargs = kwargs
        self.recordFrameIntervals = False
        self.frameIntervals: list[float] = []
        self.size = kwargs.get("size", [1920, 1080])
        self.monitor = None
        self._flip_times = list(flip_times or [])
        self._flip_index = 0
        self._last_flip_time = 0.0
        self._call_on_flip: list[tuple[object, tuple[object, ...]]] = []

    @property
    def last_flip_time(self) -> float:
        return self._last_flip_time

    def flip(self) -> float:
        if self._flip_index < len(self._flip_times):
            self._last_flip_time = self._flip_times[self._flip_index]
        else:
            self._last_flip_time += 1.0 / 60.0
        self._flip_index += 1
        pending_callbacks = list(self._call_on_flip)
        self._call_on_flip.clear()
        for callback, args in pending_callbacks:
            callback(*args)
        return self._last_flip_time

    def callOnFlip(self, callback: object, *args: object) -> None:
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
    def __init__(self, window: _FakeWindow) -> None:
        self.clock = _FakeClock(window)

    def clearEvents(self) -> None:
        return None

    def getKeys(
        self,
        *,
        keyList: list[str] | None = None,
        waitRelease: bool = False,
        clear: bool = True,
    ) -> list[object]:
        return []


class _FakeStim:
    def __init__(self, *args, **kwargs) -> None:
        self.lineColor = kwargs.get("lineColor")

    def draw(self) -> None:
        return None


def _build_fake_psychopy(captures: dict[str, object], *, flip_times: list[float]) -> object:
    def _fake_window(**kwargs):
        captures["window_kwargs"] = kwargs
        window = _FakeWindow(flip_times=flip_times, **kwargs)
        captures["window"] = window
        return window

    def _fake_keyboard():
        return _FakeKeyboard(captures["window"])

    fake_visual = SimpleNamespace(
        Window=_fake_window,
        ShapeStim=_FakeStim,
        ImageStim=_FakeStim,
        TextStim=_FakeStim,
    )
    fake_core = SimpleNamespace(Clock=lambda: _FakeClock(captures["window"]))
    return SimpleNamespace(
        visual=fake_visual,
        core=fake_core,
        hardware=SimpleNamespace(keyboard=SimpleNamespace(Keyboard=_fake_keyboard)),
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
