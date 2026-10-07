"""App-owned condition preparation/upload jobs; no file or HTTP work on the UI thread."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import cast
from uuid import uuid4

from PySide6.QtCore import QObject, Qt
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
    submit_condition,
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
        self._source: Path | None = None
        self._save: Callable[[], bool] | None = None
        self._identity: tuple[str, str, str, str] | None = None

    def show(
        self,
        *,
        project_root: Path,
        conditions: list[tuple[str, str]],
        save_project: Callable[[], bool],
    ) -> None:
        if self._prepared is None and self._job is None:
            self._source, self._save = project_root, save_project
            self.dialog.conditions.clear()
            for identity, name in conditions:
                self.dialog.conditions.addItem(name, identity)
                self.dialog.conditions.setItemData(
                    self.dialog.conditions.count() - 1, name, Qt.ItemDataRole.ToolTipRole
                )
            self.dialog.set_state(False, False, False)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _cancel(self) -> None:
        if self._job is not None:
            self._job.cancel()
            self.dialog.status.setText(
                "Canceling. The prepared bundle is retained; "
                "refresh requests to confirm remote status."
            )

    def _start(
        self, operation: Callable[[Event], object], finished: Callable[[object], None], message: str
    ) -> None:
        if self._job is not None or self.lifecycle.is_shutting_down:
            return
        self.dialog.set_state(True, self._prepared is not None, self._attempted)
        self.dialog.status.setText(message)
        job = self.lifecycle.start_task(lambda _progress, cancel: operation(cancel))
        self._job = job

        def complete(value: object) -> None:
            result = cast(UpdateTaskResult, value)
            self._job = None
            if result.cancelled:
                self.dialog.status.setText(
                    "Canceled. Refresh my requests before retrying the same prepared bundle."
                )
            elif result.error is not None:
                detail = (
                    str(result.error)
                    if isinstance(result.error, (LibraryError, PublisherError))
                    else "The operation failed. Check project files, Library access "
                    "and network, then retry."
                )
                self.dialog.status.setText(detail[:1024])
            else:
                finished(result.value)
            self.dialog.set_state(False, self._prepared is not None, self._attempted)

        job.finished.connect(complete)

    def _action(self, action: str) -> None:
        if action == "cancel":
            self._cancel()
            return
        if self._job is not None or self.lifecycle.is_shutting_down:
            return
        if action == "prepare" and self._prepared is None:
            if (
                not self.dialog.author_edit.text().strip()
                or "@" not in self.dialog.email_edit.text()
            ):
                self.dialog.status.setText("Enter your name and a contact email before preparing.")
                return
            try:
                request = PublicationRequest(
                    f"reviewed-{uuid4()}",
                    self.dialog.title_edit.text().strip(),
                    "1.0.0",
                    self.dialog.description.toPlainText(),
                    __version__,
                )
            except PublisherError as error:
                self.dialog.status.setText(str(error))
                return
            if self._save is None or not self._save():
                self.dialog.status.setText(
                    "Save the current experiment before preparing a condition."
                )
                return
            source = self._source
            assert source is not None
            identity = (
                str(self.dialog.conditions.currentData()),
                self.dialog.conditions.currentText(),
                self.dialog.author_edit.text().strip(),
                self.dialog.email_edit.text().strip(),
            )
            self._identity = identity
            self._start(
                lambda cancel: self.service.prepare(
                    source, request, condition_id=identity[0], cancel_event=cancel
                ),
                self._ready,
                "Preparing a clean condition bundle…",
            )
        elif action == "submit" and self._prepared is not None and self.dialog.rights.isChecked():
            prepared, prepared_identity = self._prepared, self._identity
            assert prepared_identity is not None
            self._attempted = True
            self._start(
                lambda cancel: submit_condition(
                    self.client,
                    prepared,
                    condition_id=prepared_identity[0],
                    condition_name=prepared_identity[1],
                    author_name=prepared_identity[2],
                    author_email=prepared_identity[3],
                    cancel_event=cancel,
                ),
                self._submitted,
                "Uploading the reviewed condition to a private GitHub draft…",
            )
        elif action == "refresh":
            self._start(
                lambda cancel: list_submissions(self.client, cancel),
                self._history,
                "Checking review decisions…",
            )
        elif action == "new" and self._prepared is not None:
            prepared = self._prepared
            if self._attempted:
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
        self.dialog.status.setText(
            "Review this condition’s files and confirm sharing permission before submitting."
        )

    def _submitted(self, value: object) -> None:
        result = cast(SubmissionStatus, value)
        self.dialog.status.setText(
            f"Request {result.submission_id}: {result.status}. {result.review_notes}"
        )
        self.dialog.history.setPlainText(
            f"{result.title}\nRequest: {result.submission_id}\n"
            f"Status: {result.status}\n{result.review_notes}"
        )

    def _history(self, value: object) -> None:
        history = cast(SubmissionList, value)
        self.dialog.history.setPlainText(
            "\n\n".join(
                f"{item.title} · {item.condition_name}\nRequest: {item.submission_id}\n"
                f"Status: {item.status}\n"
                f"Tested Studio: {item.tested_studio_version or 'Awaiting testing'}\n"
                f"{item.review_notes}"
                for item in history.submissions
            )
            or "No submissions from this enrolled computer."
        )
        self.dialog.status.setText("Review status refreshed.")

    def _reset(self, _value: object) -> None:
        self._prepared = None
        self._attempted = False
        self.dialog.rights.setChecked(False)
        self.dialog.review.clear()
        self.dialog.status.setText("Prepare a new condition. Future edits require another review.")
