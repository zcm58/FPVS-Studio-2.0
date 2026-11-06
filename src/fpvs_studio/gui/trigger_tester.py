"""Send operator-selected digits through the existing hardware adapters."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt, Slot
from PySide6.QtGui import QKeyEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.models import ProjectRecordingSettings, TriggerSettings
from fpvs_studio.gui.components import apply_dialog_theme, mark_secondary_action
from fpvs_studio.gui.window_helpers import _coerce_exception, _show_error_dialog
from fpvs_studio.gui.workers import BackgroundTask
from fpvs_studio.triggers.base import TriggerBackend
from fpvs_studio.triggers.biosemi_errors import biosemi_port_error_message
from fpvs_studio.triggers.brainproducts_backend import BrainProductsTriggerBoxBackend
from fpvs_studio.triggers.brainproducts_errors import triggerbox_port_error_message
from fpvs_studio.triggers.manual import send_test_trigger
from fpvs_studio.triggers.parallel_backend import ParallelPortBackend
from fpvs_studio.triggers.serial_backend import SerialBackend, resolve_serial_port
from fpvs_studio.triggers.serial_port_access import SerialPortAccessError, check_serial_port_access

LOGGER = logging.getLogger(__name__)


class TriggerTesterDialog(QDialog):
    """Test a recording output with a single digit at a time."""

    def __init__(
        self,
        configuration: dict[str, object],
        triggers: TriggerSettings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Trigger Tester")
        self.setMinimumSize(560, 340)
        self.resize(self.minimumSize())
        self.setWindowModality(Qt.WindowModality.WindowModal)

        recording = ProjectRecordingSettings.model_validate(configuration)
        self._ports = {
            "serial": resolve_serial_port(triggers.serial_port),
            "brainproducts_triggerbox": recording.brainproducts_serial_port,
        }
        self._baudrate = triggers.baudrate
        self._pulse_width_ms = recording.brainproducts_pulse_width_ms
        self._parallel_address = recording.brainproducts_parallel_address
        self._output = ""
        self._task: BackgroundTask | None = None
        self._checked_port: tuple[str, str] | None = None
        self._pending_error: tuple[str, Exception, str | None] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        form = QFormLayout()
        self.output_combo = QComboBox(self)
        self.output_combo.setPlaceholderText("Select an output")
        self.output_combo.addItem("BioSemi USB Trigger Interface", "serial")
        self.output_combo.addItem("BrainVision (TriggerBox / Plus)", "brainproducts_triggerbox")
        self.output_combo.addItem("BrainVision (actiCHamp parallel port)", "brainproducts_parallel")
        self.output_combo.setAccessibleName("Recording output")
        form.addRow("Recording output", self.output_combo)
        self.port_edit = QLineEdit(self)
        self._port_label = QLabel(self)
        self._port_label.setBuddy(self.port_edit)
        port_row = QHBoxLayout()
        port_row.addWidget(self.port_edit, 1)
        self.check_port_button = QPushButton("Check Port", self)
        self.check_port_button.setAutoDefault(False)
        self.check_port_button.setToolTip("Check port access without sending a trigger.")
        mark_secondary_action(self.check_port_button)
        self.check_port_button.clicked.connect(self._check_port)
        port_row.addWidget(self.check_port_button)
        form.addRow(self._port_label, port_row)
        layout.addLayout(form)

        layout.addWidget(QLabel("Press 0–9 to send the matching trigger code.", self))
        codes = QHBoxLayout()
        self.digit_buttons = tuple(QPushButton(str(code), self) for code in range(10))
        for code, button in enumerate(self.digit_buttons):
            button.setAccessibleName(f"Send trigger {code}")
            button.setAutoDefault(False)
            button.setAutoRepeat(False)
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            button.setMinimumWidth(36)
            button.clicked.connect(lambda _checked=False, code=code: self._send(code))
            codes.addWidget(button, 1)
        self.digit_buttons[0].setToolTip("0 writes idle and may not appear as a marker.")
        layout.addLayout(codes)

        self.status_label = QLabel(self)
        self.status_label.setAccessibleName("Trigger status")
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.status_label.setMinimumHeight(4 * self.status_label.fontMetrics().lineSpacing())
        layout.addWidget(self.status_label, 1)

        self.close_button = QPushButton("Close", self)
        self.close_button.setAutoDefault(False)
        mark_secondary_action(self.close_button)
        self.close_button.clicked.connect(self.reject)
        layout.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignRight)

        default_output = recording.recording_backend
        if default_output == "biosemi_active_three":
            default_output = "serial"
        self.output_combo.setCurrentIndex(self.output_combo.findData(default_output))
        self.output_combo.currentIndexChanged.connect(self._select_output)
        self.port_edit.textChanged.connect(self._port_changed)
        self.port_edit.returnPressed.connect(self._check_port)
        self._select_output()
        apply_dialog_theme(self)
        for widget in (
            self, self.output_combo, self.port_edit, self.check_port_button,
            *self.digit_buttons, self.close_button,
        ):
            widget.installEventFilter(self)
        initial_focus: QWidget = self.output_combo
        if self.digit_buttons[1].isEnabled():
            initial_focus = self.digit_buttons[1]
        elif self.port_edit.isEnabled() and not self.port_edit.isReadOnly():
            initial_focus = self.port_edit
        initial_focus.setFocus()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if not event.spontaneous():
            self._check_port()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if isinstance(event, QKeyEvent) and event.type() == QEvent.Type.KeyPress:
            code = event.key() - Qt.Key.Key_0
            editing_port = self.port_edit.hasFocus() and not self.port_edit.isReadOnly()
            if (
                0 <= code <= 9 and not editing_port and not self.output_combo.view().isVisible()
                and event.modifiers() in (
                    Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.KeypadModifier,
                )
            ):
                if not event.isAutoRepeat():
                    self._send(code)
                return True
        return super().eventFilter(watched, event)

    def reject(self) -> None:
        if self._task is None:
            super().reject()

    @Slot()
    def _select_output(self) -> None:
        if self._output in self._ports:
            self._ports[self._output] = self.port_edit.text()
        self._output = self.output_combo.currentData() or ""
        parallel = self._output == "brainproducts_parallel"
        endpoint = "Parallel address" if parallel else "COM port"
        self._port_label.setText(endpoint)
        self.port_edit.setAccessibleName(endpoint)
        self.port_edit.setReadOnly(parallel)
        self.port_edit.setToolTip("" if parallel else "Press Enter to check the COM port.")
        self.port_edit.setText(
            f"0x{self._parallel_address:X}" if parallel and self._parallel_address is not None
            else self._ports.get(self._output, "")
        )
        self._port_changed()
        if self.isVisible():
            self._check_port()

    def _configuration_issue(self) -> str:
        if not self._output:
            return "Choose a recording output."
        if self._output == "brainproducts_parallel" and self._parallel_address is None:
            return "Set the parallel I/O address in Settings > Recording > Recording Setup."
        if self._output in self._ports:
            port = self.port_edit.text().strip()
            if not port:
                return "Enter the COM port for this output."
            if self._checked_port != (self._output, port):
                return "Check the COM port before sending a trigger."
        return ""

    @Slot()
    def _port_changed(self) -> None:
        self._checked_port = None
        self.status_label.setText(self._configuration_issue())
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        idle = self._task is None
        self.output_combo.setEnabled(idle)
        self.port_edit.setEnabled(idle and bool(self._output))
        serial = self._output in self._ports
        self.check_port_button.setVisible(serial)
        self.check_port_button.setEnabled(idle and serial and bool(self.port_edit.text().strip()))
        self.close_button.setEnabled(idle)
        can_send = idle and not self._configuration_issue()
        for button in self.digit_buttons:
            button.setEnabled(can_send)

    @Slot()
    def _check_port(self) -> None:
        output, port = self._output, self.port_edit.text().strip()
        if self._task is not None or output not in self._ports or not port:
            return
        baudrate = self._baudrate if output == "serial" else 2_000_000
        self._checked_port = None

        def check() -> tuple[str, str]:
            result = check_serial_port_access(port, baudrate=baudrate)
            if not result.accessible:
                raise RuntimeError(result.access_error)
            return output, port

        self._start_task(check, f"Checking {port}…", checking_port=True)

    def _send(self, code: int) -> None:
        if self._task is not None or self._configuration_issue():
            return
        output = self._output
        port = self.port_edit.text().strip()
        address = self._parallel_address
        baudrate = self._baudrate
        pulse_width_ms = self._pulse_width_ms

        def send() -> int:
            backend: TriggerBackend
            if output == "serial":
                backend = SerialBackend(port=port, baudrate=baudrate)
            elif output == "brainproducts_triggerbox":
                backend = BrainProductsTriggerBoxBackend(port=port, pulse_width_ms=pulse_width_ms)
            elif output == "brainproducts_parallel" and address is not None:
                backend = ParallelPortBackend(address, pulse_width_ms=pulse_width_ms)
            else:
                raise ValueError("Choose a configured recording output.")
            send_test_trigger(backend, code)
            return code

        self._start_task(send, f"Sending trigger {code}…")

    def _start_task(
        self, callback: Callable[[], object], status: str, *, checking_port: bool = False,
    ) -> None:
        task = BackgroundTask(parent_widget=self, callback=callback)
        self._task = task
        self.status_label.setText(status)
        self._refresh_controls()
        if checking_port:
            task.succeeded.connect(self._show_port_access_success)
            task.failed.connect(self._remember_port_access_error)
        else:
            task.succeeded.connect(self._show_send_success)
            task.failed.connect(self._remember_send_error)
        task.finished.connect(self._finish_task)
        try:
            task.start()
        except RuntimeError as error:
            LOGGER.warning("Trigger Tester worker could not start: %s", error)
            self.status_label.setText(
                "Studio could not start the operation. Restart Studio and retry."
            )
            task.deleteLater()
            self._finish_task()

    @Slot(object)
    def _show_port_access_success(self, endpoint: object) -> None:
        current = (self._output, self.port_edit.text().strip())
        if endpoint == current:
            self._checked_port = current
        self.status_label.setText(self._configuration_issue())

    @Slot(object)
    def _remember_port_access_error(self, error: object) -> None:
        failure = _coerce_exception(error)
        port = self.port_edit.text().strip()
        if self._output == "serial":
            title = "BioSemi Serial Port Error"
            message = biosemi_port_error_message(port, failure)
        else:
            title = "TriggerBox Serial Port Error"
            if isinstance(failure, (ImportError, SerialPortAccessError)):
                message = (
                    "Studio could not check the TriggerBox port because serial support is "
                    "unavailable. Repair or reinstall Studio, then try again."
                )
            else:
                message = triggerbox_port_error_message(port, failure)
        self.status_label.setText(self._configuration_issue())
        self._pending_error = (title, failure, message)

    @Slot(object)
    def _show_send_success(self, code: object) -> None:
        self.status_label.setText(
            "Studio wrote 0 (idle). It may not appear as a marker." if code == 0
            else f"Studio sent trigger {code}. Check the recording software."
        )

    @Slot(object)
    def _remember_send_error(self, error: object) -> None:
        self._checked_port = None
        self.status_label.setText(self._configuration_issue())
        self._pending_error = ("Send Test Trigger", _coerce_exception(error), None)

    @Slot()
    def _finish_task(self) -> None:
        self._task = None
        error, self._pending_error = self._pending_error, None
        self._refresh_controls()
        if self.digit_buttons[1].isEnabled():
            self.digit_buttons[1].setFocus()
        elif self.check_port_button.isEnabled():
            self.check_port_button.setFocus()
        if error is not None and self.isVisible():
            title, failure, message = error
            _show_error_dialog(self, title, failure, message=message)
