"""Selected monitor identity stays consistent across native checks and rendering."""

from __future__ import annotations

import ctypes
from types import SimpleNamespace
from typing import cast

import pytest
from tests.platform_adapters import set_module_platform

from fpvs_studio.engines import psychopy_window
from fpvs_studio.engines.base import PresentationEngine
from fpvs_studio.runtime import display_mode, display_refresh, launcher, windows_display
from fpvs_studio.runtime.launcher import LaunchSettings, LaunchSettingsError
from fpvs_studio.runtime.windows_display import WindowsDisplayModeError, WindowsMonitor


def _fake_monitor_api(monkeypatch, *, flags=(0, 1), failure=None):
    names = [r"\\.\DISPLAY2", r"\\.\DISPLAY1"]

    def get_info(handle, pointer):
        if failure == "info":
            return 0
        info = pointer._obj
        index = handle - 1
        info.szDevice = names[index] if failure != "duplicate" else names[0]
        info.dwFlags = flags[index]
        info.rcMonitor = windows_display._MonitorRect(
            -1920 if index == 0 else 0, 0, 0 if index == 0 else 2560,
            1080 if index == 0 else 1440,
        )
        return 1

    def enumerate_monitors(_dc, _clip, callback, data):
        if failure == "enumerate":
            return 0
        for handle in (1, 2):
            rect = windows_display._MonitorRect()
            if not callback(handle, None, ctypes.byref(rect), data):
                return 0
        return 1

    monkeypatch.setattr(windows_display, "_load_user32", lambda: SimpleNamespace(
        EnumDisplayMonitors=enumerate_monitors, GetMonitorInfoW=get_info,
    ))


def test_native_monitor_list_preserves_identity_geometry_and_nonfirst_primary(monkeypatch):
    _fake_monitor_api(monkeypatch)
    assert windows_display.query_windows_monitors() == (
        WindowsMonitor(r"\\.\DISPLAY2", False, 1920, 1080, -1920, 0),
        WindowsMonitor(r"\\.\DISPLAY1", True, 2560, 1440, 0, 0),
    )


@pytest.mark.parametrize(("failure", "flags", "message"), [
    ("info", (0, 1), "identity"),
    ("enumerate", (0, 1), "enumerate"),
    ("duplicate", (0, 1), "ambiguous"),
    (None, (0, 0), "primary"),
    (None, (1, 1), "primary"),
])
def test_native_monitor_list_rejects_unusable_topology(monkeypatch, failure, flags, message):
    _fake_monitor_api(monkeypatch, flags=flags, failure=failure)
    with pytest.raises(WindowsDisplayModeError, match=message):
        windows_display.query_windows_monitors()


def test_selected_mode_matches_device_without_using_primary(monkeypatch):
    monkeypatch.setattr(windows_display, "_load_user32", object)
    monkeypatch.setattr(windows_display, "_query_active_display_paths", lambda _: [
        windows_display._ActiveDisplayPath(r"\\.\DISPLAY1", 60, 1, False),
        windows_display._ActiveDisplayPath(r"\\.\DISPLAY2", 144, 1, False),
    ])
    selected = windows_display.query_windows_display_mode(r"\\.\display2")
    assert selected.hz == 144
    with pytest.raises(WindowsDisplayModeError, match="selected display"):
        windows_display.query_windows_display_mode(r"\\.\DISPLAY3")


def test_recommendation_reads_selected_monitor(monkeypatch):
    names = []

    def query(name):
        names.append(name)
        return windows_display.WindowsDisplayMode(name, 144, 1)

    monkeypatch.setattr(windows_display, "query_windows_display_mode", query)
    assert windows_display.query_windows_refresh_recommendation(r"\\.\DISPLAY2") is None
    assert names == [r"\\.\DISPLAY2"]


@pytest.mark.parametrize("selection", ["name", "index", "primary"])
def test_refresh_checks_and_probes_same_monitor(monkeypatch, selection):
    set_module_platform(monkeypatch, display_refresh, "win32")
    set_module_platform(monkeypatch, display_mode, "win32")
    checked = []
    probed = []

    def native(name=None):
        checked.append(name)
        return windows_display.WindowsDisplayMode(name or r"\\.\DISPLAY2", 144, 1)

    def measure(*, runtime_options):
        probed.append(runtime_options)
        return 144.0

    monkeypatch.setattr(windows_display, "query_windows_display_mode", native)
    monkeypatch.setattr(windows_display, "query_windows_monitors", lambda: (
        WindowsMonitor(r"\\.\DISPLAY1", False, 1920, 1080),
        WindowsMonitor(r"\\.\DISPLAY2", True, 2560, 1440),
    ))
    options = {"fullscreen": True}
    if selection == "name":
        options["display_device_name"] = r"\\.\DISPLAY2"
    elif selection == "index":
        options["display_index"] = 1
    engine = cast(PresentationEngine, SimpleNamespace(measure_refresh_hz=measure))
    result = display_refresh.verify_primary_display_refresh(engine, runtime_options=options)
    assert result.approved_hz == 144
    assert checked == [None if selection == "primary" else r"\\.\DISPLAY2"]
    assert probed[0]["display_device_name"] == r"\\.\DISPLAY2"
    assert probed[0].get("display_index") is None
    assert options.get("display_index") == (1 if selection == "index" else None)


def _fake_screens(monkeypatch):
    set_module_platform(monkeypatch, psychopy_window, "win32")
    monkeypatch.setattr(windows_display, "query_windows_monitors", lambda: (
        WindowsMonitor(r"\\.\DISPLAY1", True, 1920, 1080),
        WindowsMonitor(r"\\.\DISPLAY2", False, 2560, 1440),
    ))
    screens = [
        SimpleNamespace(get_device_name=lambda: r"\\.\DISPLAY2", width=2560, height=1440),
        SimpleNamespace(get_device_name=lambda: r"\\.\DISPLAY1", width=1920, height=1080),
    ]
    monkeypatch.setattr(psychopy_window, "_pyglet_screens", lambda: screens)
    return screens


def test_default_rendering_uses_windows_primary_independent_of_pyglet_order(monkeypatch):
    _fake_screens(monkeypatch)
    options = psychopy_window.build_window_kwargs({})
    assert options["screen"] == 1
    assert options["winType"] == "pyglet"
    assert options["size"] == [1920, 1080]


def test_named_monitor_rendering_resolves_current_pyglet_order(monkeypatch):
    screens = _fake_screens(monkeypatch)
    options = {"display_device_name": r"\\.\display2"}
    assert psychopy_window.build_window_kwargs(options)["screen"] == 0
    screens.reverse()
    resolved = psychopy_window.build_window_kwargs(options)
    assert resolved["screen"] == 1
    assert resolved["size"] == [2560, 1440]


@pytest.mark.parametrize("failure", ["missing", "ambiguous", "index"])
def test_rendering_never_falls_back_for_disconnected_or_ambiguous_choice(monkeypatch, failure):
    screens = _fake_screens(monkeypatch)
    options = {"display_device_name": r"\\.\DISPLAY2"}
    if failure == "missing":
        screens.pop(0)
    elif failure == "ambiguous":
        screens.append(screens[0])
    else:
        options = {"display_index": 2}
    with pytest.raises(RuntimeError, match="Could not select the presentation monitor"):
        psychopy_window.build_window_kwargs(options)


def test_named_launch_option_is_transient_and_validated(monkeypatch):
    set_module_platform(monkeypatch, launcher, "win32")
    settings = LaunchSettings(
        display_device_name=r"\\.\DISPLAY2", experiment_test_mode=True, serial_enabled=False,
    )
    launcher._validate_launch_settings(settings)
    assert settings.as_runtime_options()["display_device_name"] == r"\\.\DISPLAY2"
    assert "display_device_name" not in LaunchSettings().as_runtime_options()
    with pytest.raises(LaunchSettingsError, match="name or index"):
        launcher._validate_launch_settings(LaunchSettings(
            display_device_name=r"\\.\DISPLAY2", display_index=1,
        ))


def test_legacy_launch_index_is_pinned_before_preflight_and_playback(monkeypatch):
    set_module_platform(monkeypatch, launcher, "win32")
    monkeypatch.setattr(windows_display, "query_windows_monitors", lambda: (
        WindowsMonitor(r"\\.\DISPLAY1", True, 1920, 1080),
        WindowsMonitor(r"\\.\DISPLAY2", False, 2560, 1440),
    ))
    settings = LaunchSettings(display_index=1)
    options = launcher._launch_runtime_options(settings)
    assert options["display_device_name"] == r"\\.\DISPLAY2"
    assert options["display_index"] is None
    assert settings.display_index == 1
    with pytest.raises(LaunchSettingsError, match="no longer available"):
        launcher._launch_runtime_options(LaunchSettings(display_index=2))
