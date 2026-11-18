"""Operator controls for local collection and the independently authorized website study."""

from __future__ import annotations

from pathlib import Path
from threading import Event

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from fpvs_studio.core.study_lifecycle import read_study, set_collection_complete
from fpvs_studio.data_sharing.client import DataSharingClient
from fpvs_studio.data_sharing.collection import last_collection_status, refresh_collection_status
from fpvs_studio.data_sharing.storage import list_records, load_settings
from fpvs_studio.gui.components import apply_dialog_theme
from fpvs_studio.gui.update_lifecycle import (
    ProgressReporter,
    UpdateJob,
    UpdateTaskResult,
    update_lifecycle,
)


def change_collection(parent: QWidget, root: Path, complete: bool) -> bool:
    title = "Data Collection Complete" if complete else "Reopen Collection"
    message = (
        "Finish local data collection? Review and export will remain available. "
        "Reopen Collection before another research session."
        if complete else "Reopen local collection to allow further research sessions?"
    )
    if QMessageBox.question(
        parent, title, message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    ) != QMessageBox.StandardButton.Yes:
        return False
    set_collection_complete(root, complete)
    return True


class LinkedStudyDialog(QDialog):
    def __init__(self, root: Path, parent: QWidget) -> None:
        super().__init__(parent)
        self.root = root
        settings = load_settings(root)
        if not settings.profile or not settings.profile.project_id:
            raise ValueError("Connect this project to an OpenFPVS study using Data Sharing.")
        self.profile = settings.profile
        self._job: UpdateJob | None = None
        self.setWindowTitle("Linked OpenFPVS Study")
        layout = QVBoxLayout(self)
        name = QLabel(self.profile.title, self)
        name.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(name)
        state = read_study(root)
        local_state = "complete" if state and state.collection_complete else "in progress"
        layout.addWidget(QLabel(f"Local collection: {local_state}", self))
        self.confirmed = QLabel(self)
        layout.addWidget(self.confirmed)
        self._render_status(last_collection_status(root, self.profile))
        self.notice = QLabel("Review outstanding reports before closing website collection.", self)
        self.notice.setWordWrap(True)
        self.notice.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.notice)
        self.refresh = QPushButton("Check website status", self)
        self.refresh.clicked.connect(lambda: self._run("status"))
        layout.addWidget(self.refresh)
        self.website = QPushButton("Manage collection on OpenFPVS…", self)
        self.website.clicked.connect(self._open_website)
        layout.addWidget(self.website)
        self.share = QPushButton("Share study roster…", self)
        self.share.setEnabled(bool(settings.enabled and state and state.collection_complete))
        self.share.clicked.connect(self._confirm_roster)
        layout.addWidget(self.share)
        close = QPushButton("Close", self)
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        apply_dialog_theme(self)

    def _render_status(self, status: str | None) -> None:
        states = {"complete": "complete", "in_progress": "in progress"}
        value = states.get(status or "", "unconfirmed")
        self.confirmed.setText(f"Last confirmed by OpenFPVS: {value}")

    def _confirm_roster(self) -> None:
        if QMessageBox.question(
            self, "Share study roster",
            f"Send the study ID, roster revision and a one-way identifier for each research "
            f"visit to {self.profile.title} on OpenFPVS to compare dataset coverage? "
            "Participant labels, EEG and local paths stay on this computer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        ) == QMessageBox.StandardButton.Yes:
            self._run("roster")

    def _open_website(self) -> None:
        self._run("website")

    def _run(self, action: str) -> None:
        if self._job is not None:
            return
        root, profile = self.root, self.profile

        def perform(_progress: ProgressReporter, cancel: Event) -> str | int:
            if action == "website":
                return sum(1 for item in list_records(root)
                           if item.project_id == profile.project_id and item.state != "uploaded")
            if action == "status":
                return refresh_collection_status(root, profile, cancel)
            from fpvs_studio.data_sharing.roster import share_study_roster

            return share_study_roster(root, cancel)

        self.notice.setText("Working…")
        self._job = update_lifecycle().start_task(perform)
        self._operation = action
        self._job.finished.connect(self._finished)

    def _finished(self, result: UpdateTaskResult) -> None:
        self._job = None
        if result.cancelled or not self.isVisible():
            return
        if result.error:
            self.notice.setText(str(result.error))
            return
        if self._operation == "status":
            self._render_status(str(result.value))
            self.notice.setText("Website status confirmed.")
        elif self._operation == "roster":
            self.notice.setText("OpenFPVS accepted the study roster.")
        else:
            if QMessageBox.question(
                self, "Manage collection on OpenFPVS",
                f"{result.value} outstanding local reports for this linked study. Closing website "
                "collection stops new Studio reports across participating labs. Review their "
                "outstanding reports before closing. Continue to the signed-in website?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            ) == QMessageBox.StandardButton.Yes:
                origin = DataSharingClient.configured().origin
                url = f"{origin}/projects/{self.profile.project_id}#collection"
                if not QDesktopServices.openUrl(QUrl(url)):
                    self.notice.setText(f"Open {url} in your browser.")
                    return
            self.notice.setText("Check website status after making a change on OpenFPVS.")
