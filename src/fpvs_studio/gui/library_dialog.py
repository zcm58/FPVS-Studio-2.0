"""Native whole-experiment library view; services own credentials and downloads."""

from __future__ import annotations

import socket
from typing import cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.experiment_categories import experiment_category_label
from fpvs_studio.core.library_installations import (
    InstalledLibraryProject,
    LibraryInstallStatus,
    library_install_status,
)
from fpvs_studio.gui.components import DialogHeader, apply_dialog_theme, mark_primary_action
from fpvs_studio.library.models import LibraryCatalog, LibraryConnection, LibraryItem


class LibraryDialog(QDialog):
    """Browse editable local experiment copies at 900x640 minimum / 1040x760 default."""

    action_requested = Signal(str)
    closing = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("experiment_library_dialog")
        self.setWindowTitle("FPVS Studio Experiment Library")
        self.setMinimumSize(900, 640)
        self.resize(1040, 760)
        self.setModal(True)
        self._busy = False
        self._connected = False
        self._items: tuple[LibraryItem, ...] = ()
        self._installations: tuple[InstalledLibraryProject, ...] | None = None
        self._service_url = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(
            DialogHeader(
                "Experiment Library",
                "Download a complete experiment, then review its settings for this computer.",
                parent=self,
            )
        )
        self.connection_label = QLabel("Connect this computer with your lab's access code.", self)
        self.connection_label.setWordWrap(True)
        self.connection_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.connection_label)
        self.connection_fields = QWidget(self)
        connection_form = QFormLayout(self.connection_fields)
        connection_form.setContentsMargins(0, 0, 0, 0)
        self.code_edit = QLineEdit(self.connection_fields)
        self.code_edit.setObjectName("library_access_code")
        self.code_edit.setMaxLength(128)
        self.code_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.code_edit.setPlaceholderText("Lab-issued access code")
        self.device_edit = QLineEdit(socket.gethostname()[:80], self.connection_fields)
        self.device_edit.setObjectName("library_device_name")
        self.device_edit.setMaxLength(80)
        connection_form.addRow("Access code", self.code_edit)
        connection_form.addRow("Computer name", self.device_edit)
        layout.addWidget(self.connection_fields)
        connection_actions = QHBoxLayout()
        self.connect_button = QPushButton("Connect", self)
        self.disconnect_button = QPushButton("Disconnect this computer", self)
        self.refresh_button = QPushButton("Refresh", self)
        for button, action in (
            (self.connect_button, "connect"),
            (self.disconnect_button, "disconnect"),
            (self.refresh_button, "refresh"),
        ):
            button.setAutoDefault(False)
            button.clicked.connect(
                lambda _checked=False, value=action: self.action_requested.emit(value)
            )
            connection_actions.addWidget(button)
        connection_actions.addStretch(1)
        layout.addLayout(connection_actions)
        self.search_edit = QLineEdit(self)
        self.search_edit.setObjectName("library_search")
        self.search_edit.setPlaceholderText("Search experiments by title, description, or category")
        self.search_edit.setAccessibleName("Search experiments")
        self.search_edit.textChanged.connect(self._filter)
        layout.addWidget(self.search_edit)
        columns = QHBoxLayout()
        self.item_list = QListWidget(self)
        self.item_list.setObjectName("library_experiments")
        self.item_list.setAccessibleName("Available experiments")
        self.item_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.item_list.currentItemChanged.connect(self._selection_changed)
        self.item_list.setMinimumWidth(260)
        self.details = QTextBrowser(self)
        self.details.setObjectName("library_experiment_details")
        self.details.setAccessibleName("Selected experiment details")
        self.details.setOpenExternalLinks(False)
        self.details.setMinimumWidth(0)
        columns.addWidget(self.item_list, 2)
        columns.addWidget(self.details, 3)
        layout.addLayout(columns, 1)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        self.status_label = QLabel("", self)
        self.status_label.setObjectName("library_status")
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status_label)
        footer = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel operation", self)
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(lambda: self.action_requested.emit("cancel"))
        self.cancel_button.hide()
        self.close_button = QPushButton("Close", self)
        self.close_button.setAutoDefault(False)
        self.close_button.clicked.connect(self.reject)
        self.install_button = QPushButton("Download and set up experiment", self)
        self.install_button.setObjectName("library_install")
        self.install_button.setAutoDefault(False)
        mark_primary_action(self.install_button)
        self.install_button.clicked.connect(lambda: self.action_requested.emit("install"))
        footer.addWidget(self.cancel_button)
        footer.addStretch(1)
        footer.addWidget(self.close_button)
        footer.addWidget(self.install_button)
        layout.addLayout(footer)
        self.code_edit.textChanged.connect(self._sync_actions)
        self.device_edit.textChanged.connect(self._sync_actions)
        self.set_connection(None)
        apply_dialog_theme(self)

    def set_connection(self, connection: LibraryConnection | None) -> None:
        self._connected = connection is not None
        self.connection_fields.setVisible(not self._connected)
        self.connect_button.setVisible(not self._connected)
        self.disconnect_button.setVisible(self._connected)
        self.connection_label.setText(
            f"{connection.library_name} · {connection.device_name}"
            if connection
            else "Connect this computer with your lab's access code."
        )
        if connection is not None:
            self.code_edit.clear()
        else:
            self.set_catalog(None)
        self._sync_actions()

    def set_catalog(self, catalog: LibraryCatalog | None) -> None:
        self._items = (
            tuple(item for item in catalog.items if item.kind == "experiment") if catalog else ()
        )
        self._filter()

    def selected_item(self) -> LibraryItem | None:
        row = self.item_list.currentItem()
        return cast(LibraryItem, row.data(Qt.ItemDataRole.UserRole)) if row is not None else None

    def set_installations(
        self, projects: tuple[InstalledLibraryProject, ...] | None, service_url: str,
    ) -> None:
        self._installations = projects
        self._service_url = service_url
        self._selection_changed()

    def selected_installation(self) -> LibraryInstallStatus | None:
        item = self.selected_item()
        if item is None or self._installations is None:
            return None
        return library_install_status(
            self._installations, service_url=self._service_url,
            item_id=item.item_id, version=item.version, title=item.title,
        )

    def set_busy(self, busy: bool, message: str = "", *, downloading: bool = False) -> None:
        self._busy = busy
        self.status_label.setText(message)
        self.progress_bar.setVisible(downloading)
        self.progress_bar.setValue(0)
        self.cancel_button.setVisible(busy)
        self.cancel_button.setEnabled(busy)
        self._sync_actions()

    def show_progress(self, received: int, total: int) -> None:
        self.progress_bar.setValue(min(100, max(0, round(100 * received / max(1, total)))))
        self.status_label.setText(
            f"Downloading: {received / 1048576:.1f} of {total / 1048576:.1f} MB"
        )

    def _filter(self, _text: str = "") -> None:
        query = self.search_edit.text().strip().casefold()
        self.item_list.clear()
        for item in self._items:
            category = experiment_category_label(ExperimentCategory(item.experiment_category))
            if (
                query
                not in f"{item.title} {item.description} {category}".casefold()
            ):
                continue
            row = QListWidgetItem(f"{item.title}  ·  {item.version}", self.item_list)
            row.setToolTip(f"{item.title}\nVersion {item.version}\n{item.description}")
            row.setData(Qt.ItemDataRole.UserRole, item)
        if self.item_list.count():
            self.item_list.setCurrentRow(0)
        else:
            self.details.setPlainText(
                "No matching experiments." if query else "No experiments available."
            )
        self._sync_actions()

    def _selection_changed(self, *_args: object) -> None:
        item = self.selected_item()
        if item is not None:
            category = experiment_category_label(ExperimentCategory(item.experiment_category))
            compatibility = item.compatibility_message or "Compatible with this Studio version."
            installed = self.selected_installation()
            installation = installed.message if installed else "Checking installed experiments…"
            self.details.setPlainText(
                f"{item.title}\n\n{item.description}\n\n"
                f"Version: {item.version}\nCategory: {category}\n"
                f"Download: {item.size_bytes / 1048576:.1f} MB\n"
                f"Project files: {item.file_count:,} · "
                f"{item.uncompressed_size_bytes / 1048576:.1f} MB\n"
                f"Minimum FPVS Studio: {item.min_studio_version}\n\n"
                f"{compatibility}\n\n"
                f"{installation}\n\n"
                "Creates an independent, editable project in your Studio Root Folder. "
                "Existing projects stay in place. "
                "Review display, timing and triggers in Setup before use."
            )
        self._sync_actions()

    def _sync_actions(self, *_args: object) -> None:
        item = self.selected_item()
        installed = self.selected_installation()
        self.install_button.setText({
            "new": "Download and set up experiment",
            "installed": "Already installed",
            "update": "Review update…",
            "review": "Review existing project…",
        }[installed.state] if installed else "Checking installation…")
        self.connect_button.setEnabled(
            not self._busy
            and bool(self.code_edit.text().strip())
            and bool(self.device_edit.text().strip())
        )
        self.disconnect_button.setEnabled(not self._busy and self._connected)
        self.refresh_button.setEnabled(not self._busy and self._connected)
        self.install_button.setEnabled(
            not self._busy and self._connected and item is not None and item.compatible
            and installed is not None and installed.state != "installed"
        )
        self.connection_fields.setEnabled(not self._busy)
        self.search_edit.setEnabled(not self._busy and self._connected)
        self.item_list.setEnabled(not self._busy)

    def reject(self) -> None:
        self.closing.emit()
        if self._busy:
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._busy:
            self.closing.emit()
            event.ignore()
            return
        super().closeEvent(event)
