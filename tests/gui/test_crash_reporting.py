"""Approved visible opt-out/settings tests; no real network, browser or credentials."""

from __future__ import annotations

import json
from threading import Event

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QLabel
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.gui import crash_report_controller as module
from fpvs_studio.gui.settings_dialog import AppSettingsDialog
from fpvs_studio.gui.update_lifecycle import UpdateTaskResult
from fpvs_studio.support.client import SERVICE_ORIGIN, ReportClient, ReportServiceError
from fpvs_studio.support.crash_reporting import CrashConsent, CrashSession, CrashStore


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
            value = self.callback(lambda *args: None, self.cancel_event)
            result = UpdateTaskResult(value=value)
        except Exception as error:
            result = UpdateTaskResult(error=error)
        self.finished.emit(result)


class FakeLifecycle(QObject):
    shutdown_started = Signal()
    is_shutting_down = False

    def __init__(self):
        super().__init__()
        self.jobs = []

    def start_task(self, callback, **kwargs):
        job = FakeJob(callback)
        self.jobs.append((job, kwargs))
        return job


@pytest.mark.parametrize("size", [(700, 560), (700, 650)])
@pytest.mark.parametrize("state", ["off", "registering", "enabled", "error"])
def test_settings_diagnostics_fit_and_bind(qtbot, tmp_path, size, state):
    changes = []
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path,
        on_automatic_crash_reports_changed=changes.append,
    )
    qtbot.addWidget(dialog)
    assert dialog.crash_reports_checkbox.isChecked()
    dialog.resize(*size)
    dialog.tabs.setCurrentIndex(dialog.tabs.count() - 1)
    messages = {
        "off": "Automatic reporting is off. Access revocation will be retried when connected.",
        "registering": "Automatic crash reporting is on by default. Connecting in the background…",
        "enabled": "On. Sanitized crash reports are sent at the next startup. "
        "You can turn this off here at any time.",
        "error": "Automatic reporting is enabled. Delivery is unavailable; reports remain "
        "on this computer and will be retried later.",
    }
    dialog.set_crash_reporting_state(state != "off", messages[state], state == "registering")
    dialog.show()
    qtbot.wait(25)
    assert_visible_children_within_parent(dialog)
    for label in dialog.tabs.currentWidget().findChildren(QLabel):
        assert label.height() >= label.heightForWidth(label.width())
    assert dialog.crash_reports_checkbox.isEnabled()  # Opt-out never waits for HTTP.
    dialog.crash_reports_checkbox.click()
    assert changes == [state == "off"]


def controller(tmp_path, monkeypatch, transport):
    lifecycle = FakeLifecycle()
    monkeypatch.setattr(module, "update_lifecycle", lambda app=None: lifecycle)
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: pytest.fail("browser opened"))
    value = module.CrashReportController(
        QApplication.instance(),
        root=tmp_path,
        client=ReportClient(SERVICE_ORIGIN, transport=transport),
    )
    return value, lifecycle


def registration(method, url, data, headers):
    assert url.endswith("/v1/crash-installations")
    body = json.loads(data)
    assert set(body) == {"schema_version", "installation_id"}
    return json.dumps({"installation_id": body["installation_id"], "state": "registered"}).encode()


def test_default_startup_registers_once_in_background_without_browser(tmp_path, monkeypatch):
    requests = []

    def transport(*args):
        requests.append(args)
        return registration(*args)

    value, lifecycle = controller(tmp_path, monkeypatch, transport)
    value.start()
    lifecycle.jobs[-1][0].complete()  # Local preference.
    assert value.enabled and value.busy
    assert requests == []
    lifecycle.jobs[-1][0].complete()  # Background registration, empty outbox.
    assert value.enabled and not value.busy
    assert CrashStore(tmp_path).consent().registered
    assert len(requests) == 1
    value.start()
    lifecycle.jobs[-1][0].complete()
    lifecycle.jobs[-1][0].complete()
    assert len(requests) == 1
    value.deleteLater()


def test_saved_opt_out_has_no_http_on_startup(tmp_path, monkeypatch):
    CrashStore(tmp_path).save_consent(CrashConsent(enabled=False))
    value, lifecycle = controller(
        tmp_path, monkeypatch, lambda *args: pytest.fail("HTTP after opt-out")
    )
    value.start()
    lifecycle.jobs[-1][0].complete()
    assert not value.enabled and not value.busy
    assert len(lifecycle.jobs) == 1
    assert not CrashStore(tmp_path).consent().enabled
    value.deleteLater()


def test_can_disable_offline_and_stay_off_after_restart(tmp_path, monkeypatch):
    def unavailable(*args):
        raise ReportServiceError("Synthetic unavailable service")

    value, lifecycle = controller(tmp_path, monkeypatch, unavailable)
    value.start()
    lifecycle.jobs[-1][0].complete()
    lifecycle.jobs[-1][0].complete()
    assert value.enabled and "unavailable" in value.status
    assert value.store().consent().enabled
    value.configure(False)
    lifecycle.jobs[-1][0].complete()  # Local opt-out precedes remote revocation.
    assert not value.store().consent().enabled
    lifecycle.jobs[-1][0].complete()  # Offline revocation keeps the local choice.
    assert not value.enabled and value.store().consent().revoke_pending
    value.deleteLater()
    restarted, restarted_lifecycle = controller(tmp_path, monkeypatch, unavailable)
    restarted.start()
    restarted_lifecycle.jobs[-1][0].complete()
    restarted_lifecycle.jobs[-1][0].complete()
    assert not restarted.enabled
    restarted.deleteLater()


def test_opt_out_during_registration_cancels_before_request(tmp_path, monkeypatch):
    calls = []

    def transport(method, url, data, headers):
        calls.append(url)
        assert url.endswith("/revoke")
        raise ReportServiceError("Unknown synthetic grant", status=401)

    value, lifecycle = controller(tmp_path, monkeypatch, transport)
    value.start()
    lifecycle.jobs[-1][0].complete()
    network_job = lifecycle.jobs[-1][0]
    value.configure(False)
    assert network_job.cancel_event.is_set()
    network_job.complete()
    lifecycle.jobs[-1][0].complete()
    lifecycle.jobs[-1][0].complete()
    assert not value.store().consent().enabled and not value.enabled
    assert not any(url.endswith("/crash-installations") for url in calls)
    value.deleteLater()


def test_lost_registration_response_keeps_default_on_and_retries_same_identity(
    tmp_path, monkeypatch
):
    calls = []

    def transport(*args):
        calls.append(args)
        if len(calls) == 1:
            raise ReportServiceError("Synthetic lost response")
        return registration(*args)

    value, lifecycle = controller(tmp_path, monkeypatch, transport)
    value.start()
    lifecycle.jobs[-1][0].complete()
    lifecycle.jobs[-1][0].complete()
    assert value.enabled and not value.store().consent().registered
    assert "unavailable" in value.status
    value._upload()
    lifecycle.jobs[-1][0].complete()
    assert calls[0] == calls[1]
    assert value.store().consent().registered and "On." in value.status
    value.deleteLater()


def test_reenable_revokes_old_access_before_registering_new_generation(tmp_path, monkeypatch):
    store = CrashStore(tmp_path)
    first = store.consent()
    store.disable()
    requests = []

    def transport(method, url, data, headers):
        requests.append(url)
        return (
            b'{"state":"revoked"}'
            if url.endswith("/revoke")
            else registration(method, url, data, headers)
        )

    value, lifecycle = controller(tmp_path, monkeypatch, transport)
    value.configure(True)
    lifecycle.jobs[-1][0].complete()
    lifecycle.jobs[-1][0].complete()
    assert requests[0].endswith("/revoke") and requests[1].endswith("/crash-installations")
    assert value.store().consent().installation_id != first.installation_id
    assert value.enabled and value.store().consent().registered
    value.deleteLater()


def test_shutdown_during_registration_preserves_preference(tmp_path, monkeypatch):
    value, lifecycle = controller(tmp_path, monkeypatch, lambda *args: pytest.fail("HTTP"))
    value.start()
    lifecycle.jobs[-1][0].complete()
    network_job = lifecycle.jobs[-1][0]
    lifecycle.is_shutting_down = True
    lifecycle.shutdown_started.emit()
    assert network_job.cancel_event.is_set()
    assert len(lifecycle.jobs) == 2
    assert value.store().consent().enabled
    value.deleteLater()


def test_shutdown_flushes_pending_opt_out_without_http(tmp_path, monkeypatch):
    value, lifecycle = controller(tmp_path, monkeypatch, lambda *args: pytest.fail("HTTP"))
    value.start()
    lifecycle.jobs[-1][0].complete()
    value.configure(False)
    lifecycle.is_shutting_down = True
    lifecycle.shutdown_started.emit()
    job, options = lifecycle.jobs[-1]
    assert options["finish_on_shutdown"]
    job.complete()
    assert not value.store().consent().enabled
    value.deleteLater()


def test_bad_local_preference_disables_delivery_without_http(tmp_path, monkeypatch):
    (CrashStore(tmp_path).folder() / "consent.json").write_text("invalid")
    value, lifecycle = controller(tmp_path, monkeypatch, lambda *args: pytest.fail("HTTP"))
    value.start()
    lifecycle.jobs[-1][0].complete()
    assert not value.enabled and "No further reports" in value.status
    assert len(lifecycle.jobs) == 1 and not value._retry.isActive()
    value.deleteLater()


def test_disabled_service_pauses_default_on_without_network(tmp_path, monkeypatch):
    value, lifecycle = controller(tmp_path, monkeypatch, lambda *args: pytest.fail("HTTP"))
    value.client = ReportClient()
    value.start()
    lifecycle.jobs[-1][0].complete()
    assert value.enabled and "paused" in value.status
    assert len(lifecycle.jobs) == 1
    value.deleteLater()


def test_expired_grant_is_registered_again_without_browser_or_losing_reports(tmp_path, monkeypatch):
    from uuid import uuid4

    monkeypatch.setattr("fpvs_studio.support.crash_reporting.process_alive", lambda pid: False)
    store = CrashStore(tmp_path)
    consent = store.consent()
    store.mark_registered(consent.installation_id, Event())
    store.save_session(
        CrashSession(
            session_id=uuid4(),
            pid=123456,
            os_version="test",
            installation_id=consent.installation_id,
        )
    )
    requests = []

    def transport(method, url, data, headers):
        requests.append(url)
        if url.endswith("/crash-reports"):
            raise ReportServiceError("Synthetic expired grant", status=401)
        return registration(method, url, data, headers)

    value, lifecycle = controller(tmp_path, monkeypatch, transport)
    value.start()
    lifecycle.jobs[-1][0].complete()
    lifecycle.jobs[-1][0].complete()
    assert value.enabled and not value.store().consent().registered
    assert len(value.store().pending()) == 1
    value._upload()
    lifecycle.jobs[-1][0].complete()
    assert requests == [
        SERVICE_ORIGIN + "/v1/crash-reports",
        SERVICE_ORIGIN + "/v1/crash-installations",
    ]
    assert value.store().consent().installation_id == consent.installation_id
    assert len(value.store().pending()) == 1 and "On." in value.status
    value.deleteLater()


def test_native_fatal_is_recovered_for_default_enabled_first_session(tmp_path):
    import subprocess
    import sys

    store = CrashStore(tmp_path)
    script = """
import sys
from pathlib import Path
from fpvs_studio.support.diagnostics import DiagnosticLogging
logging = DiagnosticLogging(Path(sys.argv[1]), capture_native=True)
logging.start()
assert logging.ready.wait(5)
from fpvs_studio.gui.qt_diagnostics import install_qt_diagnostics
from PySide6.QtCore import qFatal
install_qt_diagnostics()
qFatal("Synthetic fatal; private participant detail must not enter automatic reports")
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)], capture_output=True, timeout=15
    )
    assert result.returncode != 0
    events = store.recover()
    assert len(events) == 1 and events[0].report.crash_type == "native_fault"
    assert events[0].report.stack
    assert "private" not in events[0].model_dump_json()
    assert any(
        frame.module == "fpvs_studio/support/diagnostics.py" for frame in events[0].report.stack
    )


def test_real_worker_keeps_gui_responsive_and_retains_opt_out_after_settings_close(
    qapp,
    qtbot,
    tmp_path,
    monkeypatch,
):
    from PySide6.QtCore import QThread, QTimer

    from fpvs_studio.gui.update_lifecycle import UpdateLifecycle

    entered, release = Event(), Event()
    requests = []
    original_auto_quit = qapp.quitOnLastWindowClosed()
    qapp.setQuitOnLastWindowClosed(False)
    lifecycle = UpdateLifecycle(qapp, quit_callback=lambda: None)
    monkeypatch.setattr(qapp, "_fpvs_update_lifecycle", lifecycle, raising=False)

    def transport(method, url, data, headers):
        assert QThread.currentThread() != qapp.thread()
        requests.append(url)
        if url.endswith("/revoke"):
            return b'{"state":"revoked"}'
        entered.set()
        assert release.wait(5)
        return registration(method, url, data, headers)

    value = module.CrashReportController(
        qapp,
        root=tmp_path,
        client=ReportClient(SERVICE_ORIGIN, transport=transport),
    )
    dialog = AppSettingsDialog(
        fpvs_root_dir=tmp_path, on_automatic_crash_reports_changed=value.configure
    )
    qtbot.addWidget(dialog)
    dialog.tabs.setCurrentIndex(dialog.tabs.count() - 1)
    value.changed.connect(dialog.set_crash_reporting_state)
    dialog.show()
    try:
        value.start()
        qtbot.waitUntil(entered.is_set, timeout=5000)
        ticks = []
        QTimer.singleShot(0, lambda: ticks.append(True))
        qtbot.waitUntil(lambda: bool(ticks))
        assert value.busy and dialog.crash_reports_checkbox.isEnabled()
        dialog.crash_reports_checkbox.click()
        assert not value.enabled
        dialog.close()
        release.set()
        qtbot.waitUntil(lambda: not lifecycle.has_active_jobs, timeout=5000)
        assert not value.store().consent().enabled
        assert not value.store().consent().revoke_pending
        assert not any(url.endswith("/crash-reports") for url in requests)
    finally:
        release.set()
        lifecycle.request_shutdown()
        qtbot.waitUntil(lambda: not lifecycle.has_active_jobs, timeout=10000)
        qapp.removeEventFilter(lifecycle)
        qapp.lastWindowClosed.disconnect(lifecycle._last_window_closed)
        qapp.aboutToQuit.disconnect(lifecycle._about_to_quit)
        value.deleteLater()
        lifecycle.deleteLater()
        qapp.setQuitOnLastWindowClosed(original_auto_quit)
