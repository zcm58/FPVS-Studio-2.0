"""Runtime settings and launch pages for the FPVS Studio main window."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEventLoop, QSignalBlocker, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.design_system import (
    PAGE_SECTION_GAP,
    StatusBadgeLabel,
)
from fpvs_studio.gui.document import DocumentError, ProjectDocument
from fpvs_studio.gui.window_helpers import (
    _RUNTIME_BACKGROUND_COLOR_PRESETS,
    LauncherReadinessReport,
    _canonical_runtime_background_hex,
    _configure_read_only_list,
    _launcher_readiness_report,
    _prefixed_object_name,
    _set_list_items,
    _show_error_dialog,
)
from fpvs_studio.gui.window_layout import NonHomePageShell, SectionCard


def _compat_progress_dialog(*args, **kwargs) -> QProgressDialog:
    from fpvs_studio.gui import main_window

    return main_window.QProgressDialog(*args, **kwargs)


def _show_runtime_error_dialog(parent: QWidget, title: str, error: Exception) -> None:
    from fpvs_studio.gui import main_window

    main_window._show_error_dialog(parent, title, error)


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


class RuntimeSettingsEditor(QWidget):
    """Reusable runtime settings editor for refresh/display/serial controls."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        object_name_prefix: str = "",
        editable: bool = True,
        fullscreen_state_getter: Callable[[], bool] | None = None,
        fullscreen_state_setter: Callable[[bool], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._editable = editable
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
            subtitle="Refresh, background, fullscreen, and trigger configuration.",
            object_name=_prefixed_object_name(object_name_prefix, "runtime_settings_card"),
            parent=self,
        )
        self.card.layout().setContentsMargins(12, 10, 12, 10)
        self.card.layout().setSpacing(8)
        self.card.body_layout.setSpacing(8)
        self.summary_note_label = QLabel(self.card)
        self.summary_note_label.setObjectName(
            _prefixed_object_name(object_name_prefix, "runtime_settings_summary_note")
        )
        self.summary_note_label.setWordWrap(True)
        self.summary_value_labels: dict[str, QLabel] = {}
        self.form_container = QWidget(self.card)
        self.form_layout = QGridLayout(self.form_container)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setHorizontalSpacing(PAGE_SECTION_GAP)
        self.form_layout.setVerticalSpacing(8)
        self.form_layout.addWidget(QLabel("Refresh (Hz)", self.form_container), 0, 0)
        self.form_layout.addWidget(self.refresh_hz_spin, 0, 1)
        self.form_layout.addWidget(QLabel("Background", self.form_container), 0, 2)
        self.form_layout.addWidget(self.runtime_background_color_combo, 0, 3)
        self.form_layout.addWidget(self.runtime_background_scope_label, 1, 0, 1, 4)
        self.form_layout.addWidget(QLabel("Serial Port", self.form_container), 2, 0)
        self.form_layout.addWidget(self.serial_port_edit, 2, 1)
        self.form_layout.addWidget(QLabel("Baud Rate", self.form_container), 2, 2)
        self.form_layout.addWidget(self.serial_baudrate_spin, 2, 3)
        self.form_layout.addWidget(self.test_mode_checkbox, 3, 0, 1, 2)
        self.form_layout.addWidget(self.fullscreen_checkbox, 3, 2, 1, 2)
        self.form_layout.setColumnStretch(1, 1)
        self.form_layout.setColumnStretch(3, 1)
        self.summary_container = QWidget(self.card)
        self.summary_layout = QFormLayout(self.summary_container)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_layout.setHorizontalSpacing(12)
        self.summary_layout.setVerticalSpacing(6)
        for key, label_text in (
            ("refresh", "Refresh"),
            ("background", "Background"),
            ("serial_port", "Serial Port"),
            ("serial_baudrate", "Baud Rate"),
            ("test_mode", "Runtime Path"),
            ("fullscreen", "Fullscreen"),
        ):
            value_label = QLabel(self.summary_container)
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.summary_value_labels[key] = value_label
            self.summary_layout.addRow(label_text, value_label)
        if not self._editable:
            self.card.title_label.setText("Runtime Settings Summary")
            if self.card.subtitle_label is not None:
                self.card.subtitle_label.setText(
                    "Mirrored from Run / Runtime."
                )
            self.summary_note_label.setText(
                "Open Run / Runtime to edit launch settings. This view is a compact mirror."
            )
            self.card.body_layout.addWidget(self.summary_note_label)
            self.card.body_layout.addWidget(self.summary_container)
        else:
            self.card.body_layout.addWidget(self.form_container)

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
        self.refresh_hz_spin.setEnabled(self._editable)
        self.runtime_background_color_combo.setEnabled(self._editable)
        self.serial_port_edit.setEnabled(self._editable)
        self.fullscreen_checkbox.setEnabled(self._editable)
        if not self._editable:
            self.summary_note_label.setVisible(True)
            self.summary_container.setVisible(True)
            self.form_container.setVisible(False)
            self.summary_value_labels["refresh"].setText(f"{preferred_refresh:.2f} Hz")
            self.summary_value_labels["background"].setText(
                self.runtime_background_color_combo.currentText()
            )
            self.summary_value_labels["serial_port"].setText(
                self._document.project.settings.triggers.serial_port or "Not set"
            )
            self.summary_value_labels["serial_baudrate"].setText(
                str(self._document.project.settings.triggers.baudrate)
            )
            self.summary_value_labels["test_mode"].setText("Alpha test-mode path only")
            self.summary_value_labels["fullscreen"].setText(
                "Enabled" if target_fullscreen_value else "Disabled"
            )
        else:
            self.summary_note_label.setVisible(False)
            self.summary_container.setVisible(False)
            self.form_container.setVisible(True)

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
            subtitle="Display routing that stays specific to this page.",
            object_name="run_display_card",
            parent=self,
        )
        display_card.layout().setContentsMargins(12, 10, 12, 10)
        display_card.layout().setSpacing(8)
        display_card.body_layout.setSpacing(8)
        display_layout = QFormLayout()
        display_layout.setVerticalSpacing(8)
        display_layout.addRow("Display Index", self.display_index_edit)
        display_layout.addRow("Engine", self.engine_name_value)
        display_card.body_layout.addLayout(display_layout)

        self.compile_button = QPushButton("Preview Session Plan", self)
        self.compile_button.setObjectName("compile_session_button")
        self.compile_button.clicked.connect(self.compile_session)
        self.compile_button.setProperty("secondaryActionRole", "true")
        self.launch_button = QPushButton("Launch Experiment", self)
        self.launch_button.setObjectName("launch_test_session_button")
        self.launch_button.setProperty("launchActionRole", "primary")
        self.launch_button.setProperty("primaryActionRole", "true")
        self.launch_button.setToolTip(
            "Launch Experiment on the current alpha test-mode runtime path."
        )
        self.launch_button.setMinimumHeight(42)
        self.launch_button.clicked.connect(self.launch_test_session)

        button_row = QWidget(self)
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(PAGE_SECTION_GAP)
        button_layout.addWidget(self.compile_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.launch_button)

        controls_card = SectionCard(
            title="Run Controls",
            subtitle="Preview first, then launch with one primary action.",
            object_name="run_controls_card",
            parent=self,
        )
        controls_card.layout().setContentsMargins(12, 10, 12, 10)
        controls_card.layout().setSpacing(8)
        controls_card.body_layout.setSpacing(8)
        controls_card.body_layout.addWidget(button_row)

        self.summary_stack = QStackedWidget(self)
        self.summary_stack.setObjectName("run_summary_stack")
        self.summary_empty_panel = QFrame(self.summary_stack)
        self.summary_empty_panel.setObjectName("run_summary_empty_state")
        empty_layout = QVBoxLayout(self.summary_empty_panel)
        empty_layout.setContentsMargins(16, 14, 16, 14)
        empty_layout.setSpacing(8)
        empty_title = QLabel("No session preview yet", self.summary_empty_panel)
        empty_title.setObjectName("run_summary_empty_title")
        empty_body = QLabel(
            "Preview the session plan to reveal block order, launch diagnostics, and feedback details.",
            self.summary_empty_panel,
        )
        empty_body.setObjectName("run_summary_empty_body")
        empty_body.setWordWrap(True)
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(empty_body)
        empty_layout.addStretch(1)

        self.summary_text = QPlainTextEdit(self.summary_stack)
        self.summary_text.setObjectName("session_summary_text")
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumBlockCount(500)
        self.summary_text.setPlaceholderText(
            "Preview the session plan or launch to populate runtime diagnostics."
        )

        self.summary_stack.addWidget(self.summary_empty_panel)
        self.summary_stack.addWidget(self.summary_text)

        summary_card = SectionCard(
            title="Session Summary & Runtime Feedback",
            subtitle="Structured preview and launch diagnostics.",
            object_name="run_summary_card",
            parent=self,
        )
        summary_card.layout().setContentsMargins(12, 10, 12, 10)
        summary_card.layout().setSpacing(8)
        summary_card.body_layout.setSpacing(8)
        summary_card.body_layout.addWidget(self.summary_stack)

        self.readiness_badge = StatusBadgeLabel("Status: Setup Required", self)
        self.readiness_badge.setObjectName("run_readiness_badge")
        self.readiness_badge.setMinimumHeight(34)

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
        readiness_card.layout().setContentsMargins(12, 10, 12, 10)
        readiness_card.layout().setSpacing(8)
        readiness_card.body_layout.setSpacing(8)
        readiness_card.body_layout.addWidget(self.readiness_badge)
        readiness_card.body_layout.addWidget(self.readiness_summary_value)
        readiness_card.body_layout.addWidget(self.readiness_checklist, 1)

        self.shell = NonHomePageShell(
            title="Run / Runtime",
            subtitle="Preview the session plan, review readiness, and launch from the supported alpha path.",
            layout_mode="three_column",
            width_preset="medium",
            parent=self,
        )
        self.shell.set_column_stretches(4, 3, 3)
        self.shell.add_column_widget(0, self.runtime_settings_editor)
        self.shell.add_column_widget(0, display_card)
        self.shell.add_column_widget(1, readiness_card, stretch=1)
        self.shell.add_column_widget(2, controls_card)
        self.shell.add_column_widget(2, summary_card, stretch=1)
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
            _show_runtime_error_dialog(self, "Compile Error", error)
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
            _show_runtime_error_dialog(self, "Preflight Error", error)
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
            _show_runtime_error_dialog(self, "Launch Blocked", error)
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
            _show_runtime_error_dialog(self, "Launch Error", error)
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
        dialog = _compat_progress_dialog("Launching experiment: Please wait", "", 0, 0, self)
        dialog.setWindowTitle("FPVS Studio")
        dialog.setCancelButton(None)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.show()
        QApplication.processEvents()
        try:
            from fpvs_studio.gui import main_window

            launch_interstitial_duration_ms = main_window._LAUNCH_INTERSTITIAL_DURATION_MS
            if launch_interstitial_duration_ms > 0:
                loop = QEventLoop(self)
                QTimer.singleShot(launch_interstitial_duration_ms, loop.quit)
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
                self.summary_stack.setCurrentWidget(self.summary_text)
                lines = [f"- {issue.message}" for issue in validation.issues]
                self.summary_text.setPlainText("\n".join(lines))
                return
            self.summary_text.clear()
            self.summary_stack.setCurrentWidget(self.summary_empty_panel)
            return
        self._set_summary(session_plan)

    def _refresh_readiness_panel(self) -> None:
        report = self._status_report()
        self.readiness_badge.set_state(report.badge_state, f"Status: {report.status_label}")
        summary_text = report.status_summary
        if report.preview_note:
            summary_text = f"{summary_text} {report.preview_note}"
        self.readiness_summary_value.setText(summary_text)
        _set_list_items(self.readiness_checklist, report.readiness_items)

    def _set_summary(self, session_plan, *, extra_lines: list[str] | None = None) -> None:
        self.summary_stack.setCurrentWidget(self.summary_text)
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
