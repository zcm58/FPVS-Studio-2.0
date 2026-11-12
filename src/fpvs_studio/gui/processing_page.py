"""In-window processing screens for long-running FPVS Studio tasks."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QHideEvent, QPainter, QPaintEvent, QPen, QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.project_bundle import BundleExportStage, BundleImportStage
from fpvs_studio.gui.components import (
    PathValueLabel,
    mark_primary_action,
    mark_secondary_action,
    refresh_widget_style,
)
from fpvs_studio.gui.design_system import FONT_SIZE_PAGE_TITLE, resolve_studio_theme

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
    "verify": ("1", "Verify"),
    "base": ("2", "Base"),
    "oddball": ("3", "Oddball"),
    "project": ("4", "Project"),
}
_IMPORT_ACTIVITY_LABELS: dict[_ProcessingStage, str] = {
    "verify": "Verify bundle",
    "base": "Check base stimuli",
    "oddball": "Check oddball stimuli",
    "project": "Create project",
}
_StepState = Literal["pending", "active", "complete"]


class SpinnerWidget(QWidget):
    """Small indeterminate spinner used on embedded processing pages."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("processing_spinner")
        self.setFixedSize(44, 44)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._advance)

    def sizeHint(self) -> QSize:
        return QSize(44, 44)

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
        title: str,
        status_hint: str,
        complete_activity_text: str,
        stage_order: tuple[_ProcessingStage, ...],
        step_labels: dict[_ProcessingStage, tuple[str, str]],
        activity_labels: dict[_ProcessingStage, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._stage_order = stage_order
        self._activity_labels = activity_labels or {
            stage: label for stage, (_number, label) in step_labels.items()
        }
        self._complete_activity_text = complete_activity_text
        self._default_title = title
        self.setObjectName(f"{object_prefix}_page")
        self.setProperty("bundleProcessingPage", "true")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(0)

        self.content = QFrame(self)
        self.content.setObjectName(f"{object_prefix}_content")
        self.content.setProperty("bundleProcessingCard", "true")
        self.content.setMaximumWidth(880)
        self.content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(28, 24, 28, 24)
        content_layout.setSpacing(14)

        self.title_label = QLabel(title, self.content)
        self.title_label.setObjectName(f"{object_prefix}_title_label")
        self.title_label.setProperty("bundleProcessingRole", "title")
        self.title_label.setMinimumWidth(0)
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        self.title_label.setWordWrap(True)
        title_font = self.title_label.font()
        title_font.setPointSize(FONT_SIZE_PAGE_TITLE)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        content_layout.addWidget(self.title_label)

        self.context_card = QWidget(self.content)
        self.context_card.setObjectName(f"{object_prefix}_context_card")
        context_layout = QGridLayout(self.context_card)
        context_layout.setContentsMargins(0, 6, 0, 6)
        context_layout.setHorizontalSpacing(12)
        context_layout.setVerticalSpacing(8)
        self.source_heading_label = QLabel("Source", self.context_card)
        self.source_heading_label.setProperty("bundleProcessingRole", "contextLabel")
        self.source_value_label = PathValueLabel(parent=self.context_card, single_line=True)
        self.source_value_label.setObjectName(f"{object_prefix}_source_value")
        self.source_value_label.setProperty("pathValue", "false")
        self.destination_heading_label = QLabel("Destination", self.context_card)
        self.destination_heading_label.setProperty("bundleProcessingRole", "contextLabel")
        self.destination_value_label = PathValueLabel(parent=self.context_card, single_line=True)
        self.destination_value_label.setObjectName(f"{object_prefix}_destination_value")
        self.destination_value_label.setProperty("pathValue", "false")
        context_layout.addWidget(self.source_heading_label, 0, 0)
        context_layout.addWidget(self.source_value_label, 0, 1)
        context_layout.addWidget(self.destination_heading_label, 1, 0)
        context_layout.addWidget(self.destination_value_label, 1, 1)
        context_layout.setColumnStretch(1, 1)
        self.context_card.hide()
        content_layout.addWidget(self.context_card)

        self.activity_card = QWidget(self.content)
        self.activity_card.setObjectName(f"{object_prefix}_activity_card")
        activity_layout = QHBoxLayout(self.activity_card)
        activity_layout.setContentsMargins(0, 8, 0, 8)
        activity_layout.setSpacing(12)
        self.spinner = SpinnerWidget(parent=self.activity_card)
        activity_layout.addWidget(self.spinner)
        activity_text_layout = QVBoxLayout()
        activity_text_layout.setContentsMargins(0, 0, 0, 0)
        activity_text_layout.setSpacing(3)
        self.current_activity_label = QLabel("Preparing…", self.activity_card)
        self.current_activity_label.setObjectName(f"{object_prefix}_current_activity")
        self.current_activity_label.setProperty("bundleProcessingRole", "activity")
        activity_text_layout.addWidget(self.current_activity_label)

        self.status_hint_label = QLabel(
            status_hint,
            self.activity_card,
        )
        self.status_hint_label.setObjectName(f"{object_prefix}_status_hint_label")
        self.status_hint_label.setProperty("bundleProcessingRole", "statusHint")
        self.status_hint_label.setWordWrap(True)
        self.status_hint_label.setMinimumWidth(0)
        activity_text_layout.addWidget(self.status_hint_label)
        activity_layout.addLayout(activity_text_layout, 1)
        content_layout.addWidget(self.activity_card)

        steps_row = QHBoxLayout()
        steps_row.setContentsMargins(0, 6, 0, 0)
        steps_row.setSpacing(14)
        self._steps: dict[_ProcessingStage, _ProcessingStep] = {}
        for stage in self._stage_order:
            number, step_text = step_labels[stage]
            step = _ProcessingStep(object_prefix, number, step_text, parent=self.content)
            self._steps[stage] = step
            steps_row.addWidget(step, 1)
        content_layout.addLayout(steps_row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 42, 40, 42)
        layout.setSpacing(0)
        layout.addStretch(1)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.content, 1)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch(1)
        self.reset_steps()

    def set_transfer_context(
        self,
        *,
        title: str | None,
        source_label: str,
        source_path: Path,
        destination_label: str,
        destination_path: Path,
    ) -> None:
        self.title_label.setText(title or self._default_title)
        self.source_heading_label.setText(source_label)
        self.source_value_label.set_path_text(str(source_path))
        self.destination_heading_label.setText(destination_label)
        self.destination_value_label.set_path_text(str(destination_path))
        self.context_card.show()

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
            self.current_activity_label.setText(self._complete_activity_text)
            self.spinner.stop()
            return
        if stage not in self._steps:
            return
        active_index = self._stage_order.index(stage)
        activity_text = self._activity_labels[stage]
        self.current_activity_label.setText(f"{activity_text}…")
        self.spinner.start()
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
            title="Exporting project bundle",
            status_hint="Keep FPVS Studio open until the export finishes.",
            complete_activity_text="Bundle ready",
            stage_order=_EXPORT_STEP_STAGE_ORDER,
            step_labels=_EXPORT_STEP_LABELS,
            parent=parent,
        )


class BundleImportProcessingPage(_BundleProcessingPage):
    """Embedded progress page shown while an `.fpvsbundle` project is imported."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(
            object_prefix="bundle_import_processing",
            title="Importing project bundle",
            status_hint="Keep FPVS Studio open until the import finishes.",
            complete_activity_text="Project ready",
            stage_order=_IMPORT_STEP_STAGE_ORDER,
            step_labels=_IMPORT_STEP_LABELS,
            activity_labels=_IMPORT_ACTIVITY_LABELS,
            parent=parent,
        )


def _format_file_size(size_bytes: int) -> str:
    value = float(max(0, size_bytes))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024.0 or unit == "GB":
            if unit == "B":
                return f"{int(value):,} {unit}"
            return f"{value:,.1f} {unit}"
        value /= 1024.0
    return f"{size_bytes:,} B"


class BundleExportResultPage(QWidget):
    """Persistent completion page shown after a bundle export succeeds."""

    done_requested = Signal()
    open_folder_requested = Signal(object)
    copy_path_requested = Signal(str)

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("bundle_export_result_page")
        self.setProperty("bundleResultPage", "true")
        self._bundle_path: Path | None = None

        card = QFrame(self)
        card.setObjectName("bundle_export_result_card")
        card.setProperty("bundleResultCard", "true")
        card.setMaximumWidth(760)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(13)

        heading = QVBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(5)
        title = QLabel("Project bundle ready", card)
        title.setObjectName("bundle_export_result_title")
        title.setProperty("bundleResultRole", "title")
        heading.addWidget(title)
        self.subtitle_label = QLabel(card)
        self.subtitle_label.setObjectName("bundle_export_result_subtitle")
        self.subtitle_label.setProperty("bundleResultRole", "lead")
        self.subtitle_label.setTextFormat(Qt.TextFormat.PlainText)
        self.subtitle_label.setWordWrap(True)
        heading.addWidget(self.subtitle_label)
        card_layout.addLayout(heading)

        file_text = QHBoxLayout()
        file_text.setContentsMargins(0, 0, 0, 0)
        file_text.setSpacing(12)
        self.filename_label = PathValueLabel(parent=card, single_line=True)
        self.filename_label.setObjectName("bundle_export_result_filename")
        self.filename_label.setProperty("pathValue", "false")
        self.filename_label.setProperty("bundleWorkflowRole", "fileName")
        self.metadata_label = QLabel(card)
        self.metadata_label.setObjectName("bundle_export_result_metadata")
        self.metadata_label.setProperty("bundleWorkflowRole", "meta")
        file_text.addWidget(self.filename_label, 1)
        file_text.addWidget(self.metadata_label)
        card_layout.addLayout(file_text)

        saved_heading = QLabel("Saved to", card)
        saved_heading.setProperty("bundleWorkflowRole", "sectionTitle")
        self.path_label = PathValueLabel(parent=card, single_line=True)
        self.path_label.setObjectName("bundle_export_result_path")
        self.path_label.setProperty("pathValue", "false")
        location = QHBoxLayout()
        location.setSpacing(12)
        location.addWidget(saved_heading)
        location.addWidget(self.path_label, 1)
        card_layout.addLayout(location)

        contents_layout = QVBoxLayout()
        contents_layout.setContentsMargins(0, 0, 0, 0)
        contents_layout.setSpacing(7)
        contents_heading = QLabel("Bundle contents", card)
        contents_heading.setProperty("bundleWorkflowRole", "sectionTitle")
        contents_layout.addWidget(contents_heading)
        self.contents_label = QLabel(card)
        self.contents_label.setWordWrap(True)
        contents_layout.addWidget(self.contents_label)
        excluded = QLabel("Not included: cache, logs, and runs", card)
        excluded.setProperty("bundleWorkflowRole", "meta")
        contents_layout.addWidget(excluded)
        card_layout.addLayout(contents_layout)

        self.copy_path_button = QPushButton("Copy Path", card)
        self.copy_path_button.setObjectName("bundle_export_result_copy_path")
        mark_secondary_action(self.copy_path_button)
        self.copy_path_button.clicked.connect(self._request_copy_path)
        self.open_folder_button = QPushButton("Open Folder", card)
        self.open_folder_button.setObjectName("bundle_export_result_open_folder")
        mark_secondary_action(self.open_folder_button)
        self.open_folder_button.clicked.connect(self._request_open_folder)
        self.done_button = QPushButton("Done", card)
        self.done_button.setObjectName("bundle_export_result_done")
        mark_primary_action(self.done_button)
        self.done_button.clicked.connect(self.done_requested.emit)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 2, 0, 0)
        buttons.setSpacing(10)
        buttons.addStretch(1)
        buttons.addWidget(self.copy_path_button)
        buttons.addWidget(self.open_folder_button)
        buttons.addWidget(self.done_button)
        card_layout.addLayout(buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 28, 40, 28)
        layout.addStretch(1)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(card, 1)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch(1)

    def set_result(
        self,
        *,
        project_name: str,
        bundle_path: Path,
        packaged_file_count: int,
    ) -> None:
        self._bundle_path = Path(bundle_path)
        self.subtitle_label.setText(project_name)
        self.filename_label.set_path_text(self._bundle_path.name)
        try:
            size_text = _format_file_size(self._bundle_path.stat().st_size)
        except OSError:
            size_text = "Size unavailable"
        self.metadata_label.setText(size_text)
        self.path_label.set_path_text(str(self._bundle_path))
        self.contents_label.setText(
            f"Project settings, {packaged_file_count:,} packaged files, "
            "manifest and integrity hashes"
        )

    def _request_copy_path(self) -> None:
        if self._bundle_path is not None:
            self.copy_path_requested.emit(str(self._bundle_path))

    def _request_open_folder(self) -> None:
        if self._bundle_path is not None:
            self.open_folder_requested.emit(self._bundle_path.parent)


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
        self.setObjectName(f"{object_prefix}_step_{number}")
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
