"""Mac probe recovery through real non-graphics children and explicit platform seams."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.platform_adapters import python_child_command, set_module_platform
from tests.unit.runtime_launcher_helpers import StubEngine

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.runtime import display_refresh
from fpvs_studio.runtime import macos_session_process as process
from fpvs_studio.runtime.display_mode import NativeDisplayMode
from fpvs_studio.runtime.display_refresh import (
    DisplayRefreshVerification,
    DisplayRefreshVerificationError,
)
from fpvs_studio.runtime.preflight import PreflightError, preflight_session_plan


def _verified():
    return DisplayRefreshVerification(
        NativeDisplayMode("macOS", "Primary", 60.0, "CoreGraphics", True), 60.0, 60.0,
    )


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_primary_platforms_keep_in_process_engine_verification(monkeypatch, platform):
    set_module_platform(monkeypatch, display_refresh, platform)
    engine = SimpleNamespace(engine_id="psychopy")
    options = {"fullscreen": True, "display_index": 0}
    calls = []

    def verify(selected, *, runtime_options):
        calls.append((selected, runtime_options))
        return _verified()

    monkeypatch.setattr(
        display_refresh, "_verify_primary_display_refresh_in_process", verify,
    )
    monkeypatch.setattr(process, "verify_macos_primary_display_refresh",
                        lambda **_: pytest.fail("Mac child must not be used"))
    assert display_refresh.verify_primary_display_refresh(engine, runtime_options=options)
    assert calls == [(engine, options)]


@pytest.mark.parametrize("failure", [False, True])
def test_mac_automatic_preflight_uses_bounded_probe_before_playback(
    monkeypatch, sample_project, sample_project_root, failure,
):
    class Engine(StubEngine):
        @property
        def engine_id(self):
            return "psychopy"

    set_module_platform(monkeypatch, display_refresh, "darwin")
    monkeypatch.setattr(display_refresh, "_verify_primary_display_refresh_in_process",
                        lambda *_a, **_k: pytest.fail("Parent must not create graphics"))
    calls = []

    def probe():
        calls.append(True)
        if failure:
            raise process.MacOSSessionProcessError("Display refresh check timed out.")
        return _verified()

    monkeypatch.setattr(process, "verify_macos_primary_display_refresh", probe)
    plan = compile_session_plan(sample_project, project_root=sample_project_root, refresh_hz=60)
    captures = {}
    if failure:
        with pytest.raises(PreflightError, match="timed out"):
            preflight_session_plan(sample_project_root, plan, engine=Engine(captures),
                                   runtime_options={"verify_refresh_rate": True})
    else:
        preflight_session_plan(sample_project_root, plan, engine=Engine(captures),
                               runtime_options={"verify_refresh_rate": True})
    assert calls == [True]
    assert "refresh_measurement_count" not in captures
    assert "open_count" not in captures
    assert not (sample_project_root / "runs").exists()


def test_mac_automatic_preflight_forwards_selected_identity_to_bounded_probe(monkeypatch):
    set_module_platform(monkeypatch, display_refresh, "darwin")
    seen = []

    def probe(*, display_device_name):
        seen.append(display_device_name)
        return _verified()

    monkeypatch.setattr(process, "verify_macos_primary_display_refresh", probe)
    monkeypatch.setattr(display_refresh, "_verify_primary_display_refresh_in_process",
                        lambda *_a, **_k: pytest.fail("Parent must not create graphics"))
    result = display_refresh.verify_primary_display_refresh(
        SimpleNamespace(engine_id="psychopy"),
        runtime_options={"display_device_name": "macos:84", "display_index": None},
    )
    assert result == _verified()
    assert seen == ["macos:84"]


@pytest.mark.parametrize("options", [
    {"display_device_name": False}, {"display_index": 1}, {"display_index": False},
    {"display_device_name": "macos:84", "display_index": 0},
])
def test_mac_refresh_rejects_ambiguous_or_invalid_selection_before_probe(monkeypatch, options):
    set_module_platform(monkeypatch, display_refresh, "darwin")
    monkeypatch.setattr(process, "verify_macos_primary_display_refresh",
                        lambda **_: pytest.fail("No probe"))
    with pytest.raises(DisplayRefreshVerificationError, match="Mac presentation monitor"):
        display_refresh.verify_primary_display_refresh(
            SimpleNamespace(engine_id="psychopy"), runtime_options=options,
        )


@pytest.mark.parametrize("selected_name", [None, "macos:84"])
def test_child_probe_uses_the_same_native_monitor_for_mode_and_frame_delivery(
    monkeypatch, selected_name,
):
    set_module_platform(monkeypatch, display_refresh, "darwin")
    identity = selected_name or "macos:42"
    mode = NativeDisplayMode(
        "macOS", "Display", 60.0, "CoreGraphics/AppKit", False,
        display_device_name=identity,
    )
    queries, observed = [], []

    def query(name=None):
        queries.append(name)
        return mode

    def measure(*, runtime_options):
        observed.append(runtime_options)
        return 60.0

    monkeypatch.setattr(display_refresh, "query_primary_native_display_mode", query)
    monkeypatch.setattr(display_refresh, "query_native_display_mode", query)
    options = {"fullscreen": True, "display_index": None}
    if selected_name is not None:
        options["display_device_name"] = selected_name
    result = display_refresh._verify_primary_display_refresh_in_process(
        SimpleNamespace(measure_refresh_hz=measure), runtime_options=options,
    )
    assert result.display_mode is mode
    assert queries == [selected_name]
    assert observed[0]["display_device_name"] == identity
    assert observed[0]["display_index"] is None
    assert options.get("display_device_name") == selected_name


@pytest.fixture
def native_child(monkeypatch):
    """Replace only the child command; never import PsychoPy or open a window."""
    set_module_platform(monkeypatch, process, "darwin")
    monkeypatch.setattr(process.sys, "frozen", False, raising=False)
    popen = process.subprocess.Popen
    children, requests = [], []

    def install(*, cancel=None, success=False):
        def start(command, **options):
            request = Path(command[-1])
            requests.append(request)
            if success:
                process._private_file(
                    request.parent / "response.json",
                    write=process._Response(verification=_verified()).model_dump_json().encode(),
                )
            script = "pass" if success else "import time; time.sleep(120)"
            child = popen(python_child_command(script), **options)
            children.append(child)
            if cancel is not None:
                cancel.set()
            return child

        monkeypatch.setattr(process.subprocess, "Popen", start)

    yield install, children, requests
    for child in children:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)


def test_hung_probe_is_killed_reaped_and_cleaned_then_retry_succeeds(monkeypatch, native_child):
    install, children, requests = native_child
    install()
    monkeypatch.setattr(process, "REFRESH_TIMEOUT_SECONDS", 0.3)
    with pytest.raises(process.MacOSSessionProcessError, match="timed out"):
        process.verify_macos_primary_display_refresh()
    assert children[0].poll() is not None
    if os.name == "posix":
        with pytest.raises(ChildProcessError):
            os.waitpid(children[0].pid, os.WNOHANG)
    assert not requests[0].parent.exists()
    install(success=True)
    monkeypatch.setattr(process, "REFRESH_TIMEOUT_SECONDS", 10)
    assert process.verify_macos_primary_display_refresh() == _verified()
    assert requests[0].parent != requests[1].parent
    assert all(not path.parent.exists() for path in requests)


@pytest.mark.parametrize("display_device_name", [None, "macos:84"])
def test_cancel_during_probe_kills_and_reaps_only_probe(native_child, display_device_name):
    install, children, requests = native_child
    cancel = threading.Event()
    install(cancel=cancel)
    with pytest.raises(process.MacOSSessionProcessError, match="canceled"):
        process.verify_macos_primary_display_refresh(
            cancel_event=cancel, display_device_name=display_device_name,
        )
    assert children[0].poll() is not None
    assert not requests[0].parent.exists()


def test_canceled_probe_is_not_started(monkeypatch):
    cancel = threading.Event()
    cancel.set()
    monkeypatch.setattr(process.subprocess, "Popen", lambda *_a, **_k: pytest.fail("No child"))
    with pytest.raises(process.MacOSSessionProcessError, match="canceled"):
        process._run_refresh_child([], {}, cancel)


def test_cancel_after_result_does_not_accept_stale_verification(monkeypatch):
    set_module_platform(monkeypatch, process, "darwin")
    cancel = threading.Event()
    paths = []

    def complete(command, _environment, _cancel):
        path = Path(command[-1])
        paths.append(path)
        process._private_file(path.parent / "response.json",
                              write=process._Response(verification=_verified()).model_dump_json().encode())
        cancel.set()
        return 0

    monkeypatch.setattr(process, "_run_refresh_child", complete)
    with pytest.raises(process.MacOSSessionProcessError, match="canceled"):
        process.verify_macos_primary_display_refresh(cancel_event=cancel)
    assert not paths[0].parent.exists()


def test_mac_probe_failure_is_a_display_verification_error(monkeypatch):
    set_module_platform(monkeypatch, display_refresh, "darwin")

    def fail():
        raise process.MacOSSessionProcessError("Display refresh check canceled.")

    monkeypatch.setattr(process, "verify_macos_primary_display_refresh", fail)
    with pytest.raises(DisplayRefreshVerificationError, match="canceled"):
        display_refresh.verify_primary_display_refresh(SimpleNamespace(engine_id="psychopy"))
