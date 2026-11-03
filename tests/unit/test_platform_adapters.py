"""Platform test adapters preserve the real host and private-child safety boundary."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from tests.platform_adapters import platform_sys, python_child_command, set_module_platform


@pytest.mark.parametrize("selected", ["win32", "darwin", "linux"])
def test_platform_view_is_local_and_restores_its_owner(monkeypatch, selected):
    host_platform = sys.platform
    owner = ModuleType("synthetic_platform_owner")
    owner.sys = sys
    with monkeypatch.context() as scoped:
        set_module_platform(scoped, owner, selected)
        assert owner.sys.platform == selected
        assert owner.sys.executable == sys.executable
        assert owner.sys.modules is sys.modules
        assert sys.platform == host_platform
    assert owner.sys is sys


def test_independent_owner_views_do_not_change_each_other():
    windows = platform_sys("win32")
    mac = platform_sys("darwin")
    windows.frozen = True
    assert windows.platform == "win32"
    assert mac.platform == "darwin"
    assert getattr(mac, "frozen", None) == getattr(sys, "frozen", None)


def test_real_child_keeps_source_and_installed_dependencies_without_linked_executable():
    command = python_child_command(
        "import sys, packaging.version, fpvs_studio\n"
        "assert sys.argv[1] == 'Unicode café with spaces'\n"
        "assert 'PySide6' not in sys.modules\n"
        "print(fpvs_studio.__version__)\n",
        "Unicode café with spaces",
    )
    assert Path(command[0]).is_file()
    assert not Path(command[0]).is_symlink()
    result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()
