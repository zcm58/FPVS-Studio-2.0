"""Dialog for managing reusable condition-template profiles in the GUI."""

from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.condition_template_profiles import (
    delete_condition_template_profile,
    list_condition_template_profiles,
    upsert_condition_template_profile,
)
from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.models import ConditionTemplateProfile, FixationTaskSettings
from fpvs_studio.gui.components import apply_condition_template_details_header_style
from fpvs_studio.gui.condition_template_profile_editor_dialog import (
    ConditionTemplateProfileEditorDialog,
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
                "Display Refresh Rate: "
                f"{_format_refresh_rate(defaults.display.preferred_refresh_hz)}",
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
            "<div>"
            '<span style="font-size: 14px; font-weight: 700; text-decoration: underline;">'
            f"{html.escape(title)}"
            "</span>"
            "</div>"
        )
        for line in lines:
            parts.append(f'<div style="margin-top: 4px;">{html.escape(line)}</div>')
    parts.append("</div>")
    return "".join(parts)


class ConditionTemplateManagerDialog(QDialog):
    """Manage app-level condition-template profiles under the FPVS root folder."""

    def __init__(self, *, root_dir: Path, parent: QWidget | None = None) -> None:
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
        apply_condition_template_details_header_style(self.details_header)

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

    def _update_buttons(self, *_args: object) -> None:
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


__all__ = [
    "ConditionTemplateManagerDialog",
    "ConditionTemplateProfileEditorDialog",
]
