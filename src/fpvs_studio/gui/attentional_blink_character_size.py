"""Native character height with the existing display-calibration controls."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QWidget

from fpvs_studio.core.enums import PresentationUnit, TextHeightMode
from fpvs_studio.core.models import TextHeightScheduleSettings
from fpvs_studio.gui.components import mark_error_text
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.runtime_settings_page import ImageDisplaySizeEditor


class AttentionalBlinkCharacterSizeEditor(ImageDisplaySizeEditor):
    """Reuse viewing geometry while editing the text-height owner, not image width."""

    draft_changed = Signal()

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(document, parent)
        self.setObjectName("ab_character_size_editor")
        self.character_height_edit = QLineEdit(self)
        self.character_height_edit.setAccessibleName("Character height")
        self.character_height_edit.setMaximumWidth(160)
        self.character_unit_combo = QComboBox(self)
        self.character_unit_combo.addItem("Visual degrees", PresentationUnit.DEGREES)
        self.character_unit_combo.addItem(
            "Screen-height fraction",
            PresentationUnit.WINDOW_HEIGHT_FRACTION,
        )
        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.character_height_edit)
        row_layout.addWidget(self.character_unit_combo)
        row_layout.addStretch(1)
        self.form_layout.insertRow(0, "Character height", row)
        self.size_validation_label = QLabel(self)
        self.size_validation_label.setWordWrap(True)
        mark_error_text(self.size_validation_label)
        layout = self.layout()
        assert layout is not None
        layout.addWidget(self.size_validation_label)
        self.character_height_edit.editingFinished.connect(self._apply_character_size)
        self.character_height_edit.textChanged.connect(self._validate_character_size)
        self.character_unit_combo.currentIndexChanged.connect(self._apply_character_size)
        self.refresh()

    def refresh(self) -> None:
        super().refresh()
        if not hasattr(self, "character_height_edit"):
            return
        self.width_degrees_spin.hide()
        width_label = self.form_layout.labelForField(self.width_degrees_spin)
        assert width_label is not None
        width_label.hide()
        self.full_screen_preview_button.hide()
        self.preview_value_label.hide()
        self.configure_presentation_button.hide()
        self.presentation_summary_label.setText(
            "The same fixed height is used for base digits, T1 and T2. "
            "Viewing geometry below determines the size in visual degrees."
        )
        height = self._document.project.settings.presentation.defaults.text_height
        if not self.character_height_edit.hasFocus():
            with QSignalBlocker(self.character_height_edit):
                self.character_height_edit.setText(f"{height.values[0]:g}")
        with QSignalBlocker(self.character_unit_combo):
            self.character_unit_combo.setCurrentIndex(
                self.character_unit_combo.findData(height.unit)
            )
        self._validate_character_size()

    def _height_settings(self) -> TextHeightScheduleSettings:
        return TextHeightScheduleSettings(
            mode=TextHeightMode.FIXED,
            unit=self.character_unit_combo.currentData(),
            values=[float(self.character_height_edit.text())],
        )

    def validation_message(self) -> str:
        try:
            self._height_settings()
        except ValueError:
            return "Enter a character height greater than zero."
        return ""

    def _validate_character_size(self, *_args: object) -> None:
        message = self.validation_message()
        self.size_validation_label.setText(message)
        self.size_validation_label.setVisible(bool(message))
        self.draft_changed.emit()

    def _apply_character_size(self, *_args: object) -> None:
        if self.validation_message():
            self._validate_character_size()
            return
        defaults = self._document.project.settings.presentation.defaults.model_copy(
            update={"text_height": self._height_settings()},
            deep=True,
        )
        self._document.update_presentation_settings(defaults=defaults)
