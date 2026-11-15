"""Optional first-connection setup, with app-owned credential and enrollment jobs."""

from __future__ import annotations

import logging
import socket
from collections.abc import Callable
from threading import Event
from typing import cast

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.library_origin import MANAGED_LIBRARY_SERVICE_URL
from fpvs_studio.gui.components import DialogHeader, apply_dialog_theme, mark_primary_action
from fpvs_studio.gui.update_lifecycle import UpdateJob, UpdateTaskResult, update_lifecycle
from fpvs_studio.library.client import LibraryClient
from fpvs_studio.library.errors import LibraryCancelled, LibraryError
from fpvs_studio.library.models import LibraryConnection
from fpvs_studio.support.error_explanations import describe_error

_LOGGER = logging.getLogger(__name__)
STUDIO_ACCOUNT_URL = f"{MANAGED_LIBRARY_SERVICE_URL}/account#connect-studio"


class LibraryAccessDialog(QDialog):
    """Optional setup at 640x420 minimum / 700x460 default."""

    connect_requested = Signal(str, str)
    dismissed = Signal()

    def __init__(self, *, openfpvs: bool = True) -> None:
        super().__init__()
        self.setObjectName("library_startup_access_dialog")
        self.setWindowTitle("Connect to the Experiment Library")
        self.setMinimumSize(640, 420)
        self.resize(700, 460)
        self.setModal(True)
        self._connected = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(DialogHeader(
            "Connect to the Experiment Library",
            "Sign in to OpenFPVS and paste a one-time computer code here."
            if openfpvs else "Enter the enrollment code for your Library service.",
            parent=self,
        ))
        explanation = QLabel(
            "You can set this up later from View > Experiment Library.", self,
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.sign_in_button = QPushButton("Sign in to OpenFPVS", self)
        self.sign_in_button.setAutoDefault(False)
        self.sign_in_button.clicked.connect(self._open_sign_in)
        self.sign_in_button.setVisible(openfpvs)
        layout.addWidget(self.sign_in_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.fields = QWidget(self)
        form = QFormLayout(self.fields)
        form.setContentsMargins(0, 0, 0, 0)
        self.code_edit = QLineEdit(self.fields)
        self.code_edit.setObjectName("startup_lab_access_code")
        self.code_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.code_edit.setMaxLength(128)
        code_label = "Computer code" if openfpvs else "Enrollment code"
        self.code_edit.setPlaceholderText(code_label)
        self.device_edit = QLineEdit(socket.gethostname()[:100], self.fields)
        self.device_edit.setObjectName("startup_library_computer_name")
        self.device_edit.setMaxLength(100)
        form.addRow(code_label, self.code_edit)
        form.addRow("Computer name", self.device_edit)
        layout.addWidget(self.fields)
        self.status_label = QLabel(
            "Local experiments remain available without Library access.", self,
        )
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.offline_button = QPushButton("Continue offline", self)
        self.offline_button.setAutoDefault(False)
        self.offline_button.clicked.connect(self.reject)
        self.connect_button = QPushButton("Connect this PC", self)
        self.connect_button.setAutoDefault(False)
        self.connect_button.clicked.connect(self._connect)
        buttons.addWidget(self.offline_button)
        buttons.addWidget(self.connect_button)
        layout.addLayout(buttons)
        mark_primary_action(self.connect_button)
        apply_dialog_theme(self)

    def _open_sign_in(self) -> None:
        if not QDesktopServices.openUrl(QUrl(STUDIO_ACCOUNT_URL)):
            self.status_label.setText(f"Could not open your browser. Visit {STUDIO_ACCOUNT_URL}.")

    def _connect(self) -> None:
        if self._connected:
            self.accept()
            return
        code, name = self.code_edit.text().strip(), self.device_edit.text().strip()
        if not code or not name:
            self.status_label.setText("Enter a connection code and a name for this PC.")
            return
        self.connect_requested.emit(code, name)

    def set_busy(self, busy: bool, message: str) -> None:
        self.fields.setEnabled(not busy)
        self.sign_in_button.setEnabled(not busy)
        self.connect_button.setEnabled(not busy)
        self.connect_button.setText("Connecting…" if busy else "Connect this PC")
        self.status_label.setText(message)
        self.status_label.setToolTip("")

    def set_connected(self, connection: LibraryConnection) -> None:
        self._connected = True
        self.code_edit.clear()
        self.fields.hide()
        self.sign_in_button.hide()
        permission = "View and download" if connection.access_level == "download" else "View only"
        self.status_label.setText(
            f"Connected to {connection.lab_name or connection.library_name}. {permission} access. "
            "This PC will remember its connection securely."
        )
        self.status_label.setToolTip("")
        self.offline_button.hide()
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Continue to Studio")

    def done(self, result: int) -> None:
        self.code_edit.clear()
        self.dismissed.emit()
        super().done(result)


class LibraryAccessController(QObject):
    """Check saved access locally once per launch; contact the server only on Connect."""

    def __init__(self, app: QApplication, *, client: LibraryClient | None = None) -> None:
        super().__init__(app)
        self._client = client
        self.dialog: LibraryAccessDialog | None = None
        self._lifecycle = update_lifecycle(app)
        self._job: UpdateJob | None = None
        self._started = False
        self._dismissed = False
        self._lifecycle.shutdown_started.connect(self._dismiss)

    @property
    def client(self) -> LibraryClient:
        # Construct in the job callback: unavailable app-local cache settings must
        # use the recoverable/offline error path rather than abort GUI startup.
        if self._client is None:
            self._client = LibraryClient()
        return self._client

    @client.setter
    def client(self, value: LibraryClient) -> None:
        self._client = value

    def check(self) -> None:
        if self._started or self._lifecycle.is_shutting_down:
            return
        self._started = True
        self._run(lambda _cancel: self.client.connection_info(), self._checked)

    def _run(
        self, operation: Callable[[Event], object], completed: Callable[[object], None],
    ) -> None:
        job = self._lifecycle.start_task(
            lambda _progress, cancel: operation(cancel), keep_success_on_cancel=True,
        )
        self._job = job

        def finished(value: object) -> None:
            self._job = None
            result = cast(UpdateTaskResult, value)
            if self._dismissed or self._lifecycle.is_shutting_down or result.cancelled:
                return
            if result.error is not None:
                if isinstance(result.error, LibraryCancelled):
                    return
                self._show()
                if isinstance(result.error, LibraryError):
                    message = describe_error("Library Access", result.error)
                else:
                    _LOGGER.error("Library startup setup failed (%s)", type(result.error).__name__)
                    message = "Library access could not be configured. Retry or continue offline."
                assert self.dialog is not None
                self.dialog.set_busy(False, message)
                if isinstance(result.error, LibraryError):
                    self.dialog.status_label.setToolTip(f"{message}\n\nDetails: {result.error}")
            else:
                completed(result.value)

        job.finished.connect(finished)

    def _checked(self, value: object) -> None:
        if value is None:
            self._show()

    def _show(self) -> None:
        if self.dialog is None:
            self.dialog = LibraryAccessDialog(openfpvs=(
                self._client is None or self._client.service_url == MANAGED_LIBRARY_SERVICE_URL
            ))
            self.dialog.connect_requested.connect(self._connect)
            self.dialog.dismissed.connect(self._dismiss)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _connect(self, code: str, name: str) -> None:
        if self._job is not None or self._dismissed or self._lifecycle.is_shutting_down:
            return
        assert self.dialog is not None
        self.dialog.set_busy(True, "Connecting this PC to your lab's Library…")
        self._run(
            lambda cancel: self.client.enroll(code, name, cancel_event=cancel), self._connected,
        )

    def _connected(self, value: object) -> None:
        assert self.dialog is not None
        self.dialog.set_connected(cast(LibraryConnection, value))

    def _dismiss(self) -> None:
        self._dismissed = True
        if self._job is not None:
            self._job.cancel()
        if self.dialog is not None:
            self.dialog.code_edit.clear()
            self.dialog.hide()
