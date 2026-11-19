"""Queue-backed application logging and bounded, best-effort redacted collection."""

from __future__ import annotations

import copy
import faulthandler
import logging
import logging.handlers
import os
import queue
import re
import stat
import sys
import threading
import time
import traceback
from collections import deque
from contextlib import nullcontext
from pathlib import Path
from types import TracebackType
from typing import BinaryIO
from uuid import UUID, uuid4

from fpvs_studio.support.crash_inventory import collect_inventory, os_identity
from fpvs_studio.support.crash_reporting import (
    CrashContext,
    CrashSession,
    CrashStore,
    HandledIncident,
    Operation,
    OSFamily,
    StackFrame,
    safe_frame,
)
from fpvs_studio.support.models import MAX_LOG_BYTES, utc_now
from fpvs_studio.support.storage import owned_folder, support_directory

_LOG_NAME = re.compile(r"session-[0-9a-f]{32}(?:-native)?\.log(?:\.[12])?\Z")
_CREDENTIAL = re.compile(
    r"""(?P<label>(?<!\w)(?P<key_quote>["']?)(?:password|token|secret|api[_-]?key)
    (?P=key_quote)\s*[:=]\s*)
    (?P<value>
        "(?:\\[^\r\n]|[^"\\\r\n])*(?:"|\\?(?=\r?$))
        | '(?:\\[^\r\n]|[^'\\\r\n])*(?:'|\\?(?=\r?$))
        | [^\s,;}\]"']+
    )""",
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)
_logging_notice = ""
_native_diagnostic_fd: int | None = None
_active_logging: DiagnosticLogging | None = None


def refresh_automatic_capture(*, enabled: bool) -> None:
    if (active := _active_logging) is not None:
        if enabled:
            active.capture_refresh.set()
        else:
            active._capture_can_start = False
            active.capture_enabled.clear()


def record_internal_error(error: BaseException, operation: Operation) -> None:
    if (active := _active_logging) is not None:
        active.record_handled(error, operation)


def record_qt_fatal(message: str) -> None:
    """Write one redacted breadcrumb before Qt aborts and the log queue is lost."""

    descriptor = _native_diagnostic_fd
    if descriptor is not None:
        try:
            text = "Qt fatal: " + redact(bounded_text(message, 8192)) + "\n"
            os.write(descriptor, text.encode("utf-8", errors="replace"))
            # Windows fast-fail exits can bypass Python's installed signal handler.
            # Qt gives us this last callback before aborting, so capture stacks now.
            faulthandler.dump_traceback(file=descriptor, all_threads=True)
        except OSError:
            pass


def bounded_text(text: str, limit: int = MAX_LOG_BYTES) -> str:
    data = text.encode("utf-8", errors="replace")
    if len(data) <= limit:
        return data.decode("utf-8")
    prefix = "[Earlier text omitted to fit the diagnostic limit.]\n"
    return prefix + data[-(limit - len(prefix.encode())) :].decode("utf-8", errors="ignore")


def redact(text: str) -> str:
    """Remove common paths, participant tags, emails and credentials; review is still required."""
    text = re.sub(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=\-]+", "Bearer <redacted>", text)

    def credential(match: re.Match[str]) -> str:
        value = match["value"]
        quote = value[0] if value[0] in "\"'" else ""
        return match["label"] + quote + "<redacted>" + quote

    text = _CREDENTIAL.sub(credential, text)
    text = re.sub(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "<email>", text)
    text = re.sub(
        r"(?i)(participant(?:[_ -]?(?:id|number))?\s*[:=]\s*)[^\s,;]+", r"\1<redacted>", text
    )
    # Quoted traceback filenames first; retain only the module filename for debugging.
    text = re.sub(
        r'File "([^"\r\n]+)"', lambda m: 'File "<path>/' + re.split(r"[/\\]", m[1])[-1] + '"', text
    )
    text = re.sub(re.escape(str(Path.home())) + r"(?:[/\\][^\r\n\"<>]+)?", "<path>", text)
    text = re.sub(r"(?:[A-Za-z]:[\\/]|\\\\)[^\r\n\"<>]+", "<path>", text)
    text = re.sub(r"(?<![\w:])/(?:home|Users|tmp|mnt|media|var)/[^\s\"<>]+", "<path>", text)
    return text


def combine_diagnostics(logs: str, details: str) -> str:
    """Keep reviewed session context and the reported error within one explicit limit."""
    logs, details = redact(logs), redact(details)
    if not details or logs == details:
        return bounded_text(logs)
    if not logs:
        return bounded_text(details)
    error_heading = "Reported error\n"
    log_heading = "\n\nApplication session logs\n"
    if logs.startswith(error_heading):
        existing_error, separator, _existing_logs = logs[len(error_heading):].partition(log_heading)
        same_error = existing_error == details or (
            existing_error.startswith("[Earlier text omitted to fit the diagnostic limit.]\n")
            and bounded_text(details, len(existing_error.encode("utf-8"))) == existing_error
        )
        if separator and same_error:
            if len(logs.encode("utf-8")) <= MAX_LOG_BYTES:
                return logs
            logs = _existing_logs
    available = MAX_LOG_BYTES - len((error_heading + log_heading).encode())
    # A long traceback must not displace all session context, or vice versa.
    error_budget = min(
        len(details.encode("utf-8")),
        max(available // 2, available - len(logs.encode("utf-8"))),
    )
    details = bounded_text(details, error_budget)
    logs = bounded_text(logs, available - len(details.encode("utf-8")))
    return error_heading + details + log_heading + logs


def _log_files(folder: Path) -> list[tuple[Path, os.stat_result]]:
    """Snapshot owned regular files, allowing peers to rotate or prune a log."""
    files = []
    for path in folder.iterdir():
        if not _LOG_NAME.fullmatch(path.name):
            continue
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISREG(metadata.st_mode) and not (
            getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            files.append((path, metadata))
    return files


def collect_diagnostics(root: Path) -> str:
    """Snapshot the active session, or explicitly identify the latest retained one."""
    folder = owned_folder(root, "logs")
    active = _active_logging
    if active is not None and active.root.absolute() != root.absolute():
        active = None
    notices: list[str] = []
    if active is not None and not active.flush():
        notices.append("Some queued application messages were not ready during collection.")
    # Ordinary rotation and this bounded snapshot cannot race within this process.
    with active.snapshot_lock if active is not None else nullcontext():
        files = _log_files(folder)
        if active is not None:
            session_id = active.session_id
            heading = "Current Studio session"
        elif files:
            latest = max(files, key=lambda pair: (pair[1].st_mtime, pair[0].name))[0]
            session_id = latest.name[8:40]
            heading = "Latest retained Studio session (no active log capture)"
        else:
            return "No application session logs are available." + (
                "\n" + _logging_notice if _logging_notice else ""
            )
        files = [pair for pair in files if pair[0].name[8:40] == session_id]
        sections, truncated = _read_session_logs(files)
    if truncated:
        notices.append("Earlier session log text omitted to fit the 256 KiB diagnostic limit.")
    if _logging_notice:
        notices.append(_logging_notice)
    if not sections:
        notices.append("No retained log text was available for this session.")
    return bounded_text("\n\n".join([heading, *notices, *sections]))


def _read_session_logs(files: list[tuple[Path, os.stat_result]]) -> tuple[list[str], bool]:
    """Prefer recent ordinary logs while reserving a share for native crash evidence."""
    chunks: list[str] = []
    budget = MAX_LOG_BYTES - 1024  # Headings, notices and per-file labels remain visible.
    truncated = False
    # Current log follows .1 and .2 in display order; native evidence is separate.
    files = sorted(files, key=lambda pair: (
        "-native" in pair[0].name,
        -int(pair[0].suffix[1:]) if pair[0].suffix in (".1", ".2") else 0,
    ), reverse=True)
    has_ordinary = any("-native" not in path.name for path, _metadata in files)
    for path, metadata in files:
        if budget <= 0:
            truncated = True
            break
        native = "-native" in path.name
        allowance = min(budget, MAX_LOG_BYTES // 4) if native and has_ordinary else budget
        try:
            with path.open("rb") as stream:
                opened = os.fstat(stream.fileno())
                if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
                    # A rotated/replaced path must not redirect collection to other data.
                    truncated = True
                    continue
                size = opened.st_size
                offset = max(0, size - allowance)
                stream.seek(offset)
                data = stream.read(allowance)
                if offset:
                    # Never start halfway through a credential or private path.
                    data = data.partition(b"\n")[2]
                    truncated = True
        except FileNotFoundError:
            truncated = True
            continue
        text = bounded_text(redact(data.decode("utf-8", errors="replace")), allowance)
        label = "Native traceback" if native else (
            "Application log" + (f" (rotation {path.suffix[1:]})" if path.suffix != ".log" else "")
        )
        section = label + "\n" + text
        if native:
            chunks.append(section)
        else:
            chunks.insert(0, section)
        budget -= len(section.encode("utf-8"))
    return chunks, truncated


class _QueueHandler(logging.Handler):
    def __init__(self, records: queue.Queue[logging.LogRecord | threading.Event]) -> None:
        super().__init__(logging.INFO)
        self.records = records

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.records.put_nowait(copy.copy(record))
        except queue.Full:
            # Do not block the presentation thread or recurse into logging.
            global _logging_notice
            _logging_notice = "Some application log messages were omitted because logging was busy."


class _SafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return bounded_text(redact(super().format(record)), 16 * 1024)


class _LogFile(logging.handlers.RotatingFileHandler):
    def handleError(self, record: logging.LogRecord) -> None:  # noqa: N802
        global _logging_notice
        _logging_notice = "Some application logs could not be written."


class DiagnosticLogging:
    """File I/O and exception formatting happen on one daemon thread, not the GUI."""

    def __init__(self, root: Path, *, capture_native: bool = False) -> None:
        self.root = root
        self.capture_native = capture_native
        self.session_id = uuid4().hex
        self._crash_store: CrashStore | None = None
        self._crash_session: CrashSession | None = None
        self._failure: tuple[str, Operation, list[StackFrame]] | None = None
        self._handled: queue.Queue[HandledIncident] = queue.Queue(maxsize=10)
        self._inventory: queue.Queue[CrashContext] = queue.Queue(maxsize=1)
        self.capture_enabled = threading.Event()
        self.capture_refresh = threading.Event()
        self.capture_refresh.set()
        self._capture_can_start = True
        self.ready = threading.Event()
        self._native_file: BinaryIO | None = None
        self._owns_fault_handler = False
        self.records: queue.Queue[logging.LogRecord | threading.Event] = queue.Queue(maxsize=256)
        self.snapshot_lock = threading.RLock()
        self.handler = _QueueHandler(self.records)
        self.stop_event = threading.Event()
        self.logger = logging.getLogger("fpvs_studio")
        self.previous_level = self.logger.level
        self.previous_hook = sys.excepthook
        self.previous_thread_hook = threading.excepthook
        self.thread = threading.Thread(target=self._run, daemon=True, name="fpvs-support-log")

    def start(self) -> None:
        global _active_logging
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        sys.excepthook = self._exception
        threading.excepthook = self._thread_exception
        self.thread.start()
        _active_logging = self
        if self.capture_native:
            # Bootstrap calls this before importing Qt or creating its event loop.
            # Avoid delaying startup indefinitely if app-local storage is unavailable.
            self.ready.wait(timeout=0.5)

    def flush(self, timeout: float = 2) -> bool:
        """Wait in the collection worker for records already queued, without blocking emitters."""
        if not self.thread.is_alive():
            return False
        barrier = threading.Event()
        deadline = time.monotonic() + timeout
        try:
            self.records.put(barrier, timeout=timeout)
        except queue.Full:
            return False
        return barrier.wait(max(0, deadline - time.monotonic()))

    def _exception(
        self, kind: type[BaseException], value: BaseException, tb: TracebackType | None
    ) -> None:
        self.record_handled(value, "application")
        self.logger.error("Unhandled application error", exc_info=(kind, value, tb))
        self.previous_hook(kind, value, tb)

    def _thread_exception(self, args: threading.ExceptHookArgs) -> None:
        if args.exc_value is not None:
            self.record_handled(args.exc_value, "application")
        self.logger.error(
            "Unhandled thread error",
            exc_info=(
                args.exc_type,
                args.exc_value or RuntimeError("Thread failed"),
                args.exc_traceback,
            ),
        )
        self.previous_thread_hook(args)

    def record_failure(self, error: BaseException, operation: Operation = "startup") -> None:
        """Remember only source locations; persistence remains on the logging thread."""
        if self.capture_enabled.is_set():
            self._failure = (utc_now(), operation, self._safe_stack(error))

    @staticmethod
    def _safe_stack(error: BaseException) -> list[StackFrame]:
        frames = deque(traceback.walk_tb(error.__traceback__), maxlen=40)
        return [safe_frame(frame.f_code.co_filename, frame.f_code.co_name, line)
                for frame, line in frames]

    def record_handled(self, error: BaseException, operation: Operation) -> None:
        # Catch only programming/internal failures at app/worker boundaries. Routine
        # validation, I/O, cancellation and dependency-specific errors stay local.
        if not self.capture_enabled.is_set():
            return
        for _ in range(8):
            cause = error.__cause__
            if cause is None or cause is error:
                break
            error = cause
        if getattr(error, "_fpvs_automatic_incident", False) or type(error) not in (
            AssertionError, AttributeError, IndexError, KeyError, NameError,
            NotImplementedError, RuntimeError, TypeError, ZeroDivisionError,
        ):
            return
        stack = self._safe_stack(error)
        modules = [frame.module for frame in stack if frame.module != "<external>"]
        if not modules or any(
            module.startswith(("fpvs_studio/support/", "fpvs_studio/gui/crash_report_"))
            for module in modules
        ):
            return
        if operation == "application":
            for module in reversed(modules):
                if module.startswith("fpvs_studio/preprocessing/"):
                    operation = "processing"
                    break
                if "export" in module:
                    operation = "export"
                    break
                if module.startswith("fpvs_studio/core/project_"):
                    operation = "project"
                    break
        try:
            self._handled.put_nowait(HandledIncident(operation=operation, stack=stack))
        except queue.Full:
            return
        error._fpvs_automatic_incident = True  # type: ignore[attr-defined]

    def _update_crash_capture(self, *, closing: bool = False) -> None:
        global _logging_notice
        store = self._crash_store
        if store is None:
            return
        try:
            if self.capture_refresh.is_set():
                self.capture_refresh.clear()
                consent = store.consent()
                if self._capture_can_start and not consent.enabled:
                    self._capture_can_start = False  # An opted-out session stays local.
                if (
                    self._capture_can_start and self._crash_session is None and consent.enabled
                    and consent.expanded_disclosed and not consent.revoke_pending
                ):
                    family, version, build = os_identity()
                    self._crash_session = CrashSession(
                        session_id=UUID(self.session_id), pid=os.getpid(),
                        os_version=version, os_family=family,
                        installation_id=consent.installation_id,
                        generation=consent.workflow_generation,
                        pycharm_hosted=(
                            os.environ.get("PYCHARM_HOSTED") == "1"
                            and not getattr(sys, "frozen", False)
                        ),
                    )
                    if store.update_session(self._crash_session):
                        self.capture_enabled.set()
                        threading.Thread(
                            target=self._collect_inventory, args=(family, build), daemon=True,
                            name="fpvs-crash-inventory",
                        ).start()
            session = self._crash_session
            if session is None:
                return
            changed = closing
            if not self._inventory.empty():
                session.context = self._inventory.get_nowait()
                changed = True
            while not self._handled.empty():
                handled = self._handled.get_nowait()
                if len(session.handled) < 10:
                    session.handled.append(handled)
                    changed = True
            if self._failure is not None:
                session.failed_at, session.operation, session.stack = self._failure
                session.state = "failed"
                self._failure = None
                changed = True
            if closing and session.state != "failed":
                session.state = "clean"
            if changed and not store.update_session(session):
                self.capture_enabled.clear()
        except (OSError, ValueError):
            self.capture_enabled.clear()
            _logging_notice = "Automatic crash capture could not update its local record."

    def _collect_inventory(self, family: OSFamily, build: str | None) -> None:
        try:
            if self.capture_enabled.is_set():
                self._inventory.put_nowait(collect_inventory(family, build))
        except (OSError, ValueError):
            pass  # Optional inventory never blocks diagnostics or native recovery.

    def _run(self) -> None:
        global _logging_notice, _native_diagnostic_fd
        sink: logging.handlers.RotatingFileHandler | None = None
        try:
            if self.capture_native:
                try:
                    self._crash_store = CrashStore(self.root)
                    self._crash_store.prune_sessions()
                    self._update_crash_capture()
                except (OSError, ValueError):
                    _logging_notice = "Automatic crash capture could not access its local settings."
            folder = owned_folder(self.root, "logs")
            files = _log_files(folder)
            retained = sum(metadata.st_size for _path, metadata in files)
            for path, metadata in sorted(files, key=lambda pair: pair[1].st_mtime):
                # Never remove a potentially active session's log.
                age = time.time() - metadata.st_mtime
                if age > 7 * 24 * 3600 or (retained > 7 * 1024 * 1024 and age > 24 * 3600):
                    retained -= metadata.st_size
                    path.unlink(missing_ok=True)
            if retained > 7 * 1024 * 1024:
                raise OSError("Recent support logs already occupy the local logging budget.")
            session_id = self.session_id
            sink = _LogFile(
                folder / f"session-{session_id}.log",
                maxBytes=1024 * 1024,
                backupCount=2,
                encoding="utf-8",
            )
            sink.setFormatter(_SafeFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
            if self.capture_native and not faulthandler.is_enabled():
                self._native_file = (folder / f"session-{session_id}-native.log").open("xb")
                faulthandler.enable(file=self._native_file, all_threads=True)
                self._owns_fault_handler = True
                _native_diagnostic_fd = self._native_file.fileno()
            self.ready.set()
            while not self.stop_event.is_set() or not self.records.empty():
                self._update_crash_capture()
                # Windows can report recoverable native exceptions too. Stop capture
                # at the budget rather than accumulating unlimited raw tracebacks.
                if self._native_file is not None and self._native_file.tell() >= 1024 * 1024:
                    self._close_native_capture()
                try:
                    record = self.records.get(timeout=0.1)
                except queue.Empty:
                    continue
                if isinstance(record, threading.Event):
                    sink.flush()
                    record.set()
                    continue
                total = sum(metadata.st_size for _path, metadata in _log_files(folder))
                if total + 20 * 1024 > 10 * 1024 * 1024:
                    _logging_notice = "Application logging paused at its local storage budget."
                    break
                with self.snapshot_lock:
                    sink.handle(record)
        except Exception:
            _logging_notice = "Persistent application logs are unavailable on this machine."
        finally:
            self.ready.set()
            self._close_native_capture()
            # A full or unavailable log sink must not finish the running app's
            # session. Drain the bounded queue until explicit app shutdown; a
            # later abrupt exit still recovers the active snapshot honestly.
            while not self.stop_event.is_set():
                self._update_crash_capture()
                try:
                    discarded = self.records.get(timeout=0.1)
                    if isinstance(discarded, threading.Event):
                        discarded.set()
                except queue.Empty:
                    pass
            self._update_crash_capture(closing=True)
            if sink is not None:
                sink.close()

    def _close_native_capture(self) -> None:
        global _native_diagnostic_fd
        if self._owns_fault_handler:
            _native_diagnostic_fd = None
            faulthandler.disable()
            self._owns_fault_handler = False
        if self._native_file is not None:
            self._native_file.close()
            self._native_file = None

    def close(self) -> None:
        global _active_logging
        self.logger.removeHandler(self.handler)
        self.logger.setLevel(self.previous_level)
        if sys.excepthook == self._exception:
            sys.excepthook = self.previous_hook
        if threading.excepthook == self._thread_exception:
            threading.excepthook = self.previous_thread_hook
        self.stop_event.set()
        self.thread.join(timeout=2)  # Called only after the GUI event loop has exited.
        if _active_logging is self:
            _active_logging = None


def start_diagnostic_logging() -> DiagnosticLogging | None:
    global _logging_notice
    try:
        session = DiagnosticLogging(support_directory(), capture_native=True)
        session.start()
        return session
    except OSError:
        _logging_notice = "Persistent application logs are unavailable on this machine."
        return None
