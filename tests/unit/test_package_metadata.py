"""Packaging metadata regression guards."""

from __future__ import annotations

import re
from pathlib import Path

from fpvs_studio import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_TEXT = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
PACKAGE_INIT_TEXT = (REPO_ROOT / "src" / "fpvs_studio" / "__init__.py").read_text(
    encoding="utf-8"
)
PYINSTALLER_SPEC_TEXT = (
    REPO_ROOT / "packaging" / "pyinstaller" / "fpvs_studio.spec"
).read_text(encoding="utf-8")
BUILD_EXE_TEXT = (REPO_ROOT / "scripts" / "build_exe.ps1").read_text(encoding="utf-8")
BUILD_INSTALLER_TEXT = (REPO_ROOT / "scripts" / "build_installer.ps1").read_text(
    encoding="utf-8"
)
BUILD_RELEASE_TEXT = (REPO_ROOT / "scripts" / "build_release.ps1").read_text(
    encoding="utf-8"
)
PACKAGED_SMOKE_TEXT = (REPO_ROOT / "src" / "fpvs_studio" / "app" / "packaged_smoke.py").read_text(
    encoding="utf-8"
)
INNO_SCRIPT_TEXT = (REPO_ROOT / "packaging" / "inno" / "fpvs_studio.iss").read_text(
    encoding="utf-8"
)


def _extract_list_assignment(name: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(name)} = \[(.*?)^\]",
        PYPROJECT_TEXT,
    )
    if match is None:
        raise AssertionError(f"Could not find list assignment for '{name}'.")
    return match.group(1)


def test_pyproject_targets_python_310_only() -> None:
    assert 'name = "fpvs-studio"' in PYPROJECT_TEXT
    assert 'requires-python = ">=3.10,<3.11"' in PYPROJECT_TEXT
    assert '"Programming Language :: Python :: 3 :: Only"' in PYPROJECT_TEXT
    assert '"Programming Language :: Python :: 3.10"' in PYPROJECT_TEXT


def test_package_version_matches_pyproject_version() -> None:
    pyproject_match = re.search(r'^version = "([^"]+)"$', PYPROJECT_TEXT, re.MULTILINE)

    assert pyproject_match is not None
    assert "version(\"fpvs-studio\")" in PACKAGE_INIT_TEXT
    assert "_source_tree_version() or version(\"fpvs-studio\")" in PACKAGE_INIT_TEXT
    assert "__version__ = \"0.1.0\"" not in PACKAGE_INIT_TEXT
    assert __version__ == pyproject_match.group(1)


def test_default_install_requires_pyside6_but_keeps_psychopy_optional() -> None:
    dependencies_block = _extract_list_assignment("dependencies").lower()
    dev_dependencies_block = _extract_list_assignment("dev").lower()
    packaging_dependencies_block = _extract_list_assignment("packaging").lower()
    assert "psychopy" not in dependencies_block
    assert "pyside6" in dependencies_block
    engine_dependencies_block = _extract_list_assignment("engine").lower()
    assert "psychopy" in engine_dependencies_block
    assert "sounddevice" in engine_dependencies_block
    assert "pytest-qt" in dev_dependencies_block
    assert "pytest-timeout" in dev_dependencies_block
    assert "pyinstaller" in packaging_dependencies_block


def test_pyinstaller_includes_psychopy_visual_lazy_imports() -> None:
    assert '_collect_submodules("psychopy.visual")' in PYINSTALLER_SPEC_TEXT
    assert '"psychopy.visual.backends.pygletbackend"' in PYINSTALLER_SPEC_TEXT
    assert '"psychopy.visual.backends.glfwbackend"' in PYINSTALLER_SPEC_TEXT
    assert '"psychopy.visual.line"' in PYINSTALLER_SPEC_TEXT
    assert "Could not collect PyInstaller submodules" in PYINSTALLER_SPEC_TEXT
    assert "Could not copy PyInstaller package metadata" in PYINSTALLER_SPEC_TEXT


def test_build_exe_fails_on_stale_installed_package_metadata() -> None:
    assert "Assert-PackageMetadataVersion" in BUILD_EXE_TEXT
    assert "Assert-BundledPackageMetadataVersion" in BUILD_EXE_TEXT
    assert "m.version('fpvs-studio')" in BUILD_EXE_TEXT
    assert "Package version drift before PyInstaller build" in BUILD_EXE_TEXT


def test_installer_removes_stale_fpvs_studio_metadata_before_update() -> None:
    assert "[InstallDelete]" in INNO_SCRIPT_TEXT
    assert r'Name: "{app}\_internal\fpvs_studio-*.dist-info"' in INNO_SCRIPT_TEXT
    assert r'Name: "{app}\pyproject.toml"' in INNO_SCRIPT_TEXT


def test_installer_build_validates_bundle_and_runs_packaged_smoke() -> None:
    assert "[switch]$SkipSmoke" in BUILD_INSTALLER_TEXT
    assert "Assert-BundleInput" in BUILD_INSTALLER_TEXT
    assert "dist\\FPVS Studio\\_internal" in BUILD_INSTALLER_TEXT
    assert (
        'Get-ChildItem -Path $BundleInternalPath -Directory -Filter "fpvs_studio-*.dist-info"'
        in BUILD_INSTALLER_TEXT
    )
    assert "Running packaged app smoke check before installer build" in BUILD_INSTALLER_TEXT
    assert "Invoke-PackagedSmoke" in BUILD_INSTALLER_TEXT
    assert "$SmokePackagedAppScript" not in BUILD_RELEASE_TEXT


def test_packaged_smoke_checks_runtime_dependency_imports() -> None:
    assert "_isolate_psychopy_user_dirs" in PACKAGED_SMOKE_TEXT
    assert '"APPDATA"' in PACKAGED_SMOKE_TEXT
    assert '"LOCALAPPDATA"' in PACKAGED_SMOKE_TEXT
    assert "runtime_dependencies_ok" in PACKAGED_SMOKE_TEXT
    assert "runtime_dependency_report" in PACKAGED_SMOKE_TEXT
    assert '"psychopy.visual.backends.pygletbackend"' in PACKAGED_SMOKE_TEXT
    assert '"psychopy.visual.backends.glfwbackend"' in PACKAGED_SMOKE_TEXT
    assert '"psychtoolbox"' in PACKAGED_SMOKE_TEXT
    assert '"sounddevice"' in PACKAGED_SMOKE_TEXT
