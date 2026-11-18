"""Project discovery keeps the manager usable without touching widgets from workers."""

import json
from threading import Event
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTreeWidget,
)
from shiboken6 import delete, isValid
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.core.project_service import create_project
from fpvs_studio.gui import controller as controller_module
from fpvs_studio.gui.manage_projects_dialog import ManageProjectsDialog, ProjectManagementEntry
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
    start_task = controller._update_lifecycle.start_task

    def start(callback, **options):
        # Reporting can finish startup while the synthetic manager scan is pending.
        if options:
            return start_task(callback, **options)
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
    old_job = pending_jobs[-1]
    # Both paths explicitly destroy this dialog before pytest-qt teardown.
    if dispose:
        delete(old)
    else:
        old.close_button.click()
    qtbot.waitUntil(lambda: not isValid(old))
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


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"], ids=["light", "dark"])
def test_manage_projects_search_preserves_selection_and_recovers_at_minimum_size(
    qtbot, qapp, tmp_path, background,
):
    studies = tmp_path / "Perception and Cognition Lab" / "Visual recognition projects"
    first_root = studies / "Baseline sessions" / "First visual search experiment"
    second_root = studies / "Follow-up sessions" / "Second visual search experiment"
    entries = [
        ProjectManagementEntry(
            name=f"{position} visual search and shape discrimination across eccentricities",
            root=root,
            status_text="Ready",
            status_state="success",
            can_open=True,
            can_delete=True,
            can_rename=True,
        )
        for position, root in (("First", first_root), ("Second", second_root))
    ]
    dialog = ManageProjectsDialog(entries=entries)
    qtbot.addWidget(dialog)
    palette = QPalette(dialog.palette())
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.show()
    qapp.processEvents()

    search = dialog.filter_edit
    assert search.accessibleName() == "Search projects"
    assert search.isClearButtonEnabled()
    dialog.project_list.setCurrentRow(1)
    selected_item = dialog.project_list.currentItem()
    search.setFocus()
    qtbot.keyClicks(search, "visual search")
    qapp.processEvents()
    assert dialog.project_list.count() == 2
    assert dialog.project_list.currentItem() is selected_item
    assert dialog.name_label.text() == entries[1].name
    assert dialog.name_label.height() >= dialog.name_label.heightForWidth(dialog.name_label.width())
    assert dialog.path_label.toolTip() == str(second_root)
    assert dialog.open_button.isEnabled()
    assert_visible_children_within_parent(dialog)

    qtbot.keyClicks(search, " unavailable cohort")
    qapp.processEvents()
    assert dialog.project_list.count() == 0
    empty_label = dialog.empty_label
    assert empty_label.isVisible()
    assert empty_label.text() == "No matching projects. Try another name or folder."
    assert empty_label.height() >= empty_label.heightForWidth(empty_label.width())
    assert search.isEnabled() and dialog.close_button.isEnabled()
    assert not dialog.retry_button.isVisible()
    for button in (
        dialog.open_button, dialog.rename_button, dialog.copy_path_button, dialog.delete_button,
    ):
        assert not button.isEnabled()
    assert_visible_children_within_parent(dialog)

    search.selectAll()
    qtbot.keyClick(search, Qt.Key.Key_Backspace)
    assert search.text() == ""
    assert dialog.project_list.count() == 2
    assert dialog.project_list.currentRow() == 0
    assert not dialog.empty_label.isVisible()
    assert dialog.open_button.isEnabled()

    dialog.project_list.setCurrentRow(1)
    qtbot.keyClicks(search, "baseline sessions")
    assert dialog.project_list.count() == 1
    assert dialog.path_label.toolTip() == str(first_root)
    with qtbot.waitSignal(dialog.open_requested) as open_signal:
        qtbot.mouseClick(dialog.open_button, Qt.MouseButton.LeftButton)
    assert open_signal.args == [str(first_root)]
    assert dialog.size().toTuple() == (860, 520)

    dialog.set_project_entries([])
    assert dialog.empty_label.isVisible()
    assert dialog.empty_label.text() == "No active projects."
    dialog.groups.setCurrentIndex(1)
    assert dialog.empty_label.text() == "No completed projects."
    dialog.groups.setCurrentIndex(2)
    assert dialog.empty_label.text() == "No archived projects."


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"], ids=["light", "dark"])
def test_copy_path_confirms_selected_project_at_minimum_size(
    qtbot, qapp, tmp_path, monkeypatch, background,
):
    copied_paths: list[str] = []
    clipboard = SimpleNamespace(setText=copied_paths.append)
    monkeypatch.setattr(QApplication, "clipboard", lambda: clipboard)
    first_root = tmp_path / "Research projects with descriptive directory names" / "First study"
    second_root = first_root.with_name("Second study")
    entries = [
        ProjectManagementEntry(
            name="First visual search and shape discrimination experiment",
            root=first_root,
            status_text="Ready",
            status_state="success",
            can_open=True,
            can_delete=True,
        ),
        ProjectManagementEntry(
            name="Second visual search and shape discrimination experiment",
            root=second_root,
            status_text="Ready",
            status_state="success",
            can_open=True,
            can_delete=True,
        ),
    ]
    dialog = ManageProjectsDialog(entries=entries)
    qtbot.addWidget(dialog)
    palette = QPalette(dialog.palette())
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    dialog.setPalette(palette)
    dialog.show()
    qapp.processEvents()

    button = dialog.copy_path_button
    assert dialog.size().toTuple() == (860, 520)
    assert button.text() == "Copy Path"
    initial_geometry = button.geometry()
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert copied_paths == [str(first_root)]
    assert button.text() == "Copied"
    assert button.geometry() == initial_geometry
    assert button.width() >= button.fontMetrics().horizontalAdvance(button.text())
    assert_visible_children_within_parent(dialog)

    dialog.project_list.setCurrentRow(1)
    assert button.text() == "Copy Path"
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert copied_paths == [str(first_root), str(second_root)]
    assert button.text() == "Copied"

    dialog.set_loading()
    assert not button.isEnabled()
    assert button.text() == "Copy Path"


def test_manage_project_groups_keep_collection_state_through_archive(
    controller, qtbot, monkeypatch,
):
    from PySide6.QtWidgets import QMessageBox

    from fpvs_studio.core.study_lifecycle import read_study

    root = create_project(controller.load_fpvs_root_dir(), "Collection review").project_root
    monkeypatch.setattr(QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes)
    controller.show_manage_projects_dialog()
    dialog = controller._manage_projects_dialog
    qtbot.addWidget(dialog)

    def group(name):
        qtbot.waitUntil(lambda: controller._manage_projects_job is None)
        assert dialog.groups.tabText(dialog.groups.currentIndex()) == name
        assert dialog.project_list.currentItem().text() == "Collection review"

    group("Active")
    dialog.collection_button.click()
    group("Completed")
    dialog.archive_button.click()
    group("Archived")
    assert read_study(root).collection_complete
    assert not dialog.collection_button.isVisible()
    dialog.archive_button.click()
    group("Completed")
    dialog.collection_button.click()
    group("Active")
    assert not read_study(root).collection_complete


@pytest.mark.parametrize("action", ["open", "inspect", "restore", "cancel_restore", "review"])
def test_manage_saved_versions_keeps_latest_open_and_routes_explicit_choices(
    controller, qtbot, qapp, monkeypatch, action,
):
    from fpvs_studio.core import study_versions
    from fpvs_studio.core.study_lifecycle import get_study
    from fpvs_studio.runtime.participant_results import research_visits_by_version

    scaffold = create_project(controller.load_fpvs_root_dir(), "Versioned study")
    root, project = scaffold.project_root, scaffold.project
    for frequency, keep in ((6, True), (8, True), (10, False)):
        project.settings.protocol.base_hz = frequency
        draft = study_versions.prepare_setup_change(root, project)
        study_versions.commit_setup_change(
            root, project, draft, "", research_visits_by_version, save_version=keep,
        )
    original_id = get_study(root).study_id
    snapshots = study_versions.list_versions(root)
    assert len(snapshots) == 2
    if action in ("open", "inspect"):
        def forbid_asset_scan(*_args, **_kwargs):
            pytest.fail("Project discovery, opening and read-only inspection must skip assets.")

        monkeypatch.setattr(study_versions, "_assets", forbid_asset_scan)

    visited = []
    confirmations = []
    collection_reviews = []
    if action == "review":
        evidence = root / "logs/.participant-results"
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "partial.json").write_text(json.dumps({
            "schema_version": 1,
            "participant_number": "synthetic",
            "session_id": "visit",
            "protocol_version_id": snapshots[1].version_id,
            "runs": [{"completed_frames": 1}],
        }), encoding="utf-8")

        def cancel_review(dialog):
            collection_reviews.append(dialog.windowTitle())
            dialog.reject()
            return dialog.result()

        monkeypatch.setattr(QMessageBox, "exec", cancel_review)

    def confirm_restore(_parent, title, message, buttons, default):
        confirmations.append(title)
        assert default == QMessageBox.StandardButton.Cancel
        assert "working settings and stimuli" in message
        return QMessageBox.StandardButton.Yes if action == "restore" else default

    monkeypatch.setattr(QMessageBox, "question", confirm_restore)

    def open_dialog(dialog):
        visited.append(dialog.windowTitle())
        dialog.show()
        qapp.processEvents()
        assert dialog.size().toTuple() == (660, 460)
        assert_visible_children_within_parent(dialog)
        dialog.resize(dialog.minimumSize())
        qapp.processEvents()
        assert_visible_children_within_parent(dialog)
        if dialog.windowTitle() == "Experiment version history":
            rows = dialog.findChild(QListWidget)
            assert rows.item(0).text().startswith("Version 2 ")
            assert rows.item(1).text().startswith("Version 1 ")
            rows.setCurrentRow(1)
            buttons = {button.text(): button for button in dialog.findChildren(QPushButton)}
            if action in ("restore", "cancel_restore", "review"):
                buttons["Restore this version…"].click()
            else:
                buttons["Open version read-only…"].click()
                dialog.reject()
        else:
            assert dialog.windowTitle() == "Version 1 — read-only"
            tree = dialog.findChild(QTreeWidget)
            match = Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive
            rates = tree.findItems("base hz", match)
            assert any(rate.text(1) == "6.0" for rate in rates)
            assert all(not rate.flags() & Qt.ItemFlag.ItemIsEditable for rate in rates)
            assert tree.findItems("conditions", Qt.MatchFlag.MatchExactly)
            dialog.reject()
        return dialog.result()

    monkeypatch.setattr(QDialog, "exec", open_dialog)
    controller.show_manage_projects_dialog()
    manager = controller._manage_projects_dialog
    qtbot.waitUntil(lambda: controller._manage_projects_job is None)
    assert manager.project_list.currentItem().text() == "Versioned study  ·  2 saved versions"
    assert manager.versions_button.text() == "View 2 saved versions…"
    assert manager.size().toTuple() == (860, 520)
    assert_visible_children_within_parent(manager)
    if action == "open":
        manager.filter_edit.setFocus()
        qtbot.keyClick(manager.filter_edit, Qt.Key.Key_Return)
    else:
        manager.versions_button.click()
    qtbot.waitUntil(lambda: controller.main_window is not None)
    qtbot.addWidget(controller.main_window)
    if action != "open":
        qtbot.waitUntil(lambda: bool(visited))
    document = controller.main_window.document
    assert document.project_root == root
    assert document.project.settings.protocol.base_hz == (6 if action == "restore" else 10)
    assert get_study(root).study_id == original_id
    assert study_versions.list_versions(root)[:2] == snapshots
    assert len(study_versions.list_versions(root)) == (3 if action == "restore" else 2)
    expected = [] if action == "open" else ["Experiment version history"]
    if action == "inspect":
        expected.append("Version 1 — read-only")
    assert visited == expected
    assert confirmations == (["Restore Version 1?"] if "restore" in action else [])
    assert collection_reviews == (["Review changes to this study"] if action == "review" else [])
