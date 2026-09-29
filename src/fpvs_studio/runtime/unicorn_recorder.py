"""Bounded, read-only checks of local Unicorn Recorder raw recording activity.

This observes the application's recording state, not saved EEG integrity, electrode
contact, trigger reception, or a guarantee that recording will continue after launch.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .unicorn_recorder_windows import POWER_SHELL_SCRIPT


class RecorderReadinessError(RuntimeError):
    """Recorder is unavailable, idle, or its recording state cannot be verified."""


_PROBE_TIMEOUT_SECONDS = 12
_SUPPORTED_RECORDER_VERSIONS = frozenset({"1.24.2.2760"})
_SETTINGS_RECOVERY = (
    "If Recorder is already recording or you changed its raw BDF logging settings, "
    "stop recording, close and reopen Recorder, then reconnect and start recording "
    "before launching again. Recorder saves logging settings only when it closes."
)


def require_unicorn_recorder_recording() -> None:
    """Fail closed unless one supported Recorder is writing its raw BDF output.

    Call in the launch worker, before participant presentation, never on the GUI
    thread or within a frame callback. No state is cached between launch attempts.
    """

    if sys.platform != "win32":
        raise RecorderReadinessError(
            "Automatic Unicorn Recorder recording checks require Windows."
        )
    executable = (
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    )
    encoded = base64.b64encode(POWER_SHELL_SCRIPT.encode("utf-16-le")).decode("ascii")
    try:
        result = subprocess.run(
            [str(executable), "-NoLogo", "-NoProfile", "-NonInteractive", "-STA",
             "-EncodedCommand", encoded],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_PROBE_TIMEOUT_SECONDS,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RecorderReadinessError(
            "Unicorn Recorder did not respond to the recording check. "
            "Check Recorder, then launch again."
        ) from exc
    except OSError as exc:
        raise RecorderReadinessError(
            "Studio could not run the Unicorn Recorder recording check. "
            "Check that Windows PowerShell is available, then launch again."
        ) from exc
    if result.returncode != 0 or len(result.stdout) > 8192:
        raise RecorderReadinessError(
            "Studio could not read Unicorn Recorder's recording state. "
            f"Check Recorder and its raw BDF output. {_SETTINGS_RECOVERY}"
        )
    try:
        snapshot: Any = json.loads(result.stdout.lstrip("\ufeff"))
    except (TypeError, ValueError) as exc:
        raise RecorderReadinessError(
            "Studio received an unreadable Unicorn Recorder recording state. "
            "Check Recorder, then launch again."
        ) from exc
    _require_recording_snapshot(snapshot)


def _require_recording_snapshot(snapshot: object) -> None:
    if not isinstance(snapshot, dict):
        raise RecorderReadinessError("Studio could not verify Unicorn Recorder's recording state.")
    state = snapshot.get("state")
    if state == "not_running":
        raise RecorderReadinessError(
            "Unicorn Recorder is not open. Please open the Unicorn Recorder software "
            "and start recording before starting the experiment."
        )
    if state == "ambiguous":
        raise RecorderReadinessError(
            "More than one Unicorn Recorder is open. Close the extra instances, "
            "start recording in the intended Recorder, then launch again."
        )
    version = snapshot.get("version")
    if state == "unavailable" and version is None:
        raise RecorderReadinessError(
            "Studio could not verify Unicorn Recorder's recording state. "
            f"{_SETTINGS_RECOVERY}"
        )
    if not isinstance(version, str) or version not in _SUPPORTED_RECORDER_VERSIONS:
        raise RecorderReadinessError(
            "Studio cannot verify recording state for this Unicorn Recorder version. "
            "The recording check currently supports Recorder 1.24.02 (1.24.2.2760)."
        )
    if state == "not_recording":
        raise RecorderReadinessError(
            "Unicorn Recorder is open, but Studio could not verify an active raw BDF "
            "recording using Recorder's saved settings.\n\n"
            f"{_SETTINGS_RECOVERY}\n\n"
            "Otherwise, connect the headset in Recorder and start recording data "
            "before launching the experiment."
            f"{_saved_output_description(snapshot)}"
        )
    if state == "not_writing":
        raise RecorderReadinessError(
            "Unicorn Recorder is open, but no new recording data was saved during "
            "the check. Please ensure the Unicorn headset is switched on and connected "
            "to this PC, check the connection and recording status in Recorder, "
            "and try launching again."
        )
    if state == "not_configured":
        raise RecorderReadinessError(
            "Recorder's saved settings do not describe enabled, valid raw BDF logging. "
            "Check raw BDF logging in Recorder.\n\n"
            f"{_SETTINGS_RECOVERY}"
            f"{_saved_output_description(snapshot)}"
        )
    process_id = snapshot.get("process_id")
    if (
        state != "recording"
        or type(process_id) is not int
        or process_id <= 0
    ):
        raise RecorderReadinessError(
            "Studio could not verify that Unicorn Recorder is recording. "
            f"{_SETTINGS_RECOVERY}"
        )


def _saved_output_description(snapshot: dict[str, Any]) -> str:
    """Display bounded optional diagnostics without treating them as readiness proof."""

    details = []
    for key, label, limit in (
        ("raw_folder", "Saved raw BDF folder", 2048),
        ("raw_prefix", "Saved filename prefix", 255),
    ):
        value = snapshot.get(key)
        if (
            isinstance(value, str)
            and value.strip()
            and len(value) <= limit
            and value.isprintable()
        ):
            details.append(f"{label}: {value}")
    return "\n\n" + "\n".join(details) if details else ""
