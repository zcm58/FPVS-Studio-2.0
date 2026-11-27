"""Check Windows setup's project and profile changes without opening PyCharm."""

from __future__ import annotations

import shutil
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from scripts.windows_pycharm import configure, find_profile

RUN_PATH = ".idea/runConfigurations/FPVS_Studio_Windows.xml"
TABLE_PATH = "options/jdk.table.xml"


@pytest.mark.skipif(sys.platform != "win32", reason="Starts the Windows source bootstrap")
@pytest.mark.parametrize("venv_name", [".venv3.11", ".venv"])
def test_bootstrap_uses_existing_project_venv_for_install_and_checks(tmp_path, venv_name):
    checkout = tmp_path / "Studio checkout"
    scripts = checkout / "scripts"
    scripts.mkdir(parents=True)
    source_scripts = Path(__file__).resolve().parents[2] / "scripts"
    shutil.copyfile(source_scripts / "setup_windows.ps1", scripts / "setup_windows.ps1")
    shutil.copyfile(source_scripts / "script_helpers.ps1", scripts / "script_helpers.ps1")
    # Run the real setup selection and working-directory logic. Stand in for
    # installation and IDE writes to keep this test independent of the network.
    with (scripts / "script_helpers.ps1").open("a", encoding="utf-8") as helpers:
        helpers.write("""
function Invoke-WebRequest { throw 'Setup attempted a download despite a compatible venv.' }
function Invoke-NativeChecked {
    param([string]$File, [string[]]$Arguments)
    if ($File -ne [IO.Path]::GetFullPath((Join-Path $PWD 'VENV_NAME/Scripts/python.exe'))) {
        throw "Unexpected interpreter: $File"
    }
    Add-Content -LiteralPath 'setup-calls.txt' -Value ($Arguments -join ' ')
}
""".replace("VENV_NAME", venv_name))
    app = checkout / "src/fpvs_studio/app"
    app.mkdir(parents=True)
    (app / "main.py").touch()
    (checkout / "requirements.txt").touch()
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(checkout / venv_name)], check=True,
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
         str(scripts / "setup_windows.ps1")],
        capture_output=True, text=True, timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    commands = (checkout / "setup-calls.txt").read_text().splitlines()
    requirements = checkout / "requirements.txt"
    assert f"-I -m pip --require-virtualenv install --requirement {requirements}" in commands
    assert "-I -m pip check" in commands


@pytest.mark.skipif(find_spec("psychopy") is None, reason="Requires the optional engine")
def test_installed_engine_supplies_moviepy_api_used_by_psychopy():
    import numpy as np
    from moviepy import ImageSequenceClip, VideoFileClip

    assert callable(VideoFileClip)
    frame = np.full((4, 6, 3), (12, 34, 56), dtype=np.uint8)
    with ImageSequenceClip([frame], fps=1) as clip:
        small = clip.resized(new_size=(3, 2)).get_frame(0)
    np.testing.assert_array_equal(small, frame[::2, ::2])


def test_setup_registers_sdk_and_binds_main_in_a_fresh_checkout(tmp_path):
    checkout = tmp_path / "Studio & projects"
    python = checkout / ".venv3.11/Scripts/python.exe"
    profile = tmp_path / "PyCharm2026.3"

    configure(checkout, python, profile)

    sdk = ET.parse(profile / TABLE_PATH).find(".//jdk")
    assert sdk.find("homePath").get("value") == python.as_posix()
    name = sdk.find("name").get("value")
    project_sdk = ET.parse(checkout / ".idea/misc.xml").find(".//component")
    assert project_sdk.get("project-jdk-name") == name
    run = ET.parse(checkout / RUN_PATH).find("configuration")
    options = {option.get("name"): option.get("value") for option in run.findall("option")}
    assert options["SDK_NAME"] == name
    assert options["SDK_HOME"] == "$PROJECT_DIR$/.venv3.11/Scripts/python.exe"
    assert options["SCRIPT_NAME"] == "$PROJECT_DIR$/src/fpvs_studio/app/main.py"
    assert options["WORKING_DIRECTORY"] == "$PROJECT_DIR$"
    assert run.find("module").get("name") == "fpvs-studio"

    files = [*checkout.rglob("*.xml"), *checkout.rglob("*.iml"), profile / TABLE_PATH]
    snapshots = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in files}
    configure(checkout, python, profile)
    assert all((path.read_bytes(), path.stat().st_mtime_ns) == value
               for path, value in snapshots.items())
    assert not list(checkout.rglob("*.bak"))


def test_setup_updates_an_explicit_old_module_sdk_and_preserves_other_settings(tmp_path):
    checkout = tmp_path / "checkout"
    python = checkout / ".venv3.11/Scripts/python.exe"
    profile = tmp_path / "PyCharm2026.3"
    configure(checkout, python, profile)
    module = checkout / ".idea/fpvs-studio.iml"
    module.write_text(
        '<module><component name="NewModuleRootManager">'
        '<orderEntry type="jdk" jdkType="Python SDK" jdkName="Python 3.14" />'
        '</component><component name="CustomSettings" /></module>', encoding="utf-8",
    )
    prior_module = module.read_bytes()
    table = profile / TABLE_PATH
    old_sdk = '<jdk><name value="Python 3.14"/><type value="Python SDK"/></jdk>'
    table.write_text(table.read_text(encoding="utf-8").replace("</component>",
                                                              f"{old_sdk}</component>"),
                     encoding="utf-8")
    prior_table = table.read_bytes()

    configure(checkout, python, profile)

    tree = ET.parse(module)
    assert tree.find(".//orderEntry").get("jdkName") == "Python 3.11 (FPVS Studio: checkout)"
    assert tree.find("component[@name='CustomSettings']") is not None
    assert table.read_bytes() == prior_table
    backup = next((checkout / ".idea/fpvs-setup-backups").glob("fpvs-studio.iml.*.bak"))
    assert backup.read_bytes() == prior_module


def test_setup_can_prepare_run_before_installing_pycharm(tmp_path):
    python = tmp_path / ".venv/Scripts/python.exe"
    configure(tmp_path, python, None)
    assert (tmp_path / RUN_PATH).is_file()
    assert not (tmp_path / ".idea/misc.xml").exists()


def test_setup_preserves_a_custom_run_configuration(tmp_path):
    path = tmp_path / RUN_PATH
    path.parent.mkdir(parents=True)
    custom = b'<component><configuration name="Custom workflow" /></component>'
    path.write_bytes(custom)
    profile = tmp_path / "PyCharm2026.3"
    with pytest.raises(ValueError, match="custom run configuration"):
        configure(tmp_path, tmp_path / ".venv/Scripts/python.exe", profile)
    assert path.read_bytes() == custom
    assert not profile.exists()


def test_profile_discovery_prefers_installed_pycharm_before_first_run(tmp_path, monkeypatch):
    roaming = tmp_path / "Roaming"
    local = tmp_path / "Local"
    install = local / "Programs/PyCharm"
    install.mkdir(parents=True)
    (install / "product-info.json").write_text('{"dataDirectoryName": "PyCharm2026.3"}')
    (roaming / "JetBrains/PyCharm2026.2").mkdir(parents=True)
    monkeypatch.delenv("FPVS_PYCHARM_CONFIG", raising=False)
    monkeypatch.delenv("ProgramFiles", raising=False)
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    assert find_profile() == roaming / "JetBrains/PyCharm2026.3"
