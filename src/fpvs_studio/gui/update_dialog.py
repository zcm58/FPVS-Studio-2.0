"""User-facing update dialog for FPVS Studio."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio import __version__
from fpvs_studio.gui.components import mark_primary_action, mark_secondary_action
from fpvs_studio.updates.downloader import download_installer
from fpvs_studio.updates.github_releases import check_for_updates
from fpvs_studio.updates.installer import launch_installer
from fpvs_studio.updates.models import DownloadedInstaller, InstallerAsset, UpdateCheckResult

ProgressReporter = Callable[[int, int | None], None]
TaskCallback = Callable[[ProgressReporter], object]


class _UpdateTaskWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    progress_changed = Signal(int, object)
    finished = Signal()

    def __init__(self, callback: TaskCallback) -> None:
        super().__init__()
        self._callback = callback

    @Slot()
    def run(self) -> None:
        try:
            result = self._callback(self._emit_progress)
        except Exception as error:
            self.failed.emit(error)
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()

    def _emit_progress(self, downloaded: int, total: int | None) -> None:
        self.progress_changed.emit(downloaded, total)


class UpdateDialog(QDialog):
    """Check GitHub Releases and guide the user through an installer update."""

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        auto_check: bool = True,
        check_callback: Callable[[], UpdateCheckResult] = check_for_updates,
        download_callback: Callable[
            [InstallerAsset, ProgressReporter],
            DownloadedInstaller,
        ] = lambda asset, progress: download_installer(asset, progress_callback=progress),
        installer_launcher: Callable[[Path], object] = launch_installer,
        on_before_install: Callable[[], bool] | None = None,
        quit_app: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("update_dialog")
        self.setWindowTitle("Check for Updates")
        self.setMinimumWidth(520)

        self._check_callback = check_callback
        self._download_callback = download_callback
        self._installer_launcher = installer_launcher
        self._on_before_install = on_before_install
        self._quit_app = quit_app or self._quit_application
        self._thread: QThread | None = None
        self._worker: _UpdateTaskWorker | None = None
        self._result: UpdateCheckResult | None = None
        self._downloaded_installer: DownloadedInstaller | None = None

        self._build_ui()
        self._set_idle_state()
        if auto_check:
            QTimer.singleShot(0, self.start_update_check)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.title_label = QLabel("FPVS Studio updates", self)
        self.title_label.setObjectName("update_dialog_title")
        layout.addWidget(self.title_label)

        self.status_label = QLabel("Ready to check for updates.", self)
        self.status_label.setObjectName("update_dialog_status")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        versions_layout = QVBoxLayout()
        versions_layout.setSpacing(4)
        self.current_version_label = QLabel(f"Current version: {__version__}", self)
        self.latest_version_label = QLabel("Latest version: Not checked yet", self)
        versions_layout.addWidget(self.current_version_label)
        versions_layout.addWidget(self.latest_version_label)
        layout.addLayout(versions_layout)

        self.notes_heading_label = QLabel("What's New", self)
        self.notes_heading_label.setObjectName("update_dialog_notes_heading")
        layout.addWidget(self.notes_heading_label)
        self.notes_label = QLabel("Release notes will appear when an update is available.", self)
        self.notes_label.setObjectName("update_dialog_notes")
        self.notes_label.setWordWrap(True)
        layout.addWidget(self.notes_label)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setObjectName("update_dialog_progress")
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.release_notes_button = QPushButton("View Full Release Notes", self)
        self.release_notes_button.setObjectName("update_dialog_release_notes_button")
        mark_secondary_action(self.release_notes_button)
        self.release_notes_button.clicked.connect(self._open_release_notes)
        button_row.addWidget(self.release_notes_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.button_box = QDialogButtonBox(self)
        self.check_button = self.button_box.addButton(
            "Check Again",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        self.download_button = self.button_box.addButton(
            "Download Update",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        self.install_button = self.button_box.addButton(
            "Install and Restart",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        self.close_button = self.button_box.addButton(QDialogButtonBox.StandardButton.Close)
        mark_secondary_action(self.check_button)
        mark_primary_action(self.download_button)
        mark_primary_action(self.install_button)
        self.check_button.clicked.connect(self.start_update_check)
        self.download_button.clicked.connect(self.start_download)
        self.install_button.clicked.connect(self.install_and_restart)
        self.close_button.clicked.connect(self.reject)
        layout.addWidget(self.button_box)

    @Slot()
    def start_update_check(self) -> None:
        if self._thread is not None:
            return
        self._result = None
        self._downloaded_installer = None
        self._set_busy_state("Checking GitHub Releases...")
        self.progress_bar.setVisible(False)
        self._start_task(lambda _progress: self._check_callback(), self._handle_check_result)

    @Slot()
    def start_download(self) -> None:
        if self._thread is not None:
            QTimer.singleShot(0, self.start_download)
            return
        if self._result is None:
            return
        asset = self._result.installer_asset
        if asset is None:
            return
        self._downloaded_installer = None
        self._set_busy_state("Downloading update...")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self._start_task(
            lambda progress: self._download_callback(asset, progress),
            self._handle_download_result,
        )

    @Slot()
    def install_and_restart(self) -> None:
        if self._downloaded_installer is None:
            return
        answer = QMessageBox.question(
            self,
            "Install Update",
            "FPVS Studio needs to close to install the update.\n\n"
            "Install the update and restart FPVS Studio?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self._on_before_install is not None and not self._on_before_install():
            return
        try:
            self._installer_launcher(self._downloaded_installer.path)
        except Exception as error:
            self._show_error("Install Update", str(error))
            return
        self.accept()
        self._quit_app()

    def _start_task(
        self,
        callback: TaskCallback,
        result_handler: Callable[[object], None],
    ) -> None:
        thread = QThread(self)
        worker = _UpdateTaskWorker(callback)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(result_handler)
        worker.failed.connect(self._handle_task_error)
        worker.progress_changed.connect(self._handle_download_progress)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._handle_thread_finished)
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(object)
    def _handle_check_result(self, result: object) -> None:
        if not isinstance(result, UpdateCheckResult):
            self._handle_task_error(TypeError("Update check returned an unexpected result."))
            return
        self._result = result
        self.current_version_label.setText(f"Current version: {result.current_version}")
        self.latest_version_label.setText(f"Latest version: {result.latest_version}")
        self.release_notes_button.setEnabled(result.release_url is not None)
        if result.release_notes_summary:
            self.notes_label.setText(result.release_notes_summary)
        elif result.release_url is not None:
            self.notes_label.setText("No release notes were provided for this release.")
        else:
            self.notes_label.setText("Release notes will appear when an update is available.")

        if result.update_available and result.installer_asset is not None:
            self.status_label.setText("A new FPVS Studio version is available.")
            self.download_button.setEnabled(True)
        else:
            self.status_label.setText("FPVS Studio is up to date.")
            self.download_button.setEnabled(False)
        self.check_button.setEnabled(True)
        self.install_button.setEnabled(False)
        self.close_button.setEnabled(True)

    @Slot(object)
    def _handle_download_result(self, result: object) -> None:
        if not isinstance(result, DownloadedInstaller):
            self._handle_task_error(TypeError("Update download returned an unexpected result."))
            return
        self._downloaded_installer = result
        self.status_label.setText("The update is ready to install.")
        self.download_button.setEnabled(True)
        self.install_button.setEnabled(True)
        self.check_button.setEnabled(True)
        self.close_button.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, max(1, result.size_bytes))
        self.progress_bar.setValue(result.size_bytes)

    @Slot(object)
    def _handle_task_error(self, error: object) -> None:
        self.status_label.setText(
            "The update check could not be completed. You can still visit GitHub "
            "Releases manually."
        )
        self.notes_label.setText(str(error))
        self.progress_bar.setVisible(False)
        self.check_button.setEnabled(True)
        self.download_button.setEnabled(False)
        self.install_button.setEnabled(False)
        self.close_button.setEnabled(True)

    @Slot(int, object)
    def _handle_download_progress(self, downloaded: int, total: object) -> None:
        if isinstance(total, int) and total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(min(downloaded, total))
        else:
            self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)

    @Slot()
    def _handle_thread_finished(self) -> None:
        self._thread = None
        self._worker = None

    def _set_idle_state(self) -> None:
        self.release_notes_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.install_button.setEnabled(False)
        self.check_button.setEnabled(True)
        self.close_button.setEnabled(True)

    def _set_busy_state(self, status_text: str) -> None:
        self.status_label.setText(status_text)
        self.check_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.install_button.setEnabled(False)
        self.close_button.setEnabled(False)

    def _open_release_notes(self) -> None:
        if self._result is None or self._result.release_url is None:
            return
        QDesktopServices.openUrl(QUrl(self._result.release_url))

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    @staticmethod
    def _quit_application() -> None:
        app = QApplication.instance()
        if app is not None:
            app.quit()
