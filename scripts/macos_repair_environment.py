"""One-click macOS repair with diagnostics; --check leaves environment/IDE settings unchanged."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import platform
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

_LOGGER = logging.getLogger("fpvs_studio.environment")
_DIAGNOSTICS: _Diagnostics | None = None


def _redact(text: str) -> str:
    """Scrub credentials and personal paths before console/file/report formatting."""
    text = re.sub(r"(?i)(https?://)[^\s/@]+(?::[^\s/@]*)?@", r"\1[redacted]@", text)
    text = re.sub(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=\-]+", r"\1 [redacted]", text)
    text = re.sub(
        r"(?im)((?:--)?(?:[\w-]*(?:token|password|secret|api[_-]?key)[\w-]*)"
        r"[\"']?[ \t]*(?:[:=][ \t]*|[ \t]+))"
        r"(?:\[redacted\]|\"(?:\\[^\r\n]|[^\"\\\r\n])*(?:\"|$)"
        r"|'(?:\\[^\r\n]|[^'\\\r\n])*(?:'|$)|[^\s&\"',;}\]]+)",
        r"\1[redacted]", text,
    )
    text = re.sub(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", text)
    text = re.sub(r"(?i)(/verify#)[^\s]+", r"\1[redacted]", text)
    text = re.sub(r"(?i)(pycharm-repair[/\\])[a-f0-9]{32}", r"\1[repair-job]", text)
    text = re.sub(r"(?i)(?:/Users/|/home/|[A-Z]:[\\/]Users[\\/])[^/\\\r\n]+", "<home>", text)
    return text


def _private_json(path: Path, data: dict) -> None:
    """Atomically retain private local state before any delivery side effect."""
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Diagnostic state must not use linked paths.")
    temporary = path.with_name(f".{path.name}-{uuid.uuid4().hex}.tmp")
    try:
        with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                       "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _owned_path(root: Path, path: Path) -> Path:
    """Only helper-owned files inside this checkout, with no linked ancestors."""
    base = root.absolute() / ".fpvs-macos"
    candidate = path.absolute() if path.is_absolute() else (root / path).absolute()
    candidate.relative_to(base)
    for item in (candidate, *candidate.parents):
        if item == root.absolute():
            break
        if item.is_symlink():
            raise ValueError("Diagnostic paths must not follow links.")
    candidate.resolve().relative_to(base.resolve())
    return candidate


class _DiagnosticFormatter(logging.Formatter):
    @staticmethod
    def converter(timestamp: float | None) -> time.struct_time:
        return time.gmtime(timestamp)

    def format(self, record: logging.LogRecord) -> str:
        # Formatting first also covers chained exceptions and subprocess tracebacks.
        return _redact(super().format(record))


class _DiagnosticFileHandler(logging.StreamHandler):
    failed = False

    def handleError(self, record: logging.LogRecord) -> None:
        self.failed = True


class _Diagnostics:
    def __init__(self, root: Path, log_path: Path | None = None) -> None:
        self.root = root
        self.started = time.monotonic()
        self.job_log: Path | None = None
        self.pending = False
        if log_path is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            directory = _owned_path(root, root / ".fpvs-macos/diagnostics" / (
                f"{stamp}-{uuid.uuid4().hex}"
            ))
            directory.mkdir(parents=True, mode=0o700)
            log_path = directory / "repair.log"
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        else:
            log_path = _owned_path(root, log_path)
            flags = os.O_WRONLY | os.O_APPEND
        self.path = log_path
        self.stream = os.fdopen(os.open(log_path, flags, 0o600), "a", encoding="utf-8")
        self.file_handler = _DiagnosticFileHandler(self.stream)
        self.file_handler.setFormatter(_DiagnosticFormatter(
            "%(asctime)sZ %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S",
        ))
        self.console_handler = logging.StreamHandler()
        self.console_handler.setFormatter(_DiagnosticFormatter("%(message)s"))
        self.previous_level = _LOGGER.level
        self.previous_propagate = _LOGGER.propagate
        _LOGGER.setLevel(logging.INFO)
        _LOGGER.propagate = False
        _LOGGER.addHandler(self.file_handler)
        _LOGGER.addHandler(self.console_handler)

    def close(self) -> None:
        _LOGGER.removeHandler(self.file_handler)
        self.file_handler.close()
        try:
            self.stream.close()
        except OSError:
            self.file_handler.failed = True
        if self.file_handler.failed:
            _LOGGER.error("Could not save the complete diagnostic log. Copy the PyCharm console.")
        _LOGGER.removeHandler(self.console_handler)
        self.console_handler.close()
        _LOGGER.setLevel(self.previous_level)
        _LOGGER.propagate = self.previous_propagate

    def observe(self, line: str) -> None:
        if "Repair log: " in line:
            path = Path(line.rsplit("Repair log: ", 1)[1].strip())
            path = _owned_path(self.root, path)
            if (path.parent != self.root / ".fpvs-macos/pycharm-repair"
                    or not re.fullmatch(r"[a-f0-9]{32}\.log", path.name)):
                raise ValueError("Unrecognized PyCharm repair log.")
            self.job_log = path

    def command(self, command: list[str], *, cwd: Path, check: bool = False,
                timeout: int | None = None, env: dict[str, str] | None = None
                ) -> subprocess.CompletedProcess:
        # Avoid dumping inline probe source, environment values or capability arguments.
        label = ("Python probe" if "-c" in command else " ".join(command[:4]))
        started = time.monotonic()
        _LOGGER.info("START %s (timeout: %s)", label, timeout or "setup managed")
        child = subprocess.Popen(
            command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            start_new_session=True,
        )
        errors: list[Exception] = []

        def drain() -> None:
            assert child.stdout is not None
            try:
                # Bound a single pip progress line; universal newlines handle carriage returns.
                while line := child.stdout.readline(16384):
                    self.observe(line)
                    _LOGGER.info("%s", line.rstrip())
            except Exception as exc:
                errors.append(exc)
            finally:
                child.stdout.close()

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        try:
            code = child.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            # Only our newly created process group, including children of setup/pip.
            _stop_child(child, force=False)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _stop_child(child, force=True)
                child.wait(timeout=5)
            _LOGGER.error("STOP %s after %.1fs", label, time.monotonic() - started)
            raise
        finally:
            reader.join(timeout=5)
        if reader.is_alive():
            raise ValueError("A child kept its output pipe open; diagnostic capture is incomplete.")
        if errors:
            raise ValueError("Could not capture all subprocess diagnostics.") from errors[0]
        _LOGGER.info("END %s: exit=%s, elapsed=%.1fs", label, code, time.monotonic() - started)
        return subprocess.CompletedProcess(command, code)


def _stop_child(child: subprocess.Popen, *, force: bool) -> None:
    try:
        if sys.platform == "darwin":
            os.killpg(child.pid, 9 if force else signal.SIGTERM)
        elif force:
            child.kill()
        else:
            child.terminate()
    except ProcessLookupError:
        pass  # The owned process group already exited.


def _command(command: list[str], *, cwd: Path, check: bool = False,
             timeout: int | None = None, env: dict[str, str] | None = None
             ) -> subprocess.CompletedProcess:
    if _DIAGNOSTICS is not None:
        return _DIAGNOSTICS.command(command, cwd=cwd, check=check, timeout=timeout, env=env)
    # Preserve inherited output for library callers outside the diagnostic entry point.
    options: dict = {"cwd": cwd, "check": check}
    if env is not None:
        options["env"] = env
    if timeout is not None:
        options["timeout"] = timeout
    return subprocess.run(command, **options)


def _source_version(root: Path) -> str:
    try:
        source = (root / "pyproject.toml").read_text(encoding="utf-8")
        project = re.search(r"(?ms)^\[project\]\s*\n(.*?)(?=^\[|\Z)", source)
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', project[1] if project else "")
        return match[1] if match else "unknown"
    except OSError:
        return "unknown"


def _log_context(root: Path, check_only: bool) -> None:
    _LOGGER.info("FPVS Studio macOS repair | UTC %s | version %s | check_only=%s",
                 datetime.now(timezone.utc).isoformat(), _source_version(root), check_only)
    _LOGGER.info("Host: %s %s; CPU=%s; macOS=%s", platform.system(), platform.release(),
                 platform.machine(), platform.mac_ver()[0])
    _LOGGER.info("Launcher Python: %s; version=%s; prefix=%s; base_prefix=%s; PID=%s",
                 sys.executable, sys.version.replace("\n", " "), sys.prefix,
                 sys.base_prefix, os.getpid())
    for name in ("pyproject.toml", "requirements-macos.txt", "scripts/macos_repair_environment.py"):
        source = root / name
        if source.is_file():
            _LOGGER.info("Source SHA256 %s: %s", name,
                         hashlib.sha256(source.read_bytes()).hexdigest())


def _native_dialog(message: str, buttons: tuple[str, ...], default: str) -> str:
    if sys.platform != "darwin":
        return "Close"
    # argv passes text literally; no interpolated AppleScript or shell command.
    script = '''on run argv
set choices to items 3 thru -1 of argv
set answer to display dialog (item 1 of argv) with title "FPVS Studio Repair" ¬
buttons choices default button (item 2 of argv) giving up after 120
if gave up of answer then return "Close"
return button returned of answer
end run'''
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script, message, default, *buttons],
            capture_output=True, text=True, check=False, timeout=130,
        )
        return result.stdout.strip() if result.returncode == 0 else "Close"
    except (OSError, subprocess.SubprocessError):
        _LOGGER.exception("Could not display the report action; the saved log is still available")
        return "Close"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def _finish_diagnostics(root: Path, state_path: Path) -> int:
    """Observe the existing IDE finalizer without changing its ownership or settings."""
    if sys.platform != "darwin":
        raise ValueError("Diagnostic continuation is only supported on macOS.")
    state_path = _owned_path(root, state_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    log = _owned_path(root, Path(state["log"]))
    job = _owned_path(root, Path(state["job_log"]))
    if (log.parent != state_path.parent or log.name != "repair.log"
            or job.parent != root / ".fpvs-macos/pycharm-repair"
            or not re.fullmatch(r"[a-f0-9]{32}\.log", job.name)):
        raise ValueError("Invalid diagnostic continuation.")
    diagnostics = _Diagnostics(root, log)
    outcome = "PyCharm repair completion could not be confirmed."
    code = 1
    try:
        deadline = time.monotonic() + 420
        result_path = _owned_path(root, job.with_suffix(".result.json"))
        claim = _owned_path(root, job.with_suffix(".claim"))
        pid = None
        while time.monotonic() < deadline:
            # The worker writes its receipt before its final cleanup/dialog. Wait
            # for exit so late cleanup failures are included and dialogs don't overlap.
            pid = int(claim.read_text()) if claim.exists() else None
            if pid is not None and not _pid_alive(pid):
                break
            time.sleep(1)
        if job.is_file():
            _LOGGER.info("PyCharm finalizer output:\n%s",
                         job.read_text(encoding="utf-8", errors="replace"))
        if result_path.is_file():
            result = json.loads(result_path.read_text(encoding="utf-8"))
            outcome = str(result.get("message", outcome))
            still_running = pid is not None and _pid_alive(pid)
            job_text = job.read_text(encoding="utf-8", errors="replace") if job.is_file() else ""
            if (result.get("success") is True and pid is not None and not still_running
                    and "Could not release this PyCharm repair request" not in job_text
                    and "Could not retain the PyCharm repair result" not in job_text):
                code = 0
            else:
                outcome = "PyCharm repair did not finish cleanly. See the diagnostic log."
        _LOGGER.info("FINAL outcome: %s (exit=%s)", outcome, code)
    except Exception:
        _LOGGER.exception("Could not collect the final PyCharm repair outcome")
    finally:
        diagnostics.close()
    if diagnostics.file_handler.failed:
        outcome += " Diagnostic log is incomplete; also retain the original PyCharm console."
    _offer_report(log, outcome, str(state["app_version"]))
    return code


def _continue_diagnostics(diagnostics: _Diagnostics) -> None:
    if diagnostics.job_log is None:
        raise ValueError("PyCharm is finishing, but its diagnostic log could not be identified.")
    state_path = diagnostics.path.with_name("continuation.json")
    _private_json(state_path, {
        "log": str(diagnostics.path), "job_log": str(diagnostics.job_log),
        "app_version": _source_version(diagnostics.root),
    })
    # The verified environment survives an IDE restart; the launching interpreter
    # might have been moved into an environment backup during this repair.
    python = expected_environment(diagnostics.root) / "bin/python"
    subprocess.Popen(
        [str(python), "-I", str(Path(__file__).absolute()),
         "--finish-diagnostics", str(state_path)],
        cwd=diagnostics.root, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, start_new_session=True,
    )
    _LOGGER.info("Diagnostic report action will appear after PyCharm finishes restarting.")

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
    return _command(
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
    result = _command(
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
    result = _command(
        [python, "-I", str(repo_root / "scripts/macos_pycharm.py"), str(repo_root), python,
         "--check" if check_only else "--repair", "--repair-parent-pid", str(os.getpid()),
         "--repair-launch-prefix", sys.prefix, "--repair-launch-version",
         f"{sys.version_info[0]}.{sys.version_info[1]}"],
        cwd=repo_root, check=False, timeout=120,
    )
    if result.returncode == 0:
        return "ready"
    if result.returncode == 10:
        if _DIAGNOSTICS is not None:
            _DIAGNOSTICS.pending = True
        return "pending"
    raise ValueError("PyCharm configuration did not complete. See its error above.")


def repair_environment(repo_root: Path, *, check_only: bool = False) -> int:
    validate_checkout(repo_root)
    repaired = False
    try:
        python = validate_environment(repo_root)
    except EnvironmentInvalidError as exc:
        if check_only:
            raise
        _LOGGER.info("Preparing a compatible environment automatically: %s", exc)
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


def _report_bytes(value: dict) -> bytes:
    """Match support.Report's canonical bug-report bytes without optional imports."""
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _report_log(path: Path, limit: int = 256 * 1024) -> str:
    """Keep this repair's environment header and failure tail within a UTF-8 limit."""
    marker = b"\n[Middle log text omitted to fit the diagnostic limit.]\n"
    head_size = min(16 * 1024, limit // 4)
    if path.is_symlink():
        raise ValueError("The diagnostic log cannot be a symbolic link.")
    with path.open("rb") as stream:
        size = stream.seek(0, 2)
        stream.seek(0)
        if size <= limit:
            raw = stream.read(limit)
        else:
            head = stream.read(head_size)
            tail_size = limit - head_size - len(marker)
            stream.seek(size - tail_size)
            raw = head + marker + stream.read(tail_size)
    text = _redact(raw.decode("utf-8", errors="replace"))
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) > limit:
        head_text = encoded[:head_size].decode("utf-8", errors="ignore")
        tail_text = encoded[-(limit - head_size - len(marker)):].decode("utf-8", errors="ignore")
        return head_text + marker.decode() + tail_text
    return text


def _report_payload(log_path: Path, outcome: str, app_version: str) -> dict:
    import platform
    from datetime import datetime, timezone
    from uuid import uuid4

    description = _redact(outcome) or "Environment repair finished; diagnostic report requested."
    return {
        "schema_version": "1", "report_id": str(uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": "macOS environment repair diagnostic report",
        "happened": description.encode("utf-8")[:8000].decode("utf-8", errors="ignore"),
        "steps": "Ran scripts/macos_repair_environment.py in PyCharm on macOS.",
        "expected": "Studio's virtual environment, engine and PyCharm interpreter are ready.",
        "email": "", "app_version": app_version,
        "os_version": f"{platform.system()} {platform.release()}",
        "diagnostics": _report_log(log_path),
    }


def _report_origin() -> str:
    import os

    approved = "https://reports.zack-murphy.com"
    origin = os.environ.get("FPVS_REPORT_SERVICE_URL", approved).strip()
    if not origin:
        raise ValueError("Online reporting is disabled. Copy the diagnostic log instead.")
    if origin != approved:
        raise ValueError("The report endpoint must be the approved HTTPS reporting service.")
    return origin


def _report_request(
    origin: str, method: str, path: str, *, data: bytes | None = None, token: str = "",
) -> dict:
    """Bounded, fixed-origin manual reporting; never echo bodies or credentials."""
    import json
    import time
    from http.client import HTTPException
    from urllib.error import URLError
    from urllib.request import HTTPRedirectHandler, Request, build_opener

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(
            self, req: object, fp: object, code: int, msg: str, headers: object, newurl: str,
        ) -> None:
            return None

    if origin != "https://reports.zack-murphy.com" or not path.startswith("/v1/"):
        raise ValueError("The report endpoint must be the approved HTTPS reporting service.")
    headers = {
        "User-Agent": "FPVS-Studio/1.0", "Accept": "application/json",
        "Content-Type": "application/json", "Accept-Encoding": "identity",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(origin + path, data=data, headers=headers, method=method)
    deadline = time.monotonic() + 30
    try:
        with build_opener(NoRedirect()).open(request, timeout=10) as response:
            if (response.headers.get_content_type() != "application/json"
                    or response.headers.get("Content-Encoding", "identity") != "identity"):
                raise ValueError("Unexpected report response format.")
            raw = bytearray()
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError
                chunk = response.read1(min(4096, 16 * 1024 + 1 - len(raw)))
                if time.monotonic() >= deadline:
                    raise TimeoutError
                raw.extend(chunk)
                if len(raw) > 16 * 1024:
                    raise ValueError("The report response exceeds its limit.")
                if not chunk:
                    break
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("Unexpected report response.")
        return result
    except (OSError, URLError, HTTPException, ValueError, RecursionError):
        raise ValueError(
            "The reporting service could not complete the request. The diagnostic log and "
            "any saved receipt are preserved; check report status before another submission."
        ) from None


def _report_load(path: Path) -> dict | None:
    """A retained receipt is authoritative: malformed state must never cause a resend."""
    import json
    import re
    from uuid import UUID

    if path.is_symlink():
        raise ValueError("The saved report receipt cannot be a symbolic link.")
    if not path.exists():
        return None
    try:
        with path.open("rb") as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError
        draft = json.loads(raw)
        if not isinstance(draft, dict):
            raise ValueError
        report = draft["report"]
        fields = {
            "schema_version", "report_id", "created_at", "title", "happened", "steps",
            "expected", "email", "app_version", "os_version", "diagnostics",
        }
        if (set(report) != fields or any(not isinstance(value, str) for value in report.values())
                or report["schema_version"] != "1"
                or str(UUID(report["report_id"])) != report["report_id"]
                or not report["title"].strip() or len(report["title"]) > 160
                or not report["happened"].strip()
                or len((report["happened"] + report["steps"]
                        + report["expected"]).encode("utf-8")) > 16 * 1024
                or len(report["diagnostics"].encode("utf-8")) > 256 * 1024
                or draft["service_url"] != "https://reports.zack-murphy.com"
                or draft["include_logs"] is not True
                or draft["delivery"] not in ("editing", "uncertain", "received", "submitted")
                or not re.fullmatch(r"[A-Za-z0-9_-]{43}", draft["receipt_token"])):
            raise ValueError
        return draft
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        raise ValueError(
            "The saved report receipt could not be read safely. It was preserved; copy the "
            "diagnostic log instead of starting another submission."
        ) from None


def _report_save(path: Path, draft: dict) -> None:
    import json
    from datetime import datetime, timezone

    draft["updated_at"] = datetime.now(timezone.utc).isoformat()
    if len(json.dumps(draft, ensure_ascii=False).encode("utf-8")) > 1024 * 1024:
        raise ValueError("The diagnostic report is too large to save. Copy the log instead.")
    try:
        _private_json(path, draft)
    except OSError:
        raise ValueError(
            "The report receipt could not be saved. No further upload was attempted. "
            "Keep the diagnostic log; any earlier delivery may need a status check."
        ) from None


def _report_receipt(path: Path, draft: dict, receipt: dict) -> str:
    state = receipt.get("state")
    if (receipt.get("report_id") != draft["report"]["report_id"]
            or state not in ("received", "submitted", "uncertain", "not_received")):
        raise ValueError("The service returned an invalid receipt. Check status before retrying.")
    draft["delivery"] = "editing" if state == "not_received" else state
    _report_save(path, draft)
    messages = {
        "received": "Report received; issue creation is pending. You can check its status later.",
        "submitted": "Error report submitted.",
        "uncertain": "Delivery is uncertain. Use Check Status before another submission.",
        "not_received": "The service confirms this report was not received. You can send it again.",
    }
    return f"{messages[state]}\nReceipt: {draft['report']['report_id']}"


def _send_repair_report(log_path: Path, outcome: str, app_version: str) -> str:
    """Explicit user action only; browser verification precedes the sole upload."""
    import hashlib
    import re
    import secrets
    import time
    import webbrowser
    from urllib.parse import urlencode

    origin = _report_origin()
    path = log_path.with_suffix(".report.json")
    draft = _report_load(path)
    if draft is None:
        draft = {
            "report": _report_payload(log_path, outcome, app_version), "include_logs": True,
            "accepted_error": "", "delivery": "editing", "receipt_token": secrets.token_urlsafe(32),
            "service_url": origin,
        }
    if draft["delivery"] != "editing":
        receipt = _report_request(
            origin, "GET", f"/v1/reports/{draft['report']['report_id']}/status",
            token=draft["receipt_token"],
        )
        return _report_receipt(path, draft, receipt)
    payload = _report_bytes(draft["report"])
    if len(payload) > 1024 * 1024:
        raise ValueError("The diagnostic report is too large to upload. Copy the log instead.")
    _report_save(path, draft)
    intent = _report_request(origin, "POST", "/v1/intents", data=_report_bytes({
        "schema_version": "1", "report_id": draft["report"]["report_id"],
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "receipt_token_sha256": hashlib.sha256(draft["receipt_token"].encode()).hexdigest(),
    }))
    patterns = {"intent_id": r"[A-Za-z0-9_-]{16,128}",
                "browser_token": r"[A-Za-z0-9_-]{32,256}",
                "desktop_token": r"[A-Za-z0-9_-]{32,256}"}
    if set(intent) != set(patterns) or any(
        not isinstance(intent[key], str) or not re.fullmatch(pattern, intent[key])
        for key, pattern in patterns.items()
    ):
        raise ValueError(
            "The service returned invalid browser verification data. The report was not sent."
        )
    verification = origin + "/verify#" + urlencode({
        "intent_id": intent["intent_id"], "token": intent["browser_token"],
    })
    try:
        opened = webbrowser.open(verification, new=2)
    except (OSError, webbrowser.Error):
        opened = False
    if not opened:
        raise ValueError("Browser verification could not open. Your diagnostic report is saved.")
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        status = _report_request(
            origin, "GET", f"/v1/intents/{intent['intent_id']}/status",
            token=intent["desktop_token"],
        ).get("state")
        if status == "verified":
            # Persist the receipt before any report bytes leave this process.
            draft["delivery"] = "uncertain"
            _report_save(path, draft)
            receipt = _report_request(
                origin, "POST", f"/v1/reports?intent_id={intent['intent_id']}",
                data=payload, token=intent["desktop_token"],
            )
            return _report_receipt(path, draft, receipt)
        if status == "expired":
            raise ValueError("Browser verification expired. The saved report was not uploaded.")
        if status != "pending":
            raise ValueError(
                "The verification response was not understood. The report was not uploaded."
            )
        time.sleep(3)
    raise ValueError("Browser verification timed out. The saved report was not uploaded.")


def _offer_report(log_path: Path, outcome: str, app_version: str) -> None:
    """Native recovery actions work even when Studio's dependencies cannot import."""
    if sys.platform != "darwin":
        return
    message = _redact(outcome)
    while True:
        notice = (
            "Send Error Report shares this diagnostic log with Studio support after browser "
            "verification. Copy Log copies it for a bug report."
        )
        try:
            draft = _report_load(log_path.with_suffix(".report.json"))
            locked = draft and draft["delivery"] != "editing"
            action = "Check Status" if locked else "Send Error Report"
            buttons: tuple[str, ...] = ("Close", "Copy Log", action)
            if locked:
                notice = "This report has a saved receipt. Check Status will not resend it."
        except ValueError as exc:
            notice = str(exc)
            action = ""
            buttons = ("Close", "Copy Log")
            _LOGGER.error("%s", notice)
        choice = _native_dialog(
            f"{message}\n\nDiagnostic log: {log_path}\n\n{notice}", buttons, "Close",
        )
        if choice == "Close" or choice not in ("Copy Log", action):
            return
        try:
            if choice == "Copy Log":
                subprocess.run(
                    ["/usr/bin/pbcopy"], input=_report_log(log_path, 1024 * 1024),
                    text=True, check=True, timeout=10, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                _native_dialog(
                    "Diagnostic log copied. Paste it into your bug report.", ("Close",), "Close",
                )
                return
            message = _send_repair_report(log_path, outcome, app_version)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            # Controlled service errors never include credentials or response bodies.
            message = str(exc) if isinstance(exc, ValueError) else (
                "The report action could not finish. The diagnostic log is still saved."
            )
            _LOGGER.error("Report action: %s", message)


def main(argv: list[str] | None = None) -> int:
    global _DIAGNOSTICS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="check without installing or configuring",
    )
    parser.add_argument("--report-log", type=Path, help="offer reporting for a saved repair.log")
    parser.add_argument("--finish-diagnostics", type=Path, help=argparse.SUPPRESS)
    arguments = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    repo_root = Path(__file__).resolve().parents[1]
    diagnostics = None
    code = 1
    outcome = "Environment repair did not complete."
    try:
        if arguments.finish_diagnostics:
            return _finish_diagnostics(repo_root, arguments.finish_diagnostics)
        if arguments.report_log:
            log = _owned_path(repo_root, arguments.report_log)
            if not log.is_file() or log.name != "repair.log":
                raise ValueError("Select a saved repair.log from this checkout's diagnostics.")
            _offer_report(log, "Saved macOS environment repair diagnostics.",
                          _source_version(repo_root))
            return 0
        diagnostics = _DIAGNOSTICS = _Diagnostics(repo_root)
        _log_context(repo_root, arguments.check)
        code = repair_environment(repo_root, check_only=arguments.check)
        if diagnostics.pending:
            _continue_diagnostics(diagnostics)
            outcome = "Dependencies passed; PyCharm repair is pending."
        elif code == 0:
            outcome = "Studio's environment, engine and PyCharm configuration are ready."
    except KeyboardInterrupt:
        _LOGGER.warning("Repair was interrupted. The environment has not been certified ready.")
        code = 130
        outcome = "Environment repair was interrupted."
    except Exception as exc:
        # Include unexpected failures and original chained causes, not only a short UI error.
        _LOGGER.exception("Environment check stopped")
        code = 1
        if diagnostics is not None:
            diagnostics.pending = False
        elif sys.platform == "darwin":
            message = "Could not finish diagnostic capture: " + _redact(str(exc))
            if arguments.finish_diagnostics:
                try:
                    log = _owned_path(repo_root, arguments.finish_diagnostics.parent / "repair.log")
                    if not log.is_file():
                        raise ValueError("The original diagnostic log is unavailable.")
                    _offer_report(log, message + " PyCharm completion is unconfirmed.",
                                  _source_version(repo_root))
                except Exception:
                    _native_dialog(message, ("Close",), "Close")
            else:
                _native_dialog(message + " Retain the PyCharm console output.", ("Close",), "Close")
    finally:
        if diagnostics is not None:
            _LOGGER.info("RESULT: %s | exit=%s | elapsed=%.1fs", outcome, code,
                         time.monotonic() - diagnostics.started)
            relative_log = diagnostics.path.relative_to(repo_root)
            _LOGGER.info("Diagnostic log in this checkout: %s", relative_log)
            _LOGGER.info("Send later: run this helper with --report-log \"%s\"", relative_log)
            diagnostics.close()
        _DIAGNOSTICS = None
    if diagnostics is not None and not diagnostics.pending:
        if diagnostics.file_handler.failed:
            outcome += " Diagnostic log is incomplete; also retain the PyCharm console."
        try:
            _offer_report(diagnostics.path, outcome, _source_version(repo_root))
        except Exception:
            _LOGGER.exception("Could not open reporting. Keep the saved diagnostic log")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
