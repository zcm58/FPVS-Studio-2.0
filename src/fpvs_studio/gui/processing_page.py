"""In-window processing screens for long-running FPVS Studio tasks."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QHideEvent, QPainter, QPaintEvent, QPen, QShowEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from fpvs_studio.gui.components import StatusBadgeLabel
from fpvs_studio.gui.design_system import (
    FONT_SIZE_BODY,
    FONT_SIZE_PAGE_TITLE,
    FONT_SIZE_SECTION_TITLE,
    resolve_studio_theme,
)


class SpinnerWidget(QWidget):
    """Small indeterminate spinner used on embedded processing pages."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("processing_spinner")
        self.setFixedSize(72, 72)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._advance)

    def sizeHint(self) -> QSize:
        return QSize(72, 72)

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def stop(self) -> None:
        self._timer.stop()
        self.update()

    def _advance(self) -> None:
        self._angle = (self._angle + 18) % 360
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        theme = resolve_studio_theme(self.palette())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        side = min(self.width(), self.height()) - 8
        rect = QRectF(
            (self.width() - side) / 2,
            (self.height() - side) / 2,
            side,
            side,
        )
        background_pen = QPen(QColor(theme.border_soft), 5)
        background_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(background_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(rect, 0, 360 * 16)

        foreground_pen = QPen(QColor(theme.primary), 5)
        foreground_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(foreground_pen)
        painter.drawArc(rect, -self._angle * 16, -260 * 16)
        painter.end()


class BundleExportProcessingPage(QWidget):
    """Embedded progress page shown while a `.fpvsbundle` archive is created."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("bundle_export_processing_page")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(0)

        self.content = QWidget(self)
        self.content.setObjectName("bundle_export_processing_content")
        self.content.setMaximumWidth(1180)
        self.content.setMinimumHeight(300)
        self.content.setMinimumWidth(0)
        self.content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        content_layout = QHBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(32)

        status_column = QWidget(self.content)
        status_column.setObjectName("bundle_export_processing_status_column")
        status_column.setMinimumWidth(230)
        status_column.setMaximumWidth(270)
        status_layout = QVBoxLayout(status_column)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(18)
        status_layout.addStretch(1)

        self.spinner = SpinnerWidget(parent=status_column)
        status_layout.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignHCenter)

        self.status_badge = StatusBadgeLabel(parent=status_column)
        self.status_badge.setObjectName("bundle_export_processing_status_badge")
        self.status_badge.set_state("info", "Export running")
        status_layout.addWidget(self.status_badge)

        self.status_hint_label = QLabel(
            "This may take a moment for large image sets.",
            status_column,
        )
        self.status_hint_label.setObjectName("bundle_export_processing_status_hint_label")
        self.status_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_hint_label.setWordWrap(True)
        self.status_hint_label.setMinimumWidth(0)
        self.status_hint_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        status_layout.addWidget(self.status_hint_label)
        status_layout.addStretch(1)

        divider = QFrame(self.content)
        divider.setObjectName("bundle_export_processing_divider")
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setProperty("processingDivider", "true")

        text_column = QWidget(self.content)
        text_column.setObjectName("bundle_export_processing_text_column")
        text_column.setMinimumWidth(0)
        text_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        text_layout = QVBoxLayout(text_column)
        text_layout.setContentsMargins(0, 6, 0, 0)
        text_layout.setSpacing(16)

        self.eyebrow_label = QLabel("FPVS Studio Project Bundle", text_column)
        self.eyebrow_label.setObjectName("bundle_export_processing_eyebrow_label")
        self.eyebrow_label.setMinimumWidth(0)
        text_layout.addWidget(self.eyebrow_label)

        self.title_label = QLabel("Preparing project bundle", text_column)
        self.title_label.setObjectName("bundle_export_processing_title_label")
        self.title_label.setMinimumWidth(0)
        title_font = self.title_label.font()
        title_font.setPointSize(FONT_SIZE_PAGE_TITLE)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        text_layout.addWidget(self.title_label)

        self.message_label = QLabel(
            "FPVS Studio is currently compiling your project into a shareable format. "
            "Please wait.",
            text_column,
        )
        self.message_label.setObjectName("bundle_export_processing_message_label")
        self.message_label.setWordWrap(True)
        self.message_label.setMinimumWidth(0)
        self.message_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        message_font = self.message_label.font()
        message_font.setPointSize(FONT_SIZE_SECTION_TITLE)
        message_font.setBold(True)
        self.message_label.setFont(message_font)
        text_layout.addWidget(self.message_label)

        self.detail_label = QLabel(
            "Validating project settings, checking stimulus files, and writing the "
            ".fpvsbundle archive.",
            text_column,
        )
        self.detail_label.setObjectName("bundle_export_processing_detail_label")
        self.detail_label.setWordWrap(True)
        self.detail_label.setMinimumWidth(0)
        self.detail_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        detail_font = self.detail_label.font()
        detail_font.setPointSize(FONT_SIZE_BODY)
        self.detail_label.setFont(detail_font)
        text_layout.addWidget(self.detail_label)

        steps_row = QHBoxLayout()
        steps_row.setContentsMargins(0, 24, 0, 8)
        steps_row.setSpacing(14)
        steps = (
            ("1", "Validate"),
            ("2", "Check stimuli"),
            ("3", "Write bundle"),
        )
        for number, text in steps:
            step = _ProcessingStep(number, text, parent=text_column)
            steps_row.addWidget(step, 1)
        text_layout.addLayout(steps_row)
        text_layout.addStretch(1)

        content_layout.addWidget(status_column, 0)
        content_layout.addWidget(divider)
        content_layout.addWidget(text_column, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 52, 40, 52)
        layout.setSpacing(0)
        layout.addStretch(1)
        layout.addWidget(self.content)
        layout.addStretch(1)

    def start(self) -> None:
        self.spinner.start()

    def stop(self) -> None:
        self.spinner.stop()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self.start()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self.stop()
        super().hideEvent(event)


class _ProcessingStep(QWidget):
    """One compact status step in the bundle-export processing sequence."""

    def __init__(self, number: str, text: str, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(f"bundle_export_processing_step_{number}")
        self.setProperty("processingStep", "true")
        self.setMinimumWidth(0)
        self.setMinimumHeight(42)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        number_label = QLabel(number, self)
        number_label.setObjectName(f"bundle_export_processing_step_{number}_number")
        number_label.setProperty("processingStepNumber", "true")
        number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number_label.setFixedSize(30, 30)

        text_label = QLabel(text, self)
        text_label.setObjectName(f"bundle_export_processing_step_{number}_label")
        text_label.setProperty("processingStepLabel", "true")
        text_label.setWordWrap(False)
        text_label.setMinimumWidth(0)
        text_label.setMinimumHeight(30)
        text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        text_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

        layout.addWidget(number_label)
        layout.addWidget(text_label, 1)
