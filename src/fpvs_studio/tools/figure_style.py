"""Reusable publication defaults for Studio figure renderers."""

FIGURE_EXPORT_DPI = 600
FIGURE_DOUBLE_COLUMN_WIDTH_MM = 183
FIGURE_FONT_FAMILY = "Open Sans"
FIGURE_TEXT_COLOR = "#000000"

FIGURE_TITLE_SIZE_PT = 7
FIGURE_LABEL_SIZE_PT = 6
FIGURE_TICK_SIZE_PT = 5


def pixels_per_placed_point(
    canvas_width_px: int, placed_width_mm: float = FIGURE_DOUBLE_COLUMN_WIDTH_MM,
) -> float:
    """Return export pixels per point when the canvas is placed at its final width."""
    return canvas_width_px * 25.4 / (placed_width_mm * 72)
