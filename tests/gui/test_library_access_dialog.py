"""Optional startup enrollment; synthetic jobs only, without real credentials/network."""

from __future__ import annotations

from threading import Event
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.gui import library_access_dialog as module
from fpvs_studio.gui.update_lifecycle import UpdateTaskResult
from fpvs_studio.library import cache as cache_module
from fpvs_studio.library import client as client_module
from fpvs_studio.library.client import LibraryClient
from fpvs_studio.library.errors import LibraryError
from fpvs_studio.library.models import DeviceCredential, LibraryConnection


class _Job(QObject):
    finished = Signal(object)

    def __init__(self, callback, parent):
        super().__init__(parent)
        self.callback = callback
        self.cancel_event = Event()

    def cancel(self):
        self.cancel_event.set()

    def finish(self):
        try:
            result = UpdateTaskResult(value=self.callback(None, self.cancel_event))
        except Exception as error:
            result = UpdateTaskResult(error=error)
        self.finished.emit(result)


class _Lifecycle(QObject):
    shutdown_started = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.is_shutting_down = False
        self.jobs = []

    def start_task(self, callback, **_kwargs):
        job = _Job(callback, self)
        self.jobs.append(job)
        return job


def _connection(**updates):
    return LibraryConnection(
        device_id="test-device", device_name="Lab PC", library_name="Experiment Library",
        **updates,
    )


@pytest.fixture
def setup(qapp, monkeypatch):
    lifecycle = _Lifecycle(qapp)
    monkeypatch.setattr(module, "update_lifecycle", lambda _app: lifecycle)
    reads, enrollments = [], []

    def read():
        reads.append(True)
        return client.connection

    def enroll(code, name, **_kwargs):
        enrollments.append((code, name))
        client.connection = _connection(access_level="view", lab_name="NERD Lab")
        return client.connection

    client = SimpleNamespace(connection=None, connection_info=read, enroll=enroll)
    controller = module.LibraryAccessController(qapp, client=client)
    yield controller, lifecycle, client, reads, enrollments
    controller._dismiss()


def test_saved_enrollment_skips_prompt_without_network(setup):
    controller, lifecycle, client, reads, enrollments = setup
    client.connection = _connection()
    controller.check()
    lifecycle.jobs[-1].finish()
    controller.check()
    assert controller.dialog is None
    assert len(reads) == 1 and not enrollments


@pytest.mark.parametrize("connected", [True, False])
def test_previous_protocol_prompts_for_reconnection_with_offline_available(
    setup, qtbot, tmp_path, monkeypatch, connected,
):
    controller, lifecycle, _client, _reads, _enrollments = setup
    stored = [DeviceCredential(
        token="o" * 43, device_name="Previously connected PC",
        connection=_connection() if connected else None,
    )]
    store = SimpleNamespace(
        load=lambda: stored[0], delete=lambda: stored.__setitem__(0, None),
    )
    monkeypatch.setattr(cache_module, "_private_directory", lambda _path: None)
    monkeypatch.setattr(
        client_module, "build_opener", lambda *_args: pytest.fail("unexpected network"),
    )
    controller.client = LibraryClient(
        "https://library.example.test", credential_store=store, cache_root=tmp_path / "cache",
    )
    controller.check()
    lifecycle.jobs[-1].finish()
    dialog = controller.dialog
    qtbot.addWidget(dialog)
    assert dialog.isVisible()
    assert dialog.code_edit.isEnabled()
    assert dialog.offline_button.isEnabled()
    assert stored[0] is None
    qtbot.mouseClick(dialog.offline_button, Qt.MouseButton.LeftButton)
    assert not dialog.isVisible()


def test_unconfigured_startup_and_success_use_existing_enrollment(setup, qtbot):
    controller, lifecycle, _client, _reads, enrollments = setup
    controller.check()
    assert controller.dialog is None
    lifecycle.jobs[-1].finish()
    dialog = controller.dialog
    qtbot.addWidget(dialog)
    assert dialog.isVisible()
    dialog.code_edit.setText("synthetic-shared-lab-code")
    dialog.device_edit.setText("Lab PC 2")
    qtbot.mouseClick(dialog.connect_button, Qt.MouseButton.LeftButton)
    assert not dialog.connect_button.isEnabled()
    assert dialog.offline_button.isEnabled()
    lifecycle.jobs[-1].finish()
    assert enrollments == [("synthetic-shared-lab-code", "Lab PC 2")]
    assert "View only" in dialog.status_label.text()
    assert "NERD Lab" in dialog.status_label.text()
    assert not dialog.code_edit.text()
    qtbot.mouseClick(dialog.connect_button, Qt.MouseButton.LeftButton)
    assert not dialog.isVisible()


def test_continue_offline_cancels_late_enrollment_without_reopening(setup, qtbot):
    controller, lifecycle, client, _reads, _enrollments = setup
    controller.check()
    lifecycle.jobs[-1].finish()
    dialog = controller.dialog
    qtbot.addWidget(dialog)
    dialog.code_edit.setText("synthetic-shared-lab-code")
    qtbot.mouseClick(dialog.connect_button, Qt.MouseButton.LeftButton)
    job = lifecycle.jobs[-1]
    qtbot.mouseClick(dialog.offline_button, Qt.MouseButton.LeftButton)
    assert job.cancel_event.is_set()
    assert not dialog.code_edit.text()
    job.finish()
    assert not dialog.isVisible()
    assert client.connection is not None  # A completed enrollment remains saved.


def test_local_storage_error_is_visible_and_offline_remains_available(setup, qtbot):
    controller, lifecycle, client, _reads, _enrollments = setup

    def unavailable():
        raise LibraryError("Protected Library storage is unavailable.")

    client.connection_info = unavailable
    controller.check()
    lifecycle.jobs[-1].finish()
    qtbot.addWidget(controller.dialog)
    assert "Protected Library storage" in controller.dialog.status_label.text()
    assert controller.dialog.offline_button.isEnabled()


def test_client_construction_failure_keeps_startup_recoverable(qapp, qtbot, monkeypatch):
    lifecycle = _Lifecycle(qapp)
    monkeypatch.setattr(module, "update_lifecycle", lambda _app: lifecycle)
    attempts = []

    def unavailable():
        attempts.append(True)
        raise LibraryError("The Windows per-user Library cache location is unavailable.")

    monkeypatch.setattr(module, "LibraryClient", unavailable)
    controller = module.LibraryAccessController(qapp)
    assert attempts == []
    controller.check()
    lifecycle.jobs[-1].finish()
    dialog = controller.dialog
    qtbot.addWidget(dialog)
    assert attempts == [True]
    assert "cache location is unavailable" in dialog.status_label.text()
    assert dialog.offline_button.isEnabled()
    qtbot.mouseClick(dialog.offline_button, Qt.MouseButton.LeftButton)
    assert not dialog.isVisible()


def test_shutdown_does_not_open_a_late_startup_prompt(setup):
    controller, lifecycle, _client, _reads, _enrollments = setup
    controller.check()
    lifecycle.is_shutting_down = True
    lifecycle.shutdown_started.emit()
    lifecycle.jobs[-1].finish()
    assert controller.dialog is None


@pytest.mark.parametrize("busy", [False, True])
def test_shutdown_clears_typed_code_even_while_a_job_drains(setup, qtbot, busy):
    controller, lifecycle, _client, _reads, _enrollments = setup
    controller.check()
    lifecycle.jobs[-1].finish()
    dialog = controller.dialog
    qtbot.addWidget(dialog)
    dialog.code_edit.setText("synthetic-shared-lab-code")
    if busy:
        qtbot.mouseClick(dialog.connect_button, Qt.MouseButton.LeftButton)
    lifecycle.is_shutting_down = True
    lifecycle.shutdown_started.emit()
    assert not dialog.code_edit.text()
    assert not dialog.isVisible()
    if busy:
        assert lifecycle.jobs[-1].cancel_event.is_set()
        lifecycle.jobs[-1].finish()
        assert not dialog.isVisible()


@pytest.mark.parametrize("size", [(640, 420), (700, 460)])
@pytest.mark.parametrize("state", ["ready", "busy", "error", "connected"])
def test_startup_access_fits_all_states(qtbot, size, state):
    dialog = module.LibraryAccessDialog()
    qtbot.addWidget(dialog)
    dialog.resize(*size)
    dialog.device_edit.setText("Long laboratory workstation name " * 4)
    if state == "busy":
        dialog.set_busy(True, "Connecting this PC to your lab's Library…")
    elif state == "error":
        dialog.set_busy(False, "Could not reach the Experiment Library. "
                        "Check your connection and retry, or continue offline.")
    elif state == "connected":
        dialog.set_connected(_connection(access_level="view", lab_name="Long Lab Name " * 8))
    dialog.show()
    qtbot.wait(1)
    assert_visible_children_within_parent(dialog)
    for button in (dialog.offline_button, dialog.connect_button):
        if button.isVisible():
            assert button.width() >= button.fontMetrics().horizontalAdvance(button.text()) + 16
    assert dialog.status_label.height() >= dialog.status_label.heightForWidth(
        dialog.status_label.width(),
    )


@pytest.mark.parametrize("current_access", [False, True])
def test_managed_origin_move_prompts_once_without_reusing_old_access(
    setup, qtbot, tmp_path, monkeypatch, current_access,
):
    controller, lifecycle, _client, _reads, _enrollments = setup
    previous = DeviceCredential(
        token="o" * 43, device_name="Previously connected PC", library_api_version=2,
        connection=_connection(),
    )
    canonical_origin = "https://openfpvs.com"
    stored = {
        "https://fpvs-studio-library.fpvs-studio-zcm58.workers.dev": previous,
        "https://fpvs.zack-murphy.com": previous,
        canonical_origin: previous.model_copy(update={"token": "n" * 43})
        if current_access else None,
    }
    before = stored.copy()
    selected_origins = []

    def select_store(service_url):
        selected_origins.append(service_url)
        assert service_url == canonical_origin
        return SimpleNamespace(
            load=lambda: stored[service_url],
            save=lambda _value: pytest.fail("startup cannot transfer credentials"),
            delete=lambda: pytest.fail("startup cannot remove current protocol credentials"),
        )

    monkeypatch.setattr(cache_module, "_private_directory", lambda _path: None)
    monkeypatch.setattr(client_module, "credential_store", select_store)
    monkeypatch.setattr(
        client_module, "build_opener", lambda *_args: pytest.fail("unexpected startup network"),
    )
    controller.client = LibraryClient(cache_root=tmp_path / "cache")
    controller.check()
    lifecycle.jobs[-1].finish()
    assert selected_origins == [canonical_origin]
    assert stored == before
    if current_access:
        assert controller.dialog is None
    else:
        dialog = controller.dialog
        qtbot.addWidget(dialog)
        assert dialog.isVisible()
        assert dialog.code_edit.isEnabled()
        assert dialog.offline_button.isEnabled()
        qtbot.mouseClick(dialog.offline_button, Qt.MouseButton.LeftButton)
        assert not dialog.isVisible()
