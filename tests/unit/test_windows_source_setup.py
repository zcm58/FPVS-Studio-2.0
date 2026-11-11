"""Check Windows setup's project and profile changes without opening PyCharm."""

from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest
from scripts.windows_pycharm import configure, find_profile

RUN_PATH = ".idea/runConfigurations/FPVS_Studio_Windows.xml"
TABLE_PATH = "options/jdk.table.xml"


def test_setup_registers_sdk_and_binds_main_in_a_fresh_checkout(tmp_path):
    checkout = tmp_path / "Studio & projects"
    python = checkout / ".venv3.10/Scripts/python.exe"
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
    assert options["SDK_HOME"] == "$PROJECT_DIR$/.venv3.10/Scripts/python.exe"
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
    python = checkout / ".venv3.10/Scripts/python.exe"
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
    assert tree.find(".//orderEntry").get("jdkName") == "Python 3.10 (FPVS Studio: checkout)"
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
