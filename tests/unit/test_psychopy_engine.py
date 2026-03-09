"""Unit tests for PsychoPy engine launch wiring."""

from __future__ import annotations

from types import SimpleNamespace

from fpvs_studio.engines.psychopy_engine import PsychoPyEngine


class _FakeWindow:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.recordFrameIntervals = False
        self.size = kwargs.get("size", [1920, 1080])
        self.monitor = None

    def close(self) -> None:
        return None


class _FakeKeyboard:
    def clearEvents(self) -> None:
        return None


def test_psychopy_engine_opens_fullscreen_window_for_launched_session(monkeypatch) -> None:
    captures: dict[str, object] = {}

    def _fake_window(**kwargs):
        captures["window_kwargs"] = kwargs
        return _FakeWindow(**kwargs)

    fake_psychopy = SimpleNamespace(
        visual=SimpleNamespace(Window=_fake_window),
        hardware=SimpleNamespace(keyboard=SimpleNamespace(Keyboard=_FakeKeyboard)),
    )

    engine = PsychoPyEngine()
    monkeypatch.setattr(engine, "_load_psychopy", lambda: fake_psychopy)

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
