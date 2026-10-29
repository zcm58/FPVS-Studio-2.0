"""Visible opt-in popup reporting tests; callbacks never use the live service."""

from __future__ import annotations

import errno

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.gui.error_dialogs import REPORT_BUTTON_TEXT, ErrorDialogReporter
from fpvs_studio.triggers.parallel_backend import (
    ParallelPortDriverUnavailableError,
    ParallelPortError,
)


@pytest.fixture
def popups(qapp):
    requests = []
    previous = qapp.findChild(ErrorDialogReporter, "fpvs_error_dialog_reporter")
    if previous is not None:
        qapp.removeEventFilter(previous)
    reporter = ErrorDialogReporter(qapp, report=lambda *args: requests.append(args))
    yield reporter, requests
    qapp.removeEventFilter(reporter)
    reporter.deleteLater()
    if previous is not None:
        qapp.installEventFilter(previous)


@pytest.mark.parametrize("icon", [QMessageBox.Icon.Critical, QMessageBox.Icon.Warning])
def test_report_button_automatically_covers_static_error_popups(qtbot, popups, icon):
    _reporter, requests = popups
    box = QMessageBox(
        icon, "Import Error", "Unable to import project bundle", QMessageBox.StandardButton.Ok
    )
    qtbot.addWidget(box)
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
    assert title == "Import Error"
    assert "WinError 5" in diagnostic
    assert "couldn't access" in message


def test_confirmations_information_and_normal_dismissal_do_not_report(qtbot, popups):
    _reporter, requests = popups
    for icon, buttons in (
        (QMessageBox.Icon.Information, QMessageBox.StandardButton.Ok),
        (QMessageBox.Icon.Warning, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No),
    ):
        box = QMessageBox(icon, "Review", "Continue?", buttons)
        qtbot.addWidget(box)
        box.show()
        assert box.findChild(QPushButton, "report_error_button") is None
        box.close()
    box = QMessageBox(
        QMessageBox.Icon.Critical, "Error", "Unable to save", QMessageBox.StandardButton.Ok
    )
    qtbot.addWidget(box)
    box.show()
    qtbot.keyClick(box, Qt.Key.Key_Return)
    QApplication.processEvents()
    assert not box.isVisible()
    assert requests == []


def test_exception_popup_without_explicit_buttons_keeps_ok_and_escape(qtbot, popups):
    reporter, requests = popups
    box = QMessageBox()
    qtbot.addWidget(box)
    box.setIcon(QMessageBox.Icon.Critical)
    box.setText("Unable to import")
    box.setDetailedText("Original traceback")
    reporter.decorate(box)
    assert box.standardButtons() & QMessageBox.StandardButton.Ok
    box.show()
    qtbot.keyClick(box, Qt.Key.Key_Escape)
    QApplication.processEvents()
    assert not box.isVisible()
    assert requests == []


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("expanded", [False, True])
def test_long_error_button_and_details_fit_without_clipping(qtbot, popups, background, expanded):
    reporter, _requests = popups
    box = QMessageBox(
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
    box = QMessageBox(
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
    qtbot.keyClick(box, Qt.Key.Key_Escape)
    QApplication.processEvents()
    assert not box.isVisible()
    assert requests == []


@pytest.mark.parametrize("message", [
    "Unable to open BioSemi serial port COM3: access denied.",
    "Trigger preflight failed for Brain Products TriggerBox on COM7: port unavailable.",
])
def test_other_recording_errors_do_not_request_parallel_driver_installation(qtbot, popups, message):
    reporter, requests = popups
    box = QMessageBox(
        QMessageBox.Icon.Critical, "Launch Error", message, QMessageBox.StandardButton.Ok,
    )
    qtbot.addWidget(box)
    error = RuntimeError(message)
    reporter.decorate(box, error=error)
    assert "InpOut" not in box.text() + box.informativeText()
    assert "install drivers" not in box.informativeText()
    assert message in box.detailedText()
    assert requests == []
