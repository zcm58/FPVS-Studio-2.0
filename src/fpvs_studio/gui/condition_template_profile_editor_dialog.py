"""Editor dialog for one reusable condition-template profile."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
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


class ConditionTemplateProfileEditorDialog(QDialog):
    """Create or edit one user-defined condition-template profile."""

    def __init__(
        self,
        *,
        existing_profile_ids: set[str],
        initial_profile: ConditionTemplateProfile | None = None,
        parent: QWidget | None = None,
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
        self.preferred_refresh_enabled_checkbox.setObjectName(
            "condition_profile_refresh_enabled_checkbox"
        )
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
        self.target_count_mode_combo.currentIndexChanged.connect(
            self._update_target_count_mode_state
        )
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
