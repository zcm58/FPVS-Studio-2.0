"""Explicit platform boundaries for tests, independent of the machine running them.

Windows acquisition/rendering contracts remain the primary defaults in their test
fixtures. Mac adapter tests opt into Darwin at the same owning module. Neither
choice changes the host interpreter's process-wide ``sys.platform``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def platform_sys(
    platform_name: str, *, source: ModuleType | SimpleNamespace = sys,
) -> SimpleNamespace:
    """Copy a module's sys view while retaining the real interpreter capabilities."""

    values = vars(source).copy()
    values["platform"] = platform_name
    return SimpleNamespace(**values)


def set_module_platform(
    monkeypatch: pytest.MonkeyPatch, module: ModuleType, platform_name: str,
) -> None:
    """Select a platform only at the production owner under test."""

    monkeypatch.setattr(module, "sys", platform_sys(platform_name, source=module.sys))


def windows_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the primary launcher policy with the test's existing fake services."""

    from fpvs_studio.runtime import launcher

    set_module_platform(monkeypatch, launcher, "win32")


def python_child_command(script: str, *arguments: str | Path) -> list[str]:
    """Use a regular interpreter for real IPC tests, retaining parent import paths.

    POSIX venv executables are commonly links. Resolve the test interpreter without
    relaxing the production helper's executable/link validation, and explicitly
    retain the virtual environment's import context in the synthetic child.
    """

    bootstrap = f"import sys\nsys.path[:0] = {sys.path!r}\n{script}"
    return [str(Path(sys.executable).resolve()), "-c", bootstrap, *map(str, arguments)]
