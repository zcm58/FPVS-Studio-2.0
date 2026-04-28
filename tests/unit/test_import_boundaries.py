"""Import-boundary tests."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


def _clear_imports(package_name: str) -> None:
    for module_name in list(sys.modules):
        if module_name == package_name or module_name.startswith(f"{package_name}."):
            sys.modules.pop(module_name, None)


def _find_import_violations(*, package_name: str, allowed_package: str) -> list[str]:
    project_root = Path(__file__).resolve().parents[2]
    violations: list[str] = []

    for path in (project_root / "src" / "fpvs_studio").rglob("*.py"):
        if allowed_package in path.parts:
            continue
        module = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module] if node.module is not None else []
            else:
                continue
            if any(name == package_name or name.startswith(f"{package_name}.") for name in names):
                violations.append(path.relative_to(project_root).as_posix())
                break

    return violations


def test_backend_imports_do_not_pull_in_optional_gui_or_engine_dependencies() -> None:
    _clear_imports("psychopy")
    _clear_imports("PySide6")

    importlib.import_module("fpvs_studio.app.main")
    importlib.import_module("fpvs_studio.core.run_spec")
    importlib.import_module("fpvs_studio.core.session_plan")
    importlib.import_module("fpvs_studio.core.compiler")
    importlib.import_module("fpvs_studio.core.execution")
    importlib.import_module("fpvs_studio.runtime.launcher")
    importlib.import_module("fpvs_studio.runtime.fixation")
    importlib.import_module("fpvs_studio.runtime.preflight")
    importlib.import_module("fpvs_studio.preprocessing.importer")

    assert all(
        module_name != "psychopy"
        and not module_name.startswith("psychopy.")
        and module_name != "PySide6"
        and not module_name.startswith("PySide6.")
        for module_name in sys.modules
    )


def test_psychopy_imports_are_confined_to_engines_package() -> None:
    violations = _find_import_violations(package_name="psychopy", allowed_package="engines")

    assert violations == []


def test_pyside6_imports_are_confined_to_gui_package() -> None:
    violations = _find_import_violations(package_name="PySide6", allowed_package="gui")

    assert violations == []
