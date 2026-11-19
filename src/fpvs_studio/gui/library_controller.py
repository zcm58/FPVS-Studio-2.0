"""App-owned asynchronous library operations and whole-project import handoff."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import cast

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication

from fpvs_studio.core.library_installations import (
    InstalledLibraryProject,
    LibraryInstallStatus,
    scan_library_projects,
)
from fpvs_studio.core.library_origin import (
    MANAGED_LIBRARY_SERVICE_URL,
    LibraryOriginError,
    LibraryProjectOrigin,
    LibraryScope,
)
from fpvs_studio.core.project_bundle import (
    ProjectBundleError,
    ProjectBundleManifest,
    read_project_bundle_manifest,
)
from fpvs_studio.gui.library_dialog import LibraryDialog
from fpvs_studio.gui.update_lifecycle import (
    ProgressReporter,
    UpdateCallback,
    UpdateJob,
    UpdateTaskResult,
    update_lifecycle,
)
from fpvs_studio.library.client import LibraryClient
from fpvs_studio.library.errors import LibraryAuthorizationError, LibraryCancelled, LibraryError
from fpvs_studio.library.installations import download_library_install
from fpvs_studio.library.models import LibraryCatalog, LibraryConnection, LibraryItem
from fpvs_studio.support.error_explanations import describe_error

_LOGGER = logging.getLogger(__name__)
ImportCallback = Callable[
    [Path, ProjectBundleManifest, LibraryProjectOrigin, Callable[[Path | None], None]], None
]


class LibraryController(QObject):
    """Retain one download until the existing project importer has finished with it."""

    def __init__(
        self,
        app: QApplication,
        *,
        import_bundle: ImportCallback,
        studio_root: Callable[[], Path],
        review_project: Callable[[Path], None],
        client: LibraryClient | None = None,
    ) -> None:
        super().__init__(app)
        self.client = client or LibraryClient()
        self._import_bundle = import_bundle
        self._studio_root = studio_root
        self._review_project = review_project
        self.dialog: LibraryDialog | None = None
        self._job: UpdateJob | None = None
        self._catalog_jobs: dict[LibraryScope, UpdateJob] = {}
        self._summary_job: UpdateJob | None = None
        self._summary_timer = QTimer(self)
        self._summary_timer.setSingleShot(True)
        self._summary_timer.setInterval(160)
        self._summary_timer.timeout.connect(self._load_condition_count)
        self._importing = False
        self._install_item: tuple[LibraryItem, LibraryScope] | None = None
        self._closing = False
        self._lifecycle = update_lifecycle(app)
        self._lifecycle.shutdown_started.connect(self._shutdown)

    def show(self) -> None:
        if self._lifecycle.is_shutting_down or self._importing:
            return
        was_visible = self.dialog is not None and self.dialog.isVisible()
        if self.dialog is None:
            self.dialog = LibraryDialog(
                openfpvs=self.client.service_url == MANAGED_LIBRARY_SERVICE_URL,
            )
            self.dialog.action_requested.connect(self._action)
            self.dialog.summary_requested.connect(self._summary_timer.start)
            self.dialog.closing.connect(self._close)
        self._closing = False
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
        if self._job is None and not was_visible:
            if self.client.service_url == MANAGED_LIBRARY_SERVICE_URL:
                self._refresh("public")
            self._start_catalog(
                "lab", lambda _progress, _cancel: self.client.connection_info(),
                self._connection_ready,
            )

    def _view(self) -> LibraryDialog:
        assert self.dialog is not None
        return self.dialog

    def _start(
        self,
        callback: UpdateCallback,
        completed: Callable[[object], None],
        message: str,
        *,
        downloading: bool = False,
        holds_download: bool = False,
        scope: LibraryScope = "lab",
    ) -> None:
        if self._job is not None or self._lifecycle.is_shutting_down:
            return
        self._view().status_label.setToolTip("")
        self._view().set_busy(True, message, downloading=downloading)
        job = self._lifecycle.start_task(callback, keep_success_on_cancel=True)
        self._job = job
        job.progress_changed.connect(self._progress)

        def finished(result: object) -> None:
            self._job = None
            outcome = cast(UpdateTaskResult, result)
            canceled = outcome.cancelled or isinstance(outcome.error, LibraryCancelled)
            if outcome.error is not None or canceled:
                if holds_download:
                    self.client.release_download()
                if downloading or holds_download:
                    self._install_item = None
                if scope == "lab" and isinstance(outcome.error, LibraryAuthorizationError):
                    self._view().set_connection(None)
                message = "Operation canceled." if canceled else self._error(outcome.error)
                self._view().set_busy(False, message)
                if not canceled and isinstance(
                    outcome.error, (LibraryError, LibraryOriginError, ProjectBundleError),
                ):
                    self._view().status_label.setToolTip(
                        f"{message}\n\nDetails: {outcome.error}",
                    )
            elif self._closing or self._lifecycle.is_shutting_down or job.cancel_event.is_set():
                # A transfer/enrollment may finish just before cancellation. Never
                # start an import after Close; keep successfully stored enrollment.
                if downloading or holds_download:
                    self.client.release_download()
                    self._install_item = None
                self._view().set_busy(False, "Operation canceled.")
            else:
                self._view().set_busy(False)
                completed(outcome.value)
            if self._closing and self._job is None:
                self._view().hide()

        job.finished.connect(finished)

    def _start_catalog(
        self, scope: LibraryScope, callback: UpdateCallback, completed: Callable[[object], None],
    ) -> None:
        if scope in self._catalog_jobs or self._lifecycle.is_shutting_down:
            return
        view = self._view()
        view.set_catalog_state(scope, loading=True)
        job = self._lifecycle.start_task(callback)
        self._catalog_jobs[scope] = job

        def finished(result: object) -> None:
            if self._catalog_jobs.get(scope) is not job:
                return
            del self._catalog_jobs[scope]
            outcome = cast(UpdateTaskResult, result)
            view.set_catalog_state(scope)
            if outcome.cancelled or self._closing or self._lifecycle.is_shutting_down:
                return
            if outcome.error is not None:
                if scope == "public":
                    view.set_public_catalog(None)
                else:
                    if isinstance(outcome.error, LibraryAuthorizationError):
                        view.set_connection(None)
                    view.set_catalog(None)
                view.set_catalog_state(scope, error=self._error(outcome.error))
                return
            completed(outcome.value)

        job.finished.connect(finished)

    def _connection_ready(self, value: object) -> None:
        connection = cast(LibraryConnection | None, value)
        self._view().set_connection(connection)
        if connection is not None:
            self._refresh("lab")

    def _refresh(self, scope: LibraryScope) -> None:
        root = self._studio_root()

        def refresh(
            _progress: ProgressReporter, cancel: Event,
        ) -> tuple[LibraryCatalog, tuple[InstalledLibraryProject, ...]]:
            load = self.client.public_catalog if scope == "public" else self.client.catalog
            catalog = load(cancel_event=cancel)
            return catalog, scan_library_projects(root, cancel_event=cancel)

        self._start_catalog(scope, refresh, lambda value: self._catalog_ready(scope, value))

    def _catalog_ready(self, scope: LibraryScope, value: object) -> None:
        catalog, projects = cast(tuple[LibraryCatalog, tuple[InstalledLibraryProject, ...]], value)
        self._view().set_installations(projects, self.client.service_url)
        if scope == "public":
            self._view().set_public_catalog(catalog)
        else:
            self._view().set_catalog(catalog)

    def _load_condition_count(self) -> None:
        if self._summary_job is not None or self._closing or self._lifecycle.is_shutting_down:
            return
        view = self._view()
        item, scope = view.selected_item(), view.selected_scope()
        if item is None or not view.needs_condition_count(item, scope):
            return
        job = self._lifecycle.start_task(
            lambda _progress, cancel: self.client.condition_count(
                item, scope=scope, cancel_event=cancel,
            ),
        )
        self._summary_job = job

        def finished(result: object) -> None:
            self._summary_job = None
            if self._closing or self._lifecycle.is_shutting_down:
                return
            outcome = cast(UpdateTaskResult, result)
            if not outcome.cancelled:
                count = outcome.value if outcome.error is None else None
                view.set_condition_count(item, scope, count if isinstance(count, int) else None)
            self._summary_timer.start()

        job.finished.connect(finished)

    def _action(self, action: str) -> None:
        if action == "cancel":
            if self._job is not None:
                self._job.cancel()
                self._view().status_label.setText("Canceling; waiting for the operation to stop…")
                self._view().cancel_button.setEnabled(False)
            return
        if self._job is not None or self._importing:
            return
        if action in {"connect", "disconnect", "install"} and "lab" in self._catalog_jobs:
            return
        if action == "connect":
            code = self._view().code_edit.text().strip()
            name = self._view().device_edit.text().strip()
            self._start(
                lambda _progress, cancel: self.client.enroll(code, name, cancel_event=cancel),
                self._connection_ready,
                "Connecting this computer…",
            )
        elif action == "refresh":
            self._refresh("lab")
        elif action == "refresh-public" and self.client.service_url == MANAGED_LIBRARY_SERVICE_URL:
            self._refresh("public")
        elif action == "disconnect":
            self._start(
                lambda _progress, cancel: self.client.disconnect(cancel_event=cancel),
                self._disconnected,
                "Disconnecting this computer…",
            )
        elif action == "install":
            item = self._view().selected_item()
            if item is None or not item.compatible or not self._view().can_download:
                return
            scope = self._view().selected_scope()
            self._install_item = (item, scope)
            root = self._studio_root()
            self._start(
                lambda progress, cancel: download_library_install(
                    self.client, item, root,
                    scope=scope,
                    cancel_event=cancel,
                    progress_callback=progress,
                ),
                self._downloaded,
                "Checking installed projects before downloading…",
                downloading=True,
                scope=scope,
            )

    def _disconnected(self, _value: object) -> None:
        self._view().set_connection(None)
        self._view().set_catalog_state(
            "lab", error="Disconnected. Experiments already installed remain available offline.",
        )
        target = self._view().connect_toggle
        if target.isVisible():
            target.setFocus()
        else:
            self._view().code_edit.setFocus()

    def _downloaded(self, value: object) -> None:
        if isinstance(value, LibraryInstallStatus):
            assert self._install_item is not None
            _item, scope = self._install_item
            self._install_item = None
            if value.state == "installed":
                self._refresh(scope)
            elif value.project is not None:
                self._view().hide()
                self._review_project(value.project.root)
            return
        path = cast(Path, value)
        assert self._install_item is not None
        # Archive-directory and manifest parsing can be substantial. Keep this work
        # off the GUI thread and retain the payload lease until review/import ends.
        self._start(
            lambda _progress, _cancel: read_project_bundle_manifest(path),
            lambda manifest: self._review_ready(path, cast(ProjectBundleManifest, manifest)),
            "Reading experiment details for review…",
            holds_download=True,
            scope=self._install_item[1],
        )

    def _review_ready(self, path: Path, manifest: ProjectBundleManifest) -> None:
        self._importing = True
        self._view().set_busy(True, "Review the experiment and its destination.")
        self._view().hide()
        try:
            assert self._install_item is not None
            item, scope = self._install_item
            origin = LibraryProjectOrigin(
                service_url=self.client.service_url, item_id=item.item_id,
                installed_version=item.version, bundle_sha256=item.sha256,
                local_project_id=manifest.project.project_id,
                scope=scope,
            )
            self._import_bundle(path, manifest, origin, self._import_finished)
        except Exception as error:
            _LOGGER.exception("Library project import handoff failed")
            self._import_finished(None)
            message = self._error(error)
            self._view().status_label.setText(message)
            if isinstance(error, (LibraryError, LibraryOriginError, ProjectBundleError)):
                self._view().status_label.setToolTip(f"{message}\n\nDetails: {error}")

    def _import_finished(self, project_root: Path | None) -> None:
        self.client.release_download()
        self._importing = False
        self._install_item = None
        self._view().set_busy(
            False,
            (
                f"Experiment installed at {project_root}. Review Setup before running."
                if project_root is not None
                else "Setup canceled or unsuccessful. You can try again."
            ),
        )
        if project_root is None and not self._lifecycle.is_shutting_down:
            self._view().show()
            self._view().raise_()

    def _progress(self, received: object, total: object) -> None:
        if isinstance(received, int) and isinstance(total, int) and total > 0:
            self._view().show_progress(received, total)

    def _close(self) -> None:
        self._closing = True
        self._summary_timer.stop()
        if self._summary_job is not None:
            self._summary_job.cancel()
        for job in self._catalog_jobs.values():
            job.cancel()
        self._catalog_jobs.clear()
        self._action("cancel")

    def _shutdown(self) -> None:
        self._close()

    @staticmethod
    def _error(error: Exception | None) -> str:
        if isinstance(error, (LibraryError, LibraryOriginError, ProjectBundleError)):
            return describe_error("Experiment Library", error)
        _LOGGER.error("Library operation failed (%s)", type(error).__name__)
        return "The library operation could not finish. Retry or contact your lab administrator."
