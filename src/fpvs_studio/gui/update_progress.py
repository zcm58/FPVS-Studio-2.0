"""Shared progress rail for Studio and Library updates."""

from PySide6.QtCore import QAbstractAnimation, QRectF, Qt, QVariantAnimation, Slot
from PySide6.QtGui import (
    QColor,
    QHideEvent,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QShowEvent,
)
from PySide6.QtWidgets import QProgressBar, QWidget

from fpvs_studio.gui.components import widget_animation_duration
from fpvs_studio.gui.design_system import resolve_studio_theme

PROGRESS_MAXIMUM = 1000


class UpdateProgressBar(QProgressBar):
    """Display reported progress on a compact rail with optional download motion."""

    def __init__(self, parent: QWidget, *, animate_download: bool = False) -> None:
        super().__init__(parent)
        self.setMinimumHeight(22)
        self._animate_download = animate_download
        self._motion_enabled = False
        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(1650)
        self._animation.setLoopCount(-1)
        self._animation.valueChanged.connect(lambda _value: self.update())
        self.valueChanged.connect(self._sync_animation)

    def setRange(self, minimum: int, maximum: int) -> None:  # noqa: N802
        if (minimum, maximum) != (self.minimum(), self.maximum()):
            super().setRange(minimum, maximum)
            self._sync_animation()

    def set_byte_progress(self, received: int, total: int | None) -> None:
        """Scale byte counts to Qt's integer range without rounding up."""
        if total is None or total <= 0:
            self.setRange(0, 0)
            return
        self.setRange(0, PROGRESS_MAXIMUM)
        self.setValue(max(0, min(received, total)) * PROGRESS_MAXIMUM // total)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._motion_enabled = bool(widget_animation_duration(self, 160))
        self._sync_animation()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self._animation.stop()
        super().hideEvent(event)

    @Slot()
    def _sync_animation(self) -> None:
        should_move = self._motion_enabled and self.isVisible() and (
            self.maximum() == 0
            or (self._animate_download and self.minimum() < self.value() < self.maximum())
        )
        if should_move:
            if self._animation.state() != QAbstractAnimation.State.Running:
                self._animation.start()
        else:
            self._animation.stop()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        theme = resolve_studio_theme(self.window().palette())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        bar_height = 6.0
        rail = QRectF(0, (self.height() - bar_height) / 2, self.width(), bar_height)
        percentage = self.text() if self.isTextVisible() else ""
        if percentage:
            rail.setWidth(rail.width() - self.fontMetrics().horizontalAdvance("100%") - 12)
            painter.setPen(QColor(theme.text_secondary))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                percentage,
            )
            painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(QColor(theme.border_soft))
        radius = bar_height / 2
        painter.drawRoundedRect(rail, radius, radius)
        fill = QRectF(rail)
        accent = QColor(theme.primary)
        painter.setBrush(accent)
        moving = self._animation.state() == QAbstractAnimation.State.Running
        position = float(self._animation.currentValue()) if moving else 0.5
        if self.maximum() == 0:
            segment = rail.width() * 0.20
            fill.setWidth(segment)
            fill.moveLeft(position * (rail.width() + segment) - segment)
            fill = fill.intersected(rail)
        else:
            span = max(1, self.maximum() - self.minimum())
            progress = max(0, self.value() - self.minimum()) / span
            fill.setWidth(rail.width() * progress)
            if moving:
                # The highlight travels across the reported fill. It adds no progress of its own.
                band = min(rail.width() * 0.14, 64.0)
                center = position * (fill.width() + 2 * band) - band
                highlight = QLinearGradient(center - band, 0, center + band, 0)
                highlight.setColorAt(0.0, accent)
                highlight.setColorAt(0.5, accent.lighter(135))
                highlight.setColorAt(1.0, accent)
                painter.setBrush(highlight)
        if fill.width() > 0:
            radius = min(radius, fill.width() / 2)
            painter.drawRoundedRect(fill, radius, radius)
        painter.end()
