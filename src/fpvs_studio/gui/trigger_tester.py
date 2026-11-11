"""Send operator-selected digits through the existing hardware adapters."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QSignalBlocker, Qt, Slot
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
from fpvs_studio.triggers.biosemi_discovery import (
    biosemi_reconnected_port,
    discover_biosemi_ports,
    enumerate_com_ports,
)
from fpvs_studio.triggers.biosemi_errors import biosemi_port_error_message
from fpvs_studio.triggers.brainproducts_backend import BrainProductsTriggerBoxBackend
from fpvs_studio.triggers.brainproducts_discovery import (
    TriggerBoxDiscoveryError,
    discover_triggerbox_ports,
)
from fpvs_studio.triggers.brainproducts_errors import (
    triggerbox_failure_reason,
    triggerbox_port_error_message,
)
from fpvs_studio.triggers.manual import send_test_trigger
from fpvs_studio.triggers.parallel_backend import ParallelPortBackend
from fpvs_studio.triggers.serial_backend import SerialBackend, resolve_serial_port
from fpvs_studio.triggers.serial_port_access import SerialPortAccessError, check_serial_port_access

LOGGER = logging.getLogger(__name__)


class _PortCheckError(RuntimeError):
    """A connection check with recovery guidance for the operator."""


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
        self._disconnected_ports: frozenset[str] | None = None
        self._reconnected_port: str | None = None
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
        self.check_port_button.setToolTip("Check the connection without sending a trigger.")
        mark_secondary_action(self.check_port_button)
        self.check_port_button.clicked.connect(self._check_port)
        port_row.addWidget(self.check_port_button)
        self.manual_port_button = QPushButton(self)
        self.manual_port_button.setCheckable(True)
        self.manual_port_button.setAutoDefault(False)
        mark_secondary_action(self.manual_port_button)
        self.manual_port_button.toggled.connect(self._manual_port_toggled)
        port_row.addWidget(self.manual_port_button)
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

        actions = QHBoxLayout()
        self.find_port_button = QPushButton("Find Port…", self)
        self.find_port_button.setCheckable(True)
        self.find_port_button.setAutoDefault(False)
        self.find_port_button.setToolTip(
            "Find the BioSemi interface by reconnecting its USB cable."
        )
        mark_secondary_action(self.find_port_button)
        self.find_port_button.toggled.connect(self._find_port_toggled)
        actions.addWidget(self.find_port_button)
        actions.addStretch()
        self.close_button = QPushButton("Close", self)
        self.close_button.setAutoDefault(False)
        mark_secondary_action(self.close_button)
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)

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
            self.manual_port_button, *self.digit_buttons, self.find_port_button, self.close_button,
        ):
            widget.installEventFilter(self)
        initial_focus: QWidget = self.output_combo
        if self.digit_buttons[1].isEnabled():
            initial_focus = self.digit_buttons[1]
        elif (
            not self._automatic_connection
            and self.port_edit.isEnabled()
            and not self.port_edit.isReadOnly()
        ):
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

    @property
    def _automatic_connection(self) -> bool:
        return self._output in self._ports and not self.manual_port_button.isChecked()

    @Slot()
    def _select_output(self) -> None:
        if self._output in self._ports:
            self._ports[self._output] = self.port_edit.text()
        self._output = self.output_combo.currentData() or ""
        with QSignalBlocker(self.manual_port_button):
            self.manual_port_button.setChecked(False)
        self._stop_finding_port()
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
        if self.find_port_button.isChecked():
            return "Finish finding the BioSemi interface before sending a trigger."
        if self._automatic_connection:
            return "" if self._checked_port is not None else "Check the device connection."
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
        self.status_label.setToolTip("")
        self._refresh_controls()

    @Slot(bool)
    def _manual_port_toggled(self, manual: bool) -> None:
        self._port_changed()
        if manual:
            self.port_edit.setFocus()
        elif self.isVisible():
            self._check_port()

    @Slot(bool)
    def _find_port_toggled(self, finding: bool) -> None:
        self._disconnected_ports = None
        self._port_changed()
        if finding:
            self.status_label.setText(
                "Unplug the BioSemi USB Trigger Interface from this computer, "
                "then choose Scan Unplugged."
            )

    def _stop_finding_port(self) -> None:
        with QSignalBlocker(self.find_port_button):
            self.find_port_button.setChecked(False)
        self._disconnected_ports = None

    def _refresh_controls(self) -> None:
        idle = self._task is None
        automatic = self._automatic_connection
        serial = self._output in self._ports
        finding = self.find_port_button.isChecked()
        self.output_combo.setEnabled(idle)
        self.port_edit.setVisible(not (automatic or finding))
        self.port_edit.setEnabled(idle and bool(self._output))
        if serial:
            self._port_label.setText("Connection" if automatic or finding else "COM port")
        self.manual_port_button.setVisible(serial and not finding)
        self.manual_port_button.setEnabled(idle)
        self.manual_port_button.setText("Choose Port…" if automatic else "Use Automatic Detection")
        self.find_port_button.setVisible(self._output == "serial")
        self.find_port_button.setEnabled(idle)
        self.find_port_button.setText("Cancel Find" if finding else "Find Port…")
        self.check_port_button.setVisible(serial)
        if finding:
            check_label = (
                "Scan Unplugged" if self._disconnected_ports is None else "Find Connected Port"
            )
        else:
            check_label = "Check Connection" if automatic else "Check Port"
        self.check_port_button.setText(check_label)
        self.check_port_button.setEnabled(
            idle and serial and (automatic or finding or bool(self.port_edit.text().strip())),
        )
        self.close_button.setEnabled(idle)
        can_send = idle and not self._configuration_issue()
        for button in self.digit_buttons:
            button.setEnabled(can_send)

    @Slot()
    def _check_port(self) -> None:
        output, port = self._output, self.port_edit.text().strip()
        automatic = self._automatic_connection
        finding = self.find_port_button.isChecked()
        if (
            self._task is not None or output not in self._ports
            or not (automatic or finding or port)
        ):
            return
        biosemi = output == "serial"
        device = "BioSemi USB Trigger Interface" if biosemi else "BrainVision TriggerBox"
        baudrate = self._baudrate if biosemi else 2_000_000
        self._checked_port = None
        disconnected = self._disconnected_ports
        reconnected = self._reconnected_port if automatic and biosemi else None
        if finding and disconnected is None:
            self._start_task(
                enumerate_com_ports, "Scanning for serial ports…",
                succeeded=self._remember_disconnected_ports, failed=self._show_reconnect_scan_error,
            )
            return

        def check() -> tuple[str, str, bool]:
            target = port
            ports: tuple[str, ...]
            if disconnected is not None:
                try:
                    target = biosemi_reconnected_port(disconnected, enumerate_com_ports())
                except SerialPortAccessError as error:
                    raise _PortCheckError(str(error)) from error
                ports = (target,)
            elif reconnected is not None:
                ports = (reconnected,)
            else:
                try:
                    ports = discover_biosemi_ports() if biosemi else tuple(
                        candidate.port for candidate in discover_triggerbox_ports()
                    )
                except (SerialPortAccessError, TriggerBoxDiscoveryError) as error:
                    if automatic and not biosemi:
                        raise
                    LOGGER.warning("Cannot list %s ports: %s", device, error)
                    ports = ()

            if automatic and not finding:
                if not ports and not biosemi:
                    raise _PortCheckError(
                        "Studio could not find a BrainVision TriggerBox. Connect it and check "
                        "again, or choose its port manually.",
                    )
                if len(ports) > 1:
                    devices = "BioSemi interfaces" if biosemi else "BrainVision TriggerBoxes"
                    action = "Use Find Port or choose a port." if biosemi else "Choose a port."
                    raise _PortCheckError(
                        f"Studio found multiple {devices}. {action} "
                        f"Details: Detected ports: {', '.join(ports)}",
                    )
                if ports:
                    target = ports[0]
            elif not finding and ports and port.upper() not in ports:
                if len(ports) == 1:
                    raise _PortCheckError(
                        f"You selected {port.upper()}. Windows lists the {device} "
                        f"on {ports[0]}. Enter {ports[0]} or choose Use Automatic Detection.",
                    )
                raise _PortCheckError(
                    f"You selected {port.upper()}. Choose a listed {device} port. "
                    f"Details: Detected ports: {', '.join(ports)}",
                )
            try:
                result = check_serial_port_access(target, baudrate=baudrate)
            except SerialPortAccessError as error:
                if biosemi and ports:
                    guidance = biosemi_port_error_message(target.upper(), error)
                    raise _PortCheckError(f"{guidance} Details: {error}") from error
                raise
            if result.accessible:
                return output, target, bool(ports)
            if biosemi and not ports:
                raise RuntimeError(result.access_error)
            port_name = target.upper()
            LOGGER.warning(
                "%s access check failed on %s: %s", device, port_name, result.access_error,
            )
            format_error = biosemi_port_error_message if biosemi else triggerbox_port_error_message
            guidance = format_error(port_name, result.access_error)
            if finding:
                guidance = f"Studio found the reconnected interface on {port_name}. {guidance}"
            elif reconnected is not None:
                guidance = f"The reconnect identified the interface on {port_name}. {guidance}"
            elif ports:
                guidance = f"Windows lists the {device} on {port_name}. {guidance}"
            elif triggerbox_failure_reason(result.access_error) == "missing":
                guidance = (
                    f"Windows could not find the selected port {port_name}. Connect the TriggerBox "
                    "and check its port in Device Manager."
                )
            raise _PortCheckError(f"{guidance} Details: {result.access_error}")

        status = f"Connecting to the {device}…" if automatic or finding else f"Checking {port}…"
        self._start_task(
            check, status,
            succeeded=self._show_port_access_success, failed=self._remember_port_access_error,
        )

    @Slot(object)
    def _remember_disconnected_ports(self, ports: frozenset[str]) -> None:
        self._disconnected_ports = ports
        self.status_label.setText(
            "Reconnect the BioSemi USB Trigger Interface, then choose Find Connected Port."
        )

    @Slot(object)
    def _show_reconnect_scan_error(self, error: object) -> None:
        self.status_label.setText(
            "Studio could not list serial ports. Check Device Manager and retry."
        )
        self.status_label.setToolTip(str(error))

    def _send(self, code: int) -> None:
        if self._task is not None or self._configuration_issue():
            return
        output = self._output
        port = self._checked_port[1] if self._checked_port is not None else ""
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

        self._start_task(
            send, f"Sending trigger {code}…",
            succeeded=self._show_send_success, failed=self._remember_send_error,
        )

    def _start_task(
        self, callback: Callable[[], object], status: str, *,
        succeeded: Callable[..., None], failed: Callable[..., None],
    ) -> None:
        task = BackgroundTask(parent_widget=self, callback=callback)
        self._task = task
        self.status_label.setText(status)
        self.status_label.setToolTip("")
        self._refresh_controls()
        task.succeeded.connect(succeeded)
        task.failed.connect(failed)
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
    def _show_port_access_success(self, result: tuple[str, str, bool]) -> None:
        output, port, identified = result
        endpoint = (output, port)
        if (
            output == self._output
            and (self._automatic_connection or self.find_port_button.isChecked())
        ):
            if self.find_port_button.isChecked():
                self._reconnected_port = port
            self._stop_finding_port()
            with QSignalBlocker(self.manual_port_button):
                self.manual_port_button.setChecked(not identified)
            self._checked_port = endpoint
            if identified:
                device, recorder = (
                    ("BioSemi USB Trigger Interface", "ActiView") if output == "serial"
                    else ("BrainVision TriggerBox", "Recorder")
                )
                self.status_label.setText(
                    f"FPVS Studio has successfully connected to the {device}."
                )
                self.status_label.setToolTip(
                    f"Send a test trigger to verify receipt in {recorder}.",
                )
            else:
                self.status_label.setText(self._configuration_issue())
            return
        current = (self._output, self.port_edit.text().strip())
        if endpoint == current:
            self._checked_port = current
        self.status_label.setText(self._configuration_issue())

    @Slot(object)
    def _remember_port_access_error(self, error: object) -> None:
        failure = _coerce_exception(error)
        if isinstance(failure, (_PortCheckError, TriggerBoxDiscoveryError)):
            message, _, details = str(failure).partition("Details:")
            self.status_label.setText(message.strip())
            self.status_label.setToolTip(details.strip())
            return
        if self._output == "brainproducts_triggerbox" or self.find_port_button.isChecked():
            if isinstance(failure, (ImportError, SerialPortAccessError)):
                self.status_label.setText(
                    "Studio could not check the connection because serial support is "
                    "unavailable. Repair or reinstall Studio, then try again."
                )
            else:
                self.status_label.setText("Studio could not check the connection.")
            self.status_label.setToolTip(str(failure))
            return
        with QSignalBlocker(self.manual_port_button):
            self.manual_port_button.setChecked(True)
        port = self.port_edit.text().strip()
        self.status_label.setText(self._configuration_issue())
        self._pending_error = (
            "BioSemi Serial Port Error", failure, biosemi_port_error_message(port, failure),
        )

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
