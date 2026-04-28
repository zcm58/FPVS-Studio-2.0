"""Reusable layout widgets for the FPVS Studio main window pages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.design_system import (
    CARD_CORNER_RADIUS,
    CARD_PADDING_X,
    CARD_PADDING_Y,
    COLOR_BORDER,
    COLOR_BORDER_SOFT,
    COLOR_SURFACE,
    COLOR_SURFACE_ALT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    PAGE_MARGIN_X,
    PAGE_MARGIN_Y,
    PAGE_SECTION_GAP,
)
from fpvs_studio.gui.window_helpers import (
    _PAGE_WIDTH_PRESETS,
    _configure_centered_page_header_label,
)


class PageContainer(QWidget):
    """Top-aligned page container with optional bounded or full-width content."""

    def __init__(
        self,
        *,
        width_preset: str = "wide",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if width_preset not in _PAGE_WIDTH_PRESETS:
            raise ValueError(f"Unsupported width_preset: {width_preset}")

        self.width_preset = width_preset
        self.header_widget = QWidget(self)
        self.header_widget.setObjectName("page_container_header_widget")
        self.header_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        self.header_widget.setVisible(False)

        self.header_layout = QVBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(4)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("page_container_scroll_area")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.scroll_content = QWidget(self.scroll_area)
        self.scroll_content.setObjectName("page_container_scroll_content")
        self.scroll_content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.scroll_area.setWidget(self.scroll_content)

        self.scroll_content_layout = QVBoxLayout(self.scroll_content)
        self.scroll_content_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_content_layout.setSpacing(PAGE_SECTION_GAP)

        self.content_frame = QFrame(self)
        self.content_frame.setObjectName("page_container_content_frame")
        self.content_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(PAGE_SECTION_GAP)

        self._content_row = QHBoxLayout()
        self._content_row.setContentsMargins(0, 0, 0, 0)
        self._content_row.setSpacing(0)
        self._content_row.addStretch(1)
        self._content_row.addWidget(self.content_frame)
        self._content_row.addStretch(1)

        self.footer_strip = QFrame(self)
        self.footer_strip.setObjectName("non_home_shell_footer_strip")
        self.footer_strip.setVisible(False)
        footer_layout = QHBoxLayout(self.footer_strip)
        footer_layout.setContentsMargins(12, 8, 12, 8)
        footer_layout.setSpacing(8)
        self.footer_label = QLabel(self.footer_strip)
        self.footer_label.setObjectName("non_home_shell_footer_label")
        self.footer_label.setWordWrap(True)
        footer_layout.addWidget(self.footer_label, 1)

        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(
            PAGE_MARGIN_X, PAGE_MARGIN_Y, PAGE_MARGIN_X, PAGE_MARGIN_Y
        )
        self._outer_layout.setSpacing(PAGE_SECTION_GAP)
        self._outer_layout.addWidget(self.header_widget)
        self._outer_layout.addWidget(self.scroll_area, 1)

        self.scroll_content_layout.addLayout(self._content_row)
        self.scroll_content_layout.addWidget(self.footer_strip)

        self.set_width_preset(width_preset)

    def set_width_preset(self, width_preset: str) -> None:
        if width_preset not in _PAGE_WIDTH_PRESETS:
            raise ValueError(f"Unsupported width_preset: {width_preset}")
        self.width_preset = width_preset
        self.content_frame.setMaximumWidth(_PAGE_WIDTH_PRESETS[width_preset])
        if width_preset == "full":
            self._content_row.setStretch(0, 0)
            self._content_row.setStretch(1, 1)
            self._content_row.setStretch(2, 0)
        else:
            self._content_row.setStretch(0, 1)
            self._content_row.setStretch(1, 0)
            self._content_row.setStretch(2, 1)
        self.content_frame.setProperty("pageWidthPreset", width_preset)

    def max_content_width(self) -> int:
        return _PAGE_WIDTH_PRESETS[self.width_preset]


class NonHomePageShell(QWidget):
    """Reusable shell for non-home pages with bounded, top-aligned content."""

    def __init__(
        self,
        *,
        title: str,
        subtitle: str,
        layout_mode: str = "single_column",
        width_preset: str = "wide",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if layout_mode not in {"single_column", "three_column"}:
            raise ValueError(f"Unsupported layout_mode: {layout_mode}")

        self.layout_mode = layout_mode
        self._single_column_layout: QVBoxLayout | None = None
        self._column_layouts: list[QVBoxLayout] = []
        self._footer_widget: QWidget | None = None
        self.page_container = PageContainer(width_preset=width_preset, parent=self)

        self.title_label = QLabel(title, self.page_container.header_widget)
        self.title_label.setObjectName("non_home_shell_title")
        _configure_centered_page_header_label(self.title_label)
        self.subtitle_label = QLabel(subtitle, self.page_container.header_widget)
        self.subtitle_label.setObjectName("non_home_shell_subtitle")
        self.subtitle_label.setWordWrap(True)
        _configure_centered_page_header_label(self.subtitle_label)

        self.page_container.header_layout.addWidget(self.title_label)
        self.page_container.header_layout.addWidget(self.subtitle_label)
        self.page_container.header_widget.setVisible(True)

        self.content_frame = QFrame(self.page_container.content_frame)
        self.content_frame.setObjectName("non_home_shell_content_frame")
        self.page_container.content_layout.addWidget(self.content_frame)

        if layout_mode == "single_column":
            single_layout = QVBoxLayout(self.content_frame)
            single_layout.setContentsMargins(0, 0, 0, 0)
            single_layout.setSpacing(12)
            self._single_column_layout = single_layout
        else:
            columns_layout = QHBoxLayout(self.content_frame)
            columns_layout.setContentsMargins(0, 0, 0, 0)
            columns_layout.setSpacing(12)
            for column_name in ("left", "center", "right"):
                column_container = QWidget(self.content_frame)
                column_container.setObjectName(f"non_home_shell_column_{column_name}")
                column_layout = QVBoxLayout(column_container)
                column_layout.setContentsMargins(0, 0, 0, 0)
                column_layout.setSpacing(12)
                columns_layout.addWidget(column_container, 1)
                self._column_layouts.append(column_layout)
            columns_layout.setStretch(0, 3)
            columns_layout.setStretch(1, 4)
            columns_layout.setStretch(2, 3)

        self.footer_strip = self.page_container.footer_strip
        self.footer_label = self.page_container.footer_label

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.page_container)

        self.setStyleSheet(
            f"""
            QLabel#non_home_shell_title {{
                font-size: 24px;
                font-weight: 700;
                color: {COLOR_TEXT_PRIMARY};
            }}
            QLabel#non_home_shell_subtitle {{
                color: {COLOR_TEXT_SECONDARY};
                font-size: 13px;
            }}
            QFrame#non_home_shell_footer_strip {{
                border: 1px solid {COLOR_BORDER_SOFT};
                border-radius: {CARD_CORNER_RADIUS}px;
                background-color: {COLOR_SURFACE};
            }}
            QLabel#non_home_shell_footer_label {{
                color: {COLOR_TEXT_SECONDARY};
            }}
            """
        )

    def add_content_widget(self, widget: QWidget, *, stretch: int = 0) -> None:
        if self._single_column_layout is None:
            raise RuntimeError("add_content_widget is only available in single_column mode.")
        self._single_column_layout.addWidget(widget, stretch)

    def add_column_widget(self, column_index: int, widget: QWidget, *, stretch: int = 0) -> None:
        if self.layout_mode != "three_column":
            raise RuntimeError("add_column_widget is only available in three_column mode.")
        self._column_layouts[column_index].addWidget(widget, stretch)

    def add_column_stretch(self, column_index: int, stretch: int = 1) -> None:
        if self.layout_mode != "three_column":
            raise RuntimeError("add_column_stretch is only available in three_column mode.")
        self._column_layouts[column_index].addStretch(stretch)

    def set_column_stretches(self, left: int, center: int, right: int) -> None:
        if self.layout_mode != "three_column":
            raise RuntimeError("set_column_stretches is only available in three_column mode.")
        columns_layout = self.content_frame.layout()
        assert isinstance(columns_layout, QHBoxLayout)
        columns_layout.setStretch(0, left)
        columns_layout.setStretch(1, center)
        columns_layout.setStretch(2, right)

    def column_count(self) -> int:
        return len(self._column_layouts)

    def set_width_preset(self, width_preset: str) -> None:
        self.page_container.set_width_preset(width_preset)

    def set_footer_text(self, text: str | None) -> None:
        if not text:
            self.footer_label.clear()
            self.footer_strip.setVisible(False)
            return
        self.footer_label.setText(text)
        self.footer_strip.setVisible(True)

    def set_footer_widget(self, widget: QWidget | None) -> None:
        footer_layout = self.footer_strip.layout()
        assert isinstance(footer_layout, QHBoxLayout)
        if self._footer_widget is not None:
            footer_layout.removeWidget(self._footer_widget)
            self._footer_widget.setParent(None)
            self._footer_widget = None
        if widget is None:
            return
        widget.setParent(self.footer_strip)
        footer_layout.insertWidget(0, widget, 1)
        self._footer_widget = widget
        self.footer_strip.setVisible(True)


class SectionCard(QFrame):
    """Reusable section card with optional tooltip affordance."""

    def __init__(
        self,
        *,
        title: str,
        subtitle: str | None = None,
        tooltip_text: str | None = None,
        object_name: str = "section_card",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setProperty("sectionCard", "true")
        if tooltip_text:
            self.setToolTip(tooltip_text)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self.title_label = QLabel(title, self)
        self.title_label.setProperty("sectionCardRole", "title")
        header_layout.addWidget(self.title_label)

        self.tooltip_badge: QLabel | None = None
        if tooltip_text:
            self.tooltip_badge = QLabel("i", self)
            self.tooltip_badge.setObjectName("section_card_tooltip_badge")
            self.tooltip_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tooltip_badge.setToolTip(tooltip_text)
            self.tooltip_badge.setFixedSize(16, 16)
            header_layout.addWidget(self.tooltip_badge)

        header_layout.addStretch(1)

        self.card_layout = QVBoxLayout(self)
        self.card_layout.setContentsMargins(
            CARD_PADDING_X, CARD_PADDING_Y, CARD_PADDING_X, CARD_PADDING_Y
        )
        self.card_layout.setSpacing(PAGE_SECTION_GAP)
        self.card_layout.addLayout(header_layout)

        self.subtitle_label: QLabel | None = None
        if subtitle:
            self.subtitle_label = QLabel(subtitle, self)
            self.subtitle_label.setProperty("sectionCardRole", "subtitle")
            self.subtitle_label.setWordWrap(True)
            self.card_layout.addWidget(self.subtitle_label)

        self.body_layout = QVBoxLayout()
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(PAGE_SECTION_GAP)
        self.card_layout.addLayout(self.body_layout)

        self.setStyleSheet(
            f"""
            QFrame[sectionCard="true"] {{
                border: 1px solid {COLOR_BORDER};
                border-radius: {CARD_CORNER_RADIUS}px;
                background-color: {COLOR_SURFACE};
            }}
            QLabel[sectionCardRole="title"] {{
                font-size: 15px;
                font-weight: 700;
                color: {COLOR_TEXT_PRIMARY};
            }}
            QLabel[sectionCardRole="subtitle"] {{
                color: {COLOR_TEXT_SECONDARY};
            }}
            QLabel#section_card_tooltip_badge {{
                border: 1px solid {COLOR_BORDER_SOFT};
                border-radius: 8px;
                background-color: {COLOR_SURFACE_ALT};
                color: {COLOR_TEXT_PRIMARY};
                font-size: 11px;
                font-weight: 700;
            }}
            """
        )
