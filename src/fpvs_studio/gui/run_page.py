"""Run and launch page for the FPVS Studio main window."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
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

from fpvs_studio.core.execution import PARTICIPANT_SEX_VALUES, ParticipantMetadata
from fpvs_studio.core.models import normalize_manual_removed_electrodes
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.gui import folder_actions
from fpvs_studio.gui.components import (
    PAGE_SECTION_GAP,
    NonHomePageShell,
    SectionCard,
    StatusBadgeLabel,
    mark_launch_action,
    mark_secondary_action,
)
from fpvs_studio.gui.document import LaunchSummary, ProjectDocument
from fpvs_studio.gui.document_support import DocumentError, format_validation_report
from fpvs_studio.gui.runtime_settings_page import DisplaySettingsEditor
from fpvs_studio.gui.window_helpers import (
    LauncherReadinessReport,
    _coerce_exception,
    _configure_read_only_list,
    _launcher_readiness_report,
    _set_list_items,
)
from fpvs_studio.gui.workers import ProgressTask

TEST_MODE_PARTICIPANT_NUMBER = "0"


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


@dataclass(frozen=True)
class ParticipantLaunchDetails:
    """Launch-time participant details collected by the GUI."""

    participant_number: str
    participant_metadata: ParticipantMetadata | None = None
    manual_removed_electrodes: tuple[str, ...] = ()


@dataclass(frozen=True)
class LaunchTaskResult:
    """Prepared session plan plus the resulting launch summary."""

    session_plan: SessionPlan
    summary: LaunchSummary


class ParticipantNumberDialog(QDialog):
    """Collect the required launch-time participant details."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        manual_removed_electrodes: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        super().__init__(parent)
        self._saved_manual_removed_electrodes = {
            key: tuple(value)
            for key, value in (manual_removed_electrodes or {}).items()
        }
        self.setWindowTitle("Participant Information")
        self.setModal(True)
        self.setMinimumSize(600, 360)
        self.resize(600, 360)

        self.prompt_label = QLabel("Please enter the participant details.", self)
        self.prompt_label.setObjectName("participant_number_prompt_label")

        self.participant_number_edit = QLineEdit(self)
        self.participant_number_edit.setObjectName("participant_number_edit")
        self.participant_number_edit.setPlaceholderText("Digits only (for example, 0012)")
        self.participant_number_edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.participant_number_edit.setFocus()

        self.age_edit = QLineEdit(self)
        self.age_edit.setObjectName("participant_age_edit")
        self.age_edit.setPlaceholderText("Whole number from 1 to 120")
        self.age_edit.setValidator(QIntValidator(1, 120, self.age_edit))
        self.age_edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

        self.sex_combo = QComboBox(self)
        self.sex_combo.setObjectName("participant_sex_combo")
        self.sex_combo.addItem("Select sex...", None)
        for value in sorted(PARTICIPANT_SEX_VALUES):
            self.sex_combo.addItem(value, value)

        self.handedness_combo = QComboBox(self)
        self.handedness_combo.setObjectName("participant_handedness_combo")
        self.handedness_combo.addItem("Select handedness...", None)
        for value in ["Right handed", "Left handed", "Ambidextrous"]:
            self.handedness_combo.addItem(value, value)

        self.colorblind_combo = QComboBox(self)
        self.colorblind_combo.setObjectName("participant_colorblind_combo")
        self.colorblind_combo.addItem("Select yes or no...", None)
        self.colorblind_combo.addItem("No", False)
        self.colorblind_combo.addItem("Yes", True)

        self.manual_removed_electrodes_edit = QLineEdit(self)
        self.manual_removed_electrodes_edit.setObjectName(
            "participant_manual_removed_electrodes_edit"
        )
        self.manual_removed_electrodes_edit.setPlaceholderText(
            "Input manually removed electrodes (optional)"
        )
        placeholder_width = (
            self.manual_removed_electrodes_edit.fontMetrics().horizontalAdvance(
                self.manual_removed_electrodes_edit.placeholderText()
            )
        )
        self.manual_removed_electrodes_edit.setMinimumWidth(placeholder_width + 32)
        self.manual_removed_electrodes_edit.setToolTip(
            "Enter electrodes physically removed or unplugged before recording. "
            "Separate labels with commas (for example, FT7, P9, Oz)."
        )
        self.manual_removed_electrodes_edit.setClearButtonEnabled(True)
        self.manual_removed_electrodes_edit.setLayoutDirection(
            Qt.LayoutDirection.LeftToRight
        )

        form_layout = QFormLayout()
        form_layout.addRow("Participant Number", self.participant_number_edit)
        form_layout.addRow("Age", self.age_edit)
        form_layout.addRow("Sex", self.sex_combo)
        form_layout.addRow("Handedness", self.handedness_combo)
        form_layout.addRow("Are you colorblind?", self.colorblind_combo)
        self.manual_removed_electrodes_label = QLabel(
            "Manually Removed Electrodes",
            self,
        )
        self.manual_removed_electrodes_label.setObjectName(
            "participant_manual_removed_electrodes_label"
        )
        self.manual_removed_electrodes_label.setBuddy(
            self.manual_removed_electrodes_edit
        )
        form_layout.addRow(self.manual_removed_electrodes_label)
        form_layout.addRow(self.manual_removed_electrodes_edit)

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

        self.participant_number_edit.textChanged.connect(
            self._prefill_manual_removed_electrodes
        )

    @property
    def participant_number(self) -> str:
        """Return the trimmed participant number value."""

        return self.participant_number_edit.text().strip()

    @property
    def participant_metadata(self) -> ParticipantMetadata:
        """Return validated launch-time participant metadata."""

        return ParticipantMetadata(
            age=int(self.age_edit.text().strip()),
            sex=self.sex_combo.currentData(),
            handedness=self.handedness_combo.currentData(),
            colorblind=self.colorblind_combo.currentData(),
        )

    @property
    def manual_removed_electrodes(self) -> tuple[str, ...]:
        """Return normalized manually removed electrode labels."""

        return tuple(
            normalize_manual_removed_electrodes(
                self.manual_removed_electrodes_edit.text()
            )
        )

    @property
    def participant_details(self) -> ParticipantLaunchDetails:
        """Return the full participant details captured by the dialog."""

        return ParticipantLaunchDetails(
            participant_number=self.participant_number,
            participant_metadata=self.participant_metadata,
            manual_removed_electrodes=self.manual_removed_electrodes,
        )

    def _prefill_manual_removed_electrodes(self, participant_number: str) -> None:
        saved = self._saved_manual_removed_electrodes.get(participant_number.strip(), ())
        self.manual_removed_electrodes_edit.setText(", ".join(saved))

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
        age_text = self.age_edit.text().strip()
        if not age_text:
            QMessageBox.warning(
                self,
                "Age Required",
                "Enter the participant age to launch the session.",
            )
            self.age_edit.setFocus()
            return
        if not age_text.isdigit() or int(age_text) < 1 or int(age_text) > 120:
            QMessageBox.warning(
                self,
                "Invalid Age",
                "Participant age must be a whole number from 1 to 120.",
            )
            self.age_edit.setFocus()
            self.age_edit.selectAll()
            return
        if self.sex_combo.currentData() is None:
            QMessageBox.warning(
                self,
                "Sex Required",
                "Select the participant sex to launch the session.",
            )
            self.sex_combo.setFocus()
            return
        if self.handedness_combo.currentData() is None:
            QMessageBox.warning(
                self,
                "Handedness Required",
                "Select the participant handedness to launch the session.",
            )
            self.handedness_combo.setFocus()
            return
        if self.colorblind_combo.currentData() is None:
            QMessageBox.warning(
                self,
                "Colorblind Status Required",
                "Select whether the participant is colorblind to launch the session.",
            )
            self.colorblind_combo.setFocus()
            return
        signals_were_blocked = self.participant_number_edit.blockSignals(True)
        try:
            self.participant_number_edit.setText(participant_number)
        finally:
            self.participant_number_edit.blockSignals(signals_were_blocked)
        self.age_edit.setText(age_text)
        super().accept()


class BioSemiRecordingConfirmationDialog(QDialog):
    """Require a Sophia Mode administrator confirmation before runtime launch."""

    CONFIRMATION_WORD = "confirm"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("biosemi_recording_confirmation_dialog")
        self.setWindowTitle("Sophia Mode Recording Check")
        self.setModal(True)
        self.resize(640, 260)

        self.prompt_label = QLabel(
            "NERD Lab Administrator: Sophia Mode is enabled. Confirm that the BioSemi "
            "PC is recording data, then type 'Confirm' to continue.",
            self,
        )
        self.prompt_label.setObjectName("biosemi_recording_confirmation_prompt")
        self.prompt_label.setWordWrap(True)

        self.confirmation_edit = QLineEdit(self)
        self.confirmation_edit.setObjectName("biosemi_recording_confirmation_edit")
        self.confirmation_edit.setPlaceholderText("Type Confirm to continue")
        self.confirmation_edit.setFocus()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.button_box.setObjectName("biosemi_recording_confirmation_button_box")
        self.continue_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.continue_button.setObjectName("biosemi_recording_confirmation_continue_button")
        self.continue_button.setText("Continue")
        self.continue_button.setEnabled(False)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.confirmation_edit.textChanged.connect(self._refresh_continue_enabled)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self.prompt_label)
        layout.addWidget(self.confirmation_edit)
        layout.addWidget(self.button_box)

    def accept(self) -> None:
        if not self._confirmation_matches():
            self.confirmation_edit.setFocus()
            return
        super().accept()

    def _refresh_continue_enabled(self) -> None:
        self.continue_button.setEnabled(self._confirmation_matches())

    def _confirmation_matches(self) -> bool:
        return (
            self.confirmation_edit.text().strip().casefold()
            == self.CONFIRMATION_WORD
        )


class TestModeLaunchConfirmationDialog(QDialog):
    """Require explicit acknowledgement of experiment test-mode limitations."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("test_mode_launch_confirmation_dialog")
        self.setWindowTitle("Confirm Experiment Test Launch")
        self.setModal(True)
        self.resize(700, 320)

        self.prompt_label = QLabel(
            "Experiment Test Mode is enabled. This launch verifies experiment setup "
            "and behavior without lab hardware. Serial-port validation and output, the "
            "Sophia Mode recording check, connected-display refresh verification, and "
            "participant information collection are disabled. The run uses reserved "
            "test ID 0. Fullscreen presentation, compiled timing and asset validation, "
            "runtime timing QC, condition tasks, and normal test outputs remain enabled.",
            self,
        )
        self.prompt_label.setObjectName("test_mode_launch_confirmation_prompt")
        self.prompt_label.setWordWrap(True)

        self.acknowledgement_checkbox = QCheckBox(
            "I understand this is a non-participant test launch.",
            self,
        )
        self.acknowledgement_checkbox.setObjectName("test_mode_launch_acknowledgement_checkbox")

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.button_box.setObjectName("test_mode_launch_confirmation_button_box")
        self.launch_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.launch_button.setObjectName("test_mode_launch_confirmation_continue_button")
        self.launch_button.setText("Launch Test")
        self.launch_button.setEnabled(False)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.acknowledgement_checkbox.toggled.connect(self.launch_button.setEnabled)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self.prompt_label)
        layout.addWidget(self.acknowledgement_checkbox)
        layout.addWidget(self.button_box)

    def accept(self) -> None:
        if not self.acknowledgement_checkbox.isChecked():
            self.acknowledgement_checkbox.setFocus()
            return
        super().accept()


def _coerce_participant_launch_details(
    value: str | ParticipantLaunchDetails | None,
) -> ParticipantLaunchDetails | None:
    if value is None:
        return None
    if isinstance(value, ParticipantLaunchDetails):
        return value
    return ParticipantLaunchDetails(participant_number=value.strip())


def _participant_metadata_summary_lines(metadata: ParticipantMetadata) -> list[str]:
    if metadata.is_empty:
        return []
    lines: list[str] = []
    if metadata.age is not None:
        lines.append(f"Participant Age: {metadata.age}")
    if metadata.sex is not None:
        lines.append(f"Participant Sex: {metadata.sex}")
    if metadata.handedness is not None:
        lines.append(f"Participant Handedness: {metadata.handedness}")
    if metadata.colorblind is not None:
        colorblind_label = "Yes" if metadata.colorblind else "No"
        lines.append(f"Participant Colorblind: {colorblind_label}")
    return lines


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
        self._active_launch_participant_number: str | None = None
        self._last_run_output_dir: str | None = None

        self.runtime_settings_editor = DisplaySettingsEditor(
            document,
            framed=True,
            parent=self,
        )
        self.refresh_hz_combo = self.runtime_settings_editor.refresh_hz_combo
        self.runtime_background_color_combo = (
            self.runtime_settings_editor.runtime_background_color_combo
        )
        self.runtime_background_scope_label = (
            self.runtime_settings_editor.runtime_background_scope_label
        )

        self.compile_button = QPushButton("Preview Session Plan", self)
        self.compile_button.setObjectName("compile_session_button")
        self.compile_button.clicked.connect(self.compile_session)
        mark_secondary_action(self.compile_button)
        self.launch_button = QPushButton("Launch Experiment", self)
        self.launch_button.setObjectName("launch_session_button")
        mark_launch_action(self.launch_button)
        self.launch_button.setToolTip(
            "Launch Experiment with fullscreen display verification and timing checks."
        )
        self.launch_button.setMinimumHeight(42)
        self.launch_button.clicked.connect(self.launch_session)

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
        self.open_run_folder_button = QPushButton("Open Run Folder", summary_card)
        self.open_run_folder_button.setObjectName("run_open_folder_button")
        self.open_run_folder_button.clicked.connect(self._open_run_folder)
        mark_secondary_action(self.open_run_folder_button)
        self.copy_run_folder_button = QPushButton("Copy Run Folder", summary_card)
        self.copy_run_folder_button.setObjectName("run_copy_folder_button")
        self.copy_run_folder_button.clicked.connect(self._copy_run_folder)
        mark_secondary_action(self.copy_run_folder_button)
        run_action_row = QHBoxLayout()
        run_action_row.addStretch(1)
        run_action_row.addWidget(self.open_run_folder_button)
        run_action_row.addWidget(self.copy_run_folder_button)
        summary_card.body_layout.addLayout(run_action_row)

        self.readiness_badge = StatusBadgeLabel("Setup Required", self)
        self.readiness_badge.setObjectName("run_readiness_badge")
        self.readiness_badge.setMinimumHeight(34)
        self.readiness_badge.setMinimumWidth(224)

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
        self.shell.add_column_widget(1, readiness_card, stretch=1)
        self.shell.add_column_widget(2, controls_card)
        self.shell.add_column_widget(2, summary_card, stretch=1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.shell)

        self._document.project_changed.connect(self.refresh)
        self._document.session_plan_changed.connect(self._refresh_summary)
        self._refresh_run_output_actions()
        self.refresh()

    def current_refresh_hz(self) -> float:
        return self.runtime_settings_editor.current_refresh_hz()

    def sync_fullscreen_checkbox(self, _checked: bool) -> None:
        return

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
            session_plan = self._document.preflight_session(refresh_hz=self.current_refresh_hz())
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
            "Preflight succeeded for the current session launch.",
        )

    def launch_session(self) -> None:
        if self._active_launch_task is not None:
            return
        try:
            refresh_hz = self.current_refresh_hz()
            validation = self._document.validation_report(refresh_hz=refresh_hz)
            if not validation.is_valid:
                raise DocumentError(format_validation_report(validation))
        except Exception as error:
            _show_runtime_error_dialog(self, "Launch Blocked", error)
            return

        participant_details = self._collect_launch_participant_details()
        if participant_details is None:
            return
        participant_number = participant_details.participant_number
        if not self._document.experiment_test_mode_enabled:
            try:
                self._document.update_manual_removed_electrodes(
                    participant_number,
                    participant_details.manual_removed_electrodes,
                )
                self._document.save()
            except Exception as error:
                _show_runtime_error_dialog(self, "Launch Blocked", error)
                return
        try:
            session_plan = self._document.compile_session(refresh_hz=refresh_hz)
        except Exception as error:
            _show_runtime_error_dialog(self, "Launch Blocked", error)
            return
        self._set_summary(
            session_plan,
            extra_lines=["Status: launch checks queued."],
        )
        if (
            self._document.require_biosemi_recording_confirmation
            and not self._confirm_biosemi_recording_started()
        ):
            return

        def _launch() -> LaunchTaskResult:
            self._document.preflight_compiled_session(session_plan)
            summary = self._document.launch_compiled_session(
                session_plan,
                participant_number=participant_number,
                participant_metadata=participant_details.participant_metadata,
                display_index=None,
                fullscreen=True,
            )
            return LaunchTaskResult(session_plan=session_plan, summary=summary)

        self._active_launch_participant_number = participant_number
        self._last_run_output_dir = None
        self._refresh_run_output_actions()
        task = ProgressTask(
            parent_widget=self,
            label="Launching experiment: Please wait",
            callback=_launch,
            dialog_factory=_compat_progress_dialog,
            window_title="FPVS Studio",
            persistent_thread=True,
        )
        self._active_launch_task = task
        self._update_launch_buttons()
        task.succeeded.connect(self._on_launch_succeeded)
        task.failed.connect(self._on_launch_failed)
        task.finished.connect(self._on_launch_finished)
        task.start()

    def _on_launch_succeeded(self, result: object) -> None:
        if not isinstance(result, LaunchTaskResult):
            _show_runtime_error_dialog(
                self,
                "Launch Error",
                RuntimeError("Runtime launch returned an unexpected result."),
            )
            return
        participant_number = self._active_launch_participant_number
        if participant_number is None:
            return
        self._apply_launch_summary(result.session_plan, participant_number, result.summary)

    def _on_launch_failed(self, error: object) -> None:
        _show_runtime_error_dialog(self, "Launch Error", _coerce_exception(error))

    def _on_launch_finished(self) -> None:
        self._active_launch_task = None
        self._active_launch_participant_number = None
        self._update_launch_buttons()

    def _update_launch_buttons(
        self,
        status_report: LauncherReadinessReport | None = None,
    ) -> None:
        is_busy = self._active_launch_task is not None
        if status_report is None:
            status_report = self._status_report()
        launch_ready = status_report.badge_state == "ready" or (
            status_report.status_label == "Validation Issues"
        )
        self.compile_button.setEnabled(not is_busy)
        self.launch_button.setEnabled(not is_busy and launch_ready)

    def _apply_launch_summary(
        self,
        session_plan: SessionPlan,
        participant_number: str,
        summary: LaunchSummary,
    ) -> None:
        output_line = (
            f"Output Dir: {summary.output_dir}"
            if summary.output_dir
            else "Output: Compact summary logs"
        )
        self._last_run_output_dir = summary.output_dir
        self._refresh_run_output_actions()
        participant_value = summary.participant_number or participant_number
        participant_metadata_lines = _participant_metadata_summary_lines(
            summary.participant_metadata
        )
        identity_line = (
            f"Launch Mode: Experiment Test (reserved ID {participant_value})"
            if self._document.experiment_test_mode_enabled
            else f"Participant Number: {participant_value}"
        )
        if summary.aborted:
            abort_reason = summary.abort_reason or "No abort reason was provided."
            extra_lines = [
                "Status: runtime launch aborted.",
                identity_line,
                *participant_metadata_lines,
                output_line,
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
                "The experiment aborted.\n\n"
                f"Reason: {abort_reason}\n"
                "Completed Conditions: "
                f"{summary.completed_condition_count}/{summary.total_condition_count}\n"
                f"{output_line}\n\n"
                + (
                    "Review run exports in the project runs folder."
                    if summary.output_dir
                    else "Review participant summary files in the project logs folder."
                ),
            )
            return
        extra_lines = [
            "Status: runtime launch completed.",
            identity_line,
            *participant_metadata_lines,
            output_line,
        ]
        self._set_summary(session_plan, extra_lines=extra_lines)
        QMessageBox.information(
            self,
            "Launch Complete",
            (
                "The experiment finished. "
                "Review run exports in the project runs folder."
            )
            if summary.output_dir
            else (
                "The experiment finished. "
                "Review participant summary files in the project logs folder."
            ),
        )

    def _prompt_participant_number(self) -> str | ParticipantLaunchDetails | None:
        dialog = ParticipantNumberDialog(
            self,
            manual_removed_electrodes=self._document.project.manual_removed_electrodes,
        )
        if dialog.exec() != int(QDialog.DialogCode.Accepted):
            return None
        return dialog.participant_details

    def _confirm_biosemi_recording_started(self) -> bool:
        dialog = BioSemiRecordingConfirmationDialog(self)
        return dialog.exec() == int(QDialog.DialogCode.Accepted)

    def _confirm_test_mode_launch(self) -> bool:
        dialog = TestModeLaunchConfirmationDialog(self)
        return dialog.exec() == int(QDialog.DialogCode.Accepted)

    def _collect_launch_participant_details(self) -> ParticipantLaunchDetails | None:
        if self._document.experiment_test_mode_enabled:
            if not self._confirm_test_mode_launch():
                return None
            return ParticipantLaunchDetails(participant_number=TEST_MODE_PARTICIPANT_NUMBER)
        while True:
            participant_details = _coerce_participant_launch_details(
                self._prompt_participant_number()
            )
            if participant_details is None:
                return None
            participant_number = participant_details.participant_number

            if not self._document.has_completed_session_for_participant(participant_number):
                return participant_details

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
                return participant_details

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
        self.readiness_badge.set_state(report.badge_state, report.status_label)
        summary_text = report.status_summary
        if report.preview_note:
            summary_text = f"{summary_text} {report.preview_note}"
        self.readiness_summary_value.setText(summary_text)
        _set_list_items(self.readiness_checklist, report.readiness_items)
        self._update_launch_buttons(report)

    def _set_summary(
        self, session_plan: SessionPlan, *, extra_lines: list[str] | None = None
    ) -> None:
        self.summary_stack.setCurrentWidget(self.summary_text)
        lines = [
            f"Session ID: {session_plan.session_id}",
            f"Random Order Seed: {session_plan.random_seed}",
            f"Block Count: {session_plan.block_count}",
            f"Run Count: {session_plan.total_runs}",
            f"Refresh (Hz): {session_plan.refresh_hz:.2f}",
            "Condition Start: Press Space to begin",
        ]
        lines.append("")
        for block in session_plan.blocks:
            lines.append(f"Block {block.block_index + 1}: " + " -> ".join(block.condition_order))
        if extra_lines:
            lines.extend(["", *extra_lines])
        self.summary_text.setPlainText("\n".join(lines))
        self._refresh_readiness_panel()

    def _refresh_run_output_actions(self) -> None:
        has_output = bool(self._last_run_output_dir)
        self.open_run_folder_button.setEnabled(has_output)
        self.copy_run_folder_button.setEnabled(has_output)
        self.open_run_folder_button.setVisible(has_output)
        self.copy_run_folder_button.setVisible(has_output)

    def _open_run_folder(self) -> None:
        if self._last_run_output_dir:
            folder_actions.open_folder(self._last_run_output_dir)

    def _copy_run_folder(self) -> None:
        if self._last_run_output_dir:
            QApplication.clipboard().setText(self._last_run_output_dir)
