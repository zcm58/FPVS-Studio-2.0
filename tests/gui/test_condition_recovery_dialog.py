"""Visible, isolated recovery guidance and launch-guard regression coverage."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.gui import condition_recovery_dialog as module
from fpvs_studio.gui import main_window
from fpvs_studio.runtime.condition_recovery import ConditionRecoveryReport, InterruptedCondition


def _record(**changes):
    item = InterruptedCondition(
        execution_id="execution-1", participant_number="0012", participant_session_number=1,
        session_id="session-1", run_id="run-006-condition-4", run_ordinal=6, total_runs=8,
        condition_id="condition-4",
        condition_name="Emotional Processing with a very long condition name",
        completed_run_ids=("run-001", "run-002", "run-003", "run-004", "run-005"),
        not_started_run_ids=("run-007", "run-008"),
        completed_run_labels=("Run 5: Low-Level Color Condition",),
        not_started_run_labels=("Run 7: Word Recognition", "Run 8: Semantic Categorization"),
        stage="transition", playback_completed=False, status="unverified", can_rerun=True,
        evidence_path="logs/acquisition/example.acquisition-v1.json",
        updated_at=datetime.now(timezone.utc),
    )
    return replace(item, **changes)


@pytest.mark.parametrize("size", [(640, 440), (760, 520)])
@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_details_distinguish_run_occurrences_and_fit(qtbot, size, background):
    item = _record()
    dialog = module.ConditionRecoveryDialog(ConditionRecoveryReport(records=(item,)))
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    module.apply_studio_theme(dialog)
    dialog.resize(*size)
    dialog.show()
    QApplication.processEvents()
    text = dialog.details.toPlainText()
    assert "Run 6 of 8" in text
    assert item.condition_name in text
    assert "Completed runs retained: 5" in text
    assert "Run 7: Word Recognition" in text
    assert "new participant visit" in text
    assert dialog.condition_combo.toolTip() == dialog.condition_combo.currentText()
    assert_visible_children_within_parent(dialog)
    for label in dialog.findChildren(QLabel):
        if label.isVisible() and label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width())
    assert dialog.confirmation.width() >= dialog.confirmation.sizeHint().width()
    assert not dialog.rerun_button.isEnabled()
    dialog.confirmation.setChecked(True)
    with qtbot.waitSignal(dialog.rerun_requested) as emitted:
        dialog.rerun_button.click()
    assert emitted.args == [item]


def test_missing_plan_and_finished_playback_are_explicit(qtbot):
    item = _record(playback_completed=True, stage="post_condition", can_rerun=False)
    dialog = module.ConditionRecoveryDialog(ConditionRecoveryReport(records=(item,)))
    qtbot.addWidget(dialog)
    assert "Stimulus playback completed" in dialog.details.toPlainText()
    assert "original compiled condition is unavailable" in dialog.details.toPlainText()
    dialog.confirmation.setChecked(True)
    assert not dialog.rerun_button.isEnabled()


def test_missing_plan_offers_explicit_current_setup_for_existing_condition(qtbot):
    item = _record(can_rerun=False)
    dialog = module.ConditionRecoveryDialog(
        ConditionRecoveryReport(records=(item,)),
        current_condition_ids=frozenset({item.condition_id}),
    )
    qtbot.addWidget(dialog)
    assert dialog.rerun_button.text() == "Re-run with Current Setup…"
    assert "new randomized schedule" in dialog.details.toPlainText()
    assert not dialog.rerun_button.isEnabled()
    dialog.confirmation.setChecked(True)
    assert dialog.rerun_button.isEnabled()


def test_empty_and_warning_states_do_not_offer_rerun(qtbot):
    dialog = module.ConditionRecoveryDialog(
        ConditionRecoveryReport(warnings=("Unreadable evidence.",)),
    )
    qtbot.addWidget(dialog)
    assert "No interrupted" in dialog.summary_label.text()
    assert "Unreadable evidence" in dialog.details.toPlainText()
    assert not dialog.rerun_button.isEnabled()


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


def test_controller_uses_worker_and_suppresses_active_launch(qtbot, tmp_path, monkeypatch):
    DeferredTask.instances.clear()
    monkeypatch.setattr(module, "BackgroundTask", DeferredTask)
    window = QWidget()
    qtbot.addWidget(window)
    window.show()
    busy = False
    query = Mock(return_value=ConditionRecoveryReport(records=(_record(),)))
    monkeypatch.setattr(module, "query_condition_recovery", query)
    controller = module.ConditionRecoveryController(
        parent=window, project_root=tmp_path, is_busy=lambda: busy,
        rerun=Mock(), show_error=Mock(),
    )
    controller.check(automatic=True)
    query.assert_not_called()
    task = DeferredTask.instances[-1]
    result = task.callback()
    query.assert_called_once_with(tmp_path, include_acknowledged=False)
    busy = True
    task.succeeded.emit(result)
    task.finished.emit()
    assert controller._dialog is None
    busy = False
    controller.check(automatic=True)
    task = DeferredTask.instances[-1]
    task.succeeded.emit(result)
    task.finished.emit()
    assert controller._dialog is not None
    controller.close_dialog()
    controller.check(automatic=True)
    task = DeferredTask.instances[-1]
    task.succeeded.emit(result)
    task.finished.emit()
    assert not controller._dialog.isVisible()


@pytest.mark.parametrize("testing, repeats, expected", [
    (True, True, "Turn off Experiment Test"),
    (False, False, "Allow repeat participant sessions"),
])
def test_rerun_keeps_recording_and_visit_safeguards(monkeypatch, testing, repeats, expected):
    show_error = Mock()
    monkeypatch.setattr(main_window, "_show_error_dialog", show_error)
    document = SimpleNamespace(
        local_testing_enabled=testing,
        project=SimpleNamespace(settings=SimpleNamespace(allow_repeated_participant_sessions=repeats)),
        validate_recording_launch=Mock(),
    )
    window = SimpleNamespace(
        isVisible=lambda: True, is_launch_busy=lambda: False, document=document,
    )
    main_window.StudioMainWindow._launch_recovered_condition(window, _record())
    assert expected in str(show_error.call_args.args[2])
    document.validate_recording_launch.assert_not_called()


def test_busy_window_does_not_start_recovery_launch():
    window = SimpleNamespace(isVisible=lambda: True, is_launch_busy=lambda: True)
    main_window.StudioMainWindow._launch_recovered_condition(window, _record())


def test_current_setup_replacement_cancel_does_not_compile_or_launch(monkeypatch):
    document = SimpleNamespace(
        local_testing_enabled=False,
        project=SimpleNamespace(settings=SimpleNamespace(allow_repeated_participant_sessions=True)),
        validate_recording_launch=Mock(), compile_session=Mock(),
    )
    window = SimpleNamespace(
        isVisible=lambda: True, is_launch_busy=lambda: False,
        document=document, flush_pending_edits=lambda: True,
    )
    monkeypatch.setattr(
        main_window.QMessageBox, "question",
        lambda *args: main_window.QMessageBox.StandardButton.Cancel,
    )
    main_window.StudioMainWindow._launch_recovered_condition(window, _record(can_rerun=False))
    document.compile_session.assert_not_called()


def test_current_setup_waits_for_new_seed_without_starting_full_session(monkeypatch):
    document = SimpleNamespace(
        local_testing_enabled=False,
        project=SimpleNamespace(settings=SimpleNamespace(allow_repeated_participant_sessions=True)),
        validate_recording_launch=Mock(), compile_session=Mock(),
    )
    window = SimpleNamespace(
        isVisible=lambda: True, is_launch_busy=lambda: False, document=document,
        flush_pending_edits=lambda: True, _session_seed_ready=False,
        _start_deferred_session_seed_task=Mock(), launch_session=Mock(),
    )
    monkeypatch.setattr(
        main_window.QMessageBox, "question",
        lambda *args: main_window.QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(main_window.QMessageBox, "information", Mock())
    main_window.StudioMainWindow._launch_recovered_condition(window, _record(can_rerun=False))
    window._start_deferred_session_seed_task.assert_called_once()
    document.compile_session.assert_not_called()
    window.launch_session.assert_not_called()


@pytest.mark.parametrize("close_kind", ["hidden", "deactivated", "presentation", "shutdown"])
def test_late_recovery_results_and_errors_cannot_reopen_old_project(
    qtbot, tmp_path, monkeypatch, close_kind,
):
    monkeypatch.setattr(module, "BackgroundTask", DeferredTask)
    window = QWidget()
    qtbot.addWidget(window)
    window.show()
    busy = False
    lifecycle = SimpleNamespace(is_shutting_down=False)
    monkeypatch.setattr(module, "update_lifecycle", lambda: lifecycle)
    rerun, show_error = Mock(), Mock()
    controller = module.ConditionRecoveryController(
        parent=window, project_root=tmp_path, is_busy=lambda: busy,
        rerun=rerun, show_error=show_error,
    )
    controller.check(automatic=True)
    task = DeferredTask.instances[-1]
    if close_kind == "hidden":
        window.hide()
    elif close_kind == "deactivated":
        controller.deactivate()
    elif close_kind == "shutdown":
        lifecycle.is_shutting_down = True
    else:
        busy = True
    task.succeeded.emit(ConditionRecoveryReport(records=(_record(),)))
    task.failed.emit(RuntimeError("query failed"))
    task.finished.emit()
    controller._request_rerun(_record())
    assert controller._dialog is None
    rerun.assert_not_called()
    show_error.assert_not_called()
    controller.check(automatic=True)
    assert controller._task is None


@pytest.mark.parametrize("size", [(640, 440), (760, 520)])
@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("state", ["pending", "acknowledged", "saving", "error"])
def test_acknowledgement_states_fit_minimum_and_default(qtbot, size, background, state):
    first = _record(can_rerun=False)
    if state == "acknowledged":
        first = replace(first, acknowledged_at=datetime.now(timezone.utc))
    second = replace(first, execution_id="execution-2", run_id="run-008-condition-4")
    dialog = module.ConditionRecoveryDialog(
        ConditionRecoveryReport(records=(first, second)),
        current_condition_ids=frozenset({first.condition_id}),
    )
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    module.apply_studio_theme(dialog)
    if state == "saving":
        dialog.set_saving(True)
    elif state == "error":
        dialog.show_save_error(PermissionError(
            "A long project path cannot be written: " + "folder/" * 35,
        ))
    dialog.resize(*size)
    dialog.show()
    QApplication.processEvents()
    assert dialog.size().toTuple() == size
    assert_visible_children_within_parent(dialog)
    for label in dialog.findChildren(QLabel):
        if label.isVisible() and label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width())
    for button in (dialog.rerun_button, dialog.acknowledge_button, dialog.close_button):
        assert button.width() >= button.sizeHint().width()
    if state == "pending":
        assert dialog.acknowledge_button.text() == "Acknowledge All and Continue"
        assert dialog.acknowledge_button.property("primaryActionRole") == "true"
    elif state == "acknowledged":
        assert not dialog.acknowledge_button.isEnabled()
        assert "Acknowledged:" in dialog.details.toPlainText()
        assert "record is unchanged" in dialog.details.toPlainText()
        assert "Acknowledged" in dialog.condition_combo.currentText()
    elif state == "saving":
        assert not dialog.acknowledge_button.isEnabled()
        assert not dialog.close_button.isEnabled()
        dialog.set_saving(False)
    else:
        assert "Could not save acknowledgement" in dialog.status_label.text()
        assert "folder/" in dialog.status_label.toolTip()


def _controller_with_report(qtbot, tmp_path, monkeypatch, report):
    DeferredTask.instances.clear()
    monkeypatch.setattr(module, "BackgroundTask", DeferredTask)
    window = QWidget()
    qtbot.addWidget(window)
    window.show()
    errors = Mock()
    controller = module.ConditionRecoveryController(
        parent=window, project_root=tmp_path, is_busy=lambda: False,
        rerun=Mock(), show_error=errors,
    )
    controller._loaded(report, automatic=False)
    assert controller._dialog is not None
    return controller, window, controller._dialog, errors


def test_explicit_acknowledgement_saves_all_pending_rows_off_gui_thread(
    qtbot, tmp_path, monkeypatch,
):
    first = _record()
    second = replace(first, execution_id="execution-2", run_id="run-002")
    old = replace(first, execution_id="execution-old", acknowledged_at=datetime.now(timezone.utc))
    controller, _window, dialog, errors = _controller_with_report(
        qtbot, tmp_path, monkeypatch, ConditionRecoveryReport(records=(first, second, old)),
    )
    save = Mock()
    monkeypatch.setattr(module, "acknowledge_condition_recovery", save)
    dialog.acknowledge_button.click()
    save.assert_not_called()
    task = DeferredTask.instances[-1]
    assert controller._ack_task is task
    assert not dialog.rerun_button.isEnabled()
    assert not dialog.condition_combo.isEnabled()
    assert not dialog.close()
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.isVisible()
    controller._acknowledge(dialog)
    assert DeferredTask.instances == [task]
    controller._loaded(ConditionRecoveryReport(records=(second,)), automatic=True)
    assert controller._dialog is dialog
    result = task.callback()
    save.assert_called_once_with(tmp_path, (first, second))
    task.succeeded.emit(result)
    assert dialog.isVisible()  # Native worker cleanup has not finished yet.
    task.finished.emit()
    assert not dialog.isVisible()
    assert controller._ack_task is None
    errors.assert_not_called()


def test_acknowledgement_failure_keeps_dialog_and_can_be_retried(qtbot, tmp_path, monkeypatch):
    item = _record()
    controller, _window, dialog, errors = _controller_with_report(
        qtbot, tmp_path, monkeypatch, ConditionRecoveryReport(records=(item,)),
    )
    save = Mock(side_effect=[PermissionError("Project is read-only"), None])
    monkeypatch.setattr(module, "acknowledge_condition_recovery", save)
    dialog.acknowledge_button.click()
    task = DeferredTask.instances[-1]
    with pytest.raises(PermissionError) as failure:
        task.callback()
    task.failed.emit(failure.value)
    task.finished.emit()
    assert dialog.isVisible()
    assert dialog.acknowledge_button.isEnabled()
    assert "Check project permissions" in dialog.status_label.text()
    errors.assert_called_once_with(failure.value)
    dialog.acknowledge_button.click()
    retry = DeferredTask.instances[-1]
    assert retry is not task
    retry.succeeded.emit(retry.callback())
    retry.finished.emit()
    assert not dialog.isVisible()
    assert save.call_count == 2


@pytest.mark.parametrize("close_kind", ["button", "escape", "window"])
def test_passive_close_never_acknowledges_a_session(qtbot, tmp_path, monkeypatch, close_kind):
    _controller, _window, dialog, _errors = _controller_with_report(
        qtbot, tmp_path, monkeypatch, ConditionRecoveryReport(records=(_record(),)),
    )
    save = Mock()
    monkeypatch.setattr(module, "acknowledge_condition_recovery", save)
    if close_kind == "button":
        dialog.close_button.click()
    elif close_kind == "escape":
        qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    else:
        dialog.close()
    assert not dialog.isVisible()
    save.assert_not_called()
    assert not DeferredTask.instances


def test_new_controller_hides_saved_acknowledgements_but_manual_history_keeps_them(
    qtbot, tmp_path, monkeypatch,
):
    DeferredTask.instances.clear()
    monkeypatch.setattr(module, "BackgroundTask", DeferredTask)
    records = [_record()]
    acknowledged = set()

    def query(_root, *, include_acknowledged):
        rows = tuple(
            replace(item, acknowledged_at=datetime.now(timezone.utc))
            if item.execution_id in acknowledged else item for item in records
        )
        return ConditionRecoveryReport(records=tuple(
            item for item in rows if include_acknowledged or item.acknowledged_at is None
        ))

    def save(_root, rows):
        acknowledged.update(item.execution_id for item in rows)

    monkeypatch.setattr(module, "query_condition_recovery", query)
    monkeypatch.setattr(module, "acknowledge_condition_recovery", save)

    def make_controller():
        window = QWidget()
        qtbot.addWidget(window)
        window.show()
        return module.ConditionRecoveryController(
            parent=window, project_root=tmp_path, is_busy=lambda: False,
            rerun=Mock(), show_error=Mock(),
        )

    def finish_query(controller, *, automatic):
        controller.check(automatic=automatic)
        task = DeferredTask.instances[-1]
        task.succeeded.emit(task.callback())
        task.finished.emit()

    first = make_controller()
    finish_query(first, automatic=True)
    assert first._dialog is not None
    first._dialog.acknowledge_button.click()
    task = DeferredTask.instances[-1]
    task.succeeded.emit(task.callback())
    task.finished.emit()
    first.deactivate()
    reopened = make_controller()
    finish_query(reopened, automatic=True)
    assert reopened._dialog is None
    finish_query(reopened, automatic=False)
    assert reopened._dialog is not None
    assert "Acknowledged:" in reopened._dialog.details.toPlainText()
    assert not reopened._dialog.acknowledge_button.isEnabled()
    records.append(replace(records[0], execution_id="execution-new", run_id="run-new"))
    finish_query(reopened, automatic=True)
    assert reopened._dialog is not None
    assert reopened._dialog.pending_records() == (records[-1],)


@pytest.mark.parametrize("state", ["hidden", "deactivated", "presentation", "shutdown", "replaced"])
@pytest.mark.parametrize("failed", [False, True])
def test_late_acknowledgement_result_cannot_close_or_reopen_another_view(
    qtbot, tmp_path, monkeypatch, state, failed,
):
    controller, window, dialog, errors = _controller_with_report(
        qtbot, tmp_path, monkeypatch, ConditionRecoveryReport(records=(_record(),)),
    )
    lifecycle = SimpleNamespace(is_shutting_down=False)
    monkeypatch.setattr(module, "update_lifecycle", lambda: lifecycle)
    monkeypatch.setattr(module, "acknowledge_condition_recovery", Mock())
    dialog.acknowledge_button.click()
    task = DeferredTask.instances[-1]
    accepted = Mock()
    monkeypatch.setattr(dialog, "accept", accepted)
    if state == "hidden":
        window.hide()
    elif state == "deactivated":
        controller.deactivate()
    elif state == "presentation":
        controller._is_busy = lambda: True
    elif state == "shutdown":
        lifecycle.is_shutting_down = True
    else:
        replacement = module.ConditionRecoveryDialog(ConditionRecoveryReport(), window)
        controller._dialog = replacement
        replacement.show()
    if failed:
        task.failed.emit(PermissionError("Project is unavailable"))
    else:
        task.succeeded.emit(None)
    task.finished.emit()
    if not failed and state in {"hidden", "presentation"}:
        accepted.assert_called_once_with()
    else:
        accepted.assert_not_called()
    errors.assert_not_called()
    assert controller._ack_task is None
    if state == "replaced":
        assert replacement.isVisible()
    else:
        assert not dialog._saving


@pytest.mark.parametrize("failed", [False, True])
def test_acknowledgement_finishes_quietly_during_launch_and_can_recover(
    qtbot, tmp_path, monkeypatch, failed,
):
    controller, _window, dialog, errors = _controller_with_report(
        qtbot, tmp_path, monkeypatch, ConditionRecoveryReport(records=(_record(),)),
    )
    monkeypatch.setattr(module, "acknowledge_condition_recovery", Mock())
    dialog.acknowledge_button.click()
    task = DeferredTask.instances[-1]
    controller._is_busy = lambda: True
    if failed:
        task.failed.emit(PermissionError("Project is read-only"))
    else:
        task.succeeded.emit(None)
    task.finished.emit()
    controller._is_busy = lambda: False
    assert controller._ack_task is None
    assert not dialog._saving
    errors.assert_not_called()
    if failed:
        assert dialog.isVisible()
        assert dialog.acknowledge_button.isEnabled()
        assert "Could not save acknowledgement" in dialog.status_label.text()
        dialog.acknowledge_button.click()
        retry = DeferredTask.instances[-1]
        retry.succeeded.emit(retry.callback())
        retry.finished.emit()
    assert not dialog.isVisible()


def test_acknowledged_legacy_history_keeps_confirmation_and_rerun_guards(qtbot):
    item = _record(acknowledged_at=datetime.now(timezone.utc))
    dialog = module.ConditionRecoveryDialog(ConditionRecoveryReport(records=(item,)))
    qtbot.addWidget(dialog)
    assert not dialog.acknowledge_button.isEnabled()
    assert not dialog.rerun_button.isEnabled()
    dialog.confirmation.setChecked(True)
    with qtbot.waitSignal(dialog.rerun_requested) as emitted:
        dialog.rerun_button.click()
    assert emitted.args == [item]


def test_same_occurrence_with_new_evidence_can_prompt_again_in_same_window(
    qtbot, tmp_path, monkeypatch,
):
    item = _record()
    controller, _window, dialog, _errors = _controller_with_report(
        qtbot, tmp_path, monkeypatch, ConditionRecoveryReport(records=(item,)),
    )
    dialog.close()
    controller._loaded(ConditionRecoveryReport(records=(item,)), automatic=True)
    assert controller._dialog is dialog
    assert not dialog.isVisible()
    newer = replace(item, updated_at=item.updated_at + timedelta(seconds=1))
    controller._loaded(ConditionRecoveryReport(records=(newer,)), automatic=True)
    assert controller._dialog is not dialog
    assert controller._dialog.isVisible()
