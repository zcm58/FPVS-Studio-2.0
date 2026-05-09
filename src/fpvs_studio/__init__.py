"""FPVS Studio package surface for the Phase 5 desktop application. It groups engine-
neutral core contracts, preprocessing, runtime, engines, and the PySide6 GUI under one
namespace. The package itself is only an import boundary; protocol ownership stays in
core models and compiled artifacts."""

from importlib.metadata import version
from pathlib import Path

__all__ = ["__version__"]


def _source_tree_version() -> str | None:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if not pyproject_path.is_file():
        return None

    in_project_table = False
    project_name: str | None = None
    project_version: str | None = None
    for raw_line in pyproject_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_project_table = line == "[project]"
            continue
        if not in_project_table or "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        if key == "name":
            project_name = value.strip('"')
        elif key == "version":
            project_version = value.strip('"')

    if project_name != "fpvs-studio":
        return None
    return project_version


__version__ = _source_tree_version() or version("fpvs-studio")
