"""Review and Welcome-hosted progress dialogs for project-bundle imports."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.project_bundle import BundleImportStage, ProjectBundleManifest
from fpvs_studio.gui.components import (
    PathValueLabel,
    StatusBadgeLabel,
    apply_studio_theme,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.processing_page import BundleImportProcessingPage, _format_file_size


class BundleImportReviewDialog(QDialog):
    """Let the user review bundle identity and destination before import starts."""

    CHOOSE_ANOTHER_RESULT = 2

    def __init__(
        self,
        *,
        bundle_path: Path,
        root_dir: Path,
        manifest: ProjectBundleManifest,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("bundle_import_review_dialog")
        self.setWindowTitle("Review Project Bundle")
        self.setModal(True)
        self.setMinimumSize(720, 560)
        self.resize(780, 610)

        total_bytes = sum(record.size_bytes for record in manifest.files)
        destination_path = root_dir / manifest.project.project_id

        title = QLabel("Review project bundle", self)
        title.setObjectName("bundle_import_review_title")
        title.setProperty("bundleWorkflowRole", "title")

        file_layout = QHBoxLayout()
        file_layout.setSpacing(14)

        file_text_layout = QVBoxLayout()
        file_text_layout.setContentsMargins(0, 0, 0, 0)
        file_text_layout.setSpacing(5)
        self.filename_label = PathValueLabel(bundle_path.name, self, single_line=True)
        self.filename_label.setObjectName("bundle_import_review_filename")
        self.filename_label.setProperty("pathValue", "false")
        self.filename_label.setProperty("bundleWorkflowRole", "fileName")
        metadata_label = QLabel(
            f"{manifest.project.name}   •   {len(manifest.files):,} files   •   "
            f"{_format_file_size(total_bytes)}",
            self,
        )
        metadata_label.setObjectName("bundle_import_review_metadata")
        metadata_label.setProperty("bundleWorkflowRole", "meta")
        metadata_label.setTextFormat(Qt.TextFormat.PlainText)
        metadata_label.setWordWrap(True)
        file_text_layout.addWidget(self.filename_label)
        file_text_layout.addWidget(metadata_label)

        self.manifest_badge = StatusBadgeLabel(parent=self)
        self.manifest_badge.setObjectName("bundle_import_review_status")
        self.manifest_badge.setMinimumWidth(110)
        self.manifest_badge.set_state("ready", "Manifest readable")

        file_layout.addLayout(file_text_layout, 1)
        file_layout.addWidget(self.manifest_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        destination_heading = QLabel("Import destination", self)
        destination_heading.setProperty("bundleWorkflowRole", "sectionTitle")
        self.destination_label = PathValueLabel(parent=self, single_line=True)
        self.destination_label.setObjectName("bundle_import_review_destination")
        self.destination_label.set_path_text(str(destination_path))

        collision_note = QLabel(
            "Studio creates a new project folder. If this name is taken, Studio adds a suffix.",
            self,
        )
        collision_note.setProperty("bundleWorkflowRole", "meta")
        collision_note.setWordWrap(True)

        safety_note = QLabel(
            "The bundle includes original stimulus files, project settings, and provenance. "
            "It excludes logs, runs, and cache.",
            self,
        )
        safety_note.setObjectName("bundle_import_review_safety_note")
        safety_note.setProperty("bundleWorkflowRole", "note")
        safety_note.setWordWrap(True)

        self.choose_another_button = QPushButton("Choose Another File", self)
        self.choose_another_button.setObjectName("bundle_import_review_choose_another")
        mark_secondary_action(self.choose_another_button)
        self.choose_another_button.clicked.connect(
            lambda: self.done(self.CHOOSE_ANOTHER_RESULT)
        )

        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.setObjectName("bundle_import_review_cancel")
        mark_secondary_action(self.cancel_button)
        self.cancel_button.clicked.connect(self.reject)

        self.import_button = QPushButton("Import Project", self)
        self.import_button.setObjectName("bundle_import_review_import")
        mark_primary_action(self.import_button)
        self.import_button.clicked.connect(self.accept)
        self.import_button.setDefault(True)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 4, 0, 0)
        button_row.setSpacing(10)
        button_row.addWidget(self.choose_another_button)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.import_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addLayout(file_layout)
        layout.addWidget(destination_heading)
        layout.addWidget(self.destination_label)
        layout.addWidget(collision_note)
        layout.addWidget(safety_note)
        layout.addStretch(1)
        layout.addLayout(button_row)

        apply_studio_theme(self)


class BundleImportProgressDialog(QDialog):
    """Show the embedded import progress page when no project window exists yet."""

    def __init__(
        self, *, parent: QWidget | None = None, on_cancel: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("bundle_import_progress_dialog")
        self.setWindowTitle("Importing FPVS Studio Project")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setMinimumSize(940, 600)
        self.resize(1040, 680)
        self._import_active = False
        self._on_cancel = on_cancel

        self.page = BundleImportProcessingPage(parent=self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.page)
        self.cancel_button = QPushButton("Cancel setup", self)
        self.cancel_button.setAutoDefault(False)
        mark_secondary_action(self.cancel_button)
        self.cancel_button.setVisible(on_cancel is not None)
        self.cancel_button.clicked.connect(self._cancel)
        layout.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignRight)
        apply_studio_theme(self)

    def set_context(
        self,
        *,
        project_name: str,
        bundle_path: Path,
        root_dir: Path,
    ) -> None:
        self.page.set_transfer_context(
            title=f"Importing {project_name}",
            source_label="Source",
            source_path=bundle_path,
            destination_label="Destination root",
            destination_path=root_dir,
        )

    def start(self) -> None:
        self._import_active = True
        self.page.reset_steps()
        self.page.set_stage("verify")
        self.page.start()
        self.show()
        self.raise_()

    def set_stage(self, stage: str) -> None:
        if stage in {"verify", "base", "oddball", "project", "complete"}:
            self.page.set_stage(cast(BundleImportStage, stage))

    def finish(self) -> None:
        self._import_active = False
        self.page.stop()
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._import_active:
            self._cancel()
            event.ignore()
            return
        super().closeEvent(event)

    def reject(self) -> None:
        if self._import_active:
            self._cancel()
            return
        super().reject()

    def _cancel(self) -> None:
        if self._on_cancel is not None and self._import_active:
            self._on_cancel()
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText("Finishing cancellation…")
