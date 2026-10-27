"""Project port selection and worker-backed availability checks for BioSemi."""

from __future__ import annotations

import logging
from typing import cast

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.components import mark_secondary_action
from fpvs_studio.gui.update_lifecycle import (
    UpdateCallback,
    UpdateJob,
    UpdateTaskResult,
    update_lifecycle,
)
from fpvs_studio.triggers.serial_backend import resolve_serial_port
from fpvs_studio.triggers.serial_port_access import (
    SerialPortAccessResult,
    SerialPortInfo,
    check_serial_port_access,
    enumerate_serial_ports,
)

_LOGGER = logging.getLogger(__name__)


class BioSemiPortSelector(QWidget):
    """Keep manual selection independent of generic serial-port metadata."""

    port_changed = Signal()

    def __init__(self, port: str | None, baudrate: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.baudrate = baudrate
        self._job: UpdateJob | None = None
        self._operation: str | None = None
        self._checked_port = ""
        self._enumeration_started = False
        self._dismissed = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.combo = QComboBox(self)
        self.combo.setObjectName("biosemi_serial_port_combo")
        self.combo.setAccessibleName("BioSemi trigger interface serial port")
        self.combo.setEditable(True)
        self.combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon,
        )
        self.combo.setMinimumContentsLength(8)
        self.combo.setEditText(resolve_serial_port(port))
        self.edit = cast(QLineEdit, self.combo.lineEdit())
        self.edit.setObjectName("biosemi_serial_port_edit")
        self.edit.setAccessibleName("BioSemi trigger interface serial port")
        self.combo.setToolTip(
            "Choose the USB Trigger Interface port shown in Device Manager, or enter it. "
            "Generic USB serial names do not identify BioSemi hardware. COM3 is the default."
        )
        row.addWidget(self.combo, 1)
        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.setAutoDefault(False)
        self.refresh_button.setToolTip("Refresh serial-port names without opening any ports.")
        self.check_button = QPushButton("Check Port", self)
        self.check_button.setAutoDefault(False)
        self.check_button.setToolTip(
            f"Open and close only the selected port at {baudrate} baud / 8N1. "
            "No marker bytes are sent. Access does not confirm BioSemi identity or marker receipt. "
            "The driver may change control lines while opening the port."
        )
        for button in (self.refresh_button, self.check_button):
            mark_secondary_action(button)
            row.addWidget(button)
        layout.addLayout(row)
        self.status_label = QLabel(self)
        self.status_label.setObjectName("biosemi_port_status")
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.hide()
        layout.addWidget(self.status_label)
        self.edit.textChanged.connect(self._port_edited)
        self.refresh_button.clicked.connect(self.refresh_ports)
        self.check_button.clicked.connect(self.check_port)

    @property
    def port(self) -> str:
        return self.edit.text().strip()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._dismissed = False
        if not self._enumeration_started:
            self.refresh_ports()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self.cancel()
        super().hideEvent(event)

    def _status(self, text: str, details: str = "") -> None:
        self.status_label.setText(text)
        self.status_label.setToolTip(details)
        self.status_label.setAccessibleDescription(details)
        self.status_label.setVisible(bool(text))

    def _buttons(self) -> None:
        self.refresh_button.setEnabled(self._job is None)
        self.check_button.setEnabled(self._job is None and bool(self.port))

    def _port_edited(self) -> None:
        # A completed check applies only to its original selection, including after
        # editing away and back to the same port while a request is in flight.
        if self._operation == "check":
            self._checked_port = ""
            if self._job is not None:
                self._job.cancel()
        self._status("")
        self._buttons()
        self.port_changed.emit()

    def refresh_ports(self) -> None:
        if self._job is not None or self._dismissed:
            return
        self._enumeration_started = True
        self._operation = "list"
        self._status("Refreshing serial ports…")
        self._start(lambda _progress, cancel: enumerate_serial_ports(cancel_event=cancel))

    def check_port(self) -> None:
        if self._job is not None or self._dismissed or not self.port:
            return
        port, baudrate = self.port, self.baudrate
        self._checked_port = port
        self._operation = "check"
        self._status(f"Checking {port}…")
        self._start(lambda _progress, cancel: check_serial_port_access(
            port, baudrate=baudrate, cancel_event=cancel,
        ))

    def _start(self, callback: UpdateCallback) -> None:
        try:
            self._job = update_lifecycle().start_task(callback)
        except RuntimeError as exc:
            self._complete(UpdateTaskResult(error=exc))
        else:
            self._job.finished.connect(self._finished)
        self._buttons()

    @Slot(object)
    def _finished(self, value: object) -> None:
        # Queued results from a dismissed/reopened request cannot replace a new job.
        if self._job is None or self.sender() is not self._job:
            return
        self._complete(cast(UpdateTaskResult, value))

    def _complete(self, result: UpdateTaskResult) -> None:
        operation = self._operation
        checked_port = self._checked_port
        self._job = None
        self._operation = None
        self._buttons()
        if self._dismissed:
            return
        if operation == "check" and (not checked_port or self.port != checked_port):
            self._status("")
            return
        if result.cancelled:
            self._status("Port check cancelled. Retry." if operation == "check"
                         else "Refresh cancelled. Retry or enter a port.")
        elif result.error is not None:
            _LOGGER.warning("BioSemi serial-port %s failed: %s", operation, result.error)
            text = (f"{checked_port}: Check failed. Retry." if operation == "check"
                    else "Could not list ports. Retry or enter a port.")
            self._status(text, str(result.error))
        elif operation == "list":
            ports = cast(tuple[SerialPortInfo, ...], result.value)
            previous = self.edit.text()
            self.combo.blockSignals(True)
            self.edit.blockSignals(True)
            self.combo.clear()
            for info in ports:
                self.combo.addItem(info.port)
                self.combo.setItemData(
                    self.combo.count() - 1, info.description, Qt.ItemDataRole.ToolTipRole,
                )
            self.combo.setEditText(previous)
            self.edit.blockSignals(False)
            self.combo.blockSignals(False)
            self._status(
                "" if ports else "No serial ports listed. Connect the interface or enter its port.",
            )
        else:
            access = cast(SerialPortAccessResult, result.value)
            if access.port != checked_port:
                self._status("")
                return
            state = "Port accessible." if access.accessible else "Port unavailable. See details."
            details = access.access_error if not access.accessible else (
                "The selected port opened and closed. "
                "BioSemi identity and marker receipt are unverified."
            )
            self._status(f"{checked_port}: {state}", details)

    def cancel(self) -> None:
        self._dismissed = True
        if self._operation == "list" and self._job is not None:
            self._enumeration_started = False
        if self._job is not None:
            self._job.finished.disconnect(self._finished)
            self._job.cancel()
        self._job = None
        self._operation = None
        self._checked_port = ""
        self._status("")
        self._buttons()
