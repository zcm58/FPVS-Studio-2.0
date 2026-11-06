"""Visible opt-in popup reporting tests; callbacks never use the live service."""

from __future__ import annotations

import errno
import sys

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton
from tests.gui.helpers import assert_visible_children_within_parent, widget_message_box

from fpvs_studio.gui.error_dialogs import REPORT_BUTTON_TEXT, ErrorDialogReporter
from fpvs_studio.triggers.biosemi_errors import (
    biosemi_port_error_message,
    biosemi_write_error_message,
)
from fpvs_studio.triggers.brainproducts_backend import BrainProductsTriggerBoxError
from fpvs_studio.triggers.brainproducts_errors import triggerbox_port_error_message
from fpvs_studio.triggers.parallel_backend import (
    ParallelPortDriverUnavailableError,
    ParallelPortError,
)
from fpvs_studio.triggers.serial_backend import SerialBackendError


@pytest.fixture
def popups(qapp):
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    requests = []
    previous = qapp.findChild(ErrorDialogReporter, "fpvs_error_dialog_reporter")
    if previous is not None:
        qapp.removeEventFilter(previous)
    reporter = ErrorDialogReporter(qapp, report=lambda *args: requests.append(args))
    yield reporter, requests
    qapp.removeEventFilter(reporter)
    reporter.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    if previous is not None:
        qapp.installEventFilter(previous)


@pytest.mark.parametrize("icon", [QMessageBox.Icon.Critical, QMessageBox.Icon.Warning])
def test_report_button_automatically_covers_static_error_popups(qtbot, popups, icon):
    _reporter, requests = popups
    box = widget_message_box(
        icon, "Import Error", "Unable to import project bundle", QMessageBox.StandardButton.Ok
    )
    qtbot.addWidget(box)
    expected_title = box.windowTitle()
    if sys.platform != "darwin":
        assert expected_title == "Import Error"
    box.setDetailedText("PermissionError: [WinError 5] Access is denied")
    box.show()
    button = box.findChild(QPushButton, "report_error_button")
    assert button is not None
    assert button.text() == REPORT_BUTTON_TEXT
    assert "couldn't access" in box.text()
    assert "WinError 5" in box.detailedText()
    assert not requests
    button.click()
    qtbot.waitUntil(lambda: len(requests) == 1)
    assert not box.isVisible()
    title, diagnostic, message = requests[0]
    assert title == expected_title
    assert "WinError 5" in diagnostic
    assert "couldn't access" in message


def test_confirmations_information_and_normal_dismissal_do_not_report(qtbot, popups):
    _reporter, requests = popups
    for icon, buttons in (
        (QMessageBox.Icon.Information, QMessageBox.StandardButton.Ok),
        (QMessageBox.Icon.Warning, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No),
    ):
        box = widget_message_box(icon, "Review", "Continue?", buttons)
        qtbot.addWidget(box)
        box.show()
        assert box.findChild(QPushButton, "report_error_button") is None
        box.close()
    box = widget_message_box(
        QMessageBox.Icon.Critical, "Error", "Unable to save", QMessageBox.StandardButton.Ok
    )
    qtbot.addWidget(box)
    box.show()
    qtbot.waitExposed(box)
    qtbot.keyClick(box, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: not box.isVisible())
    assert requests == []


@pytest.mark.parametrize("error", [
    TypeError("unsupported operand type(s) for +: 'NoneType' and 'int'"),
    ValueError("serial_enabled must be a boolean; input_value=None"),
    PermissionError(errno.EACCES, "Permission denied", "C:/results/session.xlsx"),
])
def test_technical_failures_keep_plain_primary_text_and_complete_details(qtbot, popups, error):
    reporter, _requests = popups
    box = widget_message_box(
        QMessageBox.Icon.Critical, "Save Error", str(error), QMessageBox.StandardButton.Ok,
    )
    qtbot.addWidget(box)
    reporter.decorate(box, error=error)
    box.show()
    primary = box.text() + " " + box.informativeText()
    for technical in ("NoneType", "serial_enabled", "input_value", "[Errno", "TypeError"):
        assert technical not in primary
    assert box.informativeText()
    assert str(error) in box.detailedText()
    QApplication.processEvents()
    assert_visible_children_within_parent(box)


def test_standalone_updater_startup_error_has_recovery_and_expandable_diagnostics(
    qtbot, monkeypatch,
):
    from fpvs_studio.gui.updater_window import _show_startup_error

    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: shown.append(box))
    error = PermissionError(errno.EACCES, "Permission denied", "C:/Studio/installer.exe")
    _show_startup_error(error)
    assert len(shown) == 1
    box = shown[0]
    qtbot.addWidget(box)
    primary = box.text() + " " + box.informativeText()
    assert "[Errno" not in primary
    assert "full installer" in box.informativeText()
    assert str(error) in box.detailedText()


def test_exception_popup_without_explicit_buttons_keeps_ok_and_escape(qtbot, popups):
    reporter, requests = popups
    box = widget_message_box()
    qtbot.addWidget(box)
    box.setIcon(QMessageBox.Icon.Critical)
    box.setText("Unable to import")
    box.setDetailedText("Original traceback")
    reporter.decorate(box)
    assert box.standardButtons() & QMessageBox.StandardButton.Ok
    box.show()
    qtbot.waitExposed(box)
    qtbot.keyClick(box, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: not box.isVisible())
    assert requests == []


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("expanded", [False, True])
def test_long_error_button_and_details_fit_without_clipping(qtbot, popups, background, expanded):
    reporter, _requests = popups
    box = widget_message_box(
        QMessageBox.Icon.Critical,
        "Import FPVS Studio Project Error",
        "Unable to import project bundle",
        QMessageBox.StandardButton.Ok,
    )
    qtbot.addWidget(box)
    palette = box.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    box.setPalette(palette)
    error = PermissionError(errno.EACCES, "denied", "C:/" + "long study folder/" * 20)
    box.setDetailedText(str(error))
    reporter.decorate(box, error=error)
    reporter.decorate(box, error=error)
    box.show()
    assert len(box.findChildren(QPushButton, "report_error_button")) == 1
    if expanded:
        details_button = next(button for button in box.buttons() if "Details" in button.text())
        details_button.click()
    QApplication.processEvents()
    assert_visible_children_within_parent(box)
    button = box.findChild(QPushButton, "report_error_button")
    assert button.width() >= button.fontMetrics().horizontalAdvance(button.text())
    assert box.width() <= box.screen().availableGeometry().width()


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("expanded", [False, True])
@pytest.mark.parametrize("representation", ["cause_chain", "serialized_details"])
def test_parallel_driver_prompt_preserves_details_and_fits(
    qtbot, popups, background, expanded, representation,
):
    reporter, requests = popups
    driver_message = (
        "An already installed, running InpOut driver is required for native LPT output "
        "(Windows error 5). Studio does not install or start kernel drivers."
    )
    if representation == "cause_chain":
        driver_message = "Driver device unavailable: [WinError 5] Access is denied."
    driver_error = ParallelPortDriverUnavailableError(driver_message)
    initialization_error = ParallelPortError("Unable to initialize parallel-port output")
    initialization_error.__cause__ = driver_error
    error = RuntimeError("Trigger preflight failed before launch")
    error.__cause__ = initialization_error
    details = f"Parallel-port initialization failed. Details: {driver_message}"
    box = widget_message_box(
        QMessageBox.Icon.Critical, "Launch Error", str(error), QMessageBox.StandardButton.Ok,
    )
    qtbot.addWidget(box)
    palette = box.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    box.setPalette(palette)
    box.setDetailedText(details)
    reporter.decorate(box, error=error if representation == "cause_chain" else None)
    assert box.text() == "FPVS Studio couldn't access the parallel-port driver."
    assert box.informativeText() == (
        "Ensure the drivers for your parallel-port interface and a compatible InpOut driver "
        "are installed and running. Close any other app using the parallel port, then retry. "
        "Studio does not install drivers."
    )
    assert details in box.detailedText()
    assert driver_message in box.detailedText()
    box.resize(580, box.sizeHint().height())
    box.show()
    details_button = next(button for button in box.buttons() if "Details" in button.text())
    if expanded:
        details_button.click()
    QApplication.processEvents()
    assert details_button.isVisible()
    assert_visible_children_within_parent(box)
    if sys.platform == "darwin":
        # QMessageBox chooses its content width on Mac even in widget mode.
        assert box.width() >= box.minimumSizeHint().width()
    else:
        assert box.width() >= 580
    assert box.width() <= box.screen().availableGeometry().width()
    for label in box.findChildren(QLabel):
        if not label.isVisible() or not label.text():
            continue
        if label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width())
        else:
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
    report_button = box.findChild(QPushButton, "report_error_button")
    assert report_button is not None and report_button.isVisible()
    for button in (report_button, details_button, box.button(QMessageBox.StandardButton.Ok)):
        assert button is not None
        assert button.width() >= button.sizeHint().width()
    qtbot.waitExposed(box)
    qtbot.keyClick(box, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: not box.isVisible())
    assert requests == []


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("serialized", [False, True])
def test_triggerbox_error_keeps_plain_guidance_and_fits(qtbot, popups, background, serialized):
    reporter, requests = popups
    message = triggerbox_port_error_message("COM1234567890", "[WinError 5] Access is denied")
    message += " Details: [WinError 5] Access is denied"
    hardware_error = BrainProductsTriggerBoxError(message)
    hardware_error.__cause__ = PermissionError(errno.EACCES, "Access is denied")
    box = widget_message_box(
        QMessageBox.Icon.Critical, "Launch Error", message, QMessageBox.StandardButton.Ok,
    )
    qtbot.addWidget(box)
    palette = box.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    box.setPalette(palette)
    reporter.decorate(box, error=None if serialized else hardware_error)
    assert box.text() == "The COM1234567890 port is occupied or access was denied."
    assert "Fully exit the TriggerBox software" in box.informativeText()
    assert "Configuration/Test IO" in box.informativeText()
    assert "Pressing Stop can leave the port occupied" in box.informativeText()
    assert "file or folder" not in box.text()
    assert "WinError 5" not in box.informativeText()
    assert message in box.detailedText()
    box.resize(580, box.sizeHint().height())
    box.show()
    QApplication.processEvents()
    assert_visible_children_within_parent(box)
    assert box.width() <= box.screen().availableGeometry().width()
    for label in box.findChildren(QLabel):
        if label.isVisible() and label.text():
            if label.wordWrap():
                assert label.height() >= label.heightForWidth(label.width())
            else:
                assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
    box.close()
    assert requests == []


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("serialized", [False, True])
@pytest.mark.parametrize("operation,failure", [
    ("open", PermissionError(errno.EACCES, "Access is denied")),
    ("open", FileNotFoundError(errno.ENOENT, "Missing device")),
    ("open", ValueError("Cannot configure port")),
    ("write", TimeoutError("Write timed out")),
])
def test_biosemi_error_keeps_specific_guidance_and_fits(
    qtbot, popups, background, serialized, operation, failure,
):
    reporter, requests = popups
    port = "COM1234567890"
    plain = (biosemi_port_error_message(port, failure) if operation == "open" else
             biosemi_write_error_message(port, failure))
    message = f"{plain} Details: {failure!r}"
    hardware_error = SerialBackendError(message)
    hardware_error.__cause__ = failure
    box = widget_message_box(
        QMessageBox.Icon.Critical, "Launch Error", message, QMessageBox.StandardButton.Ok,
    )
    qtbot.addWidget(box)
    palette = box.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    box.setPalette(palette)
    reporter.decorate(box, error=None if serialized else hardware_error)
    summary, _, advice = plain.partition(". ")
    assert box.text() == summary + "."
    assert box.informativeText() == advice
    assert "TriggerBox" not in box.informativeText()
    assert "BrainVision" not in box.informativeText()
    assert "file or folder" not in box.text()
    assert "Error(" not in box.informativeText()
    assert message in box.detailedText()
    box.resize(580, box.sizeHint().height())
    box.show()
    QApplication.processEvents()
    assert_visible_children_within_parent(box)
    assert box.width() <= box.screen().availableGeometry().width()
    for label in box.findChildren(QLabel):
        if label.isVisible() and label.text():
            if label.wordWrap():
                assert label.height() >= label.heightForWidth(label.width())
            else:
                assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
    box.close()
    assert requests == []


@pytest.mark.parametrize("message", [
    "Unable to open BioSemi serial port COM3: access denied.",
    "Trigger preflight failed for Brain Products TriggerBox on COM7: port unavailable.",
])
def test_other_recording_errors_do_not_request_parallel_driver_installation(qtbot, popups, message):
    reporter, requests = popups
    box = widget_message_box(
        QMessageBox.Icon.Critical, "Launch Error", message, QMessageBox.StandardButton.Ok,
    )
    qtbot.addWidget(box)
    error = RuntimeError(message)
    reporter.decorate(box, error=error)
    assert "InpOut" not in box.text() + box.informativeText()
    assert "install drivers" not in box.informativeText()
    assert message in box.detailedText()
    assert requests == []


@pytest.mark.skipif(sys.platform != "darwin", reason="Native Cocoa alert contract")
def test_native_mac_alert_keeps_reporting_and_dismissal(qtbot, popups):
    _reporter, requests = popups
    box = QMessageBox(
        QMessageBox.Icon.Critical, "Import Error", "Unable to import project bundle",
        QMessageBox.StandardButton.Ok,
    )
    qtbot.addWidget(box)
    assert not box.testOption(QMessageBox.Option.DontUseNativeDialog)
    expected_title = box.windowTitle()
    box.setDetailedText("PermissionError: synthetic Mac import failure")
    box.show()
    report = box.findChild(QPushButton, "report_error_button")
    assert report is not None
    report.click()
    qtbot.waitUntil(lambda: len(requests) == 1)
    assert not box.isVisible()
    assert requests[0][0] == expected_title
    assert "synthetic Mac import failure" in requests[0][1]
