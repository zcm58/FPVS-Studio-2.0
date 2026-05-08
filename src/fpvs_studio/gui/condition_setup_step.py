"""Simplified condition setup surface for the Setup Wizard."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
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

from fpvs_studio.core.enums import StimulusVariant
from fpvs_studio.core.models import Condition, StimulusSet
from fpvs_studio.core.paths import stimuli_dir
from fpvs_studio.gui.components import (
    PAGE_SECTION_GAP,
    SetupSourceCard,
    SetupWorkspaceFrame,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.control_condition_dialog import ControlConditionDialog
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import (
    DebouncedTextCommitter,
    _resolution_text,
    _show_error_dialog,
    _sync_text_editor_contents,
)
from fpvs_studio.gui.workers import ProgressTask

_DEFAULT_CONDITION_NAME_RE = re.compile(r"^Condition \d+$")
_SOURCE_CARD_WIDTH = 210
_SOURCE_CARD_HEIGHT = 232
_SOURCE_ROW_MIN_WIDTH = (_SOURCE_CARD_WIDTH * 2) + PAGE_SECTION_GAP
_SOURCE_FOLDER_VALUE_HEIGHT = 68
_SOURCE_METRICS_HEIGHT = 58
_INSTRUCTIONS_HEIGHT = 92
_CONDITION_STEP_MIN_WIDTH = 840


class _ConditionSourcesRow(QWidget):
    """Fixed source-card row with deterministic bottom-edge alignment."""

    def __init__(
        self,
        base_card: SetupSourceCard,
        oddball_card: SetupSourceCard,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("setup_conditions_sources_row")
        self.setFixedHeight(_SOURCE_CARD_HEIGHT)
        self.setMinimumWidth(_SOURCE_ROW_MIN_WIDTH)
        self._base_card = base_card
        self._oddball_card = oddball_card
        self._base_card.setParent(self)
        self._oddball_card.setParent(self)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        left = max(0, round((self.width() - _SOURCE_ROW_MIN_WIDTH) / 2))
        card_top = 0
        self._base_card.setGeometry(
            left,
            card_top,
            _SOURCE_CARD_WIDTH,
            _SOURCE_CARD_HEIGHT,
        )
        self._oddball_card.setGeometry(
            left + _SOURCE_CARD_WIDTH + PAGE_SECTION_GAP,
            card_top,
            _SOURCE_CARD_WIDTH,
            _SOURCE_CARD_HEIGHT,
        )


def is_guided_condition_name(value: str) -> bool:
    """Return whether a condition name is intentional enough for guided setup."""

    cleaned = value.strip()
    return len(cleaned) >= 3 and _DEFAULT_CONDITION_NAME_RE.fullmatch(cleaned) is None


def is_guided_trigger_code(value: int) -> bool:
    """Return whether a trigger code is acceptable in guided setup."""

    return value > 0


class ConditionSetupStep(QWidget):
    """Focused wizard step for condition identity and linked image sources."""

    def __init__(
        self,
        document: ProjectDocument,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumWidth(_CONDITION_STEP_MIN_WIDTH)
        self._document = document
        self._pending_instruction_condition_id: str | None = None
        self._active_task: ProgressTask | None = None

        self.condition_list = QListWidget(self)
        self.condition_list.setObjectName("setup_wizard_condition_list")
        self.condition_list.setProperty("setupConditionsList", "true")
        self.condition_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.condition_list.setAlternatingRowColors(True)
        self.condition_list.currentItemChanged.connect(self._handle_current_condition_changed)

        self.add_condition_button = QPushButton("+ Add Condition", self)
        self.add_condition_button.setObjectName("setup_wizard_add_condition_button")
        self.add_condition_button.clicked.connect(self._add_condition)
        mark_primary_action(self.add_condition_button)
        self.duplicate_condition_button = QPushButton("Duplicate", self)
        self.duplicate_condition_button.setObjectName("setup_wizard_duplicate_condition_button")
        self.duplicate_condition_button.clicked.connect(self._duplicate_condition)
        mark_secondary_action(self.duplicate_condition_button)
        self.create_control_condition_button = QPushButton("Create Control Condition...", self)
        self.create_control_condition_button.setObjectName(
            "setup_wizard_create_control_condition_button"
        )
        self.create_control_condition_button.clicked.connect(self._create_control_condition)
        mark_secondary_action(self.create_control_condition_button)
        self.remove_condition_button = QPushButton("Remove", self)
        self.remove_condition_button.setObjectName("setup_wizard_remove_condition_button")
        self.remove_condition_button.clicked.connect(self._remove_condition)
        self.remove_condition_button.setProperty("destructiveActionRole", "true")

        list_panel = QWidget(self)
        list_panel.setObjectName("setup_conditions_left_panel")
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)
        list_layout.addWidget(self.condition_list, 1)
        action_grid = QGridLayout()
        action_grid.setContentsMargins(0, 0, 0, 0)
        action_grid.setHorizontalSpacing(8)
        action_grid.setVerticalSpacing(8)
        action_grid.addWidget(self.add_condition_button, 0, 0)
        action_grid.addWidget(self.duplicate_condition_button, 0, 1)
        action_grid.addWidget(self.create_control_condition_button, 1, 0)
        action_grid.addWidget(self.remove_condition_button, 1, 1)
        action_grid.setColumnStretch(0, 1)
        action_grid.setColumnStretch(1, 1)
        list_layout.addLayout(action_grid)

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
        self.instructions_edit.setFixedHeight(_INSTRUCTIONS_HEIGHT)
        self._instructions_committer = DebouncedTextCommitter(
            self.instructions_edit,
            self._apply_instructions,
        )
        self.instructions_edit.textChanged.connect(self._schedule_instruction_commit)

        self.condition_details_section = QFrame(self)
        self.condition_details_section.setObjectName("setup_conditions_details_section")
        self.condition_details_section.setProperty("conditionDetailsSection", "true")
        details_section_layout = QVBoxLayout(self.condition_details_section)
        details_section_layout.setContentsMargins(10, 8, 10, 8)
        details_section_layout.setSpacing(0)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setVerticalSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.addRow("Condition Name", self.condition_name_edit)
        form.addRow("Trigger Code", self.trigger_code_spin)
        form.addRow("Participant Instructions", self.instructions_edit)
        details_section_layout.addLayout(form)

        self.base_source_card = SetupSourceCard(
            "Base Images",
            "Choose Base Images...",
            object_name="setup_conditions_base_source_card",
            compact=True,
            show_variants=False,
            parent=self,
        )
        self.base_source_card.status_badge.setVisible(False)
        self.base_source_card.setFixedSize(_SOURCE_CARD_WIDTH, _SOURCE_CARD_HEIGHT)
        self.base_source_value = self.base_source_card.folder_value
        self.base_source_value.setObjectName("setup_wizard_base_source_value")
        self.base_source_value.setFixedHeight(_SOURCE_FOLDER_VALUE_HEIGHT)
        self.base_count_value = QLabel(self)
        self.base_count_value.setObjectName("setup_wizard_base_count_value")
        self.base_resolution_value = QLabel(self)
        self.base_resolution_value.setObjectName("setup_wizard_base_resolution_value")
        self.base_source_card.metrics.setFixedHeight(_SOURCE_METRICS_HEIGHT)
        self.base_import_button = self.base_source_card.choose_button
        self.base_import_button.setObjectName("setup_wizard_import_base_folder_button")
        self.base_source_card.choose_requested.connect(lambda: self._import_stimulus_folder("base"))

        self.oddball_source_card = SetupSourceCard(
            "Oddball Images",
            "Choose Oddball Images...",
            object_name="setup_conditions_oddball_source_card",
            compact=True,
            show_variants=False,
            parent=self,
        )
        self.oddball_source_card.status_badge.setVisible(False)
        self.oddball_source_card.setFixedSize(_SOURCE_CARD_WIDTH, _SOURCE_CARD_HEIGHT)
        self.oddball_source_value = self.oddball_source_card.folder_value
        self.oddball_source_value.setObjectName("setup_wizard_oddball_source_value")
        self.oddball_source_value.setFixedHeight(_SOURCE_FOLDER_VALUE_HEIGHT)
        self.oddball_count_value = QLabel(self)
        self.oddball_count_value.setObjectName("setup_wizard_oddball_count_value")
        self.oddball_resolution_value = QLabel(self)
        self.oddball_resolution_value.setObjectName("setup_wizard_oddball_resolution_value")
        self.oddball_source_card.metrics.setFixedHeight(_SOURCE_METRICS_HEIGHT)
        self.oddball_import_button = self.oddball_source_card.choose_button
        self.oddball_import_button.setObjectName("setup_wizard_import_oddball_folder_button")
        self.oddball_source_card.choose_requested.connect(
            lambda: self._import_stimulus_folder("oddball")
        )

        sources_row = _ConditionSourcesRow(
            self.base_source_card,
            self.oddball_source_card,
            parent=self,
        )

        detail_panel = QWidget(self)
        detail_panel.setObjectName("setup_conditions_main_panel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(8)

        detail_layout.addWidget(self.condition_details_section)
        detail_layout.addStretch(1)
        detail_layout.addWidget(sources_row)

        workspace = SetupWorkspaceFrame(object_name="setup_conditions_workspace", parent=self)
        workspace.set_regions(left=list_panel, main=detail_panel)
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
        if self._instructions_committer.pending:
            self._instructions_committer.flush()
        selected_condition_id = self.selected_condition_id()
        with QSignalBlocker(self.condition_list):
            self.condition_list.clear()
            for condition in self._document.ordered_conditions():
                item = QListWidgetItem(condition.name)
                item.setToolTip(self._condition_status_text(condition))
                item.setSizeHint(QSize(0, 34))
                item.setData(Qt.ItemDataRole.UserRole, condition.condition_id)
                self.condition_list.addItem(item)
                if condition.condition_id == selected_condition_id:
                    self.condition_list.setCurrentItem(item)
            if selected_condition_id is None and self.condition_list.count() > 0:
                self.condition_list.setCurrentRow(0)
        self._refresh_editor()

    def flush_pending_edits(self) -> None:
        self._instructions_committer.flush()

    def _handle_current_condition_changed(self, *_args: object) -> None:
        self.flush_pending_edits()
        self._refresh_editor()

    def _condition_status_text(self, condition: Condition) -> str:
        base_set = self._document.get_condition_stimulus_set(condition.condition_id, "base")
        oddball_set = self._document.get_condition_stimulus_set(condition.condition_id, "oddball")
        if not is_guided_condition_name(condition.name):
            return "Needs name"
        elif not is_guided_trigger_code(condition.trigger_code):
            return "Needs trigger"
        elif self._stimulus_ready(base_set) and self._stimulus_ready(oddball_set):
            return "Ready"
        else:
            return "Needs images"

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
        self.create_control_condition_button.setEnabled(
            enabled and self._condition_has_control_sources(condition)
        )
        self.create_control_condition_button.setToolTip(
            ""
            if self.create_control_condition_button.isEnabled()
            else "Choose base and oddball images before creating a control condition."
        )
        if condition is None:
            with QSignalBlocker(self.condition_name_edit):
                self.condition_name_edit.clear()
            with QSignalBlocker(self.trigger_code_spin):
                self.trigger_code_spin.setValue(0)
            with QSignalBlocker(self.instructions_edit):
                self.instructions_edit.clear()
            self._set_checklist_statuses(False, False, False, False)
            self._set_source_summary(None, role="base")
            self._set_source_summary(None, role="oddball")
            return

        base_set = self._document.get_condition_stimulus_set(condition.condition_id, "base")
        oddball_set = self._document.get_condition_stimulus_set(condition.condition_id, "oddball")
        named = is_guided_condition_name(condition.name)
        trigger_ready = is_guided_trigger_code(condition.trigger_code)
        base_ready = self._stimulus_ready(base_set)
        oddball_ready = self._stimulus_ready(oddball_set)
        with QSignalBlocker(self.condition_name_edit):
            self.condition_name_edit.setText(condition.name)
        with QSignalBlocker(self.trigger_code_spin):
            self.trigger_code_spin.setValue(condition.trigger_code)
        if not self._instructions_committer.pending:
            _sync_text_editor_contents(self.instructions_edit, condition.instructions)
        self._set_checklist_statuses(named, trigger_ready, base_ready, oddball_ready)
        self._set_source_summary(base_set, role="base")
        self._set_source_summary(oddball_set, role="oddball")

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

    def _add_condition(self) -> None:
        self.flush_pending_edits()
        try:
            condition_id = self._document.create_condition()
        except Exception as error:
            _show_error_dialog(self, "Condition Error", error)
            return
        self._select_condition(condition_id)

    def _duplicate_condition(self) -> None:
        self.flush_pending_edits()
        condition_id = self.selected_condition_id()
        if condition_id is None:
            return
        try:
            duplicated_id = self._document.duplicate_condition(condition_id)
        except Exception as error:
            _show_error_dialog(self, "Condition Error", error)
            return
        self._select_condition(duplicated_id)

    def _create_control_condition(self) -> None:
        self.flush_pending_edits()
        condition_id = self.selected_condition_id()
        source_condition = self._current_condition()
        if condition_id is None or source_condition is None:
            return
        dialog = ControlConditionDialog(
            source_condition_name=source_condition.name,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        variant = dialog.selected_variant()
        should_materialize = self._control_variant_missing(condition_id, variant)
        try:
            new_condition_id = self._document.create_control_condition(
                condition_id,
                variant=variant,
                name=dialog.condition_name(),
            )
            if variant not in self._document.project.settings.supported_variants:
                self._document.set_supported_variants(
                    [*self._document.project.settings.supported_variants, variant]
                )
        except Exception as error:
            _show_error_dialog(self, "Control Condition Error", error)
            return
        self._select_condition(new_condition_id)
        if should_materialize:
            self._materialize_control_variant()

    def _remove_condition(self) -> None:
        self.flush_pending_edits()
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

    def _schedule_instruction_commit(self) -> None:
        self._pending_instruction_condition_id = self.selected_condition_id()
        self._instructions_committer.schedule()

    def _apply_instructions(self) -> None:
        condition_id = self._pending_instruction_condition_id or self.selected_condition_id()
        self._pending_instruction_condition_id = None
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
            str(self._stimulus_dialog_start_dir()),
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

    def _stimulus_dialog_start_dir(self) -> Path:
        project_stimuli_dir = stimuli_dir(self._document.project_root)
        return project_stimuli_dir if project_stimuli_dir.exists() else self._document.project_root

    def _condition_has_control_sources(self, condition: Condition | None) -> bool:
        if condition is None or self._active_task is not None:
            return False
        base_set = self._document.get_condition_stimulus_set(condition.condition_id, "base")
        oddball_set = self._document.get_condition_stimulus_set(condition.condition_id, "oddball")
        return self._stimulus_ready(base_set) and self._stimulus_ready(oddball_set)

    def _control_variant_missing(self, condition_id: str, variant: StimulusVariant) -> bool:
        base_set = self._document.get_condition_stimulus_set(condition_id, "base")
        oddball_set = self._document.get_condition_stimulus_set(condition_id, "oddball")
        return (
            variant not in base_set.available_variants
            or variant not in oddball_set.available_variants
        )

    def _materialize_control_variant(self) -> None:
        if self._active_task is not None:
            return
        task = ProgressTask(
            parent_widget=self,
            label="Building control-condition image variants...",
            callback=self._document.materialize_assets,
        )
        self._active_task = task
        self._refresh_editor()
        task.succeeded.connect(lambda _result: self.refresh())
        task.failed.connect(self._on_materialization_failed)
        task.finished.connect(self._on_materialization_finished)
        task.start()

    def _on_materialization_failed(self, error: object) -> None:
        if isinstance(error, Exception):
            _show_error_dialog(self, "Control Condition Variant Error", error)
        else:
            _show_error_dialog(self, "Control Condition Variant Error", RuntimeError(str(error)))

    def _on_materialization_finished(self) -> None:
        self._active_task = None
        self._refresh_editor()

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
