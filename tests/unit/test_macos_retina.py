"""Backing-pixel geometry checks with fake windows; no native graphics calls."""

from types import SimpleNamespace

import pytest

from fpvs_studio.engines import psychopy_window


def test_mac_window_uses_retina_pyglet(monkeypatch):
    monkeypatch.setattr(psychopy_window, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(psychopy_window, "_detect_fullscreen_size_px", lambda _: (1440, 900))
    values = psychopy_window.build_window_kwargs({"fullscreen": True})
    assert values["useRetina"] is True
    assert values["winType"] == "pyglet"
    assert values["screen"] == 0


@pytest.mark.parametrize("actual", [(1440, 900), None])
def test_retina_mismatch_blocks_playback(monkeypatch, actual):
    monkeypatch.setattr(psychopy_window, "sys", SimpleNamespace(platform="darwin"))
    spec = SimpleNamespace(display=SimpleNamespace(screen_width_px=2880, screen_height_px=1800))
    with pytest.raises(RuntimeError, match="backing pixels"):
        psychopy_window.validate_macos_framebuffer(SimpleNamespace(frameBufferSize=actual), spec)


def test_retina_matching_backing_pixels_pass(monkeypatch):
    monkeypatch.setattr(psychopy_window, "sys", SimpleNamespace(platform="darwin"))
    spec = SimpleNamespace(display=SimpleNamespace(screen_width_px=2880, screen_height_px=1800))
    psychopy_window.validate_macos_framebuffer(
        SimpleNamespace(frameBufferSize=(2880, 1800)), spec,
    )
