"""Native macOS monitor selection with fake CoreGraphics and AppKit metadata."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from tests.platform_adapters import set_module_platform

from fpvs_studio.runtime import display_mode, macos_display
from fpvs_studio.runtime.display_mode import DisplayModeError


def _native_topology(
    monkeypatch, *, identifiers=(7, 42), primary=42, mirrors=None, inactive=(), error=0,
):
    mirrors = mirrors or {}
    sizes = {7: (1920, 1080, 1920, 1080), 42: (1512, 982, 3024, 1964)}

    def active_displays(capacity, values, count):
        count._obj.value = len(identifiers)
        for index, identifier in enumerate(identifiers[:capacity]):
            values[index] = identifier
        return error

    library = SimpleNamespace(
        CGMainDisplayID=Mock(return_value=primary),
        CGGetActiveDisplayList=active_displays,
        CGDisplayIsActive=lambda identifier: (
            identifier in identifiers and identifier not in inactive
        ),
        CGDisplayMirrorsDisplay=lambda identifier: mirrors.get(identifier, 0),
        CGDisplayCopyDisplayMode=lambda identifier: identifier,
        CGDisplayModeGetRefreshRate=lambda identifier: 0.0 if identifier == 42 else 144.0,
        CGDisplayModeGetWidth=lambda identifier: sizes[identifier][0],
        CGDisplayModeGetHeight=lambda identifier: sizes[identifier][1],
        CGDisplayModeGetPixelWidth=lambda identifier: sizes[identifier][2],
        CGDisplayModeGetPixelHeight=lambda identifier: sizes[identifier][3],
        CGDisplayModeRelease=Mock(),
    )
    set_module_platform(monkeypatch, macos_display, "darwin")
    monkeypatch.setattr(macos_display, "_load_core_graphics", lambda: library)
    return library


def test_discovery_uses_native_primary_and_retina_pixels_without_refresh_gate(monkeypatch):
    library = _native_topology(monkeypatch)
    intervals = Mock(side_effect=AssertionError("Enumeration must not require a fixed mode"))
    monkeypatch.setattr(macos_display, "_query_refresh_intervals", intervals)

    monitors = macos_display.query_macos_monitors()

    assert monitors == (
        macos_display.MacOSMonitor(7, False, 1920, 1080),
        macos_display.MacOSMonitor(42, True, 3024, 1964),
    )
    assert monitors[1].device_name == "macos:42"
    intervals.assert_not_called()
    assert library.CGDisplayModeRelease.call_count == 2


def test_selected_fixed_external_display_is_independent_of_variable_primary(monkeypatch):
    _native_topology(monkeypatch)
    intervals = Mock(side_effect=lambda identifier: (
        (1 / 144, 1 / 144) if identifier == 7 else (1 / 120, 1 / 48)
    ))
    monkeypatch.setattr(macos_display, "_query_refresh_intervals", intervals)

    selected = macos_display.query_macos_display_mode(7)

    assert selected.display_device_name == "macos:7"
    assert selected.display_name == "Display 7"
    assert selected.refresh_hz == 144
    assert (selected.pixel_width, selected.pixel_height) == (1920, 1080)
    intervals.assert_called_once_with(7)
    with pytest.raises(DisplayModeError, match="Adaptive Sync or ProMotion"):
        macos_display.query_primary_macos_display_mode()


def test_mirrored_secondary_is_not_an_independent_choice_and_cannot_be_selected(monkeypatch):
    _native_topology(monkeypatch, mirrors={7: 42})

    assert macos_display.query_macos_monitors() == (
        macos_display.MacOSMonitor(42, True, 3024, 1964),
    )
    with pytest.raises(DisplayModeError, match="mirrors another monitor"):
        macos_display.query_macos_display_mode(7)


def test_single_active_display_is_returned_without_artificial_mirror_entries(monkeypatch):
    _native_topology(monkeypatch, identifiers=(42,))
    assert macos_display.query_macos_monitors() == (
        macos_display.MacOSMonitor(42, True, 3024, 1964),
    )


@pytest.mark.parametrize(("kwargs", "message"), [
    ({"identifiers": ()}, "complete list"),
    ({"identifiers": (7, 7)}, "ambiguous"),
    ({"identifiers": (0, 42)}, "ambiguous"),
    ({"primary": 99}, "one active primary"),
    ({"inactive": (7,)}, "no active presentation"),
    ({"error": 1001}, "error 1001"),
])
def test_discovery_fails_for_unusable_topology(monkeypatch, kwargs, message):
    _native_topology(monkeypatch, **kwargs)
    with pytest.raises(DisplayModeError, match=message):
        macos_display.query_macos_monitors()


def test_discovery_rejects_primary_change_during_enumeration(monkeypatch):
    library = _native_topology(monkeypatch)
    library.CGMainDisplayID.side_effect = [42, 7]
    with pytest.raises(DisplayModeError, match="primary display changed"):
        macos_display.query_macos_monitors()


def test_disconnected_selection_fails_without_default_fallback(monkeypatch):
    _native_topology(monkeypatch)
    with pytest.raises(DisplayModeError, match="Reconnect it or choose another display"):
        macos_display.query_macos_display_mode(99)


@pytest.mark.parametrize("name", [
    "", "macos:", "macos:0", "macos:-1", "macos:042", "macos:1.0", "macos:4294967296",
    "macos:４２", "macos:42 ", "MACOS:42", r"\\.\DISPLAY1", None, 42,
])
def test_invalid_launch_identity_is_rejected_without_native_calls(name):
    with pytest.raises(DisplayModeError, match="valid macOS presentation display"):
        macos_display.macos_display_id(name)


@pytest.mark.parametrize("identifier", [1, 42, 0xFFFFFFFF])
def test_canonical_launch_identity_round_trips(identifier):
    monitor = macos_display.MacOSMonitor(identifier, True, 1920, 1080)
    assert macos_display.macos_display_id(monitor.device_name) == identifier


def test_platform_dispatch_preserves_selected_native_identity(monkeypatch):
    set_module_platform(monkeypatch, display_mode, "darwin")
    selected = object()
    query = Mock(return_value=selected)
    monkeypatch.setattr(macos_display, "query_macos_display_mode", query)
    assert display_mode.query_native_display_mode("macos:42") is selected
    query.assert_called_once_with(42)


def test_monitor_discovery_is_guarded_on_other_platforms(monkeypatch):
    set_module_platform(monkeypatch, macos_display, "win32")
    query = Mock(side_effect=AssertionError("Must not load CoreGraphics"))
    monkeypatch.setattr(macos_display, "_load_core_graphics", query)
    with pytest.raises(DisplayModeError, match="only available on macOS"):
        macos_display.query_macos_monitors()
    query.assert_not_called()
