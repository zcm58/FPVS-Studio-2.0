"""Selected monitor routing through GUI launch and explicit refresh checks."""

from unittest.mock import Mock

import pytest
from tests.gui.helpers import (
    ImmediateProgressTask,
    open_created_project,
    prepare_compile_ready_project,
)
from tests.platform_adapters import set_module_platform

from fpvs_studio.gui import (
    document_runtime,
    local_test_display_dialog,
    main_window,
    run_page,
    runtime_settings_page,
)
from fpvs_studio.gui.run_page import ParticipantLaunchDetails
from fpvs_studio.runtime import macos_session_process
from fpvs_studio.runtime.display_mode import NativeDisplayMode
from fpvs_studio.runtime.display_refresh import DisplayRefreshVerification

SELECTED_DISPLAY = r"\\.\DISPLAY2"


@pytest.mark.parametrize("surface", ["home", "run"])
@pytest.mark.parametrize("accepted", [True, False])
@pytest.mark.parametrize("platform_name", ["win32", "darwin"])
def test_monitor_choice_precedes_participant_entry_and_reaches_runtime(
    qtbot, controller, tmp_path, monkeypatch, surface, accepted, platform_name,
):
    for module in (document_runtime, main_window, run_page):
        set_module_platform(monkeypatch, module, platform_name)
    document, window = open_created_project(controller, qtbot, tmp_path, "Monitor launch")
    prepare_compile_ready_project(window, tmp_path / "stimuli")
    qtbot.waitUntil(lambda: window._session_seed_ready)
    document.set_experiment_test_mode_enabled(True)
    page = window if surface == "home" else window.run_page
    module = main_window if surface == "home" else run_page
    events = []
    selected = SELECTED_DISPLAY if platform_name == "win32" else "macos:73"

    def calibrate(_document, _parent, *, display_device_name):
        assert display_device_name == selected
        events.append("calibration")
        return document.project.settings.display.model_copy(update={"preferred_refresh_hz": 60.0})

    monkeypatch.setattr(local_test_display_dialog, "confirm_local_test_display", calibrate)

    def choose(_parent, proceed):
        events.append("select")
        if accepted:
            proceed(selected)

    def advise(_parent, proceed, *, display_device_name):
        assert display_device_name == selected
        events.append("advice")
        proceed()

    def participant():
        events.append("participant")
        return ParticipantLaunchDetails(participant_number="0")

    def launch(_root, _plan, **kwargs):
        events.append("launch")
        assert kwargs["launch_settings"].display_device_name == selected
        assert kwargs["launch_settings"].display_index is None
        assert kwargs["launch_settings"].fullscreen is True
        return object()

    monkeypatch.setattr(module, "choose_experiment_display", choose)
    monkeypatch.setattr(module, "check_windows_refresh", advise)
    monkeypatch.setattr(module, "ProgressTask", ImmediateProgressTask)
    monkeypatch.setattr(page, "_collect_launch_participant_details", participant)
    monkeypatch.setattr(window, "_notify_session_started", lambda start: start())
    monkeypatch.setattr(window, "_on_home_launch_succeeded", Mock())
    if surface == "run":
        page.set_launch_gate(lambda start: start())
        monkeypatch.setattr(page, "_on_launch_succeeded", Mock())
    launcher = Mock(side_effect=launch)
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", launcher)
    monkeypatch.setattr(macos_session_process, "launch_macos_test_session", launcher)
    page.launch_session()

    expected = ["select", "advice"]
    if platform_name == "darwin":
        expected.append("calibration")
    expected.extend(["participant", "launch"])
    assert events == (expected if accepted else ["select"])
    assert launcher.call_count == int(accepted)


def test_refresh_check_measures_the_selected_monitor(qtbot, controller, tmp_path, monkeypatch):
    set_module_platform(monkeypatch, runtime_settings_page, "win32")
    document, window = open_created_project(controller, qtbot, tmp_path, "Monitor refresh")
    editor = window.run_page.runtime_settings_editor
    engine = object()
    mode = NativeDisplayMode(
        platform_name="Windows", display_name=SELECTED_DISPLAY, refresh_hz=120.0,
        source_name="QueryDisplayConfig", exact_refresh=True,
    )
    verify = Mock(return_value=DisplayRefreshVerification(mode, 120.0, 120.0))
    monkeypatch.setattr(runtime_settings_page, "create_engine", lambda _name: engine)
    monkeypatch.setattr(runtime_settings_page, "verify_primary_display_refresh", verify)
    monkeypatch.setattr(runtime_settings_page, "ProgressTask", ImmediateProgressTask)
    monkeypatch.setattr(
        runtime_settings_page, "choose_experiment_display",
        lambda _parent, proceed: proceed(SELECTED_DISPLAY),
    )
    advisory = Mock(side_effect=lambda _parent, proceed, **_kwargs: proceed())
    monkeypatch.setattr(runtime_settings_page, "check_windows_refresh", advisory)

    editor.detect_refresh_button.click()

    assert advisory.call_args.kwargs["display_device_name"] == SELECTED_DISPLAY
    verify.assert_called_once_with(engine, runtime_options={
        "fullscreen": True, "display_index": None, "display_device_name": SELECTED_DISPLAY,
    })
    assert editor.refresh_is_verified()
    assert document.project.settings.display.preferred_refresh_hz == 120.0
    assert editor._refresh_verification.display_mode.display_name == SELECTED_DISPLAY


def test_mac_refresh_check_passes_selection_to_bounded_probe(
    qtbot, controller, tmp_path, monkeypatch,
):
    set_module_platform(monkeypatch, runtime_settings_page, "darwin")
    document, window = open_created_project(controller, qtbot, tmp_path, "Mac monitor refresh")
    editor = window.run_page.runtime_settings_editor
    selected = "macos:73"
    mode = NativeDisplayMode(
        platform_name="macOS", display_name="Display 73", refresh_hz=120,
        source_name="CoreGraphics/AppKit", exact_refresh=False, display_device_name=selected,
    )
    verify = Mock(return_value=DisplayRefreshVerification(mode, 120.0, 120.0))
    monkeypatch.setattr(macos_session_process, "verify_macos_primary_display_refresh", verify)
    monkeypatch.setattr(runtime_settings_page, "ProgressTask", ImmediateProgressTask)
    monkeypatch.setattr(
        runtime_settings_page, "choose_experiment_display",
        lambda _parent, proceed: proceed(selected),
    )
    monkeypatch.setattr(
        runtime_settings_page, "check_windows_refresh",
        lambda _parent, proceed, **_kwargs: proceed(),
    )
    editor.detect_refresh_button.click()
    assert verify.call_args.kwargs["display_device_name"] == selected
    assert verify.call_args.kwargs["cancel_event"] is not None
    assert editor.refresh_is_verified()
    assert document.project.settings.display.preferred_refresh_hz == 120.0
