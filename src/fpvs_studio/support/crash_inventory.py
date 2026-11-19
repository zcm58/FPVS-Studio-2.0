"""Bounded non-unique environment facts for automatic reports."""

from __future__ import annotations

import ctypes
import json
import platform
import re
import shlex
import struct
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from fpvs_studio.support.crash_reporting import CrashContext, OSFamily

_NAME = re.compile(r"[A-Za-z0-9 .,_()+:\-]{1,128}\Z")
_IDENTIFIER = re.compile(
    r"\b(?:serial|hostname|asset tag|service tag)\b|\b[0-9a-f]{12,}\b|"
    r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b|"
    r"\b[0-9a-f]{2}(?:[:-][0-9a-f]{2}){5}\b",
    re.IGNORECASE,
)
_DEPENDENCIES = {
    "pyside6": "PySide6",
    "psychopy": "psychopy",
    "numpy": "numpy",
    "scipy": "scipy",
    "mne": "mne",
}


def safe_name(value: object) -> str | None:
    """Reject untrusted inventory strings rather than trying to redact fragments."""
    if isinstance(value, str):
        value = value.strip()
        if _NAME.fullmatch(value) and not _IDENTIFIER.search(value):
            return value
    return None


def os_identity() -> tuple[OSFamily, str, str | None]:
    family = platform.system()
    if family == "Windows":
        info = sys.getwindowsversion()
        major, minor, build = info.platform_version
        version = f"{major}.{minor}.{build}"
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
                access=winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as key:
                revision, _ = winreg.QueryValueEx(key, "UBR")
            if isinstance(revision, int) and revision >= 0:
                version = f"{version}.{revision}"
        except OSError:
            pass
        return "Windows", version, version.split(".", 2)[2]
    if family == "Darwin":
        return "macOS", safe_name(platform.mac_ver()[0]) or "Unknown", None
    return "Linux", safe_name(platform.release()) or "Unknown", None


def _windows_inventory() -> dict:
    """Select model names and memory only. Never request raw CIM output."""
    directory = ctypes.create_unicode_buffer(32768)
    count = ctypes.windll.kernel32.GetSystemDirectoryW(directory, len(directory))
    if not 0 < count < len(directory):
        return {}
    shell = Path(directory.value) / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    query = """
$ErrorActionPreference = 'SilentlyContinue'
$computer = Get-CimInstance Win32_ComputerSystem | Select-Object -First 1
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$gpus = @(Get-CimInstance Win32_VideoController | Select-Object -First 4 -ExpandProperty Name)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
@{hardware_model = $computer.Model; cpu_model = $cpu.Name; gpus = $gpus;
  ram = $computer.TotalPhysicalMemory} | ConvertTo-Json -Compress
"""
    output = _system_output(
        [str(shell), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", query]
    )
    if output:
        try:
            data = json.loads(output)
        except ValueError:
            return {}
        if isinstance(data, dict):
            return data
    return {}


def _system_output(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=4,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (
        completed.stdout.decode("utf-8", errors="replace")
        if len(completed.stdout) <= 16 * 1024
        else ""
    )


def _read_system(path: str, limit: int) -> str:
    try:
        with Path(path).open(encoding="utf-8", errors="replace") as stream:
            return stream.read(limit)
    except OSError:
        return ""


def _linux_inventory() -> dict:
    cpu_info = _read_system("/proc/cpuinfo", 8192)
    cpu = re.search(r"^(?:model name|Hardware)\s*:\s*(.+)$", cpu_info, re.MULTILINE)
    ram = re.search(r"^MemTotal:\s+(\d+) kB", _read_system("/proc/meminfo", 4096), re.MULTILINE)
    gpus = []
    for line in _system_output(["/usr/bin/lspci", "-mm"]).splitlines():
        try:
            fields = shlex.split(line, comments=False)
        except ValueError:
            continue
        if len(fields) >= 4 and fields[1] in {
            "VGA compatible controller",
            "3D controller",
            "Display controller",
        }:
            # pci.ids often renders the preferred device label in square brackets.
            gpus.append(re.sub(r"[\[\]]", "", fields[3]))
    return {
        "hardware_model": _read_system("/sys/devices/virtual/dmi/id/product_name", 129),
        "cpu_model": cpu[1] if cpu else None,
        "gpus": gpus[:4],
        "ram": int(ram[1]) * 1024 if ram else None,
    }


def _mac_inventory() -> dict:
    facts = dict(
        line.split(": ", 1)
        for line in _system_output(
            [
                "/usr/sbin/sysctl",
                "hw.model",
                "machdep.cpu.brand_string",
                "hw.memsize",
            ]
        ).splitlines()
        if ": " in line
    )
    displays = _system_output(
        [
            "/usr/sbin/system_profiler",
            "SPDisplaysDataType",
            "-detailLevel",
            "mini",
            "-json",
        ]
    )
    gpus = []
    try:
        data = json.loads(displays)
        if isinstance(data, dict) and isinstance(data.get("SPDisplaysDataType"), list):
            gpus = [
                item.get("sppci_model") or item.get("_name")
                for item in data["SPDisplaysDataType"][:4]
                if isinstance(item, dict)
            ]
    except (ValueError, RecursionError):
        pass
    translated = _system_output(["/usr/sbin/sysctl", "-n", "sysctl.proc_translated"]).strip()
    ram = facts.get("hw.memsize", "")
    return {
        "hardware_model": facts.get("hw.model"),
        "cpu_model": facts.get("machdep.cpu.brand_string"),
        "cpu_arch": "arm64" if translated == "1" else platform.machine(),
        "translation": "Rosetta 2" if translated == "1" else None,
        "os_build": _system_output(["/usr/bin/sw_vers", "-buildVersion"]),
        "gpus": gpus,
        "ram": int(ram) if ram.isascii() and ram.isdecimal() and len(ram) < 16 else None,
    }


def collect_inventory(os_family: OSFamily, os_build: str | None) -> CrashContext:
    """Run in the diagnostics worker, without importing any scientific or GUI package."""
    if os_family == "Windows":
        hardware = _windows_inventory()
    elif os_family == "macOS":
        hardware = _mac_inventory()
    else:
        hardware = _linux_inventory()
    architecture = platform.machine()
    bits = struct.calcsize("P") * 8
    process_arch = (
        architecture
        if "64" not in architecture or bits == 64
        else ("x86" if architecture.lower() in {"amd64", "x86_64"} else "32-bit")
    )
    context: dict[str, object] = {
        key: safe
        for key, value in {
            "os_build": os_build or hardware.get("os_build"),
            "hardware_model": hardware.get("hardware_model"),
            "cpu_arch": hardware.get("cpu_arch") or architecture,
            "cpu_model": hardware.get("cpu_model"),
            "process_arch": process_arch,
            "translation": hardware.get("translation"),
        }.items()
        if (safe := safe_name(value))
    }
    if isinstance(hardware.get("gpus"), list):
        gpus = list(
            dict.fromkeys(safe for value in hardware["gpus"][:4] if (safe := safe_name(value)))
        )
        if gpus:
            context["gpus"] = gpus
    memory = hardware.get("ram")
    if type(memory) is int and 0 < memory < (65537 << 30):
        ram_gib = round(memory / (1 << 30))
        if 1 <= ram_gib <= 65536:
            context["ram_gib"] = ram_gib
    software = {"python": platform.python_version()}
    for key, package in _DEPENDENCIES.items():
        module = sys.modules.get(package)
        version = vars(module).get("__version__") if module else None
        if not version:
            try:
                version = metadata.version(package)
            except metadata.PackageNotFoundError:
                continue
        if safe := safe_name(version):
            software[key] = safe
    qt_core = sys.modules.get("PySide6.QtCore")
    qversion = vars(qt_core).get("qVersion") if qt_core else None
    if callable(qversion) and (qt_version := safe_name(qversion())):
        software["qt"] = qt_version
    context["software"] = software
    return CrashContext.model_validate(context)
