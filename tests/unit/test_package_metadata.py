"""Packaging metadata regression guards."""

from __future__ import annotations

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_TEXT = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")


def _extract_list_assignment(name: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(name)} = \[(.*?)^\]",
        PYPROJECT_TEXT,
    )
    if match is None:
        raise AssertionError(f"Could not find list assignment for '{name}'.")
    return match.group(1)


def test_pyproject_targets_python_310_only() -> None:
    assert 'requires-python = ">=3.10,<3.11"' in PYPROJECT_TEXT
    assert '"Programming Language :: Python :: 3 :: Only"' in PYPROJECT_TEXT
    assert '"Programming Language :: Python :: 3.10"' in PYPROJECT_TEXT


def test_default_install_requires_pyside6_but_keeps_psychopy_optional() -> None:
    dependencies_block = _extract_list_assignment("dependencies").lower()
    dev_dependencies_block = _extract_list_assignment("dev").lower()
    assert "psychopy" not in dependencies_block
    assert "pyside6" in dependencies_block
    assert "psychopy" in _extract_list_assignment("engine").lower()
    assert "pytest-qt" in dev_dependencies_block
    assert "pytest-timeout" in dev_dependencies_block
