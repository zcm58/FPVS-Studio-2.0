"""Welcome screen shown before a project is opened."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)


def _rgba(color: QColor) -> str:
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


class WelcomeWindow(QWidget):
    """Responsive start page for creating/opening FPVS projects."""

    create_requested = Signal()
    open_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FPVS Studio")
        self.setMinimumSize(760, 520)
        self.resize(1040, 680)
        self._adopt_app_icon()

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(32, 32, 32, 32)
        page_layout.setSpacing(16)

        centered_content_layout = QHBoxLayout()
        centered_content_layout.setContentsMargins(0, 0, 0, 0)
        centered_content_layout.setSpacing(0)
        centered_content_layout.addStretch(1)

        self.content_frame = QFrame(self)
        self.content_frame.setObjectName("welcome_content_frame")
        self.content_frame.setMaximumWidth(980)
        self.content_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        centered_content_layout.addWidget(self.content_frame, 1)
        centered_content_layout.addStretch(1)
        page_layout.addLayout(centered_content_layout, 1)

        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(32, 32, 32, 32)
        content_layout.setSpacing(24)

        self.brand_label = QLabel("FPVS Studio", self.content_frame)
        self.brand_label.setObjectName("welcome_brand_label")
        content_layout.addWidget(self.brand_label)

        self.headline_label = QLabel("Start a project", self.content_frame)
        self.headline_label.setObjectName("welcome_headline_label")
        content_layout.addWidget(self.headline_label)

        self.body_label = QLabel(
            "Create or open an FPVS project, import assets, validate your session, "
            "and launch a supported test runtime.",
            self.content_frame,
        )
        self.body_label.setObjectName("welcome_body_label")
        self.body_label.setWordWrap(True)
        content_layout.addWidget(self.body_label)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)
        action_layout.setContentsMargins(0, 8, 0, 0)

        self.create_button = QPushButton("New Project", self.content_frame)
        self.create_button.setObjectName("create_project_button")
        self.create_button.setProperty("welcomeRole", "primary")
        self.create_button.setMinimumHeight(44)
        self.create_button.clicked.connect(self.create_requested.emit)
        action_layout.addWidget(self.create_button)

        self.open_button = QPushButton("Open Project", self.content_frame)
        self.open_button.setObjectName("open_project_button")
        self.open_button.setProperty("welcomeRole", "secondary")
        self.open_button.setMinimumHeight(44)
        self.open_button.clicked.connect(self.open_requested.emit)
        action_layout.addWidget(self.open_button)
        action_layout.addStretch(1)
        content_layout.addLayout(action_layout)
        content_layout.addStretch(1)

        self._apply_theme_styles()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            self._apply_theme_styles()

    def _apply_theme_styles(self) -> None:
        palette = self.palette()
        window_color = palette.color(QPalette.ColorRole.Window)
        base_color = palette.color(QPalette.ColorRole.Base)
        mid_color = palette.color(QPalette.ColorRole.Mid)
        text_color = palette.color(QPalette.ColorRole.Text)
        highlight_color = palette.color(QPalette.ColorRole.Highlight)
        highlighted_text_color = palette.color(QPalette.ColorRole.HighlightedText)

        muted_text = QColor(text_color)
        muted_text.setAlpha(190)
        subtle_text = QColor(text_color)
        subtle_text.setAlpha(150)

        is_dark = window_color.lightness() < 128
        content_bg = window_color.lighter(108) if is_dark else window_color.lighter(103)
        row_hover_bg = base_color.lighter(118) if is_dark else window_color.lighter(107)
        focus_color = highlight_color.lighter(125) if is_dark else highlight_color.darker(110)
        primary_hover = highlight_color.lighter(112) if is_dark else highlight_color.darker(108)
        primary_pressed = highlight_color.lighter(124) if is_dark else highlight_color.darker(118)

        self.setStyleSheet(
            f"""
            QFrame#welcome_content_frame {{
                border: 1px solid {_rgba(mid_color)};
                border-radius: 14px;
                background-color: {_rgba(content_bg)};
            }}
            QLabel#welcome_brand_label {{
                color: {_rgba(subtle_text)};
                font-size: 13px;
                font-weight: 600;
            }}
            QLabel#welcome_headline_label {{
                color: {_rgba(text_color)};
                font-size: 34px;
                font-weight: 700;
            }}
            QLabel#welcome_body_label {{
                color: {_rgba(muted_text)};
                font-size: 14px;
            }}
            QPushButton {{
                border: 1px solid {_rgba(mid_color)};
                border-radius: 8px;
                padding: 8px 14px;
                background-color: {_rgba(base_color)};
                color: {_rgba(text_color)};
            }}
            QPushButton:hover {{
                background-color: {_rgba(row_hover_bg)};
            }}
            QPushButton:pressed {{
                background-color: {_rgba(content_bg)};
            }}
            QPushButton[welcomeRole="primary"] {{
                border-color: {_rgba(highlight_color.darker(115))};
                background-color: {_rgba(highlight_color)};
                color: {_rgba(highlighted_text_color)};
                font-weight: 600;
            }}
            QPushButton[welcomeRole="primary"]:hover {{
                background-color: {_rgba(primary_hover)};
            }}
            QPushButton[welcomeRole="primary"]:pressed {{
                background-color: {_rgba(primary_pressed)};
            }}
            QPushButton:focus {{
                border: 2px solid {_rgba(focus_color)};
            }}
            """
        )

    def _adopt_app_icon(self) -> None:
        app = QApplication.instance()
        if app is not None and not app.windowIcon().isNull():
            self.setWindowIcon(app.windowIcon())
            return
        if self.windowIcon().isNull():
            fallback_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            if not fallback_icon.isNull():
                self.setWindowIcon(fallback_icon)
