"""Shared GUI design tokens and small presentation helpers for the PySide6 shell.

The module keeps the visual system lightweight and reusable without moving any
project semantics or runtime behavior into the GUI layer.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

PAGE_MARGIN_X = 24
PAGE_MARGIN_Y = 18
PAGE_SECTION_GAP = 12
CARD_PADDING_X = 14
CARD_PADDING_Y = 12
CARD_CORNER_RADIUS = 10
CARD_BORDER_WIDTH = 1

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
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

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
