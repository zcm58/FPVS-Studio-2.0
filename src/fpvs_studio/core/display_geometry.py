"""Display geometry helpers for visual-angle stimulus sizing."""

from __future__ import annotations

from math import atan, radians, tan
from math import degrees as radians_to_degrees


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


def scaled_visual_angle_degrees(*, degrees: float, scale: float) -> float:
    """Scale a visual-angle extent in physical space and return visual degrees."""

    half_angle_radians = radians(degrees) / 2.0
    return radians_to_degrees(2.0 * atan(scale * tan(half_angle_radians)))
