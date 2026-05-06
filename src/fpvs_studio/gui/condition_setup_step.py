"""Simplified condition setup surface for the Setup Wizard."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt
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
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.models import Condition, StimulusSet
from fpvs_studio.gui.components import (
    PAGE_SECTION_GAP,
    PathValueLabel,
    StatusBadgeLabel,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import (
    _resolution_text,
    _show_error_dialog,
    _sync_text_editor_contents,
)


class ConditionSetupStep(QWidget):
    """Focused wizard step for condition identity and linked image sources."""

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._document = document

        self.condition_list = QListWidget(self)
        self.condition_list.setObjectName("setup_wizard_condition_list")
        self.condition_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.condition_list.setAlternatingRowColors(True)
        self.condition_list.currentItemChanged.connect(self._refresh_editor)

        self.add_condition_button = QPushButton("Add Condition", self)
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

        list_buttons = QGridLayout()
        list_buttons.setContentsMargins(0, 0, 0, 0)
        list_buttons.setHorizontalSpacing(8)
        list_buttons.setVerticalSpacing(8)
        list_buttons.addWidget(self.add_condition_button, 0, 0)
        list_buttons.addWidget(self.duplicate_condition_button, 0, 1)
        list_buttons.addWidget(self.remove_condition_button, 1, 0, 1, 2)

        list_panel = QWidget(self)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)
        list_title = QLabel("Conditions", list_panel)
        list_title.setProperty("sectionCardRole", "title")
        list_layout.addWidget(list_title)
        list_layout.addWidget(self.condition_list, 1)
        list_layout.addLayout(list_buttons)

        self.selected_condition_badge = StatusBadgeLabel("No condition selected", self)
        self.selected_condition_badge.setObjectName("setup_wizard_selected_condition_badge")
        self.named_status = StatusBadgeLabel("Named", self)
        self.named_status.setObjectName("setup_wizard_condition_named_status")
        self.trigger_status = StatusBadgeLabel("Trigger", self)
        self.trigger_status.setObjectName("setup_wizard_condition_trigger_status")
        self.base_status = StatusBadgeLabel("Base images", self)
        self.base_status.setObjectName("setup_wizard_condition_base_status")
        self.oddball_status = StatusBadgeLabel("Oddball images", self)
        self.oddball_status.setObjectName("setup_wizard_condition_oddball_status")
        self.ready_status = StatusBadgeLabel("Ready", self)
        self.ready_status.setObjectName("setup_wizard_condition_ready_status")

        status_row = QWidget(self)
        status_layout = QHBoxLayout(status_row)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)
        for badge in (
            self.selected_condition_badge,
            self.named_status,
            self.trigger_status,
            self.base_status,
            self.oddball_status,
            self.ready_status,
        ):
            status_layout.addWidget(badge)
        status_layout.addStretch(1)

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

        self.base_source_value = PathValueLabel(self)
        self.base_source_value.setObjectName("setup_wizard_base_source_value")
        self.base_count_value = QLabel(self)
        self.base_count_value.setObjectName("setup_wizard_base_count_value")
        self.base_resolution_value = QLabel(self)
        self.base_resolution_value.setObjectName("setup_wizard_base_resolution_value")
        self.base_import_button = QPushButton("Choose Base Images...", self)
        self.base_import_button.setObjectName("setup_wizard_import_base_folder_button")
        self.base_import_button.clicked.connect(lambda: self._import_stimulus_folder("base"))
        mark_secondary_action(self.base_import_button)

        self.oddball_source_value = PathValueLabel(self)
        self.oddball_source_value.setObjectName("setup_wizard_oddball_source_value")
        self.oddball_count_value = QLabel(self)
        self.oddball_count_value.setObjectName("setup_wizard_oddball_count_value")
        self.oddball_resolution_value = QLabel(self)
        self.oddball_resolution_value.setObjectName("setup_wizard_oddball_resolution_value")
        self.oddball_import_button = QPushButton("Choose Oddball Images...", self)
        self.oddball_import_button.setObjectName("setup_wizard_import_oddball_folder_button")
        self.oddball_import_button.clicked.connect(
            lambda: self._import_stimulus_folder("oddball")
        )
        mark_secondary_action(self.oddball_import_button)

        sources_grid = QGridLayout()
        sources_grid.setContentsMargins(0, 0, 0, 0)
        sources_grid.setHorizontalSpacing(PAGE_SECTION_GAP)
        sources_grid.setVerticalSpacing(8)
        self._add_source_column(
            sources_grid,
            0,
            "Base Images",
            self.base_source_value,
            self.base_count_value,
            self.base_resolution_value,
            self.base_import_button,
        )
        self._add_source_column(
            sources_grid,
            1,
            "Oddball Images",
            self.oddball_source_value,
            self.oddball_count_value,
            self.oddball_resolution_value,
            self.oddball_import_button,
        )
        sources_grid.setColumnStretch(0, 1)
        sources_grid.setColumnStretch(1, 1)

        detail_panel = QWidget(self)
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(12)
        detail_title = QLabel("Selected Condition", detail_panel)
        detail_title.setProperty("sectionCardRole", "title")
        detail_layout.addWidget(detail_title)
        detail_layout.addWidget(status_row)
        detail_layout.addLayout(form)
        sources_title = QLabel("Image Sources", detail_panel)
        sources_title.setProperty("sectionCardRole", "title")
        detail_layout.addWidget(sources_title)
        detail_layout.addLayout(sources_grid)
        detail_layout.addStretch(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(PAGE_SECTION_GAP)
        layout.addWidget(list_panel, 1)
        layout.addWidget(detail_panel, 3)

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
        status = (
            "Ready"
            if self._stimulus_ready(base_set) and self._stimulus_ready(oddball_set)
            else "Needs images"
        )
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
        if condition is None:
            self.selected_condition_badge.set_state("pending", "No condition selected")
            with QSignalBlocker(self.condition_name_edit):
                self.condition_name_edit.clear()
            with QSignalBlocker(self.trigger_code_spin):
                self.trigger_code_spin.setValue(0)
            with QSignalBlocker(self.instructions_edit):
                self.instructions_edit.clear()
            self._set_status_badges(False, False, False, False)
            self._set_source_summary(None, role="base")
            self._set_source_summary(None, role="oddball")
            return

        base_set = self._document.get_condition_stimulus_set(condition.condition_id, "base")
        oddball_set = self._document.get_condition_stimulus_set(condition.condition_id, "oddball")
        named = bool(condition.name.strip())
        trigger_ready = condition.trigger_code >= 0
        base_ready = self._stimulus_ready(base_set)
        oddball_ready = self._stimulus_ready(oddball_set)
        self.selected_condition_badge.set_state("ready", condition.name)
        with QSignalBlocker(self.condition_name_edit):
            self.condition_name_edit.setText(condition.name)
        with QSignalBlocker(self.trigger_code_spin):
            self.trigger_code_spin.setValue(condition.trigger_code)
        _sync_text_editor_contents(self.instructions_edit, condition.instructions)
        self._set_status_badges(named, trigger_ready, base_ready, oddball_ready)
        self._set_source_summary(base_set, role="base")
        self._set_source_summary(oddball_set, role="oddball")

    def _set_status_badges(
        self,
        named: bool,
        trigger_ready: bool,
        base_ready: bool,
        oddball_ready: bool,
    ) -> None:
        self.named_status.set_state(
            "ready" if named else "warning",
            "Named" if named else "Name needed",
        )
        self.trigger_status.set_state(
            "ready" if trigger_ready else "warning",
            "Trigger set" if trigger_ready else "Trigger needed",
        )
        self.base_status.set_state(
            "ready" if base_ready else "warning",
            "Base ready" if base_ready else "Base needed",
        )
        self.oddball_status.set_state(
            "ready" if oddball_ready else "warning",
            "Oddball ready" if oddball_ready else "Oddball needed",
        )
        ready = named and trigger_ready and base_ready and oddball_ready
        self.ready_status.set_state(
            "ready" if ready else "warning",
            "Ready" if ready else "Not ready",
        )

    def _set_source_summary(self, stimulus_set: StimulusSet | None, *, role: str) -> None:
        source_value = self.base_source_value if role == "base" else self.oddball_source_value
        count_value = self.base_count_value if role == "base" else self.oddball_count_value
        resolution_value = (
            self.base_resolution_value if role == "base" else self.oddball_resolution_value
        )
        if stimulus_set is None:
            source_value.set_path_text("Not configured", max_length=86)
            count_value.setText("0 images")
            resolution_value.setText("Not imported")
            return
        source_value.set_path_text(stimulus_set.source_dir, max_length=86)
        count_value.setText(f"{stimulus_set.image_count} images")
        resolution_value.setText(_resolution_text(stimulus_set.resolution))

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
    def _add_source_column(
        layout: QGridLayout,
        column: int,
        title: str,
        source_value: PathValueLabel,
        count_value: QLabel,
        resolution_value: QLabel,
        import_button: QPushButton,
    ) -> None:
        title_label = QLabel(title)
        title_label.setProperty("sectionCardRole", "title")
        layout.addWidget(title_label, 0, column)
        layout.addWidget(source_value, 1, column)
        detail_row = QWidget()
        detail_layout = QHBoxLayout(detail_row)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(8)
        detail_layout.addWidget(count_value)
        detail_layout.addWidget(resolution_value)
        detail_layout.addStretch(1)
        layout.addWidget(detail_row, 2, column)
        layout.addWidget(import_button, 3, column)
        import_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
