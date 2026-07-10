"""Explicit Qt-test registry parsing and completeness checks."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

QT_TEST_REGISTRY_PATH = Path("tests/qt_test_files.txt")
QT_TESTS_ENV_VAR = "FPVS_ALLOW_QT_TESTS"

_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})
_QT_TEST_INDICATORS = (
    re.compile(r"\bqtbot\b"),
    re.compile(r"\bqapp\b"),
    re.compile(r"\bQApplication\b"),
    re.compile(r"\bpytestqt\b"),
    re.compile(r"QT_QPA_PLATFORM"),
    re.compile(r"pytest\.mark\.qt\b"),
)


def _imports_pyside6(source: str) -> bool:
    """Return whether source contains a real PySide6 import, not just prose."""

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            module_names = (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module_names = (node.module,) if node.module else ()
        else:
            continue
        if any(name == "PySide6" or name.startswith("PySide6.") for name in module_names):
            return True
    return False


def qt_tests_requested(*, cli_opt_in: bool, environ: Mapping[str, str]) -> bool:
    """Return whether this run explicitly opted into Qt test collection."""

    return cli_opt_in or environ.get(QT_TESTS_ENV_VAR, "").strip().lower() in _TRUTHY_VALUES


def load_qt_test_registry(repo_root: Path) -> frozenset[str]:
    """Load and validate the sorted repository-relative Qt test registry."""

    registry_path = repo_root / QT_TEST_REGISTRY_PATH
    entries = [
        line.strip().replace("\\", "/")
        for line in registry_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not entries:
        raise ValueError(f"Qt test registry is empty: {registry_path}")
    if entries != sorted(set(entries)):
        raise ValueError(f"Qt test registry must contain unique, sorted paths: {registry_path}")

    resolved_root = repo_root.resolve()
    for entry in entries:
        candidate = (resolved_root / entry).resolve()
        try:
            candidate.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError(f"Qt test registry path escapes the repository: {entry}") from exc
        if not entry.startswith("tests/") or candidate.suffix != ".py":
            raise ValueError(f"Qt test registry must name a Python test under tests/: {entry}")
        if not candidate.is_file() or not candidate.name.startswith("test_"):
            raise ValueError(f"Qt test registry path does not name a test module: {entry}")
    return frozenset(entries)


def repo_relative_path(path: Path, repo_root: Path) -> str | None:
    """Return a normalized repository-relative path, or ``None`` if external."""

    candidate = path if path.is_absolute() else repo_root / path
    try:
        return candidate.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None


def requested_registered_qt_files(
    arguments: Iterable[str],
    *,
    repo_root: Path,
    registry: frozenset[str],
) -> frozenset[str]:
    """Return registered files named by explicit pytest file, node, or directory args."""

    requested: set[str] = set()
    for argument in arguments:
        if argument.startswith("-"):
            continue
        path_argument = argument.split("::", maxsplit=1)[0]
        relative_path = repo_relative_path(Path(path_argument), repo_root)
        if relative_path is None:
            continue
        if relative_path in registry:
            requested.add(relative_path)
            continue
        prefix = f"{relative_path.rstrip('/')}/"
        requested.update(entry for entry in registry if entry.startswith(prefix))
    return frozenset(requested)


def find_qt_test_files(repo_root: Path) -> frozenset[str]:
    """Find GUI tests and other test modules containing a known Qt indicator."""

    detected: set[str] = set()
    tests_root = repo_root / "tests"
    for path in tests_root.rglob("test_*.py"):
        relative_path = path.relative_to(repo_root).as_posix()
        source = path.read_text(encoding="utf-8", errors="replace")
        if (
            relative_path.startswith("tests/gui/")
            or _imports_pyside6(source)
            or any(pattern.search(source) for pattern in _QT_TEST_INDICATORS)
        ):
            detected.add(relative_path)
    return frozenset(detected)


def registry_mismatches(
    repo_root: Path,
    registry: frozenset[str],
) -> tuple[frozenset[str], frozenset[str]]:
    """Return candidate files missing from the registry and stale registry entries."""

    detected = find_qt_test_files(repo_root)
    return detected - registry, registry - detected
