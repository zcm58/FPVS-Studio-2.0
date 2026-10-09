"""App-owned whole-project preparation/upload jobs with exact-byte retries."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import cast
from uuid import uuid4

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from fpvs_studio import __version__
from fpvs_studio.developer.library_publisher import (
    PreparedPublication,
    PublicationRequest,
    PublisherError,
    PublisherService,
)
from fpvs_studio.gui.library_publisher_controller import publication_review
from fpvs_studio.gui.library_submission_dialog import LibrarySubmissionDialog
from fpvs_studio.gui.update_lifecycle import UpdateJob, UpdateTaskResult, update_lifecycle
from fpvs_studio.library.client import LibraryClient
from fpvs_studio.library.errors import LibraryError
from fpvs_studio.library.submissions import (
    SubmissionList,
    SubmissionStatus,
    list_submissions,
    submit_project,
)


class LibrarySubmissionController(QObject):
    def __init__(self, app: QApplication, *, client: LibraryClient | None = None) -> None:
        super().__init__(app)
        self.client = client or LibraryClient()
        self.service = PublisherService()
        self.lifecycle = update_lifecycle(app)
        self.dialog = LibrarySubmissionDialog()
        self.dialog.action_requested.connect(self._action)
        self.dialog.closing.connect(self._cancel)
        self.lifecycle.shutdown_started.connect(self._cancel)
        self._job: UpdateJob | None = None
        self._prepared: PreparedPublication | None = None
        self._attempted = False
        self._completed = False
        self._source: Path | None = None
        self._save: Callable[[], bool] | None = None
        self._identity: tuple[str, str] | None = None
        self._current_project: tuple[Path, str, str, Callable[[], bool]] | None = None
        self._retained_uploads: dict[str, tuple[PreparedPublication, tuple[str, str]]] = {}

    def show(
        self,
        *,
        project_root: Path,
        title: str,
        description: str,
        save_project: Callable[[], bool],
    ) -> None:
        changed_project = self._current_project is None or self._current_project[0] != project_root
        self._current_project = project_root, title, description, save_project
        if self._prepared is None and self._job is None:
            self._bind_current_project()
            if changed_project:
                self.dialog.rights.setChecked(False)
            self.dialog.set_state(False, False, False)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _bind_current_project(self) -> None:
        if self._current_project is not None:
            self._source, title, description, self._save = self._current_project
            self.dialog.title_edit.setText(title)
            self.dialog.description.setPlainText(description)

    def _status(self, text: str) -> None:
        self.dialog.status.setText(text if len(text) <= 240 else text[:237] + "…")
        self.dialog.status.setToolTip(text)
        self.dialog.status.setAccessibleDescription(text)

    def _cancel(self) -> None:
        if self._job is not None:
            self._job.cancel()
            self._status("Canceling…")

    def _start(
        self, operation: Callable[[Event], object], finished: Callable[[object], None], message: str
    ) -> None:
        if self._job is not None or self.lifecycle.is_shutting_down:
            return
        self.dialog.set_state(True, self._prepared is not None, self._attempted, self._completed)
        self._status(message)
        job = self.lifecycle.start_task(lambda _progress, cancel: operation(cancel))
        self._job = job

        def complete(value: object) -> None:
            result = cast(UpdateTaskResult, value)
            self._job = None
            if result.cancelled:
                self._status("Canceled. You can retry this upload.")
            elif result.error is not None:
                detail = (
                    str(result.error)
                    if isinstance(result.error, (LibraryError, PublisherError))
                    else "The operation failed. Check project files and network, then retry."
                )
                self._status(detail)
            else:
                finished(result.value)
            if (
                self._job is None and self._prepared is None and self._current_project is not None
                and self._save is not self._current_project[3]
            ):
                self._bind_current_project()
                self.dialog.rights.setChecked(False)
            self.dialog.set_state(
                self._job is not None, self._prepared is not None, self._attempted, self._completed
            )

        job.finished.connect(complete)

    def _action(self, action: str) -> None:
        if action == "cancel":
            self._cancel()
            return
        if self._job is not None or self.lifecycle.is_shutting_down:
            return
        if (
            action == "submit"
            and not self._completed
            and self.dialog.rights.isChecked()
            and self._prepared is None
        ):
            if (
                not self.dialog.author_edit.text().strip()
                or "@" not in self.dialog.email_edit.text()
            ):
                self._status("Enter your name and a contact email.")
                return
            try:
                request = PublicationRequest(
                    f"submitted-{uuid4()}",
                    self.dialog.title_edit.text().strip(),
                    "1.0.0",
                    self.dialog.description.toPlainText(),
                    __version__,
                )
            except PublisherError as error:
                self._status(str(error))
                return
            if self._save is None or not self._save():
                self._status("Save the current project before uploading.")
                return
            source = self._source
            assert source is not None
            identity = (
                self.dialog.author_edit.text().strip(),
                self.dialog.email_edit.text().strip(),
            )
            self._identity = identity
            self._start(
                lambda cancel: self.service.prepare(source, request, cancel_event=cancel),
                self._ready,
                "Preparing project…",
            )
        elif (
            action == "submit"
            and not self._completed
            and self._prepared is not None
            and self.dialog.rights.isChecked()
        ):
            prepared, prepared_identity = self._prepared, self._identity
            assert prepared_identity is not None
            self._attempted = True
            self._start(
                lambda cancel: submit_project(
                    self.client,
                    prepared,
                    author_name=prepared_identity[0],
                    author_email=prepared_identity[1],
                    cancel_event=cancel,
                ),
                self._submitted,
                "Uploading project…",
            )
        elif action == "refresh":
            self._start(
                lambda cancel: list_submissions(self.client, cancel, project_uploads=True),
                self._history,
                "Checking review decisions…",
            )
        elif action == "new" and self._prepared is not None:
            prepared = self._prepared
            if self._attempted:
                if self._identity is not None:
                    self._retained_uploads[prepared.request.item_id] = prepared, self._identity
                self._reset(None)
                self.dialog.review.setPlainText(
                    f"Earlier submission files retained for an exact retry:\n{prepared.bundle_path}"
                )
            else:
                self._start(
                    lambda _cancel: self.service.discard(prepared),
                    self._reset,
                    "Removing the unsubmitted copy…",
                )

    def _ready(self, value: object) -> None:
        self._prepared = cast(PreparedPublication, value)
        self.dialog.review.setPlainText(
            f"Source project: {self._source}\n\n" + publication_review(self._prepared)
        )
        self._action("submit")

    def _submitted(self, value: object) -> None:
        result = cast(SubmissionStatus, value)
        self._completed = result.status != "uploading"
        labels = {
            "pending": "Uploaded — awaiting review.",
            "accepted": "Published.",
            "rejected": "Declined.",
            "publishing": "Publishing…",
            "uploading": "Upload incomplete. Retry upload.",
        }
        self._status(f"{labels[result.status]} {result.review_notes}".strip())
        self.dialog.history.setPlainText(
            f"{result.title}\nRequest: {result.submission_id}\n"
            f"Status: {result.status}\n{result.review_notes}"
        )

    def _history(self, value: object) -> None:
        history = cast(SubmissionList, value)
        if self._prepared is not None:
            current = next(
                (
                    item
                    for item in history.submissions
                    if item.item_id == self._prepared.request.item_id
                ),
                None,
            )
            if current is not None:
                self._completed = current.status != "uploading"
        self.dialog.history.setPlainText(
            "\n\n".join(
                f"{item.title}\nRequest: {item.submission_id}\n"
                f"Status: {item.status}\n"
                f"{item.review_notes}"
                for item in history.submissions
            )
            or "No uploads from this computer."
        )
        self._status("Review status refreshed.")

    def _reset(self, _value: object) -> None:
        self._prepared = None
        self._attempted = False
        self._completed = False
        self._identity = None
        self._bind_current_project()
        self.dialog.rights.setChecked(False)
        self.dialog.review.clear()
        self._status("")
        self.dialog.set_state(self._job is not None, False, False, False)
