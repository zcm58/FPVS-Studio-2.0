"""Deterministic GUI coordination checks; no real network, filesystem I/O or runtime."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget
from tests.unit.test_library_installations import project as installed_project

from fpvs_studio.core.library_origin import LibraryOriginError, LibraryProjectOrigin
from fpvs_studio.gui import project_update_controller as module
from fpvs_studio.gui.update_lifecycle import UpdateTaskResult
from fpvs_studio.library.errors import LibraryCancelled
from fpvs_studio.library.models import LibraryCatalog, LibraryConnection, LibraryItem


class _Job(QObject):
    finished = Signal(object)
    progress_changed = Signal(object, object)

    def __init__(self, callback, parent):
        super().__init__(parent)
        self.callback = callback
        self.cancel_event = Event()
        self.result = None

    def cancel(self):
        self.cancel_event.set()

    def run_callback(self):
        try:
            value = self.callback(self.progress_changed.emit, self.cancel_event)
            self.result = UpdateTaskResult(value=value)
        except Exception as error:
            self.result = UpdateTaskResult(error=error)

    def finish(self):
        assert self.result is not None
        self.finished.emit(self.result)


class _Lifecycle(QObject):
    shutdown_started = Signal()

    def __init__(self, app):
        super().__init__(app)
        self.is_shutting_down = False
        self.jobs = []
        self.pending = []

    def start_task(self, callback, **_kwargs):
        assert not self.is_shutting_down
        job = _Job(callback, self)
        self.jobs.append(job)
        self.pending.append(job)
        job.finished.connect(lambda _result: self.pending.remove(job))
        return job

    def drain(self):
        for _ in range(10):
            if not self.pending:
                QApplication.processEvents()
                return
            job = self.pending[0]
            job.run_callback()
            job.finish()
        pytest.fail("Project update operations did not settle")

    def request_shutdown(self):
        self.is_shutting_down = True
        self.shutdown_started.emit()
        for job in self.pending:
            job.cancel()


class _Window(QWidget):
    def __init__(self, project_root: Path):
        super().__init__()
        self.document = SimpleNamespace(
            project_root=project_root,
            project=SimpleNamespace(
                meta=SimpleNamespace(project_id="local-study", name="Local study")
            ),
        )
        self.notices = []
        self.launch_busy = False

    def set_project_update_notice(self, message):
        self.notices.append(message)

    def is_launch_busy(self):
        return self.launch_busy


def _item():
    return LibraryItem(
        item_id="masking", version="1.0.1", title="Masking",
        description="New matching circle geometry and distinct condition markers.",
        experiment_category="fpvs_oddball", filename="masking-1.0.1.fpvsbundle",
        size_bytes=1024, uncompressed_size_bytes=4096, file_count=3,
        sha256="a" * 64, min_studio_version="1.0.0",
    )


def _origin(**updates):
    return LibraryProjectOrigin(
        service_url="https://library.example.test", item_id="masking",
        installed_version="1.0.0", bundle_sha256="b" * 64, local_project_id="local-study",
        **updates,
    )


class _Client:
    service_url = "https://library.example.test"

    def __init__(self, path):
        self.path = path
        self.catalog_calls = 0
        self.download_calls = []
        self.releases = 0

    def connection_info(self):
        return LibraryConnection(device_id="device-1", library_name="Lab", device_name="Desktop")

    def catalog(self, *, cancel_event=None):
        self.catalog_calls += 1
        if cancel_event is not None and cancel_event.is_set():
            raise LibraryCancelled("Canceled")
        return LibraryCatalog(schema_version="1.0", library_name="Lab", items=[_item()])

    def download(self, item, *, cancel_event=None, progress_callback=None):
        self.download_calls.append(item)
        if cancel_event is not None and cancel_event.is_set():
            raise LibraryCancelled("Canceled")
        if progress_callback is not None:
            progress_callback(item.size_bytes, item.size_bytes)
        return self.path

    def release_download(self):
        self.releases += 1


@pytest.fixture
def updates(qapp, qtbot, monkeypatch, tmp_path):
    window = _Window(tmp_path)
    qtbot.addWidget(window)
    window.show()
    current = [window]
    lifecycle = _Lifecycle(qapp)
    monkeypatch.setattr(module, "update_lifecycle", lambda _app: lifecycle)
    io_calls = []
    origins = {tmp_path: _origin()}

    def load_origin(root):
        io_calls.append(("load", root))
        return origins.get(root)

    def save_origin(root, origin):
        io_calls.append(("save", root, origin))
        origins[root] = origin

    monkeypatch.setattr(module, "load_library_origin", load_origin)
    monkeypatch.setattr(module, "save_library_origin", save_origin)
    monkeypatch.setattr(
        module, "read_project_bundle_manifest",
        lambda _path: SimpleNamespace(project=SimpleNamespace(project_id="masking")),
    )
    handoffs = []
    client = _Client(tmp_path / "masking-1.0.1.fpvsbundle")
    controller = module.ProjectUpdateController(
        qapp, current_window=lambda: current[0],
        import_bundle=lambda *args: handoffs.append(args), client=client,
        studio_root=lambda: tmp_path,
    )
    yield SimpleNamespace(
        controller=controller, window=window, current=current, lifecycle=lifecycle,
        client=client, handoffs=handoffs, io_calls=io_calls, origins=origins, root=tmp_path,
    )
    lifecycle.request_shutdown()
    lifecycle.drain()
    if controller.dialog is not None:
        qtbot.addWidget(controller.dialog)
        controller.dialog.close()
    controller.deleteLater()
    lifecycle.deleteLater()


def test_open_check_is_deferred_coalesced_and_never_installs(updates):
    state = updates
    state.controller.opened(state.window)
    state.controller.opened(state.window)
    assert len(state.lifecycle.pending) == 1
    assert state.io_calls == []
    assert state.client.catalog_calls == 0
    assert state.controller.dialog is None

    state.lifecycle.drain()
    assert state.client.catalog_calls == 1
    assert all(call[0] == "load" for call in state.io_calls)
    assert any("1.0.1" in notice for notice in state.window.notices)
    assert state.client.download_calls == []
    assert state.handoffs == []
    assert state.controller.dialog is None


def test_latest_version_already_installed_elsewhere_disables_update(updates):
    state = updates
    installed_project(state.root, project_id="masking-from-bundle", version="1.0.1")
    state.controller.show(state.window)
    state.lifecycle.drain()
    assert not state.controller._result.can_install
    assert "already installed" in state.controller._result.message
    state.controller._action("install")
    state.lifecycle.drain()
    assert state.client.download_calls == []
    assert state.handoffs == []

def test_closed_project_ignores_completed_background_result(updates):
    state = updates
    state.controller.opened(state.window)
    job = state.lifecycle.pending[0]
    job.run_callback()
    state.current[0] = None
    state.window.close()
    job.finish()
    state.lifecycle.drain()
    assert not any(state.window.notices)
    assert state.controller.dialog is None
    assert state.handoffs == []


def test_replaced_project_receives_only_its_own_completed_check(updates, qtbot):
    state = updates
    state.controller.opened(state.window)
    previous = state.lifecycle.pending[0]
    previous.run_callback()
    replacement = _Window(state.root / "replacement")
    qtbot.addWidget(replacement)
    replacement.show()
    state.origins[replacement.document.project_root] = _origin()
    state.current[0] = replacement
    state.controller.opened(replacement)
    assert previous.cancel_event.is_set()
    assert len(state.lifecycle.pending) == 1
    previous.finish()
    state.lifecycle.drain()
    assert not any(state.window.notices)
    assert any("1.0.1" in notice for notice in replacement.notices)
    assert state.handoffs == []


def test_manual_review_is_blocked_during_presentation(updates):
    state = updates
    state.window.launch_busy = True
    state.controller.show(state.window)
    assert state.controller.dialog is None
    assert state.lifecycle.pending == []
    assert state.client.download_calls == []


def test_install_requires_explicit_action_and_retains_download_until_import_finishes(updates):
    state = updates
    state.controller.opened(state.window)
    state.lifecycle.drain()
    state.controller.show(state.window)
    state.lifecycle.drain()
    dialog = state.controller.dialog
    assert dialog is not None and not dialog.isModal()
    assert dialog.install_button.isEnabled()
    assert state.client.download_calls == []
    assert state.handoffs == []

    dialog.install_button.click()
    assert state.client.download_calls == []
    state.lifecycle.drain()
    assert len(state.handoffs) == 1
    path, manifest, origin, finished = state.handoffs[0]
    assert path == state.client.path
    assert manifest.project.project_id == "masking"
    assert origin.installed_version == "1.0.1"
    assert origin.bundle_sha256 == _item().sha256
    assert state.client.releases == 0
    assert state.origins[state.root].installed_version == "1.0.0"
    assert state.window.document.project.meta.project_id == "local-study"
    finished(None)
    assert state.client.releases == 1


@pytest.mark.parametrize("action", ["cancel", "close", "shutdown"])
def test_late_download_cancellation_releases_lease_without_import(updates, action):
    state = updates
    state.controller.show(state.window)
    state.lifecycle.drain()
    state.controller.dialog.install_button.click()
    job = state.lifecycle.pending[0]
    job.run_callback()  # Download wins the race, but the worker has not finished yet.
    assert state.client.releases == 0
    if action == "shutdown":
        state.lifecycle.request_shutdown()
    elif action == "close":
        state.controller.dialog.close()
    else:
        state.controller.dialog.cancel_button.click()
    assert job.cancel_event.is_set()
    job.finish()
    state.lifecycle.drain()
    assert state.handoffs == []
    assert state.client.releases == 1


def test_download_finishing_during_presentation_does_not_start_modal_import(updates):
    state = updates
    state.controller.show(state.window)
    state.lifecycle.drain()
    state.controller.dialog.install_button.click()
    job = state.lifecycle.pending[0]
    job.run_callback()
    state.window.launch_busy = True
    job.finish()
    state.lifecycle.drain()
    assert state.handoffs == []
    assert state.client.releases == 1


def test_manifest_failure_releases_download_and_shows_error(updates, monkeypatch):
    state = updates

    def fail_manifest(_path):
        raise ValueError("Invalid project manifest")

    monkeypatch.setattr(module, "read_project_bundle_manifest", fail_manifest)
    state.controller.show(state.window)
    state.lifecycle.drain()
    state.controller.dialog.install_button.click()
    state.lifecycle.drain()
    assert state.handoffs == []
    assert state.client.releases == 1
    assert "Invalid project manifest" in state.controller.dialog.status_label.text()


def test_automatic_preference_is_persisted_only_by_worker(updates):
    state = updates
    state.controller.show(state.window)
    state.lifecycle.drain()
    dialog = state.controller.dialog
    assert dialog.auto_check_checkbox.isChecked()
    state.io_calls.clear()
    dialog.auto_check_checkbox.click()
    assert not dialog.auto_check_checkbox.isChecked()
    assert state.io_calls == []
    assert state.origins[state.root].auto_check
    state.lifecycle.drain()
    assert not state.origins[state.root].auto_check
    assert [call[0] for call in state.io_calls] == ["save", "load"]


def test_unlinked_open_stays_quiet_and_manual_review_loads_link_choices(updates):
    state = updates
    state.origins.clear()
    state.controller.opened(state.window)
    state.lifecycle.drain()
    assert state.client.catalog_calls == 0
    assert state.controller.dialog is None
    assert not any(state.window.notices)
    state.controller.show(state.window)
    state.lifecycle.drain()
    dialog = state.controller.dialog
    assert dialog.link_combo.count() == 2
    assert not dialog.install_button.isEnabled()
    assert state.client.catalog_calls == 1
    assert not any(call[0] == "save" for call in state.io_calls)
    assert state.client.download_calls == []


@pytest.mark.parametrize("receipt_state", ["mismatched", "corrupt"])
def test_invalid_receipt_is_quiet_on_open_and_requires_explicit_link_repair(
    updates, monkeypatch, receipt_state,
):
    state = updates
    corrupt = object()
    state.origins[state.root] = (
        _origin().model_copy(update={"local_project_id": "different-project"})
        if receipt_state == "mismatched" else corrupt
    )
    original = state.origins[state.root]

    def load_origin(root):
        state.io_calls.append(("load", root))
        origin = state.origins.get(root)
        if origin is corrupt:
            raise LibraryOriginError("The Library receipt is corrupt.")
        return origin

    monkeypatch.setattr(module, "load_library_origin", load_origin)
    state.controller.opened(state.window)
    state.lifecycle.drain()
    assert state.client.catalog_calls == 0
    assert state.controller.dialog is None
    assert not any(state.window.notices)
    assert all(call[0] == "load" for call in state.io_calls)
    assert state.origins[state.root] is original

    state.controller.show(state.window)
    state.lifecycle.drain()
    dialog = state.controller.dialog
    assert "Link this project explicitly to repair" in dialog.status_label.text()
    assert dialog.link_panel.isVisible()
    assert dialog.link_combo.count() == 2
    assert not dialog.install_button.isEnabled()
    assert state.client.catalog_calls == 1
    assert state.origins[state.root] is original
    assert all(call[0] == "load" for call in state.io_calls)

    dialog.link_combo.setCurrentIndex(1)
    dialog.installed_version_edit.clear()  # An unknown version must remain unknown.
    dialog.link_button.click()
    assert state.origins[state.root] is original
    state.lifecycle.drain()
    repaired = state.origins[state.root]
    assert repaired.local_project_id == state.window.document.project.meta.project_id
    assert repaired.item_id == "masking"
    assert repaired.installed_version is None
    assert repaired.bundle_sha256 is None
    assert [call[0] for call in state.io_calls].count("save") == 1
    assert state.client.download_calls == []
    assert state.handoffs == []


def test_failed_manual_recheck_invalidates_previously_available_install(updates, monkeypatch):
    state = updates
    state.controller.show(state.window)
    state.lifecycle.drain()
    dialog = state.controller.dialog
    assert dialog.install_button.isEnabled()

    def unreadable_origin(_root):
        raise OSError("Project receipt could not be read")

    monkeypatch.setattr(module, "load_library_origin", unreadable_origin)
    dialog.check_button.click()
    assert not dialog.install_button.isEnabled()
    state.lifecycle.drain()
    assert "Project receipt could not be read" in dialog.status_label.text()
    assert not dialog.install_button.isEnabled()
    jobs_before_install = len(state.lifecycle.jobs)
    state.controller._action("install")
    assert len(state.lifecycle.jobs) == jobs_before_install
    assert state.client.download_calls == []
    assert state.handoffs == []


def test_canceled_manual_recheck_requires_fresh_check_before_install(updates):
    state = updates
    state.controller.show(state.window)
    state.lifecycle.drain()
    dialog = state.controller.dialog
    assert dialog.install_button.isEnabled()
    dialog.check_button.click()
    assert not dialog.install_button.isEnabled()
    dialog.cancel_button.click()
    state.lifecycle.drain()
    assert "canceled" in dialog.status_label.text().lower()
    assert not dialog.install_button.isEnabled()
    jobs_before_install = len(state.lifecycle.jobs)
    state.controller._action("install")
    assert len(state.lifecycle.jobs) == jobs_before_install
    assert state.client.download_calls == []
    assert state.handoffs == []


def test_shutdown_cancels_check_and_prevents_new_operations(updates):
    state = updates
    state.controller.opened(state.window)
    job = state.lifecycle.pending[0]
    state.lifecycle.request_shutdown()
    assert job.cancel_event.is_set()
    state.lifecycle.drain()
    count = len(state.lifecycle.jobs)
    state.controller.opened(state.window)
    state.controller.show(state.window)
    assert len(state.lifecycle.jobs) == count
    assert state.controller.dialog is None
    assert not any(state.window.notices)
    assert state.handoffs == []
