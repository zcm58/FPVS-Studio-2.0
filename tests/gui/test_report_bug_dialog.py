"""Registered visible-only coverage; all transport, browser, and dialogs are fake."""

from __future__ import annotations

import json
from threading import Event

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QPushButton
from tests.gui.helpers import assert_visible_children_within_parent, open_created_project

from fpvs_studio.gui import bug_report_controller as module
from fpvs_studio.gui.report_bug_dialog import ReportBugDialog
from fpvs_studio.gui.root_folder_setup_dialog import RootFolderSetupDialog
from fpvs_studio.gui.update_lifecycle import UpdateTaskResult
from fpvs_studio.gui.welcome_window import WelcomeWindow
from fpvs_studio.support.client import SERVICE_ORIGIN, ReportClient, ReportServiceError
from fpvs_studio.support.models import Draft, Intent, Report
from fpvs_studio.support.storage import DraftStore


class FakeJob(QObject):
    finished = Signal(object)

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.cancel_event = Event()

    def cancel(self):
        self.cancel_event.set()

    def complete(self):
        try:
            value = self.callback(lambda *_args: None, self.cancel_event)
            result = UpdateTaskResult(value=value)
        except Exception as error:
            result = UpdateTaskResult(error=error)
        self.finished.emit(result)


class FakeLifecycle(QObject):
    is_shutting_down = False
    shutdown_started = Signal()

    def start_task(self, callback, **kwargs):
        return FakeJob(callback)


@pytest.mark.parametrize("size", [(760, 680), (860, 760)])
@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_feature_editor_limit_and_layout(qtbot, size, background):
    dialog = ReportBugDialog(Draft(report=Report(kind="feature"), include_logs=False), online=True)
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.resize(*size)
    dialog.show()
    assert dialog.tabs.count() == 1
    assert not dialog.title_edit.isVisible()
    assert not dialog.submit_button.isEnabled()
    dialog.happened_edit.setPlainText("😀" * 4000)
    assert dialog.submit_button.isEnabled()
    assert dialog.feature_count.text() == "4,000 / 4,000 characters"
    with qtbot.waitSignal(dialog.action_requested) as emitted:
        dialog.submit_button.click()
    assert emitted.args == ["submit"]
    dialog.menu_actions["copy"].trigger()
    assert "Requested feature" in QApplication.clipboard().text()
    assert "Error logs" not in QApplication.clipboard().text()
    dialog.happened_edit.insertPlainText("x")
    assert not dialog.submit_button.isEnabled()
    assert len(dialog.happened_edit.toPlainText()) == 4001
    for delivery, state in (
        ("editing", "editing"), ("editing", "loading"), ("editing", "verifying"),
        ("uncertain", "sending"), ("uncertain", "checking"),
        ("received", "editing"), ("submitted", "editing"),
    ):
        draft = dialog.snapshot()
        draft.delivery = delivery
        dialog.set_delivery(draft)
        dialog.set_state(state, "Request received. Receipt: 12345678-1234-1234-1234-123456789abc")
        QApplication.processEvents()
        assert (dialog.width(), dialog.height()) == size
        assert_visible_children_within_parent(dialog)


def test_feature_controller_never_collects_logs(qtbot, qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(module, "update_lifecycle", lambda _app: FakeLifecycle())
    monkeypatch.setattr(module, "collect_diagnostics", lambda _root: pytest.fail("Collected logs"))
    controller = module.BugReportController(
        qapp, root=tmp_path, kind="feature", client=ReportClient()
    )
    controller.show()
    qtbot.addWidget(controller.dialog)
    controller._job.complete()
    dialog = controller.dialog
    dialog.happened_edit.setPlainText("Add keyboard shortcuts")
    dialog.close()
    controller._job.complete()
    saved = DraftStore(tmp_path, kind="feature").load_latest()
    assert saved.report.happened == "Add keyboard shortcuts"
    assert not saved.include_logs
    assert saved.report.diagnostics == ""
    controller.show()
    assert controller.dialog is dialog
    controller._dirty = False
    controller._autosave.stop()
    dialog.close()
    controller.deleteLater()


@pytest.fixture
def reporter(qtbot, qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(module, "update_lifecycle", lambda _app: FakeLifecycle())
    monkeypatch.setattr(module.QDesktopServices, "openUrl", lambda _url: True)
    controller = module.BugReportController(qapp, root=tmp_path, client=ReportClient())
    controller.show()
    qtbot.addWidget(controller.dialog)
    controller._job.complete()
    controller._dirty = False
    controller._autosave.stop()
    yield controller
    controller._autosave.stop()
    controller._poll.stop()
    controller._dirty = False
    if controller._job is not None:
        controller._job.cancel()
        controller._job.complete()
    controller.dialog.close()
    if controller._job is not None:
        controller._job.complete()
    controller.deleteLater()


@pytest.mark.parametrize("size", [(760, 680), (860, 760)])
@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_layout_every_state_and_tab(qtbot, size, background):
    dialog = ReportBugDialog(Draft(), online=True)
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.resize(*size)
    dialog.happened_edit.setPlainText("Detailed reproduction information. " * 150)
    dialog.offer_error("Another error", "A traceback")
    dialog.show()
    for delivery, state in (
        ("editing", "editing"),
        ("editing", "loading"),
        ("editing", "verifying"),
        ("uncertain", "sending"),
        ("uncertain", "checking"),
        ("received", "editing"),
        ("submitted", "editing"),
    ):
        draft = dialog.snapshot()
        draft.delivery = delivery
        dialog.set_delivery(draft)
        dialog.set_state(
            state,
            "The report is preserved while the service processes the request. "
            "Receipt: 12345678-1234-1234-1234-123456789abc",
        )
        for tab in (0, 1):
            dialog.tabs.setCurrentIndex(tab)
            QApplication.processEvents()
            assert (dialog.width(), dialog.height()) == size
            assert_visible_children_within_parent(dialog)
            for label in dialog.findChildren(QLabel):
                if label.isVisible() and not label.wordWrap():
                    assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())


def test_offline_editor_validation_exclusion_and_save_cancel(qtbot, monkeypatch):
    dialog = ReportBugDialog(Draft(report=Report(diagnostics="Private diagnostic")))
    qtbot.addWidget(dialog)
    assert not dialog.submit_button.isEnabled()
    assert "not connected" in dialog.status_label.text()
    dialog.online = True
    dialog.set_state("editing", "Review")
    dialog._submit()
    assert "summary" in dialog.status_label.text()
    dialog.title_edit.setText("Error exporting")
    dialog.happened_edit.setPlainText("Export failed")
    dialog.include_logs.setChecked(False)
    assert "Private diagnostic" not in dialog.snapshot().report.as_text(include_logs=False)
    dialog._secondary("copy")
    assert "Private diagnostic" not in QApplication.clipboard().text()
    requests = []
    dialog.export_requested.connect(requests.append)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: ("", ""))
    dialog._export()
    assert requests == []
    with qtbot.waitSignal(dialog.action_requested):
        dialog._submit()


def test_repeat_open_preserves_draft_and_new_error_requires_action(reporter):
    dialog = reporter.dialog
    dialog.happened_edit.setPlainText("My carefully written report")
    dialog.diagnostics_edit.setPlainText("Reviewed logs")
    reporter.show("New error", "New traceback")
    assert reporter.dialog is dialog
    assert dialog.diagnostics_edit.toPlainText() == "Reviewed logs"
    dialog.use_pending_error()
    assert dialog.happened_edit.toPlainText() == "My carefully written report"
    assert dialog.diagnostics_edit.toPlainText() == "New traceback"


def test_close_during_verification_reopens_editable(reporter):
    reporter._intent = Intent(intent_id="i" * 20, browser_token="b" * 43, desktop_token="d" * 43)
    reporter.dialog.set_state("verifying", "Complete verification")
    reporter.dialog.close()
    reporter.show()
    assert reporter._intent is None
    assert not reporter.dialog.happened_edit.isReadOnly()
    assert reporter.dialog.submit_button.isVisible()


def test_failed_draft_save_reopens_with_copyable_text(reporter, monkeypatch):
    def fail(_draft):
        raise PermissionError("read only")

    monkeypatch.setattr(reporter.store(), "save", fail)
    reporter.dialog.happened_edit.setPlainText("Keep this text")
    reporter.dialog.close()
    reporter._job.complete()
    assert reporter.dialog.isVisible()
    assert reporter.dialog.happened_edit.toPlainText() == "Keep this text"
    assert "could not" in reporter.dialog.status_label.text()
    assert reporter._save_failed


def test_shutdown_saves_dirty_text_without_canceling_local_write(reporter):
    reporter.dialog.happened_edit.setPlainText("Persist on quit")
    reporter._lifecycle.is_shutting_down = True
    reporter._lifecycle.shutdown_started.emit()
    assert reporter._job is not None
    assert not reporter._job.cancel_event.is_set()
    reporter._job.complete()
    assert reporter.store().load_latest().report.happened == "Persist on quit"
    reporter._lifecycle.is_shutting_down = False


def test_draft_close_saves_and_receipt_is_durable_before_upload(reporter, tmp_path):
    dialog = reporter.dialog
    dialog.title_edit.setText("Crash")
    dialog.happened_edit.setPlainText("It stopped")
    report_id = dialog.snapshot().report.report_id
    intent = Intent(intent_id="i" * 20, browser_token="b" * 43, desktop_token="d" * 43)
    calls = []

    def transport(method, url, data, headers):
        calls.append(url)
        if url.endswith("/v1/intents"):
            return intent.model_dump_json().encode()
        if "/intents/" in url:
            return b'{"state":"verified"}'
        persisted = DraftStore(tmp_path).load_latest()
        assert persisted.delivery == "uncertain"
        assert persisted.report.report_id == report_id
        raise ReportServiceError("The connection was lost.")

    reporter.client = ReportClient(SERVICE_ORIGIN, transport=transport)
    dialog.online = True
    reporter._action("submit")
    reporter._job.complete()
    reporter._poll.stop()
    reporter._poll_verification()
    reporter._job.complete()  # Verification starts upload job.
    reporter._job.complete()  # Simulate ambiguous upload result.
    assert dialog.snapshot().delivery == "uncertain"
    assert dialog.submit_button.text() == "Check status"
    assert dialog.happened_edit.isReadOnly()
    assert sum("/v1/reports?" in url for url in calls) == 1
    dialog.close()
    if reporter._job is not None:
        reporter._job.complete()
    assert DraftStore(tmp_path).load_latest().report.report_id == report_id


def test_cancel_during_intent_does_not_open_browser(reporter, monkeypatch):
    opened = []
    monkeypatch.setattr(module.QDesktopServices, "openUrl", opened.append)
    reporter.dialog.title_edit.setText("Error")
    reporter.dialog.happened_edit.setPlainText("Failure")
    reporter.client = ReportClient(
        SERVICE_ORIGIN,
        transport=lambda *_args: (
            Intent(intent_id="i" * 20, browser_token="b" * 43, desktop_token="d" * 43)
            .model_dump_json()
            .encode()
        ),
    )
    reporter.dialog.online = True
    reporter._action("submit")
    reporter._action("cancel")
    reporter._job.complete()
    assert opened == []
    assert reporter._intent is None


def test_received_response_keeps_identity_and_prevents_new_submission(reporter):
    draft = reporter.dialog.snapshot()
    draft.delivery = "uncertain"
    draft.service_url = SERVICE_ORIGIN
    reporter.dialog.set_delivery(draft)
    reporter.client = ReportClient(
        SERVICE_ORIGIN,
        transport=lambda *_args: json.dumps(
            {
                "report_id": str(draft.report.report_id),
                "state": "received",
            }
        ).encode(),
    )
    reporter._action("check")
    reporter._job.complete()
    assert reporter.dialog.snapshot().delivery == "received"
    reporter._action("new")
    assert reporter.dialog.snapshot().report.report_id == draft.report.report_id


def test_welcome_and_root_have_no_reporting_buttons(qtbot):
    root = RootFolderSetupDialog(first_run=True)
    welcome = WelcomeWindow()
    qtbot.addWidget(root)
    qtbot.addWidget(welcome)
    for surface in (root, welcome):
        assert not any(
            "Report" in button.text() for button in surface.findChildren(QPushButton)
        )


def test_file_menu_support_order(controller, qtbot, tmp_path, monkeypatch):
    _, window = open_created_project(controller, qtbot, tmp_path, "Bug Report Menu")
    actions = window.file_menu.actions()
    assert window.report_bug_action.text() == "Report a Bug..."
    assert actions.index(window.report_bug_action) == actions.index(window.check_updates_action) + 1
    assert (
        actions.index(window.request_feature_action) == actions.index(window.report_bug_action) + 1
    )
    calls = []
    monkeypatch.setattr(module, "show_feature_request", lambda: calls.append(True))
    window.request_feature_action.trigger()
    assert calls == [True]
