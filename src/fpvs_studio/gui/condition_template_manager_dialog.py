"""Dialogs for managing app-level condition-template profiles."""

from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from fpvs_studio.core.condition_template_profiles import (
    delete_condition_template_profile,
    list_condition_template_profiles,
    upsert_condition_template_profile,
)
from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.models import (
    ConditionDefaults,
    ConditionTemplateDefaults,
    ConditionTemplateDisplayDefaults,
    ConditionTemplateProfile,
    FixationTaskSettings,
)


def _duty_cycle_label(mode: DutyCycleMode) -> str:
    return {
        DutyCycleMode.CONTINUOUS: "Continuous",
        DutyCycleMode.BLANK_50: "50% Blank",
    }[mode]


_DISPLAY_RESOLUTION_TEXT = "Full Screen (1920 × 1080)"


def _enabled_label(value: bool) -> str:
    return "Enabled" if value else "Disabled"


def _format_refresh_rate(preferred_refresh_hz: float | None) -> str:
    if preferred_refresh_hz is None:
        return "Not Set"
    value_text = f"{preferred_refresh_hz:.3f}".rstrip("0").rstrip(".")
    return f"{value_text} Hz"


def _format_color_changes_per_condition(fixation: FixationTaskSettings) -> str:
    if fixation.target_count_mode != "randomized":
        return str(fixation.changes_per_sequence)
    min_count = fixation.target_count_min
    max_count = fixation.target_count_max
    midpoint_sum = min_count + max_count
    if midpoint_sum % 2 == 0:
        center = midpoint_sum // 2
        delta = max_count - center
        if center - delta == min_count and center + delta == max_count:
            return f"{center} ± {delta}"
    return f"{min_count} to {max_count}"


def _format_profile_details(profile: ConditionTemplateProfile) -> str:
    defaults = profile.defaults
    fixation = defaults.fixation_task
    sections = [
        (
            "Template",
            [
                f"Template Name: {profile.display_name}",
                f"Built-in: {'Yes' if profile.built_in else 'No'}",
            ],
        ),
        (
            "Display",
            [
                f"Display Refresh Rate: {_format_refresh_rate(defaults.display.preferred_refresh_hz)}",
                f"Display Resolution: {_DISPLAY_RESOLUTION_TEXT}",
            ],
        ),
        (
            "Fixation Cross",
            [
                f"Fixation Cross: {_enabled_label(fixation.enabled)}",
                f"Fixation Cross Accuracy Task: {_enabled_label(fixation.accuracy_task_enabled)}",
                (
                    "Total cross color changes in each condition: "
                    f"{_format_color_changes_per_condition(fixation)}"
                ),
                f"Fixation cross timing: {fixation.target_duration_ms} ms",
                f"Minimum time between color changes: {fixation.min_gap_ms} ms",
                f"Maximum time between color changes: {fixation.max_gap_ms} ms",
            ],
        ),
        (
            "Condition Settings",
            [
                f"Duty Cycle: {_duty_cycle_label(defaults.condition.duty_cycle_mode)}",
                f"Repeats: {defaults.condition.sequence_count}",
                f"Cycles per Repeat: {defaults.condition.oddball_cycle_repeats_per_sequence}",
            ],
        ),
        (
            "Description",
            [profile.description.strip() or "No description provided."],
        ),
    ]
    parts = ['<div style="line-height: 1.45;">']
    for index, (title, lines) in enumerate(sections):
        if index:
            parts.append('<div style="height: 12px;"></div>')
        parts.append(
            '<div>'
            '<span style="font-size: 14px; font-weight: 700; text-decoration: underline;">'
            f"{html.escape(title)}"
            "</span>"
            "</div>"
        )
        for line in lines:
            parts.append(f'<div style="margin-top: 4px;">{html.escape(line)}</div>')
    parts.append("</div>")
    return "".join(parts)


class ConditionTemplateProfileEditorDialog(QDialog):
    """Create or edit one user-defined condition-template profile."""

    def __init__(
        self,
        *,
        existing_profile_ids: set[str],
        initial_profile: ConditionTemplateProfile | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._existing_profile_ids = existing_profile_ids
        self._original_profile_id = (
            initial_profile.profile_id if initial_profile is not None else None
        )
        self._saved_profile: ConditionTemplateProfile | None = None

        self.setWindowTitle("Condition Template Profile")
        self.setModal(True)
        self.resize(760, 760)

        self.profile_id_edit = QLineEdit(self)
        self.profile_id_edit.setObjectName("condition_profile_id_edit")
        self.display_name_edit = QLineEdit(self)
        self.display_name_edit.setObjectName("condition_profile_display_name_edit")
        self.description_edit = QLineEdit(self)
        self.description_edit.setObjectName("condition_profile_description_edit")

        profile_group = QGroupBox("Profile Metadata", self)
        profile_layout = QFormLayout(profile_group)
        profile_layout.addRow("Profile Id", self.profile_id_edit)
        profile_layout.addRow("Display Name", self.display_name_edit)
        profile_layout.addRow("Description", self.description_edit)

        self.duty_cycle_combo = QComboBox(self)
        self.duty_cycle_combo.setObjectName("condition_profile_duty_cycle_combo")
        for mode in DutyCycleMode:
            self.duty_cycle_combo.addItem(_duty_cycle_label(mode), userData=mode)
        self.sequence_count_spin = QSpinBox(self)
        self.sequence_count_spin.setObjectName("condition_profile_sequence_count_spin")
        self.sequence_count_spin.setRange(1, 10000)
        self.oddball_cycles_spin = QSpinBox(self)
        self.oddball_cycles_spin.setObjectName("condition_profile_oddball_cycles_spin")
        self.oddball_cycles_spin.setRange(1, 10000)

        condition_group = QGroupBox("Condition Defaults", self)
        condition_layout = QFormLayout(condition_group)
        condition_layout.addRow("Duty Cycle", self.duty_cycle_combo)
        condition_layout.addRow("Condition Repeats", self.sequence_count_spin)
        condition_layout.addRow("Cycles / Condition Repeat", self.oddball_cycles_spin)

        self.preferred_refresh_enabled_checkbox = QCheckBox(
            "Set preferred refresh rate",
            self,
        )
        self.preferred_refresh_enabled_checkbox.setObjectName("condition_profile_refresh_enabled_checkbox")
        self.preferred_refresh_spin = QDoubleSpinBox(self)
        self.preferred_refresh_spin.setObjectName("condition_profile_refresh_spin")
        self.preferred_refresh_spin.setRange(1.0, 1000.0)
        self.preferred_refresh_spin.setDecimals(3)
        self.preferred_refresh_spin.setSingleStep(1.0)
        self.preferred_refresh_enabled_checkbox.stateChanged.connect(
            lambda *_args: self.preferred_refresh_spin.setEnabled(
                self.preferred_refresh_enabled_checkbox.isChecked()
            )
        )

        display_group = QGroupBox("Display Defaults", self)
        display_layout = QVBoxLayout(display_group)
        display_layout.addWidget(self.preferred_refresh_enabled_checkbox)
        display_layout.addWidget(self.preferred_refresh_spin)

        self.fixation_enabled_checkbox = QCheckBox("Fixation task enabled", self)
        self.fixation_enabled_checkbox.setObjectName("condition_profile_fixation_enabled_checkbox")
        self.accuracy_enabled_checkbox = QCheckBox("Fixation accuracy scoring enabled", self)
        self.accuracy_enabled_checkbox.setObjectName("condition_profile_fixation_accuracy_checkbox")
        self.changes_per_sequence_spin = QSpinBox(self)
        self.changes_per_sequence_spin.setObjectName("condition_profile_changes_per_sequence_spin")
        self.changes_per_sequence_spin.setRange(0, 1000)
        self.target_count_mode_combo = QComboBox(self)
        self.target_count_mode_combo.setObjectName("condition_profile_target_count_mode_combo")
        self.target_count_mode_combo.addItem("Fixed", userData="fixed")
        self.target_count_mode_combo.addItem("Randomized", userData="randomized")
        self.target_count_mode_combo.currentIndexChanged.connect(self._update_target_count_mode_state)
        self.target_count_min_spin = QSpinBox(self)
        self.target_count_min_spin.setObjectName("condition_profile_target_count_min_spin")
        self.target_count_min_spin.setRange(0, 1000)
        self.target_count_max_spin = QSpinBox(self)
        self.target_count_max_spin.setObjectName("condition_profile_target_count_max_spin")
        self.target_count_max_spin.setRange(0, 1000)
        self.no_repeat_count_checkbox = QCheckBox(
            "Avoid immediate repeated randomized target counts",
            self,
        )
        self.no_repeat_count_checkbox.setObjectName("condition_profile_no_repeat_count_checkbox")
        self.target_duration_spin = QSpinBox(self)
        self.target_duration_spin.setObjectName("condition_profile_target_duration_spin")
        self.target_duration_spin.setRange(0, 10000)
        self.min_gap_spin = QSpinBox(self)
        self.min_gap_spin.setObjectName("condition_profile_min_gap_spin")
        self.min_gap_spin.setRange(0, 60000)
        self.max_gap_spin = QSpinBox(self)
        self.max_gap_spin.setObjectName("condition_profile_max_gap_spin")
        self.max_gap_spin.setRange(0, 60000)
        self.base_color_edit = QLineEdit(self)
        self.base_color_edit.setObjectName("condition_profile_base_color_edit")
        self.target_color_edit = QLineEdit(self)
        self.target_color_edit.setObjectName("condition_profile_target_color_edit")
        self.response_key_edit = QLineEdit(self)
        self.response_key_edit.setObjectName("condition_profile_response_key_edit")
        self.response_keys_edit = QLineEdit(self)
        self.response_keys_edit.setObjectName("condition_profile_response_keys_edit")
        self.response_keys_edit.setPlaceholderText(
            "Comma-separated keys (for example: space,return)"
        )
        self.response_window_spin = QDoubleSpinBox(self)
        self.response_window_spin.setObjectName("condition_profile_response_window_spin")
        self.response_window_spin.setRange(0.1, 30.0)
        self.response_window_spin.setDecimals(3)
        self.response_window_spin.setSingleStep(0.1)
        self.cross_size_spin = QSpinBox(self)
        self.cross_size_spin.setObjectName("condition_profile_cross_size_spin")
        self.cross_size_spin.setRange(1, 2000)
        self.line_width_spin = QSpinBox(self)
        self.line_width_spin.setObjectName("condition_profile_line_width_spin")
        self.line_width_spin.setRange(1, 200)

        fixation_group = QGroupBox("Fixation Defaults", self)
        fixation_layout = QGridLayout(fixation_group)
        fixation_layout.addWidget(self.fixation_enabled_checkbox, 0, 0, 1, 2)
        fixation_layout.addWidget(self.accuracy_enabled_checkbox, 1, 0, 1, 2)

        fixation_form = QFormLayout()
        fixation_form.addRow("Color changes / condition", self.changes_per_sequence_spin)
        fixation_form.addRow("Target count mode", self.target_count_mode_combo)
        fixation_form.addRow("Target count min", self.target_count_min_spin)
        fixation_form.addRow("Target count max", self.target_count_max_spin)
        fixation_form.addRow("No immediate repeat", self.no_repeat_count_checkbox)
        fixation_form.addRow("Target duration (ms)", self.target_duration_spin)
        fixation_form.addRow("Min gap (ms)", self.min_gap_spin)
        fixation_form.addRow("Max gap (ms)", self.max_gap_spin)
        fixation_form.addRow("Base color", self.base_color_edit)
        fixation_form.addRow("Target color", self.target_color_edit)
        fixation_form.addRow("Response key", self.response_key_edit)
        fixation_form.addRow("Response keys", self.response_keys_edit)
        fixation_form.addRow("Response window (s)", self.response_window_spin)
        fixation_form.addRow("Cross size (px)", self.cross_size_spin)
        fixation_form.addRow("Line width (px)", self.line_width_spin)
        fixation_layout.addLayout(fixation_form, 2, 0, 1, 2)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(profile_group)
        layout.addWidget(condition_group)
        layout.addWidget(display_group)
        layout.addWidget(fixation_group, 1)
        layout.addWidget(self.button_box)

        self._apply_profile(initial_profile or self._default_profile())

    @property
    def saved_profile(self) -> ConditionTemplateProfile | None:
        """Return the validated saved profile when the dialog was accepted."""

        return self._saved_profile

    def _default_profile(self) -> ConditionTemplateProfile:
        return ConditionTemplateProfile(
            profile_id="new-profile",
            display_name="New Profile",
            built_in=False,
            defaults=ConditionTemplateDefaults(
                condition=ConditionDefaults(),
                display=ConditionTemplateDisplayDefaults(preferred_refresh_hz=None),
                fixation_task=FixationTaskSettings(),
            ),
        )

    def _apply_profile(self, profile: ConditionTemplateProfile) -> None:
        self.profile_id_edit.setText(profile.profile_id)
        self.display_name_edit.setText(profile.display_name)
        self.description_edit.setText(profile.description)
        self.sequence_count_spin.setValue(profile.defaults.condition.sequence_count)
        self.oddball_cycles_spin.setValue(
            profile.defaults.condition.oddball_cycle_repeats_per_sequence
        )
        self.duty_cycle_combo.setCurrentIndex(
            self.duty_cycle_combo.findData(profile.defaults.condition.duty_cycle_mode)
        )
        preferred_refresh = profile.defaults.display.preferred_refresh_hz
        self.preferred_refresh_enabled_checkbox.setChecked(preferred_refresh is not None)
        self.preferred_refresh_spin.setEnabled(preferred_refresh is not None)
        self.preferred_refresh_spin.setValue(
            preferred_refresh if preferred_refresh is not None else 60.0
        )

        fixation = profile.defaults.fixation_task
        self.fixation_enabled_checkbox.setChecked(fixation.enabled)
        self.accuracy_enabled_checkbox.setChecked(fixation.accuracy_task_enabled)
        self.changes_per_sequence_spin.setValue(fixation.changes_per_sequence)
        self.target_count_mode_combo.setCurrentIndex(
            self.target_count_mode_combo.findData(fixation.target_count_mode)
        )
        self.target_count_min_spin.setValue(fixation.target_count_min)
        self.target_count_max_spin.setValue(fixation.target_count_max)
        self.no_repeat_count_checkbox.setChecked(fixation.no_immediate_repeat_count)
        self.target_duration_spin.setValue(fixation.target_duration_ms)
        self.min_gap_spin.setValue(fixation.min_gap_ms)
        self.max_gap_spin.setValue(fixation.max_gap_ms)
        self.base_color_edit.setText(str(fixation.base_color))
        self.target_color_edit.setText(str(fixation.target_color))
        self.response_key_edit.setText(fixation.response_key)
        self.response_keys_edit.setText(",".join(fixation.response_keys))
        self.response_window_spin.setValue(fixation.response_window_seconds)
        self.cross_size_spin.setValue(fixation.cross_size_px)
        self.line_width_spin.setValue(fixation.line_width_px)
        self._update_target_count_mode_state()

    def _update_target_count_mode_state(self) -> None:
        randomized = self.target_count_mode_combo.currentData() == "randomized"
        self.target_count_min_spin.setEnabled(randomized)
        self.target_count_max_spin.setEnabled(randomized)
        self.no_repeat_count_checkbox.setEnabled(randomized)

    def _build_profile(self) -> ConditionTemplateProfile:
        response_key = self.response_key_edit.text().strip().lower()
        response_keys = [
            item.strip().lower()
            for item in self.response_keys_edit.text().split(",")
            if item.strip()
        ]
        if not response_keys and response_key:
            response_keys = [response_key]
        preferred_refresh_hz = (
            self.preferred_refresh_spin.value()
            if self.preferred_refresh_enabled_checkbox.isChecked()
            else None
        )
        return ConditionTemplateProfile(
            profile_id=self.profile_id_edit.text().strip(),
            display_name=self.display_name_edit.text().strip(),
            description=self.description_edit.text().strip(),
            built_in=False,
            defaults=ConditionTemplateDefaults(
                condition=ConditionDefaults(
                    duty_cycle_mode=self.duty_cycle_combo.currentData(),
                    sequence_count=self.sequence_count_spin.value(),
                    oddball_cycle_repeats_per_sequence=self.oddball_cycles_spin.value(),
                ),
                display=ConditionTemplateDisplayDefaults(preferred_refresh_hz=preferred_refresh_hz),
                fixation_task=FixationTaskSettings(
                    enabled=self.fixation_enabled_checkbox.isChecked(),
                    accuracy_task_enabled=self.accuracy_enabled_checkbox.isChecked(),
                    changes_per_sequence=self.changes_per_sequence_spin.value(),
                    target_count_mode=self.target_count_mode_combo.currentData(),
                    target_count_min=self.target_count_min_spin.value(),
                    target_count_max=self.target_count_max_spin.value(),
                    no_immediate_repeat_count=self.no_repeat_count_checkbox.isChecked(),
                    target_duration_ms=self.target_duration_spin.value(),
                    min_gap_ms=self.min_gap_spin.value(),
                    max_gap_ms=self.max_gap_spin.value(),
                    base_color=self.base_color_edit.text().strip(),
                    target_color=self.target_color_edit.text().strip(),
                    response_key=response_key,
                    response_keys=response_keys,
                    response_window_seconds=self.response_window_spin.value(),
                    cross_size_px=self.cross_size_spin.value(),
                    line_width_px=self.line_width_spin.value(),
                ),
            ),
        )

    def accept(self) -> None:
        try:
            profile = self._build_profile()
        except Exception as error:
            QMessageBox.warning(self, "Invalid Template Profile", str(error))
            return
        if (
            profile.profile_id != self._original_profile_id
            and profile.profile_id in self._existing_profile_ids
        ):
            QMessageBox.warning(
                self,
                "Duplicate Profile Id",
                f"A condition template profile with id '{profile.profile_id}' already exists.",
            )
            return
        self._saved_profile = profile
        super().accept()


class ConditionTemplateManagerDialog(QDialog):
    """Manage app-level condition-template profiles under the FPVS root folder."""

    def __init__(self, *, root_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self._root_dir = Path(root_dir)
        self._profiles: list[ConditionTemplateProfile] = []
        self.setWindowTitle("Manage Condition Templates")
        self.setModal(True)
        self.resize(760, 540)

        self.profile_list = QListWidget(self)
        self.profile_list.setObjectName("condition_template_profile_list")
        self.profile_list.currentItemChanged.connect(self._update_buttons)

        self.profile_details = QLabel(self)
        self.profile_details.setObjectName("condition_template_profile_details")
        self.profile_details.setWordWrap(True)
        self.profile_details.setTextFormat(Qt.TextFormat.RichText)
        self.profile_details.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.details_header = QLabel("Details", self)
        self.details_header.setObjectName("condition_template_details_header")
        self.details_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.details_header.setStyleSheet(
            "font-size: 18px; font-weight: 700; text-decoration: underline;"
        )

        self.add_button = QPushButton("Add", self)
        self.add_button.setObjectName("condition_template_add_button")
        self.add_button.clicked.connect(self._add_profile)
        self.edit_button = QPushButton("Edit", self)
        self.edit_button.setObjectName("condition_template_edit_button")
        self.edit_button.clicked.connect(self._edit_profile)
        self.duplicate_button = QPushButton("Duplicate", self)
        self.duplicate_button.setObjectName("condition_template_duplicate_button")
        self.duplicate_button.clicked.connect(self._duplicate_profile)
        self.delete_button = QPushButton("Delete", self)
        self.delete_button.setObjectName("condition_template_delete_button")
        self.delete_button.clicked.connect(self._delete_profile)

        button_row = QHBoxLayout()
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.edit_button)
        button_row.addWidget(self.duplicate_button)
        button_row.addWidget(self.delete_button)
        button_row.addStretch(1)

        content_layout = QGridLayout()
        content_layout.addWidget(QLabel("Profiles", self), 0, 0)
        content_layout.addWidget(self.details_header, 0, 1)
        content_layout.addWidget(self.profile_list, 1, 0)
        content_layout.addWidget(self.profile_details, 1, 1)
        content_layout.setColumnStretch(0, 1)
        content_layout.setColumnStretch(1, 1)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(content_layout, 1)
        layout.addLayout(button_row)
        layout.addWidget(self.button_box)

        self._reload_profiles()

    def _selected_profile(self) -> ConditionTemplateProfile | None:
        item = self.profile_list.currentItem()
        if item is None:
            return None
        profile_id = item.data(Qt.ItemDataRole.UserRole)
        for profile in self._profiles:
            if profile.profile_id == profile_id:
                return profile
        return None

    def _reload_profiles(self, *, select_profile_id: str | None = None) -> None:
        self._profiles = list_condition_template_profiles(self._root_dir)
        self.profile_list.clear()
        selected_row = -1
        for index, profile in enumerate(self._profiles):
            item = QListWidgetItem(profile.display_name)
            item.setData(Qt.ItemDataRole.UserRole, profile.profile_id)
            self.profile_list.addItem(item)
            if select_profile_id is not None and profile.profile_id == select_profile_id:
                selected_row = index
        if selected_row >= 0:
            self.profile_list.setCurrentRow(selected_row)
        elif self.profile_list.count() > 0:
            self.profile_list.setCurrentRow(0)
        self._update_buttons()

    def _update_buttons(self, *_args) -> None:
        profile = self._selected_profile()
        has_profile = profile is not None
        self.edit_button.setEnabled(has_profile and not profile.built_in if profile else False)
        self.duplicate_button.setEnabled(has_profile)
        self.delete_button.setEnabled(has_profile and not profile.built_in if profile else False)
        if profile is None:
            self.profile_details.setText("Select a condition template profile.")
            return
        self.profile_details.setText(_format_profile_details(profile))

    def _existing_profile_ids(self) -> set[str]:
        return {item.profile_id for item in self._profiles}

    def _add_profile(self) -> None:
        dialog = ConditionTemplateProfileEditorDialog(
            existing_profile_ids=self._existing_profile_ids(),
            parent=self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.saved_profile is None:
            return
        upsert_condition_template_profile(self._root_dir, dialog.saved_profile)
        self._reload_profiles(select_profile_id=dialog.saved_profile.profile_id)

    def _edit_profile(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        if profile.built_in:
            QMessageBox.warning(
                self,
                "Built-in Template",
                "Built-in condition templates are read-only. Duplicate it to edit.",
            )
            return
        dialog = ConditionTemplateProfileEditorDialog(
            existing_profile_ids=self._existing_profile_ids(),
            initial_profile=profile,
            parent=self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.saved_profile is None:
            return
        upsert_condition_template_profile(self._root_dir, dialog.saved_profile)
        self._reload_profiles(select_profile_id=dialog.saved_profile.profile_id)

    def _duplicate_profile(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        existing_ids = self._existing_profile_ids()
        duplicate_id = f"{profile.profile_id}-copy"
        suffix = 2
        while duplicate_id in existing_ids:
            duplicate_id = f"{profile.profile_id}-copy-{suffix}"
            suffix += 1
        duplicate_profile = profile.model_copy(
            deep=True,
            update={
                "profile_id": duplicate_id,
                "display_name": f"{profile.display_name} Copy",
                "built_in": False,
            },
        )
        dialog = ConditionTemplateProfileEditorDialog(
            existing_profile_ids=existing_ids,
            initial_profile=duplicate_profile,
            parent=self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted or dialog.saved_profile is None:
            return
        upsert_condition_template_profile(self._root_dir, dialog.saved_profile)
        self._reload_profiles(select_profile_id=dialog.saved_profile.profile_id)

    def _delete_profile(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            return
        if profile.built_in:
            QMessageBox.warning(
                self,
                "Built-in Template",
                "Built-in condition templates cannot be deleted.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Delete Condition Template",
            f"Delete condition template profile '{profile.display_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        delete_condition_template_profile(self._root_dir, profile.profile_id)
        self._reload_profiles()
