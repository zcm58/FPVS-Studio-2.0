"""Registered visible Qt checks for local recording setup and launch guards."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QLabel
from tests.gui.helpers import (
    ImmediateProgressTask,
    assert_visible_children_within_parent,
    open_created_project,
    prepare_compile_ready_project,
)

from fpvs_studio.core.enums import ExperimentCategory, RunMode
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.models import ProjectRecordingSettings
from fpvs_studio.gui import home_page as home_page_module
from fpvs_studio.gui import recording_dialog as recording_dialog_module
from fpvs_studio.gui.document import ProjectDocument
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
from fpvs_studio.triggers.brainproducts_discovery import TriggerBoxPortCandidate


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
    monkeypatch.setattr(
        recording_dialog_module, "discover_triggerbox_ports",
        Mock(side_effect=AssertionError("GUI tests must not enumerate real serial ports")),
    )
    return jobs


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


def _assert_labels_fit(widget) -> None:
    assert_visible_children_within_parent(widget)
    for label in widget.findChildren(QLabel):
        if not label.isVisible():
            continue
        if label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width())
        else:
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
    for checkbox in widget.findChildren(QCheckBox):
        if checkbox.isVisible():
            assert checkbox.width() >= checkbox.sizeHint().width()


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("backend, port", [
    (None, 1000), ("serial", 1000), ("unicorn_udp", 65535),
    ("biosemi_active_three", 1000), ("brainproducts_triggerbox", 1000),
    ("unicorn_udp", "broken saved port"), ("unknown old selection", 1000),
])
def test_recording_setup_geometry_and_validation(qtbot, background, backend, port):
    configuration = {"recording_backend": backend, "unicorn_udp_port": port}
    if backend == "brainproducts_triggerbox":
        configuration.update(
            brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
        )
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
        assert dialog.apply_button.isEnabled() == isinstance(port, int)
    elif backend == "brainproducts_triggerbox":
        assert dialog.backend_combo.currentText() == (
            "Brain Products / BrainVision (TriggerBox/Plus)"
        )
        assert dialog.brainproducts_port_edit.isVisible()
        assert dialog.brainproducts_pulse_edit.isVisible()
        assert "Start recording in BrainVision Recorder" in dialog.guidance_label.text()
        assert "high-active" in dialog.guidance_label.toolTip()
        assert "eight output switches to PC" in dialog.guidance_label.toolTip()
        assert dialog.apply_button.isEnabled()
    elif backend == "biosemi_active_three":
        assert "128-electrode" in dialog.guidance_label.toolTip()
        assert dialog.apply_button.isEnabled()
    elif backend not in (None, "serial"):
        assert dialog.backend_combo.currentData() == backend
        assert backend in dialog.backend_combo.toolTip()
        assert not dialog.apply_button.isEnabled()


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
        "brainproducts_amplifier": None, "brainproducts_sampling_rate_hz": None,
    }


@pytest.mark.parametrize("port, pulse, valid", [
    ("COM123", "1000", True), (" ", "10", False),
    ("COM123", "0", False), ("COM123", "1001", False),
    ("COM123", "broken saved pulse", False),
])
def test_triggerbox_fields_validation_and_geometry(qtbot, port, pulse, valid):
    dialog = RecordingSetupDialog(_triggerbox_configuration(
        brainproducts_serial_port=port, brainproducts_pulse_width_ms=pulse,
    ))
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    assert (dialog.width(), dialog.height()) == (700, 640)
    assert not dialog.port_edit.isEnabled()
    assert not dialog.endpoint_label.isVisible()
    assert dialog.apply_button.isEnabled() is valid
    assert "250 Hz" in dialog.brainproducts_pulse_edit.toolTip()
    assert "twice the pulse width" in dialog.brainproducts_pulse_edit.toolTip()
    _assert_labels_fit(dialog)


@pytest.mark.parametrize("amplifier, sampling_rate", [
    (None, None), ("actichamp", None), (None, 500),
    ("actichamp", 777), ("liveamp", 100), ("unknown amplifier", 500),
])
def test_triggerbox_apply_requires_supported_amplifier_and_sampling_rate(
    qtbot, amplifier, sampling_rate,
):
    original = _triggerbox_configuration(
        brainproducts_amplifier=amplifier, brainproducts_sampling_rate_hz=sampling_rate,
    )
    dialog = RecordingSetupDialog(original)
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    assert not dialog.apply_button.isEnabled()
    assert dialog.error_label.text()
    dialog.accept()
    assert dialog.result() != int(QDialog.DialogCode.Accepted)
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
    qtbot, amplifier, sampling_rate, pulse, valid, minimum,
):
    dialog = RecordingSetupDialog(_triggerbox_configuration(
        brainproducts_amplifier=amplifier,
        brainproducts_sampling_rate_hz=sampling_rate,
        brainproducts_pulse_width_ms=pulse,
    ))
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    assert dialog.apply_button.isEnabled() is valid
    assert f"{minimum} ms" in dialog.pulse_requirement_label.text()
    assert "spacing" in dialog.pulse_requirement_label.text()
    if not valid:
        assert dialog.error_label.text()
    _assert_labels_fit(dialog)


def test_triggerbox_amplifier_change_preserves_supported_rate_and_clears_unsupported(qtbot):
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
    assert not dialog.apply_button.isEnabled()
    assert {dialog.brainproducts_sampling_rate_combo.itemData(index)
            for index in range(dialog.brainproducts_sampling_rate_combo.count())} == {
        None, 250, 500, 1000,
    }
    _select_triggerbox_timing(dialog, amplifier="liveamp", sampling_rate=250)
    assert dialog.apply_button.isEnabled()


def test_triggerbox_detection_starts_once_on_first_visible_selection(
    qtbot, port_detection_jobs,
):
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
    port_detection_jobs[0].finish()
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("serial"))
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData("brainproducts_triggerbox"))
    assert len(port_detection_jobs) == 1
    dialog.detect_ports_button.click()
    assert len(port_detection_jobs) == 2


@pytest.mark.parametrize("initial_port", ["COM3", "COM123"])
def test_triggerbox_unique_detection_preserves_explicit_custom_port(
    qtbot, port_detection_jobs, initial_port,
):
    dialog = RecordingSetupDialog(_triggerbox_configuration(brainproducts_serial_port=initial_port))
    qtbot.addWidget(dialog)
    dialog.show()
    assert len(port_detection_jobs) == 1
    candidate = TriggerBoxPortCandidate("COM9", "TriggerBox Plus")
    port_detection_jobs[0].finish(candidates=(candidate,))
    expected = "COM9" if initial_port == "COM3" else initial_port
    assert dialog.brainproducts_port_edit.text() == expected
    assert dialog.brainproducts_port_combo.itemText(0) == "COM9"
    assert dialog.brainproducts_port_combo.itemData(0, Qt.ItemDataRole.ToolTipRole) == (
        candidate.description
    )
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
    dialog = RecordingSetupDialog(_triggerbox_configuration(brainproducts_serial_port=initial_port))
    qtbot.addWidget(dialog)
    dialog.show()
    port_detection_jobs[0].finish(candidates=(
        TriggerBoxPortCandidate(first_candidate_port, "TriggerBox Plus"),
        TriggerBoxPortCandidate("COM12", "TriggerBox VirtualSerial Port"),
    ))
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
    qtbot, port_detection_jobs,
):
    dialog = RecordingSetupDialog(_triggerbox_configuration(brainproducts_serial_port="COM123"))
    qtbot.addWidget(dialog)
    dialog.show()
    port_detection_jobs[0].finish()
    assert "No TriggerBox" in dialog.detection_status_label.text()
    assert dialog.brainproducts_port_edit.text() == "COM123"
    assert dialog.detect_ports_button.isEnabled()
    dialog.detect_ports_button.click()
    port_detection_jobs[1].finish(error=RuntimeError("Serial port metadata is unavailable"))
    assert "failed" in dialog.detection_status_label.text()
    assert "Serial port metadata is unavailable" in dialog.detection_status_label.toolTip()
    assert dialog.brainproducts_port_edit.text() == "COM123"
    assert dialog.apply_button.isEnabled()
    dialog.detect_ports_button.click()
    assert len(port_detection_jobs) == 3
    port_detection_jobs[2].finish(candidates=(
        TriggerBoxPortCandidate("COM123", "TriggerBox Plus"),
    ))
    assert "failed" not in dialog.detection_status_label.text()
    assert "unavailable" not in dialog.detection_status_label.toolTip()


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
@pytest.mark.parametrize("state", ["busy", "empty", "multiple", "error", "unique"])
def test_triggerbox_discovery_states_fit_minimum_dialog_with_full_metadata_paths(
    qtbot, port_detection_jobs, background, state,
):
    dialog = RecordingSetupDialog(_triggerbox_configuration(
        brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=100,
    ))
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.show()
    description = "Brain Products GmbH TriggerBox rev. 02 VirtualSerial Port (COM1234567890)"
    candidate = TriggerBoxPortCandidate("COM1234567890", description)
    if state == "empty":
        port_detection_jobs[0].finish()
    elif state == "multiple":
        port_detection_jobs[0].finish(candidates=(
            candidate, TriggerBoxPortCandidate("COM12", "TriggerBox Plus"),
        ))
    elif state == "error":
        error = "Unable to enumerate TriggerBox ports: Windows device metadata access failed. " * 8
        port_detection_jobs[0].finish(error=RuntimeError(error))
        assert dialog.detection_status_label.toolTip() == error
    elif state == "unique":
        port_detection_jobs[0].finish(candidates=(candidate,))
    QApplication.processEvents()
    assert (dialog.width(), dialog.height()) == (700, 640)
    assert not dialog.apply_button.isEnabled()  # 10 ms is below the 20 ms minimum at 100 Hz.
    assert dialog.error_label.text()
    assert dialog.detection_status_label.wordWrap()
    assert dialog.pulse_requirement_label.wordWrap()
    assert dialog.detection_status_label.textFormat() == Qt.TextFormat.PlainText
    _assert_labels_fit(dialog)
    if state in ("multiple", "unique"):
        assert description in dialog.detection_status_label.toolTip()
        assert dialog.brainproducts_port_combo.itemData(0, Qt.ItemDataRole.ToolTipRole) == (
            description
        )


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
        "brainproducts_amplifier": "actichamp", "brainproducts_sampling_rate_hz": 500,
    }


@pytest.mark.parametrize("edited_backend, selected_backend", [
    ("brainproducts_triggerbox", "serial"),
    ("brainproducts_triggerbox", "unicorn_udp"),
    ("unicorn_udp", "brainproducts_triggerbox"),
])
def test_switch_from_invalid_device_draft_applies_last_valid_inactive_values(
    qtbot, edited_backend, selected_backend,
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
    assert not dialog.apply_button.isEnabled()
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData(selected_backend))
    assert dialog.apply_button.isEnabled()
    QApplication.processEvents()
    _assert_labels_fit(dialog)
    dialog.backend_combo.setCurrentIndex(dialog.backend_combo.findData(edited_backend))
    assert not dialog.apply_button.isEnabled()
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
def test_settings_recording_subdialog_persists_only_apply(
    qtbot, tmp_path, monkeypatch, accepted, backend,
):
    saved = []
    original = {"recording_backend": None, "unicorn_udp_port": 1000}
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path, recording_configuration=original,
        on_recording_configuration_changed=saved.append,
    )
    qtbot.addWidget(dialog)
    dialog.tabs.setCurrentIndex(2)
    dialog.show()
    def fake_exec(child):
        child.backend_combo.setCurrentIndex(child.backend_combo.findData(backend))
        child.port_edit.setText("2345")
        child.brainproducts_port_edit.setText("COM123")
        child.brainproducts_pulse_edit.setText("20")
        _select_triggerbox_timing(child)
        child.accept() if accepted else child.reject()
        return child.result()
    monkeypatch.setattr(RecordingSetupDialog, "exec", fake_exec)
    dialog.recording_setup_button.click()
    QApplication.processEvents()
    _assert_labels_fit(dialog)
    help_label = dialog.findChild(QLabel, "settings_recording_help")
    assert help_label is not None
    assert "require Recorder to be open and recording" in help_label.text()
    assert "blocked until" not in help_label.text()
    if accepted:
        assert saved == [{
            "recording_backend": backend,
            "unicorn_udp_port": 2345 if backend == "unicorn_udp" else 1000,
            "brainproducts_serial_port": (
                "COM123" if backend == "brainproducts_triggerbox" else "COM3"
            ),
            "brainproducts_pulse_width_ms": 20 if backend == "brainproducts_triggerbox" else 10,
            "brainproducts_amplifier": (
                "actichamp" if backend == "brainproducts_triggerbox" else None
            ),
            "brainproducts_sampling_rate_hz": (
                500 if backend == "brainproducts_triggerbox" else None
            ),
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
        first_window.home_page.recording_summary.text()
        == "Recording Device: Unicorn Black Mobile Headset"
    )
    second, second_window = open_created_project(controller, qtbot, tmp_path, "Other study")
    assert second_window.home_page.recording_summary.text() == "Recording Device: BioSemi ActiveTwo"
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
    assert len(tasks) == 1
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
    assert window.home_page.recording_summary.text() == (
        "Recording Device: Unicorn Black Mobile Headset"
    )
    assert "127.0.0.1:1000" in window.home_page.recording_summary.toolTip()
    _assert_labels_fit(window.home_page)
    document.set_experiment_test_mode_enabled(True)
    assert "No marker output" in document.recording_setup_summary()
    assert window.home_page.recording_summary.text() == "No marker output (Test/Pilot)"


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

    ready.assert_called_once_with()
    assert trace == ["ready", "engine", "preflight", "reserve", "execute"]
    assert errors == []
    assert not window.is_launch_busy()
    assert page._active_launch_task is None
    assert "Recorder check before launch" in document.recording_setup_summary()


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize(
    "backend, port, expected",
    [
        (None, 1000, "Recording Device: BioSemi ActiveTwo"),
        ("serial", 1000, "Recording Device: BioSemi ActiveTwo"),
        ("biosemi_active_three", 1000, "Recording Device: BioSemi ActiveThree (128 electrodes)"),
        (
            "brainproducts_triggerbox", 1000,
            "Recording Device: Brain Products / BrainVision (TriggerBox/Plus)",
        ),
        ("unicorn_udp", 65535, "Recording Device: Unicorn Black Mobile Headset"),
        (
            "unicorn_udp",
            "broken saved port",
            "Recording setup invalid. Open Settings > Recording to correct it.",
        ),
        (
            "unknown old selection",
            1000,
            "Recording setup invalid. Open Settings > Recording to correct it.",
        ),
    ],
)
def test_home_recording_device_label_fits_and_preserves_output_details(
    qtbot,
    controller,
    tmp_path,
    monkeypatch,
    background,
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
        "serial", "biosemi_active_three", "brainproducts_triggerbox", "unicorn_udp",
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
        if backend == "brainproducts_triggerbox":
            configuration.update(
                brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
            )
        document.set_recording_configuration(configuration)
    palette = window.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    window.setPalette(palette)
    window.resize(1120, 720)
    window.show()
    page = window.home_page
    label = page.recording_summary

    for setup_ready in (False, True):
        if setup_ready:
            prepare_compile_ready_project(window, tmp_path / "home-recording-assets")
        QApplication.processEvents()
        assert label.text() == expected
        assert label.toolTip() == document.recording_setup_summary()
        assert label.accessibleDescription() == document.recording_setup_summary()
        assert label.textFormat() == Qt.TextFormat.PlainText
        assert label.alignment() == Qt.AlignmentFlag.AlignCenter
        assert label.geometry().bottom() < page.launch_button.geometry().top()
        _assert_labels_fit(page)

    if backend in (
        None, "serial", "biosemi_active_three", "brainproducts_triggerbox", "unicorn_udp",
    ) and isinstance(port, int):
        document.set_experiment_test_mode_enabled(True)
        QApplication.processEvents()
        assert label.text() == "No marker output (Test/Pilot)"
        _assert_labels_fit(page)
        document.set_experiment_test_mode_enabled(False)
        assert label.text() == expected
    recorder_probe.assert_not_called()


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_home_recording_device_name_extension_and_pilot_output(
    qtbot, tmp_path, monkeypatch, background,
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
    page.resize(1120, 720)
    page.show()
    document.set_recording_configuration({
        "recording_backend": "unicorn_udp", "unicorn_udp_port": 1000,
    })
    QApplication.processEvents()
    assert page.recording_summary.text() == f"Recording Device: {name}"
    _assert_labels_fit(page)
    document.set_attentional_blink_pilot_mode_enabled(True)
    QApplication.processEvents()
    assert page.recording_summary.text() == "No marker output (Test/Pilot)"
    _assert_labels_fit(page)
    document.set_attentional_blink_pilot_mode_enabled(False)
    assert page.recording_summary.text() == f"Recording Device: {name}"
    document.set_recording_configuration({"recording_backend": "serial"})
    assert page.recording_summary.text() == "Recording Device: BioSemi ActiveTwo"


@pytest.mark.parametrize(
    "backend, port",
    [
        (None, 1000),
        ("biosemi_active_three", 1000),
        ("brainproducts_triggerbox", 1000),
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
        if backend == "brainproducts_triggerbox":
            configuration.update(
                brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
            )
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


def test_recording_settings_failed_save_preserves_accepted_device(qtbot, tmp_path, monkeypatch):
    original = {"recording_backend": "serial", "unicorn_udp_port": 1000}
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path,
        recording_configuration=original,
        on_recording_configuration_changed=Mock(side_effect=PermissionError("locked")),
    )
    qtbot.addWidget(dialog)
    dialog.tabs.setCurrentIndex(2)
    dialog.show()

    def fake_exec(child):
        child.backend_combo.setCurrentIndex(child.backend_combo.findData("unicorn_udp"))
        child.accept()
        return child.result()

    monkeypatch.setattr(RecordingSetupDialog, "exec", fake_exec)
    dialog.recording_setup_button.click()
    QApplication.processEvents()
    assert "not saved" in dialog.recording_summary.text()
    assert dialog._recording_configuration == original
    _assert_labels_fit(dialog)
