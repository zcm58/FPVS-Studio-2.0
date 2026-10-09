"""App-owned opt-out preferences, background registration and crash delivery."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication

from fpvs_studio.gui.update_lifecycle import UpdateJob, UpdateTaskResult, update_lifecycle
from fpvs_studio.support.client import ReportClient, ReportServiceError
from fpvs_studio.support.crash_reporting import CrashConsent, CrashStore
from fpvs_studio.support.storage import support_directory

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _SyncResult:
    consent: CrashConsent
    sent: int = 0
    connected: bool = False


class CrashReportController(QObject):
    """No storage/HTTP on the GUI; one installation preference shared by app windows."""

    changed = Signal(bool, str, bool)

    def __init__(
        self, app: QApplication, *, root: Path | None = None, client: ReportClient | None = None
    ) -> None:
        super().__init__(app)
        self.setObjectName("fpvs_automatic_crash_controller")
        self._root = root
        self._store: CrashStore | None = None
        try:
            self.client = client if client is not None else ReportClient.configured()
        except ValueError:
            self.client = ReportClient()
        self.enabled = True
        self.status = "Automatic crash reporting is on by default. Loading your preference…"
        self.busy = False
        self._consent: CrashConsent | None = None
        self._job: UpdateJob | None = None
        self._stage = ""
        self._requested: bool | None = None
        self._delivery_notice = ""
        self._lifecycle = update_lifecycle(app)
        self._lifecycle.shutdown_started.connect(self._shutdown)
        self._retry = QTimer(self)
        self._retry.setInterval(15 * 60 * 1000)
        self._retry.timeout.connect(self._upload)

    def store(self) -> CrashStore:
        if self._store is None:
            self._store = CrashStore(self._root if self._root is not None else support_directory())
        return self._store

    def _notify(self, message: str) -> None:
        self.status = message
        self.changed.emit(self.enabled, self.status, self.busy)

    def start(self) -> None:
        if self._job is None:
            self._start("load", lambda cancel: self.store().consent())

    def _start(
        self, stage: str, callback: Callable[[Event], object], *, saving: bool = False
    ) -> None:
        if self._job is not None or (self._lifecycle.is_shutting_down and not saving):
            return
        self._stage = stage
        self.busy = stage == "sync"
        self._job = self._lifecycle.start_task(
            lambda progress, cancel: callback(cancel),
            keep_success_on_cancel=True,
            finish_on_shutdown=saving,
        )
        self._job.finished.connect(self._done)
        self._notify(self.status)

    @Slot(bool)
    def configure(self, enabled: bool) -> None:
        self.enabled = enabled  # The opt-out control stays usable during every network stage.
        self._delivery_notice = ""
        if not enabled:
            self._retry.stop()
        if self._job is not None:
            self._requested = enabled
            self._job.cancel()
            self._notify("Saving your crash reporting preference…")
            return
        self._requested = None
        self._notify("Saving your crash reporting preference…")
        self._start(
            "enable" if enabled else "disable",
            lambda cancel: self.store().enable() if enabled else self.store().disable(),
            saving=True,
        )

    def _sync(self, cancel: Event) -> _SyncResult:
        store = self.store()
        consent = store.consent()
        connected = False
        if consent.revoke_pending:
            self.client.revoke_crashes(consent, cancel)
            consent = store.finish_revocation(consent.installation_id, cancel)
            connected = True
        if not consent.enabled or cancel.is_set():
            return _SyncResult(consent, connected=connected)
        if not consent.registered:
            self.client.register_crashes(consent, cancel)
            consent = store.mark_registered(consent.installation_id, cancel)
            connected = True
        try:
            sent = store.deliver(self.client, cancel)
            return _SyncResult(consent, sent, connected or sent > 0)
        except ReportServiceError as error:
            if error.status in (401, 410):
                store.invalidate_registration(consent.installation_id)
            raise

    @Slot()
    def _upload(self) -> None:
        pending_revocation = self._consent is not None and self._consent.revoke_pending
        if (self.enabled or pending_revocation) and self.client.enabled and self._job is None:
            self._start("sync", self._sync)

    @Slot(object)
    def _done(self, result: UpdateTaskResult) -> None:
        stage = self._stage
        self._job = None
        self.busy = False
        if self._requested is not None:
            requested, self._requested = self._requested, None
            self.configure(requested)
            return
        if self._lifecycle.is_shutting_down:
            return
        if result.error is not None or result.cancelled:
            _LOGGER.warning("Automatic crash-report operation failed (%s)", stage)
            if stage in ("load", "enable", "disable"):
                self.enabled = False
                self._consent = None
                self._retry.stop()
                self._notify(
                    "Crash reporting could not save or read your preference. "
                    "No further reports will be sent during this launch."
                )
                return
            self._retry.start()
            self._delivery_notice = (
                "Automatic reporting is enabled. Delivery is unavailable; reports remain "
                "on this computer and will be retried later."
                if self.enabled
                else "Automatic reporting is off. Access revocation will be retried when connected."
            )
            self._notify(self._delivery_notice)
            return
        if isinstance(result.value, CrashConsent):
            self._consent = result.value
            self.enabled = self._consent.enabled
        if isinstance(result.value, _SyncResult):
            self._consent = result.value.consent
            self.enabled = self._consent.enabled
            if result.value.connected:
                self._delivery_notice = ""
        pending_revocation = self._consent is not None and self._consent.revoke_pending
        if self.enabled or pending_revocation:
            self._retry.start()
        else:
            self._retry.stop()
        self._notify(
            "Automatic crash reporting is off."
            if not self.enabled
            else "Automatic reporting is paused because this launch disabled the reporting service."
            if not self.client.enabled
            else self._delivery_notice
            or "On. Sanitized crash reports are sent at the next startup. "
            "You can turn this off here at any time."
        )
        if stage in ("load", "enable", "disable"):
            self._upload()

    @Slot()
    def _shutdown(self) -> None:
        self._retry.stop()
        if self._job is not None and self._stage not in ("enable", "disable"):
            self._job.cancel()
        if self._requested is not None:
            requested, self._requested = self._requested, None
            self._lifecycle.start_task(
                lambda progress, cancel: (
                    self.store().enable() if requested else self.store().disable()
                ),
                finish_on_shutdown=True,
                keep_success_on_cancel=True,
            )


def crash_report_controller() -> CrashReportController:
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        raise RuntimeError("Automatic reporting requires the Studio application.")
    controller = app.findChild(CrashReportController, "fpvs_automatic_crash_controller")
    return controller if controller is not None else CrashReportController(app)
