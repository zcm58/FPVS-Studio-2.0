"""Mac environment repair never installs into an unrelated interpreter."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "macos_environment_repair", ROOT / "scripts/macos_repair_environment.py",
)
assert SPEC is not None and SPEC.loader is not None
repair = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(repair)


def _checkout(tmp_path: Path, environment: str = ".venv3.10") -> tuple[Path, Path]:
    root = tmp_path / "Studio café & projects"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "fpvs-studio"\n')
    (root / "requirements-macos.txt").write_text("-e .[dev,engine]\n")
    source = root / "src/fpvs_studio/app/main.py"
    source.parent.mkdir(parents=True)
    source.write_text("# synthetic Studio checkout\n")
    python = root / environment / "bin/python"
    python.parent.mkdir(parents=True)
    python.touch()
    (python.parent.parent / "pyvenv.cfg").write_text("home = /base/python\n")
    return root, python


@pytest.fixture
def valid_environment(monkeypatch, tmp_path):
    root, python = _checkout(tmp_path)
    selected = SimpleNamespace(**vars(sys))
    selected.platform = "darwin"
    selected.version = "3.10.14 (synthetic test interpreter)"
    selected.version_info = (3, 10, 14)
    selected.executable = str(python)
    selected.prefix = str(python.parent.parent)
    selected.base_prefix = str(tmp_path / "base-python")
    monkeypatch.setattr(repair, "sys", selected)
    monkeypatch.setattr(repair.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(repair, "_native_architecture", lambda: "arm64")
    return root, python, selected


@pytest.mark.parametrize("preferred_exists,fallback_exists,expected", [
    (False, False, ".venv3.10"),
    (True, False, ".venv3.10"),
    (False, True, ".venv"),
    (True, True, ".venv3.10"),
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
def test_broken_environment_symlink_is_preserved_instead_of_selecting_another(
    monkeypatch, tmp_path, environment,
):
    target = tmp_path / environment
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == target or original(path))
    if environment == ".venv3.10":
        (tmp_path / ".venv").mkdir()
    assert repair.expected_environment(tmp_path) == target


def test_validated_interpreter_retains_venv_executable_path(valid_environment):
    root, python, selected = valid_environment
    selected.executable = str(python.parent / "python3.10")
    assert repair.validate_environment(root) == selected.executable


@pytest.mark.parametrize("attribute,value", [
    ("platform", "win32"),
    ("version_info", (3, 11, 9)),
    ("version_info", (3, 9, 21)),
    ("prefix", "/different/project/.venv"),
])
def test_invalid_selected_interpreter_is_rejected(valid_environment, attribute, value):
    root, _python, selected = valid_environment
    setattr(selected, attribute, value)
    with pytest.raises(ValueError):
        repair.validate_environment(root)


def test_system_interpreter_is_rejected(valid_environment):
    root, _python, selected = valid_environment
    selected.base_prefix = selected.prefix
    with pytest.raises(ValueError):
        repair.validate_environment(root)


def test_rosetta_interpreter_is_rejected(monkeypatch, valid_environment):
    root, _python, _selected = valid_environment
    monkeypatch.setattr(repair.platform, "machine", lambda: "x86_64")
    with pytest.raises(ValueError):
        repair.validate_environment(root)


def test_unsupported_native_cpu_is_rejected(monkeypatch, valid_environment):
    root, _python, _selected = valid_environment
    monkeypatch.setattr(repair, "_native_architecture", lambda: "unsupported")
    with pytest.raises(ValueError):
        repair.validate_environment(root)


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
    assert calls == [(
        ["/usr/sbin/sysctl", "-n", "hw.optional.arm64"],
        {"capture_output": True, "text": True, "check": False, "timeout": 10},
    )]


@pytest.mark.parametrize("missing", ["bin/python", "pyvenv.cfg"])
def test_incomplete_environment_is_preserved_and_rejected(valid_environment, missing):
    root, python, _selected = valid_environment
    (python.parent.parent / missing).unlink()
    with pytest.raises(ValueError):
        repair.validate_environment(root)
    assert python.parent.parent.exists()


def test_subprocess_uses_exact_interpreter_isolation_and_checkout(monkeypatch, tmp_path):
    root = tmp_path / "Studio café & projects"
    python = str(root / ".venv/bin/python")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(repair.subprocess, "run", run)
    assert repair._run(python, ["-m", "pip", "check"], root, timeout=30) == 7
    assert calls == [(
        [python, "-I", "-m", "pip", "check"],
        {"cwd": root, "check": False, "timeout": 30},
    )]


def _fake_commands(monkeypatch, root, *, failures=None):
    calls = []
    python = str(root / ".venv3.10/bin/python")
    monkeypatch.setattr(repair, "validate_environment", lambda _root: python)
    failures = failures or {}

    def run(selected, arguments, cwd, *, timeout=None):
        assert selected == python
        assert cwd == root
        calls.append((arguments, timeout))
        for marker, result in failures.items():
            if marker in arguments:
                return result
        return 0

    monkeypatch.setattr(repair, "_run", run)
    return calls


def test_repair_installs_declared_profile_then_checks_metadata_and_engine(monkeypatch, tmp_path):
    root, _python = _checkout(tmp_path)
    calls = _fake_commands(monkeypatch, root)
    assert repair.repair_environment(root) == 0
    commands = [arguments for arguments, _timeout in calls]
    assert commands[0] == ["-m", "pip", "--version"]
    assert commands[1] == ["-m", "pip", "install", "--upgrade", "pip>=25,<27"]
    assert commands[2] == ["-m", "pip", "install", "--requirement", "requirements-macos.txt"]
    assert commands[3] == ["-m", "pip", "check"]
    assert commands[4] == ["-c", repair.ENGINE_PROBE, str(root)]
    assert len(commands) == 5


def test_missing_pip_uses_same_interpreter_ensurepip_before_install(monkeypatch, tmp_path):
    root, _python = _checkout(tmp_path)
    calls = _fake_commands(monkeypatch, root, failures={"--version": 1})
    assert repair.repair_environment(root) == 0
    commands = [arguments for arguments, _timeout in calls]
    assert commands[:3] == [
        ["-m", "pip", "--version"],
        ["-m", "ensurepip", "--upgrade"],
        ["-m", "pip", "install", "--upgrade", "pip>=25,<27"],
    ]


@pytest.mark.parametrize("failure", ["ensurepip", "pip>=25,<27", "requirements-macos.txt"])
def test_install_failure_stops_without_reporting_success(monkeypatch, tmp_path, failure):
    root, _python = _checkout(tmp_path)
    failures = {failure: 19}
    if failure == "ensurepip":
        failures["--version"] = 1
    calls = _fake_commands(monkeypatch, root, failures=failures)
    assert repair.repair_environment(root) != 0
    assert failure in calls[-1][0]
    assert not any("check" in arguments or "-c" in arguments for arguments, _ in calls)


@pytest.mark.parametrize("failure", ["check", "-c"])
def test_dependency_or_loader_failure_cannot_report_success(monkeypatch, tmp_path, failure):
    root, _python = _checkout(tmp_path)
    calls = _fake_commands(monkeypatch, root, failures={failure: 23})
    assert repair.repair_environment(root) != 0
    assert any(failure in arguments for arguments, _ in calls)


def test_check_only_runs_checks_without_installing_anything(monkeypatch, tmp_path):
    root, _python = _checkout(tmp_path)
    calls = _fake_commands(monkeypatch, root)
    assert repair.repair_environment(root, check_only=True) == 0
    commands = [arguments for arguments, _timeout in calls]
    assert commands == [["-m", "pip", "check"], ["-c", repair.ENGINE_PROBE, str(root)]]


def test_validation_failure_happens_before_any_pip_invocation(monkeypatch, tmp_path):
    root, _python = _checkout(tmp_path)
    calls = []

    def fail(_root):
        raise ValueError("Wrong project interpreter")

    monkeypatch.setattr(repair, "validate_environment", fail)
    monkeypatch.setattr(repair, "_run", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(ValueError, match="Wrong project interpreter"):
        repair.repair_environment(root)
    assert calls == []


def test_main_check_uses_script_checkout_not_process_working_directory(monkeypatch, tmp_path):
    root, _python = _checkout(tmp_path)
    monkeypatch.setattr(repair, "__file__", str(root / "scripts/macos_repair_environment.py"))
    calls = []

    def run(selected, *, check_only=False):
        calls.append((selected, check_only))
        return 0

    monkeypatch.setattr(repair, "repair_environment", run)
    assert repair.main(["--check"]) == 0
    assert calls == [(root, True)]


@pytest.mark.parametrize("error", [
    OSError("missing executable"),
    ValueError("wrong interpreter"),
    subprocess.TimeoutExpired("probe", 30),
])
def test_main_reports_environment_or_subprocess_errors(monkeypatch, tmp_path, error):
    root, _python = _checkout(tmp_path)
    monkeypatch.setattr(repair, "__file__", str(root / "scripts/macos_repair_environment.py"))

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(repair, "repair_environment", fail)
    assert repair.main([]) != 0


@pytest.mark.parametrize("missing", [
    "pyproject.toml", "requirements-macos.txt", "src/fpvs_studio/app/main.py",
])
def test_main_refuses_incomplete_checkout_before_pip(monkeypatch, valid_environment, missing):
    root, _python, _selected = valid_environment
    (root / missing).unlink()
    monkeypatch.setattr(repair, "__file__", str(root / "scripts/macos_repair_environment.py"))
    calls = []
    monkeypatch.setattr(repair, "_run", lambda *a, **k: calls.append(a))
    assert repair.main([]) != 0
    assert calls == []


def _fake_probe(
    monkeypatch, root, *, source_root=None, requirements=(), versions=None, loader=None,
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
    return calls


def test_probe_reaches_only_engine_boundary_after_matching_source_and_extras(monkeypatch, tmp_path):
    calls = _fake_probe(monkeypatch, tmp_path, requirements=[
        "numpy>=1.26,<3", "psychopy>=2026.1; extra == 'engine'",
        "pytest>=9; extra == 'dev'", "absent-packaging-tool; extra == 'packaging'",
    ])
    exec(repair.ENGINE_PROBE, {})
    assert calls == ["engine imports"]


def test_probe_rejects_another_studio_checkout_before_loading_engine(monkeypatch, tmp_path):
    calls = _fake_probe(monkeypatch, tmp_path, source_root=tmp_path / "another checkout")
    with pytest.raises(RuntimeError, match="Studio imports from"):
        exec(repair.ENGINE_PROBE, {})
    assert calls == []


def test_probe_rejects_stale_editable_metadata_after_source_update(monkeypatch, tmp_path):
    calls = _fake_probe(monkeypatch, tmp_path, versions={"fpvs-studio": "2.8.0"})
    with pytest.raises(RuntimeError, match="metadata"):
        exec(repair.ENGINE_PROBE, {})
    assert calls == []


@pytest.mark.parametrize("requirement", [
    "psychopy>=2026.3; extra == 'engine'", "pytest>=10; extra == 'dev'", "numpy>=2",
])
def test_probe_rejects_unsatisfied_base_or_extra_requirements(monkeypatch, tmp_path, requirement):
    calls = _fake_probe(monkeypatch, tmp_path, requirements=[requirement])
    with pytest.raises(RuntimeError, match="does not satisfy"):
        exec(repair.ENGINE_PROBE, {})
    assert calls == []


def test_probe_keeps_engine_import_failure_cause_for_researcher_diagnostics(monkeypatch, tmp_path):
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
