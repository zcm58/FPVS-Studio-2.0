"""Display localization dialog shown after importing a project bundle."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.models import DisplaySettings
from fpvs_studio.gui.components import (
    StatusBadgeLabel,
    apply_studio_theme,
    mark_primary_action,
    mark_secondary_action,
)


@dataclass(frozen=True)
class DetectedDisplaySettings:
    """Best-effort display values from Qt's primary screen."""

    refresh_hz: float | None = None
    screen_width_cm: float | None = None
    screen_width_px: int | None = None
    screen_height_px: int | None = None


class ImportDisplaySettingsDialog(QDialog):
    """Ask users to localize display settings for an imported project."""

    def __init__(self, display: DisplaySettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("import_display_settings_dialog")
        self.setWindowTitle("Match Project Display — FPVS Studio")
        self.setModal(True)
        self.setMinimumSize(720, 590)
        self.resize(780, 660)
        self._apply_updates = False

        self.eyebrow_label = QLabel("DISPLAY SETUP", self)
        self.eyebrow_label.setObjectName("import_display_eyebrow")
        self.eyebrow_label.setProperty("importDisplayRole", "eyebrow")

        self.title_label = QLabel("Match this project's display", self)
        self.title_label.setObjectName("import_display_title")
        self.title_label.setProperty("importDisplayRole", "title")

        self.intro_label = QLabel(
            (
                f"The imported project targets a {display.stimulus_width_degrees:.1f}° image "
                "width. Confirm this computer's physical display details before opening it."
            ),
            self,
        )
        self.intro_label.setProperty("importDisplayRole", "lead")
        self.intro_label.setWordWrap(True)

        self.image_width_label = QLabel(
            f"Visual-angle target: {display.stimulus_width_degrees:.1f}°",
            self,
        )
        self.image_width_label.setObjectName("import_display_image_width_label")
        self.image_width_label.setProperty("bundleWorkflowRole", "meta")

        imported_refresh = display.preferred_refresh_hz or 60.0
        comparison_card = QFrame(self)
        comparison_card.setObjectName("import_display_comparison_card")
        comparison_card.setProperty("bundleWorkflowCard", "true")
        comparison_layout = QGridLayout(comparison_card)
        comparison_layout.setContentsMargins(16, 14, 16, 14)
        comparison_layout.setHorizontalSpacing(20)
        comparison_layout.setVerticalSpacing(10)
        imported_header = QLabel("Imported settings", comparison_card)
        imported_header.setProperty("importDisplayRole", "columnHeader")
        detected_header = QLabel("Detected on this computer", comparison_card)
        detected_header.setProperty("importDisplayRole", "columnHeader")
        self.detected_badge = StatusBadgeLabel(parent=comparison_card)
        self.detected_badge.setObjectName("import_display_detected_badge")
        self.detected_badge.set_state("info", "Not detected")
        comparison_layout.addWidget(imported_header, 0, 1)
        comparison_layout.addWidget(detected_header, 0, 2)
        comparison_layout.addWidget(self.detected_badge, 0, 3)

        imported_values = (
            ("Refresh rate", f"{imported_refresh:.2f} Hz"),
            ("Resolution", f"{display.screen_width_px} × {display.screen_height_px} px"),
            ("Screen width", f"{display.screen_width_cm:.2f} cm"),
        )
        self.detected_refresh_label = QLabel("—", comparison_card)
        self.detected_resolution_label = QLabel("—", comparison_card)
        self.detected_width_label = QLabel("—", comparison_card)
        detected_labels = (
            self.detected_refresh_label,
            self.detected_resolution_label,
            self.detected_width_label,
        )
        for row, ((label_text, imported_text), detected_label) in enumerate(
            zip(imported_values, detected_labels, strict=True),
            start=1,
        ):
            row_label = QLabel(label_text, comparison_card)
            row_label.setProperty("importDisplayRole", "columnHeader")
            imported_label = QLabel(imported_text, comparison_card)
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
        self.detect_button.clicked.connect(self.apply_detected_primary_display)
        mark_secondary_action(self.detect_button)

        comparison_layout.addWidget(self.detect_button, 4, 2, 1, 2, Qt.AlignmentFlag.AlignRight)

        values_card = QFrame(self)
        values_card.setObjectName("import_display_values_card")
        values_card.setProperty("bundleWorkflowCard", "true")
        values_layout = QGridLayout(values_card)
        values_layout.setContentsMargins(16, 12, 16, 12)
        values_layout.setHorizontalSpacing(12)
        values_layout.setVerticalSpacing(8)
        values_heading = QLabel("Values to apply", values_card)
        values_heading.setProperty("bundleWorkflowRole", "sectionTitle")
        values_layout.addWidget(values_heading, 0, 0, 1, 4)
        values_layout.addWidget(QLabel("Refresh rate", values_card), 1, 0)
        values_layout.addWidget(self.refresh_hz_spin, 1, 1)
        values_layout.addWidget(QLabel("Viewing distance", values_card), 1, 2)
        values_layout.addWidget(self.viewing_distance_spin, 1, 3)
        values_layout.addWidget(QLabel("Screen width", values_card), 2, 0)
        values_layout.addWidget(self.screen_width_cm_spin, 2, 1)
        values_layout.addWidget(QLabel("Resolution", values_card), 2, 2)
        resolution_row = QHBoxLayout()
        resolution_row.setContentsMargins(0, 0, 0, 0)
        resolution_row.setSpacing(6)
        resolution_row.addWidget(self.screen_width_px_spin)
        resolution_separator = QLabel("×", values_card)
        resolution_separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        resolution_row.addWidget(resolution_separator)
        resolution_row.addWidget(self.screen_height_px_spin)
        values_layout.addLayout(resolution_row, 2, 3)
        helper = QLabel(
            "Measure viewing distance from the participant's eyes to the screen.",
            values_card,
        )
        helper.setProperty("importDisplayRole", "helper")
        helper.setWordWrap(True)
        values_layout.addWidget(helper, 3, 0, 1, 4)

        info_label = QLabel(
            (
                f"Applying local display values preserves the "
                f"{display.stimulus_width_degrees:.1f}° visual-angle target. "
                "Stimulus files and protocol settings are unchanged."
            ),
            self,
        )
        info_label.setObjectName("import_display_info")
        info_label.setProperty("importDisplayRole", "info")
        info_label.setWordWrap(True)

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
        layout.addWidget(self.eyebrow_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.intro_label)
        layout.addWidget(self.image_width_label)
        layout.addWidget(comparison_card)
        layout.addWidget(values_card)
        layout.addWidget(info_label)
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
        """Fill available fields from Qt's primary screen metadata."""

        detected = detect_primary_display_settings()
        if detected.refresh_hz is not None:
            self.refresh_hz_spin.setValue(detected.refresh_hz)
            self.detected_refresh_label.setText(f"{detected.refresh_hz:.2f} Hz")
        else:
            self.detected_refresh_label.setText("Unavailable")
        if detected.screen_width_cm is not None:
            self.screen_width_cm_spin.setValue(detected.screen_width_cm)
            self.detected_width_label.setText(f"{detected.screen_width_cm:.2f} cm")
        else:
            self.detected_width_label.setText("Unavailable")
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
        self.detected_badge.set_state("ready", "Detected")


def detect_primary_display_settings() -> DetectedDisplaySettings:
    """Return best-effort current display values without importing PsychoPy."""

    screen = QApplication.primaryScreen()
    if screen is None:
        return DetectedDisplaySettings()

    geometry = screen.geometry()
    physical_size = screen.physicalSize()
    screen_width_cm = None
    if physical_size.width() > 0:
        screen_width_cm = physical_size.width() / 10.0

    refresh_hz = screen.refreshRate()
    return DetectedDisplaySettings(
        refresh_hz=refresh_hz if refresh_hz > 0 else None,
        screen_width_cm=screen_width_cm,
        screen_width_px=max(1, geometry.width()),
        screen_height_px=max(1, geometry.height()),
    )


def _display_double_spin_box(
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


def _display_resolution_spin_box(*, parent: QWidget, object_name: str) -> QSpinBox:
    spin_box = QSpinBox(parent)
    spin_box.setObjectName(object_name)
    spin_box.setRange(1, 20000)
    spin_box.setSingleStep(10)
    spin_box.setSuffix(" px")
    return spin_box
