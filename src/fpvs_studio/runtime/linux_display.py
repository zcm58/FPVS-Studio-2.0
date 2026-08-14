"""Read-only Linux display-mode queries for refresh verification."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any

from fpvs_studio.runtime.display_mode import DisplayModeError, NativeDisplayMode

_COMMAND_TIMEOUT_SECONDS = 10.0
_XRANDR_OUTPUT_RE = re.compile(r"^(?P<name>\S+)\s+connected(?P<details>.*)$")
_XRANDR_CURRENT_RATE_RE = re.compile(r"(?P<hz>\d+(?:\.\d+)?)\*")


def _run_display_query(command: Sequence[str]) -> str:
    try:
        result = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DisplayModeError(f"Linux display query {command[0]!r} failed: {exc}") from exc
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
        raise DisplayModeError(
            f"Linux display query {command[0]!r} exited with code "
            f"{result.returncode}: {details}"
        )
    return result.stdout


def _mapping(value: object, *, description: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DisplayModeError(f"KScreen returned an invalid {description} record.")
    return value


def _select_kscreen_output(outputs: object) -> Mapping[str, Any]:
    if not isinstance(outputs, list):
        raise DisplayModeError("KScreen output did not contain a display list.")
    active = [
        _mapping(output, description="display")
        for output in outputs
        if isinstance(output, Mapping)
        and output.get("connected") is True
        and output.get("enabled") is True
    ]
    if not active:
        raise DisplayModeError("KScreen reported no enabled connected displays.")
    if len(active) == 1:
        return active[0]

    priorities: list[int] = []
    for output in active:
        priority = output.get("priority")
        if isinstance(priority, int) and not isinstance(priority, bool) and priority > 0:
            priorities.append(priority)
    if not priorities:
        raise DisplayModeError(
            "KScreen reported multiple enabled displays without a primary priority."
        )
    primary_priority = min(priorities)
    primary = [output for output in active if output.get("priority") == primary_priority]
    if len(primary) != 1:
        raise DisplayModeError(
            "KScreen reported multiple enabled displays at the primary priority."
        )
    return primary[0]


def _mode_refresh_hz(mode: Mapping[str, Any]) -> float:
    raw_refresh = mode.get("refreshRate")
    if isinstance(raw_refresh, bool) or not isinstance(raw_refresh, (int, float)):
        raise DisplayModeError("KScreen current mode has no numeric refresh rate.")
    refresh_hz = float(raw_refresh)
    if not isfinite(refresh_hz) or refresh_hz <= 0:
        raise DisplayModeError("KScreen current mode has an invalid refresh rate.")
    return refresh_hz


def parse_kscreen_display_mode(payload: str) -> NativeDisplayMode:
    """Parse `kscreen-doctor --json` output into the active primary mode."""

    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise DisplayModeError(f"KScreen returned invalid JSON: {exc}") from exc
    root = _mapping(document, description="configuration")
    output = _select_kscreen_output(root.get("outputs"))

    display_name = output.get("name")
    current_mode_id = output.get("currentModeId")
    modes = output.get("modes")
    if not isinstance(display_name, str) or not display_name.strip():
        raise DisplayModeError("KScreen primary display has no connector name.")
    if not isinstance(current_mode_id, (str, int)) or not str(current_mode_id).strip():
        raise DisplayModeError("KScreen primary display has no current mode identifier.")
    if not isinstance(modes, list):
        raise DisplayModeError("KScreen primary display has no mode list.")

    matching_modes = [
        _mapping(mode, description="mode")
        for mode in modes
        if isinstance(mode, Mapping) and str(mode.get("id")) == str(current_mode_id)
    ]
    if len(matching_modes) != 1:
        raise DisplayModeError(
            "KScreen could not resolve one current mode for the primary display."
        )

    vrr_policy = output.get("vrrPolicy")
    if (
        isinstance(vrr_policy, bool)
        or not isinstance(vrr_policy, int)
        or vrr_policy not in {0, 1, 2}
    ):
        raise DisplayModeError("KScreen returned an unknown variable-refresh policy.")
    vrr_labels = {0: "Never", 1: "Always", 2: "Automatic"}
    return NativeDisplayMode(
        platform_name="Linux",
        display_name=display_name.strip(),
        refresh_hz=_mode_refresh_hz(matching_modes[0]),
        source_name="KScreen",
        exact_refresh=False,
        variable_refresh_enabled=vrr_policy != 0,
        variable_refresh_label=(vrr_labels[vrr_policy] if vrr_policy != 0 else None),
    )


def query_kscreen_display_mode(executable: str) -> NativeDisplayMode:
    """Query KDE's structured display configuration."""

    return parse_kscreen_display_mode(_run_display_query((executable, "--json")))


def parse_xrandr_display_mode(payload: str) -> NativeDisplayMode:
    """Parse an XRandR current-mode listing and select its primary output."""

    displays: list[tuple[str, bool, float]] = []
    current_name: str | None = None
    current_primary = False
    current_hz: float | None = None

    def _finish_current() -> None:
        if current_name is not None and current_hz is not None:
            displays.append((current_name, current_primary, current_hz))

    for line in payload.splitlines():
        output_match = _XRANDR_OUTPUT_RE.match(line)
        if output_match:
            _finish_current()
            current_name = output_match.group("name")
            current_primary = " primary " in f" {output_match.group('details')} "
            current_hz = None
            continue
        if current_name is None or current_hz is not None:
            continue
        rate_match = _XRANDR_CURRENT_RATE_RE.search(line)
        if rate_match:
            current_hz = float(rate_match.group("hz"))
    _finish_current()

    primary = [display for display in displays if display[1]]
    selected = primary if primary else displays
    if len(selected) != 1:
        raise DisplayModeError(
            "XRandR could not resolve one active primary display. Mark the presentation "
            "display as primary or use a single active display."
        )
    display_name, _is_primary, refresh_hz = selected[0]
    return NativeDisplayMode(
        platform_name="Linux",
        display_name=display_name,
        refresh_hz=refresh_hz,
        source_name="XRandR",
        exact_refresh=False,
    )


def query_xrandr_display_mode(executable: str) -> NativeDisplayMode:
    """Query an X11 session's active primary display mode."""

    return parse_xrandr_display_mode(_run_display_query((executable, "--current")))


def query_primary_linux_display_mode() -> NativeDisplayMode:
    """Return the native mode for the Linux primary/default fullscreen display."""

    session_type = os.environ.get("XDG_SESSION_TYPE", "").strip().casefold()
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").casefold()
    kscreen = shutil.which("kscreen-doctor")
    if kscreen is not None and ("kde" in desktop or session_type == "wayland"):
        return query_kscreen_display_mode(kscreen)

    if session_type == "wayland":
        raise DisplayModeError(
            "This Wayland compositor does not expose a supported fixed-mode and "
            "variable-refresh query. KDE Plasma with kscreen-doctor is currently "
            "supported for Wayland timing verification."
        )

    xrandr = shutil.which("xrandr")
    if xrandr is not None:
        return query_xrandr_display_mode(xrandr)

    if kscreen is not None:
        return query_kscreen_display_mode(kscreen)
    raise DisplayModeError(
        "Linux display-mode detection requires kscreen-doctor (KDE) or xrandr (X11)."
    )
