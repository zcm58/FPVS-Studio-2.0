"""Condition authoring page for the FPVS Studio main window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.enums import (
    DutyCycleMode,
    StimulusVariant,
)
from fpvs_studio.core.models import Condition
from fpvs_studio.core.template_library import get_template
from fpvs_studio.gui.components import (
    PAGE_SECTION_GAP,
    NonHomePageShell,
    PathValueLabel,
    SectionCard,
    StatusBadgeLabel,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import (
    _CYCLE_HELP_TEXT,
    _duty_cycle_label,
    _resolution_text,
    _show_error_dialog,
    _sync_text_editor_contents,
    _variant_label,
)


class ConditionsPage(QWidget):
    """Condition list/editor page."""

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._document = document

        self.condition_list = QListWidget(self)
        self.condition_list.setObjectName("condition_list")
        self.condition_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.condition_list.setAlternatingRowColors(True)
        self.condition_list.setMinimumWidth(260)
        self.condition_list.setMinimumHeight(0)
        self.condition_list.currentItemChanged.connect(self._refresh_editor)

        self.add_condition_button = QPushButton("Add", self)
        self.add_condition_button.setObjectName("add_condition_button")
        self.add_condition_button.clicked.connect(self._add_condition)
        mark_primary_action(self.add_condition_button)
        self.remove_condition_button = QPushButton("Remove", self)
        self.remove_condition_button.setObjectName("remove_condition_button")
        self.remove_condition_button.clicked.connect(self._remove_condition)
        self.move_up_button = QPushButton("Up", self)
        self.move_up_button.setObjectName("move_condition_up_button")
        self.move_up_button.clicked.connect(lambda: self._move_condition(-1))
        self.move_down_button = QPushButton("Down", self)
        self.move_down_button.setObjectName("move_condition_down_button")
        self.move_down_button.clicked.connect(lambda: self._move_condition(1))

        list_button_layout = QHBoxLayout()
        list_button_layout.addWidget(self.add_condition_button)
        list_button_layout.addWidget(self.remove_condition_button)
        list_button_layout.addWidget(self.move_up_button)
        list_button_layout.addWidget(self.move_down_button)
        self.condition_list_card = SectionCard(
            title="Condition List",
            subtitle="Create, remove, and reorder session conditions.",
            object_name="conditions_list_card",
            parent=self,
        )
        self.condition_list_card.card_layout.setContentsMargins(12, 10, 12, 10)
        self.condition_list_card.card_layout.setSpacing(8)
        self.condition_list_card.body_layout.setSpacing(8)
        list_panel_layout = QVBoxLayout()
        list_panel_layout.setContentsMargins(0, 0, 0, 0)
        list_panel_layout.setSpacing(8)
        list_panel_layout.addWidget(self.condition_list, 1)
        list_panel_layout.addLayout(list_button_layout)
        self.condition_list_card.body_layout.addLayout(list_panel_layout)

        self.condition_name_edit = QLineEdit(self)
        self.condition_name_edit.setObjectName("condition_name_edit")
        self.condition_name_edit.editingFinished.connect(self._apply_name)

        self.instructions_edit = QTextEdit(self)
        self.instructions_edit.setObjectName("condition_instructions_edit")
        self.instructions_edit.textChanged.connect(self._apply_instructions)

        self.trigger_code_spin = QSpinBox(self)
        self.trigger_code_spin.setObjectName("condition_trigger_code_spin")
        self.trigger_code_spin.setRange(0, 65535)
        self.trigger_code_spin.valueChanged.connect(self._apply_numeric_fields)

        self.sequence_count_spin = QSpinBox(self)
        self.sequence_count_spin.setObjectName("condition_sequence_count_spin")
        self.sequence_count_spin.setRange(1, 10000)
        self.sequence_count_spin.setToolTip(_CYCLE_HELP_TEXT)
        self.sequence_count_spin.valueChanged.connect(self._apply_numeric_fields)

        self.oddball_cycles_spin = QSpinBox(self)
        self.oddball_cycles_spin.setObjectName("condition_oddball_cycles_spin")
        self.oddball_cycles_spin.setRange(1, 10000)
        self.oddball_cycles_spin.setToolTip(_CYCLE_HELP_TEXT)
        self.oddball_cycles_spin.valueChanged.connect(self._apply_numeric_fields)

        self.variant_combo = QComboBox(self)
        self.variant_combo.setObjectName("condition_variant_combo")
        for variant in StimulusVariant:
            self.variant_combo.addItem(_variant_label(variant), userData=variant)
        self.variant_combo.currentIndexChanged.connect(self._apply_variant_fields)

        self.duty_cycle_combo = QComboBox(self)
        self.duty_cycle_combo.setObjectName("condition_duty_cycle_combo")
        for mode in DutyCycleMode:
            self.duty_cycle_combo.addItem(_duty_cycle_label(mode), userData=mode)
        self.duty_cycle_combo.currentIndexChanged.connect(self._apply_variant_fields)

        self.template_info_label = QLabel(self)
        self.template_info_label.setWordWrap(True)
        self.template_info_label.setObjectName("template_info_label")
        self.template_info_label.setToolTip(_CYCLE_HELP_TEXT)

        self.selected_condition_badge = StatusBadgeLabel("Select a condition to edit", self)
        self.selected_condition_badge.setObjectName("selected_condition_badge")
        self.selected_condition_note = QLabel(self)
        self.selected_condition_note.setObjectName("selected_condition_note")
        self.selected_condition_note.setWordWrap(True)

        self.base_source_value = PathValueLabel(self)
        self.base_source_value.setObjectName("base_source_value")
        self.base_source_state = StatusBadgeLabel("Base source not configured", self)
        self.base_source_state.setObjectName("base_source_state")
        self.base_count_value = QLabel(self)
        self.base_count_value.setObjectName("base_count_value")
        self.base_resolution_value = QLabel(self)
        self.base_resolution_value.setObjectName("base_resolution_value")
        self.base_variants_value = QLabel(self)
        self.base_variants_value.setObjectName("base_variants_value")
        self.base_import_button = QPushButton("Import Base Folder...", self)
        self.base_import_button.setObjectName("import_base_folder_button")
        self.base_import_button.clicked.connect(lambda: self._import_stimulus_folder("base"))
        mark_secondary_action(self.base_import_button)

        self.oddball_source_value = PathValueLabel(self)
        self.oddball_source_value.setObjectName("oddball_source_value")
        self.oddball_source_state = StatusBadgeLabel("Oddball source not configured", self)
        self.oddball_source_state.setObjectName("oddball_source_state")
        self.oddball_count_value = QLabel(self)
        self.oddball_count_value.setObjectName("oddball_count_value")
        self.oddball_resolution_value = QLabel(self)
        self.oddball_resolution_value.setObjectName("oddball_resolution_value")
        self.oddball_variants_value = QLabel(self)
        self.oddball_variants_value.setObjectName("oddball_variants_value")
        self.oddball_import_button = QPushButton("Import Oddball Folder...", self)
        self.oddball_import_button.setObjectName("import_oddball_folder_button")
        self.oddball_import_button.clicked.connect(lambda: self._import_stimulus_folder("oddball"))
        mark_secondary_action(self.oddball_import_button)

        self.condition_editor_card = SectionCard(
            title="Condition Editor",
            subtitle="Edit identity, instructions, timing, and stimulus configuration.",
            object_name="conditions_editor_card",
            parent=self,
        )
        self.condition_editor_card.card_layout.setContentsMargins(12, 10, 12, 10)
        self.condition_editor_card.card_layout.setSpacing(8)
        self.condition_editor_card.body_layout.setSpacing(8)
        selected_row = QWidget(self.condition_editor_card)
        selected_row_layout = QHBoxLayout(selected_row)
        selected_row_layout.setContentsMargins(0, 0, 0, 0)
        selected_row_layout.setSpacing(PAGE_SECTION_GAP)
        selected_row_layout.addWidget(self.selected_condition_badge, 0)
        selected_row_layout.addWidget(self.selected_condition_note, 1)
        self.condition_editor_card.body_layout.addWidget(selected_row)

        basic_form = QFormLayout()
        basic_form.setVerticalSpacing(7)
        basic_form.addRow("Condition Name", self.condition_name_edit)
        basic_form.addRow("Trigger Code", self.trigger_code_spin)
        self.instructions_edit.setMinimumHeight(88)
        self.instructions_edit.setMaximumHeight(120)
        self.instructions_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        timing_grid = QGridLayout()
        timing_grid.setHorizontalSpacing(PAGE_SECTION_GAP)
        timing_grid.setVerticalSpacing(8)
        timing_grid.addWidget(QLabel("Condition Repeats", self.condition_editor_card), 0, 0)
        timing_grid.addWidget(self.sequence_count_spin, 0, 1)
        timing_grid.addWidget(QLabel("Cycles / Repeat", self.condition_editor_card), 1, 0)
        timing_grid.addWidget(self.oddball_cycles_spin, 1, 1)
        timing_grid.addWidget(QLabel("Stimulus Variant", self.condition_editor_card), 0, 2)
        timing_grid.addWidget(self.variant_combo, 0, 3)
        timing_grid.addWidget(QLabel("Duty Cycle", self.condition_editor_card), 1, 2)
        timing_grid.addWidget(self.duty_cycle_combo, 1, 3)
        timing_grid.setColumnStretch(1, 1)
        timing_grid.setColumnStretch(3, 1)
        basics_header = QLabel("Basics / Identity", self.condition_editor_card)
        basics_header.setProperty("sectionCardRole", "subtitle")
        instructions_header = QLabel("Instructions", self.condition_editor_card)
        instructions_header.setProperty("sectionCardRole", "subtitle")
        timing_header = QLabel("Timing / Stimulus", self.condition_editor_card)
        timing_header.setProperty("sectionCardRole", "subtitle")
        template_header = QLabel("Template / Info", self.condition_editor_card)
        template_header.setProperty("sectionCardRole", "subtitle")
        editor_columns = QGridLayout()
        editor_columns.setContentsMargins(0, 0, 0, 0)
        editor_columns.setHorizontalSpacing(PAGE_SECTION_GAP)
        editor_columns.setVerticalSpacing(8)
        editor_columns.addWidget(basics_header, 0, 0)
        editor_columns.addWidget(timing_header, 0, 1)
        editor_columns.addLayout(basic_form, 1, 0)
        editor_columns.addLayout(timing_grid, 1, 1)
        editor_columns.addWidget(instructions_header, 2, 0)
        editor_columns.addWidget(template_header, 2, 1)
        editor_columns.addWidget(self.instructions_edit, 3, 0)
        editor_columns.addWidget(self.template_info_label, 3, 1)
        editor_columns.setColumnStretch(0, 1)
        editor_columns.setColumnStretch(1, 1)
        self.condition_editor_card.body_layout.addLayout(editor_columns)

        self.stimulus_sources_card = SectionCard(
            title="Stimulus Sources & Status",
            subtitle="Base and oddball sources shown side by side for quick comparison.",
            object_name="conditions_stimulus_sources_card",
            parent=self,
        )
        self.stimulus_sources_card.card_layout.setContentsMargins(12, 10, 12, 10)
        self.stimulus_sources_card.card_layout.setSpacing(8)
        self.stimulus_sources_card.body_layout.setSpacing(8)
        base_panel = QWidget(self.stimulus_sources_card)
        base_layout = QFormLayout(base_panel)
        base_layout.setContentsMargins(0, 0, 0, 0)
        base_layout.setHorizontalSpacing(10)
        base_layout.setVerticalSpacing(6)
        base_layout.addRow("Readiness", self.base_source_state)
        base_layout.addRow("Source Folder", self.base_source_value)
        base_layout.addRow("Image Count", self.base_count_value)
        base_layout.addRow("Resolution", self.base_resolution_value)
        base_layout.addRow("Variants", self.base_variants_value)
        base_layout.addRow("", self.base_import_button)

        oddball_panel = QWidget(self.stimulus_sources_card)
        oddball_layout = QFormLayout(oddball_panel)
        oddball_layout.setContentsMargins(0, 0, 0, 0)
        oddball_layout.setHorizontalSpacing(10)
        oddball_layout.setVerticalSpacing(6)
        oddball_layout.addRow("Readiness", self.oddball_source_state)
        oddball_layout.addRow("Source Folder", self.oddball_source_value)
        oddball_layout.addRow("Image Count", self.oddball_count_value)
        oddball_layout.addRow("Resolution", self.oddball_resolution_value)
        oddball_layout.addRow("Variants", self.oddball_variants_value)
        oddball_layout.addRow("", self.oddball_import_button)

        source_columns = QGridLayout()
        source_columns.setContentsMargins(0, 0, 0, 0)
        source_columns.setHorizontalSpacing(PAGE_SECTION_GAP)
        source_columns.setVerticalSpacing(8)
        base_header = QLabel("Base", self.stimulus_sources_card)
        base_header.setProperty("sectionCardRole", "title")
        oddball_header = QLabel("Oddball", self.stimulus_sources_card)
        oddball_header.setProperty("sectionCardRole", "title")
        source_columns.addWidget(base_header, 0, 0)
        source_columns.addWidget(oddball_header, 0, 1)
        source_columns.addWidget(base_panel, 1, 0)
        source_columns.addWidget(oddball_panel, 1, 1)
        source_columns.setColumnStretch(0, 1)
        source_columns.setColumnStretch(1, 1)
        self.stimulus_sources_card.body_layout.addLayout(source_columns)

        self.condition_detail_stack = QWidget(self)
        self.condition_detail_stack.setObjectName("conditions_detail_stack")
        detail_stack_layout = QVBoxLayout(self.condition_detail_stack)
        detail_stack_layout.setContentsMargins(0, 0, 0, 0)
        detail_stack_layout.setSpacing(10)
        detail_stack_layout.addWidget(self.condition_editor_card, 1)
        detail_stack_layout.addWidget(self.stimulus_sources_card)

        self.master_detail_container = QWidget(self)
        self.master_detail_container.setObjectName("conditions_master_detail_container")
        self.master_detail_layout = QHBoxLayout(self.master_detail_container)
        self.master_detail_layout.setContentsMargins(0, 0, 0, 0)
        self.master_detail_layout.setSpacing(12)
        self.master_detail_layout.addWidget(self.condition_list_card, 3)
        self.master_detail_layout.addWidget(self.condition_detail_stack, 7)

        self.shell = NonHomePageShell(
            title="Conditions",
            subtitle=(
                "Edit condition ordering, identity, logic, and stimulus sources in a "
                "dedicated master-detail workspace."
            ),
            layout_mode="single_column",
            width_preset="wide",
            parent=self,
        )
        self.shell.add_content_widget(self.master_detail_container, stretch=1)
        self.shell.set_footer_text(
            "Condition edits update the shared project document used by Setup "
            "Dashboard and Run / Runtime."
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.shell)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def selected_condition_id(self) -> str | None:
        item = self.condition_list.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, str) else None

    def refresh(self) -> None:
        selected_condition_id = self.selected_condition_id()
        with QSignalBlocker(self.condition_list):
            self.condition_list.clear()
            for condition in self._document.ordered_conditions():
                item = QListWidgetItem(condition.name)
                item.setData(Qt.ItemDataRole.UserRole, condition.condition_id)
                self.condition_list.addItem(item)
                if condition.condition_id == selected_condition_id:
                    self.condition_list.setCurrentItem(item)
            if selected_condition_id is None and self.condition_list.count() > 0:
                self.condition_list.setCurrentRow(0)
        self._refresh_editor()

    def _current_condition(self) -> Condition | None:
        condition_id = self.selected_condition_id()
        return self._document.get_condition(condition_id) if condition_id else None

    def _refresh_editor(self, *_args: object) -> None:
        condition = self._current_condition()
        enabled = condition is not None
        widgets = [
            self.condition_name_edit,
            self.instructions_edit,
            self.trigger_code_spin,
            self.sequence_count_spin,
            self.oddball_cycles_spin,
            self.variant_combo,
            self.duty_cycle_combo,
            self.base_import_button,
            self.oddball_import_button,
            self.remove_condition_button,
            self.move_up_button,
            self.move_down_button,
        ]
        for widget in widgets:
            widget.setEnabled(enabled)
        if condition is None:
            self.selected_condition_badge.set_state("pending", "No condition selected")
            self.selected_condition_note.setText("Choose a condition in the list to edit it.")
            with QSignalBlocker(self.condition_name_edit):
                self.condition_name_edit.clear()
            with QSignalBlocker(self.instructions_edit):
                self.instructions_edit.clear()
            self.template_info_label.setText("Add a condition to begin.")
            self.base_source_state.set_state("pending", "Base source not configured")
            self.base_source_value.set_path_text("Not configured", max_length=74)
            self.base_count_value.setText("0")
            self.base_resolution_value.setText("Not imported")
            self.base_variants_value.setText("original")
            self.oddball_source_state.set_state("pending", "Oddball source not configured")
            self.oddball_source_value.set_path_text("Not configured", max_length=74)
            self.oddball_count_value.setText("0")
            self.oddball_resolution_value.setText("Not imported")
            self.oddball_variants_value.setText("original")
            return

        template = get_template(self._document.project.meta.template_id)
        base_set = self._document.get_condition_stimulus_set(condition.condition_id, "base")
        oddball_set = self._document.get_condition_stimulus_set(condition.condition_id, "oddball")
        self.selected_condition_badge.set_state("ready", condition.name)
        self.selected_condition_note.setText(
            f"Condition ID: {condition.condition_id}   |   Trigger code: {condition.trigger_code}"
        )

        with QSignalBlocker(self.condition_name_edit):
            self.condition_name_edit.setText(condition.name)
        _sync_text_editor_contents(self.instructions_edit, condition.instructions)
        with QSignalBlocker(self.trigger_code_spin):
            self.trigger_code_spin.setValue(condition.trigger_code)
        with QSignalBlocker(self.sequence_count_spin):
            self.sequence_count_spin.setValue(condition.sequence_count)
        with QSignalBlocker(self.oddball_cycles_spin):
            self.oddball_cycles_spin.setValue(condition.oddball_cycle_repeats_per_sequence)
        with QSignalBlocker(self.variant_combo):
            self.variant_combo.setCurrentIndex(
                self.variant_combo.findData(condition.stimulus_variant)
            )
        with QSignalBlocker(self.duty_cycle_combo):
            self.duty_cycle_combo.setCurrentIndex(
                self.duty_cycle_combo.findData(condition.duty_cycle_mode)
            )
        self.template_info_label.setText(
            f"{template.display_name}: base {template.base_hz:.1f} Hz, oddball every "
            f"{template.oddball_every_n}th image, oddball {template.oddball_hz:.1f} Hz."
        )
        self.base_source_state.set_state(
            "ready" if base_set.image_count > 0 else "warning",
            "Base source ready" if base_set.image_count > 0 else "Base source needs attention",
        )
        self.base_source_value.set_path_text(base_set.source_dir, max_length=74)
        self.base_count_value.setText(str(base_set.image_count))
        self.base_resolution_value.setText(_resolution_text(base_set.resolution))
        self.base_variants_value.setText(
            ", ".join(item.value for item in base_set.available_variants)
        )
        self.oddball_source_state.set_state(
            "ready" if oddball_set.image_count > 0 else "warning",
            "Oddball source ready"
            if oddball_set.image_count > 0
            else "Oddball source needs attention",
        )
        self.oddball_source_value.set_path_text(oddball_set.source_dir, max_length=74)
        self.oddball_count_value.setText(str(oddball_set.image_count))
        self.oddball_resolution_value.setText(_resolution_text(oddball_set.resolution))
        self.oddball_variants_value.setText(
            ", ".join(item.value for item in oddball_set.available_variants)
        )

    def _add_condition(self) -> None:
        try:
            condition_id = self._document.create_condition()
        except Exception as error:
            _show_error_dialog(self, "Condition Error", error)
            return
        self.refresh()
        for index in range(self.condition_list.count()):
            item = self.condition_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == condition_id:
                self.condition_list.setCurrentItem(item)
                break

    def _remove_condition(self) -> None:
        condition_id = self.selected_condition_id()
        if condition_id is None:
            return
        try:
            self._document.remove_condition(condition_id)
        except Exception as error:
            _show_error_dialog(self, "Condition Error", error)

    def _move_condition(self, offset: int) -> None:
        condition_id = self.selected_condition_id()
        if condition_id is None:
            return
        try:
            self._document.move_condition(condition_id, offset=offset)
        except Exception as error:
            _show_error_dialog(self, "Condition Order Error", error)
            return
        self.refresh()
        for index in range(self.condition_list.count()):
            item = self.condition_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == condition_id:
                self.condition_list.setCurrentItem(item)
                break

    def _apply_name(self) -> None:
        condition_id = self.selected_condition_id()
        if condition_id is None:
            return
        try:
            self._document.update_condition(condition_id, name=self.condition_name_edit.text())
        except Exception as error:
            _show_error_dialog(self, "Condition Error", error)
            self.refresh()

    def _apply_instructions(self) -> None:
        condition_id = self.selected_condition_id()
        if condition_id is None:
            return
        try:
            self._document.update_condition(
                condition_id,
                instructions=self.instructions_edit.toPlainText(),
            )
        except Exception as error:
            _show_error_dialog(self, "Condition Error", error)
            self.refresh()

    def _apply_numeric_fields(self) -> None:
        condition_id = self.selected_condition_id()
        if condition_id is None:
            return
        try:
            self._document.update_condition(
                condition_id,
                trigger_code=self.trigger_code_spin.value(),
                sequence_count=self.sequence_count_spin.value(),
                oddball_cycle_repeats_per_sequence=self.oddball_cycles_spin.value(),
            )
        except Exception as error:
            _show_error_dialog(self, "Condition Error", error)
            self.refresh()

    def _apply_variant_fields(self) -> None:
        condition_id = self.selected_condition_id()
        if condition_id is None:
            return
        try:
            self._document.update_condition(
                condition_id,
                stimulus_variant=self.variant_combo.currentData(),
                duty_cycle_mode=self.duty_cycle_combo.currentData(),
            )
        except Exception as error:
            _show_error_dialog(self, "Condition Error", error)
            self.refresh()

    def _import_stimulus_folder(self, role: str) -> None:
        condition_id = self.selected_condition_id()
        if condition_id is None:
            return
        directory = QFileDialog.getExistingDirectory(
            self,
            f"Choose {role.title()} Stimulus Folder",
            str(Path.home()),
        )
        if not directory:
            return
        try:
            self._document.import_condition_stimulus_folder(
                condition_id,
                role=role,
                source_dir=Path(directory),
            )
        except Exception as error:
            _show_error_dialog(self, "Stimulus Import Error", error)
