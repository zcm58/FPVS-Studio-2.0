"""Main authoring window for the Phase 5 FPVS Studio GUI."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import traceback

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QAction, QCloseEvent, QTextCursor, QTextOption
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from fpvs_studio.core.enums import DutyCycleMode, InterConditionMode, StimulusVariant
from fpvs_studio.core.template_library import get_template
from fpvs_studio.gui.document import ConditionStimulusRow, DocumentError, ProjectDocument

_CYCLE_HELP_TEXT = "Cycle = one turn of base presentations plus one oddball presentation."


def _show_error_dialog(parent: QWidget, title: str, error: Exception) -> None:
    """Show one user-facing error dialog with expandable details."""

    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Critical)
    dialog.setWindowTitle(title)
    dialog.setText(str(error))
    dialog.setDetailedText(
        "".join(traceback.format_exception(type(error), error, error.__traceback__))
    )
    dialog.exec()


def _variant_label(variant: StimulusVariant) -> str:
    return {
        StimulusVariant.ORIGINAL: "Original",
        StimulusVariant.GRAYSCALE: "Grayscale",
        StimulusVariant.ROT180: "Orientation-Inverted (180 deg)",
        StimulusVariant.PHASE_SCRAMBLED: "Fourier Phase-Scrambled",
    }[variant]


def _duty_cycle_label(mode: DutyCycleMode) -> str:
    return {
        DutyCycleMode.CONTINUOUS: "Continuous",
        DutyCycleMode.BLANK_50: "50% Blank",
    }[mode]


def _transition_label(mode: InterConditionMode) -> str:
    return {
        InterConditionMode.FIXED_BREAK: "Fixed Break",
        InterConditionMode.MANUAL_CONTINUE: "Manual Continue",
    }[mode]


def _resolution_text(width_height) -> str:
    if width_height is None:
        return "Not imported"
    return f"{width_height.width_px} x {width_height.height_px}"


def _sync_text_editor_contents(editor: QTextEdit | QPlainTextEdit, text: str) -> None:
    """Update a text editor only when external state actually changed."""

    if editor.toPlainText() == text:
        return

    cursor = editor.textCursor()
    anchor = cursor.anchor()
    position = cursor.position()
    had_focus = editor.hasFocus()

    with QSignalBlocker(editor):
        editor.setPlainText(text)

    if not had_focus:
        return

    restored_cursor = editor.textCursor()
    restored_cursor.setPosition(min(anchor, len(text)))
    move_mode = (
        QTextCursor.MoveMode.KeepAnchor
        if anchor != position
        else QTextCursor.MoveMode.MoveAnchor
    )
    restored_cursor.setPosition(min(position, len(text)), move_mode)
    editor.setTextCursor(restored_cursor)


class LeftToRightPlainTextEdit(QPlainTextEdit):
    """Plain-text editor with left-to-right document defaults."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LeftToRight)
        text_option = self.document().defaultTextOption()
        text_option.setTextDirection(Qt.LeftToRight)
        self.document().setDefaultTextOption(text_option)


class ProjectPage(QWidget):
    """Project metadata and display settings page."""

    def __init__(self, document: ProjectDocument, parent=None) -> None:
        super().__init__(parent)
        self._document = document

        self.project_name_edit = QLineEdit(self)
        self.project_name_edit.setObjectName("project_name_edit")
        self.project_name_edit.editingFinished.connect(self._apply_project_name)

        self.project_description_edit = LeftToRightPlainTextEdit(self)
        self.project_description_edit.setObjectName("project_description_edit")
        self.project_description_edit.setMaximumBlockCount(20)
        self.project_description_edit.textChanged.connect(self._apply_project_description)

        self.project_root_value = QLabel(self)
        self.project_root_value.setObjectName("project_root_value")
        self.project_root_value.setWordWrap(True)
        self.template_value = QLabel(self)
        self.template_value.setObjectName("template_value")
        self.template_value.setWordWrap(True)
        self.background_color_edit = QLineEdit(self)
        self.background_color_edit.setObjectName("background_color_edit")
        self.background_color_edit.editingFinished.connect(self._apply_background_color)

        self.runtime_note = QLabel(
            "Runtime launch currently uses the supported test-mode path. "
            "Launched PsychoPy playback opens fullscreen on the selected display and "
            "shows a manual continue screen between non-final blocks. Broader "
            "production validation remains deferred.",
            self,
        )
        self.runtime_note.setWordWrap(True)

        metadata_group = QGroupBox("Project", self)
        metadata_layout = QFormLayout(metadata_group)
        metadata_layout.addRow("Name", self.project_name_edit)
        metadata_layout.addRow("Description", self.project_description_edit)
        metadata_layout.addRow("Project Root", self.project_root_value)
        metadata_layout.addRow("Template", self.template_value)

        display_group = QGroupBox("Display", self)
        display_layout = QFormLayout(display_group)
        display_layout.addRow("Background Color", self.background_color_edit)
        display_layout.addRow("", self.runtime_note)

        layout = QVBoxLayout(self)
        layout.addWidget(metadata_group)
        layout.addWidget(display_group)
        layout.addStretch(1)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        project = self._document.project
        template = get_template(project.meta.template_id)
        with QSignalBlocker(self.project_name_edit):
            self.project_name_edit.setText(project.meta.name)
        _sync_text_editor_contents(self.project_description_edit, project.meta.description)
        with QSignalBlocker(self.background_color_edit):
            self.background_color_edit.setText(str(project.settings.display.background_color))
        self.project_root_value.setText(str(self._document.project_root))
        self.template_value.setText(f"{template.display_name} ({template.template_id})")

    def _apply_project_name(self) -> None:
        try:
            self._document.update_project_name(self.project_name_edit.text())
        except Exception as error:  # pragma: no cover - exercised via GUI tests
            _show_error_dialog(self, "Project Name Error", error)
            self.refresh()

    def _apply_project_description(self) -> None:
        description = self.project_description_edit.toPlainText()
        if description == self._document.project.meta.description:
            return
        try:
            self._document.update_project_description(description)
        except Exception as error:  # pragma: no cover - exercised via GUI tests
            _show_error_dialog(self, "Project Description Error", error)
            self.refresh()

    def _apply_background_color(self) -> None:
        try:
            self._document.update_display_settings(
                background_color=self.background_color_edit.text().strip()
            )
        except Exception as error:
            _show_error_dialog(self, "Display Settings Error", error)
            self.refresh()


class ConditionsPage(QWidget):
    """Condition list/editor page."""

    def __init__(self, document: ProjectDocument, parent=None) -> None:
        super().__init__(parent)
        self._document = document

        self.condition_list = QListWidget(self)
        self.condition_list.setObjectName("condition_list")
        self.condition_list.currentItemChanged.connect(self._refresh_editor)

        self.add_condition_button = QPushButton("Add", self)
        self.add_condition_button.setObjectName("add_condition_button")
        self.add_condition_button.clicked.connect(self._add_condition)
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

        list_panel = QWidget(self)
        list_panel_layout = QVBoxLayout(list_panel)
        list_panel_layout.addWidget(self.condition_list, 1)
        list_panel_layout.addLayout(list_button_layout)

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

        self.base_source_value = QLabel(self)
        self.base_source_value.setObjectName("base_source_value")
        self.base_source_value.setWordWrap(True)
        self.base_count_value = QLabel(self)
        self.base_count_value.setObjectName("base_count_value")
        self.base_resolution_value = QLabel(self)
        self.base_resolution_value.setObjectName("base_resolution_value")
        self.base_variants_value = QLabel(self)
        self.base_variants_value.setObjectName("base_variants_value")
        self.base_import_button = QPushButton("Import Base Folder...", self)
        self.base_import_button.setObjectName("import_base_folder_button")
        self.base_import_button.clicked.connect(lambda: self._import_stimulus_folder("base"))

        self.oddball_source_value = QLabel(self)
        self.oddball_source_value.setObjectName("oddball_source_value")
        self.oddball_source_value.setWordWrap(True)
        self.oddball_count_value = QLabel(self)
        self.oddball_count_value.setObjectName("oddball_count_value")
        self.oddball_resolution_value = QLabel(self)
        self.oddball_resolution_value.setObjectName("oddball_resolution_value")
        self.oddball_variants_value = QLabel(self)
        self.oddball_variants_value.setObjectName("oddball_variants_value")
        self.oddball_import_button = QPushButton("Import Oddball Folder...", self)
        self.oddball_import_button.setObjectName("import_oddball_folder_button")
        self.oddball_import_button.clicked.connect(lambda: self._import_stimulus_folder("oddball"))

        editor_group = QGroupBox("Condition Editor", self)
        editor_layout = QFormLayout(editor_group)
        editor_layout.addRow("Condition Name", self.condition_name_edit)
        editor_layout.addRow("Instructions", self.instructions_edit)
        editor_layout.addRow("Trigger Code", self.trigger_code_spin)
        editor_layout.addRow("Condition Repeats", self.sequence_count_spin)
        editor_layout.addRow("Cycles / Condition Repeat", self.oddball_cycles_spin)
        editor_layout.addRow("Stimulus Variant", self.variant_combo)
        editor_layout.addRow("Duty Cycle", self.duty_cycle_combo)
        editor_layout.addRow("Template Info", self.template_info_label)

        stimulus_group = QGroupBox("Stimulus Sources", self)
        stimulus_layout = QGridLayout(stimulus_group)
        stimulus_layout.addWidget(QLabel(""), 0, 0)
        stimulus_layout.addWidget(QLabel("Base"), 0, 1)
        stimulus_layout.addWidget(QLabel("Oddball"), 0, 2)
        stimulus_layout.addWidget(QLabel("Source Folder"), 1, 0)
        stimulus_layout.addWidget(self.base_source_value, 1, 1)
        stimulus_layout.addWidget(self.oddball_source_value, 1, 2)
        stimulus_layout.addWidget(QLabel("Image Count"), 2, 0)
        stimulus_layout.addWidget(self.base_count_value, 2, 1)
        stimulus_layout.addWidget(self.oddball_count_value, 2, 2)
        stimulus_layout.addWidget(QLabel("Resolution"), 3, 0)
        stimulus_layout.addWidget(self.base_resolution_value, 3, 1)
        stimulus_layout.addWidget(self.oddball_resolution_value, 3, 2)
        stimulus_layout.addWidget(QLabel("Available Variants"), 4, 0)
        stimulus_layout.addWidget(self.base_variants_value, 4, 1)
        stimulus_layout.addWidget(self.oddball_variants_value, 4, 2)
        stimulus_layout.addWidget(self.base_import_button, 5, 1)
        stimulus_layout.addWidget(self.oddball_import_button, 5, 2)

        editor_panel = QWidget(self)
        editor_panel_layout = QVBoxLayout(editor_panel)
        editor_panel_layout.addWidget(editor_group)
        editor_panel_layout.addWidget(stimulus_group)
        editor_panel_layout.addStretch(1)

        splitter = QSplitter(self)
        splitter.addWidget(list_panel)
        splitter.addWidget(editor_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def selected_condition_id(self) -> str | None:
        item = self.condition_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

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

    def _current_condition(self):
        condition_id = self.selected_condition_id()
        return self._document.get_condition(condition_id) if condition_id else None

    def _refresh_editor(self, *_args) -> None:
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
            with QSignalBlocker(self.condition_name_edit):
                self.condition_name_edit.clear()
            with QSignalBlocker(self.instructions_edit):
                self.instructions_edit.clear()
            self.template_info_label.setText("Add a condition to begin.")
            self.base_source_value.setText("Not configured")
            self.base_count_value.setText("0")
            self.base_resolution_value.setText("Not imported")
            self.base_variants_value.setText("original")
            self.oddball_source_value.setText("Not configured")
            self.oddball_count_value.setText("0")
            self.oddball_resolution_value.setText("Not imported")
            self.oddball_variants_value.setText("original")
            return

        template = get_template(self._document.project.meta.template_id)
        base_set = self._document.get_condition_stimulus_set(condition.condition_id, "base")
        oddball_set = self._document.get_condition_stimulus_set(condition.condition_id, "oddball")

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
            self.variant_combo.setCurrentIndex(self.variant_combo.findData(condition.stimulus_variant))
        with QSignalBlocker(self.duty_cycle_combo):
            self.duty_cycle_combo.setCurrentIndex(
                self.duty_cycle_combo.findData(condition.duty_cycle_mode)
            )
        self.template_info_label.setText(
            f"{template.display_name}: base {template.base_hz:.1f} Hz, oddball every "
            f"{template.oddball_every_n}th image, oddball {template.oddball_hz:.1f} Hz."
        )
        self.base_source_value.setText(base_set.source_dir)
        self.base_count_value.setText(str(base_set.image_count))
        self.base_resolution_value.setText(_resolution_text(base_set.resolution))
        self.base_variants_value.setText(", ".join(item.value for item in base_set.available_variants))
        self.oddball_source_value.setText(oddball_set.source_dir)
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


class SessionFixationPage(QWidget):
    """Combined session and fixation settings page."""

    def __init__(self, document: ProjectDocument, parent=None) -> None:
        super().__init__(parent)
        self._document = document

        self.block_count_spin = QSpinBox(self)
        self.block_count_spin.setObjectName("block_count_spin")
        self.block_count_spin.setRange(1, 1000)
        self.block_count_spin.valueChanged.connect(self._apply_session_settings)

        self.session_seed_spin = QSpinBox(self)
        self.session_seed_spin.setObjectName("session_seed_spin")
        self.session_seed_spin.setRange(0, 2_147_483_647)
        self.session_seed_spin.valueChanged.connect(self._apply_session_settings)
        self.generate_seed_button = QPushButton("Generate New Seed", self)
        self.generate_seed_button.setObjectName("generate_seed_button")
        self.generate_seed_button.clicked.connect(self._generate_seed)

        self.randomize_checkbox = QCheckBox("Randomize conditions within each block", self)
        self.randomize_checkbox.setObjectName("randomize_conditions_checkbox")
        self.randomize_checkbox.stateChanged.connect(self._apply_session_settings)

        self.inter_condition_mode_combo = QComboBox(self)
        self.inter_condition_mode_combo.setObjectName("inter_condition_mode_combo")
        for mode in InterConditionMode:
            self.inter_condition_mode_combo.addItem(_transition_label(mode), userData=mode)
        self.inter_condition_mode_combo.currentIndexChanged.connect(self._apply_session_settings)

        self.break_seconds_spin = QDoubleSpinBox(self)
        self.break_seconds_spin.setObjectName("inter_condition_break_seconds_spin")
        self.break_seconds_spin.setRange(0.0, 3600.0)
        self.break_seconds_spin.setDecimals(1)
        self.break_seconds_spin.valueChanged.connect(self._apply_session_settings)

        self.continue_key_edit = QLineEdit(self)
        self.continue_key_edit.setObjectName("continue_key_edit")
        self.continue_key_edit.editingFinished.connect(self._apply_session_settings)

        self.fixation_enabled_checkbox = QCheckBox("Enable fixation color changes per condition", self)
        self.fixation_enabled_checkbox.setObjectName("fixation_enabled_checkbox")
        self.fixation_enabled_checkbox.stateChanged.connect(self._apply_fixation_settings)

        self.fixation_accuracy_checkbox = QCheckBox(
            "Enable fixation accuracy task (Space within 1.0 s)",
            self,
        )
        self.fixation_accuracy_checkbox.setObjectName("fixation_accuracy_checkbox")
        self.fixation_accuracy_checkbox.stateChanged.connect(self._on_fixation_accuracy_toggled)

        self.target_count_mode_combo = QComboBox(self)
        self.target_count_mode_combo.setObjectName("target_count_mode_combo")
        self.target_count_mode_combo.addItem("Fixed per condition", userData="fixed")
        self.target_count_mode_combo.addItem("Randomized per condition run", userData="randomized")
        self.target_count_mode_combo.currentIndexChanged.connect(self._on_target_count_mode_changed)

        self.changes_per_sequence_spin = QSpinBox(self)
        self.changes_per_sequence_spin.setObjectName("changes_per_sequence_spin")
        self.changes_per_sequence_spin.setRange(0, 1000)
        self.changes_per_sequence_spin.valueChanged.connect(self._apply_fixation_settings)

        self.target_count_min_spin = QSpinBox(self)
        self.target_count_min_spin.setObjectName("target_count_min_spin")
        self.target_count_min_spin.setRange(0, 1000)
        self.target_count_min_spin.valueChanged.connect(self._apply_fixation_settings)

        self.target_count_max_spin = QSpinBox(self)
        self.target_count_max_spin.setObjectName("target_count_max_spin")
        self.target_count_max_spin.setRange(0, 1000)
        self.target_count_max_spin.valueChanged.connect(self._apply_fixation_settings)

        self.no_repeat_count_checkbox = QCheckBox(
            "No immediate repeat between consecutive condition runs",
            self,
        )
        self.no_repeat_count_checkbox.setObjectName("no_immediate_repeat_count_checkbox")
        self.no_repeat_count_checkbox.stateChanged.connect(self._apply_fixation_settings)

        self.target_duration_spin = QSpinBox(self)
        self.target_duration_spin.setObjectName("target_duration_spin")
        self.target_duration_spin.setRange(0, 10000)
        self.target_duration_spin.valueChanged.connect(self._apply_fixation_settings)

        self.min_gap_spin = QSpinBox(self)
        self.min_gap_spin.setObjectName("min_gap_spin")
        self.min_gap_spin.setRange(0, 10000)
        self.min_gap_spin.valueChanged.connect(self._apply_fixation_settings)

        self.max_gap_spin = QSpinBox(self)
        self.max_gap_spin.setObjectName("max_gap_spin")
        self.max_gap_spin.setRange(0, 10000)
        self.max_gap_spin.valueChanged.connect(self._apply_fixation_settings)

        self.base_color_edit = QLineEdit(self)
        self.base_color_edit.setObjectName("fixation_base_color_edit")
        self.base_color_edit.editingFinished.connect(self._apply_fixation_settings)

        self.target_color_edit = QLineEdit(self)
        self.target_color_edit.setObjectName("fixation_target_color_edit")
        self.target_color_edit.editingFinished.connect(self._apply_fixation_settings)

        self.response_key_edit = QLineEdit(self)
        self.response_key_edit.setObjectName("response_key_edit")
        self.response_key_edit.editingFinished.connect(self._apply_fixation_settings)

        self.response_window_spin = QDoubleSpinBox(self)
        self.response_window_spin.setObjectName("response_window_seconds_spin")
        self.response_window_spin.setRange(0.1, 10.0)
        self.response_window_spin.setDecimals(2)
        self.response_window_spin.setSingleStep(0.1)
        self.response_window_spin.valueChanged.connect(self._apply_fixation_settings)

        self.cross_size_spin = QSpinBox(self)
        self.cross_size_spin.setObjectName("cross_size_spin")
        self.cross_size_spin.setRange(1, 1000)
        self.cross_size_spin.valueChanged.connect(self._apply_fixation_settings)

        self.line_width_spin = QSpinBox(self)
        self.line_width_spin.setObjectName("line_width_spin")
        self.line_width_spin.setRange(1, 1000)
        self.line_width_spin.valueChanged.connect(self._apply_fixation_settings)

        self.cycle_help_label = QLabel(_CYCLE_HELP_TEXT, self)
        self.cycle_help_label.setObjectName("cycle_help_label")
        self.cycle_help_label.setWordWrap(True)

        self.fixation_guidance_text = QPlainTextEdit(self)
        self.fixation_guidance_text.setObjectName("fixation_condition_guidance_text")
        self.fixation_guidance_text.setReadOnly(True)
        self.fixation_guidance_text.setMaximumBlockCount(200)

        session_group = QGroupBox("Session Settings", self)
        session_layout = QFormLayout(session_group)
        seed_layout = QHBoxLayout()
        seed_layout.addWidget(self.session_seed_spin, 1)
        seed_layout.addWidget(self.generate_seed_button)
        session_layout.addRow("Block Count", self.block_count_spin)
        session_layout.addRow("Session Seed", seed_layout)
        session_layout.addRow("", self.randomize_checkbox)
        session_layout.addRow("Inter-Condition Mode", self.inter_condition_mode_combo)
        session_layout.addRow("Break Seconds", self.break_seconds_spin)
        session_layout.addRow("Continue Key", self.continue_key_edit)

        fixation_group = QGroupBox("Fixation Task", self)
        fixation_layout = QFormLayout(fixation_group)
        fixation_layout.addRow("", self.fixation_enabled_checkbox)
        fixation_layout.addRow("", self.fixation_accuracy_checkbox)
        fixation_layout.addRow("Color Changes / Condition Mode", self.target_count_mode_combo)
        fixation_layout.addRow(
            "Color Changes / Condition (fixed target count)",
            self.changes_per_sequence_spin,
        )
        fixation_layout.addRow(
            "Color Changes Min / Condition (target count)",
            self.target_count_min_spin,
        )
        fixation_layout.addRow(
            "Color Changes Max / Condition (target count)",
            self.target_count_max_spin,
        )
        fixation_layout.addRow("", self.no_repeat_count_checkbox)
        fixation_layout.addRow("Color Change Duration (target) (ms)", self.target_duration_spin)
        fixation_layout.addRow("Min Gap (ms)", self.min_gap_spin)
        fixation_layout.addRow("Max Gap (ms)", self.max_gap_spin)
        fixation_layout.addRow("Default Color", self.base_color_edit)
        fixation_layout.addRow("Change Color (target)", self.target_color_edit)
        fixation_layout.addRow("Response Key", self.response_key_edit)
        fixation_layout.addRow("Response Window (s)", self.response_window_spin)
        fixation_layout.addRow("Cross Size (px)", self.cross_size_spin)
        fixation_layout.addRow("Line Width (px)", self.line_width_spin)

        guidance_group = QGroupBox("Condition Guidance", self)
        guidance_layout = QVBoxLayout(guidance_group)
        guidance_layout.addWidget(self.cycle_help_label)
        guidance_layout.addWidget(self.fixation_guidance_text)

        layout = QVBoxLayout(self)
        layout.addWidget(session_group)
        layout.addWidget(fixation_group)
        layout.addWidget(guidance_group)
        layout.addStretch(1)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        session = self._document.project.settings.session
        fixation = self._document.project.settings.fixation_task
        with QSignalBlocker(self.block_count_spin):
            self.block_count_spin.setValue(session.block_count)
        with QSignalBlocker(self.session_seed_spin):
            self.session_seed_spin.setValue(session.session_seed)
        with QSignalBlocker(self.randomize_checkbox):
            self.randomize_checkbox.setChecked(session.randomize_conditions_per_block)
        with QSignalBlocker(self.inter_condition_mode_combo):
            self.inter_condition_mode_combo.setCurrentIndex(
                self.inter_condition_mode_combo.findData(session.inter_condition_mode)
            )
        with QSignalBlocker(self.break_seconds_spin):
            self.break_seconds_spin.setValue(session.inter_condition_break_seconds)
        with QSignalBlocker(self.continue_key_edit):
            self.continue_key_edit.setText(session.continue_key)

        with QSignalBlocker(self.fixation_enabled_checkbox):
            self.fixation_enabled_checkbox.setChecked(fixation.enabled)
        with QSignalBlocker(self.fixation_accuracy_checkbox):
            self.fixation_accuracy_checkbox.setChecked(fixation.accuracy_task_enabled)
        with QSignalBlocker(self.target_count_mode_combo):
            self.target_count_mode_combo.setCurrentIndex(
                self.target_count_mode_combo.findData(fixation.target_count_mode)
            )
        with QSignalBlocker(self.changes_per_sequence_spin):
            self.changes_per_sequence_spin.setValue(fixation.changes_per_sequence)
        with QSignalBlocker(self.target_count_min_spin):
            self.target_count_min_spin.setValue(fixation.target_count_min)
        with QSignalBlocker(self.target_count_max_spin):
            self.target_count_max_spin.setValue(fixation.target_count_max)
        with QSignalBlocker(self.no_repeat_count_checkbox):
            self.no_repeat_count_checkbox.setChecked(fixation.no_immediate_repeat_count)
        with QSignalBlocker(self.target_duration_spin):
            self.target_duration_spin.setValue(fixation.target_duration_ms)
        with QSignalBlocker(self.min_gap_spin):
            self.min_gap_spin.setValue(fixation.min_gap_ms)
        with QSignalBlocker(self.max_gap_spin):
            self.max_gap_spin.setValue(fixation.max_gap_ms)
        with QSignalBlocker(self.base_color_edit):
            self.base_color_edit.setText(str(fixation.base_color))
        with QSignalBlocker(self.target_color_edit):
            self.target_color_edit.setText(str(fixation.target_color))
        with QSignalBlocker(self.response_key_edit):
            self.response_key_edit.setText(fixation.response_key)
        with QSignalBlocker(self.response_window_spin):
            self.response_window_spin.setValue(fixation.response_window_seconds)
        with QSignalBlocker(self.cross_size_spin):
            self.cross_size_spin.setValue(fixation.cross_size_px)
        with QSignalBlocker(self.line_width_spin):
            self.line_width_spin.setValue(fixation.line_width_px)
        self._update_transition_state()
        self._update_fixation_target_count_state()
        self._update_fixation_accuracy_state()
        self._refresh_condition_guidance()

    def _update_transition_state(self) -> None:
        mode = self.inter_condition_mode_combo.currentData()
        self.break_seconds_spin.setEnabled(mode == InterConditionMode.FIXED_BREAK)
        self.continue_key_edit.setEnabled(mode == InterConditionMode.MANUAL_CONTINUE)

    def _update_fixation_target_count_state(self) -> None:
        randomized_mode = self.target_count_mode_combo.currentData() == "randomized"
        self.changes_per_sequence_spin.setEnabled(not randomized_mode)
        self.target_count_min_spin.setEnabled(randomized_mode)
        self.target_count_max_spin.setEnabled(randomized_mode)
        self.no_repeat_count_checkbox.setEnabled(randomized_mode)

    def _update_fixation_accuracy_state(self) -> None:
        accuracy_enabled = self.fixation_accuracy_checkbox.isChecked()
        self.response_key_edit.setEnabled(accuracy_enabled)
        self.response_window_spin.setEnabled(accuracy_enabled)

    def _refresh_condition_guidance(self) -> None:
        refresh_hz = self._document.project.settings.display.preferred_refresh_hz or 60.0
        try:
            guidance_rows = self._document.fixation_guidance(refresh_hz=refresh_hz)
        except Exception as error:
            self.fixation_guidance_text.setPlainText(
                f"Condition guidance unavailable at {refresh_hz:.2f} Hz: {error}"
            )
            return
        if not guidance_rows:
            self.fixation_guidance_text.setPlainText(
                "Add a condition to preview condition duration and estimated max feasible "
                "color changes per condition."
            )
            return
        lines = [
            f"Refresh: {refresh_hz:.2f} Hz",
            "Color changes are distributed across each full condition duration.",
            "",
        ]
        for row in guidance_rows:
            lines.append(
                f"{row.condition_name}: {row.condition_duration_seconds:.2f} s "
                f"({row.total_frames} frames, {row.total_cycles} cycle(s)); "
                "estimated max feasible color changes per condition: "
                f"{row.estimated_max_color_changes_per_condition}"
            )
        self.fixation_guidance_text.setPlainText("\n".join(lines))

    def _apply_session_settings(self) -> None:
        try:
            self._document.update_session_settings(
                block_count=self.block_count_spin.value(),
                session_seed=self.session_seed_spin.value(),
                randomize_conditions_per_block=self.randomize_checkbox.isChecked(),
                inter_condition_mode=self.inter_condition_mode_combo.currentData(),
                inter_condition_break_seconds=self.break_seconds_spin.value(),
                continue_key=self.continue_key_edit.text().strip(),
            )
        except Exception as error:
            _show_error_dialog(self, "Session Settings Error", error)
            self.refresh()
            return
        self._update_transition_state()

    def _generate_seed(self) -> None:
        try:
            self._document.generate_new_session_seed()
        except Exception as error:
            _show_error_dialog(self, "Session Seed Error", error)

    def _on_target_count_mode_changed(self) -> None:
        self._update_fixation_target_count_state()
        self._apply_fixation_settings()

    def _on_fixation_accuracy_toggled(self) -> None:
        self._update_fixation_accuracy_state()
        self._apply_fixation_settings()

    def _apply_fixation_settings(self) -> None:
        try:
            response_key = self.response_key_edit.text().strip().lower() or "space"
            self._document.update_fixation_settings(
                enabled=self.fixation_enabled_checkbox.isChecked(),
                accuracy_task_enabled=self.fixation_accuracy_checkbox.isChecked(),
                target_count_mode=self.target_count_mode_combo.currentData(),
                changes_per_sequence=self.changes_per_sequence_spin.value(),
                target_count_min=self.target_count_min_spin.value(),
                target_count_max=self.target_count_max_spin.value(),
                no_immediate_repeat_count=self.no_repeat_count_checkbox.isChecked(),
                target_duration_ms=self.target_duration_spin.value(),
                min_gap_ms=self.min_gap_spin.value(),
                max_gap_ms=self.max_gap_spin.value(),
                base_color=self.base_color_edit.text().strip(),
                target_color=self.target_color_edit.text().strip(),
                response_key=response_key,
                response_window_seconds=self.response_window_spin.value(),
                response_keys=[response_key],
                cross_size_px=self.cross_size_spin.value(),
                line_width_px=self.line_width_spin.value(),
            )
        except Exception as error:
            _show_error_dialog(self, "Fixation Settings Error", error)
            self.refresh()


class AssetsPage(QWidget):
    """Preprocessing/materialization page."""

    def __init__(self, document: ProjectDocument, parent=None) -> None:
        super().__init__(parent)
        self._document = document
        self._variant_checkboxes: dict[StimulusVariant, QCheckBox] = {}

        supported_variants_group = QGroupBox("Project Materialization Variants", self)
        supported_variants_layout = QHBoxLayout(supported_variants_group)
        for variant in StimulusVariant:
            checkbox = QCheckBox(_variant_label(variant), supported_variants_group)
            checkbox.setObjectName(f"variant_checkbox_{variant.value}")
            checkbox.stateChanged.connect(self._apply_supported_variants)
            if variant == StimulusVariant.ORIGINAL:
                checkbox.setEnabled(False)
                checkbox.setChecked(True)
            self._variant_checkboxes[variant] = checkbox
            supported_variants_layout.addWidget(checkbox)

        self.import_source_button = QPushButton("Import Source Folder...", self)
        self.import_source_button.setObjectName("assets_import_source_button")
        self.import_source_button.clicked.connect(self._import_selected_source)
        self.refresh_button = QPushButton("Refresh Inspection", self)
        self.refresh_button.setObjectName("assets_refresh_button")
        self.refresh_button.clicked.connect(self._refresh_inspection)
        self.materialize_button = QPushButton("Materialize Supported Variants", self)
        self.materialize_button.setObjectName("materialize_assets_button")
        self.materialize_button.clicked.connect(self._materialize_assets)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.import_source_button)
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.materialize_button)

        self.assets_table = QTableWidget(0, 6, self)
        self.assets_table.setObjectName("assets_table")
        self.assets_table.setHorizontalHeaderLabels(
            ["Condition", "Role", "Source Dir", "Images", "Resolution", "Variants"]
        )
        self.assets_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.assets_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.assets_table.itemSelectionChanged.connect(self._update_buttons)
        self.assets_table.horizontalHeader().setStretchLastSection(True)

        self.assets_status_text = QPlainTextEdit(self)
        self.assets_status_text.setObjectName("assets_status_text")
        self.assets_status_text.setReadOnly(True)
        self.assets_status_text.setMaximumBlockCount(200)

        layout = QVBoxLayout(self)
        layout.addWidget(supported_variants_group)
        layout.addLayout(button_layout)
        layout.addWidget(self.assets_table, 1)
        layout.addWidget(self.assets_status_text)

        self._document.project_changed.connect(self.refresh)
        self._document.manifest_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        supported_variants = set(self._document.project.settings.supported_variants)
        for variant, checkbox in self._variant_checkboxes.items():
            with QSignalBlocker(checkbox):
                checkbox.setChecked(variant in supported_variants)

        rows = self._document.condition_rows()
        with QSignalBlocker(self.assets_table):
            self.assets_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                self._set_table_item(row_index, 0, row.condition_name)
                self._set_table_item(row_index, 1, row.role)
                source_item = self._set_table_item(row_index, 2, row.stimulus_set.source_dir)
                source_item.setData(
                    Qt.ItemDataRole.UserRole,
                    (row.condition_id, row.role),
                )
                self._set_table_item(row_index, 3, str(row.stimulus_set.image_count))
                self._set_table_item(row_index, 4, _resolution_text(row.stimulus_set.resolution))
                self._set_table_item(
                    row_index,
                    5,
                    ", ".join(item.value for item in row.stimulus_set.available_variants),
                )
        self.assets_table.resizeColumnsToContents()
        self.assets_status_text.setPlainText(self._build_status_text(rows))
        self._update_buttons()

    def _set_table_item(self, row: int, column: int, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
        self.assets_table.setItem(row, column, item)
        return item

    def _build_status_text(self, rows: list[ConditionStimulusRow]) -> str:
        manifest = self._document.manifest
        lines = [
            f"Condition stimulus rows: {len(rows)}",
            f"Project-supported variants: {', '.join(item.value for item in self._document.project.settings.supported_variants)}",
        ]
        if manifest is None:
            lines.append("Manifest status: no manifest loaded yet.")
        else:
            lines.append(
                f"Manifest status: {len(manifest.sets)} stimulus set(s), generated {manifest.generated_at.isoformat()}."
            )
        validation = self._document.validation_report(
            refresh_hz=self._document.project.settings.display.preferred_refresh_hz or 60.0
        )
        if validation.issues:
            lines.append("")
            lines.append("Validation issues:")
            lines.extend(f"- {issue.message}" for issue in validation.issues)
        return "\n".join(lines)

    def _selected_binding(self) -> tuple[str, str] | None:
        selected_items = self.assets_table.selectedItems()
        if not selected_items:
            return None
        return self.assets_table.item(selected_items[0].row(), 2).data(Qt.ItemDataRole.UserRole)

    def _update_buttons(self) -> None:
        self.import_source_button.setEnabled(self._selected_binding() is not None)

    def _apply_supported_variants(self) -> None:
        variants = [
            variant
            for variant, checkbox in self._variant_checkboxes.items()
            if checkbox.isChecked()
        ]
        try:
            self._document.set_supported_variants(variants)
        except Exception as error:
            _show_error_dialog(self, "Supported Variants Error", error)
            self.refresh()

    def _import_selected_source(self) -> None:
        binding = self._selected_binding()
        if binding is None:
            return
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose Source Folder",
            str(Path.home()),
        )
        if not directory:
            return
        condition_id, role = binding
        try:
            self._document.import_condition_stimulus_folder(
                condition_id,
                role=role,
                source_dir=Path(directory),
            )
        except Exception as error:
            _show_error_dialog(self, "Stimulus Import Error", error)

    def _refresh_inspection(self) -> None:
        try:
            self._run_with_progress("Refreshing source inspection...", self._document.refresh_stimulus_inspection)
        except Exception as error:
            _show_error_dialog(self, "Inspection Error", error)

    def _materialize_assets(self) -> None:
        try:
            self._run_with_progress("Materializing project assets...", self._document.materialize_assets)
        except Exception as error:
            _show_error_dialog(self, "Materialization Error", error)

    def _run_with_progress(self, label: str, callback: Callable[[], object]) -> None:
        dialog = QProgressDialog(label, "", 0, 0, self)
        dialog.setCancelButton(None)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.show()
        QApplication.processEvents()
        try:
            callback()
        finally:
            dialog.close()


class RunPage(QWidget):
    """Session compile, preflight, and launch page."""

    def __init__(self, document: ProjectDocument, parent=None) -> None:
        super().__init__(parent)
        self._document = document

        self.refresh_hz_spin = QDoubleSpinBox(self)
        self.refresh_hz_spin.setObjectName("refresh_hz_spin")
        self.refresh_hz_spin.setRange(1.0, 500.0)
        self.refresh_hz_spin.setDecimals(2)
        self.refresh_hz_spin.valueChanged.connect(self._apply_refresh_hz)

        self.display_index_edit = QLineEdit(self)
        self.display_index_edit.setObjectName("display_index_edit")
        self.display_index_edit.setPlaceholderText("Leave blank for default display")

        self.engine_name_value = QLabel("psychopy", self)
        self.engine_name_value.setObjectName("engine_name_value")

        self.serial_port_edit = QLineEdit(self)
        self.serial_port_edit.setObjectName("serial_port_edit")
        self.serial_port_edit.setPlaceholderText("COM3")
        self.serial_port_edit.editingFinished.connect(self._apply_serial_settings)

        self.serial_baudrate_spin = QSpinBox(self)
        self.serial_baudrate_spin.setObjectName("serial_baudrate_spin")
        self.serial_baudrate_spin.setRange(1, 2_000_000)
        self.serial_baudrate_spin.valueChanged.connect(self._apply_serial_settings)

        self.test_mode_checkbox = QCheckBox("Launch the currently supported test-mode path", self)
        self.test_mode_checkbox.setObjectName("test_mode_checkbox")
        self.test_mode_checkbox.setChecked(True)
        self.test_mode_checkbox.setEnabled(False)
        self.fullscreen_checkbox = QCheckBox("Present launched playback fullscreen", self)
        self.fullscreen_checkbox.setObjectName("fullscreen_checkbox")
        self.fullscreen_checkbox.setChecked(True)

        self.compile_button = QPushButton("Compile Session", self)
        self.compile_button.setObjectName("compile_session_button")
        self.compile_button.clicked.connect(self.compile_session)
        self.preflight_button = QPushButton("Preflight", self)
        self.preflight_button.setObjectName("preflight_button")
        self.preflight_button.clicked.connect(self.preflight_session)
        self.launch_button = QPushButton("Launch Test Session", self)
        self.launch_button.setObjectName("launch_test_session_button")
        self.launch_button.clicked.connect(self.launch_test_session)

        self.summary_text = QPlainTextEdit(self)
        self.summary_text.setObjectName("session_summary_text")
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumBlockCount(500)

        runtime_group = QGroupBox("Runtime Settings", self)
        runtime_layout = QFormLayout(runtime_group)
        runtime_layout.addRow("Refresh (Hz)", self.refresh_hz_spin)
        runtime_layout.addRow("Display Index", self.display_index_edit)
        runtime_layout.addRow("Engine", self.engine_name_value)
        runtime_layout.addRow("Serial Port", self.serial_port_edit)
        runtime_layout.addRow("Serial Baud Rate", self.serial_baudrate_spin)
        runtime_layout.addRow("", self.test_mode_checkbox)
        runtime_layout.addRow("", self.fullscreen_checkbox)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.compile_button)
        button_layout.addWidget(self.preflight_button)
        button_layout.addWidget(self.launch_button)

        layout = QVBoxLayout(self)
        layout.addWidget(runtime_group)
        layout.addLayout(button_layout)
        layout.addWidget(self.summary_text, 1)

        self._document.project_changed.connect(self.refresh)
        self._document.session_plan_changed.connect(self._refresh_summary)
        self.refresh()

    def current_refresh_hz(self) -> float:
        return self.refresh_hz_spin.value()

    def current_display_index(self) -> int | None:
        raw_value = self.display_index_edit.text().strip()
        if not raw_value:
            return None
        try:
            display_index = int(raw_value)
        except ValueError as exc:
            raise DocumentError("Display index must be blank or a non-negative integer.") from exc
        if display_index < 0:
            raise DocumentError("Display index must be blank or a non-negative integer.")
        return display_index

    def refresh(self) -> None:
        preferred_refresh = self._document.project.settings.display.preferred_refresh_hz or 60.0
        with QSignalBlocker(self.refresh_hz_spin):
            self.refresh_hz_spin.setValue(preferred_refresh)
        with QSignalBlocker(self.serial_port_edit):
            self.serial_port_edit.setText(self._document.project.settings.triggers.serial_port or "")
        with QSignalBlocker(self.serial_baudrate_spin):
            self.serial_baudrate_spin.setValue(self._document.project.settings.triggers.baudrate)
        self._refresh_summary()

    def compile_session(self) -> None:
        try:
            session_plan = self._document.compile_session(refresh_hz=self.current_refresh_hz())
        except Exception as error:
            _show_error_dialog(self, "Compile Error", error)
            return
        self._set_summary(
            session_plan,
            extra_lines=["Status: session compiled successfully."],
        )

    def preflight_session(self) -> None:
        try:
            session_plan = self._document.preflight_session(refresh_hz=self.current_refresh_hz())
        except Exception as error:
            _show_error_dialog(self, "Preflight Error", error)
            return
        self._set_summary(
            session_plan,
            extra_lines=["Status: preflight passed for the current test-mode launch path."],
        )
        QMessageBox.information(
            self,
            "Preflight Passed",
            "Preflight succeeded for the current test-mode session launch.",
        )

    def launch_test_session(self) -> None:
        try:
            session_plan, summary = self._document.launch_test_session(
                refresh_hz=self.current_refresh_hz(),
                display_index=self.current_display_index(),
                fullscreen=self.fullscreen_checkbox.isChecked(),
            )
        except Exception as error:
            _show_error_dialog(self, "Launch Error", error)
            return
        extra_lines = [
            "Status: runtime launch completed.",
            f"Output Dir: {summary.output_dir or 'runs/...'}",
        ]
        self._set_summary(session_plan, extra_lines=extra_lines)
        QMessageBox.information(
            self,
            "Launch Complete",
            "The test session finished. Review the run exports in the project runs folder.",
        )

    def _apply_refresh_hz(self) -> None:
        try:
            self._document.update_display_settings(preferred_refresh_hz=self.refresh_hz_spin.value())
        except Exception as error:
            _show_error_dialog(self, "Refresh Setting Error", error)
            self.refresh()

    def _apply_serial_settings(self) -> None:
        serial_port = self.serial_port_edit.text().strip() or None
        try:
            self._document.update_trigger_settings(
                serial_port=serial_port,
                baudrate=self.serial_baudrate_spin.value(),
            )
        except Exception as error:
            _show_error_dialog(self, "Serial Settings Error", error)
            self.refresh()

    def _refresh_summary(self) -> None:
        session_plan = self._document.last_session_plan
        if session_plan is None:
            validation = self._document.validation_report(refresh_hz=self.current_refresh_hz())
            if validation.issues:
                self.summary_text.setPlainText(
                    "\n".join(f"- {issue.message}" for issue in validation.issues)
                )
            else:
                self.summary_text.setPlainText(
                    "Compile the session to preview block order, seed, and run count."
                )
            return
        self._set_summary(session_plan)

    def _set_summary(self, session_plan, *, extra_lines: list[str] | None = None) -> None:
        lines = [
            f"Session ID: {session_plan.session_id}",
            f"Session Seed: {session_plan.random_seed}",
            f"Block Count: {session_plan.block_count}",
            f"Run Count: {session_plan.total_runs}",
            f"Refresh (Hz): {session_plan.refresh_hz:.2f}",
            f"Transition Mode: {session_plan.transition.mode.value}",
        ]
        if session_plan.transition.break_seconds is not None:
            lines.append(f"Break Seconds: {session_plan.transition.break_seconds}")
        if session_plan.transition.continue_key is not None:
            lines.append(f"Continue Key: {session_plan.transition.continue_key}")
        lines.append("")
        for block in session_plan.blocks:
            lines.append(
                f"Block {block.block_index + 1}: " + " -> ".join(block.condition_order)
            )
        if extra_lines:
            lines.extend(["", *extra_lines])
        self.summary_text.setPlainText("\n".join(lines))


class StudioMainWindow(QMainWindow):
    """Main window hosting the Phase 5 authoring tabs."""

    def __init__(
        self,
        *,
        document: ProjectDocument,
        on_request_new_project: Callable[[], None],
        on_request_open_project: Callable[[], None],
    ) -> None:
        super().__init__()
        self.document = document
        self._on_request_new_project = on_request_new_project
        self._on_request_open_project = on_request_open_project
        self.setWindowTitle("FPVS Studio")
        self.resize(1200, 860)

        self.project_page = ProjectPage(document, self)
        self.conditions_page = ConditionsPage(document, self)
        self.session_fixation_page = SessionFixationPage(document, self)
        self.assets_page = AssetsPage(document, self)
        self.run_page = RunPage(document, self)

        self.main_tabs = QTabWidget(self)
        self.main_tabs.setObjectName("main_tabs")
        self.main_tabs.addTab(self.project_page, "Project")
        self.main_tabs.addTab(self.conditions_page, "Conditions")
        self.main_tabs.addTab(self.session_fixation_page, "Fixation & Session")
        self.main_tabs.addTab(self.assets_page, "Assets / Preprocessing")
        self.main_tabs.addTab(self.run_page, "Run / Runtime")
        self.setCentralWidget(self.main_tabs)

        self.setStatusBar(QStatusBar(self))
        self._create_actions()
        self._create_menu_and_toolbar()
        self._wire_document()
        self._update_window_title()

    def _wire_document(self) -> None:
        self.document.project_changed.connect(self._update_window_title)
        self.document.dirty_changed.connect(self._update_window_title)
        self.document.saved.connect(lambda: self.statusBar().showMessage("Project saved.", 3000))

    def _create_actions(self) -> None:
        self.new_project_action = QAction("Create New Project", self)
        self.new_project_action.triggered.connect(self._request_new_project)
        self.open_project_action = QAction("Open Project...", self)
        self.open_project_action.triggered.connect(self._request_open_project)
        self.save_project_action = QAction("Save", self)
        self.save_project_action.triggered.connect(self.save_project)
        self.preflight_action = QAction("Preflight", self)
        self.preflight_action.triggered.connect(self.run_page.preflight_session)
        self.launch_action = QAction("Launch Test Session", self)
        self.launch_action.triggered.connect(self.run_page.launch_test_session)

    def _create_menu_and_toolbar(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.new_project_action)
        file_menu.addAction(self.open_project_action)
        file_menu.addAction(self.save_project_action)

        run_menu = self.menuBar().addMenu("Run")
        run_menu.addAction(self.preflight_action)
        run_menu.addAction(self.launch_action)

        toolbar = self.addToolBar("Main")
        toolbar.addAction(self.new_project_action)
        toolbar.addAction(self.open_project_action)
        toolbar.addAction(self.save_project_action)
        toolbar.addSeparator()
        toolbar.addAction(self.preflight_action)
        toolbar.addAction(self.launch_action)

    def save_project(self) -> bool:
        try:
            self.document.save()
        except Exception as error:
            _show_error_dialog(self, "Save Error", error)
            return False
        return True

    def maybe_save_changes(self) -> bool:
        if not self.document.dirty:
            return True
        result = QMessageBox.question(
            self,
            "Unsaved Changes",
            "Save changes to the current project before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if result == QMessageBox.StandardButton.Save:
            return self.save_project()
        if result == QMessageBox.StandardButton.Cancel:
            return False
        return True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.maybe_save_changes():
            event.accept()
        else:
            event.ignore()

    def _request_new_project(self) -> None:
        if self.maybe_save_changes():
            self._on_request_new_project()

    def _request_open_project(self) -> None:
        if self.maybe_save_changes():
            self._on_request_open_project()

    def _update_window_title(self, *_args) -> None:
        dirty_prefix = "*" if self.document.dirty else ""
        self.setWindowTitle(
            f"{dirty_prefix}{self.document.project.meta.name} - FPVS Studio"
        )
