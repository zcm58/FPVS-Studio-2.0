"""Display localization dialog shown after importing a project bundle."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.models import DisplaySettings
from fpvs_studio.core.validation import nearest_approved_monitor_refresh_rate
from fpvs_studio.gui.components import (
    StatusBadgeLabel,
    apply_studio_theme,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.components import (
    create_double_spin_box as _display_double_spin_box,
)
from fpvs_studio.gui.components import (
    create_resolution_spin_box as _display_resolution_spin_box,
)


@dataclass(frozen=True)
class DetectedDisplaySettings:
    """Best-effort refresh rate and pixel dimensions of Qt's primary screen."""

    refresh_hz: float | None = None
    screen_width_px: int | None = None
    screen_height_px: int | None = None


class ImportDisplaySettingsDialog(QDialog):
    """Ask users to localize display settings for an imported project."""

    def __init__(self, display: DisplaySettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("import_display_settings_dialog")
        self.setWindowTitle("Match Project Display — FPVS Studio")
        self.setModal(True)
        self.setMinimumSize(720, 640)
        self.resize(780, 660)
        self._apply_updates = False

        self.title_label = QLabel("Match this project's display", self)
        self.title_label.setObjectName("import_display_title")
        self.title_label.setProperty("importDisplayRole", "title")

        self.intro_label = QLabel(
            (
                "Confirm this computer's display details to preserve the project's "
                f"{display.stimulus_width_degrees:.1f}° image width."
            ),
            self,
        )
        self.intro_label.setProperty("importDisplayRole", "lead")
        self.intro_label.setWordWrap(True)

        imported_refresh = display.preferred_refresh_hz or 60.0
        comparison_layout = QGridLayout()
        comparison_layout.setHorizontalSpacing(20)
        comparison_layout.setVerticalSpacing(10)
        imported_header = QLabel("Imported settings", self)
        imported_header.setProperty("importDisplayRole", "columnHeader")
        detected_header = QLabel("Detected on this computer", self)
        detected_header.setProperty("importDisplayRole", "columnHeader")
        self.detected_badge = StatusBadgeLabel(parent=self)
        self.detected_badge.setObjectName("import_display_detected_badge")
        self.detected_badge.set_state("info", "Not detected")
        comparison_layout.addWidget(imported_header, 0, 1)
        comparison_layout.addWidget(detected_header, 0, 2)
        comparison_layout.addWidget(self.detected_badge, 0, 3)

        imported_values = (
            ("Refresh rate", f"{imported_refresh:.2f} Hz"),
            ("Resolution", f"{display.screen_width_px} × {display.screen_height_px} px"),
        )
        self.detected_refresh_label = QLabel("—", self)
        self.detected_refresh_label.setWordWrap(True)
        self.detected_resolution_label = QLabel("—", self)
        detected_labels = (
            self.detected_refresh_label,
            self.detected_resolution_label,
        )
        for row, ((label_text, imported_text), detected_label) in enumerate(
            zip(imported_values, detected_labels, strict=True),
            start=1,
        ):
            row_label = QLabel(label_text, self)
            row_label.setProperty("importDisplayRole", "columnHeader")
            imported_label = QLabel(imported_text, self)
            imported_label.setProperty("importDisplayRole", "lead")
            detected_label.setProperty("importDisplayRole", "lead")
            comparison_layout.addWidget(row_label, row, 0)
            comparison_layout.addWidget(imported_label, row, 1)
            comparison_layout.addWidget(detected_label, row, 2, 1, 2)
        comparison_layout.setColumnStretch(1, 1)
        comparison_layout.setColumnStretch(2, 1)

        self.refresh_hz_spin = _display_double_spin_box(
            parent=self,
            object_name="import_display_refresh_hz_spin",
            minimum=1.0,
            maximum=500.0,
            decimals=2,
            step=1.0,
            suffix=" Hz",
        )
        self.refresh_hz_spin.setValue(display.preferred_refresh_hz or 60.0)

        self.viewing_distance_spin = _display_double_spin_box(
            parent=self,
            object_name="import_display_viewing_distance_cm_spin",
            minimum=1.0,
            maximum=500.0,
            decimals=1,
            step=5.0,
            suffix=" cm",
        )
        self.viewing_distance_spin.setValue(display.viewing_distance_cm)

        self.screen_width_cm_spin = _display_double_spin_box(
            parent=self,
            object_name="import_display_screen_width_cm_spin",
            minimum=1.0,
            maximum=500.0,
            decimals=2,
            step=0.25,
            suffix=" cm",
        )
        self.screen_width_cm_spin.setValue(display.screen_width_cm)

        self.screen_width_px_spin = _display_resolution_spin_box(
            parent=self,
            object_name="import_display_screen_width_px_spin",
        )
        self.screen_width_px_spin.setValue(display.screen_width_px)

        self.screen_height_px_spin = _display_resolution_spin_box(
            parent=self,
            object_name="import_display_screen_height_px_spin",
        )
        self.screen_height_px_spin.setValue(display.screen_height_px)

        self.detect_button = QPushButton("Detect Primary Display", self)
        self.detect_button.setObjectName("import_display_detect_button")
        self.detect_button.setToolTip("Detect the primary display's refresh rate and resolution.")
        self.detect_button.clicked.connect(self.apply_detected_primary_display)
        mark_secondary_action(self.detect_button)

        comparison_layout.addWidget(self.detect_button, 3, 2, 1, 2, Qt.AlignmentFlag.AlignRight)

        values_layout = QGridLayout()
        values_layout.setHorizontalSpacing(12)
        values_layout.setVerticalSpacing(8)
        values_heading = QLabel("Values to apply", self)
        values_heading.setProperty("bundleWorkflowRole", "sectionTitle")
        values_layout.addWidget(values_heading, 0, 0, 1, 4)
        values_layout.addWidget(QLabel("Refresh rate", self), 1, 0)
        values_layout.addWidget(self.refresh_hz_spin, 1, 1)
        values_layout.addWidget(QLabel("Viewing distance", self), 1, 2)
        values_layout.addWidget(self.viewing_distance_spin, 1, 3)
        values_layout.addWidget(QLabel("Screen width", self), 2, 0)
        values_layout.addWidget(self.screen_width_cm_spin, 2, 1)
        values_layout.addWidget(QLabel("Resolution", self), 2, 2)
        resolution_row = QHBoxLayout()
        resolution_row.setContentsMargins(0, 0, 0, 0)
        resolution_row.setSpacing(6)
        resolution_row.addWidget(self.screen_width_px_spin)
        resolution_separator = QLabel("×", self)
        resolution_separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        resolution_row.addWidget(resolution_separator)
        resolution_row.addWidget(self.screen_height_px_spin)
        values_layout.addLayout(resolution_row, 2, 3)
        helper = QLabel(
            "Measure the width across the lit screen and the viewing distance "
            "from the participant's eyes to the screen.",
            self,
        )
        helper.setProperty("importDisplayRole", "helper")
        helper.setWordWrap(True)
        values_layout.addWidget(helper, 3, 0, 1, 4)

        self.keep_button = QPushButton("Open with Imported Values", self)
        self.keep_button.setObjectName("import_display_keep_button")
        mark_secondary_action(self.keep_button)
        self.keep_button.clicked.connect(self._accept_imported_settings)
        self.apply_button = QPushButton("Apply && Open Project", self)
        self.apply_button.setObjectName("import_display_apply_button")
        mark_primary_action(self.apply_button)
        self.apply_button.clicked.connect(self._accept_display_updates)
        self.apply_button.setDefault(True)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 2, 0, 0)
        button_row.setSpacing(10)
        button_row.addStretch(1)
        button_row.addWidget(self.keep_button)
        button_row.addWidget(self.apply_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(10)
        layout.addWidget(self.title_label)
        layout.addWidget(self.intro_label)
        layout.addSpacing(10)
        layout.addLayout(comparison_layout)
        layout.addSpacing(10)
        layout.addLayout(values_layout)
        layout.addStretch(1)
        layout.addLayout(button_row)
        apply_studio_theme(self)

    @property
    def should_apply_updates(self) -> bool:
        return self._apply_updates

    def _accept_imported_settings(self) -> None:
        self._apply_updates = False
        self.accept()

    def _accept_display_updates(self) -> None:
        self._apply_updates = True
        self.accept()

    def display_updates(self) -> dict[str, object]:
        """Return display updates selected by the user."""

        return {
            "preferred_refresh_hz": self.refresh_hz_spin.value(),
            "viewing_distance_cm": self.viewing_distance_spin.value(),
            "screen_width_cm": self.screen_width_cm_spin.value(),
            "screen_width_px": self.screen_width_px_spin.value(),
            "screen_height_px": self.screen_height_px_spin.value(),
            "use_current_screen_resolution": False,
        }

    def apply_detected_primary_display(self) -> None:
        """Fill refresh rate and pixel dimensions from Qt's primary screen metadata."""

        detected = detect_primary_display_settings()
        refresh_supported = True
        if detected.refresh_hz is not None:
            approved_refresh_hz = nearest_approved_monitor_refresh_rate(
                detected.refresh_hz
            )
            if approved_refresh_hz is None:
                refresh_supported = False
                self.detected_refresh_label.setText(
                    f"{detected.refresh_hz:.2f} Hz (not an approved FPVS rate)"
                )
            else:
                self.refresh_hz_spin.setValue(approved_refresh_hz)
                self.detected_refresh_label.setText(
                    f"{detected.refresh_hz:.2f} Hz (use {approved_refresh_hz:g} Hz)"
                )
        else:
            self.detected_refresh_label.setText("Unavailable")
        if detected.screen_width_px is not None:
            self.screen_width_px_spin.setValue(detected.screen_width_px)
        if detected.screen_height_px is not None:
            self.screen_height_px_spin.setValue(detected.screen_height_px)
        if detected.screen_width_px is not None and detected.screen_height_px is not None:
            self.detected_resolution_label.setText(
                f"{detected.screen_width_px} × {detected.screen_height_px} px"
            )
        else:
            self.detected_resolution_label.setText("Unavailable")
        if refresh_supported:
            self.detected_badge.set_state("ready", "Detected")
        else:
            self.detected_badge.set_state("warning", "Review refresh")


def detect_primary_display_settings() -> DetectedDisplaySettings:
    """Read the current refresh rate and pixel dimensions without importing PsychoPy."""

    screen = QApplication.primaryScreen()
    if screen is None:
        return DetectedDisplaySettings()

    geometry = screen.geometry()
    pixel_ratio = screen.devicePixelRatio()

    refresh_hz = screen.refreshRate()
    return DetectedDisplaySettings(
        refresh_hz=refresh_hz if refresh_hz > 0 else None,
        screen_width_px=max(1, round(geometry.width() * pixel_ratio)),
        screen_height_px=max(1, round(geometry.height() * pixel_ratio)),
    )
