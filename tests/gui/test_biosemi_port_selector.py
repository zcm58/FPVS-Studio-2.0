"""Visible BioSemi port selection checks using held jobs and fake serial services."""

from __future__ import annotations

from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QLabel
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.core.models import ProjectRecordingSettings
from fpvs_studio.gui import biosemi_port_selector as selector_module
from fpvs_studio.gui import recording_dialog as dialog_module
from fpvs_studio.gui.recording_dialog import RecordingSetupDialog
from fpvs_studio.gui.update_lifecycle import UpdateTaskResult
from fpvs_studio.triggers.serial_port_access import SerialPortAccessResult, SerialPortInfo


class _HeldJob(QObject):
    finished = Signal(object)

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def finish(self, value=(), *, error=None, cancelled=False):
        self.finished.emit(UpdateTaskResult(value=value, error=error, cancelled=cancelled))


@pytest.fixture(autouse=True)
def serial_jobs(monkeypatch):
    """Never enumerate hardware, open a port or start a worker from these tests."""

    jobs = []

    def start_task(callback, **_kwargs):
        job = _HeldJob(callback)
        jobs.append(job)
        return job

    lifecycle = SimpleNamespace(start_task=start_task)
    enumeration = Mock(return_value=(SerialPortInfo("COM193", "USB Serial Converter"),))
    access = Mock(return_value=SerialPortAccessResult("COM193", True))
    monkeypatch.setattr(selector_module, "update_lifecycle", lambda: lifecycle)
    monkeypatch.setattr(selector_module, "enumerate_serial_ports", enumeration)
    monkeypatch.setattr(selector_module, "check_serial_port_access", access)
    monkeypatch.setattr(dialog_module, "update_lifecycle", lambda: lifecycle)
    monkeypatch.setattr(dialog_module, "discover_triggerbox_ports", Mock(return_value=()))
    return SimpleNamespace(jobs=jobs, enumeration=enumeration, access=access)


def _dialog(qtbot, *, backend="serial", port="COM3", baudrate=115200, computer_default=False):
    configuration = {"recording_backend": backend}
    if backend == "brainproducts_triggerbox":
        configuration.update(
            brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
        )
    dialog = RecordingSetupDialog(
        configuration, computer_default=computer_default,
        biosemi_serial_port=port, biosemi_serial_baudrate=baudrate,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    return dialog


def _finish_list(serial_jobs, *ports):
    values = tuple(SerialPortInfo(port, "USB Serial Converter") for port in ports)
    serial_jobs.jobs[-1].finish(values)
    QApplication.processEvents()


def _assert_geometry(dialog):
    assert (dialog.width(), dialog.height()) == (700, 640)
    assert_visible_children_within_parent(dialog)
    for label in dialog.findChildren(QLabel):
        if not label.isVisible():
            continue
        if label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width())
        else:
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
    selector = dialog.biosemi_port_selector
    controls = (selector.combo, selector.refresh_button, selector.check_button)
    for index, first in enumerate(controls):
        for second in controls[index + 1:]:
            assert not first.geometry().intersects(second.geometry())
    for button in controls[1:]:
        assert button.width() >= button.sizeHint().width()
    assert selector.combo.width() >= (
        selector.combo.fontMetrics().horizontalAdvance(selector.combo.currentText()) + 32
    )


@pytest.mark.parametrize("port", [None, "COM3", "COM193", "/dev/ttyUSB0"])
@pytest.mark.parametrize("listed", [(), ("COM193",), ("COM2", "COM193")])
def test_metadata_keeps_default_and_explicit_port_without_identifying_hardware(
    qtbot, serial_jobs, port, listed,
):
    dialog = _dialog(qtbot, port=port)
    selector = dialog.biosemi_port_selector
    assert len(serial_jobs.jobs) == 1
    assert not selector.refresh_button.isEnabled()
    assert not selector.check_button.isEnabled()
    cancel = Event()
    serial_jobs.jobs[0].callback(None, cancel)
    serial_jobs.enumeration.assert_called_once_with(cancel_event=cancel)
    serial_jobs.access.assert_not_called()
    _finish_list(serial_jobs, *listed)

    expected = port or "COM3"
    assert selector.port == expected
    assert [selector.combo.itemText(index)
            for index in range(selector.combo.count())] == list(listed)
    assert dialog.apply_button.isEnabled()
    assert selector.refresh_button.isEnabled()
    assert selector.check_button.isEnabled()
    if listed:
        assert selector.combo.itemData(0, Qt.ItemDataRole.ToolTipRole) == "USB Serial Converter"
        assert not selector.status_label.text()
    else:
        assert "No serial ports listed" in selector.status_label.text()
    assert "do not identify BioSemi" in selector.combo.toolTip()


def test_manual_edit_survives_pending_metadata_and_enumeration_failure(qtbot, serial_jobs):
    dialog = _dialog(qtbot)
    selector = dialog.biosemi_port_selector
    selector.edit.setText("COM42")
    _finish_list(serial_jobs, "COM193")
    assert selector.port == "COM42"

    selector.refresh_button.click()
    selector.edit.setText("COM64")
    serial_jobs.jobs[-1].finish(error=OSError("Synthetic enumeration denied"))
    assert selector.port == "COM64"
    assert "Could not list ports" in selector.status_label.text()
    assert "Synthetic enumeration denied" in selector.status_label.toolTip()
    assert selector.status_label.accessibleDescription() == selector.status_label.toolTip()
    assert dialog.apply_button.isEnabled()


@pytest.mark.parametrize("baudrate", [115200, 57600])
@pytest.mark.parametrize("accessible", [True, False])
def test_check_opens_only_selected_port_and_reports_its_result(
    qtbot, serial_jobs, baudrate, accessible,
):
    dialog = _dialog(qtbot, port="COM193", baudrate=baudrate)
    selector = dialog.biosemi_port_selector
    _finish_list(serial_jobs, "COM2", "COM193")
    selector.check_button.click()
    job = serial_jobs.jobs[-1]
    cancel = Event()
    job.callback(None, cancel)
    serial_jobs.access.assert_called_once_with("COM193", baudrate=baudrate, cancel_event=cancel)
    assert serial_jobs.enumeration.call_count == 0  # Held metadata was supplied, not executed.
    assert "Checking COM193" in selector.status_label.text()
    assert not selector.refresh_button.isEnabled()
    assert not selector.check_button.isEnabled()
    error = "[WinError 5] Access denied to COM193" if not accessible else ""
    job.finish(SerialPortAccessResult("COM193", accessible, error))

    state = "Port accessible" if accessible else "Port unavailable"
    assert f"COM193: {state}" in selector.status_label.text()
    assert selector.port == "COM193"
    assert selector.refresh_button.isEnabled() and selector.check_button.isEnabled()
    assert "No marker bytes" in selector.check_button.toolTip()
    if accessible:
        assert "identity and marker receipt are unverified" in selector.status_label.toolTip()
    else:
        assert error in selector.status_label.toolTip()
        assert error in selector.status_label.accessibleDescription()


@pytest.mark.parametrize("restore_original", [False, True])
def test_editing_during_check_cancels_it_and_ignores_even_matching_late_result(
    qtbot, serial_jobs, restore_original,
):
    dialog = _dialog(qtbot, port="COM193")
    selector = dialog.biosemi_port_selector
    _finish_list(serial_jobs, "COM193")
    selector.check_button.click()
    job = serial_jobs.jobs[-1]
    selector.edit.setText("COM42")
    if restore_original:
        selector.edit.setText("COM193")
    assert job.cancelled
    assert not selector.status_label.text()
    job.finish(SerialPortAccessResult("COM193", True))
    assert selector.port == ("COM193" if restore_original else "COM42")
    assert not selector.status_label.text()
    assert selector.check_button.isEnabled()


def test_retry_clears_previous_error_and_supports_cancelled_check(qtbot, serial_jobs):
    dialog = _dialog(qtbot, port="COM193")
    selector = dialog.biosemi_port_selector
    _finish_list(serial_jobs, "COM193")
    selector.check_button.click()
    serial_jobs.jobs[-1].finish(error=RuntimeError("Synthetic missing driver"))
    assert "Synthetic missing driver" in selector.status_label.toolTip()
    selector.check_button.click()
    assert "Checking COM193" in selector.status_label.text()
    assert selector.status_label.toolTip() == ""
    assert selector.status_label.accessibleDescription() == ""
    serial_jobs.jobs[-1].finish(cancelled=True)
    assert "cancelled" in selector.status_label.text()
    assert selector.check_button.isEnabled()


def test_dismissed_scan_cannot_replace_reopened_request(qtbot, serial_jobs):
    dialog = _dialog(qtbot, port="COM42")
    selector = dialog.biosemi_port_selector
    old = serial_jobs.jobs[-1]
    dialog.reject()
    assert old.cancelled
    old.finish((SerialPortInfo("COM1", "Old result"),))
    assert selector.port == "COM42"
    dialog.show()
    QApplication.processEvents()
    current = serial_jobs.jobs[-1]
    assert current is not old
    old.finish((SerialPortInfo("COM2", "Late old result"),))
    assert "Refreshing" in selector.status_label.text()
    current.finish((SerialPortInfo("COM193", "Current result"),))
    assert selector.port == "COM42"
    assert [selector.combo.itemText(index) for index in range(selector.combo.count())] == ["COM193"]


def test_device_change_cancels_check_and_does_not_claim_access_on_return(qtbot, serial_jobs):
    dialog = _dialog(qtbot, port="COM193")
    selector = dialog.biosemi_port_selector
    _finish_list(serial_jobs, "COM193")
    selector.check_button.click()
    job = serial_jobs.jobs[-1]
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("unicorn_udp"))
    assert job.cancelled
    assert not selector.isVisible()
    job.finish(SerialPortAccessResult("COM193", True))
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("serial"))
    assert selector.isVisible()
    assert selector.port == "COM193"
    assert not selector.status_label.text()
    assert selector.check_button.isEnabled()


@pytest.mark.parametrize("backend", ["serial", "biosemi_active_three"])
def test_apply_stages_port_and_cancel_preserves_original(qtbot, serial_jobs, backend):
    dialog = _dialog(qtbot, backend=backend, port="COM42")
    selector = dialog.biosemi_port_selector
    selector.edit.setText("COM193")
    dialog.reject()
    assert dialog.biosemi_serial_port == "COM42"
    assert dialog.configuration == {"recording_backend": backend}
    assert serial_jobs.jobs[0].cancelled

    dialog.show()
    QApplication.processEvents()
    dialog.apply_button.click()
    assert dialog.result() == int(QDialog.DialogCode.Accepted)
    assert dialog.biosemi_serial_port == "COM193"
    assert "serial_port" not in dialog.configuration
    ProjectRecordingSettings.model_validate(dialog.configuration)
    assert serial_jobs.jobs[-1].cancelled


def test_blank_port_blocks_apply_and_check_but_not_other_devices(qtbot, serial_jobs):
    dialog = _dialog(qtbot, port="COM42")
    selector = dialog.biosemi_port_selector
    _finish_list(serial_jobs, "COM193")
    selector.edit.setText("   ")
    assert not dialog.apply_button.isEnabled()
    assert not selector.check_button.isEnabled()
    assert "Enter the BioSemi" in dialog.error_label.text()
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("unicorn_udp"))
    assert not selector.isVisible()
    assert dialog.apply_button.isEnabled()
    dialog.apply_button.click()
    assert dialog.biosemi_serial_port == "COM42"


@pytest.mark.parametrize("backend", ["serial", "biosemi_active_three", "unicorn_udp"])
def test_computer_defaults_hide_project_only_port_controls(qtbot, serial_jobs, backend):
    dialog = _dialog(qtbot, backend=backend, computer_default=True, port="COM42")
    assert not dialog.biosemi_port_label.isVisible()
    assert not dialog.biosemi_port_selector.isVisible()
    assert serial_jobs.jobs == []
    dialog.apply_button.click()
    assert "serial_port" not in dialog.configuration
    assert dialog.biosemi_serial_port == "COM42"


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("state", ["list_busy", "empty", "list_error", "check_busy",
                                   "available", "unavailable", "invalid", "manual"])
def test_biosemi_geometry_fits_at_minimum_size_in_each_state(qtbot, serial_jobs, background, state):
    dialog = _dialog(qtbot, backend="biosemi_active_three", port="COM193")
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    selector = dialog.biosemi_port_selector
    if state == "list_error":
        serial_jobs.jobs[-1].finish(error=OSError(
            "Synthetic serial driver metadata is unavailable",
        ))
    elif state != "list_busy":
        ports = () if state == "empty" else ("COM2", "COM193")
        _finish_list(serial_jobs, *ports)
        if state in {"check_busy", "available", "unavailable"}:
            selector.check_button.click()
            if state != "check_busy":
                available = state == "available"
                serial_jobs.jobs[-1].finish(SerialPortAccessResult(
                    "COM193", available,
                    "[WinError 5] Access denied: another program owns the configured USB interface"
                    if not available else "",
                ))
        elif state == "invalid":
            selector.edit.setText(" ")
        elif state == "manual":
            selector.edit.setText("COM12345")
    QApplication.processEvents()
    _assert_geometry(dialog)
