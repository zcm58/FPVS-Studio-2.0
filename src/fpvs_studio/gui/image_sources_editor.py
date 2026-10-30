"""Per-condition image selection for Setup, without visual preview work."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from fpvs_studio.core.models import StimulusSet
from fpvs_studio.gui.components import SetupSourceCard, mark_error_text
from fpvs_studio.gui.designer_sources import import_designer_source
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import _resolution_text
from fpvs_studio.gui.workers import BackgroundTask
from fpvs_studio.preprocessing.models import StimulusSetInspectionSummary

_LOG = logging.getLogger(__name__)


class ImageSourcesEditor(QWidget):
    """Adopt each selected source immediately through the document's import seam."""

    applied = Signal()
    busy_changed = Signal(bool)
    draft_changed = Signal()

    def __init__(
        self, document: ProjectDocument, *, condition_id: str, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._condition_id = condition_id
        self._task: BackgroundTask | None = None
        self._import_role: str | None = None
        self._error = ""
        self.setObjectName("image_sources_editor")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        sources = QHBoxLayout()
        sources.setSpacing(12)
        self.base_source = SetupSourceCard(
            "Base images", "Choose Base folder…", object_name="design_base_source",
            show_variants=False, show_details=True, parent=self,
        )
        self.oddball_source = SetupSourceCard(
            "Oddball images", "Choose Oddball folder…", object_name="design_oddball_source",
            show_variants=False, show_details=True, parent=self,
        )
        self._cards = {"base": self.base_source, "oddball": self.oddball_source}
        for role, card in self._cards.items():
            sources.addWidget(card, 1)
            card.choose_requested.connect(lambda role=role: self._choose_source(role))
        layout.addLayout(sources)
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        mark_error_text(self.status_label)
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        self.refresh()

    def has_pending_design(self) -> bool:
        return False

    def is_busy(self) -> bool:
        return self._task is not None

    def is_importing(self) -> bool:
        return self.is_busy()

    def validation_message(self) -> str:
        if self.is_importing():
            return "Wait for the image folder to finish loading."
        if self._error:
            return self._error
        if any(
            self._document.get_condition_stimulus_set(self._condition_id, role).image_count == 0
            for role in self._cards
        ):
            return "Choose Base and Oddball images to continue."
        return ""

    def apply_pending_design(self) -> bool:
        message = self.validation_message()
        self.status_label.setText(message)
        self.status_label.setVisible(bool(message))
        return not message

    def request_close(self) -> bool:
        return not self.is_busy()

    def refresh(self) -> None:
        for role, card in self._cards.items():
            source = self._document.get_condition_stimulus_set(self._condition_id, role)
            path = (
                str(self._document.project_root / source.source_dir)
                if source.source_dir and source.image_count else ""
            )
            card.set_source_state(
                ready=source.image_count > 0, folder=path,
                image_count=f"{source.image_count} images",
                resolution=_resolution_text(source.resolution), variants="",
            )
            card.set_source_details(path)
            card.choose_button.setEnabled(not self.is_busy())
            if role == self._import_role:
                card.status_badge.set_state("busy", "Importing…")
        self.status_label.setText(self._error)
        self.status_label.setVisible(bool(self._error))

    def _choose_source(self, role: str) -> None:
        if self.is_busy():
            return
        title = self._cards[role].title_label.text()
        directory = QFileDialog.getExistingDirectory(
            self, f"Choose {title} folder", str(self._document.project_root / "stimuli"),
        )
        if directory:
            self._start_source_import(role, Path(directory))

    def _start_source_import(self, role: str, directory: Path) -> None:
        if self.is_busy():
            return
        self._error = ""
        self._import_role = role
        root, condition_id = self._document.project_root, self._condition_id
        task = BackgroundTask(
            parent_widget=self,
            callback=lambda: import_designer_source(root, condition_id, role, directory),
        )
        self._task = task
        task.succeeded.connect(lambda result: self._source_imported(role, result))
        task.failed.connect(self._task_failed)
        task.finished.connect(self._import_finished)
        self.refresh()
        self.busy_changed.emit(True)
        task.start()

    def _source_imported(self, role: str, result: object) -> None:
        summary, source = cast(tuple[StimulusSetInspectionSummary, StimulusSet], result)
        try:
            self._document.apply_designer_source(
                self._condition_id, role=role, stimulus_set=source, summary=summary,
            )
        except (ValueError, OSError) as error:
            self._task_failed(error)
            return
        self.refresh()
        self.applied.emit()

    def _task_failed(self, error: object) -> None:
        _LOG.error("Setup image source import failed: %s", error)
        self._error = str(error)
        self.refresh()
        self.draft_changed.emit()

    def _import_finished(self) -> None:
        self._task = None
        self._import_role = None
        self.refresh()
        self.busy_changed.emit(False)
        self.draft_changed.emit()
