"""GUI smoke tests for the in-app update flow."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from threading import Event

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt, QThread, QTimer
from PySide6.QtWidgets import QLabel, QMessageBox, QWidget
from shiboken6 import isValid
from tests.gui.helpers import assert_visible_children_within_parent, open_created_project

from fpvs_studio.gui import application as application_module
from fpvs_studio.gui import controller as controller_module
from fpvs_studio.gui import update_lifecycle as lifecycle_module
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.main_window import _TUTORIALS_URL
from fpvs_studio.gui.update_dialog import UpdateDialog
from fpvs_studio.gui.update_lifecycle import UpdateJob, UpdateLifecycle
from fpvs_studio.updates.models import (
    CacheCleanupResult,
    DownloadedInstaller,
    InstallerAsset,
    UpdateCancelled,
    UpdateCheckResult,
)


def _available_update(_cancel_event: Event | None = None) -> UpdateCheckResult:
    asset = InstallerAsset(
        name="FPVS-Studio-Setup-0.9.0b2.exe",
        download_url=(
            "https://github.com/zcm58/FPVS-Studio-2.0/releases/download/v0.9.0b2/"
            "FPVS-Studio-Setup-0.9.0b2.exe"
        ),
        size_bytes=10,
        sha256=hashlib.sha256(b"installer").hexdigest(),
        version="0.9.0b2",
        asset_id=10,
    )
    return UpdateCheckResult(
        current_version="0.9.0b1",
        latest_version="0.9.0b2",
        update_available=True,
        release_url="https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v0.9.0b2",
        release_notes_summary="Improved update flow",
        installer_asset=asset,
        is_prerelease=True,
    )


def test_main_window_file_menu_groups_actions(
    controller,
    qtbot,
    tmp_path: Path,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path)

    menu_entries = [
        "---" if action.isSeparator() else action.text()
        for action in window.file_menu.actions()
        if action.isVisible()
    ]

    assert menu_entries == [
        "Manage Projects...",
        "---",
        "Import",
        "Export",
        "---",
        "Settings...",
        "---",
        "Check for Updates",
        "About",
    ]
    assert [action.text() for action in window.import_menu.actions()] == [
        "Project Bundle...",
        "Project Config...",
    ]
    assert [action.text() for action in window.export_menu.actions()] == [
        "Project Bundle...",
        "FPVS Toolbox Config...",
        "Completed Project Config...",
        "Group Summary...",
    ]


def test_main_window_exposes_file_check_for_updates_action(
    controller,
    qtbot,
    tmp_path: Path,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path)

    actions = [action.text() for action in window.file_menu.actions()]

    assert window.check_updates_action.text() == "Check for Updates"
    assert "Check for Updates" in actions


def test_main_window_exposes_file_about_action(
    controller,
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path)
    messages: list[tuple[str, str]] = []

    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, message: messages.append((title, message)),
    )

    actions = [action.text() for action in window.file_menu.actions()]
    assert window.about_action.text() == "About"
    assert "About" in actions

    window.about_action.trigger()

    assert messages
    assert messages[0][0] == "About FPVS Studio"
    assert "FPVS Studio version" in messages[0][1]
    assert "Zack Murphy" in messages[0][1]
    assert "Neural Engineering Research Division, Mississippi State University" in messages[0][1]


def test_main_window_hides_file_tutorials_action_but_preserves_link(
    controller,
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _document, window = open_created_project(controller, qtbot, tmp_path)
    opened_urls: list[str] = []

    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QDesktopServices.openUrl",
        lambda url: opened_urls.append(url.toString()),
    )

    visible_actions = [
        action.text() for action in window.file_menu.actions() if action.isVisible()
    ]
    assert window.tutorials_action.text() == "Tutorials"
    assert window.tutorials_action in window.file_menu.actions()
    assert not window.tutorials_action.isVisible()
    assert "Tutorials" not in visible_actions

    window.tutorials_action.trigger()

    assert opened_urls == [_TUTORIALS_URL]


def test_startup_update_check_prompts_only_when_update_available(
    qapp,
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    controller = StudioController(qapp)
    fpvs_root_dir = tmp_path / "fpvs-root"
    fpvs_root_dir.mkdir(parents=True, exist_ok=True)
    controller.save_fpvs_root_dir(fpvs_root_dir)
    controller._startup_update_check_callback = _available_update
    dialogs: list[UpdateDialog] = []

    def _capture_exec(dialog: UpdateDialog) -> int:
        dialogs.append(dialog)
        return int(dialog.DialogCode.Accepted)

    monkeypatch.setattr("fpvs_studio.gui.controller.UpdateDialog.exec", _capture_exec)

    controller.show_welcome()
    assert controller.welcome_window is not None
    qtbot.addWidget(controller.welcome_window)

    qtbot.waitUntil(lambda: bool(dialogs), timeout=5000)

    dialog = dialogs[0]
    assert "A new FPVS Studio version is available." in dialog.status_label.text()
    assert "projects, templates, settings, run history, and logs" in dialog.status_label.text()
    assert dialog.download_button.isEnabled()
    assert dialog.close_button.text() == "Remind Me Later"


def test_update_dialog_initial_result_is_themed_and_remind_later_dismisses(qtbot) -> None:
    dialog = UpdateDialog(auto_check=False, initial_result=_available_update())
    qtbot.addWidget(dialog)
    dialog.show()

    qtbot.waitUntil(lambda: dialog.close_button.text() == "Remind Me Later")
    assert "QDialog#update_dialog" in dialog.styleSheet()
    assert "QPushButton" in dialog.styleSheet()

    dialog.close_button.click()

    qtbot.waitUntil(lambda: not dialog.isVisible())


def test_startup_update_prompt_remind_later_returns_to_welcome(
    qapp,
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    controller = StudioController(qapp)
    fpvs_root_dir = tmp_path / "fpvs-root"
    fpvs_root_dir.mkdir(parents=True, exist_ok=True)
    controller.save_fpvs_root_dir(fpvs_root_dir)
    controller._startup_update_check_callback = _available_update
    original_exec = UpdateDialog.exec
    dialog_versions: list[str] = []

    def _click_remind_later(dialog: UpdateDialog) -> int:
        dialog_versions.append(dialog.current_version_label.text())
        QTimer.singleShot(0, dialog.close_button.click)
        return original_exec(dialog)

    monkeypatch.setattr(UpdateDialog, "exec", _click_remind_later)

    controller.show_welcome()
    assert controller.welcome_window is not None
    qtbot.addWidget(controller.welcome_window)

    qtbot.waitUntil(lambda: bool(dialog_versions), timeout=5000)
    qtbot.waitUntil(lambda: controller._startup_update_job is None, timeout=5000)

    assert dialog_versions == ["Current version: 0.9.0b1"]
    assert controller.welcome_window.isVisible()


def test_update_dialog_action_buttons_fit_text_at_compact_width(qtbot) -> None:
    dialog = UpdateDialog(auto_check=False, initial_result=_available_update())
    qtbot.addWidget(dialog)
    dialog.resize(dialog.minimumSizeHint())
    dialog.show()
    qtbot.waitUntil(lambda: dialog.close_button.width() > 0)

    for button in (
        dialog.check_button,
        dialog.download_button,
        dialog.install_button,
        dialog.close_button,
    ):
        required_width = button.fontMetrics().horizontalAdvance(button.text()) + 20
        assert button.width() >= required_width, button.text()


def test_startup_update_check_is_silent_when_no_update_or_error(
    qapp,
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    exec_calls: list[str] = []

    monkeypatch.setattr(
        "fpvs_studio.gui.controller.UpdateDialog.exec",
        lambda _dialog: exec_calls.append("dialog"),
    )

    callbacks: list[Callable[[Event], UpdateCheckResult]] = []
    callback_calls: list[int] = []

    def _no_update(_cancel_event: Event) -> UpdateCheckResult:
        callback_calls.append(0)
        return UpdateCheckResult(
            current_version="0.9.1b4",
            latest_version="0.9.1b4",
            update_available=False,
            release_url=None,
            release_notes_summary="",
            installer_asset=None,
            is_prerelease=True,
        )

    def _update_error(_cancel_event: Event) -> UpdateCheckResult:
        callback_calls.append(1)
        raise RuntimeError("network unavailable")

    callbacks.extend((_no_update, _update_error))
    for index, callback in enumerate(callbacks):
        controller = StudioController(qapp)
        fpvs_root_dir = tmp_path / f"fpvs-root-{index}"
        fpvs_root_dir.mkdir(parents=True, exist_ok=True)
        controller.save_fpvs_root_dir(fpvs_root_dir)
        controller._startup_update_check_callback = callback

        controller.show_welcome()
        assert controller.welcome_window is not None
        qtbot.addWidget(controller.welcome_window)

        qtbot.waitUntil(
            lambda target=controller, expected_index=index: (
                expected_index in callback_calls
                and target._startup_update_check_started
                and target._startup_update_job is None
            ),
            timeout=5000,
        )

    assert exec_calls == []


def test_update_dialog_downloads_then_launches_installer(
    qtbot,
    monkeypatch,
    tmp_path: Path,
) -> None:
    installer_path = tmp_path / "FPVS-Studio-Setup-0.9.0b2.exe"
    installer_path.write_bytes(b"installer")
    launched: list[Path] = []
    quit_calls: list[str] = []
    worker_threads: list[QThread] = []
    gui_threads: list[QThread] = []

    def _download(asset, progress, cancel_event):
        worker_threads.append(QThread.currentThread())
        assert isinstance(cancel_event, Event)
        return _download_with_progress(installer_path, progress, asset)

    def _launch(downloaded, cancel_event):
        worker_threads.append(QThread.currentThread())
        assert isinstance(cancel_event, Event)
        launched.append(downloaded.path)

    def _save() -> bool:
        gui_threads.append(QThread.currentThread())
        return True

    dialog = UpdateDialog(
        auto_check=False,
        check_callback=_available_update,
        download_callback=_download,
        installer_launcher=_launch,
        on_before_install=_save,
        quit_app=lambda: quit_calls.append("quit"),
    )
    qtbot.addWidget(dialog)
    dialog.show()

    dialog.start_update_check()
    qtbot.waitUntil(lambda: dialog.download_button.isEnabled())
    assert "A new FPVS Studio version is available." in dialog.status_label.text()
    assert "projects, templates, settings, run history, and logs" in dialog.status_label.text()
    assert "0.9.0b1" in dialog.current_version_label.text()
    assert "0.9.0b2" in dialog.latest_version_label.text()
    assert "Improved update flow" in dialog.notes_label.text()
    assert dialog.release_notes_button.isEnabled()
    assert dialog.close_button.text() == "Remind Me Later"

    dialog.start_download()
    qtbot.waitUntil(lambda: dialog.install_button.isEnabled())
    assert dialog.progress_bar.value() == dialog.progress_bar.maximum() == 1000

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    dialog.install_and_restart()

    qtbot.waitUntil(lambda: quit_calls == ["quit"])
    assert launched == [installer_path]
    assert quit_calls == ["quit"]
    assert all(thread is not dialog.thread() for thread in worker_threads)
    assert gui_threads == [dialog.thread()]


def test_update_dialog_reports_no_update(qtbot) -> None:
    dialog = UpdateDialog(
        auto_check=False,
        check_callback=lambda _cancel: UpdateCheckResult(
            current_version="0.9.0b1",
            latest_version="0.9.0b1",
            update_available=False,
            release_url=None,
            release_notes_summary="",
            installer_asset=None,
            is_prerelease=True,
        ),
    )
    qtbot.addWidget(dialog)
    dialog.show()

    dialog.start_update_check()
    qtbot.waitUntil(lambda: dialog.status_label.text() == "FPVS Studio is up to date.")

    assert dialog.download_button.isEnabled() is False
    assert dialog.install_button.isEnabled() is False
    assert dialog.close_button.text() == "Close"


def test_update_dialog_reports_manual_server_error(qtbot) -> None:
    dialog = UpdateDialog(
        auto_check=False,
        check_callback=lambda _cancel: (_ for _ in ()).throw(RuntimeError("network unavailable")),
    )
    qtbot.addWidget(dialog)
    dialog.show()

    dialog.start_update_check()
    qtbot.waitUntil(
        lambda: "try again later from File > Check for Updates" in dialog.status_label.text()
    )

    assert "network unavailable" in dialog.notes_label.text()
    assert dialog.download_button.isEnabled() is False
    assert dialog.install_button.isEnabled() is False
    assert dialog.close_button.text() == "Close"


def _download_with_progress(
    installer_path: Path,
    progress: Callable[[int, int | None], None],
    asset: InstallerAsset,
) -> DownloadedInstaller:
    size = installer_path.stat().st_size
    progress(size // 2, size)
    progress(size, size)
    return DownloadedInstaller(
        path=installer_path,
        size_bytes=size,
        sha256=hashlib.sha256(installer_path.read_bytes()).hexdigest(),
        asset=asset,
    )


_UNSET = object()


class _DeferredUpdateJob(UpdateJob):
    """A deterministic worker double: callback return and thread finish are separate."""

    def start(self) -> None:
        self._started = True
        self._running = True

    def run_callback(self) -> None:
        assert self._started
        try:
            if self.cancel_event.is_set():
                raise UpdateCancelled("Canceled before starting.")
            self._outcome.value = self.callback(self.progress_changed.emit, self.cancel_event)
        except Exception as error:
            self._outcome.error = error

    def finish(self, value: object = _UNSET, error: Exception | None = None) -> None:
        assert self._started
        if value is not _UNSET:
            self._outcome.value = value
        if error is not None:
            self._outcome.error = error
        self._finish()


@pytest.fixture
def deferred_updates(qapp, qtbot, monkeypatch):
    jobs: list[_DeferredUpdateJob] = []
    quit_calls: list[str] = []
    original_auto_quit = qapp.quitOnLastWindowClosed()
    qapp.setQuitOnLastWindowClosed(False)

    def _create_job(*args, **kwargs):
        job = _DeferredUpdateJob(*args, **kwargs)
        jobs.append(job)
        return job

    monkeypatch.setattr(lifecycle_module, "UpdateJob", _create_job)
    lifecycle = UpdateLifecycle(qapp, quit_callback=lambda: quit_calls.append("quit"))
    monkeypatch.setattr(controller_module, "update_lifecycle", lambda _app: lifecycle)
    yield lifecycle, jobs, quit_calls

    qtbot.waitUntil(lambda: all(job._started for job in lifecycle._jobs))
    for job in tuple(lifecycle._jobs):
        job.cancel()
        job.finish(error=UpdateCancelled("Test teardown cancellation."))
    qtbot.waitUntil(lambda: not lifecycle.has_active_jobs)
    qapp.processEvents()
    qapp.removeEventFilter(lifecycle)
    qapp.lastWindowClosed.disconnect(lifecycle._last_window_closed)
    qapp.aboutToQuit.disconnect(lifecycle._about_to_quit)
    lifecycle.deleteLater()
    qapp.setQuitOnLastWindowClosed(original_auto_quit)


def _downloaded_fixture(tmp_path: Path) -> DownloadedInstaller:
    asset = _available_update().installer_asset
    assert asset is not None and asset.sha256 is not None
    return DownloadedInstaller(
        path=tmp_path / asset.name,
        size_bytes=9,
        sha256=asset.sha256,
        asset=asset,
    )


@pytest.mark.parametrize("metadata", ["missing-asset", "missing-digest", "invalid-digest"])
def test_new_release_without_trusted_installer_metadata_is_not_reported_as_current(
    qtbot, monkeypatch, metadata,
) -> None:
    result = _available_update()
    assert result.installer_asset is not None
    asset = None if metadata == "missing-asset" else replace(
        result.installer_asset,
        sha256=None if metadata == "missing-digest" else "not-a-valid-digest",
    )
    result = replace(result, installer_asset=asset)
    dialog = UpdateDialog(auto_check=False, initial_result=result)
    qtbot.addWidget(dialog)
    dialog.show()
    opened: list[str] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.update_dialog.QDesktopServices.openUrl",
        lambda url: opened.append(url.toString()),
    )

    assert "new FPVS Studio version is available" in dialog.status_label.text()
    assert "in-app installation is unavailable" in dialog.status_label.text()
    assert "valid trusted installer metadata" in dialog.status_label.text()
    assert "SHA-256 checksum" in dialog.status_label.text()
    assert "up to date" not in dialog.status_label.text()
    assert not dialog.download_button.isEnabled()
    assert not dialog.install_button.isEnabled()
    assert dialog.release_notes_button.isEnabled()
    dialog.release_notes_button.click()
    assert opened == [result.release_url]


@pytest.mark.parametrize("action", ["button", "window", "escape"])
@pytest.mark.parametrize("operation", ["check", "download", "install"])
def test_close_cancels_but_keeps_dialog_alive_until_worker_finishes(
    qtbot, monkeypatch, tmp_path, deferred_updates, action, operation,
) -> None:
    lifecycle, jobs, quit_calls = deferred_updates
    dialog = UpdateDialog(auto_check=False, initial_result=_available_update(), lifecycle=lifecycle)
    qtbot.addWidget(dialog)
    dialog.show()
    if operation == "check":
        dialog.start_update_check()
    elif operation == "download":
        dialog.start_download()
    else:
        dialog._handle_download_result(_downloaded_fixture(tmp_path))
        monkeypatch.setattr(
            QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes
        )
        dialog.install_and_restart()
    job = jobs[-1]
    qtbot.waitUntil(lambda: job.is_running)

    if action == "button":
        dialog.close_button.click()
    elif action == "window":
        dialog.close()
    else:
        qtbot.keyClick(dialog, Qt.Key.Key_Escape)

    assert job.cancel_event.is_set()
    assert dialog.isVisible()
    assert dialog.close_button.text() == "Canceling..."
    assert not dialog.close_button.isEnabled()
    assert not dialog.install_button.isEnabled()
    assert lifecycle.has_active_jobs
    assert quit_calls == []

    job.finish(error=UpdateCancelled("Canceled safely."))
    qtbot.waitUntil(lambda: not dialog.isVisible())
    assert not lifecycle.has_active_jobs
    assert dialog._job is None
    assert quit_calls == []


def test_download_result_does_not_enable_install_until_thread_finished(
    qtbot, monkeypatch, tmp_path, deferred_updates,
) -> None:
    lifecycle, jobs, _quit_calls = deferred_updates
    confirmations: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args: confirmations.append("confirm")
    )
    downloaded = _downloaded_fixture(tmp_path)
    dialog = UpdateDialog(
        auto_check=False,
        initial_result=_available_update(),
        lifecycle=lifecycle,
        download_callback=lambda _asset, _progress, _cancel: downloaded,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.start_download()
    job = jobs[-1]
    qtbot.waitUntil(lambda: job.is_running)
    job.run_callback()

    assert not dialog.install_button.isEnabled()
    assert dialog._downloaded_installer is None
    dialog.install_and_restart()
    dialog.start_download()
    assert confirmations == []
    assert len(jobs) == 1

    job.finish()
    assert dialog.install_button.isEnabled()
    assert dialog._downloaded_installer is downloaded
    assert dialog._job is None


def test_cancel_wins_over_a_download_result_not_yet_delivered(
    qtbot, tmp_path, deferred_updates,
) -> None:
    lifecycle, jobs, _quit_calls = deferred_updates
    dialog = UpdateDialog(
        auto_check=False,
        initial_result=_available_update(),
        lifecycle=lifecycle,
        download_callback=lambda _asset, _progress, _cancel: _downloaded_fixture(tmp_path),
    )
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.start_download()
    job = jobs[-1]
    qtbot.waitUntil(lambda: job.is_running)
    job.run_callback()
    dialog.reject()
    job.finish()

    assert not dialog.isVisible()
    assert dialog._downloaded_installer is None
    assert not dialog.install_button.isEnabled()


def test_launch_success_survives_late_cancel_and_quits_only_after_finish(
    qtbot, monkeypatch, tmp_path, deferred_updates,
) -> None:
    lifecycle, jobs, _quit_calls = deferred_updates
    events: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes
    )
    dialog = UpdateDialog(
        auto_check=False,
        initial_result=_available_update(),
        lifecycle=lifecycle,
        installer_launcher=lambda _downloaded, _cancel: events.append("launch"),
        on_before_install=lambda: events.append("save") or True,
        quit_app=lambda: events.append("quit"),
    )
    qtbot.addWidget(dialog)
    dialog.show()
    dialog._handle_download_result(_downloaded_fixture(tmp_path))
    dialog.install_and_restart()
    assert events == ["save"]
    job = jobs[-1]
    qtbot.waitUntil(lambda: job.is_running)
    job.run_callback()
    assert events == ["save", "launch"]
    dialog.close()
    assert job.cancel_event.is_set()
    assert events == ["save", "launch"]

    job.finish()
    qtbot.waitUntil(lambda: events == ["save", "launch", "quit"])
    assert not dialog.isVisible()
    assert not lifecycle.has_active_jobs


@pytest.mark.parametrize("operation", ["check", "download", "install"])
def test_parent_destruction_cancels_without_destroying_or_orphaning_worker(
    qtbot, monkeypatch, tmp_path, deferred_updates, operation,
) -> None:
    lifecycle, jobs, _quit_calls = deferred_updates
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()
    dialog = UpdateDialog(
        parent=parent, auto_check=False, initial_result=_available_update(), lifecycle=lifecycle
    )
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dialog.show()
    if operation == "check":
        dialog.start_update_check()
    elif operation == "download":
        dialog.start_download()
    else:
        dialog._handle_download_result(_downloaded_fixture(tmp_path))
        monkeypatch.setattr(
            QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes
        )
        dialog.install_and_restart()
    job = jobs[-1]
    qtbot.waitUntil(lambda: job.is_running)
    parent.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert not isValid(dialog)
    assert job.cancel_event.is_set()
    assert lifecycle.has_active_jobs
    job.finish(error=UpdateCancelled("Canceled after parent destruction."))
    assert not lifecycle.has_active_jobs


def test_committed_launch_still_quits_when_its_dialog_was_destroyed(
    qtbot, monkeypatch, tmp_path, deferred_updates,
) -> None:
    lifecycle, jobs, _quit_calls = deferred_updates
    events: list[str] = []
    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = UpdateDialog(
        parent=parent,
        auto_check=False,
        initial_result=_available_update(),
        lifecycle=lifecycle,
        installer_launcher=lambda _downloaded, _cancel: events.append("launch"),
        quit_app=lambda: events.append("quit"),
    )
    dialog._handle_download_result(_downloaded_fixture(tmp_path))
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes
    )
    dialog.install_and_restart()
    job = jobs[-1]
    qtbot.waitUntil(lambda: job.is_running)
    job.run_callback()
    parent.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not isValid(dialog)
    job.finish()
    qtbot.waitUntil(lambda: events == ["launch", "quit"])
    assert not lifecycle.has_active_jobs


@pytest.mark.parametrize("stage", ["confirmation", "save"])
@pytest.mark.parametrize("interruption", ["close", "destroy", "shutdown"])
def test_install_prompt_interruption_cannot_start_a_hidden_launch(
    qtbot, monkeypatch, tmp_path, deferred_updates, stage, interruption,
) -> None:
    lifecycle, jobs, _quit_calls = deferred_updates
    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = UpdateDialog(
        parent=parent, auto_check=False, initial_result=_available_update(), lifecycle=lifecycle
    )
    dialog._handle_download_result(_downloaded_fixture(tmp_path))

    def _interrupt() -> None:
        if interruption == "close":
            dialog.reject()
        elif interruption == "destroy":
            parent.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        else:
            lifecycle.request_shutdown()

    def _confirm(*_args):
        if stage == "confirmation":
            _interrupt()
        return QMessageBox.StandardButton.Yes

    def _save() -> bool:
        assert stage == "save", "Do not save after confirmation was interrupted."
        _interrupt()
        return True

    dialog._on_before_install = _save
    monkeypatch.setattr(QMessageBox, "question", _confirm)
    dialog.install_and_restart()
    assert not jobs
    assert not lifecycle.has_active_jobs


def test_large_download_byte_counts_are_scaled_without_qt_integer_overflow(
    qtbot, tmp_path, deferred_updates,
) -> None:
    lifecycle, jobs, _quit_calls = deferred_updates
    dialog = UpdateDialog(auto_check=False, initial_result=_available_update(), lifecycle=lifecycle)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.start_download()
    job = jobs[-1]
    qtbot.waitUntil(lambda: job.is_running)
    total = 4 * 1024**3
    job.progress_changed.emit(3 * 1024**3, total)
    assert dialog.progress_bar.maximum() == 1000
    assert dialog.progress_bar.value() == 750
    job.progress_changed.emit(total + 1, total)
    assert dialog.progress_bar.value() == 1000
    job.progress_changed.emit(total, None)
    assert dialog.progress_bar.maximum() == 0
    job.finish(replace(_downloaded_fixture(tmp_path), size_bytes=total))
    assert dialog.progress_bar.maximum() == dialog.progress_bar.value() == 1000
    assert dialog.install_button.isEnabled()


@pytest.mark.parametrize("source", ["dialog", "startup"])
def test_metadata_callback_receives_the_worker_cancellation_event(
    qapp, qtbot, deferred_updates, source,
) -> None:
    lifecycle, jobs, _quit_calls = deferred_updates
    events: list[Event] = []

    def _check(cancel_event: Event) -> UpdateCheckResult:
        events.append(cancel_event)
        return replace(_available_update(), update_available=False)

    if source == "dialog":
        dialog = UpdateDialog(auto_check=False, check_callback=_check, lifecycle=lifecycle)
        qtbot.addWidget(dialog)
        dialog.start_update_check()
    else:
        controller = StudioController(qapp)
        controller._startup_update_check_callback = _check
        controller._start_startup_update_check()
    job = jobs[-1]
    assert job.thread() is qapp.thread()
    assert job.worker_thread is None  # The fake job deliberately creates no native worker.
    qtbot.waitUntil(lambda: job.is_running)
    job.run_callback()
    assert events == [job.cancel_event]
    job.finish()
    assert not lifecycle.has_active_jobs


@pytest.mark.parametrize("shutdown", ["quit_event", "last_window", "about_to_quit"])
def test_application_shutdown_cancels_all_jobs_and_defers_quit(
    qapp, qtbot, deferred_updates, shutdown,
) -> None:
    lifecycle, jobs, quit_calls = deferred_updates
    qapp.setQuitOnLastWindowClosed(True)
    lifecycle.start_task(lambda _progress, _cancel: None)
    lifecycle.start_task(lambda _progress, _cancel: None)
    qtbot.waitUntil(lambda: all(job.is_running for job in jobs))
    assert not qapp.quitOnLastWindowClosed()

    if shutdown == "quit_event":
        QCoreApplication.sendEvent(qapp, QEvent(QEvent.Type.Quit))
    elif shutdown == "last_window":
        qapp.lastWindowClosed.emit()
    else:
        lifecycle._about_to_quit()
    assert lifecycle.is_shutting_down
    assert all(job.cancel_event.is_set() for job in jobs)
    assert quit_calls == []
    with pytest.raises(RuntimeError, match="closing"):
        lifecycle.start_task(lambda _progress, _cancel: None)

    jobs[0].finish()
    qapp.processEvents()
    assert lifecycle.has_active_jobs
    assert quit_calls == []
    jobs[1].finish()
    qtbot.waitUntil(lambda: quit_calls == ["quit"])
    assert not lifecycle.has_active_jobs
    assert qapp.quitOnLastWindowClosed()


def test_root_onboarding_window_transitions_do_not_cancel_startup_work(
    qapp, qtbot, deferred_updates,
) -> None:
    lifecycle, jobs, quit_calls = deferred_updates
    qapp.setQuitOnLastWindowClosed(True)
    lifecycle.begin_startup()
    lifecycle.start_task(lambda _progress, _cancel: None)
    qtbot.waitUntil(lambda: jobs[-1].is_running)
    qapp.lastWindowClosed.emit()
    assert not lifecycle.is_shutting_down
    assert not jobs[-1].cancel_event.is_set()
    jobs[-1].finish()
    assert not qapp.quitOnLastWindowClosed()
    lifecycle.finish_startup()
    assert qapp.quitOnLastWindowClosed()
    assert quit_calls == []


def test_housekeeping_is_offline_once_and_independent_of_root_or_update_check(
    qapp, qtbot, monkeypatch, deferred_updates,
) -> None:
    lifecycle, jobs, _quit_calls = deferred_updates
    controller = StudioController(qapp)
    controller.startup_update_checks_enabled = False
    calls: list[tuple[str, Event]] = []

    def _cleanup(version: str, *, cancel_event: Event) -> CacheCleanupResult:
        calls.append((version, cancel_event))
        return CacheCleanupResult()

    controller._startup_cache_cleanup_callback = _cleanup
    monkeypatch.setattr(
        controller, "ensure_fpvs_root_configured", lambda: pytest.fail("Root lookup is not needed")
    )
    controller._startup_update_check_callback = lambda _cancel: pytest.fail("Network is not needed")
    controller.start_update_cache_housekeeping()
    controller.start_update_cache_housekeeping()
    assert len(jobs) == 1
    assert calls == []
    assert not controller._startup_update_check_started
    qtbot.waitUntil(lambda: jobs[0].is_running)
    jobs[0].run_callback()
    assert len(calls) == 1
    assert calls[0][1] is jobs[0].cancel_event
    jobs[0].finish()
    assert controller._startup_cache_job is None
    assert not lifecycle.has_active_jobs


def test_housekeeping_failure_does_not_prompt_or_block_other_startup_work(
    qapp, qtbot, monkeypatch, deferred_updates, caplog,
) -> None:
    lifecycle, jobs, _quit_calls = deferred_updates
    controller = StudioController(qapp)
    monkeypatch.setattr(UpdateDialog, "exec", lambda _self: pytest.fail("No cache-error dialog"))
    controller.start_update_cache_housekeeping()
    qtbot.waitUntil(lambda: jobs[0].is_running)
    jobs[0].finish(error=PermissionError("A cache file is locked."))
    assert controller._startup_cache_job is None
    assert not lifecycle.has_active_jobs
    assert "housekeeping could not complete" in caplog.text
    controller._startup_update_check_callback = _available_update
    controller._start_startup_update_check()
    assert controller._startup_update_job is not None


def test_canceled_startup_metadata_check_cannot_open_a_late_prompt(
    qapp, qtbot, monkeypatch, deferred_updates,
) -> None:
    lifecycle, jobs, quit_calls = deferred_updates
    controller = StudioController(qapp)
    controller._startup_update_check_callback = _available_update
    monkeypatch.setattr(UpdateDialog, "exec", lambda _self: pytest.fail("No late update dialog"))
    controller._start_startup_update_check()
    job = jobs[-1]
    qtbot.waitUntil(lambda: job.is_running)
    job.run_callback()
    lifecycle.request_shutdown()
    job.finish()
    qtbot.waitUntil(lambda: quit_calls == ["quit"])
    assert controller._startup_update_job is None


@pytest.mark.parametrize("operation", ["download", "install"])
def test_failed_update_stays_recoverable_and_does_not_quit(
    qtbot, monkeypatch, tmp_path, deferred_updates, operation,
) -> None:
    lifecycle, jobs, quit_calls = deferred_updates
    dialog = UpdateDialog(auto_check=False, initial_result=_available_update(), lifecycle=lifecycle)
    qtbot.addWidget(dialog)
    dialog.show()
    if operation == "download":
        dialog.start_download()
    else:
        dialog._handle_download_result(_downloaded_fixture(tmp_path))
        monkeypatch.setattr(
            QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes
        )
        dialog.install_and_restart()
    qtbot.waitUntil(lambda: jobs[-1].is_running)
    jobs[-1].finish(error=RuntimeError("The cached installer could not be verified."))
    assert dialog.isVisible()
    assert dialog.download_button.isEnabled()
    assert dialog.check_button.isEnabled()
    assert not dialog.install_button.isEnabled()
    assert dialog._downloaded_installer is None
    assert "could not" in dialog.status_label.text()
    assert quit_calls == []


@pytest.mark.parametrize("size", [(680, 600), (760, 620)])
@pytest.mark.parametrize("state", ["available", "unverifiable", "busy", "canceling", "error"])
def test_update_dialog_long_content_fits_minimum_and_default_sizes(
    qtbot, tmp_path, deferred_updates, size, state,
) -> None:
    lifecycle, jobs, _quit_calls = deferred_updates
    full_notes = (
        "Improved update integrity, recoverable interrupted transfers, and compatible upgrade "
        "history. " * 12
    ) + str(tmp_path / ("very-long-installer-folder-" * 12))
    result = replace(
        _available_update(),
        current_version="2026.123.456rc987654321",
        latest_version="2027.123.456rc987654321",
        release_notes_summary=full_notes,
    )
    if state == "unverifiable":
        assert result.installer_asset is not None
        result = replace(result, installer_asset=replace(result.installer_asset, sha256=None))
    dialog = UpdateDialog(auto_check=False, initial_result=result, lifecycle=lifecycle)
    qtbot.addWidget(dialog)
    dialog.resize(*size)
    dialog.show()
    if state in {"busy", "canceling"}:
        dialog.start_download()
        qtbot.waitUntil(lambda: jobs[-1].is_running)
        if state == "canceling":
            dialog.reject()
    elif state == "error":
        dialog._handle_task_error(RuntimeError(full_notes), "install")
    qtbot.waitUntil(lambda: dialog.close_button.width() > 0)

    assert dialog.width() == size[0]
    assert dialog.height() == size[1]
    assert_visible_children_within_parent(dialog)
    for button in (
        dialog.check_button, dialog.download_button, dialog.install_button,
        dialog.close_button, dialog.release_notes_button,
    ):
        assert button.width() >= button.fontMetrics().horizontalAdvance(button.text()) + 20
    for label in dialog.findChildren(QLabel):
        if not label.isVisible():
            continue
        if label.wordWrap():
            assert label.height() + 1 >= label.heightForWidth(label.width()), label.objectName()
        else:
            assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
    assert dialog.notes_label.toolTip() == full_notes
    assert len(dialog.notes_label.text()) <= 240
    assert dialog.notes_label.text() != full_notes


def test_application_starts_cache_work_before_root_setup_and_drains_on_failure(monkeypatch):
    calls: list[str] = []
    pending: list[Callable[[], None]] = []

    class FakeLifecycle:
        has_active_jobs = True

        def begin_startup(self):
            calls.append("begin-startup")

        def finish_startup(self):
            calls.append("finish-startup")

        def request_shutdown(self):
            calls.append("cancel")

    lifecycle = FakeLifecycle()

    class FakeApp:
        def exec(self):
            calls.append("event-loop")
            if pending:
                pending.pop(0)()
            else:
                lifecycle.has_active_jobs = False
            return 0

    class FakeController:
        welcome_window = None
        main_window = None

        def __init__(self, _app):
            pass

        def start_update_cache_housekeeping(self):
            calls.append("cache-worker")

        def show_welcome(self):
            calls.append("root-setup")
            raise RuntimeError("Startup was interrupted.")

    monkeypatch.setattr(application_module, "create_application", lambda _args: FakeApp())
    monkeypatch.setattr(application_module, "StudioController", FakeController)
    monkeypatch.setattr(application_module, "update_lifecycle", lambda _app: lifecycle)
    monkeypatch.setattr(
        application_module.QTimer, "singleShot", lambda _delay, call: pending.append(call)
    )
    with pytest.raises(RuntimeError, match="interrupted"):
        application_module.run_gui_app([])
    assert calls.index("cache-worker") < calls.index("root-setup")
    assert calls.count("event-loop") == 2
    assert "cancel" in calls
    assert not lifecycle.has_active_jobs
