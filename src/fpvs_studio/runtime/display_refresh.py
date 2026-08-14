"""Combined native display-mode and presentation-engine refresh verification."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isclose, isfinite

from fpvs_studio.core.validation import (
    APPROVED_MONITOR_REFRESH_RATES_HZ,
    nearest_approved_monitor_refresh_rate,
)
from fpvs_studio.engines.base import PresentationEngine
from fpvs_studio.runtime.display_mode import (
    DisplayModeError,
    NativeDisplayMode,
    query_primary_native_display_mode,
)

PSYCHOPY_STABILITY_RELATIVE_TOLERANCE = 0.005
# The authored 59.94 label represents 60000/1001 (59.9400599...). This narrow
# tolerance admits that display fraction without conflating it with integer 60/1.
EXACT_MODE_APPROVED_ABSOLUTE_TOLERANCE_HZ = 0.001


class DisplayRefreshVerificationError(RuntimeError):
    """Raised when native mode detection or PsychoPy stability validation fails."""


@dataclass(frozen=True)
class DisplayRefreshVerification:
    """Neutral result of native mode detection plus observed frame delivery."""

    display_mode: NativeDisplayMode
    psychopy_measured_hz: float
    approved_hz: float


def _approved_refresh_for_native_mode(display_mode: NativeDisplayMode) -> float | None:
    if not display_mode.exact_refresh:
        return nearest_approved_monitor_refresh_rate(display_mode.hz)
    matching_rates = [
        approved_hz
        for approved_hz in APPROVED_MONITOR_REFRESH_RATES_HZ
        if isclose(
            display_mode.hz,
            approved_hz,
            rel_tol=0.0,
            abs_tol=EXACT_MODE_APPROVED_ABSOLUTE_TOLERANCE_HZ,
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
    """Verify the primary display's native mode and stable fullscreen frame delivery."""

    try:
        display_mode = query_primary_native_display_mode()
    except DisplayModeError as exc:
        raise DisplayRefreshVerificationError(str(exc)) from exc
    if display_mode.variable_refresh_enabled:
        variable_refresh_name = display_mode.variable_refresh_label or "enabled"
        platform_guidance = (
            " In KDE System Settings > Display & Monitor, set Adaptive Sync to Never, "
            "then retry."
            if display_mode.platform_name == "Linux" and display_mode.source_name == "KScreen"
            else " Disable Adaptive Sync, VRR, or Dynamic Refresh Rate, then retry."
        )
        raise DisplayRefreshVerificationError(
            f"{display_mode.platform_name} variable refresh is {variable_refresh_name} "
            f"on presentation display {display_mode.display_name!r}. Variable refresh "
            f"must be disabled for FPVS timing.{platform_guidance}"
        )

    approved_hz = _approved_refresh_for_native_mode(display_mode)
    if approved_hz is None:
        raise DisplayRefreshVerificationError(
            f"{display_mode.platform_name} reports display mode {display_mode.mode_text}, "
            "which does not match an approved FPVS "
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
        display_mode.hz,
        psychopy_measured_hz,
        rel_tol=PSYCHOPY_STABILITY_RELATIVE_TOLERANCE,
        abs_tol=0.0,
    ):
        raise DisplayRefreshVerificationError(
            f"{display_mode.platform_name} reports display mode {display_mode.mode_text}, "
            "but PsychoPy observed "
            f"{psychopy_measured_hz:.3f} Hz. Confirm the presentation display, disable "
            "variable refresh, and close graphics-intensive applications before retrying."
        )

    return DisplayRefreshVerification(
        display_mode=display_mode,
        psychopy_measured_hz=psychopy_measured_hz,
        approved_hz=approved_hz,
    )
