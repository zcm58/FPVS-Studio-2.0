"""Read-only burst recall results and explicit Excel export for the active project."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.components import (
    PathValueLabel,
    SectionCard,
    StatusBadgeLabel,
    apply_studio_theme,
    mark_secondary_action,
)
from fpvs_studio.gui.workers import BackgroundTask
from fpvs_studio.runtime.attentional_blink_report import (
    AttentionalBlinkDataSummary,
    load_attentional_blink_data,
    write_attentional_blink_accuracy_xlsx,
)

LOGGER = logging.getLogger(__name__)


class AttentionalBlinkDataDialog(QDialog):
    """Keep scoring in runtime while making answers and burst order inspectable."""

    def __init__(self, *, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("attentional_blink_data_dialog")
        self.setWindowTitle("T1 and T2 Accuracy — FPVS Studio")
        self.setMinimumSize(920, 600)
        self.resize(1080, 680)
        self._project_root = Path(project_root)
        self._summary: AttentionalBlinkDataSummary | None = None
        self._active_load_task: BackgroundTask | None = None
        self._active_export_task: BackgroundTask | None = None
        self.state_name = "loading"
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)
        self.data_card = SectionCard(
            title="T1 and T2 Accuracy",
            subtitle="Compare T1 and T2 recall by SOA and inspect learning across numbered bursts.",
            object_name="attentional_blink_data_card", parent=self,
        )
        root.addWidget(self.data_card, 1)
        self.status_badge = StatusBadgeLabel(parent=self)
        self.data_card.body_layout.addWidget(self.status_badge)
        self.summary_label = QLabel(self)
        self.summary_label.setWordWrap(True)
        self.data_card.body_layout.addWidget(self.summary_label)
        self.inclusion_label = QLabel(
            "Accuracy uses valid answers from completed stimulus bursts, including test sessions "
            "marked Test below. "
            "T1 and T2 have separate answer counts. "
            "Partial and aborted bursts remain "
            "visible; an answered T1 is retained if T2 or the session is later aborted. "
            "Stimulus time excludes questions and breaks.", self,
        )
        self.inclusion_label.setWordWrap(True)
        self.inclusion_label.setProperty("sectionCardRole", "subtitle")
        self.data_card.body_layout.addWidget(self.inclusion_label)
        self.tabs = QTabWidget(self)
        self.soa_table = self._table(
            ["SOA (ms)", "Trigger codes", "Bursts", "T1 correct /\nanswered", "T1 accuracy",
             "T2 correct /\nanswered", "T2 accuracy"],
            "ab_accuracy_by_soa",
        )
        self.soa_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.soa_table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        trigger_header = self.soa_table.horizontalHeaderItem(1)
        assert trigger_header is not None
        trigger_header.setToolTip("All trigger codes recorded for this SOA, in numerical order.")
        self.soa_table.setToolTip(
            "T1 and T2 correct / answered use separate valid-answer counts. "
            "Hover over a cell to see its complete value, including all recorded trigger codes."
        )
        self.bursts_table = self._table(
            ["Participant / session", "Burst", "SOA / code", "T1 target → answer",
             "T1 correct", "T2 target → answer", "T2 correct", "Stimulus time (s)", "Status"],
            "ab_accuracy_bursts",
        )
        self.bursts_table.setToolTip(
            "Chronological burst numbers restart for each participant session. "
            "Hover over a cell for its full value; scroll horizontally for all columns."
        )
        self.tabs.addTab(self.soa_table, "Accuracy by SOA")
        self.tabs.addTab(self.bursts_table, "Bursts over time")
        self.data_card.body_layout.addWidget(self.tabs, 1)
        self.feedback_label = QLabel(self)
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.data_card.body_layout.addWidget(self.feedback_label)
        self.export_path_label = PathValueLabel(parent=self)
        self.export_path_label.setMinimumWidth(0)
        self.data_card.body_layout.addWidget(self.export_path_label)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.export_button = QPushButton("Export Excel…", self)
        self.refresh_button = QPushButton("Refresh", self)
        self.close_button = QPushButton("Close", self)
        for button in (self.export_button, self.refresh_button, self.close_button):
            mark_secondary_action(button)
            buttons.addWidget(button)
        self.export_button.clicked.connect(self.start_export)
        self.refresh_button.clicked.connect(self.start_loading)
        self.close_button.clicked.connect(self.close)
        root.addLayout(buttons)
        apply_studio_theme(self)
        self._show_message("loading", "Loading", "Reading this project's burst recall records…")

    def _table(self, headings: list[str], name: str) -> QTableWidget:
        table = QTableWidget(0, len(headings), self)
        table.setObjectName(name)
        table.setHorizontalHeaderLabels(headings)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.verticalHeader().hide()
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        return table

    @property
    def is_loading(self) -> bool:
        return self._active_load_task is not None

    @property
    def is_exporting(self) -> bool:
        return self._active_export_task is not None

    @property
    def is_busy(self) -> bool:
        return self.is_loading or self.is_exporting

    def _sync_actions(self) -> None:
        self.export_button.setEnabled(self._summary is not None and not self.is_busy)
        self.refresh_button.setEnabled(not self.is_busy)
        self.close_button.setEnabled(not self.is_busy)
        self.refresh_button.setText("Retry" if self.state_name == "error" else "Refresh")

    def _show_message(self, state: str, title: str, message: str) -> None:
        self.state_name = state
        self.status_badge.set_state(
            "error" if state == "error" else "pending" if state == "loading" else "info", title,
        )
        self.summary_label.setText(message)
        self.tabs.hide()
        self.inclusion_label.hide()
        self.feedback_label.hide()
        self.export_path_label.hide()
        self._sync_actions()

    @Slot()
    def start_loading(self) -> None:
        if self.is_busy:
            return
        self._summary = None
        task = BackgroundTask(
            parent_widget=self, callback=lambda: load_attentional_blink_data(self._project_root),
        )
        self._active_load_task = task
        self._show_message("loading", "Loading", "Reading this project's burst recall records…")
        task.succeeded.connect(self._on_loaded)
        task.failed.connect(self._on_load_failed)
        task.finished.connect(self._on_load_finished)
        task.start()

    @Slot(object)
    def _on_loaded(self, result: object) -> None:
        if not isinstance(result, AttentionalBlinkDataSummary):
            self._on_load_failed(RuntimeError("Unexpected attentional blink data response."))
            return
        if not result.bursts:
            self._show_message(
                "no_data", "No Data", "No burst recall data yet. Run a burst-based "
                "attentional blink experiment, then refresh this view.",
            )
            return
        self._summary = result
        self.state_name = "populated"
        self.status_badge.set_state("ready", "Data Ready")
        self.summary_label.setText(
            f"{result.included_session_count} included sessions · "
            f"{result.included_burst_count} included bursts · "
            f"{result.total_bursts} recorded bursts"
            + ("\n" + "\n".join(result.warnings) if result.warnings else "")
        )
        self.soa_table.setRowCount(len(result.conditions))
        for row, condition in enumerate(result.conditions):
            self._fill_row(self.soa_table, row, [
                f"{condition.soa_ms:g}",
                ", ".join(str(code) for code in condition.condition_trigger_codes) or "—",
                str(condition.burst_count),
                f"{condition.t1_correct_count} / {condition.t1_answer_count}",
                _percentage(condition.t1_accuracy_percent),
                f"{condition.t2_correct_count} / {condition.t2_answer_count}",
                _percentage(condition.t2_accuracy_percent),
            ], centered=True)
        self.bursts_table.setRowCount(len(result.bursts))
        for row, burst in enumerate(result.bursts):
            status = "Complete" if burst.recall_completed else "Partial recall"
            if not burst.stimulus_completed:
                status = "Partial stimulus"
            if burst.run_aborted or burst.session_aborted:
                status += " · aborted"
            if not burst.session_finalized:
                status += " · checkpoint"
            if burst.is_test_session:
                status += " · Test"
            if burst.is_pilot_session:
                status += " · Pilot"
            if not burst.included_in_accuracy:
                status += " · excluded"
            session = burst.participant_session_number
            self._fill_row(self.bursts_table, row, [
                f"P{burst.participant_number or '?'} / {session if session is not None else '?'}"
                + (" · Test" if burst.is_test_session else "")
                + (" · Pilot" if burst.is_pilot_session else ""),
                str(burst.burst_number),
                f"{burst.requested_soa_ms:g} ms / {burst.condition_trigger_code}",
                f"{burst.t1_target} → {burst.t1_response or '—'}", _correct(burst.t1_correct),
                f"{burst.t2_target} → {burst.t2_response or '—'}", _correct(burst.t2_correct),
                f"{burst.cumulative_stimulus_s:g}", status,
            ])
            identity = self.bursts_table.item(row, 0)
            assert identity is not None
            identity.setToolTip(
                f"Participant {burst.participant_number}; session {session}\n"
                f"Session ID: {burst.session_id}\nRun ID: {burst.run_id}\n"
                + "\n".join(
                    f"{key.replace('_', ' ').capitalize()}: {value}"
                    for key, value in burst.participant_metadata.model_dump().items()
                    if value is not None
                )
            )
        self.tabs.show()
        self.inclusion_label.show()
        self.feedback_label.hide()
        self.export_path_label.hide()
        self._sync_actions()

    @staticmethod
    def _fill_row(
        table: QTableWidget, row: int, values: list[str], *, centered: bool = False,
    ) -> None:
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setToolTip(value)
            if centered:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, column, item)

    @Slot(object)
    def _on_load_failed(self, error: object) -> None:
        self._summary = None
        self._show_message("error", "Could Not Load", f"{error}\nChoose Retry to try again.")
        LOGGER.warning("Could not load attentional blink accuracy: %s", error)

    @Slot()
    def _on_load_finished(self) -> None:
        self._active_load_task = None
        self._sync_actions()

    @Slot()
    def start_export(self) -> None:
        summary = self._summary
        if summary is None or self.is_busy:
            return
        destination, _filter = QFileDialog.getSaveFileName(
            self, "Export T1 and T2 Accuracy",
            str(self._project_root / "attentional_blink_accuracy.xlsx"), "Excel Workbooks (*.xlsx)",
        )
        if not destination:
            return
        task = BackgroundTask(
            parent_widget=self,
            callback=lambda: write_attentional_blink_accuracy_xlsx(summary, Path(destination)),
        )
        self._active_export_task = task
        self.status_badge.set_state("pending", "Exporting Excel")
        self.feedback_label.setText("Writing the workbook in the background…")
        self.feedback_label.show()
        self.export_path_label.set_path_text(destination, max_length=100)
        self.export_path_label.show()
        self._sync_actions()
        task.succeeded.connect(self._on_exported)
        task.failed.connect(self._on_export_failed)
        task.finished.connect(self._on_export_finished)
        task.start()

    @Slot(object)
    def _on_exported(self, result: object) -> None:
        if not isinstance(result, Path):
            self._on_export_failed(RuntimeError("Unexpected Excel export result."))
            return
        self.status_badge.set_state("ready", "Excel Exported")
        self.feedback_label.setText("Excel workbook exported successfully.")
        self.export_path_label.set_path_text(str(result), max_length=100)

    @Slot(object)
    def _on_export_failed(self, error: object) -> None:
        self.status_badge.set_state("error", "Export Failed")
        self.feedback_label.setText(f"{error}\nThe loaded results are still available.")
        LOGGER.warning("Could not export attentional blink accuracy: %s", error)

    @Slot()
    def _on_export_finished(self) -> None:
        self._active_export_task = None
        self._sync_actions()

    def reject(self) -> None:
        if not self.is_busy:
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.is_busy:
            event.ignore()
            return
        super().closeEvent(event)


def _percentage(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}%"


def _correct(value: bool | None) -> str:
    return "—" if value is None else "Yes" if value else "No"
