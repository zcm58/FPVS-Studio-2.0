"""Opt-out crash recovery and a bounded outbox; never collect research data or messages."""

from __future__ import annotations

import ctypes
import logging
import os
import re
import secrets
import stat
import sys
import time
from pathlib import Path
from threading import Event, RLock
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from fpvs_studio import __version__
from fpvs_studio.support.client import ReportClient
from fpvs_studio.support.models import Intent, utc_now
from fpvs_studio.support.storage import atomic_text, owned_folder

MAX_CRASH_BYTES = 32 * 1024
_MAX_SESSION_BYTES = 160 * 1024
_HANDLED_GRACE_SECONDS = 15
_SESSION_NAME = re.compile(r"session-([0-9a-f]{32})\.json\Z")
_EVENT_NAME = re.compile(r"crash-[a-f0-9-]{36}\.json\Z")
_NATIVE_FRAME = re.compile(r'File "([^"\r\n]+)", line (\d+) in ([^\r\n]+)')
_LOGGER = logging.getLogger(__name__)
_LOCK = RLock()
Operation = Literal[
    "startup", "application", "project", "processing", "presentation", "export", "unknown",
]
OSFamily = Literal["Windows", "macOS", "Linux"]
CrashType = Literal["internal_error", "python_exception", "native_fault", "unclean_shutdown"]
InventoryText = Annotated[
    str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9 .,_()+:\-]+$"),
]
UTCTimestamp = Annotated[str, Field(
    pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$",
)]
Software = Literal["python", "qt", "pyside6", "psychopy", "numpy", "scipy", "mne"]


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
    if len(module) > 160 or not re.fullmatch(
        r"fpvs_studio/(?:[a-zA-Z0-9_]+/)*[a-zA-Z0-9_]+\.py", module
    ):
        module, function = "<external>", "<external>"
    if not re.fullmatch(r"[a-zA-Z0-9_.<>-]{1,80}", function):
        function = "<unknown>"
    return StackFrame(module=module, function=function, line=min(max(line, 0), 1_000_000))


class CrashContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_build: InventoryText | None = None
    os_build: InventoryText | None = None
    hardware_model: InventoryText | None = None
    cpu_arch: InventoryText | None = None
    cpu_model: InventoryText | None = None
    process_arch: InventoryText | None = None
    translation: InventoryText | None = None
    gpus: list[InventoryText] | None = Field(default=None, max_length=4)
    ram_gib: int | None = Field(default=None, ge=1, le=65536)
    software: dict[Software, InventoryText] | None = None


class CrashReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["2"] = "2"
    kind: Literal["crash"] = "crash"
    report_id: UUID
    created_at: UTCTimestamp
    time_basis: Literal["occurrence", "recovery"]
    product: Literal["studio"] = "studio"
    app_version: InventoryText
    os_family: OSFamily
    os_version: InventoryText
    crash_type: CrashType
    operation: Operation
    stack: list[StackFrame] = Field(default_factory=list, max_length=40)
    context: CrashContext | None = None


class CrashConsent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    registered: bool = False
    installation_id: UUID = Field(default_factory=uuid4)
    workflow_generation: UUID = Field(default_factory=uuid4)
    token: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        repr=False,
        pattern=r"^[A-Za-z0-9_-]{43}$",
    )
    enrollment: Intent | None = None
    revoke_pending: bool = False
    expanded_disclosed: bool = False


class HandledIncident(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report_id: UUID = Field(default_factory=uuid4)
    created_at: str = Field(default_factory=utc_now)
    created_epoch: float = Field(default_factory=time.time)
    operation: Operation
    stack: list[StackFrame] = Field(max_length=40)
    queued: bool = False


def _same_incident(handled: list[StackFrame], fatal: list[StackFrame]) -> bool:
    # Use the innermost Studio location. External placeholders cannot identify an incident.
    leaf = next((frame for frame in reversed(handled) if frame.module != "<external>"), None)
    return leaf is not None and leaf in fatal


class CrashSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    pid: int = Field(gt=0)
    created_at: str = Field(default_factory=utc_now)
    created_epoch: float = Field(default_factory=time.time)
    app_version: str = Field(default_factory=lambda: str(__version__))
    os_version: str
    os_family: OSFamily | None = None
    context: CrashContext | None = None
    installation_id: UUID | None = None
    generation: UUID | None = None
    state: Literal["active", "clean", "failed"] = "active"
    stack: list[StackFrame] = Field(default_factory=list, max_length=40)
    failed_at: str | None = None
    operation: Operation = "unknown"
    handled: list[HandledIncident] = Field(default_factory=list, max_length=10)
    reported: bool = False


class CrashEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report: CrashReport
    installation_id: UUID
    session_id: UUID | None = None
    generation: UUID | None = None
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
        self._lock = _LOCK

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
            consent.workflow_generation = uuid4()
            self.save_consent(consent)
            self.discard_pending()
            return consent

    def disclose(self) -> CrashConsent:
        with self._lock:
            consent = self.consent()
            if consent.enabled:
                consent.expanded_disclosed = True
                self.save_consent(consent)
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
                consent = consent if consent.revoke_pending else CrashConsent(
                    expanded_disclosed=consent.expanded_disclosed,
                )
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
            consent = CrashConsent(
                enabled=consent.enabled, expanded_disclosed=consent.expanded_disclosed,
            )
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

    def update_session(self, session: CrashSession) -> bool:
        """Merge worker updates with receipt and queue state written during the session."""
        with self._lock:
            consent = self.consent()
            if (
                not consent.enabled or not consent.expanded_disclosed or consent.revoke_pending
                or consent.installation_id != session.installation_id
                or consent.workflow_generation != session.generation
            ):
                return False
            path = self._session_path(session)
            if path.exists():
                stored = CrashSession.model_validate_json(_read(path, _MAX_SESSION_BYTES))
                queued = {incident.report_id for incident in stored.handled if incident.queued}
                session.reported = stored.reported
                for incident in session.handled:
                    incident.queued = incident.report_id in queued
            self.save_session(session)
            return True

    def prune_sessions(self) -> None:
        """Bound local metadata even on installations whose users turn reporting off."""
        sessions = []
        for path in self.folder().iterdir():
            if _SESSION_NAME.fullmatch(path.name):
                try:
                    session = CrashSession.model_validate_json(_read(path, _MAX_SESSION_BYTES))
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
                try:
                    info = path.lstat()
                    if (
                        stat.S_ISREG(info.st_mode)
                        and not getattr(info, "st_file_attributes", 0) & 0x400
                    ):
                        path.unlink(missing_ok=True)
                except FileNotFoundError:
                    continue

    def recover(self) -> list[CrashEvent]:
        """Materialize eligible incidents using cached evidence and stable report IDs."""
        with self._lock:
            return self._recover()

    def _recover(self) -> list[CrashEvent]:
        consent = self.consent()
        if not consent.enabled or consent.revoke_pending or not consent.expanded_disclosed:
            return []
        events = self.pending()
        ids = {event.report.report_id for event in events}
        sessions = []
        for path in self.folder().iterdir():
            if not _SESSION_NAME.fullmatch(path.name):
                continue
            try:
                session = CrashSession.model_validate_json(_read(path, _MAX_SESSION_BYTES))
            except (OSError, ValueError):
                continue
            alive = session.state != "clean" and process_alive(session.pid)
            if session.created_epoch < time.time() - 7 * 86400 and not alive:
                path.unlink()
            elif (
                session.os_family is not None and session.installation_id == consent.installation_id
                and session.generation == consent.workflow_generation
            ):
                sessions.append((session, alive))
        sessions.sort(key=lambda pair: pair[0].created_epoch, reverse=True)
        for session, alive in sessions:
            if len(events) >= 10:
                break
            fatal = not alive and session.state != "clean" and not session.reported
            fatal = fatal and session.session_id not in ids
            kind: CrashType = (
                "python_exception" if session.state == "failed" else "unclean_shutdown"
            )
            stack = session.stack
            if fatal and kind != "python_exception":
                try:
                    native = self._native_stack(session)
                except OSError as error:
                    _LOGGER.warning(
                        "Native crash trace recovery deferred (%s)", type(error).__name__,
                    )
                    continue
                if native is not None:
                    stack, kind = native, "native_fault"
            matched = next((incident for incident in reversed(session.handled)
                            if fatal and _same_incident(incident.stack, stack)), None)
            if fatal:
                if matched is None or (not matched.queued and matched.report_id not in ids):
                    self._queue(session, events, consent, kind, stack, matched)
                # A correlated incident may already be queued or accepted. Mark the fatal
                # snapshot resolved only after an immutable event exists.
                session.reported = True
                if matched is not None:
                    matched.queued = True
                self.save_session(session)
            for incident in session.handled:
                if len(events) >= 10:
                    break
                if incident.queued or incident.report_id in ids:
                    continue
                if alive and time.time() - incident.created_epoch < _HANDLED_GRACE_SECONDS:
                    continue
                self._queue(session, events, consent, "internal_error", incident.stack, incident)
                incident.queued = True
                self.save_session(session)
        return [event for event in events if event.installation_id == consent.installation_id]

    def _queue(
        self, session: CrashSession, events: list[CrashEvent], consent: CrashConsent,
        kind: CrashType, stack: list[StackFrame], incident: HandledIncident | None,
    ) -> None:
        assert session.os_family is not None
        occurred = session.failed_at if kind == "python_exception" else None
        if incident is not None and kind == "internal_error":
            occurred = incident.created_at
        event = CrashEvent(
            report=CrashReport(
                report_id=incident.report_id if incident else session.session_id,
                created_at=occurred or utc_now(),
                time_basis="occurrence" if occurred else "recovery",
                app_version=session.app_version,
                os_family=session.os_family,
                os_version=session.os_version,
                crash_type=kind,
                operation=incident.operation if incident else session.operation,
                stack=stack,
                context=session.context,
            ),
            installation_id=consent.installation_id,
            session_id=session.session_id,
            generation=consent.workflow_generation,
        )
        self.save_event(event)
        events.append(event)

    def _native_stack(self, session: CrashSession) -> list[StackFrame] | None:
        """Read bounded native evidence, deferring on unsafe or changing traces."""
        native = owned_folder(self.root, "logs") / f"session-{session.session_id.hex}-native.log"
        # Absence is normal when native capture was unavailable; changes defer recovery.
        before = native.lstat() if native.exists() else None
        if before is None:
            return None
        if not stat.S_ISREG(before.st_mode) or getattr(before, "st_file_attributes", 0) & 0x400:
            raise OSError("The native crash trace is not a regular local file.")
        with native.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if (
                not os.path.samestat(before, opened)
                or before.st_size != opened.st_size
                or before.st_mtime_ns != opened.st_mtime_ns
            ):
                raise OSError("The native crash trace changed during recovery.")
            stream.seek(max(0, opened.st_size - 64 * 1024))
            data = stream.read(64 * 1024).decode("utf-8", errors="replace")
            final = os.fstat(stream.fileno())
            if opened.st_size != final.st_size or opened.st_mtime_ns != final.st_mtime_ns:
                raise OSError("The native crash trace changed during recovery.")
        if not opened.st_size:
            return None
        return [
            safe_frame(name, function, int(line))
            for name, line, function in _NATIVE_FRAME.findall(data)
        ][-40:]

    def accepted(self, event: CrashEvent) -> None:
        with self._lock:
            session_id = event.session_id or event.report.report_id
            path = self.folder() / f"session-{session_id.hex}.json"
            if path.exists():
                session = CrashSession.model_validate_json(_read(path, _MAX_SESSION_BYTES))
                if event.report.crash_type != "internal_error":
                    session.reported = True
                for incident in session.handled:
                    if incident.report_id == event.report.report_id:
                        incident.queued = True
                self.save_session(session)
            self._event_path(event).unlink(missing_ok=True)

    def deliver(self, client: ReportClient, cancel: Event) -> int:
        sent = attempted = 0
        for event in self.recover():
            with self._lock:
                consent = self.consent()  # Recheck opt-out before each HTTP request.
                if (
                    cancel.is_set()
                    or not consent.enabled
                    or not consent.expanded_disclosed
                    or consent.revoke_pending
                    or event.installation_id != consent.installation_id
                    or event.generation != consent.workflow_generation
                    or attempted >= 3
                ):
                    break
                if event.next_attempt > time.time() or not self._event_path(event).exists():
                    continue
                attempted += 1
                event.attempts += 1
                event.next_attempt = time.time() + min(86400, 900 * 2 ** min(event.attempts - 1, 7))
                self.save_event(event)  # Stable identity/capability precede ambiguous delivery.
            receipt = client.check_crash_receipt(event, cancel) if event.attempts > 1 else None
            if receipt is None or receipt.state == "not_received":
                latest = self.consent()
                if not latest.enabled or latest.workflow_generation != event.generation:
                    break
                receipt = client.submit_crash(event, consent.token, cancel)
            if receipt.state in ("received", "submitted"):
                self.accepted(event)
                sent += 1
        return sent
