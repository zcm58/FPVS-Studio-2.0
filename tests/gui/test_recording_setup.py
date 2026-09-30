"""Registered visible Qt checks for local recording setup and launch guards."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QSettings, Qt
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
from fpvs_studio.gui import controller as controller_module
from fpvs_studio.gui import home_page as home_page_module
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.recording_dialog import RecordingSetupDialog
from fpvs_studio.gui.run_page import ParticipantLaunchDetails, RunPage
from fpvs_studio.gui.settings_dialog import AppSettingsDialog
from fpvs_studio.runtime import launcher as runtime_launcher
from fpvs_studio.runtime.recording import UNICORN_VALIDATION_NOTE
from fpvs_studio.runtime.unicorn_recorder import (
    RecorderReadinessError,
    _require_recording_snapshot,
)


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
    ("unicorn_udp", "broken saved port"), ("unknown old selection", 1000),
])
def test_recording_setup_geometry_and_validation(qtbot, background, backend, port):
    dialog = RecordingSetupDialog({"recording_backend": backend, "unicorn_udp_port": port})
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.show()
    QApplication.processEvents()
    assert (dialog.width(), dialog.height()) == (640, 560)
    _assert_labels_fit(dialog)
    if backend == "unicorn_udp":
        assert UNICORN_VALIDATION_NOTE in dialog.guidance_label.text()
        assert dialog.guidance_label.toolTip() == UNICORN_VALIDATION_NOTE
        assert "unavailable" not in dialog.guidance_label.text()
        assert "open and recording" in dialog.guidance_label.text()
        assert "raw BDF or BDF+" in dialog.guidance_label.text()
        assert "operator responsibilities" in dialog.guidance_label.text()
        assert dialog.apply_button.isEnabled() == isinstance(port, int)
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
    assert dialog.configuration == {"recording_backend": "unicorn_udp", "unicorn_udp_port": 65535}


@pytest.mark.parametrize("accepted", [False, True])
def test_settings_recording_subdialog_persists_only_apply(qtbot, tmp_path, monkeypatch, accepted):
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
        child.backend_combo.setCurrentIndex(child.backend_combo.findData("unicorn_udp"))
        child.port_edit.setText("2345")
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
        assert saved == [{"recording_backend": "unicorn_udp", "unicorn_udp_port": 2345}]
        assert "2345" in dialog.recording_summary.text()
    else:
        assert saved == []
        assert "legacy" in dialog.recording_summary.text()


def test_recording_preferences_reopen_preserve_invalid_choices(controller, tmp_path):
    path = str(tmp_path / "recording.ini")
    controller._settings = QSettings(path, QSettings.Format.IniFormat)
    original = controller.load_recording_configuration()
    assert original == {"recording_backend": None, "unicorn_udp_port": 1000}
    controller.save_recording_configuration({
        "recording_backend": "unicorn_udp", "unicorn_udp_port": 3456,
    })
    controller._settings = QSettings(path, QSettings.Format.IniFormat)
    assert controller.load_recording_configuration() == {
        "recording_backend": "unicorn_udp", "unicorn_udp_port": 3456,
    }
    controller._settings.setValue(controller_module._RECORDING_BACKEND_KEY, "removed-backend")
    controller._settings.setValue(controller_module._UNICORN_UDP_PORT_KEY, "12.5")
    controller._settings.sync()
    assert controller.load_recording_configuration() == {
        "recording_backend": "removed-backend", "unicorn_udp_port": "12.5",
    }
    assert controller._settings.value(controller_module._RECORDING_BACKEND_KEY) == "removed-backend"


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
@pytest.mark.parametrize("backend, port, expected", [
    (None, 1000, "Recording Device: BioSemi ActiveTwo"),
    ("serial", 1000, "Recording Device: BioSemi ActiveTwo"),
    ("unicorn_udp", 65535, "Recording Device: Unicorn Black Mobile Headset"),
    ("unicorn_udp", "broken saved port",
     "Recording setup invalid. Open Settings > Recording to correct it."),
    ("unknown old selection", 1000,
     "Recording setup invalid. Open Settings > Recording to correct it."),
])
def test_home_recording_device_label_fits_and_preserves_output_details(
    qtbot, controller, tmp_path, monkeypatch, background, backend, port, expected,
):
    document, window = open_created_project(controller, qtbot, tmp_path, "Home recording setup")
    recorder_probe = Mock(side_effect=AssertionError("Home refresh must not probe Recorder"))
    monkeypatch.setattr(runtime_launcher, "require_unicorn_recorder_recording", recorder_probe)
    document.set_recording_configuration({"recording_backend": backend, "unicorn_udp_port": port})
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

    if backend in (None, "serial", "unicorn_udp") and isinstance(port, int):
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


@pytest.mark.parametrize("backend, port", [
    (None, 1000), ("unicorn_udp", 65535), ("invalid", 1000),
])
def test_run_recording_summary_fits_existing_window_budget(
    qtbot, controller, tmp_path, backend, port,
):
    document, _window = open_created_project(controller, qtbot, tmp_path, "Run recording setup")
    document.set_recording_configuration({"recording_backend": backend, "unicorn_udp_port": port})
    page = RunPage(document)
    qtbot.addWidget(page)
    page.resize(1120, 720)
    page.show()
    QApplication.processEvents()
    assert_visible_children_within_parent(page)
    label = page.recording_summary
    assert label.height() >= label.heightForWidth(label.width())
    assert label.text() == document.recording_setup_summary()
