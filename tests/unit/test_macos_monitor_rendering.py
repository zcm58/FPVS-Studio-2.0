"""Mac monitor mapping, placement confirmation and mixed-DPI repair without graphics."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from tests.platform_adapters import set_module_platform
from tests.unit.test_psychopy_engine import _build_fake_psychopy, _patch_fake_psychopy

from fpvs_studio.engines import psychopy_macos_display as adapter
from fpvs_studio.engines import psychopy_window
from fpvs_studio.engines.psychopy_engine import PsychoPyEngine
from fpvs_studio.runtime import macos_display


def _screens(monkeypatch):
    set_module_platform(monkeypatch, psychopy_window, "darwin")
    screens = [
        SimpleNamespace(_cg_display_id=21, width=1920, height=1080, x=-1920, y=-1080),
        SimpleNamespace(_cg_display_id=17, width=1440, height=900, x=0, y=0),
    ]
    monkeypatch.setattr(psychopy_window, "_pyglet_screens", lambda: screens)
    monkeypatch.setattr(macos_display, "query_macos_monitors", lambda: (
        SimpleNamespace(display_id=21, primary=False),
        SimpleNamespace(display_id=17, primary=True),
    ))
    return screens


def test_mac_default_uses_native_primary_independent_of_screen_order(monkeypatch):
    _screens(monkeypatch)
    values = psychopy_window.build_window_kwargs({"fullscreen": True})
    assert values["screen"] == 1
    assert values["size"] == [1440, 900]
    assert values["pos"] == [0, 0]
    assert values["fullscr"] is False
    assert values["useRetina"] is True
    assert values["winType"] == "pyglet"


@pytest.mark.parametrize("position", [(-1920, -1080), (1440, 0), (0, 900)])
def test_mac_named_display_resolves_reorder_with_screen_relative_origin(monkeypatch, position):
    screens = _screens(monkeypatch)
    screens[0].x, screens[0].y = position
    options = {"display_device_name": "macos:21"}
    assert psychopy_window.build_refresh_probe_window_kwargs(options)["screen"] == 0
    screens.reverse()
    values = psychopy_window.build_window_kwargs(options)
    assert values["screen"] == 1
    # PsychoPy applies the selected screen's origin, with its Cocoa height correction.
    assert values["pos"] == [0, 0]
    assert values["size"] == [1920, 1080]


@pytest.mark.parametrize("failure", ["missing", "duplicate", "invalid", "index"])
def test_mac_selection_never_falls_back_to_another_screen(monkeypatch, failure):
    screens = _screens(monkeypatch)
    options = {"display_device_name": "macos:21"}
    if failure == "missing":
        screens.pop(0)
    elif failure == "duplicate":
        screens.append(screens[0])
    elif failure == "invalid":
        options = {"display_device_name": "not-a-mac-display"}
    else:
        options = {"display_index": 1}
    with pytest.raises(RuntimeError, match="Could not select the presentation monitor"):
        psychopy_window.build_window_kwargs(options)


def _window(monkeypatch, *, actual_id=21, backing=(3840, 2160), cached=(3840, 2160)):
    set_module_platform(monkeypatch, adapter, "darwin")
    monkeypatch.setattr(adapter, "_macos_window_display_id", lambda _window: actual_id)
    window = SimpleNamespace(
        frameBufferSize=list(cached), size=list(cached), _isFullScr=False, useFBO=False,
        winHandle=SimpleNamespace(get_framebuffer_size=lambda: backing),
    )

    def update(fullscreen):
        assert fullscreen is False
        window.frameBufferSize[:] = backing
        window.size[:] = backing

    window.backend = SimpleNamespace(setFullScr=Mock(side_effect=update))
    return window


def test_mac_confirm_reads_realized_nswindow_identity(monkeypatch):
    window = SimpleNamespace(winHandle=SimpleNamespace(_nswindow=SimpleNamespace(ptr=12345)))
    appkit = SimpleNamespace(NSWindow=Mock(return_value=SimpleNamespace(
        screen=lambda: SimpleNamespace(deviceDescription=lambda: {"NSScreenNumber": 21}),
    )))
    monkeypatch.setattr(adapter, "import_module", lambda _name: appkit)
    assert adapter._macos_window_display_id(window) == 21
    appkit.NSWindow.assert_called_once_with(c_void_p=12345)


def test_mac_confirm_accepts_native_backing_without_resizing(monkeypatch):
    window = _window(monkeypatch)
    adapter.confirm_macos_window_display(window, 21)
    window.backend.setFullScr.assert_not_called()


@pytest.mark.parametrize(("backing", "cached"), [
    ((3840, 2160), (1920, 1080)), ((1920, 1080), (3840, 2160)),
])
def test_mac_confirm_refreshes_stale_retina_cache_through_existing_backend(
    monkeypatch, backing, cached,
):
    window = _window(monkeypatch, backing=backing, cached=cached)
    adapter.confirm_macos_window_display(window, 21)
    window.backend.setFullScr.assert_called_once_with(False)
    assert tuple(window.frameBufferSize) == tuple(window.size) == backing


def test_mac_confirm_rejects_actual_window_on_other_monitor(monkeypatch):
    window = _window(monkeypatch, actual_id=17)
    with pytest.raises(RuntimeError, match="Mac presentation display changed from 21 to 17"):
        adapter.confirm_macos_window_display(window, 21)
    window.backend.setFullScr.assert_not_called()


@pytest.mark.parametrize("failure", ["invalid", "unchanged", "unsafe", "viewport"])
def test_mac_confirm_rejects_unverified_backing(monkeypatch, failure):
    window = _window(monkeypatch, cached=(1920, 1080))
    if failure == "invalid":
        window.winHandle.get_framebuffer_size = lambda: (0, 2160)
    elif failure == "unchanged":
        window.backend.setFullScr.side_effect = None
    elif failure == "unsafe":
        window._isFullScr = True
    else:
        window.backend.setFullScr.side_effect = lambda _value: window.frameBufferSize.__setitem__(
            slice(None), [3840, 2160],
        )
    with pytest.raises(RuntimeError, match="Mac presentation display"):
        adapter.confirm_macos_window_display(window, 21)


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_other_platforms_do_not_read_mac_window_identity(monkeypatch, platform):
    set_module_platform(monkeypatch, adapter, platform)
    read = Mock(side_effect=AssertionError("Unexpected native Mac call"))
    monkeypatch.setattr(adapter, "_macos_window_display_id", read)
    adapter.confirm_macos_window_display(object(), 21)
    read.assert_not_called()


@pytest.mark.parametrize("operation", ["probe", "session"])
def test_engine_closes_window_when_actual_monitor_does_not_match(monkeypatch, operation):
    captures = {}
    engine = PsychoPyEngine()
    fake = _build_fake_psychopy(captures, flip_times=[])
    _patch_fake_psychopy(monkeypatch, engine, fake, platform_name="darwin")
    monkeypatch.setattr(adapter, "_macos_window_display_id", lambda _window: 99)
    with pytest.raises(RuntimeError, match="Mac presentation display changed"):
        if operation == "probe":
            engine.measure_refresh_hz(runtime_options={"display_device_name": "macos:1"})
        else:
            engine.open_session(runtime_options={"display_device_name": "macos:1"})
    assert captures["window"].closed
