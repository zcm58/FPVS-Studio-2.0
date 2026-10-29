"""Read-only native LPT discovery using synthetic Windows device resources."""

from __future__ import annotations

import json
import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

from fpvs_studio.triggers import parallel_discovery as discovery


def _metadata(monkeypatch, rows):
    monkeypatch.setattr(discovery, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(discovery, "_query_metadata", lambda _cancelled: json.dumps(rows))


def test_discovery_normalizes_deduplicates_and_orders_only_metadata(monkeypatch) -> None:
    rows = [
        {"Name": "PCI Parallel Port (LPT10)", "DeviceId": "PCI/10", "Addresses": ["56320"]},
        {"Name": "LPT2", "DeviceId": "ACPI/2", "Addresses": ["888", "888"]},
        {"Name": "LPT1", "DeviceId": "ACPI/1", "Addresses": ["0x278"]},
        {"Name": "lpt2", "DeviceId": "acpi/2", "Addresses": ["888"]},
        {"Name": "USB Printer", "DeviceId": "USB/1", "Addresses": ["888"]},
    ]
    _metadata(monkeypatch, rows)
    expected = (
        discovery.ParallelPortCandidate("LPT1", 0x278, "ACPI/1"),
        discovery.ParallelPortCandidate("LPT2", 0x378, "ACPI/2"),
        discovery.ParallelPortCandidate("LPT10", 0xDC00, "PCI/10"),
    )
    assert discovery.discover_parallel_ports() == expected
    _metadata(monkeypatch, list(reversed(rows)))
    assert discovery.discover_parallel_ports() == expected


@pytest.mark.parametrize("addresses", [
    [], None, "888", [None], [True], [888.0], ["bad"], ["0"], ["65536"],
    ["888", "1912"], ["888", "bad"],
])
def test_missing_invalid_or_ambiguous_resources_never_guess_address(monkeypatch, addresses) -> None:
    _metadata(monkeypatch, [{"Name": "LPT1", "DeviceId": "ACPI/1", "Addresses": addresses}])
    assert discovery.discover_parallel_ports() == (
        discovery.ParallelPortCandidate("LPT1", None, "ACPI/1"),
    )


def test_conflicting_duplicate_metadata_needs_manual_address(monkeypatch) -> None:
    _metadata(monkeypatch, [
        {"Name": "LPT1", "DeviceId": "ACPI/1", "Addresses": ["888"]},
        {"Name": "LPT1", "DeviceId": "ACPI/1", "Addresses": ["632"]},
        {"Name": "LPT1", "DeviceId": "ACPI/1", "Addresses": ["888"]},
    ])
    assert discovery.discover_parallel_ports()[0].address is None


def test_missing_device_identity_does_not_adopt_unmatched_resource(monkeypatch) -> None:
    _metadata(monkeypatch, [{"Name": "LPT1", "Addresses": ["888"]}])
    assert discovery.discover_parallel_ports() == (
        discovery.ParallelPortCandidate("LPT1", None, ""),
    )


def test_multiple_devices_claiming_one_lpt_name_need_manual_address(monkeypatch) -> None:
    _metadata(monkeypatch, [
        {"Name": "LPT1", "DeviceId": "ACPI/1", "Addresses": ["888"]},
        {"Name": "LPT1", "DeviceId": "PCI/1", "Addresses": ["56320"]},
    ])
    assert discovery.discover_parallel_ports() == (
        discovery.ParallelPortCandidate("LPT1", None, "ACPI/1"),
        discovery.ParallelPortCandidate("LPT1", None, "PCI/1"),
    )


def test_empty_inventory_and_immutable_candidates(monkeypatch) -> None:
    _metadata(monkeypatch, [])
    assert discovery.discover_parallel_ports() == ()
    candidate = discovery.ParallelPortCandidate("LPT1", None, "ACPI/1")
    with pytest.raises(FrozenInstanceError):
        candidate.address = 888  # type: ignore[misc]


@pytest.mark.parametrize("payload", ["not json", "{}", "[null]"])
def test_invalid_metadata_is_explicit(monkeypatch, payload) -> None:
    _metadata(monkeypatch, [])
    monkeypatch.setattr(discovery, "_query_metadata", lambda _cancelled: payload)
    with pytest.raises(discovery.ParallelPortDiscoveryError, match="metadata"):
        discovery.discover_parallel_ports()


def test_metadata_access_failure_is_explicit(monkeypatch) -> None:
    _metadata(monkeypatch, [])

    def fail(_cancelled):
        raise OSError("CIM unavailable")

    monkeypatch.setattr(discovery, "_query_metadata", fail)
    with pytest.raises(discovery.ParallelPortDiscoveryError, match="metadata") as error:
        discovery.discover_parallel_ports()
    assert isinstance(error.value.__cause__, OSError)


def test_unsupported_platform_does_not_query_metadata(monkeypatch) -> None:
    monkeypatch.setattr(discovery, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(discovery, "_query_metadata", lambda _cancelled: pytest.fail("not Windows"))
    with pytest.raises(discovery.ParallelPortDiscoveryError, match="requires Windows"):
        discovery.discover_parallel_ports()


@pytest.mark.parametrize("cancel_at", [1, 2, 3])
def test_discovery_cancellation_before_query_during_rows_and_after_rows(
    monkeypatch, cancel_at,
) -> None:
    _metadata(monkeypatch, [{"Name": "LPT1", "DeviceId": "ACPI/1", "Addresses": ["888"]}])
    calls = 0

    def cancelled():
        nonlocal calls
        calls += 1
        return calls == cancel_at

    with pytest.raises(InterruptedError, match="cancelled"):
        discovery.discover_parallel_ports(cancelled=cancelled)


class FakeProcess:
    def __init__(self, *, fail=False, block=False):
        self.returncode = None
        self.fail = fail
        self.block = block
        self.killed = False

    def communicate(self, timeout=None):
        if self.block and not self.killed:
            raise subprocess.TimeoutExpired("powershell", timeout)
        self.returncode = 1 if self.fail else 0
        return "[]", "CIM unavailable" if self.fail else ""

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True


def _process(monkeypatch, process):
    calls = []
    monkeypatch.setattr(discovery, "windows_system_directory", lambda: Path("C:/Windows/System32"))

    def launch(*args, **kwargs):
        calls.append((args, kwargs))
        return process

    monkeypatch.setattr(discovery.subprocess, "Popen", launch)
    return calls


def test_metadata_query_uses_fixed_system_powershell_and_no_driver(monkeypatch) -> None:
    calls = _process(monkeypatch, FakeProcess())
    assert discovery._query_metadata(None) == "[]"
    command = calls[0][0][0]
    assert command[0] == str(Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"))
    assert command[1:5] == ["-NoLogo", "-NoProfile", "-NonInteractive", "-Command"]
    assert "Win32_ParallelPort" in command[-1] and "Win32_PnPAllocatedResource" in command[-1]
    assert calls[0][1]["creationflags"] == 0x08000000


def test_process_failure_and_cancellation_are_explicit_and_reaped(monkeypatch) -> None:
    process = FakeProcess(fail=True)
    _process(monkeypatch, process)
    with pytest.raises(discovery.ParallelPortDiscoveryError, match="resources"):
        discovery._query_metadata(None)
    process = FakeProcess(block=True)
    _process(monkeypatch, process)
    calls = 0

    def cancelled():
        nonlocal calls
        calls += 1
        return calls >= 3

    with pytest.raises(InterruptedError, match="cancelled"):
        discovery._query_metadata(cancelled)
    assert process.killed


def test_process_timeout_is_explicit_and_reaps_child(monkeypatch) -> None:
    process = FakeProcess(block=True)
    _process(monkeypatch, process)
    ticks = iter([0, 0, 16])
    monkeypatch.setattr(discovery, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
    with pytest.raises(discovery.ParallelPortDiscoveryError, match="timed out"):
        discovery._query_metadata(None)
    assert process.killed
