"""Registered GUI coverage for recall summaries, burst order and explicit export."""

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.execution import AttentionalBlinkBurstRecord
from fpvs_studio.gui import attentional_blink_data_dialog as module
from fpvs_studio.runtime.attentional_blink_report import (
    AttentionalBlinkDataSummary,
    AttentionalBlinkSOASummary,
)


class DeferredTask(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()
    instances = []

    def __init__(self, *, parent_widget, callback):
        super().__init__(parent_widget)
        self.callback = callback
        self.instances.append(self)

    def start(self):
        pass

    def complete(self, result):
        self.succeeded.emit(result)
        self.finished.emit()


def _summary():
    burst = AttentionalBlinkBurstRecord(
        project_id="study", participant_number="1234567890", participant_session_number=12,
        session_id="long-session-id-for-an-inspectable-session-identity",
        run_id="burst-run-1", condition_id="soa-100", condition_name="SOA 100 ms",
        session_seed=42, run_seed=7, burst_number=1, soa_repetition=1,
        condition_trigger_code=4, requested_soa_ms=100, achieved_soa_ms=100,
        t1_target="3", t2_target="9", t1_response="3", t1_correct=True,
        t1_valid=True, planned_duration_s=5, completed_stimulus_s=5,
        cumulative_stimulus_s=5, stimulus_completed=True, recall_completed=False,
        run_aborted=True, session_aborted=True, included_in_accuracy=True,
    )
    return AttentionalBlinkDataSummary(
        bursts=(burst,), conditions=(AttentionalBlinkSOASummary(
            soa_ms=100, burst_count=1, t1_answer_count=1, t1_correct_count=1,
            t1_accuracy_percent=100, t2_answer_count=0, t2_correct_count=0,
            t2_accuracy_percent=None,
            condition_trigger_codes=(4,),
        ),), included_session_count=1, included_burst_count=1, total_bursts=1,
        warnings=("An interrupted final write was omitted; completed checkpoints are shown.",),
    )


@pytest.fixture
def dialog(qtbot, tmp_path, monkeypatch):
    DeferredTask.instances.clear()
    monkeypatch.setattr(module, "BackgroundTask", DeferredTask)
    dialog = module.AttentionalBlinkDataDialog(project_root=tmp_path)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.start_loading()
    return dialog


@pytest.mark.parametrize("size", [(920, 600), (1080, 680)])
def test_data_and_partial_recall_remain_readable_at_minimum_and_default(dialog, size):
    dialog.resize(*size)
    assert dialog.is_loading
    assert not dialog.close_button.isEnabled()
    DeferredTask.instances[-1].complete(_summary())
    QApplication.processEvents()
    assert dialog.state_name == "populated"
    assert dialog.windowTitle() == "T1 and T2 Accuracy â€” FPVS Studio"
    assert dialog.data_card.title_label.text() == "T1 and T2 Accuracy"
    assert dialog.soa_table.columnCount() == 7
    assert dialog.soa_table.item(0, 1).text() == "4"
    assert dialog.soa_table.item(0, 2).text() == "1"
    assert dialog.soa_table.item(0, 3).text() == "1 / 1"
    assert dialog.soa_table.item(0, 4).text() == "100.0%"
    assert dialog.soa_table.item(0, 5).text() == "0 / 0"
    assert dialog.soa_table.item(0, 6).text() == "â€”"
    assert dialog.soa_table.horizontalScrollBar().maximum() == 0
    for column in range(dialog.soa_table.columnCount()):
        header = dialog.soa_table.horizontalHeaderItem(column)
        required = max(dialog.soa_table.fontMetrics().horizontalAdvance(line)
                       for line in header.text().splitlines())
        assert dialog.soa_table.columnWidth(column) >= required
        assert dialog.soa_table.item(0, column).textAlignment() == Qt.AlignmentFlag.AlignCenter
    assert "interrupted final write" in dialog.summary_label.text()
    assert dialog.bursts_table.item(0, 1).text() == "1"
    assert dialog.bursts_table.item(0, 3).text() == "3 â†’ 3"
    assert dialog.bursts_table.item(0, 4).text() == "Yes"
    assert "aborted" in dialog.bursts_table.item(0, 8).text()
    assert "long-session-id" in dialog.bursts_table.item(0, 0).toolTip()
    for index in (0, 1):
        dialog.tabs.setCurrentIndex(index)
        QApplication.processEvents()
        assert_visible_children_within_parent(dialog)
    for label in (dialog.summary_label, dialog.inclusion_label):
        assert label.height() >= label.heightForWidth(label.width())
    for button in (dialog.export_button, dialog.refresh_button, dialog.close_button):
        assert button.width() >= button.sizeHint().width()


def test_export_cancel_and_background_failure_preserve_loaded_results(
    dialog, monkeypatch, tmp_path,
):
    DeferredTask.instances[-1].complete(_summary())
    monkeypatch.setattr(module.QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    dialog.start_export()
    assert len(DeferredTask.instances) == 1
    path = tmp_path / ("Long exported attentional blink results " * 3 + ".xlsx")
    monkeypatch.setattr(module.QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), ""))
    dialog.start_export()
    assert dialog.is_exporting
    assert not dialog.close_button.isEnabled()
    event = QCloseEvent()
    dialog.closeEvent(event)
    assert not event.isAccepted()
    dialog.reject()
    assert dialog.isVisible()
    DeferredTask.instances[-1].failed.emit(PermissionError("Workbook is open in Excel."))
    DeferredTask.instances[-1].finished.emit()
    assert dialog.state_name == "populated"
    assert dialog.export_button.isEnabled()
    assert "Workbook is open" in dialog.feedback_label.text()
    QApplication.processEvents()
    assert_visible_children_within_parent(dialog)
    assert str(path) in dialog.export_path_label.toolTip()


def test_empty_error_and_retry_states(dialog):
    DeferredTask.instances[-1].complete(AttentionalBlinkDataSummary((), (), 0, 0, 0))
    assert dialog.state_name == "no_data"
    assert not dialog.export_button.isEnabled()
    dialog.start_loading()
    DeferredTask.instances[-1].failed.emit(ValueError("The journal has invalid JSON on line 3."))
    DeferredTask.instances[-1].finished.emit()
    assert dialog.state_name == "error"
    assert dialog.refresh_button.text() == "Retry"
    assert "line 3" in dialog.summary_label.text()
    QApplication.processEvents()
    assert_visible_children_within_parent(dialog)


def test_test_sessions_are_included_and_visibly_identified(dialog):
    summary = _summary()
    test_burst = summary.bursts[0].model_copy(update={"participant_number": "0"})
    DeferredTask.instances[-1].complete(replace(summary, bursts=(test_burst,)))
    assert "including test sessions" in dialog.inclusion_label.text()
    assert "Test" in dialog.bursts_table.item(0, 0).text()
    assert "Test" in dialog.bursts_table.item(0, 8).text()
    assert dialog.soa_table.item(0, 4).text() == "100.0%"


def test_actual_trigger_lists_are_displayed_with_full_value_access(dialog):
    summary = _summary()
    codes = (4, 7, 11, 13, 17, 19, 23, 29, 31, 255)
    condition = replace(summary.conditions[0], condition_trigger_codes=codes)
    DeferredTask.instances[-1].complete(replace(summary, conditions=(condition,)))
    dialog.resize(920, 600)
    QApplication.processEvents()
    trigger_cell = dialog.soa_table.item(0, 1)
    expected = ", ".join(str(code) for code in codes)
    assert trigger_cell.text() == expected
    assert trigger_cell.toolTip() == expected
    assert "All trigger codes recorded" in dialog.soa_table.horizontalHeaderItem(1).toolTip()
    assert dialog.soa_table.horizontalScrollBar().maximum() == 0
    assert dialog.soa_table.item(0, 3).text() == "1 / 1"
    assert dialog.soa_table.item(0, 4).text() == "100.0%"
    assert_visible_children_within_parent(dialog)


def test_view_action_uses_ab_project_and_blocks_handoff_while_busy(
    qtbot, controller, tmp_path, monkeypatch,
):
    document = controller.create_project(
        "AB accuracy", tmp_path, experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
    )
    assert document is not None
    window = controller.main_window
    assert window is not None
    qtbot.addWidget(window)
    DeferredTask.instances.clear()
    monkeypatch.setattr(module, "BackgroundTask", DeferredTask)
    calls = []
    monkeypatch.setattr(
        module, "load_attentional_blink_data",
        lambda root: calls.append(root) or AttentionalBlinkDataSummary((), (), 0, 0, 0),
    )
    monkeypatch.setattr("fpvs_studio.gui.main_window.QMessageBox.information", lambda *a: None)
    assert window.fixation_cross_data_action in window.view_menu.actions()
    assert window.fixation_cross_data_action.text() == "T1 and T2 Accuracy..."
    assert [action.text() for action in window.tools_menu.actions()] == ["Image Resizer"]
    window.fixation_cross_data_action.trigger()
    task = DeferredTask.instances[-1]
    assert not window._allow_project_handoff_during_fixation_load()
    task.complete(task.callback())
    assert calls == [document.project_root]
    assert window._allow_project_handoff_during_fixation_load()


def test_export_succeeds_to_selected_path(dialog, monkeypatch, tmp_path):
    DeferredTask.instances[-1].complete(_summary())
    output = tmp_path / "recall.xlsx"
    calls = []
    picker_titles = []
    monkeypatch.setattr(
        module.QFileDialog, "getSaveFileName",
        lambda *args: picker_titles.append(args[1]) or (str(output), ""),
    )
    monkeypatch.setattr(
        module, "write_attentional_blink_accuracy_xlsx",
        lambda summary, path: calls.append((summary, path)) or Path(path),
    )
    dialog.start_export()
    task = DeferredTask.instances[-1]
    task.complete(task.callback())
    assert calls == [(_summary(), output)]
    assert picker_titles == ["Export T1 and T2 Accuracy"]
    assert "successfully" in dialog.feedback_label.text()
    assert not dialog.is_busy


def test_pilot_identity_and_demographics_are_visible(dialog):
    from fpvs_studio.core.execution import ParticipantMetadata

    summary = _summary()
    burst = summary.bursts[0].model_copy(
        update={
            "is_pilot_session": True,
            "participant_metadata": ParticipantMetadata(
                age=22, sex="Female", handedness="Left handed", colorblind=False
            ),
        }
    )
    DeferredTask.instances[-1].complete(replace(summary, bursts=(burst,)))
    assert "Pilot" in dialog.bursts_table.item(0, 0).text()
    assert "Age: 22" in dialog.bursts_table.item(0, 0).toolTip()
    assert "Colorblind: False" in dialog.bursts_table.item(0, 0).toolTip()
