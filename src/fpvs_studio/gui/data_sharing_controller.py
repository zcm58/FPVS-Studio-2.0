"""App-owned reporting jobs with explicit opt-in and stale-project guards."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from threading import Event
from types import ModuleType
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from fpvs_studio.core.data_sharing import protocol_fingerprint
from fpvs_studio.core.paths import filesystem_path, project_json_path
from fpvs_studio.core.project_service import discover_project_roots
from fpvs_studio.data_sharing import service
from fpvs_studio.data_sharing.client import DataSharingClient
from fpvs_studio.data_sharing.errors import DataSharingCancelled, DataSharingError
from fpvs_studio.data_sharing.service import ConditionAggregate, SharingView
from fpvs_studio.data_sharing.storage import load_settings
from fpvs_studio.gui.data_sharing_dialog import ComparisonRow, DataSharingDialog
from fpvs_studio.gui.update_lifecycle import (
    ProgressReporter,
    UpdateJob,
    UpdateTaskResult,
    update_lifecycle,
)

if TYPE_CHECKING:
    from fpvs_studio.gui.main_window import StudioMainWindow

_LOGGER = logging.getLogger(__name__)
_RETRY_LIMIT = 4
_STOPPING_MESSAGE = "Stopping uploads… An in-flight report may already have been received."


class DataSharingController(QObject):
    def __init__(
        self, app: QApplication, *,
        current_window: Callable[[], StudioMainWindow | None],
        backend: ModuleType | None = None,
        startup_status: Callable[[str], None] = lambda _message: None,
    ) -> None:
        super().__init__(app)
        self._backend = backend or service
        self._current_window = current_window
        self._lifecycle = update_lifecycle(app)
        self._lifecycle.shutdown_started.connect(self._shutdown)
        self._window: StudioMainWindow | None = None
        self.dialog: DataSharingDialog | None = None
        self._job: UpdateJob | None = None
        self._startup_source: tuple[Path, tuple[Path, ...]] | None = None
        self._startup_roots: list[Path] | None = None
        self._startup_problem = False
        self._startup_status = startup_status
        self._off_job: UpdateJob | None = None
        self._off_error = ""
        self._launch_waiter: tuple[StudioMainWindow, Callable[[], None]] | None = None
        self._pending: tuple[str, str | bool | tuple[str, str] | None] | None = None
        self._generation = 0
        self._view: SharingView | None = None
        self._protocol = ""
        self._labels: dict[str, str] = {}
        self._retries = 0
        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._retry)

    def startup(self, root: Path, recent_roots: tuple[Path, ...]) -> None:
        """One app-owned pass; discovery and delivery use the same launch/shutdown gate."""
        if self._startup_source is not None or self._lifecycle.is_shutting_down:
            return
        self._startup_source = (root, recent_roots)
        self._startup_status("Checking saved reports…")
        self._resume_startup()

    def _resume_startup(self) -> None:
        if (
            self._startup_source is None or self._job is not None
            or self._off_job is not None or self._lifecycle.is_shutting_down
            or self._launch_waiter is not None
            or (self._window is not None and self._window.is_launch_busy())
        ):
            return
        source = self._startup_source
        discovering = self._startup_roots is None
        if not discovering and not self._startup_roots:
            if not self._startup_problem:
                self._startup_status("")
            return
        root = None
        if not discovering:
            assert self._startup_roots is not None
            root = self._startup_roots.pop(0)
            window = self._window
            if (
                window is not None and self._current(window)
                and filesystem_path(window.document.project_root) == filesystem_path(root)
            ):
                # The open document may have unsaved protocol edits. Its existing
                # job captures authored state on the GUI thread before hashing.
                self._request("startup")
                return
        backend = self._backend

        def work(_progress: ProgressReporter, cancel: Event) -> object:
            if discovering:
                roots = discover_project_roots(source[0], cancelled=cancel.is_set)
                roots.extend(
                    path for path in source[1]
                    if filesystem_path(project_json_path(path)).is_file()
                )
                return list(dict.fromkeys(path.resolve() for path in roots))
            if cancel.is_set():
                raise DataSharingCancelled()
            return backend.sync_startup_project(root, cancel)

        job = self._lifecycle.start_task(work, keep_success_on_cancel=True)
        self._job = job

        def finished(value: object) -> None:
            self._job = None
            outcome = cast(UpdateTaskResult, value)
            if job.cancel_event.is_set() or outcome.cancelled:
                if root is not None:
                    assert self._startup_roots is not None
                    self._startup_roots.insert(0, root)
            elif outcome.error is not None:
                self._startup_problem = True
                _LOGGER.warning(
                    "Startup reporting needs attention for %s: %s",
                    root or source[0], outcome.error,
                )
                if discovering:
                    self._startup_roots = []
                self._startup_status(
                    "Saved reports need attention. See the Studio log for details."
                )
            elif discovering:
                self._startup_roots = cast(list[Path], outcome.value)
            elif outcome.value is not None:
                assert root is not None
                self._report_startup_view(root, cast(SharingView, outcome.value))
            self._run_pending()

        job.finished.connect(finished)

    def _report_startup_view(self, root: Path, view: SharingView) -> None:
        if view.status == "waiting_connection":
            if not self._startup_problem:
                self._startup_status(
                    "Saved reports are waiting for connection. "
                    "Studio will retry on its next launch."
                )
            self._startup_problem = True
        elif view.error:
            self._startup_problem = True
            _LOGGER.warning("Startup reporting needs attention for %s: %s", root, view.error)
            self._startup_status(
                "Saved reports need attention. "
                "Open Data Sharing & Comparison in the affected project."
            )
        elif view.pending_count:
            if not self._startup_problem:
                self._startup_status(
                    "Saved reports are pending. Studio will retry on its next launch."
                )
            self._startup_problem = True

    def _current(self, window: StudioMainWindow) -> bool:
        return (
            not self._lifecycle.is_shutting_down and isValid(window) and window.isVisible()
            and window is self._window and window is self._current_window()
        )

    def opened(self, window: StudioMainWindow) -> None:
        self._generation += 1
        self._retry_timer.stop()
        self._retries = 0
        self._pending = None
        self._launch_waiter = None
        self._off_error = ""
        if self._job is not None:
            self._job.cancel()
        if self.dialog is not None and isValid(self.dialog):
            self.dialog.hide()
            self.dialog.deleteLater()
        self.dialog = None
        self._window = window
        self._view = None
        self._request("sync")

    def show(self, window: StudioMainWindow) -> None:
        if self._lifecycle.is_shutting_down or window.is_launch_busy():
            return
        if window is not self._window:
            self.opened(window)
        if not self._current(window):
            return
        if self.dialog is None:
            self.dialog = DataSharingDialog(configured=self._backend.configured(), parent=window)
            self.dialog.action_requested.connect(self._action)
            self.dialog.enabled_requested.connect(self._enable)
            self.dialog.closing.connect(self._close)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
        if self._view is not None:
            self._render()
        self._request("sync")

    def session_started(
        self, window: StudioMainWindow, on_ready: Callable[[], None] | None = None,
    ) -> None:
        if self._current(window):
            self._retry_timer.stop()
            self._pending = None
            self._launch_waiter = (window, on_ready) if on_ready is not None else None
            if self._job is not None:
                self._job.cancel()
            else:
                self._release_launch_gate()

    def _release_launch_gate(self) -> None:
        if self._job is not None:
            return
        waiter, self._launch_waiter = self._launch_waiter, None
        if waiter is not None and self._current(waiter[0]):
            waiter[1]()

    def session_completed(self, window: StudioMainWindow) -> None:
        if self._current(window):
            self._retries = 0
            self._request("sync")

    def _request(self, operation: str, value: str | bool | tuple[str, str] | None = None) -> None:
        window = self._window
        if window is None or not self._current(window):
            return
        if window.is_launch_busy():
            return
        if self._off_job is not None:
            self._pending = (operation, value)
            if self.dialog is not None:
                self.dialog.set_busy(True, _STOPPING_MESSAGE)
                self.dialog.enabled_checkbox.setEnabled(False)
            return
        if self._job is not None:
            self._pending = (operation, value)
            return
        self._retry_timer.stop()
        # Capture all document state on the GUI thread. Workers never read widgets.
        root = window.document.project_root
        original_project = window.document.project
        project = original_project.model_copy(deep=True)
        labels = {condition.condition_id: condition.name for condition in project.conditions}
        backend = self._backend
        previous_view = self._view
        cached_protocol = self._protocol
        may_sync = not window.is_launch_busy()
        generation = self._generation
        dialog = self.dialog
        if dialog is not None:
            dialog.set_busy(
                True, "Updating sharing settings and comparison…",
            )

        def work(_progress: ProgressReporter, cancel: Event) -> tuple[str, SharingView]:
            if cancel.is_set():
                raise DataSharingCancelled()
            settings = (
                load_settings(root) if operation in {"load", "sync", "retry", "startup"} else None
            )
            if cancel.is_set():
                raise DataSharingCancelled()
            fingerprint = (
                cached_protocol
                if operation in {"disconnect", "archive"} or (
                    settings is not None and settings.profile is None and not settings.enabled
                )
                else protocol_fingerprint(project, root, cancelled=cancel.is_set)
            )
            if cancel.is_set():
                raise DataSharingCancelled()
            if operation == "connect":
                code, project_id = cast(tuple[str, str], value)
                result = backend.enroll_project(
                    root, code, fingerprint, cancel, project_id=project_id or None,
                )
            elif operation == "enable":
                result = backend.set_sharing_enabled(root, bool(value), fingerprint, cancel)
            elif operation == "disconnect":
                try:
                    result = backend.disconnect_project(root, fingerprint, cancel)
                except DataSharingError as error:
                    if cancel.is_set():
                        raise
                    result = replace(
                        backend.load_view(root, fingerprint, cancel), error=str(error),
                    )
            elif operation == "archive":
                result = backend.archive_project(root, fingerprint, cancel)
                if (
                    previous_view is not None
                    and result.settings.profile == previous_view.settings.profile
                    and result.latest_completed_at == previous_view.latest_completed_at
                ):
                    result = replace(result, remote=previous_view.remote)
            else:
                result = backend.load_view(root, fingerprint, cancel)
            if (
                (operation in {"sync", "retry", "startup"} or (operation == "enable" and value))
                and result.settings.enabled and may_sync
            ):
                result = backend.sync_project(
                    root, fingerprint, cancel, release_held=operation == "retry",
                    retry_offline=operation == "startup", fetch_comparison=operation != "startup",
                )
            return fingerprint, result

        job = self._lifecycle.start_task(work, keep_success_on_cancel=True)
        self._job = job

        def finished(value: object) -> None:
            self._job = None
            outcome = cast(UpdateTaskResult, value)
            current = self._current(window) and generation == self._generation
            project_changed = current and window.document.project is not original_project
            discarded = (
                not current or project_changed or job.cancel_event.is_set() or outcome.cancelled
            )
            if not discarded:
                if outcome.error is not None:
                    _LOGGER.warning("Experiment sharing operation failed (%s)",
                                    type(outcome.error).__name__)
                    if self.dialog is not None:
                        self._render()
                        self.dialog.set_busy(False, str(outcome.error))
                    self._schedule_retry()
                else:
                    self._protocol, self._view = cast(tuple[str, SharingView], outcome.value)
                    self._off_error = ""
                    self._labels = labels
                    if operation == "connect" and self.dialog is not None:
                        self.dialog.clear_invitation()
                    self._render()
                    if operation == "protocol" and self.dialog is not None:
                        QApplication.clipboard().setText(self._protocol)
                        self.dialog.status_label.setText(
                            "Protocol fingerprint copied. Ask the OpenFPVS administrator "
                            "to enable this project."
                        )
                    self._schedule_retry()
            elif current and self.dialog is not None:
                if self._off_job is not None:
                    self.dialog.set_busy(True, _STOPPING_MESSAGE)
                    self.dialog.enabled_checkbox.setEnabled(False)
                elif self._off_error:
                    self._render()
                else:
                    self.dialog.set_busy(
                        False, "Operation canceled. Reload to check current settings.",
                    )
            if project_changed and self._pending is None:
                self._pending = ("load", None)
            if operation == "startup":
                if discarded:
                    assert self._startup_roots is not None
                    self._startup_roots.insert(0, root)
                elif outcome.error is not None:
                    self._startup_problem = True
                    _LOGGER.warning("Startup reporting needs attention for %s: %s",
                                    root, outcome.error)
                    self._startup_status(
                        "Saved reports need attention. See the Studio log for details."
                    )
                elif self._view is not None:
                    self._report_startup_view(root, self._view)
            self._run_pending()

        job.finished.connect(finished)

    def _action(self, action: str) -> None:
        if action == "cancel":
            self._pending = None
            if self._job is not None:
                self._job.cancel()
            return
        window, dialog = self._window, self.dialog
        if window is None or dialog is None or not self._current(window) or window.is_launch_busy():
            return
        if action == "connect":
            code = dialog.invitation_code()
            if not code:
                dialog.set_busy(False, "Enter the lab-issued invitation code.")
                return
            self._request("connect", (code, dialog.project_id()))
        elif action == "website":
            profile = self._view.settings.profile if self._view is not None else None
            if profile is not None and profile.project_id:
                QDesktopServices.openUrl(QUrl(
                    f"{DataSharingClient.configured().origin}/projects/{profile.project_id}"
                ))
        elif action in {"retry", "disconnect", "archive", "protocol"}:
            self._retries = 0
            self._request(action)

    def _enable(self, enabled: bool) -> None:
        window = self._window
        if window is None or not self._current(window):
            return
        if not enabled:
            self._disable(window)
        elif self._off_job is None and not window.is_launch_busy():
            self._retries = 0
            self._request("enable", True)

    def _disable(self, window: StudioMainWindow) -> None:
        if self._off_job is not None:
            return
        self._retry_timer.stop()
        self._pending = None
        self._off_error = ""
        if self._job is not None:
            self._job.cancel()
        root = window.document.project_root
        fingerprint = self._protocol
        backend = self._backend
        generation = self._generation
        if self.dialog is not None:
            self.dialog.set_busy(True, _STOPPING_MESSAGE)
            self.dialog.enabled_checkbox.setEnabled(False)

        def persist_off(_progress: ProgressReporter, _cancel: Event) -> SharingView:
            # A requested local opt-out must survive Close, project handoff and Quit.
            try:
                return cast(
                    SharingView, backend.set_sharing_enabled(root, False, fingerprint, Event()),
                )
            except Exception as error:
                _LOGGER.error("Could not finish disabling experiment sharing: %s", error)
                settings = load_settings(root)
                message = (
                    "Sharing is off, but upload history needs review: "
                    if not settings.enabled else "Could not turn sharing off: "
                )
                return SharingView(
                    settings=settings, status="off" if not settings.enabled else "failed",
                    error=message + str(error),
                )

        job = self._lifecycle.start_task(
            persist_off, finish_on_shutdown=True, keep_success_on_cancel=True,
        )
        self._off_job = job

        def finished(value: object) -> None:
            if self._off_job is not job:
                return
            self._off_job = None
            outcome = cast(UpdateTaskResult, value)
            current = self._current(window) and generation == self._generation
            if outcome.error is not None:
                _LOGGER.error("Could not disable experiment sharing: %s", outcome.error)
                if current:
                    self._off_error = f"Could not turn sharing off: {outcome.error}"
                    if self.dialog is not None:
                        self._render()
                        self.dialog.set_busy(False, self._off_error)
            elif current:
                self._view = cast(SharingView, outcome.value)
                self._off_error = self._view.error
                self._render()
            self._run_pending()

        job.finished.connect(finished)

    def _run_pending(self) -> None:
        if self._job is not None or self._off_job is not None:
            return
        pending, self._pending = self._pending, None
        if pending is not None:
            self._request(*pending)
        self._release_launch_gate()
        self._resume_startup()

    def _render(self) -> None:
        view, dialog = self._view, self.dialog
        if view is None or dialog is None or not isValid(dialog):
            return
        profile = view.settings.profile
        if profile is None:
            profile_text = "No experiment enrollment. Sharing is off."
        else:
            profile_text = (
                f"{profile.title}\nExperiment: {profile.experiment_id} · Version: "
                f"{profile.experiment_version}\nProtocol SHA-256: {profile.protocol_sha256}"
            )
        status = self._off_error or view.error or {
            "disabled": "Sharing is off. Unsent reports are paused.",
            "off": "Sharing is off. Unsent reports are paused.",
            "not_enrolled": "Connect with a lab-issued code, then enable sharing explicitly.",
            "protocol_mismatch": (
                "The protocol has changed. Register this protocol before sharing resumes."
            ),
            "not_configured": "Sharing service is not configured. Local results remain available.",
            "enabled": "Automatic sharing is enabled for newly completed eligible sessions.",
            "uploaded": "Eligible completed session reports are uploaded.",
            "pending": "Reports are pending. Retry when the service is available.",
            "waiting_connection": (
                "Waiting for connection. Reports are saved locally; "
                "Studio will retry on its next launch."
            ),
            "ready": "Sharing is enabled. New eligible sessions will be reported automatically.",
            "failed": "A contribution needs attention. Review the connection, then retry.",
            "unavailable": "The sharing service is unavailable. Local results remain available.",
        }.get(view.status, view.status.replace("_", " ").capitalize())
        if not self._backend.configured() and not view.error and not self._off_error:
            status = "Sharing service is not configured. Local results remain available."
        dialog.set_state(
            connected=profile is not None, enabled=view.settings.enabled,
            profile=profile_text, status=status, pending=view.pending_count,
            held=view.held_count, uploaded=view.uploaded_count,
        )
        dialog.set_project_url(
            f"{DataSharingClient.configured().origin}/projects/{profile.project_id}"
            if profile is not None and profile.project_id else ""
        )
        remote = view.remote
        matches = remote is not None and profile is not None and (
            remote.experiment_id == profile.experiment_id
            and remote.experiment_version == profile.experiment_version
            and remote.protocol_sha256 == profile.protocol_sha256 == self._protocol
        )
        available = bool(matches and remote is not None and remote.status == "available")
        shared_rows = (
            {item.condition_id: item for item in remote.conditions} if available and remote else {}
        )
        local_rows = {item.condition_id: item for item in view.local_conditions}
        rows = []
        for condition_id in dict.fromkeys((*local_rows, *shared_rows)):
            local = local_rows.get(condition_id)
            shared = shared_rows.get(condition_id)
            rows.append(ComparisonRow(
                condition=self._labels.get(condition_id, condition_id), condition_id=condition_id,
                local=self._metric(local, shared=False), shared=self._metric(shared, shared=True),
            ))
        minimum = remote.minimum_sessions if remote is not None else 10
        devices = remote.minimum_devices if remote is not None else 3
        details = (
            f"Shared accuracy requires at least {minimum} session reports from "
            f"{devices} device enrollments "
            "per condition with compatible scoring. "
            "This task performance does not measure EEG quality."
        )
        notice = ""
        if remote is not None and remote.message:
            notice = remote.message
        elif remote is not None and not matches:
            notice = "The reference protocol does not match this experiment."
        elif not view.local_conditions:
            notice = "No eligible completed session is available locally."
        elif not view.settings.enabled:
            notice = "Enable sharing to retrieve a private aggregate comparison."
        timestamp = f" ({view.latest_completed_at})" if view.latest_completed_at else ""
        dialog.set_comparison(
            rows, scope=f"Local: latest eligible completed session{timestamp}.\n"
            "Shared: same experiment/version/protocol; this enrollment's reports are excluded.",
            notice=notice, details=details,
        )
        dialog.set_busy(False)

    @staticmethod
    def _metric(row: ConditionAggregate | None, *, shared: bool) -> str:
        if row is None:
            return "Not enough compatible reference data" if shared else "No eligible local session"
        if not row.eligible or row.fixation_targets is None or row.fixation_hits is None:
            return "Not enough compatible reference data" if shared else "Not applicable"
        accuracy = (
            f"{row.accuracy_percent:.1f}%"
            if row.accuracy_percent is not None else "No fixation targets"
        )
        sessions = "session" if row.session_count == 1 else "sessions"
        text = (
            f"{accuracy}\n{row.fixation_hits:,} hits / {row.fixation_targets:,} targets · "
            f"{row.session_count:,} {sessions}"
        )
        if shared:
            text += f" · {row.device_count:,} enrollments"
        return text

    def _schedule_retry(self) -> None:
        view = self._view
        if (
            view is not None and view.settings.enabled and view.pending_count > 0
            and self._backend.configured() and self._retries < _RETRY_LIMIT
            and not self._lifecycle.is_shutting_down
            and self._window is not None and not self._window.is_launch_busy()
        ):
            self._retry_timer.start(min(60_000 * 2**self._retries, 600_000))

    def _retry(self) -> None:
        if self._window is None or self._window.is_launch_busy():
            return
        self._retries += 1
        self._request("sync")

    def _close(self) -> None:
        self._pending = None
        if self._job is not None:
            self._job.cancel()

    def _shutdown(self) -> None:
        self._retry_timer.stop()
        self._pending = None
        self._launch_waiter = None
        if self._job is not None:
            self._job.cancel()
