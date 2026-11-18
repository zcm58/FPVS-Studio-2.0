"""Operator controls for local collection and the independently authorized website study."""

from __future__ import annotations

from pathlib import Path
from threading import Event

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.study_lifecycle import read_study, set_collection_complete
from fpvs_studio.data_sharing.client import DataSharingClient
from fpvs_studio.data_sharing.collection import last_collection_status, refresh_collection_status
from fpvs_studio.data_sharing.storage import list_records, load_settings
from fpvs_studio.gui.components import DialogHeader, apply_dialog_theme, mark_primary_action
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
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(DialogHeader(self.profile.title, parent=self))
        state = read_study(root)
        local_state = "Complete" if state and state.collection_complete else "In progress"
        status = QGridLayout()
        status.setColumnStretch(1, 1)
        status.setHorizontalSpacing(16)
        status.addWidget(QLabel("Local collection", self), 0, 0)
        status.addWidget(QLabel(local_state, self), 0, 1)
        status.addWidget(QLabel("Last website status", self), 1, 0)
        self.confirmed = QLabel(self)
        status.addWidget(self.confirmed, 1, 1)
        self._render_status(last_collection_status(root, self.profile))
        self.refresh = QPushButton("Check status", self)
        self.refresh.clicked.connect(lambda: self._run("status"))
        status.addWidget(self.refresh, 1, 2)
        layout.addLayout(status)
        self.notice = QLabel(self)
        self.notice.setWordWrap(True)
        self.notice.setTextFormat(Qt.TextFormat.PlainText)
        self.notice.hide()
        layout.addWidget(self.notice)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.website = buttons.addButton(
            "Manage collection on OpenFPVS…", QDialogButtonBox.ButtonRole.ActionRole
        )
        mark_primary_action(self.website)
        self.website.clicked.connect(self._open_website)
        self.share = buttons.addButton("Share roster…", QDialogButtonBox.ButtonRole.ActionRole)
        self._can_share = bool(settings.enabled and state and state.collection_complete)
        self.share.setEnabled(self._can_share)
        if not self._can_share:
            self.share.setToolTip(
                "Roster sharing requires Data Sharing and completed local collection."
            )
        self.share.clicked.connect(self._confirm_roster)
        buttons.rejected.connect(self.accept)
        layout.addWidget(buttons)
        apply_dialog_theme(self)

    def _render_status(self, status: str | None) -> None:
        states = {"complete": "Complete", "in_progress": "In progress"}
        self.confirmed.setText(states.get(status or "", "Unconfirmed"))

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

        self._job = update_lifecycle().start_task(perform)
        self._operation = action
        self.notice.setText({
            "status": "Checking website status…",
            "roster": "Sharing the study roster…",
            "website": "Checking for pending reports…",
        }[action])
        self.notice.show()
        for button in (self.refresh, self.website, self.share):
            button.setEnabled(False)
        self._job.finished.connect(self._finished)

    def _finished(self, result: UpdateTaskResult) -> None:
        self._job = None
        self.refresh.setEnabled(True)
        self.website.setEnabled(True)
        self.share.setEnabled(self._can_share)
        if not self.isVisible():
            return
        if result.cancelled:
            self.notice.hide()
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
            count = result.value
            pending = (
                "No local session reports are pending." if count == 0 else
                "One local session report is pending." if count == 1 else
                f"{count} local session reports are pending."
            )
            if QMessageBox.question(
                self, "Manage collection on OpenFPVS",
                f"{pending} Closing collection on OpenFPVS stops new reports from all "
                "participating labs. Check their pending reports before closing. "
                "Open the website?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            ) != QMessageBox.StandardButton.Yes:
                self.notice.hide()
                return
            origin = DataSharingClient.configured().origin
            url = f"{origin}/projects/{self.profile.project_id}#collection"
            if not QDesktopServices.openUrl(QUrl(url)):
                self.notice.setText(f"Open {url} in your browser.")
                return
            self.notice.setText("Check website status after making a change on OpenFPVS.")
