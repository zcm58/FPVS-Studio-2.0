"""Queue-backed application logging and bounded, best-effort redacted collection."""

from __future__ import annotations

import copy
import logging
import logging.handlers
import queue
import re
import sys
import threading
import time
from pathlib import Path
from types import TracebackType
from uuid import uuid4

from fpvs_studio.support.models import MAX_LOG_BYTES
from fpvs_studio.support.storage import owned_folder, support_directory

_LOG_NAME = re.compile(r"session-[0-9a-f]{32}\.log(?:\.[12])?\Z")
_logging_notice = ""


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

    def __init__(self, root: Path) -> None:
        self.root = root
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

    def _run(self) -> None:
        global _logging_notice
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
            sink = _LogFile(
                folder / f"session-{uuid4().hex}.log",
                maxBytes=1024 * 1024,
                backupCount=2,
                encoding="utf-8",
            )
            sink.setFormatter(_SafeFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
            while not self.stop_event.is_set() or not self.records.empty():
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
            if sink is not None:
                sink.close()

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
        session = DiagnosticLogging(support_directory())
        session.start()
        return session
    except OSError:
        _logging_notice = "Persistent application logs are unavailable on this machine."
        return None
