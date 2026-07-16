"""Exact Windows display-mode and PsychoPy stability verification tests."""

from __future__ import annotations

from typing import cast

import pytest

from fpvs_studio.engines.base import PresentationEngine
from fpvs_studio.runtime import windows_display as windows_display_module
from fpvs_studio.runtime.display_refresh import (
    DisplayRefreshVerificationError,
    verify_primary_display_refresh,
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


def test_windows_mode_preserves_exact_fraction() -> None:
    mode = WindowsDisplayMode(
        display_device_name=r"\\.\DISPLAY1",
        numerator=60_000,
        denominator=1_001,
    )

    assert mode.hz == pytest.approx(59.94005994005994)
    assert mode.fraction_text == "60000/1001"


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


def test_verifier_uses_windows_fraction_to_distinguish_5994_from_60(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_windows_display_mode",
        lambda: WindowsDisplayMode(r"\\.\DISPLAY1", 60_000, 1_001),
    )
    presentation_engine, measured_engine = _engine(59.998)

    result = verify_primary_display_refresh(presentation_engine)

    assert result.approved_hz == 59.94
    assert result.windows_mode.fraction_text == "60000/1001"
    assert result.psychopy_measured_hz == 59.998
    assert measured_engine.measurement_count == 1


def test_verifier_keeps_exact_60_mode_when_psychopy_estimate_is_5994(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_windows_display_mode",
        lambda: WindowsDisplayMode(r"\\.\DISPLAY1", 60, 1),
    )
    presentation_engine, _ = _engine(59.94)

    result = verify_primary_display_refresh(presentation_engine)

    assert result.approved_hz == 60.0
    assert result.windows_mode.fraction_text == "60/1"


def test_verifier_rejects_nonapproved_exact_windows_fraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_windows_display_mode",
        lambda: WindowsDisplayMode(r"\\.\DISPLAY1", 599, 10),
    )
    presentation_engine, measured_engine = _engine(59.9)

    with pytest.raises(DisplayRefreshVerificationError, match="59.900000 Hz.*does not match"):
        verify_primary_display_refresh(presentation_engine)

    assert measured_engine.measurement_count == 0


def test_verifier_rejects_dynamic_refresh_before_psychopy_measurement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_windows_display_mode",
        lambda: WindowsDisplayMode(r"\\.\DISPLAY1", 120, 1, True),
    )
    presentation_engine, measured_engine = _engine(120.0)

    with pytest.raises(DisplayRefreshVerificationError, match="Dynamic Refresh Rate"):
        verify_primary_display_refresh(presentation_engine)

    assert measured_engine.measurement_count == 0


def test_verifier_reports_windows_query_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail_query() -> WindowsDisplayMode:
        raise WindowsDisplayModeError("query failed")

    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_windows_display_mode",
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
        (60.0, "Windows reports 144.000000 Hz.*PsychoPy observed 60.000 Hz"),
    ],
)
def test_verifier_rejects_unstable_invalid_or_disagreeing_psychopy_result(
    monkeypatch: pytest.MonkeyPatch,
    measured_hz: float | Exception,
    message: str,
) -> None:
    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_windows_display_mode",
        lambda: WindowsDisplayMode(r"\\.\DISPLAY1", 144, 1),
    )
    presentation_engine, _ = _engine(measured_hz)

    with pytest.raises(DisplayRefreshVerificationError, match=message):
        verify_primary_display_refresh(presentation_engine)
