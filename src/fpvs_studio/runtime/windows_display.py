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
) -> WindowsDisplayMode:
    matching = [
        path
        for path in active_paths
        if path.source_device_name.casefold() == primary_device_name.casefold()
    ]
    if not matching:
        raise WindowsDisplayModeError(
            f"Windows could not match primary display {primary_device_name!r} to an active path."
        )
    if len(matching) > 1:
        raise WindowsDisplayModeError(
            "The primary Windows desktop source maps to multiple active display paths. "
            "Use an extended single-primary display configuration for exact verification."
        )
    selected = matching[0]
    if selected.numerator <= 0 or selected.denominator <= 0:
        raise WindowsDisplayModeError(
            "Windows reported an invalid rational refresh rate for the primary display."
        )
    return WindowsDisplayMode(
        display_device_name=selected.source_device_name,
        numerator=selected.numerator,
        denominator=selected.denominator,
        dynamic_refresh_enabled=selected.dynamic_refresh_enabled,
    )


def query_primary_windows_display_mode() -> WindowsDisplayMode:
    """Return the exact rational refresh mode for the active primary Windows display."""

    user32 = _load_user32()
    return _select_primary_display_mode(
        _primary_gdi_device_name(user32),
        _query_active_display_paths(user32),
    )
