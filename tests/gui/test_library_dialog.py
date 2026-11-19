"""Registered visible smoke coverage for the whole-experiment Library workflow."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QAbstractAnimation, Qt, QThread
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QWidget
from tests.gui.helpers import (
    assert_visible_children_within_parent,
    open_created_project,
    select_settings_category,
)
from tests.unit.test_library_installations import project as installed_project

from fpvs_studio.core.library_installations import scan_library_projects
from fpvs_studio.core.library_origin import MANAGED_LIBRARY_SERVICE_URL
from fpvs_studio.core.project_bundle import ProjectBundleCancelled, ProjectBundleError
from fpvs_studio.core.project_service import create_project
from fpvs_studio.gui import library_controller as library_module
from fpvs_studio.gui import library_dialog as library_ui
from fpvs_studio.gui.bundle_import_dialog import BundleImportProgressDialog
from fpvs_studio.gui.create_project_dialog import CreateProjectDialog
from fpvs_studio.gui.library_controller import LibraryController
from fpvs_studio.gui.library_dialog import LibraryDialog
from fpvs_studio.gui.settings_dialog import AppSettingsDialog
from fpvs_studio.gui.update_lifecycle import UpdateLifecycle
from fpvs_studio.gui.welcome_window import WelcomeWindow
from fpvs_studio.library.errors import LibraryAuthorizationError, LibraryCancelled, LibraryError
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


def _demo() -> LibraryItem:
    return _item(
        item_id="color-oddball-demo", version="1.0.0", title="Color Oddball Demo",
        experiment_category="fpvs_oddball", filename="color-oddball-demo.fpvsbundle",
        description="The same grayscale objects, followed by red or green oddballs.",
    )


def _connection(**updates) -> LibraryConnection:
    values = dict(
        device_id="device-1",
        library_name="Research experiment library",
        device_name="Lab computer",
    )
    values.update(updates)
    return LibraryConnection(**values)


def _project_buttons(dialog: LibraryDialog) -> list[QPushButton]:
    return [
        button for button in dialog.findChildren(QPushButton)
        if button.property("libraryProject") == "true" and not button.isHidden()
    ]


def test_library_sign_in_is_available_for_openfpvs_disconnected_state(qtbot, monkeypatch):
    opened = []
    monkeypatch.setattr(library_ui, "QDesktopServices", SimpleNamespace(
        openUrl=lambda url: opened.append(url.toString()) or True,
    ))
    dialog = LibraryDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    assert not dialog.sign_in_button.isVisible()
    qtbot.mouseClick(dialog.connect_toggle, Qt.MouseButton.LeftButton)
    assert dialog.sign_in_button.isVisible()
    qtbot.mouseClick(dialog.sign_in_button, Qt.MouseButton.LeftButton)
    assert opened == ["https://openfpvs.com/account#connect-studio"]
    dialog.set_connection(_connection())
    assert not dialog.sign_in_button.isVisible()
    custom = LibraryDialog(openfpvs=False)
    qtbot.addWidget(custom)
    assert custom.sign_in_button.isHidden()
    assert custom.code_edit.placeholderText() == "Enrollment code"


@pytest.mark.parametrize("size", [(900, 640), (1040, 760)])
@pytest.mark.parametrize("state", [
    "disconnected", "connect", "ready", "busy", "error", "authorization_error", "empty",
    "installed", "update", "review", "view_only",
])
def test_library_layout_and_full_metadata(qtbot, tmp_path, size, state) -> None:
    dialog = LibraryDialog()
    qtbot.addWidget(dialog)
    item = _item(title="Long experiment name " * 7, description="Protocol description. " * 150)
    if state not in {"disconnected", "connect"}:
        dialog.set_connection(_connection(
            library_name="Research experiment library " * 4,
            device_name="Research computer name " * 4,
            lab_name="Research laboratory name " * 4,
        ) if state == "view_only" else _connection())
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
            LibraryCatalog(
                schema_version="1.0", library_name="Research", items=[item],
                access_level="view" if state == "view_only" else "download",
                lab_name="Research laboratory name " * 4 if state == "view_only" else None,
            )
        )
    if state == "busy":
        dialog.set_busy(True, "Downloading and verifying the experiment…", downloading=True)
        dialog.show_progress(512, 1024)
    elif state == "error":
        dialog.set_busy(
            False,
            "This computer's access was revoked. Disconnect and reconnect with a new access code.",
        )
    elif state == "authorization_error":
        dialog.set_connection(None)
        dialog.set_busy(
            False, "Library access was rejected. Reconnect through OpenFPVS.",
        )
    elif state == "empty":
        dialog.set_catalog(LibraryCatalog(schema_version="1.0", library_name="Research", items=[]))
    elif state == "connect":
        dialog.connect_toggle.click()
    dialog.resize(*size)
    dialog.show()
    QApplication.processEvents()
    assert (dialog.width(), dialog.height()) == size
    assert_visible_children_within_parent(dialog, allow_scroll_content=True)
    assert not dialog.header.subtitle_label.isVisible()
    for button in dialog.findChildren(QPushButton):
        if button.isVisible():
            assert all(
                button.width() >= button.fontMetrics().horizontalAdvance(line)
                for line in button.text().splitlines()
            )
    for label in dialog.findChildren(QLabel):
        if label.isVisible() and label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width())
    if state in ("ready", "busy", "error"):
        assert item.title in dialog.details.toPlainText()
        assert _project_buttons(dialog)[0].toolTip() == item.title
        assert "Download size" in dialog.details.toPlainText()
        assert "Minimum Studio version\n1.0.0" in dialog.details.toPlainText()
        assert "Conditions" in dialog.details.toPlainText()
        assert "Project files" not in dialog.details.toPlainText()
        assert item.description not in dialog.details.toPlainText()
        assert "Compatible with this Studio version" not in dialog.details.toPlainText()
        assert "This experiment is not installed" not in dialog.details.toPlainText()
        assert "Review display, timing and triggers" not in dialog.details.toPlainText()
        assert "Creates a separate project" in dialog.install_button.toolTip()
        assert dialog.install_button.accessibleDescription() == dialog.install_button.toolTip()
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
    elif state == "view_only":
        assert not dialog.install_button.isEnabled()
        assert dialog.install_button.text() == "View-only access"
        assert "not permitted" in dialog.install_button.toolTip()
        assert "View-only" in dialog.connection_label.text()
        assert "Research laboratory name " * 4 in dialog.connection_label.text()
        assert "View-only" not in dialog.details.toPlainText()
        assert dialog.refresh_button.isEnabled()
        assert dialog.search_edit.isEnabled()
    elif state == "disconnected":
        assert "projects shared by your lab" in dialog.connection_label.text()
        assert dialog.connect_toggle.isVisible()
        assert not dialog.connection_fields.isVisible()
    elif state == "connect":
        assert dialog.connection_fields.isVisible()
        assert "one-time computer code from your OpenFPVS account" in dialog.code_edit.toolTip()
        assert dialog.code_edit.accessibleDescription() == dialog.code_edit.toolTip()
    if state in {"installed", "update", "review"}:
        installed = dialog.selected_installation()
        assert installed is not None
        assert str(installed.project.root) not in dialog.details.toPlainText()
        row = _project_buttons(dialog)[0]
        assert row.accessibleDescription() == {
            "installed": "Installed", "update": "Installed · update available",
            "review": "Possible local copy",
        }[state]


def test_catalog_permission_overrides_saved_access_and_refreshes_actions(qtbot) -> None:
    dialog = LibraryDialog()
    qtbot.addWidget(dialog)
    dialog.set_connection(_connection(access_level="download", lab_name="Previous lab"))
    dialog.set_installations((), "https://library.example.test")
    dialog.set_catalog(LibraryCatalog(
        schema_version="1.0", library_name="Shared library", items=[_item()],
        access_level="view", lab_name="Current lab",
    ))
    assert not dialog.install_button.isEnabled()
    assert not dialog.can_download
    assert "Current lab" in dialog.connection_label.text()
    assert "Previous lab" not in dialog.connection_label.text()
    dialog.set_catalog(LibraryCatalog(
        schema_version="1.0", library_name="Shared library", items=[_item()],
        access_level="download", lab_name="Current lab",
    ))
    assert dialog.install_button.isEnabled()
    assert dialog.can_download
    assert "Download access" in dialog.connection_label.text()
    assert "View-only" not in dialog.details.toPlainText()
    assert "Creates a separate project" in dialog.install_button.toolTip()


def test_library_install_action_waits_for_installation_check(qtbot) -> None:
    dialog = LibraryDialog()
    qtbot.addWidget(dialog)
    dialog.set_connection(_connection())
    dialog.set_catalog(LibraryCatalog(
        schema_version="1.0", library_name="Research", items=[_item()],
    ))
    assert dialog.install_button.text() == "Checking installation…"
    assert not dialog.install_button.isEnabled()
    dialog.set_installations((), "https://library.example.test")
    assert dialog.install_button.text() == "Download and set up experiment"
    assert "This experiment is not installed" not in dialog.details.toPlainText()
    assert dialog.install_button.isEnabled()


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
    assert "Minimum Studio version\n999.0.0" in dialog.details.toPlainText()
    assert dialog.install_button.text() == "Studio update required"
    assert "Requires FPVS Studio 999.0.0" in dialog.install_button.toolTip()
    assert not dialog.install_button.isEnabled()
    dialog.search_edit.setText("nothing matches")
    assert dialog.selected_item() is None
    assert "No matching" in dialog.details.toPlainText()


def test_library_summary_reveal_respects_reduce_motion(qtbot, qapp, monkeypatch):
    monkeypatch.setattr("fpvs_studio.gui.components._system_motion_enabled", lambda: True)
    previous = qapp.property("studioReduceMotion")
    dialog = LibraryDialog()
    qtbot.addWidget(dialog)
    dialog.set_public_catalog(LibraryCatalog(
        schema_version="1.0", library_name="Public projects", items=[_demo(), _item()],
    ))
    dialog.show()
    first, second = _project_buttons(dialog)
    try:
        qapp.setProperty("studioReduceMotion", False)
        second.click()
        assert dialog._reveal_animation.state() == QAbstractAnimation.State.Running
        dialog._reveal_animation.setCurrentTime(dialog._reveal_animation.duration())
        assert dialog.details.graphicsEffect() is None
        qapp.setProperty("studioReduceMotion", True)
        first.click()
        assert dialog._reveal_animation.state() == QAbstractAnimation.State.Stopped
        assert dialog.details.graphicsEffect() is None
    finally:
        qapp.setProperty("studioReduceMotion", previous)


def test_library_list_distinguishes_releases_with_the_same_title(qtbot):
    dialog = LibraryDialog()
    qtbot.addWidget(dialog)
    dialog.set_public_catalog(LibraryCatalog(
        schema_version="1.0", library_name="Public projects",
        items=[
            _item(title="Masking", version="2.0"), _item(title="Masking", version="1.0"), _demo(),
        ],
    ))
    assert [row.accessibleName() for row in _project_buttons(dialog)] == [
        "Masking · 2.0", "Masking · 1.0", "Color Oddball Demo",
    ]


@pytest.mark.parametrize("size", [(900, 640), (1040, 760)])
@pytest.mark.parametrize("dark", [False, True])
def test_public_demo_and_view_only_lab_share_one_browser(qtbot, monkeypatch, size, dark):
    monkeypatch.setattr(library_ui, "widget_animation_duration", lambda *_args: 0)
    dialog = LibraryDialog()
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#202124" if dark else "#f4f7fb"))
    dialog.setPalette(palette)
    dialog.set_installations((), MANAGED_LIBRARY_SERVICE_URL)
    dialog.set_public_catalog(LibraryCatalog(
        schema_version="1.0", library_name="Public projects", items=[_demo()],
    ))
    dialog.resize(*size)
    dialog.show()
    QApplication.processEvents()
    assert (dialog.width(), dialog.height()) == size
    assert_visible_children_within_parent(dialog, allow_scroll_content=True)
    assert dialog.selected_scope() == "public"
    assert dialog.install_button.isEnabled()
    assert dialog.status_label.text() == "No account required"
    dialog.set_condition_count(_demo(), "public", 2)
    assert "Conditions\n2" in dialog.details.toPlainText()
    assert "1.2 Hz" not in dialog.details.toPlainText()
    dialog.set_catalog_state("lab", loading=True)
    assert dialog.selected_scope() == "public"
    assert not dialog.install_button.isEnabled()
    assert "current Library check" in dialog.install_button.toolTip()
    dialog.set_catalog_state("lab")
    assert dialog.install_button.isEnabled()
    dialog.search_edit.setFocus()
    qtbot.keyClick(dialog.search_edit, Qt.Key.Key_Tab)
    assert _project_buttons(dialog)[0].hasFocus()
    qtbot.keyClick(_project_buttons(dialog)[0], Qt.Key.Key_Tab)
    assert dialog.connect_toggle.hasFocus()
    qtbot.keyClick(dialog.connect_toggle, Qt.Key.Key_Space)
    assert dialog.connection_fields.isVisible()
    assert dialog.connection_fields.graphicsEffect() is None
    assert dialog.install_button.isEnabled()
    dialog.set_connection(_connection(access_level="view", lab_name="Vision Lab"))
    dialog.set_catalog(LibraryCatalog(
        schema_version="1.0", library_name="Research", access_level="view",
        items=[_item(), _item(item_id="reading", title="Reading Priming")],
    ))
    QApplication.processEvents()
    assert_visible_children_within_parent(dialog, allow_scroll_content=True)
    assert len(_project_buttons(dialog)) == 3
    assert dialog.install_button.isEnabled()
    dialog.search_edit.setText("reading")
    assert dialog.selected_scope() == "lab"
    assert dialog.install_button.text() == "View-only access"
    assert "Conditions\nNot listed" in dialog.details.toPlainText()
    assert not dialog.install_button.isEnabled()
    assert "No matching public projects" in dialog.public_status.text()
    dialog.search_edit.clear()
    dialog.set_connection(None)
    assert dialog.selected_scope() == "public"
    assert dialog.install_button.isEnabled()


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
        self.access_level = "download"
        self.download_denied = False
        self.public_error = False
        self.download_scopes = []

    def connection_info(self):
        return self.connection

    def enroll(self, code, device_name, *, cancel_event=None):
        assert code == "test-access"
        self.connection = _connection(access_level=self.access_level, lab_name="Shared lab")
        return self.connection

    def catalog(self, *, cancel_event=None):
        if self.authorization_error:
            raise LibraryAuthorizationError(
                "Access revoked. Disconnect this computer and reconnect."
            )
        return LibraryCatalog(
            schema_version="1.0", library_name="Research", items=[_item()],
            access_level=self.access_level, lab_name="Shared lab",
        )

    def public_catalog(self, *, cancel_event=None):
        if self.public_error:
            raise LibraryError("Public catalog unavailable.")
        return LibraryCatalog(schema_version="1.0", library_name="Public projects", items=[_demo()])

    def condition_count(self, item, *, scope, cancel_event=None):
        return 2 if scope == "public" else 3

    def download(self, item, *, scope="lab", cancel_event=None, progress_callback=None):
        self.download_started.set()
        self.download_scopes.append(scope)
        if self.download_denied:
            raise LibraryError(
                "Your lab has view-only Library access. Downloads are not permitted."
            )
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


def _controller(qapp, qtbot, monkeypatch, tmp_path, import_bundle, *, client=None):
    lifecycle = UpdateLifecycle(qapp, quit_callback=lambda: None)
    monkeypatch.setattr(library_module, "update_lifecycle", lambda app: lifecycle)
    monkeypatch.setattr(
        library_module, "read_project_bundle_manifest",
        lambda path: SimpleNamespace(project=SimpleNamespace(project_id="example")),
    )
    client = client or _Client(tmp_path / "example.fpvsbundle")
    controller = LibraryController(
        qapp, import_bundle=import_bundle, client=client, studio_root=lambda: tmp_path,
        review_project=lambda root: None,
    )
    controller.show()
    qtbot.addWidget(controller.dialog)
    qtbot.waitUntil(lambda: not controller._catalog_jobs and controller._job is None)
    return controller, client, lifecycle


def _enroll(controller, qtbot) -> None:
    controller.dialog.code_edit.setText("test-access")
    controller.dialog.connect_button.click()
    qtbot.waitUntil(lambda: not controller._catalog_jobs and controller._job is None)
    assert controller.dialog.selected_item() is not None


def test_public_catalog_requires_no_connection_and_preserves_scope_on_import(
    qapp, qtbot, monkeypatch, tmp_path,
) -> None:
    client = _Client(tmp_path / "demo.fpvsbundle")
    client.service_url = MANAGED_LIBRARY_SERVICE_URL
    handoffs = []
    controller, _client, _lifecycle = _controller(
        qapp, qtbot, monkeypatch, tmp_path, lambda *args: handoffs.append(args), client=client,
    )
    assert client.connection is None
    assert controller.dialog.install_button.isEnabled()
    controller.dialog.install_button.click()
    qtbot.waitUntil(lambda: len(handoffs) == 1)
    assert client.download_scopes == ["public"]
    _path, _manifest, origin, finished = handoffs[0]
    assert origin.scope == "public"
    assert origin.item_id == "color-oddball-demo"
    finished(None)
    assert client.releases == 1


def test_condition_summary_reads_selected_proof_without_download(
    qapp, qtbot, monkeypatch, tmp_path,
):
    client = _Client(tmp_path / "demo.fpvsbundle")
    client.service_url = MANAGED_LIBRARY_SERVICE_URL
    client.connection = _connection()
    controller, _client, _lifecycle = _controller(
        qapp, qtbot, monkeypatch, tmp_path, lambda *_args: pytest.fail("Unexpected import"),
        client=client,
    )
    dialog = controller.dialog
    assert dialog.selected_scope() == "public"
    qtbot.waitUntil(lambda: "Conditions\n2" in dialog.details.toPlainText())
    dialog.search_edit.setText(_item().title)
    assert dialog.selected_scope() == "lab"
    qtbot.waitUntil(lambda: "Conditions\n3" in dialog.details.toPlainText())
    assert not client.download_started.is_set()


def test_catalog_failures_do_not_clear_other_scope(qapp, qtbot, monkeypatch, tmp_path) -> None:
    client = _Client(tmp_path / "demo.fpvsbundle")
    client.service_url = MANAGED_LIBRARY_SERVICE_URL
    client.connection = _connection()
    client.public_error = True
    controller, _client, _lifecycle = _controller(
        qapp, qtbot, monkeypatch, tmp_path, lambda *_args: None, client=client,
    )
    dialog = controller.dialog
    assert dialog.selected_scope() == "lab"
    assert dialog.install_button.isEnabled()
    assert dialog.public_retry.isVisible()
    client.public_error = False
    dialog.public_retry.click()
    qtbot.waitUntil(lambda: not controller._catalog_jobs)
    assert dialog.selected_scope() == "public"
    client.authorization_error = True
    dialog.refresh_button.click()
    qtbot.waitUntil(lambda: not controller._catalog_jobs)
    assert "revoked" in dialog.lab_status.text()
    assert dialog.selected_scope() == "public"
    assert dialog.install_button.isEnabled()


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
    assert not _project_buttons(controller.dialog)
    assert "remain available offline" in controller.dialog.lab_status.text()


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
    qtbot.waitUntil(lambda: not controller._catalog_jobs)
    assert not _project_buttons(controller.dialog)
    assert not controller.dialog.install_button.isEnabled()
    assert "revoked" in controller.dialog.lab_status.text()
    assert controller.dialog.connection_fields.isVisible()
    assert controller.dialog.connect_button.isVisible()
    assert not controller.dialog.disconnect_button.isVisible()
    client.authorization_error = False
    _enroll(controller, qtbot)
    assert len(_project_buttons(controller.dialog)) == 1
    assert controller.dialog.install_button.isEnabled()


def test_view_only_catalog_blocks_programmatic_install(qapp, qtbot, monkeypatch, tmp_path) -> None:
    controller, client, _lifecycle = _controller(
        qapp, qtbot, monkeypatch, tmp_path, lambda *_args: pytest.fail("Unexpected import"),
    )
    client.access_level = "view"
    _enroll(controller, qtbot)
    assert "View-only" in controller.dialog.connection_label.text()
    assert controller.dialog.status_label.text() == ""
    assert not controller.dialog.install_button.isEnabled()
    assert controller.dialog.refresh_button.isEnabled()
    controller._action("install")
    assert not client.download_started.is_set()
    assert controller._job is None
    assert client.connection is not None


def test_download_permission_denial_keeps_library_connected(qapp, qtbot, monkeypatch, tmp_path):
    controller, client, _lifecycle = _controller(
        qapp, qtbot, monkeypatch, tmp_path, lambda *_args: pytest.fail("Unexpected import"),
    )
    _enroll(controller, qtbot)
    client.download_denied = True
    controller.dialog.install_button.click()
    qtbot.waitUntil(lambda: controller._job is None)
    assert "view-only" in controller.dialog.status_label.text()
    assert len(_project_buttons(controller.dialog)) == 1
    assert not controller.dialog.connection_fields.isVisible()
    assert controller.dialog.disconnect_button.isVisible()
    assert client.connection is not None
    client.access_level = "view"
    controller.dialog.refresh_button.click()
    qtbot.waitUntil(lambda: not controller._catalog_jobs)
    assert not controller.dialog.install_button.isEnabled()
    assert len(_project_buttons(controller.dialog)) == 1


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
        prepare_project_handoff=lambda: save,
        is_launch_busy=lambda: True,
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
    started, cancel_seen, finish_cancel = Event(), Event(), Event()

    def canceled_import(*args, cancel_event, **kwargs):
        started.set()
        assert cancel_event.wait(5), "Import never received cancellation"
        cancel_seen.set()
        assert finish_cancel.wait(5), "Test never released canceled import"
        raise ProjectBundleCancelled("Canceled")

    monkeypatch.setattr(controller_module, "import_project_bundle", canceled_import)
    results = []
    controller.import_project_bundle_file(tmp_path / "test.fpvsbundle", on_finished=results.append)
    try:
        qtbot.waitUntil(started.is_set)
        progress = controller._import_bundle_processing_dialog
        assert progress is not None
        progress.reject()
        qtbot.waitUntil(cancel_seen.is_set)
        assert progress.isVisible()
        assert progress.page.title_label.text() == "Canceling import…"
        assert not progress.cancel_button.isEnabled()
        assert results == []
    finally:
        finish_cancel.set()
    qtbot.waitUntil(lambda: results == [None])
    assert controller._library_import_job is None
    assert controller._import_bundle_processing_dialog is None

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


def test_library_import_error_delays_handoff_release_until_dismissed(
    controller, qtbot, tmp_path, monkeypatch,
) -> None:
    from fpvs_studio.gui import controller as controller_module

    manifest = SimpleNamespace(project=SimpleNamespace(name="Library example"))
    monkeypatch.setattr(
        controller,
        "_show_project_bundle_import_review",
        lambda *_args, **_kwargs: (int(QDialog.DialogCode.Accepted), manifest),
    )
    monkeypatch.setattr(
        controller_module,
        "_show_error",
        lambda *_args, **_kwargs: pytest.fail("Import failure should appear on the progress page"),
    )
    release = Event()

    def invalid_import(*args, progress_callback, **kwargs):
        progress_callback("oddball")
        assert release.wait(5), "Test never released invalid import"
        raise ProjectBundleError("Project bundle checksum mismatch: stimuli/oddball/example.png")

    monkeypatch.setattr(controller_module, "import_project_bundle", invalid_import)
    results = []
    controller.import_project_bundle_file(
        tmp_path / "invalid.fpvsbundle", on_finished=results.append,
    )
    progress = controller._import_bundle_processing_dialog
    assert progress is not None
    oddball = progress.page.findChild(QWidget, "bundle_import_processing_step_3")
    assert oddball is not None
    try:
        qtbot.waitUntil(lambda: oddball.property("processingStepState") == "active")
    finally:
        release.set()
    qtbot.waitUntil(lambda: oddball.property("processingStepState") == "failed")
    assert results == []
    assert progress.isVisible()
    assert "damaged" in progress.page.outcome_label.text().lower()
    assert progress.cancel_button.text() == "Close"
    assert progress.cancel_button.isEnabled()
    progress.cancel_button.click()
    assert not progress.isVisible()
    qtbot.waitUntil(lambda: results == [None])
    assert controller._library_import_job is None


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
    select_settings_category(dialog, "Workspace")
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
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    dialog.set_stage("oddball")
    assert canceled == [True]
    assert dialog.isVisible()
    assert dialog.page.title_label.text() == "Canceling import…"
    assert not dialog.cancel_button.isEnabled()
    verify = dialog.findChild(QWidget, "bundle_import_processing_step_1")
    assert verify is not None and verify.property("processingStepState") == "stopped"
    dialog.finish()


def test_bundle_review_error_is_actionable_and_releases_download(
    qapp, qtbot, monkeypatch, tmp_path,
):
    controller, client, _lifecycle = _controller(
        qapp, qtbot, monkeypatch, tmp_path,
        lambda *_args: pytest.fail("Invalid bundle must not import"),
    )
    _enroll(controller, qtbot)
    message = "Project bundle checksum mismatch: project.json"

    def invalid(path):
        raise ProjectBundleError(message)

    monkeypatch.setattr(library_module, "read_project_bundle_manifest", invalid)
    controller.dialog.install_button.click()
    qtbot.waitUntil(lambda: client.releases == 1 and controller._job is None)
    assert "damaged" in controller.dialog.status_label.text()
    assert "Download a fresh copy" in controller.dialog.status_label.text()
    assert "checksum mismatch" not in controller.dialog.status_label.text()
    assert not controller._importing
    assert controller.dialog.install_button.isEnabled()
