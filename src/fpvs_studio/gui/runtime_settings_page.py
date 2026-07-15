"""Focused display settings editor for the FPVS Studio GUI."""

from __future__ import annotations

import logging

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.display_geometry import visual_angle_width_cm, visual_angle_width_px
from fpvs_studio.core.enums import DutyCycleMode, EngineName
from fpvs_studio.core.models import DisplayValidationReport
from fpvs_studio.core.validation import (
    APPROVED_MONITOR_REFRESH_RATES_HZ,
    approved_monitor_refresh_rate,
    measured_refresh_matches_configured,
    nearest_approved_monitor_refresh_rate,
    validate_display_refresh,
)
from fpvs_studio.engines.registry import create_engine
from fpvs_studio.gui.components import (
    SectionCard,
    apply_image_size_preview_dialog_theme,
    mark_secondary_action,
    refresh_widget_style,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import (
    _RUNTIME_BACKGROUND_COLOR_PRESETS,
    _canonical_runtime_background_hex,
    _prefixed_object_name,
    _show_error_dialog,
)
from fpvs_studio.gui.workers import ProgressTask

LOGGER = logging.getLogger(__name__)


class DisplaySettingsEditor(QWidget):
    """Reusable display and project-wide FPVS timing editor."""

    refresh_verification_changed = Signal()

    def __init__(
        self,
        document: ProjectDocument,
        *,
        object_name_prefix: str = "",
        editable: bool = True,
        framed: bool = False,
        show_scope_label: bool = True,
        require_refresh_verification: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._editable = editable
        self._require_refresh_verification = require_refresh_verification
        self._background_refresh_guard = False
        self._refresh_probe_task: ProgressTask | None = None
        self._measured_refresh_hz: float | None = None
        self._verified_refresh_hz: float | None = None
        self._refresh_measurement_error: str | None = None

        self.refresh_hz_combo = QComboBox(self)
        self.refresh_hz_combo.setObjectName(
            _prefixed_object_name(object_name_prefix, "refresh_hz_combo")
        )
        for refresh_hz in APPROVED_MONITOR_REFRESH_RATES_HZ:
            self.refresh_hz_combo.addItem(f"{refresh_hz:g} Hz", userData=refresh_hz)
        self.refresh_hz_combo.setToolTip(
            "Approved presentation-display rates. Use Detect My Refresh Rate to verify "
            "the connected monitor and apply the closest approved value."
        )
        self.refresh_hz_combo.currentIndexChanged.connect(self._apply_refresh_hz)

        self.detect_refresh_button = QPushButton("Detect My Refresh Rate", self)
        self.detect_refresh_button.setObjectName(
            _prefixed_object_name(object_name_prefix, "detect_refresh_button")
        )
        self.detect_refresh_button.setToolTip(
            "Temporarily opens PsychoPy fullscreen on the default presentation display "
            "and measures its actual frame rate."
        )
        self.detect_refresh_button.clicked.connect(self._start_refresh_detection)
        mark_secondary_action(self.detect_refresh_button)

        self.base_hz_spin = QDoubleSpinBox(self)
        self.base_hz_spin.setObjectName(
            _prefixed_object_name(object_name_prefix, "base_hz_spin")
        )
        self.base_hz_spin.setRange(0.01, 500.0)
        self.base_hz_spin.setDecimals(3)
        self.base_hz_spin.setSingleStep(0.1)
        self.base_hz_spin.setSuffix(" Hz")
        self.base_hz_spin.valueChanged.connect(self._apply_protocol_settings)

        self.oddball_every_n_spin = QSpinBox(self)
        self.oddball_every_n_spin.setObjectName(
            _prefixed_object_name(object_name_prefix, "oddball_every_n_spin")
        )
        self.oddball_every_n_spin.setRange(1, 1000)
        self.oddball_every_n_spin.setSuffix(" stimuli")
        self.oddball_every_n_spin.valueChanged.connect(self._apply_protocol_settings)

        self.runtime_background_color_combo = QComboBox(self)
        self.runtime_background_color_combo.setObjectName(
            _prefixed_object_name(object_name_prefix, "runtime_background_color_combo")
        )
        for label, background_hex in _RUNTIME_BACKGROUND_COLOR_PRESETS:
            self.runtime_background_color_combo.addItem(label, userData=background_hex)
        self.runtime_background_color_combo.currentIndexChanged.connect(
            self._apply_runtime_background_color
        )

        self.runtime_background_scope_label = QLabel(
            "Used during FPVS image presentation.",
            self,
        )
        self.runtime_background_scope_label.setObjectName(
            _prefixed_object_name(object_name_prefix, "runtime_background_scope_label")
        )
        self.runtime_background_scope_label.setWordWrap(True)

        self.timing_summary_label = QLabel(self)
        self.timing_summary_label.setObjectName(
            _prefixed_object_name(object_name_prefix, "timing_summary_label")
        )
        self.timing_summary_label.setWordWrap(True)
        self.timing_summary_label.setMinimumWidth(0)

        self.timing_status_label = QLabel(self)
        self.timing_status_label.setObjectName(
            _prefixed_object_name(object_name_prefix, "timing_status_label")
        )
        self.timing_status_label.setWordWrap(True)
        self.timing_status_label.setMinimumWidth(0)
        self.timing_status_label.setProperty("statusBadge", "true")

        self.summary_value_labels: dict[str, QLabel] = {}
        self.form_container = QWidget(self)
        self.form_layout = QFormLayout(self.form_container)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setHorizontalSpacing(12)
        self.form_layout.setVerticalSpacing(8)
        self.form_layout.addRow("Monitor refresh", self.refresh_hz_combo)
        self.form_layout.addRow(self.detect_refresh_button)
        self.form_layout.addRow("Base rate", self.base_hz_spin)
        self.form_layout.addRow("Oddball every", self.oddball_every_n_spin)
        self.form_layout.addRow("Background", self.runtime_background_color_combo)
        self.form_layout.addRow(self.timing_summary_label)
        self.form_layout.addRow(self.timing_status_label)
        if show_scope_label:
            self.form_layout.addRow("", self.runtime_background_scope_label)
        else:
            self.runtime_background_scope_label.setText("")
            self.runtime_background_scope_label.setVisible(False)

        self.summary_container = QWidget(self)
        self.summary_layout = QFormLayout(self.summary_container)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_layout.setHorizontalSpacing(12)
        self.summary_layout.setVerticalSpacing(6)
        for key, label_text in (
            ("refresh", "Refresh"),
            ("base", "Base rate"),
            ("oddball", "Oddball"),
            ("background", "Background"),
        ):
            value_label = QLabel(self.summary_container)
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.summary_value_labels[key] = value_label
            self.summary_layout.addRow(label_text, value_label)

        content_parent: QWidget = self
        if framed:
            self.card = SectionCard(
                title="Display Settings",
                subtitle="Monitor, FPVS timing, and presentation background.",
                object_name=_prefixed_object_name(object_name_prefix, "display_settings_card"),
                parent=self,
            )
            self.card.card_layout.setContentsMargins(12, 10, 12, 10)
            self.card.card_layout.setSpacing(8)
            self.card.body_layout.setSpacing(8)
            content_parent = self.card
        else:
            self.card = None

        target_layout = self.card.body_layout if self.card is not None else QVBoxLayout(self)
        if self.card is None:
            target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.addWidget(self.form_container)
        target_layout.addWidget(self.summary_container)

        if self.card is not None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(content_parent)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def current_refresh_hz(self) -> float:
        refresh_hz = self.refresh_hz_combo.currentData()
        return float(refresh_hz) if isinstance(refresh_hz, (int, float)) else 60.0

    def timing_report(self) -> DisplayValidationReport:
        protocol = self._document.project.settings.protocol
        condition_modes = [
            condition.duty_cycle_mode for condition in self._document.project.conditions
        ]
        if not condition_modes:
            condition_modes = [
                self._document.project.settings.condition_defaults.duty_cycle_mode
            ]
        duty_cycle_mode = (
            DutyCycleMode.BLANK_50
            if DutyCycleMode.BLANK_50 in condition_modes
            else DutyCycleMode.CONTINUOUS
        )
        return validate_display_refresh(
            self.current_refresh_hz(),
            duty_cycle_mode=duty_cycle_mode,
            base_hz=protocol.base_hz,
            oddball_every_n=protocol.oddball_every_n,
        )

    def timing_is_compatible(self) -> bool:
        return self.timing_report().compatible and (
            not self._require_refresh_verification or self.refresh_is_verified()
        )

    def refresh_is_verified(self) -> bool:
        """Return whether the current selection matches this editor's measurement."""

        if self._measured_refresh_hz is None or self._verified_refresh_hz is None:
            return False
        return (
            approved_monitor_refresh_rate(self.current_refresh_hz())
            == self._verified_refresh_hz
            and measured_refresh_matches_configured(
                self.current_refresh_hz(),
                self._measured_refresh_hz,
            )
        )

    def timing_blocker(self) -> str:
        report = self.timing_report()
        if report.errors:
            return report.errors[0]
        if self._refresh_probe_task is not None:
            return "Wait for display refresh detection to finish"
        if self._refresh_measurement_error:
            return self._refresh_measurement_error
        if self._require_refresh_verification and not self.refresh_is_verified():
            return "Detect and verify the connected display refresh rate"
        return "Set compatible FPVS timing"

    def refresh(self) -> None:
        background_color = self._normalized_background_color()
        preferred_refresh = self._document.project.settings.display.preferred_refresh_hz or 60.0
        protocol = self._document.project.settings.protocol
        self._sync_refresh_combo(preferred_refresh)
        with QSignalBlocker(self.base_hz_spin):
            self.base_hz_spin.setValue(protocol.base_hz)
        with QSignalBlocker(self.oddball_every_n_spin):
            self.oddball_every_n_spin.setValue(protocol.oddball_every_n)
        with QSignalBlocker(self.runtime_background_color_combo):
            selected_index = self.runtime_background_color_combo.findData(background_color)
            if selected_index < 0:
                selected_index = self.runtime_background_color_combo.findData("#000000")
            self.runtime_background_color_combo.setCurrentIndex(selected_index)

        controls_enabled = self._editable and self._refresh_probe_task is None
        self.refresh_hz_combo.setEnabled(controls_enabled)
        self.detect_refresh_button.setEnabled(controls_enabled)
        self.detect_refresh_button.setVisible(self._editable)
        self.base_hz_spin.setEnabled(self._editable)
        self.oddball_every_n_spin.setEnabled(self._editable)
        self.runtime_background_color_combo.setEnabled(self._editable)
        self.form_container.setVisible(self._editable)
        self.summary_container.setVisible(not self._editable)
        if not self._editable:
            self.summary_value_labels["refresh"].setText(f"{preferred_refresh:.2f} Hz")
            self.summary_value_labels["base"].setText(f"{protocol.base_hz:g} Hz")
            self.summary_value_labels["oddball"].setText(
                f"Every {protocol.oddball_every_n} stimuli ({protocol.oddball_hz:g} Hz)"
            )
            self.summary_value_labels["background"].setText(
                self.runtime_background_color_combo.currentText()
            )
        self._refresh_timing_status()

    def _refresh_timing_status(self) -> None:
        report = self.timing_report()
        protocol = self._document.project.settings.protocol
        if report.frames_per_cycle is None:
            self.timing_summary_label.setText(
                f"Requested: {protocol.base_hz:g} Hz base, "
                f"{protocol.oddball_hz:g} Hz oddball."
            )
        else:
            frames_per_oddball = report.frames_per_cycle * protocol.oddball_every_n
            duration_text = self._condition_duration_text(report.frames_per_cycle)
            self.timing_summary_label.setText(
                f"{report.frames_per_cycle} frames/stimulus; "
                f"{frames_per_oddball} frames/oddball; "
                f"requested oddball {protocol.oddball_hz:g} Hz; {duration_text}."
            )

        verification_prefix = self._refresh_verification_prefix()
        if self._refresh_probe_task is not None:
            self.timing_status_label.setProperty("statusState", "info")
            self.timing_status_label.setText(
                "Measuring refresh rate with PsychoPy on the default presentation display..."
            )
            self.timing_status_label.setVisible(True)
        elif report.errors:
            self.timing_status_label.setProperty("statusState", "error")
            self.timing_status_label.setText(report.errors[0])
            self.timing_status_label.setVisible(True)
        elif self._refresh_measurement_error:
            self.timing_status_label.setProperty("statusState", "error")
            self.timing_status_label.setText(self._refresh_measurement_error)
            self.timing_status_label.setVisible(True)
        elif self._require_refresh_verification and not self.refresh_is_verified():
            self.timing_status_label.setProperty("statusState", "warning")
            self.timing_status_label.setText(
                "Verification required: detect the connected display refresh rate "
                "before continuing."
            )
            self.timing_status_label.setVisible(True)
        elif report.warnings:
            self.timing_status_label.setProperty("statusState", "warning")
            realized_base = report.realized_base_hz or protocol.base_hz
            realized_oddball = report.realized_oddball_hz or protocol.oddball_hz
            self.timing_status_label.setText(
                f"{verification_prefix}Approximate timing: whole-frame scheduling realizes "
                f"{realized_base:.6g} Hz base and {realized_oddball:.6g} Hz oddball. "
                "Runtime QC reports dropped or late frames separately."
            )
            self.timing_status_label.setVisible(True)
        elif verification_prefix:
            self.timing_status_label.setProperty("statusState", "ready")
            self.timing_status_label.setText(verification_prefix.rstrip())
            self.timing_status_label.setVisible(True)
        else:
            self.timing_status_label.setText("")
            self.timing_status_label.setVisible(False)
        refresh_widget_style(self.timing_status_label)

    def _refresh_verification_prefix(self) -> str:
        if not self.refresh_is_verified() or self._measured_refresh_hz is None:
            return ""
        return (
            f"Verified: measured {self._measured_refresh_hz:.3f} Hz and applied "
            f"{self.current_refresh_hz():g} Hz. "
        )

    def _sync_refresh_combo(self, preferred_refresh: float) -> None:
        with QSignalBlocker(self.refresh_hz_combo):
            unsupported_indices = [
                index
                for index in range(self.refresh_hz_combo.count())
                if approved_monitor_refresh_rate(float(self.refresh_hz_combo.itemData(index)))
                is None
            ]
            for index in reversed(unsupported_indices):
                self.refresh_hz_combo.removeItem(index)
            selected_index = self.refresh_hz_combo.findData(preferred_refresh)
            if selected_index < 0:
                self.refresh_hz_combo.insertItem(
                    0,
                    f"{preferred_refresh:g} Hz (not approved)",
                    userData=preferred_refresh,
                )
                selected_index = 0
            self.refresh_hz_combo.setCurrentIndex(selected_index)

    def _condition_duration_text(self, frames_per_stimulus_value: int) -> str:
        protocol = self._document.project.settings.protocol
        refresh_hz = self.current_refresh_hz()
        conditions = self._document.project.conditions
        if conditions:
            durations = [
                (
                    condition.sequence_count
                    * condition.oddball_cycle_repeats_per_sequence
                    * protocol.oddball_every_n
                    * frames_per_stimulus_value
                    / refresh_hz
                )
                for condition in conditions
            ]
        else:
            defaults = self._document.project.settings.condition_defaults
            durations = [
                (
                    defaults.sequence_count
                    * defaults.oddball_cycle_repeats_per_sequence
                    * protocol.oddball_every_n
                    * frames_per_stimulus_value
                    / refresh_hz
                )
            ]
        minimum = min(durations)
        maximum = max(durations)
        if abs(maximum - minimum) < 1e-9:
            return f"condition {minimum:.1f} s"
        return f"conditions {minimum:.1f}-{maximum:.1f} s"

    def _normalized_background_color(self) -> str:
        background_color = self._document.project.settings.display.background_color
        if isinstance(background_color, str):
            canonical_preset = _canonical_runtime_background_hex(background_color)
            if canonical_preset is not None:
                return canonical_preset

        if self._background_refresh_guard:
            return "#000000"

        self._background_refresh_guard = True
        try:
            self._document.update_display_settings(background_color="#000000")
        finally:
            self._background_refresh_guard = False
        return "#000000"

    def _apply_refresh_hz(self) -> None:
        self._clear_refresh_verification()
        try:
            self._document.update_display_settings(
                preferred_refresh_hz=self.current_refresh_hz()
            )
        except Exception as error:
            _show_error_dialog(self, "Refresh Setting Error", error)
            self.refresh()

    def _clear_refresh_verification(self) -> None:
        self._measured_refresh_hz = None
        self._verified_refresh_hz = None
        self._refresh_measurement_error = None
        self.refresh_verification_changed.emit()

    def _start_refresh_detection(self) -> None:
        if self._refresh_probe_task is not None:
            return
        self._clear_refresh_verification()

        def _measure() -> float:
            engine = create_engine(EngineName.PSYCHOPY)
            return engine.measure_refresh_hz(
                runtime_options={"fullscreen": True, "display_index": None}
            )

        task = ProgressTask(
            parent_widget=self,
            label="Measuring the connected display refresh rate...",
            callback=_measure,
            window_title="Detect Display Refresh Rate",
            persistent_thread=True,
        )
        self._refresh_probe_task = task
        task.succeeded.connect(self._on_refresh_detection_succeeded)
        task.failed.connect(self._on_refresh_detection_failed)
        task.finished.connect(self._on_refresh_detection_finished)
        self.refresh()
        self.refresh_verification_changed.emit()
        task.start()

    def _on_refresh_detection_succeeded(self, result: object) -> None:
        if not isinstance(result, (int, float)):
            self._on_refresh_detection_failed(
                RuntimeError("PsychoPy returned an invalid display refresh measurement.")
            )
            return
        measured_hz = float(result)
        approved_hz = nearest_approved_monitor_refresh_rate(measured_hz)
        if approved_hz is None:
            self._on_refresh_detection_failed(
                RuntimeError(
                    f"Measured {measured_hz:.3f} Hz, which is not near an approved "
                    "monitor refresh rate (59.94, 60, 120, 144, or 240 Hz)."
                )
            )
            return

        self._measured_refresh_hz = measured_hz
        self._verified_refresh_hz = approved_hz
        self._refresh_measurement_error = None
        self._sync_refresh_combo(approved_hz)
        try:
            self._document.update_display_settings(preferred_refresh_hz=approved_hz)
        except Exception as error:
            self._on_refresh_detection_failed(error)
            return
        self._refresh_timing_status()
        self.refresh_verification_changed.emit()

    def _on_refresh_detection_failed(self, error: object) -> None:
        LOGGER.error("Display refresh detection failed: %s", error)
        self._measured_refresh_hz = None
        self._verified_refresh_hz = None
        self._refresh_measurement_error = f"Refresh detection failed: {error}"
        self._refresh_timing_status()
        self.refresh_verification_changed.emit()

    def _on_refresh_detection_finished(self) -> None:
        self._refresh_probe_task = None
        self.refresh()
        self.refresh_verification_changed.emit()

    def _apply_protocol_settings(self) -> None:
        try:
            self._document.update_protocol_settings(
                base_hz=self.base_hz_spin.value(),
                oddball_every_n=self.oddball_every_n_spin.value(),
            )
        except Exception as error:
            _show_error_dialog(self, "FPVS Timing Error", error)
            self.refresh()

    def _apply_runtime_background_color(self) -> None:
        selected_background_color = self.runtime_background_color_combo.currentData()
        if not isinstance(selected_background_color, str):
            return
        try:
            self._document.update_display_settings(background_color=selected_background_color)
        except Exception as error:
            _show_error_dialog(self, "Display Settings Error", error)
            self.refresh()


RuntimeSettingsEditor = DisplaySettingsEditor


class ImageSizePreview(QWidget):
    """Actual-size square preview for configured stimulus visual angle."""

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("image_size_preview")
        self._document = document
        self._preview_width_px = 1
        self._capped = False
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def refresh(self) -> None:
        display = self._document.project.settings.display
        self._preview_width_px = visual_angle_width_px(
            degrees=display.stimulus_width_degrees,
            viewing_distance_cm=display.viewing_distance_cm,
            screen_width_cm=display.screen_width_cm,
            screen_width_px=_display_screen_width_px(display),
        )
        max_preview = max(1, min(self.width(), self.height()) - 18)
        self._capped = self._preview_width_px > max_preview
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#101010"))
        painter.setPen(QPen(QColor("#6b7280"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        available = max(1, min(self.width(), self.height()) - 18)
        square_size = min(self._preview_width_px, available)
        left = (self.width() - square_size) // 2
        top = (self.height() - square_size) // 2
        painter.fillRect(left, top, square_size, square_size, QColor("#f8fafc"))
        painter.setPen(QPen(QColor("#2563eb"), 2))
        painter.drawRect(left, top, square_size, square_size)


class ImageSizePreviewDialog(QDialog):
    """Full-screen actual-size stimulus preview."""

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("image_size_preview_dialog")
        self._document = document
        self.setWindowTitle("Image Size Preview")
        self.setModal(True)
        apply_image_size_preview_dialog_theme(self)

        self.preview = ImageSizePreview(document, self)
        self.preview.setObjectName("image_size_full_screen_preview")
        self.preview_value_label = QLabel(self)
        self.preview_value_label.setObjectName("image_size_preview_value_label")
        self.preview_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_value_label.setWordWrap(True)

        self.width_degrees_spin = _image_size_spin_box(
            parent=self,
            object_name="preview_stimulus_width_degrees_spin",
            minimum=0.1,
            maximum=90.0,
            decimals=1,
            step=0.5,
            suffix=" deg",
        )
        self.viewing_distance_spin = _image_size_spin_box(
            parent=self,
            object_name="preview_viewing_distance_cm_spin",
            minimum=1.0,
            maximum=500.0,
            decimals=1,
            step=5.0,
            suffix=" cm",
        )
        self.screen_width_spin = _image_size_spin_box(
            parent=self,
            object_name="preview_screen_width_cm_spin",
            minimum=1.0,
            maximum=500.0,
            decimals=2,
            step=0.25,
            suffix=" cm",
        )
        self.use_current_resolution_checkbox = QCheckBox(
            "Use current primary screen resolution",
            self,
        )
        self.use_current_resolution_checkbox.setObjectName(
            "preview_use_current_screen_resolution_checkbox"
        )
        self.screen_width_px_spin = _resolution_spin_box(
            parent=self,
            object_name="preview_screen_width_px_spin",
        )
        self.screen_height_px_spin = _resolution_spin_box(
            parent=self,
            object_name="preview_screen_height_px_spin",
        )
        self.width_degrees_spin.valueChanged.connect(self._apply_image_display_settings)
        self.viewing_distance_spin.valueChanged.connect(self._apply_image_display_settings)
        self.screen_width_spin.valueChanged.connect(self._apply_image_display_settings)
        self.use_current_resolution_checkbox.toggled.connect(
            self._apply_image_display_settings
        )
        self.screen_width_px_spin.valueChanged.connect(self._apply_image_display_settings)
        self.screen_height_px_spin.valueChanged.connect(self._apply_image_display_settings)

        self.exit_button = QPushButton("Exit Preview", self)
        self.exit_button.setObjectName("image_size_preview_exit_button")
        self.exit_button.clicked.connect(self.accept)
        mark_secondary_action(self.exit_button)

        control_panel = QWidget(self)
        control_panel.setObjectName("image_size_preview_control_panel")
        control_panel.setFixedWidth(300)
        control_panel_layout = QVBoxLayout(control_panel)
        control_panel_layout.setContentsMargins(18, 18, 18, 18)
        control_panel_layout.setSpacing(12)
        title_label = QLabel("Image Size", control_panel)
        title_label.setProperty("sectionCardRole", "title")
        control_panel_layout.addWidget(title_label)
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(10)
        form_layout.addRow("Image width (deg)", self.width_degrees_spin)
        form_layout.addRow("Viewing distance (cm)", self.viewing_distance_spin)
        form_layout.addRow("Screen width (cm)", self.screen_width_spin)
        form_layout.addRow("Resolution width (px)", self.screen_width_px_spin)
        form_layout.addRow("Resolution height (px)", self.screen_height_px_spin)
        control_panel_layout.addLayout(form_layout)

        checkbox_row = QHBoxLayout()
        checkbox_row.setContentsMargins(0, 0, 0, 0)
        checkbox_row.addWidget(self.use_current_resolution_checkbox)
        checkbox_row.addStretch(1)
        control_panel_layout.addLayout(checkbox_row)

        control_panel_layout.addWidget(self.exit_button)
        control_panel_layout.addStretch(1)

        preview_panel = QWidget(self)
        preview_panel_layout = QVBoxLayout(preview_panel)
        preview_panel_layout.setContentsMargins(0, 0, 0, 0)
        preview_panel_layout.setSpacing(16)
        preview_panel_layout.addWidget(self.preview, 1)
        preview_panel_layout.addWidget(self.preview_value_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(0)
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(18)
        row_layout.addWidget(control_panel)
        row_layout.addWidget(preview_panel, 1)
        layout.addLayout(row_layout)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self.preview.refresh()

    def refresh(self) -> None:
        display = self._document.project.settings.display
        with QSignalBlocker(self.width_degrees_spin):
            self.width_degrees_spin.setValue(display.stimulus_width_degrees)
        with QSignalBlocker(self.viewing_distance_spin):
            self.viewing_distance_spin.setValue(display.viewing_distance_cm)
        with QSignalBlocker(self.screen_width_spin):
            self.screen_width_spin.setValue(display.screen_width_cm)
        with QSignalBlocker(self.use_current_resolution_checkbox):
            self.use_current_resolution_checkbox.setChecked(
                display.use_current_screen_resolution
            )
        with QSignalBlocker(self.screen_width_px_spin):
            self.screen_width_px_spin.setValue(display.screen_width_px)
        with QSignalBlocker(self.screen_height_px_spin):
            self.screen_height_px_spin.setValue(display.screen_height_px)
        self.screen_width_px_spin.setEnabled(not display.use_current_screen_resolution)
        self.screen_height_px_spin.setEnabled(not display.use_current_screen_resolution)
        physical_width_cm = visual_angle_width_cm(
            degrees=display.stimulus_width_degrees,
            viewing_distance_cm=display.viewing_distance_cm,
        )
        screen_width_px = _display_screen_width_px(display)
        preview_width_px = visual_angle_width_px(
            degrees=display.stimulus_width_degrees,
            viewing_distance_cm=display.viewing_distance_cm,
            screen_width_cm=display.screen_width_cm,
            screen_width_px=screen_width_px,
        )
        self.preview_value_label.setText(
            f"{display.stimulus_width_degrees:.1f} deg at "
            f"{display.viewing_distance_cm:.1f} cm = "
            f"{physical_width_cm:.1f} cm wide, about {preview_width_px} px "
            f"on a {screen_width_px} px-wide display"
        )
        self.preview.refresh()

    def _apply_image_display_settings(self) -> None:
        try:
            self._document.update_display_settings(
                stimulus_width_degrees=self.width_degrees_spin.value(),
                viewing_distance_cm=self.viewing_distance_spin.value(),
                screen_width_cm=self.screen_width_spin.value(),
                screen_width_px=self.screen_width_px_spin.value(),
                screen_height_px=self.screen_height_px_spin.value(),
                use_current_screen_resolution=self.use_current_resolution_checkbox.isChecked(),
            )
        except Exception as error:
            _show_error_dialog(self, "Image Size Error", error)
            self.refresh()


class ImageDisplaySizeEditor(QWidget):
    """Project-wide stimulus display-size controls and preview."""

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("image_display_size_editor")
        self._document = document

        self.width_degrees_spin = _image_size_spin_box(
            parent=self,
            object_name="stimulus_width_degrees_spin",
            minimum=0.1,
            maximum=90.0,
            decimals=1,
            step=0.5,
            suffix=" deg",
        )
        self.width_degrees_spin.valueChanged.connect(self._apply_image_display_settings)

        self.viewing_distance_spin = _image_size_spin_box(
            parent=self,
            object_name="viewing_distance_cm_spin",
            minimum=1.0,
            maximum=500.0,
            decimals=1,
            step=5.0,
            suffix=" cm",
        )
        self.viewing_distance_spin.valueChanged.connect(self._apply_image_display_settings)

        self.screen_width_spin = _image_size_spin_box(
            parent=self,
            object_name="screen_width_cm_spin",
            minimum=1.0,
            maximum=500.0,
            decimals=2,
            step=0.25,
            suffix=" cm",
        )
        self.screen_width_spin.valueChanged.connect(self._apply_image_display_settings)
        self.use_current_resolution_checkbox = QCheckBox(
            "Use current primary screen resolution",
            self,
        )
        self.use_current_resolution_checkbox.setObjectName(
            "use_current_screen_resolution_checkbox"
        )
        self.screen_width_px_spin = _resolution_spin_box(
            parent=self,
            object_name="screen_width_px_spin",
        )
        self.screen_height_px_spin = _resolution_spin_box(
            parent=self,
            object_name="screen_height_px_spin",
        )
        self.use_current_resolution_checkbox.toggled.connect(
            self._apply_image_display_settings
        )
        self.screen_width_px_spin.valueChanged.connect(self._apply_image_display_settings)
        self.screen_height_px_spin.valueChanged.connect(self._apply_image_display_settings)

        self.preview_value_label = QLabel(self)
        self.preview_value_label.setObjectName("image_size_preview_value_label")
        self.preview_value_label.setWordWrap(True)
        self.preview_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.full_screen_preview_button = QPushButton("Full Screen Preview", self)
        self.full_screen_preview_button.setObjectName("image_size_full_screen_preview_button")
        self.full_screen_preview_button.clicked.connect(self._show_full_screen_preview)
        mark_secondary_action(self.full_screen_preview_button)

        self.form_layout = QFormLayout()
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setHorizontalSpacing(12)
        self.form_layout.setVerticalSpacing(8)
        self.form_layout.addRow("Image width (deg)", self.width_degrees_spin)
        self.form_layout.addRow("Viewing distance (cm)", self.viewing_distance_spin)
        self.form_layout.addRow("Screen width (cm)", self.screen_width_spin)
        self.form_layout.addRow("Resolution width (px)", self.screen_width_px_spin)
        self.form_layout.addRow("Resolution height (px)", self.screen_height_px_spin)

        checkbox_row = QHBoxLayout()
        checkbox_row.setContentsMargins(0, 0, 0, 0)
        checkbox_row.addWidget(self.use_current_resolution_checkbox)
        checkbox_row.addStretch(1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.addStretch(1)
        button_row.addWidget(self.full_screen_preview_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(self.form_layout)
        layout.addLayout(checkbox_row)
        layout.addWidget(self.preview_value_label)
        layout.addLayout(button_row)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        display = self._document.project.settings.display
        with QSignalBlocker(self.width_degrees_spin):
            self.width_degrees_spin.setValue(display.stimulus_width_degrees)
        with QSignalBlocker(self.viewing_distance_spin):
            self.viewing_distance_spin.setValue(display.viewing_distance_cm)
        with QSignalBlocker(self.screen_width_spin):
            self.screen_width_spin.setValue(display.screen_width_cm)
        with QSignalBlocker(self.use_current_resolution_checkbox):
            self.use_current_resolution_checkbox.setChecked(
                display.use_current_screen_resolution
            )
        with QSignalBlocker(self.screen_width_px_spin):
            self.screen_width_px_spin.setValue(display.screen_width_px)
        with QSignalBlocker(self.screen_height_px_spin):
            self.screen_height_px_spin.setValue(display.screen_height_px)
        self.screen_width_px_spin.setEnabled(not display.use_current_screen_resolution)
        self.screen_height_px_spin.setEnabled(not display.use_current_screen_resolution)

        physical_width_cm = visual_angle_width_cm(
            degrees=display.stimulus_width_degrees,
            viewing_distance_cm=display.viewing_distance_cm,
        )
        screen_width_px = _display_screen_width_px(display)
        preview_width_px = visual_angle_width_px(
            degrees=display.stimulus_width_degrees,
            viewing_distance_cm=display.viewing_distance_cm,
            screen_width_cm=display.screen_width_cm,
            screen_width_px=screen_width_px,
        )
        self.preview_value_label.setText(
            f"{physical_width_cm:.1f} cm wide, about {preview_width_px} px "
            f"on a {screen_width_px} px-wide display"
        )

    def _apply_image_display_settings(self) -> None:
        try:
            self._document.update_display_settings(
                stimulus_width_degrees=self.width_degrees_spin.value(),
                viewing_distance_cm=self.viewing_distance_spin.value(),
                screen_width_cm=self.screen_width_spin.value(),
                screen_width_px=self.screen_width_px_spin.value(),
                screen_height_px=self.screen_height_px_spin.value(),
                use_current_screen_resolution=self.use_current_resolution_checkbox.isChecked(),
            )
        except Exception as error:
            _show_error_dialog(self, "Image Size Error", error)
            self.refresh()

    def _show_full_screen_preview(self) -> None:
        dialog = ImageSizePreviewDialog(self._document, self)
        screen = QApplication.primaryScreen()
        if screen is not None:
            dialog.setGeometry(screen.geometry())
        dialog.setWindowState(dialog.windowState() | Qt.WindowState.WindowFullScreen)
        dialog.exec()


def _primary_screen_width_px() -> int:
    screen = QApplication.primaryScreen()
    if screen is None:
        return 1920
    return max(1, screen.geometry().width())


def _display_screen_width_px(display: object) -> int:
    if bool(getattr(display, "use_current_screen_resolution", False)):
        return _primary_screen_width_px()
    return max(1, int(getattr(display, "screen_width_px", 1920)))


def _image_size_spin_box(
    *,
    parent: QWidget,
    object_name: str,
    minimum: float,
    maximum: float,
    decimals: int,
    step: float,
    suffix: str,
) -> QDoubleSpinBox:
    spin_box = QDoubleSpinBox(parent)
    spin_box.setObjectName(object_name)
    spin_box.setRange(minimum, maximum)
    spin_box.setDecimals(decimals)
    spin_box.setSingleStep(step)
    spin_box.setSuffix(suffix)
    return spin_box


def _resolution_spin_box(*, parent: QWidget, object_name: str) -> QSpinBox:
    spin_box = QSpinBox(parent)
    spin_box.setObjectName(object_name)
    spin_box.setRange(1, 20000)
    spin_box.setSingleStep(10)
    spin_box.setSuffix(" px")
    return spin_box
