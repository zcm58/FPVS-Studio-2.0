"""Primary Phase 5 authoring window for FPVS Studio.
It binds user actions to backend document services for project editing, preprocessing, validation, preflight, and test-mode launch workflows.
The window owns UI composition and honest runtime messaging, not protocol semantics, RunSpec compilation rules, or execution flow."""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEventLoop, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
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
    QSizePolicy,
    QSpinBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.enums import (
    DutyCycleMode,
    InterConditionMode,
    StimulusVariant,
    ValidationSeverity,
)
from fpvs_studio.core.models import ConditionTemplateProfile
from fpvs_studio.core.template_library import get_template
from fpvs_studio.gui.animations import AnimatedTabBar, ButtonHoverAnimator
from fpvs_studio.gui.document import ConditionStimulusRow, DocumentError, ProjectDocument

_CYCLE_HELP_TEXT = "Cycle = one turn of base presentations plus one oddball presentation."
_FIXATION_FEASIBILITY_TOOLTIP_TEXT = (
    "Derived from each condition's duration and the current fixation timing settings."
)
_RUNTIME_BACKGROUND_COLOR_PRESETS: tuple[tuple[str, str], ...] = (
    ("Black", "#000000"),
    ("Dark Gray", "#101010"),
)
_LAUNCH_INTERSTITIAL_DURATION_MS = 700
_PAGE_WIDTH_PRESETS: dict[str, int] = {
    "narrow": 920,
    "medium": 1100,
    "wide": 1280,
}


def _canonical_runtime_background_hex(background_color: str) -> str | None:
    """Return the canonical preset hex when one runtime background preset matches."""

    normalized = background_color.strip().lower()
    for _label, preset_hex in _RUNTIME_BACKGROUND_COLOR_PRESETS:
        if preset_hex.lower() == normalized:
            return preset_hex
    return None


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


def _set_form_row_visible(layout: QFormLayout, field: QWidget, visible: bool) -> None:
    label = layout.labelForField(field)
    if label is not None:
        label.setVisible(visible)
    field.setVisible(visible)


def _prefixed_object_name(prefix: str, name: str) -> str:
    if not prefix:
        return name
    return f"{prefix}{name}"


@dataclass(frozen=True)
class LauncherReadinessReport:
    status_label: str
    badge_state: str
    status_summary: str
    readiness_items: tuple[str, ...]
    preview_note: str | None = None


def _truncate_line(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 3]}..."


def _configure_read_only_list(widget: QListWidget) -> None:
    widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
    widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    widget.setWordWrap(True)
    widget.setSpacing(2)
    widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)


def _set_widget_property(widget: QWidget, name: str, value: str) -> None:
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def _set_list_items(widget: QListWidget, lines: list[str] | tuple[str, ...]) -> None:
    widget.clear()
    for line in lines:
        widget.addItem(line)


def _conditions_have_assigned_assets(document: ProjectDocument, ordered_conditions: list) -> bool:
    if not ordered_conditions:
        return False
    available_set_ids = {stimulus_set.set_id for stimulus_set in document.project.stimulus_sets}
    if not available_set_ids:
        return False
    return all(
        condition.base_stimulus_set_id in available_set_ids
        and condition.oddball_stimulus_set_id in available_set_ids
        for condition in ordered_conditions
    )


def _launcher_readiness_report(document: ProjectDocument, *, refresh_hz: float) -> LauncherReadinessReport:
    ordered_conditions = document.ordered_conditions()
    validation = document.validation_report(refresh_hz=refresh_hz)
    blocking_issues = [
        issue for issue in validation.issues if issue.severity == ValidationSeverity.ERROR
    ]
    blocking_issue_count = len(blocking_issues)

    conditions_ready = bool(ordered_conditions)
    assets_ready = _conditions_have_assigned_assets(document, ordered_conditions)
    preview_available = document.last_session_plan is not None

    if not conditions_ready:
        status_label = "Setup Required"
        badge_state = "pending"
    elif not assets_ready:
        status_label = "Missing Required Assets"
        badge_state = "warning"
    elif blocking_issue_count > 0:
        status_label = "Validation Issues"
        badge_state = "warning"
    else:
        status_label = "Ready to Launch"
        badge_state = "ready"

    if not conditions_ready:
        status_summary = "Add at least one condition before launching."
    elif not assets_ready:
        status_summary = "Assign all base and oddball stimulus sets before launching."
    elif blocking_issue_count > 0:
        status_summary = (
            f"Validation at {refresh_hz:.2f} Hz reports {blocking_issue_count} blocking issue(s)."
        )
    else:
        status_summary = f"Launch requirements are satisfied at {refresh_hz:.2f} Hz."

    readiness_items: list[str] = []
    if conditions_ready:
        readiness_items.append(f"[OK] Conditions configured: {len(ordered_conditions)}.")
    else:
        readiness_items.append("[TODO] Add at least one condition.")

    if conditions_ready and assets_ready:
        readiness_items.append("[OK] Stimulus assignments present for all conditions.")
    elif conditions_ready:
        readiness_items.append("[TODO] Assign base and oddball sets for each condition.")
    else:
        readiness_items.append("[TODO] Assign base and oddball sets for each condition.")

    if blocking_issue_count > 0:
        readiness_items.append(
            f"[WARN] Validation ({refresh_hz:.2f} Hz): {blocking_issue_count} blocking issue(s)."
        )
        readiness_items.append(
            f"[WARN] First blocker: {_truncate_line(blocking_issues[0].message, 120)}"
        )
    else:
        readiness_items.append(f"[OK] Validation ({refresh_hz:.2f} Hz) clear.")

    readiness_items.append("[INFO] Runtime path: alpha test-mode only.")
    return LauncherReadinessReport(
        status_label=status_label,
        badge_state=badge_state,
        status_summary=status_summary,
        readiness_items=tuple(readiness_items),
        preview_note=(
            "Session preview available for inspection. Launch will still compile and run launch checks automatically."
            if preview_available
            else "Launch will compile and run launch checks automatically."
        ),
    )


class LeftToRightPlainTextEdit(QPlainTextEdit):
    """Plain-text editor with left-to-right document defaults."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setLayoutDirection(Qt.LeftToRight)
        text_option = self.document().defaultTextOption()
        text_option.setTextDirection(Qt.LeftToRight)
        self.document().setDefaultTextOption(text_option)


class ParticipantNumberDialog(QDialog):
    """Collect the required launch-time participant number."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Participant Number")
        self.setModal(True)
        self.resize(420, 120)

        self.prompt_label = QLabel("Please enter the participant number.", self)
        self.prompt_label.setObjectName("participant_number_prompt_label")

        self.participant_number_edit = QLineEdit(self)
        self.participant_number_edit.setObjectName("participant_number_edit")
        self.participant_number_edit.setPlaceholderText("Digits only (for example, 0012)")
        self.participant_number_edit.setLayoutDirection(Qt.LeftToRight)
        self.participant_number_edit.setFocus()

        form_layout = QFormLayout()
        form_layout.addRow("Participant Number", self.participant_number_edit)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.button_box.setObjectName("participant_number_button_box")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.prompt_label)
        layout.addLayout(form_layout)
        layout.addWidget(self.button_box)

    @property
    def participant_number(self) -> str:
        """Return the trimmed participant number value."""

        return self.participant_number_edit.text().strip()

    def accept(self) -> None:
        participant_number = self.participant_number
        if not participant_number:
            QMessageBox.warning(
                self,
                "Participant Number Required",
                "Enter a participant number to launch the session.",
            )
            self.participant_number_edit.setFocus()
            return
        if not participant_number.isdigit():
            QMessageBox.warning(
                self,
                "Invalid Participant Number",
                "Participant number must contain digits only.",
            )
            self.participant_number_edit.setFocus()
            self.participant_number_edit.selectAll()
            return
        self.participant_number_edit.setText(participant_number)
        super().accept()


class ProjectOverviewEditor(QWidget):
    """Compact project metadata and condition template controls editor."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        load_condition_template_profiles: Callable[[], list[ConditionTemplateProfile]],
        manage_condition_templates: Callable[[], list[ConditionTemplateProfile]],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._load_condition_template_profiles = load_condition_template_profiles
        self._manage_condition_templates = manage_condition_templates
        self._condition_profiles_by_id: dict[str, ConditionTemplateProfile] = {}

        self.project_name_edit = QLineEdit(self)
        self.project_name_edit.setObjectName("project_name_edit")
        self.project_name_edit.editingFinished.connect(self._apply_project_name)

        self.project_description_edit = LeftToRightPlainTextEdit(self)
        self.project_description_edit.setObjectName("project_description_edit")
        self.project_description_edit.setPlaceholderText(
            "Describe the project goal and participant instructions."
        )
        self.project_description_edit.setFixedHeight(90)
        self.project_description_edit.setMaximumBlockCount(20)
        self.project_description_edit.textChanged.connect(self._apply_project_description)

        self.project_root_value = QLabel(self)
        self.project_root_value.setObjectName("project_root_value")
        self.project_root_value.setWordWrap(True)
        self.project_root_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.condition_profile_combo = QComboBox(self)
        self.condition_profile_combo.setObjectName("project_condition_profile_combo")
        self.condition_profile_combo.setPlaceholderText("Select a condition template profile...")
        self.condition_profile_combo.currentIndexChanged.connect(self._apply_condition_profile_selection)
        self.manage_templates_button = QPushButton("Manage Templates...", self)
        self.manage_templates_button.setObjectName("project_manage_templates_button")
        self.manage_templates_button.clicked.connect(self._open_template_manager)
        self.apply_profile_to_conditions_button = QPushButton("Apply Template To All Conditions", self)
        self.apply_profile_to_conditions_button.setObjectName("apply_profile_to_conditions_button")
        self.apply_profile_to_conditions_button.clicked.connect(self._apply_profile_to_conditions)

        condition_profile_row = QWidget(self)
        condition_profile_layout = QHBoxLayout(condition_profile_row)
        condition_profile_layout.setContentsMargins(0, 0, 0, 0)
        condition_profile_layout.setSpacing(8)
        condition_profile_layout.addWidget(self.condition_profile_combo, 1)
        condition_profile_layout.addWidget(self.manage_templates_button)
        condition_profile_layout.addWidget(self.apply_profile_to_conditions_button)

        self.project_overview_card = SectionCard(
            title="Project Overview",
            subtitle=(
                "Set project metadata and choose the default condition template "
                "profile used when new conditions are added."
            ),
            object_name="dashboard_project_overview_card",
            parent=self,
        )
        metadata_layout = QFormLayout()
        metadata_layout.setVerticalSpacing(10)
        metadata_layout.addRow("Name", self.project_name_edit)
        metadata_layout.addRow("Description", self.project_description_edit)
        metadata_layout.addRow("Project Root", self.project_root_value)
        metadata_layout.addRow("Condition Template", condition_profile_row)
        self.project_overview_card.body_layout.addLayout(metadata_layout)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.project_overview_card)

        self.setStyleSheet(
            """
            QLabel#project_root_value {
                border: 1px solid #d6dde8;
                border-radius: 6px;
                background-color: #ffffff;
                padding: 6px 8px;
            }
            """
        )

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        project = self._document.project
        with QSignalBlocker(self.project_name_edit):
            self.project_name_edit.setText(project.meta.name)
        _sync_text_editor_contents(self.project_description_edit, project.meta.description)
        self.project_root_value.setText(str(self._document.project_root))
        self._refresh_condition_profile_widgets()

    def _refresh_condition_profile_widgets(self) -> None:
        profiles = self._load_condition_template_profiles()
        self._condition_profiles_by_id = {profile.profile_id: profile for profile in profiles}
        selected_profile_id = self._document.project.settings.condition_profile_id
        with QSignalBlocker(self.condition_profile_combo):
            self.condition_profile_combo.clear()
            for profile in profiles:
                self.condition_profile_combo.addItem(
                    f"{profile.display_name} ({profile.profile_id})",
                    userData=profile.profile_id,
                )
            if selected_profile_id is None:
                self.condition_profile_combo.setCurrentIndex(-1)
            else:
                selected_index = self.condition_profile_combo.findData(selected_profile_id)
                self.condition_profile_combo.setCurrentIndex(
                    selected_index if selected_index >= 0 else -1
                )

        profile = (
            self._condition_profiles_by_id.get(selected_profile_id)
            if selected_profile_id is not None
            else None
        )
        self.apply_profile_to_conditions_button.setEnabled(
            profile is not None and bool(self._document.project.conditions)
        )

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

    def _apply_condition_profile_selection(self) -> None:
        profile_id = self.condition_profile_combo.currentData()
        if not profile_id:
            return
        profile = self._condition_profiles_by_id.get(str(profile_id))
        if profile is None:
            return
        try:
            self._document.apply_condition_template_profile(
                profile,
                apply_to_existing_conditions=False,
            )
        except Exception as error:
            _show_error_dialog(self, "Condition Template Error", error)
            self.refresh()

    def _open_template_manager(self) -> None:
        try:
            self._manage_condition_templates()
        except Exception as error:
            _show_error_dialog(self, "Condition Template Error", error)
            return
        self.refresh()

    def _apply_profile_to_conditions(self) -> None:
        profile_id = self._document.project.settings.condition_profile_id
        if profile_id is None:
            QMessageBox.warning(
                self,
                "No Condition Template Selected",
                "Select a condition template profile before applying defaults to all conditions.",
            )
            return
        profile = self._condition_profiles_by_id.get(profile_id)
        if profile is None:
            QMessageBox.warning(
                self,
                "Condition Template Missing",
                "The selected condition template profile is missing from the global library.",
            )
            return
        try:
            self._document.apply_condition_template_profile(
                profile,
                apply_to_existing_conditions=True,
            )
        except Exception as error:
            _show_error_dialog(self, "Condition Template Error", error)
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
        self.condition_list_card = SectionCard(
            title="Condition List",
            subtitle="Create, remove, and reorder conditions in session order.",
            object_name="conditions_list_card",
            parent=self,
        )
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

        self.condition_editor_card = SectionCard(
            title="Identity & Logic",
            subtitle="Edit condition naming, instructions, trigger code, and timing defaults.",
            object_name="conditions_editor_card",
            parent=self,
        )
        editor_layout = QFormLayout()
        editor_layout.addRow("Condition Name", self.condition_name_edit)
        editor_layout.addRow("Instructions", self.instructions_edit)
        editor_layout.addRow("Trigger Code", self.trigger_code_spin)
        editor_layout.addRow("Condition Repeats", self.sequence_count_spin)
        editor_layout.addRow("Cycles / Condition Repeat", self.oddball_cycles_spin)
        editor_layout.addRow("Stimulus Variant", self.variant_combo)
        editor_layout.addRow("Duty Cycle", self.duty_cycle_combo)
        editor_layout.addRow("Template Info", self.template_info_label)
        self.condition_editor_card.body_layout.addLayout(editor_layout)

        self.stimulus_sources_card = SectionCard(
            title="Stimulus Sources & Status",
            subtitle="Review current source folders and import base/oddball sets.",
            object_name="conditions_stimulus_sources_card",
            parent=self,
        )
        stimulus_layout = QGridLayout()
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
        self.stimulus_sources_card.body_layout.addLayout(stimulus_layout)

        self.condition_detail_stack = QWidget(self)
        self.condition_detail_stack.setObjectName("conditions_detail_stack")
        detail_stack_layout = QVBoxLayout(self.condition_detail_stack)
        detail_stack_layout.setContentsMargins(0, 0, 0, 0)
        detail_stack_layout.setSpacing(12)
        detail_stack_layout.addWidget(self.condition_editor_card)
        detail_stack_layout.addWidget(self.stimulus_sources_card)
        detail_stack_layout.addStretch(1)

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
            "Condition edits update the shared project document used by Setup Dashboard and Run / Runtime."
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.shell)

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


class PageContainer(QWidget):
    """Centered page container with bounded width and top-aligned content."""

    def __init__(
        self,
        *,
        width_preset: str = "wide",
        parent=None,
    ) -> None:
        super().__init__(parent)
        if width_preset not in _PAGE_WIDTH_PRESETS:
            raise ValueError(f"Unsupported width_preset: {width_preset}")

        self.width_preset = width_preset
        self.content_frame = QFrame(self)
        self.content_frame.setObjectName("page_container_content_frame")
        self.content_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)

        centered_row = QHBoxLayout()
        centered_row.setContentsMargins(0, 0, 0, 0)
        centered_row.setSpacing(0)
        centered_row.addStretch(1)
        centered_row.addWidget(self.content_frame)
        centered_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(0)
        layout.addLayout(centered_row)
        layout.addStretch(1)

        self.set_width_preset(width_preset)

    def set_width_preset(self, width_preset: str) -> None:
        if width_preset not in _PAGE_WIDTH_PRESETS:
            raise ValueError(f"Unsupported width_preset: {width_preset}")
        self.width_preset = width_preset
        self.content_frame.setMaximumWidth(_PAGE_WIDTH_PRESETS[width_preset])
        self.content_frame.setProperty("pageWidthPreset", width_preset)

    def max_content_width(self) -> int:
        return _PAGE_WIDTH_PRESETS[self.width_preset]


class NonHomePageShell(QWidget):
    """Reusable shell for non-home pages with bounded, top-aligned content."""

    def __init__(
        self,
        *,
        title: str,
        subtitle: str,
        layout_mode: str = "single_column",
        width_preset: str = "wide",
        parent=None,
    ) -> None:
        super().__init__(parent)
        if layout_mode not in {"single_column", "three_column"}:
            raise ValueError(f"Unsupported layout_mode: {layout_mode}")

        self.layout_mode = layout_mode
        self._single_column_layout: QVBoxLayout | None = None
        self._column_layouts: list[QVBoxLayout] = []
        self._footer_widget: QWidget | None = None
        self.page_container = PageContainer(width_preset=width_preset, parent=self)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("non_home_shell_title")
        self.subtitle_label = QLabel(subtitle, self)
        self.subtitle_label.setObjectName("non_home_shell_subtitle")
        self.subtitle_label.setWordWrap(True)

        self.content_frame = QFrame(self.page_container.content_frame)
        self.content_frame.setObjectName("non_home_shell_content_frame")
        self.page_container.content_layout.addWidget(self.title_label)
        self.page_container.content_layout.addWidget(self.subtitle_label)
        self.page_container.content_layout.addWidget(self.content_frame)

        if layout_mode == "single_column":
            single_layout = QVBoxLayout(self.content_frame)
            single_layout.setContentsMargins(0, 0, 0, 0)
            single_layout.setSpacing(12)
            self._single_column_layout = single_layout
        else:
            columns_layout = QHBoxLayout(self.content_frame)
            columns_layout.setContentsMargins(0, 0, 0, 0)
            columns_layout.setSpacing(12)
            for column_name in ("left", "center", "right"):
                column_container = QWidget(self.content_frame)
                column_container.setObjectName(f"non_home_shell_column_{column_name}")
                column_layout = QVBoxLayout(column_container)
                column_layout.setContentsMargins(0, 0, 0, 0)
                column_layout.setSpacing(12)
                columns_layout.addWidget(column_container, 1)
                self._column_layouts.append(column_layout)
            columns_layout.setStretch(0, 3)
            columns_layout.setStretch(1, 4)
            columns_layout.setStretch(2, 3)

        self.footer_strip = QFrame(self)
        self.footer_strip.setObjectName("non_home_shell_footer_strip")
        self.footer_strip.setVisible(False)
        footer_layout = QHBoxLayout(self.footer_strip)
        footer_layout.setContentsMargins(12, 8, 12, 8)
        footer_layout.setSpacing(8)
        self.footer_label = QLabel(self.footer_strip)
        self.footer_label.setObjectName("non_home_shell_footer_label")
        self.footer_label.setWordWrap(True)
        footer_layout.addWidget(self.footer_label, 1)
        self.page_container.content_layout.addWidget(self.footer_strip)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.page_container)

        self.setStyleSheet(
            """
            QLabel#non_home_shell_title {
                font-size: 24px;
                font-weight: 700;
                color: #1f2f44;
            }
            QLabel#non_home_shell_subtitle {
                color: #42566f;
                font-size: 13px;
            }
            QFrame#non_home_shell_footer_strip {
                border: 1px solid #d2dbe7;
                border-radius: 8px;
                background-color: #f8fafd;
            }
            QLabel#non_home_shell_footer_label {
                color: #33485f;
            }
            """
        )

    def add_content_widget(self, widget: QWidget, *, stretch: int = 0) -> None:
        if self._single_column_layout is None:
            raise RuntimeError("add_content_widget is only available in single_column mode.")
        self._single_column_layout.addWidget(widget, stretch)

    def add_column_widget(self, column_index: int, widget: QWidget, *, stretch: int = 0) -> None:
        if self.layout_mode != "three_column":
            raise RuntimeError("add_column_widget is only available in three_column mode.")
        self._column_layouts[column_index].addWidget(widget, stretch)

    def add_column_stretch(self, column_index: int, stretch: int = 1) -> None:
        if self.layout_mode != "three_column":
            raise RuntimeError("add_column_stretch is only available in three_column mode.")
        self._column_layouts[column_index].addStretch(stretch)

    def set_column_stretches(self, left: int, center: int, right: int) -> None:
        if self.layout_mode != "three_column":
            raise RuntimeError("set_column_stretches is only available in three_column mode.")
        columns_layout = self.content_frame.layout()
        assert isinstance(columns_layout, QHBoxLayout)
        columns_layout.setStretch(0, left)
        columns_layout.setStretch(1, center)
        columns_layout.setStretch(2, right)

    def column_count(self) -> int:
        return len(self._column_layouts)

    def set_width_preset(self, width_preset: str) -> None:
        self.page_container.set_width_preset(width_preset)

    def set_footer_text(self, text: str | None) -> None:
        if not text:
            self.footer_label.clear()
            self.footer_strip.setVisible(False)
            return
        self.footer_label.setText(text)
        self.footer_strip.setVisible(True)

    def set_footer_widget(self, widget: QWidget | None) -> None:
        footer_layout = self.footer_strip.layout()
        assert isinstance(footer_layout, QHBoxLayout)
        if self._footer_widget is not None:
            footer_layout.removeWidget(self._footer_widget)
            self._footer_widget.setParent(None)
            self._footer_widget = None
        if widget is None:
            return
        widget.setParent(self.footer_strip)
        footer_layout.insertWidget(0, widget, 1)
        self._footer_widget = widget
        self.footer_strip.setVisible(True)


class SectionCard(QFrame):
    """Reusable section card with optional tooltip affordance."""

    def __init__(
        self,
        *,
        title: str,
        subtitle: str | None = None,
        tooltip_text: str | None = None,
        object_name: str = "section_card",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setProperty("sectionCard", "true")
        if tooltip_text:
            self.setToolTip(tooltip_text)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self.title_label = QLabel(title, self)
        self.title_label.setProperty("sectionCardRole", "title")
        header_layout.addWidget(self.title_label)

        if tooltip_text:
            self.tooltip_badge = QLabel("i", self)
            self.tooltip_badge.setObjectName("section_card_tooltip_badge")
            self.tooltip_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tooltip_badge.setToolTip(tooltip_text)
            self.tooltip_badge.setFixedSize(16, 16)
            header_layout.addWidget(self.tooltip_badge)
        else:
            self.tooltip_badge = None

        header_layout.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        layout.addLayout(header_layout)

        if subtitle:
            self.subtitle_label = QLabel(subtitle, self)
            self.subtitle_label.setProperty("sectionCardRole", "subtitle")
            self.subtitle_label.setWordWrap(True)
            layout.addWidget(self.subtitle_label)
        else:
            self.subtitle_label = None

        self.body_layout = QVBoxLayout()
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(8)
        layout.addLayout(self.body_layout)

        self.setStyleSheet(
            """
            QFrame[sectionCard="true"] {
                border: 1px solid #c7d0dd;
                border-radius: 9px;
                background-color: #f8fafc;
            }
            QLabel[sectionCardRole="title"] {
                font-size: 15px;
                font-weight: 700;
                color: #1f2f44;
            }
            QLabel[sectionCardRole="subtitle"] {
                color: #455a72;
            }
            QLabel#section_card_tooltip_badge {
                border: 1px solid #9fb1c8;
                border-radius: 8px;
                background-color: #eef3f9;
                color: #2c4a69;
                font-size: 11px;
                font-weight: 700;
            }
            """
        )


class SessionStructureEditor(QWidget):
    """Reusable session-structure editor widget."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        object_name_prefix: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._document = document

        self.block_count_spin = QSpinBox(self)
        self.block_count_spin.setObjectName(_prefixed_object_name(object_name_prefix, "block_count_spin"))
        self.block_count_spin.setRange(1, 1000)
        self.block_count_spin.valueChanged.connect(self._apply_session_settings)

        self.session_seed_spin = QSpinBox(self)
        self.session_seed_spin.setObjectName(_prefixed_object_name(object_name_prefix, "session_seed_spin"))
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
        for mode in InterConditionMode:
            self.inter_condition_mode_combo.addItem(_transition_label(mode), userData=mode)
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
        self.continue_key_edit.editingFinished.connect(self._apply_session_settings)

        self.session_card = SectionCard(
            title="Session Structure",
            subtitle="Configure block count, ordering strategy, and inter-condition transitions.",
            object_name=_prefixed_object_name(object_name_prefix, "session_structure_card"),
            parent=self,
        )
        self.session_layout = QFormLayout()
        self.session_layout.setVerticalSpacing(9)
        seed_layout = QHBoxLayout()
        seed_layout.addWidget(self.session_seed_spin, 1)
        seed_layout.addWidget(self.generate_seed_button)
        self.session_layout.addRow("Block count", self.block_count_spin)
        self.session_layout.addRow("Session seed", seed_layout)
        self.session_layout.addRow("", self.randomize_checkbox)
        self.session_layout.addRow("Inter-condition mode", self.inter_condition_mode_combo)
        self.session_layout.addRow("Break seconds", self.break_seconds_spin)
        self.session_layout.addRow("Continue key", self.continue_key_edit)
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
                self.inter_condition_mode_combo.findData(session.inter_condition_mode)
            )
        with QSignalBlocker(self.break_seconds_spin):
            self.break_seconds_spin.setValue(session.inter_condition_break_seconds)
        with QSignalBlocker(self.continue_key_edit):
            self.continue_key_edit.setText(session.continue_key)
        self._update_session_visibility_state()

    def _update_session_visibility_state(self) -> None:
        mode = self.inter_condition_mode_combo.currentData()
        show_break_seconds = mode == InterConditionMode.FIXED_BREAK
        show_continue_key = mode == InterConditionMode.MANUAL_CONTINUE
        _set_form_row_visible(self.session_layout, self.break_seconds_spin, show_break_seconds)
        _set_form_row_visible(self.session_layout, self.continue_key_edit, show_continue_key)
        self.break_seconds_spin.setEnabled(show_break_seconds)
        self.continue_key_edit.setEnabled(show_continue_key)

    def _on_inter_condition_mode_changed(self) -> None:
        self._update_session_visibility_state()
        self._apply_session_settings()

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
        self._update_session_visibility_state()

    def _generate_seed(self) -> None:
        try:
            self._document.generate_new_session_seed()
        except Exception as error:
            _show_error_dialog(self, "Session Seed Error", error)


class SessionStructurePage(QWidget):
    """Session-level settings page."""

    def __init__(self, document: ProjectDocument, parent=None) -> None:
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


class FixationSettingsEditor(QWidget):
    """Reusable fixation-task settings editor."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        schedule_row_behavior: str = "hide",
        parent=None,
    ) -> None:
        super().__init__(parent)
        if schedule_row_behavior not in {"hide", "disable"}:
            raise ValueError(f"Unsupported schedule_row_behavior: {schedule_row_behavior}")
        self._document = document
        self._schedule_row_behavior = schedule_row_behavior

        self.fixation_enabled_checkbox = QCheckBox("Enable fixation color changes per condition", self)
        self.fixation_enabled_checkbox.setObjectName("fixation_enabled_checkbox")
        self.fixation_enabled_checkbox.stateChanged.connect(self._on_fixation_enabled_toggled)

        self.fixation_accuracy_checkbox = QCheckBox(
            "Enable fixation accuracy task",
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

        self.fixation_panel = QFrame(self)
        self.fixation_panel.setObjectName("fixation_settings_panel")
        self.fixation_panel.setMaximumWidth(980)
        fixation_panel_layout = QVBoxLayout(self.fixation_panel)
        fixation_panel_layout.setContentsMargins(18, 16, 18, 16)
        fixation_panel_layout.setSpacing(10)

        panel_title = QLabel("Fixation Cross Task", self.fixation_panel)
        panel_title.setObjectName("fixation_page_title")
        panel_subtitle = QLabel(
            "Configure color-change behavior, timing, response, and appearance.",
            self.fixation_panel,
        )
        panel_subtitle.setObjectName("fixation_page_subtitle")
        panel_subtitle.setWordWrap(True)
        fixation_panel_layout.addWidget(panel_title)
        fixation_panel_layout.addWidget(panel_subtitle)

        fixation_enablement_group = QGroupBox("Task Enablement", self.fixation_panel)
        fixation_enablement_layout = QVBoxLayout(fixation_enablement_group)
        fixation_enablement_layout.setContentsMargins(10, 10, 10, 10)
        fixation_enablement_layout.setSpacing(6)
        fixation_enablement_layout.addWidget(self.fixation_enabled_checkbox)
        fixation_enablement_layout.addWidget(self.fixation_accuracy_checkbox)

        self.fixation_behavior_group = QGroupBox("Behavior", self.fixation_panel)
        self.fixation_behavior_layout = QFormLayout(self.fixation_behavior_group)
        self.fixation_behavior_layout.addRow("Color change schedule", self.target_count_mode_combo)
        self.fixation_behavior_layout.addRow("Changes per condition", self.changes_per_sequence_spin)
        self.fixation_behavior_layout.addRow("Minimum changes", self.target_count_min_spin)
        self.fixation_behavior_layout.addRow("Maximum changes", self.target_count_max_spin)
        self.fixation_behavior_layout.addRow("No immediate repeat", self.no_repeat_count_checkbox)

        self.fixation_timing_group = QGroupBox("Timing", self.fixation_panel)
        fixation_timing_layout = QFormLayout(self.fixation_timing_group)
        fixation_timing_layout.addRow("Color change duration (ms)", self.target_duration_spin)
        fixation_timing_layout.addRow("Minimum gap (ms)", self.min_gap_spin)
        fixation_timing_layout.addRow("Maximum gap (ms)", self.max_gap_spin)

        self.fixation_response_group = QGroupBox("Response", self.fixation_panel)
        fixation_response_layout = QFormLayout(self.fixation_response_group)
        fixation_response_layout.addRow("Response key", self.response_key_edit)
        fixation_response_layout.addRow("Response window (s)", self.response_window_spin)

        self.fixation_appearance_group = QGroupBox("Appearance", self.fixation_panel)
        fixation_appearance_layout = QFormLayout(self.fixation_appearance_group)
        fixation_appearance_layout.addRow("Default color", self.base_color_edit)
        fixation_appearance_layout.addRow("Change color", self.target_color_edit)
        fixation_appearance_layout.addRow("Cross size (px)", self.cross_size_spin)
        fixation_appearance_layout.addRow("Line width (px)", self.line_width_spin)

        feasibility_card = QFrame(self.fixation_panel)
        feasibility_card.setObjectName("fixation_feasibility_card")
        feasibility_card.setToolTip(_FIXATION_FEASIBILITY_TOOLTIP_TEXT)
        feasibility_layout = QVBoxLayout(feasibility_card)
        feasibility_layout.setContentsMargins(10, 8, 10, 8)
        feasibility_layout.setSpacing(4)
        self.fixation_feasibility_label = QLabel(feasibility_card)
        self.fixation_feasibility_label.setObjectName("fixation_feasibility_label")
        self.fixation_feasibility_label.setToolTip(_FIXATION_FEASIBILITY_TOOLTIP_TEXT)
        self.fixation_feasibility_label.setWordWrap(True)
        feasibility_layout.addWidget(self.fixation_feasibility_label)

        fixation_panel_layout.addWidget(fixation_enablement_group)
        fixation_panel_layout.addWidget(self.fixation_behavior_group)
        fixation_panel_layout.addWidget(self.fixation_timing_group)
        fixation_panel_layout.addWidget(self.fixation_response_group)
        fixation_panel_layout.addWidget(self.fixation_appearance_group)
        fixation_panel_layout.addWidget(feasibility_card)

        centered_row = QHBoxLayout()
        centered_row.addStretch(1)
        centered_row.addWidget(self.fixation_panel)
        centered_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        layout.addLayout(centered_row)
        layout.addStretch(1)

        self.setStyleSheet(
            """
            QFrame#fixation_settings_panel {
                border: 1px solid #a8b7c8;
                border-radius: 12px;
                background-color: #e4ebf3;
            }
            QLabel#fixation_page_title {
                font-size: 18px;
                font-weight: 700;
                color: #1f2f44;
            }
            QLabel#fixation_page_subtitle {
                color: #33485f;
            }
            QGroupBox {
                border: 1px solid #c1ccda;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #f7f9fc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                font-weight: 600;
            }
            QFrame#fixation_feasibility_card {
                border: 1px solid #c0cddd;
                border-radius: 8px;
                background-color: #fbfdff;
            }
            QLabel#fixation_feasibility_label {
                color: #233a52;
                font-weight: 600;
            }
            """
        )

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        fixation = self._document.project.settings.fixation_task
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
        self._update_fixation_visibility_state()
        self._refresh_condition_guidance()

    def _update_fixation_visibility_state(self) -> None:
        fixation_enabled = self.fixation_enabled_checkbox.isChecked()
        if not fixation_enabled and self.fixation_accuracy_checkbox.isChecked():
            with QSignalBlocker(self.fixation_accuracy_checkbox):
                self.fixation_accuracy_checkbox.setChecked(False)
        self.fixation_accuracy_checkbox.setEnabled(fixation_enabled)

        for group in (
            self.fixation_behavior_group,
            self.fixation_timing_group,
            self.fixation_appearance_group,
        ):
            group.setVisible(fixation_enabled)
            group.setEnabled(fixation_enabled)

        randomized_mode = self.target_count_mode_combo.currentData() == "randomized"
        if self._schedule_row_behavior == "hide":
            _set_form_row_visible(
                self.fixation_behavior_layout,
                self.changes_per_sequence_spin,
                not randomized_mode,
            )
            _set_form_row_visible(
                self.fixation_behavior_layout,
                self.target_count_min_spin,
                randomized_mode,
            )
            _set_form_row_visible(
                self.fixation_behavior_layout,
                self.target_count_max_spin,
                randomized_mode,
            )
            _set_form_row_visible(
                self.fixation_behavior_layout,
                self.no_repeat_count_checkbox,
                randomized_mode,
            )
        else:
            _set_form_row_visible(self.fixation_behavior_layout, self.changes_per_sequence_spin, True)
            _set_form_row_visible(self.fixation_behavior_layout, self.target_count_min_spin, True)
            _set_form_row_visible(self.fixation_behavior_layout, self.target_count_max_spin, True)
            _set_form_row_visible(
                self.fixation_behavior_layout,
                self.no_repeat_count_checkbox,
                True,
            )
            self.changes_per_sequence_spin.setEnabled(fixation_enabled and not randomized_mode)
            self.target_count_min_spin.setEnabled(fixation_enabled and randomized_mode)
            self.target_count_max_spin.setEnabled(fixation_enabled and randomized_mode)
            self.no_repeat_count_checkbox.setEnabled(fixation_enabled and randomized_mode)

        accuracy_enabled = fixation_enabled and self.fixation_accuracy_checkbox.isChecked()
        self.fixation_response_group.setVisible(accuracy_enabled)
        self.fixation_response_group.setEnabled(accuracy_enabled)

    def _build_compact_feasibility_text(
        self,
        *,
        guidance_rows: list[object] | None,
        guidance_error: Exception | None,
    ) -> str:
        label = "Estimated maximum feasible cross changes per condition"
        if guidance_error is not None:
            return f"{label}: unavailable ({guidance_error})"
        if not guidance_rows:
            return f"{label}: unavailable (add a condition)."
        estimated_values = sorted(
            {row.estimated_max_color_changes_per_condition for row in guidance_rows}
        )
        if len(estimated_values) == 1:
            return f"{label}: {estimated_values[0]}"
        return f"{label}: {estimated_values[0]}-{estimated_values[-1]} (varies by condition)"

    def _refresh_condition_guidance(self) -> None:
        refresh_hz = self._document.project.settings.display.preferred_refresh_hz or 60.0
        guidance_rows: list[object] | None = None
        guidance_error: Exception | None = None
        try:
            guidance_rows = self._document.fixation_guidance(refresh_hz=refresh_hz)
        except Exception as error:
            guidance_error = error
        self.fixation_feasibility_label.setText(
            self._build_compact_feasibility_text(
                guidance_rows=guidance_rows,
                guidance_error=guidance_error,
            )
        )

    def _on_fixation_enabled_toggled(self) -> None:
        self._update_fixation_visibility_state()
        self._apply_fixation_settings()

    def _on_target_count_mode_changed(self) -> None:
        self._update_fixation_visibility_state()
        self._apply_fixation_settings()

    def _on_fixation_accuracy_toggled(self) -> None:
        self._update_fixation_visibility_state()
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


class FixationCrossSettingsPage(FixationSettingsEditor):
    """Fixation-task settings page."""

    def __init__(self, document: ProjectDocument, parent=None) -> None:
        super().__init__(document, schedule_row_behavior="hide", parent=parent)


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

        actions_row = QWidget(self)
        button_layout = QHBoxLayout(actions_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)
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

        self.shell = NonHomePageShell(
            title="Assets / Preprocessing",
            subtitle=(
                "Inspect source folders, refresh derived-asset status, and materialize "
                "project-supported variants."
            ),
            layout_mode="single_column",
            width_preset="wide",
            parent=self,
        )
        self.shell.add_content_widget(supported_variants_group)
        self.shell.add_content_widget(actions_row)
        self.shell.add_content_widget(self.assets_table)
        self.shell.add_content_widget(self.assets_status_text)
        self.shell.set_footer_text(
            "Select a condition-role row to import or refresh assets without changing the outer window size."
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.shell)

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


class RuntimeSettingsEditor(QWidget):
    """Reusable runtime settings editor for refresh/display/serial controls."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        object_name_prefix: str = "",
        fullscreen_state_getter: Callable[[], bool] | None = None,
        fullscreen_state_setter: Callable[[bool], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._fullscreen_state_getter = fullscreen_state_getter
        self._fullscreen_state_setter = fullscreen_state_setter
        self._runtime_background_refresh_guard = False

        self.refresh_hz_spin = QDoubleSpinBox(self)
        self.refresh_hz_spin.setObjectName(
            _prefixed_object_name(object_name_prefix, "refresh_hz_spin")
        )
        self.refresh_hz_spin.setRange(1.0, 500.0)
        self.refresh_hz_spin.setDecimals(2)
        self.refresh_hz_spin.valueChanged.connect(self._apply_refresh_hz)

        self.runtime_background_color_combo = QComboBox(self)
        self.runtime_background_color_combo.setObjectName(
            _prefixed_object_name(object_name_prefix, "runtime_background_color_combo")
        )
        for label, background_hex in _RUNTIME_BACKGROUND_COLOR_PRESETS:
            self.runtime_background_color_combo.addItem(label, userData=background_hex)
        self.runtime_background_color_combo.currentIndexChanged.connect(
            self._apply_runtime_background_color
        )
        self.runtime_background_scope_label = QLabel(
            "Used during FPVS image presentation.",
            self,
        )
        self.runtime_background_scope_label.setObjectName(
            _prefixed_object_name(object_name_prefix, "runtime_background_scope_label")
        )
        self.runtime_background_scope_label.setWordWrap(True)

        self.serial_port_edit = QLineEdit(self)
        self.serial_port_edit.setObjectName(
            _prefixed_object_name(object_name_prefix, "serial_port_edit")
        )
        self.serial_port_edit.setPlaceholderText("COM3")
        self.serial_port_edit.editingFinished.connect(self._apply_serial_settings)

        self.serial_baudrate_spin = QSpinBox(self)
        self.serial_baudrate_spin.setObjectName(
            _prefixed_object_name(object_name_prefix, "serial_baudrate_spin")
        )
        self.serial_baudrate_spin.setRange(1, 2_000_000)
        self.serial_baudrate_spin.setEnabled(False)
        self.serial_baudrate_spin.setToolTip(
            "Baud rate is stored in project settings and shown here for reference."
        )
        self.serial_baudrate_spin.valueChanged.connect(self._apply_serial_settings)

        self.test_mode_checkbox = QCheckBox(
            "Launch the currently supported alpha test-mode path",
            self,
        )
        self.test_mode_checkbox.setObjectName(
            _prefixed_object_name(object_name_prefix, "test_mode_checkbox")
        )
        self.test_mode_checkbox.setChecked(True)
        self.test_mode_checkbox.setEnabled(False)

        self.fullscreen_checkbox = QCheckBox("Present launched playback fullscreen", self)
        self.fullscreen_checkbox.setObjectName(
            _prefixed_object_name(object_name_prefix, "fullscreen_checkbox")
        )
        self.fullscreen_checkbox.stateChanged.connect(self._on_fullscreen_toggled)

        self.card = SectionCard(
            title="Runtime Settings",
            subtitle="Refresh, background, fullscreen, and serial trigger controls.",
            object_name=_prefixed_object_name(object_name_prefix, "runtime_settings_card"),
            parent=self,
        )
        self.form_layout = QFormLayout()
        self.form_layout.addRow("Refresh (Hz)", self.refresh_hz_spin)
        self.form_layout.addRow("Stimulus Background", self.runtime_background_color_combo)
        self.form_layout.addRow("", self.runtime_background_scope_label)
        self.form_layout.addRow("Serial Port", self.serial_port_edit)
        self.form_layout.addRow("Serial Baud Rate", self.serial_baudrate_spin)
        self.form_layout.addRow("", self.test_mode_checkbox)
        self.form_layout.addRow("", self.fullscreen_checkbox)
        self.card.body_layout.addLayout(self.form_layout)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.card)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def current_refresh_hz(self) -> float:
        return self.refresh_hz_spin.value()

    def set_fullscreen_checked(self, checked: bool) -> None:
        with QSignalBlocker(self.fullscreen_checkbox):
            self.fullscreen_checkbox.setChecked(checked)

    def refresh(self) -> None:
        background_color = self._normalized_runtime_background_color()
        preferred_refresh = self._document.project.settings.display.preferred_refresh_hz or 60.0
        with QSignalBlocker(self.refresh_hz_spin):
            self.refresh_hz_spin.setValue(preferred_refresh)
        with QSignalBlocker(self.runtime_background_color_combo):
            selected_index = self.runtime_background_color_combo.findData(background_color)
            if selected_index < 0:
                selected_index = self.runtime_background_color_combo.findData("#000000")
            self.runtime_background_color_combo.setCurrentIndex(selected_index)
        with QSignalBlocker(self.serial_port_edit):
            self.serial_port_edit.setText(self._document.project.settings.triggers.serial_port or "")
        with QSignalBlocker(self.serial_baudrate_spin):
            self.serial_baudrate_spin.setValue(self._document.project.settings.triggers.baudrate)
        target_fullscreen_value = (
            self._fullscreen_state_getter()
            if self._fullscreen_state_getter is not None
            else self.fullscreen_checkbox.isChecked()
        )
        self.set_fullscreen_checked(target_fullscreen_value)

    def _normalized_runtime_background_color(self) -> str:
        background_color = self._document.project.settings.display.background_color
        if isinstance(background_color, str):
            canonical_preset = _canonical_runtime_background_hex(background_color)
            if canonical_preset is not None:
                return canonical_preset

        if self._runtime_background_refresh_guard:
            return "#000000"

        self._runtime_background_refresh_guard = True
        try:
            self._document.update_display_settings(background_color="#000000")
        finally:
            self._runtime_background_refresh_guard = False
        return "#000000"

    def _apply_refresh_hz(self) -> None:
        try:
            self._document.update_display_settings(preferred_refresh_hz=self.refresh_hz_spin.value())
        except Exception as error:
            _show_error_dialog(self, "Refresh Setting Error", error)
            self.refresh()

    def _apply_runtime_background_color(self) -> None:
        selected_background_color = self.runtime_background_color_combo.currentData()
        if not isinstance(selected_background_color, str):
            return
        try:
            self._document.update_display_settings(background_color=selected_background_color)
        except Exception as error:
            _show_error_dialog(self, "Display Settings Error", error)
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

    def _on_fullscreen_toggled(self) -> None:
        if self._fullscreen_state_setter is not None:
            self._fullscreen_state_setter(self.fullscreen_checkbox.isChecked())


class AssetsReadinessEditor(QWidget):
    """Compact assets readiness snapshot and actions."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        object_name_prefix: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._variant_checkboxes: dict[StimulusVariant, QCheckBox] = {}

        self.card = SectionCard(
            title="Assets Readiness",
            subtitle="Supported variants, inspection status, and materialization actions.",
            object_name=_prefixed_object_name(object_name_prefix, "assets_readiness_card"),
            parent=self,
        )

        variants_row = QWidget(self.card)
        variants_layout = QHBoxLayout(variants_row)
        variants_layout.setContentsMargins(0, 0, 0, 0)
        variants_layout.setSpacing(8)
        for variant in StimulusVariant:
            checkbox = QCheckBox(_variant_label(variant), variants_row)
            checkbox.setObjectName(
                _prefixed_object_name(object_name_prefix, f"variant_checkbox_{variant.value}")
            )
            checkbox.stateChanged.connect(self._apply_supported_variants)
            if variant == StimulusVariant.ORIGINAL:
                checkbox.setEnabled(False)
            self._variant_checkboxes[variant] = checkbox
            variants_layout.addWidget(checkbox)

        self.condition_rows_value = QLabel(self.card)
        self.condition_rows_value.setObjectName(
            _prefixed_object_name(object_name_prefix, "assets_condition_rows_value")
        )
        self.manifest_status_value = QLabel(self.card)
        self.manifest_status_value.setObjectName(
            _prefixed_object_name(object_name_prefix, "assets_manifest_status_value")
        )
        self.manifest_status_value.setWordWrap(True)
        self.materialization_status_value = QLabel(self.card)
        self.materialization_status_value.setObjectName(
            _prefixed_object_name(object_name_prefix, "assets_materialization_status_value")
        )
        self.materialization_status_value.setWordWrap(True)

        self.refresh_button = QPushButton("Refresh Inspection", self.card)
        self.refresh_button.setObjectName(
            _prefixed_object_name(object_name_prefix, "assets_refresh_button")
        )
        self.refresh_button.clicked.connect(self._refresh_inspection)
        self.materialize_button = QPushButton("Materialize Supported Variants", self.card)
        self.materialize_button.setObjectName(
            _prefixed_object_name(object_name_prefix, "materialize_assets_button")
        )
        self.materialize_button.clicked.connect(self._materialize_assets)

        actions_row = QWidget(self.card)
        actions_layout = QHBoxLayout(actions_row)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.addWidget(self.refresh_button)
        actions_layout.addWidget(self.materialize_button)

        self.card.body_layout.addWidget(variants_row)
        self.card.body_layout.addWidget(self.condition_rows_value)
        self.card.body_layout.addWidget(self.manifest_status_value)
        self.card.body_layout.addWidget(self.materialization_status_value)
        self.card.body_layout.addWidget(actions_row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.card)

        self._document.project_changed.connect(self.refresh)
        self._document.manifest_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        supported_variants = set(self._document.project.settings.supported_variants)
        for variant, checkbox in self._variant_checkboxes.items():
            with QSignalBlocker(checkbox):
                checkbox.setChecked(variant in supported_variants)

        rows = self._document.condition_rows()
        self.condition_rows_value.setText(f"Condition stimulus rows: {len(rows)}")
        manifest = self._document.manifest
        if manifest is None:
            self.manifest_status_value.setText("Manifest status: no manifest loaded yet.")
        else:
            self.manifest_status_value.setText(
                "Manifest status: "
                f"{len(manifest.sets)} set(s), generated {manifest.generated_at.isoformat()}."
            )
        refresh_hz = self._document.project.settings.display.preferred_refresh_hz or 60.0
        validation = self._document.validation_report(refresh_hz=refresh_hz)
        issue_count = len(validation.issues)
        if issue_count == 0:
            self.materialization_status_value.setText(
                "Materialization readiness: clear validation checks."
            )
        else:
            self.materialization_status_value.setText(
                f"Materialization readiness: {issue_count} validation issue(s) need attention."
            )

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

    def _refresh_inspection(self) -> None:
        try:
            self._run_with_progress(
                "Refreshing source inspection...",
                self._document.refresh_stimulus_inspection,
            )
        except Exception as error:
            _show_error_dialog(self, "Inspection Error", error)

    def _materialize_assets(self) -> None:
        try:
            self._run_with_progress(
                "Materializing project assets...",
                self._document.materialize_assets,
            )
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


class SetupDashboardPage(QWidget):
    """Curated setup dashboard that surfaces key controls across tabs."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        load_condition_template_profiles: Callable[[], list[ConditionTemplateProfile]],
        manage_condition_templates: Callable[[], list[ConditionTemplateProfile]],
        fullscreen_state_getter: Callable[[], bool] | None = None,
        fullscreen_state_setter: Callable[[bool], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.shell = NonHomePageShell(
            title="Setup Dashboard",
            subtitle=(
                "Configure project metadata, session structure, fixation behavior, runtime, "
                "and asset readiness from one view."
            ),
            layout_mode="three_column",
            width_preset="wide",
            parent=self,
        )
        self.shell.set_column_stretches(3, 4, 3)
        self.shell.set_footer_text(
            "Setup changes here update the shared project state used by Home and Run / Runtime."
        )

        self.project_overview_editor = ProjectOverviewEditor(
            document,
            load_condition_template_profiles=load_condition_template_profiles,
            manage_condition_templates=manage_condition_templates,
            parent=self.shell,
        )
        self.session_structure_editor = SessionStructureEditor(
            document,
            object_name_prefix="dashboard_",
            parent=self.shell,
        )
        self.fixation_settings_editor = FixationSettingsEditor(
            document,
            schedule_row_behavior="disable",
            parent=self.shell,
        )
        self.runtime_settings_editor = RuntimeSettingsEditor(
            document,
            object_name_prefix="dashboard_",
            fullscreen_state_getter=fullscreen_state_getter,
            fullscreen_state_setter=fullscreen_state_setter,
            parent=self.shell,
        )
        self.assets_readiness_editor = AssetsReadinessEditor(
            document,
            object_name_prefix="dashboard_",
            parent=self.shell,
        )

        self.shell.add_column_widget(0, self.project_overview_editor)
        self.shell.add_column_widget(0, self.session_structure_editor)
        self.shell.add_column_widget(1, self.fixation_settings_editor)
        self.shell.add_column_widget(2, self.runtime_settings_editor)
        self.shell.add_column_widget(2, self.assets_readiness_editor)
        self.shell.add_column_stretch(0)
        self.shell.add_column_stretch(1)
        self.shell.add_column_stretch(2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.shell)

    def sync_fullscreen_checkbox(self, checked: bool) -> None:
        self.runtime_settings_editor.set_fullscreen_checked(checked)


class RunPage(QWidget):
    """Session compile and launch page with detailed runtime diagnostics."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        fullscreen_state_getter: Callable[[], bool] | None = None,
        fullscreen_state_setter: Callable[[bool], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._document = document

        self.runtime_settings_editor = RuntimeSettingsEditor(
            document,
            fullscreen_state_getter=fullscreen_state_getter,
            fullscreen_state_setter=fullscreen_state_setter,
            parent=self,
        )
        self.refresh_hz_spin = self.runtime_settings_editor.refresh_hz_spin
        self.runtime_background_color_combo = self.runtime_settings_editor.runtime_background_color_combo
        self.runtime_background_scope_label = self.runtime_settings_editor.runtime_background_scope_label
        self.serial_port_edit = self.runtime_settings_editor.serial_port_edit
        self.serial_baudrate_spin = self.runtime_settings_editor.serial_baudrate_spin
        self.test_mode_checkbox = self.runtime_settings_editor.test_mode_checkbox
        self.fullscreen_checkbox = self.runtime_settings_editor.fullscreen_checkbox

        self.display_index_edit = QLineEdit(self)
        self.display_index_edit.setObjectName("display_index_edit")
        self.display_index_edit.setPlaceholderText("Leave blank for default display")

        self.engine_name_value = QLabel("psychopy", self)
        self.engine_name_value.setObjectName("engine_name_value")

        display_card = SectionCard(
            title="Display & Engine",
            subtitle="Display index remains editable only on this dedicated Run / Runtime page.",
            object_name="run_display_card",
            parent=self,
        )
        display_layout = QFormLayout()
        display_layout.setVerticalSpacing(10)
        display_layout.addRow("Display Index", self.display_index_edit)
        display_layout.addRow("Engine", self.engine_name_value)
        display_card.body_layout.addLayout(display_layout)

        self.compile_button = QPushButton("Preview Session Plan", self)
        self.compile_button.setObjectName("compile_session_button")
        self.compile_button.clicked.connect(self.compile_session)
        self.launch_button = QPushButton("Launch Experiment", self)
        self.launch_button.setObjectName("launch_test_session_button")
        self.launch_button.setProperty("launchActionRole", "primary")
        self.launch_button.setToolTip(
            "Launch Experiment on the current alpha test-mode runtime path."
        )
        self.launch_button.clicked.connect(self.launch_test_session)

        button_row = QWidget(self)
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)
        button_layout.addWidget(self.compile_button)
        button_layout.addWidget(self.launch_button)
        button_layout.addStretch(1)

        controls_card = SectionCard(
            title="Run Controls",
            subtitle="Preview the session plan or launch from this page.",
            object_name="run_controls_card",
            parent=self,
        )
        controls_card.body_layout.addWidget(button_row)

        self.summary_text = QPlainTextEdit(self)
        self.summary_text.setObjectName("session_summary_text")
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumBlockCount(500)
        self.summary_text.setPlaceholderText(
            "Preview the session plan or launch to populate runtime diagnostics."
        )

        summary_card = SectionCard(
            title="Session Summary & Runtime Feedback",
            subtitle="Detailed session-preview and launch diagnostics for the current project.",
            object_name="run_summary_card",
            parent=self,
        )
        summary_card.body_layout.addWidget(self.summary_text)

        self.readiness_badge = QLabel("Status: Setup Required", self)
        self.readiness_badge.setObjectName("run_readiness_badge")
        self.readiness_badge.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.readiness_badge.setWordWrap(True)
        self.readiness_badge.setMinimumHeight(34)
        self.readiness_badge.setProperty("readinessRole", "compact")

        self.readiness_summary_value = QLabel("Not computed yet.", self)
        self.readiness_summary_value.setObjectName("run_readiness_summary_value")
        self.readiness_summary_value.setWordWrap(True)
        self.readiness_summary_value.setMinimumHeight(24)

        self.readiness_checklist = QListWidget(self)
        self.readiness_checklist.setObjectName("run_readiness_checklist")
        _configure_read_only_list(self.readiness_checklist)

        readiness_card = SectionCard(
            title="Launch Readiness",
            subtitle="Validation, asset checks, and launch prerequisites.",
            object_name="run_readiness_card",
            parent=self,
        )
        readiness_card.body_layout.addWidget(self.readiness_badge)
        readiness_card.body_layout.addWidget(self.readiness_summary_value)
        readiness_card.body_layout.addWidget(self.readiness_checklist, 1)

        self.shell = NonHomePageShell(
            title="Run / Runtime",
            subtitle="Preview the session plan and launch with detailed runtime feedback.",
            layout_mode="three_column",
            width_preset="medium",
            parent=self,
        )
        self.shell.add_column_widget(0, self.runtime_settings_editor)
        self.shell.add_column_widget(1, controls_card)
        self.shell.add_column_widget(1, summary_card, stretch=1)
        self.shell.add_column_widget(2, readiness_card)
        self.shell.add_column_widget(2, display_card, stretch=1)
        self.shell.set_footer_text(
            "Display index and runtime settings are available only on this page."
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.shell)

        self._document.project_changed.connect(self.refresh)
        self._document.session_plan_changed.connect(self._refresh_summary)
        self.refresh()

    def current_refresh_hz(self) -> float:
        return self.runtime_settings_editor.current_refresh_hz()

    def sync_fullscreen_checkbox(self, checked: bool) -> None:
        self.runtime_settings_editor.set_fullscreen_checked(checked)

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

    def _status_report(self) -> LauncherReadinessReport:
        return _launcher_readiness_report(
            self._document,
            refresh_hz=self.current_refresh_hz(),
        )

    def refresh(self) -> None:
        self.runtime_settings_editor.refresh()
        self._refresh_summary()

    def compile_session(self) -> None:
        try:
            session_plan = self._document.compile_session(refresh_hz=self.current_refresh_hz())
        except Exception as error:
            _show_error_dialog(self, "Compile Error", error)
            return
        self._set_summary(
            session_plan,
            extra_lines=["Status: session preview refreshed."],
        )

    def preflight_session(self) -> None:
        try:
            session_plan = self._document.prepare_test_session_launch(
                refresh_hz=self.current_refresh_hz()
            )
        except Exception as error:
            _show_error_dialog(self, "Preflight Error", error)
            return
        self._set_summary(
            session_plan,
            extra_lines=["Status: launch checks passed."],
        )
        QMessageBox.information(
            self,
            "Preflight Passed",
            "Preflight succeeded for the current test-mode session launch.",
        )

    def launch_test_session(self) -> None:
        try:
            refresh_hz = self.current_refresh_hz()
            session_plan = self._document.prepare_test_session_launch(refresh_hz=refresh_hz)
            display_index = self.current_display_index()
        except Exception as error:
            _show_error_dialog(self, "Launch Blocked", error)
            return
        self._set_summary(
            session_plan,
            extra_lines=["Status: launch checks passed."],
        )

        participant_number = self._collect_launch_participant_number()
        if participant_number is None:
            return
        try:
            self._show_launch_interstitial()
            summary = self._document.launch_compiled_session(
                session_plan,
                participant_number=participant_number,
                display_index=display_index,
                fullscreen=self.fullscreen_checkbox.isChecked(),
            )
        except Exception as error:
            _show_error_dialog(self, "Launch Error", error)
            return
        output_dir = summary.output_dir or "runs/..."
        participant_value = summary.participant_number or participant_number
        if summary.aborted:
            abort_reason = summary.abort_reason or "No abort reason was provided."
            extra_lines = [
                "Status: runtime launch aborted.",
                f"Participant Number: {participant_value}",
                f"Output Dir: {output_dir}",
                f"Abort Reason: {abort_reason}",
                (
                    "Completed Conditions: "
                    f"{summary.completed_condition_count}/{summary.total_condition_count}"
                ),
            ]
            self._set_summary(session_plan, extra_lines=extra_lines)
            QMessageBox.warning(
                self,
                "Launch Aborted",
                "The experiment aborted on the current alpha test-mode path.\n\n"
                f"Reason: {abort_reason}\n"
                "Completed Conditions: "
                f"{summary.completed_condition_count}/{summary.total_condition_count}\n"
                f"Output Dir: {output_dir}\n\n"
                "Review run exports in the project runs folder.",
            )
            return
        extra_lines = [
            "Status: runtime launch completed.",
            f"Participant Number: {participant_value}",
            f"Output Dir: {output_dir}",
        ]
        self._set_summary(session_plan, extra_lines=extra_lines)
        QMessageBox.information(
            self,
            "Launch Complete",
            "The experiment finished on the current alpha test-mode path. "
            "Review run exports in the project runs folder.",
        )

    def _show_launch_interstitial(self) -> None:
        dialog = QProgressDialog("Launching experiment: Please wait", "", 0, 0, self)
        dialog.setWindowTitle("FPVS Studio")
        dialog.setCancelButton(None)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.show()
        QApplication.processEvents()
        try:
            if _LAUNCH_INTERSTITIAL_DURATION_MS > 0:
                loop = QEventLoop(self)
                QTimer.singleShot(_LAUNCH_INTERSTITIAL_DURATION_MS, loop.quit)
                loop.exec()
        finally:
            dialog.close()

    def _prompt_participant_number(self) -> str | None:
        dialog = ParticipantNumberDialog(self)
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return dialog.participant_number

    def _collect_launch_participant_number(self) -> str | None:
        while True:
            participant_number = self._prompt_participant_number()
            if participant_number is None:
                return None

            if not self._document.has_completed_session_for_participant(participant_number):
                return participant_number

            warning_text = (
                f"Warning: logs indicate that {participant_number} has already completed this study, "
                f"but you entered {participant_number}. Do you wish to overwrite the existing data?"
            )
            answer = QMessageBox.question(
                self,
                "Participant Already Completed",
                warning_text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                return participant_number

    def _refresh_summary(self) -> None:
        self._refresh_readiness_panel()
        session_plan = self._document.last_session_plan
        if session_plan is None:
            validation = self._document.validation_report(refresh_hz=self.current_refresh_hz())
            if validation.issues:
                lines = [f"- {issue.message}" for issue in validation.issues]
                self.summary_text.setPlainText("\n".join(lines))
                return
            self.summary_text.clear()
            return
        self._set_summary(session_plan)

    def _refresh_readiness_panel(self) -> None:
        report = self._status_report()
        self.readiness_badge.setText(f"Status: {report.status_label}")
        _set_widget_property(self.readiness_badge, "readinessState", report.badge_state)
        summary_text = report.status_summary
        if report.preview_note:
            summary_text = f"{summary_text} {report.preview_note}"
        self.readiness_summary_value.setText(summary_text)
        _set_list_items(self.readiness_checklist, report.readiness_items)

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
        self._refresh_readiness_panel()


class HomePage(QWidget):
    """Launcher-oriented overview page for the current project."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        load_condition_template_profiles: Callable[[], list[ConditionTemplateProfile]],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._load_condition_template_profiles = load_condition_template_profiles
        self.setObjectName("home_page")
        self.page_container = PageContainer(width_preset="narrow", parent=self)

        self.current_project_header = QLabel(self)
        self.current_project_header.setObjectName("home_current_project_header")

        self.current_project_subtitle = QLabel(
            "Open a project, confirm its identity, and launch quickly.",
            self,
        )
        self.current_project_subtitle.setObjectName("home_current_project_subtitle")
        self.current_project_subtitle.setWordWrap(True)

        self.open_project_button = QPushButton("Open Project", self)
        self.open_project_button.setObjectName("home_open_project_button")
        self.launch_button = QPushButton("Launch Experiment", self)
        self.launch_button.setObjectName("home_launch_test_session_button")
        self.launch_button.setProperty("launchActionRole", "primary")
        self.launch_button.setProperty("homeActionRole", "primary")
        self.save_project_button = QPushButton("Save", self)
        self.save_project_button.setObjectName("home_save_project_button")
        self.new_project_button = QPushButton("Create New Project", self)
        self.new_project_button.setObjectName("home_create_project_button")

        for button in (
            self.open_project_button,
            self.new_project_button,
            self.save_project_button,
            self.launch_button,
        ):
            button.setMinimumHeight(38)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)
        action_layout.addWidget(self.open_project_button)
        action_layout.addWidget(self.new_project_button)
        action_layout.addWidget(self.save_project_button)
        action_layout.addWidget(self.launch_button)

        project_card = SectionCard(
            title="Project Info",
            subtitle="Project identity and template settings.",
            object_name="home_project_card",
            parent=self,
        )
        project_layout = QFormLayout()
        project_layout.setContentsMargins(0, 0, 0, 0)
        project_layout.setVerticalSpacing(6)
        project_layout.setHorizontalSpacing(12)
        self.project_name_value = self._new_value_label(
            "home_project_name_value",
            role="primary",
        )
        self.project_root_value = self._new_value_label(
            "home_project_root_value",
            selectable=True,
        )
        self.project_template_value = self._new_value_label("home_project_template_value")
        self.project_description_value = self._new_value_label("home_project_description_value")
        self._add_summary_row(project_layout, "Project Name", self.project_name_value)
        self._add_summary_row(project_layout, "Description", self.project_description_value)
        self._add_summary_row(project_layout, "Template", self.project_template_value)
        self._add_summary_row(project_layout, "Root Path", self.project_root_value)
        project_card.layout().setContentsMargins(12, 10, 12, 10)
        project_card.layout().setSpacing(6)
        project_card.body_layout.setSpacing(6)
        project_card.body_layout.addLayout(project_layout)

        session_card = SectionCard(
            title="Session Summary",
            subtitle="Compact launch essentials.",
            object_name="home_session_card",
            parent=self,
        )
        session_layout = QFormLayout()
        session_layout.setContentsMargins(0, 0, 0, 0)
        session_layout.setVerticalSpacing(6)
        session_layout.setHorizontalSpacing(12)
        self.condition_count_value = self._new_value_label(
            "home_condition_count_value",
            role="primary",
        )
        self.block_count_value = self._new_value_label(
            "home_block_count_value",
            role="primary",
        )
        self.session_randomization_value = self._new_value_label("home_session_randomization_value")
        self.fixation_task_value = self._new_value_label("home_fixation_task_value")
        self.accuracy_task_value = self._new_value_label("home_accuracy_task_value")
        self._add_summary_row(session_layout, "Condition Count", self.condition_count_value)
        self._add_summary_row(session_layout, "Block Count", self.block_count_value)
        self._add_summary_row(session_layout, "Order Strategy", self.session_randomization_value)
        self._add_summary_row(session_layout, "Fixation Task", self.fixation_task_value)
        self._add_summary_row(session_layout, "Accuracy Task", self.accuracy_task_value)
        session_card.layout().setContentsMargins(12, 10, 12, 10)
        session_card.layout().setSpacing(6)
        session_card.body_layout.setSpacing(6)
        session_card.body_layout.addLayout(session_layout)

        self.launch_status_label = QLabel("Status: Setup Required", self)
        self.launch_status_label.setObjectName("home_launch_status_indicator")
        self.launch_status_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.launch_status_label.setWordWrap(False)
        self.launch_status_label.setMinimumHeight(28)

        status_card = SectionCard(
            title="Launch Readiness",
            subtitle="Single-line launch state.",
            object_name="home_status_card",
            parent=self,
        )
        status_card.layout().setContentsMargins(12, 10, 12, 10)
        status_card.layout().setSpacing(6)
        status_card.body_layout.setSpacing(4)
        status_card.body_layout.addWidget(self.launch_status_label)

        cards_grid = QGridLayout()
        cards_grid.setContentsMargins(0, 0, 0, 0)
        cards_grid.setHorizontalSpacing(10)
        cards_grid.setVerticalSpacing(10)
        cards_grid.addWidget(project_card, 0, 0)
        cards_grid.addWidget(session_card, 0, 1)
        cards_grid.addWidget(status_card, 1, 0, 1, 2)
        cards_grid.setColumnStretch(0, 3)
        cards_grid.setColumnStretch(1, 3)

        page_layout = self.page_container.content_layout
        page_layout.addWidget(self.current_project_header)
        page_layout.addWidget(self.current_project_subtitle)
        page_layout.addLayout(action_layout)
        page_layout.addLayout(cards_grid)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.page_container)

        self.setStyleSheet(
            """
            QWidget#home_page {
                color: #243447;
                font-size: 13px;
            }
            QLabel#home_current_project_header {
                font-size: 26px;
                font-weight: 700;
            }
            QLabel#home_current_project_subtitle {
                font-size: 13px;
                color: #495869;
            }
            QLabel[homeFieldLabel="true"] {
                color: #4c5d73;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel[homeValueRole="primary"] {
                color: #1f2f44;
                font-size: 15px;
                font-weight: 600;
            }
            QLabel[homeValueRole="secondary"] {
                color: #2f435b;
                font-size: 13px;
            }
            QPushButton#home_create_project_button,
            QPushButton#home_open_project_button,
            QPushButton#home_save_project_button,
            QPushButton#home_launch_test_session_button {
                font-size: 14px;
                padding: 7px 12px;
            }
            QPushButton[launchActionRole="primary"],
            QPushButton[homeActionRole="primary"] {
                font-weight: 700;
            }
            QLabel#home_launch_status_indicator {
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#home_launch_status_indicator[readinessState="ready"] {
                background-color: #dcfce7;
                border: 1px solid #86efac;
                color: #166534;
            }
            QLabel#home_launch_status_indicator[readinessState="warning"] {
                background-color: #ffedd5;
                border: 1px solid #fdba74;
                color: #9a3412;
            }
            QLabel#home_launch_status_indicator[readinessState="info"] {
                background-color: #e0f2fe;
                border: 1px solid #7dd3fc;
                color: #0c4a6e;
            }
            QLabel#home_launch_status_indicator[readinessState="pending"] {
                background-color: #f1f5f9;
                border: 1px solid #cbd5e1;
                color: #475569;
            }
            """
        )

        self._document.project_changed.connect(self.refresh)
        self._document.session_plan_changed.connect(self.refresh)
        self.refresh()

    def bind_quick_actions(
        self,
        *,
        new_project_action: QAction,
        open_project_action: QAction,
        save_project_action: QAction,
        launch_action: QAction,
    ) -> None:
        self._bind_button_to_action(
            self.new_project_button,
            new_project_action,
            "Create New Project",
        )
        self._bind_button_to_action(
            self.open_project_button,
            open_project_action,
            "Open Project",
        )
        self._bind_button_to_action(self.save_project_button, save_project_action, "Save")
        self._bind_button_to_action(
            self.launch_button,
            launch_action,
            "Launch Experiment",
        )

    def refresh(self) -> None:
        project = self._document.project
        session_settings = project.settings.session
        fixation_settings = project.settings.fixation_task
        ordered_conditions = self._document.ordered_conditions()
        report = self._status_report()

        self.current_project_header.setText(project.meta.name)
        self.current_project_subtitle.setText(
            "Open a project, confirm its identity, and launch quickly."
        )
        self.project_name_value.setText(project.meta.name)
        self.project_root_value.setText(str(self._document.project_root))
        self.project_template_value.setText(self._condition_template_summary_text())
        self.project_description_value.setText(
            self._project_description_text(project.meta.description)
        )

        self.condition_count_value.setText(str(len(ordered_conditions)))
        self.block_count_value.setText(str(session_settings.block_count))
        self.session_randomization_value.setText(self._session_order_text())
        self.fixation_task_value.setText("Enabled" if fixation_settings.enabled else "Disabled")
        self.accuracy_task_value.setText(
            "Enabled" if fixation_settings.accuracy_task_enabled else "Disabled"
        )
        self._set_status_indicator(report)

    def _status_report(self) -> LauncherReadinessReport:
        return _launcher_readiness_report(
            self._document,
            refresh_hz=self._status_refresh_hz(),
        )

    def _status_refresh_hz(self) -> float:
        preferred_refresh = self._document.project.settings.display.preferred_refresh_hz
        return float(preferred_refresh if preferred_refresh is not None else 60.0)

    @staticmethod
    def _project_description_text(description: str) -> str:
        compact = " ".join(description.split())
        if not compact:
            return "No description set yet."
        if len(compact) > 160:
            compact = f"{compact[:157]}..."
        return compact

    def _condition_template_summary_text(self) -> str:
        profile_id = self._document.project.settings.condition_profile_id
        if profile_id is None:
            return "No template selected"
        profiles_by_id = {
            profile.profile_id: profile
            for profile in self._load_condition_template_profiles()
        }
        profile = profiles_by_id.get(profile_id)
        if profile is None:
            return f"Missing template: {profile_id}"
        return profile.display_name

    def _set_status_indicator(self, report: LauncherReadinessReport) -> None:
        self.launch_status_label.setText(f"Status: {report.status_label}")
        _set_widget_property(
            self.launch_status_label,
            "readinessState",
            report.badge_state,
        )
        self.launch_status_label.setToolTip(report.status_summary)

    def _add_summary_row(
        self,
        layout: QFormLayout,
        label_text: str,
        value_widget: QWidget,
    ) -> None:
        row_label = QLabel(label_text, self)
        row_label.setProperty("homeFieldLabel", "true")
        row_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addRow(row_label, value_widget)

    def _new_value_label(
        self,
        object_name: str,
        *,
        role: str = "secondary",
        selectable: bool = False,
    ) -> QLabel:
        label = QLabel(self)
        label.setObjectName(object_name)
        label.setProperty("homeValueRole", role)
        label.setWordWrap(True)
        if selectable:
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    @staticmethod
    def _bind_button_to_action(button: QPushButton, action: QAction, label: str) -> None:
        button.setText(label)
        if action.toolTip():
            button.setToolTip(action.toolTip())
        if action.statusTip():
            button.setStatusTip(action.statusTip())
        button.clicked.connect(lambda _checked=False, target=action: target.trigger())

    def _session_order_text(self) -> str:
        ordered_conditions = self._document.ordered_conditions()
        if not ordered_conditions:
            return "No conditions configured yet."

        if (
            self._document.project.settings.session.randomize_conditions_per_block
            and len(ordered_conditions) > 1
        ):
            return "Randomized within each block."
        return "Fixed project order."
class StudioMainWindow(QMainWindow):
    """Main window hosting the Phase 5 authoring tabs."""

    def __init__(
        self,
        *,
        document: ProjectDocument,
        on_request_new_project: Callable[[], None],
        on_request_open_project: Callable[[], None],
        on_request_settings: Callable[[], None],
        on_load_condition_template_profiles: Callable[[], list[ConditionTemplateProfile]],
        on_manage_condition_templates: Callable[[], list[ConditionTemplateProfile]],
    ) -> None:
        super().__init__()
        self.document = document
        self._on_request_new_project = on_request_new_project
        self._on_request_open_project = on_request_open_project
        self._on_request_settings = on_request_settings
        self.setWindowTitle("FPVS Studio (Alpha)")
        self.resize(1200, 860)

        self.conditions_page = ConditionsPage(document, self)
        self.session_structure_page = SessionStructurePage(document, self)
        self.fixation_cross_settings_page = FixationCrossSettingsPage(document, self)
        self.assets_page = AssetsPage(document, self)
        self._runtime_fullscreen_ui_state = True
        self.run_page = RunPage(
            document,
            fullscreen_state_getter=self._runtime_fullscreen_state,
            fullscreen_state_setter=self._set_runtime_fullscreen_state,
            parent=self,
        )
        self.setup_dashboard_page = SetupDashboardPage(
            document,
            load_condition_template_profiles=on_load_condition_template_profiles,
            manage_condition_templates=on_manage_condition_templates,
            fullscreen_state_getter=self._runtime_fullscreen_state,
            fullscreen_state_setter=self._set_runtime_fullscreen_state,
            parent=self,
        )
        self.home_page = HomePage(
            document,
            load_condition_template_profiles=on_load_condition_template_profiles,
            parent=self,
        )

        self.main_tabs = QTabWidget(self)
        self.main_tabs.setObjectName("main_tabs")
        self.main_tabs.setTabBar(AnimatedTabBar(self.main_tabs))
        self.main_tabs.addTab(self.home_page, "Home")
        self.main_tabs.addTab(self.setup_dashboard_page, "Setup Dashboard")
        self.main_tabs.addTab(self.conditions_page, "Conditions")
        self.main_tabs.addTab(self.assets_page, "Assets / Preprocessing")
        self.main_tabs.addTab(self.run_page, "Run / Runtime")
        self.setCentralWidget(self.main_tabs)
        self._apply_chrome_styles()

        self.setStatusBar(QStatusBar(self))
        self.alpha_status_label = QLabel("Alpha: test-mode runtime path only", self)
        self.alpha_status_label.setObjectName("alpha_runtime_status_label")
        self.alpha_status_label.setToolTip(
            "Runtime launch currently supports the alpha test-mode path only (test_mode=True)."
        )
        self.statusBar().addPermanentWidget(self.alpha_status_label)
        self._create_actions()
        self.home_page.bind_quick_actions(
            new_project_action=self.new_project_action,
            open_project_action=self.open_project_action,
            save_project_action=self.save_project_action,
            launch_action=self.launch_action,
        )
        self._create_menu_and_toolbar()
        self._button_hover_animators: list[ButtonHoverAnimator] = []
        self._install_button_hover_animations()
        self._wire_document()
        self._update_window_title()

    def _wire_document(self) -> None:
        self.document.project_changed.connect(self._update_window_title)
        self.document.dirty_changed.connect(self._update_window_title)
        self.document.saved.connect(lambda: self.statusBar().showMessage("Project saved.", 3000))

    def _runtime_fullscreen_state(self) -> bool:
        return self._runtime_fullscreen_ui_state

    def _set_runtime_fullscreen_state(self, checked: bool) -> None:
        checked_bool = bool(checked)
        if self._runtime_fullscreen_ui_state == checked_bool:
            return
        self._runtime_fullscreen_ui_state = checked_bool
        self.run_page.sync_fullscreen_checkbox(checked_bool)
        self.setup_dashboard_page.sync_fullscreen_checkbox(checked_bool)
        self.home_page.refresh()

    def _apply_chrome_styles(self) -> None:
        self.setStyleSheet(
            """
            QTabWidget#main_tabs::pane {
                border: 1px solid #c5cfdb;
                background-color: #ffffff;
                top: -1px;
            }
            QPushButton {
                border: 1px solid #c3d0de;
                border-radius: 8px;
                background-color: #f8fafc;
                padding: 6px 12px;
                color: #243447;
            }
            QPushButton:hover {
                border-color: #a8bad2;
                background-color: #ecf2fa;
            }
            QPushButton:pressed {
                border-color: #94aac6;
                background-color: #dfe8f5;
            }
            QPushButton:disabled {
                border-color: #d4dbe6;
                background-color: #f1f4f8;
                color: #8a97a8;
            }
            QPushButton[launchActionRole="primary"] {
                border-color: #1d4ed8;
                background-color: #2563eb;
                color: #ffffff;
                font-weight: 600;
                padding-left: 14px;
                padding-right: 14px;
            }
            QPushButton[launchActionRole="primary"]:hover {
                border-color: #1e40af;
                background-color: #1d4ed8;
            }
            QPushButton[launchActionRole="primary"]:pressed {
                border-color: #1e3a8a;
                background-color: #1e40af;
            }
            QPushButton[launchActionRole="primary"]:disabled {
                border-color: #93c5fd;
                background-color: #93c5fd;
                color: #eff6ff;
            }
            """
        )

    def _install_button_hover_animations(self) -> None:
        self._button_hover_animators.clear()
        for button in self.findChildren(QPushButton):
            self._button_hover_animators.append(ButtonHoverAnimator(button, parent=self))

    def _create_actions(self) -> None:
        self.new_project_action = QAction("Create New Project", self)
        self.new_project_action.triggered.connect(self._request_new_project)
        self.open_project_action = QAction("Open Project...", self)
        self.open_project_action.triggered.connect(self._request_open_project)
        self.save_project_action = QAction("Save", self)
        self.save_project_action.triggered.connect(self.save_project)
        self.settings_action = QAction("Settings...", self)
        self.settings_action.setObjectName("settings_action")
        self.settings_action.triggered.connect(self._request_settings)
        self.launch_action = QAction("Launch Experiment", self)
        launch_help = (
            "Launch Experiment on the current alpha test-mode runtime path. "
            "Launch checks run automatically before participant entry."
        )
        self.launch_action.setToolTip(launch_help)
        self.launch_action.setStatusTip(launch_help)
        self.launch_action.triggered.connect(self.run_page.launch_test_session)

    def _create_menu_and_toolbar(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.settings_action)

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

    def _request_settings(self) -> None:
        self._on_request_settings()

    def _update_window_title(self, *_args) -> None:
        dirty_prefix = "*" if self.document.dirty else ""
        self.setWindowTitle(
            f"{dirty_prefix}{self.document.project.meta.name} - FPVS Studio (Alpha)"
        )
