"""Offer Windows refresh-rate guidance before a display check or session launch."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget
from shiboken6 import isValid

from fpvs_studio.core.validation import approved_monitor_refresh_rate
from fpvs_studio.gui.components import (
    DialogHeader,
    apply_dialog_theme,
    mark_error_text,
    mark_primary_action,
)
from fpvs_studio.gui.monitor_selection_dialog import windows_display_label
from fpvs_studio.gui.update_lifecycle import update_lifecycle
from fpvs_studio.gui.workers import BackgroundTask
from fpvs_studio.runtime.windows_display import (
    WindowsRefreshRecommendation,
    query_windows_refresh_recommendation,
)

LOGGER = logging.getLogger(__name__)
_PENDING_PROPERTY = "windowsRefreshRecommendationPending"


class RefreshRecommendationDialog(QDialog):
    def __init__(
        self,
        recommendation: WindowsRefreshRecommendation,
        parent: QWidget,
        *,
        display_device_name: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Higher refresh rate available")
        self.setMinimumSize(520, 280)
        self.resize(560, 300)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        highest = recommendation.highest_hz
        recommended_hz = max(
            (
                rate for rate in recommendation.higher_rates_hz
                if approved_monitor_refresh_rate(rate) is not None
            ),
            default=None,
        )
        guidance = (
            f"Choose {recommended_hz} Hz in Windows for Studio timing checks."
            if recommended_hz is not None
            else "60 Hz is the highest Studio-supported rate Windows reported at this resolution."
        )
        layout.addWidget(DialogHeader(
            f"60 Hz in use · {highest} Hz available", guidance, parent=self,
        ))
        display = windows_display_label(display_device_name) if display_device_name else None
        resolution = f"{recommendation.pixel_width} × {recommendation.pixel_height}"
        self.details_label = QLabel(
            f"{display} · {resolution}" if display else f"Resolution {resolution}", self,
        )
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)
        self.settings_hint = QLabel(
            "Select the experiment display in Windows. After changing its rate, "
            "use Check refresh rate on the same display."
            if display
            else "After changing the rate in Windows, use Check refresh rate in Studio.",
            self,
        )
        self.settings_hint.setWordWrap(True)
        self.settings_hint.setVisible(recommended_hz is not None)
        layout.addWidget(self.settings_hint)
        self.settings_error = QLabel(
            "Windows Settings could not open. "
            "Go to Settings → System → Display → Advanced display.",
            self,
        )
        self.settings_error.setWordWrap(True)
        mark_error_text(self.settings_error)
        self.settings_error.hide()
        layout.addWidget(self.settings_error)
        layout.addStretch()
        buttons = QDialogButtonBox(self)
        self.settings_button = buttons.addButton(
            "Open Advanced display settings", QDialogButtonBox.ButtonRole.ActionRole,
        )
        self.continue_button = buttons.addButton(
            "Continue at 60 Hz", QDialogButtonBox.ButtonRole.AcceptRole,
        )
        primary_button = (
            self.settings_button if recommended_hz is not None else self.continue_button
        )
        mark_primary_action(primary_button)
        primary_button.setDefault(True)
        self.settings_button.clicked.connect(self._open_settings)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        apply_dialog_theme(self)
        primary_button.setFocus()

    def _open_settings(self) -> None:
        if QDesktopServices.openUrl(QUrl("ms-settings:display-advanced")):
            self.reject()
        else:
            self.settings_error.show()


def check_windows_refresh(
    parent: QWidget, proceed: Callable[[], None], *, display_device_name: str | None = None,
) -> None:
    """Run the read-only advisory, then continue only if the user chooses to."""
    if sys.platform != "win32":
        proceed()
        return
    owner = parent.window()
    if owner.property(_PENDING_PROPERTY) or owner.property("experimentDisplaySelectionPending"):
        return
    owner.setProperty(_PENDING_PROPERTY, True)
    recommendation: WindowsRefreshRecommendation | None = None

    def receive(result: object) -> None:
        nonlocal recommendation
        if isinstance(result, WindowsRefreshRecommendation):
            recommendation = result

    def finish() -> None:
        def can_continue() -> bool:
            return (
                isValid(parent) and parent.isVisible() and not update_lifecycle().is_shutting_down
            )

        def resume(accepted: bool) -> None:
            if not isValid(owner):
                return
            owner.setProperty(_PENDING_PROPERTY, False)
            if accepted and can_continue():
                proceed()

        if recommendation is None or not can_continue():
            resume(recommendation is None)
            return
        dialog = RefreshRecommendationDialog(
            recommendation, parent, display_device_name=display_device_name,
        )
        dialog.finished.connect(lambda code: resume(code == QDialog.DialogCode.Accepted))
        dialog.finished.connect(dialog.deleteLater)
        dialog.open()

    def compare_rates() -> WindowsRefreshRecommendation | None:
        if display_device_name is None:
            return query_windows_refresh_recommendation()
        return query_windows_refresh_recommendation(display_device_name)

    task = BackgroundTask(parent_widget=owner, callback=compare_rates)
    task.succeeded.connect(receive)
    task.failed.connect(
        lambda error: LOGGER.warning("Could not compare Windows refresh rates: %s", error)
    )
    task.finished.connect(finish)
    task.start()
