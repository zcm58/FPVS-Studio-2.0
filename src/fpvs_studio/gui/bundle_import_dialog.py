"""Review and Welcome-hosted progress dialogs for project-bundle imports."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
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
from fpvs_studio.gui.processing_page import BundleImportProcessingPage


def _format_bytes(size_bytes: int) -> str:
    value = float(max(0, size_bytes))
    units = ("B", "KB", "MB", "GB")
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value):,} {unit}"
            return f"{value:,.1f} {unit}"
        value /= 1024.0
    return f"{int(size_bytes):,} B"


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

        eyebrow = QLabel("PROJECT IMPORT", self)
        eyebrow.setObjectName("bundle_import_review_eyebrow")
        eyebrow.setProperty("bundleWorkflowRole", "eyebrow")

        title = QLabel("Review project bundle", self)
        title.setObjectName("bundle_import_review_title")
        title.setProperty("bundleWorkflowRole", "title")

        lead = QLabel("Confirm what will be added to this computer.", self)
        lead.setObjectName("bundle_import_review_lead")
        lead.setProperty("bundleWorkflowRole", "lead")

        file_card = QFrame(self)
        file_card.setObjectName("bundle_import_review_file_card")
        file_card.setProperty("bundleWorkflowCard", "true")
        file_layout = QHBoxLayout(file_card)
        file_layout.setContentsMargins(18, 16, 18, 16)
        file_layout.setSpacing(14)

        file_mark = QLabel("FPVS", file_card)
        file_mark.setObjectName("bundle_import_review_file_mark")
        file_mark.setProperty("bundleWorkflowRole", "fileMark")
        file_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_mark.setFixedSize(52, 52)

        file_text_layout = QVBoxLayout()
        file_text_layout.setContentsMargins(0, 0, 0, 0)
        file_text_layout.setSpacing(5)
        self.filename_label = QLabel(bundle_path.name, file_card)
        self.filename_label.setObjectName("bundle_import_review_filename")
        self.filename_label.setProperty("bundleWorkflowRole", "fileName")
        self.filename_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        metadata_label = QLabel(
            f"{manifest.project.name}   •   {len(manifest.files):,} files   •   "
            f"{_format_bytes(total_bytes)}",
            file_card,
        )
        metadata_label.setObjectName("bundle_import_review_metadata")
        metadata_label.setProperty("bundleWorkflowRole", "meta")
        file_text_layout.addWidget(self.filename_label)
        file_text_layout.addWidget(metadata_label)

        self.manifest_badge = StatusBadgeLabel(parent=file_card)
        self.manifest_badge.setObjectName("bundle_import_review_status")
        self.manifest_badge.setMinimumWidth(110)
        self.manifest_badge.set_state("ready", "Manifest readable")

        file_layout.addWidget(file_mark)
        file_layout.addLayout(file_text_layout, 1)
        file_layout.addWidget(self.manifest_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        destination_heading = QLabel("Import destination", self)
        destination_heading.setProperty("bundleWorkflowRole", "sectionTitle")
        self.destination_label = PathValueLabel(parent=self)
        self.destination_label.setObjectName("bundle_import_review_destination")
        self.destination_label.set_path_text(str(destination_path), max_length=100)

        destination_card = QFrame(self)
        destination_card.setObjectName("bundle_import_review_destination_card")
        destination_card.setProperty("bundleWorkflowCard", "true")
        destination_layout = QVBoxLayout(destination_card)
        destination_layout.setContentsMargins(16, 12, 16, 12)
        destination_layout.setSpacing(5)
        destination_layout.addWidget(self.destination_label)
        collision_note = QLabel(
            "If that folder already exists, FPVS Studio creates a uniquely named project folder.",
            destination_card,
        )
        collision_note.setProperty("bundleWorkflowRole", "meta")
        collision_note.setWordWrap(True)
        destination_layout.addWidget(collision_note)

        actions_card = QFrame(self)
        actions_card.setObjectName("bundle_import_review_actions_card")
        actions_card.setProperty("bundleWorkflowCard", "true")
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(16, 14, 16, 14)
        actions_layout.setSpacing(8)
        actions_heading = QLabel("What FPVS Studio will do", actions_card)
        actions_heading.setProperty("bundleWorkflowRole", "sectionTitle")
        actions_layout.addWidget(actions_heading)
        for text in (
            "Create a new project folder",
            "Copy original stimulus files",
            "Preserve project settings and provenance",
        ):
            item = QLabel(f"✓  {text}", actions_card)
            item.setProperty("bundleWorkflowRole", "checkItem")
            actions_layout.addWidget(item)

        safety_note = QLabel(
            "Existing projects are never overwritten. Logs, runs, and cache are not included.",
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
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(lead)
        layout.addWidget(file_card)
        layout.addWidget(destination_heading)
        layout.addWidget(destination_card)
        layout.addWidget(actions_card)
        layout.addWidget(safety_note)
        layout.addStretch(1)
        layout.addLayout(button_row)

        apply_studio_theme(self)


class BundleImportProgressDialog(QDialog):
    """Show the embedded import progress page when no project window exists yet."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("bundle_import_progress_dialog")
        self.setWindowTitle("Importing FPVS Studio Project")
        self.setModal(True)
        self.setMinimumSize(940, 600)
        self.resize(1040, 680)

        self.page = BundleImportProcessingPage(parent=self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.page)
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
        self.page.reset_steps()
        self.page.set_stage("verify")
        self.page.start()
        self.show()
        self.raise_()

    def set_stage(self, stage: str) -> None:
        if stage in {"verify", "base", "oddball", "project", "complete"}:
            self.page.set_stage(cast(BundleImportStage, stage))

    def finish(self) -> None:
        self.page.stop()
        self.close()
