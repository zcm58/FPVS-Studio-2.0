"""User-facing update dialog for FPVS Studio."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from threading import Event

from PySide6.QtCore import Qt, QTimer, QUrl, Slot
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio import __version__
from fpvs_studio.gui.components import (
    apply_studio_theme,
    mark_primary_action,
    mark_secondary_action,
    mark_text_role,
)
from fpvs_studio.gui.update_lifecycle import (
    ProgressReporter,
    UpdateCallback,
    UpdateJob,
    UpdateLifecycle,
    UpdateTaskResult,
    update_lifecycle,
)
from fpvs_studio.gui.update_progress import PROGRESS_MAXIMUM, UpdateProgressBar
from fpvs_studio.support.error_explanations import explain_error
from fpvs_studio.updates.helper_client import (
    HelperClient,
    check_app_updates,
    installer_updates_supported,
)
from fpvs_studio.updates.models import (
    DownloadedInstaller,
    InstallerAsset,
    UpdateCheckResult,
    UpdatePhase,
)

_LOGGER = logging.getLogger(__name__)
_MINIMUM_SIZE = (600, 270)
_DEFAULT_SIZE = (620, 280)
SOURCE_UPDATE_INSTRUCTIONS = (
    "Close Studio, pull the latest changes from the remote Git repository, then restart Studio."
)


def _check_update(progress: ProgressReporter, cancel_event: Event) -> UpdateCheckResult:
    return check_app_updates(
        __version__, cancel_event=cancel_event, phase_callback=lambda phase: progress(phase, None)
    )


def _download_update(
    asset: InstallerAsset,
    progress: ProgressReporter,
    cancel_event: Event,
) -> DownloadedInstaller:
    return HelperClient().download(
        asset,
        progress_callback=progress,
        cancel_event=cancel_event,
        phase_callback=lambda phase: progress(phase, None),
    )


def _launch_update(downloaded: DownloadedInstaller, cancel_event: Event) -> object:
    return HelperClient().launch_install(
        downloaded, parent_pid=os.getpid(), cancel_event=cancel_event
    )


class UpdateDialog(QDialog):
    """Check releases and explain the update route for this installation."""

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        auto_check: bool = True,
        check_callback: Callable[[Event], UpdateCheckResult] | None = None,
        check_task: UpdateCallback | None = None,
        download_callback: Callable[
            [InstallerAsset, ProgressReporter, Event],
            DownloadedInstaller,
        ] = _download_update,
        installer_launcher: Callable[[DownloadedInstaller, Event], object] = _launch_update,
        initial_result: UpdateCheckResult | None = None,
        on_before_install: Callable[[], bool] | None = None,
        quit_app: Callable[[], None] | None = None,
        lifecycle: UpdateLifecycle | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("update_dialog")
        self.setWindowTitle("Check for Updates")
        self.setMinimumSize(*_MINIMUM_SIZE)
        self.resize(*_DEFAULT_SIZE)

        self._check_callback = check_callback
        self._installer_updates_enabled = installer_updates_supported()
        self._check_task = check_task
        self._download_callback = download_callback
        self._installer_launcher = installer_launcher
        self._on_before_install = on_before_install
        self._quit_app = quit_app or self._quit_application
        self._lifecycle = lifecycle or update_lifecycle()
        self._job: UpdateJob | None = None
        self._task_kind: str | None = None
        self._close_pending = False
        self._close_result = int(QDialog.DialogCode.Rejected)
        self._result: UpdateCheckResult | None = None
        self._idle_title = "Studio updates"
        self._downloaded_installer: DownloadedInstaller | None = None
        self._preparing_install = False
        self._disposed = Event()
        disposed = self._disposed
        self.destroyed.connect(lambda _object=None: disposed.set())
        self._lifecycle.shutdown_started.connect(self._handle_application_shutdown)

        self._build_ui()
        self._set_idle_state()
        if not self._installer_updates_enabled:
            self._show_source_updates()
        if initial_result is not None:
            self.show_update_result(initial_result)
        elif auto_check:
            QTimer.singleShot(0, self.start_update_check)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.title_label = QLabel(self._idle_title, self)
        self.title_label.setObjectName("update_dialog_title")
        mark_text_role(self.title_label, "dialogTitle")
        layout.addWidget(self.title_label)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("update_dialog_status")
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        mark_text_role(self.status_label, "body")
        self.status_label.hide()
        layout.addWidget(self.status_label)

        facts = QFrame(self)
        facts.setObjectName("update_dialog_facts")
        facts_layout = QGridLayout(facts)
        facts_layout.setContentsMargins(16, 12, 16, 12)
        facts_layout.setHorizontalSpacing(16)
        facts_layout.setVerticalSpacing(4)
        self.current_version_label = QLabel(__version__, facts)
        self.latest_version_label = QLabel("—", facts)
        self.download_size_heading = QLabel("Download size", facts)
        self.download_size_label = QLabel(facts)
        for column, (heading, value) in enumerate((
            (QLabel("Current version", facts), self.current_version_label),
            (QLabel("Latest version", facts), self.latest_version_label),
            (self.download_size_heading, self.download_size_label),
        )):
            mark_text_role(heading, "metadata")
            mark_text_role(value, "sectionTitle")
            value.setTextFormat(Qt.TextFormat.PlainText)
            facts_layout.addWidget(heading, 0, column)
            facts_layout.addWidget(value, 1, column)
        facts_layout.setColumnStretch(0, 1)
        facts_layout.setColumnStretch(1, 1)
        self._set_download_size(None)
        layout.addWidget(facts)

        self.detail_label = QLabel(self)
        self.detail_label.setObjectName("update_dialog_detail")
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextFormat(Qt.TextFormat.PlainText)
        mark_text_role(self.detail_label, "supporting")
        self.detail_label.hide()
        layout.addWidget(self.detail_label)

        self.progress_bar = UpdateProgressBar(self, animate_download=True)
        self.progress_bar.setObjectName("update_dialog_progress")
        self.progress_bar.setAccessibleName("Update progress")
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        layout.addStretch(1)

        self.button_box = QWidget(self)
        self.button_box.setObjectName("update_dialog_button_box")
        actions_layout = QGridLayout(self.button_box)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setHorizontalSpacing(8)
        actions_layout.setVerticalSpacing(8)
        actions_layout.setColumnStretch(2, 1)
        self.release_notes_button = QPushButton("Release Notes", self.button_box)
        self.release_notes_button.setObjectName("update_dialog_release_notes_button")
        self.check_button = QPushButton("Check Again", self.button_box)
        self.check_button.setObjectName("update_dialog_check_button")
        self.download_button = QPushButton("Download and Install", self.button_box)
        self.download_button.setObjectName("update_dialog_download_button")
        self.close_button = QPushButton("Close", self.button_box)
        self.close_button.setObjectName("update_dialog_close_button")
        actions_layout.addWidget(self.release_notes_button, 0, 0)
        actions_layout.addWidget(self.check_button, 0, 1)
        actions_layout.addWidget(self.close_button, 0, 3)
        actions_layout.addWidget(self.download_button, 0, 4)
        mark_secondary_action(self.release_notes_button)
        mark_secondary_action(self.check_button)
        mark_primary_action(self.download_button)
        mark_secondary_action(self.close_button)
        self.release_notes_button.clicked.connect(self._open_release_notes)
        self.check_button.clicked.connect(self.start_update_check)
        self.download_button.clicked.connect(self.start_download)
        self.close_button.clicked.connect(self._dismiss_dialog)
        layout.addWidget(self.button_box)
        apply_studio_theme(self)
        self.close_button.setFocus()

    @Slot()
    def start_update_check(self) -> None:
        if (
            self._disposed.is_set()
            or self._job is not None
            or self._preparing_install
            or self._close_pending
            or self._lifecycle.is_shutting_down
        ):
            return
        self._result = None
        self._downloaded_installer = None
        self.title_label.setText(self._idle_title)
        self.latest_version_label.setText("—")
        self._set_download_size(None)
        self.release_notes_button.hide()
        self.release_notes_button.setEnabled(False)
        self._set_busy_state("Checking for updates…")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        check_callback = self._check_callback
        self._lifecycle.manual_check_requested.emit()
        self._start_task(
            "check",
            self._check_task
            or (
                _check_update
                if check_callback is None
                else lambda _progress, cancel: check_callback(cancel)
            ),
        )

    def show_update_result(self, result: UpdateCheckResult) -> None:
        """Populate the dialog from an already-completed update check."""

        if not self._disposed.is_set() and self._job is None and not self._close_pending:
            self._handle_check_result(result)

    @Slot()
    def start_download(self) -> None:
        if not self._installer_updates_enabled:
            return
        if (
            self._disposed.is_set()
            or self._job is not None
            or self._preparing_install
            or self._close_pending
            or self._lifecycle.is_shutting_down
        ):
            return
        if self._result is None:
            return
        asset = self._result.installer_asset
        if asset is None or asset.sha256 is None:
            return
        if self._downloaded_installer is not None:
            self.install_and_restart()
            return
        self._set_busy_state("Downloading the update...")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        download_callback = self._download_callback
        self._start_task(
            "download",
            lambda progress, cancel: download_callback(asset, progress, cancel),
        )

    @Slot()
    def install_and_restart(self) -> None:
        if (
            not self._installer_updates_enabled
            or self._disposed.is_set()
            or self._job is not None
            or self._preparing_install
            or self._downloaded_installer is None
            or self._close_pending
            or self._lifecycle.is_shutting_down
        ):
            return
        downloaded = self._downloaded_installer
        self._preparing_install = True
        self._set_busy_state("Preparing FPVS Studio Updater. Studio will close when it is ready...")
        try:
            # The combined action authorizes installation. Save can enter a nested
            # event loop, so block repeat actions and recheck close/shutdown afterward.
            if self._on_before_install is not None and not self._on_before_install():
                if not (
                    self._disposed.is_set()
                    or self._close_pending
                    or self._lifecycle.is_shutting_down
                ):
                    self._handle_download_result(downloaded)
                return
            if self._disposed.is_set() or self._close_pending or self._lifecycle.is_shutting_down:
                return
            installer_launcher = self._installer_launcher
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setVisible(True)
            self._start_task(
                "install",
                lambda _progress, cancel: installer_launcher(downloaded, cancel),
                keep_success_on_cancel=True,
                on_committed_success=self._quit_app,
            )
        finally:
            self._preparing_install = False

    def _start_task(
        self,
        kind: str,
        callback: UpdateCallback,
        *,
        keep_success_on_cancel: bool = False,
        on_committed_success: Callable[[], None] | None = None,
    ) -> None:
        job = self._lifecycle.start_task(
            callback,
            keep_success_on_cancel=keep_success_on_cancel,
            on_committed_success=on_committed_success,
        )
        job.finished.connect(self._handle_task_finished)
        job.progress_changed.connect(self._handle_download_progress)
        self.destroyed.connect(job.cancel)
        self._job = job
        self._task_kind = kind

    @Slot(object)
    def _handle_task_finished(self, outcome: object) -> None:
        kind = self._task_kind
        self._job = None
        self._task_kind = None
        if not isinstance(outcome, UpdateTaskResult) and (
            self._close_pending or self._lifecycle.is_shutting_down
        ):
            super().done(self._close_result)
            return
        if not isinstance(outcome, UpdateTaskResult):
            self._handle_task_error(TypeError("Updater returned an unexpected outcome."), kind)
        elif kind == "install" and outcome.error is None and not outcome.cancelled:
            # Launch has committed. A late close/cancel cannot undo Popen, and the app
            # must exit, but only now that the launch/verification worker has stopped.
            self._close_pending = False
            self.accept()
            return
        elif self._close_pending or self._lifecycle.is_shutting_down:
            super().done(self._close_result)
            return
        elif outcome.cancelled:
            self._handle_task_cancelled()
        elif outcome.error is not None:
            self._handle_task_error(outcome.error, kind)
        elif kind == "check":
            self._handle_check_result(outcome.value)
        elif kind == "download":
            self._handle_download_result(outcome.value)
            if isinstance(outcome.value, DownloadedInstaller):
                self.install_and_restart()

    @Slot(object)
    def _handle_check_result(self, result: object) -> None:
        if not isinstance(result, UpdateCheckResult):
            self._handle_task_error(
                TypeError("Update check returned an unexpected result."), "check"
            )
            return
        self._result = result
        self._downloaded_installer = None
        self.progress_bar.setVisible(False)
        self.current_version_label.setText(result.current_version)
        self.latest_version_label.setText(result.latest_version)
        has_release = result.release_url is not None
        self.release_notes_button.setVisible(has_release)
        self.release_notes_button.setEnabled(has_release)
        self._set_detail("")
        can_install = self._download_available()
        self._set_download_size(
            result.installer_size_bytes if can_install else None,
            result.selection_reason,
        )
        current_title = (
            "Studio is up to date" if self._installer_updates_enabled else "No newer release"
        )
        self.title_label.setText("Update available" if result.update_available else current_title)
        if not self._installer_updates_enabled:
            self._set_status(SOURCE_UPDATE_INSTRUCTIONS)
        elif result.update_available and not can_install:
            guidance = " See the release page for details." if result.release_url else ""
            self._set_status(f"The installer could not be verified.{guidance}")
        else:
            self._set_status("")
        self.download_button.setEnabled(can_install)
        self.close_button.setText("Later" if result.update_available else "Close")
        self.check_button.setEnabled(True)
        self.close_button.setEnabled(True)

    @Slot(object)
    def _handle_download_result(self, result: object) -> None:
        if not self._installer_updates_enabled:
            self._downloaded_installer = None
            return
        if not isinstance(result, DownloadedInstaller):
            self._handle_task_error(
                TypeError("Update download returned an unexpected result."), "download"
            )
            return
        self._downloaded_installer = result
        self._set_status("The update is verified and ready to install.")
        self.download_button.setEnabled(True)
        self.check_button.setEnabled(True)
        self.close_button.setEnabled(True)
        self.close_button.setText("Close")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, PROGRESS_MAXIMUM)
        self.progress_bar.setValue(PROGRESS_MAXIMUM)

    def _handle_task_error(self, error: object, kind: str | None = None) -> None:
        _LOGGER.warning("Updater operation failed", extra={"operation": kind, "error": str(error)})
        if kind == "install":
            self._downloaded_installer = None
        title = {"download": "Update Download", "install": "Update Install"}.get(
            kind or "", "Update Check",
        )
        explanation = explain_error(
            title, str(error), error=error if isinstance(error, BaseException) else None,
        )
        advice = explanation.advice if self._installer_updates_enabled else (
            "Check your internet connection and try Check Again."
        )
        self._set_status(
            explanation.summary if self._installer_updates_enabled else
            f"{explanation.summary}\n{SOURCE_UPDATE_INSTRUCTIONS}"
        )
        self._set_detail(advice)
        self.detail_label.setToolTip(f"{advice}\n\nTechnical details:\n{error}")
        self.progress_bar.setVisible(False)
        self.check_button.setEnabled(True)
        self.download_button.setEnabled(self._download_available())
        self.close_button.setEnabled(True)
        self.close_button.setText("Close")

    @Slot(object, object)
    def _handle_download_progress(self, downloaded: object, total: object) -> None:
        if self._close_pending or self._job is None:
            return
        if isinstance(downloaded, UpdatePhase):
            self._set_status(downloaded.text)
            result = downloaded.result
            if result is not None and self._task_kind == "check":
                self.current_version_label.setText(result.current_version)
                self.latest_version_label.setText(result.latest_version)
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setVisible(True)
            return
        if isinstance(downloaded, int):
            self.progress_bar.set_byte_progress(
                downloaded, total if isinstance(total, int) else None,
            )
        else:
            self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)

    def _handle_task_cancelled(self) -> None:
        self._downloaded_installer = None
        self._set_status(
            "The update operation was canceled. Retry starts from zero."
            if self._installer_updates_enabled else
            f"The update check was canceled.\n{SOURCE_UPDATE_INSTRUCTIONS}"
        )
        self.progress_bar.setVisible(False)
        self.check_button.setEnabled(True)
        self.download_button.setEnabled(self._download_available())
        self.close_button.setEnabled(True)
        self.close_button.setText("Close")

    def _download_available(self) -> bool:
        asset = None if self._result is None else self._result.installer_asset
        return bool(
            self._installer_updates_enabled
            and self._result is not None
            and self._result.update_available
            and asset is not None
            and asset.sha256 is not None
        )

    def _set_idle_state(self) -> None:
        self.release_notes_button.hide()
        self.release_notes_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.check_button.setEnabled(True)
        self.close_button.setEnabled(True)

    def _show_source_updates(self) -> None:
        self._idle_title = "macOS source updates" if sys.platform == "darwin" else "Source updates"
        self.title_label.setText(self._idle_title)
        self._set_status(SOURCE_UPDATE_INSTRUCTIONS)
        self.status_label.setToolTip(
            "After pulling, follow the updated checkout's setup instructions "
            "if dependencies changed. "
            "On macOS, use Setup Mac.command."
        )
        self.download_button.setEnabled(False)
        self.download_button.hide()

    def _set_busy_state(self, status_text: str) -> None:
        self._set_status(status_text)
        self._set_detail("")
        self.check_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.close_button.setEnabled(True)
        self.close_button.setText("Cancel and Close")

    @Slot()
    def _dismiss_dialog(self) -> None:
        self.reject()

    def reject(self) -> None:
        self.done(int(QDialog.DialogCode.Rejected))

    def done(self, result: int) -> None:
        if self._job is not None:
            self._request_close(result)
            return
        self._close_pending = True
        super().done(result)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._job is not None:
            self._request_close(int(QDialog.DialogCode.Rejected))
            event.ignore()
            return
        super().closeEvent(event)

    def _request_close(self, result: int) -> None:
        self._close_pending = True
        self._close_result = result
        self.check_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.close_button.setEnabled(False)
        self.close_button.setText("Canceling...")
        self._set_status("The dialog will close when the operation stops.")
        if self._job is not None:
            self._job.cancel()

    @Slot()
    def _handle_application_shutdown(self) -> None:
        if self._job is not None:
            self._request_close(int(QDialog.DialogCode.Rejected))
        else:
            self.reject()

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self.status_label.setVisible(bool(text))

    def _set_detail(self, text: str) -> None:
        self.detail_label.setText(text)
        self.detail_label.setVisible(bool(text))
        self.detail_label.setToolTip("")

    def _set_download_size(self, size_bytes: int | None, reason: str = "") -> None:
        size = f"{size_bytes / 1_000_000:.1f} MB" if size_bytes else ""
        self.download_size_label.setText(size)
        self.download_size_label.setToolTip(reason if size else "")
        self.download_size_label.setVisible(bool(size))
        self.download_size_heading.setVisible(bool(size))

    def _open_release_notes(self) -> None:
        if self._result is None or self._result.release_url is None:
            return
        QDesktopServices.openUrl(QUrl(self._result.release_url))

    @staticmethod
    def _quit_application() -> None:
        app = QApplication.instance()
        if app is not None:
            app.quit()
