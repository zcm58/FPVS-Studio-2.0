"""App-owned asynchronous library operations and whole-project import handoff."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import cast

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from fpvs_studio.core.library_installations import (
    InstalledLibraryProject,
    LibraryInstallStatus,
    scan_library_projects,
)
from fpvs_studio.core.library_origin import LibraryOriginError, LibraryProjectOrigin
from fpvs_studio.core.project_bundle import ProjectBundleManifest, read_project_bundle_manifest
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
        self._importing = False
        self._install_item: LibraryItem | None = None
        self._closing = False
        self._lifecycle = update_lifecycle(app)
        self._lifecycle.shutdown_started.connect(self._shutdown)

    def show(self) -> None:
        if self._lifecycle.is_shutting_down or self._importing:
            return
        if self.dialog is None:
            self.dialog = LibraryDialog()
            self.dialog.action_requested.connect(self._action)
            self.dialog.closing.connect(self._close)
        self._closing = False
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
        if self._job is None:
            self._start(
                lambda _progress, _cancel: self.client.connection_info(),
                self._connection_ready,
                "Reading this computer's library connection…",
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
    ) -> None:
        if self._job is not None or self._lifecycle.is_shutting_down:
            return
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
                if isinstance(outcome.error, LibraryAuthorizationError):
                    self._view().set_catalog(None)
                message = "Operation canceled." if canceled else self._error(outcome.error)
                self._view().set_busy(False, message)
            elif self._closing or self._lifecycle.is_shutting_down or job.cancel_event.is_set():
                # A transfer/enrollment may finish just before cancellation. Never
                # start an import after Close; keep successfully stored enrollment.
                if downloading or holds_download:
                    self.client.release_download()
                self._view().set_busy(False, "Operation canceled.")
            else:
                self._view().set_busy(False)
                completed(outcome.value)
            if self._closing and self._job is None:
                self._view().hide()

        job.finished.connect(finished)

    def _connection_ready(self, value: object) -> None:
        connection = cast(LibraryConnection | None, value)
        self._view().set_connection(connection)
        if connection is not None:
            self._refresh()

    def _refresh(self) -> None:
        self._view().set_catalog(None)
        self._view().set_installations(None, self.client.service_url)
        root = self._studio_root()

        def refresh(
            _progress: ProgressReporter, cancel: Event,
        ) -> tuple[LibraryCatalog, tuple[InstalledLibraryProject, ...]]:
            catalog = self.client.catalog(cancel_event=cancel)
            return catalog, scan_library_projects(root, cancel_event=cancel)

        self._start(
            refresh,
            self._catalog_ready,
            "Loading available experiments…",
        )

    def _catalog_ready(self, value: object) -> None:
        catalog, projects = cast(tuple[LibraryCatalog, tuple[InstalledLibraryProject, ...]], value)
        self._view().set_installations(projects, self.client.service_url)
        self._view().set_catalog(catalog)
        self._view().status_label.setText(
            "Select an experiment to review its contents."
            if catalog.items
            else "Your lab has not published any experiments yet."
        )

    def _action(self, action: str) -> None:
        if action == "cancel":
            if self._job is not None:
                self._job.cancel()
                self._view().status_label.setText("Canceling; waiting for the operation to stop…")
                self._view().cancel_button.setEnabled(False)
            return
        if self._job is not None or self._importing:
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
            self._refresh()
        elif action == "disconnect":
            self._start(
                lambda _progress, cancel: self.client.disconnect(cancel_event=cancel),
                self._disconnected,
                "Disconnecting this computer…",
            )
        elif action == "install":
            item = self._view().selected_item()
            if item is None or not item.compatible:
                return
            self._install_item = item
            root = self._studio_root()
            self._start(
                lambda progress, cancel: download_library_install(
                    self.client, item, root,
                    cancel_event=cancel,
                    progress_callback=progress,
                ),
                self._downloaded,
                "Checking installed projects before downloading…",
                downloading=True,
            )

    def _disconnected(self, _value: object) -> None:
        self._view().set_connection(None)
        self._view().status_label.setText(
            "Disconnected. Experiments already installed remain available offline."
        )

    def _downloaded(self, value: object) -> None:
        if isinstance(value, LibraryInstallStatus):
            self._install_item = None
            if value.state == "installed":
                self._refresh()
            elif value.project is not None:
                self._view().hide()
                self._review_project(value.project.root)
            return
        path = cast(Path, value)
        # Archive-directory and manifest parsing can be substantial. Keep this work
        # off the GUI thread and retain the payload lease until review/import ends.
        self._start(
            lambda _progress, _cancel: read_project_bundle_manifest(path),
            lambda manifest: self._review_ready(path, cast(ProjectBundleManifest, manifest)),
            "Reading experiment details for review…",
            holds_download=True,
        )

    def _review_ready(self, path: Path, manifest: ProjectBundleManifest) -> None:
        self._importing = True
        self._view().set_busy(True, "Review the experiment and its destination.")
        self._view().hide()
        try:
            assert self._install_item is not None
            item = self._install_item
            origin = LibraryProjectOrigin(
                service_url=self.client.service_url, item_id=item.item_id,
                installed_version=item.version, bundle_sha256=item.sha256,
                local_project_id=manifest.project.project_id,
            )
            self._import_bundle(path, manifest, origin, self._import_finished)
        except Exception as error:
            _LOGGER.exception("Library project import handoff failed")
            self._import_finished(None)
            self._view().status_label.setText(self._error(error))

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
        self._action("cancel")

    def _shutdown(self) -> None:
        self._closing = True
        self._action("cancel")

    @staticmethod
    def _error(error: Exception | None) -> str:
        if isinstance(error, (LibraryError, LibraryOriginError)):
            return str(error)
        _LOGGER.error("Library operation failed (%s)", type(error).__name__)
        return "The library operation could not finish. Retry or contact your lab administrator."
