"""Recorder readiness protocol and bounded Windows helper tests; no real UI access."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import Mock

import pytest

from fpvs_studio.runtime import unicorn_recorder as recorder


def _snapshot(**changes):
    return {"state": "recording", "version": "1.24.2.2760", "process_id": 1234, **changes}


@pytest.fixture
def windows_probe(monkeypatch):
    monkeypatch.setattr(recorder.sys, "platform", "win32")
    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    run = Mock(return_value=subprocess.CompletedProcess([], 0, json.dumps(_snapshot()), ""))
    monkeypatch.setattr(recorder.subprocess, "run", run)
    return run


def test_fresh_bounded_hidden_read_only_probe_for_each_attempt(windows_probe):
    recorder.require_unicorn_recorder_recording()
    recorder.require_unicorn_recorder_recording()
    assert windows_probe.call_count == 2
    args, kwargs = windows_probe.call_args
    assert args[0][0].replace("\\", "/").lower().endswith(
        "windowspowershell/v1.0/powershell.exe"
    )
    assert args[0][1:5] == ["-NoLogo", "-NoProfile", "-NonInteractive", "-STA"]
    assert args[0][5] == "-EncodedCommand"
    assert "-ExecutionPolicy" not in args[0]
    assert kwargs["timeout"] == 12
    assert kwargs["capture_output"]
    assert kwargs["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)
    assert not kwargs.get("shell", False)


@pytest.mark.parametrize("snapshot, message", [
    ({"state": "not_running"}, "not open"),
    ({"state": "ambiguous"}, "More than one"),
    (_snapshot(state="not_recording"), "using Recorder's saved settings"),
    (_snapshot(state="not_writing"), "no new recording data was saved"),
    (_snapshot(state="unavailable"), "could not verify"),
    ({"state": "unavailable"}, "could not verify"),
    (_snapshot(state="not_configured"), "saved settings do not describe"),
    (_snapshot(state="acquiring"), "could not verify"),
    (_snapshot(state="Recording"), "could not verify"),
    (_snapshot(version="2.0"), "version"),
    (_snapshot(version=None), "version"),
    (_snapshot(process_id=True), "could not verify"),
    (_snapshot(process_id=0), "could not verify"),
    (_snapshot(process_id=-1), "could not verify"),
    (_snapshot(process_id="1234"), "could not verify"),
    (True, "could not verify"),
    ([], "could not verify"),
    (None, "could not verify"),
])
def test_non_recording_or_unverifiable_snapshot_blocks(windows_probe, snapshot, message):
    windows_probe.return_value.stdout = json.dumps(snapshot)
    with pytest.raises(recorder.RecorderReadinessError, match=message):
        recorder.require_unicorn_recorder_recording()


@pytest.mark.parametrize("state", ["not_recording", "not_configured"])
def test_saved_output_context_explains_restart_recovery(windows_probe, state, tmp_path):
    folder = str(tmp_path / "Unicorn Data")
    windows_probe.return_value.stdout = json.dumps(_snapshot(
        state=state, raw_folder=folder, raw_prefix="Studio_Test",
    ))
    with pytest.raises(recorder.RecorderReadinessError) as error:
        recorder.require_unicorn_recorder_recording()
    message = str(error.value)
    assert "saved settings" in message
    assert "If Recorder is already recording" in message
    assert "close and reopen Recorder" in message
    assert "Recorder saves logging settings only when it closes" in message
    assert f"Saved raw BDF folder: {folder}" in message
    assert "Saved filename prefix: Studio_Test" in message
    assert "headset is disconnected" not in message


@pytest.mark.parametrize("state", ["not_recording", "not_configured"])
@pytest.mark.parametrize("diagnostics", [{}, {"raw_folder": None, "raw_prefix": None}])
def test_missing_optional_context_keeps_actionable_failure(windows_probe, state, diagnostics):
    windows_probe.return_value.stdout = json.dumps(_snapshot(state=state, **diagnostics))
    with pytest.raises(recorder.RecorderReadinessError) as error:
        recorder.require_unicorn_recorder_recording()
    message = str(error.value)
    assert "saved settings" in message
    assert "close and reopen Recorder" in message
    assert "Saved raw BDF folder:" not in message
    assert "Saved filename prefix:" not in message
    assert "None" not in message


@pytest.mark.parametrize("key, value", [
    ("raw_folder", {"untrusted": "path"}),
    ("raw_folder", True),
    ("raw_folder", ""),
    ("raw_folder", "   "),
    ("raw_folder", "x" * 2049),
    ("raw_folder", "folder\nrecording verified"),
    ("raw_folder", "folder\x00suffix"),
    ("raw_prefix", ["prefix"]),
    ("raw_prefix", 123),
    ("raw_prefix", "x" * 256),
    ("raw_prefix", "prefix\rrecording verified"),
    ("raw_prefix", "prefix\u202esuffix"),
])
def test_malformed_optional_diagnostic_is_omitted_without_hiding_failure(
    windows_probe, key, value,
):
    diagnostics = {"raw_folder": r"C:\Raw", "raw_prefix": "Studio_Test", key: value}
    windows_probe.return_value.stdout = json.dumps(_snapshot(
        state="not_recording", **diagnostics,
    ))
    with pytest.raises(recorder.RecorderReadinessError) as error:
        recorder.require_unicorn_recorder_recording()
    message = str(error.value)
    assert "using Recorder's saved settings" in message
    assert "close and reopen Recorder" in message
    if key == "raw_folder":
        assert "Saved raw BDF folder:" not in message
        assert "Saved filename prefix: Studio_Test" in message
    else:
        assert "Saved filename prefix:" not in message
        assert "Saved raw BDF folder: C:\\Raw" in message


@pytest.mark.parametrize("changes", [
    {"state": None},
    {"state": ["recording"]},
    {"state": "unknown"},
    {"process_id": None},
    {"process_id": True},
])
def test_saved_output_context_is_never_readiness_evidence(windows_probe, changes):
    windows_probe.return_value.stdout = json.dumps(_snapshot(
        raw_folder=r"C:\Raw", raw_prefix="Studio_Test", **changes,
    ))
    with pytest.raises(recorder.RecorderReadinessError, match="could not verify"):
        recorder.require_unicorn_recorder_recording()


@pytest.mark.parametrize("diagnostics", [
    {},
    {"raw_folder": None, "raw_prefix": None},
    {"raw_folder": r"C:\Raw", "raw_prefix": "Studio_Test"},
])
def test_optional_context_does_not_change_valid_recording_acceptance(windows_probe, diagnostics):
    windows_probe.return_value.stdout = json.dumps(_snapshot(**diagnostics))
    recorder.require_unicorn_recorder_recording()


@pytest.mark.parametrize("output", ["", "not JSON", "{\"state\":", "{}\n{}"])
def test_malformed_output_never_passes(windows_probe, output):
    windows_probe.return_value.stdout = output
    with pytest.raises(recorder.RecorderReadinessError, match="unreadable"):
        recorder.require_unicorn_recorder_recording()


def test_utf8_bom_is_accepted(windows_probe):
    windows_probe.return_value.stdout = "\ufeff" + json.dumps(_snapshot())
    recorder.require_unicorn_recorder_recording()


@pytest.mark.parametrize("failure, message", [
    (subprocess.TimeoutExpired("powershell.exe", 12), "did not respond"),
    (FileNotFoundError("powershell.exe"), "could not run"),
    (PermissionError("denied"), "could not run"),
])
def test_helper_failures_are_actionable_and_never_fall_back(windows_probe, failure, message):
    windows_probe.side_effect = failure
    with pytest.raises(recorder.RecorderReadinessError, match=message):
        recorder.require_unicorn_recorder_recording()
    assert windows_probe.call_count == 1


def test_failed_helper_cannot_pass_with_recording_json(windows_probe):
    windows_probe.return_value.returncode = 1
    with pytest.raises(recorder.RecorderReadinessError, match="could not read"):
        recorder.require_unicorn_recorder_recording()


def test_excessive_output_fails_closed(windows_probe):
    windows_probe.return_value.stdout = " " * 8193
    with pytest.raises(recorder.RecorderReadinessError, match="could not read"):
        recorder.require_unicorn_recorder_recording()


def test_other_platform_does_not_start_helper(monkeypatch, windows_probe):
    monkeypatch.setattr(recorder.sys, "platform", "linux")
    with pytest.raises(recorder.RecorderReadinessError, match="require Windows"):
        recorder.require_unicorn_recorder_recording()
    windows_probe.assert_not_called()
