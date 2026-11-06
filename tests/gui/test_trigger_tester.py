"""Registered keyboard and worker smoke checks for the hardware trigger tester."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLabel
from tests.gui.helpers import assert_visible_children_within_parent, open_created_project

from fpvs_studio.core.models import TriggerSettings
from fpvs_studio.gui import trigger_tester as tester_module
from fpvs_studio.gui.trigger_tester import TriggerTesterDialog
from fpvs_studio.triggers.biosemi_errors import biosemi_port_error_message
from fpvs_studio.triggers.serial_backend import SerialBackendError
from fpvs_studio.triggers.serial_port_access import SerialPortAccessResult


class _HeldTask(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def start(self) -> None:
        pass

    def deliver_result(self) -> None:
        try:
            result = self.callback()
        except Exception as error:
            self.failed.emit(error)
        else:
            self.succeeded.emit(result)

    def complete(self) -> None:
        self.deliver_result()
        self.finished.emit()


@pytest.fixture
def hardware(monkeypatch):
    tasks = []

    def task(*, callback, **_kwargs):
        held = _HeldTask(callback)
        tasks.append(held)
        return held

    send = Mock()
    serial = Mock(return_value=object())
    triggerbox = Mock(return_value=object())
    parallel = Mock(return_value=object())
    check = Mock(side_effect=lambda port, **_: SerialPortAccessResult(port, True))
    popup = Mock()
    monkeypatch.setattr(tester_module, "BackgroundTask", task)
    monkeypatch.setattr(tester_module, "send_test_trigger", send)
    monkeypatch.setattr(tester_module, "SerialBackend", serial)
    monkeypatch.setattr(tester_module, "BrainProductsTriggerBoxBackend", triggerbox)
    monkeypatch.setattr(tester_module, "ParallelPortBackend", parallel)
    monkeypatch.setattr(tester_module, "check_serial_port_access", check)
    monkeypatch.setattr(tester_module, "_show_error_dialog", popup)
    return SimpleNamespace(
        tasks=tasks, send=send, serial=serial, triggerbox=triggerbox, parallel=parallel,
        check=check, popup=popup,
    )


def _open_tester(qtbot, *, output="serial", address=None):
    configuration = {
        "recording_backend": output,
        "brainproducts_serial_port": "COM1234567890",
        "brainproducts_parallel_address": address,
    }
    dialog = TriggerTesterDialog(
        configuration, TriggerSettings(serial_port="COM193", baudrate=57600),
    )
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    return dialog


def _select_output(dialog, output):
    index = dialog.output_combo.findData(output)
    assert index >= 0
    dialog.output_combo.setCurrentIndex(index)


def _assert_dialog_geometry(qtbot, dialog) -> None:
    QApplication.processEvents()
    assert dialog.minimumSize().toTuple() == (560, 340)
    assert dialog.size().toTuple() == (560, 340)
    labels = [label for label in dialog.findChildren(QLabel) if label.isVisible()]
    qtbot.waitUntil(lambda: all(
        label.height() >= label.heightForWidth(label.width())
        for label in labels if label.wordWrap()
    ))
    assert_visible_children_within_parent(dialog)
    for label in labels:
        if not label.wordWrap():
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
    output = dialog.output_combo
    assert output.width() >= output.fontMetrics().horizontalAdvance(output.currentText()) + 32
    port = dialog.port_edit
    assert port.width() >= port.fontMetrics().horizontalAdvance(port.text()) + 16
    check = dialog.check_port_button
    if check.isVisible():
        assert check.width() >= check.sizeHint().width()
        assert not port.geometry().intersects(check.geometry())


@pytest.mark.parametrize(
    ("output", "adapter", "modifier", "port", "baudrate"),
    [
        ("biosemi_active_three", "serial", Qt.KeyboardModifier.NoModifier, "COM193", 57600),
        ("brainproducts_triggerbox", "triggerbox", Qt.KeyboardModifier.KeypadModifier,
         "COM1234567890", 2_000_000),
    ],
)
def test_startup_checks_access_before_sending_exact_digits(
    qtbot, hardware, output, adapter, modifier, port, baudrate,
):
    dialog = _open_tester(qtbot, output=output)
    qtbot.waitUntil(lambda: len(hardware.tasks) == 1)
    assert not any(button.isEnabled() for button in dialog.digit_buttons)
    qtbot.keyClick(dialog, Qt.Key.Key_4, modifier)
    assert len(hardware.tasks) == 1
    _assert_dialog_geometry(qtbot, dialog)
    hardware.tasks[0].complete()
    hardware.check.assert_called_once_with(port, baudrate=baudrate)
    hardware.send.assert_not_called()
    getattr(hardware, adapter).assert_not_called()
    assert not dialog.status_label.text()
    assert all(button.isEnabled() for button in dialog.digit_buttons)

    for digit in range(10):
        key = Qt.Key(Qt.Key.Key_0 + digit)
        qtbot.keyClick(dialog.digit_buttons[1], key, modifier)
        assert len(hardware.tasks) == digit + 2
        assert hardware.send.call_count == digit
        hardware.tasks[-1].complete()
        hardware.send.assert_called_with(getattr(hardware, adapter).return_value, digit)
        expected = (
            "Studio wrote 0 (idle). It may not appear as a marker."
            if digit == 0 else f"Studio sent trigger {digit}. Check the recording software."
        )
        assert dialog.status_label.text() == expected
    assert getattr(hardware, adapter).call_args.kwargs["port"] == port
    if adapter == "serial":
        assert hardware.serial.call_args.kwargs["baudrate"] == baudrate
    hardware.check.assert_called_once_with(port, baudrate=baudrate)
    _assert_dialog_geometry(qtbot, dialog)


@pytest.mark.parametrize(
    ("output", "title", "raw_error", "recovery"),
    [
        ("serial", "BioSemi Serial Port Error", "[WinError 5] Access is denied",
         "Fully exit serial test tools"),
        ("serial", "BioSemi Serial Port Error", "[WinError 2] File not found",
         "Reconnect the USB Trigger Interface"),
        ("brainproducts_triggerbox", "TriggerBox Serial Port Error",
         "[WinError 2] The system cannot find the file specified", "check Device Manager"),
        ("brainproducts_triggerbox", "TriggerBox Serial Port Error",
         "[WinError 5] Access is denied", "Fully exit the TriggerBox software"),
    ],
)
def test_startup_access_failure_shows_vendor_modal_and_allows_correcting_port(
    qtbot, hardware, output, title, raw_error, recovery,
):
    hardware.check.side_effect = lambda port, **_: SerialPortAccessResult(port, False, raw_error)
    dialog = _open_tester(qtbot, output=output)
    qtbot.waitUntil(lambda: len(hardware.tasks) == 1)
    port = dialog.port_edit.text()
    hardware.tasks[0].deliver_result()
    hardware.popup.assert_not_called()
    hardware.tasks[0].finished.emit()

    hardware.popup.assert_called_once()
    assert hardware.popup.call_args.args[:2] == (dialog, title)
    assert raw_error in str(hardware.popup.call_args.args[2])
    assert port in hardware.popup.call_args.kwargs["message"]
    assert recovery in hardware.popup.call_args.kwargs["message"]
    assert dialog.port_edit.text() == port
    assert dialog.port_edit.isEnabled()
    assert dialog.check_port_button.isEnabled()
    assert not any(button.isEnabled() for button in dialog.digit_buttons)
    qtbot.keyClick(dialog, Qt.Key.Key_6)
    assert len(hardware.tasks) == 1
    hardware.send.assert_not_called()
    _assert_dialog_geometry(qtbot, dialog)

    hardware.check.side_effect = lambda port, **_: SerialPortAccessResult(port, True)
    dialog.port_edit.setText("COM42")
    qtbot.mouseClick(dialog.check_port_button, Qt.MouseButton.LeftButton)
    assert len(hardware.tasks) == 2
    hardware.tasks[-1].complete()
    assert hardware.check.call_args.args == ("COM42",)
    assert all(button.isEnabled() for button in dialog.digit_buttons)
    hardware.popup.assert_called_once()
    hardware.send.assert_not_called()


def test_busy_send_blocks_close_and_reenables_controls_after_failure(qtbot, hardware):
    dialog = _open_tester(qtbot)
    qtbot.waitUntil(lambda: len(hardware.tasks) == 1)
    hardware.tasks[0].complete()
    message = biosemi_port_error_message("COM1234567890", PermissionError("Access is denied"))
    hardware.send.side_effect = SerialBackendError(message)
    qtbot.mouseClick(dialog.digit_buttons[3], Qt.MouseButton.LeftButton)

    for control in (
        *dialog.digit_buttons, dialog.output_combo, dialog.port_edit, dialog.close_button,
        dialog.check_port_button,
    ):
        assert not control.isEnabled()
    qtbot.keyClick(dialog, Qt.Key.Key_9)
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    dialog.close()
    assert len(hardware.tasks) == 2
    assert dialog.isVisible()
    _assert_dialog_geometry(qtbot, dialog)

    hardware.tasks[-1].complete()
    hardware.popup.assert_called_once()
    assert hardware.popup.call_args.args[:2] == (dialog, "Send Test Trigger")
    assert str(hardware.popup.call_args.args[2]) == message
    _assert_dialog_geometry(qtbot, dialog)
    assert dialog.close_button.isEnabled()
    assert dialog.check_port_button.isEnabled()
    assert not any(button.isEnabled() for button in dialog.digit_buttons)

    hardware.send.side_effect = None
    qtbot.mouseClick(dialog.check_port_button, Qt.MouseButton.LeftButton)
    assert len(hardware.tasks) == 3
    hardware.tasks[-1].complete()
    qtbot.mouseClick(dialog.digit_buttons[3], Qt.MouseButton.LeftButton)
    hardware.tasks[-1].complete()
    assert dialog.status_label.text() == "Studio sent trigger 3. Check the recording software."
    qtbot.mouseClick(dialog.close_button, Qt.MouseButton.LeftButton)
    assert not dialog.isVisible()


def test_editing_port_and_holding_a_key_do_not_send(qtbot, hardware):
    dialog = _open_tester(qtbot)
    qtbot.waitUntil(lambda: len(hardware.tasks) == 1)
    hardware.tasks[0].complete()
    assert dialog.port_edit.text() == "COM193"
    dialog.port_edit.clear()
    assert not any(button.isEnabled() for button in dialog.digit_buttons)
    dialog.port_edit.setFocus()
    qtbot.waitUntil(dialog.port_edit.hasFocus)
    qtbot.keyClicks(dialog.port_edit, "COM42")
    assert dialog.port_edit.text() == "COM42"
    assert len(hardware.tasks) == 1
    qtbot.keyClick(dialog.port_edit, Qt.Key.Key_Return)
    assert len(hardware.tasks) == 2
    hardware.tasks[-1].complete()
    qtbot.waitUntil(dialog.digit_buttons[1].hasFocus)
    hardware.check.assert_called_with("COM42", baudrate=57600)
    hardware.send.assert_not_called()

    _select_output(dialog, "brainproducts_triggerbox")
    assert dialog.port_edit.text() == "COM1234567890"
    qtbot.waitUntil(lambda: len(hardware.tasks) == 3)
    hardware.tasks[-1].complete()
    hardware.check.assert_called_with("COM1234567890", baudrate=2_000_000)
    _select_output(dialog, "serial")
    assert dialog.port_edit.text() == "COM42"
    qtbot.waitUntil(lambda: len(hardware.tasks) == 4)
    hardware.tasks[-1].complete()
    dialog.close_button.setFocus()
    repeat = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_4, Qt.KeyboardModifier.NoModifier, "4", True,
    )
    QApplication.sendEvent(dialog, repeat)
    qtbot.keyClick(dialog, Qt.Key.Key_4, Qt.KeyboardModifier.ControlModifier)
    assert len(hardware.tasks) == 4
    hardware.send.assert_not_called()


@pytest.mark.parametrize("address", [None, 0xD010])
def test_parallel_uses_configured_address(qtbot, hardware, address):
    dialog = _open_tester(qtbot, output="brainproducts_parallel", address=address)
    assert dialog.port_edit.isReadOnly()
    assert not dialog.check_port_button.isVisible()
    assert not hardware.tasks
    assert all(button.isEnabled() == (address is not None) for button in dialog.digit_buttons)
    _assert_dialog_geometry(qtbot, dialog)

    dialog.close_button.setFocus()
    qtbot.keyClick(dialog, Qt.Key.Key_8)
    if address is None:
        assert not hardware.tasks
        return
    assert len(hardware.tasks) == 1
    hardware.tasks[0].complete()
    assert hardware.parallel.call_args.args == (address,)
    hardware.send.assert_called_once_with(hardware.parallel.return_value, 8)


def test_tools_action_opens_tester_without_sending(qtbot, controller, tmp_path, hardware):
    document, window = open_created_project(controller, qtbot, tmp_path, "Trigger Tester Menu")
    saved_port = document.project.settings.triggers.serial_port
    assert window.trigger_tester_action in window.tools_menu.actions()
    assert window.trigger_tester_action.text() == "Trigger Tester"
    window.trigger_tester_action.trigger()

    dialog = window.findChild(TriggerTesterDialog)
    assert dialog is not None
    assert dialog.isVisible()
    qtbot.waitUntil(lambda: len(hardware.tasks) == 1)
    hardware.tasks[0].complete()
    hardware.send.assert_not_called()
    dialog.port_edit.setText("COM42")
    dialog.close()
    assert document.project.settings.triggers.serial_port == saved_port
    assert window.main_stack.currentWidget() is window.home_page
