"""Registered visible Qt checks for local recording setup and launch guards."""

from __future__ import annotations

from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QColor, QPalette, QTextDocument
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QLabel, QScrollArea
from tests.gui.helpers import (
    ImmediateProgressTask,
    assert_visible_children_within_parent,
    open_created_project,
    prepare_compile_ready_project,
    select_settings_category,
)

from fpvs_studio.core.enums import ExperimentCategory, RunMode
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.models import ProjectRecordingSettings
from fpvs_studio.gui import home_page as home_page_module
from fpvs_studio.gui import parallel_port_selector as parallel_port_selector_module
from fpvs_studio.gui import recording_dialog as recording_dialog_module
from fpvs_studio.gui import settings_dialog as settings_dialog_module
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.document_support import DocumentError
from fpvs_studio.gui.recording_dialog import RecordingSetupDialog
from fpvs_studio.gui.run_page import ParticipantLaunchDetails, RunPage
from fpvs_studio.gui.settings_dialog import AppSettingsDialog
from fpvs_studio.gui.update_lifecycle import UpdateTaskResult
from fpvs_studio.runtime import launcher as runtime_launcher
from fpvs_studio.runtime.recording import UNICORN_VALIDATION_NOTE
from fpvs_studio.runtime.unicorn_recorder import (
    RecorderReadinessError,
    _require_recording_snapshot,
)
from fpvs_studio.triggers.brainproducts_discovery import (
    TriggerBoxDiscoveryError,
    TriggerBoxPortCandidate,
)
from fpvs_studio.triggers.brainproducts_errors import triggerbox_port_error_message
from fpvs_studio.triggers.parallel_discovery import ParallelPortCandidate


class _HeldPortDetectionJob(QObject):
    finished = Signal(object)

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def finish(self, *, candidates=(), error=None, cancelled=False):
        self.finished.emit(UpdateTaskResult(
            value=tuple(candidates), error=error, cancelled=cancelled,
        ))


@pytest.fixture(autouse=True)
def port_detection_jobs(monkeypatch):
    """Hold every discovery job without enumerating ports or starting a thread."""

    jobs = []

    def start_task(callback, **_kwargs):
        job = _HeldPortDetectionJob(callback)
        jobs.append(job)
        return job

    lifecycle = SimpleNamespace(is_shutting_down=False, start_task=start_task)
    monkeypatch.setattr(recording_dialog_module, "update_lifecycle", lambda: lifecycle)
    monkeypatch.setattr(parallel_port_selector_module, "update_lifecycle", lambda: lifecycle)
    monkeypatch.setattr(
        recording_dialog_module, "discover_triggerbox_ports",
        Mock(side_effect=AssertionError("GUI tests must not enumerate real serial ports")),
    )
    monkeypatch.setattr(
        parallel_port_selector_module, "discover_parallel_ports",
        Mock(side_effect=AssertionError("GUI tests must not enumerate real parallel ports")),
    )
    return jobs


@pytest.fixture(autouse=True)
def recording_errors(monkeypatch):
    """Capture standard error popups without entering a second modal event loop."""
    popup = Mock()
    for module in (recording_dialog_module, parallel_port_selector_module, settings_dialog_module):
        monkeypatch.setattr(module, "_show_error_dialog", popup)
    return popup


def _assert_invalid_apply(dialog, recording_errors):
    recording_errors.reset_mock()
    dialog.apply_button.click()
    assert dialog.result() != int(QDialog.DialogCode.Accepted)
    assert recording_errors.call_args.args[:2] == (dialog, "Recording Setup Error")
    recording_errors.assert_called_once()


def _detection_error_message(dialog, recording_errors):
    assert not dialog.detection_status_label.text()
    assert recording_errors.call_args.args[:2] == (dialog, "TriggerBox Detection Error")
    return recording_errors.call_args.kwargs["message"]


def _select_triggerbox_timing(dialog, *, amplifier="actichamp", sampling_rate=500):
    dialog.brainproducts_amplifier_combo.setCurrentIndex(
        dialog.brainproducts_amplifier_combo.findData(amplifier),
    )
    dialog.brainproducts_sampling_rate_combo.setCurrentIndex(
        dialog.brainproducts_sampling_rate_combo.findData(sampling_rate),
    )


def _triggerbox_configuration(**overrides):
    return {
        "recording_backend": "brainproducts_triggerbox",
        "brainproducts_serial_port": "COM3",
        "brainproducts_pulse_width_ms": 10,
        "brainproducts_amplifier": "actichamp",
        "brainproducts_sampling_rate_hz": 500,
        **overrides,
    }


def _parallel_configuration(**overrides):
    return {
        **_triggerbox_configuration(),
        "recording_backend": "brainproducts_parallel",
        "brainproducts_parallel_address": 0x378,
        **overrides,
    }


def _unconfigured_triggerbox(**overrides):
    return _triggerbox_configuration(**{
        "brainproducts_amplifier": None, "brainproducts_sampling_rate_hz": None, **overrides,
    })


def _label_plain_text(label: QLabel) -> str:
    if label.textFormat() != Qt.TextFormat.RichText:
        return label.text()
    text = QTextDocument()
    text.setHtml(label.text())
    return text.toPlainText()


def _assert_labels_fit(widget) -> None:
    assert_visible_children_within_parent(
        widget, allow_scroll_content=isinstance(widget, AppSettingsDialog),
    )
    for label in widget.findChildren(QLabel):
        if not label.isVisible():
            continue
        if label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width())
        else:
            assert label.width() >= label.fontMetrics().horizontalAdvance(_label_plain_text(label))
    for checkbox in widget.findChildren(QCheckBox):
        if checkbox.isVisible():
            assert checkbox.width() >= checkbox.sizeHint().width()


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("backend, port", [
    (None, 1000), ("serial", 1000), ("unicorn_udp", 65535),
    ("biosemi_active_three", 1000), ("brainproducts_triggerbox", 1000),
    ("brainproducts_parallel", 1000),
    ("unicorn_udp", "broken saved port"), ("unknown old selection", 1000),
])
def test_recording_setup_geometry_and_validation(
    qtbot, background, backend, port, recording_errors,
):
    configuration = {"recording_backend": backend, "unicorn_udp_port": port}
    if backend in ("brainproducts_triggerbox", "brainproducts_parallel"):
        configuration.update(
            brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
        )
    if backend == "brainproducts_parallel":
        configuration["brainproducts_parallel_address"] = 0x378
    dialog = RecordingSetupDialog(configuration)
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.show()
    QApplication.processEvents()
    assert (dialog.width(), dialog.height()) == (700, 640)
    _assert_labels_fit(dialog)
    assert dialog.backend_combo.width() >= (
        dialog.backend_combo.fontMetrics().horizontalAdvance(dialog.backend_combo.currentText())
        + 32
    )
    if backend == "unicorn_udp":
        assert UNICORN_VALIDATION_NOTE in dialog.guidance_label.text()
        assert dialog.guidance_label.toolTip() == UNICORN_VALIDATION_NOTE
        assert "unavailable" not in dialog.guidance_label.text()
        assert "open and recording" in dialog.guidance_label.text()
        assert "raw BDF or BDF+" in dialog.guidance_label.text()
        assert "operator responsibilities" in dialog.guidance_label.text()
        if not isinstance(port, int):
            _assert_invalid_apply(dialog, recording_errors)
    elif backend == "brainproducts_triggerbox":
        assert dialog.backend_combo.currentText() == (
            "Brain Products / BrainVision (TriggerBox/Plus)"
        )
        assert dialog.brainproducts_port_edit.isVisible()
        assert dialog.brainproducts_pulse_edit.isVisible()
        assert "Install TriggerBox software/drivers on this PC" in dialog.guidance_label.text()
        assert "Fully exit Configuration/Test IO before launch" in dialog.guidance_label.text()
        assert "keep them closed" in dialog.guidance_label.text()
        assert "Stop can leave the COM port occupied" in dialog.guidance_label.text()
        assert "Start recording in BrainVision Recorder" in dialog.guidance_label.text()
        assert "keep it recording" in dialog.guidance_label.text()
        assert "high-active" in dialog.guidance_label.toolTip()
        assert "eight output switches to PC" in dialog.guidance_label.toolTip()
        assert "delay/jitter <1 ms" in dialog.guidance_label.toolTip()
        assert "no fixed timing correction" in dialog.guidance_label.toolTip()
        assert dialog.apply_button.isEnabled()
    elif backend == "biosemi_active_three":
        assert dialog.backend_combo.currentText() == "BioSemi ActiveThree"
        assert "USB Trigger Interface" in dialog.guidance_label.toolTip()
        assert dialog.apply_button.isEnabled()
    elif backend == "brainproducts_parallel":
        assert dialog.backend_combo.currentText() == (
            "Brain Products / BrainVision (Parallel port)"
        )
        assert dialog.brainproducts_parallel_edit.isVisible()
        assert dialog.brainproducts_parallel_edit.text() == "0x378"
        assert not dialog.brainproducts_port_edit.isVisible()
        assert not dialog.brainproducts_amplifier_combo.isVisible()
        assert dialog.apply_button.isEnabled()
    elif backend not in (None, "serial"):
        assert dialog.backend_combo.currentData() == backend
        assert backend in dialog.backend_combo.toolTip()
        _assert_invalid_apply(dialog, recording_errors)


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("amplifier, recorder", [
    ("actichamp", "BrainVision Recorder 1 or 2"), ("liveamp", "BrainVision Recorder 1"),
])
def test_triggerbox_amplifier_specific_recording_guidance_fits(
    qtbot, background, amplifier, recorder, port_detection_jobs, recording_errors,
):
    dialog = RecordingSetupDialog(_triggerbox_configuration(
        brainproducts_amplifier=amplifier, brainproducts_serial_port="COM4",
    ))
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.show()
    port_detection_jobs[0].finish()
    QApplication.processEvents()
    assert (dialog.width(), dialog.height()) == (700, 640)
    assert recorder in dialog.guidance_label.text()
    assert "Fully exit Configuration/Test IO" in dialog.guidance_label.text()
    assert "Stop can leave the COM port occupied" in dialog.guidance_label.text()
    assert dialog.apply_button.isEnabled()
    if amplifier == "liveamp":
        assert "wired 8-bit STE" in dialog.brainproducts_amplifier_combo.currentText()
        assert "wired eight-bit STE or STE compact" in dialog.guidance_label.text()
        assert "exclude the native jack inputs" in dialog.guidance_label.toolTip()
        assert "first eight rows blindly" in dialog.guidance_label.toolTip()
        assert "1.27.0001" in dialog.guidance_label.toolTip()
        assert "lower eight bits as high-active" not in dialog.guidance_label.toolTip()
    else:
        assert "Workspace Editor" in dialog.guidance_label.toolTip()
        assert "lower eight bits as high-active" in dialog.guidance_label.toolTip()
    assert dialog.guidance_label.accessibleDescription() == dialog.guidance_label.toolTip()
    _assert_labels_fit(dialog)
    dialog.brainproducts_pulse_edit.setText("1")
    QApplication.processEvents()
    _assert_invalid_apply(dialog, recording_errors)
    _assert_labels_fit(dialog)


def test_recording_setup_apply_and_keyboard_cancel(qtbot):
    original = {"recording_backend": None, "unicorn_udp_port": 1000}
    dialog = RecordingSetupDialog(original)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("unicorn_udp"))
    dialog.port_edit.setText("65535")
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.result() == int(QDialog.DialogCode.Rejected)
    assert dialog.configuration == original
    assert original["recording_backend"] is None
    dialog.show()
    dialog.apply_button.setFocus()
    qtbot.keyClick(dialog.apply_button, Qt.Key.Key_Space)
    assert dialog.result() == int(QDialog.DialogCode.Accepted)
    assert dialog.configuration == {
        "recording_backend": "unicorn_udp", "unicorn_udp_port": 65535,
        "brainproducts_serial_port": "COM3", "brainproducts_pulse_width_ms": 10,
        "brainproducts_parallel_address": None,
        "brainproducts_amplifier": None, "brainproducts_sampling_rate_hz": None,
    }


@pytest.mark.parametrize("address, rate, pulse, valid", [
    ("0x378", 500, 10, True), ("378", 500, 10, True), ("0xFFFF", 500, 10, True),
    ("", 500, 10, False), ("0x0", 500, 10, False), ("0x10000", 500, 10, False),
    ("not an address", 500, 10, False), ("0x378", None, 10, False),
    ("0x378", 777, 10, False), ("0x378", 100, 19, False),
    ("0x378", 100, 20, True),
])
def test_parallel_address_and_actichamp_timing_validation(
    qtbot, address, rate, pulse, valid, recording_errors,
):
    dialog = RecordingSetupDialog(_parallel_configuration(
        brainproducts_sampling_rate_hz=rate, brainproducts_pulse_width_ms=pulse,
    ))
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.brainproducts_parallel_edit.setText(address)
    QApplication.processEvents()
    assert dialog.backend_combo.currentText() == "Brain Products / BrainVision (Parallel port)"
    assert dialog.brainproducts_parallel_edit.isVisible()
    assert not dialog.brainproducts_port_edit.isVisible()
    assert not dialog.brainproducts_amplifier_combo.isVisible()
    assert dialog.brainproducts_sampling_rate_combo.isVisible()
    assert dialog.brainproducts_pulse_edit.isVisible()
    assert "actiCHamp" in dialog.guidance_label.toolTip()
    assert "InpOut driver installed and running" in dialog.guidance_label.toolTip()
    if valid:
        dialog.apply_button.click()
        assert dialog.configuration["brainproducts_parallel_address"] == int(address, 16)
        assert dialog.configuration["brainproducts_amplifier"] == "actichamp"
    else:
        _assert_invalid_apply(dialog, recording_errors)
    _assert_labels_fit(dialog)


def test_parallel_discovery_uses_only_metadata_and_retains_manual_address(
    qtbot, port_detection_jobs, monkeypatch,
):
    discovery = Mock(return_value=())
    monkeypatch.setattr(parallel_port_selector_module, "discover_parallel_ports", discovery)
    dialog = RecordingSetupDialog(_parallel_configuration(brainproducts_parallel_address=None))
    qtbot.addWidget(dialog)
    dialog.show()
    assert len(port_detection_jobs) == 1
    cancel = Event()
    assert port_detection_jobs[0].callback(None, cancel) == ()
    cancelled = discovery.call_args.kwargs["cancelled"]
    assert set(discovery.call_args.kwargs) == {"cancelled"}
    assert not cancelled()
    cancel.set()
    assert cancelled()
    assert "without loading a driver" in dialog.detect_parallel_ports_button.toolTip()
    candidate = ParallelPortCandidate("ECP Printer Port (LPT1)", 0x378, "ACPI\\PNP0401\\1")
    port_detection_jobs[0].finish(candidates=(candidate,))
    assert dialog.brainproducts_parallel_edit.text() == "0x378"
    dialog.brainproducts_parallel_edit.selectAll()
    qtbot.keyClicks(dialog.brainproducts_parallel_edit, "0xD010")
    dialog.detect_parallel_ports_button.click()
    port_detection_jobs[1].finish(candidates=(candidate,))
    assert dialog.brainproducts_parallel_edit.text() == "0xD010"
    dialog.apply_button.click()
    assert dialog.configuration["brainproducts_parallel_address"] == 0xD010


def test_parallel_discovery_requires_choice_for_multiple_or_missing_addresses(
    qtbot, port_detection_jobs, recording_errors,
):
    dialog = RecordingSetupDialog(_parallel_configuration(brainproducts_parallel_address=None))
    qtbot.addWidget(dialog)
    dialog.show()
    port_detection_jobs[0].finish(candidates=(
        ParallelPortCandidate("LPT1", 0x378, "first device"),
        ParallelPortCandidate("LPT2", 0xD010, "second device"),
    ))
    assert dialog.brainproducts_parallel_edit.text() == ""
    _assert_invalid_apply(dialog, recording_errors)
    assert "Several" in dialog.parallel_port_selector.status_label.text()
    dialog.brainproducts_parallel_combo.setCurrentIndex(1)
    assert dialog.parallel_port_selector.address == 0xD010
    assert dialog.apply_button.isEnabled()
    dialog.brainproducts_parallel_edit.clear()
    dialog.detect_parallel_ports_button.click()
    port_detection_jobs[1].finish(candidates=(ParallelPortCandidate("LPT3", None, "third device"),))
    assert dialog.brainproducts_parallel_edit.text() == ""
    assert "Device Manager > Resources" in dialog.parallel_port_selector.status_label.text()
    _assert_invalid_apply(dialog, recording_errors)


def test_parallel_manual_draft_survives_backend_switch_and_cancel(
    qtbot, port_detection_jobs, recording_errors,
):
    original = _parallel_configuration()
    dialog = RecordingSetupDialog(original)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.brainproducts_parallel_edit.selectAll()
    qtbot.keyClicks(dialog.brainproducts_parallel_edit, "0xD010")
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("unicorn_udp"))
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("brainproducts_parallel"))
    assert dialog.brainproducts_parallel_edit.text() == "0xD010"
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.configuration == original
    dialog.show()
    dialog.brainproducts_parallel_edit.selectAll()
    qtbot.keyClick(dialog.brainproducts_parallel_edit, Qt.Key.Key_Backspace)
    port_detection_jobs[-1].finish(candidates=(
        ParallelPortCandidate("LPT1", 0x378, "detected device"),
    ))
    assert dialog.brainproducts_parallel_edit.text() == ""
    _assert_invalid_apply(dialog, recording_errors)


@pytest.mark.parametrize("finish", ["cancel", "switch"])
def test_parallel_discovery_cancel_and_backend_switch_ignore_stale_results(
    qtbot, port_detection_jobs, finish,
):
    original = _parallel_configuration(brainproducts_parallel_address=None)
    dialog = RecordingSetupDialog(original)
    qtbot.addWidget(dialog)
    dialog.show()
    job = port_detection_jobs[0]
    if finish == "cancel":
        qtbot.keyClick(dialog, Qt.Key.Key_Escape)
        assert dialog.configuration == original
    else:
        dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("unicorn_udp"))
        dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("brainproducts_parallel"))
        assert len(port_detection_jobs) == 2
    assert job.cancelled
    job.finish(candidates=(ParallelPortCandidate("LPT1", 0x378, "stale device"),))
    assert dialog.brainproducts_parallel_edit.text() == ""
    if finish == "switch":
        assert dialog.parallel_port_selector._job is port_detection_jobs[1]
        port_detection_jobs[1].finish(candidates=(
            ParallelPortCandidate("LPT2", 0xD010, "current device"),
        ))
        assert dialog.brainproducts_parallel_edit.text() == "0xD010"


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("state", [
    "busy", "empty", "multiple", "missing", "error", "unique", "cancelled", "manual",
])
def test_parallel_discovery_states_fit_minimum_dialog(
    qtbot, port_detection_jobs, background, state, recording_errors,
):
    dialog = RecordingSetupDialog(_parallel_configuration(
        brainproducts_parallel_address=None,
        brainproducts_sampling_rate_hz=100, brainproducts_pulse_width_ms=20,
    ))
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.resize(700, 640)
    dialog.show()
    description = "PCI Express Multi-Mode ECP Parallel Port (LPT123) " * 8
    device_id = "PCI\\VEN_9710&DEV_9901&SUBSYS_2000A000\\VERY_LONG_DEVICE_INSTANCE " * 8
    candidate = ParallelPortCandidate(description, 0xD010, device_id)
    if state == "empty":
        port_detection_jobs[0].finish()
    elif state == "multiple":
        port_detection_jobs[0].finish(candidates=(
            candidate, ParallelPortCandidate("LPT2", 0x378, "second device"),
        ))
    elif state == "missing":
        port_detection_jobs[0].finish(candidates=(
            ParallelPortCandidate(description, None, device_id),
        ))
    elif state == "error":
        details = "Windows could not read the parallel-port device resources. " * 12
        port_detection_jobs[0].finish(error=RuntimeError(details))
        assert not dialog.parallel_port_selector.status_label.text()
        assert str(recording_errors.call_args.args[2]) == details
    elif state == "cancelled":
        port_detection_jobs[0].finish(cancelled=True)
    elif state == "unique":
        port_detection_jobs[0].finish(candidates=(candidate,))
    elif state == "manual":
        qtbot.keyClicks(dialog.brainproducts_parallel_edit, "0xFFFF")
        port_detection_jobs[0].finish(candidates=(candidate,))
        assert dialog.brainproducts_parallel_edit.text() == "0xFFFF"
    QApplication.processEvents()
    assert dialog.size().toTuple() == (700, 640)
    _assert_labels_fit(dialog)
    assert dialog.backend_combo.width() >= (
        dialog.backend_combo.fontMetrics().horizontalAdvance(dialog.backend_combo.currentText())
        + 32
    )
    if state in ("unique", "multiple", "missing", "manual"):
        assert description in dialog.parallel_port_selector.status_label.toolTip()
        assert device_id in dialog.parallel_port_selector.status_label.accessibleDescription()
        assert description in dialog.brainproducts_parallel_combo.itemData(
            0, Qt.ItemDataRole.ToolTipRole,
        )


@pytest.mark.parametrize("port, pulse, valid", [
    ("COM123", "1000", True), (" ", "10", False),
    ("COM123", "0", False), ("COM123", "1001", False),
    ("COM123", "broken saved pulse", False),
])
def test_triggerbox_fields_validation_and_geometry(qtbot, port, pulse, valid, recording_errors):
    dialog = RecordingSetupDialog(_triggerbox_configuration(
        brainproducts_serial_port=port, brainproducts_pulse_width_ms=pulse,
    ))
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    assert (dialog.width(), dialog.height()) == (700, 640)
    assert not dialog.port_edit.isEnabled()
    assert not dialog.endpoint_label.isVisible()
    if not valid:
        _assert_invalid_apply(dialog, recording_errors)
    assert "250 Hz" in dialog.brainproducts_pulse_edit.toolTip()
    assert "twice the pulse width" in dialog.brainproducts_pulse_edit.toolTip()
    _assert_labels_fit(dialog)


@pytest.mark.parametrize("amplifier, sampling_rate", [
    (None, None), ("actichamp", None), (None, 500),
    ("actichamp", 777), ("liveamp", 100), ("unknown amplifier", 500),
])
def test_triggerbox_apply_requires_supported_amplifier_and_sampling_rate(
    qtbot, amplifier, sampling_rate, recording_errors,
):
    original = _triggerbox_configuration(
        brainproducts_amplifier=amplifier, brainproducts_sampling_rate_hz=sampling_rate,
    )
    dialog = RecordingSetupDialog(original)
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    _assert_invalid_apply(dialog, recording_errors)
    assert dialog.configuration == original
    _assert_labels_fit(dialog)


@pytest.mark.parametrize("amplifier, sampling_rate, pulse, valid, minimum", [
    ("actichamp", 100, 19, False, 20),
    ("actichamp", 100, 20, True, 20),
    ("actichamp", 250, 7, False, 8),
    ("actichamp", 250, 8, True, 8),
    ("brainamp", 100, 9, False, 10),
    ("brainamp", 100, 10, True, 10),
    ("brainamp", 1000, 1, True, 1),
    ("liveamp", 250, 7, False, 8),
    ("liveamp", 250, 8, True, 8),
])
def test_triggerbox_sampling_rate_updates_pulse_requirement_and_apply(
    qtbot, amplifier, sampling_rate, pulse, valid, minimum, recording_errors,
):
    dialog = RecordingSetupDialog(_triggerbox_configuration(
        brainproducts_amplifier=amplifier,
        brainproducts_sampling_rate_hz=sampling_rate,
        brainproducts_pulse_width_ms=pulse,
    ))
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    assert f"{minimum} ms" in dialog.pulse_requirement_label.text()
    assert "spacing" in dialog.pulse_requirement_label.text()
    if not valid:
        _assert_invalid_apply(dialog, recording_errors)
    _assert_labels_fit(dialog)


def test_triggerbox_amplifier_change_preserves_supported_rate_and_clears_unsupported(
    qtbot, recording_errors,
):
    dialog = RecordingSetupDialog(_triggerbox_configuration())
    qtbot.addWidget(dialog)
    dialog.show()
    _select_triggerbox_timing(dialog, amplifier="brainamp", sampling_rate=500)
    assert dialog.brainproducts_sampling_rate_combo.currentData() == 500
    assert dialog.apply_button.isEnabled()
    _select_triggerbox_timing(dialog, amplifier="actichamp", sampling_rate=25000)
    dialog.brainproducts_amplifier_combo.setCurrentIndex(
        dialog.brainproducts_amplifier_combo.findData("liveamp"),
    )
    assert dialog.brainproducts_sampling_rate_combo.currentData() is None
    _assert_invalid_apply(dialog, recording_errors)
    assert {dialog.brainproducts_sampling_rate_combo.itemData(index)
            for index in range(dialog.brainproducts_sampling_rate_combo.count())} == {
        None, 250, 500, 1000,
    }
    _select_triggerbox_timing(dialog, amplifier="liveamp", sampling_rate=250)
    assert dialog.apply_button.isEnabled()


def test_triggerbox_detection_starts_once_on_first_visible_selection(
    qtbot, port_detection_jobs, monkeypatch,
):
    discovery = Mock(return_value=())
    monkeypatch.setattr(recording_dialog_module, "discover_triggerbox_ports", discovery)
    dialog = RecordingSetupDialog({"recording_backend": "serial"})
    qtbot.addWidget(dialog)
    assert port_detection_jobs == []
    dialog.show()
    QApplication.processEvents()
    assert port_detection_jobs == []
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("brainproducts_triggerbox"))
    assert len(port_detection_jobs) == 1
    assert not dialog.detect_ports_button.isEnabled()
    assert "Detecting" in dialog.detection_status_label.text()
    assert dialog.brainproducts_port_edit is dialog.brainproducts_port_combo.lineEdit()
    initial_cancel = Event()
    assert port_detection_jobs[0].callback(None, initial_cancel) == ()
    discovery.assert_called_once_with(check_access=False, cancel_event=initial_cancel)
    port_detection_jobs[0].finish()
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("serial"))
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("brainproducts_triggerbox"))
    assert len(port_detection_jobs) == 1
    dialog.detect_ports_button.click()
    assert len(port_detection_jobs) == 2
    assert "Checking" in dialog.detection_status_label.text()
    explicit_cancel = Event()
    assert port_detection_jobs[1].callback(None, explicit_cancel) == ()
    assert discovery.call_args.kwargs == {
        "check_access": True, "cancel_event": explicit_cancel, "selected_port": None,
    }
    assert "opening and closing" in dialog.detect_ports_button.toolTip()
    assert "manually selected COM port" in dialog.detect_ports_button.toolTip()


@pytest.mark.parametrize("accessible, error, action", [
    (True, "", "Port accessible when checked"),
    (False, "[WinError 5] Access is denied: COM9", "Fully exit the TriggerBox software"),
    (False, "[WinError 2] The system cannot find the file specified: COM9", "check Device Manager"),
    (False, "Cannot configure port: PermissionError(13, 'Incorrect function.', None, 1)",
     "repair the TriggerBox driver if needed"),
    (False, "[WinError 1117] The request could not be performed because of an I/O device error",
     "Reconnect the USB cable"),
    (False, "Write timeout", "Reconnect the USB cable"),
    (False, "Unable to close the port: driver handle error.", "Restart Studio before retrying"),
    (False, "[WinError 5] Access is denied. Closing the port also failed: driver handle error.",
     "Restart Studio before retrying"),
    (False, "", "check its port in Device Manager"),
])
def test_triggerbox_detect_reports_access_without_changing_port_values(
    qtbot, port_detection_jobs, accessible, error, action, recording_errors,
):
    dialog = RecordingSetupDialog(_unconfigured_triggerbox())
    qtbot.addWidget(dialog)
    dialog.show()
    candidate = TriggerBoxPortCandidate("COM9", "TriggerBox Plus")
    port_detection_jobs[0].finish(candidates=(candidate,))
    assert "TriggerBox port listed: COM9" in dialog.detection_status_label.text()
    assert "Access not checked" in dialog.detection_status_label.text()
    assert "does not prove" in dialog.detection_status_label.toolTip()
    assert "Disable Recorder Debouncing" in dialog.guidance_label.toolTip()
    _select_triggerbox_timing(dialog)
    dialog.detect_ports_button.click()
    port_detection_jobs[1].finish(candidates=(TriggerBoxPortCandidate(
        "COM9", candidate.description, accessible=accessible, access_error=error,
    ),))

    message = (dialog.detection_status_label.text() if accessible else
               _detection_error_message(dialog, recording_errors))
    assert "COM9" in message
    assert action in message
    if not accessible:
        assert message == triggerbox_port_error_message("COM9", error)
    assert dialog.brainproducts_port_combo.itemText(0) == "COM9"
    assert dialog.brainproducts_port_edit.text() == "COM9"
    details = dialog.brainproducts_port_combo.itemData(0, Qt.ItemDataRole.ToolTipRole)
    assert candidate.description in details
    assert action in details
    assert "does not verify the amplifier" in details
    if accessible:
        assert "when checked" in dialog.detection_status_label.text()
    elif "TriggerBox software" in action:
        assert "Configuration/Test IO" in details
        assert "Only one application" in details
        assert "Selecting a port manually cannot release it" in details
        assert "other apps using COM9, then try again" in message
        assert "Pressing Stop can leave the port occupied" in message
    else:
        assert "occupied or access was denied" not in details
        assert "Configuration/Test IO" not in details
        assert "Only one application" not in details
    if error:
        assert error in details
        assert error in str(recording_errors.call_args.args[2])
        assert error not in message
    assert dialog.configuration["brainproducts_serial_port"] == "COM3"
    dialog.apply_button.click()
    assert dialog.configuration["brainproducts_serial_port"] == "COM9"


def test_triggerbox_access_results_keep_unavailable_candidates_selectable(
    qtbot, port_detection_jobs, recording_errors,
):
    dialog = RecordingSetupDialog(_unconfigured_triggerbox())
    qtbot.addWidget(dialog)
    dialog.show()
    port_detection_jobs[0].finish(candidates=(
        TriggerBoxPortCandidate("COM9", "TriggerBox Plus"),
        TriggerBoxPortCandidate("COM12", "TriggerBox Virtual Serial Port"),
    ))
    _select_triggerbox_timing(dialog)
    dialog.detect_ports_button.click()
    port_detection_jobs[1].finish(candidates=(
        TriggerBoxPortCandidate("COM9", "TriggerBox Plus", accessible=True),
        TriggerBoxPortCandidate(
            "COM12", "TriggerBox Virtual Serial Port", accessible=False,
            access_error="The port is in use by another application.",
        ),
    ))

    assert dialog.brainproducts_port_combo.count() == 2
    assert dialog.brainproducts_port_edit.text() == ""
    assert "1 accessible, 1 unavailable" in dialog.detection_status_label.text()
    assert "Choose a port" in dialog.detection_status_label.text()
    _assert_invalid_apply(dialog, recording_errors)
    dialog.brainproducts_port_combo.setCurrentIndex(1)
    dialog.brainproducts_port_combo.activated.emit(1)
    assert dialog.brainproducts_port_edit.text() == "COM12"
    recovery = triggerbox_port_error_message("COM12", "The port is in use by another application.")
    assert _detection_error_message(dialog, recording_errors) == (
        f"{recovery} Choose COM9 if it is your TriggerBox port."
    )
    assert dialog.apply_button.isEnabled()
    dialog.brainproducts_port_combo.setCurrentIndex(0)
    dialog.brainproducts_port_combo.activated.emit(0)
    assert dialog.brainproducts_port_edit.text() == "COM9"
    assert "COM9: Port accessible" in dialog.detection_status_label.text()


def test_triggerbox_detect_preserves_manual_edit_after_selecting_listed_port(
    qtbot, port_detection_jobs, monkeypatch,
):
    discovery = Mock(return_value=())
    monkeypatch.setattr(recording_dialog_module, "discover_triggerbox_ports", discovery)
    dialog = RecordingSetupDialog(_triggerbox_configuration())
    qtbot.addWidget(dialog)
    dialog.show()
    port_detection_jobs[0].finish(candidates=(
        TriggerBoxPortCandidate("COM3", "TriggerBox Plus"),
        TriggerBoxPortCandidate("COM9", "TriggerBox Plus"),
    ))
    dialog.brainproducts_port_combo.setCurrentIndex(1)
    dialog.brainproducts_port_combo.activated.emit(1)
    dialog.brainproducts_port_edit.setText("COM42")
    dialog.brainproducts_port_edit.textEdited.emit("COM42")

    dialog.detect_ports_button.click()

    assert dialog.brainproducts_port_edit.text() == "COM42"
    cancel = Event()
    port_detection_jobs[1].callback(None, cancel)
    discovery.assert_called_once_with(check_access=True, cancel_event=cancel, selected_port="COM42")
    port_detection_jobs[1].finish(candidates=(
        TriggerBoxPortCandidate("COM9", "TriggerBox Plus", accessible=True),
        TriggerBoxPortCandidate("COM42", "Manually selected port", accessible=True),
    ))
    assert dialog.brainproducts_port_edit.text() == "COM42"
    assert dialog.detection_status_label.text() == "COM42: Port accessible when checked."


def test_triggerbox_checked_results_do_not_verify_a_manual_edit_during_scan(
    qtbot, port_detection_jobs, monkeypatch,
):
    discovery = Mock(return_value=())
    monkeypatch.setattr(recording_dialog_module, "discover_triggerbox_ports", discovery)
    dialog = RecordingSetupDialog(_triggerbox_configuration(brainproducts_serial_port="COM42"))
    qtbot.addWidget(dialog)
    dialog.show()
    initial_cancel = Event()
    port_detection_jobs[0].callback(None, initial_cancel)
    discovery.assert_called_once_with(check_access=False, cancel_event=initial_cancel)
    port_detection_jobs[0].finish(candidates=(TriggerBoxPortCandidate("COM9", "TriggerBox Plus"),))
    dialog.detect_ports_button.click()
    dialog.brainproducts_port_edit.setText("COM77")
    dialog.brainproducts_port_edit.textEdited.emit("COM77")
    explicit_cancel = Event()
    port_detection_jobs[1].callback(None, explicit_cancel)
    assert discovery.call_args.kwargs == {
        "check_access": True, "cancel_event": explicit_cancel, "selected_port": "COM42",
    }
    port_detection_jobs[1].finish(candidates=(
        TriggerBoxPortCandidate("COM9", "TriggerBox Plus", accessible=True),
        TriggerBoxPortCandidate(
            "COM42", "Manually selected port (device identity not verified)", accessible=True,
        ),
    ))

    assert dialog.brainproducts_port_edit.text() == "COM77"
    assert "Selected port was not checked" in dialog.detection_status_label.text()
    assert "Click Detect to check it" in dialog.detection_status_label.text()
    assert "Port accessible" not in dialog.detection_status_label.text()
    dialog.brainproducts_port_edit.setText("COM9")
    dialog.brainproducts_port_edit.textEdited.emit("COM9")
    assert "COM9: Port accessible" in dialog.detection_status_label.text()
    dialog.brainproducts_port_edit.setText("COM88")
    dialog.brainproducts_port_edit.textEdited.emit("COM88")
    assert "Selected port was not checked" in dialog.detection_status_label.text()


def test_triggerbox_manual_port_access_denied_can_retry_without_changing_selection(
    qtbot, port_detection_jobs, monkeypatch, recording_errors,
):
    discovery = Mock(return_value=())
    monkeypatch.setattr(recording_dialog_module, "discover_triggerbox_ports", discovery)
    dialog = RecordingSetupDialog(_triggerbox_configuration())
    qtbot.addWidget(dialog)
    dialog.show()
    port_detection_jobs[0].finish()
    dialog.brainproducts_port_edit.setText(" COM4 ")
    dialog.brainproducts_port_edit.textEdited.emit(" COM4 ")
    assert "Detect can check your entered COM port" in dialog.detection_status_label.text()
    dialog.detect_ports_button.click()
    cancel = Event()
    port_detection_jobs[1].callback(None, cancel)
    assert discovery.call_args.kwargs == {
        "check_access": True, "cancel_event": cancel, "selected_port": "COM4",
    }
    description = "Manually selected port (device identity not verified)"
    error = "could not open port 'COM4': PermissionError(13, 'Access is denied.', None, 5)"
    port_detection_jobs[1].finish(candidates=(
        TriggerBoxPortCandidate("COM4", description, accessible=False, access_error=error),
    ))
    assert _detection_error_message(dialog, recording_errors) == (
        triggerbox_port_error_message("COM4", error)
    )
    assert description in str(recording_errors.call_args.args[2])
    assert error in str(recording_errors.call_args.args[2])
    assert dialog.brainproducts_port_edit.text() == " COM4 "
    assert dialog.detect_ports_button.isEnabled()
    assert dialog.apply_button.isEnabled()
    dialog.detect_ports_button.click()
    assert "access was denied" not in dialog.detection_status_label.text()
    assert dialog.detection_status_label.toolTip() == ""
    port_detection_jobs[2].callback(None, cancel)
    assert discovery.call_args.kwargs["selected_port"] == "COM4"
    port_detection_jobs[2].finish(candidates=(
        TriggerBoxPortCandidate("COM4", description, accessible=True),
    ))
    assert dialog.detection_status_label.text() == "COM4: Port accessible when checked."
    assert "access was denied" not in dialog.detection_status_label.toolTip()
    assert dialog.brainproducts_port_edit.text() == " COM4 "
    dialog.apply_button.click()
    assert dialog.configuration["brainproducts_serial_port"] == "COM4"


@pytest.mark.parametrize("accessible", [False, True])
def test_default_triggerbox_detect_checks_saved_com3_with_generic_metadata(
    qtbot, port_detection_jobs, monkeypatch, accessible, recording_errors,
):
    from fpvs_studio.triggers import brainproducts_discovery as discovery_module

    error = "" if accessible else "could not open port: FileNotFoundError(2, 'Missing', None, 2)"
    metadata = SimpleNamespace(device="COM3", description="USB Serial Port (COM3)")
    list_ports = SimpleNamespace(comports=lambda: [metadata])
    serial = SimpleNamespace()
    modules = {"serial.tools.list_ports": list_ports, "serial": serial}
    check_access = Mock(return_value=SimpleNamespace(accessible=accessible, access_error=error))
    monkeypatch.setattr(discovery_module, "importlib", SimpleNamespace(import_module=modules.get))
    monkeypatch.setattr(discovery_module, "check_serial_port_access", check_access)
    monkeypatch.setattr(
        recording_dialog_module, "discover_triggerbox_ports",
        discovery_module.discover_triggerbox_ports,
    )
    dialog = RecordingSetupDialog(_triggerbox_configuration(), computer_default=True)
    qtbot.addWidget(dialog)
    dialog.show()
    initial = port_detection_jobs[0].callback(None, Event())
    assert initial == ()
    check_access.assert_not_called()
    port_detection_jobs[0].finish(candidates=initial)

    qtbot.mouseClick(dialog.detect_ports_button, Qt.MouseButton.LeftButton)
    cancel = Event()
    candidates = port_detection_jobs[1].callback(None, cancel)
    check_access.assert_called_once_with(
        "COM3", baudrate=2_000_000, serial_module=serial, cancel_event=cancel,
    )
    port_detection_jobs[1].finish(candidates=candidates)
    if accessible:
        assert dialog.detection_status_label.text() == "COM3: Port accessible when checked."
        assert "device identity not verified" in dialog.detection_status_label.toolTip()
    else:
        message = _detection_error_message(dialog, recording_errors)
        assert message.startswith("TriggerBox port COM3 was not found.")
        assert "install its driver if needed" in message
    assert dialog.brainproducts_port_edit.text() == "COM3"
    assert dialog.detect_ports_button.isEnabled()


def test_triggerbox_blank_manual_port_is_not_sent_to_access_check(
    qtbot, port_detection_jobs, monkeypatch,
):
    discovery = Mock(return_value=())
    monkeypatch.setattr(recording_dialog_module, "discover_triggerbox_ports", discovery)
    dialog = RecordingSetupDialog(_triggerbox_configuration(brainproducts_serial_port="COM42"))
    qtbot.addWidget(dialog)
    dialog.show()
    port_detection_jobs[0].finish()
    dialog.brainproducts_port_edit.setText(" ")
    dialog.brainproducts_port_edit.textEdited.emit(" ")
    dialog.detect_ports_button.click()
    port_detection_jobs[1].callback(None, Event())
    assert discovery.call_args.kwargs["selected_port"] is None


@pytest.mark.parametrize("accept", [False, True])
def test_triggerbox_accept_or_cancel_ignores_late_access_results(
    qtbot, port_detection_jobs, accept,
):
    dialog = RecordingSetupDialog(_triggerbox_configuration())
    qtbot.addWidget(dialog)
    dialog.show()
    port_detection_jobs[0].finish(candidates=(TriggerBoxPortCandidate("COM9", "TriggerBox Plus"),))
    dialog.detect_ports_button.click()
    job = port_detection_jobs[1]
    previous_status = dialog.detection_status_label.text()
    if accept:
        dialog.accept()
    else:
        dialog.reject()
    accepted_configuration = dialog.configuration
    assert job.cancelled
    job.finish(candidates=(TriggerBoxPortCandidate("COM12", "TriggerBox Plus", accessible=True),))

    assert dialog.brainproducts_port_edit.text() == "COM3"
    assert dialog.detection_status_label.text() == previous_status
    assert dialog.configuration == accepted_configuration
    assert dialog.result() == int(
        QDialog.DialogCode.Accepted if accept else QDialog.DialogCode.Rejected
    )


def test_triggerbox_cancelled_access_check_allows_retry(qtbot, port_detection_jobs):
    dialog = RecordingSetupDialog(_triggerbox_configuration())
    qtbot.addWidget(dialog)
    dialog.show()
    port_detection_jobs[0].finish()
    dialog.detect_ports_button.click()
    port_detection_jobs[1].finish(cancelled=True)

    assert "cancelled" in dialog.detection_status_label.text()
    assert dialog.detect_ports_button.isEnabled()
    assert dialog.brainproducts_port_edit.text() == "COM3"
    dialog.detect_ports_button.click()
    assert len(port_detection_jobs) == 3


@pytest.mark.parametrize("cancelled", [False, True])
def test_triggerbox_retry_discards_previous_access_annotations(
    qtbot, port_detection_jobs, cancelled,
):
    dialog = RecordingSetupDialog(_triggerbox_configuration())
    qtbot.addWidget(dialog)
    dialog.show()
    port_detection_jobs[0].finish(candidates=(TriggerBoxPortCandidate("COM3", "TriggerBox Plus"),))
    dialog.detect_ports_button.click()
    port_detection_jobs[1].finish(candidates=(
        TriggerBoxPortCandidate("COM3", "TriggerBox Plus", accessible=True),
    ))
    assert "Port accessible" in dialog.brainproducts_port_combo.itemData(
        0, Qt.ItemDataRole.ToolTipRole,
    )

    dialog.detect_ports_button.click()
    assert dialog.brainproducts_port_combo.itemData(
        0, Qt.ItemDataRole.ToolTipRole,
    ) == "TriggerBox Plus"
    assert dialog.detection_status_label.toolTip() == ""
    assert dialog.detection_status_label.accessibleDescription() == ""
    port_detection_jobs[2].finish(
        cancelled=cancelled,
        error=None if cancelled else RuntimeError("Windows device metadata access failed."),
    )

    assert "Port accessible" not in dialog.detection_status_label.text()
    assert "Port accessible" not in dialog.detection_status_label.toolTip()
    assert dialog.brainproducts_port_combo.itemData(
        0, Qt.ItemDataRole.ToolTipRole,
    ) == "TriggerBox Plus"


@pytest.mark.parametrize("initial_port", ["COM3", "COM4", "COM123"])
def test_triggerbox_unique_detection_preserves_saved_port(
    qtbot, port_detection_jobs, initial_port,
):
    dialog = RecordingSetupDialog(_triggerbox_configuration(brainproducts_serial_port=initial_port))
    qtbot.addWidget(dialog)
    dialog.show()
    assert len(port_detection_jobs) == 1
    candidate = TriggerBoxPortCandidate("COM9", "TriggerBox Plus")
    port_detection_jobs[0].finish(candidates=(candidate,))
    assert dialog.brainproducts_port_edit.text() == initial_port
    assert dialog.brainproducts_port_combo.itemText(0) == "COM9"
    details = dialog.brainproducts_port_combo.itemData(0, Qt.ItemDataRole.ToolTipRole)
    assert candidate.description in details
    assert "A listed port does not prove the TriggerBox is plugged in" in details
    assert "does not verify the amplifier connection, recording or marker receipt" in details
    assert dialog.detect_ports_button.isEnabled()
    assert "COM9" in dialog.detection_status_label.text()
    assert dialog.apply_button.isEnabled()
    assert dialog.configuration["brainproducts_serial_port"] == initial_port


def test_triggerbox_detection_preserves_operator_edit_during_scan(qtbot, port_detection_jobs):
    dialog = RecordingSetupDialog(_triggerbox_configuration())
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.brainproducts_port_edit.setText("COM42")
    dialog.brainproducts_port_edit.textEdited.emit("COM42")
    port_detection_jobs[0].finish(candidates=(TriggerBoxPortCandidate("COM9", "TriggerBox Plus"),))
    assert dialog.brainproducts_port_edit.text() == "COM42"
    dialog.apply_button.click()
    assert dialog.configuration["brainproducts_serial_port"] == "COM42"


@pytest.mark.parametrize("initial_port, expected_port", [
    ("COM3", ""), ("COM9", "COM9"), ("COM123", "COM123"),
])
@pytest.mark.parametrize("first_candidate_port", ["COM3", "COM9"])
def test_triggerbox_multiple_candidates_never_choose_arbitrary_first(
    qtbot, port_detection_jobs, initial_port, expected_port, first_candidate_port,
):
    dialog = RecordingSetupDialog(_unconfigured_triggerbox(brainproducts_serial_port=initial_port))
    qtbot.addWidget(dialog)
    dialog.show()
    port_detection_jobs[0].finish(candidates=(
        TriggerBoxPortCandidate(first_candidate_port, "TriggerBox Plus"),
        TriggerBoxPortCandidate("COM12", "TriggerBox VirtualSerial Port"),
    ))
    _select_triggerbox_timing(dialog)
    assert dialog.brainproducts_port_combo.count() == 2
    assert dialog.brainproducts_port_edit.text() == expected_port
    assert "Choose a port" in dialog.detection_status_label.text()
    assert dialog.apply_button.isEnabled() is bool(expected_port)
    if not expected_port:
        dialog.brainproducts_port_combo.setCurrentIndex(1)
        dialog.brainproducts_port_combo.activated.emit(1)
        assert dialog.brainproducts_port_edit.text() == "COM12"
        assert dialog.apply_button.isEnabled()


def test_triggerbox_empty_and_failed_detection_allow_manual_port_and_retry(
    qtbot, port_detection_jobs, recording_errors,
):
    dialog = RecordingSetupDialog(_triggerbox_configuration(brainproducts_serial_port="COM123"))
    qtbot.addWidget(dialog)
    dialog.show()
    port_detection_jobs[0].finish()
    assert "No TriggerBox" in dialog.detection_status_label.text()
    assert "install TriggerBox software/drivers" in dialog.detection_status_label.text()
    assert "Detect can check your entered COM port" in dialog.detection_status_label.text()
    assert dialog.brainproducts_port_edit.text() == "COM123"
    assert dialog.detect_ports_button.isEnabled()
    dialog.detect_ports_button.click()
    port_detection_jobs[1].finish(error=RuntimeError("Serial port metadata is unavailable"))
    assert "Unable to list TriggerBox ports" in _detection_error_message(dialog, recording_errors)
    assert str(recording_errors.call_args.args[2]) == "Serial port metadata is unavailable"
    assert dialog.brainproducts_port_edit.text() == "COM123"
    assert dialog.apply_button.isEnabled()
    dialog.detect_ports_button.click()
    assert len(port_detection_jobs) == 3
    port_detection_jobs[2].finish(candidates=(
        TriggerBoxPortCandidate("COM123", "TriggerBox Plus"),
    ))
    assert "Unable to list" not in dialog.detection_status_label.text()
    assert "unavailable" not in dialog.detection_status_label.toolTip()


@pytest.mark.parametrize("public_message", [
    "Studio could not load its TriggerBox connection component. The installation may be "
    "incomplete. Repair or reinstall FPVS Studio, then try Detect again.",
    "Windows could not list serial ports. Device information may be unavailable. "
    "Check Device Manager, then try Detect again or enter the COM port.",
    "Enter a valid COM port, such as COM4, before checking access.",
])
def test_triggerbox_discovery_failures_show_known_recovery_and_preserve_raw_details(
    qtbot, port_detection_jobs, public_message, recording_errors,
):
    dialog = RecordingSetupDialog(_triggerbox_configuration())
    qtbot.addWidget(dialog)
    dialog.show()
    raw_details = "Serial provider diagnostic with a long device path: C:/driver/details"
    error = TriggerBoxDiscoveryError(f"{public_message} Details: {raw_details}")
    error.__cause__ = RuntimeError("Underlying serial provider error")
    port_detection_jobs[0].finish(error=error)

    assert _detection_error_message(dialog, recording_errors) == public_message
    failure = recording_errors.call_args.args[2]
    assert raw_details in str(failure)
    assert str(failure.__cause__) == "Underlying serial provider error"
    assert dialog.detect_ports_button.isEnabled()
    assert dialog.brainproducts_port_edit.isEnabled()


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("serial_attribute_present", [False, True])
def test_triggerbox_broken_serial_support_does_not_request_device_driver_repair(
    qtbot, port_detection_jobs, monkeypatch, background, serial_attribute_present, recording_errors,
):
    from fpvs_studio.triggers import brainproducts_discovery as discovery_module
    from fpvs_studio.triggers.serial_port_access import SerialPortAccessError

    dialog = RecordingSetupDialog(_triggerbox_configuration(brainproducts_serial_port="COM4"))
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.show()
    port_detection_jobs[0].finish()
    dialog.detect_ports_button.click()
    serial_module = SimpleNamespace(EIGHTBITS=8, PARITY_NONE="N", STOPBITS_ONE=1)
    if serial_attribute_present:
        serial_module.Serial = None  # Imported transport is not callable.
    provider = SimpleNamespace(comports=Mock(return_value=()))
    modules = {"serial.tools.list_ports": provider, "serial": serial_module}
    with monkeypatch.context() as imports:
        imports.setattr(discovery_module.importlib, "import_module", modules.__getitem__)
        imports.setattr(
            recording_dialog_module, "discover_triggerbox_ports",
            discovery_module.discover_triggerbox_ports,
        )
        with pytest.raises(SerialPortAccessError) as failure:
            port_detection_jobs[1].callback(None, Event())
    port_detection_jobs[1].finish(error=failure.value)

    message = _detection_error_message(dialog, recording_errors)
    assert message == (
        "Studio could not check TriggerBox ports because its serial support is "
        "unavailable. Repair or reinstall Studio, then try Detect again."
    )
    assert recording_errors.call_args.args[2] is failure.value
    assert "pyserial" not in message
    assert "Details:" not in message
    assert "Device Manager" not in message
    assert "driver" not in message
    assert "Fully exit Configuration/Test IO before launch" in dialog.guidance_label.text()
    assert "Stop can leave the COM port occupied" in dialog.guidance_label.text()
    assert dialog.brainproducts_port_edit.text() == "COM4"
    assert dialog.detect_ports_button.isEnabled() and dialog.apply_button.isEnabled()
    QApplication.processEvents()
    assert (dialog.width(), dialog.height()) == (700, 640)
    _assert_labels_fit(dialog)


def test_triggerbox_cancel_cancels_discovery_and_ignores_late_result(
    qtbot, port_detection_jobs,
):
    original = _triggerbox_configuration()
    dialog = RecordingSetupDialog(original)
    qtbot.addWidget(dialog)
    dialog.show()
    job = port_detection_jobs[0]
    previous_status = dialog.detection_status_label.text()
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert job.cancelled
    assert dialog.result() == int(QDialog.DialogCode.Rejected)
    job.finish(candidates=(TriggerBoxPortCandidate("COM9", "TriggerBox Plus"),))
    assert dialog.brainproducts_port_edit.text() == "COM3"
    assert dialog.detection_status_label.text() == previous_status
    assert dialog.configuration == original


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("state", [
    "busy", "empty", "manual_empty", "multiple", "error", "unique", "checking", "accessible",
    "unavailable", "denied", "settings", "device_io", "timeout", "close", "unknown",
    "multiple_access", "multiple_unavailable", "serial_missing", "enumeration_error",
    "detect_empty",
])
def test_triggerbox_discovery_states_fit_minimum_dialog_with_full_metadata_paths(
    qtbot, port_detection_jobs, background, state, recording_errors,
):
    access_errors = {
        "unavailable": "[WinError 2] The system cannot find the file specified. ",
        "denied": "could not open port: PermissionError(13, 'Access is denied.', None, 5) ",
        "settings": "Cannot configure port: PermissionError(13, 'Incorrect function.', None, 1) ",
        "device_io": "[WinError 1117] The request failed because of an I/O device error. ",
        "timeout": "Write timeout. ",
        "close": "Unable to close the port: [WinError 6] The handle is invalid. ",
        "unknown": "Unrecognized adapter response. ",
    }
    selected_port = (
        "COM1234567890" if state in ("manual_empty", "checking", "accessible")
        or state in access_errors else "COM3"
    )
    dialog = RecordingSetupDialog(_triggerbox_configuration(
        brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=100,
        brainproducts_serial_port=selected_port,
    ))
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.show()
    description = "Brain Products GmbH TriggerBox rev. 02 VirtualSerial Port (COM1234567890)"
    candidate = TriggerBoxPortCandidate("COM1234567890", description)
    access_error = access_errors.get(state, access_errors["denied"]) * 8
    if state in ("empty", "manual_empty"):
        port_detection_jobs[0].finish()
    elif state == "detect_empty":
        port_detection_jobs[0].finish()
        recording_errors.assert_not_called()
        dialog.detect_ports_button.click()
        assert "Checking TriggerBox port access" in dialog.detection_status_label.text()
        port_detection_jobs[1].finish()
        message = _detection_error_message(dialog, recording_errors)
        assert message.startswith("No TriggerBox COM port")
        assert "install its software and driver" in message
        assert "Device Manager" in message
        assert dialog.detect_ports_button.isEnabled()
    elif state == "multiple":
        port_detection_jobs[0].finish(candidates=(
            candidate, TriggerBoxPortCandidate("COM12", "TriggerBox Plus"),
        ))
    elif state == "error":
        error = "Unable to enumerate TriggerBox ports: Windows device metadata access failed. " * 8
        port_detection_jobs[0].finish(error=RuntimeError(error))
        message = _detection_error_message(dialog, recording_errors)
        assert str(recording_errors.call_args.args[2]) == error
        assert "Unable to list TriggerBox ports" in message
        assert error not in message
    elif state in ("serial_missing", "enumeration_error"):
        public_message = (
            "Studio could not load its TriggerBox connection component. The installation may be "
            "incomplete. Repair or reinstall FPVS Studio, then try Detect again."
            if state == "serial_missing" else
            "Windows could not list serial ports. Device information may be unavailable. "
            "Check Device Manager, then try Detect again or enter the COM port."
        )
        error = f"{public_message} Details: {'Long serial-provider diagnostic. ' * 8}"
        port_detection_jobs[0].finish(error=TriggerBoxDiscoveryError(error))
        assert _detection_error_message(dialog, recording_errors) == public_message
        assert str(recording_errors.call_args.args[2]) == error
    elif state == "unique":
        port_detection_jobs[0].finish(candidates=(candidate,))
    elif state in ("checking", "accessible", "multiple_access", "multiple_unavailable") or (
        state in access_errors
    ):
        multiple = state in ("multiple_access", "multiple_unavailable")
        unavailable = state in access_errors or state == "multiple_unavailable"
        initial_candidates = (candidate,)
        if multiple:
            initial_candidates += (TriggerBoxPortCandidate("COM12", "TriggerBox Plus"),)
        port_detection_jobs[0].finish(candidates=initial_candidates)
        if multiple:
            dialog.brainproducts_port_edit.clear()
            dialog.brainproducts_port_edit.textEdited.emit("")
        dialog.detect_ports_button.click()
        if state != "checking":
            checked_candidates = (TriggerBoxPortCandidate(
                candidate.port, description, accessible=not unavailable,
                access_error=access_error if unavailable else "",
            ),)
            if multiple:
                checked_candidates += (TriggerBoxPortCandidate(
                    "COM12", "TriggerBox Plus", accessible=False, access_error=access_error,
                ),)
            port_detection_jobs[1].finish(candidates=checked_candidates)
    QApplication.processEvents()
    assert (dialog.width(), dialog.height()) == (700, 640)
    assert dialog.detect_ports_button.height() == dialog.brainproducts_port_combo.height()
    assert dialog.detect_ports_button.width() >= dialog.detect_ports_button.sizeHint().width()
    assert dialog.detection_status_label.wordWrap()
    assert dialog.pulse_requirement_label.wordWrap()
    assert "Fully exit Configuration/Test IO before launch" in dialog.guidance_label.text()
    assert "Stop can leave the COM port occupied" in dialog.guidance_label.text()
    assert "keep it recording" in dialog.guidance_label.text()
    assert dialog.detection_status_label.textFormat() == Qt.TextFormat.PlainText
    if state in access_errors:
        assert dialog.brainproducts_port_edit.text() == candidate.port
        recovery = triggerbox_port_error_message(candidate.port, access_error)
        assert _detection_error_message(dialog, recording_errors) == recovery
    elif state == "accessible":
        assert dialog.detection_status_label.text() == (
            f"{candidate.port}: Port accessible when checked."
        )
    elif state == "multiple_access":
        assert dialog.detection_status_label.text() == (
            "2 ports checked: 1 accessible, 1 unavailable. Choose a port."
        )
    elif state == "multiple_unavailable":
        message = _detection_error_message(dialog, recording_errors)
        assert "No checked port could be opened" in message
    _assert_labels_fit(dialog)
    if state in ("multiple", "unique", "accessible", "multiple_access"):
        assert description in dialog.detection_status_label.toolTip()
        assert "can remain listed when unplugged" in dialog.detection_status_label.toolTip()
    if state in ("multiple", "unique", "accessible", "multiple_access") or state in access_errors:
        assert description in dialog.brainproducts_port_combo.itemData(
            0, Qt.ItemDataRole.ToolTipRole,
        )
    if state == "multiple_access":
        assert access_error in dialog.detection_status_label.toolTip()
        assert access_error in dialog.detection_status_label.accessibleDescription()
    elif state in access_errors or state == "multiple_unavailable":
        assert access_error in str(recording_errors.call_args.args[2])


def test_triggerbox_drafts_survive_device_switch_and_cancel(qtbot):
    original = ProjectRecordingSettings(
        recording_backend="biosemi_active_three", unicorn_udp_port=3456,
    ).model_dump(mode="json")
    dialog = RecordingSetupDialog(original)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("brainproducts_triggerbox"))
    _select_triggerbox_timing(dialog)
    dialog.brainproducts_port_edit.setText(" COM123 ")
    dialog.brainproducts_pulse_edit.setText("20")
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("biosemi_active_three"))
    QApplication.processEvents()
    assert not dialog.brainproducts_port_edit.isVisible()
    assert not dialog.brainproducts_pulse_edit.isVisible()
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("brainproducts_triggerbox"))
    assert dialog.brainproducts_port_edit.text() == " COM123 "
    assert dialog.brainproducts_pulse_edit.text() == "20"
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.configuration == original
    dialog.show()
    dialog.apply_button.click()
    assert dialog.result() == int(QDialog.DialogCode.Accepted)
    assert dialog.configuration == {
        "recording_backend": "brainproducts_triggerbox", "unicorn_udp_port": 3456,
        "brainproducts_serial_port": "COM123", "brainproducts_pulse_width_ms": 20,
        "brainproducts_parallel_address": None,
        "brainproducts_amplifier": "actichamp", "brainproducts_sampling_rate_hz": 500,
    }


@pytest.mark.parametrize("edited_backend, selected_backend", [
    ("brainproducts_triggerbox", "serial"),
    ("brainproducts_triggerbox", "unicorn_udp"),
    ("unicorn_udp", "brainproducts_triggerbox"),
])
def test_switch_from_invalid_device_draft_applies_last_valid_inactive_values(
    qtbot, edited_backend, selected_backend, recording_errors,
):
    original = ProjectRecordingSettings(
        recording_backend=edited_backend,
        brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
    ).model_dump(mode="json")
    dialog = RecordingSetupDialog(original)
    qtbot.addWidget(dialog)
    dialog.show()
    if edited_backend == "unicorn_udp":
        dialog.port_edit.setText("4321")
        dialog.port_edit.clear()
    else:
        dialog.brainproducts_port_edit.setText("COM123")
        dialog.brainproducts_pulse_edit.setText("20")
        dialog.brainproducts_port_edit.clear()
        dialog.brainproducts_pulse_edit.clear()
    _assert_invalid_apply(dialog, recording_errors)
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData(selected_backend))
    assert dialog.apply_button.isEnabled()
    QApplication.processEvents()
    _assert_labels_fit(dialog)
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData(edited_backend))
    _assert_invalid_apply(dialog, recording_errors)
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData(selected_backend))
    dialog.apply_button.click()
    accepted = ProjectRecordingSettings.model_validate(dialog.configuration)
    assert accepted.recording_backend == selected_backend
    assert accepted.unicorn_udp_port == (4321 if edited_backend == "unicorn_udp" else 1000)
    assert accepted.brainproducts_serial_port == (
        "COM123" if edited_backend == "brainproducts_triggerbox" else "COM3"
    )
    assert accepted.brainproducts_pulse_width_ms == (
        20 if edited_backend == "brainproducts_triggerbox" else 10
    )
    assert original["recording_backend"] == edited_backend


@pytest.mark.parametrize("accepted", [False, True])
@pytest.mark.parametrize("backend", [
    "unicorn_udp", "biosemi_active_three", "brainproducts_triggerbox",
])
def test_settings_recording_editor_persists_only_apply(
    qtbot, tmp_path, monkeypatch, accepted, backend,
):
    saved = []
    original = {"recording_backend": None, "unicorn_udp_port": 1000}
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path, recording_configuration=original,
        on_recording_configuration_changed=saved.append,
    )
    qtbot.addWidget(dialog)
    select_settings_category(dialog, "Recording")
    dialog.show()
    editor = dialog.recording_editor
    editor.backend_combo.setCurrentIndex(editor.backend_combo.findData(backend))
    editor.port_edit.setText("2345")
    editor.brainproducts_port_edit.setText("COM123")
    editor.brainproducts_pulse_edit.setText("20")
    _select_triggerbox_timing(editor)
    if accepted:
        dialog.apply_recording_button.click()
        assert dialog.isVisible()
    else:
        dialog.reject()
    QApplication.processEvents()
    _assert_labels_fit(dialog)
    if accepted:
        assert saved == [{
            "recording_backend": backend,
            "unicorn_udp_port": 2345 if backend == "unicorn_udp" else 1000,
            "brainproducts_serial_port": (
                "COM123" if backend == "brainproducts_triggerbox" else "COM3"
            ),
            "brainproducts_parallel_address": None,
            "brainproducts_pulse_width_ms": 20 if backend == "brainproducts_triggerbox" else 10,
            "brainproducts_amplifier": (
                "actichamp" if backend == "brainproducts_triggerbox" else None
            ),
            "brainproducts_sampling_rate_hz": (
                500 if backend == "brainproducts_triggerbox" else None
            ),
            **({"serial_port": "COM3"}
               if backend in ("serial", "biosemi_active_three") else {}),
        }]
        assert "legacy" not in dialog.recording_summary.text()
        assert "invalid" not in dialog.recording_summary.text()
        if backend == "unicorn_udp":
            assert "2345" in dialog.recording_summary.text()
        elif backend == "brainproducts_triggerbox":
            assert "COM123" in dialog.recording_summary.text()
        else:
            assert "ActiveThree" in dialog.recording_summary.text()
    else:
        assert saved == []
        assert "legacy" in dialog.recording_summary.text()


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("size", [(860, 560), (1000, 680)])
@pytest.mark.parametrize("configuration", [
    {"recording_backend": "serial"},
    {"recording_backend": "biosemi_active_three"},
    _triggerbox_configuration(),
    _parallel_configuration(),
    {"recording_backend": "unicorn_udp", "unicorn_udp_port": 65535},
])
def test_inline_recording_controls_and_save_actions_fit_settings(
    qtbot, tmp_path, background, size, configuration,
):
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path,
        initial_category="Recording",
        recording_configuration=configuration,
        on_recording_configuration_changed=lambda _configuration: None,
        on_default_recording_configuration_changed=lambda _configuration: None,
        on_use_default_recording_configuration=lambda: None,
    )
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.resize(*size)
    dialog.show()
    QApplication.processEvents()

    assert dialog.size().toTuple() == size
    assert dialog.recording_editor.backend_combo.isVisible()
    assert not dialog.findChildren(RecordingSetupDialog)
    scroll = dialog.pages.currentWidget()
    assert isinstance(scroll, QScrollArea)
    assert scroll.horizontalScrollBar().maximum() == 0
    for button in (
        dialog.apply_recording_button,
        dialog.save_default_recording_button,
        dialog.use_default_recording_button,
    ):
        scroll.ensureWidgetVisible(button)
        QApplication.processEvents()
        assert button.isVisible()
        assert button.width() >= button.sizeHint().width()
        assert scroll.viewport().rect().contains(button.mapTo(
            scroll.viewport(), button.rect().center(),
        ))
        _assert_labels_fit(dialog)
    assert dialog.size().toTuple() == size


def test_inline_recording_draft_survives_category_changes_without_saving(
    qtbot, tmp_path,
):
    project_save = Mock()
    default_save = Mock()
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path, initial_category="Recording",
        recording_configuration={"recording_backend": "serial"},
        on_recording_configuration_changed=project_save,
        on_default_recording_configuration_changed=default_save,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    editor = dialog.recording_editor
    editor.backend_combo.setCurrentIndex(editor.backend_combo.findData("unicorn_udp"))
    editor.port_edit.setText("4321")
    select_settings_category(dialog, "General")
    select_settings_category(dialog, "Recording")
    assert dialog.recording_editor is editor
    assert editor.backend_combo.currentData() == "unicorn_udp"
    assert editor.port_edit.text() == "4321"
    project_save.assert_not_called()
    default_save.assert_not_called()
    dialog.reject()
    project_save.assert_not_called()
    default_save.assert_not_called()


@pytest.mark.parametrize("action", ["apply_recording_button", "save_default_recording_button"])
def test_inline_recording_invalid_draft_can_be_corrected_before_saving(
    qtbot, tmp_path, action, recording_errors,
):
    project_save = Mock()
    default_save = Mock()
    original = {"recording_backend": "unicorn_udp", "unicorn_udp_port": 1000}
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path, recording_configuration=original,
        on_recording_configuration_changed=project_save,
        on_default_recording_configuration_changed=default_save,
    )
    qtbot.addWidget(dialog)
    editor = dialog.recording_editor
    editor.port_edit.setText("70000")
    button = getattr(dialog, action)
    button.click()
    recording_errors.assert_called_once()
    assert recording_errors.call_args.args[:2] == (dialog, "Recording Setup Error")
    project_save.assert_not_called()
    default_save.assert_not_called()
    assert dialog._recording_configuration == original
    assert editor.port_edit.text() == "70000"
    editor.port_edit.setText("5432")
    button.click()
    chosen_save = project_save if action == "apply_recording_button" else default_save
    other_save = default_save if action == "apply_recording_button" else project_save
    chosen_save.assert_called_once()
    assert chosen_save.call_args.args[0]["unicorn_udp_port"] == 5432
    other_save.assert_not_called()
    assert recording_errors.call_count == 1


@pytest.mark.parametrize("finish", ["close", "category", "use_default"])
def test_inline_recording_hiding_or_replacing_editor_ignores_stale_detection(
    qtbot, tmp_path, port_detection_jobs, recording_errors, finish,
):
    reset = Mock()
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path, initial_category="Recording",
        recording_configuration=_unconfigured_triggerbox(),
        default_recording_configuration={"recording_backend": "unicorn_udp"},
        on_recording_configuration_changed=lambda _configuration: None,
        on_use_default_recording_configuration=reset,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    assert len(port_detection_jobs) == 1
    editor = dialog.recording_editor
    editor.brainproducts_port_edit.selectAll()
    qtbot.keyClicks(editor.brainproducts_port_edit, "COM19")
    job = port_detection_jobs[0]
    if finish == "close":
        dialog.reject()
    elif finish == "category":
        select_settings_category(dialog, "General")
        assert job.cancelled
        select_settings_category(dialog, "Recording")
        assert len(port_detection_jobs) == 2
    else:
        dialog.use_default_recording_button.click()
        reset.assert_called_once_with()
        assert dialog.recording_editor is not editor
    assert job.cancelled
    job.finish(candidates=(TriggerBoxPortCandidate("COM42", "TriggerBox Plus"),))
    job.finish(error=OSError("Late failure from the cancelled detection"))
    QApplication.processEvents()
    if finish == "use_default":
        assert dialog.recording_editor.backend_combo.currentData() == "unicorn_udp"
    else:
        assert dialog.recording_editor is editor
        assert editor.brainproducts_port_edit.text() == "COM19"
    if finish == "category":
        port_detection_jobs[1].finish(candidates=(
            TriggerBoxPortCandidate("COM24", "Current TriggerBox Plus"),
        ))
        assert editor.detect_ports_button.isEnabled()
        assert editor.brainproducts_port_edit.text() == "COM19"
    recording_errors.assert_not_called()


@pytest.mark.parametrize("computer_default", [False, True])
@pytest.mark.parametrize("save_fails", [False, True])
def test_inline_recording_save_keeps_reviewed_port_during_pending_detection(
    qtbot, tmp_path, port_detection_jobs, recording_errors, computer_default, save_fails,
):
    save = Mock(side_effect=OSError("Read-only settings") if save_fails else None)
    initial = _unconfigured_triggerbox(brainproducts_serial_port="COM3")
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path, initial_category="Recording",
        recording_configuration=initial,
        default_recording_configuration=initial,
        on_recording_configuration_changed=save if not computer_default else Mock(),
        on_default_recording_configuration_changed=save if computer_default else Mock(),
    )
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    assert len(port_detection_jobs) == 1
    editor = dialog.recording_editor
    _select_triggerbox_timing(editor)
    button = (dialog.save_default_recording_button if computer_default
              else dialog.apply_recording_button)
    button.click()
    save.assert_called_once()
    assert save.call_args.args[0]["brainproducts_serial_port"] == "COM3"
    assert dialog.isVisible()
    port_detection_jobs[0].finish(candidates=(
        TriggerBoxPortCandidate("COM9", "Detected TriggerBox Plus"),
    ))
    assert editor.brainproducts_port_edit.text() == ("COM9" if save_fails else "COM3")
    accepted = (dialog._default_recording_configuration if computer_default
                else dialog._recording_configuration)
    if save_fails:
        assert accepted == initial
    else:
        assert ProjectRecordingSettings.model_validate(accepted) == (
            ProjectRecordingSettings.model_validate(_triggerbox_configuration())
        )
    assert recording_errors.call_count == int(save_fails)


def test_project_device_reopen_and_switch_ignore_obsolete_global_choice(
    qtbot,
    controller,
    tmp_path,
):
    controller._settings = QSettings(str(tmp_path / "recording.ini"), QSettings.Format.IniFormat)
    controller._settings.setValue("recording/backend", "unicorn_udp")
    controller._settings.setValue("recording/unicorn_udp_port", 5432)
    controller._settings.sync()
    first, first_window = open_created_project(controller, qtbot, tmp_path, "Semantic Categories")
    assert first.validate_recording_launch() == "serial"
    controller.save_recording_configuration(
        {"recording_backend": "unicorn_udp", "unicorn_udp_port": 3456}
    )
    assert (
        _label_plain_text(first_window.home_page.recording_summary)
        == "Recording Device: Unicorn Black Mobile Headset"
    )
    second, second_window = open_created_project(controller, qtbot, tmp_path, "Other study")
    assert _label_plain_text(second_window.home_page.recording_summary) == (
        "Recording Device: BioSemi ActiveTwo"
    )
    assert controller.load_recording_configuration()["recording_backend"] == "serial"
    controller.save_recording_configuration(
        {"recording_backend": "serial", "unicorn_udp_port": 1000}
    )
    reopened = ProjectDocument.open_existing(first.project_root)
    controller._open_document(reopened)
    qtbot.addWidget(controller.main_window)
    assert controller.load_recording_configuration() == ProjectRecordingSettings(
        recording_backend="unicorn_udp", unicorn_udp_port=3456,
    ).model_dump(mode="json")
    assert (
        ProjectDocument.open_existing(second.project_root).validate_recording_launch() == "serial"
    )


@pytest.mark.parametrize("port", ["COM3", "COM4"])
@pytest.mark.parametrize("computer_default", [False, True])
def test_actichamp_port_apply_and_reopen_keeps_saved_port_during_detection(
    qtbot, controller, tmp_path, monkeypatch, port_detection_jobs, port, computer_default,
):
    ini_path = str(tmp_path / "recording.ini")
    controller._settings = QSettings(ini_path, QSettings.Format.IniFormat)
    document, _window = open_created_project(controller, qtbot, tmp_path, "actiCHamp recording")
    other_port = "COM4" if port == "COM3" else "COM3"
    original = _triggerbox_configuration(brainproducts_serial_port=other_port)
    settings = AppSettingsDialog(
        fpvs_root_dir=tmp_path, default_recording_configuration=original,
        on_default_recording_configuration_changed=controller.save_default_recording_configuration,
        recording_configuration=original,
        on_recording_configuration_changed=controller.save_recording_configuration,
    )
    qtbot.addWidget(settings)

    settings.recording_editor.brainproducts_port_edit.setText(port)
    _select_triggerbox_timing(settings.recording_editor, sampling_rate=1000)
    button = (settings.save_default_recording_button if computer_default
              else settings.apply_recording_button)
    button.click()
    if computer_default:
        controller._settings = QSettings(ini_path, QSettings.Format.IniFormat)
        saved = controller.load_default_recording_configuration()
    else:
        saved = ProjectDocument.open_existing(document.project_root).recording_configuration
    assert saved is not None
    assert saved["brainproducts_serial_port"] == port
    assert saved["brainproducts_amplifier"] == "actichamp"
    assert saved["brainproducts_sampling_rate_hz"] == 1000

    reopened = RecordingSetupDialog(saved, computer_default=computer_default)
    qtbot.addWidget(reopened)
    reopened.show()
    other_candidate = TriggerBoxPortCandidate(other_port, "TriggerBox Plus")
    port_detection_jobs[0].finish(candidates=(other_candidate,))
    assert reopened.brainproducts_port_edit.text() == port
    assert reopened.brainproducts_amplifier_combo.currentData() == "actichamp"
    assert reopened.brainproducts_sampling_rate_combo.currentData() == 1000
    discovery = Mock(return_value=())
    monkeypatch.setattr(recording_dialog_module, "discover_triggerbox_ports", discovery)
    reopened.detect_ports_button.click()
    cancel = Event()
    port_detection_jobs[1].callback(None, cancel)
    discovery.assert_called_once_with(check_access=True, cancel_event=cancel, selected_port=port)
    port_detection_jobs[1].finish(candidates=(
        TriggerBoxPortCandidate(other_port, "TriggerBox Plus", accessible=True),
        TriggerBoxPortCandidate("COM9", "TriggerBox VirtualSerial Port", accessible=True),
    ))
    QApplication.processEvents()
    assert reopened.brainproducts_port_edit.text() == port
    assert reopened.apply_button.isEnabled()
    assert (reopened.width(), reopened.height()) == (700, 640)
    _assert_labels_fit(reopened)


@pytest.mark.parametrize("entrypoint", ["home", "run"])
@pytest.mark.parametrize("has_default_timing", [False, True])
def test_first_brainproducts_launch_saves_project_timing_before_participant_entry(
    qtbot, controller, tmp_path, monkeypatch, entrypoint, has_default_timing,
):
    default = _triggerbox_configuration() if has_default_timing else _unconfigured_triggerbox()
    controller.save_default_recording_configuration(default)
    document, window = open_created_project(controller, qtbot, tmp_path, "First EEG launch")
    prepare_compile_ready_project(window, tmp_path / "first-eeg-assets")
    qtbot.waitUntil(lambda: window._session_seed_ready)
    page = window if entrypoint == "home" else window.run_page
    participant = Mock(return_value=None)
    monkeypatch.setattr(page, "_collect_launch_participant_details", participant)
    popup = Mock()
    monkeypatch.setattr("fpvs_studio.gui.main_window._show_error_dialog", popup)
    manifest = document.project_root / "project.json"
    original = manifest.read_bytes()
    assert document.uses_default_recording_configuration
    with pytest.raises(DocumentError, match="amplifier"):
        document.validate_recording_launch()

    def configure(child):
        qtbot.addWidget(child)
        assert child.brainproducts_amplifier_combo.currentData() == (
            default["brainproducts_amplifier"]
        )
        assert child.brainproducts_sampling_rate_combo.currentData() == (
            default["brainproducts_sampling_rate_hz"]
        )
        _select_triggerbox_timing(child, sampling_rate=1000)
        child.apply_button.click()
        return child.result()

    setup = Mock(return_value=int(QDialog.DialogCode.Rejected))
    monkeypatch.setattr(RecordingSetupDialog, "exec", setup)
    page.launch_session()
    setup.assert_called_once()
    participant.assert_not_called()
    popup.assert_not_called()
    assert manifest.read_bytes() == original

    monkeypatch.setattr(RecordingSetupDialog, "exec", configure)
    save_error = PermissionError("Synthetic read-only project file")
    with monkeypatch.context() as denied:
        denied.setattr(document, "save_recording_configuration", Mock(side_effect=save_error))
        page.launch_session()
    popup.assert_called_once_with(page, "Launch Blocked", save_error)
    participant.assert_not_called()
    assert manifest.read_bytes() == original
    assert document.uses_default_recording_configuration

    page.launch_session()
    participant.assert_called_once_with()
    assert not document.uses_default_recording_configuration
    reopened = ProjectDocument.open_existing(document.project_root)
    assert reopened.recording_configuration["brainproducts_amplifier"] == "actichamp"
    assert reopened.recording_configuration["brainproducts_sampling_rate_hz"] == 1000
    assert reopened.validate_recording_launch() == "brainproducts_triggerbox"
    assert controller.load_default_recording_configuration() == (
        ProjectRecordingSettings.model_validate(default).model_dump(mode="json")
    )

    monkeypatch.setattr(RecordingSetupDialog, "exec", setup)
    setup.reset_mock()
    page.launch_session()
    setup.assert_not_called()
    assert participant.call_count == 2


@pytest.mark.parametrize("entrypoint", ["home", "run"])
@pytest.mark.parametrize("readiness_state", [
    "not_running", "not_recording", "not_writing", "unavailable",
])
def test_unicorn_launch_queues_automatic_check_and_surfaces_failure(
    qtbot, controller, tmp_path, monkeypatch, entrypoint, readiness_state,
):
    with pytest.raises(RecorderReadinessError) as failure:
        _require_recording_snapshot({
            "state": readiness_state, "process_id": 1234, "version": "1.24.2.2760",
        })
    readiness_error = failure.value
    document, window = open_created_project(controller, qtbot, tmp_path, "Unicorn preparation")
    prepare_compile_ready_project(window, tmp_path / "recorder-check-assets")
    qtbot.waitUntil(lambda: window._session_seed_ready)
    document.set_recording_configuration({
        "recording_backend": "unicorn_udp", "unicorn_udp_port": 1000,
    })
    page = window if entrypoint == "home" else window.run_page
    errors = []
    tasks = []

    class HeldLaunchTask(ImmediateProgressTask):
        def __init__(self, *, persistent_thread=False, **kwargs):
            super().__init__(persistent_thread=persistent_thread, **kwargs)
            self._is_launch = persistent_thread

        def start(self):
            if self._is_launch:
                tasks.append(self)
            else:
                super().start()

    monkeypatch.setattr("fpvs_studio.gui.main_window.ProgressTask", HeldLaunchTask)
    monkeypatch.setattr("fpvs_studio.gui.run_page.ProgressTask", HeldLaunchTask)
    monkeypatch.setattr("fpvs_studio.gui.main_window._show_error_dialog",
                        lambda _parent, _title, error: errors.append(str(error)))
    participant_prompt = Mock(return_value=ParticipantLaunchDetails(participant_number="007"))
    monkeypatch.setattr(page, "_collect_launch_participant_details", participant_prompt)
    monkeypatch.setattr(document, "next_participant_session_number",
                        lambda _participant: 1)
    ready = Mock(side_effect=readiness_error)
    engine = Mock(side_effect=AssertionError("No participant presentation may start"))
    reserve = Mock(side_effect=AssertionError("No visit may be reserved"))
    monkeypatch.setattr(runtime_launcher, "require_unicorn_recorder_recording", ready)
    monkeypatch.setattr(runtime_launcher, "create_engine", engine)
    monkeypatch.setattr("fpvs_studio.gui.document.create_engine", engine)
    monkeypatch.setattr(runtime_launcher, "reserve_participant_session", reserve)

    assert document.validate_recording_launch() == "unicorn_udp"
    ready.assert_not_called()
    page.launch_session()
    participant_prompt.assert_called_once_with()
    qtbot.waitUntil(lambda: len(tasks) == 1)
    assert window.is_launch_busy()
    assert errors == []
    ready.assert_not_called()
    page.launch_session()
    assert len(tasks) == 1

    ImmediateProgressTask.start(tasks[0])
    ready.assert_called_once_with()
    engine.assert_not_called()
    reserve.assert_not_called()
    assert errors == [str(readiness_error)]
    assert not window.is_launch_busy()
    assert page._active_launch_task is None
    assert not document.require_biosemi_recording_confirmation
    window.resize(1120, 720)
    window.show()
    QApplication.processEvents()
    assert _label_plain_text(window.home_page.recording_summary) == (
        "Recording Device: Unicorn Black Mobile Headset"
    )
    assert "127.0.0.1:1000" in window.home_page.recording_summary.toolTip()
    _assert_labels_fit(window.home_page)
    document.set_experiment_test_mode_enabled(True)
    assert "No marker output" in document.recording_setup_summary()
    assert _label_plain_text(window.home_page.recording_summary) == "No marker output (Test/Pilot)"


@pytest.mark.parametrize("entrypoint", ["home", "run"])
def test_ready_unicorn_reaches_runtime_execution_on_both_launch_surfaces(
    qtbot, controller, tmp_path, monkeypatch, entrypoint,
):
    document, window = open_created_project(controller, qtbot, tmp_path, "Unicorn recording test")
    prepare_compile_ready_project(window, tmp_path / "recorder-ready-assets")
    qtbot.waitUntil(lambda: window._session_seed_ready)
    document.set_recording_configuration({
        "recording_backend": "unicorn_udp", "unicorn_udp_port": 1000,
    })
    page = window if entrypoint == "home" else window.run_page
    trace = []
    errors = []
    monkeypatch.setattr("fpvs_studio.gui.main_window.ProgressTask", ImmediateProgressTask)
    monkeypatch.setattr("fpvs_studio.gui.run_page.ProgressTask", ImmediateProgressTask)
    monkeypatch.setattr("fpvs_studio.gui.main_window._show_error_dialog",
                        lambda _parent, _title, error: errors.append(str(error)))
    monkeypatch.setattr(page, "_collect_launch_participant_details",
                        lambda: ParticipantLaunchDetails(participant_number="007"))
    monkeypatch.setattr(document, "next_participant_session_number", lambda _participant: 1)
    monkeypatch.setattr(document, "refresh_participant_summary_if_stale", lambda: None)
    monkeypatch.setattr("fpvs_studio.gui.document.create_engine",
                        Mock(side_effect=AssertionError("Engine creation belongs in runtime")))
    ready = Mock(side_effect=lambda: trace.append("ready"))
    monkeypatch.setattr(runtime_launcher, "require_unicorn_recorder_recording", ready)
    engine = object()

    def create_engine(_name):
        trace.append("engine")
        return engine

    def preflight(_root, _plan, **kwargs):
        assert kwargs["engine"] is engine
        trace.append("preflight")

    def reserve(_root, _participant, **_kwargs):
        trace.append("reserve")
        return SimpleNamespace(output_label="P007_session01", participant_session_number=1)

    def execute(_root, plan, _output, **kwargs):
        trace.append("execute")
        options = kwargs["runtime_options"]
        assert options["recording_backend"] == "unicorn_udp"
        assert not options["recording_operator_confirmed"]
        assert options["recording_association"] is None
        return SessionExecutionSummary(
            project_id=plan.project_id, session_id=plan.session_id, engine_name="fake",
            run_mode=RunMode.SESSION, participant_number="007", participant_session_number=1,
            total_condition_count=plan.total_runs, completed_condition_count=plan.total_runs,
        )

    monkeypatch.setattr(runtime_launcher, "create_engine", create_engine)
    monkeypatch.setattr(runtime_launcher, "preflight_session_plan", preflight)
    monkeypatch.setattr(runtime_launcher, "reserve_participant_session", reserve)
    monkeypatch.setattr(runtime_launcher, "RuntimeWorker",
                        lambda _engine: SimpleNamespace(execute_session=execute))

    page.launch_session()

    qtbot.waitUntil(lambda: bool(trace) or bool(errors))
    ready.assert_called_once_with()
    assert trace == ["ready", "engine", "preflight", "reserve", "execute"]
    assert errors == []
    assert not window.is_launch_busy()
    assert page._active_launch_task is None
    assert "Recorder check before launch" in document.recording_setup_summary()


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("size", [(760, 520), (1120, 720)], ids=["minimum", "default"])
@pytest.mark.parametrize(
    "backend, port, expected",
    [
        (None, 1000, "Recording Device: BioSemi ActiveTwo"),
        ("serial", 1000, "Recording Device: BioSemi ActiveTwo"),
        ("biosemi_active_three", 1000, "Recording Device: BioSemi ActiveThree"),
        (
            "brainproducts_triggerbox", 1000,
            "Recording Device: Brain Products / BrainVision (TriggerBox/Plus)",
        ),
        (
            "brainproducts_parallel", 1000,
            "Recording Device: Brain Products / BrainVision (Parallel port)",
        ),
        ("unicorn_udp", 65535, "Recording Device: Unicorn Black Mobile Headset"),
        (
            "unicorn_udp",
            "broken saved port",
            "Recording Setup required before recording.",
        ),
        (
            "unknown old selection",
            1000,
            "Recording Setup required before recording.",
        ),
    ],
)
def test_home_recording_device_label_fits_and_preserves_output_details(
    qtbot,
    controller,
    tmp_path,
    monkeypatch,
    background,
    size,
    backend,
    port,
    expected,
):
    document, window = open_created_project(controller, qtbot, tmp_path, "Home recording setup")
    recorder_probe = Mock(side_effect=AssertionError("Home refresh must not probe Recorder"))
    monkeypatch.setattr(runtime_launcher, "require_unicorn_recorder_recording", recorder_probe)
    if backend is None:
        assert document.validate_recording_launch() == "serial"
    elif backend not in (
        "serial", "biosemi_active_three", "brainproducts_triggerbox", "brainproducts_parallel",
        "unicorn_udp",
    ) or not isinstance(port, int):
        # Corrupt drafts remain actionable; disk loading rejects malformed typed settings.
        monkeypatch.setattr(
            document,
            "recording_launch_options",
            lambda: {
                "recording_backend": backend,
                "unicorn_udp_port": port,
            },
        )
        document.project_changed.emit()
    else:
        configuration = {"recording_backend": backend, "unicorn_udp_port": port}
        if backend in ("brainproducts_triggerbox", "brainproducts_parallel"):
            configuration.update(
                brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
            )
        if backend == "brainproducts_parallel":
            configuration["brainproducts_parallel_address"] = 0x378
        document.set_recording_configuration(configuration)
    palette = window.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    window.setPalette(palette)
    window.resize(*size)
    window.show()
    page = window.home_page
    label = page.recording_summary

    for setup_ready in (False, True):
        if setup_ready:
            prepare_compile_ready_project(window, tmp_path / "home-recording-assets")
        QApplication.processEvents()
        assert window.size().toTuple() == size
        assert _label_plain_text(label) == expected
        assert label.toolTip() == document.recording_setup_summary()
        assert label.accessibleName() == expected
        assert label.accessibleDescription() == (
            document.recording_setup_summary() + "\nOpen recording settings."
        )
        assert label.statusTip() == "Open recording settings"
        assert label.textFormat() == Qt.TextFormat.RichText
        assert label.textInteractionFlags() == (
            Qt.TextInteractionFlag.LinksAccessibleByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
        )
        assert label.focusPolicy() == Qt.FocusPolicy.StrongFocus
        assert not label.openExternalLinks()
        assert label.alignment() == Qt.AlignmentFlag.AlignCenter
        assert label.geometry().bottom() < page.launch_button.geometry().top()
        _assert_labels_fit(page)

    if backend in (
        None, "serial", "biosemi_active_three", "brainproducts_triggerbox",
        "brainproducts_parallel", "unicorn_udp",
    ) and isinstance(port, int):
        document.set_experiment_test_mode_enabled(True)
        QApplication.processEvents()
        assert _label_plain_text(label) == "No marker output (Test/Pilot)"
        _assert_labels_fit(page)
        document.set_experiment_test_mode_enabled(False)
        assert _label_plain_text(label) == expected
    recorder_probe.assert_not_called()


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("size", [(760, 520), (1120, 720)], ids=["minimum", "default"])
def test_home_recording_fallback_is_an_escaped_internal_link(
    qtbot, tmp_path, monkeypatch, background, size,
):
    summary = 'BioSemi serial — COM3 <Research & EEG> "Lab"'
    document = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Mac recording summary")
    monkeypatch.setattr(document, "recording_setup_summary", lambda: summary)
    monkeypatch.setattr(
        document, "validate_recording_launch",
        Mock(side_effect=DocumentError("Local test required")),
    )
    page = home_page_module.HomePage(document, load_condition_template_profiles=lambda: [])
    qtbot.addWidget(page)
    palette = page.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    page.setPalette(palette)
    page.resize(*size)
    page.show()
    QApplication.processEvents()

    assert page.size().toTuple() == size
    link = page.recording_summary
    assert _label_plain_text(link) == summary
    assert link.toolTip() == summary
    assert link.accessibleName() == summary
    assert link.text().count("<a ") == 1
    assert 'href="recording-settings"' in link.text()
    assert "&lt;Research &amp; EEG&gt;" in link.text()
    assert not link.openExternalLinks()
    _assert_labels_fit(page)


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("size", [(760, 520), (1120, 720)], ids=["minimum", "default"])
def test_home_recording_device_name_extension_and_pilot_output(
    qtbot, tmp_path, monkeypatch, background, size,
):
    name = (
        "Wireless High Density Research EEG Headset with an Extended Computer Local "
        "Acquisition Configuration for the Cognitive Neuroscience Laboratory"
    )
    monkeypatch.setitem(home_page_module._HOME_RECORDING_DEVICE_NAMES, "unicorn_udp", name)
    document = ProjectDocument.create_new(
        parent_dir=tmp_path, project_name="Recording label extension",
        experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
    )
    page = home_page_module.HomePage(document, load_condition_template_profiles=lambda: [])
    qtbot.addWidget(page)
    palette = page.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    page.setPalette(palette)
    page.resize(*size)
    page.show()
    document.set_recording_configuration({
        "recording_backend": "unicorn_udp", "unicorn_udp_port": 1000,
    })
    QApplication.processEvents()
    assert page.size().toTuple() == size
    assert _label_plain_text(page.recording_summary) == f"Recording Device: {name}"
    _assert_labels_fit(page)
    document.set_attentional_blink_pilot_mode_enabled(True)
    QApplication.processEvents()
    assert _label_plain_text(page.recording_summary) == "No marker output (Test/Pilot)"
    _assert_labels_fit(page)
    document.set_attentional_blink_pilot_mode_enabled(False)
    assert _label_plain_text(page.recording_summary) == f"Recording Device: {name}"
    document.set_recording_configuration({"recording_backend": "serial"})
    assert _label_plain_text(page.recording_summary) == "Recording Device: BioSemi ActiveTwo"


@pytest.mark.parametrize(
    "backend, port",
    [
        (None, 1000),
        ("biosemi_active_three", 1000),
        ("brainproducts_triggerbox", 1000),
        ("brainproducts_parallel", 1000),
        ("unicorn_udp", 65535),
        ("invalid", 1000),
    ],
)
def test_run_recording_summary_fits_existing_window_budget(
    qtbot,
    controller,
    tmp_path,
    monkeypatch,
    backend,
    port,
):
    document, _window = open_created_project(controller, qtbot, tmp_path, "Run recording setup")
    if backend is None:
        assert document.validate_recording_launch() == "serial"
    elif backend == "invalid":
        monkeypatch.setattr(
            document,
            "recording_launch_options",
            lambda: {
                "recording_backend": backend,
                "unicorn_udp_port": port,
            },
        )
    else:
        configuration = {"recording_backend": backend, "unicorn_udp_port": port}
        if backend in ("brainproducts_triggerbox", "brainproducts_parallel"):
            configuration.update(
                brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
            )
        if backend == "brainproducts_parallel":
            configuration["brainproducts_parallel_address"] = 0x378
        document.set_recording_configuration(configuration)
    page = RunPage(document)
    qtbot.addWidget(page)
    page.resize(1120, 720)
    page.show()
    QApplication.processEvents()
    assert_visible_children_within_parent(page)
    label = page.recording_summary
    assert label.height() >= label.heightForWidth(label.width())
    assert label.text() == document.recording_setup_summary()


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_recording_settings_failed_save_preserves_accepted_device(
    qtbot, tmp_path, monkeypatch, background, recording_errors,
):
    original = {"recording_backend": "serial", "unicorn_udp_port": 1000}
    error = PermissionError(13, "Access is denied", str(tmp_path / "project.json"))
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path,
        recording_configuration=original,
        on_recording_configuration_changed=Mock(side_effect=error),
    )
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    select_settings_category(dialog, "Recording")
    dialog.show()

    editor = dialog.recording_editor
    editor.backend_combo.setCurrentIndex(editor.backend_combo.findData("unicorn_udp"))
    initial_summary = dialog.recording_summary.text()
    dialog.apply_recording_button.click()
    QApplication.processEvents()
    recording_errors.assert_called_once_with(dialog, "Save Recording Setup Error", error)
    assert dialog.recording_summary.text() == initial_summary
    assert not dialog.recording_summary.toolTip()
    assert dialog._recording_configuration == original
    assert editor.backend_combo.currentData() == "unicorn_udp"
    _assert_labels_fit(dialog)


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_recording_validation_keeps_diagnostics_out_of_primary_text(
    qtbot, monkeypatch, background, recording_errors,
):
    validator = recording_dialog_module.validate_recording_configuration
    error = ValueError("invalid literal for int() with base 10: 'broken'")
    monkeypatch.setattr(
        recording_dialog_module, "validate_recording_configuration", Mock(side_effect=error),
    )
    dialog = RecordingSetupDialog(_triggerbox_configuration())
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.show()
    QApplication.processEvents()
    recording_errors.assert_not_called()
    _assert_invalid_apply(dialog, recording_errors)
    recording_errors.assert_called_once_with(dialog, "Recording Setup Error", error)
    assert all("int()" not in label.text() for label in dialog.findChildren(QLabel))
    assert dialog.size().toTuple() == (700, 640)
    _assert_labels_fit(dialog)
    monkeypatch.setattr(recording_dialog_module, "validate_recording_configuration", validator)
    recording_errors.reset_mock()
    dialog.apply_button.click()
    assert dialog.result() == int(QDialog.DialogCode.Accepted)
    recording_errors.assert_not_called()
