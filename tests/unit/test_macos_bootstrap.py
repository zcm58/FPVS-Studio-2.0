"""Fresh-clone setup and IDE paths without modifying a user's Python or IDE settings."""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
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
