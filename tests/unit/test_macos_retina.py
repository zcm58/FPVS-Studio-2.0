"""Backing-pixel geometry checks with fake windows; no native graphics calls."""

from types import SimpleNamespace

import pytest
from tests.platform_adapters import set_module_platform
from tests.unit.test_psychopy_engine import (
    _build_fake_psychopy,
    _patch_fake_psychopy,
    _tiny_run_spec,
)

from fpvs_studio.engines import psychopy_window
from fpvs_studio.engines.psychopy_engine import PsychoPyEngine


def test_mac_window_uses_retina_pyglet(monkeypatch):
    set_module_platform(monkeypatch, psychopy_window, "darwin")
    monkeypatch.setattr(psychopy_window, "_detect_fullscreen_size_px", lambda _: (1440, 900))
    values = psychopy_window.build_window_kwargs({"fullscreen": True})
    assert values["useRetina"] is True
    assert values["winType"] == "pyglet"
    assert values["screen"] == 0


@pytest.mark.parametrize("actual", [(1440, 900), None])
def test_retina_mismatch_blocks_playback(monkeypatch, actual):
    set_module_platform(monkeypatch, psychopy_window, "darwin")
    spec = SimpleNamespace(display=SimpleNamespace(screen_width_px=2880, screen_height_px=1800))
    with pytest.raises(RuntimeError, match="backing pixels"):
        psychopy_window.validate_macos_framebuffer(SimpleNamespace(frameBufferSize=actual), spec)


def test_retina_matching_backing_pixels_pass(monkeypatch):
    set_module_platform(monkeypatch, psychopy_window, "darwin")
    spec = SimpleNamespace(display=SimpleNamespace(screen_width_px=2880, screen_height_px=1800))
    psychopy_window.validate_macos_framebuffer(
        SimpleNamespace(frameBufferSize=(2880, 1800)), spec,
    )


@pytest.mark.parametrize("platform", ["win32", "darwin"])
@pytest.mark.parametrize("backing", ["matching", "logical_only", "missing"])
def test_shared_engine_keeps_windows_contract_and_mac_backing_pixel_guard(
    monkeypatch, sample_project, sample_project_root, platform, backing,
):
    captures = {}
    engine = PsychoPyEngine()
    fake = _build_fake_psychopy(captures, flip_times=[])
    _patch_fake_psychopy(monkeypatch, engine, fake, platform_name=platform)
    spec = _tiny_run_spec(sample_project, sample_project_root)
    expected = (spec.display.screen_width_px, spec.display.screen_height_px)
    try:
        engine.open_session(runtime_options={"fullscreen": True})
        window = captures["window"]
        window.frameBufferSize = (
            expected if backing == "matching" else
            tuple(value // 2 for value in expected) if backing == "logical_only" else None
        )
        assert captures["window_kwargs"].get("useRetina", False) is (platform == "darwin")
        if platform == "darwin" and backing != "matching":
            with pytest.raises(RuntimeError, match="backing pixels"):
                engine._prepare_condition_playback(spec, sample_project_root)
        else:
            engine._prepare_condition_playback(spec, sample_project_root)
    finally:
        engine.close_session()
    assert window.closed
