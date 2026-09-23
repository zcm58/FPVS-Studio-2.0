"""Condition selection around the shared, category-specific visual design editor."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from fpvs_studio.core.compiler_masking import validate_masking_settings
from fpvs_studio.core.enums import ExperimentCategory, StimulusModality
from fpvs_studio.core.experiment_categories import (
    RETIRED_IMAGE_PAIR_MESSAGE,
    category_conflict_condition_ids,
    experiment_category_label,
    has_retired_image_pair_design,
)
from fpvs_studio.core.masking import condition_masking
from fpvs_studio.core.models import AttentionalBlinkStreamSettings
from fpvs_studio.gui.attentional_blink_stream_designer import (
    AttentionalBlinkStreamDesigner,
    is_letter_stream_project,
)
from fpvs_studio.gui.components import mark_secondary_action
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.experiment_designer_dialog import ExperimentDesignerWidget


class DesignSetupStep(QWidget):
    """Keep each draft with its condition and apply it before leaving Design."""

    applied = Signal()
    busy_changed = Signal(bool)
    draft_changed = Signal()

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._document = document
        self._selected_id: str | None = None
        self._refreshing = False
        self._displayed_project = document.project
        self.editor: ExperimentDesignerWidget | AttentionalBlinkStreamDesigner | None = None
        self.setObjectName("design_setup_step")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        selector = QHBoxLayout()
        self.condition_label = QLabel("Condition", self)
        selector.addWidget(self.condition_label)
        self.condition_combo = QComboBox(self)
        self.condition_combo.setMinimumWidth(0)
        self.condition_combo.setAccessibleName("Condition to design")
        selector.addWidget(self.condition_combo, 1)
        self.category_label = QLabel(
            experiment_category_label(document.project.experiment_category), self
        )
        selector.addWidget(self.category_label)
        layout.addLayout(selector)
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.masking_edit_button = QPushButton("Edit Masking Modifier…", self)
        self.masking_edit_button.setObjectName("design_masking_edit_button")
        mark_secondary_action(self.masking_edit_button)
        self.masking_edit_button.clicked.connect(self._edit_masking)
        self.masking_edit_button.hide()
        layout.addWidget(self.masking_edit_button)
        self.editor_container = QWidget(self)
        self.editor_layout = QVBoxLayout(self.editor_container)
        self.editor_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.editor_container, 1)
        self.condition_combo.currentIndexChanged.connect(self._selection_changed)
        document.project_changed.connect(self.refresh)
        self.refresh()

    def selected_condition_id(self) -> str | None:
        return self._selected_id

    def has_pending_design(self) -> bool:
        return self.editor is not None and self.editor.has_pending_design()

    def is_busy(self) -> bool:
        return self.editor is not None and self.editor.is_busy()

    def is_importing(self) -> bool:
        return self.editor is not None and self.editor.is_importing()

    def _show_message(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setVisible(bool(message))

    def _category_message(self) -> str:
        if has_retired_image_pair_design(self._document.project):
            return RETIRED_IMAGE_PAIR_MESSAGE
        if self._document.project.experiment_category == ExperimentCategory.FPVS:
            return (
                "Standard FPVS design is coming soon. "
                "Create an FPVS Oddball Paradigm or Attentional-Blink experiment."
            )
        if category_conflict_condition_ids(self._document.project):
            return (
                "This experiment contains conditions from another category. "
                "Return to Conditions and separate them into "
                "an experiment of the matching category."
            )
        if self._selected_id is None:
            return "Add a condition in Conditions, then return here to design its sequence."
        return ""

    def validation_message(self) -> str:
        message = self._category_message()
        if message:
            return message
        condition = self._document.get_condition(self._selected_id) if self._selected_id else None
        masking = condition_masking(self._document.project, condition) if condition else None
        if masking is not None and condition is not None:
            try:
                validate_masking_settings(
                    self._document.project, condition, masking,
                    self._document.project.settings.display.preferred_refresh_hz or 60.0,
                )
            except ValueError as error:
                return str(error)
        elif condition is not None and any(
            self._document.get_stimulus_set(set_id) is None for set_id in (
                condition.base_stimulus_set_id, condition.oddball_stimulus_set_id,
            )
        ):
            return "This condition has no stimulus sources. Configure its sources in Conditions."
        return self.editor.validation_message() if self.editor is not None else ""

    def apply_pending_design(self) -> bool:
        message = self._category_message()
        if message:
            self._show_message(message)
            return False
        if self.editor is None:
            message = self.validation_message()
            self._show_message(message)
            return not message
        self._show_message("")
        if not self.editor.apply_pending_design():
            return False
        self._show_message("")
        return True

    def discard_pending_design(self) -> bool:
        """Restore the saved document draft after an explicit discard action."""
        if self.is_busy():
            return False
        self._display_condition(self._selected_id)
        self._restore_selection()
        return True

    def select_condition(self, condition_id: str) -> bool:
        index = self.condition_combo.findData(condition_id)
        if index < 0:
            return False
        if condition_id == self._selected_id:
            return True
        if isinstance(self.editor, AttentionalBlinkStreamDesigner):
            self.editor.select_condition(condition_id)
            return True
        if self.is_busy():
            self._show_message(
                "Wait for the image folder to finish loading before changing conditions."
            )
            return False
        if self.has_pending_design() and not self.apply_pending_design():
            self._restore_selection()
            return False
        self._display_condition(condition_id)
        self._restore_selection()
        return True

    def _restore_selection(self) -> None:
        with QSignalBlocker(self.condition_combo):
            self.condition_combo.setCurrentIndex(self.condition_combo.findData(self._selected_id))

    def _selection_changed(self, _index: int) -> None:
        selected = self.condition_combo.currentData()
        if isinstance(selected, str) and not self.select_condition(selected):
            self._restore_selection()

    def refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        try:
            conditions = self._document.ordered_conditions()
            stream = is_letter_stream_project(self._document)
            self.condition_label.setVisible(not stream)
            self.condition_combo.setVisible(not stream)
            self.category_label.setVisible(not stream)
            desired = self._selected_id
            if desired not in {condition.condition_id for condition in conditions}:
                desired = conditions[0].condition_id if conditions else None
            with QSignalBlocker(self.condition_combo):
                self.condition_combo.clear()
                for condition in conditions:
                    self.condition_combo.addItem(condition.name, condition.condition_id)
                self.condition_combo.setCurrentIndex(self.condition_combo.findData(desired))
            self.condition_combo.setEnabled(bool(conditions) and not self.is_busy())
            conflict = desired in category_conflict_condition_ids(self._document.project)
            selected = self._document.get_condition(desired) if desired else None
            masking = condition_masking(self._document.project, selected) if selected else None
            if (desired != self._selected_id
                    or (self.editor is not None and (conflict or masking is not None))):
                if not self.is_busy():
                    self._display_condition(desired)
            elif self.editor is not None and self._displayed_project is not self._document.project:
                self.editor.refresh()
            elif self.editor is None:
                self._display_condition(desired)
            self._displayed_project = self._document.project
        finally:
            self._refreshing = False

    def _display_condition(self, condition_id: str | None) -> None:
        self.masking_edit_button.hide()
        if self.editor is not None:
            self.editor.request_close()
            self.editor_layout.removeWidget(self.editor)
            self.editor.hide()
            self.editor.deleteLater()
            self.editor = None
        self._selected_id = condition_id
        self._show_message("")
        condition = self._document.get_condition(condition_id) if condition_id else None
        if condition is None:
            self._show_message(self._category_message())
            return
        if (
            has_retired_image_pair_design(self._document.project)
            or condition_id in category_conflict_condition_ids(self._document.project)
        ):
            self._show_message(self._category_message())
            return
        masking = condition_masking(self._document.project, condition)
        if masking is not None:
            self._show_message(
                f"{masking.variant.title()} masking · {masking.soa_ms:g} ms target-to-mask SOA.\n"
                f"{len(masking.base_visuals)} base and "
                f"{len(masking.target_visuals)} target visuals. "
                "Condition Modifiers owns the source pools, exact appearance, timing and questions."
            )
            self.masking_edit_button.show()
            return
        source = self._document.get_stimulus_set(condition.base_stimulus_set_id)
        if source is None:
            self._show_message(
                "This condition has no stimulus sources. Add a modifier in Conditions "
                "or create a condition with image or word sources."
            )
            return
        stream = isinstance(condition.attentional_blink, AttentionalBlinkStreamSettings)
        if source.modality == StimulusModality.WORD and not stream:
            self._show_message(
                "This condition uses word lists. Edit its words in Conditions and its "
                "presentation rate in Timing. Image blocks are available for image conditions."
            )
            return
        if stream:
            self.editor = AttentionalBlinkStreamDesigner(
                self._document, condition_id=condition.condition_id, parent=self,
            )
            self.editor.condition_selected.connect(self._stream_condition_selected)
        else:
            self.editor = ExperimentDesignerWidget(
                self._document, condition_id=condition.condition_id, embedded=True, parent=self,
            )
        self.editor_layout.addWidget(self.editor)
        self.editor.applied.connect(self.applied.emit)
        self.editor.draft_changed.connect(self.draft_changed.emit)
        self.editor.busy_changed.connect(self._editor_busy_changed)
        self.condition_combo.setEnabled(not self.editor.is_busy())
        self._displayed_project = self._document.project

    def _edit_masking(self) -> None:
        if self._selected_id is None:
            return
        from fpvs_studio.gui.condition_modifier_dialog import ConditionModifierDialog

        dialog = ConditionModifierDialog(
            self._document, condition_id=self._selected_id, parent=self,
        )
        dialog.exec()
        self.refresh()

    def _stream_condition_selected(self, condition_id: str) -> None:
        self._selected_id = condition_id
        self._restore_selection()

    def _editor_busy_changed(self, busy: bool) -> None:
        self.condition_combo.setEnabled(not busy)
        self.busy_changed.emit(busy)
        if not busy:
            self.refresh()
