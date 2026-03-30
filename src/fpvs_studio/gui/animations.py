"""Reusable UI animation helpers for the PySide6 authoring shell.
These classes style widget motion and hover behavior so the GUI can feel responsive without embedding domain or runtime logic.
The module owns presentation polish only; project semantics and launch behavior stay in backend services and main widgets."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QPushButton, QTabBar


def _interpolate_color(start: QColor, end: QColor, progress: float) -> QColor:
    """Return a linear color interpolation between start and end."""

    clamped = max(0.0, min(1.0, progress))
    return QColor(
        round(start.red() + (end.red() - start.red()) * clamped),
        round(start.green() + (end.green() - start.green()) * clamped),
        round(start.blue() + (end.blue() - start.blue()) * clamped),
        round(start.alpha() + (end.alpha() - start.alpha()) * clamped),
    )


class ButtonHoverAnimator(QObject):
    """Animate a subtle hover glow for QPushButton widgets."""

    def __init__(
        self,
        button: QPushButton,
        *,
        duration_ms: int = 160,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent or button)
        self._button = button
        self._hover_progress = 0.0
        self._shadow = QGraphicsDropShadowEffect(button)
        self._shadow.setBlurRadius(0.0)
        self._shadow.setOffset(0.0, 0.0)
        self._shadow.setColor(QColor(37, 99, 235, 0))
        button.setGraphicsEffect(self._shadow)
        button.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        button.setProperty("hoverAnimationEnabled", True)

        self._animation = QVariantAnimation(self)
        self._animation.setDuration(duration_ms)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._on_animation_value_changed)

        button.installEventFilter(self)

    @property
    def button(self) -> QPushButton:
        return self._button

    def hover_progress(self) -> float:
        return self._hover_progress

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is not self._button:
            return super().eventFilter(watched, event)

        event_type = event.type()
        if event_type in (QEvent.Type.Enter, QEvent.Type.HoverEnter):
            self._animate_to(1.0)
        elif event_type in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
            self._animate_to(0.0)
        elif event_type == QEvent.Type.EnabledChange and not self._button.isEnabled():
            self._animate_to(0.0)
        return super().eventFilter(watched, event)

    def _animate_to(self, target: float) -> None:
        desired = max(0.0, min(1.0, target))
        self._animation.stop()
        self._animation.setStartValue(self._hover_progress)
        self._animation.setEndValue(desired)
        self._animation.start()

    def _on_animation_value_changed(self, value: object) -> None:
        self._hover_progress = float(value)
        progress = self._hover_progress if self._button.isEnabled() else 0.0
        shadow_color = _interpolate_color(
            QColor(37, 99, 235, 0),
            QColor(37, 99, 235, 90),
            progress,
        )
        self._shadow.setColor(shadow_color)
        self._shadow.setBlurRadius(6.0 + (14.0 * progress))
        self._shadow.setOffset(0.0, 1.0 + progress)


class AnimatedTabBar(QTabBar):
    """QTabBar that animates hover transitions for each tab."""

    def __init__(self, parent=None, *, duration_ms: int = 180) -> None:
        super().__init__(parent)
        self._duration_ms = duration_ms
        self._hovered_tab_index = -1
        self._hover_progress: dict[int, float] = {}
        self._animations: dict[int, QVariantAnimation] = {}
        self.setMouseTracking(True)
        self.setDrawBase(False)
        self.setExpanding(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def hovered_tab_index(self) -> int:
        return self._hovered_tab_index

    def tab_hover_progress(self, index: int) -> float:
        return self._hover_progress.get(index, 0.0)

    def _uniform_tab_size_hint(self) -> QSize:
        tab_count = self.count()
        if tab_count == 0:
            return QSize(130, 40)

        max_width = 0
        max_height = 0
        for tab_index in range(tab_count):
            hint = super().tabSizeHint(tab_index)
            max_width = max(max_width, hint.width())
            max_height = max(max_height, hint.height())

        return QSize(max(130, max_width + 14), max(40, max_height + 10))

    def minimumTabSizeHint(self, index: int) -> QSize:  # noqa: N802
        return self._uniform_tab_size_hint()

    def tabSizeHint(self, index: int) -> QSize:  # noqa: N802
        return self._uniform_tab_size_hint()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._set_hovered_tab(self.tabAt(event.position().toPoint()))
        super().mouseMoveEvent(event)

    def event(self, event: QEvent) -> bool:
        event_type = event.type()
        if event_type == QEvent.Type.HoverMove:
            position_getter = getattr(event, "position", None)
            if callable(position_getter):
                self._set_hovered_tab(self.tabAt(position_getter().toPoint()))
        elif event_type == QEvent.Type.HoverLeave:
            self._set_hovered_tab(-1)
        return super().event(event)

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802
        self._set_hovered_tab(-1)
        super().leaveEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: ARG002, N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        neutral_fill = QColor("#e7edf7")
        hover_fill = QColor("#dbeafe")
        active_fill = QColor("#2563EB")
        active_hover_fill = QColor("#1D4ED8")

        neutral_border = QColor("#bcc9db")
        hover_border = QColor("#9fb2cc")
        active_border = QColor("#1E40AF")
        active_hover_border = QColor("#1E3A8A")

        neutral_text = QColor("#2f3f56")
        hover_text = QColor("#223751")
        active_text = QColor("#ffffff")
        active_indicator = QColor("#dbeafe")

        for index in range(self.count()):
            tab_rect = self.tabRect(index)
            if not tab_rect.isValid():
                continue

            rect = QRectF(tab_rect.adjusted(4, 6, -4, -4))
            progress = self._hover_progress.get(index, 0.0)
            is_current = index == self.currentIndex()

            if is_current:
                fill = _interpolate_color(active_fill, active_hover_fill, progress)
                border = _interpolate_color(active_border, active_hover_border, progress)
                text_color = active_text
            else:
                fill = _interpolate_color(neutral_fill, hover_fill, progress)
                border = _interpolate_color(neutral_border, hover_border, progress)
                text_color = _interpolate_color(neutral_text, hover_text, progress)

            painter.setPen(QPen(border, 1.0))
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 8.0, 8.0)

            font = painter.font()
            font.setBold(is_current)
            painter.setFont(font)
            painter.setPen(text_color)

            text_bounds = rect.toRect().adjusted(10, 0, -10, 0)
            label = painter.fontMetrics().elidedText(
                self.tabText(index),
                Qt.TextElideMode.ElideRight,
                max(0, text_bounds.width()),
            )
            painter.drawText(text_bounds, Qt.AlignmentFlag.AlignCenter, label)

            if is_current:
                indicator_rect = QRectF(
                    rect.left() + 12.0,
                    rect.bottom() - 2.0,
                    max(0.0, rect.width() - 24.0),
                    2.0,
                )
                painter.fillRect(indicator_rect, active_indicator)

    def _set_hovered_tab(self, index: int) -> None:
        if index == self._hovered_tab_index:
            return

        previous = self._hovered_tab_index
        self._hovered_tab_index = index

        if previous >= 0:
            self._animate_tab(previous, 0.0)
        if index >= 0:
            self._animate_tab(index, 1.0)

    def _animate_tab(self, index: int, target: float) -> None:
        if not 0 <= index < self.count():
            return

        animation = self._animations.get(index)
        if animation is None:
            animation = QVariantAnimation(self)
            animation.setDuration(self._duration_ms)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.valueChanged.connect(
                lambda value, tab_index=index: self._on_tab_progress_changed(tab_index, value)
            )
            self._animations[index] = animation

        animation.stop()
        animation.setStartValue(self._hover_progress.get(index, 0.0))
        animation.setEndValue(max(0.0, min(1.0, target)))
        animation.start()

    def _on_tab_progress_changed(self, index: int, value: object) -> None:
        self._hover_progress[index] = float(value)
        self.update()
