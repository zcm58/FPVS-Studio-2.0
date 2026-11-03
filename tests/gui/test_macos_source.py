"""Visible Mac-policy smoke; native OS/runtime calls stay stubbed."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel
from tests.gui.helpers import assert_visible_children_within_parent
from tests.platform_adapters import set_module_platform

from fpvs_studio.core.serialization import save_project_file
from fpvs_studio.gui import (
    controller,
    local_test_display_dialog,
    main_window,
    run_page,
    settings_dialog,
    update_dialog,
)
from fpvs_studio.gui import (
    document as document_module,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.document_support import DocumentError
from fpvs_studio.gui.local_test_display_dialog import LocalTestDisplayDialog
from fpvs_studio.gui.main_window import StudioMainWindow
from fpvs_studio.gui.run_page import ParticipantLaunchDetails, RunPage
from fpvs_studio.gui.workers import GuiTaskWorker
from fpvs_studio.runtime.display_mode import NativeDisplayMode


def _mode():
    return NativeDisplayMode(
        platform_name="macOS", display_name="Display 1", refresh_hz=120,
        source_name="CoreGraphics/AppKit", exact_refresh=False,
        pixel_width=2880, pixel_height=1800,
    )


@pytest.mark.parametrize("size", [(520, 360), (600, 380)])
@pytest.mark.parametrize("matching", [False, True])
@pytest.mark.parametrize("pixels", [(2880, 1800), (16384, 8640)])
def test_local_test_display_confirmation_preserves_input_and_fits(
    qtbot, monkeypatch, sample_project, size, matching, pixels,
):
    monkeypatch.setattr(
        local_test_display_dialog, "detect_primary_display_settings",
        lambda: SimpleNamespace(screen_width_cm=33),
    )
    display = sample_project.settings.display.model_copy(deep=True)
    if matching:
        display.screen_width_px, display.screen_height_px = pixels
    before = display.model_dump()
    mode = replace(_mode(), pixel_width=pixels[0], pixel_height=pixels[1])
    dialog = LocalTestDisplayDialog(display, mode)
    qtbot.addWidget(dialog)
    dialog.resize(*size)
    dialog.show()
    QApplication.processEvents()
    assert dialog.size().toTuple() == size
    assert_visible_children_within_parent(dialog)
    assert "120 Hz" in dialog.mode_label.text()
    assert f"{pixels[0]} × {pixels[1]} backing px" in dialog.mode_label.text()
    assert dialog.configured_resolution_label.text() == (
        f"{display.screen_width_px} × {display.screen_height_px} px"
    )
    assert dialog.resolution_mismatch is not matching
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).text() == (
        "Use for this test" if matching else "Update resolution and continue"
    )
    for label in dialog.findChildren(QLabel):
        if label.isVisible() and label.wordWrap():
            required = label.fontMetrics().boundingRect(
                QRect(0, 0, label.contentsRect().width(), 10000),
                Qt.TextFlag.TextWordWrap, label.text(),
            )
            assert label.contentsRect().height() >= required.height(), label.text()
    dialog.distance_spin.setValue(55)
    local = dialog.local_display()
    assert local.screen_width_px == pixels[0]
    assert local.screen_height_px == pixels[1]
    assert local.screen_width_cm == 33
    assert local.viewing_distance_cm == 55
    assert local.use_current_screen_resolution is False
    assert display.model_dump() == before
    dialog.reject()
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_mac_source_has_test_mode_and_no_hardware_onboarding(monkeypatch):
    monkeypatch.setattr(controller, "sys", SimpleNamespace(platform="darwin"))
    assert controller.experiment_test_mode_available() is True
    host = SimpleNamespace(_startup_update_check_started=False)
    controller.StudioController._schedule_startup_update_check(host)
    assert host._startup_update_check_started is False
    host._startup_cache_cleanup_started = False
    controller.StudioController.start_update_cache_housekeeping(host)
    assert host._startup_cache_cleanup_started is False


def test_mac_test_settings_describe_required_local_display_check(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(settings_dialog, "sys", SimpleNamespace(platform="darwin"))
    dialog = settings_dialog.AppSettingsDialog(
        fpvs_root_dir=tmp_path, experiment_test_mode_available=True,
        attentional_blink_pilot_mode_available=True,
    )
    qtbot.addWidget(dialog)
    assert "verifies the local display" in dialog.experiment_test_mode_checkbox.toolTip()
    assert "verifies the local display" in dialog.attentional_blink_pilot_mode_checkbox.toolTip()


def test_mac_update_dialog_explains_source_updates_without_checking(qtbot, monkeypatch):
    monkeypatch.setattr(update_dialog, "sys", SimpleNamespace(platform="darwin"))
    callback = Mock(side_effect=AssertionError("Windows updater must not start"))
    dialog = update_dialog.UpdateDialog(check_callback=callback)
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    assert_visible_children_within_parent(dialog)
    assert dialog.title_label.text() == "macOS source updates"
    assert dialog.download_button.isHidden()
    assert dialog.check_button.isHidden()
    dialog.start_update_check()
    dialog.start_download()
    callback.assert_not_called()


@pytest.mark.parametrize("accepted", [True, False])
@pytest.mark.parametrize("surface", ["home", "run"])
@pytest.mark.parametrize("platform_name", ["win32", "darwin"])
@pytest.mark.parametrize("test_mode", [True, False])
def test_launch_confirms_local_display_only_on_mac_before_condition_selection(
    qtbot, monkeypatch, sample_project, accepted, surface, platform_name, test_mode,
):
    from fpvs_studio.runtime import display_mode

    owner = main_window if surface == "home" else run_page
    set_module_platform(monkeypatch, owner, platform_name)
    monkeypatch.setattr(display_mode, "query_primary_native_display_mode", _mode)
    local = sample_project.settings.display.model_copy(deep=True)
    local.preferred_refresh_hz = 120
    dialog = SimpleNamespace(
        exec=lambda: QDialog.DialogCode.Accepted if accepted else QDialog.DialogCode.Rejected,
        local_display=lambda: local, refresh_hz=120,
    )
    create_dialog = Mock(return_value=dialog)
    monkeypatch.setattr(local_test_display_dialog, "LocalTestDisplayDialog", create_dialog)
    participant = ParticipantLaunchDetails(participant_number="0" if test_mode else "7")
    confirmation = SimpleNamespace(confirmed=Mock(), failed=Mock(), finished=Mock())
    confirmation.confirmed.connect.side_effect = lambda callback: setattr(
        confirmation, "start", lambda: callback(1),
    )
    monkeypatch.setattr(owner, "ParticipantSessionCheckTask", Mock(return_value=confirmation))
    page = SimpleNamespace(
        _project_update_reload_failed=False,
        _bundle_import_processing_active=False,
        is_launch_busy=lambda: False,
        current_refresh_hz=lambda: 60,
        _home_launch_refresh_hz=lambda: 60,
        _ensure_session_seed_ready_for_launch=lambda: True,
        flush_pending_edits=lambda: True,
        launch_action=Mock(), _update_launch_buttons=Mock(),
        _on_participant_session_check_finished=Mock(),
        _document=SimpleNamespace(
            project=sample_project, experiment_test_mode_enabled=test_mode,
            validate_recording_launch=Mock(),
            validation_report=Mock(return_value=SimpleNamespace(
                is_valid=platform_name == "win32",
            )),
            next_participant_session_number=Mock(return_value=1),
        ),
        _collect_launch_participant_details=Mock(return_value=participant),
        _launch_participant_session=Mock(),
    )
    page.document = page._document
    launch = StudioMainWindow.launch_session if surface == "home" else RunPage.launch_session
    launch(page)
    if accepted or platform_name == "win32":
        refresh = 120 if platform_name == "darwin" else 60
        if platform_name == "win32":
            page._document.validation_report.assert_called_once_with(refresh_hz=refresh)
        else:
            page._document.validation_report.assert_not_called()
        options = (
            {"local_display": local} if platform_name == "darwin" else
            {"local_display": None} if surface == "run" else {}
        )
        page._launch_participant_session.assert_called_once_with(
            participant, refresh, None if test_mode else 1, **options,
        )
    else:
        page._collect_launch_participant_details.assert_not_called()
        page._launch_participant_session.assert_not_called()
    if platform_name == "win32":
        create_dialog.assert_not_called()
    else:
        create_dialog.assert_called_once()


@pytest.mark.parametrize("surface", ["home", "run"])
@pytest.mark.parametrize("outcome", ["update", "matching", "save_failure", "compile_failure"])
def test_mac_resolution_save_runs_in_launch_worker_before_compile(
    qtbot, monkeypatch, sample_project, sample_project_root, surface, outcome,
):
    project = sample_project.model_copy(deep=True)
    if outcome == "matching":
        project.settings.display.screen_width_px = 2880
        project.settings.display.screen_height_px = 1800
        project.settings.display.use_current_screen_resolution = True
    project_path = sample_project_root / "project.json"
    save_project_file(project, project_path)
    original_bytes = project_path.read_bytes()
    before = json.loads(original_bytes)
    document = ProjectDocument(project_root=sample_project_root, project=project)
    document.set_experiment_test_mode_enabled(True)
    before_memory = document.project.model_dump(mode="json")
    monkeypatch.setattr(document, "validate_recording_launch", Mock())
    monkeypatch.setattr(document, "prepare_participant_randomization", Mock(return_value=None))
    local = project.settings.display.model_copy(deep=True)
    local.screen_width_px, local.screen_height_px = 2880, 1800
    local.use_current_screen_resolution = False
    local.screen_width_cm, local.viewing_distance_cm = 33, 55
    local.preferred_refresh_hz = 120
    gui_thread = threading.get_ident()
    calls = []
    plan = object()

    def compile_session(**options):
        assert threading.get_ident() != gui_thread
        assert options["local_display"] == local
        persisted = json.loads(project_path.read_bytes())
        assert persisted["settings"]["display"]["screen_width_px"] == 2880
        assert persisted["settings"]["display"]["screen_height_px"] == 1800
        calls.append("compile")
        if outcome == "compile_failure":
            raise DocumentError("The compiled local display remains invalid.")
        return plan

    def present(compiled_plan, **_options):
        assert compiled_plan is plan
        calls.append("playback")
        return object()

    monkeypatch.setattr(document, "compile_session", Mock(side_effect=compile_session))
    monkeypatch.setattr(document, "launch_compiled_session", Mock(side_effect=present))
    save = Mock(wraps=document.save_display_resolution)
    if outcome == "save_failure":
        monkeypatch.setattr(
            document_module, "save_project_file",
            Mock(side_effect=PermissionError("Project resolution could not be saved.")),
        )
    monkeypatch.setattr(document, "save_display_resolution", save)
    held = []

    class HeldTask:
        def __init__(self, *, callback, **_options):
            self.callback = callback
            self.succeeded, self.failed, self.finished = Mock(), Mock(), Mock()

        def start(self):
            held.append(self)

    owner = main_window if surface == "home" else run_page
    monkeypatch.setattr(owner, "ProgressTask", HeldTask)
    page = SimpleNamespace(
        document=document, _document=document,
        _set_summary=Mock(), _refresh_run_output_actions=Mock(),
        _update_launch_buttons=Mock(), launch_action=Mock(),
        _notify_session_started=lambda start: start(), _launch_gate=None,
        _on_home_launch_succeeded=Mock(), _on_home_launch_failed=Mock(),
        _on_home_launch_finished=Mock(), _on_launch_succeeded=Mock(),
        _on_launch_failed=Mock(), _on_launch_finished=Mock(),
    )
    errors = []
    if outcome == "compile_failure":
        error_function = "_show_error_dialog" if surface == "home" else "_show_runtime_error_dialog"
        monkeypatch.setattr(
            owner, error_function,
            lambda _parent, title, error: errors.append((title, str(error))),
        )
        page._on_home_launch_failed = lambda error: StudioMainWindow._on_home_launch_failed(
            page, error,
        )
        page._on_launch_failed = lambda error: RunPage._on_launch_failed(page, error)
    launch = (
        StudioMainWindow._launch_participant_session if surface == "home"
        else RunPage._launch_participant_session
    )
    launch(page, ParticipantLaunchDetails(participant_number="0"), 120, None, local_display=local)
    assert project_path.read_bytes() == original_bytes
    document.compile_session.assert_not_called()
    document.launch_compiled_session.assert_not_called()
    assert len(held) == 1
    with ThreadPoolExecutor(max_workers=1) as executor:
        if outcome == "compile_failure":
            worker = GuiTaskWorker(held[0].callback)
            worker.failed.connect(held[0].failed.connect.call_args.args[0])
            executor.submit(worker.run).result()
        else:
            result = executor.submit(held[0].callback)
            if outcome == "save_failure":
                with pytest.raises(PermissionError, match="resolution could not be saved"):
                    result.result()
            else:
                result.result()
    if outcome == "save_failure":
        assert project_path.read_bytes() == original_bytes
        assert document.project.model_dump(mode="json") == before_memory
        assert document.dirty is False
        assert calls == []
        document.compile_session.assert_not_called()
        document.launch_compiled_session.assert_not_called()
        monkeypatch.setattr(document_module, "save_project_file", save_project_file)
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(held[0].callback).result()
        assert save.call_count == 2
        assert calls == ["compile", "playback"]
        assert document.project.settings.display.screen_width_px == 2880
        assert document.dirty is False
    elif outcome == "matching":
        assert project_path.read_bytes() == original_bytes
        save.assert_not_called()
        assert calls == ["compile", "playback"]
    elif outcome == "compile_failure":
        qtbot.waitUntil(lambda: bool(errors))
        assert errors == [("Launch Error", "The compiled local display remains invalid.")]
        assert calls == ["compile"]
        document.launch_compiled_session.assert_not_called()
    else:
        save.assert_called_once_with(2880, 1800)
        after = json.loads(project_path.read_bytes())
        expected = deepcopy(before)
        expected["settings"]["display"].update({
            "screen_width_px": 2880, "screen_height_px": 1800,
            "use_current_screen_resolution": False,
        })
        expected["meta"]["updated_at"] = after["meta"]["updated_at"]
        assert after == expected
        assert calls == ["compile", "playback"]


def test_rejecting_mac_display_confirmation_preserves_saved_project(
    qtbot, monkeypatch, sample_project, sample_project_root,
):
    from fpvs_studio.runtime import display_mode

    project_path = sample_project_root / "project.json"
    save_project_file(sample_project, project_path)
    before = project_path.read_bytes()
    document = ProjectDocument(project_root=sample_project_root, project=sample_project)
    parent = QDialog()
    qtbot.addWidget(parent)
    monkeypatch.setattr(display_mode, "query_primary_native_display_mode", _mode)
    monkeypatch.setattr(
        local_test_display_dialog, "detect_primary_display_settings",
        lambda: SimpleNamespace(screen_width_cm=33),
    )
    monkeypatch.setattr(LocalTestDisplayDialog, "exec", lambda _self: QDialog.DialogCode.Rejected)

    assert local_test_display_dialog.confirm_local_test_display(document, parent) is None
    assert project_path.read_bytes() == before
    assert document.project == sample_project
