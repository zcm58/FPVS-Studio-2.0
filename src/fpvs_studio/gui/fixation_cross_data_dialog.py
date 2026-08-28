"""Presentation and explicit-path export for pooled fixation-task response data."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
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
from fpvs_studio.runtime.fixation_report import (
    FIXATION_TASK_ACCURACY_FILENAME,
    FixationCrossDataSummary,
    FixationDataError,
    FixationExportError,
    load_fixation_cross_data,
    write_fixation_task_accuracy_xlsx,
)

LOGGER = logging.getLogger(__name__)

_MINIMUM_SIZE = (720, 480)
_DEFAULT_SIZE = (800, 520)


class FixationCrossDataDialog(QDialog):
    """Load, display, and export the active project's typed fixation summary."""

    def __init__(self, *, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("fixation_cross_data_dialog")
        self.setWindowTitle("Fixation Task Accuracy — FPVS Studio")
        self.setMinimumSize(*_MINIMUM_SIZE)
        self.resize(*_DEFAULT_SIZE)
        self._project_root = Path(project_root)
        self._active_load_task: BackgroundTask | None = None
        self._active_export_task: BackgroundTask | None = None
        self._summary: FixationCrossDataSummary | None = None
        self.state_name = "loading"
        self.export_state_name = "idle"

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(12)

        self.data_card = SectionCard(
            title="Fixation Task Accuracy",
            subtitle=(
                "Pooled fixation-task accuracy and reaction time from included "
                "participant sessions in this project."
            ),
            object_name="fixation_cross_data_card",
            parent=self,
        )
        root_layout.addWidget(self.data_card, 1)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(8)
        self.status_badge = StatusBadgeLabel(parent=self.data_card)
        self.status_badge.setObjectName("fixation_cross_data_status_badge")
        status_row.addWidget(self.status_badge)
        self.export_path_label = PathValueLabel(parent=self.data_card)
        self.export_path_label.setObjectName("fixation_cross_data_export_path")
        self.export_path_label.setMinimumWidth(0)
        self.export_path_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.export_path_label.setVisible(False)
        status_row.addWidget(self.export_path_label, 1)
        self.data_card.body_layout.addLayout(status_row)

        self.state_stack = QStackedWidget(self.data_card)
        self.state_stack.setObjectName("fixation_cross_data_state_stack")
        self.state_page = self._build_state_page()
        self.results_page = self._build_results_page()
        self.state_stack.addWidget(self.state_page)
        self.state_stack.addWidget(self.results_page)
        self.data_card.body_layout.addWidget(self.state_stack, 1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        button_row.addStretch(1)
        self.export_button = QPushButton("Export Excel...", self)
        self.export_button.setObjectName("fixation_cross_data_export_button")
        self.export_button.clicked.connect(self.start_export)
        mark_secondary_action(self.export_button)
        button_row.addWidget(self.export_button)
        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.setObjectName("fixation_cross_data_refresh_button")
        self.refresh_button.clicked.connect(self.start_loading)
        mark_secondary_action(self.refresh_button)
        button_row.addWidget(self.refresh_button)
        self.close_button = QPushButton("Close", self)
        self.close_button.setObjectName("fixation_cross_data_close_button")
        self.close_button.clicked.connect(self.close)
        mark_secondary_action(self.close_button)
        button_row.addWidget(self.close_button)
        root_layout.addLayout(button_row)

        apply_studio_theme(self)
        self._show_loading_state()

    @property
    def is_loading(self) -> bool:
        return self._active_load_task is not None

    @property
    def is_exporting(self) -> bool:
        return self._active_export_task is not None

    @property
    def is_busy(self) -> bool:
        return self.is_loading or self.is_exporting

    def _build_state_page(self) -> QWidget:
        page = QFrame(self.state_stack)
        page.setObjectName("fixation_cross_data_message_panel")
        page.setProperty("setupMetricStrip", "true")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(8)
        layout.addStretch(1)
        self.state_title_label = QLabel(page)
        self.state_title_label.setObjectName("fixation_cross_data_state_title")
        self.state_title_label.setProperty("sectionCardRole", "title")
        self.state_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_title_label.setWordWrap(True)
        layout.addWidget(self.state_title_label)
        self.state_detail_label = QLabel(page)
        self.state_detail_label.setObjectName("fixation_cross_data_state_detail")
        self.state_detail_label.setProperty("sectionCardRole", "subtitle")
        self.state_detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_detail_label.setWordWrap(True)
        self.state_detail_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.state_detail_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        layout.addWidget(self.state_detail_label)
        layout.addStretch(1)
        return page

    def _build_results_page(self) -> QWidget:
        page = QWidget(self.state_stack)
        page.setObjectName("fixation_cross_data_results_page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        metrics_panel = QFrame(page)
        metrics_panel.setObjectName("fixation_cross_data_metrics_panel")
        metrics_panel.setProperty("setupMetricStrip", "true")
        metrics_layout = QGridLayout(metrics_panel)
        metrics_layout.setContentsMargins(12, 8, 12, 8)
        metrics_layout.setHorizontalSpacing(12)
        metrics_layout.setVerticalSpacing(3)
        self.accuracy_value_label = QLabel("—", metrics_panel)
        self.mean_rt_value_label = QLabel("—", metrics_panel)
        self.included_sessions_value_label = QLabel("—", metrics_panel)
        metric_specs = (
            ("Weighted Accuracy", "accuracy", self.accuracy_value_label),
            ("Mean Reaction Time", "mean_rt", self.mean_rt_value_label),
            ("Included Sessions", "included_sessions", self.included_sessions_value_label),
        )
        for column, (label_text, object_suffix, value) in enumerate(metric_specs):
            label = QLabel(label_text, metrics_panel)
            label.setProperty("setupMetricLabel", "true")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value.setObjectName(f"fixation_cross_data_{object_suffix}_value_label")
            value.setProperty("setupMetricValue", "true")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            metrics_layout.addWidget(label, 0, column)
            metrics_layout.addWidget(value, 1, column)
            metrics_layout.setColumnStretch(column, 1)
        layout.addWidget(metrics_panel)

        self.conditions_table = QTableWidget(0, 4, page)
        self.conditions_table.setObjectName("fixation_cross_data_table")
        self.conditions_table.setHorizontalHeaderLabels(
            ("Condition", "Sessions", "Hits / Targets", "Accuracy")
        )
        self.conditions_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.conditions_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.conditions_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.conditions_table.setAlternatingRowColors(True)
        self.conditions_table.setWordWrap(True)
        self.conditions_table.verticalHeader().setVisible(False)
        self.conditions_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        header = self.conditions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, self.conditions_table.columnCount()):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.conditions_table.setMinimumHeight(110)
        layout.addWidget(self.conditions_table, 1)

        self.export_feedback_label = QLabel(page)
        self.export_feedback_label.setObjectName("fixation_cross_data_export_feedback")
        self.export_feedback_label.setProperty("setupMetricValue", "true")
        self.export_feedback_label.setWordWrap(True)
        self.export_feedback_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.export_feedback_label.setMinimumWidth(0)
        self.export_feedback_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Minimum,
        )
        self.export_feedback_label.setVisible(False)
        layout.addWidget(self.export_feedback_label)
        return page

    @Slot()
    def start_loading(self) -> None:
        """Load the current project's report on a disposable worker thread."""

        if self.is_busy:
            return
        self._show_loading_state()
        project_root = self._project_root
        task = BackgroundTask(
            parent_widget=self,
            callback=lambda: load_fixation_cross_data(project_root),
        )
        self._active_load_task = task
        task.succeeded.connect(self._on_load_succeeded)
        task.failed.connect(self._on_load_failed)
        task.finished.connect(self._on_load_finished)
        task.start()

    @Slot(object)
    def _on_load_succeeded(self, result: object) -> None:
        if result is None:
            self._show_no_data_state()
            return
        if not isinstance(result, FixationCrossDataSummary):
            self._show_error_state(
                RuntimeError("FPVS Studio received an unexpected fixation-data result.")
            )
            return
        self._show_summary(result)

    @Slot(object)
    def _on_load_failed(self, error: object) -> None:
        self._show_error_state(error)

    @Slot()
    def _on_load_finished(self) -> None:
        self._active_load_task = None
        self._sync_action_enabled_states()

    @Slot()
    def start_export(self) -> None:
        """Choose a destination and export the currently displayed typed summary."""

        summary = self._summary
        if summary is None or self.is_busy:
            return
        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Fixation Task Accuracy",
            str(self._project_root / FIXATION_TASK_ACCURACY_FILENAME),
            "Excel Workbooks (*.xlsx);;All Files (*)",
        )
        if not selected_path:
            return

        output_path = Path(selected_path)
        task = BackgroundTask(
            parent_widget=self,
            callback=lambda: write_fixation_task_accuracy_xlsx(summary, output_path),
        )
        self._active_export_task = task
        self._show_export_pending(output_path)
        task.succeeded.connect(self._on_export_succeeded)
        task.failed.connect(self._on_export_failed)
        task.finished.connect(self._on_export_finished)
        task.start()

    @Slot(object)
    def _on_export_succeeded(self, result: object) -> None:
        if not isinstance(result, Path):
            self._show_export_error(
                RuntimeError("FPVS Studio received an unexpected Excel export result.")
            )
            return
        self.export_state_name = "success"
        self.status_badge.set_state("ready", "Excel Exported")
        self.export_path_label.set_path_text(str(result), max_length=72)
        self.export_path_label.setVisible(True)
        self.export_feedback_label.setText("Excel workbook exported successfully.")
        self.export_feedback_label.setVisible(True)

    @Slot(object)
    def _on_export_failed(self, error: object) -> None:
        self._show_export_error(error)

    @Slot()
    def _on_export_finished(self) -> None:
        self._active_export_task = None
        self._sync_action_enabled_states()

    def _show_export_pending(self, output_path: Path) -> None:
        self.export_state_name = "pending"
        self.status_badge.set_state("pending", "Exporting Excel")
        self.export_path_label.set_path_text(str(output_path), max_length=72)
        self.export_path_label.setVisible(True)
        self.export_feedback_label.setText("Writing the selected workbook in the background...")
        self.export_feedback_label.setVisible(True)
        self._sync_action_enabled_states()

    def _show_export_error(self, error: object) -> None:
        self.export_state_name = "error"
        self.status_badge.set_state("error", "Export Failed")
        message = str(error).strip() or "The Excel workbook could not be written."
        self.export_feedback_label.setText(
            f"{message} The loaded fixation results are still available."
        )
        self.export_feedback_label.setVisible(True)
        if isinstance(error, FixationExportError):
            LOGGER.warning("Could not export fixation-task accuracy: %s", error)
        else:
            LOGGER.warning(
                "Unexpected fixation-task accuracy export error (%s): %s",
                type(error).__name__,
                error,
            )

    def _sync_action_enabled_states(self) -> None:
        loading = self.state_name == "loading"
        busy = self.is_busy or loading
        self.export_button.setEnabled(self._summary is not None and not busy)
        self.refresh_button.setEnabled(not busy)
        self.close_button.setEnabled(not busy)
        if loading:
            self.refresh_button.setText("Loading...")
        else:
            self.refresh_button.setText(
                "Retry" if self.state_name == "error" else "Refresh"
            )

    def _show_loading_state(self) -> None:
        self._summary = None
        self.state_name = "loading"
        self.export_state_name = "idle"
        self.status_badge.set_state("pending", "Loading")
        self.state_title_label.setText("Loading fixation task accuracy...")
        self.state_detail_label.setText("Reading included session history from this project.")
        self.state_stack.setCurrentWidget(self.state_page)
        self.export_path_label.setVisible(False)
        self.export_feedback_label.setVisible(False)
        self._sync_action_enabled_states()

    def _show_no_data_state(self) -> None:
        self._summary = None
        self.state_name = "no_data"
        self.status_badge.set_state("info", "No Data")
        self.state_title_label.setText("No fixation data yet")
        self.state_detail_label.setText(
            "Included participant sessions with fixation targets will appear here."
        )
        self.state_stack.setCurrentWidget(self.state_page)
        self._sync_action_enabled_states()

    def _show_error_state(self, error: object) -> None:
        self._summary = None
        self.state_name = "error"
        self.status_badge.set_state("error", "Could Not Load")
        self.state_title_label.setText("Fixation data could not be loaded")
        message = str(error).strip() or "The fixation history could not be read."
        self.state_detail_label.setText(
            f"{message}\n\nThe project was not changed. Choose Retry to try again."
        )
        self.state_stack.setCurrentWidget(self.state_page)
        self._sync_action_enabled_states()
        if isinstance(error, FixationDataError):
            LOGGER.warning("Could not load fixation-task accuracy: %s", error)
        else:
            LOGGER.warning(
                "Unexpected fixation-task accuracy error (%s): %s",
                type(error).__name__,
                error,
            )

    def _show_summary(self, summary: FixationCrossDataSummary) -> None:
        self._summary = summary
        self.state_name = "populated"
        self.export_state_name = "idle"
        self.status_badge.set_state("ready", "Data Ready")
        self.export_path_label.setVisible(False)
        self.export_feedback_label.setVisible(False)
        self.accuracy_value_label.setText(f"{summary.accuracy_percent:.1f}%")
        self.accuracy_value_label.setToolTip(
            f"{summary.hit_count} hits / {summary.total_targets} targets"
        )
        self.mean_rt_value_label.setText(_format_mean_rt(summary.mean_rt_ms))
        self.included_sessions_value_label.setText(str(summary.included_session_count))

        self.conditions_table.setRowCount(len(summary.conditions))
        for row, condition in enumerate(summary.conditions):
            condition_item = QTableWidgetItem(condition.condition_name)
            condition_item.setToolTip(condition.condition_name)
            condition_item.setData(Qt.ItemDataRole.UserRole, condition.condition_id)
            self.conditions_table.setItem(row, 0, condition_item)
            self.conditions_table.setItem(
                row,
                1,
                _centered_item(str(condition.included_session_count)),
            )
            self.conditions_table.setItem(
                row,
                2,
                _centered_item(f"{condition.hit_count} / {condition.total_targets}"),
            )
            self.conditions_table.setItem(
                row,
                3,
                _centered_item(f"{condition.accuracy_percent:.1f}%"),
            )
        self.conditions_table.resizeRowsToContents()
        self.state_stack.setCurrentWidget(self.results_page)
        self._sync_action_enabled_states()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.is_busy:
            event.ignore()
            return
        super().closeEvent(event)


def _format_mean_rt(mean_rt_ms: float | None) -> str:
    return "N/A" if mean_rt_ms is None else f"{mean_rt_ms:.1f} ms"


def _centered_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    return item
