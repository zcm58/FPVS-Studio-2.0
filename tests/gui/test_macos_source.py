"""Visible Mac-policy smoke; native OS/runtime calls stay stubbed."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QDialog
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.gui import (
    controller,
    local_test_display_dialog,
    run_page,
    settings_dialog,
    update_dialog,
)
from fpvs_studio.gui.local_test_display_dialog import LocalTestDisplayDialog
from fpvs_studio.gui.run_page import ParticipantLaunchDetails, RunPage
from fpvs_studio.runtime.display_mode import NativeDisplayMode


def _mode():
    return NativeDisplayMode(
        platform_name="macOS", display_name="Display 1", refresh_hz=120,
        source_name="CoreGraphics/AppKit", exact_refresh=False,
        pixel_width=2880, pixel_height=1800,
    )


@pytest.mark.parametrize("size", [(520, 360), (600, 380)])
def test_local_test_calibration_is_launch_only_and_fits(
    qtbot, monkeypatch, sample_project, size,
):
    monkeypatch.setattr(
        local_test_display_dialog, "detect_primary_display_settings",
        lambda: SimpleNamespace(screen_width_cm=33),
    )
    display = sample_project.settings.display
    before = display.model_dump()
    dialog = LocalTestDisplayDialog(display, _mode())
    qtbot.addWidget(dialog)
    dialog.resize(*size)
    dialog.show()
    QApplication.processEvents()
    assert_visible_children_within_parent(dialog)
    assert "120 Hz" in dialog.mode_label.text()
    dialog.distance_spin.setValue(55)
    local = dialog.local_display()
    assert local.screen_width_px == 2880
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
def test_mac_launch_confirms_local_display_before_condition_selection(
    qtbot, monkeypatch, sample_project, accepted,
):
    from fpvs_studio.runtime import display_mode

    monkeypatch.setattr(run_page, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(display_mode, "query_primary_native_display_mode", _mode)
    local = sample_project.settings.display.model_copy(deep=True)
    local.preferred_refresh_hz = 120
    dialog = SimpleNamespace(
        exec=lambda: QDialog.DialogCode.Accepted if accepted else QDialog.DialogCode.Rejected,
        local_display=lambda: local, refresh_hz=120,
    )
    monkeypatch.setattr(local_test_display_dialog, "LocalTestDisplayDialog", lambda *_: dialog)
    participant = ParticipantLaunchDetails(participant_number="0")
    page = SimpleNamespace(
        is_launch_busy=lambda: False,
        current_refresh_hz=lambda: 60,
        _document=SimpleNamespace(
            project=sample_project, experiment_test_mode_enabled=True,
            validate_recording_launch=Mock(),
            validation_report=Mock(return_value=SimpleNamespace(is_valid=True)),
        ),
        _collect_launch_participant_details=Mock(return_value=participant),
        _launch_participant_session=Mock(),
    )
    RunPage.launch_session(page)
    if accepted:
        page._document.validation_report.assert_called_once_with(refresh_hz=120)
        page._launch_participant_session.assert_called_once_with(
            participant, 120, None, local_display=local,
        )
    else:
        page._collect_launch_participant_details.assert_not_called()
        page._launch_participant_session.assert_not_called()
