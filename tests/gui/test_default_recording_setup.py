"""Registered Qt coverage for computer recording defaults and project inheritance."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton
from tests.gui.helpers import (
    assert_visible_children_within_parent,
    open_created_project,
    select_settings_category,
)

from fpvs_studio.core.models import ProjectRecordingSettings
from fpvs_studio.gui import controller as controller_module
from fpvs_studio.gui import settings_dialog as settings_dialog_module
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.document_support import DocumentError
from fpvs_studio.gui.parallel_port_selector import ParallelPortSelector
from fpvs_studio.gui.recording_dialog import (
    DefaultRecordingHardwareDialog,
    RecordingSetupEditor,
)
from fpvs_studio.gui.root_folder_setup_dialog import RootFolderSetupDialog
from fpvs_studio.gui.settings_dialog import AppSettingsDialog

_BACKENDS = (
    "serial", "biosemi_active_three", "brainproducts_triggerbox", "brainproducts_parallel",
    "unicorn_udp",
)
_PROMPT = "Please select your default EEG hardware. You can change this choice later."


@pytest.fixture(autouse=True)
def _no_hardware_discovery(monkeypatch):
    """Preference tests never need to enumerate hardware."""
    monkeypatch.setattr(RecordingSetupEditor, "_maybe_detect_ports", lambda _self: None)
    monkeypatch.setattr(ParallelPortSelector, "detect_ports", lambda _self: None)


def _configuration(backend: str, **values: object) -> dict[str, object]:
    return ProjectRecordingSettings(recording_backend=backend, **values).model_dump(mode="json")


def _controller(qapp, tmp_path: Path, monkeypatch) -> StudioController:
    controller = StudioController(qapp)
    controller._settings = QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    controller.startup_update_checks_enabled = False
    sharing = SimpleNamespace(startup=lambda *_args: None)
    monkeypatch.setattr(controller, "_data_sharing", lambda: sharing)
    return controller


@pytest.mark.parametrize("backend", _BACKENDS)
def test_hardware_picker_requires_an_explicit_choice(qtbot, backend):
    dialog = DefaultRecordingHardwareDialog()
    qtbot.addWidget(dialog)
    assert dialog.selected_backend is None
    assert not dialog.continue_button.isEnabled()
    assert [dialog.hardware_combo.itemData(i) for i in range(dialog.hardware_combo.count())] == [
        None, *_BACKENDS,
    ]
    assert _PROMPT in [label.text() for label in dialog.findChildren(QLabel)]
    dialog.hardware_combo.setCurrentIndex(dialog.hardware_combo.findData(backend))
    assert dialog.selected_backend == backend
    assert dialog.continue_button.isEnabled()
    dialog.continue_button.click()
    assert dialog.result() == QDialog.DialogCode.Accepted


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("error_message", ["", "The saved EEG hardware choice is invalid."])
@pytest.mark.parametrize("backend", ["brainproducts_triggerbox", "brainproducts_parallel"])
def test_hardware_picker_fits_minimum_size(qtbot, background, error_message, backend):
    dialog = DefaultRecordingHardwareDialog(error_message=error_message)
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.hardware_combo.setCurrentIndex(dialog.hardware_combo.findData(backend))
    dialog.resize(640, 300)
    dialog.show()
    QApplication.processEvents()
    assert dialog.size().toTuple() == (640, 300)
    assert_visible_children_within_parent(dialog)
    assert dialog.hardware_combo.width() >= (
        dialog.hardware_combo.fontMetrics().horizontalAdvance(dialog.hardware_combo.currentText())
        + 30
    )
    for label in dialog.findChildren(QLabel):
        if not label.isVisible():
            continue
        if label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width())
        else:
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.result() == QDialog.DialogCode.Rejected


@pytest.mark.parametrize("backend", _BACKENDS)
def test_first_run_selects_root_before_hardware_and_persists_across_restart(
    qtbot, qapp, tmp_path, monkeypatch, backend,
):
    controller = _controller(qapp, tmp_path, monkeypatch)
    root = tmp_path / "Research experiments"
    root.mkdir()
    order = []

    def choose_root(_dialog):
        order.append("root guidance")
        return int(QDialog.DialogCode.Accepted)

    def root_picker(*_args):
        order.append("root picker")
        return str(root)

    def choose_hardware(dialog):
        qtbot.addWidget(dialog)
        order.append("hardware")
        assert controller.load_fpvs_root_dir() == root
        dialog.hardware_combo.setCurrentIndex(dialog.hardware_combo.findData(backend))
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(RootFolderSetupDialog, "exec", choose_root)
    monkeypatch.setattr(controller_module.QFileDialog, "getExistingDirectory", root_picker)
    monkeypatch.setattr(DefaultRecordingHardwareDialog, "exec", choose_hardware)
    controller.show_welcome()
    qtbot.addWidget(controller.welcome_window)
    assert order == ["root guidance", "root picker", "hardware"]
    assert controller.load_default_recording_configuration() == _configuration(backend)
    stored = controller._settings.value(controller_module._DEFAULT_RECORDING_CONFIGURATION_KEY)
    assert json.loads(stored) == _configuration(backend)

    restarted = _controller(qapp, tmp_path, monkeypatch)
    monkeypatch.setattr(
        DefaultRecordingHardwareDialog, "exec",
        lambda _: pytest.fail("Saved default must be reused"),
    )
    assert restarted.ensure_fpvs_root_configured()
    assert restarted.load_default_recording_configuration() == _configuration(backend)


def test_saved_root_without_hardware_is_prompted_and_exit_keeps_root(
    qtbot, qapp, tmp_path, monkeypatch,
):
    controller = _controller(qapp, tmp_path, monkeypatch)
    controller.save_fpvs_root_dir(tmp_path)
    quits = []
    monkeypatch.setattr(qapp, "quit", lambda: quits.append(True))
    monkeypatch.setattr(
        RootFolderSetupDialog, "exec", lambda _: pytest.fail("Existing root should be reused"),
    )

    def reject_hardware(dialog):
        qtbot.addWidget(dialog)
        assert dialog.selected_backend is None
        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(DefaultRecordingHardwareDialog, "exec", reject_hardware)
    controller.show_welcome()
    assert quits == [True]
    assert controller.welcome_window is None
    assert controller.load_fpvs_root_dir() == tmp_path
    assert controller.load_default_recording_configuration() is None


@pytest.mark.parametrize("invalid", ["not JSON", '{"recording_backend":"unknown"}'])
def test_invalid_saved_hardware_is_repaired_explicitly(
    qtbot, qapp, tmp_path, monkeypatch, invalid,
):
    controller = _controller(qapp, tmp_path, monkeypatch)
    controller.save_fpvs_root_dir(tmp_path)
    controller._settings.setValue(controller_module._DEFAULT_RECORDING_CONFIGURATION_KEY, invalid)
    controller._settings.sync()
    with pytest.raises(ValueError):
        controller.load_default_recording_configuration()
    dialogs = []

    def choose_hardware(dialog):
        dialogs.append(dialog)
        qtbot.addWidget(dialog)
        assert dialog.selected_backend is None
        assert dialog.error_label.text()
        dialog.hardware_combo.setCurrentIndex(dialog.hardware_combo.findData("biosemi_active_three"))
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(DefaultRecordingHardwareDialog, "exec", choose_hardware)
    assert controller.ensure_fpvs_root_configured()
    assert len(dialogs) == 1
    assert controller.load_default_recording_configuration() == _configuration(
        "biosemi_active_three",
    )


def test_rejecting_invalid_saved_hardware_never_installs_a_fallback(
    qtbot, qapp, tmp_path, monkeypatch,
):
    controller = _controller(qapp, tmp_path, monkeypatch)
    controller.save_fpvs_root_dir(tmp_path)
    controller._settings.setValue(
        controller_module._DEFAULT_RECORDING_CONFIGURATION_KEY, "bad JSON",
    )
    quits = []
    monkeypatch.setattr(qapp, "quit", lambda: quits.append(True))

    def reject_hardware(dialog):
        qtbot.addWidget(dialog)
        assert dialog.error_label.text()
        assert dialog.selected_backend is None
        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(DefaultRecordingHardwareDialog, "exec", reject_hardware)
    assert not controller.ensure_fpvs_root_configured()
    assert quits == [True]
    assert controller._settings.value(controller_module._DEFAULT_RECORDING_CONFIGURATION_KEY) == (
        "bad JSON"
    )


def test_failed_first_run_save_allows_explicit_retry(qtbot, qapp, tmp_path, monkeypatch):
    controller = _controller(qapp, tmp_path, monkeypatch)
    controller.save_fpvs_root_dir(tmp_path)
    save = controller.save_default_recording_configuration
    errors = []
    attempts = []

    def save_after_retry(configuration):
        attempts.append(configuration)
        if len(attempts) == 1:
            raise OSError("Preferences are read-only")
        save(configuration)

    def choose_hardware(dialog):
        qtbot.addWidget(dialog)
        errors.append(dialog.error_label.text())
        assert dialog.selected_backend is None
        dialog.hardware_combo.setCurrentIndex(dialog.hardware_combo.findData("unicorn_udp"))
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(controller, "save_default_recording_configuration", save_after_retry)
    monkeypatch.setattr(DefaultRecordingHardwareDialog, "exec", choose_hardware)
    assert controller.ensure_fpvs_root_configured()
    assert len(attempts) == 2
    assert errors[0] == ""
    assert errors[1]
    assert controller.load_default_recording_configuration() == _configuration("unicorn_udp")


def test_changed_computer_default_updates_inherited_project_but_preserves_override(
    controller, qtbot, tmp_path,
):
    document, window = open_created_project(controller, qtbot, tmp_path)
    assert document.uses_default_recording_configuration
    saved_project = (document.project_root / "project.json").read_bytes()
    controller.save_default_recording_configuration(
        _configuration("unicorn_udp", unicorn_udp_port=5432),
    )
    QApplication.processEvents()
    assert document.recording_configuration == _configuration("unicorn_udp", unicorn_udp_port=5432)
    assert document.project.settings.recording is None
    assert (document.project_root / "project.json").read_bytes() == saved_project
    assert "Unicorn" in window.home_page.recording_summary.text()
    controller.save_recording_configuration(_configuration("biosemi_active_three"))
    controller.save_default_recording_configuration(_configuration("serial"))
    QApplication.processEvents()
    assert not document.uses_default_recording_configuration
    assert document.recording_configuration == _configuration("biosemi_active_three")
    assert "ActiveThree" in window.home_page.recording_summary.text()
    controller.use_default_recording_configuration()
    QApplication.processEvents()
    assert document.uses_default_recording_configuration
    assert document.recording_configuration == _configuration("serial")
    assert ProjectDocument.open_existing(document.project_root).project.settings.recording is None
    assert "ActiveTwo" in window.home_page.recording_summary.text()


def test_actichamp_project_port_and_timing_survive_computer_default_changes(
    controller, qtbot, tmp_path,
):
    initial = _configuration(
        "brainproducts_triggerbox", brainproducts_serial_port="COM4",
        brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=100,
        brainproducts_pulse_width_ms=20,
    )
    override = _configuration(
        "brainproducts_triggerbox", brainproducts_serial_port="COM3",
        brainproducts_amplifier="actichamp", brainproducts_sampling_rate_hz=500,
    )
    replacement = _configuration(
        "brainproducts_triggerbox", brainproducts_serial_port="COM9",
        brainproducts_amplifier="liveamp", brainproducts_sampling_rate_hz=1000,
        brainproducts_pulse_width_ms=4,
    )
    controller.save_default_recording_configuration(initial)
    document, _window = open_created_project(controller, qtbot, tmp_path)
    assert document.uses_default_recording_configuration
    assert document.recording_configuration == initial
    controller.save_recording_configuration(override)
    saved_project = (document.project_root / "project.json").read_bytes()

    controller.save_default_recording_configuration(replacement)

    assert not document.uses_default_recording_configuration
    assert document.recording_configuration == override
    assert document.validate_recording_launch() == "brainproducts_triggerbox"
    assert (document.project_root / "project.json").read_bytes() == saved_project
    reopened = ProjectDocument.open_existing(document.project_root)
    assert reopened.recording_configuration == override
    controller.use_default_recording_configuration()
    assert document.uses_default_recording_configuration
    assert document.recording_configuration == replacement
    with pytest.raises(DocumentError, match="Confirm this project's"):
        document.validate_recording_launch()
    assert ProjectDocument.open_existing(document.project_root).project.settings.recording is None


@pytest.mark.parametrize("uses_default", [False, True])
def test_inline_default_save_updates_inheritance_without_writing_project(
    controller, qtbot, tmp_path, monkeypatch, uses_default,
):
    controller.save_default_recording_configuration(_configuration("serial"))
    document, _window = open_created_project(controller, qtbot, tmp_path)
    if not uses_default:
        controller.save_recording_configuration(_configuration("biosemi_active_three"))
    previous_recording = document.recording_configuration
    saved_project = document.project_file_path.read_bytes()
    project_save = Mock(wraps=controller.save_recording_configuration)
    monkeypatch.setattr(controller, "save_recording_configuration", project_save)
    replacement = _configuration("unicorn_udp", unicorn_udp_port=5432)

    def save_default(dialog):
        qtbot.addWidget(dialog)
        select_settings_category(dialog, "Recording")
        dialog.show()
        editor = dialog.recording_editor
        editor.backend_combo.setCurrentIndex(editor.backend_combo.findData("unicorn_udp"))
        editor.port_edit.setText("5432")
        dialog.save_default_recording_button.click()
        assert dialog.isVisible()
        assert dialog._default_recording_configuration == replacement
        assert dialog._recording_configuration == (
            replacement if uses_default else previous_recording
        )
        assert dialog._recording_uses_default == uses_default
        assert ("Unicorn" if uses_default else "ActiveThree") in dialog.recording_summary.text()
        dialog.reject()
        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(AppSettingsDialog, "exec", save_default)
    controller.show_settings_dialog()
    project_save.assert_not_called()
    assert controller.load_default_recording_configuration() == replacement
    assert document.uses_default_recording_configuration == uses_default
    assert document.recording_configuration == (
        replacement if uses_default else previous_recording
    )
    assert document.project_file_path.read_bytes() == saved_project


def test_settings_default_is_editable_without_a_project(qtbot, qapp, tmp_path, monkeypatch):
    controller = _controller(qapp, tmp_path, monkeypatch)
    controller.save_fpvs_root_dir(tmp_path)
    controller.save_default_recording_configuration(_configuration("serial"))

    def use_settings(dialog):
        qtbot.addWidget(dialog)
        select_settings_category(dialog, "Recording")
        dialog.show()
        assert dialog.save_default_recording_button.isEnabled()
        assert dialog.apply_recording_button.isHidden()
        assert dialog.use_default_recording_button.isHidden()
        editor = dialog.recording_editor
        assert editor.biosemi_port_selector.isHidden()
        editor.backend_combo.setCurrentIndex(editor.backend_combo.findData("unicorn_udp"))
        dialog.save_default_recording_button.click()
        assert dialog.isVisible()
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(AppSettingsDialog, "exec", use_settings)
    controller.show_settings_dialog()
    assert controller.main_window is None
    assert controller.load_default_recording_configuration() == _configuration("unicorn_udp")


@pytest.mark.parametrize("size", [(760, 520), (1120, 720)])
@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("long_label", [False, True])
def test_welcome_settings_fits_and_changes_default_without_a_project(
    controller, qtbot, monkeypatch, size, background, long_label,
):
    welcome = controller.welcome_window
    assert controller.main_window is None
    assert welcome.settings_button.text() == "Settings…"
    if long_label:
        welcome.settings_button.setText("Default EEG hardware settings for this research computer")
    palette = welcome.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    welcome.setPalette(palette)
    welcome._apply_theme_styles()
    welcome.resize(*size)
    welcome.show()
    QApplication.processEvents()
    buttons = (
        welcome.create_button,
        welcome.import_project_button,
        welcome.manage_projects_button,
        welcome.root_folder_setup_button,
        welcome.settings_button,
    )
    assert welcome.size().toTuple() == size
    assert len({button.width() for button in buttons}) == 1
    assert welcome._action_columns == (1 if long_label else 2)
    assert welcome.action_layout.getItemPosition(
        welcome.action_layout.indexOf(welcome.settings_button),
    ) == ((4, 0, 1, 1) if long_label else (2, 0, 1, 2))
    assert_visible_children_within_parent(welcome)
    for button in buttons:
        assert button.contentsRect().width() >= (
            button.fontMetrics().horizontalAdvance(button.text())
        )
    for label in welcome.findChildren(QLabel):
        if not label.isVisible():
            continue
        if label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width())
        else:
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())

    settings_calls = []

    def use_settings(dialog):
        qtbot.addWidget(dialog)
        settings_calls.append(True)
        assert dialog.save_default_recording_button.isEnabled()
        assert dialog.apply_recording_button.isHidden()
        editor = dialog.recording_editor
        editor.backend_combo.setCurrentIndex(editor.backend_combo.findData("unicorn_udp"))
        dialog.save_default_recording_button.click()
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(AppSettingsDialog, "exec", use_settings)
    welcome.set_import_busy(True)
    QApplication.processEvents()
    assert all(not button.isEnabled() for button in buttons)
    assert_visible_children_within_parent(welcome)
    qtbot.mouseClick(welcome.settings_button, Qt.MouseButton.LeftButton)
    assert settings_calls == []
    welcome.set_import_busy(False)
    QApplication.processEvents()
    assert all(button.isEnabled() for button in buttons)
    with qtbot.waitSignal(welcome.settings_requested):
        qtbot.mouseClick(welcome.settings_button, Qt.MouseButton.LeftButton)
    assert settings_calls == [True]
    assert controller.main_window is None
    assert controller.load_default_recording_configuration() == _configuration("unicorn_udp")


def test_failed_preference_sync_does_not_change_live_hardware(controller, qtbot, tmp_path):
    document, _window = open_created_project(controller, qtbot, tmp_path)
    settings = controller._settings

    class UnwritableSettings:
        def value(self, *args, **kwargs):
            return settings.value(*args, **kwargs)

        def setValue(self, *_args):
            pass

        def sync(self):
            pass

        def status(self):
            return QSettings.Status.AccessError

    controller._settings = UnwritableSettings()
    with pytest.raises(OSError):
        controller.save_default_recording_configuration(_configuration("unicorn_udp"))
    assert document.recording_configuration == _configuration("serial")
    assert controller.load_default_recording_configuration() == _configuration("serial")


@pytest.mark.parametrize("cancel", [False, True])
def test_settings_cancel_and_failed_save_retain_computer_default(
    qtbot, tmp_path, monkeypatch, cancel,
):
    popup = Mock()
    monkeypatch.setattr(settings_dialog_module, "_show_error_dialog", popup)
    saves = []
    error = PermissionError(13, "Access is denied", str(tmp_path / "preferences.ini"))

    def fail_save(configuration):
        saves.append(configuration)
        raise error

    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path,
        default_recording_configuration=_configuration("serial"),
        on_default_recording_configuration_changed=fail_save,
    )
    qtbot.addWidget(dialog)
    editor = dialog.recording_editor
    editor.backend_combo.setCurrentIndex(editor.backend_combo.findData("unicorn_udp"))
    assert saves == []
    if cancel:
        dialog.reject()
        popup.assert_not_called()
        assert saves == []
    else:
        dialog.save_default_recording_button.click()
        assert len(saves) == 1
        assert ProjectRecordingSettings.model_validate(saves[0]).model_dump(mode="json") == (
            _configuration("unicorn_udp")
        )
        popup.assert_called_once_with(dialog, "Save Default Recording Setup Error", error)
    assert "ActiveTwo" in dialog.default_recording_summary.text()
    assert not dialog.default_recording_summary.toolTip()
    assert dialog._default_recording_configuration == _configuration("serial")
    assert editor.backend_combo.currentData() == "unicorn_udp"
    if not cancel:
        dialog.save_default_recording_button.click()
        assert len(saves) == 2
    assert dialog._default_recording_configuration == _configuration("serial")


def test_failed_project_reset_retains_override_and_retry_action(qtbot, tmp_path, monkeypatch):
    popup = Mock()
    monkeypatch.setattr(settings_dialog_module, "_show_error_dialog", popup)
    attempts = []
    error = PermissionError(13, "Access is denied", str(tmp_path / "project.json"))

    def fail_reset():
        attempts.append(True)
        raise error

    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path,
        recording_configuration=_configuration("biosemi_active_three"),
        on_recording_configuration_changed=lambda _: None,
        default_recording_configuration=_configuration("serial"),
        recording_uses_default=False,
        on_use_default_recording_configuration=fail_reset,
    )
    qtbot.addWidget(dialog)
    dialog.use_default_recording_button.click()
    assert attempts == [True]
    popup.assert_called_once_with(dialog, "Reset Recording Setup Error", error)
    assert "ActiveThree" in dialog.recording_summary.text()
    assert not dialog.recording_summary.toolTip()
    assert dialog.use_default_recording_button.isEnabled()
    assert not dialog._recording_uses_default
    assert dialog._recording_configuration == _configuration("biosemi_active_three")


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("developer", [False, True])
@pytest.mark.parametrize("uses_default", [False, True])
@pytest.mark.parametrize("size", [(860, 560), (1000, 680)])
def test_recording_settings_fit_sidebar_sizes(
    qtbot, tmp_path, background, developer, uses_default, size,
):
    resets = []
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path / ("Long research experiments root " * 5),
        experiment_test_mode_available=developer,
        recording_configuration=_configuration("biosemi_active_three"),
        on_recording_configuration_changed=lambda _: None,
        default_recording_configuration=_configuration("brainproducts_triggerbox"),
        on_default_recording_configuration_changed=lambda _: None,
        recording_uses_default=uses_default,
        on_use_default_recording_configuration=lambda: resets.append(True),
    )
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    select_settings_category(dialog, "Recording")
    dialog.resize(*size)
    dialog.show()
    QApplication.processEvents()
    assert dialog.size().toTuple() == size
    assert_visible_children_within_parent(dialog, allow_scroll_content=True)
    for button in dialog.findChildren(QPushButton):
        if button.isVisible():
            assert button.width() >= button.sizeHint().width()
    for label in dialog.findChildren(QLabel):
        if not label.isVisible():
            continue
        if label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width())
        else:
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
    assert dialog.use_default_recording_button.isEnabled() == (not uses_default)
    if not uses_default:
        dialog.use_default_recording_button.click()
        assert resets == [True]
        assert not dialog.use_default_recording_button.isEnabled()
        assert dialog.recording_summary.text().startswith("Using computer default:")
