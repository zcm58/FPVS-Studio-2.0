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
from fpvs_studio.triggers.brainproducts_discovery import TriggerBoxPortCandidate
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
    discover = Mock(return_value=(
        TriggerBoxPortCandidate("COM42", "Brain Products GmbH TriggerBox Plus Virtual Serial Port"),
    ))
    discover_biosemi = Mock(return_value=())
    enumerate_ports = Mock(return_value=frozenset())
    popup = Mock()
    monkeypatch.setattr(tester_module, "BackgroundTask", task)
    monkeypatch.setattr(tester_module, "send_test_trigger", send)
    monkeypatch.setattr(tester_module, "SerialBackend", serial)
    monkeypatch.setattr(tester_module, "BrainProductsTriggerBoxBackend", triggerbox)
    monkeypatch.setattr(tester_module, "ParallelPortBackend", parallel)
    monkeypatch.setattr(tester_module, "check_serial_port_access", check)
    monkeypatch.setattr(tester_module, "discover_triggerbox_ports", discover)
    monkeypatch.setattr(tester_module, "discover_biosemi_ports", discover_biosemi)
    monkeypatch.setattr(tester_module, "enumerate_com_ports", enumerate_ports)
    monkeypatch.setattr(tester_module, "_show_error_dialog", popup)
    return SimpleNamespace(
        tasks=tasks, send=send, serial=serial, triggerbox=triggerbox, parallel=parallel,
        check=check, discover=discover, discover_biosemi=discover_biosemi,
        enumerate_ports=enumerate_ports, popup=popup,
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
    if port.isVisible():
        assert port.width() >= port.fontMetrics().horizontalAdvance(port.text()) + 16
    for button in (dialog.check_port_button, dialog.manual_port_button, dialog.find_port_button):
        if button.isVisible():
            assert button.width() >= button.sizeHint().width()
            if port.isVisible() and port.parentWidget() == button.parentWidget():
                assert not port.geometry().intersects(button.geometry())


@pytest.mark.parametrize(
    ("output", "adapter", "modifier", "port", "baudrate"),
    [
        ("biosemi_active_three", "serial", Qt.KeyboardModifier.NoModifier, "COM193", 57600),
        ("brainproducts_triggerbox", "triggerbox", Qt.KeyboardModifier.KeypadModifier,
         "COM42", 2_000_000),
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
    assert not dialog.port_edit.isVisible()
    assert dialog.check_port_button.text() == "Check Connection"
    hardware.discover.assert_not_called()
    hardware.discover_biosemi.assert_not_called()
    hardware.check.assert_not_called()
    _assert_dialog_geometry(qtbot, dialog)
    hardware.tasks[0].complete()
    hardware.check.assert_called_once_with(port, baudrate=baudrate)
    hardware.send.assert_not_called()
    getattr(hardware, adapter).assert_not_called()
    if adapter == "triggerbox":
        hardware.discover.assert_called_once()
        hardware.discover_biosemi.assert_not_called()
        assert not hardware.discover.call_args.kwargs.get("check_access", False)
        assert hardware.discover.call_args.kwargs.get("selected_port") is None
        assert dialog.status_label.text() == (
            "FPVS Studio has successfully connected to the BrainVision TriggerBox."
        )
    else:
        hardware.discover.assert_not_called()
        hardware.discover_biosemi.assert_called_once()
        assert dialog.port_edit.isVisible()
        assert dialog.port_edit.text() == port
        assert not dialog.status_label.text()
    assert all(button.isEnabled() for button in dialog.digit_buttons)
    _assert_dialog_geometry(qtbot, dialog)

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
    ("raw_error", "recovery"),
    [
        ("[WinError 5] Access is denied", "Fully exit serial test tools"),
        ("[WinError 2] File not found", "Reconnect the USB Trigger Interface"),
    ],
)
def test_startup_access_failure_shows_vendor_modal_and_allows_correcting_port(
    qtbot, hardware, raw_error, recovery,
):
    hardware.check.side_effect = lambda port, **_: SerialPortAccessResult(port, False, raw_error)
    dialog = _open_tester(qtbot)
    qtbot.waitUntil(lambda: len(hardware.tasks) == 1)
    port = dialog.port_edit.text()
    hardware.tasks[0].deliver_result()
    hardware.popup.assert_not_called()
    hardware.tasks[0].finished.emit()

    hardware.popup.assert_called_once()
    assert hardware.popup.call_args.args[:2] == (dialog, "BioSemi Serial Port Error")
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


def test_named_biosemi_port_uses_project_baudrate_and_reports_selection_errors(qtbot, hardware):
    hardware.discover_biosemi.return_value = ("COM12",)
    dialog = _open_tester(qtbot, output="biosemi_active_three")
    hardware.tasks[0].complete()

    hardware.check.assert_called_once_with("COM12", baudrate=57600)
    hardware.send.assert_not_called()
    assert not dialog.port_edit.isVisible()
    assert dialog.status_label.text() == (
        "FPVS Studio has successfully connected to the BioSemi USB Trigger Interface."
    )
    _assert_dialog_geometry(qtbot, dialog)

    qtbot.mouseClick(dialog.digit_buttons[5], Qt.MouseButton.LeftButton)
    hardware.tasks[-1].complete()
    hardware.serial.assert_called_once_with(port="COM12", baudrate=57600)
    hardware.send.assert_called_once_with(hardware.serial.return_value, 5)

    qtbot.mouseClick(dialog.manual_port_button, Qt.MouseButton.LeftButton)
    assert dialog.port_edit.text() == "COM193"
    hardware.check.reset_mock()
    qtbot.mouseClick(dialog.check_port_button, Qt.MouseButton.LeftButton)
    hardware.tasks[-1].complete()
    hardware.check.assert_not_called()
    assert "You selected COM193." in dialog.status_label.text()
    assert "COM12" in dialog.status_label.text()

    denied = "[WinError 5] Access is denied"
    hardware.check.side_effect = lambda port, **_: SerialPortAccessResult(port, False, denied)
    dialog.port_edit.setText("com12")
    qtbot.mouseClick(dialog.check_port_button, Qt.MouseButton.LeftButton)
    hardware.tasks[-1].complete()
    assert hardware.check.call_args.args[0].upper() == "COM12"
    assert "access was denied" in dialog.status_label.text()
    assert denied in dialog.status_label.toolTip()
    assert not any(button.isEnabled() for button in dialog.digit_buttons)
    hardware.popup.assert_not_called()
    _assert_dialog_geometry(qtbot, dialog)


@pytest.mark.parametrize("new_ports", [{"COM17"}, {"COM17", "COM18"}])
def test_biosemi_find_port_requires_one_port_added_after_reconnecting(qtbot, hardware, new_ports):
    dialog = _open_tester(qtbot)
    hardware.tasks[0].complete()
    hardware.check.reset_mock()
    hardware.enumerate_ports.side_effect = (
        frozenset({"COM3", "COM193"}), frozenset({"COM3", "COM193"} | new_ports),
    )

    qtbot.mouseClick(dialog.find_port_button, Qt.MouseButton.LeftButton)
    assert dialog.check_port_button.text() == "Scan Unplugged"
    assert not any(button.isEnabled() for button in dialog.digit_buttons)
    _assert_dialog_geometry(qtbot, dialog)
    qtbot.mouseClick(dialog.check_port_button, Qt.MouseButton.LeftButton)
    hardware.tasks[-1].complete()
    hardware.check.assert_not_called()
    assert dialog.check_port_button.text() == "Find Connected Port"
    _assert_dialog_geometry(qtbot, dialog)
    qtbot.mouseClick(dialog.check_port_button, Qt.MouseButton.LeftButton)
    hardware.tasks[-1].complete()
    assert hardware.enumerate_ports.call_count == 2
    hardware.send.assert_not_called()
    hardware.popup.assert_not_called()

    if len(new_ports) == 1:
        hardware.check.assert_called_once_with("COM17", baudrate=57600)
        assert dialog.status_label.text() == (
            "FPVS Studio has successfully connected to the BioSemi USB Trigger Interface."
        )
        assert all(button.isEnabled() for button in dialog.digit_buttons)
        assert not dialog.port_edit.isVisible()
        qtbot.mouseClick(dialog.check_port_button, Qt.MouseButton.LeftButton)
        hardware.tasks[-1].complete()
        assert hardware.check.call_count == 2
        hardware.check.assert_called_with("COM17", baudrate=57600)
        assert not dialog.port_edit.isVisible()
        assert dialog.port_edit.text() == "COM193"
    else:
        hardware.check.assert_not_called()
        assert "Other serial ports changed" in dialog.status_label.text()
        assert not any(button.isEnabled() for button in dialog.digit_buttons)
        qtbot.mouseClick(dialog.find_port_button, Qt.MouseButton.LeftButton)
        assert dialog.port_edit.isVisible()
        assert dialog.port_edit.text() == "COM193"
    _assert_dialog_geometry(qtbot, dialog)


@pytest.mark.parametrize("candidate_ports", [(), ("COM42", "COM198")])
def test_triggerbox_requires_one_named_candidate_and_supports_manual_retry(
    qtbot, hardware, candidate_ports,
):
    hardware.discover.return_value = tuple(
        TriggerBoxPortCandidate(port, f"Brain Products GmbH TriggerBox Plus ({port})")
        for port in candidate_ports
    )
    dialog = _open_tester(qtbot, output="brainproducts_triggerbox")
    qtbot.waitUntil(lambda: len(hardware.tasks) == 1)
    hardware.tasks[0].complete()

    hardware.discover.assert_called_once()
    hardware.check.assert_not_called()
    hardware.popup.assert_not_called()
    assert not dialog.port_edit.isVisible()
    assert dialog.check_port_button.isEnabled()
    assert not any(button.isEnabled() for button in dialog.digit_buttons)
    message = dialog.status_label.text()
    assert "TriggerBox" in message
    for port in candidate_ports:
        assert port in dialog.status_label.toolTip()
    _assert_dialog_geometry(qtbot, dialog)

    qtbot.mouseClick(dialog.manual_port_button, Qt.MouseButton.LeftButton)
    assert dialog.port_edit.isVisible()
    selected_port = candidate_ports[0] if candidate_ports else "COM1234567891"
    dialog.port_edit.setText(selected_port)
    assert len(hardware.tasks) == 1
    hardware.check.assert_not_called()
    _assert_dialog_geometry(qtbot, dialog)

    qtbot.mouseClick(dialog.check_port_button, Qt.MouseButton.LeftButton)
    assert len(hardware.tasks) == 2
    hardware.tasks[-1].complete()
    assert hardware.discover.call_count == 2
    hardware.check.assert_called_once_with(selected_port, baudrate=2_000_000)
    hardware.send.assert_not_called()
    assert all(button.isEnabled() for button in dialog.digit_buttons)
    _assert_dialog_geometry(qtbot, dialog)

    qtbot.mouseClick(dialog.digit_buttons[3], Qt.MouseButton.LeftButton)
    hardware.tasks[-1].complete()
    assert hardware.triggerbox.call_args.kwargs["port"] == selected_port
    hardware.send.assert_called_once_with(hardware.triggerbox.return_value, 3)

    _select_output(dialog, "brainproducts_parallel")
    _select_output(dialog, "brainproducts_triggerbox")
    assert not dialog.port_edit.isVisible()
    assert len(hardware.tasks) == 4
    hardware.tasks[-1].complete()
    assert hardware.discover.call_count == 3
    assert hardware.check.call_count == 1
    assert not any(button.isEnabled() for button in dialog.digit_buttons)


def test_triggerbox_access_failure_is_inline_and_recheck_rediscovers(qtbot, hardware):
    raw_error = "[WinError 5] Access is denied"
    hardware.check.side_effect = lambda port, **_: SerialPortAccessResult(
        port, False, raw_error,
    )
    dialog = _open_tester(qtbot, output="brainproducts_triggerbox")
    qtbot.waitUntil(lambda: len(hardware.tasks) == 1)
    hardware.tasks[0].complete()

    hardware.check.assert_called_once_with("COM42", baudrate=2_000_000)
    hardware.popup.assert_not_called()
    message = dialog.status_label.text()
    assert message.startswith("Windows lists the BrainVision TriggerBox on COM42.")
    assert "access was denied" in message
    assert raw_error in dialog.status_label.toolTip()
    assert not dialog.port_edit.isVisible()
    assert not any(button.isEnabled() for button in dialog.digit_buttons)
    qtbot.keyClick(dialog, Qt.Key.Key_6)
    assert len(hardware.tasks) == 1
    hardware.send.assert_not_called()
    _assert_dialog_geometry(qtbot, dialog)

    hardware.discover.return_value = (TriggerBoxPortCandidate("COM77", "TriggerBox rev.02"),)
    hardware.check.side_effect = lambda port, **_: SerialPortAccessResult(port, True)
    qtbot.mouseClick(dialog.check_port_button, Qt.MouseButton.LeftButton)
    assert len(hardware.tasks) == 2
    hardware.tasks[-1].complete()
    assert hardware.discover.call_count == 2
    hardware.check.assert_called_with("COM77", baudrate=2_000_000)
    hardware.send.assert_not_called()
    assert all(button.isEnabled() for button in dialog.digit_buttons)
    assert dialog.status_label.text() == (
        "FPVS Studio has successfully connected to the BrainVision TriggerBox."
    )


def test_manual_triggerbox_distinguishes_wrong_port_from_denied_access(qtbot, hardware):
    hardware.discover.return_value = (TriggerBoxPortCandidate("COM4", "TriggerBox rev.02"),)
    dialog = _open_tester(qtbot, output="brainproducts_triggerbox")
    hardware.tasks[0].complete()
    hardware.check.reset_mock()

    qtbot.mouseClick(dialog.manual_port_button, Qt.MouseButton.LeftButton)
    dialog.port_edit.setText("COM3")
    qtbot.mouseClick(dialog.check_port_button, Qt.MouseButton.LeftButton)
    assert len(hardware.tasks) == 2
    hardware.tasks[-1].complete()

    message = dialog.status_label.text()
    assert "COM3" in message
    assert "COM4" in message
    assert "Automatic Detection" in message
    hardware.check.assert_not_called()
    assert not any(button.isEnabled() for button in dialog.digit_buttons)
    _assert_dialog_geometry(qtbot, dialog)

    raw_error = "[WinError 5] Access is denied"
    hardware.check.side_effect = lambda port, **_: SerialPortAccessResult(port, False, raw_error)
    dialog.port_edit.setText("com4")
    qtbot.mouseClick(dialog.check_port_button, Qt.MouseButton.LeftButton)
    assert len(hardware.tasks) == 3
    hardware.tasks[-1].complete()

    assert hardware.check.call_count == 1
    assert hardware.check.call_args.args[0].upper() == "COM4"
    assert hardware.check.call_args.kwargs["baudrate"] == 2_000_000
    message = dialog.status_label.text()
    assert message.startswith("Windows lists the BrainVision TriggerBox on COM4.")
    assert "access was denied" in message
    assert raw_error in dialog.status_label.toolTip()
    assert not any(button.isEnabled() for button in dialog.digit_buttons)
    _assert_dialog_geometry(qtbot, dialog)

    hardware.check.side_effect = lambda port, **_: SerialPortAccessResult(port, True)
    qtbot.mouseClick(dialog.check_port_button, Qt.MouseButton.LeftButton)
    assert len(hardware.tasks) == 4
    hardware.tasks[-1].complete()
    assert hardware.discover.call_count == 4
    assert all(button.isEnabled() for button in dialog.digit_buttons)
    hardware.send.assert_not_called()
    hardware.popup.assert_not_called()


def test_manual_triggerbox_missing_port_reports_unidentified_selection(qtbot, hardware):
    raw_error = "[WinError 2] File not found"
    hardware.discover.return_value = ()
    hardware.check.side_effect = lambda port, **_: SerialPortAccessResult(port, False, raw_error)
    dialog = _open_tester(qtbot, output="brainproducts_triggerbox")
    hardware.tasks[0].complete()

    qtbot.mouseClick(dialog.manual_port_button, Qt.MouseButton.LeftButton)
    dialog.port_edit.setText("COM3")
    qtbot.mouseClick(dialog.check_port_button, Qt.MouseButton.LeftButton)
    assert len(hardware.tasks) == 2
    hardware.tasks[-1].complete()

    hardware.check.assert_called_once_with("COM3", baudrate=2_000_000)
    message = dialog.status_label.text()
    assert message.startswith("Windows could not find the selected port COM3.")
    assert "Device Manager" in message
    assert raw_error in dialog.status_label.toolTip()
    assert not any(button.isEnabled() for button in dialog.digit_buttons)
    hardware.send.assert_not_called()
    hardware.popup.assert_not_called()
    _assert_dialog_geometry(qtbot, dialog)


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
    assert not dialog.port_edit.isVisible()
    qtbot.waitUntil(lambda: len(hardware.tasks) == 3)
    hardware.tasks[-1].complete()
    hardware.discover.assert_called_once()
    hardware.check.assert_called_with("COM42", baudrate=2_000_000)
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
    assert not dialog.manual_port_button.isVisible()
    assert not dialog.find_port_button.isVisible()
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
    hardware.discover.assert_not_called()


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
