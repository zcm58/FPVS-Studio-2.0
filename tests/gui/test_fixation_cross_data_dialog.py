"""Registered Qt coverage for the fixation-task accuracy view and export."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication
from tests.gui.helpers import assert_visible_children_within_parent, open_created_project

from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.fixation_cross_data_dialog import FixationCrossDataDialog
from fpvs_studio.runtime.fixation_report import (
    FIXATION_TASK_ACCURACY_FILENAME,
    FixationConditionSummary,
    FixationCrossDataSummary,
    FixationDataError,
    FixationExportError,
)


class _DeferredBackgroundTask(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()
    instances: list[_DeferredBackgroundTask] = []

    def __init__(self, *, parent_widget, callback) -> None:
        super().__init__(parent_widget)
        self.callback = callback
        self.started = False
        self.__class__.instances.append(self)

    def start(self) -> None:
        self.started = True

    def complete_successfully(self, result: object) -> None:
        self.succeeded.emit(result)
        self.finished.emit()

    def fail(self, error: Exception) -> None:
        self.failed.emit(error)
        self.finished.emit()


class _ImmediateBackgroundTask(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, *, parent_widget, callback) -> None:
        super().__init__(parent_widget)
        self.callback = callback

    def start(self) -> None:
        try:
            result = self.callback()
        except Exception as error:
            self.failed.emit(error)
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()


def _summary(*, long_condition_name: str = "Faces") -> FixationCrossDataSummary:
    return FixationCrossDataSummary(
        included_session_count=3,
        total_targets=24,
        hit_count=18,
        accuracy_percent=75.0,
        mean_rt_ms=412.5,
        conditions=(
            FixationConditionSummary(
                condition_id="faces",
                condition_name=long_condition_name,
                included_session_count=3,
                total_targets=16,
                hit_count=12,
                accuracy_percent=75.0,
                mean_rt_ms=400.0,
            ),
            FixationConditionSummary(
                condition_id="objects",
                condition_name="Objects",
                included_session_count=2,
                total_targets=8,
                hit_count=6,
                accuracy_percent=75.0,
                mean_rt_ms=437.5,
            ),
        ),
    )


def _deferred_dialog(qtbot, tmp_path: Path, monkeypatch) -> FixationCrossDataDialog:
    _DeferredBackgroundTask.instances.clear()
    monkeypatch.setattr(
        "fpvs_studio.gui.fixation_cross_data_dialog.BackgroundTask",
        _DeferredBackgroundTask,
    )
    dialog = FixationCrossDataDialog(project_root=tmp_path)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.start_loading()
    return dialog


def _populated_dialog(qtbot, tmp_path: Path, monkeypatch) -> FixationCrossDataDialog:
    dialog = _deferred_dialog(qtbot, tmp_path, monkeypatch)
    _DeferredBackgroundTask.instances[0].complete_successfully(_summary())
    assert dialog.state_name == "populated"
    return dialog


def test_view_menu_order_and_action_load_active_project(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    document, window = open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Fixation Data Menu",
    )
    loaded_roots: list[Path] = []

    monkeypatch.setattr(
        "fpvs_studio.gui.fixation_cross_data_dialog.BackgroundTask",
        _ImmediateBackgroundTask,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.fixation_cross_data_dialog.load_fixation_cross_data",
        lambda root: loaded_roots.append(root) or None,
    )

    assert [action.text() for action in window.menuBar().actions()] == [
        "File",
        "View",
        "Tools",
    ]
    assert [action.text() for action in window.view_menu.actions()] == [
        "Fixation Task Accuracy..."
    ]

    window.fixation_cross_data_action.trigger()

    dialog = window._fixation_cross_data_dialog
    assert dialog is not None
    assert dialog.isVisible()
    assert dialog.windowTitle() == "Fixation Task Accuracy — FPVS Studio"
    assert dialog.data_card.title_label.text() == "Fixation Task Accuracy"
    assert dialog.export_button.text() == "Export Excel..."
    assert loaded_roots == [document.project_root]
    assert dialog.state_name == "no_data"


def test_dialog_shows_loading_then_populated_data_without_clipping(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    dialog = _deferred_dialog(qtbot, tmp_path, monkeypatch)

    assert dialog.minimumWidth() == 720
    assert dialog.minimumHeight() == 480
    assert dialog.width() == 800
    assert dialog.height() == 520
    assert dialog.state_name == "loading"
    assert dialog.state_title_label.text() == "Loading fixation task accuracy..."
    assert dialog.refresh_button.isEnabled() is False
    assert dialog.export_button.isEnabled() is False
    assert dialog.close_button.isEnabled() is False
    assert len(_DeferredBackgroundTask.instances) == 1
    assert _DeferredBackgroundTask.instances[0].started is True
    QApplication.processEvents()
    assert_visible_children_within_parent(dialog)

    long_name = (
        "Faces with exceptionally long researcher-authored condition naming for "
        "a realistic longitudinal protocol"
    )
    _DeferredBackgroundTask.instances[0].complete_successfully(
        _summary(long_condition_name=long_name)
    )
    dialog.resize(720, 480)
    qtbot.waitUntil(lambda: dialog.conditions_table.rowHeight(0) > 0)

    assert dialog.width() == 720
    assert dialog.height() == 480
    assert dialog.state_name == "populated"
    assert dialog.status_badge.text() == "Data Ready"
    assert dialog.accuracy_value_label.text() == "75.0%"
    assert dialog.accuracy_value_label.toolTip() == "18 hits / 24 targets"
    assert dialog.mean_rt_value_label.text() == "412.5 ms"
    assert dialog.included_sessions_value_label.text() == "3"
    assert dialog.conditions_table.rowCount() == 2
    assert dialog.conditions_table.item(0, 0).text() == long_name
    assert dialog.conditions_table.item(0, 0).toolTip() == long_name
    assert dialog.conditions_table.wordWrap() is True
    assert dialog.conditions_table.item(0, 2).text() == "12 / 16"
    assert dialog.conditions_table.item(0, 3).text() == "75.0%"
    assert dialog.refresh_button.isEnabled()
    assert dialog.export_button.isEnabled()
    assert dialog.close_button.isEnabled()
    assert_visible_children_within_parent(dialog)


def test_dialog_treats_missing_or_zero_target_history_as_no_data(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    dialog = _deferred_dialog(qtbot, tmp_path, monkeypatch)

    _DeferredBackgroundTask.instances[0].complete_successfully(None)

    assert dialog.state_name == "no_data"
    assert dialog.status_badge.text() == "No Data"
    assert dialog.state_title_label.text() == "No fixation data yet"
    assert "fixation targets" in dialog.state_detail_label.text()
    assert dialog.refresh_button.text() == "Refresh"
    assert dialog.refresh_button.isEnabled()
    assert dialog.export_button.isEnabled() is False
    dialog.resize(720, 480)
    QApplication.processEvents()
    assert_visible_children_within_parent(dialog)


def test_dialog_keeps_load_errors_recoverable_with_retry(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    dialog = _deferred_dialog(qtbot, tmp_path, monkeypatch)

    _DeferredBackgroundTask.instances[0].fail(
        FixationDataError("session_condition_history.csv has an invalid hit count")
    )

    assert dialog.state_name == "error"
    assert dialog.status_badge.text() == "Could Not Load"
    assert "invalid hit count" in dialog.state_detail_label.text()
    assert "project was not changed" in dialog.state_detail_label.text()
    assert dialog.refresh_button.text() == "Retry"
    assert dialog.refresh_button.isEnabled()
    assert dialog.export_button.isEnabled() is False
    dialog.resize(720, 480)
    QApplication.processEvents()
    assert_visible_children_within_parent(dialog)

    dialog.refresh_button.click()

    assert len(_DeferredBackgroundTask.instances) == 2
    assert dialog.state_name == "loading"
    assert dialog.refresh_button.isEnabled() is False
    _DeferredBackgroundTask.instances[1].complete_successfully(None)


def test_excel_export_chooser_cancel_has_no_side_effects(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    dialog = _populated_dialog(qtbot, tmp_path, monkeypatch)
    export_calls: list[tuple[FixationCrossDataSummary, Path]] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.fixation_cross_data_dialog.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: ("", ""),
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.fixation_cross_data_dialog.write_fixation_task_accuracy_xlsx",
        lambda summary, path: export_calls.append((summary, path)) or path,
    )
    task_count = len(_DeferredBackgroundTask.instances)

    dialog.export_button.click()

    assert len(_DeferredBackgroundTask.instances) == task_count
    assert export_calls == []
    assert dialog.export_state_name == "idle"
    assert dialog.status_badge.text() == "Data Ready"
    assert dialog.export_button.isEnabled()
    assert dialog.state_stack.currentWidget() is dialog.results_page


def test_excel_export_uses_selected_path_and_reports_async_success(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    dialog = _populated_dialog(qtbot, tmp_path, monkeypatch)
    summary = dialog._summary
    assert summary is not None
    selected_path = (
        tmp_path
        / "a-very-long-research-export-folder-name-for-tooltip-coverage"
        / "pooled-fixation-task-accuracy"
    )
    chooser_calls: list[tuple[str, str, str]] = []
    export_calls: list[tuple[FixationCrossDataSummary, Path]] = []

    def _select_export_path(_parent, title: str, initial: str, file_filter: str):
        chooser_calls.append((title, initial, file_filter))
        return str(selected_path), "Excel Workbooks (*.xlsx)"

    def _export(loaded_summary: FixationCrossDataSummary, path: Path) -> Path:
        export_calls.append((loaded_summary, path))
        return path.with_suffix(".xlsx")

    monkeypatch.setattr(
        "fpvs_studio.gui.fixation_cross_data_dialog.QFileDialog.getSaveFileName",
        _select_export_path,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.fixation_cross_data_dialog.write_fixation_task_accuracy_xlsx",
        _export,
    )

    dialog.export_button.click()

    assert chooser_calls == [
        (
            "Export Fixation Task Accuracy",
            str(tmp_path / FIXATION_TASK_ACCURACY_FILENAME),
            "Excel Workbooks (*.xlsx);;All Files (*)",
        )
    ]
    assert len(_DeferredBackgroundTask.instances) == 2
    export_task = _DeferredBackgroundTask.instances[1]
    assert export_task.started is True
    assert dialog.is_exporting
    assert dialog.is_busy
    assert dialog.export_state_name == "pending"
    assert dialog.status_badge.text() == "Exporting Excel"
    assert dialog.export_button.isEnabled() is False
    assert dialog.refresh_button.isEnabled() is False
    assert dialog.close_button.isEnabled() is False
    assert dialog.state_stack.currentWidget() is dialog.results_page
    dialog.resize(720, 480)
    QApplication.processEvents()
    assert dialog.width() == 720
    assert dialog.height() == 480
    assert_visible_children_within_parent(dialog)

    close_event = QCloseEvent()
    dialog.closeEvent(close_event)
    assert close_event.isAccepted() is False

    actual_path = export_task.callback()
    assert export_calls == [(summary, selected_path)]
    assert actual_path == selected_path.with_suffix(".xlsx")
    export_task.complete_successfully(actual_path)

    assert dialog.is_exporting is False
    assert dialog.export_state_name == "success"
    assert dialog.status_badge.text() == "Excel Exported"
    assert dialog.export_path_label.toolTip() == str(actual_path)
    assert "exported successfully" in dialog.export_feedback_label.text().lower()
    assert dialog.export_button.isEnabled()
    assert dialog.refresh_button.isEnabled()
    assert dialog.close_button.isEnabled()
    QApplication.processEvents()
    assert_visible_children_within_parent(dialog)


def test_excel_export_error_keeps_loaded_results_and_allows_retry(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    dialog = _populated_dialog(qtbot, tmp_path, monkeypatch)
    selected_path = tmp_path / "blocked-export.xlsx"
    monkeypatch.setattr(
        "fpvs_studio.gui.fixation_cross_data_dialog.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(selected_path), "Excel Workbooks (*.xlsx)"),
    )

    dialog.export_button.click()
    _DeferredBackgroundTask.instances[1].fail(
        FixationExportError("The selected workbook could not be written.")
    )

    assert dialog.export_state_name == "error"
    assert dialog.status_badge.text() == "Export Failed"
    assert "could not be written" in dialog.export_feedback_label.text()
    assert "still available" in dialog.export_feedback_label.text()
    assert dialog.state_name == "populated"
    assert dialog.state_stack.currentWidget() is dialog.results_page
    assert dialog.conditions_table.rowCount() == 2
    assert dialog.export_button.isEnabled()
    assert dialog.refresh_button.isEnabled()
    assert dialog.close_button.isEnabled()
    dialog.resize(720, 480)
    QApplication.processEvents()
    assert dialog.width() == 720
    assert dialog.height() == 480
    assert_visible_children_within_parent(dialog)


def test_fixation_data_action_is_disabled_during_bundle_processing(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _document, window = open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Fixation Data Bundle Busy",
    )

    assert window.fixation_cross_data_action.isEnabled()

    window._set_bundle_processing_busy(True)
    assert window.fixation_cross_data_action.isEnabled() is False

    window._set_bundle_processing_busy(False)
    assert window.fixation_cross_data_action.isEnabled()


def test_active_fixation_tasks_block_window_close_and_project_handoff(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Fixation Data Handoff Guard",
    )
    _DeferredBackgroundTask.instances.clear()
    monkeypatch.setattr(
        "fpvs_studio.gui.fixation_cross_data_dialog.BackgroundTask",
        _DeferredBackgroundTask,
    )
    information_messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.information",
        lambda _parent, title, message: information_messages.append((title, message)),
    )
    open_requests: list[bool] = []
    window._on_request_open_project = lambda: open_requests.append(True)

    window.show_fixation_cross_data()
    assert len(_DeferredBackgroundTask.instances) == 1

    close_event = QCloseEvent()
    window.closeEvent(close_event)
    window._request_open_project()

    assert close_event.isAccepted() is False
    assert open_requests == []
    assert [title for title, _message in information_messages] == [
        "Fixation Accuracy Loading",
        "Fixation Accuracy Loading",
    ]

    _DeferredBackgroundTask.instances[0].complete_successfully(_summary())
    dialog = window._fixation_cross_data_dialog
    assert dialog is not None
    selected_path = tmp_path / "handoff-guard.xlsx"
    monkeypatch.setattr(
        "fpvs_studio.gui.fixation_cross_data_dialog.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(selected_path), "Excel Workbooks (*.xlsx)"),
    )
    dialog.export_button.click()

    export_close_event = QCloseEvent()
    window.closeEvent(export_close_event)
    window._request_open_project()

    assert export_close_event.isAccepted() is False
    assert open_requests == []
    assert [title for title, _message in information_messages] == [
        "Fixation Accuracy Loading",
        "Fixation Accuracy Loading",
        "Fixation Accuracy Export",
        "Fixation Accuracy Export",
    ]

    _DeferredBackgroundTask.instances[1].complete_successfully(selected_path)
    window._request_open_project()

    assert open_requests == [True]
