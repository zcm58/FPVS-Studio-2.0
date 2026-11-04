"""Registered coverage for direct, asynchronous access to participant results."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication, QLabel
from tests.gui.helpers import assert_visible_children_within_parent, open_created_project


class _DeferredTask(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()
    instances: list[_DeferredTask] = []

    def __init__(self, *, parent_widget, callback) -> None:
        super().__init__(parent_widget)
        self.callback = callback
        self.started = False
        self.__class__.instances.append(self)

    def start(self) -> None:
        self.started = True

    def complete(self) -> None:
        try:
            result = self.callback()
        except Exception as error:
            self.failed.emit(error)
        else:
            self.succeeded.emit(result)
        self.finished.emit()


def _window(qtbot, controller, tmp_path, monkeypatch):
    document, window = open_created_project(controller, qtbot, tmp_path, "Participant Results")
    _DeferredTask.instances.clear()
    monkeypatch.setattr("fpvs_studio.gui.main_window.BackgroundTask", _DeferredTask)
    return document, window


def test_results_action_refreshes_active_project_before_opening_workbook(
    qtbot, controller, tmp_path, monkeypatch,
):
    document, window = _window(qtbot, controller, tmp_path, monkeypatch)
    calls = []
    opened = []
    workbook = document.project_root / "logs" / "participant_summary.xlsx"
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.write_participant_summary",
        lambda root, *, require_data: calls.append((root, require_data)) or workbook,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QDesktopServices.openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )
    assert window.participant_results_action in window.view_menu.actions()
    entry = next(item for item in window._action_palette_entries()
                 if item.action is window.participant_results_action)
    assert "demographics" in entry.keywords

    window.participant_results_action.trigger()
    assert calls == opened == []
    assert not window.participant_results_action.isEnabled()
    assert _DeferredTask.instances[-1].started
    window.open_participant_results()
    assert len(_DeferredTask.instances) == 1

    _DeferredTask.instances[-1].complete()
    assert calls == [(document.project_root, True)]
    assert [Path(path) for path in opened] == [workbook]
    assert window.participant_results_action.isEnabled()
    assert window._participant_results_task is None


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (ValueError("No participant results are available. Run a participant session first."),
         "Run a participant session first"),
        (PermissionError("file is locked"), "Close participant_summary.xlsx in Excel"),
    ],
)
def test_results_errors_are_actionable_and_allow_retry(
    qtbot, controller, tmp_path, monkeypatch, failure, expected,
):
    _, window = _window(qtbot, controller, tmp_path, monkeypatch)
    notices = []

    def fail(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr("fpvs_studio.gui.main_window.write_participant_summary", fail)
    monkeypatch.setattr(
        window, "_show_participant_results_notice",
        lambda title, text, **kwargs: notices.append(text),
    )
    window.participant_results_action.trigger()
    _DeferredTask.instances[-1].complete()
    assert expected in notices[-1]
    assert window.participant_results_action.isEnabled()
    window.participant_results_action.trigger()
    assert len(_DeferredTask.instances) == 2
    _DeferredTask.instances[-1].complete()


def test_results_do_not_open_after_window_handoff(qtbot, controller, tmp_path, monkeypatch):
    document, window = _window(qtbot, controller, tmp_path, monkeypatch)
    opened = []
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.write_participant_summary",
        lambda *_args, **_kwargs: document.project_root / "logs" / "participant_summary.xlsx",
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QDesktopServices.openUrl",
        lambda url: opened.append(url) or True,
    )
    window.open_participant_results()
    window.hide()
    _DeferredTask.instances[-1].complete()
    assert opened == []


def test_open_failure_notice_is_nonmodal_and_keeps_full_path_accessible(
    qtbot, controller, tmp_path, monkeypatch,
):
    document, window = _window(qtbot, controller, tmp_path, monkeypatch)
    workbook = (document.project_root / "a long research project directory" /
                "logs" / "participant_summary.xlsx")
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.write_participant_summary",
        lambda *_args, **_kwargs: workbook,
    )
    monkeypatch.setattr("fpvs_studio.gui.main_window.QDesktopServices.openUrl", lambda _url: False)
    window.open_participant_results()
    _DeferredTask.instances[-1].complete()
    notice = window._participant_results_notice
    assert notice is not None
    qtbot.addWidget(notice)
    QApplication.processEvents()
    assert notice.isVisible()
    assert notice.windowModality() == Qt.WindowModality.NonModal
    assert str(workbook) in notice.text()
    assert "open this file manually" in notice.text()
    assert_visible_children_within_parent(notice)
    for label in notice.findChildren(QLabel):
        if label.isVisible() and label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width())
