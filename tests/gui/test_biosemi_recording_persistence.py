"""Registered Qt binding checks for project-owned BioSemi serial-port preferences."""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QDialog
from tests.gui.helpers import assert_visible_children_within_parent, open_created_project

from fpvs_studio.core.models import ProjectRecordingSettings
from fpvs_studio.core.serialization import load_project_file
from fpvs_studio.gui import settings_dialog as settings_module
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.settings_dialog import AppSettingsDialog


def _recording(backend="serial"):
    return ProjectRecordingSettings(recording_backend=backend).model_dump(mode="json")


def _stub_recording_dialog(monkeypatch, *, backend="serial", accepted=True, port="COM193"):
    contexts = []

    class Dialog:
        configuration = _recording(backend)
        biosemi_serial_port = port

        def __init__(self, configuration, parent=None, **context):
            contexts.append((dict(configuration), context))

        def exec(self):
            return int(QDialog.DialogCode.Accepted if accepted else QDialog.DialogCode.Rejected)

    monkeypatch.setattr(settings_module, "RecordingSetupDialog", Dialog)
    return contexts


def _document(tmp_path):
    document = ProjectDocument.create_new(parent_dir=tmp_path, project_name="BioSemi project")
    document.update_trigger_settings(
        serial_port="COM7", baudrate=57600, pulse_width_ms=17,
        reset_code=0, reset_delay_ms=9,
    )
    document.save()
    return document


@pytest.mark.parametrize("backend", ["serial", "biosemi_active_three"])
@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_settings_biosemi_apply_updates_only_saved_port_and_device_and_keeps_drafts(
    qapp, qtbot, tmp_path, monkeypatch, backend, background,
):
    document = _document(tmp_path)
    before = load_project_file(document.project_file_path)
    document.update_protocol_settings(base_hz=5.0)
    contexts = _stub_recording_dialog(monkeypatch, backend=backend)
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path,
        recording_configuration=document.recording_configuration,
        biosemi_serial_port="COM7", biosemi_serial_baudrate=57600,
        on_recording_configuration_changed=document.save_recording_configuration,
    )
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.tabs.setCurrentIndex(next(
        index for index in range(dialog.tabs.count()) if dialog.tabs.tabText(index) == "Recording"
    ))
    dialog.show()
    dialog._show_recording_setup()
    QApplication.processEvents()

    assert contexts[0][1] == {
        "biosemi_serial_port": "COM7", "biosemi_serial_baudrate": 57600,
    }
    saved = load_project_file(document.project_file_path)
    expected_triggers = before.settings.triggers.model_dump()
    expected_triggers["serial_port"] = "COM193"
    assert saved.settings.triggers.model_dump() == expected_triggers
    assert saved.settings.recording.recording_backend == backend
    assert saved.settings.protocol == before.settings.protocol
    assert document.project.settings.protocol.base_hz == 5.0 and document.dirty
    assert document.recording_launch_options()["serial_port"] == "COM193"
    assert "serial_port" not in document.recording_configuration
    assert "COM193" in dialog.recording_summary.text()
    assert dialog._biosemi_serial_baudrate == 57600
    assert (dialog.width(), dialog.height()) == (700, 560)
    assert_visible_children_within_parent(dialog)
    assert dialog.recording_summary.height() >= dialog.recording_summary.heightForWidth(
        dialog.recording_summary.width(),
    )
    document.save()
    reopened = ProjectDocument.open_existing(document.project_root)
    assert reopened.project.settings.triggers.serial_port == "COM193"
    assert reopened.project.settings.triggers.baudrate == 57600


@pytest.mark.parametrize("failure", [False, True])
def test_settings_biosemi_cancel_or_save_failure_retains_port_device_and_context(
    qapp, qtbot, tmp_path, monkeypatch, failure,
):
    document = _document(tmp_path)
    before = document.project_file_path.read_bytes()
    contexts = _stub_recording_dialog(monkeypatch, accepted=failure)
    save = Mock(side_effect=OSError("project is read-only"))
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path, recording_configuration=document.recording_configuration,
        biosemi_serial_port="COM7", biosemi_serial_baudrate=57600,
        on_recording_configuration_changed=save,
    )
    qtbot.addWidget(dialog)
    dialog._show_recording_setup()
    assert save.call_count == int(failure)
    assert document.project_file_path.read_bytes() == before
    assert dialog._biosemi_serial_port == "COM7"
    assert dialog._recording_configuration == document.recording_configuration
    dialog._show_recording_setup()
    assert contexts[-1][1]["biosemi_serial_port"] == "COM7"
    if failure:
        assert "not saved" in dialog.recording_summary.text()


def test_recording_document_failure_keeps_port_and_unrelated_drafts(qapp, tmp_path, monkeypatch):
    document = _document(tmp_path)
    before_disk = document.project_file_path.read_bytes()
    document.update_protocol_settings(base_hz=5.0)
    before_live = document.project.model_dump(mode="json")
    monkeypatch.setattr(
        "fpvs_studio.gui.document.save_project_recording_settings",
        Mock(side_effect=PermissionError("locked project")),
    )
    with pytest.raises(PermissionError, match="locked project"):
        document.save_recording_configuration({**_recording(), "serial_port": "COM193"})
    assert document.project_file_path.read_bytes() == before_disk
    assert document.project.model_dump(mode="json") == before_live and document.dirty


def test_other_recording_devices_do_not_include_a_biosemi_port_edit(
    qapp, qtbot, tmp_path, monkeypatch,
):
    contexts = _stub_recording_dialog(monkeypatch, backend="unicorn_udp")
    save = Mock()
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path, recording_configuration=_recording(),
        biosemi_serial_port="COM7", biosemi_serial_baudrate=57600,
        on_recording_configuration_changed=save,
    )
    qtbot.addWidget(dialog)
    dialog._show_recording_setup()
    assert contexts[0][1]["biosemi_serial_port"] == "COM7"
    assert save.call_args.args == (_recording("unicorn_udp"),)
    assert dialog._biosemi_serial_port == "COM7"


def test_computer_default_changes_and_reset_preserve_project_serial_context(
    qapp, qtbot, tmp_path, monkeypatch,
):
    contexts = _stub_recording_dialog(monkeypatch, backend="biosemi_active_three")
    project_save = Mock()
    default_save = Mock()
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path, recording_configuration=_recording(),
        default_recording_configuration=_recording(), recording_uses_default=True,
        biosemi_serial_port="COM7", biosemi_serial_baudrate=57600,
        on_default_recording_configuration_changed=default_save,
        on_recording_configuration_changed=project_save,
        on_use_default_recording_configuration=Mock(),
    )
    qtbot.addWidget(dialog)
    dialog._show_default_recording_setup()
    assert contexts[0][1] == {"computer_default": True}
    assert default_save.call_args.args == (_recording("biosemi_active_three"),)
    project_save.assert_not_called()
    dialog._use_default_recording_setup()
    assert dialog._biosemi_serial_port == "COM7"
    dialog._show_recording_setup()
    assert contexts[-1][1] == {
        "biosemi_serial_port": "COM7", "biosemi_serial_baudrate": 57600,
    }


def test_controller_forwards_active_project_port_and_baud_to_settings(
    controller, qtbot, tmp_path, monkeypatch,
):
    document, _window = open_created_project(controller, qtbot, tmp_path)
    document.update_trigger_settings(serial_port="COM193", baudrate=57600)
    contexts = []

    def inspect(dialog):
        qtbot.addWidget(dialog)
        contexts.append((dialog._biosemi_serial_port, dialog._biosemi_serial_baudrate))
        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(AppSettingsDialog, "exec", inspect)
    controller.show_settings_dialog()
    assert contexts == [("COM193", 57600)]
    assert "serial_port" not in controller.load_default_recording_configuration()
    assert json.loads(document.project_file_path.read_text())["settings"]["triggers"][
        "serial_port"
    ] == "COM3"
