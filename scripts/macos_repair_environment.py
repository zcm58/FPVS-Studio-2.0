"""Run from PyCharm to repair its Studio environment, or pass --check to diagnose only."""

from __future__ import annotations

import argparse
import logging
import platform
import subprocess
import sys
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
for raw in distribution("fpvs-studio").requires or []:
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


def validate_environment(repo_root: Path) -> str:
    """Require the interpreter selected for this checkout; never silently switch it."""

    _LOGGER.info("Studio checkout: %s", repo_root)
    _LOGGER.info("Python executable: %s", sys.executable)
    _LOGGER.info("Python version: %s; CPU: %s", platform.python_version(), platform.machine())
    _LOGGER.info("Environment: %s", sys.prefix)
    for relative in ("pyproject.toml", "requirements-macos.txt", "src/fpvs_studio/app/main.py"):
        if not (repo_root / relative).is_file():
            raise ValueError(
                f"Missing {relative}. Keep this helper in scripts/ inside the complete Studio "
                "checkout, alongside its original dependency files."
            )
    if sys.platform != "darwin":
        raise ValueError("This helper is for macOS source installations.")
    expected = expected_environment(repo_root)
    expected_python = expected / "bin/python"
    _LOGGER.info("Setup Mac environment: %s", expected_python)
    if sys.version_info[:2] != (3, 10):
        raise ValueError(
            "Studio requires Python 3.10. Run Setup Mac.command, then select "
            f"{expected_python} for both Studio and this helper in PyCharm."
        )
    if (not expected_python.is_file() or not (expected / "pyvenv.cfg").is_file()):
        raise ValueError(
            "The checkout's environment is missing or incomplete. Run Setup Mac.command."
        )
    if (sys.prefix == sys.base_prefix
            or Path(sys.prefix).resolve() != expected.resolve()):
        raise ValueError(
            "PyCharm is using a different interpreter from Setup Mac. Select "
            f"{expected_python} in BOTH the Studio and helper run configurations, then retry. "
            "No packages were changed."
        )
    native = _native_architecture()
    if native not in ("arm64", "x86_64") or platform.machine() != native:
        raise ValueError(
            f"Python CPU {platform.machine()} does not match the native Mac CPU {native}. "
            "Run Setup Mac.command and follow its environment guidance."
        )
    # Resolving a venv executable symlink would install into its base interpreter.
    return sys.executable


def _run(
    python: str, arguments: list[str], repo_root: Path, *, timeout: int | None = None,
) -> int:
    # Isolate from PyCharm's injected PYTHONPATH and user-site packages. Keep pip's
    # network/index configuration available, just as the existing Mac setup does.
    return subprocess.run(
        [python, "-I", *arguments], cwd=repo_root, check=False, timeout=timeout,
    ).returncode


def repair_environment(repo_root: Path, *, check_only: bool = False) -> int:
    python = validate_environment(repo_root)
    if not check_only:
        _LOGGER.info(
            "Installing into the environment shown above. Close Studio before running this."
        )
        if _run(python, ["-m", "pip", "--version"], repo_root, timeout=60) != 0:
            _LOGGER.info("Restoring pip in this virtual environment...")
            if _run(python, ["-m", "ensurepip", "--upgrade"], repo_root) != 0:
                _LOGGER.error(
                    "Could not restore pip. Run Setup Mac.command and retain its error log."
                )
                return 1
        commands = (
            ["-m", "pip", "install", "--upgrade", "pip>=25,<27"],
            ["-m", "pip", "install", "--requirement", "requirements-macos.txt"],
        )
        for command in commands:
            _LOGGER.info("Installing %s", " ".join(command[3:]))
            if _run(python, command, repo_root) != 0:
                _LOGGER.error(
                    "Installation failed; the environment has not passed verification. "
                    "Keep the error above. For missing Apple/Rust/OpenSSL build tools, "
                    "rerun Setup Mac.command."
                )
                return 1
    _LOGGER.info("Checking dependency consistency...")
    dependencies_ok = _run(python, ["-m", "pip", "check"], repo_root, timeout=120) == 0
    _LOGGER.info("Checking the installed Studio source, dependency versions and engine imports...")
    imports_ok = _run(python, ["-c", ENGINE_PROBE, str(repo_root)], repo_root, timeout=120) == 0
    if not dependencies_ok or not imports_ok:
        _LOGGER.error(
            "Environment checks failed. Copy the output above, including the first error and "
            "any chained traceback. A separately installed PsychoPy app does not supply "
            "packages to this virtual environment."
        )
        return 1
    _LOGGER.info("Environment checks passed. Restart Studio with this same Python interpreter.")
    _LOGGER.info("Run Test/Pilot again; this import check does not verify display refresh timing.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check without installing packages")
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
