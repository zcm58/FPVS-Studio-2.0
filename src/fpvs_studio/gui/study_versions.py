"""Review protocol edits and browse local experiment versions."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from sqlite3 import Error as DatabaseError
from typing import TYPE_CHECKING, TypeVar

from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.serialization import save_project_file
from fpvs_studio.core.study_versions import (
    ProtocolDraft,
    StudyVersion,
    commit_setup_change,
    create_from_version,
    has_pending_setup_save,
    historical_draft,
    keep_saved_stimuli,
    list_versions,
    list_working_revisions,
    name_version,
    read_version_protocol,
    restore_version,
    saved_version_count,
)
from fpvs_studio.gui.components import (
    apply_dialog_theme,
    mark_compact_action,
    mark_primary_action,
    mark_secondary_action,
    mark_text_role,
)
from fpvs_studio.gui.document_support import DocumentError
from fpvs_studio.gui.workers import BackgroundTask, ProgressTask
from fpvs_studio.preprocessing.manifest import create_empty_manifest
from fpvs_studio.runtime.participant_results import research_visits_by_version

if TYPE_CHECKING:
    from fpvs_studio.gui.main_window import StudioMainWindow

_Result = TypeVar("_Result")


class ProtocolReviewCancelled(DocumentError):
    """The author kept the original study active."""


class _StudyCopied(ProtocolReviewCancelled):
    """The source was already restored and the new study is ready to open."""


class StudyVersionController:
    def __init__(
        self, window: StudioMainWindow, open_project: Callable[[Path], object] | None
    ) -> None:
        self.window = window
        self.document = window.document
        self.root = self.document.project_root
        self.open_project = open_project

    def _work(self, label: str | None, callback: Callable[[], _Result]) -> _Result:
        # Save callers need a synchronous decision. Native Qt continues to service
        # paints, events and the worker while this window-modal operation runs.
        loop = QEventLoop()
        values: list[_Result] = []
        errors: list[Exception] = []
        task = (
            ProgressTask(parent_widget=self.window, label=label, callback=callback)
            if label is not None else BackgroundTask(parent_widget=self.window, callback=callback)
        )
        task.succeeded.connect(values.append)
        task.failed.connect(errors.append)
        task.finished.connect(loop.quit)
        self.window.destroyed.connect(loop.quit)
        task.start()
        if not values and not errors:
            flags = QEventLoop.ProcessEventsFlag
            loop.exec(flags.AllEvents if label is not None else flags.ExcludeUserInputEvents)
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
        first.setTextFormat(Qt.TextFormat.PlainText)
        summary = list(draft.changes[:5])
        if len(draft.changes) > len(summary):
            summary.append(f"Show Details for all {len(draft.changes)} changes.")
            first.setDetailedText("\n".join(draft.changes))
        first.setInformativeText("\n".join(summary))
        new_study = first.addButton("Save as new study…", QMessageBox.ButtonRole.ActionRole)
        mark_primary_action(new_study)
        same = first.addButton(
            "Reviewed — continue in this study…", QMessageBox.ButtonRole.AcceptRole
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
                raise _StudyCopied("Saved as a separate study.")
            raise ProtocolReviewCancelled("The original study was kept.")
        if first.clickedButton() is not same:
            raise ProtocolReviewCancelled("The original study was kept.")
        second = QDialog(self.window)
        second.setWindowTitle("Confirm the risk to earlier data")
        second.setMinimumWidth(440)
        layout = QVBoxLayout(second)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        warning = QLabel("Earlier visits used a different protocol. Their data may be unusable "
                         "for your analysis. Pooling them with future visits may invalidate "
                         "the comparison.")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        layout.addSpacing(4)
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
        apply_dialog_theme(second)
        second.resize(460, 190)
        if second.exec() != QDialog.DialogCode.Accepted:
            raise ProtocolReviewCancelled("The original study was kept.")
        return reason.text().strip()

    def _choose_checkpoint(self) -> bool:
        dialog = QMessageBox(self.window)
        dialog.setWindowTitle("Save a project version?")
        dialog.setText("Keep a rollback copy of this setup?")
        dialog.setInformativeText(
            "Save changes only updates the project you open next time. "
            "Saving a project version also keeps a copy of the settings and stimuli "
            "that you can restore from Manage Projects."
        )
        version = dialog.addButton("Save project version", QMessageBox.ButtonRole.ActionRole)
        working = dialog.addButton("Save changes only", QMessageBox.ButtonRole.AcceptRole)
        cancel = dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.setDefaultButton(working)
        dialog.setEscapeButton(cancel)
        dialog.exec()
        if dialog.clickedButton() is version:
            return True
        if dialog.clickedButton() is working:
            return False
        raise ProtocolReviewCancelled("Setup is still open.")

    def save(self, project: ProjectFile, completed_setup: bool) -> None:
        def prepare() -> tuple[ProtocolDraft, bool, bool, bool] | None:
            draft = self.document.prepare_protocol_change(project)
            if not completed_setup and not draft.changes:
                save_project_file(project, self.root / "project.json")
                return None
            collected = bool(draft.changes) and bool(research_visits_by_version(self.root))
            first = completed_setup and saved_version_count(self.root) == 0
            pending = completed_setup and has_pending_setup_save(self.root)
            return draft, collected, first, pending

        reviewed = self._work(None, prepare)
        if reviewed is None:
            return
        draft, collected, first_version, pending = reviewed
        reason = ""
        if collected:
            try:
                reason = self.review(draft)
            except _StudyCopied:
                raise
            except ProtocolReviewCancelled:
                recovered = self._work(
                    "Keeping the saved protocol…",
                    lambda: keep_saved_stimuli(self.root, draft),
                )
                if recovered is not None:
                    self._reload()
                    self.window.statusBar().showMessage(f"Unapplied stimulus files: {recovered}")
                raise
        checkpoint = first_version or (
            completed_setup and (bool(draft.changes) or pending) and self._choose_checkpoint()
        )

        def persist() -> None:
            commit_setup_change(
                self.root, project, draft, reason, research_visits_by_version,
                save_version=checkpoint, completed_setup=completed_setup,
            )

        if checkpoint:
            label = "Saving Project version 1…" if first_version else "Saving project version…"
            self._work(label, persist)
        else:
            self._work(None, persist)

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
        def load() -> tuple[list[StudyVersion], list[StudyVersion], dict[str, set[str]]]:
            return (
                list_versions(self.root)[::-1], list_working_revisions(self.root)[::-1],
                research_visits_by_version(self.root),
            )

        versions, revisions, visits = self._work("Reading experiment history…", load)
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Experiment version history")
        dialog.setMinimumSize(560, 360)
        dialog.resize(660, 460)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        lineage = self.window.document.study_lineage()
        if lineage:
            origin = QLabel("Created from " + lineage)
            origin.setTextFormat(Qt.TextFormat.PlainText)
            origin.setWordWrap(True)
            layout.addWidget(origin)
        if visits.get(""):
            count = len(visits[""])
            unknown = QLabel(f"Research visits with an unrecorded protocol version: {count}")
            unknown.setWordWrap(True)
            unknown.setToolTip(", ".join(sorted(visits[""])))
            layout.addWidget(unknown)
        items = QListWidget()
        items.setAccessibleName("Saved protocol versions")
        details = QPlainTextEdit()
        details.setReadOnly(True)
        details.setAccessibleName("Selected version details")
        for index, version in enumerate(versions):
            stamp = version.saved_at[:19].replace("T", " ")
            title = f"Version {len(versions) - index}"
            if version.label:
                title += f" — {version.label}"
            text = f"{title}   ·   {stamp} UTC"
            items.addItem(text)
            items.item(items.count() - 1).setToolTip(text)
        working_records = [
            version for version in revisions if version.reason or visits.get(version.version_id)
        ]
        if working_records:
            items.addItem("Working revisions used or reviewed during collection")
        for title, view, stretch in (("Saved versions", items, 2), ("Version details", details, 3)):
            heading = QLabel(title, dialog)
            mark_text_role(heading, "sectionTitle")
            heading.setBuddy(view)
            section = QVBoxLayout()
            section.setSpacing(6)
            section.addWidget(heading)
            section.addWidget(view, 1)
            layout.addLayout(section, stretch)

        def selected() -> StudyVersion:
            return versions[items.currentRow()]

        def describe(version: StudyVersion) -> str:
            lines = list(version.changes)
            if version.reason:
                lines.insert(0, f"Author's reason: {version.reason}")
            recorded = ", ".join(sorted(visits.get(version.version_id, ()))) or "None recorded"
            lines.append(f"Research visits: {recorded}")
            return "\n".join(lines)

        def refresh() -> None:
            is_snapshot = 0 <= items.currentRow() < len(versions)
            for action in (inspect, rename, restore, copy):
                action.setEnabled(is_snapshot)
            if is_snapshot:
                details.setPlainText(describe(selected()))
            elif working_records:
                sections = [
                    f"{record.saved_at}  ·  {record.version_id}\n{describe(record)}"
                    for record in working_records
                ]
                details.setPlainText("\n\n".join(sections))
            else:
                details.setPlainText("No saved versions yet. Save the project at the end of Setup.")

        inspect = QPushButton("Open read-only…", dialog)
        inspect.clicked.connect(
            lambda: self._inspect_version(dialog, selected(), len(versions) - items.currentRow())
        )
        mark_primary_action(inspect)
        rename = QPushButton("Name…", dialog)
        rename.setAccessibleName("Name version")
        restore = QPushButton("Restore…", dialog)
        restore.setAccessibleName("Restore selected version")
        copy = QPushButton("Save as new study…", dialog)
        close = QPushButton("Close", dialog)
        close.clicked.connect(dialog.reject)
        footer = QHBoxLayout()
        footer.setSpacing(6)
        choice: QPushButton | None = None

        def choose(button: QPushButton) -> None:
            nonlocal choice
            choice = button
            dialog.accept()

        for action in (rename, restore, copy):
            action.clicked.connect(lambda _checked=False, button=action: choose(button))
            footer.addWidget(action)
        footer.addStretch(1)
        footer.addWidget(close)
        footer.addWidget(inspect)
        for action in (rename, restore, copy, close):
            mark_secondary_action(action)
        for action in (rename, restore, copy, close, inspect):
            mark_compact_action(action)
            action.setAutoDefault(False)
        dialog.setTabOrder(close, inspect)
        layout.addLayout(footer)

        items.currentRowChanged.connect(refresh)
        if items.count():
            items.setCurrentRow(0)
        else:
            refresh()
        apply_dialog_theme(dialog)
        result = dialog.exec()
        row = items.currentRow()
        dialog.deleteLater()
        if result != QDialog.DialogCode.Accepted or not choice:
            return
        version = versions[row]
        if choice is rename:
            label, ok = QInputDialog.getText(
                self.window, "Name experiment version", "Optional name", text=version.label
            )
            if ok:
                name_version(self.root, version.version_id, label)
            return
        if self.window.is_launch_busy():
            raise DocumentError("Finish the current visit before switching experiment versions.")
        if not self.window.flush_pending_edits() or self.document.dirty:
            raise DocumentError(
                "Save or discard open edits before switching to another experiment version."
            )
        draft = self._work(
            "Checking the selected version…",
            lambda: historical_draft(self.root, version.version_id),
        )
        if choice is copy:
            self._copy(draft, version_id=version.version_id)
            return
        if draft.changes:
            if not visits and draft.previous not in {v.version_id for v in versions}:
                number = len(versions) - row
                answer = QMessageBox.question(
                    self.window, f"Restore Version {number}?",
                    f"Replace the current working settings and stimuli with Version {number}? "
                    "Changes made since the last saved version will be lost.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel,
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            reason = self.review(draft, version_id=version.version_id) if visits else ""
            self._work(
                "Restoring the saved experiment…",
                lambda: restore_version(self.root, draft, reason, research_visits_by_version),
            )
            self._reload()

    def _inspect_version(self, parent: QDialog, version: StudyVersion, number: int) -> None:
        try:
            protocol = self._work(
                "Reading saved settings…",
                lambda: read_version_protocol(self.root, version.version_id),
            )
        except (OSError, ValueError, RuntimeError, DatabaseError) as error:
            QMessageBox.warning(parent, "Unable to open saved version", str(error))
            return
        dialog = QDialog(parent)
        dialog.setWindowTitle(f"Version {number} — read-only")
        dialog.setMinimumSize(420, 300)
        dialog.resize(660, 460)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        tree = QTreeWidget(dialog)
        tree.setAccessibleName("Saved experiment settings")
        tree.setHeaderLabels(["Setting", "Saved value"])
        layout.addWidget(tree)
        groups: dict[QTreeWidgetItem, dict | list] = {}

        def add(parent_item: QTreeWidgetItem, key: str, value: object) -> QTreeWidgetItem:
            item = QTreeWidgetItem(parent_item, [key])
            if isinstance(value, (dict, list)):
                if value:
                    groups[item] = value
                    item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            else:
                display = "—" if value is None else str(value)
                item.setText(1, display)
                item.setToolTip(1, display)
            item.setToolTip(0, key)
            return item

        def expand(item: QTreeWidgetItem) -> None:
            value = groups.pop(item, None)
            if isinstance(value, dict):
                for name, child in value.items():
                    add(item, name.replace("_", " "), child)
            elif isinstance(value, list):
                for index, child in enumerate(value, 1):
                    name = child.get("name") if isinstance(child, dict) else None
                    add(item, str(name or index), child)

        tree.itemExpanded.connect(expand)
        for name, value in protocol.items():
            item = add(tree.invisibleRootItem(), name.replace("_", " "), value)
            if name == "settings":
                item.setExpanded(True)
                for index in range(item.childCount()):
                    child = item.child(index)
                    if child is not None and child.toolTip(0) == "protocol":
                        child.setExpanded(True)
        tree.setColumnWidth(0, 260)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=dialog)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        apply_dialog_theme(dialog)
        dialog.exec()
        dialog.deleteLater()
