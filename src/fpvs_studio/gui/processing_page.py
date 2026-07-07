"""In-window processing screens for long-running FPVS Studio tasks."""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QHideEvent, QPainter, QPaintEvent, QPen, QShowEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from fpvs_studio.core.project_bundle import BundleExportStage, BundleImportStage
from fpvs_studio.gui.components import StatusBadgeLabel, refresh_widget_style
from fpvs_studio.gui.design_system import (
    FONT_SIZE_BODY,
    FONT_SIZE_PAGE_TITLE,
    FONT_SIZE_SECTION_TITLE,
    resolve_studio_theme,
)

_ProcessingStage = BundleExportStage | BundleImportStage
_EXPORT_STEP_STAGE_ORDER: tuple[_ProcessingStage, ...] = (
    "validate",
    "stimuli",
    "write",
)
_EXPORT_STEP_LABELS: dict[_ProcessingStage, tuple[str, str]] = {
    "validate": ("1", "Validate"),
    "stimuli": ("2", "Check stimuli"),
    "write": ("3", "Write bundle"),
}
_IMPORT_STEP_STAGE_ORDER: tuple[_ProcessingStage, ...] = (
    "verify",
    "base",
    "oddball",
    "project",
)
_IMPORT_STEP_LABELS: dict[_ProcessingStage, tuple[str, str]] = {
    "verify": ("1", "Verify bundle"),
    "base": ("2", "Set up base images"),
    "oddball": ("3", "Set up oddball images"),
    "project": ("4", "Open project"),
}
_StepState = Literal["pending", "active", "complete"]


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


class _BundleProcessingPage(QWidget):
    """Embedded progress page shown during portable bundle work."""

    def __init__(
        self,
        *,
        object_prefix: str,
        eyebrow: str,
        title: str,
        message: str,
        detail: str,
        status_badge_text: str,
        status_hint: str,
        complete_badge_text: str,
        stage_order: tuple[_ProcessingStage, ...],
        step_labels: dict[_ProcessingStage, tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._stage_order = stage_order
        self._complete_badge_text = complete_badge_text
        self.setObjectName(f"{object_prefix}_page")
        self.setProperty("bundleProcessingPage", "true")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(0)

        self.content = QWidget(self)
        self.content.setObjectName(f"{object_prefix}_content")
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
        status_column.setObjectName(f"{object_prefix}_status_column")
        status_column.setMinimumWidth(230)
        status_column.setMaximumWidth(270)
        status_layout = QVBoxLayout(status_column)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(18)
        status_layout.addStretch(1)

        self.spinner = SpinnerWidget(parent=status_column)
        status_layout.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignHCenter)

        self.status_badge = StatusBadgeLabel(parent=status_column)
        self.status_badge.setObjectName(f"{object_prefix}_status_badge")
        self.status_badge.setProperty("bundleProcessingStatusBadge", "true")
        self.status_badge.set_state("info", status_badge_text)
        status_layout.addWidget(self.status_badge)

        self.status_hint_label = QLabel(
            status_hint,
            status_column,
        )
        self.status_hint_label.setObjectName(f"{object_prefix}_status_hint_label")
        self.status_hint_label.setProperty("bundleProcessingRole", "statusHint")
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
        divider.setObjectName(f"{object_prefix}_divider")
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setProperty("processingDivider", "true")

        text_column = QWidget(self.content)
        text_column.setObjectName(f"{object_prefix}_text_column")
        text_column.setMinimumWidth(0)
        text_column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        text_layout = QVBoxLayout(text_column)
        text_layout.setContentsMargins(0, 6, 0, 0)
        text_layout.setSpacing(16)

        self.eyebrow_label = QLabel(eyebrow, text_column)
        self.eyebrow_label.setObjectName(f"{object_prefix}_eyebrow_label")
        self.eyebrow_label.setProperty("bundleProcessingRole", "eyebrow")
        self.eyebrow_label.setMinimumWidth(0)
        text_layout.addWidget(self.eyebrow_label)

        self.title_label = QLabel(title, text_column)
        self.title_label.setObjectName(f"{object_prefix}_title_label")
        self.title_label.setProperty("bundleProcessingRole", "title")
        self.title_label.setMinimumWidth(0)
        title_font = self.title_label.font()
        title_font.setPointSize(FONT_SIZE_PAGE_TITLE)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        text_layout.addWidget(self.title_label)

        self.message_label = QLabel(
            message,
            text_column,
        )
        self.message_label.setObjectName(f"{object_prefix}_message_label")
        self.message_label.setProperty("bundleProcessingRole", "message")
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
            detail,
            text_column,
        )
        self.detail_label.setObjectName(f"{object_prefix}_detail_label")
        self.detail_label.setProperty("bundleProcessingRole", "detail")
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
        self._steps: dict[_ProcessingStage, _ProcessingStep] = {}
        for stage in self._stage_order:
            number, text = step_labels[stage]
            step = _ProcessingStep(object_prefix, number, text, parent=text_column)
            self._steps[stage] = step
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
        self.reset_steps()

    def start(self) -> None:
        self.spinner.start()

    def stop(self) -> None:
        self.spinner.stop()
        for step in self._steps.values():
            step.stop_animation()

    def reset_steps(self) -> None:
        for step in self._steps.values():
            step.set_state("pending")

    def set_stage(self, stage: _ProcessingStage) -> None:
        if stage == "complete":
            for step in self._steps.values():
                step.set_state("complete")
            self.status_badge.set_state("ready", self._complete_badge_text)
            return
        if stage not in self._steps:
            return
        active_index = self._stage_order.index(stage)
        self.status_badge.set_state("info", f"{self._steps[stage].label_text}...")
        for index, step_stage in enumerate(self._stage_order):
            if index < active_index:
                state: _StepState = "complete"
            elif index == active_index:
                state = "active"
            else:
                state = "pending"
            self._steps[step_stage].set_state(state)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self.start()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self.stop()
        super().hideEvent(event)


class BundleExportProcessingPage(_BundleProcessingPage):
    """Embedded progress page shown while a `.fpvsbundle` archive is created."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(
            object_prefix="bundle_export_processing",
            eyebrow="FPVS Studio Project Bundle",
            title="Preparing project bundle",
            message=(
                "FPVS Studio is currently compiling your project into a shareable format. "
                "Please wait."
            ),
            detail=(
                "Validating project settings, checking stimulus files, and writing the "
                ".fpvsbundle archive."
            ),
            status_badge_text="Export running",
            status_hint="This may take a moment for large image sets.",
            complete_badge_text="Bundle ready",
            stage_order=_EXPORT_STEP_STAGE_ORDER,
            step_labels=_EXPORT_STEP_LABELS,
            parent=parent,
        )


class BundleImportProcessingPage(_BundleProcessingPage):
    """Embedded progress page shown while an `.fpvsbundle` project is imported."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(
            object_prefix="bundle_import_processing",
            eyebrow="FPVS Studio Project Import",
            title="Setting up imported project",
            message="FPVS Studio is currently setting up your project. Please wait.",
            detail=(
                "Verifying the bundle, setting up base and oddball image filepaths, "
                "and preparing the imported project."
            ),
            status_badge_text="Import running",
            status_hint="FPVS Studio is creating a local project from the bundle.",
            complete_badge_text="Project ready",
            stage_order=_IMPORT_STEP_STAGE_ORDER,
            step_labels=_IMPORT_STEP_LABELS,
            parent=parent,
        )


class _ProcessingStep(QWidget):
    """One compact status step in a bundle processing sequence."""

    def __init__(
        self,
        object_prefix: str,
        number: str,
        text: str,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.label_text = text
        self.setObjectName(f"{object_prefix}_step_{number}")
        self.setProperty("processingStep", "true")
        self.setMinimumWidth(0)
        self.setMinimumHeight(42)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._pulse_on = False
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(520)
        self._pulse_timer.timeout.connect(self._toggle_pulse)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        self.number_label = QLabel(number, self)
        self.number_label.setObjectName(f"{object_prefix}_step_{number}_number")
        self.number_label.setProperty("processingStepNumber", "true")
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_label.setFixedSize(30, 30)

        self.text_label = QLabel(text, self)
        self.text_label.setObjectName(f"{object_prefix}_step_{number}_label")
        self.text_label.setProperty("processingStepLabel", "true")
        self.text_label.setWordWrap(False)
        self.text_label.setMinimumWidth(0)
        self.text_label.setMinimumHeight(30)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.text_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

        layout.addWidget(self.number_label)
        layout.addWidget(self.text_label, 1)
        self.set_state("pending")

    def set_state(self, state: _StepState) -> None:
        self._pulse_on = False
        if state == "active":
            self._pulse_timer.start()
        else:
            self._pulse_timer.stop()
        self._set_step_property("processingStepState", state)
        self._set_step_property("processingStepPulse", "off")

    def stop_animation(self) -> None:
        self._pulse_timer.stop()
        self._pulse_on = False
        self._set_step_property("processingStepPulse", "off")

    def _toggle_pulse(self) -> None:
        self._pulse_on = not self._pulse_on
        self._set_step_property("processingStepPulse", "on" if self._pulse_on else "off")

    def _set_step_property(self, name: str, value: str) -> None:
        for widget in (self, self.number_label, self.text_label):
            widget.setProperty(name, value)
            refresh_widget_style(widget)
