"""App-owned opt-out preferences, background registration and crash delivery."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event, RLock

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QMessageBox

from fpvs_studio.gui.update_lifecycle import UpdateJob, UpdateTaskResult, update_lifecycle
from fpvs_studio.support.client import ReportCancelled, ReportClient, ReportServiceError
from fpvs_studio.support.crash_reporting import CrashConsent, CrashStore
from fpvs_studio.support.diagnostics import refresh_automatic_capture
from fpvs_studio.support.storage import support_directory

_LOGGER = logging.getLogger(__name__)
REPORT_CONTENTS = (
    "Reports include the app and operating system versions, hardware model, CPU, GPU, "
    "memory, selected software versions, the failed operation, and sanitized stack locations "
    "when available. They exclude error messages, full logs, project data, stimuli, and "
    "participant records."
)


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
        self._store_lock = RLock()
        try:
            self.client = client if client is not None else ReportClient.configured()
        except ValueError:
            self.client = ReportClient()
        self.enabled = True
        self.status = "Loading reporting preference…"
        self.busy = False
        self._consent: CrashConsent | None = None
        self._job: UpdateJob | None = None
        self._preference_job: UpdateJob | None = None
        self._stage = ""
        self._requested: bool | None = None
        self._preference_revision = 0
        self._job_revision = 0
        self._delivery_notice = ""
        self._disclosure: QMessageBox | None = None
        self._disclosure_shown = False
        self._lifecycle = update_lifecycle(app)
        self._lifecycle.shutdown_started.connect(self._shutdown)
        self._retry = QTimer(self)
        self._retry.setInterval(15 * 60 * 1000)
        self._retry.timeout.connect(self._upload)

    def store(self) -> CrashStore:
        with self._store_lock:
            if self._store is None:
                self._store = CrashStore(
                    self._root if self._root is not None else support_directory()
                )
            return self._store

    def _notify(self, message: str) -> None:
        self.status = message
        self.changed.emit(self.enabled, self.status, self.busy)

    def start(self) -> None:
        if self._job is None and self._preference_job is None:
            self._start("load", lambda cancel: self.store().consent())

    def _start(
        self, stage: str, callback: Callable[[Event], object], *, saving: bool = False
    ) -> None:
        if self._job is not None or (self._lifecycle.is_shutting_down and not saving):
            return
        self._stage = stage
        self._job_revision = self._preference_revision
        self.busy = stage == "sync"
        self._job = self._lifecycle.start_task(
            lambda progress, cancel: callback(cancel),
            keep_success_on_cancel=True,
            finish_on_shutdown=saving,
        )
        self._job.finished.connect(self._done)
        self._notify(
            "Connecting to the reporting service…"
            if stage == "sync" and self.enabled
            and self._consent is not None and not self._consent.registered
            else self.status
        )

    @Slot(bool)
    def configure(self, enabled: bool) -> None:
        self.enabled = enabled  # The opt-out control stays usable during every network stage.
        self._preference_revision += 1
        self._delivery_notice = ""
        if not enabled:
            refresh_automatic_capture(enabled=False)
            self._retry.stop()
            self._disclosure_shown = False
        if self._job is not None:
            self._job.cancel()
        self._notify("Saving preference…")
        if self._preference_job is not None:
            self._requested = enabled
            return
        self._requested = None
        # Local consent never waits for a blocked HTTP request. Serialize only
        # preference writes, and keep them alive through ordinary shutdown.
        self._preference_job = self._lifecycle.start_task(
            lambda progress, cancel: self.store().enable() if enabled else self.store().disable(),
            keep_success_on_cancel=True,
            finish_on_shutdown=True,
        )
        self._preference_job.finished.connect(self._preference_done)

    @Slot(object)
    def _preference_done(self, result: UpdateTaskResult) -> None:
        self._preference_job = None
        if self._requested is not None:
            requested, self._requested = self._requested, None
            self.configure(requested)
            return
        if self._lifecycle.is_shutting_down:
            return
        if result.error is not None or result.cancelled:
            self._preference_failed()
            return
        if isinstance(result.value, CrashConsent):
            self._consent = result.value
            self.enabled = self._consent.enabled
            if self.enabled and self._consent.expanded_disclosed:
                refresh_automatic_capture(enabled=True)
        self._report_state()
        self._upload()

    def _preference_failed(self) -> None:
        self.enabled = False
        self._consent = None
        self._retry.stop()
        self._notify(
            "Could not read or save the setting. No reports will be sent this launch."
        )

    def _sync(self, cancel: Event) -> _SyncResult:
        store = self.store()
        consent = store.consent()
        connected = False
        if consent.revoke_pending:
            self.client.revoke_crashes(consent, cancel)
            consent = store.finish_revocation(consent.installation_id, cancel)
            connected = True
        if not consent.enabled or not consent.expanded_disclosed or cancel.is_set():
            return _SyncResult(consent, connected=connected)
        store.recover()  # Freeze local recovery before a potentially blocked registration request.
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
        disclosed = self._consent is not None and self._consent.expanded_disclosed
        if (
            (self.enabled and disclosed or pending_revocation)
            and self.client.enabled
            and self._job is None
            and self._preference_job is None
        ):
            self._start("sync", self._sync)

    @Slot(object)
    def _done(self, result: UpdateTaskResult) -> None:
        stage = self._stage
        self._job = None
        self.busy = False
        if self._lifecycle.is_shutting_down:
            return
        if self._job_revision != self._preference_revision:
            # A canceled load/network result predates the operator's choice.
            self._upload()
            return
        if result.error is not None or result.cancelled:
            if result.cancelled or isinstance(result.error, ReportCancelled):
                _LOGGER.info("Automatic crash-report operation canceled (operation=%s)", stage)
            else:
                # Keep local failures diagnosable without logging messages, bodies or capabilities.
                _LOGGER.warning(
                    "Automatic crash-report operation failed "
                    "(operation=%s error_type=%s http_status=%s)",
                    stage, type(result.error).__name__,
                    result.error.status if isinstance(result.error, ReportServiceError) else None,
                )
            if stage == "load":
                self._preference_failed()
                return
            self._retry.start()
            self._delivery_notice = (
                "Delivery is unavailable. Queued reports stay on this computer and will be retried."
                if self.enabled
                else "Access revocation will retry when connected."
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
        self._report_state()
        if self.enabled and self._consent is not None and self._consent.expanded_disclosed:
            refresh_automatic_capture(enabled=True)
        if stage == "load":
            self._upload()

    def _report_state(self) -> None:
        pending_revocation = self._consent is not None and self._consent.revoke_pending
        if self.enabled or pending_revocation:
            self._retry.start()
        else:
            self._retry.stop()
        status = self._delivery_notice
        if pending_revocation and not self.enabled:
            status = "Access revocation will retry when connected."
        elif self.enabled and self._consent is not None and not self._consent.expanded_disclosed:
            status = "Review the report contents before automatic reporting starts."
            self._show_disclosure()
        elif self.enabled and not self.client.enabled:
            status = "Report delivery is paused for this launch."
        self._notify(status)

    def _show_disclosure(self) -> None:
        if self._disclosure is not None or self._disclosure_shown:
            return
        self._disclosure_shown = True
        notice = QMessageBox(QApplication.activeWindow())
        notice.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        notice.setObjectName("automatic_crash_report_disclosure")
        notice.setWindowTitle("Automatic error and crash reports")
        notice.setText(
            "Studio can send automatic reports to its maintainer after an error or crash."
        )
        notice.setInformativeText(REPORT_CONTENTS + "\n\nChange this in Settings > Diagnostics.")
        keep = notice.addButton("Keep enabled", QMessageBox.ButtonRole.AcceptRole)
        off = notice.addButton("Turn off", QMessageBox.ButtonRole.RejectRole)
        notice.setDefaultButton(keep)
        notice.setEscapeButton(off)

        def disclose() -> None:
            self._disclosure = None
            if self._lifecycle.is_shutting_down:
                return
            if notice.clickedButton() is off:
                self.configure(False)
            elif notice.clickedButton() is keep and self.enabled and self._preference_job is None:
                # A remote revocation can be in flight while the operator reads the notice.
                self._preference_revision += 1
                self._preference_job = self._lifecycle.start_task(
                    lambda progress, cancel: self.store().disclose(),
                    keep_success_on_cancel=True,
                    finish_on_shutdown=True,
                )
                self._preference_job.finished.connect(self._preference_done)

        notice.finished.connect(disclose)
        self._disclosure = notice
        notice.show()

    @Slot()
    def _shutdown(self) -> None:
        self._retry.stop()
        if self._disclosure is not None:
            self._disclosure.close()
        if self._job is not None:
            self._job.cancel()


def crash_report_controller() -> CrashReportController:
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        raise RuntimeError("Automatic reporting requires the Studio application.")
    controller = app.findChild(CrashReportController, "fpvs_automatic_crash_controller")
    return controller if controller is not None else CrashReportController(app)
