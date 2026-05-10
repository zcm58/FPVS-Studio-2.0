"""Shared GUI design tokens and small presentation helpers for the PySide6 shell.

The module keeps the visual system lightweight and reusable without moving any
project semantics or runtime behavior into the GUI layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QLabel, QWidget

PAGE_MARGIN_X = 24
PAGE_MARGIN_Y = 18
PAGE_SECTION_GAP = 12
CARD_PADDING_X = 14
CARD_PADDING_Y = 12
CARD_CORNER_RADIUS = 10
CARD_BORDER_WIDTH = 1
FONT_SIZE_META = 12
FONT_SIZE_BODY = 13
FONT_SIZE_CONTROL = 13
FONT_SIZE_SECTION_TITLE = 16
FONT_SIZE_PAGE_TITLE = 24

CONTENT_MAX_WIDTHS: dict[str, int] = {
    "narrow": 920,
    "medium": 1100,
    "wide": 1280,
    "data_wide": 1440,
    "full": 16_777_215,
}

COLOR_PAGE_BACKGROUND = "#f4f7fb"
COLOR_SURFACE = "#f8fafc"
COLOR_SURFACE_ALT = "#eef3f9"
COLOR_SURFACE_ELEVATED = "#ffffff"
COLOR_BORDER = "#c7d0dd"
COLOR_BORDER_SOFT = "#d7dfea"
COLOR_TEXT_PRIMARY = "#1f2f44"
COLOR_TEXT_SECONDARY = "#33485f"
COLOR_TEXT_MUTED = "#455a72"
COLOR_TEXT_HINT = "#5f7084"
COLOR_PRIMARY = "#2563eb"
COLOR_PRIMARY_HOVER = "#1d4ed8"
COLOR_PRIMARY_PRESSED = "#1e40af"
COLOR_PRIMARY_BORDER = "#1e40af"
COLOR_SUCCESS_BG = "#dcfce7"
COLOR_SUCCESS_BORDER = "#86efac"
COLOR_SUCCESS_TEXT = "#166534"
COLOR_WARNING_BG = "#ffedd5"
COLOR_WARNING_BORDER = "#fdba74"
COLOR_WARNING_TEXT = "#9a3412"
COLOR_INFO_BG = "#e0f2fe"
COLOR_INFO_BORDER = "#7dd3fc"
COLOR_INFO_TEXT = "#0c4a6e"
COLOR_PENDING_BG = "#f1f5f9"
COLOR_PENDING_BORDER = "#cbd5e1"
COLOR_PENDING_TEXT = "#475569"


class StudioColorScheme(Enum):
    """Supported Studio authoring UI color schemes."""

    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class StudioTheme:
    """Resolved color tokens for shared PySide6 stylesheets."""

    scheme: StudioColorScheme
    page_background: str
    surface: str
    surface_alt: str
    surface_elevated: str
    border: str
    border_soft: str
    text_primary: str
    text_secondary: str
    text_muted: str
    text_hint: str
    disabled_text: str
    primary: str
    primary_hover: str
    primary_pressed: str
    primary_border: str
    primary_disabled_bg: str
    primary_disabled_text: str
    focus_ring: str
    success_bg: str
    success_border: str
    success_text: str
    warning_bg: str
    warning_border: str
    warning_text: str
    info_bg: str
    info_border: str
    info_text: str
    pending_bg: str
    pending_border: str
    pending_text: str
    error_bg: str
    error_border: str
    error_text: str
    destructive_text: str
    selected_text: str


LIGHT_STUDIO_THEME = StudioTheme(
    scheme=StudioColorScheme.LIGHT,
    page_background=COLOR_PAGE_BACKGROUND,
    surface=COLOR_SURFACE,
    surface_alt=COLOR_SURFACE_ALT,
    surface_elevated=COLOR_SURFACE_ELEVATED,
    border=COLOR_BORDER,
    border_soft=COLOR_BORDER_SOFT,
    text_primary=COLOR_TEXT_PRIMARY,
    text_secondary=COLOR_TEXT_SECONDARY,
    text_muted=COLOR_TEXT_MUTED,
    text_hint=COLOR_TEXT_HINT,
    disabled_text="#8a97a8",
    primary=COLOR_PRIMARY,
    primary_hover=COLOR_PRIMARY_HOVER,
    primary_pressed=COLOR_PRIMARY_PRESSED,
    primary_border=COLOR_PRIMARY_BORDER,
    primary_disabled_bg="#93c5fd",
    primary_disabled_text="#eff6ff",
    focus_ring=COLOR_PRIMARY,
    success_bg=COLOR_SUCCESS_BG,
    success_border=COLOR_SUCCESS_BORDER,
    success_text=COLOR_SUCCESS_TEXT,
    warning_bg=COLOR_WARNING_BG,
    warning_border=COLOR_WARNING_BORDER,
    warning_text=COLOR_WARNING_TEXT,
    info_bg=COLOR_INFO_BG,
    info_border=COLOR_INFO_BORDER,
    info_text=COLOR_INFO_TEXT,
    pending_bg=COLOR_PENDING_BG,
    pending_border=COLOR_PENDING_BORDER,
    pending_text=COLOR_PENDING_TEXT,
    error_bg="#fef2f2",
    error_border="#fca5a5",
    error_text="#991b1b",
    destructive_text="#b91c1c",
    selected_text="#ffffff",
)


DARK_STUDIO_THEME = StudioTheme(
    scheme=StudioColorScheme.DARK,
    page_background="#202124",
    surface="#24272d",
    surface_alt="#2d333b",
    surface_elevated="#30343b",
    border="#566170",
    border_soft="#3f4854",
    text_primary="#f3f6fb",
    text_secondary="#cbd5e1",
    text_muted="#aeb8c7",
    text_hint="#94a3b8",
    disabled_text="#727d8c",
    primary="#60a5fa",
    primary_hover="#93c5fd",
    primary_pressed="#3b82f6",
    primary_border="#93c5fd",
    primary_disabled_bg="#1e3a5f",
    primary_disabled_text="#93a4ba",
    focus_ring="#93c5fd",
    success_bg="#123524",
    success_border="#2e7d4f",
    success_text="#8ee6aa",
    warning_bg="#3a2a13",
    warning_border="#9a6a21",
    warning_text="#f8c471",
    info_bg="#123246",
    info_border="#2f7ea8",
    info_text="#9bdcf8",
    pending_bg="#2b3139",
    pending_border="#576274",
    pending_text="#cbd5e1",
    error_bg="#3a171b",
    error_border="#a0444d",
    error_text="#ffb4bd",
    destructive_text="#ffb4bd",
    selected_text="#07111f",
)


def resolve_studio_theme(palette: QPalette | None = None) -> StudioTheme:
    """Return the Studio theme that matches the effective Qt color scheme."""

    effective_palette = palette or QGuiApplication.palette()
    window_lightness = effective_palette.color(QPalette.ColorRole.Window).lightness()

    style_hints = QGuiApplication.styleHints() if QGuiApplication.instance() else None
    color_scheme = style_hints.colorScheme() if style_hints is not None else None
    if color_scheme == Qt.ColorScheme.Dark and window_lightness < 170:
        return DARK_STUDIO_THEME
    if color_scheme == Qt.ColorScheme.Light and window_lightness > 96:
        return LIGHT_STUDIO_THEME
    if window_lightness < 128:
        return DARK_STUDIO_THEME
    return LIGHT_STUDIO_THEME


def contrast_ratio(foreground: str, background: str) -> float:
    """Compute the WCAG contrast ratio for two hex colors."""

    foreground_luminance = _relative_luminance(QColor(foreground))
    background_luminance = _relative_luminance(QColor(background))
    lighter = max(foreground_luminance, background_luminance)
    darker = min(foreground_luminance, background_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def _relative_luminance(color: QColor) -> float:
    channels = [color.redF(), color.greenF(), color.blueF()]
    linear_channels = [
        channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return (
        0.2126 * linear_channels[0]
        + 0.7152 * linear_channels[1]
        + 0.0722 * linear_channels[2]
    )


def elide_middle(text: str, max_length: int) -> str:
    """Return a centered elision when text exceeds the preferred length."""

    if max_length <= 3 or len(text) <= max_length:
        return text

    keep_length = max_length - 3
    front_length = keep_length // 2
    back_length = keep_length - front_length
    return f"{text[:front_length]}...{text[-back_length:]}"


def set_truncated_label_text(label: QLabel, text: str, *, max_length: int) -> None:
    """Set a label to an elided value while preserving the full value in a tooltip."""

    display_text = elide_middle(text, max_length)
    label.setText(display_text)
    label.setToolTip(text if display_text != text else "")


class StatusBadgeLabel(QLabel):
    """Small badge-style label used for readiness and summary states."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("status_badge_label")
        self.setProperty("statusBadge", "true")
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_state(self, state: str, text: str) -> None:
        self.setText(text)
        self.setProperty("statusState", state)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class PathValueLabel(QLabel):
    """Selectable label that shows a shortened path and preserves the full path tooltip."""

    def __init__(self, text: str | QWidget = "", parent: QWidget | None = None) -> None:
        if isinstance(text, QWidget):
            if parent is None:
                parent = text
            label_text = ""
        else:
            label_text = text
        super().__init__(label_text, parent)
        self.setObjectName("path_value_label")
        self.setProperty("pathValue", "true")
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    def set_path_text(self, text: str, *, max_length: int = 72) -> None:
        set_truncated_label_text(self, text, max_length=max_length)
