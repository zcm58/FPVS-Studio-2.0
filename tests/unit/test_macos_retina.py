"""Backing-pixel geometry checks with fake windows; no native graphics calls."""

from types import SimpleNamespace

import numpy as np
import pytest
from tests.platform_adapters import set_module_platform
from tests.unit.test_psychopy_engine import (
    _build_fake_psychopy,
    _patch_fake_psychopy,
    _tiny_run_spec,
)

from fpvs_studio.engines import psychopy_engine as engine_module
from fpvs_studio.engines import psychopy_window
from fpvs_studio.engines.psychopy_engine import PsychoPyEngine
from fpvs_studio.runtime import macos_display
from fpvs_studio.runtime.preflight import PreflightError
from fpvs_studio.runtime.run_worker import _validate_configured_display_resolution


@pytest.fixture(autouse=True)
def fake_mac_monitor_identity(monkeypatch):
    monkeypatch.setattr(
        macos_display, "query_macos_monitors",
        lambda: (SimpleNamespace(display_id=1, primary=True),),
    )
    monkeypatch.setattr(
        psychopy_window, "_pyglet_screens", lambda: [SimpleNamespace(_cg_display_id=1)],
    )


def test_mac_window_uses_retina_pyglet(monkeypatch):
    set_module_platform(monkeypatch, psychopy_window, "darwin")
    monkeypatch.setattr(psychopy_window, "_detect_fullscreen_size_px", lambda _: (1440, 900))
    values = psychopy_window.build_window_kwargs({"fullscreen": True})
    assert values["useRetina"] is True
    assert values["winType"] == "pyglet"
    assert values["checkTiming"] is False
    assert values["screen"] == 0
    assert values["fullscr"] is False
    assert values["allowGUI"] is False
    assert values["size"] == [1440, 900]
    assert values["pos"] == [0, 0]


def test_mac_display_size_failure_does_not_open_smaller_window(monkeypatch):
    set_module_platform(monkeypatch, psychopy_window, "darwin")
    monkeypatch.setattr(psychopy_window, "_detect_fullscreen_size_px", lambda _: None)
    with pytest.raises(RuntimeError, match="Mac presentation display size"):
        psychopy_window.build_window_kwargs({"fullscreen": True})


def test_mac_realized_display_size_accepts_numpy_viewport(monkeypatch):
    set_module_platform(monkeypatch, engine_module, "darwin")
    engine = PsychoPyEngine()
    size = np.asarray((2880, 1800))
    engine._window = SimpleNamespace(size=size, frameBufferSize=size)
    assert engine.current_display_size_px() == (2880, 1800)


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
@pytest.mark.parametrize("matches", [True, False])
def test_numpy_window_dimensions_enforce_configured_resolution_on_every_platform(
    monkeypatch, sample_project, sample_project_root, platform, matches,
):
    set_module_platform(monkeypatch, engine_module, platform)
    spec = _tiny_run_spec(sample_project, sample_project_root)
    spec.display.use_current_screen_resolution = False
    expected = (spec.display.screen_width_px, spec.display.screen_height_px)
    actual = expected if matches else tuple(value // 2 for value in expected)
    engine = PsychoPyEngine()
    engine._window = SimpleNamespace(size=np.asarray(actual), frameBufferSize=np.asarray(actual))

    assert engine.current_display_size_px() == actual
    if matches:
        _validate_configured_display_resolution(engine, spec)
    else:
        with pytest.raises(PreflightError, match="configured to be run on a display"):
            _validate_configured_display_resolution(engine, spec)
        spec.display.use_current_screen_resolution = True
        _validate_configured_display_resolution(engine, spec)


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
        if platform == "darwin":
            assert captures["window_kwargs"]["checkTiming"] is False
            assert captures["window_kwargs"]["fullscr"] is False
            assert captures["keyboard_kwargs"] == {"backend": "event"}
            assert window.useRetina is False
            if backing == "matching":
                assert engine.current_display_size_px() == expected
        else:
            assert "checkTiming" not in captures["window_kwargs"]
            assert captures["window_kwargs"]["fullscr"] is True
            assert captures["keyboard_kwargs"] == {}
        if platform == "darwin" and backing != "matching":
            with pytest.raises(RuntimeError, match="backing pixels"):
                engine._prepare_condition_playback(spec, sample_project_root)
        else:
            engine._prepare_condition_playback(spec, sample_project_root)
    finally:
        engine.close_session()
    assert window.closed
