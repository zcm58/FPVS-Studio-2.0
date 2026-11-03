"""Launch-only Mac calibration; authored lab settings remain in ProjectFile."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.models import DisplaySettings
from fpvs_studio.core.validation import nearest_approved_monitor_refresh_rate
from fpvs_studio.gui.components import (
    DialogHeader,
    apply_dialog_theme,
    create_double_spin_box,
    mark_primary_action,
)
from fpvs_studio.gui.import_display_settings_dialog import detect_primary_display_settings
from fpvs_studio.runtime.display_mode import NativeDisplayMode


class LocalTestDisplayDialog(QDialog):
    """Confirm physical calibration for one local fullscreen test."""

    def __init__(
        self, display: DisplaySettings, mode: NativeDisplayMode,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Local test display")
        self.setObjectName("local_test_display_dialog")
        self.setMinimumSize(520, 360)
        self.resize(600, 380)
        self._display = display.model_copy(deep=True)
        self._mode = mode
        refresh_hz = nearest_approved_monitor_refresh_rate(mode.hz)
        if refresh_hz is None or not mode.pixel_width or not mode.pixel_height:
            raise ValueError(
                "Select a fixed supported display rate (59.94, 60, 120, 144 or 240 Hz) "
                "in macOS System Settings > Displays, then retry."
            )
        self.refresh_hz = refresh_hz
        detected = detect_primary_display_settings()
        self.screen_width_spin = create_double_spin_box(
            parent=self, object_name="local_test_screen_width", minimum=1, maximum=500,
            decimals=2, step=0.25, suffix=" cm",
        )
        self.screen_width_spin.setValue(detected.screen_width_cm or display.screen_width_cm)
        self.distance_spin = create_double_spin_box(
            parent=self, object_name="local_test_viewing_distance", minimum=1, maximum=500,
            decimals=1, step=5, suffix=" cm",
        )
        self.distance_spin.setValue(display.viewing_distance_cm)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(DialogHeader(
            "Local test display",
            "These values apply to this test. Your project's lab display settings stay saved.",
            parent=self,
        ))
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        self.mode_label = QLabel(
            f"{self.refresh_hz:g} Hz · {mode.pixel_width} × {mode.pixel_height} px", self,
        )
        self.mode_label.setWordWrap(True)
        form.addRow("Current display", self.mode_label)
        form.addRow("Physical screen width", self.screen_width_spin)
        form.addRow("Viewing distance", self.distance_spin)
        layout.addLayout(form)
        layout.addStretch(1)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok, self,
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Use for this test")
        mark_primary_action(self.buttons.button(QDialogButtonBox.StandardButton.Ok))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        apply_dialog_theme(self)

    def local_display(self) -> DisplaySettings:
        """Build a validated copy without changing the document or persisted project."""

        values = self._display.model_dump()
        values.update({
            "preferred_refresh_hz": self.refresh_hz,
            "screen_width_px": self._mode.pixel_width,
            "screen_height_px": self._mode.pixel_height,
            "screen_width_cm": self.screen_width_spin.value(),
            "viewing_distance_cm": self.distance_spin.value(),
            "use_current_screen_resolution": False,
        })
        return DisplaySettings.model_validate(values)
