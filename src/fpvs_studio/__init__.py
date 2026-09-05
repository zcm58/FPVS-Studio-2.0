"""FPVS Studio package surface for the Phase 5 desktop application. It groups engine-
neutral core contracts, preprocessing, runtime, engines, and the PySide6 GUI under one
namespace. The package itself is only an import boundary; protocol ownership stays in
core models and compiled artifacts."""

import sys
from importlib.metadata import distributions, version
from pathlib import Path

from packaging.version import Version

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


def _installed_version() -> str:
    """Resolve frozen metadata without mistaking retained empty directories for it."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is None:
        return version("fpvs-studio")

    versions = []
    for distribution in distributions(path=[str(bundle_root)]):
        name = distribution.metadata["Name"] or ""
        if name.lower().replace("_", "-") != "fpvs-studio":
            continue
        value = distribution.version
        if not value:
            raise RuntimeError("Bundled FPVS Studio metadata has no version.")
        Version(value)
        versions.append(value)
    if len(versions) != 1:
        raise RuntimeError("Expected exactly one complete bundled FPVS Studio distribution.")
    return versions[0]


__version__ = _source_tree_version() or _installed_version()
