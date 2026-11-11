"""One-click macOS environment and PyCharm repair; --check makes no changes."""

from __future__ import annotations

import argparse
import logging
import os
import platform
import subprocess
import sys
import uuid
from pathlib import Path

_LOGGER = logging.getLogger("fpvs_studio.environment")

# Run through the engine boundary in a fresh interpreter after pip finishes.
# An uncaught exception preserves the original cause hidden by the UI's short message.
ENGINE_PROBE = """
import logging
import sys
from importlib.metadata import distribution, version
from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version
import tomli

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("fpvs_studio.environment")
root = Path(sys.argv[1]).resolve()
import fpvs_studio
actual = Path(fpvs_studio.__file__).resolve().parent
expected = (root / "src/fpvs_studio").resolve()
if actual != expected:
    raise RuntimeError(f"Studio imports from {actual}, but this checkout is {expected}.")
if Version(version("fpvs-studio")) != Version(fpvs_studio.__version__):
    raise RuntimeError(
        "Installed Studio metadata is from a different source version. "
        "Run this helper again without --check to refresh the environment."
    )

for name in ("fpvs-studio", "psychopy", "PySide6", "PyQt6", "numpy"):
    logger.info("%s: %s", name, version(name))
with (root / "pyproject.toml").open("rb") as source:
    project = tomli.load(source)["project"]
requirements = list(distribution("fpvs-studio").requires or [])
requirements.extend(project.get("dependencies", []))
for extra in ("dev", "engine"):
    requirements.extend(project["optional-dependencies"][extra])
for raw in requirements:
    requirement = Requirement(raw)
    if requirement.marker and not any(
        requirement.marker.evaluate({"extra": extra}) for extra in ("", "dev", "engine")
    ):
        continue
    installed = version(requirement.name)
    if installed not in requirement.specifier:
        raise RuntimeError(f"{requirement.name} {installed} does not satisfy {requirement}.")

from fpvs_studio.engines.psychopy_loader import load_psychopy_modules
load_psychopy_modules()
logger.info("Studio's PsychoPy engine imports passed. No presentation window was opened.")
"""

INTERPRETER_PROBE = """
import logging
import platform
import sys
from pathlib import Path
logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.info("Selected Python: %s (%s, %s)", sys.executable,
             platform.python_version(), platform.machine())
assert sys.platform == "darwin", "The selected interpreter must run on macOS."
assert sys.version_info[:2] == (3, 10), "Studio requires Python 3.10."
assert sys.prefix != sys.base_prefix, "The selected Python must be a virtual environment."
assert Path(sys.prefix).resolve() == Path(sys.argv[1]).resolve(), "Wrong venv prefix."
assert platform.machine() == sys.argv[2], "Python must match the native Mac CPU."
"""


class EnvironmentInvalidError(ValueError):
    """The checkout environment cannot run Studio and needs to be preserved/rebuilt."""


def expected_environment(repo_root: Path) -> Path:
    """Match Setup Mac.command, including its preservation of incomplete environments."""

    preferred = repo_root / ".venv3.10"
    alternate = repo_root / ".venv"
    if preferred.exists() or preferred.is_symlink():
        return preferred
    if alternate.exists() or alternate.is_symlink():
        return alternate
    return preferred


def _native_architecture() -> str:
    result = subprocess.run(
        ["/usr/sbin/sysctl", "-n", "hw.optional.arm64"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    if result.returncode == 0 and result.stdout.strip() == "1":
        return "arm64"
    return platform.machine()


def validate_checkout(repo_root: Path) -> None:
    _LOGGER.info("Studio checkout: %s", repo_root)
    _LOGGER.info("Helper launched by: %s", sys.executable)
    if sys.platform != "darwin":
        raise ValueError("This helper is for macOS source installations.")
    for relative in (
        "pyproject.toml", "requirements-macos.txt", "src/fpvs_studio/app/main.py",
        "scripts/macos-source.sh", "scripts/macos_pycharm.py",
    ):
        if not (repo_root / relative).is_file():
            raise ValueError(
                f"Missing {relative}. Keep this helper in scripts/ inside the complete Studio "
                "checkout, alongside its original dependency files."
            )


def validate_environment(repo_root: Path) -> str:
    """Probe Setup Mac's interpreter, independently of the Python that launched us."""

    expected = expected_environment(repo_root)
    expected_python = expected / "bin/python"
    _LOGGER.info("Setup Mac environment: %s", expected_python)
    if not expected_python.is_file() or not (expected / "pyvenv.cfg").is_file():
        raise EnvironmentInvalidError("The checkout's environment is missing or incomplete.")
    native = _native_architecture()
    if native not in ("arm64", "x86_64"):
        raise ValueError(f"Unsupported Mac CPU: {native}")
    try:
        result = _run(str(expected_python), ["-c", INTERPRETER_PROBE, str(expected), native],
                      repo_root, timeout=30)
    except OSError as exc:
        raise EnvironmentInvalidError("The checkout's Python executable cannot run.") from exc
    if result != 0:
        raise EnvironmentInvalidError("The checkout's Python version, CPU or venv is incompatible.")
    # Resolving a venv executable symlink would install into its base interpreter.
    return str(expected_python)


def _run(
    python: str, arguments: list[str], repo_root: Path, *, timeout: int | None = None,
) -> int:
    # Isolate from PyCharm's injected PYTHONPATH and user-site packages. Keep pip's
    # network/index configuration available, just as the existing Mac setup does.
    return subprocess.run(
        [python, "-I", *arguments], cwd=repo_root, check=False, timeout=timeout,
    ).returncode


def _backup_environment(repo_root: Path) -> None:
    environment = expected_environment(repo_root)
    if not environment.exists() and not environment.is_symlink():
        return
    root = repo_root.resolve()
    if environment.is_symlink() or environment.parent.resolve() != root:
        raise ValueError("Cannot automatically replace a linked or external environment.")
    tools_root = root / ".fpvs-macos"
    backups = tools_root / "environment-backups"
    if tools_root.is_symlink() or backups.is_symlink():
        raise ValueError("Environment backups must stay inside this checkout.")
    backups.resolve().relative_to(root)
    destination = backups / f"{environment.name}-{uuid.uuid4().hex}"
    destination.resolve().relative_to(root)
    if destination.exists():
        raise ValueError("Environment backup already exists; no environment was moved.")
    backups.mkdir(parents=True, exist_ok=True)
    environment.rename(destination)
    _LOGGER.info("Preserved the previous environment at: %s", destination)


def _run_setup(repo_root: Path) -> bool:
    _LOGGER.info("Running Mac setup to prepare native Python and Studio's engine dependencies...")
    environment = os.environ.copy()
    # Setup normally writes the generated Run configuration. Defer all IDE writes
    # to the closed-IDE finalizer when repair was launched from within PyCharm.
    environment["FPVS_SKIP_PYCHARM_CONFIG"] = "1"
    result = subprocess.run(
        ["/bin/bash", str(repo_root / "scripts/macos-source.sh"), "setup"],
        cwd=repo_root, env=environment, check=False,
    )
    if result.returncode != 0:
        _LOGGER.error("Mac setup failed. Keep the error above; repair has not completed.")
    return result.returncode == 0


def _check_environment(repo_root: Path, python: str) -> bool:
    _LOGGER.info("Checking dependency consistency...")
    dependencies_ok = _run(python, ["-m", "pip", "check"], repo_root, timeout=120) == 0
    _LOGGER.info("Checking the installed Studio source, dependency versions and engine imports...")
    imports_ok = _run(python, ["-c", ENGINE_PROBE, str(repo_root)], repo_root, timeout=120) == 0
    return dependencies_ok and imports_ok


def _configure_pycharm(repo_root: Path, python: str, *, check_only: bool = False) -> str:
    # Run IDE code under the verified Python, even if PyCharm launched us with an
    # older interpreter. Preserve the original live-IDE interpreter for diagnosis.
    result = subprocess.run(
        [python, "-I", str(repo_root / "scripts/macos_pycharm.py"), str(repo_root), python,
         "--check" if check_only else "--repair", "--repair-parent-pid", str(os.getpid()),
         "--repair-launch-prefix", sys.prefix, "--repair-launch-version",
         f"{sys.version_info[0]}.{sys.version_info[1]}"],
        cwd=repo_root, check=False, timeout=120,
    )
    if result.returncode == 0:
        return "ready"
    if result.returncode == 10:
        return "pending"
    raise ValueError("PyCharm configuration did not complete. See its error above.")


def repair_environment(repo_root: Path, *, check_only: bool = False) -> int:
    validate_checkout(repo_root)
    repaired = False
    try:
        python = validate_environment(repo_root)
    except EnvironmentInvalidError:
        if check_only:
            raise
        _LOGGER.info("Preparing a compatible environment automatically...")
        _backup_environment(repo_root)
        if not _run_setup(repo_root):
            return 1
        python = validate_environment(repo_root)
        repaired = True

    healthy = _check_environment(repo_root, python)
    if not healthy and not check_only:
        _LOGGER.info("Repairing Setup Mac's environment...")
        if _run(python, ["-m", "pip", "--version"], repo_root, timeout=60) != 0:
            if _run(python, ["-m", "ensurepip", "--upgrade"], repo_root) != 0:
                _LOGGER.error("Could not restore pip in the selected environment.")
                return 1
        if not _run_setup(repo_root):
            return 1
        healthy = _check_environment(repo_root, python)
        repaired = True
        if not healthy:
            _LOGGER.info(
                "Dependencies remain broken; preserving this venv and rebuilding it once..."
            )
            _backup_environment(repo_root)
            if not _run_setup(repo_root):
                return 1
            python = validate_environment(repo_root)
            healthy = _check_environment(repo_root, python)
    if not healthy:
        _LOGGER.error(
            "Environment checks failed. Copy the output above, including the first error and "
            "any chained traceback. A separately installed PsychoPy app does not supply "
            "packages to this virtual environment."
        )
        return 1
    result = _configure_pycharm(repo_root, python, check_only=check_only)
    if result == "pending":
        _LOGGER.info(
            "Dependencies passed. PyCharm configuration is finishing in a separate process; "
            "wait for its completion message."
        )
        return 0
    if check_only:
        _LOGGER.info(
            "Checks passed: Studio's environment, engine and PyCharm configuration are ready."
        )
    else:
        _LOGGER.info(
            "%s Studio's environment, engine and PyCharm are ready.",
            "Repair complete." if repaired else "Checks complete.",
        )
    _LOGGER.info("Run Test/Pilot again; this import check does not verify display refresh timing.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="check without installing or configuring",
    )
    arguments = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    repo_root = Path(__file__).resolve().parents[1]
    try:
        return repair_environment(repo_root, check_only=arguments.check)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        _LOGGER.error("Environment check stopped: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
