"""Simplified condition setup surface for the Setup Wizard."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.models import Condition, StimulusSet
from fpvs_studio.core.template_library import get_template
from fpvs_studio.gui.components import (
    PAGE_SECTION_GAP,
    SetupChecklistPanel,
    SetupSidePanel,
    SetupSourceCard,
    SetupWorkspaceFrame,
    StatusBadgeLabel,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import (
    _resolution_text,
    _show_error_dialog,
    _sync_text_editor_contents,
    _variant_label,
)

_DEFAULT_CONDITION_NAME_RE = re.compile(r"^Condition \d+$")


def is_guided_condition_name(value: str) -> bool:
    """Return whether a condition name is intentional enough for guided setup."""

    cleaned = value.strip()
    return len(cleaned) >= 3 and _DEFAULT_CONDITION_NAME_RE.fullmatch(cleaned) is None


def is_guided_trigger_code(value: int) -> bool:
    """Return whether a trigger code is acceptable in guided setup."""

    return value > 0


class ConditionSetupStep(QWidget):
    """Focused wizard step for condition identity and linked image sources."""

    advanced_timing_requested = Signal()

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._document = document

        self.condition_list = QListWidget(self)
        self.condition_list.setObjectName("setup_wizard_condition_list")
        self.condition_list.setProperty("setupConditionsList", "true")
        self.condition_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.condition_list.setAlternatingRowColors(True)
        self.condition_list.currentItemChanged.connect(self._refresh_editor)

        self.add_condition_button = QPushButton("+ Add Condition", self)
        self.add_condition_button.setObjectName("setup_wizard_add_condition_button")
        self.add_condition_button.clicked.connect(self._add_condition)
        mark_primary_action(self.add_condition_button)
        self.duplicate_condition_button = QPushButton("Duplicate", self)
        self.duplicate_condition_button.setObjectName("setup_wizard_duplicate_condition_button")
        self.duplicate_condition_button.clicked.connect(self._duplicate_condition)
        mark_secondary_action(self.duplicate_condition_button)
        self.remove_condition_button = QPushButton("Remove", self)
        self.remove_condition_button.setObjectName("setup_wizard_remove_condition_button")
        self.remove_condition_button.clicked.connect(self._remove_condition)
        self.remove_condition_button.setProperty("destructiveActionRole", "true")

        list_panel = QWidget(self)
        list_panel.setObjectName("setup_conditions_left_panel")
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(10)
        list_title = QLabel("Condition List", list_panel)
        list_title.setProperty("sectionCardRole", "title")
        list_note = QLabel("Create, remove, and reorder conditions.", list_panel)
        list_note.setProperty("setupPanelHelper", "true")
        list_note.setWordWrap(True)
        list_layout.addWidget(list_title)
        list_layout.addWidget(list_note)
        list_layout.addWidget(self.condition_list, 1)
        list_layout.addWidget(self.add_condition_button)
        list_layout.addWidget(self.duplicate_condition_button)
        list_layout.addWidget(self.remove_condition_button)

        self.selected_condition_badge = StatusBadgeLabel("No condition selected", self)
        self.selected_condition_badge.setObjectName("setup_wizard_selected_condition_badge")
        self.selected_condition_note = QLabel(self)
        self.selected_condition_note.setObjectName("setup_wizard_selected_condition_note")
        self.selected_condition_note.setProperty("setupPanelHelper", "true")
        self.selected_condition_note.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.name_check_status = QLabel("Missing", self)
        self.name_check_status.setObjectName("setup_wizard_condition_name_check")
        self.trigger_check_status = QLabel("Missing", self)
        self.trigger_check_status.setObjectName("setup_wizard_condition_trigger_check")
        self.base_check_status = QLabel("Missing", self)
        self.base_check_status.setObjectName("setup_wizard_condition_base_check")
        self.oddball_check_status = QLabel("Missing", self)
        self.oddball_check_status.setObjectName("setup_wizard_condition_oddball_check")

        self.condition_name_edit = QLineEdit(self)
        self.condition_name_edit.setObjectName("setup_wizard_condition_name_edit")
        self.condition_name_edit.editingFinished.connect(self._apply_name)
        self.trigger_code_spin = QSpinBox(self)
        self.trigger_code_spin.setObjectName("setup_wizard_condition_trigger_code_spin")
        self.trigger_code_spin.setRange(0, 65535)
        self.trigger_code_spin.valueChanged.connect(self._apply_trigger_code)
        self.instructions_edit = QTextEdit(self)
        self.instructions_edit.setObjectName("setup_wizard_condition_instructions_edit")
        self.instructions_edit.setMinimumHeight(90)
        self.instructions_edit.setMaximumHeight(130)
        self.instructions_edit.textChanged.connect(self._apply_instructions)

        form = QFormLayout()
        form.setVerticalSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.addRow("Condition Name", self.condition_name_edit)
        form.addRow("Trigger Code", self.trigger_code_spin)
        form.addRow("Participant Instructions", self.instructions_edit)

        self.base_source_card = SetupSourceCard(
            "Base Images",
            "Choose Base Images...",
            object_name="setup_conditions_base_source_card",
            parent=self,
        )
        self.base_source_value = self.base_source_card.folder_value
        self.base_source_value.setObjectName("setup_wizard_base_source_value")
        self.base_count_value = QLabel(self)
        self.base_count_value.setObjectName("setup_wizard_base_count_value")
        self.base_resolution_value = QLabel(self)
        self.base_resolution_value.setObjectName("setup_wizard_base_resolution_value")
        self.base_import_button = self.base_source_card.choose_button
        self.base_import_button.setObjectName("setup_wizard_import_base_folder_button")
        self.base_source_card.choose_requested.connect(lambda: self._import_stimulus_folder("base"))

        self.oddball_source_card = SetupSourceCard(
            "Oddball Images",
            "Choose Oddball Images...",
            object_name="setup_conditions_oddball_source_card",
            parent=self,
        )
        self.oddball_source_value = self.oddball_source_card.folder_value
        self.oddball_source_value.setObjectName("setup_wizard_oddball_source_value")
        self.oddball_count_value = QLabel(self)
        self.oddball_count_value.setObjectName("setup_wizard_oddball_count_value")
        self.oddball_resolution_value = QLabel(self)
        self.oddball_resolution_value.setObjectName("setup_wizard_oddball_resolution_value")
        self.oddball_import_button = self.oddball_source_card.choose_button
        self.oddball_import_button.setObjectName("setup_wizard_import_oddball_folder_button")
        self.oddball_source_card.choose_requested.connect(
            lambda: self._import_stimulus_folder("oddball")
        )

        sources_grid = QGridLayout()
        sources_grid.setContentsMargins(0, 0, 0, 0)
        sources_grid.setHorizontalSpacing(PAGE_SECTION_GAP)
        sources_grid.setVerticalSpacing(8)
        sources_grid.addWidget(self.base_source_card, 0, 0)
        sources_grid.addWidget(self.oddball_source_card, 0, 1)
        sources_grid.setColumnStretch(0, 1)
        sources_grid.setColumnStretch(1, 1)

        detail_panel = QWidget(self)
        detail_panel.setObjectName("setup_conditions_main_panel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(12)
        detail_header = QWidget(detail_panel)
        detail_header_layout = QHBoxLayout(detail_header)
        detail_header_layout.setContentsMargins(0, 0, 0, 0)
        detail_header_layout.setSpacing(8)
        detail_title = QLabel("Selected Condition", detail_header)
        detail_title.setProperty("sectionCardRole", "title")
        detail_header_layout.addWidget(detail_title)
        detail_header_layout.addWidget(self.selected_condition_badge)
        detail_header_layout.addStretch(1)
        detail_header_layout.addWidget(self.selected_condition_note)
        detail_layout.addWidget(detail_header)
        detail_layout.addLayout(form)
        sources_title = QLabel("Image Sources", detail_panel)
        sources_title.setProperty("sectionCardRole", "title")
        detail_layout.addWidget(sources_title)
        detail_layout.addLayout(sources_grid)
        detail_layout.addStretch(1)

        self.protocol_defaults_panel = SetupSidePanel(
            "Protocol Defaults",
            object_name="setup_conditions_protocol_defaults_panel",
            parent=self,
        )
        self.edit_advanced_timing_button = QPushButton("Edit Advanced Timing", self)
        self.edit_advanced_timing_button.setObjectName(
            "setup_conditions_edit_advanced_timing_button"
        )
        self.edit_advanced_timing_button.clicked.connect(self.advanced_timing_requested)
        mark_secondary_action(self.edit_advanced_timing_button)
        self.protocol_defaults_panel.add_action_button(self.edit_advanced_timing_button)
        self.protocol_defaults_panel.add_helper_text("Most projects should keep these defaults.")

        self.setup_checklist = SetupChecklistPanel(
            "Setup Checklist",
            object_name="setup_conditions_checklist_panel",
            parent=self,
        )

        right_panel = QWidget(self)
        right_panel.setObjectName("setup_conditions_right_panel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(PAGE_SECTION_GAP)
        right_layout.addWidget(self.protocol_defaults_panel)
        right_layout.addWidget(self.setup_checklist, 1)

        workspace = SetupWorkspaceFrame(object_name="setup_conditions_workspace", parent=self)
        workspace.set_regions(left=list_panel, main=detail_panel, right=right_panel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(workspace, 1)

        self._document.project_changed.connect(self.refresh)
        self._document.manifest_changed.connect(self.refresh)
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
                item = QListWidgetItem(self._condition_list_text(condition))
                item.setData(Qt.ItemDataRole.UserRole, condition.condition_id)
                self.condition_list.addItem(item)
                if condition.condition_id == selected_condition_id:
                    self.condition_list.setCurrentItem(item)
            if selected_condition_id is None and self.condition_list.count() > 0:
                self.condition_list.setCurrentRow(0)
        self._refresh_editor()

    def _condition_list_text(self, condition: Condition) -> str:
        base_set = self._document.get_condition_stimulus_set(condition.condition_id, "base")
        oddball_set = self._document.get_condition_stimulus_set(condition.condition_id, "oddball")
        if not is_guided_condition_name(condition.name):
            status = "Needs name"
        elif not is_guided_trigger_code(condition.trigger_code):
            status = "Needs trigger"
        elif self._stimulus_ready(base_set) and self._stimulus_ready(oddball_set):
            status = "Ready"
        else:
            status = "Needs images"
        return f"{condition.name}\n{status}"

    def _current_condition(self) -> Condition | None:
        condition_id = self.selected_condition_id()
        return self._document.get_condition(condition_id) if condition_id else None

    def _refresh_editor(self, *_args: object) -> None:
        condition = self._current_condition()
        enabled = condition is not None
        for widget in (
            self.condition_name_edit,
            self.trigger_code_spin,
            self.instructions_edit,
            self.duplicate_condition_button,
            self.remove_condition_button,
            self.base_import_button,
            self.oddball_import_button,
        ):
            widget.setEnabled(enabled)
        self.edit_advanced_timing_button.setEnabled(enabled)
        if condition is None:
            self.selected_condition_badge.set_state("pending", "No condition selected")
            self.selected_condition_note.setText("Choose a condition in the list to edit it.")
            with QSignalBlocker(self.condition_name_edit):
                self.condition_name_edit.clear()
            with QSignalBlocker(self.trigger_code_spin):
                self.trigger_code_spin.setValue(0)
            with QSignalBlocker(self.instructions_edit):
                self.instructions_edit.clear()
            self._set_checklist_statuses(False, False, False, False)
            self._set_source_summary(None, role="base")
            self._set_source_summary(None, role="oddball")
            self._set_protocol_defaults(None)
            return

        base_set = self._document.get_condition_stimulus_set(condition.condition_id, "base")
        oddball_set = self._document.get_condition_stimulus_set(condition.condition_id, "oddball")
        named = is_guided_condition_name(condition.name)
        trigger_ready = is_guided_trigger_code(condition.trigger_code)
        base_ready = self._stimulus_ready(base_set)
        oddball_ready = self._stimulus_ready(oddball_set)
        condition_ready = named and trigger_ready and base_ready and oddball_ready
        self.selected_condition_badge.set_state(
            "ready" if condition_ready else "warning",
            "Ready" if condition_ready else "Setup Incomplete",
        )
        self.selected_condition_note.setText(
            f"Condition ID: {condition.condition_id}   |   Trigger code: {condition.trigger_code}"
        )
        with QSignalBlocker(self.condition_name_edit):
            self.condition_name_edit.setText(condition.name)
        with QSignalBlocker(self.trigger_code_spin):
            self.trigger_code_spin.setValue(condition.trigger_code)
        _sync_text_editor_contents(self.instructions_edit, condition.instructions)
        self._set_checklist_statuses(named, trigger_ready, base_ready, oddball_ready)
        self._set_source_summary(base_set, role="base")
        self._set_source_summary(oddball_set, role="oddball")
        self._set_protocol_defaults(condition)

    def _set_checklist_statuses(
        self,
        named: bool,
        trigger_ready: bool,
        base_ready: bool,
        oddball_ready: bool,
    ) -> None:
        name_status = "Complete" if named else "Enter a descriptive name"
        trigger_status = "Complete" if trigger_ready else "Use a trigger code of 1 or higher"
        base_status = "Complete" if base_ready else "Base Images Not Selected"
        oddball_status = "Complete" if oddball_ready else "Oddball Images Not Selected"
        self.setup_checklist.set_items(
            [
                ("Name", named, name_status),
                ("Trigger", trigger_ready, trigger_status),
                ("Base Images", base_ready, base_status),
                ("Oddball Images", oddball_ready, oddball_status),
            ]
        )
        self.name_check_status.setText(name_status)
        self.trigger_check_status.setText(trigger_status)
        self.base_check_status.setText(base_status)
        self.oddball_check_status.setText(oddball_status)

    def _set_source_summary(self, stimulus_set: StimulusSet | None, *, role: str) -> None:
        source_value = self.base_source_value if role == "base" else self.oddball_source_value
        count_value = self.base_count_value if role == "base" else self.oddball_count_value
        resolution_value = (
            self.base_resolution_value if role == "base" else self.oddball_resolution_value
        )
        source_card = self.base_source_card if role == "base" else self.oddball_source_card
        if stimulus_set is None:
            source_value.set_path_text("Not configured", max_length=86)
            count_value.setText("0 images")
            resolution_value.setText("Not imported")
            source_card.set_source_state(
                ready=False,
                folder="Not configured",
                image_count="0 images",
                resolution="Not imported",
                variants="original",
            )
            return
        source_value.set_path_text(stimulus_set.source_dir, max_length=86)
        count_text = f"{stimulus_set.image_count} images"
        resolution_text = _resolution_text(stimulus_set.resolution)
        variants_text = ", ".join(item.value for item in stimulus_set.available_variants)
        count_value.setText(count_text)
        resolution_value.setText(resolution_text)
        source_card.set_source_state(
            ready=self._stimulus_ready(stimulus_set),
            folder=stimulus_set.source_dir,
            image_count=count_text,
            resolution=resolution_text,
            variants=variants_text,
        )

    def _set_protocol_defaults(self, condition: Condition | None) -> None:
        template = get_template(self._document.project.meta.template_id)
        if condition is None:
            self.protocol_defaults_panel.set_rows(
                [
                    ("Timing Template:", template.display_name),
                    ("Image Version:", "Original"),
                    ("Estimated Duration:", "Not available"),
                    ("Base Rate:", f"{template.base_hz:.1f} Hz"),
                    ("Oddball Rate:", f"{template.oddball_hz:.1f} Hz"),
                ]
            )
            return

        total_oddball_cycles = (
            condition.sequence_count * condition.oddball_cycle_repeats_per_sequence
        )
        total_stimuli = total_oddball_cycles * template.oddball_every_n
        duration_seconds = total_stimuli / template.base_hz
        self.protocol_defaults_panel.set_rows(
            [
                ("Timing Template:", self._timing_template_label(condition)),
                ("Image Version:", _variant_label(condition.stimulus_variant)),
                ("Estimated Duration:", f"{duration_seconds:.1f} s"),
                ("Base Rate:", f"{template.base_hz:.1f} Hz"),
                ("Oddball Rate:", f"{template.oddball_hz:.1f} Hz"),
            ]
        )

    def _add_condition(self) -> None:
        try:
            condition_id = self._document.create_condition()
        except Exception as error:
            _show_error_dialog(self, "Condition Error", error)
            return
        self._select_condition(condition_id)

    def _duplicate_condition(self) -> None:
        condition_id = self.selected_condition_id()
        if condition_id is None:
            return
        try:
            duplicated_id = self._document.duplicate_condition(condition_id)
        except Exception as error:
            _show_error_dialog(self, "Condition Error", error)
            return
        self._select_condition(duplicated_id)

    def _remove_condition(self) -> None:
        condition_id = self.selected_condition_id()
        if condition_id is None:
            return
        try:
            self._document.remove_condition(condition_id)
        except Exception as error:
            _show_error_dialog(self, "Condition Error", error)
            return
        self.refresh()

    def _apply_name(self) -> None:
        condition_id = self.selected_condition_id()
        if condition_id is None:
            return
        try:
            self._document.update_condition(condition_id, name=self.condition_name_edit.text())
        except Exception as error:
            _show_error_dialog(self, "Condition Error", error)
            self.refresh()

    def _apply_trigger_code(self) -> None:
        condition_id = self.selected_condition_id()
        if condition_id is None:
            return
        try:
            self._document.update_condition(
                condition_id,
                trigger_code=self.trigger_code_spin.value(),
            )
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

    def _select_condition(self, condition_id: str) -> None:
        self.refresh()
        for index in range(self.condition_list.count()):
            item = self.condition_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == condition_id:
                self.condition_list.setCurrentItem(item)
                break

    @staticmethod
    def _stimulus_ready(stimulus_set: StimulusSet) -> bool:
        return stimulus_set.image_count > 0

    @staticmethod
    def _timing_template_label(condition: Condition) -> str:
        if condition.duty_cycle_mode == DutyCycleMode.BLANK_50:
            return "50% Blank Between Images"
        return "Continuous Images"
