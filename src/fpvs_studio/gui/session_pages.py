"""Session and fixation authoring pages for the FPVS Studio main window."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.enums import (
    InterConditionMode,
)
from fpvs_studio.core.validation import ConditionFixationGuidance
from fpvs_studio.gui.design_system import (
    CARD_CORNER_RADIUS,
    COLOR_BORDER_SOFT,
    COLOR_SURFACE_ELEVATED,
    COLOR_TEXT_PRIMARY,
    PAGE_SECTION_GAP,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import (
    _FIXATION_FEASIBILITY_TOOLTIP_TEXT,
    _prefixed_object_name,
    _set_form_row_visible,
    _show_error_dialog,
    _transition_label,
)
from fpvs_studio.gui.window_layout import NonHomePageShell, SectionCard


class SessionStructureEditor(QWidget):
    """Reusable session-structure editor widget."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        object_name_prefix: str = "",
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
            subtitle="Block order and inter-condition flow.",
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
        self.session_layout.addRow("Inter-condition mode", self.inter_condition_mode_combo)
        self.session_layout.addRow("Break seconds", self.break_seconds_spin)
        self.session_layout.addRow("Continue key", self.continue_key_edit)
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


class FixationSettingsEditor(QWidget):
    """Reusable fixation-task settings editor."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        schedule_row_behavior: str = "hide",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if schedule_row_behavior not in {"hide", "disable"}:
            raise ValueError(f"Unsupported schedule_row_behavior: {schedule_row_behavior}")
        self._document = document
        self._schedule_row_behavior = schedule_row_behavior

        self.fixation_enabled_checkbox = QCheckBox(
            "Enable fixation color changes per condition", self
        )
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

        self.fixation_panel = SectionCard(
            title="Fixation Cross Task",
            subtitle="Task enablement, behavior, timing, response, and appearance.",
            object_name="fixation_settings_panel",
            parent=self,
        )
        self.fixation_panel.card_layout.setContentsMargins(12, 10, 12, 10)
        self.fixation_panel.card_layout.setSpacing(8)
        fixation_panel_layout = self.fixation_panel.body_layout
        fixation_panel_layout.setSpacing(8)

        enablement_layout = QHBoxLayout()
        enablement_layout.setContentsMargins(0, 0, 0, 0)
        enablement_layout.setSpacing(6)
        enablement_layout.addWidget(self.fixation_enabled_checkbox)
        enablement_layout.addWidget(self.fixation_accuracy_checkbox)
        enablement_layout.addStretch(1)

        self.fixation_behavior_group = QWidget(self.fixation_panel)
        self.fixation_behavior_layout = QFormLayout(self.fixation_behavior_group)
        self.fixation_behavior_layout.setVerticalSpacing(7)
        self.fixation_behavior_layout.addRow("Color change schedule", self.target_count_mode_combo)
        self.fixation_behavior_layout.addRow(
            "Changes per condition", self.changes_per_sequence_spin
        )
        self.fixation_behavior_layout.addRow("Minimum changes", self.target_count_min_spin)
        self.fixation_behavior_layout.addRow("Maximum changes", self.target_count_max_spin)
        self.fixation_behavior_layout.addRow("No immediate repeat", self.no_repeat_count_checkbox)

        self.fixation_timing_group = QWidget(self.fixation_panel)
        timing_layout = QFormLayout(self.fixation_timing_group)
        timing_layout.setVerticalSpacing(7)
        timing_layout.addRow("Color change duration (ms)", self.target_duration_spin)
        timing_layout.addRow("Minimum gap (ms)", self.min_gap_spin)
        timing_layout.addRow("Maximum gap (ms)", self.max_gap_spin)

        self.fixation_response_group = QWidget(self.fixation_panel)
        response_layout = QFormLayout(self.fixation_response_group)
        response_layout.setVerticalSpacing(7)
        response_layout.addRow("Response key", self.response_key_edit)
        response_layout.addRow("Response window (s)", self.response_window_spin)

        self.fixation_appearance_group = QWidget(self.fixation_panel)
        appearance_layout = QFormLayout(self.fixation_appearance_group)
        appearance_layout.setVerticalSpacing(7)
        appearance_layout.addRow("Default color", self.base_color_edit)
        appearance_layout.addRow("Change color", self.target_color_edit)
        appearance_layout.addRow("Cross size (px)", self.cross_size_spin)
        appearance_layout.addRow("Line width (px)", self.line_width_spin)

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

        fixation_panel_layout.addLayout(enablement_layout)
        fixation_panel_layout.addWidget(feasibility_card)
        settings_grid = QGridLayout()
        settings_grid.setContentsMargins(0, 0, 0, 0)
        settings_grid.setHorizontalSpacing(PAGE_SECTION_GAP)
        settings_grid.setVerticalSpacing(8)
        behavior_header = QLabel("Behavior", self.fixation_panel)
        behavior_header.setProperty("sectionCardRole", "subtitle")
        timing_header = QLabel("Timing", self.fixation_panel)
        timing_header.setProperty("sectionCardRole", "subtitle")
        response_header = QLabel("Response", self.fixation_panel)
        response_header.setProperty("sectionCardRole", "subtitle")
        appearance_header = QLabel("Appearance", self.fixation_panel)
        appearance_header.setProperty("sectionCardRole", "subtitle")
        settings_grid.addWidget(behavior_header, 0, 0)
        settings_grid.addWidget(timing_header, 0, 1)
        settings_grid.addWidget(self.fixation_behavior_group, 1, 0)
        settings_grid.addWidget(self.fixation_timing_group, 1, 1)
        settings_grid.addWidget(response_header, 2, 0)
        settings_grid.addWidget(appearance_header, 2, 1)
        settings_grid.addWidget(self.fixation_response_group, 3, 0)
        settings_grid.addWidget(self.fixation_appearance_group, 3, 1)
        settings_grid.setColumnStretch(0, 1)
        settings_grid.setColumnStretch(1, 1)
        fixation_panel_layout.addLayout(settings_grid)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.fixation_panel)

        self.setStyleSheet(
            f"""
            QFrame#fixation_feasibility_card {{
                border: 1px solid {COLOR_BORDER_SOFT};
                border-radius: {CARD_CORNER_RADIUS}px;
                background-color: {COLOR_SURFACE_ELEVATED};
            }}
            QLabel#fixation_feasibility_label {{
                color: {COLOR_TEXT_PRIMARY};
                font-weight: 600;
            }}
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
            _set_form_row_visible(
                self.fixation_behavior_layout, self.changes_per_sequence_spin, True
            )
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
        guidance_rows: list[ConditionFixationGuidance] | None,
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
        guidance_rows: list[ConditionFixationGuidance] | None = None
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

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(document, schedule_row_behavior="hide", parent=parent)
