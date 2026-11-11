"""Fresh-clone setup and IDE paths without modifying a user's Python or IDE settings."""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "macos_pycharm_setup", ROOT / "scripts/macos_pycharm.py",
)
assert SPEC is not None and SPEC.loader is not None
pycharm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pycharm)


def _project(tmp_path):
    root = tmp_path / "Studio café & projects"
    main = root / "src/fpvs_studio/app/main.py"
    main.parent.mkdir(parents=True)
    main.write_text("# synthetic source\n")
    python = root / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.touch()
    return root, python


def _python_script(code):
    return ("#!/bin/sh\nexec " + shlex.quote(sys.executable) + " -c " + shlex.quote(code)
            + ' "$0" "$@"\n')


def test_pycharm_uses_venv_path_main_and_keeps_other_ide_settings(tmp_path):
    root, python = _project(tmp_path)
    settings = root / ".idea/misc.xml"
    settings.parent.mkdir()
    settings.write_bytes(b"user-owned IDE settings")
    target = pycharm.configure_pycharm(root, python)
    configuration = ET.parse(target).find("configuration")
    values = {element.get("name"): element.get("value")
              for element in configuration.findall("option")}
    assert values["SDK_HOME"] == str(python.absolute())
    assert values["IS_MODULE_SDK"] == "false"
    assert values["SCRIPT_NAME"] == "$PROJECT_DIR$/src/fpvs_studio/app/main.py"
    assert values["WORKING_DIRECTORY"] == "$PROJECT_DIR$"
    assert configuration.find("module").get("name") == root.name
    assert settings.read_bytes() == b"user-owned IDE settings"
    modified = target.stat().st_mtime_ns
    pycharm.configure_pycharm(root, python)
    assert target.stat().st_mtime_ns == modified


def test_pycharm_preserves_custom_file_instead_of_overwriting_it(tmp_path):
    root, python = _project(tmp_path)
    target = root / ".idea/runConfigurations/FPVS_Studio_Mac.xml"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"custom run configuration")
    with pytest.raises(ValueError, match="Preserving"):
        pycharm.configure_pycharm(root, python)
    assert target.read_bytes() == b"custom run configuration"


def test_pycharm_does_not_resolve_virtual_environment_symlink(tmp_path):
    root, python = _project(tmp_path)
    base = root / "base-python"
    base.touch()
    python.unlink()
    try:
        python.symlink_to(base)
    except OSError:
        pytest.skip("Native symlink creation needs Windows permission")
    target = pycharm.configure_pycharm(root, python)
    values = {item.get("name"): item.get("value") for item in ET.parse(target).iter("option")}
    assert values["SDK_HOME"] == str(python.absolute())
    assert values["SDK_HOME"] != str(base)


def test_missing_interpreter_does_not_create_ide_files(tmp_path):
    root, python = _project(tmp_path)
    python.unlink()
    with pytest.raises(ValueError, match="must exist"):
        pycharm.configure_pycharm(root, python)
    assert not (root / ".idea").exists()


def test_pycharm_does_not_follow_ide_directory_outside_checkout(tmp_path):
    root, python = _project(tmp_path)
    outside = tmp_path / "other IDE settings"
    outside.mkdir()
    try:
        (root / ".idea").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Native symlink creation needs Windows permission")
    with pytest.raises(ValueError, match="inside this checkout"):
        pycharm.configure_pycharm(root, python)
    assert not list(outside.iterdir())


def test_requirement_entrypoints_keep_versions_in_shared_metadata():
    for filename, expected in (
        ("requirements.txt", "-e .[dev,engine]"),
        ("requirements-macos.txt", "-e .[dev,engine]"),
    ):
        lines = [line.strip() for line in (ROOT / filename).read_text().splitlines()
                 if line.strip() and not line.lstrip().startswith("#")]
        assert lines == [expected]


def _ide_profile(tmp_path):
    app = tmp_path / "Applications/PyCharm.app"
    info = app / "Contents/Resources/product-info.json"
    info.parent.mkdir(parents=True)
    info.write_text(json.dumps({"dataDirectoryName": "PyCharm2026.1"}))
    config = tmp_path / "IDE settings"
    table = config / "PyCharm2026.1/options/jdk.table.xml"
    table.parent.mkdir(parents=True)
    return app, config, table


def test_sdk_registration_preserves_other_sdks_and_project_components(tmp_path):
    root, python = _project(tmp_path)
    app, config, table = _ide_profile(tmp_path)
    table.write_text('''<application><component name="OtherSettings" enabled="true" />
<component name="ProjectJdkTable"><jdk version="2"><name value="Toolbox Python" />
<homePath value="/some/other/project/python" /><type value="Python SDK" />
<additional custom="preserve" /></jdk></component></application>''')
    misc = root / ".idea/misc.xml"
    misc.parent.mkdir()
    misc.write_text('<project version="4"><component name="Custom" value="keep" /></project>')
    original = table.read_bytes()
    selected = pycharm.register_pycharm(root, python, str(app), config_home=config)
    assert selected == app
    entries = ET.parse(table).findall(".//jdk")
    assert len(entries) == 2
    assert entries[0].find("additional").get("custom") == "preserve"
    assert entries[0].find("homePath").get("value") == "/some/other/project/python"
    assert ET.parse(table).find("component[@name='OtherSettings']").get("enabled") == "true"
    assert entries[1].find("homePath").get("value") == str(python)
    project = ET.parse(misc)
    assert project.find("component[@name='Custom']").get("value") == "keep"
    assert (project.find("component[@name='ProjectRootManager']").get("project-jdk-name")
            == entries[1].find("name").get("value"))
    backups = list((root / ".fpvs-macos/pycharm-backups").glob("jdk.table.xml.*.bak"))
    assert len(backups) == 1 and backups[0].read_bytes() == original
    before = table.read_bytes()
    pycharm.register_pycharm(root, python, str(app), config_home=config)
    assert table.read_bytes() == before
    assert len(ET.parse(table).findall(".//jdk")) == 2


def test_sdk_registration_reuses_existing_sdk_without_changing_table(tmp_path):
    root, python = _project(tmp_path)
    app, config, table = _ide_profile(tmp_path)
    document = ET.Element("application")
    sdk = ET.SubElement(ET.SubElement(document, "component", name="ProjectJdkTable"), "jdk")
    ET.SubElement(sdk, "name", value="Existing studio environment")
    ET.SubElement(sdk, "homePath", value=str(python))
    ET.SubElement(sdk, "type", value="Python SDK")
    table.write_bytes(ET.tostring(document))
    original = table.read_bytes()
    pycharm.register_pycharm(root, python, str(app), config_home=config)
    assert table.read_bytes() == original
    assert (ET.parse(root / ".idea/misc.xml").find("component").get("project-jdk-name")
            == "Existing studio environment")


def test_launch_has_no_process_wide_interpreter_override(tmp_path, monkeypatch):
    root, python = _project(tmp_path)
    app, _config, _table = _ide_profile(tmp_path)
    monkeypatch.setattr(pycharm, "register_pycharm", lambda *_: app)
    monkeypatch.setenv("PYCHARM_PYTHON_PATH", "unrelated interpreter")
    calls = []

    def run(command, **options):
        calls.append((command, options))
        return subprocess.CompletedProcess(command, 1 if command[0] == "pgrep" else 0)

    monkeypatch.setattr(pycharm.subprocess, "run", run)
    pycharm.launch_pycharm(root, python, str(app))
    command, options = calls[-1]
    assert command == ["open", "-na", str(app), "--args", str(root)]
    assert "PYCHARM_PYTHON_PATH" not in options["env"]


@pytest.fixture
def repair_ide(tmp_path, monkeypatch):
    root, python = _project(tmp_path)
    app, config, _table = _ide_profile(tmp_path)
    ide = pycharm.RepairIDE(app, config / "PyCharm2026.1")
    monkeypatch.setattr(pycharm, "_discover_repair_ide", lambda: ide)
    monkeypatch.setattr(pycharm, "_target_python_version", lambda _python: "3.10.22")
    monkeypatch.setattr(pycharm, "_profile_is_closed", lambda _ide: True)
    return root, python, ide


def test_repair_configures_closed_ide_and_second_check_is_read_only(repair_ide, monkeypatch):
    root, python, ide = repair_ide
    assert pycharm.configure_for_repair(root, python) == "ready"
    assert pycharm._repair_settings_ready(root, python, ide)
    workspace = ET.parse(root / ".idea/workspace.xml")
    assert (workspace.find("component[@name='RunManager']").get("selected")
            == "Python.FPVS Studio (Mac)")
    files = [path for path in root.rglob("*") if path.is_file()]
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in files}
    monkeypatch.setattr(
        pycharm, "_apply_repair_settings", lambda *args: pytest.fail("unexpected write"),
    )
    assert pycharm.configure_for_repair(root, python, check_only=True) == "ready"
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in files}


def test_check_only_mismatch_does_not_create_ide_or_job_files(repair_ide):
    root, python, _ide = repair_ide
    with pytest.raises(ValueError, match="without --check"):
        pycharm.configure_for_repair(root, python, check_only=True)
    assert not (root / ".idea").exists()
    assert not (root / ".fpvs-macos").exists()


def _configuration(parent, name, script, *, module=False):
    config = ET.SubElement(parent, "configuration", name=name, type="PythonConfigurationType")
    for key, value in {
        "SCRIPT_NAME": script, "MODULE_MODE": str(module).lower(),
        "SDK_HOME": "/wrong/python", "SDK_NAME": "old", "IS_MODULE_SDK": "false",
        "PARAMETERS": "--participant keep", "WORKING_DIRECTORY": "$PROJECT_DIR$",
    }.items():
        ET.SubElement(config, "option", name=key, value=value)
    return config


@pytest.mark.parametrize("helper_path", [
    "$PROJECT_DIR$/macos_repair_environment.py",
    "$PROJECT_DIR$/scripts/macos_repair_environment.py",
])
def test_repair_updates_only_studio_and_helper_runs_and_preserves_other_settings(
    repair_ide, helper_path,
):
    root, python, _ide = repair_ide
    workspace = root / ".idea/workspace.xml"
    workspace.parent.mkdir()
    tree = ET.Element("project", version="4")
    ET.SubElement(tree, "component", name="Keep", value="custom")
    manager = ET.SubElement(tree, "component", name="RunManager", selected="Python.old")
    _configuration(manager, "Studio module", "fpvs_studio.app", module=True)
    _configuration(manager, "Helper", helper_path)
    _configuration(manager, "Other", "$PROJECT_DIR$/unrelated.py")
    workspace.write_bytes(ET.tostring(tree))
    directory = root / ".idea/runConfigurations"
    directory.mkdir()
    custom = ET.Element("component", name="ProjectRunConfigurationManager")
    _configuration(custom, "Custom Studio", "$PROJECT_DIR$/src/fpvs_studio/app/main.py")
    (directory / "custom.xml").write_bytes(ET.tostring(custom))
    unrelated = directory / "unrelated.xml"
    unrelated.write_bytes(b'<component name="ProjectRunConfigurationManager">\n</component>')
    untouched = unrelated.read_bytes()
    assert pycharm.configure_for_repair(root, python) == "ready"
    saved = ET.parse(workspace)
    assert saved.find("component[@name='Keep']").get("value") == "custom"
    for config in saved.findall("component[@name='RunManager']/configuration"):
        values = pycharm._options(config)
        assert values["PARAMETERS"] == "--participant keep"
        expected = "/wrong/python" if config.get("name") == "Other" else str(python)
        assert values["SDK_HOME"] == expected
        if config.get("name") == "Helper":
            assert values["SCRIPT_NAME"] == "$PROJECT_DIR$/macos_repair_environment.py"
    custom_values = pycharm._options(ET.parse(directory / "custom.xml").find("configuration"))
    assert custom_values["SDK_HOME"] == str(python)
    assert custom_values["PARAMETERS"] == "--participant keep"
    assert unrelated.read_bytes() == untouched


@pytest.mark.parametrize("location", ["workspace.xml", "runConfigurations/Repair.xml"])
def test_old_helper_path_requires_repair_even_when_its_interpreter_is_correct(repair_ide, location):
    root, python, ide = repair_ide
    assert pycharm.configure_for_repair(root, python) == "ready"
    target = root / ".idea" / location
    tree = ET.parse(target).getroot() if target.exists() else ET.Element("component")
    parent = tree.find("component[@name='RunManager']") if location == "workspace.xml" else tree
    config = _configuration(parent, "Repair", "$PROJECT_DIR$/scripts/macos_repair_environment.py")
    table = ET.parse(ide.config_dir / "options/jdk.table.xml").getroot()
    sdk = pycharm._sdk_name(table, python)
    pycharm._set_option(config, "SDK_HOME", str(python.absolute()))
    pycharm._set_option(config, "SDK_NAME", sdk)
    target.write_bytes(ET.tostring(tree))
    original = target.read_bytes()
    with pytest.raises(ValueError, match="without --check"):
        pycharm.configure_for_repair(root, python, check_only=True)
    assert target.read_bytes() == original
    assert pycharm.configure_for_repair(root, python) == "ready"
    saved = ET.parse(target).find(".//configuration[@name='Repair']")
    assert pycharm._options(saved)["SCRIPT_NAME"] == "$PROJECT_DIR$/macos_repair_environment.py"
    assert pycharm._options(saved)["PARAMETERS"] == "--participant keep"


def test_repair_preserves_unrecognized_generated_configuration(repair_ide):
    root, python, ide = repair_ide
    target = root / ".idea/runConfigurations/FPVS_Studio_Mac.xml"
    target.parent.mkdir(parents=True)
    tree = ET.Element("component")
    _configuration(tree, "Other", "$PROJECT_DIR$/unrelated.py")
    original = ET.tostring(tree)
    target.write_bytes(original)
    with pytest.raises(ValueError, match="custom FPVS_Studio_Mac"):
        pycharm.configure_for_repair(root, python)
    assert target.read_bytes() == original
    assert not (ide.config_dir / "options/jdk.table.xml").exists()


def test_reused_sdk_version_is_refreshed_after_venv_rebuild(repair_ide):
    root, python, ide = repair_ide
    table = ide.config_dir / "options/jdk.table.xml"
    document = ET.Element("application")
    sdk = ET.SubElement(ET.SubElement(document, "component", name="ProjectJdkTable"), "jdk")
    for tag, value in (("name", "Existing SDK"), ("homePath", str(python)),
                       ("type", "Python SDK"), ("version", "Python 3.11.9")):
        ET.SubElement(sdk, tag, value=value)
    ET.SubElement(sdk, "additional", SDK_UUID="preserve-identity")
    table.write_bytes(ET.tostring(document))
    pycharm.register_pycharm(
        root, python, str(ide.app), config_dir=ide.config_dir, python_version="3.10.22",
    )
    saved = ET.parse(table).find(".//jdk")
    assert saved.find("name").get("value") == "Existing SDK"
    assert saved.find("additional").get("SDK_UUID") == "preserve-identity"
    assert saved.find("version").get("value") == "Python 3.10.22"
    assert len(list((root / ".fpvs-macos/pycharm-backups").glob("jdk.table.xml.*.bak"))) == 1


def test_active_ide_repair_is_detached_and_repeated_runs_reuse_job(repair_ide, monkeypatch):
    root, python, ide = repair_ide
    ide.pids = (123,)
    calls = []
    monkeypatch.setattr(
        pycharm.subprocess, "Popen", lambda command, **kwargs: calls.append((command, kwargs)),
    )
    assert pycharm.configure_for_repair(root, python, parent_pid=777) == "pending"
    assert pycharm.configure_for_repair(root, python, parent_pid=888) == "pending"
    assert len(calls) == 1
    command, options = calls[0]
    assert command[:2] == [str(python), "-I"]
    assert options["start_new_session"] is True and options["stdin"] == subprocess.DEVNULL
    assert options["cwd"] == root and options["stderr"] == subprocess.STDOUT
    job = Path(command[command.index("--finish-repair") + 1])
    assert json.loads(job.read_text())["parent_pid"] == 777
    assert not (root / ".idea").exists()


@pytest.mark.parametrize("prefix,version", [("different", "3.10"), (None, "3.11")])
def test_wrong_live_interpreter_requires_restart_even_with_correct_xml(
    repair_ide, monkeypatch, prefix, version,
):
    root, python, ide = repair_ide
    assert pycharm.configure_for_repair(root, python) == "ready"
    ide.pids = (123,)
    launch_prefix = str(root / prefix) if prefix else str(python.parent.parent)
    with pytest.raises(ValueError, match="without --check"):
        pycharm.configure_for_repair(
            root, python, check_only=True, launch_prefix=launch_prefix, launch_version=version,
        )
    calls = []
    monkeypatch.setattr(pycharm.subprocess, "Popen", lambda *args, **kwargs: calls.append(args))
    assert pycharm.configure_for_repair(
        root, python, launch_prefix=launch_prefix, launch_version=version,
    ) == "pending"
    assert len(calls) == 1


def test_live_correct_interpreter_and_settings_do_not_restart(repair_ide, monkeypatch):
    root, python, ide = repair_ide
    pycharm.configure_for_repair(root, python)
    ide.pids = (123,)
    monkeypatch.setattr(
        pycharm.subprocess, "Popen", lambda *a, **k: pytest.fail("unexpected restart"),
    )
    assert pycharm.configure_for_repair(
        root, python, launch_prefix=str(python.parent.parent), launch_version="3.10",
    ) == "ready"


def test_stale_sdk_version_alone_requires_repair(repair_ide):
    root, python, ide = repair_ide
    pycharm.configure_for_repair(root, python)
    table = ide.config_dir / "options/jdk.table.xml"
    tree = ET.parse(table)
    tree.find(".//jdk/version").set("value", "Python 3.11.9")
    tree.write(table)
    assert not pycharm._repair_settings_ready(root, python, ide)
    assert pycharm.configure_for_repair(root, python) == "ready"
    assert ET.parse(table).find(".//jdk/version").get("value") == "Python 3.10.22"


def test_expired_lease_reuses_worker_that_is_still_finishing(repair_ide, monkeypatch):
    root, _python, ide = repair_ide
    job = _pending_job(root, ide)
    job.with_suffix(".claim").write_text("555")
    lock = pycharm._job_lock(root, ide)
    payload = json.loads(lock.read_text())
    payload["expires"] = time.time() - 1
    lock.write_text(json.dumps(payload))
    monkeypatch.setattr(pycharm, "_pid_alive", lambda pid: pid == 555)
    reused, created = pycharm._reserve_job(root, ide, 888)
    assert reused == job and not created


def test_failed_background_launch_releases_pending_lock(repair_ide, monkeypatch):
    root, python, ide = repair_ide
    ide.pids = (123,)
    def fail(*args, **kwargs):
        raise OSError("synthetic launch failure")
    monkeypatch.setattr(pycharm.subprocess, "Popen", fail)
    with pytest.raises(OSError, match="launch failure"):
        pycharm.configure_for_repair(root, python)
    assert not pycharm._job_lock(root, ide).exists()


def _pending_job(root, ide):
    ide.pids = (123,)
    path, created = pycharm._reserve_job(root, ide, 777)
    assert created
    return path


def test_finalizer_waits_for_quit_then_configures_reopens_and_reports(repair_ide, monkeypatch):
    root, python, ide = repair_ide
    job = _pending_job(root, ide)
    actions = []
    monkeypatch.setattr(pycharm, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(pycharm, "_normal_quit", lambda pid, app: actions.append("quit"))
    original = pycharm._apply_repair_settings
    def apply(*args):
        actions.append("configure")
        original(*args)
    monkeypatch.setattr(pycharm, "_apply_repair_settings", apply)
    monkeypatch.setattr(pycharm, "_reopen_pycharm", lambda *args: actions.append("reopen"))
    monkeypatch.setattr(pycharm, "_show_repair_result", lambda message: actions.append("report"))
    assert pycharm._finish_repair(root, python, job, job.stem) == 0
    assert actions == ["quit", "configure", "reopen", "report"]
    assert json.loads(job.with_suffix(".result.json").read_text())["success"] is True
    assert not pycharm._job_lock(root, ide).exists()


def test_canceled_quit_times_out_without_ide_writes(repair_ide, monkeypatch):
    root, python, ide = repair_ide
    job = _pending_job(root, ide)
    clock = [time.time()]
    monkeypatch.setattr(pycharm.time, "time", lambda: clock[0])
    monkeypatch.setattr(pycharm.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + 301))
    monkeypatch.setattr(pycharm, "_pid_alive", lambda pid: pid == 123)
    monkeypatch.setattr(pycharm, "_normal_quit", lambda *args: None)
    monkeypatch.setattr(pycharm, "_show_repair_result", lambda message: None)
    monkeypatch.setattr(
        pycharm, "_apply_repair_settings", lambda *args: pytest.fail("unexpected write"),
    )
    assert pycharm._finish_repair(root, python, job, job.stem) == 1
    assert json.loads(job.with_suffix(".result.json").read_text())["success"] is False
    assert not (root / ".idea").exists()


@pytest.mark.parametrize("failure", ["result-write", "lock-release"])
def test_finalizer_reporting_failure_still_notifies_user(repair_ide, monkeypatch, failure):
    root, python, ide = repair_ide
    job = _pending_job(root, ide)
    notifications = []
    monkeypatch.setattr(pycharm, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(pycharm, "_normal_quit", lambda *args: None)
    monkeypatch.setattr(pycharm, "_apply_repair_settings", lambda *args: None)
    monkeypatch.setattr(pycharm, "_reopen_pycharm", lambda *args: None)
    monkeypatch.setattr(pycharm, "_show_repair_result", notifications.append)
    if failure == "result-write":
        original = pycharm.os.open
        def cannot_save(path, *args, **kwargs):
            if Path(path) == job.with_suffix(".result.json"):
                raise OSError("synthetic result write failure")
            return original(path, *args, **kwargs)
        monkeypatch.setattr(pycharm.os, "open", cannot_save)
    else:
        def cannot_release(*args):
            raise OSError("synthetic lock release failure")
        monkeypatch.setattr(pycharm, "_release_job_lock", cannot_release)
    assert pycharm._finish_repair(root, python, job, job.stem) == 1
    assert len(notifications) == 1
    assert "repair did not finish" in notifications[0]
    assert str(job.with_suffix(".log")) in notifications[0]


@pytest.mark.parametrize("invalid", ["outside", "token", "existing-result"])
def test_invalid_finalizer_request_never_writes_a_result_or_ide_settings(
    repair_ide, monkeypatch, tmp_path, invalid,
):
    root, python, ide = repair_ide
    job = _pending_job(root, ide)
    token = job.stem
    if invalid == "outside":
        outside = tmp_path / "outside.json"
        outside.write_bytes(job.read_bytes())
        job = outside
    elif invalid == "token":
        token = "invalid"
    result = job.with_suffix(".result.json")
    if invalid == "existing-result":
        result.write_bytes(b"preserve")
    monkeypatch.setattr(pycharm, "_show_repair_result", lambda message: None)
    monkeypatch.setattr(pycharm, "_normal_quit", lambda *args: pytest.fail("unexpected quit"))
    assert pycharm._finish_repair(root, python, job, token) == 1
    if invalid == "existing-result":
        assert result.read_bytes() == b"preserve"
    else:
        assert not result.exists()
    assert not (root / ".idea").exists()


def test_xml_change_between_read_and_save_is_preserved(tmp_path):
    path = tmp_path / "settings.xml"
    before = b"<project />"
    path.write_bytes(b'<project changed="elsewhere" />')
    with pytest.raises(ValueError, match="changed during repair"):
        pycharm._save_xml(path, ET.Element("project"), tmp_path / "backups", expected_before=before)
    assert path.read_bytes() == b'<project changed="elsewhere" />'
    assert not (tmp_path / "backups").exists()


def test_active_profile_discovery_reads_real_jvm_directory(tmp_path, monkeypatch):
    app, _config, _table = _ide_profile(tmp_path)
    jcmd = app / "Contents/jbr/Contents/Home/bin/jcmd"
    jcmd.parent.mkdir(parents=True)
    jcmd.touch()
    custom = tmp_path / "custom profile"
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command, 0, f"idea.config.path={custom.as_posix()}\n", "",
        )
    monkeypatch.setattr(pycharm.subprocess, "run", run)
    assert pycharm._active_config_dir(app, 123) == custom
    assert calls == [[str(jcmd), "123", "VM.system_properties"]]


def test_missing_jcmd_does_not_guess_running_profile(tmp_path):
    app, _config, _table = _ide_profile(tmp_path)
    with pytest.raises(ValueError, match="diagnostic tool"):
        pycharm._active_config_dir(app, 123)


def test_discovery_selects_owning_pycharm_ancestor_and_custom_profile(tmp_path, monkeypatch):
    app, _config, _table = _ide_profile(tmp_path)
    profile = tmp_path / "actual custom profile"
    monkeypatch.setattr(pycharm, "_running_pycharm_pids", lambda: (222, 444))
    monkeypatch.setattr(pycharm, "_app_for_pid", lambda pid: app)
    monkeypatch.setattr(
        pycharm, "_active_config_dir",
        lambda selected, pid: profile if pid == 222 else tmp_path / "other",
    )
    monkeypatch.setattr(pycharm.os, "getppid", lambda: 111)
    monkeypatch.setattr(pycharm, "_process_value", lambda pid, field: "222" if pid == 111 else "1")
    ide = pycharm._discover_repair_ide()
    assert ide.app == app and ide.config_dir == profile and ide.pids == (222,)


def test_native_quit_does_not_target_reused_pid_for_another_app(monkeypatch, tmp_path):
    application = SimpleNamespace(
        bundleURL=lambda: SimpleNamespace(path=lambda: str(tmp_path / "Other.app")),
    )
    native = SimpleNamespace(NSRunningApplication=SimpleNamespace(
        runningApplicationWithProcessIdentifier_=lambda pid: application,
    ))
    monkeypatch.setattr(pycharm, "import_module", lambda name: native)
    with pytest.raises(ValueError, match="process changed"):
        pycharm._normal_quit(123, tmp_path / "PyCharm.app")


def test_native_quit_uses_normal_pid_specific_api_only(monkeypatch, tmp_path):
    app = tmp_path / "PyCharm.app"
    calls = []
    application = SimpleNamespace(
        bundleURL=lambda: SimpleNamespace(path=lambda: str(app)),
        terminate=lambda: calls.append("normal quit") or True,
    )
    native = SimpleNamespace(NSRunningApplication=SimpleNamespace(
        runningApplicationWithProcessIdentifier_=lambda pid: application if pid == 123 else None,
    ))
    monkeypatch.setattr(pycharm, "import_module", lambda name: native)
    pycharm._normal_quit(123, app)
    assert calls == ["normal quit"]


@pytest.mark.parametrize("state,code", [("ready", 0), ("pending", 10)])
def test_repair_cli_passes_original_launch_context(monkeypatch, tmp_path, state, code):
    root, python = tmp_path, tmp_path / ".venv/bin/python"
    calls = []
    monkeypatch.setattr(
        pycharm, "configure_for_repair", lambda *a, **k: calls.append((a, k)) or state,
    )
    monkeypatch.setattr(sys, "argv", [
        "macos_pycharm.py", str(root), str(python), "--repair", "--repair-parent-pid", "777",
        "--repair-launch-prefix", "/old/venv", "--repair-launch-version", "3.11",
    ])
    with pytest.raises(SystemExit) as result:
        pycharm.main()
    assert result.value.code == code
    assert calls == [((root, python), {
        "check_only": False, "parent_pid": 777,
        "launch_prefix": "/old/venv", "launch_version": "3.11",
    })]


@pytest.fixture
def shell_project(tmp_path):
    if os.name != "posix" or shutil.which("bash") is None:
        pytest.skip("Native POSIX shell adapter")
    root, _python = _project(tmp_path)
    shutil.rmtree(root / ".venv")
    (root / "scripts").mkdir()
    for name in ("macos-source.sh", "macos_pycharm.py"):
        shutil.copyfile(ROOT / "scripts" / name, root / "scripts" / name)
    shutil.copyfile(ROOT / "requirements-macos.txt", root / "requirements-macos.txt")
    tools = root / "fake tools"
    tools.mkdir()
    log = root / "commands.jsonl"
    env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"],
               FPVS_TEST_LOG=str(log))
    for name in ("FPVS_PYTHON", "FPVS_MANAGED_PYTHON", "OPENSSL_DIR", "VIRTUAL_ENV"):
        env.pop(name, None)

    def executable(name, script):
        target = tools / name
        target.write_text(script, encoding="utf-8")
        target.chmod(0o700)
        return target

    executable("uname", '#!/bin/sh\ncase "$1" in -s) echo Darwin;; -m) echo arm64;; esac\n')
    executable("sysctl", "#!/bin/sh\necho 0\n")
    executable("pgrep", "#!/bin/sh\nexit 1\n")
    python = executable("test-python", _python_script("""
import json, os, pathlib, shutil, sys
args = sys.argv[2:]
with open(os.environ['FPVS_TEST_LOG'], 'a') as log:
    log.write(json.dumps(args) + '\\n')
if args[:2] == ['-m', 'venv']:
    target = pathlib.Path(args[2]) / 'bin/python'
    target.parent.mkdir(parents=True)
    shutil.copyfile(sys.argv[1], target)
    target.chmod(0o700)
if args[:3] == ['-m', 'pip', 'install'] and os.environ.get('FPVS_TEST_PIP_FAIL'):
    sys.exit(9)
"""))
    return root, tools, log, env, executable, python


def _setup(root, env, *arguments):
    return subprocess.run(
        [shutil.which("bash"), str(root / "scripts/macos-source.sh"), *arguments],
        cwd=root.parent, env=env, capture_output=True, text=True, timeout=30, check=False,
    )


def test_fresh_setup_creates_venv_installs_complete_requirements_and_checks(shell_project):
    root, _tools, log, env, _executable, python = shell_project
    env["FPVS_PYTHON"] = str(python)
    result = _setup(root, env, "setup")
    assert result.returncode == 0, result.stdout + result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert ["-m", "venv", str(root / ".venv3.10")] in calls
    assert ["-m", "pip", "install", "--requirement", "requirements-macos.txt"] in calls
    assert ["-m", "pip", "check"] in calls
    assert any(call[0] == "scripts/macos_pycharm.py" for call in calls)
    assert "Setup complete" in result.stdout


def test_repair_setup_skips_ide_writes_until_finalization(shell_project):
    root, _tools, log, env, _executable, python = shell_project
    env.update(FPVS_PYTHON=str(python), FPVS_SKIP_PYCHARM_CONFIG="1")
    result = _setup(root, env, "setup")
    assert result.returncode == 0, result.stdout + result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert ["-m", "pip", "install", "--requirement", "requirements-macos.txt"] in calls
    assert ["-m", "pip", "check"] in calls
    assert not any(call[0] == "scripts/macos_pycharm.py" for call in calls)


def test_install_failure_keeps_environment_and_never_reports_success(shell_project):
    root, _tools, _log, env, _executable, python = shell_project
    env.update(FPVS_PYTHON=str(python), FPVS_TEST_PIP_FAIL="1")
    result = _setup(root, env, "setup")
    assert result.returncode == 9
    assert "Setup did not finish" in result.stdout
    assert "Setup complete" not in result.stdout
    assert (root / ".venv3.10/bin/python").is_file()
    assert (root / ".fpvs-macos/setup.log").is_file()


def test_incomplete_environment_is_preserved_with_clear_recovery(shell_project):
    root, _tools, _log, env, _executable, _python = shell_project
    marker = root / ".venv3.10/user-marker"
    marker.parent.mkdir()
    marker.write_text("keep")
    result = _setup(root, env, "setup")
    assert result.returncode == 2
    assert "incomplete" in result.stdout
    assert marker.read_text() == "keep"


def test_managed_download_checksum_failure_never_executes_payload(shell_project):
    root, _tools, log, env, executable, _python = shell_project
    executable("curl", '#!/bin/sh\nwhile [ "$1" != --output ]; do shift; done\n'
               'echo invalid > "$2"\n')
    env["FPVS_MANAGED_PYTHON"] = "1"
    result = _setup(root, env, "setup")
    assert result.returncode == 1
    assert "checksum failed" in result.stdout
    assert not log.exists()
    assert not (root / ".venv3.10").exists()


def test_pycharm_launcher_dispatches_scoped_setup_with_exact_interpreter(shell_project):
    root, _tools, log, env, _executable, python = shell_project
    env["FPVS_PYTHON"] = str(python)
    assert _setup(root, env, "setup").returncode == 0
    result = _setup(root, env, "pycharm")
    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert ["scripts/macos_pycharm.py", str(root), str(root / ".venv3.10/bin/python"),
            "--launch", "PyCharm.app"] in calls


def test_managed_python_is_project_local_and_does_not_install_path_links(shell_project):
    root, _tools, log, env, executable, python = shell_project
    uv = root / ".fpvs-macos/uv-0.13.7/uv"
    uv.parent.mkdir(parents=True)
    stub = executable("managed-uv", _python_script(f"""
import json, os, sys
with open(os.environ['FPVS_TEST_LOG'], 'a') as log:
    log.write(json.dumps(['uv', *sys.argv[2:]]) + '\\n')
assert os.environ['UV_PYTHON_INSTALL_DIR'] == {str(root / '.fpvs-macos/python')!r}
if sys.argv[2:4] == ['python', 'find']:
    print({str(python)!r})
"""))
    shutil.copyfile(stub, uv)
    uv.chmod(0o700)
    env["FPVS_MANAGED_PYTHON"] = "1"
    result = _setup(root, env, "setup")
    assert result.returncode == 0, result.stdout + result.stderr
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert ["uv", "python", "install", "--no-bin", "3.10"] in calls
    assert ["-m", "venv", str(root / ".venv3.10")] in calls


def test_running_pycharm_is_not_reconfigured_or_quit_by_the_launcher(shell_project):
    root, _tools, _log, env, executable, python = shell_project
    env["FPVS_PYTHON"] = str(python)
    assert _setup(root, env, "setup").returncode == 0
    executable("pgrep", "#!/bin/sh\nexit 0\n")
    result = _setup(root, env, "pycharm")
    assert result.returncode == 2
    assert "fully quit PyCharm (Command-Q)" in result.stderr


def test_intel_missing_apple_tools_requests_installer_and_explains_rerun(shell_project):
    root, _tools, log, env, executable, python = shell_project
    executable("uname", '#!/bin/sh\ncase "$1" in -s) echo Darwin;; -m) echo x86_64;; esac\n')
    marker = root / "apple-installer-requested"
    executable("xcode-select", _python_script(f"""
import pathlib, sys
if sys.argv[2:] == ['-p']: sys.exit(1)
assert sys.argv[2:] == ['--install']
pathlib.Path({str(marker)!r}).touch()
"""))
    env["FPVS_PYTHON"] = str(python)
    result = _setup(root, env, "setup")
    assert result.returncode == 2
    assert marker.exists()
    assert "Complete Apple's Command Line Tools installer" in result.stdout
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert not any(call[:3] == ["-m", "pip", "install"] for call in calls)


@pytest.mark.parametrize("filename,command", [
    ("Setup Mac.command", "setup"), ("Run Mac.command", "run"),
    ("Open in PyCharm Mac.command", "pycharm"),
])
def test_finder_shortcuts_find_checkout_from_another_directory(shell_project, filename, command):
    root, _tools, _log, env, _executable, _python = shell_project
    script = root / "scripts/macos-source.sh"
    script.write_text('printf "%s\\n" "$PWD" "$@"\n', encoding="utf-8")
    shortcut = root / filename
    shutil.copyfile(ROOT / filename, shortcut)
    result = subprocess.run([shutil.which("bash"), str(shortcut)], cwd=root.parent,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True,
                            env=env, timeout=10, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [str(root), command]
