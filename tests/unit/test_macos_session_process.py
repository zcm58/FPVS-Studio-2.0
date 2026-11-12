"""Fake-only coverage for macOS main-thread presentation and protected request transport."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.platform_adapters import set_module_platform

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.enums import RunMode
from fpvs_studio.core.execution import ParticipantMetadata, SessionExecutionSummary
from fpvs_studio.runtime import launcher
from fpvs_studio.runtime import macos_session_process as process
from fpvs_studio.runtime.display_mode import NativeDisplayMode
from fpvs_studio.runtime.display_refresh import (
    DisplayRefreshVerification,
    DisplayRefreshVerificationError,
)
from fpvs_studio.runtime.preflight import PreflightError


def _settings(**updates):
    return replace(launcher.LaunchSettings(
        experiment_test_mode=True, serial_enabled=False, verify_refresh_rate=True,
    ), **updates)


def test_child_diagnostics_use_bounded_local_logs_without_crash_registration(monkeypatch, tmp_path):
    from fpvs_studio.support import storage

    monkeypatch.setattr(storage, "support_directory", lambda: tmp_path)

    def execute():
        process.LOGGER.info("Mac presentation child started (operation=refresh pid=123)")
        return 7

    monkeypatch.setattr(process, "main", execute)
    assert process._main_with_diagnostics() == 7
    logs = list((tmp_path / "logs").glob("session-*.log"))
    assert len(logs) == 1
    assert "operation=refresh pid=123" in logs[0].read_text(encoding="utf-8")
    assert {path.name for path in tmp_path.iterdir()} == {"logs"}


def _summary(plan):
    return SessionExecutionSummary(
        project_id=plan.project_id, session_id=plan.session_id, engine_name="psychopy",
        run_mode=RunMode.SESSION, participant_number="001", participant_session_number=2,
        participant_metadata=ParticipantMetadata(age=25), total_condition_count=plan.total_runs,
    )


def _fake_process(monkeypatch, callback=None):
    calls = []
    set_module_platform(monkeypatch, process, "darwin")
    set_module_platform(monkeypatch, launcher, "darwin")
    monkeypatch.setattr(process.sys, "frozen", False, raising=False)

    def run(command, **options):
        assert command[:3] == [process.sys.executable, "-m", process._CHILD_MODULE]
        assert len(command) == 4
        assert all(options[key] == process.subprocess.DEVNULL
                   for key in ("stdin", "stdout", "stderr"))
        assert options["check"] is False
        assert not options.get("shell", False)
        path = Path(command[3])
        calls.append((path, json.loads(path.read_bytes()), options))
        assert path.name == "request.json"
        if os.name == "posix":
            assert path.stat().st_mode & 0o077 == 0
            assert path.parent.stat().st_mode & 0o077 == 0
        return SimpleNamespace(returncode=process.main([str(path)]) if callback is None
                               else callback(path))

    monkeypatch.setattr(process.subprocess, "run", run)

    class Probe:
        pid = 12345

        def __init__(self, command, **options):
            self.returncode = run(command, check=False, **options).returncode

        def wait(self, **_options):
            return self.returncode

        def poll(self):
            return self.returncode

    monkeypatch.setattr(process.subprocess, "Popen", Probe)
    return calls


@pytest.mark.parametrize("entrypoint", [launcher.launch_run, launcher.launch_session])
@pytest.mark.parametrize("updates,match", [
    ({"experiment_test_mode": False}, "Test Mode or Pilot"),
    ({"serial_enabled": True}, "trigger output disabled"),
    ({"verify_refresh_rate": False}, "refresh-rate verification"),
    ({"fullscreen": False}, "fullscreen"),
    ({"display_index": 1}, "primary display"),
    ({"display_index": False}, "primary display"),
])
def test_mac_blocked_launch_never_probes_recorders_or_constructs_engine(
    monkeypatch, tmp_path, entrypoint, updates, match,
):
    set_module_platform(monkeypatch, launcher, "darwin")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Hardware or engine must not be accessed")

    monkeypatch.setattr(launcher, "_check_recorder_before_launch", forbidden)
    monkeypatch.setattr(launcher, "create_engine", forbidden)
    with pytest.raises(launcher.LaunchSettingsError, match=match):
        entrypoint(tmp_path, object(), participant_number="001",
                   launch_settings=_settings(**updates))


@pytest.mark.parametrize("entrypoint", [launcher.launch_run, launcher.launch_session])
def test_mac_direct_launch_requires_process_main_thread(monkeypatch, tmp_path, entrypoint):
    set_module_platform(monkeypatch, launcher, "darwin")
    monkeypatch.setattr(launcher.threading, "current_thread", lambda: object())

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Hardware or engine must not be accessed")

    monkeypatch.setattr(launcher, "_check_recorder_before_launch", forbidden)
    monkeypatch.setattr(launcher, "create_engine", forbidden)
    with pytest.raises(launcher.LaunchSettingsError, match="main thread"):
        entrypoint(tmp_path, object(), participant_number="001", launch_settings=_settings())


def test_mac_frozen_guard_precedes_recording_checks(monkeypatch):
    set_module_platform(monkeypatch, launcher, "darwin")
    monkeypatch.setattr(launcher.sys, "frozen", True, raising=False)
    with pytest.raises(launcher.LaunchSettingsError, match="source environment"):
        launcher._validate_launch_settings(_settings())


def test_mac_named_secondary_launch_is_valid_and_keeps_identity(monkeypatch):
    set_module_platform(monkeypatch, launcher, "darwin")
    settings = _settings(display_device_name="macos:84")
    launcher._validate_launch_settings(settings)
    assert launcher._launch_runtime_options(settings)["display_device_name"] == "macos:84"
    with pytest.raises(launcher.LaunchSettingsError, match="name or index"):
        launcher._validate_launch_settings(replace(settings, display_index=0))


@pytest.mark.parametrize("identity", ["", "macos:0", "macos:4294967296", "macos:NaN", True,
                                      r"\\.\DISPLAY2"])
def test_mac_invalid_named_selection_is_blocked_before_hardware(monkeypatch, tmp_path, identity):
    set_module_platform(monkeypatch, launcher, "darwin")
    monkeypatch.setattr(launcher, "_check_recorder_before_launch",
                        lambda *_: pytest.fail("Invalid display must not probe recorders"))
    with pytest.raises(launcher.LaunchSettingsError, match="valid Mac"):
        launcher.launch_session(
            tmp_path, object(), participant_number="001",
            launch_settings=_settings(display_device_name=identity),
        )


def test_default_mac_launch_pins_native_primary_independent_of_enumeration_order(monkeypatch):
    from fpvs_studio.runtime import macos_display

    set_module_platform(monkeypatch, launcher, "darwin")
    monkeypatch.setattr(macos_display, "query_macos_monitors", lambda: (
        macos_display.MacOSMonitor(84, False, 2560, 1440),
        macos_display.MacOSMonitor(42, True, 3024, 1964),
    ))
    for index in (None, 0):
        settings = _settings(display_index=index)
        options = launcher._launch_runtime_options(settings)
        assert options["display_device_name"] == "macos:42"
        assert options["display_index"] is None
        assert settings.display_device_name is None


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_other_platform_launch_policy_remains_unchanged(monkeypatch, platform):
    set_module_platform(monkeypatch, launcher, platform)
    launcher._validate_launch_settings(launcher.LaunchSettings(
        fullscreen=False, verify_refresh_rate=False, display_index=1,
    ))


@pytest.mark.parametrize("pilot", [False, True])
@pytest.mark.parametrize("display_device_name", [None, "macos:84"])
def test_private_child_main_thread_roundtrip_preserves_neutral_session(
    monkeypatch, sample_project, sample_project_root, pilot, display_device_name,
):
    plan = compile_session_plan(sample_project, project_root=sample_project_root, refresh_hz=60)
    seen = []

    def launch(root, selected, **options):
        seen.append((root, selected, options))
        assert process.threading.current_thread() is process.threading.main_thread()
        assert options["launch_settings"].windowed_size_px == (1280, 720)
        assert options["launch_settings"].display_device_name == display_device_name
        return _summary(selected)

    monkeypatch.setattr(launcher, "launch_session", launch)
    calls = _fake_process(monkeypatch)
    result = process.launch_macos_test_session(
        sample_project_root, plan, participant_number="001", participant_session_number=2,
        participant_metadata={"age": 25},
        launch_settings=_settings(
            pilot_mode=pilot, experiment_test_mode=not pilot,
            display_device_name=display_device_name,
        ),
    )
    assert result == _summary(plan)
    assert seen[0][0] == sample_project_root.resolve()
    assert seen[0][1] == plan
    assert seen[0][2]["participant_metadata"].age == 25
    request_path, payload, options = calls[0]
    assert payload["operation"] == "session"
    assert payload["launch_settings"]["display_device_name"] == display_device_name
    assert "participant_metadata" in payload
    assert str(Path(process.__file__).resolve().parents[2]) in options["env"]["PYTHONPATH"]
    assert not request_path.parent.exists()


@pytest.mark.parametrize("error", [RuntimeError("private participant details"),
                                   ModuleNotFoundError("secret dependency path")])
def test_child_failure_returns_bounded_redacted_error_and_cleans_request(
    monkeypatch, sample_project, sample_project_root, error, caplog,
):
    plan = compile_session_plan(sample_project, project_root=sample_project_root, refresh_hz=60)

    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(launcher, "launch_session", fail)
    calls = _fake_process(monkeypatch)
    with pytest.raises(process.MacOSSessionProcessError) as failure:
        process.launch_macos_test_session(sample_project_root, plan, participant_number="001",
                                          launch_settings=_settings())
    assert "private" not in str(failure.value)
    assert "secret" not in str(failure.value)
    assert failure.value.child_traceback
    assert any("test_macos_session_process.py" in frame for frame in failure.value.child_traceback)
    assert "private participant details" not in caplog.text
    assert "secret dependency path" not in caplog.text
    assert "stack locations" in caplog.text
    assert not calls[0][0].parent.exists()


def test_transport_failure_is_explicit_and_does_not_run_parent_engine(
    monkeypatch, sample_project, sample_project_root,
):
    plan = compile_session_plan(sample_project, project_root=sample_project_root, refresh_hz=60)
    calls = _fake_process(monkeypatch, lambda _path: 9)
    with pytest.raises(process.MacOSSessionProcessError, match="did not return"):
        process.launch_macos_test_session(sample_project_root, plan, participant_number="001",
                                          launch_settings=_settings())
    assert not calls[0][0].parent.exists()


def test_mismatched_child_identity_is_rejected(monkeypatch, sample_project, sample_project_root):
    plan = compile_session_plan(sample_project, project_root=sample_project_root, refresh_hz=60)
    monkeypatch.setattr(launcher, "launch_session",
                        lambda *_args, **_kwargs: _summary(plan).model_copy(
                            update={"participant_number": "999"},
                        ))
    _fake_process(monkeypatch)
    with pytest.raises(process.MacOSSessionProcessError, match="mismatched"):
        process.launch_macos_test_session(sample_project_root, plan, participant_number="001",
                                          launch_settings=_settings())


@pytest.mark.parametrize("display_device_name", [None, "macos:84"])
def test_refresh_proxy_measures_selected_fullscreen_in_child_main_thread(
    monkeypatch, display_device_name,
):
    from fpvs_studio.engines import registry
    from fpvs_studio.runtime import display_refresh

    seen = []
    verification = DisplayRefreshVerification(
        NativeDisplayMode(
            "macOS", "Display 84", 60.0, "CoreGraphics", True,
            display_device_name=display_device_name,
        ), 60.0, 60.0,
    )
    engine = object()
    monkeypatch.setattr(registry, "create_engine", lambda _name: engine)

    def verify(selected, *, runtime_options):
        assert selected is engine
        assert process.threading.current_thread() is process.threading.main_thread()
        seen.append(runtime_options)
        return verification

    monkeypatch.setattr(display_refresh, "_verify_primary_display_refresh_in_process", verify)
    calls = _fake_process(monkeypatch)
    assert process.verify_macos_primary_display_refresh(
        display_device_name=display_device_name,
    ) == verification
    selection = {} if display_device_name is None else {"display_device_name": display_device_name}
    assert seen == [{"fullscreen": True, "display_index": None, **selection}]
    assert calls[0][1] == {"version": 1, "operation": "refresh", **selection}
    assert not calls[0][0].parent.exists()


def test_refresh_proxy_rejects_invalid_measurement(monkeypatch):
    def respond(path):
        verification = DisplayRefreshVerification(
            NativeDisplayMode("macOS", "Primary", 60.0, "CoreGraphics", True), 144.0, 60.0,
        )
        process._private_file(path.parent / "response.json", write=process._Response(
            verification=verification,
        ).model_dump_json().encode())
        return 0

    _fake_process(monkeypatch, respond)
    with pytest.raises(process.MacOSSessionProcessError, match="invalid result"):
        process.verify_macos_primary_display_refresh()


def test_refresh_proxy_rejects_result_for_another_monitor(monkeypatch):
    def respond(path):
        verification = DisplayRefreshVerification(
            NativeDisplayMode(
                "macOS", "Display 42", 60.0, "CoreGraphics", True,
                display_device_name="macos:42",
            ), 60.0, 60.0,
        )
        process._private_file(path.parent / "response.json", write=process._Response(
            verification=verification,
        ).model_dump_json().encode())
        return 0

    _fake_process(monkeypatch, respond)
    with pytest.raises(process.MacOSSessionProcessError, match="different display"):
        process.verify_macos_primary_display_refresh(display_device_name="macos:84")


@pytest.mark.parametrize("identity", ["", "macos:0", "macos:4294967296", "macos:NaN", True,
                                      r"\\.\DISPLAY2"])
def test_invalid_refresh_identity_never_starts_a_child(monkeypatch, identity):
    set_module_platform(monkeypatch, process, "darwin")
    monkeypatch.setattr(process, "_exchange", lambda *_a, **_k: pytest.fail("No child"))
    with pytest.raises(process.MacOSSessionProcessError, match="valid Mac"):
        process.verify_macos_primary_display_refresh(display_device_name=identity)


def test_child_rejects_invalid_monitor_identity_before_loading_engine(monkeypatch, tmp_path):
    from fpvs_studio.engines import registry

    set_module_platform(monkeypatch, process, "darwin")
    monkeypatch.setattr(registry, "create_engine", lambda *_: pytest.fail("No engine"))
    private = tmp_path / "request-area"
    private.mkdir(mode=0o700)
    request = private / "request.json"
    process._private_file(request, write=json.dumps({
        "version": 1, "operation": "refresh", "display_device_name": "macos:0",
    }).encode())
    assert process.main([str(request)]) == 1
    response = process._Response.model_validate_json(
        process._private_file(private / "response.json"),
    )
    assert response.error == "invalid_request"


def test_child_rejects_unknown_opcode_without_loading_engine(monkeypatch, tmp_path):
    set_module_platform(monkeypatch, process, "darwin")
    private = tmp_path / "request-area"
    private.mkdir(mode=0o700)
    request = private / "request.json"
    process._private_file(request, write=b'{"version":1,"operation":"execute-any-module"}')
    assert process.main([str(request)]) == 1
    response = process._Response.model_validate_json(
        process._private_file(private / "response.json"),
    )
    assert response.error == "invalid_request"


@pytest.mark.parametrize("platform,frozen", [("win32", False), ("darwin", True)])
def test_process_boundary_rejects_unsupported_host_before_spawning(monkeypatch, platform, frozen):
    set_module_platform(monkeypatch, process, platform)
    monkeypatch.setattr(process.sys, "frozen", frozen, raising=False)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("No child process should be started")

    monkeypatch.setattr(process.subprocess, "run", forbidden)
    monkeypatch.setattr(process.subprocess, "Popen", forbidden)
    with pytest.raises(process.MacOSSessionProcessError, match="macOS source"):
        process.verify_macos_primary_display_refresh()


def test_private_transport_is_bounded_and_exclusive(monkeypatch, tmp_path):
    path = tmp_path / "payload.json"
    monkeypatch.setattr(process, "MAX_PAYLOAD_BYTES", 4)
    with pytest.raises(process.MacOSSessionProcessError, match="limit"):
        process._private_file(path, write=b"12345")
    process._private_file(path, write=b"1234")
    assert process._private_file(path) == b"1234"
    with pytest.raises(FileExistsError):
        process._private_file(path, write=b"1234")


@pytest.mark.parametrize("error", [
    DisplayRefreshVerificationError(
        "Choose a fixed refresh rate in macOS System Settings > Displays.",
    ),
    PreflightError("The compiled session expects 120 Hz. Recheck the display refresh rate."),
    PreflightError("A required stimulus image is missing. Re-import the condition folder."),
])
def test_allowlisted_display_and_asset_failures_remain_actionable(
    monkeypatch, sample_project, sample_project_root, error,
):
    plan = compile_session_plan(sample_project, project_root=sample_project_root, refresh_hz=60)

    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(launcher, "launch_session", fail)
    _fake_process(monkeypatch)
    with pytest.raises(process.MacOSSessionProcessError) as failure:
        process.launch_macos_test_session(sample_project_root, plan, participant_number="001",
                                          launch_settings=_settings())
    assert str(failure.value) == str(error)
    assert failure.value.child_traceback


def test_display_guidance_is_bounded_without_echoing_arbitrary_failure_payloads():
    typed = process._launch_failure(DisplayRefreshVerificationError("Check fixed refresh. " * 200))
    assert len(typed.guidance) == 1000
    generic = process._launch_failure(RuntimeError("private participant details"))
    assert generic.guidance == ""
    framebuffer = process._launch_failure(
        RuntimeError("Mac presentation uses (1440, 900) backing pixels"),
    )
    assert "local calibration" in framebuffer.guidance


@pytest.mark.parametrize("message", [
    "macOS display refresh callback stopped. Retry after checking the display.",
    "Mac Test/Pilot requires the foreground-window keyboard backend.",
    "PsychoPy could not determine the Mac presentation display size.",
    "Could not select the presentation monitor: the selected display disconnected.",
    "Mac presentation display does not match the selected monitor. Retry the launch.",
])
def test_mac_display_adapter_failures_retain_actionable_guidance(message):
    response = process._launch_failure(RuntimeError(message))

    assert response.error == "display_verification"
    assert response.guidance == message
    assert response.summary is None
    assert response.verification is None


def test_mac_display_adapter_guidance_remains_bounded():
    response = process._launch_failure(
        RuntimeError("macOS display refresh callback stopped. " * 100),
    )

    assert response.error == "display_verification"
    assert len(response.guidance) == 1000
