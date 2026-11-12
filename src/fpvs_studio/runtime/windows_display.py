"""Windows active-display mode queries used by runtime refresh verification."""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from typing import Any

_QDC_ONLY_ACTIVE_PATHS = 0x00000002
_QDC_VIRTUAL_MODE_AWARE = 0x00000010
_QDC_VIRTUAL_REFRESH_RATE_AWARE = 0x00000040
_ERROR_SUCCESS = 0
_ERROR_INVALID_PARAMETER = 87
_ERROR_INSUFFICIENT_BUFFER = 122
_DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x00000001
_DISPLAY_DEVICE_PRIMARY_DEVICE = 0x00000004
_DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME = 1
_DISPLAYCONFIG_PATH_ACTIVE = 0x00000001
_DISPLAYCONFIG_PATH_BOOST_REFRESH_RATE = 0x00000010
_ENUM_CURRENT_SETTINGS = 0xFFFFFFFF
_DM_INTERLACED = 0x00000002
_MONITORINFOF_PRIMARY = 0x00000001

_UINT32 = ctypes.c_uint32
_UINT64 = ctypes.c_uint64
_LONG = ctypes.c_long
_BOOL = ctypes.c_int


class WindowsDisplayModeError(RuntimeError):
    """Raised when the exact active Windows display mode cannot be determined."""


class _VirtualRefreshQueryUnsupported(RuntimeError):
    """Signal that the Windows 11 virtual-refresh query flag is unavailable."""


class _Luid(ctypes.Structure):
    _fields_ = [("LowPart", _UINT32), ("HighPart", _LONG)]


class _DisplayConfigRational(ctypes.Structure):
    _fields_ = [("Numerator", _UINT32), ("Denominator", _UINT32)]


class _DisplayConfigPathSourceModeInfoIdxParts(ctypes.Structure):
    _fields_ = [("cloneGroupId", _UINT32, 16), ("sourceModeInfoIdx", _UINT32, 16)]


class _DisplayConfigPathSourceModeInfoIdx(ctypes.Union):
    _fields_ = [
        ("modeInfoIdx", _UINT32),
        ("parts", _DisplayConfigPathSourceModeInfoIdxParts),
    ]


class _DisplayConfigPathTargetModeInfoIdxParts(ctypes.Structure):
    _fields_ = [("desktopModeInfoIdx", _UINT32, 16), ("targetModeInfoIdx", _UINT32, 16)]


class _DisplayConfigPathTargetModeInfoIdx(ctypes.Union):
    _fields_ = [
        ("modeInfoIdx", _UINT32),
        ("parts", _DisplayConfigPathTargetModeInfoIdxParts),
    ]


class _DisplayConfigPathSourceInfo(ctypes.Structure):
    _fields_ = [
        ("adapterId", _Luid),
        ("id", _UINT32),
        ("modeInfoIdx", _DisplayConfigPathSourceModeInfoIdx),
        ("statusFlags", _UINT32),
    ]


class _DisplayConfigPathTargetInfo(ctypes.Structure):
    _fields_ = [
        ("adapterId", _Luid),
        ("id", _UINT32),
        ("modeInfoIdx", _DisplayConfigPathTargetModeInfoIdx),
        ("outputTechnology", _UINT32),
        ("rotation", _UINT32),
        ("scaling", _UINT32),
        ("refreshRate", _DisplayConfigRational),
        ("scanLineOrdering", _UINT32),
        ("targetAvailable", _BOOL),
        ("statusFlags", _UINT32),
    ]


class _DisplayConfigPathInfo(ctypes.Structure):
    _fields_ = [
        ("sourceInfo", _DisplayConfigPathSourceInfo),
        ("targetInfo", _DisplayConfigPathTargetInfo),
        ("flags", _UINT32),
    ]


class _DisplayConfig2DRegion(ctypes.Structure):
    _fields_ = [("cx", _UINT32), ("cy", _UINT32)]


class _DisplayConfigAdditionalSignalInfo(ctypes.Structure):
    _fields_ = [
        ("videoStandard", _UINT32, 16),
        ("vSyncFreqDivider", _UINT32, 6),
        ("reserved", _UINT32, 10),
    ]


class _DisplayConfigVideoStandard(ctypes.Union):
    _fields_ = [
        ("additionalSignalInfo", _DisplayConfigAdditionalSignalInfo),
        ("videoStandard", _UINT32),
    ]


class _DisplayConfigVideoSignalInfo(ctypes.Structure):
    _fields_ = [
        ("pixelRate", _UINT64),
        ("hSyncFreq", _DisplayConfigRational),
        ("vSyncFreq", _DisplayConfigRational),
        ("activeSize", _DisplayConfig2DRegion),
        ("totalSize", _DisplayConfig2DRegion),
        ("videoStandard", _DisplayConfigVideoStandard),
        ("scanLineOrdering", _UINT32),
    ]


class _DisplayConfigTargetMode(ctypes.Structure):
    _fields_ = [("targetVideoSignalInfo", _DisplayConfigVideoSignalInfo)]


class _PointL(ctypes.Structure):
    _fields_ = [("x", _LONG), ("y", _LONG)]


class _RectL(ctypes.Structure):
    _fields_ = [("left", _LONG), ("top", _LONG), ("right", _LONG), ("bottom", _LONG)]


class _DisplayConfigSourceMode(ctypes.Structure):
    _fields_ = [
        ("width", _UINT32),
        ("height", _UINT32),
        ("pixelFormat", _UINT32),
        ("position", _PointL),
    ]


class _DisplayConfigDesktopImageInfo(ctypes.Structure):
    _fields_ = [
        ("pathSourceSize", _PointL),
        ("desktopImageRegion", _RectL),
        ("desktopImageClip", _RectL),
    ]


class _DisplayConfigModeInfoData(ctypes.Union):
    _fields_ = [
        ("targetMode", _DisplayConfigTargetMode),
        ("sourceMode", _DisplayConfigSourceMode),
        ("desktopImageInfo", _DisplayConfigDesktopImageInfo),
    ]


class _DisplayConfigModeInfo(ctypes.Structure):
    _fields_ = [
        ("infoType", _UINT32),
        ("id", _UINT32),
        ("adapterId", _Luid),
        ("data", _DisplayConfigModeInfoData),
    ]


class _DisplayConfigDeviceInfoHeader(ctypes.Structure):
    _fields_ = [
        ("type", _UINT32),
        ("size", _UINT32),
        ("adapterId", _Luid),
        ("id", _UINT32),
    ]


class _DisplayConfigSourceDeviceName(ctypes.Structure):
    _fields_ = [
        ("header", _DisplayConfigDeviceInfoHeader),
        ("viewGdiDeviceName", ctypes.c_wchar * 32),
    ]


class _DisplayDeviceW(ctypes.Structure):
    _fields_ = [
        ("cb", _UINT32),
        ("DeviceName", ctypes.c_wchar * 32),
        ("DeviceString", ctypes.c_wchar * 128),
        ("StateFlags", _UINT32),
        ("DeviceID", ctypes.c_wchar * 128),
        ("DeviceKey", ctypes.c_wchar * 128),
    ]


class _MonitorRect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_int32), ("top", ctypes.c_int32),
        ("right", ctypes.c_int32), ("bottom", ctypes.c_int32),
    ]


class _MonitorInfoExW(ctypes.Structure):
    _fields_ = [
        ("cbSize", _UINT32),
        ("rcMonitor", _MonitorRect),
        ("rcWork", _MonitorRect),
        ("dwFlags", _UINT32),
        ("szDevice", ctypes.c_wchar * 32),
    ]


@dataclass(frozen=True)
class WindowsMonitor:
    """One independently addressable Windows desktop monitor."""

    device_name: str
    primary: bool
    pixel_width: int
    pixel_height: int
    x: int = 0
    y: int = 0


def query_windows_monitors() -> tuple[WindowsMonitor, ...]:
    """Enumerate desktop monitors without importing a GUI or graphics toolkit.

    The native enumeration order also supports the existing Pyglet index API.
    New callers retain the device name so topology changes cannot retarget a choice.
    """
    user32 = _load_user32()
    callback_type = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(
        _BOOL, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_MonitorRect), ctypes.c_ssize_t,
    )
    user32.EnumDisplayMonitors.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, callback_type, ctypes.c_ssize_t,
    ]
    user32.EnumDisplayMonitors.restype = _BOOL
    user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MonitorInfoExW)]
    user32.GetMonitorInfoW.restype = _BOOL
    monitors: list[WindowsMonitor] = []
    errors: list[str] = []

    def collect(handle: int, _dc: int, _rect: Any, _data: int) -> int:
        info = _MonitorInfoExW()
        info.cbSize = ctypes.sizeof(info)
        if not user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            errors.append("Windows could not read a connected monitor's identity.")
            return 0
        name = str(info.szDevice).strip()
        rect = info.rcMonitor
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if not name or width <= 0 or height <= 0:
            errors.append("Windows returned an incomplete connected monitor description.")
            return 0
        monitors.append(WindowsMonitor(
            name, bool(info.dwFlags & _MONITORINFOF_PRIMARY), width, height,
            rect.left, rect.top,
        ))
        return 1

    callback = callback_type(collect)
    succeeded = user32.EnumDisplayMonitors(None, None, callback, 0)
    if errors:
        raise WindowsDisplayModeError(errors[0])
    if not succeeded or not monitors:
        raise WindowsDisplayModeError("Windows could not enumerate connected monitors.")
    if len({monitor.device_name.casefold() for monitor in monitors}) != len(monitors):
        raise WindowsDisplayModeError("Windows returned ambiguous monitor identities.")
    if sum(monitor.primary for monitor in monitors) != 1:
        raise WindowsDisplayModeError("Windows did not report one active primary monitor.")
    return tuple(monitors)


class _DevModeW(ctypes.Structure):
    # Public DEVMODEW layout. Unused WCHAR arrays use the Win32 16-bit ABI
    # even when tests run on a platform with a different native wchar width.
    _fields_ = [
        ("dmDeviceName", ctypes.c_uint16 * 32),
        ("dmSpecVersion", ctypes.c_uint16),
        ("dmDriverVersion", ctypes.c_uint16),
        ("dmSize", ctypes.c_uint16),
        ("dmDriverExtra", ctypes.c_uint16),
        ("dmFields", _UINT32),
        ("printer_or_display", _UINT32 * 4),
        ("printer_fields", ctypes.c_uint16 * 5),
        ("dmFormName", ctypes.c_uint16 * 32),
        ("dmLogPixels", ctypes.c_uint16),
        ("dmBitsPerPel", _UINT32),
        ("dmPelsWidth", _UINT32),
        ("dmPelsHeight", _UINT32),
        ("dmDisplayFlags", _UINT32),
        ("dmDisplayFrequency", _UINT32),
        ("remaining_fields", _UINT32 * 8),
    ]


@dataclass(frozen=True)
class WindowsRefreshRecommendation:
    """Higher nominal fixed modes reported for the current presentation resolution."""

    pixel_width: int
    pixel_height: int
    higher_rates_hz: tuple[int, ...]

    @property
    def highest_hz(self) -> int:
        return max(self.higher_rates_hz)


@dataclass(frozen=True)
class WindowsDisplayMode:
    """Exact driver-configured refresh mode for one active Windows display path."""

    display_device_name: str
    numerator: int
    denominator: int
    dynamic_refresh_enabled: bool = False

    def __post_init__(self) -> None:
        if self.numerator <= 0 or self.denominator <= 0:
            raise ValueError("Windows display refresh numerator and denominator must be positive.")

    @property
    def hz(self) -> float:
        return self.numerator / self.denominator

    @property
    def fraction_text(self) -> str:
        return f"{self.numerator}/{self.denominator}"


@dataclass(frozen=True)
class _ActiveDisplayPath:
    source_device_name: str
    numerator: int
    denominator: int
    dynamic_refresh_enabled: bool


def _load_user32() -> Any:
    if sys.platform != "win32":
        raise WindowsDisplayModeError(
            "Exact rational display-mode detection is available only on Windows."
        )
    win_dll = getattr(ctypes, "WinDLL", None)
    if win_dll is None:
        raise WindowsDisplayModeError("Windows User32 APIs are unavailable.")
    user32 = win_dll("user32", use_last_error=True)
    user32.GetDisplayConfigBufferSizes.argtypes = [
        _UINT32,
        ctypes.POINTER(_UINT32),
        ctypes.POINTER(_UINT32),
    ]
    user32.GetDisplayConfigBufferSizes.restype = _LONG
    user32.QueryDisplayConfig.argtypes = [
        _UINT32,
        ctypes.POINTER(_UINT32),
        ctypes.POINTER(_DisplayConfigPathInfo),
        ctypes.POINTER(_UINT32),
        ctypes.POINTER(_DisplayConfigModeInfo),
        ctypes.c_void_p,
    ]
    user32.QueryDisplayConfig.restype = _LONG
    user32.DisplayConfigGetDeviceInfo.argtypes = [ctypes.c_void_p]
    user32.DisplayConfigGetDeviceInfo.restype = _LONG
    user32.EnumDisplayDevicesW.argtypes = [
        ctypes.c_wchar_p,
        _UINT32,
        ctypes.POINTER(_DisplayDeviceW),
        _UINT32,
    ]
    user32.EnumDisplayDevicesW.restype = _BOOL
    return user32


def _windows_error(operation: str, result: int) -> WindowsDisplayModeError:
    return WindowsDisplayModeError(f"{operation} failed with Windows error {result}.")


def _primary_gdi_device_name(user32: Any) -> str:
    index = 0
    while True:
        device = _DisplayDeviceW()
        device.cb = ctypes.sizeof(_DisplayDeviceW)
        if not user32.EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):
            break
        index += 1
        required_flags = _DISPLAY_DEVICE_ATTACHED_TO_DESKTOP | _DISPLAY_DEVICE_PRIMARY_DEVICE
        if int(device.StateFlags) & required_flags == required_flags:
            name = str(device.DeviceName).strip()
            if name:
                return name
    raise WindowsDisplayModeError("Windows did not report an active primary display device.")


def _source_device_name(user32: Any, path: _DisplayConfigPathInfo) -> str:
    request = _DisplayConfigSourceDeviceName()
    request.header.type = _DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME
    request.header.size = ctypes.sizeof(_DisplayConfigSourceDeviceName)
    request.header.adapterId = path.sourceInfo.adapterId
    request.header.id = path.sourceInfo.id
    result = int(user32.DisplayConfigGetDeviceInfo(ctypes.byref(request)))
    if result != _ERROR_SUCCESS:
        raise _windows_error("DisplayConfigGetDeviceInfo", result)
    return str(request.viewGdiDeviceName).strip()


def _query_active_display_paths_with_flags(
    user32: Any,
    query_flags: int,
) -> list[_ActiveDisplayPath]:
    for _attempt in range(3):
        path_count = _UINT32()
        mode_count = _UINT32()
        result = int(
            user32.GetDisplayConfigBufferSizes(
                query_flags,
                ctypes.byref(path_count),
                ctypes.byref(mode_count),
            )
        )
        if (
            result == _ERROR_INVALID_PARAMETER
            and query_flags & _QDC_VIRTUAL_REFRESH_RATE_AWARE
        ):
            raise _VirtualRefreshQueryUnsupported
        if result != _ERROR_SUCCESS:
            raise _windows_error("GetDisplayConfigBufferSizes", result)
        if path_count.value <= 0:
            raise WindowsDisplayModeError("Windows reported no active display paths.")

        paths = (_DisplayConfigPathInfo * path_count.value)()
        modes = (_DisplayConfigModeInfo * max(1, mode_count.value))()
        result = int(
            user32.QueryDisplayConfig(
                query_flags,
                ctypes.byref(path_count),
                paths,
                ctypes.byref(mode_count),
                modes,
                None,
            )
        )
        if (
            result == _ERROR_INVALID_PARAMETER
            and query_flags & _QDC_VIRTUAL_REFRESH_RATE_AWARE
        ):
            raise _VirtualRefreshQueryUnsupported
        if result == _ERROR_INSUFFICIENT_BUFFER:
            continue
        if result != _ERROR_SUCCESS:
            raise _windows_error("QueryDisplayConfig", result)

        active_paths: list[_ActiveDisplayPath] = []
        for index in range(path_count.value):
            path = paths[index]
            if not int(path.flags) & _DISPLAYCONFIG_PATH_ACTIVE:
                continue
            if not bool(path.targetInfo.targetAvailable):
                continue
            refresh_rate = path.targetInfo.refreshRate
            active_paths.append(
                _ActiveDisplayPath(
                    source_device_name=_source_device_name(user32, path),
                    numerator=int(refresh_rate.Numerator),
                    denominator=int(refresh_rate.Denominator),
                    dynamic_refresh_enabled=bool(
                        int(path.flags) & _DISPLAYCONFIG_PATH_BOOST_REFRESH_RATE
                    ),
                )
            )
        return active_paths
    raise WindowsDisplayModeError(
        "Windows display topology changed repeatedly while reading the active mode."
    )


def _query_active_display_paths(user32: Any) -> list[_ActiveDisplayPath]:
    windows_11_flags = (
        _QDC_ONLY_ACTIVE_PATHS
        | _QDC_VIRTUAL_MODE_AWARE
        | _QDC_VIRTUAL_REFRESH_RATE_AWARE
    )
    try:
        return _query_active_display_paths_with_flags(user32, windows_11_flags)
    except _VirtualRefreshQueryUnsupported:
        return _query_active_display_paths_with_flags(
            user32,
            _QDC_ONLY_ACTIVE_PATHS | _QDC_VIRTUAL_MODE_AWARE,
        )


def _select_primary_display_mode(
    primary_device_name: str,
    active_paths: list[_ActiveDisplayPath],
    *,
    selected: bool = False,
) -> WindowsDisplayMode:
    display_role = "selected" if selected else "primary"
    matching = [
        path
        for path in active_paths
        if path.source_device_name.casefold() == primary_device_name.casefold()
    ]
    if not matching:
        raise WindowsDisplayModeError(
            f"Windows could not match {display_role} display {primary_device_name!r} "
            "to an active path. Reconnect the monitor or choose another display."
        )
    if len(matching) > 1:
        raise WindowsDisplayModeError(
            f"The {display_role} Windows desktop source maps to multiple active display paths. "
            "Use an extended single-primary display configuration for exact verification."
        )
    selected_path = matching[0]
    if selected_path.numerator <= 0 or selected_path.denominator <= 0:
        raise WindowsDisplayModeError(
            f"Windows reported an invalid rational refresh rate for the {display_role} display."
        )
    return WindowsDisplayMode(
        display_device_name=selected_path.source_device_name,
        numerator=selected_path.numerator,
        denominator=selected_path.denominator,
        dynamic_refresh_enabled=selected_path.dynamic_refresh_enabled,
    )


def query_primary_windows_display_mode() -> WindowsDisplayMode:
    """Return the exact rational refresh mode for the active primary Windows display."""

    user32 = _load_user32()
    return _select_primary_display_mode(
        _primary_gdi_device_name(user32),
        _query_active_display_paths(user32),
    )


def query_windows_display_mode(display_device_name: str | None = None) -> WindowsDisplayMode:
    """Read the chosen Windows desktop source, defaulting to the current primary."""
    if display_device_name is None:
        return query_primary_windows_display_mode()
    if not isinstance(display_device_name, str) or not display_device_name.strip():
        raise WindowsDisplayModeError("The selected Windows display name must not be blank.")
    return _select_primary_display_mode(
        display_device_name, _query_active_display_paths(_load_user32()), selected=True,
    )


def query_windows_refresh_recommendation(
    display_device_name: str | None = None,
) -> WindowsRefreshRecommendation | None:
    """Find higher progressive modes at the selected display's active resolution."""
    mode = query_windows_display_mode(display_device_name)
    if mode.dynamic_refresh_enabled or mode.numerator != 60 * mode.denominator:
        return None

    user32 = _load_user32()
    enumerate_mode = user32.EnumDisplaySettingsW
    enumerate_mode.argtypes = [ctypes.c_wchar_p, _UINT32, ctypes.POINTER(_DevModeW)]
    enumerate_mode.restype = _BOOL

    def read_mode(index: int) -> _DevModeW | None:
        settings = _DevModeW()
        settings.dmSize = ctypes.sizeof(_DevModeW)
        if not enumerate_mode(mode.display_device_name, index, ctypes.byref(settings)):
            return None
        return settings

    current = read_mode(_ENUM_CURRENT_SETTINGS)
    if current is None or not current.dmPelsWidth or not current.dmPelsHeight:
        raise WindowsDisplayModeError("Windows could not read the current display resolution.")
    if current.dmDisplayFrequency != 60:
        return None  # The mode changed between the native reads.

    resolution = (current.dmPelsWidth, current.dmPelsHeight)
    rates: set[int] = set()
    for index in range(4096):
        candidate = read_mode(index)
        if candidate is None:
            break
        if (
            (candidate.dmPelsWidth, candidate.dmPelsHeight) == resolution
            and candidate.dmBitsPerPel == current.dmBitsPerPel
            and not candidate.dmDisplayFlags & _DM_INTERLACED
            and candidate.dmDisplayFrequency > 60
        ):
            rates.add(candidate.dmDisplayFrequency)
    else:
        raise WindowsDisplayModeError("Windows returned too many display modes to compare.")

    # A resolution or mode change during enumeration invalidates the comparison.
    final = read_mode(_ENUM_CURRENT_SETTINGS)
    if final is None or (
        final.dmPelsWidth, final.dmPelsHeight, final.dmBitsPerPel, final.dmDisplayFrequency,
    ) != (*resolution, current.dmBitsPerPel, 60):
        return None
    if rates:
        return WindowsRefreshRecommendation(*resolution, tuple(sorted(rates)))
    return None
