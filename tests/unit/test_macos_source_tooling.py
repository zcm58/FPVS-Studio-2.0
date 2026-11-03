"""The Mac source lane resolves real dependencies and keeps display acceptance explicit."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("command", ["run", "setup"])
@pytest.mark.parametrize("preferred", [False, True])
@pytest.mark.skipif(os.name != "posix", reason="Native POSIX shell/interpreter layout")
def test_source_helper_reuses_native_environment(tmp_path, command, preferred):
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("The macOS source helper requires Bash")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    helper = scripts / "macos-source.sh"
    shutil.copyfile(ROOT / "scripts/macos-source.sh", helper)
    tools = tmp_path / "tools"
    tools.mkdir()
    uname = tools / "uname"
    uname.write_text('#!/bin/sh\ncase "$1" in -s) echo Darwin;; -m) echo arm64;; esac\n',
                     encoding="utf-8")
    uname.chmod(0o700)
    for environment in (".venv", ".venv3.10") if preferred else (".venv",):
        python = tmp_path / environment / "bin/python"
        python.parent.mkdir(parents=True)
        python.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$0" "$@" >> "$FPVS_TEST_COMMANDS"\n',
            encoding="utf-8",
        )
        python.chmod(0o700)
    log = tmp_path / "commands.txt"
    env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"],
               FPVS_TEST_COMMANDS=str(log))
    result = subprocess.run([bash, str(helper), command], env=env, capture_output=True,
                            text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    selected = ".venv3.10" if preferred else ".venv"
    commands = log.read_text(encoding="utf-8")
    assert str(tmp_path / selected / "bin/python") in commands
    assert ("fpvs_studio.app" if command == "run" else "requirements-macos.txt") in commands
    assert (tmp_path / ".venv3.10").exists() is preferred


def test_macos_source_ci_checks_both_native_architectures_without_gui_opt_in() -> None:
    workflow = yaml.load(
        (ROOT / ".github/workflows/macos-source.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert "workflow_dispatch" in workflow["on"]
    jobs = workflow["jobs"]
    assert jobs["windows-source"]["runs-on"] == "windows-latest"
    windows_checks = next(
        step for step in jobs["windows-source"]["steps"]
        if "--tier precommit" in step.get("run", "")
    )
    assert "--scope repo" in windows_checks["run"]
    assert "FPVS_ALLOW_QT_TESTS" not in str(windows_checks)
    assert "continue-on-error" not in windows_checks
    assert jobs["windows-return"]["runs-on"] == "windows-latest"
    assert jobs["windows-return"]["needs"] == "source"
    job = jobs["source"]
    assert job["needs"] == "windows-source"
    assert job["strategy"]["matrix"]["include"] == [
        {"runner": "macos-15", "cpu": "arm64", "python-architecture": "arm64"},
        {"runner": "macos-15-intel", "cpu": "x86_64", "python-architecture": "x64"},
    ]
    setup = next(step for step in job["steps"] if step.get("uses", "").startswith(
        "actions/setup-python@"
    ))
    assert setup["with"]["python-version"] == "3.10"
    steps = "\n".join(str(step) for step in job["steps"])
    installation = next(step for step in job["steps"]
                        if step.get("run") == "bash scripts/macos-source.sh setup")
    assert installation["env"]["FPVS_MANAGED_PYTHON"] == "1"
    assert "FPVS_MACOS_NATIVE_CHECKS" in steps
    assert "FPVS_ALLOW_QT_TESTS" not in steps
    assert "offscreen" not in steps
    assert "--no-deps" not in steps
    assert "continue-on-error" not in steps
    assert "macos_bundle_handoff.py roundtrip" in steps
    assert "macos_bundle_handoff.py create" in str(jobs["windows-source"]["steps"])
    assert "macos_bundle_handoff.py roundtrip" in str(jobs["windows-return"]["steps"])
    assert "macos-handoff-*" in str(jobs["windows-return"]["steps"])
    assert "macos_bundle_handoff.py create" in steps
    assert "macos-origin-*" in str(jobs["windows-return"]["steps"])
    reverse = jobs["macos-origin-return"]
    assert reverse["needs"] == "windows-return"
    assert reverse["strategy"]["matrix"] == job["strategy"]["matrix"]
    assert "windows-origin-return-${{ matrix.cpu }}" in str(reverse["steps"])
    assert "macos_bundle_handoff.py roundtrip" in str(reverse["steps"])
    assert ".[dev,engine]" not in str(reverse["steps"])
    assert "scripts/macos-source.sh setup" not in str(reverse["steps"])
    script = (ROOT / "scripts/macos-source.sh").read_text(encoding="utf-8")
    assert "pip install --requirement requirements-macos.txt" in script
    assert "-m pip check" in script


def test_native_adapter_imports_do_not_load_gui_psychopy_or_platform_bridges() -> None:
    code = """
import sys
from fpvs_studio.core import models
from fpvs_studio.runtime import display_mode, macos_display
from fpvs_studio.gui import native_files
from fpvs_studio.library import credentials
for prefix in ('PySide6', 'psychopy', 'AppKit', 'Foundation', 'objc'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_ci_keychain_restores_selection_and_deletes_only_its_own_file(monkeypatch, tmp_path):
    from tests.integration import test_macos_native as native

    calls = []
    previous = "/Users/runner/Library/Keychains/login.keychain-db"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "github-hosted")

    def security(*arguments):
        calls.append(arguments)
        if arguments == ("default-keychain", "-d", "user"):
            return f'"{previous}"\n'
        if arguments == ("list-keychains", "-d", "user"):
            return f'"{previous}"\n'
        return ""

    monkeypatch.setattr(native, "_security", security)
    try:
        with native._temporary_ci_keychain(tmp_path) as owned:
            assert owned.parent == tmp_path
            raise RuntimeError("synthetic failure")
    except RuntimeError:
        pass

    assert calls[-3:] == [
        ("default-keychain", "-d", "user", "-s", previous),
        ("list-keychains", "-d", "user", "-s", previous),
        ("delete-keychain", str(owned)),
    ]
    assert ("unlock-keychain", "-p") == calls[4][:2]
    assert calls[4][-1] == str(owned)
    assert previous not in calls[4]


def test_ci_keychain_never_changes_a_personal_or_self_hosted_mac(monkeypatch, tmp_path):
    from tests.integration import test_macos_native as native

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "self-hosted")
    monkeypatch.setattr(
        native, "_security", lambda *_: pytest.fail("Changed a non-hosted Keychain"),
    )
    with pytest.raises(pytest.skip.Exception):
        with native._temporary_ci_keychain(tmp_path):
            pytest.fail("The hosted-only resource must not be created")


@pytest.mark.parametrize("status", [-25307, -25293])
def test_ci_keychain_distinguishes_no_default_from_a_failed_snapshot(
    monkeypatch, tmp_path, status,
):
    from tests.integration import test_macos_native as native

    calls = []
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "github-hosted")
    fake_security = SimpleNamespace(
        kSecPreferencesDomainUser=0, errSecNoDefaultKeychain=-25307,
        SecKeychainCopyDomainDefault=lambda domain, target: (status, None),
    )
    original_import = native.importlib.import_module
    monkeypatch.setattr(
        native.importlib, "import_module",
        lambda name: fake_security if name == "Security" else original_import(name),
    )

    def security(*arguments):
        calls.append(arguments)
        if arguments == ("default-keychain", "-d", "user"):
            raise subprocess.CalledProcessError(1, ["security", *arguments])
        return ""

    monkeypatch.setattr(native, "_security", security)
    if status == -25307:
        with native._temporary_ci_keychain(tmp_path) as owned:
            assert owned.parent == tmp_path
        assert calls[-3:] == [
            ("default-keychain", "-d", "user", "-s"),
            ("list-keychains", "-d", "user", "-s"),
            ("delete-keychain", str(owned)),
        ]
    else:
        with pytest.raises(subprocess.CalledProcessError):
            with native._temporary_ci_keychain(tmp_path):
                pytest.fail("An unknown selection must not be modified")
        assert calls == [("default-keychain", "-d", "user")]


@pytest.mark.parametrize("missing_after_restore", [True, False])
def test_ci_keychain_unset_error_requires_confirming_original_empty_state(
    monkeypatch, tmp_path, missing_after_restore,
):
    from tests.integration import test_macos_native as native

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "github-hosted")
    states = iter([True, missing_after_restore])
    monkeypatch.setattr(native, "_default_keychain_missing", lambda: next(states))
    calls = []

    def security(*arguments):
        calls.append(arguments)
        if arguments in {
            ("default-keychain", "-d", "user"),
            ("default-keychain", "-d", "user", "-s"),
        }:
            raise subprocess.CalledProcessError(1, ["security", *arguments])
        return ""

    monkeypatch.setattr(native, "_security", security)
    if missing_after_restore:
        with native._temporary_ci_keychain(tmp_path) as owned:
            assert owned.parent == tmp_path
    else:
        with pytest.raises(subprocess.CalledProcessError):
            with native._temporary_ci_keychain(tmp_path) as owned:
                assert owned.parent == tmp_path
    assert calls[-1] == ("delete-keychain", str(owned))
