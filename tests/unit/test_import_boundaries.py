"""Import-boundary tests."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
import sys


def test_core_imports_do_not_pull_in_psychopy() -> None:
    for module_name in list(sys.modules):
        if module_name == "psychopy" or module_name.startswith("psychopy."):
            sys.modules.pop(module_name, None)

    importlib.import_module("fpvs_studio.core.run_spec")
    importlib.import_module("fpvs_studio.core.session_plan")
    importlib.import_module("fpvs_studio.core.compiler")
    importlib.import_module("fpvs_studio.core.execution")
    importlib.import_module("fpvs_studio.runtime.launcher")
    importlib.import_module("fpvs_studio.runtime.fixation")
    importlib.import_module("fpvs_studio.runtime.preflight")
    importlib.import_module("fpvs_studio.preprocessing.importer")

    assert all(
        module_name != "psychopy" and not module_name.startswith("psychopy.")
        for module_name in sys.modules
    )


def test_psychopy_imports_are_confined_to_engines_package() -> None:
    project_root = Path(__file__).resolve().parents[2]
    violations: list[str] = []

    for path in (project_root / "src" / "fpvs_studio").rglob("*.py"):
        if "engines" in path.parts:
            continue
        module = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module] if node.module is not None else []
            else:
                continue
            if any(name == "psychopy" or name.startswith("psychopy.") for name in names):
                violations.append(path.relative_to(project_root).as_posix())
                break

    assert violations == []
