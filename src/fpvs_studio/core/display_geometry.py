"""Display geometry helpers for visual-angle stimulus sizing."""

from __future__ import annotations

from math import radians, tan


def visual_angle_width_cm(*, degrees: float, viewing_distance_cm: float) -> float:
    """Return the physical width subtended by a visual angle."""

    return 2.0 * viewing_distance_cm * tan(radians(degrees) / 2.0)


def visual_angle_width_px(
    *,
    degrees: float,
    viewing_distance_cm: float,
    screen_width_cm: float,
    screen_width_px: int | float,
) -> int:
    """Return the pixel width for a visual-angle stimulus on a display."""

    physical_width_cm = visual_angle_width_cm(
        degrees=degrees,
        viewing_distance_cm=viewing_distance_cm,
    )
    pixels_per_cm = float(screen_width_px) / screen_width_cm
    return max(1, round(physical_width_cm * pixels_per_cm))
