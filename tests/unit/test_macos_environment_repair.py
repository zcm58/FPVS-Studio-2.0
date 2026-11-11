"""One-click Mac repair selects the checkout environment instead of its launching Python."""

from __future__ import annotations

import builtins
import importlib.metadata
import importlib.util
import json
import logging
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from packaging import markers

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "macos_environment_repair", ROOT / "Repair Mac.py",
)
assert SPEC is not None and SPEC.loader is not None
repair = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repair)


@pytest.fixture(autouse=True)
def no_native_processes(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Tests must replace every native subprocess.")

    monkeypatch.setattr(repair.subprocess, "run", unexpected)
    monkeypatch.setattr(repair, "_offer_report", lambda *args: None, raising=False)
    monkeypatch.setattr(repair.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(repair.platform, "release", lambda: "25.0.0")
    monkeypatch.setattr(repair.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(repair.platform, "mac_ver", lambda: ("26.0", (), "arm64"))


def _checkout(tmp_path: Path, environment: str = ".venv3.10") -> tuple[Path, Path]:
    root = tmp_path / "Studio café & projects"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "fpvs-studio"\n')
    (root / "requirements-macos.txt").write_text("-e .[dev,engine]\n")
    for relative in (
        "src/fpvs_studio/app/main.py", "scripts/macos-source.sh", "scripts/macos_pycharm.py",
    ):
        source = root / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("# synthetic Studio checkout\n")
    python = root / environment / "bin/python"
    python.parent.mkdir(parents=True)
    python.touch()
    (python.parent.parent / "pyvenv.cfg").write_text("home = /base/python\n")
    return root, python


@pytest.fixture
def mac_checkout(monkeypatch, tmp_path):
    root, python = _checkout(tmp_path)
    launcher = SimpleNamespace(**vars(sys))
    launcher.platform = "darwin"
    launcher.executable = str(tmp_path / "unrelated Python/bin/python")
    launcher.version_info = (3, 12, 2)
    launcher.prefix = launcher.base_prefix = str(tmp_path / "unrelated Python")
    monkeypatch.setattr(repair, "sys", launcher)
    monkeypatch.setattr(repair, "_native_architecture", lambda: "arm64")
    return root, python, launcher


@pytest.mark.parametrize("preferred_exists,fallback_exists,expected", [
    (False, False, ".venv3.10"), (True, False, ".venv3.10"),
    (False, True, ".venv"), (True, True, ".venv3.10"),
])
def test_environment_selection_matches_mac_setup(
    tmp_path, preferred_exists, fallback_exists, expected,
):
    if preferred_exists:
        (tmp_path / ".venv3.10").mkdir()
    if fallback_exists:
        (tmp_path / ".venv").mkdir()
    assert repair.expected_environment(tmp_path) == tmp_path / expected


@pytest.mark.parametrize("environment", [".venv3.10", ".venv"])
def test_broken_environment_symlink_does_not_select_another_environment(
    monkeypatch, tmp_path, environment,
):
    target = tmp_path / environment
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == target or original(path))
    if environment == ".venv3.10":
        (tmp_path / ".venv").mkdir()
    assert repair.expected_environment(tmp_path) == target


@pytest.mark.parametrize("launcher_version", [(3, 9, 21), (3, 10, 14), (3, 12, 2)])
def test_probe_selects_canonical_venv_regardless_of_launching_python(
    monkeypatch, mac_checkout, launcher_version,
):
    root, python, launcher = mac_checkout
    launcher.version_info = launcher_version
    calls = []
    monkeypatch.setattr(repair, "_run", lambda *a, **k: calls.append((a, k)) or 0)
    repair.validate_checkout(root)
    assert repair.validate_environment(root) == str(python)
    assert calls == [((
        str(python), ["-c", repair.INTERPRETER_PROBE, str(python.parent.parent), "arm64"], root,
    ), {"timeout": 30})]
    assert launcher.executable != str(python)


@pytest.mark.parametrize("host", ["win32", "linux"])
def test_non_mac_host_stops_before_native_operations(mac_checkout, host):
    root, _python, launcher = mac_checkout
    launcher.platform = host
    with pytest.raises(ValueError, match="macOS"):
        repair.repair_environment(root)


@pytest.mark.parametrize("missing", ["bin/python", "pyvenv.cfg"])
def test_incomplete_environment_is_reported_for_preserved_rebuild(mac_checkout, missing):
    root, python, _launcher = mac_checkout
    (python.parent.parent / missing).unlink()
    with pytest.raises(repair.EnvironmentInvalidError, match="missing or incomplete"):
        repair.validate_environment(root)
    assert python.parent.parent.exists()


def test_failed_interpreter_probe_requests_rebuild(monkeypatch, mac_checkout):
    root, _python, _launcher = mac_checkout
    monkeypatch.setattr(repair, "_run", lambda *a, **k: 23)
    with pytest.raises(repair.EnvironmentInvalidError, match="incompatible"):
        repair.validate_environment(root)


def test_unexecutable_interpreter_is_reported_for_preserved_rebuild(monkeypatch, mac_checkout):
    root, _python, _launcher = mac_checkout

    def fail(*args, **kwargs):
        raise OSError("bad executable format")

    monkeypatch.setattr(repair, "_run", fail)
    with pytest.raises(repair.EnvironmentInvalidError):
        repair.validate_environment(root)


def test_unsupported_native_cpu_is_not_treated_as_repairable(monkeypatch, mac_checkout):
    root, _python, _launcher = mac_checkout
    monkeypatch.setattr(repair, "_native_architecture", lambda: "unsupported")
    with pytest.raises(ValueError, match="Unsupported Mac CPU") as failure:
        repair.validate_environment(root)
    assert not isinstance(failure.value, repair.EnvironmentInvalidError)


@pytest.mark.parametrize("attribute,value", [
    ("platform", "linux"), ("version_info", (3, 11)),
    ("prefix", "/unrelated/venv"), ("base_prefix", "/selected/venv"), ("machine", "x86_64"),
])
def test_child_interpreter_probe_rejects_wrong_target(attribute, value):
    selected = SimpleNamespace(
        platform="darwin", version_info=(3, 10), prefix="/selected/venv",
        base_prefix="/base", executable="/selected/venv/bin/python",
        argv=["probe", "/selected/venv", "arm64"],
    )
    machine = value if attribute == "machine" else "arm64"
    if attribute != "machine":
        setattr(selected, attribute, value)
    fake_platform = SimpleNamespace(python_version=lambda: "3.10.14", machine=lambda: machine)
    normal_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        return {"sys": selected, "platform": fake_platform}.get(name) or normal_import(
            name, *args, **kwargs,
        )

    with pytest.raises(AssertionError):
        exec(repair.INTERPRETER_PROBE, {
            "__builtins__": {**vars(builtins), "__import__": fake_import},
        })


@pytest.mark.parametrize("returncode,output,expected", [(0, "1\n", "arm64"), (1, "", "x86_64")])
def test_native_cpu_check_detects_apple_silicon_even_under_rosetta(
    monkeypatch, returncode, output, expected,
):
    calls = []
    monkeypatch.setattr(repair.platform, "machine", lambda: "x86_64")

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=returncode, stdout=output)

    monkeypatch.setattr(repair.subprocess, "run", run)
    assert repair._native_architecture() == expected
    assert calls == [([
        "/usr/sbin/sysctl", "-n", "hw.optional.arm64",
    ], {"capture_output": True, "text": True, "check": False, "timeout": 10})]


def test_subprocess_keeps_exact_venv_path_isolation_and_spaced_checkout(monkeypatch, tmp_path):
    root = tmp_path / "Studio café & projects"
    python = str(root / ".venv/bin/python")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(repair.subprocess, "run", run)
    assert repair._run(python, ["-m", "pip", "check"], root, timeout=30) == 7
    assert calls == [([python, "-I", "-m", "pip", "check"], {
        "cwd": root, "check": False, "timeout": 30,
    })]


def test_backup_preserves_all_environment_files_inside_checkout(tmp_path):
    root, python = _checkout(tmp_path)
    marker = python.parent.parent / "user-file.txt"
    marker.write_text("retained data")
    repair._backup_environment(root)
    assert not python.parent.parent.exists()
    backups = list((root / ".fpvs-macos/environment-backups").iterdir())
    assert len(backups) == 1
    assert backups[0].resolve().is_relative_to(root.resolve())
    assert (backups[0] / "user-file.txt").read_text() == "retained data"
    assert (backups[0] / "bin/python").exists()
    assert (backups[0] / "pyvenv.cfg").exists()


@pytest.mark.parametrize("linked", [".venv3.10", ".fpvs-macos", ".fpvs-macos/environment-backups"])
def test_backup_refuses_linked_paths_without_moving_environment(monkeypatch, tmp_path, linked):
    root, python = _checkout(tmp_path)
    target = root / linked
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == target or original(path))
    with pytest.raises(ValueError):
        repair._backup_environment(root)
    assert python.exists()


def test_backup_refuses_existing_destination(monkeypatch, tmp_path):
    root, python = _checkout(tmp_path)
    monkeypatch.setattr(repair.uuid, "uuid4", lambda: SimpleNamespace(hex="fixed"))
    destination = root / ".fpvs-macos/environment-backups/.venv3.10-fixed"
    destination.mkdir(parents=True)
    with pytest.raises(ValueError, match="already exists"):
        repair._backup_environment(root)
    assert python.exists()


@pytest.mark.parametrize("returncode", [0, 19])
def test_setup_uses_mac_bootstrap_and_defers_ide_writes(monkeypatch, tmp_path, returncode):
    root, _python = _checkout(tmp_path)
    monkeypatch.setenv("FPVS_TEST_KEPT_SETTING", "kept")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=returncode)

    monkeypatch.setattr(repair.subprocess, "run", run)
    assert repair._run_setup(root) is (returncode == 0)
    command, options = calls[0]
    assert command == ["/bin/bash", str(root / "scripts/macos-source.sh"), "setup"]
    assert options["cwd"] == root
    assert options["check"] is False
    assert options["env"]["FPVS_SKIP_PYCHARM_CONFIG"] == "1"
    assert options["env"]["FPVS_TEST_KEPT_SETTING"] == "kept"
    assert "shell" not in options


def _fake_flow(
    monkeypatch, root, *, checks=(True,), validations=None, setup=(True,),
    pip_present=True, ensurepip=0, ide="ready",
):
    calls = []
    python = str(root / ".venv3.10/bin/python")
    pending_checks = iter(checks)
    pending_validation = iter(validations or [python] * 4)
    pending_setup = iter(setup)

    def validate(_root):
        assert _root == root
        calls.append(("validate",))
        value = next(pending_validation)
        if isinstance(value, Exception):
            raise value
        return value

    def check(_root, selected):
        assert _root == root
        calls.append(("check", selected))
        return next(pending_checks)

    def bootstrap(_root):
        assert _root == root
        calls.append(("setup",))
        return next(pending_setup)

    def run(selected, arguments, cwd, **kwargs):
        assert selected == python and cwd == root
        calls.append(("run", arguments))
        if arguments == ["-m", "pip", "--version"]:
            return 0 if pip_present else 1
        assert arguments == ["-m", "ensurepip", "--upgrade"]
        return ensurepip

    def configure(_root, selected, *, check_only=False):
        assert _root == root
        calls.append(("ide", selected, check_only))
        if isinstance(ide, Exception):
            raise ide
        return ide

    monkeypatch.setattr(repair, "validate_environment", validate)
    monkeypatch.setattr(repair, "_check_environment", check)
    monkeypatch.setattr(repair, "_run_setup", bootstrap)
    monkeypatch.setattr(repair, "_backup_environment", lambda _root: calls.append(("backup",)))
    monkeypatch.setattr(repair, "_run", run)
    monkeypatch.setattr(repair, "_configure_pycharm", configure)
    return calls, python


def test_healthy_environment_skips_install_and_configures_correct_interpreter(
    monkeypatch, mac_checkout, caplog,
):
    root, _python, _launcher = mac_checkout
    calls, python = _fake_flow(monkeypatch, root)
    with caplog.at_level(logging.INFO, logger=repair._LOGGER.name):
        assert repair.repair_environment(root) == 0
    assert calls == [("validate",), ("check", python), ("ide", python, False)]
    assert "Checks complete" in caplog.text


def test_unhealthy_dependencies_run_setup_and_pass_recheck_before_ide(monkeypatch, mac_checkout):
    root, _python, _launcher = mac_checkout
    calls, python = _fake_flow(monkeypatch, root, checks=(False, True))
    assert repair.repair_environment(root) == 0
    assert calls == [
        ("validate",), ("check", python), ("run", ["-m", "pip", "--version"]),
        ("setup",), ("check", python), ("ide", python, False),
    ]


def test_missing_pip_is_restored_only_in_selected_environment(monkeypatch, mac_checkout):
    root, _python, _launcher = mac_checkout
    calls, _python = _fake_flow(monkeypatch, root, checks=(False, True), pip_present=False)
    assert repair.repair_environment(root) == 0
    assert ("run", ["-m", "ensurepip", "--upgrade"]) in calls
    assert calls.index(("run", ["-m", "ensurepip", "--upgrade"])) < calls.index(("setup",))


def test_failed_pip_restore_stops_before_setup_or_ide(monkeypatch, mac_checkout):
    root, _python, _launcher = mac_checkout
    calls, _python = _fake_flow(
        monkeypatch, root, checks=(False,), pip_present=False, ensurepip=19,
    )
    assert repair.repair_environment(root) == 1
    assert not any(call[0] in ("setup", "ide", "backup") for call in calls)


def test_missing_or_incompatible_environment_is_preserved_then_bootstrapped(
    monkeypatch, mac_checkout,
):
    root, python, _launcher = mac_checkout
    calls, _ = _fake_flow(monkeypatch, root, validations=[
        repair.EnvironmentInvalidError("incompatible"), str(python),
    ])
    assert repair.repair_environment(root) == 0
    assert calls[:4] == [("validate",), ("backup",), ("setup",), ("validate",)]
    assert calls[-1] == ("ide", str(python), False)


def test_persistent_failure_rebuilds_once_then_uses_revalidated_interpreter(
    monkeypatch, mac_checkout,
):
    root, python, _launcher = mac_checkout
    replacement = str(root / ".venv/bin/python")
    calls, _ = _fake_flow(
        monkeypatch, root, checks=(False, False, True), setup=(True, True),
        validations=[str(python), replacement],
    )
    assert repair.repair_environment(root) == 0
    assert calls.count(("backup",)) == 1
    assert calls.count(("setup",)) == 2
    assert calls[-2:] == [("check", replacement), ("ide", replacement, False)]


def test_failed_fresh_rebuild_never_configures_ide_or_reports_success(
    monkeypatch, mac_checkout, caplog,
):
    root, _python, _launcher = mac_checkout
    calls, _ = _fake_flow(monkeypatch, root, checks=(False, False, False), setup=(True, True))
    with caplog.at_level(logging.INFO, logger=repair._LOGGER.name):
        assert repair.repair_environment(root) == 1
    assert calls.count(("backup",)) == 1
    assert calls.count(("setup",)) == 2
    assert not any(call[0] == "ide" for call in calls)
    assert "Repair complete" not in caplog.text


@pytest.mark.parametrize("stage", ["bootstrap", "repair", "rebuild"])
def test_setup_failure_stops_further_mutations(monkeypatch, mac_checkout, stage):
    root, _python, _launcher = mac_checkout
    options = {"checks": (False,), "setup": (False,)}
    if stage == "bootstrap":
        options["validations"] = [repair.EnvironmentInvalidError("missing")]
    if stage == "rebuild":
        options.update(checks=(False, False), setup=(True, False))
    calls, _ = _fake_flow(monkeypatch, root, **options)
    assert repair.repair_environment(root) == 1
    assert calls[-1] == ("setup",)
    assert not any(call[0] == "ide" for call in calls)


def test_check_only_validates_environment_and_ide_without_mutations(monkeypatch, mac_checkout):
    root, _python, _launcher = mac_checkout
    calls, python = _fake_flow(monkeypatch, root)
    assert repair.repair_environment(root, check_only=True) == 0
    assert calls == [("validate",), ("check", python), ("ide", python, True)]


def test_check_only_does_not_repair_failed_dependencies(monkeypatch, mac_checkout):
    root, _python, _launcher = mac_checkout
    calls, python = _fake_flow(monkeypatch, root, checks=(False,))
    assert repair.repair_environment(root, check_only=True) == 1
    assert calls == [("validate",), ("check", python)]


def test_check_only_does_not_replace_invalid_environment(monkeypatch, mac_checkout):
    root, _python, _launcher = mac_checkout
    calls, _ = _fake_flow(
        monkeypatch, root, validations=[repair.EnvironmentInvalidError("missing")],
    )
    with pytest.raises(repair.EnvironmentInvalidError):
        repair.repair_environment(root, check_only=True)
    assert calls == [("validate",)]


def test_pending_ide_handoff_does_not_report_full_success(monkeypatch, mac_checkout, caplog):
    root, _python, _launcher = mac_checkout
    _fake_flow(monkeypatch, root, ide="pending")
    with caplog.at_level(logging.INFO, logger=repair._LOGGER.name):
        assert repair.repair_environment(root) == 0
    assert "finishing in a separate process" in caplog.text
    assert "configured correctly" not in caplog.text
    assert "Repair complete" not in caplog.text


def test_failed_ide_configuration_cannot_report_ready(monkeypatch, mac_checkout):
    root, _python, _launcher = mac_checkout
    _fake_flow(monkeypatch, root, ide=ValueError("IDE profile could not be determined"))
    monkeypatch.setattr(repair, "__file__", str(root / "Repair Mac.py"))
    assert repair.main([]) == 1
    log = next((root / ".fpvs-macos/diagnostics").glob("*/repair.log")).read_text()
    assert "could not be determined" in log
    assert "Checks complete" not in log


@pytest.mark.parametrize("failed", ["check", "-c"])
def test_dependency_check_preserves_engine_diagnostics_even_when_pip_check_fails(
    monkeypatch, tmp_path, failed,
):
    root, python = _checkout(tmp_path)
    calls = []

    def run(selected, arguments, cwd, **kwargs):
        assert selected == str(python) and cwd == root
        calls.append(arguments)
        return 1 if failed in arguments else 0

    monkeypatch.setattr(repair, "_run", run)
    assert not repair._check_environment(root, str(python))
    assert calls == [["-m", "pip", "check"], ["-c", repair.ENGINE_PROBE, str(root)]]


@pytest.mark.parametrize("check_only", [False, True])
@pytest.mark.parametrize("returncode,result", [(0, "ready"), (10, "pending"), (19, None)])
def test_ide_handoff_runs_under_verified_python(
    monkeypatch, mac_checkout, check_only, returncode, result,
):
    root, python, launcher = mac_checkout
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=returncode)

    monkeypatch.setattr(repair.subprocess, "run", run)
    if result is None:
        with pytest.raises(ValueError):
            repair._configure_pycharm(root, str(python), check_only=check_only)
    else:
        assert repair._configure_pycharm(root, str(python), check_only=check_only) == result
    command, options = calls[0]
    assert command[:5] == [
        str(python), "-I", str(root / "scripts/macos_pycharm.py"), str(root), str(python),
    ]
    assert ("--check" if check_only else "--repair") in command
    assert command[command.index("--repair-launch-prefix") + 1] == launcher.prefix
    assert command[command.index("--repair-launch-version") + 1] == "3.12"
    assert "--repair-parent-pid" in command
    assert options == {"cwd": root, "check": False, "timeout": 120}


def test_main_check_uses_script_checkout_not_working_directory(monkeypatch, tmp_path):
    root, _python = _checkout(tmp_path)
    monkeypatch.setattr(repair, "__file__", str(root / "Repair Mac.py"))
    calls = []
    monkeypatch.setattr(
        repair, "repair_environment",
        lambda selected, **kwargs: calls.append((selected, kwargs)) or 0,
    )
    assert repair.main(["--check"]) == 0
    assert calls == [(root, {"check_only": True})]


@pytest.mark.parametrize("error", [
    OSError("missing executable"), ValueError("wrong interpreter"),
    subprocess.TimeoutExpired("probe", 30),
])
def test_main_reports_environment_or_subprocess_errors(monkeypatch, tmp_path, error):
    root, _python = _checkout(tmp_path)
    monkeypatch.setattr(repair, "__file__", str(root / "Repair Mac.py"))

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(repair, "repair_environment", fail)
    assert repair.main([]) == 1


@pytest.mark.parametrize("missing", [
    "pyproject.toml", "requirements-macos.txt", "src/fpvs_studio/app/main.py",
    "scripts/macos-source.sh", "scripts/macos_pycharm.py",
])
def test_incomplete_checkout_fails_before_native_operations(mac_checkout, missing):
    root, _python, _launcher = mac_checkout
    (root / missing).unlink()
    with pytest.raises(ValueError, match="Missing"):
        repair.repair_environment(root)


def _fake_probe(
    monkeypatch, root, *, source_root=None, requirements=(), versions=None, loader=None,
    source_requirements=None,
):
    studio = ModuleType("fpvs_studio")
    studio.__file__ = str((source_root or root) / "src/fpvs_studio/__init__.py")
    studio.__version__ = "2.9.0"
    engines = ModuleType("fpvs_studio.engines")
    modules = ModuleType("fpvs_studio.engines.psychopy_loader")
    calls = []
    modules.load_psychopy_modules = loader or (lambda: calls.append("engine imports"))
    monkeypatch.setitem(sys.modules, "fpvs_studio", studio)
    monkeypatch.setitem(sys.modules, "fpvs_studio.engines", engines)
    monkeypatch.setitem(sys.modules, "fpvs_studio.engines.psychopy_loader", modules)
    monkeypatch.setattr(sys, "argv", ["probe", str(root)])
    installed = {
        "fpvs-studio": "2.9.0", "psychopy": "2026.2.0", "PySide6": "6.11.3",
        "PyQt6": "6.11.0", "numpy": "1.26.4", "pytest": "9.0.3",
    }
    installed.update(versions or {})
    monkeypatch.setattr(importlib.metadata, "version", lambda name: installed[name])
    monkeypatch.setattr(
        importlib.metadata, "distribution", lambda name: SimpleNamespace(requires=requirements),
    )
    monkeypatch.setattr(markers, "default_environment", lambda: {
        "implementation_name": "cpython", "implementation_version": "3.10.14",
        "os_name": "posix", "platform_machine": "arm64", "platform_release": "24.0",
        "platform_system": "Darwin", "platform_version": "synthetic Mac",
        "python_full_version": "3.10.14", "platform_python_implementation": "CPython",
        "python_version": "3.10", "sys_platform": "darwin",
    })
    declared = source_requirements or {}
    (root / "pyproject.toml").write_text(
        '[project]\nname = "fpvs-studio"\nversion = "2.9.0"\n'
        f'dependencies = {json.dumps(declared.get("base", []))}\n'
        '[project.optional-dependencies]\n'
        f'dev = {json.dumps(declared.get("dev", []))}\n'
        f'engine = {json.dumps(declared.get("engine", []))}\n'
        'packaging = ["absent-packaging-tool"]\n'
    )
    return calls


def test_probe_reaches_only_engine_boundary_after_source_and_metadata_checks(monkeypatch, tmp_path):
    calls = _fake_probe(monkeypatch, tmp_path, requirements=[
        "numpy>=1.26,<3", "psychopy>=2026.1; extra == 'engine'",
        "pytest>=9; extra == 'dev'", "absent-packaging-tool; extra == 'packaging'",
    ], source_requirements={"base": ["numpy>=1.26"], "dev": ["pytest>=9"],
                            "engine": ["psychopy>=2026.1"]})
    exec(repair.ENGINE_PROBE, {})
    assert calls == ["engine imports"]


def test_probe_rejects_another_studio_checkout_before_loading_engine(monkeypatch, tmp_path):
    calls = _fake_probe(monkeypatch, tmp_path, source_root=tmp_path / "another checkout")
    with pytest.raises(RuntimeError, match="Studio imports from"):
        exec(repair.ENGINE_PROBE, {})
    assert calls == []


def test_probe_rejects_stale_editable_release_metadata(monkeypatch, tmp_path):
    calls = _fake_probe(monkeypatch, tmp_path, versions={"fpvs-studio": "2.8.0"})
    with pytest.raises(RuntimeError, match="metadata"):
        exec(repair.ENGINE_PROBE, {})
    assert calls == []


@pytest.mark.parametrize("requirement", [
    "psychopy>=2026.3; extra == 'engine'", "pytest>=10; extra == 'dev'", "numpy>=2",
])
def test_probe_rejects_unsatisfied_installed_requirements(monkeypatch, tmp_path, requirement):
    calls = _fake_probe(monkeypatch, tmp_path, requirements=[requirement])
    with pytest.raises(RuntimeError, match="does not satisfy"):
        exec(repair.ENGINE_PROBE, {})
    assert calls == []


@pytest.mark.parametrize("group,requirement", [
    ("base", "numpy>=2"), ("dev", "pytest>=10"), ("engine", "psychopy>=2026.3"),
])
def test_probe_detects_source_requirement_changes_without_release_bump(
    monkeypatch, tmp_path, group, requirement,
):
    calls = _fake_probe(monkeypatch, tmp_path, source_requirements={group: [requirement]})
    with pytest.raises(RuntimeError, match="does not satisfy"):
        exec(repair.ENGINE_PROBE, {})
    assert calls == []


def test_probe_keeps_engine_import_failure_cause_for_researcher(monkeypatch, tmp_path):
    def fail():
        try:
            raise ImportError("synthetic missing native dependency")
        except ImportError as cause:
            raise RuntimeError("PsychoPy is not installed") from cause

    _fake_probe(monkeypatch, tmp_path, loader=fail)
    with pytest.raises(RuntimeError, match="PsychoPy is not installed") as failure:
        exec(repair.ENGINE_PROBE, {})
    assert isinstance(failure.value.__cause__, ImportError)
    assert str(failure.value.__cause__) == "synthetic missing native dependency"
