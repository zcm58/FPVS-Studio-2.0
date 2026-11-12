"""Fake-backed native macOS display detection; no AppKit, Qt or hardware is loaded."""

from __future__ import annotations

import ctypes
from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any

import pytest
from tests.platform_adapters import set_module_platform

from fpvs_studio.runtime import display_mode as display_mode_module
from fpvs_studio.runtime import macos_display
from fpvs_studio.runtime.display_mode import DisplayModeError, NativeDisplayMode


class _Function:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[tuple[object, ...]] = []
        self.argtypes: list[object] | None = None
        self.restype: object = None

    def __call__(self, *args: object) -> Any:
        self.calls.append(args)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _library(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "CGMainDisplayID": 42,
        "CGDisplayIsActive": 1,
        "CGDisplayMirrorsDisplay": 0,
        "CGGetActiveDisplayList": 0,
        "CGDisplayCopyDisplayMode": 1234,
        "CGDisplayModeGetRefreshRate": 60.0,
        "CGDisplayModeGetWidth": 1512,
        "CGDisplayModeGetHeight": 982,
        "CGDisplayModeGetPixelWidth": 3024,
        "CGDisplayModeGetPixelHeight": 1964,
        "CGDisplayModeRelease": None,
    }
    values.update(overrides)
    return SimpleNamespace(**{name: _Function(value) for name, value in values.items()})


def _mode(refresh_hz: float = 60.0) -> macos_display._CoreGraphicsMode:
    return macos_display._CoreGraphicsMode(42, refresh_hz, 1512, 982, 3024, 1964)


def _screen(display_id: int, minimum: float = 1 / 60, maximum: float = 1 / 60) -> object:
    return SimpleNamespace(
        deviceDescription=lambda: {"NSScreenNumber": display_id},
        minimumRefreshInterval=lambda: minimum,
        maximumRefreshInterval=lambda: maximum,
    )


def _appkit(monkeypatch: pytest.MonkeyPatch, screens: list[object]) -> list[str]:
    imports: list[str] = []
    modules = {
        "AppKit": SimpleNamespace(NSScreen=SimpleNamespace(screens=lambda: screens)),
        "objc": SimpleNamespace(autorelease_pool=nullcontext),
    }

    def _import(name: str) -> object:
        imports.append(name)
        return modules[name]

    monkeypatch.setattr(macos_display.importlib, "import_module", _import)
    return imports


def test_core_graphics_uses_native_abi_and_preserves_retina_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    library = _library()
    loaded: list[str] = []

    def _load(path: str) -> object:
        loaded.append(path)
        return library

    monkeypatch.setattr(macos_display.ctypes, "CDLL", _load)

    mode = macos_display._query_core_graphics_mode()

    assert mode == _mode()
    assert loaded == [macos_display._CORE_GRAPHICS_PATH]
    assert library.CGMainDisplayID.argtypes == []
    assert library.CGMainDisplayID.restype is ctypes.c_uint32
    assert library.CGDisplayIsActive.argtypes == [ctypes.c_uint32]
    assert library.CGDisplayCopyDisplayMode.restype is ctypes.c_void_p
    assert library.CGDisplayModeGetRefreshRate.argtypes == [ctypes.c_void_p]
    assert library.CGDisplayModeGetRefreshRate.restype is ctypes.c_double
    for name in (
        "CGDisplayModeGetWidth",
        "CGDisplayModeGetHeight",
        "CGDisplayModeGetPixelWidth",
        "CGDisplayModeGetPixelHeight",
    ):
        assert getattr(library, name).restype is ctypes.c_size_t
    assert library.CGDisplayModeRelease.restype is None
    assert library.CGDisplayModeRelease.calls == [(1234,)]
    assert library.CGDisplayIsActive.calls == [(42,)]
    assert library.CGDisplayCopyDisplayMode.calls == [(42,)]


@pytest.mark.parametrize(
    ("overrides", "message", "released"),
    [
        ({"CGMainDisplayID": 0}, "no active", False),
        ({"CGDisplayIsActive": 0}, "no active", False),
        ({"CGDisplayCopyDisplayMode": 0}, "did not provide", False),
        ({"CGDisplayModeGetWidth": 0}, "invalid active display dimensions", True),
        ({"CGDisplayModeGetPixelHeight": 0}, "invalid active display dimensions", True),
        ({"CGDisplayModeGetRefreshRate": -1.0}, "invalid native display refresh", True),
        ({"CGDisplayModeGetRefreshRate": float("nan")}, "invalid native display refresh", True),
        ({"CGDisplayModeGetRefreshRate": float("inf")}, "invalid native display refresh", True),
        ({"CGDisplayModeGetWidth": OSError("mode changed")}, "could not be read", True),
    ],
)
def test_core_graphics_rejects_missing_or_invalid_mode_and_releases_copy(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, object],
    message: str,
    released: bool,
) -> None:
    library = _library(**overrides)
    monkeypatch.setattr(macos_display, "_load_core_graphics", lambda: library)

    with pytest.raises(DisplayModeError, match=message):
        macos_display._query_core_graphics_mode()

    assert library.CGDisplayModeRelease.calls == ([(1234,)] if released else [])


@pytest.mark.parametrize("failure", [OSError("framework missing"), AttributeError("API missing")])
def test_core_graphics_missing_framework_or_api_is_actionable(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    def _load(_path: str) -> object:
        raise failure

    monkeypatch.setattr(macos_display.ctypes, "CDLL", _load)

    with pytest.raises(DisplayModeError, match="CoreGraphics display APIs are unavailable"):
        macos_display._load_core_graphics()


def test_appkit_matches_core_graphics_display_instead_of_focused_or_first_screen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    imports = _appkit(monkeypatch, [_screen(99, 1 / 144, 1 / 144), _screen(42)])

    assert macos_display._query_refresh_intervals(42) == (1 / 60, 1 / 60)
    assert imports == ["AppKit", "objc"]


@pytest.mark.parametrize("screens", [[], [_screen(99)], [_screen(42), _screen(42)]])
def test_appkit_rejects_missing_or_ambiguous_default_screen(
    monkeypatch: pytest.MonkeyPatch, screens: list[object]
) -> None:
    _appkit(monkeypatch, screens)

    with pytest.raises(DisplayModeError, match="uniquely match"):
        macos_display._query_refresh_intervals(42)


@pytest.mark.parametrize(
    ("minimum", "maximum"),
    [(0.0, 0.0), (-1.0, 1.0), (1.0, 0.5), (float("nan"), 1.0), (1.0, float("inf"))],
)
def test_appkit_rejects_unknown_or_invalid_refresh_intervals(
    monkeypatch: pytest.MonkeyPatch, minimum: float, maximum: float
) -> None:
    _appkit(monkeypatch, [_screen(42, minimum, maximum)])

    with pytest.raises(DisplayModeError, match="valid native refresh intervals"):
        macos_display._query_refresh_intervals(42)


def test_appkit_missing_native_interval_api_does_not_use_nominal_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _appkit(monkeypatch, [SimpleNamespace(deviceDescription=lambda: {"NSScreenNumber": 42})])

    with pytest.raises(DisplayModeError, match="macOS 12 or later"):
        macos_display._query_refresh_intervals(42)


def test_appkit_missing_dependency_has_install_guidance(monkeypatch: pytest.MonkeyPatch) -> None:
    def _import(_name: str) -> object:
        raise ImportError("not installed")

    monkeypatch.setattr(macos_display.importlib, "import_module", _import)

    with pytest.raises(DisplayModeError, match="pyobjc-framework-Cocoa"):
        macos_display._query_refresh_intervals(42)


@pytest.mark.parametrize("refresh_hz", [60.0, 60_000 / 1001, 120.0])
def test_macos_fixed_rate_preserves_native_precision_and_retina_reference(
    monkeypatch: pytest.MonkeyPatch, refresh_hz: float
) -> None:
    set_module_platform(monkeypatch, macos_display, "darwin")
    monkeypatch.setattr(macos_display, "_query_core_graphics_mode", lambda: _mode(refresh_hz))
    display_ids: list[int] = []

    def _intervals(display_id: int) -> tuple[float, float]:
        display_ids.append(display_id)
        return 1 / refresh_hz, 1 / refresh_hz

    monkeypatch.setattr(macos_display, "_query_refresh_intervals", _intervals)

    mode = macos_display.query_primary_macos_display_mode()

    assert display_ids == [42]
    assert mode.platform_name == "macOS"
    assert mode.display_name == "Display 42"
    assert mode.refresh_hz == refresh_hz
    assert mode.exact_refresh is False
    assert mode.variable_refresh_enabled is False
    assert mode.source_name == "CoreGraphics/AppKit"
    assert (mode.pixel_width, mode.pixel_height) == (3024, 1964)
    assert mode.mode_reference == "display 42; 1512 x 982 mode, 3024 x 1964 backing pixels"


def test_zero_core_graphics_rate_requires_a_fixed_positive_native_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_module_platform(monkeypatch, macos_display, "darwin")
    monkeypatch.setattr(macos_display, "_query_core_graphics_mode", lambda: _mode(0.0))
    monkeypatch.setattr(macos_display, "_query_refresh_intervals", lambda _id: (1 / 120, 1 / 120))

    assert macos_display.query_primary_macos_display_mode().refresh_hz == 120.0


@pytest.mark.parametrize("refresh_hz", [0.0, 60.0, 120.0])
def test_adaptive_sync_and_promotion_are_rejected_even_with_a_nominal_rate(
    monkeypatch: pytest.MonkeyPatch, refresh_hz: float
) -> None:
    set_module_platform(monkeypatch, macos_display, "darwin")
    monkeypatch.setattr(macos_display, "_query_core_graphics_mode", lambda: _mode(refresh_hz))
    monkeypatch.setattr(macos_display, "_query_refresh_intervals", lambda _id: (1 / 120, 1 / 48))

    with pytest.raises(DisplayModeError, match="Adaptive Sync or ProMotion.*fixed refresh rate"):
        macos_display.query_primary_macos_display_mode()



def test_native_interval_must_produce_a_finite_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    set_module_platform(monkeypatch, macos_display, "darwin")
    monkeypatch.setattr(macos_display, "_query_core_graphics_mode", lambda: _mode(0.0))
    monkeypatch.setattr(macos_display, "_query_refresh_intervals", lambda _id: (5e-324, 5e-324))

    with pytest.raises(DisplayModeError, match="invalid native display refresh interval"):
        macos_display.query_primary_macos_display_mode()


def test_disagreeing_native_rates_fail_without_rounding_5994_to_60(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_module_platform(monkeypatch, macos_display, "darwin")
    monkeypatch.setattr(macos_display, "_query_core_graphics_mode", lambda: _mode(60_000 / 1001))
    monkeypatch.setattr(macos_display, "_query_refresh_intervals", lambda _id: (1 / 60, 1 / 60))

    with pytest.raises(DisplayModeError, match="native mode and refresh intervals disagree"):
        macos_display.query_primary_macos_display_mode()


def test_macos_adapter_is_guarded_before_loading_native_frameworks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_module_platform(monkeypatch, macos_display, "win32")
    monkeypatch.setattr(
        macos_display, "_query_core_graphics_mode", lambda: pytest.fail("loaded native framework")
    )

    with pytest.raises(DisplayModeError, match="only available on macOS"):
        macos_display.query_primary_macos_display_mode()


def test_platform_selector_lazily_dispatches_to_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = NativeDisplayMode("macOS", "Display 42", 60.0, "CoreGraphics/AppKit", False)
    set_module_platform(monkeypatch, display_mode_module, "darwin")
    monkeypatch.setattr(macos_display, "query_primary_macos_display_mode", lambda: expected)

    assert display_mode_module.query_primary_native_display_mode() is expected


def test_platform_selector_preserves_macos_detection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    set_module_platform(monkeypatch, display_mode_module, "darwin")

    def _query() -> NativeDisplayMode:
        raise DisplayModeError("No fixed native rate")

    monkeypatch.setattr(macos_display, "query_primary_macos_display_mode", _query)

    with pytest.raises(DisplayModeError, match="No fixed native rate"):
        display_mode_module.query_primary_native_display_mode()
