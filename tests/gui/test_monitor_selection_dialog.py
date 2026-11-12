"""Registered visible smoke for transient experiment-monitor selection."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, QRect, Qt, Signal
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from tests.gui.helpers import assert_visible_children_within_parent
from tests.platform_adapters import set_module_platform

from fpvs_studio.gui import monitor_selection_dialog as selection
from fpvs_studio.runtime.macos_display import MacOSMonitor
from fpvs_studio.runtime.windows_display import WindowsMonitor


def _monitors() -> tuple[WindowsMonitor, ...]:
    return (
        WindowsMonitor(r"\\.\DISPLAY3", False, 3840, 2160, -3840, 0),
        WindowsMonitor(r"\\.\DISPLAY12", True, 7680, 4320, 0, 0),
    )


def _mac_monitors() -> tuple[MacOSMonitor, ...]:
    return (
        MacOSMonitor(73, False, 3840, 2160),
        MacOSMonitor(4294967295, True, 7680, 4320),
    )


class _ImmediateTask(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, *, parent_widget, callback):
        super().__init__(parent_widget)
        self.callback = callback

    def start(self):
        try:
            result = self.callback()
        except Exception as error:
            self.failed.emit(error)
        else:
            self.succeeded.emit(result)
        self.finished.emit()


@pytest.fixture
def display_gate(qtbot, monkeypatch):
    set_module_platform(monkeypatch, selection, "win32")
    monkeypatch.setattr(selection, "BackgroundTask", _ImmediateTask)
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()
    probe = Mock(return_value=_monitors())
    monkeypatch.setattr(selection, "query_windows_monitors", probe)
    error_dialog = Mock()
    monkeypatch.setattr(selection, "_show_error_dialog", error_dialog)
    return parent, probe, error_dialog


@pytest.mark.parametrize("size", [(520, 220), (560, 240)])
@pytest.mark.parametrize("platform_name", ["win32", "darwin"])
def test_primary_default_labels_actions_and_fit(qtbot, size, platform_name):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()
    monitors = _monitors() if platform_name == "win32" else _mac_monitors()
    dialog = selection.MonitorSelectionDialog(monitors, parent)
    qtbot.addWidget(dialog)
    dialog.resize(*size)
    dialog.open()
    qtbot.waitUntil(dialog.isVisible)
    QApplication.processEvents()

    assert dialog.size().toTuple() == size
    assert dialog.selected_device_name == monitors[1].device_name
    number = 12 if platform_name == "win32" else 2
    assert dialog.monitor_combo.currentText() == f"Display {number} · 7680 × 4320 (Primary)"
    assert dialog.monitor_combo.toolTip() == monitors[1].device_name
    assert dialog.monitor_combo.itemData(0, Qt.ItemDataRole.ToolTipRole) == monitors[0].device_name
    assert_visible_children_within_parent(dialog)
    for label in dialog.findChildren(QLabel):
        if not label.isVisible():
            continue
        rect = label.contentsRect()
        required = label.fontMetrics().boundingRect(
            QRect(0, 0, rect.width(), 1000), Qt.TextFlag.TextWordWrap, label.text(),
        )
        assert rect.height() >= required.height()
    longest = max(
        dialog.monitor_combo.fontMetrics().horizontalAdvance(dialog.monitor_combo.itemText(index))
        for index in range(dialog.monitor_combo.count())
    )
    assert dialog.monitor_combo.width() >= longest + 40
    for button in (dialog.continue_button, dialog.cancel_button):
        assert button.width() >= button.fontMetrics().horizontalAdvance(button.text())
    dialog.monitor_combo.setCurrentIndex(0)
    assert dialog.selected_device_name == monitors[0].device_name
    assert dialog.monitor_combo.toolTip() == monitors[0].device_name
    with qtbot.waitSignal(dialog.accepted):
        dialog.continue_button.click()


@pytest.mark.parametrize("choice", ["primary", "secondary", "cancel"])
def test_multi_monitor_prompt_and_choice(display_gate, choice):
    parent, probe, errors = display_gate
    proceed = Mock()
    selection.choose_experiment_display(parent, proceed)
    dialog = parent.findChild(selection.MonitorSelectionDialog)
    assert dialog is not None and dialog.isModal()
    assert dialog.selected_device_name == r"\\.\DISPLAY12"
    selection.choose_experiment_display(parent, proceed)
    probe.assert_called_once_with()
    proceed.assert_not_called()
    if choice == "secondary":
        dialog.monitor_combo.setCurrentIndex(0)
    if choice == "cancel":
        dialog.cancel_button.click()
        proceed.assert_not_called()
    else:
        dialog.continue_button.click()
        proceed.assert_called_once_with(
            r"\\.\DISPLAY3" if choice == "secondary" else r"\\.\DISPLAY12",
        )
    assert parent.property("experimentDisplaySelectionPending") is False
    errors.assert_not_called()


def test_single_monitor_continues_without_prompt(display_gate):
    parent, probe, errors = display_gate
    probe.return_value = (_monitors()[1],)
    proceed = Mock()
    selection.choose_experiment_display(parent, proceed)
    assert parent.findChild(selection.MonitorSelectionDialog) is None
    proceed.assert_called_once_with(r"\\.\DISPLAY12")
    errors.assert_not_called()


@pytest.mark.parametrize("result", [(), None, (object(),), (_monitors()[0],)])
def test_missing_or_invalid_displays_block_with_actionable_error(display_gate, result):
    parent, probe, errors = display_gate
    probe.return_value = result
    proceed = Mock()
    selection.choose_experiment_display(parent, proceed)
    proceed.assert_not_called()
    assert parent.findChild(selection.MonitorSelectionDialog) is None
    errors.assert_called_once()
    assert "Windows Settings > System > Display" in errors.call_args.kwargs["message"]
    assert parent.property("experimentDisplaySelectionPending") is False


def test_probe_failure_blocks_and_allows_retry(display_gate):
    parent, probe, errors = display_gate
    probe.side_effect = RuntimeError("Display enumeration failed")
    proceed = Mock()
    selection.choose_experiment_display(parent, proceed)
    proceed.assert_not_called()
    errors.assert_called_once()
    probe.side_effect = None
    probe.return_value = (_monitors()[1],)
    selection.choose_experiment_display(parent, proceed)
    proceed.assert_called_once_with(r"\\.\DISPLAY12")


def test_linux_keeps_existing_launch_path(qtbot, monkeypatch):
    set_module_platform(monkeypatch, selection, "linux")
    parent = QWidget()
    qtbot.addWidget(parent)
    probe = Mock()
    monkeypatch.setattr(selection, "query_windows_monitors", probe)
    proceed = Mock()
    selection.choose_experiment_display(parent, proceed)
    proceed.assert_called_once_with(None)
    probe.assert_not_called()


def test_existing_refresh_check_suppresses_new_selection(display_gate):
    parent, probe, errors = display_gate
    parent.setProperty("windowsRefreshRecommendationPending", True)
    proceed = Mock()
    selection.choose_experiment_display(parent, proceed)
    probe.assert_not_called()
    proceed.assert_not_called()
    errors.assert_not_called()


@pytest.mark.parametrize("state", ["hidden", "destroyed", "shutdown"])
def test_completed_probe_does_not_resume_inactive_owner(display_gate, monkeypatch, state):
    parent, probe, errors = display_gate
    held_tasks = []

    class HeldTask(_ImmediateTask):
        def start(self):
            held_tasks.append(self)

    monkeypatch.setattr(selection, "BackgroundTask", HeldTask)
    proceed = Mock()
    selection.choose_experiment_display(parent, proceed)
    selection.choose_experiment_display(parent, proceed)
    assert len(held_tasks) == 1
    task = held_tasks[0]
    if state == "hidden":
        parent.hide()
    elif state == "destroyed":
        # Keep the fake worker alive independently, as the real lifecycle does.
        task.setParent(None)
        from shiboken6 import delete

        delete(parent)
    else:
        monkeypatch.setattr(selection, "update_lifecycle", lambda: SimpleNamespace(
            is_shutting_down=True,
        ))
    task.succeeded.emit(_monitors())
    task.finished.emit()
    proceed.assert_not_called()
    errors.assert_not_called()


def test_each_invocation_redetects_and_defaults_to_current_primary(display_gate, qtbot):
    parent, probe, _errors = display_gate
    proceed = Mock()
    selection.choose_experiment_display(parent, proceed)
    first = parent.findChild(selection.MonitorSelectionDialog)
    first.monitor_combo.setCurrentIndex(0)
    first.continue_button.click()
    qtbot.waitUntil(lambda: parent.findChild(selection.MonitorSelectionDialog) is None)
    selection.choose_experiment_display(parent, proceed)
    second = parent.findChild(selection.MonitorSelectionDialog)
    assert second.selected_device_name == r"\\.\DISPLAY12"
    assert probe.call_count == 2
    second.reject()
    qtbot.waitUntil(lambda: parent.findChild(selection.MonitorSelectionDialog) is None)
    probe.return_value = (
        WindowsMonitor(r"\\.\DISPLAY3", True, 3840, 2160),
        WindowsMonitor(r"\\.\DISPLAY12", False, 7680, 4320),
    )
    selection.choose_experiment_display(parent, proceed)
    third = parent.findChild(selection.MonitorSelectionDialog)
    assert third.selected_device_name == r"\\.\DISPLAY3"
    assert probe.call_count == 3
    third.reject()


@pytest.mark.parametrize("choice", ["primary", "secondary", "cancel", "single"])
def test_mac_selector_uses_native_primary_and_prompts_only_for_multiple(
    display_gate, monkeypatch, choice,
):
    parent, windows_probe, errors = display_gate
    set_module_platform(monkeypatch, selection, "darwin")
    monitors = _mac_monitors()
    probe = Mock(return_value=(monitors[1],) if choice == "single" else monitors)
    monkeypatch.setattr(selection, "query_macos_monitors", probe)
    proceed = Mock()
    selection.choose_experiment_display(parent, proceed)
    windows_probe.assert_not_called()
    probe.assert_called_once_with()
    dialog = parent.findChild(selection.MonitorSelectionDialog)
    if choice == "single":
        assert dialog is None
        proceed.assert_called_once_with(monitors[1].device_name)
    else:
        assert dialog is not None and dialog.isModal()
        assert dialog.selected_device_name == monitors[1].device_name
        proceed.assert_not_called()
        if choice == "secondary":
            dialog.monitor_combo.setCurrentIndex(0)
        if choice == "cancel":
            dialog.reject()
            proceed.assert_not_called()
        else:
            dialog.continue_button.click()
            proceed.assert_called_once_with(
                monitors[0 if choice == "secondary" else 1].device_name,
            )
    errors.assert_not_called()


def test_mac_detection_failure_blocks_and_retry_uses_changed_primary(display_gate, monkeypatch):
    parent, windows_probe, errors = display_gate
    set_module_platform(monkeypatch, selection, "darwin")
    probe = Mock(side_effect=RuntimeError("Display disconnected"))
    monkeypatch.setattr(selection, "query_macos_monitors", probe)
    proceed = Mock()
    selection.choose_experiment_display(parent, proceed)
    proceed.assert_not_called()
    assert "macOS System Settings > Displays" in errors.call_args.kwargs["message"]
    probe.side_effect = None
    probe.return_value = (
        MacOSMonitor(73, True, 3840, 2160), MacOSMonitor(4294967295, False, 7680, 4320),
    )
    selection.choose_experiment_display(parent, proceed)
    dialog = parent.findChild(selection.MonitorSelectionDialog)
    assert dialog.selected_device_name == "macos:73"
    dialog.accept()
    proceed.assert_called_once_with("macos:73")
    windows_probe.assert_not_called()
