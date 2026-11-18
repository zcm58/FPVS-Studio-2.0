"""Review protocol edits and browse local experiment versions."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from sqlite3 import Error as DatabaseError
from typing import TYPE_CHECKING, TypeVar

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.serialization import load_project_file
from fpvs_studio.core.study_versions import (
    ProtocolDraft,
    StudyVersion,
    commit_change,
    create_from_version,
    historical_draft,
    keep_saved_stimuli,
    list_versions,
    name_version,
    prepare_change,
    restore_version,
)
from fpvs_studio.gui.document_support import DocumentError
from fpvs_studio.gui.workers import ProgressTask
from fpvs_studio.preprocessing.manifest import create_empty_manifest
from fpvs_studio.runtime.participant_results import research_visits_by_version

if TYPE_CHECKING:
    from fpvs_studio.gui.main_window import StudioMainWindow

_Result = TypeVar("_Result")


class ProtocolReviewCancelled(DocumentError):
    """The author kept the original study active."""


class StudyVersionController:
    def __init__(
        self, window: StudioMainWindow, open_project: Callable[[Path], object] | None
    ) -> None:
        self.window = window
        self.document = window.document
        self.root = self.document.project_root
        self.open_project = open_project

    def _work(self, label: str, callback: Callable[[], _Result]) -> _Result:
        # Save callers need a synchronous decision. Native Qt continues to service
        # paints, events and the worker while this window-modal operation runs.
        loop = QEventLoop()
        values: list[_Result] = []
        errors: list[Exception] = []
        task = ProgressTask(parent_widget=self.window, label=label, callback=callback)
        task.succeeded.connect(values.append)
        task.failed.connect(errors.append)
        task.finished.connect(loop.quit)
        self.window.destroyed.connect(loop.quit)
        task.start()
        if not values and not errors:
            loop.exec()
        if errors:
            raise errors[0]
        if not values:
            raise ProtocolReviewCancelled("Version review closed.")
        return values[0]

    def review(
        self,
        draft: ProtocolDraft,
        *,
        version_id: str | None = None,
        on_fork: Callable[[ProtocolDraft], None] | None = None,
    ) -> str:
        first = QMessageBox(self.window)
        first.setIcon(QMessageBox.Icon.Warning)
        first.setWindowTitle("Review changes to this study")
        first.setText(
            "Participant data has already been collected. "
            "Save as a new study to keep the cohorts separate."
        )
        first.setInformativeText("\n".join(draft.changes[:5]))
        first.setDetailedText("\n".join(draft.changes))
        new_study = first.addButton("Save as new study…", QMessageBox.ButtonRole.ActionRole)
        same = first.addButton(
            "I reviewed the changes — continue in this study", QMessageBox.ButtonRole.AcceptRole
        )
        cancel = first.addButton(QMessageBox.StandardButton.Cancel)
        first.setDefaultButton(cancel)
        first.setEscapeButton(cancel)
        first.exec()
        if first.clickedButton() is new_study:
            if on_fork is not None:
                on_fork(draft)
            elif self._copy(draft, version_id=version_id, restore_source_assets=version_id is None):
                self._reload()
            raise ProtocolReviewCancelled("The original study was kept.")
        if first.clickedButton() is not same:
            raise ProtocolReviewCancelled("The original study was kept.")
        second = QDialog(self.window)
        second.setWindowTitle("Confirm the risk to earlier data")
        layout = QVBoxLayout(second)
        warning = QLabel(
            "Earlier participants experienced a different protocol. Comparing or pooling their "
            "data with future visits may be invalid. "
            "Earlier data could be unusable for your intended analysis."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        label = QLabel("Why are you changing this study?")
        reason = QLineEdit()
        label.setBuddy(reason)
        layout.addWidget(label)
        layout.addWidget(reason)
        acknowledge = QCheckBox("I understand the risk to earlier data.")
        layout.addWidget(acknowledge)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        apply = buttons.addButton("Apply to future visits", QDialogButtonBox.ButtonRole.AcceptRole)
        apply.setAutoDefault(False)
        apply.setEnabled(False)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setDefault(True)

        def ready() -> None:
            apply.setEnabled(bool(reason.text().strip()) and acknowledge.isChecked())

        reason.textChanged.connect(ready)
        acknowledge.toggled.connect(ready)
        buttons.accepted.connect(second.accept)
        buttons.rejected.connect(second.reject)
        layout.addWidget(buttons)
        if second.exec() != QDialog.DialogCode.Accepted:
            raise ProtocolReviewCancelled("The original study was kept.")
        return reason.text().strip()

    def save(self, project: ProjectFile) -> None:
        def save_or_review() -> ProtocolDraft | None:
            draft = self.document.prepare_protocol_change(project)
            if draft.changes and research_visits_by_version(self.root):
                return draft
            commit_change(self.root, project, draft, "")
            return None

        draft = self._work("Saving the experiment…", save_or_review)
        if draft is not None:
            try:
                reason = self.review(draft)
            except ProtocolReviewCancelled:
                recovered = self._work(
                    "Keeping the saved protocol…",
                    lambda: keep_saved_stimuli(self.root, draft),
                )
                if recovered is not None:
                    self._reload()
                    self.window.statusBar().showMessage(f"Unapplied stimulus files: {recovered}")
                raise
            self._work(
                "Saving the reviewed experiment…",
                lambda: commit_change(self.root, project, draft, reason),
            )

    def _reload(self) -> None:
        _, project, manifest = self.document.read_existing(self.root)
        self.document.accept_library_project_update(
            project, manifest or create_empty_manifest(project.meta.project_id)
        )

    def _copy(
        self,
        draft: ProtocolDraft,
        *,
        version_id: str | None = None,
        restore_source_assets: bool = False,
        open_after: bool = True,
    ) -> Path | None:
        name, ok = QInputDialog.getText(self.window, "Save as new study", "New study name")
        if not ok:
            return None
        parent = (
            self.window._on_load_fpvs_root_dir()
            if self.window._on_load_fpvs_root_dir
            else self.root.parent
        )
        path = self._work(
            "Creating separate study…",
            lambda: create_from_version(
                self.root,
                Path(parent or self.root.parent),
                name,
                draft,
                source_version_id=version_id,
                restore_source_assets=restore_source_assets,
            ),
        )
        open_project = self.open_project
        if open_after and open_project is not None:
            QTimer.singleShot(0, lambda: open_project(path))
        return path

    def show_history(self) -> None:
        try:
            self._history()
        except ProtocolReviewCancelled:
            return
        except (OSError, ValueError, RuntimeError, DatabaseError) as error:
            QMessageBox.warning(self.window, "Experiment version history", str(error))

    def _history(self) -> None:
        def load() -> tuple[list[StudyVersion], dict[str, set[str]]]:
            prepare_change(self.root, load_project_file(self.root / "project.json"))
            return list_versions(self.root)[::-1], research_visits_by_version(self.root)

        versions, visits = self._work("Reading experiment history…", load)
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Experiment version history")
        dialog.resize(660, 460)
        layout = QVBoxLayout(dialog)
        lineage = self.window.document.study_lineage()
        if lineage:
            layout.addWidget(QLabel("Created from " + lineage))
        items = QListWidget()
        details = QPlainTextEdit()
        details.setReadOnly(True)
        for version in versions:
            stamp = version.saved_at[:19].replace("T", " ")
            items.addItem(f"{stamp} UTC   {version.label or version.version_id[:8]}")
        layout.addWidget(items)
        layout.addWidget(details)

        def selected() -> StudyVersion:
            return versions[items.currentRow()]

        def refresh() -> None:
            version = selected()
            lines = list(version.changes)
            if version.reason:
                lines.insert(0, f"Author's reason: {version.reason}")
            lines.append(
                "Research visits: "
                + (", ".join(sorted(visits.get(version.version_id, ()))) or "None recorded")
            )
            details.setPlainText("\n".join(lines))

        items.currentRowChanged.connect(refresh)
        items.setCurrentRow(0)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        rename = buttons.addButton("Name version…", QDialogButtonBox.ButtonRole.ActionRole)
        restore = buttons.addButton("Restore this version…", QDialogButtonBox.ButtonRole.ActionRole)
        copy = buttons.addButton("Save as new study…", QDialogButtonBox.ButtonRole.ActionRole)
        choice: list[QAbstractButton] = []

        def choose(button: QAbstractButton) -> None:
            if button in (rename, restore, copy):
                choice.append(button)
                dialog.accept()

        buttons.clicked.connect(choose)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted or not choice:
            return
        version = selected()
        if choice[0] is rename:
            label, ok = QInputDialog.getText(
                self.window, "Name experiment version", "Optional name", text=version.label
            )
            if ok:
                name_version(self.root, version.version_id, label)
            return
        draft = self._work(
            "Checking the selected version…", lambda: historical_draft(self.root, version.version_id)
        )
        if self.document.dirty:
            raise DocumentError(
                "Save or discard open edits before switching to another experiment version."
            )
        if choice[0] is copy:
            self._copy(draft, version_id=version.version_id)
            return
        if draft.changes:
            reason = self.review(draft, version_id=version.version_id) if visits else ""
            self._work(
                "Restoring the saved experiment…", lambda: restore_version(self.root, draft, reason)
            )
            self._reload()
