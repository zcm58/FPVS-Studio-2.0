"""Read the default macOS display mode without creating a GUI or choosing a rate.

CoreGraphics supplies the active mode and Retina backing dimensions. AppKit's
native refresh intervals establish whether that same display has a fixed mode;
CoreGraphics alone may report zero for a built-in or variable-refresh display.
All framework imports and calls stay lazy so this module is portable to import.
"""

from __future__ import annotations

import ctypes
import importlib
import sys
from dataclasses import dataclass
from math import isclose, isfinite

from fpvs_studio.runtime.display_mode import DisplayModeError, NativeDisplayMode

_CORE_GRAPHICS_PATH = "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
_FIXED_RATE_GUIDANCE = (
    "Choose a fixed refresh rate in macOS System Settings > Displays, then check again."
)


@dataclass(frozen=True)
class _CoreGraphicsMode:
    display_id: int
    refresh_hz: float
    width: int
    height: int
    pixel_width: int
    pixel_height: int


def _load_core_graphics() -> ctypes.CDLL:
    try:
        library = ctypes.CDLL(_CORE_GRAPHICS_PATH)
        library.CGMainDisplayID.argtypes = []
        library.CGMainDisplayID.restype = ctypes.c_uint32
        library.CGDisplayIsActive.argtypes = [ctypes.c_uint32]
        library.CGDisplayIsActive.restype = ctypes.c_uint32
        library.CGDisplayCopyDisplayMode.argtypes = [ctypes.c_uint32]
        library.CGDisplayCopyDisplayMode.restype = ctypes.c_void_p
        library.CGDisplayModeGetRefreshRate.argtypes = [ctypes.c_void_p]
        library.CGDisplayModeGetRefreshRate.restype = ctypes.c_double
        for name in (
            "CGDisplayModeGetWidth",
            "CGDisplayModeGetHeight",
            "CGDisplayModeGetPixelWidth",
            "CGDisplayModeGetPixelHeight",
        ):
            function = getattr(library, name)
            function.argtypes = [ctypes.c_void_p]
            function.restype = ctypes.c_size_t
        library.CGDisplayModeRelease.argtypes = [ctypes.c_void_p]
        library.CGDisplayModeRelease.restype = None
    except (OSError, AttributeError) as exc:
        raise DisplayModeError(f"macOS CoreGraphics display APIs are unavailable: {exc}") from exc
    return library


def _query_core_graphics_mode() -> _CoreGraphicsMode:
    library = _load_core_graphics()
    try:
        display_id = int(library.CGMainDisplayID())
        if not display_id or not library.CGDisplayIsActive(display_id):
            raise DisplayModeError("macOS has no active default fullscreen display.")
        mode = library.CGDisplayCopyDisplayMode(display_id)
        if not mode:
            raise DisplayModeError("macOS did not provide the active default display mode.")
        try:
            result = _CoreGraphicsMode(
                display_id=display_id,
                refresh_hz=float(library.CGDisplayModeGetRefreshRate(mode)),
                width=int(library.CGDisplayModeGetWidth(mode)),
                height=int(library.CGDisplayModeGetHeight(mode)),
                pixel_width=int(library.CGDisplayModeGetPixelWidth(mode)),
                pixel_height=int(library.CGDisplayModeGetPixelHeight(mode)),
            )
        finally:
            library.CGDisplayModeRelease(mode)
    except DisplayModeError:
        raise
    except Exception as exc:
        raise DisplayModeError(f"macOS active display mode could not be read: {exc}") from exc
    if min(result.width, result.height, result.pixel_width, result.pixel_height) <= 0:
        raise DisplayModeError("macOS reported invalid active display dimensions.")
    if not isfinite(result.refresh_hz) or result.refresh_hz < 0:
        raise DisplayModeError("macOS reported an invalid native display refresh rate.")
    return result


def _query_refresh_intervals(display_id: int) -> tuple[float, float]:
    try:
        appkit = importlib.import_module("AppKit")
        objc = importlib.import_module("objc")
    except (ImportError, OSError) as exc:
        raise DisplayModeError(
            "macOS refresh detection requires the pyobjc-framework-Cocoa dependency."
        ) from exc
    try:
        # AppKit objects used by a launch worker need a thread-local autorelease pool.
        with objc.autorelease_pool():
            screens = [
                screen
                for screen in appkit.NSScreen.screens()
                if int(screen.deviceDescription()["NSScreenNumber"]) == display_id
            ]
            if len(screens) != 1:
                raise DisplayModeError(
                    "macOS could not uniquely match the default display to its refresh intervals."
                )
            # Do not use mainScreen(): it follows keyboard focus rather than CGMainDisplayID.
            screen = screens[0]
            minimum = float(screen.minimumRefreshInterval())
            maximum = float(screen.maximumRefreshInterval())
    except DisplayModeError:
        raise
    except Exception as exc:
        raise DisplayModeError(
            "macOS could not read native refresh intervals; macOS 12 or later is required. "
            + _FIXED_RATE_GUIDANCE
        ) from exc
    if not isfinite(minimum) or not isfinite(maximum) or not 0 < minimum <= maximum:
        raise DisplayModeError(
            "macOS did not report valid native refresh intervals. " + _FIXED_RATE_GUIDANCE
        )
    return minimum, maximum


def query_primary_macos_display_mode() -> NativeDisplayMode:
    """Read a demonstrably fixed native mode for macOS's default fullscreen display.

    Apple documents unequal minimum/maximum NSScreen intervals as Adaptive Sync:
    https://developer.apple.com/videos/play/wwdc2021/10147/
    A zero CoreGraphics rate is usable only when equal positive AppKit intervals
    supply the fixed native rate. Unknown values never become a nominal 60 Hz.
    """

    if sys.platform != "darwin":
        raise DisplayModeError("The macOS display adapter is only available on macOS.")
    mode = _query_core_graphics_mode()
    minimum, maximum = _query_refresh_intervals(mode.display_id)
    if not isclose(minimum, maximum, rel_tol=1e-7, abs_tol=0):
        raise DisplayModeError(
            "Adaptive Sync or ProMotion variable refresh is enabled on the default display. "
            + _FIXED_RATE_GUIDANCE
        )
    interval_hz = 1.0 / minimum
    if not isfinite(interval_hz):
        raise DisplayModeError("macOS reported an invalid native display refresh interval.")
    refresh_hz = mode.refresh_hz or interval_hz
    if not isclose(refresh_hz, interval_hz, rel_tol=0.0001, abs_tol=0):
        raise DisplayModeError(
            "macOS native mode and refresh intervals disagree; the display mode may have changed. "
            "Check the display again before starting."
        )
    return NativeDisplayMode(
        platform_name="macOS",
        display_name=f"Display {mode.display_id}",
        refresh_hz=refresh_hz,
        source_name="CoreGraphics/AppKit",
        exact_refresh=False,
        pixel_width=mode.pixel_width,
        pixel_height=mode.pixel_height,
        mode_reference=(
            f"display {mode.display_id}; {mode.width} x {mode.height} mode, "
            f"{mode.pixel_width} x {mode.pixel_height} backing pixels"
        ),
    )
