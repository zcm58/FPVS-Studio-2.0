"""Read-only Windows LPT device and allocated I/O-resource discovery."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from fpvs_studio.triggers.parallel_windows import windows_system_directory

_LPT_NAME = re.compile(r"\bLPT([1-9]\d*)\b", re.IGNORECASE)
_METADATA_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$devices = @(Get-CimInstance -ClassName Win32_PnPEntity)
$rows = @(foreach ($port in @(Get-CimInstance -ClassName Win32_ParallelPort)) {
    $device = @($devices | Where-Object { $_.DeviceID -eq $port.PNPDeviceID })
    $addresses = @()
    if ($device.Count -eq 1) {
        $addresses = @(Get-CimAssociatedInstance -InputObject $device[0] `
            -Association Win32_PnPAllocatedResource -ResultClassName Win32_PortResource |
            ForEach-Object { [string]$_.StartingAddress })
    }
    [pscustomobject]@{
        Name = [string]$port.Name
        DeviceId = [string]$port.PNPDeviceID
        Addresses = $addresses
    }
})
ConvertTo-Json -InputObject $rows -Compress -Depth 4
"""


class ParallelPortDiscoveryError(RuntimeError):
    """Windows parallel-port metadata could not be enumerated."""


@dataclass(frozen=True, slots=True)
class ParallelPortCandidate:
    """One Windows LPT declaration, without proving wiring or marker reception."""

    name: str
    address: int | None
    device_id: str


def discover_parallel_ports(
    *, cancelled: Callable[[], bool] | None = None,
) -> tuple[ParallelPortCandidate, ...]:
    """Read device/resource metadata only; never load a driver or probe I/O ports.

    Missing, invalid or multiple resource addresses require a manual address.
    No conventional LPT base address is substituted for incomplete metadata.
    """

    _check_cancelled(cancelled)
    if sys.platform != "win32":
        raise ParallelPortDiscoveryError("Native parallel-port discovery requires Windows.")
    try:
        rows = json.loads(_query_metadata(cancelled))
    except InterruptedError:
        raise
    except (OSError, ValueError) as exc:
        raise ParallelPortDiscoveryError("Unable to read Windows parallel-port metadata.") from exc
    if not isinstance(rows, list):
        raise ParallelPortDiscoveryError("Windows returned invalid parallel-port metadata.")
    candidates: dict[tuple[str, str], ParallelPortCandidate] = {}
    for row in rows:
        _check_cancelled(cancelled)
        if not isinstance(row, dict):
            raise ParallelPortDiscoveryError("Windows returned invalid parallel-port metadata.")
        name = row.get("Name")
        match = _LPT_NAME.search(name) if isinstance(name, str) else None
        if match is None:
            continue
        name = f"LPT{int(match[1])}"
        identity = row.get("DeviceId")
        identity = identity.strip() if isinstance(identity, str) else ""
        address = _resource_address(row.get("Addresses")) if identity else None
        key = (name, identity.casefold())
        candidate = ParallelPortCandidate(name, address, identity)
        previous = candidates.get(key)
        if previous is not None:
            candidate = ParallelPortCandidate(
                name, address if previous.address == address else None,
                min(identity, previous.device_id),
            )
        candidates[key] = candidate
    _check_cancelled(cancelled)
    name_counts: dict[str, int] = {}
    for candidate in candidates.values():
        name_counts[candidate.name] = name_counts.get(candidate.name, 0) + 1
    resolved = (
        ParallelPortCandidate(
            item.name, item.address if name_counts[item.name] == 1 else None, item.device_id,
        ) for item in candidates.values()
    )
    return tuple(sorted(resolved, key=lambda item: (
        int(item.name[3:]), item.device_id.casefold(), item.device_id,
    )))


def _resource_address(values: object) -> int | None:
    if not isinstance(values, list) or not values:
        return None
    addresses: set[int] = set()
    for value in values:
        try:
            if isinstance(value, str):
                address = int(value, 16 if value.lower().startswith("0x") else 10)
            elif type(value) is int:
                address = value
            else:
                return None
        except ValueError:
            return None
        if not 1 <= address <= 65535:
            return None
        addresses.add(address)
    return next(iter(addresses)) if len(addresses) == 1 else None


def _query_metadata(cancelled: Callable[[], bool] | None) -> str:
    executable = windows_system_directory() / "WindowsPowerShell/v1.0/powershell.exe"
    _check_cancelled(cancelled)
    process = subprocess.Popen(
        [str(executable), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", _METADATA_SCRIPT],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
        creationflags=0x08000000,
    )
    deadline = time.monotonic() + 15
    try:
        while True:
            _check_cancelled(cancelled)
            if time.monotonic() >= deadline:
                raise ParallelPortDiscoveryError("Windows parallel-port discovery timed out.")
            try:
                output, _error = process.communicate(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                continue
        _check_cancelled(cancelled)
        if process.returncode != 0:
            raise ParallelPortDiscoveryError("Unable to enumerate Windows parallel-port resources.")
        return output
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()


def _check_cancelled(cancelled: Callable[[], bool] | None) -> None:
    if cancelled is not None and cancelled():
        raise InterruptedError("Parallel-port discovery cancelled.")
