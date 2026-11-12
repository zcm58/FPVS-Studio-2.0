"""Native display-mode and PsychoPy stability verification tests."""

from __future__ import annotations

import ctypes
import json
import subprocess
from types import SimpleNamespace
from typing import cast

import pytest
from tests.platform_adapters import set_module_platform

from fpvs_studio.engines.base import PresentationEngine
from fpvs_studio.runtime import display_mode as display_mode_module
from fpvs_studio.runtime import windows_display as windows_display_module
from fpvs_studio.runtime.display_mode import (
    DisplayModeError,
    NativeDisplayMode,
    query_primary_native_display_mode,
)
from fpvs_studio.runtime.display_refresh import (
    DisplayRefreshVerificationError,
    verify_primary_display_refresh,
)
from fpvs_studio.runtime.linux_display import (
    _run_display_query,
    parse_kscreen_display_mode,
    parse_xrandr_display_mode,
    query_primary_linux_display_mode,
)
from fpvs_studio.runtime.windows_display import (
    WindowsDisplayMode,
    WindowsDisplayModeError,
    _ActiveDisplayPath,
    _select_primary_display_mode,
)


class _MeasuredEngine:
    def __init__(self, measured_hz: float | Exception) -> None:
        self.measured_hz = measured_hz
        self.measurement_count = 0

    def measure_refresh_hz(self, *, runtime_options=None) -> float:
        self.measurement_count += 1
        if isinstance(self.measured_hz, Exception):
            raise self.measured_hz
        return self.measured_hz


def _engine(measured_hz: float | Exception) -> tuple[PresentationEngine, _MeasuredEngine]:
    measured_engine = _MeasuredEngine(measured_hz)
    return cast(PresentationEngine, measured_engine), measured_engine


def _native_windows_mode(
    numerator: int,
    denominator: int = 1,
    *,
    dynamic_refresh_enabled: bool = False,
) -> NativeDisplayMode:
    return NativeDisplayMode(
        platform_name="Windows",
        display_name=r"\\.\DISPLAY1",
        refresh_hz=numerator / denominator,
        source_name="QueryDisplayConfig",
        exact_refresh=True,
        mode_reference=f"{numerator}/{denominator}",
        variable_refresh_enabled=dynamic_refresh_enabled,
        variable_refresh_label=(
            "Dynamic Refresh Rate" if dynamic_refresh_enabled else None
        ),
    )


def test_windows_mode_preserves_exact_fraction() -> None:
    mode = WindowsDisplayMode(
        display_device_name=r"\\.\DISPLAY1",
        numerator=60_000,
        denominator=1_001,
    )

    assert mode.hz == pytest.approx(59.94005994005994)
    assert mode.fraction_text == "60000/1001"


def _windows_signal_records(virtual: bool):
    windows = windows_display_module
    path = windows._DisplayConfigPathInfo()
    path.flags = windows._DISPLAYCONFIG_PATH_ACTIVE
    path.targetInfo.targetAvailable = True
    path.targetInfo.refreshRate = windows._DisplayConfigRational(60, 1)
    path.targetInfo.scanLineOrdering = 1
    path.targetInfo.scaling = 1
    path.targetInfo.id = 256
    path.targetInfo.adapterId = path.sourceInfo.adapterId = windows._Luid(73, 9)
    target, source, desktop = (windows._DisplayConfigModeInfo() for _ in range(3))
    for mode, kind, identifier in ((target, 2, 256), (source, 1, 0), (desktop, 3, 256)):
        mode.infoType, mode.id, mode.adapterId = kind, identifier, path.targetInfo.adapterId
    source.data.sourceMode.width, source.data.sourceMode.height = (1920, 1080)
    signal = target.data.targetMode.targetVideoSignalInfo
    signal.pixelRate = 138_700_000
    signal.hSyncFreq = windows._DisplayConfigRational(138_700_000, 2080)
    signal.vSyncFreq = windows._DisplayConfigRational(60, 1)
    signal.activeSize = windows._DisplayConfig2DRegion(1920, 1080)
    signal.totalSize = windows._DisplayConfig2DRegion(2080, 1111)
    signal.scanLineOrdering = 1
    desktop.data.desktopImageInfo.pathSourceSize = windows._PointL(1920, 1080)
    desktop.data.desktopImageInfo.desktopImageRegion = windows._RectL(0, 0, 1920, 1080)
    flags = windows._QDC_ONLY_ACTIVE_PATHS
    if virtual:
        flags |= windows._QDC_VIRTUAL_MODE_AWARE
        path.flags |= windows._DISPLAYCONFIG_PATH_SUPPORT_VIRTUAL_MODE
        path.targetInfo.modeInfoIdx.parts.targetModeInfoIdx = 0
        path.targetInfo.modeInfoIdx.parts.desktopModeInfoIdx = 2
        path.sourceInfo.modeInfoIdx.parts.sourceModeInfoIdx = 1
    else:
        path.targetInfo.modeInfoIdx.modeInfoIdx = 0
        path.sourceInfo.modeInfoIdx.modeInfoIdx = 1
    return path, (target, source, desktop), flags


@pytest.mark.parametrize("virtual", [True, False])
def test_windows_query_preserves_nominal_and_distinct_signal_rate(monkeypatch, virtual):
    windows = windows_display_module
    path, modes, flags = _windows_signal_records(virtual)

    def buffer_sizes(query_flags, path_count, mode_count):
        assert query_flags == flags
        path_count._obj.value = 1
        mode_count._obj.value = len(modes) + 1
        return 0

    def query_config(query_flags, path_count, paths, mode_count, returned_modes, _topology):
        assert query_flags == flags
        paths[0] = path
        for index, mode in enumerate(modes):
            returned_modes[index] = mode
        mode_count._obj.value = len(modes)
        return 0

    user32 = SimpleNamespace(
        GetDisplayConfigBufferSizes=buffer_sizes, QueryDisplayConfig=query_config,
    )
    monkeypatch.setattr(windows, "_source_device_name", lambda *_: r"\\.\DISPLAY1")
    active = windows._query_active_display_paths_with_flags(user32, flags)
    mode = _select_primary_display_mode(r"\\.\DISPLAY1", active)

    assert mode.fraction_text == "60/1"
    assert mode.hz == 60.0
    assert mode.signal_refresh_hz == pytest.approx(60.020425119435)


@pytest.mark.parametrize("case", [
    "no_target", "wrong_target_type", "wrong_target_id", "wrong_adapter", "no_pixel_rate",
    "no_active_size", "no_total_size", "interlaced", "unknown_scanline", "missing_sync",
    "scaled", "desktop_size", "no_desktop", "virtual_refresh", "vsync_divided",
])
def test_windows_signal_metadata_omits_unusable_modes(case):
    windows = windows_display_module
    path, modes, flags = _windows_signal_records(virtual=True)
    target, source, desktop = modes
    signal = target.data.targetMode.targetVideoSignalInfo
    if case == "no_target":
        path.targetInfo.modeInfoIdx.parts.targetModeInfoIdx = 0xFFFF
    elif case == "wrong_target_type":
        target.infoType = 1
    elif case == "wrong_target_id":
        target.id += 1
    elif case == "wrong_adapter":
        target.adapterId.HighPart += 1
    elif case == "no_pixel_rate":
        signal.pixelRate = 0
    elif case == "no_active_size":
        signal.activeSize.cx = 0
    elif case == "no_total_size":
        signal.totalSize.cy = 0
    elif case == "interlaced":
        signal.scanLineOrdering = 2
    elif case == "unknown_scanline":
        path.targetInfo.scanLineOrdering = 0
    elif case == "missing_sync":
        signal.hSyncFreq.Denominator = 0
    elif case == "scaled":
        source.data.sourceMode.width = 1600
    elif case == "desktop_size":
        desktop.data.desktopImageInfo.desktopImageRegion.right = 1600
    elif case == "no_desktop":
        path.targetInfo.modeInfoIdx.parts.desktopModeInfoIdx = 0xFFFF
    elif case == "virtual_refresh":
        path.flags |= windows._DISPLAYCONFIG_PATH_BOOST_REFRESH_RATE
    else:
        signal.videoStandard.additionalSignalInfo.vSyncFreqDivider = 2

    assert windows._signal_refresh_hz(path, modes, flags) is None


@pytest.mark.parametrize(("numerator", "denominator", "dynamic"), [
    (120, 1, False), (60_000, 1_001, False), (60, 1, True),
])
def test_windows_refresh_recommendation_only_compares_fixed_60(
    monkeypatch, numerator, denominator, dynamic,
):
    monkeypatch.setattr(
        windows_display_module, "query_primary_windows_display_mode",
        lambda: WindowsDisplayMode("display", numerator, denominator, dynamic),
    )
    monkeypatch.setattr(
        windows_display_module, "_load_user32", lambda: pytest.fail("unexpected enumeration"),
    )
    assert windows_display_module.query_windows_refresh_recommendation() is None


@pytest.mark.parametrize("case", ["higher", "none", "changed", "unavailable"])
def test_windows_refresh_recommendation_enumerates_same_resolution(monkeypatch, case):
    current = (1920, 1080, 32, 0, 60)
    candidates = [
        current,
        (1920, 1080, 32, 0, 120),
        (1920, 1080, 32, 0, 165),
        (1280, 720, 32, 0, 360),
        (1920, 1080, 16, 0, 300),
        (1920, 1080, 32, 2, 240),
    ]
    if case == "none":
        candidates = [current, *candidates[3:]]
    reads = []

    def enumerate_mode(name, index, pointer):
        assert name == "presentation display"
        reads.append(index)
        settings = pointer._obj
        assert settings.dmSize == 220
        if index == 0xFFFFFFFF:
            if case == "unavailable":
                return 0
            values = (2560, 1440, 32, 0, 60) if case == "changed" and len(reads) > 1 else current
        elif index < len(candidates):
            values = candidates[index]
        else:
            return 0
        (
            settings.dmPelsWidth, settings.dmPelsHeight, settings.dmBitsPerPel,
            settings.dmDisplayFlags, settings.dmDisplayFrequency,
        ) = values
        return 1

    assert ctypes.sizeof(windows_display_module._DevModeW) == 220
    monkeypatch.setattr(
        windows_display_module, "query_primary_windows_display_mode",
        lambda: WindowsDisplayMode("presentation display", 60, 1),
    )
    monkeypatch.setattr(
        windows_display_module, "_load_user32",
        lambda: SimpleNamespace(EnumDisplaySettingsW=enumerate_mode),
    )
    if case == "unavailable":
        with pytest.raises(WindowsDisplayModeError, match="current display resolution"):
            windows_display_module.query_windows_refresh_recommendation()
        return
    result = windows_display_module.query_windows_refresh_recommendation()
    assert reads == [0xFFFFFFFF, *range(len(candidates) + 1), 0xFFFFFFFF]
    if case == "higher":
        assert result is not None
        assert (result.pixel_width, result.pixel_height) == (1920, 1080)
        assert result.higher_rates_hz == (120, 165)
        assert result.highest_hz == 165
    else:
        assert result is None


def test_primary_mode_selection_matches_device_name_case_insensitively() -> None:
    mode = _select_primary_display_mode(
        r"\\.\DISPLAY1",
        [
            _ActiveDisplayPath(r"\\.\display2", 144, 1, False),
            _ActiveDisplayPath(r"\\.\display1", 60_000, 1_001, False),
        ],
    )

    assert mode.display_device_name == r"\\.\display1"
    assert (mode.numerator, mode.denominator) == (60_000, 1_001)


@pytest.mark.parametrize(
    ("paths", "message"),
    [
        ([], "could not match primary display"),
        (
            [
                _ActiveDisplayPath(r"\\.\DISPLAY1", 60, 1, False),
                _ActiveDisplayPath(r"\\.\DISPLAY1", 60, 1, False),
            ],
            "multiple active display paths",
        ),
        ([_ActiveDisplayPath(r"\\.\DISPLAY1", 60, 0, False)], "invalid rational"),
    ],
)
def test_primary_mode_selection_rejects_ambiguous_or_invalid_paths(
    paths: list[_ActiveDisplayPath],
    message: str,
) -> None:
    with pytest.raises(WindowsDisplayModeError, match=message):
        _select_primary_display_mode(r"\\.\DISPLAY1", paths)


def test_windows_query_falls_back_when_virtual_refresh_flag_is_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queried_flags: list[int] = []

    def _query_with_flags(_user32: object, query_flags: int) -> list[_ActiveDisplayPath]:
        queried_flags.append(query_flags)
        if query_flags & windows_display_module._QDC_VIRTUAL_REFRESH_RATE_AWARE:
            raise windows_display_module._VirtualRefreshQueryUnsupported
        return []

    monkeypatch.setattr(
        windows_display_module,
        "_query_active_display_paths_with_flags",
        _query_with_flags,
    )

    assert windows_display_module._query_active_display_paths(object()) == []
    assert len(queried_flags) == 2
    assert queried_flags[0] & windows_display_module._QDC_VIRTUAL_REFRESH_RATE_AWARE
    assert not queried_flags[1] & windows_display_module._QDC_VIRTUAL_REFRESH_RATE_AWARE


def test_native_selector_preserves_windows_exact_rational_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_module_platform(monkeypatch, display_mode_module, "win32")
    monkeypatch.setattr(
        windows_display_module,
        "query_primary_windows_display_mode",
        lambda: WindowsDisplayMode(r"\\.\DISPLAY1", 60_000, 1_001),
    )

    mode = query_primary_native_display_mode()

    assert mode.platform_name == "Windows"
    assert mode.exact_refresh is True
    assert mode.mode_reference == "60000/1001"
    assert mode.refresh_hz == pytest.approx(59.94005994005994)


def test_verifier_uses_windows_fraction_to_distinguish_5994_from_60(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_native_display_mode",
        lambda: _native_windows_mode(60_000, 1_001),
    )
    presentation_engine, measured_engine = _engine(59.998)

    result = verify_primary_display_refresh(presentation_engine)

    assert result.approved_hz == 59.94
    assert result.display_mode.mode_reference == "60000/1001"
    assert result.psychopy_measured_hz == 59.998
    assert measured_engine.measurement_count == 1


def test_verifier_keeps_exact_60_mode_when_psychopy_estimate_is_5994(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_native_display_mode",
        lambda: _native_windows_mode(60),
    )
    presentation_engine, _ = _engine(59.94)

    result = verify_primary_display_refresh(presentation_engine)

    assert result.approved_hz == 60.0
    assert result.display_mode.mode_reference == "60/1"


def test_windows_verifier_logs_nominal_signal_and_probe_rates(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        windows_display_module,
        "query_windows_display_mode",
        lambda name: WindowsDisplayMode(
            r"\\.\DISPLAY1", 60, 1, signal_refresh_hz=60.020425119,
        ),
    )
    monkeypatch.setattr("fpvs_studio.runtime.display_mode.sys.platform", "win32")
    presentation_engine, _ = _engine(60.0185)

    with caplog.at_level("INFO", logger="fpvs_studio.runtime.display_refresh"):
        result = verify_primary_display_refresh(presentation_engine)

    assert result.approved_hz == 60.0
    assert result.display_mode.signal_refresh_hz == pytest.approx(60.020425119)
    assert "nominal=60.000000 Hz, scan timing=60.020425 Hz, PsychoPy probe=60.018500 Hz" in (
        caplog.text
    )


def test_verifier_maps_linux_native_mode_to_nearest_approved_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_native_display_mode",
        lambda: NativeDisplayMode(
            platform_name="Linux",
            display_name="DP-2",
            refresh_hz=239.914,
            source_name="KScreen",
            exact_refresh=False,
        ),
    )
    presentation_engine, _ = _engine(239.91)

    result = verify_primary_display_refresh(presentation_engine)

    assert result.approved_hz == 240.0
    assert result.display_mode.mode_text == "239.914 Hz (KScreen, DP-2)"


def test_verifier_rejects_nonapproved_exact_windows_fraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_native_display_mode",
        lambda: _native_windows_mode(599, 10),
    )
    presentation_engine, measured_engine = _engine(59.9)

    with pytest.raises(DisplayRefreshVerificationError, match="59.900000 Hz.*does not match"):
        verify_primary_display_refresh(presentation_engine)

    assert measured_engine.measurement_count == 0


def test_verifier_rejects_dynamic_refresh_before_psychopy_measurement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_native_display_mode",
        lambda: _native_windows_mode(120, dynamic_refresh_enabled=True),
    )
    presentation_engine, measured_engine = _engine(120.0)

    with pytest.raises(DisplayRefreshVerificationError, match="variable refresh.*Dynamic"):
        verify_primary_display_refresh(presentation_engine)

    assert measured_engine.measurement_count == 0


def test_verifier_rejects_linux_automatic_vrr_before_psychopy_measurement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_native_display_mode",
        lambda: NativeDisplayMode(
            platform_name="Linux",
            display_name="DP-2",
            refresh_hz=239.914,
            source_name="KScreen",
            exact_refresh=False,
            variable_refresh_enabled=True,
            variable_refresh_label="Automatic",
        ),
    )
    presentation_engine, measured_engine = _engine(239.91)

    with pytest.raises(
        DisplayRefreshVerificationError,
        match="Linux variable refresh.*Automatic.*Adaptive Sync to Never",
    ):
        verify_primary_display_refresh(presentation_engine)

    assert measured_engine.measurement_count == 0


def test_verifier_reports_native_query_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail_query() -> NativeDisplayMode:
        raise DisplayModeError("query failed")

    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_native_display_mode",
        _fail_query,
    )
    presentation_engine, measured_engine = _engine(60.0)

    with pytest.raises(DisplayRefreshVerificationError, match="query failed"):
        verify_primary_display_refresh(presentation_engine)

    assert measured_engine.measurement_count == 0


@pytest.mark.parametrize(
    ("measured_hz", "message"),
    [
        (RuntimeError("unstable measurement"), "unstable measurement"),
        (float("nan"), "invalid display refresh"),
        (60.0, "Windows reports display mode 144.000000 Hz.*PsychoPy observed 60.000 Hz"),
    ],
)
def test_verifier_rejects_unstable_invalid_or_disagreeing_psychopy_result(
    monkeypatch: pytest.MonkeyPatch,
    measured_hz: float | Exception,
    message: str,
) -> None:
    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_native_display_mode",
        lambda: _native_windows_mode(144),
    )
    presentation_engine, _ = _engine(measured_hz)

    with pytest.raises(DisplayRefreshVerificationError, match=message):
        verify_primary_display_refresh(presentation_engine)


def _kscreen_payload(*outputs: dict[str, object]) -> str:
    return json.dumps({"outputs": list(outputs)})


def _kscreen_output(
    *,
    name: str = "DP-2",
    priority: int = 1,
    current_mode_id: str = "2",
    refresh_hz: float = 239.914,
    vrr_policy: int = 0,
) -> dict[str, object]:
    return {
        "connected": True,
        "enabled": True,
        "name": name,
        "priority": priority,
        "currentModeId": current_mode_id,
        "vrrPolicy": vrr_policy,
        "modes": [
            {"id": "1", "refreshRate": 60.0},
            {"id": "2", "refreshRate": refresh_hz},
        ],
    }


def test_kscreen_parser_selects_primary_current_mode() -> None:
    secondary = _kscreen_output(name="HDMI-A-1", priority=2, refresh_hz=60.0)
    primary = _kscreen_output()

    mode = parse_kscreen_display_mode(_kscreen_payload(secondary, primary))

    assert mode.platform_name == "Linux"
    assert mode.display_name == "DP-2"
    assert mode.refresh_hz == pytest.approx(239.914)
    assert mode.source_name == "KScreen"
    assert mode.exact_refresh is False
    assert mode.variable_refresh_enabled is False


@pytest.mark.parametrize("vrr_policy", [1, 2])
def test_kscreen_parser_exposes_enabled_variable_refresh(vrr_policy: int) -> None:
    mode = parse_kscreen_display_mode(
        _kscreen_payload(_kscreen_output(vrr_policy=vrr_policy))
    )

    assert mode.variable_refresh_enabled is True
    assert mode.variable_refresh_label in {"Always", "Automatic"}


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not-json", "invalid JSON"),
        (_kscreen_payload(), "no enabled connected"),
        (
            _kscreen_payload(
                _kscreen_output(name="DP-1", priority=1),
                _kscreen_output(name="DP-2", priority=1),
            ),
            "multiple enabled displays at the primary priority",
        ),
        (
            _kscreen_payload(_kscreen_output(current_mode_id="missing")),
            "could not resolve one current mode",
        ),
    ],
)
def test_kscreen_parser_rejects_invalid_or_ambiguous_configuration(
    payload: str,
    message: str,
) -> None:
    with pytest.raises(DisplayModeError, match=message):
        parse_kscreen_display_mode(payload)


def test_xrandr_parser_selects_primary_current_mode() -> None:
    mode = parse_xrandr_display_mode(
        """Screen 0: current 5760 x 2160
DP-1 connected 1920x1080+3840+0
   1920x1080     60.00*+
DP-2 connected primary 3840x2160+0+0
   3840x2160    239.89*+
"""
    )

    assert mode.display_name == "DP-2"
    assert mode.refresh_hz == pytest.approx(239.89)
    assert mode.source_name == "XRandR"


def test_linux_wayland_without_kscreen_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    monkeypatch.setattr("fpvs_studio.runtime.linux_display.shutil.which", lambda _name: None)

    with pytest.raises(DisplayModeError, match="Wayland compositor"):
        query_primary_linux_display_mode()


def test_display_query_surfaces_command_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "fpvs_studio.runtime.linux_display.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["kscreen-doctor", "--json"],
            returncode=1,
            stdout="",
            stderr="could not connect to compositor",
        ),
    )

    with pytest.raises(DisplayModeError, match="could not connect to compositor"):
        _run_display_query(("kscreen-doctor", "--json"))
