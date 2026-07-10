"""Run the smallest safe verification bundle for an FPVS Studio change."""

from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / ".agents" / "verification.toml"
QT_OPT_IN_ENV = "FPVS_ALLOW_QT_TESTS"
SUPPORTED_PYTHON = (3, 10)
KNOWN_CHECKS = frozenset({"docs-hygiene", "gc"})


@dataclass(frozen=True)
class VerificationScope:
    """Machine-readable routing for one repository responsibility."""

    name: str
    checks: tuple[str, ...]
    tests: tuple[str, ...]
    ci_tests: tuple[str, ...]
    include: tuple[str, ...]
    manual_smoke: tuple[str, ...]


def resolve_repo_python(repo_root: Path = REPO_ROOT) -> Path:
    """Prefer .venv3.10, then .venv, then the current Python 3.10."""

    for environment in (".venv3.10", ".venv"):
        for suffix in (Path("Scripts/python.exe"), Path("bin/python")):
            candidate = repo_root / environment / suffix
            if candidate.is_file():
                return candidate.resolve()
    if sys.version_info[:2] != SUPPORTED_PYTHON:
        version = ".".join(map(str, sys.version_info[:2]))
        raise RuntimeError(
            "FPVS Studio verification requires Python 3.10; "
            f"found {version} at {sys.executable}. Create .venv3.10 or .venv."
        )
    return Path(sys.executable).resolve()


def resolve_powershell() -> str:
    """Return the available PowerShell executable used by existing audits."""

    executable = shutil.which("pwsh") or shutil.which("powershell")
    if executable is None:
        raise RuntimeError("PowerShell is required to run FPVS Studio harness audits.")
    return executable


def _string_tuple(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"verification field {field} must be a string array")
    return tuple(value)


def load_scopes(
    config_path: Path = CONFIG_PATH,
) -> tuple[dict[str, VerificationScope], Path]:
    """Load the verification routing map and Qt registry location."""

    with config_path.open("rb") as handle:
        payload = tomllib.load(handle)
    if payload.get("version") != 1:
        raise ValueError(".agents/verification.toml must declare version = 1")
    raw_scopes = payload.get("scopes")
    if not isinstance(raw_scopes, Mapping) or not raw_scopes:
        raise ValueError(".agents/verification.toml has no scopes")

    scopes: dict[str, VerificationScope] = {}
    for name, raw in raw_scopes.items():
        if not isinstance(raw, Mapping):
            raise ValueError(f"verification scope {name!r} must be a table")
        scope_name = str(name)
        scopes[scope_name] = VerificationScope(
            name=scope_name,
            checks=_string_tuple(raw.get("checks"), field=f"{scope_name}.checks"),
            tests=_string_tuple(raw.get("tests"), field=f"{scope_name}.tests"),
            ci_tests=_string_tuple(raw.get("ci_tests"), field=f"{scope_name}.ci_tests"),
            include=_string_tuple(raw.get("include"), field=f"{scope_name}.include"),
            manual_smoke=_string_tuple(
                raw.get("manual_smoke"), field=f"{scope_name}.manual_smoke"
            ),
        )

    registry_value = payload.get("qt_registry")
    if not isinstance(registry_value, str) or not registry_value.strip():
        raise ValueError(".agents/verification.toml must declare qt_registry")
    return scopes, (config_path.parent.parent / registry_value).resolve()


def read_qt_registry(path: Path) -> frozenset[str]:
    """Read normalized test paths requiring explicit Qt opt-in."""

    if not path.is_file():
        raise ValueError(f"Qt test registry does not exist: {path}")
    entries = [
        line.strip().replace("\\", "/")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not entries:
        raise ValueError(f"Qt test registry is empty: {path}")
    if entries != sorted(set(entries)):
        raise ValueError(f"Qt test registry must contain unique, sorted paths: {path}")
    return frozenset(entries)


def _test_candidates(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(path.rglob("test_*.py")) if path.is_dir() else []


def validate_config(
    scopes: Mapping[str, VerificationScope],
    qt_registry_path: Path,
    *,
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    """Return routing errors without executing verification commands."""

    errors: list[str] = []
    try:
        qt_tests = read_qt_registry(qt_registry_path)
    except ValueError as exc:
        return [str(exc)]

    for entry in sorted(qt_tests):
        if not (repo_root / entry).is_file():
            errors.append(f"Qt registry path does not exist: {entry}")

    for scope in scopes.values():
        unknown_checks = sorted(set(scope.checks) - KNOWN_CHECKS)
        for check in unknown_checks:
            errors.append(f"{scope.name}: unknown check: {check}")
        if not scope.include:
            errors.append(f"{scope.name}: include patterns must not be empty")
        for test_path in (*scope.tests, *scope.ci_tests):
            absolute = repo_root / test_path
            if not absolute.exists():
                errors.append(f"{scope.name}: test path does not exist: {test_path}")
        for test_path in scope.tests:
            absolute = repo_root / test_path
            for candidate in _test_candidates(absolute):
                relative = candidate.relative_to(repo_root).as_posix()
                if relative in qt_tests:
                    errors.append(
                        f"{scope.name}: focused local bundle includes Qt test: {relative}"
                    )
    return errors


def _git_lines(repo_root: Path, *arguments: str) -> list[str]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(arguments)} failed")
    return [
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def changed_files(repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    """Return staged, unstaged, and untracked worktree paths."""

    tracked = _git_lines(repo_root, "diff", "--name-only", "HEAD", "--")
    untracked = _git_lines(repo_root, "ls-files", "--others", "--exclude-standard")
    return tuple(sorted(set(tracked) | set(untracked)))


def scope_python_files(
    scope: VerificationScope, paths: Iterable[str]
) -> tuple[str, ...]:
    """Filter changed Python paths through a scope's include patterns."""

    selected: set[str] = set()
    for path in paths:
        normalized = path.replace("\\", "/")
        if normalized.endswith(".py") and any(
            fnmatch.fnmatch(normalized, pattern) for pattern in scope.include
        ):
            selected.add(normalized)
    return tuple(sorted(selected))


def _pytest_command(
    python: Path,
    tests: Sequence[str],
    *,
    allow_qt: bool,
) -> list[str]:
    command = [
        str(python),
        "-m",
        "pytest",
        "--disable-plugin-autoload",
        "-p",
        "pytest_timeout",
    ]
    if allow_qt:
        command.extend(["-p", "pytestqt.plugin", "--allow-qt-tests"])
    command.extend(["-q", *tests])
    return command


def _check_command(check: str, *, powershell: str) -> list[str]:
    if check == "gc":
        return [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/check_gc.ps1",
            "-SkipLineCounts",
            "-SkipHarnessTests",
            "-SkipDocsHygiene",
        ]
    if check == "docs-hygiene":
        return [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "scripts/check_docs_hygiene.ps1",
        ]
    raise ValueError(f"unknown verification check: {check}")


def _changed_python_commands(python: Path, paths: Sequence[str]) -> list[list[str]]:
    python_files = tuple(sorted({path for path in paths if path.endswith(".py")}))
    if not python_files:
        return []
    return [
        [str(python), "-m", "ruff", "check", *python_files],
        [str(python), "-m", "py_compile", *python_files],
    ]


def build_commands(
    scope: VerificationScope,
    *,
    tier: str,
    python: Path,
    powershell: str,
    changed: Sequence[str],
) -> list[list[str]]:
    """Build commands for a focused, precommit, or full-CI tier."""

    if tier == "full-ci" and scope.name == "repo":
        return [
            [str(python), "-m", "ruff", "check", "."],
            [str(python), "-m", "mypy", "src"],
            _check_command("gc", powershell=powershell),
            _check_command("docs-hygiene", powershell=powershell),
            _pytest_command(python, (), allow_qt=True),
        ]

    if tier == "precommit":
        commands = _changed_python_commands(
            python,
            tuple(path.replace("\\", "/") for path in changed),
        )
        commands.extend(
            [
                [str(python), "-m", "mypy", "src"],
                _check_command("gc", powershell=powershell),
                _check_command("docs-hygiene", powershell=powershell),
                _pytest_command(python, ("tests/unit",), allow_qt=False),
            ]
        )
        return commands

    commands = [
        _check_command(check, powershell=powershell) for check in scope.checks
    ]
    commands.extend(
        _changed_python_commands(python, scope_python_files(scope, changed))
    )
    tests = scope.tests
    allow_qt = False
    if tier == "full-ci":
        tests = tuple(dict.fromkeys((*scope.tests, *scope.ci_tests)))
        allow_qt = True
    if tests:
        commands.append(_pytest_command(python, tests, allow_qt=allow_qt))
    return commands


def run_commands(commands: Sequence[Sequence[str]], *, list_only: bool) -> int:
    """Print commands and optionally execute them in order."""

    for command in commands:
        print(f"> {subprocess.list2cmdline(list(command))}", flush=True)
        if list_only:
            continue
        result = subprocess.run(command, cwd=REPO_ROOT, check=False)
        if result.returncode:
            return int(result.returncode)
    return 0


def _qt_opted_in() -> bool:
    return os.environ.get(QT_OPT_IN_ENV, "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def parse_args(
    scopes: Mapping[str, VerificationScope], argv: Sequence[str] | None = None
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=sorted(scopes))
    parser.add_argument(
        "--tier",
        choices=("focused", "precommit", "full-ci"),
        default="focused",
    )
    parser.add_argument("--list", action="store_true", help="Print commands without running them.")
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate verification paths and local-safe test bundles, then exit.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        scopes, registry = load_scopes()
    except (OSError, ValueError) as exc:
        print(f"verification config error: {exc}", file=sys.stderr)
        return 2
    args = parse_args(scopes, argv)
    errors = validate_config(scopes, registry)
    if errors:
        for error in errors:
            print(f"verification config error: {error}", file=sys.stderr)
        return 2
    if args.check_config:
        if args.list or args.scope is not None:
            print(
                "verification error: --check-config cannot be combined with --list or --scope",
                file=sys.stderr,
            )
            return 2
        print(f"Verification config passed: {len(scopes)} scopes")
        return 0
    if args.list and args.scope is None:
        print("Available verification scopes:")
        for scope_name in sorted(scopes):
            print(f"- {scope_name}")
        return 0
    if args.scope is None:
        print("--scope is required unless --check-config is used", file=sys.stderr)
        return 2
    if args.tier == "full-ci" and not args.list and not _qt_opted_in():
        print(
            f"verification error: full-ci requires {QT_OPT_IN_ENV}=1",
            file=sys.stderr,
        )
        return 2

    try:
        python = resolve_repo_python()
        powershell = resolve_powershell()
        commands = build_commands(
            scopes[args.scope],
            tier=args.tier,
            python=python,
            powershell=powershell,
            changed=changed_files(),
        )
    except (RuntimeError, ValueError) as exc:
        print(f"verification error: {exc}", file=sys.stderr)
        return 2

    print(f"Verification interpreter: {python}")
    result = run_commands(commands, list_only=args.list)
    if scopes[args.scope].manual_smoke:
        print("Manual/visible smoke path:")
        for step in scopes[args.scope].manual_smoke:
            print(f"- {step}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
