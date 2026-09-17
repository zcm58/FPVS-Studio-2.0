"""Registered developer-publisher UI coverage; all external operations are fakes."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
from tests.gui.helpers import assert_visible_children_within_parent, open_created_project

from fpvs_studio.core.library_publish import LibraryBundlePreparation
from fpvs_studio.developer.library_publisher import (
    PreparedPublication,
    PublicationResult,
    PublisherAccess,
    PublisherCancelled,
    PublisherConfig,
    PublisherError,
)
from fpvs_studio.gui import controller as studio_module
from fpvs_studio.gui import library_publisher_controller as publisher_module
from fpvs_studio.gui.components import apply_dialog_theme
from fpvs_studio.gui.library_publisher_controller import (
    LibraryPublisherController,
    publication_review,
)
from fpvs_studio.gui.library_publisher_dialog import LibraryPublisherDialog
from fpvs_studio.gui.update_lifecycle import UpdateLifecycle


def _fill(dialog: LibraryPublisherDialog) -> None:
    dialog.set_context(title="Example experiment", item_id="example-experiment")
    dialog.summary_edit.setPlainText("A complete experimental task for reuse.")


def _prepared(path: Path, request) -> PreparedPublication:
    report = LibraryBundlePreparation(
        project_id="example-experiment",
        title=request.title,
        category="fpvs_oddball",
        minimum_studio_version=request.minimum_studio_version,
        bundle_schema_version="1.0",
        project_schema_version="1.0",
        condition_count=3,
        stimulus_set_count=6,
        task_count=2,
        file_count=12,
        size_bytes=2048,
        sha256="a" * 64,
        included_paths=("project.json", "stimuli/manifest.json", "stimuli/base/a.png"),
        excluded_paths=("logs/participant.csv",),
        sanitized_fields=("manual_removed_electrodes",),
        dry_run=False,
    )
    return PreparedPublication(
        request=request,
        directory=path,
        bundle_path=path / "example.fpvsbundle",
        metadata_path=path / "example.json",
        report=report,
    )


@pytest.mark.parametrize("size", [(860, 680), (940, 760)])
@pytest.mark.parametrize(
    "state", ["editing", "checking", "prepared", "failed", "published", "retained"]
)
@pytest.mark.parametrize("dark", [False, True])
def test_publisher_layout_and_plain_review(qtbot, tmp_path, size, state, dark) -> None:
    dialog = LibraryPublisherDialog()
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#202124" if dark else "#ffffff"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f1f3f4" if dark else "#202124"))
    dialog.setPalette(palette)
    apply_dialog_theme(dialog)
    _fill(dialog)
    dialog.title_edit.setText("Long research experiment title " * 5)
    dialog.set_access(True, "GitHub: zcm58 · zcm58/FPVS-Studio-Library")
    if state in {"prepared", "failed", "published", "retained"}:
        prepared = _prepared(tmp_path, dialog.request())
        dialog.set_prepared(True, publication_review(prepared))
    if state == "checking":
        dialog.set_busy(True, "Checking GitHub access and repository permissions…")
    elif state == "failed":
        dialog.set_busy(
            False, "Remote state may have changed. Retained files are available for retry."
        )
    elif state == "published":
        dialog.set_published()
        dialog.status_label.setText(
            "Published to zcm58/FPVS-Studio-Library · " + "long-release-title-" * 4
            + "v1.0.0. Catalog commit: " + "b" * 40
        )
    elif state == "retained":
        dialog.status_label.setText(
            "A prior publish was not confirmed; remote state may have changed. "
            f'Retained bundle: "{dialog.title_edit.text()}" (version 1.0.0). '
            "Publish uses these reviewed files; the source folder is listed in the review. "
            "Edit starts a new copy of the currently open experiment, "
            f'"{dialog.title_edit.text()}".'
        )
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
    if state in {"prepared", "failed", "published", "retained"}:
        text = dialog.review_edit.toPlainText()
        assert "logs/participant.csv" in text
        assert "manual_removed_electrodes" in text
        assert "SHA-256: " + "a" * 64 in text
        assert not dialog.form.isEnabled()


class _Service:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.calls = []
        self.access_denied = False
        self.publish_error = False
        self.prepare_error = False
        self.block = ""
        self.started = Event()
        self.release = Event()
        self.late_success = False
        self.gui_thread = QThread.currentThread()
        self.worker_threads = []

    def _check_thread(self):
        self.worker_threads.append(QThread.currentThread() != self.gui_thread)

    def _wait(self, operation, cancel_event):
        if self.block != operation:
            return
        self.started.set()
        while not self.release.wait(0.01):
            if cancel_event.is_set() and not self.late_success:
                raise PublisherCancelled("Stopped; remote state may have changed.")
        if cancel_event.is_set() and not self.late_success:
            raise PublisherCancelled("Stopped; remote state may have changed.")

    def check_access(self, *, cancel_event):
        self._check_thread()
        if self.access_denied:
            raise PublisherError("GitHub owner or write access is not authorized.")
        return PublisherAccess(login="zcm58", repository="zcm58/FPVS-Studio-Library")

    def prepare(self, project_root, request, *, cancel_event):
        self._check_thread()
        self.calls.append(("prepare", project_root, request))
        self._wait("prepare", cancel_event)
        if self.prepare_error:
            raise PublisherError("The current experiment contains missing images.")
        return _prepared(self.path, request)

    def publish(self, prepared, *, cancel_event):
        self._check_thread()
        self.calls.append(("publish", prepared))
        self._wait("publish", cancel_event)
        if self.publish_error:
            raise PublisherError("Connection lost while publishing.")
        return PublicationResult(
            repository="zcm58/FPVS-Studio-Library",
            tag="example-v1.0.0",
            catalog_commit="b" * 40,
        )

    def discard(self, prepared):
        self._check_thread()
        self.calls.append(("discard", prepared))


def _controller(qapp, qtbot, monkeypatch, tmp_path, *, save=True, denied=False):
    lifecycle = UpdateLifecycle(qapp, quit_callback=lambda: None)
    monkeypatch.setattr(publisher_module, "update_lifecycle", lambda app: lifecycle)
    service = _Service(tmp_path / "prepared")
    service.access_denied = denied
    saved = []
    controller = LibraryPublisherController(qapp, service=service)
    controller.show(
        project_root=tmp_path / "project",
        title="Example",
        item_id="example",
        save_project=lambda: saved.append(True) or save,
    )
    qtbot.addWidget(controller.dialog)
    qtbot.waitUntil(lambda: controller._job is None)
    _fill(controller.dialog)
    return controller, service, saved, lifecycle


def _prepare(controller, qtbot):
    controller.dialog.prepare_button.click()
    qtbot.waitUntil(lambda: controller._prepared is not None and controller._job is None)


def test_prepare_review_publish_and_exact_retry(qapp, qtbot, monkeypatch, tmp_path) -> None:
    controller, service, saved, _lifecycle = _controller(qapp, qtbot, monkeypatch, tmp_path)
    controller._action("publish")
    assert service.calls == []
    _prepare(controller, qtbot)
    assert saved == [True]
    prepared = controller._prepared
    assert not any(call[0] == "publish" for call in service.calls)
    service.publish_error = True
    controller.dialog.publish_button.click()
    qtbot.waitUntil(lambda: controller._job is None)
    assert "Remote state may have changed" in controller.dialog.status_label.text()
    assert controller._prepared is prepared
    service.publish_error = False
    controller.dialog.publish_button.click()
    qtbot.waitUntil(lambda: controller._job is None)
    published = [call[1] for call in service.calls if call[0] == "publish"]
    assert published == [prepared, prepared]
    assert published[0] is published[1]
    assert "Published to" in controller.dialog.status_label.text()
    assert not controller.dialog.publish_button.isEnabled()
    assert all(service.worker_threads)


@pytest.mark.parametrize("failure", ["access", "save", "metadata"])
def test_publisher_blocks_unreviewed_or_invalid_preparation(
    qapp,
    qtbot,
    monkeypatch,
    tmp_path,
    failure,
) -> None:
    controller, service, saved, _lifecycle = _controller(
        qapp,
        qtbot,
        monkeypatch,
        tmp_path,
        save=failure != "save",
        denied=failure == "access",
    )
    if failure == "metadata":
        controller.dialog.item_id_edit.setText("invalid ID / path")
    controller.dialog.prepare_button.click()
    assert service.calls == []
    assert saved == ([True] if failure == "save" else [])
    assert (
        not controller.dialog.publish_button.isEnabled()
        or not controller.dialog.publish_button.isVisible()
    )


@pytest.mark.parametrize("operation", ["prepare", "publish"])
@pytest.mark.parametrize("action", ["escape", "close", "cancel", "shutdown"])
def test_publisher_cancellation_drains_and_preserves_retry(
    qapp,
    qtbot,
    monkeypatch,
    tmp_path,
    operation,
    action,
) -> None:
    controller, service, _saved, lifecycle = _controller(qapp, qtbot, monkeypatch, tmp_path)
    if operation == "publish":
        _prepare(controller, qtbot)
    prepared = controller._prepared
    service.block = operation
    controller._action(operation)
    try:
        qtbot.waitUntil(service.started.is_set)
        if action == "escape":
            qtbot.keyClick(controller.dialog, Qt.Key.Key_Escape)
        elif action == "close":
            controller.dialog.close()
        elif action == "cancel":
            controller.dialog.cancel_button.click()
        else:
            lifecycle.request_shutdown()
    finally:
        service.release.set()
    qtbot.waitUntil(lambda: controller._job is None)
    assert not lifecycle.has_active_jobs
    if operation == "publish":
        assert controller._prepared is prepared
        assert "Remote state may have changed" in controller.dialog.status_label.text()
    else:
        assert not any(call[0] == "publish" for call in service.calls)


def test_publisher_late_success_is_confirmed(qapp, qtbot, monkeypatch, tmp_path) -> None:
    controller, service, _saved, _lifecycle = _controller(qapp, qtbot, monkeypatch, tmp_path)
    _prepare(controller, qtbot)
    service.block, service.late_success = "publish", True
    controller.dialog.publish_button.click()
    try:
        qtbot.waitUntil(service.started.is_set)
        controller.dialog.cancel_button.click()
    finally:
        service.release.set()
    qtbot.waitUntil(lambda: controller._job is None)
    assert "Published to" in controller.dialog.status_label.text()
    assert not controller.dialog.publish_button.isEnabled()


def test_edit_discards_on_worker_before_preparing_new_copy(
    qapp, qtbot, monkeypatch, tmp_path
) -> None:
    controller, service, saved, _lifecycle = _controller(qapp, qtbot, monkeypatch, tmp_path)
    _prepare(controller, qtbot)
    first = controller._prepared
    controller.dialog.edit_button.click()
    qtbot.waitUntil(lambda: controller._job is None)
    assert service.calls[-1] == ("discard", first)
    assert controller.dialog.form.isEnabled()
    _prepare(controller, qtbot)
    assert controller._prepared is not first
    assert saved == [True, True]
    assert all(service.worker_threads)


@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Space])
def test_focused_publisher_actions_accept_keyboard(qapp, qtbot, monkeypatch, tmp_path, key) -> None:
    controller, service, _saved, _lifecycle = _controller(qapp, qtbot, monkeypatch, tmp_path)
    controller.dialog.prepare_button.setFocus()
    qtbot.keyClick(controller.dialog.prepare_button, key)
    qtbot.waitUntil(lambda: controller._prepared is not None and controller._job is None)
    assert not any(call[0] == "publish" for call in service.calls)
    controller.dialog.publish_button.setFocus()
    qtbot.keyClick(controller.dialog.publish_button, key)
    qtbot.waitUntil(lambda: controller._result is not None and controller._job is None)
    assert len([call for call in service.calls if call[0] == "publish"]) == 1


@pytest.mark.parametrize("confirmed", [False, True])
def test_reopen_preserves_review_source_and_confirmed_result(
    qapp,
    qtbot,
    monkeypatch,
    tmp_path,
    confirmed,
) -> None:
    controller, service, _saved, _lifecycle = _controller(qapp, qtbot, monkeypatch, tmp_path)
    _prepare(controller, qtbot)
    first = controller._prepared
    if confirmed:
        controller.dialog.publish_button.click()
        qtbot.waitUntil(lambda: controller._job is None)
    controller.dialog.close()
    controller.show(
        project_root=tmp_path / "different-project",
        title="Different experiment",
        item_id="different-experiment",
        save_project=lambda: True,
    )
    qtbot.waitUntil(lambda: controller._job is None)
    assert controller._prepared is first
    assert (
        f"Source experiment: {tmp_path / 'project'}" in controller.dialog.review_edit.toPlainText()
    )
    if confirmed:
        assert "Published to" in controller.dialog.status_label.text()
        assert not controller.dialog.publish_button.isEnabled()
    else:
        assert 'Retained bundle: "Example experiment"' in controller.dialog.status_label.text()
        assert '"Different experiment"' in controller.dialog.status_label.text()
        controller.dialog.publish_button.click()
        qtbot.waitUntil(lambda: controller._job is None)
        assert service.calls[-1] == ("publish", first)


def test_edit_after_uncertain_publish_retains_original_and_requires_new_version(
    qapp,
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    controller, service, saved, _lifecycle = _controller(qapp, qtbot, monkeypatch, tmp_path)
    _prepare(controller, qtbot)
    first = controller._prepared
    service.publish_error = True
    controller.dialog.publish_button.click()
    qtbot.waitUntil(lambda: controller._job is None)
    controller.dialog.edit_button.click()
    assert controller._prepared is None
    assert not any(call[0] == "discard" for call in service.calls)
    assert str(first.bundle_path) in controller.dialog.review_edit.toPlainText()
    assert controller.dialog.version_edit.text() == ""
    controller.dialog.item_id_edit.setText(first.request.item_id)
    controller.dialog.version_edit.setText(first.request.version)
    controller.dialog.prepare_button.click()
    assert "Choose a new version" in controller.dialog.status_label.text()
    assert saved == [True]
    controller.dialog.version_edit.setText("1.0.1")
    _prepare(controller, qtbot)
    assert controller._prepared.request.version == "1.0.1"
    assert not any(call[0] == "discard" for call in service.calls)


@pytest.mark.parametrize("frozen,configured", [(True, True), (False, False)])
def test_normal_publisher_gate_does_not_call_developer_code(
    monkeypatch, frozen, configured
) -> None:
    from fpvs_studio.developer import library_publisher as backend

    monkeypatch.setattr(studio_module.sys, "frozen", frozen, raising=False)
    monkeypatch.setenv("FPVS_LIBRARY_PUBLISHER_REPO", "configured" if configured else "")
    monkeypatch.setattr(
        backend,
        "get_publisher_config",
        lambda: pytest.fail("Normal/frozen application must not load developer publishing"),
    )
    assert studio_module._library_publisher_config() is None


@pytest.mark.parametrize("enabled", [False, True])
def test_publisher_export_menu_is_source_only_and_saves_at_prepare(
    controller,
    qtbot,
    tmp_path,
    monkeypatch,
    enabled,
) -> None:
    config = PublisherConfig(tmp_path) if enabled else None
    monkeypatch.setattr(studio_module, "_library_publisher_config", lambda: config)
    document, window = open_created_project(controller, qtbot, tmp_path)
    action = window.publish_library_action
    if not enabled:
        assert action is None
        assert all(
            "Publish to Experiment Library" not in item.text()
            for item in window.export_menu.actions()
        )
        return
    assert action in window.export_menu.actions()
    assert action.text() == "Publish to Experiment Library..."
    shown, saved = [], []
    controller._library_publisher_controller = SimpleNamespace(
        show=lambda **kwargs: shown.append(kwargs)
    )
    monkeypatch.setattr(window, "save_project", lambda: saved.append(True) or True)
    action.trigger()
    assert shown[0]["project_root"] == document.project_root
    assert shown[0]["title"] == document.project.meta.name
    assert shown[0]["item_id"] == document.project.meta.project_id
    assert saved == []
    assert shown[0]["save_project"]()
    assert saved == [True]
    window._set_bundle_processing_busy(True)
    assert not action.isEnabled()
    window._set_bundle_processing_busy(False)
    assert action.isEnabled()
    controller.main_window = None
    assert not shown[0]["save_project"]()
    assert saved == [True]


@pytest.mark.parametrize("busy", ["launch", "accuracy", "export", "import"])
def test_publisher_export_action_respects_existing_guards(
    controller,
    qtbot,
    tmp_path,
    monkeypatch,
    busy,
) -> None:
    monkeypatch.setattr(
        studio_module, "_library_publisher_config", lambda: PublisherConfig(tmp_path)
    )
    _document, window = open_created_project(controller, qtbot, tmp_path)
    seen = []
    window._on_request_library_publish = lambda: seen.append(True)
    if busy == "launch":
        monkeypatch.setattr(window, "_allow_project_handoff_during_launch", lambda: False)
    elif busy == "accuracy":
        monkeypatch.setattr(window, "_allow_project_handoff_during_fixation_load", lambda: False)
    elif busy == "export":
        monkeypatch.setattr(window, "_active_bundle_export_task", object())
    else:
        monkeypatch.setattr(window, "_bundle_import_processing_active", True)
    window.publish_library_action.trigger()
    assert seen == []
    assert not controller._can_publish_from(window)


def test_publisher_changed_checkout_error_is_nonblocking(
    controller, qtbot, tmp_path, monkeypatch
) -> None:
    from fpvs_studio.developer import library_publisher as backend

    monkeypatch.setattr(
        studio_module, "_library_publisher_config", lambda: PublisherConfig(tmp_path)
    )
    _document, window = open_created_project(controller, qtbot, tmp_path)

    def removed_checkout(config):
        raise PublisherError("The configured checkout is no longer available.")

    monkeypatch.setattr(backend, "PublisherService", removed_checkout)
    window.publish_library_action.trigger()
    assert "no longer available" in window.statusBar().currentMessage()
    assert controller._library_publisher_controller is None


def test_prepare_failure_stays_editable_and_can_retry(qapp, qtbot, monkeypatch, tmp_path) -> None:
    controller, service, saved, _lifecycle = _controller(qapp, qtbot, monkeypatch, tmp_path)
    service.prepare_error = True
    controller.dialog.prepare_button.click()
    qtbot.waitUntil(lambda: controller._job is None)
    assert controller._prepared is None
    assert controller.dialog.form.isEnabled()
    assert "missing images" in controller.dialog.status_label.text()
    assert not controller.dialog.publish_button.isEnabled()
    service.prepare_error = False
    _prepare(controller, qtbot)
    assert saved == [True, True]
    assert not any(call[0] == "publish" for call in service.calls)


def test_invalid_optional_publisher_config_does_not_block_project(
    controller, qtbot, tmp_path, monkeypatch,
) -> None:
    def invalid_config():
        raise PublisherError("Invalid configured developer checkout.")

    monkeypatch.setattr(studio_module, "_library_publisher_config", invalid_config)
    _document, window = open_created_project(controller, qtbot, tmp_path)
    assert window.publish_library_action is None
    assert "Developer publishing is unavailable" in window.statusBar().currentMessage()
