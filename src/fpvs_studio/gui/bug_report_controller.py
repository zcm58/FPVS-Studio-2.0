"""Application-owned report editor and asynchronous support operations."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import cast

from PySide6.QtCore import QObject, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from fpvs_studio.gui.report_bug_dialog import ReportBugDialog
from fpvs_studio.gui.update_lifecycle import UpdateJob, UpdateTaskResult, update_lifecycle
from fpvs_studio.support.client import Receipt, ReportClient, ReportServiceError
from fpvs_studio.support.diagnostics import bounded_text, collect_diagnostics, redact
from fpvs_studio.support.models import Delivery, Draft, Intent, Report, ReportKind
from fpvs_studio.support.storage import DraftStore, export_report, support_directory


class _NotSent(ReportServiceError):
    """The local receipt could not be saved; the upload never started."""


class BugReportController(QObject):
    """Use the existing app-owned task lifecycle for save/network shutdown safety."""

    def __init__(
        self, app: QApplication, *, root: Path | None = None,
        client: ReportClient | None = None, kind: ReportKind = "bug"
    ) -> None:
        super().__init__(app)
        self.kind = kind
        self.setObjectName(f"fpvs_{kind}_report_controller")
        self._app = app
        self._root = root
        self._store: DraftStore | None = None
        self._configuration_error = ""
        try:
            self.client = client if client is not None else ReportClient.configured()
        except ValueError:
            self.client = ReportClient()
            self._configuration_error = (
                "The reporting connection is invalid. Save or copy your report."
            )
        self.dialog: ReportBugDialog | None = None
        self._job: UpdateJob | None = None
        self._intent: Intent | None = None
        self._verification_deadline = 0.0
        self._closing = False
        self._dirty = False
        self._saving = False
        self._save_failed = False
        self._loaded = False
        self._error_context: tuple[str, str] | None = None
        self._lifecycle = update_lifecycle(app)
        self._lifecycle.shutdown_started.connect(self._shutdown)
        self._autosave = QTimer(self)
        self._autosave.setSingleShot(True)
        self._autosave.setInterval(900)
        self._autosave.timeout.connect(self._save_draft)
        self._poll = QTimer(self)
        self._poll.setSingleShot(True)
        self._poll.setInterval(3000)
        self._poll.timeout.connect(self._poll_verification)

    def store(self) -> DraftStore:
        if self._store is None:
            self._store = DraftStore(
                self._root if self._root is not None else support_directory(), kind=self.kind
            )
        return self._store

    def _empty_draft(self) -> Draft:
        return Draft(report=Report(kind=self.kind), include_logs=self.kind == "bug")

    def show(self, title: str = "", details: str = "") -> None:
        if self._lifecycle.is_shutting_down:
            return
        self._closing = False
        if self.dialog is None:
            self.dialog = ReportBugDialog(self._empty_draft(), online=self.client.enabled)
            self.dialog.action_requested.connect(self._action)
            self.dialog.export_requested.connect(self._export)
            self.dialog.draft_changed.connect(self._edited)
            self.dialog.closing.connect(self._close)
        dialog = self.dialog
        if not dialog.isVisible():
            # First-run setup is modal. The report must remain interactive above it.
            dialog.setWindowModality(
                Qt.WindowModality.ApplicationModal
                if QApplication.activeModalWidget() is not None
                else Qt.WindowModality.NonModal
            )
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        if self.kind == "bug" and (title or details):
            self._error_context = (redact(title), bounded_text(redact(details)))
            if self._loaded:
                dialog.offer_error(*self._error_context)
        if not self._loaded and self._job is None:
            self._start(self._load, self._loaded_result, "loading", "Loading local report draft…")

    def _load(self, cancel: Event) -> object:
        store = self.store()
        draft = store.load_latest()
        fresh = draft is None
        if draft is None:
            draft = self._empty_draft()
            if self.kind == "bug":
                draft.report.diagnostics = collect_diagnostics(store.root)
        return draft, fresh

    def _loaded_result(self, value: object) -> None:
        dialog = self._dialog()
        self._loaded = True
        draft, fresh = cast(tuple[Draft, bool], value)
        dialog.set_draft(draft)
        if self._error_context is not None:
            dialog.offer_error(*self._error_context)
            if fresh:
                dialog.use_pending_error()
        self._show_delivery(draft)

    def _dialog(self) -> ReportBugDialog:
        assert self.dialog is not None
        return self.dialog

    def _start(
        self,
        callback: Callable[[Event], object],
        done: Callable[[object], None],
        state: str = "",
        message: str = "",
        *,
        saving: bool = False,
    ) -> None:
        if self._job is not None or (self._lifecycle.is_shutting_down and not saving):
            return
        if state:
            self._dialog().set_state(state, message)
        job = self._lifecycle.start_task(
            lambda _progress, cancel: callback(cancel),
            keep_success_on_cancel=True,
            finish_on_shutdown=saving,
        )
        self._job = job
        self._saving = saving

        def finished(result: object) -> None:
            self._job = None
            self._saving = False
            outcome = cast(UpdateTaskResult, result)
            if outcome.cancelled:
                self._intent = None
                self._poll.stop()
                self._dialog().set_state(
                    "editing", "Canceled. If upload began, check the receipt before retrying."
                )
            elif outcome.error is not None:
                self._poll.stop()
                self._intent = None
                if isinstance(outcome.error, _NotSent):
                    draft = self._dialog().snapshot()
                    draft.delivery = "editing"
                    self._dialog().set_delivery(draft)
                if not self._loaded:
                    self._loaded = True
                    if self._error_context is not None:
                        self._dialog().offer_error(*self._error_context)
                self._dialog().set_state("editing", self._safe_error(outcome.error))
                if saving:
                    self._save_failed = True
                    self._dirty = True
                    if self._closing and not self._lifecycle.is_shutting_down:
                        self._closing = False
                        self._dialog().show()
                        self._dialog().raise_()
            elif job.cancel_event.is_set() and not isinstance(outcome.value, Receipt):
                self._dialog().set_state("editing", "Canceled. Your report remains available.")
            else:
                if saving:
                    self._save_failed = False
                done(outcome.value)
            if self._save_failed:
                self._autosave.stop()
            elif self._closing and self._dirty:
                self._save_draft()
            elif self._dirty:
                self._autosave.start()

        job.finished.connect(finished)

    @staticmethod
    def _safe_error(error: Exception) -> str:
        if isinstance(error, ReportServiceError):
            return str(error)
        return (
            "Local report storage or diagnostics could not be read or saved. "
            "Your text remains in this window; copy it or save it to another location."
        )

    def _edited(self) -> None:
        if self._loaded:
            self._dirty = True
            self._autosave.start()

    def _save_draft(self) -> None:
        if self.dialog is None or not self._loaded or not self._dirty:
            return
        if self._job is not None:
            return
        snapshot = self.dialog.snapshot()
        self._dirty = False
        self._start(lambda _cancel: self.store().save(snapshot), lambda _value: None, saving=True)

    def _close(self) -> None:
        self._closing = True
        self._poll.stop()
        self._intent = None
        if self._job is not None and not self._saving:
            self._job.cancel()
        self._autosave.stop()
        if self._loaded:
            self._show_delivery(self._dialog().snapshot())
        self._save_draft()

    def _shutdown(self) -> None:
        self._closing = True
        self._autosave.stop()
        self._poll.stop()
        self._intent = None
        self._save_draft()

    def _action(self, action: str) -> None:
        dialog = self._dialog()
        if action == "cancel":
            self._poll.stop()
            self._intent = None
            if self._job is not None and not self._saving:
                self._job.cancel()
            dialog.set_state(
                "editing", "Canceled. If upload began, use Check status before retrying."
            )
            return
        if action == "browser":
            self._open_browser()
            return
        if self._job is not None:
            dialog.status_label.setText("Finishing the current report operation. Please try again.")
            return
        self._autosave.stop()
        if action == "submit":
            self._begin_submit()
        elif action == "check":
            draft = dialog.snapshot()
            self._start(
                lambda cancel: self.client.check_receipt(draft, cancel),
                self._receipt_result,
                "checking",
                "Checking report receipt…",
            )
        elif action == "refresh" and self.kind == "bug" and not dialog.snapshot().locked:

            def refreshed(value: object) -> None:
                dialog.diagnostics_edit.setPlainText(str(value))
                self._show_delivery(dialog.snapshot())

            self._start(
                lambda _cancel: collect_diagnostics(self.store().root),
                refreshed,
                "loading",
                "Collecting recent application logs…",
            )
        elif action in ("new", "discard"):
            draft = dialog.snapshot()
            if draft.delivery in ("received", "uncertain") or self._intent is not None:
                dialog.status_label.setText(
                    "Check the existing receipt before starting another report."
                )
                return
            if action == "new" and draft.delivery != "submitted":
                dialog.status_label.setText(
                    "Finish this report, or choose Discard Draft to start again."
                )
                return
            self._dirty = False
            self._start(
                lambda _cancel: self.store().discard(draft),
                self._new_draft,
                "loading",
                "Discarding local draft…",
            )

    def _new_draft(self, _value: object) -> None:
        self._intent = None
        self._dialog().set_draft(self._empty_draft())
        self._dialog().context_button.hide()
        self._show_delivery(self._dialog().snapshot())

    def _export(self, filename: str) -> None:
        if self._job is not None:
            self._dialog().status_label.setText(
                "Finish the current operation, then save the report."
            )
            return
        draft = self._dialog().snapshot()
        self._start(
            lambda _cancel: export_report(Path(filename), draft),
            lambda _value: self._dialog().status_label.setText(
                "Report saved as text. Nothing was sent."
            ),
        )

    def _begin_submit(self) -> None:
        draft = self._dialog().snapshot()
        if not self.client.enabled or draft.locked:
            return
        draft.service_url = self.client.origin
        self._dialog().set_delivery(draft)

        def begin(cancel: Event) -> object:
            self.store().save(draft)
            return self.client.create_intent(draft, cancel)

        self._start(begin, self._intent_ready, "verifying", "Preparing browser verification…")

    def _intent_ready(self, value: object) -> None:
        if self._closing:
            return
        self._intent = cast(Intent, value)
        self._verification_deadline = time.monotonic() + 120
        self._dialog().set_state(
            "verifying", "Complete verification in your browser to send the report."
        )
        self._open_browser()
        self._poll.start()

    def _open_browser(self) -> None:
        if self._intent is not None:
            if not QDesktopServices.openUrl(QUrl(self.client.verification_url(self._intent))):
                self._dialog().status_label.setText(
                    "Could not open the browser. Try Open verification page or save the report."
                )

    def _poll_verification(self) -> None:
        if self._intent is None or self._closing:
            return
        if self._job is not None:
            self._poll.start()
            return
        if time.monotonic() >= self._verification_deadline:
            self._intent = None
            self._dialog().set_state("editing", "Verification timed out. Submit again to resume.")
            return
        intent = self._intent
        self._start(lambda cancel: self.client.intent_status(intent, cancel), self._verified)

    def _verified(self, value: object) -> None:
        if self._intent is None or self._closing:
            return
        if value == "pending":
            self._poll.start()
        elif value == "expired":
            self._intent = None
            self._dialog().set_state("editing", "Verification expired. Submit again to resume.")
        else:
            intent = self._intent
            draft = self._dialog().snapshot()
            draft.delivery = "uncertain"
            self._dialog().set_delivery(draft)
            self._dirty = False

            def send(cancel: Event) -> object:
                try:
                    self.store().save(draft)  # Durable identity BEFORE any upload bytes.
                except (OSError, ValueError):
                    raise _NotSent(
                        "Nothing was sent: the local receipt could not be saved. "
                        "Copy your report or save it to another location."
                    ) from None
                return self.client.submit(draft, intent, cancel)

            self._start(send, self._receipt_result, "sending", "Sending the reviewed report…")

    def _receipt_result(self, value: object) -> None:
        receipt = cast(Receipt, value)
        draft = self._dialog().snapshot()
        draft.delivery = (
            "editing" if receipt.state == "not_received" else cast(Delivery, receipt.state)
        )
        self._dialog().set_delivery(draft)
        self._intent = None
        self._dirty = True
        self._show_delivery(draft)

    def _show_delivery(self, draft: Draft) -> None:
        messages = {
            "editing": self._configuration_error or self._dialog().connection_notice(),
            "received": "Report received; GitHub issue creation is pending.",
            "submitted": "Report submitted. Thank you for helping improve FPVS Studio.",
            "uncertain": "Delivery is uncertain. Check status before another submission.",
        }
        message = messages[draft.delivery]
        if draft.locked:
            message += f" Receipt: {draft.report.report_id}"
            if not self.client.enabled:
                message += " Online status checks are unavailable until reporting is connected."
        self._dialog().set_state("editing", message)


def report_controller(kind: ReportKind = "bug") -> BugReportController:
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        raise RuntimeError("Bug reporting requires the desktop application.")
    controller = app.findChild(BugReportController, f"fpvs_{kind}_report_controller")
    return controller if controller is not None else BugReportController(app, kind=kind)


def show_bug_report(title: str = "", details: str = "") -> None:
    report_controller().show(title, details)


def show_feature_request() -> None:
    report_controller("feature").show()
