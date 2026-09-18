"""Import-boundary tests."""

from __future__ import annotations

import ast
import importlib
import sys
from importlib.util import resolve_name
from pathlib import Path

import pytest

# Package guides remain authoritative; these are explicit forbidden dependencies,
# not a blanket DAG rule (core and preprocessing legitimately share contracts).
_FORBIDDEN_INTERNAL_IMPORTS = {
    "core": ("gui", "runtime", "engines", "triggers"),
    "preprocessing": ("gui", "runtime", "engines", "triggers", "core.run_spec"),
    "runtime": ("gui", "core.compiler", "core.models.ProjectFile"),
    "engines": ("gui", "core.compiler", "core.models.ProjectFile"),
    "updates": ("gui", "runtime", "engines"),
    "library": ("gui", "runtime", "engines", "updates"),
    "support": ("gui", "engines", "core.models"),
}


def _internal_import_violations(source: str, *, package: str) -> list[str]:
    """Resolve absolute/relative imports and qualified aliases without importing code."""
    tree = ast.parse(source)
    bindings: dict[str, str] = {}
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
                bindings[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                module = resolve_name("." * node.level + module, package)
            names.add(module)
            for alias in node.names:
                qualified = f"{module}.{alias.name}"
                names.add(qualified)
                bindings[alias.asname or alias.name] = qualified

    def qualified_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return bindings.get(node.id, "")
        if isinstance(node, ast.Attribute):
            parent = qualified_name(node.value)
            return f"{parent}.{node.attr}" if parent else ""
        return ""

    names.update(qualified_name(node) for node in ast.walk(tree) if isinstance(node, ast.Attribute))
    owner = package.split(".")[1]
    forbidden = [f"fpvs_studio.{name}" for name in _FORBIDDEN_INTERNAL_IMPORTS.get(owner, ())]
    return sorted(name for name in names if any(
        name == prefix or name.startswith(f"{prefix}.") for prefix in forbidden
    ))


def test_documented_internal_dependencies() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "fpvs_studio"
    violations = []
    for owner in _FORBIDDEN_INTERNAL_IMPORTS:
        for path in (root / owner).rglob("*.py"):
            package = ".".join(("fpvs_studio", *path.parent.relative_to(root).parts))
            imports = _internal_import_violations(path.read_text(encoding="utf-8"), package=package)
            for name in imports:
                violations.append(f"{path.relative_to(root)} imports {name}")
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize(("package", "source"), [
    ("core", "from fpvs_studio.runtime import launcher"),
    ("preprocessing", "from ..core.run_spec import RunSpec"),
    ("runtime", "from fpvs_studio.core.models import ProjectFile as EditableProject"),
    ("runtime", "from ..core import models as m\nvalue = m.ProjectFile"),
    ("engines", "import fpvs_studio.core.models\nvalue = fpvs_studio.core.models.ProjectFile"),
    ("updates", "from .. import runtime"),
    ("library", "import fpvs_studio.updates.cache"),
    ("support", "from ..core import models"),
])
def test_dependency_audit_rejects_forbidden_imports(package, source) -> None:
    assert _internal_import_violations(source, package=f"fpvs_studio.{package}")


@pytest.mark.parametrize(("package", "source"), [
    ("core", "from ..preprocessing.models import StimulusManifest"),
    ("preprocessing", "from ..core.models import StimulusSet"),
    ("runtime", "from ..core.models import ParticipantMetadata"),
    ("runtime", "from ..core.run_spec import RunSpec"),
    ("engines", "from ..core.execution import RunExecutionSummary"),
    ("updates", "from .models import UpdateError"),
    ("support", "from ..core.paths import filesystem_path"),
])
def test_dependency_audit_preserves_allowed_contracts(package, source) -> None:
    assert not _internal_import_violations(source, package=f"fpvs_studio.{package}")


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
    importlib.import_module("fpvs_studio.support.models")
    importlib.import_module("fpvs_studio.support.storage")
    importlib.import_module("fpvs_studio.support.diagnostics")
    importlib.import_module("fpvs_studio.support.client")

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
