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
    assert "__version__ = version(\"fpvs-studio\")" in PACKAGE_INIT_TEXT
    assert "__version__ = \"0.1.0\"" not in PACKAGE_INIT_TEXT
    assert __version__ == pyproject_match.group(1)


def test_default_install_requires_pyside6_but_keeps_psychopy_optional() -> None:
    dependencies_block = _extract_list_assignment("dependencies").lower()
    dev_dependencies_block = _extract_list_assignment("dev").lower()
    packaging_dependencies_block = _extract_list_assignment("packaging").lower()
    assert "psychopy" not in dependencies_block
    assert "pyside6" in dependencies_block
    assert "psychopy" in _extract_list_assignment("engine").lower()
    assert "pytest-qt" in dev_dependencies_block
    assert "pytest-timeout" in dev_dependencies_block
    assert "pyinstaller" in packaging_dependencies_block


def test_pyinstaller_includes_psychopy_visual_backends() -> None:
    assert '_collect_submodules("psychopy.visual.backends")' in PYINSTALLER_SPEC_TEXT
    assert '"psychopy.visual.backends.pygletbackend"' in PYINSTALLER_SPEC_TEXT
    assert '"psychopy.visual.backends.glfwbackend"' in PYINSTALLER_SPEC_TEXT
