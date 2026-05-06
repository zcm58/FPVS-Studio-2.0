"""Run and launch page for the FPVS Studio main window."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.gui.components import (
    PAGE_SECTION_GAP,
    NonHomePageShell,
    SectionCard,
    StatusBadgeLabel,
    mark_launch_action,
    mark_secondary_action,
)
from fpvs_studio.gui.document import DocumentError, LaunchSummary, ProjectDocument
from fpvs_studio.gui.runtime_settings_page import RuntimeSettingsEditor
from fpvs_studio.gui.window_helpers import (
    LauncherReadinessReport,
    _configure_read_only_list,
    _launcher_readiness_report,
    _set_list_items,
)
from fpvs_studio.gui.workers import ProgressTask


def _compat_progress_dialog(
    label: str,
    cancel_text: str,
    minimum: int,
    maximum: int,
    parent: QWidget,
) -> QProgressDialog:
    from fpvs_studio.gui import main_window

    return main_window.QProgressDialog(label, cancel_text, minimum, maximum, parent)


def _show_runtime_error_dialog(parent: QWidget, title: str, error: Exception) -> None:
    from fpvs_studio.gui import main_window

    main_window._show_error_dialog(parent, title, error)


class ParticipantNumberDialog(QDialog):
    """Collect the required launch-time participant number."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Participant Number")
        self.setModal(True)
        self.resize(420, 120)

        self.prompt_label = QLabel("Please enter the participant number.", self)
        self.prompt_label.setObjectName("participant_number_prompt_label")

        self.participant_number_edit = QLineEdit(self)
        self.participant_number_edit.setObjectName("participant_number_edit")
        self.participant_number_edit.setPlaceholderText("Digits only (for example, 0012)")
        self.participant_number_edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
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

class RunPage(QWidget):
    """Session compile and launch page with detailed runtime diagnostics."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        fullscreen_state_getter: Callable[[], bool] | None = None,
        fullscreen_state_setter: Callable[[bool], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._active_launch_task: ProgressTask | None = None
        self._active_launch_session_plan: SessionPlan | None = None
        self._active_launch_participant_number: str | None = None

        self.runtime_settings_editor = RuntimeSettingsEditor(
            document,
            fullscreen_state_getter=fullscreen_state_getter,
            fullscreen_state_setter=fullscreen_state_setter,
            parent=self,
        )
        self.refresh_hz_spin = self.runtime_settings_editor.refresh_hz_spin
        self.runtime_background_color_combo = (
            self.runtime_settings_editor.runtime_background_color_combo
        )
        self.runtime_background_scope_label = (
            self.runtime_settings_editor.runtime_background_scope_label
        )
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
            object_name="run_display_card",
            parent=self,
        )
        display_card.card_layout.setContentsMargins(12, 10, 12, 10)
        display_card.card_layout.setSpacing(8)
        display_card.body_layout.setSpacing(8)
        display_layout = QFormLayout()
        display_layout.setVerticalSpacing(8)
        display_layout.addRow("Display Index", self.display_index_edit)
        display_layout.addRow("Engine", self.engine_name_value)
        display_card.body_layout.addLayout(display_layout)

        self.compile_button = QPushButton("Preview Session Plan", self)
        self.compile_button.setObjectName("compile_session_button")
        self.compile_button.clicked.connect(self.compile_session)
        mark_secondary_action(self.compile_button)
        self.launch_button = QPushButton("Launch Experiment", self)
        self.launch_button.setObjectName("launch_test_session_button")
        mark_launch_action(self.launch_button)
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
            object_name="run_controls_card",
            parent=self,
        )
        controls_card.card_layout.setContentsMargins(12, 10, 12, 10)
        controls_card.card_layout.setSpacing(8)
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
            "Preview the session plan to reveal block order, launch diagnostics, "
            "and feedback details.",
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
            object_name="run_summary_card",
            parent=self,
        )
        summary_card.card_layout.setContentsMargins(12, 10, 12, 10)
        summary_card.card_layout.setSpacing(8)
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
            object_name="run_readiness_card",
            parent=self,
        )
        readiness_card.card_layout.setContentsMargins(12, 10, 12, 10)
        readiness_card.card_layout.setSpacing(8)
        readiness_card.body_layout.setSpacing(8)
        readiness_card.body_layout.addWidget(self.readiness_badge)
        readiness_card.body_layout.addWidget(self.readiness_summary_value)
        readiness_card.body_layout.addWidget(self.readiness_checklist, 1)

        self.shell = NonHomePageShell(
            title="Run / Runtime",
            subtitle="",
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
        if self._active_launch_task is not None:
            return
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
        display_fullscreen = self.fullscreen_checkbox.isChecked()

        def _launch() -> LaunchSummary:
            return self._document.launch_compiled_session(
                session_plan,
                participant_number=participant_number,
                display_index=display_index,
                fullscreen=display_fullscreen,
            )

        self._active_launch_session_plan = session_plan
        self._active_launch_participant_number = participant_number
        task = ProgressTask(
            parent_widget=self,
            label="Launching experiment: Please wait",
            callback=_launch,
            dialog_factory=_compat_progress_dialog,
            window_title="FPVS Studio",
        )
        self._active_launch_task = task
        self._update_launch_buttons()
        task.succeeded.connect(self._on_launch_succeeded)
        task.failed.connect(self._on_launch_failed)
        task.finished.connect(self._on_launch_finished)
        task.start()

    def _on_launch_succeeded(self, result: object) -> None:
        if not isinstance(result, LaunchSummary):
            _show_runtime_error_dialog(
                self,
                "Launch Error",
                RuntimeError("Runtime launch returned an unexpected result."),
            )
            return
        session_plan = self._active_launch_session_plan
        participant_number = self._active_launch_participant_number
        if session_plan is None or participant_number is None:
            return
        self._apply_launch_summary(session_plan, participant_number, result)

    def _on_launch_failed(self, error: object) -> None:
        if isinstance(error, Exception):
            _show_runtime_error_dialog(self, "Launch Error", error)
        else:
            _show_runtime_error_dialog(self, "Launch Error", RuntimeError(str(error)))

    def _on_launch_finished(self) -> None:
        self._active_launch_task = None
        self._active_launch_session_plan = None
        self._active_launch_participant_number = None
        self._update_launch_buttons()

    def _update_launch_buttons(self) -> None:
        is_busy = self._active_launch_task is not None
        self.compile_button.setEnabled(not is_busy)
        self.launch_button.setEnabled(not is_busy)

    def _apply_launch_summary(
        self,
        session_plan: SessionPlan,
        participant_number: str,
        summary: LaunchSummary,
    ) -> None:
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
                f"Warning: logs indicate that {participant_number} has already "
                "completed this study, "
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

    def _set_summary(
        self, session_plan: SessionPlan, *, extra_lines: list[str] | None = None
    ) -> None:
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
            lines.append(f"Block {block.block_index + 1}: " + " -> ".join(block.condition_order))
        if extra_lines:
            lines.extend(["", *extra_lines])
        self.summary_text.setPlainText("\n".join(lines))
        self._refresh_readiness_panel()
