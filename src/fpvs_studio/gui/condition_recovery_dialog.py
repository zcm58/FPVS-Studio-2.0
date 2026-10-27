"""Project-local interruption guidance; all evidence interpretation stays in runtime."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.components import (
    apply_studio_theme,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.update_lifecycle import update_lifecycle
from fpvs_studio.gui.workers import BackgroundTask
from fpvs_studio.runtime.condition_recovery import (
    ConditionRecoveryReport,
    InterruptedCondition,
    acknowledge_condition_recovery,
    query_condition_recovery,
)


class ConditionRecoveryDialog(QDialog):
    """Offer explicit, occurrence-specific recovery without changing saved evidence."""

    rerun_requested = Signal(object)
    acknowledgement_requested = Signal()

    def __init__(
        self, report: ConditionRecoveryReport, parent: QWidget | None = None,
        *, current_condition_ids: frozenset[str] = frozenset(),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Interrupted Sessions")
        self.setObjectName("condition_recovery_dialog")
        self.setMinimumSize(640, 440)
        self.resize(760, 520)
        self._records = report.records
        self._current_condition_ids = current_condition_ids
        self._saving = False
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        self.summary_label = QLabel(
            (
                "Completion was not confirmed for these sessions. Acknowledge to stop "
                "reminders on project open."
                if self.pending_records() else "These session notices were acknowledged."
            ) if report.records else "No interrupted conditions were found.", self,
        )
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)
        self.condition_combo = QComboBox(self)
        self.condition_combo.setMinimumWidth(0)
        self.condition_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon,
        )
        self.condition_combo.setMinimumContentsLength(20)
        for record in report.records:
            label = (
                f"Participant {record.participant_number}"
                f" · Session {record.participant_session_number}"
                f" · Run {record.run_ordinal}/{record.total_runs} · {record.condition_name}"
                + (" · Acknowledged" if record.acknowledged_at is not None else "")
            )
            self.condition_combo.addItem(label)
            self.condition_combo.setItemData(
                self.condition_combo.count() - 1, label, Qt.ItemDataRole.ToolTipRole,
            )
        self.condition_combo.setVisible(bool(report.records))
        root.addWidget(self.condition_combo)
        self.details = QTextEdit(self)
        self.details.setReadOnly(True)
        self.details.setAccessibleName("Interrupted condition details")
        root.addWidget(self.details, 1)
        self.confirmation = QCheckBox("Before re-running, I confirm this session has ended.", self)
        root.addWidget(self.confirmation)
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        root.addWidget(self.status_label)
        actions = QVBoxLayout()
        actions.setSpacing(8)
        rerun_actions = QHBoxLayout()
        acknowledgement_actions = QHBoxLayout()
        self.rerun_button = QPushButton("Re-run This Condition…", self)
        mark_secondary_action(self.rerun_button)
        self.acknowledge_button = QPushButton(self)
        mark_primary_action(self.acknowledge_button)
        self.acknowledge_button.setToolTip(
            "Stop opening reminders. Session records stay unchanged and available for review."
        )
        self.acknowledge_button.setDefault(True)
        self.close_button = QPushButton("Close", self)
        rerun_actions.addWidget(self.rerun_button)
        rerun_actions.addStretch(1)
        acknowledgement_actions.addStretch(1)
        acknowledgement_actions.addWidget(self.acknowledge_button)
        acknowledgement_actions.addWidget(self.close_button)
        actions.addLayout(rerun_actions)
        actions.addLayout(acknowledgement_actions)
        root.addLayout(actions)
        self._warnings = report.warnings
        self.condition_combo.currentIndexChanged.connect(self._refresh)
        self.confirmation.toggled.connect(self._refresh_button)
        self.rerun_button.clicked.connect(self._request_rerun)
        self.acknowledge_button.clicked.connect(self.acknowledgement_requested)
        self.close_button.clicked.connect(self.close)
        self._refresh()
        apply_studio_theme(self)

    def selected_record(self) -> InterruptedCondition | None:
        index = self.condition_combo.currentIndex()
        return self._records[index] if 0 <= index < len(self._records) else None

    def pending_records(self) -> tuple[InterruptedCondition, ...]:
        return tuple(record for record in self._records if record.acknowledged_at is None)

    def set_saving(self, saving: bool) -> None:
        self._saving = saving
        self.condition_combo.setEnabled(not saving)
        self.confirmation.setEnabled(not saving)
        self.close_button.setEnabled(not saving)
        self.status_label.setText("Saving acknowledgement…" if saving else "")
        self.status_label.setToolTip("")
        self.status_label.setVisible(saving)
        self._refresh_button()

    def show_save_error(self, error: Exception) -> None:
        self.status_label.setText(
            "Could not save acknowledgement. Check project permissions and try again."
        )
        self.status_label.setToolTip(str(error))
        self.status_label.setVisible(True)

    def close_for_project(self) -> None:
        """Project/window teardown can hide this view while its app-owned write finishes."""
        self.set_saving(False)
        self.close()

    def reject(self) -> None:
        if not self._saving:
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._saving:
            event.ignore()
        else:
            super().closeEvent(event)

    def _refresh(self, _index: int = -1) -> None:
        self.confirmation.setChecked(False)
        record = self.selected_record()
        lines: list[str] = []
        if record is not None:
            stage = (
                "pre-condition activities or playback; completion unconfirmed"
                if record.stage == "armed" else record.stage.replace("_", " ")
            )
            self.condition_combo.setToolTip(self.condition_combo.currentText())
            lines.extend([
                f"Participant {record.participant_number}"
                f" — session {record.participant_session_number}",
                f"Run {record.run_ordinal} of {record.total_runs}: {record.condition_name}",
                f"Condition ID: {record.condition_id}",
                "",
                ("Stimulus playback completed; a later activity or finalization was interrupted."
                 if record.playback_completed else "This condition was not recorded as complete."),
                f"Last recorded stage: {stage}.",
                f"Completed runs retained: {len(record.completed_run_ids)}.",
                *record.completed_run_labels,
                "",
                "Not started:",
                *(record.not_started_run_labels or ("None.",)),
                "",
                "Re-running repeats this one condition, including its before/after activities, "
                "as a new participant visit. Existing results are preserved.",
            ])
            if record.status == "unverified":
                lines.extend(["", "Older evidence cannot establish whether another Studio "
                              "process is still running this session. Confirm it has ended first."])
            if record.acknowledged_at is not None:
                lines.extend([
                    "", f"Acknowledged: {record.acknowledged_at.isoformat(timespec='seconds')}",
                    "Its opening reminder has been dismissed. The session record is unchanged.",
                ])
            if not record.can_rerun:
                lines.extend(["", "The original compiled condition is unavailable. Review the "
                              "current project setup before preparing a replacement run. "
                              "It will use current settings and a new randomized schedule."])
                if record.condition_id not in self._current_condition_ids:
                    lines.append("This condition is no longer available in the current project.")
            lines.extend(["", f"Evidence: {record.evidence_path}"])
        lines.extend(["", *self._warnings])
        self.details.setPlainText("\n".join(lines).strip())
        self.confirmation.setVisible(record is not None and record.status == "unverified")
        self.rerun_button.setText(
            "Re-run with Current Setup…" if record is not None and not record.can_rerun
            else "Re-run This Condition…",
        )
        self._refresh_button()

    def _refresh_button(self, _checked: bool = False) -> None:
        record = self.selected_record()
        self.rerun_button.setEnabled(bool(
            not self._saving and record is not None
            and (record.can_rerun or record.condition_id in self._current_condition_ids)
            and (record.status != "unverified" or self.confirmation.isChecked())
        ))
        pending = self.pending_records()
        self.acknowledge_button.setText(
            "Saving…" if self._saving else
            "Acknowledge All and Continue" if len(pending) > 1 else
            "Acknowledge and Continue" if pending else "Acknowledged"
        )
        self.acknowledge_button.setEnabled(bool(pending) and not self._saving)
        self.acknowledge_button.setVisible(bool(self._records))

    def _request_rerun(self) -> None:
        record = self.selected_record()
        if record is not None and self.rerun_button.isEnabled():
            self.rerun_requested.emit(record)


class ConditionRecoveryController(QObject):
    """Read evidence off the GUI thread and ignore results during presentation."""

    def __init__(
        self, *, parent: QWidget, project_root: Path, is_busy: Callable[[], bool],
        rerun: Callable[[InterruptedCondition], None],
        show_error: Callable[[Exception], None],
        current_condition_ids: Callable[[], frozenset[str]] = frozenset,
    ) -> None:
        super().__init__(parent)
        self._window = parent
        self._project_root = project_root
        self._is_busy = is_busy
        self._rerun = rerun
        self._show_error = show_error
        self._current_condition_ids = current_condition_ids
        self._task: BackgroundTask | None = None
        self._dialog: ConditionRecoveryDialog | None = None
        self._ack_task: BackgroundTask | None = None
        self._ack_saved = False
        self._ack_error: Exception | None = None
        self._seen: set[tuple[str, str, str, str]] = set()
        self._seen_warnings: set[str] = set()
        self._active = True

    def _available(self) -> bool:
        return (
            self._active and self._window.isVisible() and not self._is_busy()
            and not update_lifecycle().is_shutting_down
        )

    def check(self, *, automatic: bool = False) -> None:
        if self._task is not None or self._ack_task is not None or not self._available():
            return
        task = BackgroundTask(
            parent_widget=self._window,
            callback=lambda: query_condition_recovery(
                self._project_root, include_acknowledged=not automatic,
            ),
        )
        self._task = task
        task.succeeded.connect(lambda result: self._loaded(result, automatic=automatic))
        task.failed.connect(self._failed)
        task.finished.connect(self._finished)
        task.start()

    def _finished(self) -> None:
        self._task = None

    def _failed(self, error: object) -> None:
        if self._available():
            self._show_error(error if isinstance(error, Exception) else RuntimeError(str(error)))

    def _loaded(self, result: object, *, automatic: bool) -> None:
        if (
            not isinstance(result, ConditionRecoveryReport) or not self._available()
            or self._ack_task is not None
        ):
            return
        keys: set[tuple[str, str, str, str]] = {
            (item.execution_id, item.run_id, item.stage, item.updated_at.isoformat())
            for item in result.records
        }
        new_warnings = set(result.warnings) - self._seen_warnings
        if automatic and not (keys - self._seen) and not new_warnings:
            return
        self._seen.update(keys)
        self._seen_warnings.update(result.warnings)
        if self._dialog is not None:
            self._dialog.close()
            self._dialog.deleteLater()
        dialog = ConditionRecoveryDialog(
            result, self._window, current_condition_ids=self._current_condition_ids(),
        )
        self._dialog = dialog
        dialog.rerun_requested.connect(self._request_rerun)
        dialog.acknowledgement_requested.connect(lambda: self._acknowledge(dialog))
        dialog.show()
        dialog.raise_()

    def close_dialog(self) -> None:
        if self._dialog is not None:
            self._dialog.close_for_project()

    def _request_rerun(self, record: InterruptedCondition) -> None:
        if self._available() and self._ack_task is None:
            self._rerun(record)

    def _acknowledge(self, dialog: ConditionRecoveryDialog) -> None:
        if self._ack_task is not None or not self._available() or self._dialog is not dialog:
            return
        records = dialog.pending_records()
        if not records:
            return
        dialog.set_saving(True)
        self._ack_saved = False
        self._ack_error = None
        task = BackgroundTask(
            parent_widget=self._window,
            callback=lambda: acknowledge_condition_recovery(self._project_root, records),
        )
        self._ack_task = task
        task.succeeded.connect(lambda _result: self._ack_succeeded())
        task.failed.connect(self._ack_failed)
        task.finished.connect(lambda: self._ack_finished(task, dialog))
        task.start()

    def _ack_succeeded(self) -> None:
        self._ack_saved = True

    def _ack_failed(self, error: object) -> None:
        self._ack_error = error if isinstance(error, Exception) else RuntimeError(str(error))

    def _ack_finished(self, task: BackgroundTask, dialog: ConditionRecoveryDialog) -> None:
        if self._ack_task is not task:
            return
        self._ack_task = None
        if not self._active or self._dialog is not dialog:
            return
        dialog.set_saving(False)
        if update_lifecycle().is_shutting_down:
            return
        if self._ack_error is not None:
            dialog.show_save_error(self._ack_error)
            if self._available():
                self._show_error(self._ack_error)
        elif self._ack_saved:
            dialog.accept()

    def deactivate(self) -> None:
        """Discard late results after this project window is closed or replaced."""
        self._active = False
        self.close_dialog()
