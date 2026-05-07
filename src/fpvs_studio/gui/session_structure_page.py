"""Session-structure authoring widgets for the FPVS Studio GUI."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.enums import InterConditionMode
from fpvs_studio.gui.components import NonHomePageShell, SectionCard
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import (
    _prefixed_object_name,
    _set_form_row_visible,
    _show_error_dialog,
    _transition_label,
)


class SessionStructureEditor(QWidget):
    """Reusable session-structure editor widget."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        object_name_prefix: str = "",
        title: str = "Session Structure",
        subtitle: str = "Block order and inter-condition flow.",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document

        self.block_count_spin = QSpinBox(self)
        self.block_count_spin.setObjectName(
            _prefixed_object_name(object_name_prefix, "block_count_spin")
        )
        self.block_count_spin.setRange(1, 1000)
        self.block_count_spin.valueChanged.connect(self._apply_session_settings)

        self.session_seed_spin = QSpinBox(self)
        self.session_seed_spin.setObjectName(
            _prefixed_object_name(object_name_prefix, "session_seed_spin")
        )
        self.session_seed_spin.setRange(0, 2_147_483_647)
        self.session_seed_spin.valueChanged.connect(self._apply_session_settings)

        self.generate_seed_button = QPushButton("Generate New Seed", self)
        self.generate_seed_button.setObjectName(
            _prefixed_object_name(object_name_prefix, "generate_seed_button")
        )
        self.generate_seed_button.clicked.connect(self._generate_seed)

        self.randomize_checkbox = QCheckBox("Randomize conditions within each block", self)
        self.randomize_checkbox.setObjectName(
            _prefixed_object_name(object_name_prefix, "randomize_conditions_checkbox")
        )
        self.randomize_checkbox.stateChanged.connect(self._apply_session_settings)

        self.inter_condition_mode_combo = QComboBox(self)
        self.inter_condition_mode_combo.setObjectName(
            _prefixed_object_name(object_name_prefix, "inter_condition_mode_combo")
        )
        self.inter_condition_mode_combo.addItem(
            _transition_label(InterConditionMode.MANUAL_CONTINUE),
            userData=InterConditionMode.MANUAL_CONTINUE,
        )
        self.inter_condition_mode_combo.currentIndexChanged.connect(
            self._on_inter_condition_mode_changed
        )

        self.break_seconds_spin = QDoubleSpinBox(self)
        self.break_seconds_spin.setObjectName(
            _prefixed_object_name(object_name_prefix, "inter_condition_break_seconds_spin")
        )
        self.break_seconds_spin.setRange(0.0, 3600.0)
        self.break_seconds_spin.setDecimals(1)
        self.break_seconds_spin.valueChanged.connect(self._apply_session_settings)

        self.continue_key_edit = QLineEdit(self)
        self.continue_key_edit.setObjectName(
            _prefixed_object_name(object_name_prefix, "continue_key_edit")
        )
        self.continue_key_edit.setEnabled(False)

        self.session_card = SectionCard(
            title=title,
            subtitle=subtitle,
            object_name=_prefixed_object_name(object_name_prefix, "session_structure_card"),
            parent=self,
        )
        self.session_layout = QFormLayout()
        self.session_layout.setVerticalSpacing(7)
        seed_layout = QHBoxLayout()
        seed_layout.addWidget(self.session_seed_spin, 1)
        seed_layout.addWidget(self.generate_seed_button)
        self.session_layout.addRow("Block count", self.block_count_spin)
        self.session_layout.addRow("Session seed", seed_layout)
        self.session_layout.addRow("", self.randomize_checkbox)
        self.session_layout.addRow("Start key", self.continue_key_edit)
        self.session_card.card_layout.setContentsMargins(12, 10, 12, 10)
        self.session_card.card_layout.setSpacing(8)
        self.session_card.body_layout.setSpacing(8)
        self.session_card.body_layout.addLayout(self.session_layout)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.session_card)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        session = self._document.project.settings.session
        with QSignalBlocker(self.block_count_spin):
            self.block_count_spin.setValue(session.block_count)
        with QSignalBlocker(self.session_seed_spin):
            self.session_seed_spin.setValue(session.session_seed)
        with QSignalBlocker(self.randomize_checkbox):
            self.randomize_checkbox.setChecked(session.randomize_conditions_per_block)
        with QSignalBlocker(self.inter_condition_mode_combo):
            self.inter_condition_mode_combo.setCurrentIndex(
                self.inter_condition_mode_combo.findData(InterConditionMode.MANUAL_CONTINUE)
            )
        with QSignalBlocker(self.break_seconds_spin):
            self.break_seconds_spin.setValue(session.inter_condition_break_seconds)
        with QSignalBlocker(self.continue_key_edit):
            self.continue_key_edit.setText("space")
        self._update_session_visibility_state()

    def _update_session_visibility_state(self) -> None:
        _set_form_row_visible(self.session_layout, self.inter_condition_mode_combo, False)
        _set_form_row_visible(self.session_layout, self.break_seconds_spin, False)
        _set_form_row_visible(self.session_layout, self.continue_key_edit, True)
        self.inter_condition_mode_combo.setEnabled(False)
        self.break_seconds_spin.setEnabled(False)
        self.continue_key_edit.setEnabled(False)

    def _on_inter_condition_mode_changed(self) -> None:
        self._update_session_visibility_state()
        self._apply_session_settings()

    def _apply_session_settings(self) -> None:
        try:
            self._document.update_session_settings(
                block_count=self.block_count_spin.value(),
                session_seed=self.session_seed_spin.value(),
                randomize_conditions_per_block=self.randomize_checkbox.isChecked(),
                inter_condition_mode=InterConditionMode.MANUAL_CONTINUE,
                inter_condition_break_seconds=0.0,
                continue_key="space",
            )
        except Exception as error:
            _show_error_dialog(self, "Session Settings Error", error)
            self.refresh()
            return
        self._update_session_visibility_state()

    def _generate_seed(self) -> None:
        try:
            self._document.generate_new_session_seed()
        except Exception as error:
            _show_error_dialog(self, "Session Seed Error", error)


class SessionStructurePage(QWidget):
    """Session-level settings page."""

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = SessionStructureEditor(document, parent=self)
        self.shell = NonHomePageShell(
            title="Session Structure",
            subtitle="Configure block sequencing and inter-condition transition flow.",
            layout_mode="single_column",
            parent=self,
        )
        self.shell.add_content_widget(self.editor)
        self.shell.add_content_widget(QWidget(self.shell), stretch=1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.shell)

        self.block_count_spin = self.editor.block_count_spin
        self.session_seed_spin = self.editor.session_seed_spin
        self.generate_seed_button = self.editor.generate_seed_button
        self.randomize_checkbox = self.editor.randomize_checkbox
        self.inter_condition_mode_combo = self.editor.inter_condition_mode_combo
        self.break_seconds_spin = self.editor.break_seconds_spin
        self.continue_key_edit = self.editor.continue_key_edit
        self.session_layout = self.editor.session_layout

    def refresh(self) -> None:
        self.editor.refresh()
