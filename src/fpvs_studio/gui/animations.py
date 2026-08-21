"""Reusable UI animation helpers for the PySide6 authoring shell. These helpers style
widget motion and hover behavior so the GUI can feel responsive without embedding domain
or runtime logic. The module owns presentation polish only; project semantics and launch
behavior stay in backend services and main widgets."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QObject, Qt, QVariantAnimation
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QPushButton


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
        if not isinstance(value, (float, int)):
            return
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
