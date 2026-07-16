"""Combined Windows display-mode and presentation-engine refresh verification."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isclose, isfinite

from fpvs_studio.core.validation import APPROVED_MONITOR_REFRESH_RATES_HZ
from fpvs_studio.engines.base import PresentationEngine
from fpvs_studio.runtime.windows_display import (
    WindowsDisplayMode,
    WindowsDisplayModeError,
    query_primary_windows_display_mode,
)

PSYCHOPY_STABILITY_RELATIVE_TOLERANCE = 0.005
# The authored 59.94 label represents 60000/1001 (59.9400599...). This narrow
# tolerance admits that display fraction without conflating it with integer 60/1.
WINDOWS_MODE_APPROVED_ABSOLUTE_TOLERANCE_HZ = 0.001


class DisplayRefreshVerificationError(RuntimeError):
    """Raised when exact mode detection or PsychoPy stability validation fails."""


@dataclass(frozen=True)
class DisplayRefreshVerification:
    """Neutral result of exact Windows mode detection plus observed frame delivery."""

    windows_mode: WindowsDisplayMode
    psychopy_measured_hz: float
    approved_hz: float


def _approved_refresh_for_windows_mode(windows_mode: WindowsDisplayMode) -> float | None:
    matching_rates = [
        approved_hz
        for approved_hz in APPROVED_MONITOR_REFRESH_RATES_HZ
        if isclose(
            windows_mode.hz,
            approved_hz,
            rel_tol=0.0,
            abs_tol=WINDOWS_MODE_APPROVED_ABSOLUTE_TOLERANCE_HZ,
        )
    ]
    if len(matching_rates) != 1:
        return None
    return matching_rates[0]


def verify_primary_display_refresh(
    engine: PresentationEngine,
    *,
    runtime_options: Mapping[str, object] | None = None,
) -> DisplayRefreshVerification:
    """Verify the primary display's exact mode and stable fullscreen frame delivery."""

    try:
        windows_mode = query_primary_windows_display_mode()
    except WindowsDisplayModeError as exc:
        raise DisplayRefreshVerificationError(
            f"Exact Windows display mode could not be read: {exc}"
        ) from exc
    if windows_mode.dynamic_refresh_enabled:
        raise DisplayRefreshVerificationError(
            "Windows Dynamic Refresh Rate is enabled on the presentation display. "
            "Disable dynamic or variable refresh before running FPVS timing."
        )

    approved_hz = _approved_refresh_for_windows_mode(windows_mode)
    if approved_hz is None:
        raise DisplayRefreshVerificationError(
            f"Windows reports {windows_mode.hz:.6f} Hz "
            f"({windows_mode.fraction_text}), which does not match an approved FPVS "
            "refresh rate (59.94, 60, 120, 144, or 240 Hz)."
        )

    try:
        psychopy_measured_hz = float(
            engine.measure_refresh_hz(runtime_options=runtime_options)
        )
    except Exception as exc:
        raise DisplayRefreshVerificationError(
            f"PsychoPy could not confirm stable frame delivery: {exc}"
        ) from exc
    if not isfinite(psychopy_measured_hz) or psychopy_measured_hz <= 0:
        raise DisplayRefreshVerificationError(
            "PsychoPy returned an invalid display refresh measurement."
        )
    if not isclose(
        windows_mode.hz,
        psychopy_measured_hz,
        rel_tol=PSYCHOPY_STABILITY_RELATIVE_TOLERANCE,
        abs_tol=0.0,
    ):
        raise DisplayRefreshVerificationError(
            f"Windows reports {windows_mode.hz:.6f} Hz "
            f"({windows_mode.fraction_text}), but PsychoPy observed "
            f"{psychopy_measured_hz:.3f} Hz. Confirm the presentation display, disable "
            "variable refresh, and close graphics-intensive applications before retrying."
        )

    return DisplayRefreshVerification(
        windows_mode=windows_mode,
        psychopy_measured_hz=psychopy_measured_hz,
        approved_hz=approved_hz,
    )
