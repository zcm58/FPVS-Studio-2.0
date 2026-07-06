"""Display localization dialog shown after importing a project bundle."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.models import DisplaySettings
from fpvs_studio.gui.components import mark_secondary_action


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
        self.setWindowTitle("Confirm Imported Display Settings")
        self.setModal(True)

        self.intro_label = QLabel(
            "Confirm this computer's display details before opening the imported project.",
            self,
        )
        self.intro_label.setWordWrap(True)

        self.image_width_label = QLabel(
            f"Imported image width: {display.stimulus_width_degrees:.1f} deg",
            self,
        )
        self.image_width_label.setObjectName("import_display_image_width_label")
        self.image_width_label.setWordWrap(True)

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

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(8)
        form_layout.addRow("Refresh rate", self.refresh_hz_spin)
        form_layout.addRow("Viewing distance", self.viewing_distance_spin)
        form_layout.addRow("Screen width", self.screen_width_cm_spin)
        form_layout.addRow("Resolution width", self.screen_width_px_spin)
        form_layout.addRow("Resolution height", self.screen_height_px_spin)

        detect_row = QHBoxLayout()
        detect_row.setContentsMargins(0, 0, 0, 0)
        detect_row.addWidget(self.detect_button)
        detect_row.addStretch(1)

        self.button_box = QDialogButtonBox(self)
        self.apply_button = self.button_box.addButton(
            "Apply and Open",
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        self.keep_button = self.button_box.addButton(
            "Keep Imported Settings",
            QDialogButtonBox.ButtonRole.RejectRole,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(self.intro_label)
        layout.addWidget(self.image_width_label)
        layout.addLayout(form_layout)
        layout.addLayout(detect_row)
        layout.addWidget(self.button_box)

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
        if detected.screen_width_cm is not None:
            self.screen_width_cm_spin.setValue(detected.screen_width_cm)
        if detected.screen_width_px is not None:
            self.screen_width_px_spin.setValue(detected.screen_width_px)
        if detected.screen_height_px is not None:
            self.screen_height_px_spin.setValue(detected.screen_height_px)


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
