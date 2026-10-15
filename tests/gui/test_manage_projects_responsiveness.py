"""Project discovery keeps the manager usable without touching widgets from workers."""

from threading import Event

import pytest
from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QPushButton
from shiboken6 import delete
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.core.project_service import create_project
from fpvs_studio.gui import controller as controller_module
from fpvs_studio.gui.manage_projects_dialog import ManageProjectsDialog
from fpvs_studio.gui.update_lifecycle import UpdateTaskResult


@pytest.mark.parametrize("stage", ["discovery", "metadata"])
def test_slow_project_scan_keeps_close_and_event_loop_responsive(
    qtbot, qapp, controller, monkeypatch, stage,
):
    scaffold = create_project(controller.load_fpvs_root_dir(), "Managed experiment")
    entered, release = Event(), Event()
    threads, ticks = [], []
    symbol = "discover_project_roots" if stage == "discovery" else "load_project_file"
    original = getattr(controller_module, symbol)

    def slow_read(*args, **kwargs):
        threads.append(QThread.currentThread())
        entered.set()
        assert release.wait(5), "Project discovery blocked the GUI thread"
        return original(*args, **kwargs)

    monkeypatch.setattr(controller_module, symbol, slow_read)
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start()
    job = None
    try:
        controller.show_manage_projects_dialog()
        dialog = controller._manage_projects_dialog
        qtbot.addWidget(dialog)
        job = controller._manage_projects_job
        qtbot.waitUntil(entered.is_set)
        ticks.clear()
        qtbot.waitUntil(lambda: bool(ticks))
        assert dialog.isVisible()
        assert dialog.empty_label.text() == "Loading projects…"
        assert dialog.close_button.isEnabled()
        assert not dialog.open_button.isEnabled()
        assert not dialog.rename_button.isEnabled()
        assert not dialog.delete_button.isEnabled()
        assert not dialog.filter_edit.isEnabled()
        assert threads and all(thread != qapp.thread() for thread in threads)
        release.set()
        qtbot.waitUntil(lambda: controller._manage_projects_job is None)
        assert dialog.project_list.count() == 1
        assert dialog.project_list.item(0).toolTip() == str(scaffold.project_root)
        assert dialog.open_button.isEnabled()
        assert dialog.filter_edit.isEnabled()
    finally:
        release.set()
        timer.stop()
        if job is not None:
            qtbot.waitUntil(lambda: not job.is_running)


class _PendingJob(QObject):
    finished = Signal(object)

    def __init__(self, callback, parent):
        super().__init__(parent)
        self.callback = callback
        self.cancel_event = Event()

    def cancel(self):
        self.cancel_event.set()


@pytest.fixture
def pending_jobs(controller, monkeypatch):
    jobs = []

    def start(callback):
        job = _PendingJob(callback, controller)
        jobs.append(job)
        return job

    monkeypatch.setattr(controller._update_lifecycle, "start_task", start)
    return jobs


def test_scan_error_can_retry_and_preserves_name_sorting(
    qtbot, controller, pending_jobs,
):
    root = controller.load_fpvs_root_dir()
    create_project(root, "Zulu")
    create_project(root, "alpha")
    controller.show_manage_projects_dialog()
    dialog = controller._manage_projects_dialog
    qtbot.addWidget(dialog)
    pending_jobs[-1].finished.emit(UpdateTaskResult(error=OSError("Root unavailable")))
    assert dialog.retry_button.isVisible()
    assert "Could not load projects" in dialog.empty_label.text()
    assert dialog.empty_label.toolTip() == "Root unavailable"
    assert dialog.close_button.isEnabled()
    assert not dialog.open_button.isEnabled()
    dialog.retry_button.click()
    assert len(pending_jobs) == 2
    assert not dialog.retry_button.isVisible()
    assert dialog.empty_label.text() == "Loading projects…"
    job = pending_jobs[-1]
    entries = job.callback(lambda *_args: None, job.cancel_event)
    job.finished.emit(UpdateTaskResult(value=entries))
    assert [dialog.project_list.item(i).text() for i in range(2)] == ["alpha", "Zulu"]
    assert not dialog.retry_button.isVisible()
    assert dialog.open_button.isEnabled()


@pytest.mark.parametrize("dispose", [False, True])
def test_closing_or_destroying_manager_cancels_scan_and_ignores_late_result(
    qtbot, controller, pending_jobs, dispose,
):
    create_project(controller.load_fpvs_root_dir(), "Old experiment")
    entries = controller.load_manageable_project_entries()
    controller.show_manage_projects_dialog()
    old = controller._manage_projects_dialog
    qtbot.addWidget(old)
    old_job = pending_jobs[-1]
    if dispose:
        delete(old)
    else:
        old.close_button.click()
    assert old_job.cancel_event.is_set()
    assert controller._manage_projects_dialog is None
    controller.show_manage_projects_dialog()
    new = controller._manage_projects_dialog
    qtbot.addWidget(new)
    new_job = pending_jobs[-1]
    old_job.finished.emit(UpdateTaskResult(value=entries))
    assert controller._manage_projects_job is new_job
    assert new.project_list.count() == 0
    assert new.empty_label.text() == "Loading projects…"
    new_job.finished.emit(UpdateTaskResult(value=entries))
    assert new.project_list.count() == 1


def test_superseded_scan_does_not_replace_newer_selection(qtbot, controller, pending_jobs):
    root = controller.load_fpvs_root_dir()
    create_project(root, "Alpha")
    selected = create_project(root, "Zulu")
    entries = controller.load_manageable_project_entries()
    controller.show_manage_projects_dialog()
    dialog = controller._manage_projects_dialog
    qtbot.addWidget(dialog)
    old_job = pending_jobs[-1]
    controller._refresh_managed_projects(dialog, selected_root=str(selected.project_root))
    new_job = pending_jobs[-1]
    assert old_job.cancel_event.is_set()
    old_job.finished.emit(UpdateTaskResult(value=entries))
    assert dialog.project_list.count() == 0
    new_job.finished.emit(UpdateTaskResult(value=entries))
    assert dialog.project_list.currentItem().text() == "Zulu"


def test_scan_completion_during_shutdown_leaves_dialog_untouched(
    qtbot, controller, pending_jobs, monkeypatch,
):
    controller.show_manage_projects_dialog()
    dialog = controller._manage_projects_dialog
    qtbot.addWidget(dialog)
    monkeypatch.setattr(controller._update_lifecycle, "_shutdown_requested", True)
    pending_jobs[-1].finished.emit(UpdateTaskResult(value=[]))
    assert dialog.empty_label.text() == "Loading projects…"


def test_worker_snapshot_preserves_containment_current_state_and_cancellation(
    controller, pending_jobs, tmp_path, monkeypatch,
):
    root = controller.load_fpvs_root_dir()
    current = create_project(root, "Current")
    other = create_project(root, "Another")
    outside = create_project(tmp_path / "outside", "Outside")
    invalid = root / "invalid"
    invalid.mkdir()
    (invalid / "project.json").write_text('{"broken": true}', encoding="utf-8")
    monkeypatch.setattr(controller_module, "discover_project_roots", lambda *_a, **_kw: [
        current.project_root, outside.project_root, other.project_root,
        current.project_root, invalid,
    ])
    entries = controller_module._read_project_management_entries(root, current.project_root)
    assert [entry.name for entry in entries] == ["Another", "Current", "invalid"]
    assert not entries[1].can_open and not entries[1].can_delete
    assert entries[1].can_rename
    assert not entries[2].can_open and not entries[2].can_rename
    cancel = Event()
    cancel.set()
    with pytest.raises(InterruptedError):
        controller_module._read_project_management_entries(
            root, current.project_root, cancelled=cancel.is_set,
        )


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("state", ["loading", "failed"])
def test_manage_projects_loading_and_retry_fit_minimum(qtbot, qapp, dark, state):
    original = qapp.palette()
    palette = QPalette(original)
    palette.setColor(QPalette.ColorRole.Window, QColor("#202124" if dark else "#f4f7fb"))
    qapp.setPalette(palette)
    try:
        dialog = ManageProjectsDialog(entries=[])
        qtbot.addWidget(dialog)
        if state == "loading":
            dialog.set_loading()
        else:
            dialog.set_load_error(OSError("The root folder is currently unavailable."))
        dialog.resize(860, 520)
        dialog.show()
        qapp.processEvents()
        assert (dialog.width(), dialog.height()) == (860, 520)
        assert_visible_children_within_parent(dialog)
        for button in dialog.findChildren(QPushButton):
            if button.isVisible():
                assert button.width() >= button.fontMetrics().horizontalAdvance(button.text())
        label = dialog.empty_label
        assert label.height() >= label.heightForWidth(label.width())
    finally:
        qapp.setPalette(original)
