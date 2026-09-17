"""Application-owned jobs for the bundled Experiment Library publisher."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import cast

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from fpvs_studio.developer.library_publisher import (
    PreparedPublication,
    PublicationResult,
    PublisherAccess,
    PublisherCancelled,
    PublisherError,
    PublisherService,
)
from fpvs_studio.gui.library_publisher_dialog import LibraryPublisherDialog
from fpvs_studio.gui.update_lifecycle import UpdateJob, UpdateTaskResult, update_lifecycle

_LOGGER = logging.getLogger(__name__)


def publication_review(prepared: PreparedPublication) -> str:
    """Build the plain-text review in the preparation worker, without widget access."""
    report = prepared.report
    return "\n".join(
        (
            f"{prepared.request.title} · version {prepared.request.version}",
            f"Library ID: {prepared.request.item_id}",
            f"Minimum Studio: {prepared.request.minimum_studio_version}",
            f"Description: {prepared.request.summary}",
            "",
            f"{report.condition_count:,} conditions · "
            f"{report.stimulus_set_count:,} stimulus sets · "
            f"{report.task_count:,} tasks",
            f"{report.file_count:,} files · {report.size_bytes / 1048576:.2f} MB",
            f"SHA-256: {report.sha256}",
            f"Prepared bundle: {prepared.bundle_path}",
            "",
            "Review authored text and images for identifying information before publishing.",
            "",
            "SANITIZED FIELDS",
            *report.sanitized_fields,
            "",
            "INCLUDED FILES",
            *report.included_paths,
            "",
            "OMITTED FILES",
            *(report.excluded_paths or ("None",)),
        )
    )


class LibraryPublisherController(QObject):
    """Keep prepared bytes for exact retries and defer teardown until workers exit."""

    def __init__(self, app: QApplication, *, service: PublisherService) -> None:
        super().__init__(app)
        self.service = service
        self.dialog: LibraryPublisherDialog | None = None
        self._lifecycle = update_lifecycle(app)
        self._lifecycle.shutdown_started.connect(self._shutdown)
        self._job: UpdateJob | None = None
        self._operation = ""
        self._prepared: PreparedPublication | None = None
        self._attempted = False
        self._result: PublicationResult | None = None
        self._retained_attempts: dict[tuple[str, str], Path] = {}
        self._closing = False
        self._project_root: Path | None = None
        self._title = ""
        self._item_id = ""
        self._save_project: Callable[[], bool] | None = None

    def show(
        self,
        *,
        project_root: Path,
        title: str,
        item_id: str,
        save_project: Callable[[], bool],
    ) -> None:
        if self._lifecycle.is_shutting_down:
            return
        if self.dialog is None:
            self.dialog = LibraryPublisherDialog()
            self.dialog.action_requested.connect(self._action)
            self.dialog.closing.connect(self._close)
        if self._job is not None:
            self.dialog.show()
            self.dialog.raise_()
            self.dialog.activateWindow()
            return
        changed_project = self._project_root != project_root
        self._project_root, self._title, self._item_id = project_root, title, item_id
        self._save_project = save_project
        self._closing = False
        if self._prepared is None and changed_project:
            self.dialog.set_context(title=title, item_id=item_id)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
        if self._job is None:
            self._check_access()

    def _view(self) -> LibraryPublisherDialog:
        assert self.dialog is not None
        return self.dialog

    def _start(
        self,
        operation: str,
        work: Callable[[Event], object],
        done: Callable[[object], None],
        message: str,
    ) -> None:
        if self._job is not None or self._lifecycle.is_shutting_down:
            return
        self._operation = operation
        self._view().set_busy(True, message)
        job = self._lifecycle.start_task(
            lambda _progress, cancel: work(cancel),
            keep_success_on_cancel=True,
        )
        self._job = job

        def finished(value: object) -> None:
            outcome = cast(UpdateTaskResult, value)
            self._job = None
            self._operation = ""
            canceled = outcome.cancelled or isinstance(outcome.error, PublisherCancelled)
            if outcome.error is None and not canceled:
                self._view().set_busy(False, "")
                # A confirmed publish/discard remains completed even when Cancel
                # arrived just after its final operation. Never report it as undone.
                done(outcome.value)
            elif operation == "publish":
                self._view().publish_button.setText("Retry same bundle")
                detail = self._safe_error(outcome.error) if not canceled else "Publishing stopped."
                self._view().set_busy(
                    False,
                    (
                        f"{detail} Remote state may have changed. "
                        "The prepared files are retained; retry uses exactly the same bundle."
                    ),
                )
            else:
                if operation == "access":
                    self._view().set_access(False, "Developer publishing access is not verified.")
                self._view().set_busy(
                    False,
                    (
                        "Operation canceled. No upload was requested."
                        if canceled
                        else self._safe_error(outcome.error)
                    ),
                )
            if self._closing:
                self._view().hide()

        job.finished.connect(finished)

    def _check_access(self) -> None:
        self._view().set_access(False, "Checking GitHub owner and repository write access…")
        self._start(
            "access",
            lambda cancel: self.service.check_access(cancel_event=cancel),
            self._access_ready,
            "Checking developer access…",
        )

    def _access_ready(self, value: object) -> None:
        access = cast(PublisherAccess, value)
        self._view().set_access(True, f"GitHub: {access.login} · {access.repository}")
        if self._result is not None:
            self._published(self._result)
        elif self._prepared is not None:
            request = self._prepared.request
            uncertain = (
                "A prior publish was not confirmed; remote state may have changed. "
                if self._attempted else ""
            )
            self._view().status_label.setText(
                f'{uncertain}Retained bundle: "{request.title}" (version {request.version}). '
                "Publish uses these reviewed files; the source folder is listed in the review. "
                f'Edit starts a new copy of the currently open experiment, "{self._title}".'
            )

    def _action(self, action: str) -> None:
        if action == "cancel":
            if self._job is not None:
                self._job.cancel()
                self._view().cancel_button.setEnabled(False)
                self._view().status_label.setText(
                    "Stopping publishing. Remote state may have changed; "
                    "prepared files will be retained."
                    if self._operation == "publish"
                    else "Canceling; waiting for the operation to finish…"
                )
            return
        if self._job is not None or self._lifecycle.is_shutting_down:
            return
        if action == "access":
            self._check_access()
        elif action == "prepare" and self._prepared is None:
            self._prepare()
        elif action == "publish" and self._prepared is not None:
            if not self._view().publish_button.isEnabled():
                return
            prepared = self._prepared
            self._attempted = True
            self._start(
                "publish",
                lambda cancel: self.service.publish(prepared, cancel_event=cancel),
                self._published,
                "Publishing the reviewed bundle and updating the library catalog…",
            )
        elif action == "edit" and self._prepared is not None:
            prepared = self._prepared
            if self._attempted and self._result is None:
                self._retained_attempts[(prepared.request.item_id, prepared.request.version)] = (
                    prepared.bundle_path
                )
                self._discarded(None)
                self._view().version_edit.clear()
                self._view().review_edit.setPlainText(
                    "The previous publication was not confirmed. Its exact files remain at:\n"
                    f"{prepared.bundle_path}\n\n"
                    "Use a new version for a new bundle. The retained copy can be retried "
                    "with the developer publishing script."
                )
                self._view().status_label.setText(
                    "Previous files retained because remote state may have changed. "
                    "Enter a new version before preparing the currently open experiment."
                )
                return
            self._start(
                "discard",
                lambda _cancel: self.service.discard(prepared),
                self._discarded,
                "Removing the prepared local copy…",
            )

    def _prepare(self) -> None:
        if not self._view().prepare_button.isEnabled():
            return
        try:
            request = self._view().request()
        except PublisherError as error:
            self._view().set_busy(False, str(error))
            return
        if (request.item_id, request.version) in self._retained_attempts:
            self._view().status_label.setText(
                "That library ID and version already has an uncertain publication. "
                "Choose a new version; the earlier files are retained for an exact retry."
            )
            return
        if self._save_project is None or not self._save_project():
            self._view().status_label.setText(
                "Save the current experiment before preparing a bundle."
            )
            return
        project_root = self._project_root
        assert project_root is not None

        def prepare(cancel: Event) -> object:
            prepared = self.service.prepare(project_root, request, cancel_event=cancel)
            return prepared, f"Source experiment: {project_root}\n\n" + publication_review(prepared)

        self._start(
            "prepare", prepare, self._prepared_ready, "Saving a clean local bundle for review…"
        )

    def _prepared_ready(self, value: object) -> None:
        self._prepared, review = cast(tuple[PreparedPublication, str], value)
        self._attempted = False
        self._result = None
        self._view().set_prepared(True, review)
        self._view().status_label.setText(
            "Review the inventory and authored content. Publish uploads this exact bundle "
            "and adds it to the library catalog."
        )

    def _published(self, value: object) -> None:
        result = cast(PublicationResult, value)
        self._result = result
        self._view().set_published()
        self._view().status_label.setText(
            f"Published to {result.repository} · {result.tag}. "
            f"Catalog commit: {result.catalog_commit}"
        )

    def _discarded(self, _value: object) -> None:
        self._prepared = None
        self._attempted = False
        self._result = None
        self._view().set_prepared(False)
        self._view().set_context(title=self._title, item_id=self._item_id)
        self._view().status_label.setText("Edit the details, then prepare a new bundle for review.")

    def _close(self) -> None:
        self._closing = True
        self._action("cancel")

    def _shutdown(self) -> None:
        self._closing = True
        self._action("cancel")

    @staticmethod
    def _safe_error(error: Exception | None) -> str:
        if isinstance(error, PublisherError):
            return str(error)
        _LOGGER.error("Developer Library publishing failed (%s)", type(error).__name__)
        return (
            "Publishing could not finish. Check GitHub access and retry."
        )
