"""Editable parallel-port addresses with read-only device discovery."""

from __future__ import annotations

import logging
import re
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
from fpvs_studio.gui.update_lifecycle import UpdateJob, UpdateTaskResult, update_lifecycle
from fpvs_studio.triggers.parallel_discovery import ParallelPortCandidate, discover_parallel_ports

_LOGGER = logging.getLogger(__name__)


class ParallelPortSelector(QWidget):
    """Retain manual hexadecimal addresses while listing Windows port metadata."""

    address_changed = Signal()

    def __init__(self, address: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._job: UpdateJob | None = None
        self._started = False
        self._dismissed = False
        self._manual_override = address is not None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        self.combo = QComboBox(self)
        self.combo.setEditable(True)
        self.combo.setObjectName("brainproducts_parallel_address_combo")
        self.combo.setAccessibleName("Parallel port address in hexadecimal")
        self.combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon,
        )
        self.combo.setMinimumContentsLength(10)
        self.combo.setEditText(
            f"0x{address:X}" if type(address) is int else "" if address is None else str(address),
        )
        self.edit = cast(QLineEdit, self.combo.lineEdit())
        self.edit.setObjectName("brainproducts_parallel_address_edit")
        self.edit.setAccessibleName("Parallel port address in hexadecimal")
        self.edit.setPlaceholderText("e.g. 0x378")
        self.combo.setToolTip(
            "Enter the I/O start address shown in Device Manager > Resources, in hexadecimal "
            "(for example 0x378). USB printer adapters do not provide a supported parallel port.",
        )
        self.edit.setToolTip(self.combo.toolTip())
        row.addWidget(self.combo, 1)
        self.detect_button = QPushButton("Detect", self)
        self.detect_button.setAutoDefault(False)
        self.detect_button.setAccessibleName("Detect parallel ports")
        self.detect_button.setToolTip(
            "List Windows parallel-port names and I/O addresses without loading a driver, "
            "opening a port or sending markers. Missing addresses must be entered manually.",
        )
        mark_secondary_action(self.detect_button)
        row.addWidget(self.detect_button)
        layout.addLayout(row)
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setObjectName("parallel_port_status")
        self.status_label.hide()
        layout.addWidget(self.status_label)
        self.edit.textChanged.connect(self.address_changed)
        self.edit.textEdited.connect(self._manual_address_edited)
        self.combo.activated.connect(self._manual_address_edited)
        self.detect_button.clicked.connect(self.detect_ports)

    def _manual_address_edited(self, _value: object = None) -> None:
        self._manual_override = True

    @property
    def address(self) -> int | str | None:
        """Return a hexadecimal address, retaining malformed text for validation."""

        text = self.edit.text().strip()
        if not text:
            return None
        if re.fullmatch(r"(?:0[xX])?[0-9a-fA-F]{1,4}", text):
            return int(text, 16)
        return text

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._dismissed = False
        if not self._started:
            self.detect_ports()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self.cancel()
        super().hideEvent(event)

    def _status(self, text: str, details: str = "") -> None:
        self.status_label.setText(text)
        self.status_label.setToolTip(details)
        self.status_label.setAccessibleDescription(details)
        self.status_label.setVisible(bool(text))

    def detect_ports(self) -> None:
        if self._job is not None or self._dismissed:
            return
        self._started = True
        self.detect_button.setEnabled(False)
        self._status("Detecting parallel ports…")
        try:
            self._job = update_lifecycle().start_task(
                lambda _progress, cancel: discover_parallel_ports(cancelled=cancel.is_set),
            )
        except RuntimeError as exc:
            self._complete(UpdateTaskResult(error=exc))
        else:
            self._job.finished.connect(self._finished)

    @Slot(object)
    def _finished(self, value: object) -> None:
        if self._job is None or self.sender() is not self._job:
            return
        self._complete(cast(UpdateTaskResult, value))

    def _complete(self, result: UpdateTaskResult) -> None:
        self._job = None
        self.detect_button.setEnabled(True)
        if self._dismissed:
            return
        if result.cancelled:
            self._status("Detection cancelled. Retry or enter the address.")
            return
        if result.error is not None:
            _LOGGER.warning("Parallel port discovery failed: %s", result.error)
            self._status("Detection failed. Retry or enter the address.", str(result.error))
            return
        candidates = cast(tuple[ParallelPortCandidate, ...], result.value)
        previous = self.edit.text()
        self.combo.blockSignals(True)
        self.edit.blockSignals(True)
        self.combo.clear()
        for candidate in candidates:
            text = (f"0x{candidate.address:X}" if candidate.address is not None
                    else f"{candidate.name} (address unavailable)")
            self.combo.addItem(text, candidate.address)
            self.combo.setItemData(
                self.combo.count() - 1, f"{candidate.name}\n{candidate.device_id}",
                Qt.ItemDataRole.ToolTipRole,
            )
        address = previous
        if (not self._manual_override and not previous.strip()
                and len(candidates) == 1 and candidates[0].address is not None):
            address = f"0x{candidates[0].address:X}"
        self.combo.setEditText(address)
        self.edit.blockSignals(False)
        self.combo.blockSignals(False)
        details = "\n".join(
            f"{item.name}: "
            f"{f'0x{item.address:X}' if item.address is not None else 'address unavailable'}"
            f"\n{item.device_id}" for item in candidates
        )
        if not candidates:
            text = "No parallel ports found. Enter the I/O address or retry."
        elif len(candidates) > 1:
            text = "Several parallel ports found. Choose an address or enter one."
        elif candidates[0].address is None:
            text = "Port found without an I/O address. Enter it from Device Manager > Resources."
        else:
            text = "Parallel port found. Confirm its I/O address."
        self._status(text, details)
        self.address_changed.emit()

    def cancel(self, _result: int = 0) -> None:
        self._dismissed = True
        if self._job is not None:
            self._job.finished.disconnect(self._finished)
            self._job.cancel()
            self._job = None
            self._started = False
        self.detect_button.setEnabled(True)
