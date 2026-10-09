"""Opt-out crash recovery and a bounded outbox; never collect research data or messages."""

from __future__ import annotations

import ctypes
import os
import re
import secrets
import sys
import time
from pathlib import Path
from threading import Event, RLock
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from fpvs_studio import __version__
from fpvs_studio.support.client import ReportClient
from fpvs_studio.support.models import Intent, utc_now
from fpvs_studio.support.storage import atomic_text, owned_folder

MAX_CRASH_BYTES = 32 * 1024
_SESSION_NAME = re.compile(r"session-([0-9a-f]{32})\.json\Z")
_EVENT_NAME = re.compile(r"crash-[a-f0-9-]{36}\.json\Z")
_NATIVE_FRAME = re.compile(r'File "([^"\r\n]+)", line (\d+) in ([^\r\n]+)')


class StackFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    module: str = Field(
        max_length=160, pattern=r"^(?:<external>|fpvs_studio/(?:[a-zA-Z0-9_]+/)*[a-zA-Z0-9_]+\.py)$"
    )
    function: str = Field(max_length=80, pattern=r"^[a-zA-Z0-9_.<>-]{1,80}$")
    line: int = Field(ge=0, le=1_000_000)


def safe_frame(filename: str, function: str, line: int) -> StackFrame:
    """Keep package-relative source locations; remove external paths and names."""
    path = filename.replace("\\", "/")
    marker = path.rfind("/fpvs_studio/")
    module = path[marker + 1 :] if marker >= 0 else path
    if not re.fullmatch(r"fpvs_studio/(?:[a-zA-Z0-9_]+/)*[a-zA-Z0-9_]+\.py", module):
        module, function = "<external>", "<external>"
    if not re.fullmatch(r"[a-zA-Z0-9_.<>-]{1,80}", function):
        function = "<unknown>"
    return StackFrame(module=module[:160], function=function, line=min(max(line, 0), 1_000_000))


class CrashReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1"] = "1"
    kind: Literal["crash"] = "crash"
    report_id: UUID
    created_at: str
    app_version: str = Field(max_length=128)
    os_version: str = Field(max_length=256)
    crash_type: Literal["python_exception", "native_fault", "unclean_shutdown"]
    stack: list[StackFrame] = Field(default_factory=list, max_length=40)


class CrashConsent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    registered: bool = False
    installation_id: UUID = Field(default_factory=uuid4)
    token: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        repr=False,
        pattern=r"^[A-Za-z0-9_-]{43}$",
    )
    enrollment: Intent | None = None
    revoke_pending: bool = False


class CrashSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    pid: int = Field(gt=0)
    created_at: str = Field(default_factory=utc_now)
    created_epoch: float = Field(default_factory=time.time)
    app_version: str = Field(default_factory=lambda: str(__version__))
    os_version: str
    installation_id: UUID | None = None
    state: Literal["active", "clean", "failed"] = "active"
    stack: list[StackFrame] = Field(default_factory=list, max_length=40)
    reported: bool = False


class CrashEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report: CrashReport
    installation_id: UUID
    receipt_token: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        repr=False,
        pattern=r"^[A-Za-z0-9_-]{43}$",
    )
    created_epoch: float = Field(default_factory=time.time)
    attempts: int = Field(default=0, ge=0)
    next_attempt: float = 0


def process_alive(pid: int) -> bool:
    """Do not use os.kill(pid, 0) on Windows: that API can terminate the process."""
    if sys.platform == "win32":
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        api.OpenProcess.restype = ctypes.c_void_p
        api.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        api.GetExitCodeProcess.restype = ctypes.c_int
        api.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = api.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87  # Unknown/access denied: do not report.
        try:
            code = ctypes.c_uint32()
            return not api.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            api.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read(path: Path, limit: int = MAX_CRASH_BYTES) -> bytes:
    if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
        raise OSError("Crash storage cannot contain redirected files.")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("The local crash record exceeds its size limit.")
    return data


class CrashStore:
    """Only known app-owned files; consent and receipt capabilities stay account-local."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = RLock()

    def folder(self) -> Path:
        return owned_folder(self.root, "automatic-crashes")

    def consent(self) -> CrashConsent:
        with self._lock:
            path = self.folder() / "consent.json"
            if path.exists():
                return CrashConsent.model_validate_json(_read(path))
            consent = CrashConsent()
            self.save_consent(consent)  # First-session capture and registration share identity.
            return consent

    def save_consent(self, consent: CrashConsent) -> None:
        with self._lock:
            path = self.folder() / "consent.json"
            if path.exists():
                _read(path)
            atomic_text(path, consent.model_dump_json())

    def disable(self) -> CrashConsent:
        """Persist opt-out before any revocation HTTP; discard queued uploads locally."""
        with self._lock:
            consent = self.consent()
            consent.revoke_pending = (
                consent.revoke_pending or consent.enabled or consent.enrollment is not None
            )
            consent.enabled = False
            self.save_consent(consent)
            self.discard_pending()
            return consent

    def mark_registered(self, installation_id: UUID, cancel: Event) -> CrashConsent:
        with self._lock:
            consent = self.consent()
            if (
                cancel.is_set()
                or not consent.enabled
                or consent.installation_id != installation_id
                or consent.revoke_pending
            ):
                raise ValueError("Automatic-report activation was canceled.")
            consent.registered = True
            consent.enrollment = None
            self.save_consent(consent)
            return consent

    def enable(self) -> CrashConsent:
        with self._lock:
            consent = self.consent()
            if not consent.enabled:
                # Retain a pending revocation until the worker can revoke the old grant.
                consent = consent if consent.revoke_pending else CrashConsent()
                consent.enabled = True
            self.save_consent(consent)
            return consent

    def finish_revocation(self, installation_id: UUID, cancel: Event) -> CrashConsent:
        with self._lock:
            consent = self.consent()
            if (
                cancel.is_set()
                or consent.installation_id != installation_id
                or not consent.revoke_pending
            ):
                raise ValueError("Automatic-report revocation was canceled.")
            consent = CrashConsent(enabled=consent.enabled)
            self.save_consent(consent)
            return consent

    def invalidate_registration(self, installation_id: UUID) -> None:
        with self._lock:
            consent = self.consent()
            if consent.installation_id == installation_id:
                consent.registered = False
                self.save_consent(consent)

    def _session_path(self, session: CrashSession) -> Path:
        return self.folder() / f"session-{session.session_id.hex}.json"

    def save_session(self, session: CrashSession) -> None:
        with self._lock:
            atomic_text(self._session_path(session), session.model_dump_json())

    def prune_sessions(self) -> None:
        """Bound local metadata even on installations whose users turn reporting off."""
        sessions = []
        for path in self.folder().iterdir():
            if _SESSION_NAME.fullmatch(path.name):
                try:
                    session = CrashSession.model_validate_json(_read(path))
                except (OSError, ValueError):
                    continue
                sessions.append((session, path))
        sessions.sort(key=lambda pair: pair[0].created_epoch, reverse=True)
        for index, (session, path) in enumerate(sessions):
            if index >= 100 or session.created_epoch < time.time() - 7 * 86400:
                if not process_alive(session.pid):
                    path.unlink(missing_ok=True)

    def _event_path(self, event: CrashEvent) -> Path:
        return self.folder() / f"crash-{event.report.report_id}.json"

    def save_event(self, event: CrashEvent) -> None:
        data = event.model_dump_json()
        if len(data.encode()) > MAX_CRASH_BYTES:
            raise ValueError("The automatic crash report exceeds its size limit.")
        atomic_text(self._event_path(event), data)

    def pending(self) -> list[CrashEvent]:
        events = []
        for path in self.folder().iterdir():
            if not _EVENT_NAME.fullmatch(path.name):
                continue
            try:
                event = CrashEvent.model_validate_json(_read(path))
            except (OSError, ValueError):
                continue  # Preserve invalid records locally, never transmit their content.
            if event.created_epoch < time.time() - 7 * 86400:
                path.unlink()
            else:
                events.append(event)
        events.sort(key=lambda event: event.created_epoch, reverse=True)
        for event in events[10:]:
            self._event_path(event).unlink(missing_ok=True)
        return events[:10]

    def discard_pending(self) -> None:
        for path in self.folder().iterdir():
            if _EVENT_NAME.fullmatch(path.name):
                _read(path)
                path.unlink(missing_ok=True)

    def recover(self) -> list[CrashEvent]:
        """Recover only enabled, ended sessions; healthy active processes are untouched."""
        consent = self.consent()
        events = self.pending()
        if not consent.enabled or consent.revoke_pending:
            return []
        ids = {event.report.report_id for event in events}
        sessions = []
        for path in self.folder().iterdir():
            if not _SESSION_NAME.fullmatch(path.name):
                continue
            try:
                session = CrashSession.model_validate_json(_read(path))
            except (OSError, ValueError):
                continue
            if session.created_epoch < time.time() - 7 * 86400 and not process_alive(session.pid):
                path.unlink()
            elif (
                not session.reported and session.state != "clean" and not process_alive(session.pid)
            ):
                sessions.append(session)
        sessions.sort(key=lambda session: session.created_epoch, reverse=True)
        for session in sessions:
            if session.installation_id != consent.installation_id or session.session_id in ids:
                continue
            if len(events) >= 10:
                break
            stack = session.stack
            kind: Literal["python_exception", "native_fault", "unclean_shutdown"] = (
                "python_exception" if session.state == "failed" else "unclean_shutdown"
            )
            native = (
                owned_folder(self.root, "logs") / f"session-{session.session_id.hex}-native.log"
            )
            if native.exists() and native.stat().st_size:
                # Capture only stack locations. Never include raw native messages or logs.
                if native.is_symlink() or getattr(native.lstat(), "st_file_attributes", 0) & 0x400:
                    continue
                with native.open("rb") as stream:
                    stream.seek(max(0, native.stat().st_size - 64 * 1024))
                    data = stream.read(64 * 1024).decode("utf-8", errors="replace")
                stack = [
                    safe_frame(name, function, int(line))
                    for name, line, function in _NATIVE_FRAME.findall(data)
                ][-40:]
                kind = "native_fault"
            event = CrashEvent(
                report=CrashReport(
                    report_id=session.session_id,
                    created_at=session.created_at,
                    app_version=session.app_version,
                    os_version=session.os_version,
                    crash_type=kind,
                    stack=stack,
                ),
                installation_id=consent.installation_id,
            )
            self.save_event(event)
            events.append(event)
        return [event for event in events if event.installation_id == consent.installation_id]

    def accepted(self, event: CrashEvent) -> None:
        path = self.folder() / f"session-{event.report.report_id.hex}.json"
        if path.exists():
            session = CrashSession.model_validate_json(_read(path))
            session.reported = True
            self.save_session(session)
        self._event_path(event).unlink(missing_ok=True)

    def deliver(self, client: ReportClient, cancel: Event) -> int:
        sent = attempted = 0
        for event in self.recover():
            consent = self.consent()  # Recheck opt-out before each HTTP request.
            if (
                cancel.is_set()
                or not consent.enabled
                or consent.revoke_pending
                or event.installation_id != consent.installation_id
                or attempted >= 3
            ):
                break
            if event.next_attempt > time.time():
                continue
            attempted += 1
            event.attempts += 1
            event.next_attempt = time.time() + min(86400, 900 * 2 ** min(event.attempts - 1, 7))
            self.save_event(event)  # Stable identity/capability precede ambiguous delivery.
            receipt = client.submit_crash(event, consent.token, cancel)
            if receipt.state in ("received", "submitted"):
                self.accepted(event)
                sent += 1
        return sent
