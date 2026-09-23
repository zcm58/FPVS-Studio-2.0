"""Registered visible smoke coverage for the whole-experiment Library workflow."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton
from tests.gui.helpers import assert_visible_children_within_parent, open_created_project
from tests.unit.test_library_installations import project as installed_project

from fpvs_studio.core.library_installations import scan_library_projects
from fpvs_studio.core.project_bundle import ProjectBundleCancelled, ProjectBundleError
from fpvs_studio.core.project_service import create_project
from fpvs_studio.gui import library_controller as library_module
from fpvs_studio.gui.bundle_import_dialog import BundleImportProgressDialog
from fpvs_studio.gui.create_project_dialog import CreateProjectDialog
from fpvs_studio.gui.library_controller import LibraryController
from fpvs_studio.gui.library_dialog import LibraryDialog
from fpvs_studio.gui.settings_dialog import AppSettingsDialog
from fpvs_studio.gui.update_lifecycle import UpdateLifecycle
from fpvs_studio.gui.welcome_window import WelcomeWindow
from fpvs_studio.library.errors import LibraryAuthorizationError, LibraryCancelled
from fpvs_studio.library.models import LibraryCatalog, LibraryConnection, LibraryItem


def _item(**updates) -> LibraryItem:
    data = dict(
        item_id="example",
        version="1.0",
        title="Attentional Blink example experiment",
        description="An editable example with a complete task and source stimuli.",
        experiment_category="attentional_blink",
        filename="example.fpvsbundle",
        size_bytes=1024,
        uncompressed_size_bytes=4096,
        file_count=3,
        sha256="a" * 64,
        min_studio_version="1.0.0",
    )
    data.update(updates)
    return LibraryItem(**data)


def _connection() -> LibraryConnection:
    return LibraryConnection(
        device_id="device-1",
        library_name="Research experiment library",
        device_name="Lab computer",
    )


@pytest.mark.parametrize("size", [(900, 640), (1040, 760)])
@pytest.mark.parametrize("state", [
    "disconnected", "ready", "busy", "error", "empty", "installed", "update", "review",
])
def test_library_layout_and_full_metadata(qtbot, tmp_path, size, state) -> None:
    dialog = LibraryDialog()
    qtbot.addWidget(dialog)
    item = _item(title="Long experiment name " * 7, description="Protocol description. " * 150)
    if state != "disconnected":
        dialog.set_connection(_connection())
        if state in {"installed", "update", "review"}:
            installed_project(
                tmp_path / ("long-folder-name-" * 5), project_id="example",
                name=item.title, version="0.9" if state == "update" else "1.0",
                linked=False,
            )
            # Give known versions the catalog identity; unknown copies stay unlinked.
            if state != "review":
                from tests.unit.test_library_project_updates import origin

                from fpvs_studio.core.library_origin import save_library_origin
                folder = next((tmp_path / ("long-folder-name-" * 5)).iterdir())
                save_library_origin(folder, origin(
                    item_id="example", local_project_id="example",
                    installed_version="0.9" if state == "update" else "1.0",
                ))
        dialog.set_installations(scan_library_projects(tmp_path), "https://library.example.test")
        dialog.set_catalog(
            LibraryCatalog(schema_version="1.0", library_name="Research", items=[item])
        )
    if state == "busy":
        dialog.set_busy(True, "Downloading and verifying the experiment…", downloading=True)
        dialog.show_progress(512, 1024)
    elif state == "error":
        dialog.set_busy(
            False,
            "This computer's access was revoked. Disconnect and reconnect with a new access code.",
        )
    elif state == "empty":
        dialog.set_catalog(LibraryCatalog(schema_version="1.0", library_name="Research", items=[]))
    dialog.resize(*size)
    dialog.show()
    QApplication.processEvents()
    assert (dialog.width(), dialog.height()) == size
    assert_visible_children_within_parent(dialog)
    for button in dialog.findChildren(QPushButton):
        if button.isVisible():
            assert button.width() >= button.fontMetrics().horizontalAdvance(button.text())
    for label in dialog.findChildren(QLabel):
        if label.isVisible() and label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width())
    if state in ("ready", "busy", "error"):
        assert item.title in dialog.details.toPlainText()
        assert item.description in dialog.item_list.item(0).toolTip()
    if state == "busy":
        assert dialog.progress_bar.value() == 50
        assert not dialog.install_button.isEnabled()
        assert dialog.cancel_button.isEnabled()
    if state == "installed":
        assert not dialog.install_button.isEnabled()
        assert dialog.install_button.text() == "Already installed"
    elif state in {"update", "review"}:
        assert dialog.install_button.isEnabled()
        assert "Review" in dialog.install_button.text()


def test_library_rechecks_installation_before_any_download(qapp, qtbot, monkeypatch, tmp_path):
    controller, client, _lifecycle = _controller(
        qapp, qtbot, monkeypatch, tmp_path, lambda *_args: pytest.fail("Unexpected import"),
    )
    _enroll(controller, qtbot)
    reviewed = []
    controller._review_project = reviewed.append
    folder = installed_project(tmp_path, project_id="example", linked=False)
    controller.dialog.install_button.click()
    qtbot.waitUntil(lambda: controller._job is None)
    assert reviewed == [folder]
    assert not client.download_started.is_set()
    assert not controller.dialog.isVisible()


def test_library_search_and_incompatible_item(qtbot) -> None:
    dialog = LibraryDialog()
    qtbot.addWidget(dialog)
    dialog.set_connection(_connection())
    item = _item(min_studio_version="999.0.0")
    dialog.set_catalog(LibraryCatalog(schema_version="1.0", library_name="Research", items=[item]))
    assert "Requires FPVS Studio 999.0.0" in dialog.details.toPlainText()
    assert not dialog.install_button.isEnabled()
    dialog.search_edit.setText("nothing matches")
    assert dialog.selected_item() is None
    assert "No matching" in dialog.details.toPlainText()
    dialog.search_edit.setText("attentional")
    assert dialog.item_list.count() == 1


class _Client:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.service_url = "https://library.example.test"
        self.connection = None
        self.releases = 0
        self.download_started = Event()
        self.finish_download = Event()
        self.block_download = False
        self.authorization_error = False

    def connection_info(self):
        return self.connection

    def enroll(self, code, device_name, *, cancel_event=None):
        assert code == "test-access"
        self.connection = _connection()
        return self.connection

    def catalog(self, *, cancel_event=None):
        if self.authorization_error:
            raise LibraryAuthorizationError(
                "Access revoked. Disconnect this computer and reconnect."
            )
        return LibraryCatalog(schema_version="1.0", library_name="Research", items=[_item()])

    def download(self, item, *, cancel_event=None, progress_callback=None):
        self.download_started.set()
        if self.block_download:
            while not self.finish_download.wait(0.01):
                if cancel_event.is_set():
                    raise LibraryCancelled("Canceled")
        progress_callback(item.size_bytes, item.size_bytes)
        return self.path

    def release_download(self):
        self.releases += 1

    def disconnect(self, *, cancel_event=None):
        self.connection = None


def _controller(qapp, qtbot, monkeypatch, tmp_path, import_bundle):
    lifecycle = UpdateLifecycle(qapp, quit_callback=lambda: None)
    monkeypatch.setattr(library_module, "update_lifecycle", lambda app: lifecycle)
    monkeypatch.setattr(
        library_module, "read_project_bundle_manifest",
        lambda path: SimpleNamespace(project=SimpleNamespace(project_id="example")),
    )
    client = _Client(tmp_path / "example.fpvsbundle")
    controller = LibraryController(
        qapp, import_bundle=import_bundle, client=client, studio_root=lambda: tmp_path,
        review_project=lambda root: None,
    )
    controller.show()
    qtbot.addWidget(controller.dialog)
    qtbot.waitUntil(lambda: controller._job is None)
    return controller, client, lifecycle


def _enroll(controller, qtbot) -> None:
    controller.dialog.code_edit.setText("test-access")
    controller.dialog.connect_button.click()
    qtbot.waitUntil(lambda: controller._job is None and controller.dialog.item_list.count() == 1)


def test_enrollment_import_lease_and_disconnect(qapp, qtbot, monkeypatch, tmp_path) -> None:
    handoffs = []
    controller, client, _lifecycle = _controller(
        qapp,
        qtbot,
        monkeypatch,
        tmp_path,
        lambda path, manifest, origin, finished: handoffs.append(
            (path, manifest, origin, finished)
        ),
    )
    _enroll(controller, qtbot)
    assert controller.dialog.code_edit.text() == ""
    controller.dialog.install_button.click()
    qtbot.waitUntil(lambda: len(handoffs) == 1)
    assert client.releases == 0
    assert controller._importing
    controller.show()
    assert not controller.dialog.isVisible()
    assert handoffs[0][1].project.project_id == "example"
    assert handoffs[0][2].item_id == "example"
    assert handoffs[0][2].installed_version == "1.0"
    assert handoffs[0][2].bundle_sha256 == "a" * 64
    handoffs[0][3](None)
    assert client.releases == 1
    assert not controller._importing
    assert controller.dialog.isVisible()
    controller.dialog.disconnect_button.click()
    qtbot.waitUntil(lambda: controller._job is None)
    assert client.connection is None
    assert controller.dialog.item_list.count() == 0
    assert "remain available offline" in controller.dialog.status_label.text()


@pytest.mark.parametrize("action", ["escape", "close", "cancel", "shutdown"])
def test_busy_download_cancellation_does_not_import(
    qapp,
    qtbot,
    monkeypatch,
    tmp_path,
    action,
) -> None:
    handoffs = []
    controller, client, lifecycle = _controller(
        qapp,
        qtbot,
        monkeypatch,
        tmp_path,
        lambda *args: handoffs.append(args),
    )
    _enroll(controller, qtbot)
    client.block_download = True
    controller.dialog.install_button.click()
    qtbot.waitUntil(client.download_started.is_set)
    if action == "escape":
        qtbot.keyClick(controller.dialog, Qt.Key.Key_Escape)
    elif action == "close":
        controller.dialog.close()
    elif action == "cancel":
        controller.dialog.cancel_button.click()
    else:
        lifecycle.request_shutdown()
    qtbot.waitUntil(lambda: controller._job is None)
    assert handoffs == []
    assert not lifecycle.has_active_jobs
    assert "canceled" in controller.dialog.status_label.text().lower()


def test_authorization_failure_clears_catalog(qapp, qtbot, monkeypatch, tmp_path) -> None:
    controller, client, _lifecycle = _controller(
        qapp,
        qtbot,
        monkeypatch,
        tmp_path,
        lambda *args: None,
    )
    _enroll(controller, qtbot)
    client.authorization_error = True
    controller.dialog.refresh_button.click()
    qtbot.waitUntil(lambda: controller._job is None)
    assert controller.dialog.item_list.count() == 0
    assert not controller.dialog.install_button.isEnabled()
    assert "revoked" in controller.dialog.status_label.text()


def test_library_import_review_cancel_releases_handoff(controller, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(controller, "_prepare_project_bundle_import", lambda: (None, None))
    results = []
    controller.import_project_bundle_file(tmp_path / "test.fpvsbundle", on_finished=results.append)
    assert results == [None]


@pytest.mark.parametrize("allow_handoff,save", [(False, True), (True, False), (True, True)])
def test_existing_library_review_respects_handoff_and_save_guards(
    controller, tmp_path, monkeypatch, allow_handoff, save,
):
    window = SimpleNamespace(
        document=SimpleNamespace(project_root=tmp_path / "current"),
        maybe_save_changes=lambda: save,
    )
    monkeypatch.setattr(controller, "main_window", window)
    monkeypatch.setattr(controller, "_can_publish_from", lambda target: allow_handoff)
    opened = []
    monkeypatch.setattr(
        controller, "request_open_project",
        lambda path, **kwargs: opened.append((path, kwargs["on_opened"])),
    )
    controller._review_library_project(tmp_path / "existing")
    assert bool(opened) == (allow_handoff and save)
    if opened:
        assert opened == [(tmp_path / "existing", controller.show_project_versions)]


def test_library_import_cancel_and_late_commit(controller, qtbot, tmp_path, monkeypatch) -> None:
    from fpvs_studio.gui import controller as controller_module

    monkeypatch.setattr(
        controller,
        "_show_project_bundle_import_review",
        lambda *args, **kwargs: (
            int(QDialog.DialogCode.Accepted),
            SimpleNamespace(
                project=SimpleNamespace(name="Library example"),
            ),
        ),
    )
    monkeypatch.setattr(controller, "_confirm_imported_display_settings", lambda *args, **kw: True)
    started = Event()

    def canceled_import(*args, cancel_event, **kwargs):
        started.set()
        cancel_event.wait(3)
        raise ProjectBundleCancelled("Canceled")

    monkeypatch.setattr(controller_module, "import_project_bundle", canceled_import)
    results = []
    controller.import_project_bundle_file(tmp_path / "test.fpvsbundle", on_finished=results.append)
    qtbot.waitUntil(started.is_set)
    progress = controller._import_bundle_processing_dialog
    assert progress is not None
    progress.reject()
    qtbot.waitUntil(lambda: results == [None])
    assert controller._library_import_job is None

    def committed_import(bundle, root, cancel_event, **kwargs):
        scaffold = create_project(root, "Committed library project")
        cancel_event.set()  # Simulate Cancel arriving after the filesystem commit.
        return scaffold

    monkeypatch.setattr(controller_module, "import_project_bundle", committed_import)
    results.clear()
    controller.import_project_bundle_file(tmp_path / "test.fpvsbundle", on_finished=results.append)
    qtbot.waitUntil(lambda: bool(results))
    assert results[0] is not None and results[0].is_dir()
    qtbot.addWidget(controller.main_window)
    assert controller.main_window.document.project.meta.name == "Committed library project"


@pytest.mark.parametrize("outcome", ["success", "cancel", "failure", "shutdown"])
def test_manifest_read_runs_off_gui_and_retains_lease(
    qapp,
    qtbot,
    monkeypatch,
    tmp_path,
    outcome,
) -> None:
    handoffs = []
    controller, client, lifecycle = _controller(
        qapp,
        qtbot,
        monkeypatch,
        tmp_path,
        lambda *args: handoffs.append(args),
    )
    _enroll(controller, qtbot)
    started, finish_read = Event(), Event()
    worker_threads = []

    def read_manifest(path):
        worker_threads.append(QThread.currentThread() != qapp.thread())
        started.set()
        assert finish_read.wait(3), "Test did not release manifest reader"
        if outcome == "failure":
            raise ProjectBundleError("Invalid manifest")
        return SimpleNamespace(project=SimpleNamespace(project_id="worker-manifest"))

    monkeypatch.setattr(library_module, "read_project_bundle_manifest", read_manifest)
    controller.dialog.install_button.click()
    try:
        qtbot.waitUntil(started.is_set)
        assert "Reading experiment details" in controller.dialog.status_label.text()
        assert controller.dialog.cancel_button.isEnabled()
        assert client.releases == 0
        if outcome == "cancel":
            controller.dialog.cancel_button.click()
        elif outcome == "shutdown":
            lifecycle.request_shutdown()
    finally:
        finish_read.set()
    qtbot.waitUntil(lambda: controller._job is None)
    assert worker_threads == [True]
    assert not lifecycle.has_active_jobs
    if outcome == "success":
        assert handoffs[0][1].project.project_id == "worker-manifest"
        assert client.releases == 0
        handoffs[0][3](None)
    else:
        assert handoffs == []
    assert client.releases == 1


def test_library_review_uses_prepared_manifest_without_gui_file_io(
    controller,
    monkeypatch,
    tmp_path,
) -> None:
    from fpvs_studio.gui import controller as controller_module

    prepared = SimpleNamespace(project=SimpleNamespace(name="Prepared review"))
    seen = []

    class Review:
        def __init__(self, **kwargs):
            seen.append(kwargs["manifest"])

        def exec(self):
            return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(controller_module, "BundleImportReviewDialog", Review)
    monkeypatch.setattr(
        controller_module,
        "read_project_bundle_manifest",
        lambda path: pytest.fail("Library manifest must already be read on a worker"),
    )
    result, manifest = controller._show_project_bundle_import_review(
        tmp_path / "example.fpvsbundle",
        tmp_path,
        None,
        manifest=prepared,
    )
    assert result == int(QDialog.DialogCode.Rejected)
    assert manifest is prepared and seen == [prepared]


@pytest.mark.parametrize("size", [(760, 520), (1120, 720)])
def test_welcome_four_actions_layout_and_busy(qtbot, size) -> None:
    welcome = WelcomeWindow()
    qtbot.addWidget(welcome)
    welcome.resize(*size)
    welcome.show()
    QApplication.processEvents()
    assert (welcome.width(), welcome.height()) == size
    assert_visible_children_within_parent(welcome)
    assert welcome.findChild(QPushButton, "welcome_experiment_library") is None
    with qtbot.waitSignal(welcome.create_requested):
        welcome.create_button.click()
    welcome.set_import_busy(True)
    assert not welcome.create_button.isEnabled()
    welcome.set_import_busy(False)
    assert welcome.create_button.isEnabled()


@pytest.mark.parametrize("entry", ["welcome", "existing_project"])
@pytest.mark.parametrize("download", [False, True])
def test_new_experiment_library_route_and_cancel(
    controller, qtbot, tmp_path, monkeypatch, entry, download
) -> None:
    called = []
    if entry == "existing_project":
        _document, window = open_created_project(controller, qtbot, tmp_path)
        launch = window.home_page.new_project_button.click
    else:
        launch = controller.welcome_window.create_button.click

    def choose_source(dialog: CreateProjectDialog) -> int:
        qtbot.addWidget(dialog)
        assert dialog.category_stack.currentWidget() is dialog.source_page
        if download:
            dialog.library_button.click()
        else:
            dialog.reject()
        return int(dialog.result())

    monkeypatch.setattr(CreateProjectDialog, "exec", choose_source)
    monkeypatch.setattr(controller, "show_library", lambda: called.append("library"))
    monkeypatch.setattr(
        controller, "create_project",
        lambda *args, **kwargs: pytest.fail("This route must not scaffold an empty project"),
    )
    launch()
    assert called == (["library"] if download else [])


def test_settings_library_entry_and_main_view_action(controller, qtbot, tmp_path) -> None:
    called = []
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path,
        on_show_library=lambda: called.append(True),
        experiment_test_mode_available=True,
        attentional_blink_pilot_mode_available=True,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    QApplication.processEvents()
    assert_visible_children_within_parent(dialog)
    dialog.library_button.click()
    assert called == [True]
    assert not dialog.isVisible()
    _document, window = open_created_project(controller, qtbot, tmp_path)
    assert window.library_action not in window.file_menu.actions()
    assert window.view_menu.actions()[0] is window.library_action
    assert window.view_menu.actions()[1].isSeparator()
    window._on_request_library = lambda: called.append(True)
    window.library_action.trigger()
    assert called == [True, True]


def test_import_progress_escape_requests_cancel_and_stays_alive(qtbot) -> None:
    canceled = []
    dialog = BundleImportProgressDialog(on_cancel=lambda: canceled.append(True))
    qtbot.addWidget(dialog)
    dialog.start()
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert canceled == [True]
    assert dialog.isVisible()
    assert not dialog.cancel_button.isEnabled()
    dialog.finish()
