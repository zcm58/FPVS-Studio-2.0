"""Mac test calibration and explicit project pixel-resolution confirmation."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
from fpvs_studio.runtime.display_mode import NativeDisplayMode

if TYPE_CHECKING:
    from fpvs_studio.gui.document import ProjectDocument


def confirm_local_test_display(
    document: ProjectDocument, parent: QWidget, *, display_device_name: str | None = None,
) -> DisplaySettings | None:
    """Share the Mac display confirmation between Home and Run launch surfaces."""
    from fpvs_studio.runtime.display_mode import (
        query_native_display_mode,
        query_primary_native_display_mode,
    )

    mode = (
        query_primary_native_display_mode() if display_device_name is None
        else query_native_display_mode(display_device_name)
    )
    dialog = LocalTestDisplayDialog(
        document.project.settings.display, mode, parent,
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.local_display()


def save_local_test_resolution(document: ProjectDocument, display: DisplaySettings) -> None:
    """Save accepted pixel dimensions in the launch worker before compiling playback.

    Physical calibration and refresh remain launch-only. Matching dimensions leave
    the project and its resolution-selection policy untouched.
    """
    current = document.project.settings.display
    if (current.screen_width_px, current.screen_height_px) == (
        display.screen_width_px, display.screen_height_px,
    ):
        return
    document.save_display_resolution(display.screen_width_px, display.screen_height_px)


class LocalTestDisplayDialog(QDialog):
    """Confirm the detected target resolution and launch-only physical calibration."""

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
        self.resolution_mismatch = (
            display.screen_width_px, display.screen_height_px,
        ) != (mode.pixel_width, mode.pixel_height)
        refresh_hz = nearest_approved_monitor_refresh_rate(mode.hz)
        if refresh_hz is None or not mode.pixel_width or not mode.pixel_height:
            raise ValueError(
                "Select a fixed supported display rate (59.94, 60, 120, 144 or 240 Hz) "
                "in macOS System Settings > Displays, then retry."
            )
        self.refresh_hz = refresh_hz
        self.screen_width_spin = create_double_spin_box(
            parent=self, object_name="local_test_screen_width", minimum=1, maximum=500,
            decimals=2, step=0.25, suffix=" cm",
        )
        self.screen_width_spin.setValue(display.screen_width_cm)
        self.screen_width_spin.setToolTip("Measure the width across the lit screen.")
        self.distance_spin = create_double_spin_box(
            parent=self, object_name="local_test_viewing_distance", minimum=1, maximum=500,
            decimals=1, step=5, suffix=" cm",
        )
        self.distance_spin.setValue(display.viewing_distance_cm)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(DialogHeader(
            "Display resolution differs" if self.resolution_mismatch else "Local test display",
            (
                "Save the detected pixel resolution to this project before launch. "
                "Physical calibration and refresh apply only to this test."
                if self.resolution_mismatch else
                "Physical calibration and refresh apply only to this test."
            ),
            parent=self,
        ))
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        self.configured_resolution_label = QLabel(
            f"{display.screen_width_px} × {display.screen_height_px} px", self,
        )
        self.configured_resolution_label.setWordWrap(True)
        form.addRow("Project resolution", self.configured_resolution_label)
        self.mode_label = QLabel(
            f"{self.refresh_hz:g} Hz · {mode.pixel_width} × {mode.pixel_height} backing px", self,
        )
        self.mode_label.setWordWrap(True)
        self.mode_label.setToolTip(mode.mode_text)
        form.addRow("Detected display", self.mode_label)
        form.addRow("Physical screen width", self.screen_width_spin)
        form.addRow("Viewing distance", self.distance_spin)
        layout.addLayout(form)
        layout.addStretch(1)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok, self,
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Update resolution and continue" if self.resolution_mismatch else "Use for this test"
        )
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
