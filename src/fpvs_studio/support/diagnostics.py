"""Queue-backed application logging and bounded, best-effort redacted collection."""

from __future__ import annotations

import copy
import faulthandler
import logging
import logging.handlers
import os
import platform
import queue
import re
import sys
import threading
import time
import traceback
from pathlib import Path
from types import TracebackType
from typing import BinaryIO
from uuid import UUID, uuid4

from fpvs_studio.support.crash_reporting import CrashSession, CrashStore, StackFrame, safe_frame
from fpvs_studio.support.models import MAX_LOG_BYTES
from fpvs_studio.support.storage import owned_folder, support_directory

_LOG_NAME = re.compile(r"session-[0-9a-f]{32}(?:-native)?\.log(?:\.[12])?\Z")
_logging_notice = ""
_native_diagnostic_fd: int | None = None


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
        return text
    prefix = "[Earlier text omitted to fit the diagnostic limit.]\n"
    return prefix + data[-(limit - len(prefix.encode())) :].decode("utf-8", errors="ignore")


def redact(text: str) -> str:
    """Remove common paths, participant tags, emails and credentials; review is still required."""
    text = text.replace(str(Path.home()), "<user-home>")
    text = re.sub(r"(?i)\b(?:bearer\s+)[\w.\-]+", "Bearer <redacted>", text)
    text = re.sub(
        r"(?i)(\b(?:password|token|secret|api[_-]?key)\b\s*[:=]\s*)[^\s,;]+",
        r"\1<redacted>",
        text,
    )
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "<email>", text)
    text = re.sub(
        r"(?i)(participant(?:[_ -]?(?:id|number))?\s*[:=]\s*)[^\s,;]+", r"\1<redacted>", text
    )
    # Quoted traceback filenames first; retain only the module filename for debugging.
    text = re.sub(
        r'File "([^"\r\n]+)"', lambda m: 'File "<path>/' + re.split(r"[/\\]", m[1])[-1] + '"', text
    )
    text = re.sub(r"(?:[A-Za-z]:[\\/]|\\\\)[^\r\n\"<>]+", "<path>", text)
    text = re.sub(r"(?<![\w:])/(?:home|Users|tmp|mnt|media|var)/[^\s\"<>]+", "<path>", text)
    return text


def collect_diagnostics(root: Path) -> str:
    """Read only known support logs; never enumerate a project or environment."""
    folder = owned_folder(root, "logs")
    chunks: list[str] = []
    budget = MAX_LOG_BYTES
    truncated = False
    if folder.exists():
        files = sorted(
            (
                p
                for p in folder.iterdir()
                if _LOG_NAME.fullmatch(p.name) and p.is_file() and not p.is_symlink()
            ),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for path in files:
            if budget <= 0:
                truncated = True
                break
            with path.open("rb") as stream:
                size = path.stat().st_size
                truncated = truncated or size > budget
                stream.seek(max(0, size - budget))
                data = stream.read(budget)
            chunks.insert(0, data.decode("utf-8", errors="replace"))
            budget -= len(data)
    text = "\n".join(chunks)
    if truncated:
        text = "[Earlier log text omitted to fit the diagnostic limit.]\n" + text
    if _logging_notice:
        text += "\n" + _logging_notice
    return bounded_text(redact(text))


class _QueueHandler(logging.Handler):
    def __init__(self, records: queue.Queue[logging.LogRecord]) -> None:
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
        self._failure_stack: list[StackFrame] | None = None
        self.ready = threading.Event()
        self._native_file: BinaryIO | None = None
        self._owns_fault_handler = False
        self.records: queue.Queue[logging.LogRecord] = queue.Queue(maxsize=256)
        self.handler = _QueueHandler(self.records)
        self.stop_event = threading.Event()
        self.logger = logging.getLogger("fpvs_studio")
        self.previous_level = self.logger.level
        self.previous_hook = sys.excepthook
        self.previous_thread_hook = threading.excepthook
        self.thread = threading.Thread(target=self._run, daemon=True, name="fpvs-support-log")

    def start(self) -> None:
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        sys.excepthook = self._exception
        threading.excepthook = self._thread_exception
        self.thread.start()
        if self.capture_native:
            # Bootstrap calls this before importing Qt or creating its event loop.
            # Avoid delaying startup indefinitely if app-local storage is unavailable.
            self.ready.wait(timeout=0.5)

    def _exception(
        self, kind: type[BaseException], value: BaseException, tb: TracebackType | None
    ) -> None:
        self.logger.error("Unhandled application error", exc_info=(kind, value, tb))
        self.previous_hook(kind, value, tb)

    def _thread_exception(self, args: threading.ExceptHookArgs) -> None:
        self.logger.error(
            "Unhandled thread error",
            exc_info=(
                args.exc_type,
                args.exc_value or RuntimeError("Thread failed"),
                args.exc_traceback,
            ),
        )
        self.previous_thread_hook(args)

    def record_failure(self, error: BaseException) -> None:
        """Remember only source locations; persistence remains on the logging thread."""
        self._failure_stack = [
            safe_frame(frame.f_code.co_filename, frame.f_code.co_name, line)
            for frame, line in traceback.walk_tb(error.__traceback__)
        ][-40:]

    def _run(self) -> None:
        global _logging_notice, _native_diagnostic_fd
        sink: logging.handlers.RotatingFileHandler | None = None
        try:
            folder = owned_folder(self.root, "logs")
            files = [
                p
                for p in folder.iterdir()
                if _LOG_NAME.fullmatch(p.name) and not p.is_symlink() and p.is_file()
            ]
            retained = sum(p.stat().st_size for p in files)
            for path in sorted(files, key=lambda p: p.stat().st_mtime):
                # Never remove a potentially active session's log.
                age = time.time() - path.stat().st_mtime
                if age > 7 * 24 * 3600 or (retained > 7 * 1024 * 1024 and age > 24 * 3600):
                    retained -= path.stat().st_size
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
            if self.capture_native:
                try:
                    self._crash_store = CrashStore(self.root)
                    self._crash_store.prune_sessions()
                    consent = self._crash_store.consent()
                    self._crash_session = CrashSession(
                        session_id=UUID(session_id), pid=os.getpid(),
                        os_version=f"{platform.system()} {platform.release()}",
                        installation_id=(
                            consent.installation_id
                            if consent.enabled and not consent.revoke_pending else None
                        ),
                    )
                    self._crash_store.save_session(self._crash_session)
                except (OSError, ValueError):
                    _logging_notice = "Automatic crash capture could not access its local settings."
            if self.capture_native and not faulthandler.is_enabled():
                self._native_file = (folder / f"session-{session_id}-native.log").open("xb")
                faulthandler.enable(file=self._native_file, all_threads=True)
                self._owns_fault_handler = True
                _native_diagnostic_fd = self._native_file.fileno()
            self.ready.set()
            while not self.stop_event.is_set() or not self.records.empty():
                # Windows can report recoverable native exceptions too. Stop capture
                # at the budget rather than accumulating unlimited raw tracebacks.
                if self._native_file is not None and self._native_file.tell() >= 1024 * 1024:
                    self._close_native_capture()
                try:
                    record = self.records.get(timeout=0.1)
                except queue.Empty:
                    continue
                total = sum(
                    p.stat().st_size
                    for p in folder.iterdir()
                    if _LOG_NAME.fullmatch(p.name) and p.is_file() and not p.is_symlink()
                )
                if total + 20 * 1024 > 10 * 1024 * 1024:
                    _logging_notice = "Application logging paused at its local storage budget."
                    break
                sink.handle(record)
        except Exception:
            _logging_notice = "Persistent application logs are unavailable on this machine."
        finally:
            self.ready.set()
            if self._crash_session is not None and self._crash_store is not None:
                try:
                    self._crash_session.state = (
                        "failed" if self._failure_stack is not None else "clean"
                    )
                    self._crash_session.stack = self._failure_stack or []
                    self._crash_store.save_session(self._crash_session)
                except (OSError, ValueError):
                    _logging_notice = "Automatic crash capture could not finish its local record."
            self._close_native_capture()
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
        self.logger.removeHandler(self.handler)
        self.logger.setLevel(self.previous_level)
        if sys.excepthook == self._exception:
            sys.excepthook = self.previous_hook
        if threading.excepthook == self._thread_exception:
            threading.excepthook = self.previous_thread_hook
        self.stop_event.set()
        self.thread.join(timeout=2)  # Called only after the GUI event loop has exited.


def start_diagnostic_logging() -> DiagnosticLogging | None:
    global _logging_notice
    try:
        session = DiagnosticLogging(support_directory(), capture_native=True)
        session.start()
        return session
    except OSError:
        _logging_notice = "Persistent application logs are unavailable on this machine."
        return None
