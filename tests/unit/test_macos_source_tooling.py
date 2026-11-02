"""The Mac source lane resolves real dependencies and keeps display acceptance explicit."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_macos_source_ci_checks_both_native_architectures_without_gui_opt_in() -> None:
    workflow = yaml.load(
        (ROOT / ".github/workflows/macos-source.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert "workflow_dispatch" in workflow["on"]
    jobs = workflow["jobs"]
    assert jobs["windows-source"]["runs-on"] == "windows-latest"
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
    assert "pip install --editable '.[dev,engine]'" in script
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
