"""Choose a connected presentation display for one launch or refresh check."""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from typing import TypedDict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QVBoxLayout, QWidget
from shiboken6 import isValid

from fpvs_studio.gui.components import DialogHeader, apply_dialog_theme, mark_primary_action
from fpvs_studio.gui.update_lifecycle import update_lifecycle
from fpvs_studio.gui.window_helpers import _coerce_exception, _show_error_dialog
from fpvs_studio.gui.workers import BackgroundTask
from fpvs_studio.runtime.macos_display import MacOSMonitor, query_macos_monitors
from fpvs_studio.runtime.windows_display import WindowsMonitor, query_windows_monitors

_PENDING_PROPERTY = "experimentDisplaySelectionPending"
ConnectedMonitor = WindowsMonitor | MacOSMonitor


class _DisplayLaunchOptions(TypedDict, total=False):
    display_device_name: str


def selected_display_options(device_name: str | None) -> _DisplayLaunchOptions:
    """Return the transient display keyword arguments for a launch or probe."""
    return {} if device_name is None else {"display_device_name": device_name}


def windows_display_label(device_name: str) -> str | None:
    """Return the display label shared by the selector and refresh advisory."""
    match = re.search(r"DISPLAY(\d+)$", device_name, re.IGNORECASE)
    return f"Display {match.group(1)}" if match is not None else None


def _monitor_label(monitor: ConnectedMonitor, position: int) -> str:
    display = windows_display_label(monitor.device_name) or f"Display {position + 1}"
    primary = " (Primary)" if monitor.primary else ""
    return f"{display} · {monitor.pixel_width} × {monitor.pixel_height}{primary}"


class MonitorSelectionDialog(QDialog):
    """Transient display choice, reset to the operating system's primary each time."""

    def __init__(self, monitors: tuple[ConnectedMonitor, ...], parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Experiment display")
        self.setObjectName("monitor_selection_dialog")
        self.setMinimumSize(520, 220)
        self.resize(560, 240)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        header = DialogHeader("Choose experiment display", "", parent=self)
        header.subtitle_label.hide()
        layout.addWidget(header)
        self.monitor_combo = QComboBox(self)
        self.monitor_combo.setObjectName("experiment_display_combo")
        self.monitor_combo.setAccessibleName("Experiment display")
        for index, monitor in enumerate(monitors):
            self.monitor_combo.addItem(_monitor_label(monitor, index), monitor.device_name)
            self.monitor_combo.setItemData(index, monitor.device_name, Qt.ItemDataRole.ToolTipRole)
        self.monitor_combo.setCurrentIndex(next(
            index for index, monitor in enumerate(monitors) if monitor.primary
        ))
        self.monitor_combo.currentIndexChanged.connect(self._update_tooltip)
        self._update_tooltip()
        layout.addWidget(self.monitor_combo)
        layout.addStretch()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self,
        )
        self.continue_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.continue_button.setText("Continue")
        mark_primary_action(self.continue_button)
        self.cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        apply_dialog_theme(self)
        self.monitor_combo.setFocus()

    @property
    def selected_device_name(self) -> str:
        return str(self.monitor_combo.currentData())

    def _update_tooltip(self) -> None:
        self.monitor_combo.setToolTip(self.selected_device_name)


def choose_experiment_display(
    parent: QWidget, proceed: Callable[[str | None], None],
) -> None:
    """Discover displays off the GUI thread and prompt only for multiple monitors."""
    if sys.platform not in {"win32", "darwin"}:
        proceed(None)
        return
    is_macos = sys.platform == "darwin"
    platform_label = "macOS" if is_macos else "Windows"
    monitor_type = MacOSMonitor if is_macos else WindowsMonitor
    query_monitors: Callable[[], tuple[ConnectedMonitor, ...]] = (
        query_macos_monitors if is_macos else query_windows_monitors
    )
    owner = parent.window()
    if owner.property(_PENDING_PROPERTY) or owner.property("windowsRefreshRecommendationPending"):
        return
    owner.setProperty(_PENDING_PROPERTY, True)
    monitors: tuple[ConnectedMonitor, ...] = ()
    failure: Exception | None = None

    def receive(result: object) -> None:
        nonlocal monitors, failure
        if (
            not isinstance(result, tuple) or not result
            or any(not isinstance(item, monitor_type) for item in result)
        ):
            failure = RuntimeError(
                f"{platform_label} did not return any usable connected displays.",
            )
            return
        if sum(item.primary for item in result) != 1:
            failure = RuntimeError(f"{platform_label} did not identify one primary display.")
            return
        monitors = result

    def failed(error: object) -> None:
        nonlocal failure
        failure = _coerce_exception(error)

    def can_continue() -> bool:
        return isValid(parent) and parent.isVisible() and not update_lifecycle().is_shutting_down

    def resume(device_name: str | None) -> None:
        if not isValid(owner):
            return
        owner.setProperty(_PENDING_PROPERTY, False)
        if device_name is not None and can_continue():
            proceed(device_name)

    def finish() -> None:
        if not can_continue():
            resume(None)
            return
        if failure is not None or not monitors:
            resume(None)
            settings = (
                "macOS System Settings > Displays" if is_macos
                else "Windows Settings > System > Display"
            )
            _show_error_dialog(
                parent, "Display Check Failed",
                failure or RuntimeError(f"{platform_label} did not return any connected displays."),
                message="Studio could not detect the experiment displays. Check the monitor "
                f"connections and {settings}, then try again.",
            )
            return
        if len(monitors) == 1:
            resume(monitors[0].device_name)
            return
        dialog = MonitorSelectionDialog(monitors, parent)
        dialog.finished.connect(lambda code: resume(
            dialog.selected_device_name if code == QDialog.DialogCode.Accepted else None,
        ))
        dialog.finished.connect(dialog.deleteLater)
        dialog.open()

    task = BackgroundTask(parent_widget=owner, callback=query_monitors)
    task.succeeded.connect(receive)
    task.failed.connect(failed)
    task.finished.connect(finish)
    task.start()
