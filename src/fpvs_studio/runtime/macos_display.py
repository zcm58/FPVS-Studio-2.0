"""Read connected macOS displays without creating a GUI or choosing a rate.

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
_MAX_ACTIVE_DISPLAYS = 128
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


@dataclass(frozen=True)
class MacOSMonitor:
    """One independently addressable macOS desktop, identified by CoreGraphics."""

    display_id: int
    primary: bool
    pixel_width: int
    pixel_height: int

    @property
    def device_name(self) -> str:
        return f"macos:{self.display_id}"


def macos_display_id(device_name: str) -> int:
    """Decode a canonical launch-only macOS display identity without native calls."""
    prefix = "macos:"
    if not isinstance(device_name, str) or not device_name.startswith(prefix):
        raise DisplayModeError("Choose a valid macOS presentation display, then retry.")
    digits = device_name[len(prefix):]
    if (
        not 1 <= len(digits) <= 10 or not digits.isascii() or not digits.isdecimal()
        or digits.startswith("0")
    ):
        raise DisplayModeError("Choose a valid macOS presentation display, then retry.")
    return _validate_display_id(int(digits))


def _validate_display_id(display_id: int) -> int:
    if type(display_id) is not int or not 0 < display_id <= 0xFFFFFFFF:
        raise DisplayModeError("Choose a valid macOS presentation display, then retry.")
    return display_id


def _load_core_graphics() -> ctypes.CDLL:
    try:
        library = ctypes.CDLL(_CORE_GRAPHICS_PATH)
        library.CGMainDisplayID.argtypes = []
        library.CGMainDisplayID.restype = ctypes.c_uint32
        library.CGDisplayIsActive.argtypes = [ctypes.c_uint32]
        library.CGDisplayIsActive.restype = ctypes.c_uint32
        library.CGGetActiveDisplayList.argtypes = [
            ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
        ]
        library.CGGetActiveDisplayList.restype = ctypes.c_int32
        library.CGDisplayMirrorsDisplay.argtypes = [ctypes.c_uint32]
        library.CGDisplayMirrorsDisplay.restype = ctypes.c_uint32
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


def _query_core_graphics_mode(display_id: int | None = None) -> _CoreGraphicsMode:
    library = _load_core_graphics()
    return _read_core_graphics_mode(library, display_id)


def _read_core_graphics_mode(
    library: ctypes.CDLL, display_id: int | None,
) -> _CoreGraphicsMode:
    try:
        if display_id is None:
            display_id = int(library.CGMainDisplayID())
            if not display_id:
                raise DisplayModeError("macOS has no active default fullscreen display.")
        else:
            _validate_display_id(display_id)
        if not display_id or not library.CGDisplayIsActive(display_id):
            raise DisplayModeError(
                "macOS has no active presentation display for the selected monitor. "
                "Reconnect it or choose another display, then retry."
            )
        if library.CGDisplayMirrorsDisplay(display_id):
            raise DisplayModeError(
                "The selected macOS display mirrors another monitor. "
                "Use extended displays or select the mirror set's primary display."
            )
        mode = library.CGDisplayCopyDisplayMode(display_id)
        if not mode:
            raise DisplayModeError("macOS did not provide the selected display's active mode.")
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


def query_macos_monitors() -> tuple[MacOSMonitor, ...]:
    """Enumerate active desktops without requiring a fixed refresh rate.

    CoreGraphics includes software-mirrored secondary displays in its active list;
    they are not independent destinations and are omitted from this selector.
    """
    if sys.platform != "darwin":
        raise DisplayModeError("The macOS display adapter is only available on macOS.")
    library = _load_core_graphics()
    identifiers = (ctypes.c_uint32 * _MAX_ACTIVE_DISPLAYS)()
    count = ctypes.c_uint32()
    result = library.CGGetActiveDisplayList(
        _MAX_ACTIVE_DISPLAYS, identifiers, ctypes.byref(count),
    )
    if result != 0:
        raise DisplayModeError(f"macOS could not enumerate active displays (error {result}).")
    if not 0 < count.value < _MAX_ACTIVE_DISPLAYS:
        raise DisplayModeError("macOS did not report a complete list of active displays.")
    display_ids = tuple(int(identifiers[index]) for index in range(count.value))
    if len(set(display_ids)) != len(display_ids) or any(not value for value in display_ids):
        raise DisplayModeError("macOS returned ambiguous active display identities.")
    primary_id = int(library.CGMainDisplayID())
    monitors = []
    for display_id in display_ids:
        if library.CGDisplayMirrorsDisplay(display_id):
            continue
        mode = _read_core_graphics_mode(library, display_id)
        monitors.append(MacOSMonitor(
            display_id, display_id == primary_id, mode.pixel_width, mode.pixel_height,
        ))
    if sum(monitor.primary for monitor in monitors) != 1:
        raise DisplayModeError("macOS did not report one active primary display. Try again.")
    if int(library.CGMainDisplayID()) != primary_id:
        raise DisplayModeError("The macOS primary display changed during detection. Try again.")
    return tuple(monitors)


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
                    "macOS could not uniquely match the selected display to its refresh intervals."
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
    """Read a demonstrably fixed native mode for macOS's primary display."""
    return query_macos_display_mode()


def query_macos_display_mode(display_id: int | None = None) -> NativeDisplayMode:
    """Read a demonstrably fixed native mode for the selected macOS display.

    Apple documents unequal minimum/maximum NSScreen intervals as Adaptive Sync:
    https://developer.apple.com/videos/play/wwdc2021/10147/
    A zero CoreGraphics rate is usable only when equal positive AppKit intervals
    supply the fixed native rate. Unknown values never become a nominal 60 Hz.
    """

    if sys.platform != "darwin":
        raise DisplayModeError("The macOS display adapter is only available on macOS.")
    mode = (
        _query_core_graphics_mode() if display_id is None
        else _query_core_graphics_mode(display_id)
    )
    minimum, maximum = _query_refresh_intervals(mode.display_id)
    if not isclose(minimum, maximum, rel_tol=1e-7, abs_tol=0):
        raise DisplayModeError(
            "Adaptive Sync or ProMotion variable refresh is enabled on the selected display. "
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
        display_device_name=f"macos:{mode.display_id}",
        mode_reference=(
            f"display {mode.display_id}; {mode.width} x {mode.height} mode, "
            f"{mode.pixel_width} x {mode.pixel_height} backing pixels"
        ),
    )
