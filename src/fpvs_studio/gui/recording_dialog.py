"""Project recording preferences and Recorder launch-check guidance."""

from __future__ import annotations

import logging
from typing import cast

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QIntValidator, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.brainproducts import (
    AMPLIFIER_LABELS,
    minimum_pulse_width_ms,
    supported_sampling_rates_hz,
)
from fpvs_studio.core.models import ProjectRecordingSettings
from fpvs_studio.gui.biosemi_port_selector import BioSemiPortSelector
from fpvs_studio.gui.components import (
    DialogHeader,
    apply_dialog_theme,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.parallel_port_selector import ParallelPortSelector
from fpvs_studio.gui.update_lifecycle import UpdateJob, UpdateTaskResult, update_lifecycle
from fpvs_studio.runtime.recording import (
    UNICORN_VALIDATION_NOTE,
    recording_backend_label,
    validate_recording_configuration,
)
from fpvs_studio.triggers.brainproducts_discovery import (
    TriggerBoxPortCandidate,
    discover_triggerbox_ports,
)
from fpvs_studio.triggers.serial_backend import resolve_serial_port

_LOGGER = logging.getLogger(__name__)

RECORDING_HARDWARE_CHOICES = (
    ("BioSemi ActiveTwo", "serial"),
    ("BioSemi ActiveThree", "biosemi_active_three"),
    ("Brain Products / BrainVision (TriggerBox/Plus)", "brainproducts_triggerbox"),
    ("Brain Products / BrainVision (Parallel port)", "brainproducts_parallel"),
    ("Unicorn Hybrid Black", "unicorn_udp"),
)


class DefaultRecordingHardwareDialog(QDialog):
    """Choose this computer's hardware before Welcome, at 640x300."""

    def __init__(self, parent: QWidget | None = None, *, error_message: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Default EEG Hardware")
        self.setMinimumSize(640, 300)
        self.resize(self.minimumSize())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(DialogHeader(
            "Default EEG hardware",
            "Please select your default EEG hardware. You can change this choice later.",
            parent=self,
        ))
        self.hardware_combo = QComboBox(self)
        self.hardware_combo.setAccessibleName("Default EEG hardware")
        self.hardware_combo.addItem("Select EEG hardware", None)
        for label, backend in RECORDING_HARDWARE_CHOICES:
            self.hardware_combo.addItem(label, backend)
        layout.addWidget(self.hardware_combo)
        self.error_label = QLabel(error_message, self)
        self.error_label.setWordWrap(True)
        self.error_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.error_label)
        layout.addStretch(1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.exit_button = QPushButton("Exit FPVS Studio", self)
        self.exit_button.setAutoDefault(False)
        mark_secondary_action(self.exit_button)
        self.exit_button.clicked.connect(self.reject)
        buttons.addWidget(self.exit_button)
        self.continue_button = QPushButton("Continue", self)
        mark_primary_action(self.continue_button)
        self.continue_button.setEnabled(False)
        self.continue_button.clicked.connect(self.accept)
        buttons.addWidget(self.continue_button)
        layout.addLayout(buttons)
        self.hardware_combo.currentIndexChanged.connect(
            lambda: self.continue_button.setEnabled(self.selected_backend is not None),
        )
        apply_dialog_theme(self)

    @property
    def selected_backend(self) -> str | None:
        value = self.hardware_combo.currentData()
        return value if (
            isinstance(value, str)
            and value in {backend for _, backend in RECORDING_HARDWARE_CHOICES}
        ) else None

    def accept(self) -> None:
        if self.selected_backend is not None:
            super().accept()


def recording_preference_summary(configuration: dict[str, object]) -> str:
    """Describe a saved choice while preserving actionable invalid-state feedback."""

    try:
        backend = validate_recording_configuration(configuration)
        label = recording_backend_label(configuration)
    except ValueError:
        return "Recording setup invalid. Open Recording Setup to check the device and EEG settings."
    if backend == "unicorn_udp":
        return f"{label} — Recorder check before launch"
    if configuration.get("recording_backend") is None:
        return f"{label} (legacy project serial settings)"
    return label


class RecordingSetupDialog(QDialog):
    """Stage project recording hardware and endpoint settings until Apply."""

    def __init__(
        self, configuration: dict[str, object], parent: QWidget | None = None,
        *, computer_default: bool = False, biosemi_serial_port: str | None = "COM3",
        biosemi_serial_baudrate: int = 115200,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("recording_setup_dialog")
        self.setWindowTitle("Default Recording Setup" if computer_default else "Recording Setup")
        self.setMinimumSize(700, 640)
        self.resize(self.minimumSize())
        self._configuration = dict(configuration)
        self._computer_default = computer_default
        self._accepted_biosemi_serial_port = resolve_serial_port(biosemi_serial_port)
        self._port_detection_job: UpdateJob | None = None
        self._detection_started = False
        self._discovery_dismissed = False
        self._port_detection_candidates: tuple[TriggerBoxPortCandidate, ...] | None = None
        self._port_access_checked = False
        self._manual_port_override = (
            configuration.get("brainproducts_serial_port", "COM3") != "COM3"
        )
        # Inactive invalid edits remain visible when returning to that device, but
        # cannot corrupt an otherwise valid recording choice when applying another.
        udp_port = configuration.get("unicorn_udp_port", 1000)
        self._valid_udp_port = (
            udp_port if type(udp_port) is int and 1 <= udp_port <= 65535 else 1000
        )
        triggerbox_port = configuration.get("brainproducts_serial_port", "COM3")
        self._valid_triggerbox_port = (
            triggerbox_port.strip()
            if isinstance(triggerbox_port, str) and triggerbox_port.strip() else "COM3"
        )
        parallel_address = configuration.get("brainproducts_parallel_address")
        self._valid_parallel_address = (
            parallel_address
            if type(parallel_address) is int and 1 <= parallel_address <= 65535 else None
        )
        pulse_width = configuration.get("brainproducts_pulse_width_ms", 10)
        self._valid_pulse_width = (
            pulse_width if type(pulse_width) is int and 1 <= pulse_width <= 1000 else 10
        )
        self._valid_amplifier = configuration.get("brainproducts_amplifier")
        self._valid_sampling_rate = configuration.get("brainproducts_sampling_rate_hz")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(DialogHeader(
            "Default Recording Setup" if computer_default else "Recording Setup",
            ("For this computer. Projects can override this choice." if computer_default
             else "For this project. Apply saves the selection."),
            parent=self,
        ))
        self.backend_combo = QComboBox(self)
        self.backend_combo.setObjectName("recording_backend_combo")
        self.backend_combo.addItem("BioSemi ActiveTwo (serial)", "serial")
        self.backend_combo.addItem("BioSemi ActiveThree", "biosemi_active_three")
        self.backend_combo.addItem(
            "Brain Products / BrainVision (TriggerBox/Plus)", "brainproducts_triggerbox",
        )
        self.backend_combo.addItem(
            "Brain Products / BrainVision (Parallel port)", "brainproducts_parallel",
        )
        self.backend_combo.addItem("Unicorn Recorder UDP", "unicorn_udp")
        backend = configuration.get("recording_backend") or "serial"
        index = self.backend_combo.findData(backend)
        if index < 0:
            self.backend_combo.addItem("Invalid saved choice — select a recording device", backend)
            index = self.backend_combo.count() - 1
        self.backend_combo.setCurrentIndex(index)
        self.backend_combo.setToolTip(str(backend) if backend is not None else "Legacy serial")
        self.port_edit = QLineEdit(str(configuration.get("unicorn_udp_port", 1000)), self)
        self.port_edit.setObjectName("unicorn_udp_port_edit")
        self.port_edit.setValidator(QIntValidator(1, 65535, self.port_edit))
        self.port_edit.setAccessibleName("Unicorn Recorder UDP port")
        self.port_edit.setToolTip("Match Recorder's UDP input port; an integer from 1 to 65535.")
        self.biosemi_port_selector = BioSemiPortSelector(
            biosemi_serial_port, biosemi_serial_baudrate, self,
        )
        self.parallel_port_selector = ParallelPortSelector(parallel_address, self)
        self.brainproducts_parallel_combo = self.parallel_port_selector.combo
        self.brainproducts_parallel_edit = self.parallel_port_selector.edit
        self.detect_parallel_ports_button = self.parallel_port_selector.detect_button
        self.brainproducts_port_combo = QComboBox(self)
        self.brainproducts_port_combo.setEditable(True)
        self.brainproducts_port_combo.setAccessibleName("Brain Products TriggerBox COM port")
        self.brainproducts_port_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.brainproducts_port_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon,
        )
        self.brainproducts_port_combo.setMinimumContentsLength(8)
        self.brainproducts_port_combo.setEditText(
            str(configuration.get("brainproducts_serial_port", "COM3")),
        )
        self.brainproducts_port_edit = cast(QLineEdit, self.brainproducts_port_combo.lineEdit())
        self.brainproducts_port_edit.setObjectName("brainproducts_serial_port_edit")
        self.brainproducts_port_edit.setAccessibleName("Brain Products TriggerBox COM port")
        self.brainproducts_port_edit.setToolTip(
            "Detected ports remain editable. You can also enter the COM port from Device Manager. "
            "Install the vendor driver and close other programs using that port. "
            "Studio uses the vendor's fixed 2,000,000 baud USB protocol.",
        )
        self.brainproducts_port_row = QWidget(self)
        port_layout = QHBoxLayout(self.brainproducts_port_row)
        port_layout.setContentsMargins(0, 0, 0, 0)
        port_layout.addWidget(self.brainproducts_port_combo, 1)
        self.detect_ports_button = QPushButton("Detect", self.brainproducts_port_row)
        self.detect_ports_button.setAutoDefault(False)
        self.detect_ports_button.setAccessibleName("Detect TriggerBox COM ports")
        self.detect_ports_button.setToolTip(
            "Refresh TriggerBox ports and check access by opening and closing recognized ports. "
            "No marker bytes are sent.",
        )
        mark_secondary_action(self.detect_ports_button)
        port_layout.addWidget(self.detect_ports_button)
        self.brainproducts_amplifier_combo = QComboBox(self)
        self.brainproducts_amplifier_combo.setAccessibleName("Brain Products EEG amplifier")
        self.brainproducts_amplifier_combo.addItem("Choose amplifier", None)
        for value, label in AMPLIFIER_LABELS.items():
            self.brainproducts_amplifier_combo.addItem(label, value)
        amplifier = configuration.get("brainproducts_amplifier")
        amplifier_index = self.brainproducts_amplifier_combo.findData(amplifier)
        if amplifier_index < 0:
            self.brainproducts_amplifier_combo.addItem(
                "Invalid saved amplifier — choose again", amplifier,
            )
            amplifier_index = self.brainproducts_amplifier_combo.count() - 1
        self.brainproducts_amplifier_combo.setCurrentIndex(amplifier_index)
        self.brainproducts_sampling_rate_combo = QComboBox(self)
        self.brainproducts_sampling_rate_combo.setAccessibleName("EEG sampling rate in Hz")
        self.brainproducts_sampling_rate_combo.setToolTip(
            "Match the EEG sampling rate selected in BrainVision Recorder. "
            "This is independent of the display refresh rate and FPVS image rate.",
        )
        self._populate_sampling_rates(configuration.get("brainproducts_sampling_rate_hz"))
        self.brainproducts_pulse_edit = QLineEdit(
            str(configuration.get("brainproducts_pulse_width_ms", 10)), self,
        )
        self.brainproducts_pulse_edit.setObjectName("brainproducts_pulse_width_edit")
        self.brainproducts_pulse_edit.setValidator(
            QIntValidator(1, 1000, self.brainproducts_pulse_edit),
        )
        self.brainproducts_pulse_edit.setAccessibleName("Brain Products trigger pulse width in ms")
        self.brainproducts_pulse_edit.setToolTip(
            "1–1000 ms. Choose high and low intervals for the amplifier sample rate: "
            "for example, at least 8 ms at 250 Hz for actiCHamp/LiveAmp, or 20 ms at "
            "100 Hz for actiCHamp. Studio requires at least this pulse width between "
            "pulses at zero; event spacing must exceed twice the pulse width. "
            "Verify recorded markers and physical timing with the actual amplifier.",
        )
        self.endpoint_label = QLabel("Host: 127.0.0.1 (this computer only)", self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setSpacing(10)
        form.addRow("Recording device", self.backend_combo)
        self.unicorn_port_label = QLabel("Unicorn UDP port", self)
        form.addRow(self.unicorn_port_label, self.port_edit)
        self.biosemi_port_label = QLabel("BioSemi serial port", self)
        self.biosemi_port_label.setBuddy(self.biosemi_port_selector.combo)
        form.addRow(self.biosemi_port_label, self.biosemi_port_selector)
        self.brainproducts_port_label = QLabel("TriggerBox COM port", self)
        self.brainproducts_parallel_label = QLabel("Parallel I/O address (hex)", self)
        self.brainproducts_parallel_label.setBuddy(self.brainproducts_parallel_edit)
        self.brainproducts_pulse_label = QLabel("Trigger pulse width (ms)", self)
        self.brainproducts_amplifier_label = QLabel("EEG amplifier", self)
        self.brainproducts_sampling_rate_label = QLabel("EEG sampling rate (Hz)", self)
        form.addRow(self.brainproducts_port_label, self.brainproducts_port_row)
        form.addRow(self.brainproducts_parallel_label, self.parallel_port_selector)
        form.addRow(self.brainproducts_amplifier_label, self.brainproducts_amplifier_combo)
        form.addRow(self.brainproducts_sampling_rate_label, self.brainproducts_sampling_rate_combo)
        form.addRow(self.brainproducts_pulse_label, self.brainproducts_pulse_edit)
        layout.addLayout(form)
        layout.addWidget(self.endpoint_label)
        self.detection_status_label = QLabel(self)
        self.detection_status_label.setWordWrap(True)
        self.detection_status_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.detection_status_label)
        self.pulse_requirement_label = QLabel(self)
        self.pulse_requirement_label.setWordWrap(True)
        self.pulse_requirement_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.pulse_requirement_label)
        self.guidance_label = QLabel(self)
        self.guidance_label.setWordWrap(True)
        self.guidance_label.setTextFormat(Qt.TextFormat.PlainText)
        self.guidance_label.setObjectName("recording_setup_guidance")
        layout.addWidget(self.guidance_label)
        self.error_label = QLabel(self)
        self.error_label.setWordWrap(True)
        self.error_label.setTextFormat(Qt.TextFormat.PlainText)
        self.error_label.setObjectName("recording_setup_error")
        layout.addWidget(self.error_label)
        layout.addStretch(1)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.apply_button = self.button_box.button(QDialogButtonBox.StandardButton.Apply)
        mark_primary_action(self.apply_button)
        mark_secondary_action(self.button_box.button(QDialogButtonBox.StandardButton.Cancel))
        self.apply_button.clicked.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        self.backend_combo.currentIndexChanged.connect(self._backend_changed)
        self.port_edit.textChanged.connect(self._refresh)
        self.biosemi_port_selector.port_changed.connect(self._refresh)
        self.parallel_port_selector.address_changed.connect(self._refresh)
        self.brainproducts_port_edit.textChanged.connect(self._refresh)
        self.brainproducts_port_edit.textChanged.connect(self._refresh_port_detection_status)
        self.brainproducts_pulse_edit.textChanged.connect(self._refresh)
        self.brainproducts_amplifier_combo.currentIndexChanged.connect(self._amplifier_changed)
        self.brainproducts_sampling_rate_combo.currentIndexChanged.connect(self._refresh)
        self.detect_ports_button.clicked.connect(self._detect_ports)
        self.brainproducts_port_edit.textEdited.connect(self._manual_port_edited)
        self.brainproducts_port_combo.activated.connect(self._manual_port_edited)
        self.finished.connect(self._cancel_port_detection)
        self.finished.connect(self.biosemi_port_selector.cancel)
        self.finished.connect(self.parallel_port_selector.cancel)
        self._refresh()
        apply_dialog_theme(self)

    def _populate_sampling_rates(self, selected: object = None) -> None:
        amplifier = self._selected_amplifier()
        self.brainproducts_sampling_rate_combo.blockSignals(True)
        self.brainproducts_sampling_rate_combo.clear()
        self.brainproducts_sampling_rate_combo.addItem("Choose sampling rate", None)
        if amplifier is not None and amplifier in AMPLIFIER_LABELS:
            for rate in supported_sampling_rates_hz(amplifier):
                self.brainproducts_sampling_rate_combo.addItem(str(rate), rate)
        index = self.brainproducts_sampling_rate_combo.findData(selected)
        if index < 0:
            self.brainproducts_sampling_rate_combo.addItem(
                "Invalid saved rate — choose again", selected,
            )
            index = self.brainproducts_sampling_rate_combo.count() - 1
        self.brainproducts_sampling_rate_combo.setCurrentIndex(index)
        self.brainproducts_sampling_rate_combo.blockSignals(False)

    def _selected_amplifier(self) -> str | None:
        if self.backend_combo.currentData() == "brainproducts_parallel":
            return "actichamp"
        return cast(str | None, self.brainproducts_amplifier_combo.currentData())

    def _backend_changed(self) -> None:
        self._populate_sampling_rates(self.brainproducts_sampling_rate_combo.currentData())
        self._refresh()

    def _amplifier_changed(self) -> None:
        rate = self.brainproducts_sampling_rate_combo.currentData()
        amplifier = self._selected_amplifier()
        rates = (supported_sampling_rates_hz(amplifier)
                 if amplifier is not None and amplifier in AMPLIFIER_LABELS else ())
        self._populate_sampling_rates(rate if rate in rates else None)
        self._refresh()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._discovery_dismissed = False
        self._maybe_detect_ports()

    def _maybe_detect_ports(self) -> None:
        if (self.isVisible() and not self._detection_started
                and self.backend_combo.currentData() == "brainproducts_triggerbox"):
            self._start_port_detection(check_access=False)

    def _manual_port_edited(self, _value: object = None) -> None:
        self._manual_port_override = True
        self._refresh_port_detection_status()

    def _detect_ports(self) -> None:
        self._start_port_detection(check_access=True)

    def _start_port_detection(self, *, check_access: bool) -> None:
        if self._port_detection_job is not None or self._discovery_dismissed:
            return
        self._detection_started = True
        for index, candidate in enumerate(self._port_detection_candidates or ()):
            self.brainproducts_port_combo.setItemData(
                index, candidate.description, Qt.ItemDataRole.ToolTipRole,
            )
        self._port_detection_candidates = None
        self._port_access_checked = check_access
        self.detect_ports_button.setEnabled(False)
        self.detection_status_label.setText(
            "Checking TriggerBox port access…" if check_access else "Detecting TriggerBox ports…",
        )
        self.detection_status_label.setToolTip("")
        self.detection_status_label.setAccessibleDescription("")
        try:
            lifecycle = update_lifecycle()
            self._port_detection_job = lifecycle.start_task(
                lambda _progress, cancel: discover_triggerbox_ports(
                    check_access=check_access, cancel_event=cancel,
                ),
            )
        except RuntimeError as exc:
            self._port_detection_finished(UpdateTaskResult(error=exc))
            return
        self._port_detection_job.finished.connect(self._port_detection_finished)

    @Slot(object)
    def _port_detection_finished(self, value: object) -> None:
        self._port_detection_job = None
        if self._discovery_dismissed:
            return
        self.detect_ports_button.setEnabled(True)
        result = cast(UpdateTaskResult, value)
        if result.cancelled:
            self.detection_status_label.setText("Detection cancelled. Enter a COM port or retry.")
            return
        if result.error is not None:
            _LOGGER.warning("TriggerBox port detection failed: %s", result.error)
            self.detection_status_label.setText(
                "Port detection failed. Retry or enter the COM port.",
            )
            self.detection_status_label.setToolTip(str(result.error))
            self.detection_status_label.setAccessibleDescription(str(result.error))
            return
        candidates = cast(tuple[TriggerBoxPortCandidate, ...], result.value)
        self._port_detection_candidates = candidates
        previous = self.brainproducts_port_edit.text()
        self.brainproducts_port_combo.blockSignals(True)
        self.brainproducts_port_edit.blockSignals(True)
        self.brainproducts_port_combo.clear()
        for candidate in candidates:
            self.brainproducts_port_combo.addItem(candidate.port)
            self.brainproducts_port_combo.setItemData(
                self.brainproducts_port_combo.count() - 1, self._port_candidate_details(candidate),
                Qt.ItemDataRole.ToolTipRole,
            )
        port = previous
        if not self._manual_port_override:
            if len(candidates) == 1:
                port = candidates[0].port
            elif len(candidates) > 1:
                port = ""
        self.brainproducts_port_combo.setEditText(port)
        self.brainproducts_port_edit.blockSignals(False)
        self.brainproducts_port_combo.blockSignals(False)
        self._refresh_port_detection_status()
        self._refresh()

    @staticmethod
    def _port_candidate_details(candidate: TriggerBoxPortCandidate) -> str:
        details = candidate.description
        if candidate.accessible is True:
            details += "\nPort accessible."
        elif candidate.accessible is False:
            details += "\nPort unavailable."
            if candidate.access_error:
                details += f"\n{candidate.access_error}"
        return details

    def _refresh_port_detection_status(self) -> None:
        candidates = self._port_detection_candidates
        if candidates is None or self._discovery_dismissed:
            return
        details = "\n".join(
            f"{item.port}: {self._port_candidate_details(item)}" for item in candidates
        )
        self.detection_status_label.setToolTip(details)
        self.detection_status_label.setAccessibleDescription(details)
        port = self.brainproducts_port_edit.text().strip().upper()
        selected = next((item for item in candidates if item.port.upper() == port), None)
        if self._port_access_checked and candidates:
            if selected is not None:
                if selected.accessible is True:
                    text = f"{selected.port}: Port accessible."
                elif selected.accessible is False:
                    text = f"{selected.port}: Port unavailable. See details."
                else:
                    text = f"{selected.port}: Access was not checked."
            elif port:
                text = "Selected port was not checked. Choose a detected port or enter one."
            else:
                accessible = sum(item.accessible is True for item in candidates)
                unavailable = sum(item.accessible is False for item in candidates)
                text = (
                    f"{len(candidates)} ports checked: {accessible} accessible, "
                    f"{unavailable} unavailable. Choose a port."
                )
            self.detection_status_label.setText(text)
            return
        if len(candidates) == 1:
            text = f"Detected TriggerBox on {candidates[0].port}."
            if self._manual_port_override and port != candidates[0].port:
                text += " Manual port retained."
        elif candidates:
            text = "Several TriggerBoxes found. Choose a port or enter one."
        else:
            text = "No TriggerBox found. Connect it and retry, or enter its COM port."
        self.detection_status_label.setText(text)

    def _cancel_port_detection(self, _result: int) -> None:
        self._discovery_dismissed = True
        if self._port_detection_job is not None:
            self._port_detection_job.finished.disconnect(self._port_detection_finished)
            self._port_detection_job.cancel()
            self._port_detection_job = None
            self._detection_started = False
            self.detect_ports_button.setEnabled(True)

    @property
    def configuration(self) -> dict[str, object]:
        """Return only the accepted preference draft."""

        return dict(self._configuration)

    @property
    def biosemi_serial_port(self) -> str:
        """Return the accepted project port, retaining the original on Cancel."""

        return self._accepted_biosemi_serial_port

    def _draft(self) -> dict[str, object]:
        selected = self.backend_combo.currentData()
        brainproducts = selected in ("brainproducts_triggerbox", "brainproducts_parallel")
        text = self.port_edit.text()
        # Parse decimal digits only; preserve malformed saved text for validation.
        port: object = int(text) if len(text) <= 5 and text.isascii() and text.isdecimal() else text
        pulse_text = self.brainproducts_pulse_edit.text()
        pulse: object = (
            int(pulse_text)
            if len(pulse_text) <= 4 and pulse_text.isascii() and pulse_text.isdecimal()
            else pulse_text
        )
        return {
            "recording_backend": selected,
            "unicorn_udp_port": port if selected == "unicorn_udp" else self._valid_udp_port,
            "brainproducts_serial_port": (
                self.brainproducts_port_edit.text().strip()
                if selected == "brainproducts_triggerbox" else self._valid_triggerbox_port
            ),
            "brainproducts_parallel_address": (
                self.parallel_port_selector.address
                if selected == "brainproducts_parallel" else self._valid_parallel_address
            ),
            "brainproducts_pulse_width_ms": (
                pulse if brainproducts else self._valid_pulse_width
            ),
            "brainproducts_amplifier": (
                self._selected_amplifier() if brainproducts else self._valid_amplifier
            ),
            "brainproducts_sampling_rate_hz": (
                self.brainproducts_sampling_rate_combo.currentData()
                if brainproducts else self._valid_sampling_rate
            ),
        }

    def _refresh(self) -> None:
        selected = self.backend_combo.currentData()
        unicorn = selected == "unicorn_udp"
        triggerbox = selected == "brainproducts_triggerbox"
        parallel = selected == "brainproducts_parallel"
        brainproducts = triggerbox or parallel
        biosemi = selected in ("serial", "biosemi_active_three")
        self.port_edit.setEnabled(unicorn)
        self.unicorn_port_label.setVisible(unicorn)
        self.port_edit.setVisible(unicorn)
        self.biosemi_port_label.setVisible(biosemi and not self._computer_default)
        self.biosemi_port_selector.setVisible(biosemi and not self._computer_default)
        self.endpoint_label.setVisible(unicorn)
        for widget in (
            self.brainproducts_port_label, self.brainproducts_port_row,
            self.brainproducts_amplifier_label, self.brainproducts_amplifier_combo,
            self.detection_status_label,
        ):
            widget.setVisible(triggerbox)
        self.brainproducts_parallel_label.setVisible(parallel)
        self.parallel_port_selector.setVisible(parallel)
        for widget in (
            self.brainproducts_sampling_rate_label, self.brainproducts_sampling_rate_combo,
            self.brainproducts_pulse_label, self.brainproducts_pulse_edit,
            self.pulse_requirement_label,
        ):
            widget.setVisible(brainproducts)
        self.backend_combo.setToolTip(str(selected))
        if unicorn:
            guidance = (
                "Launch checks that Unicorn Recorder is open and recording before the "
                "experiment starts. Start recording in Recorder first.\n\n"
                "Select real electrodes and raw BDF or BDF+ logging in Recorder, with "
                "matching UDP input. These remain operator responsibilities.\n\n"
                f"{UNICORN_VALIDATION_NOTE}\n\n"
                "Test and Pilot modes never send markers."
            )
            detail = UNICORN_VALIDATION_NOTE
        elif brainproducts:
            guidance = (
                "Start recording in BrainVision Recorder before launch. "
                "Verify received markers and timing on your equipment. "
                "Test and Pilot modes never send markers."
            )
            detail = (
                "For actiCHamp / actiCHamp Plus. Connect the parallel port using the "
                "vendor-compatible trigger cable. Use the I/O start address from Device "
                "Manager > Resources, with a compatible InpOut driver installed and running. "
                "Detection "
                "only reads Windows metadata; it does not test the driver or attached amplifier. "
                "Enable high-active Stimulus inputs in Recorder. Confirm received codes, "
                "repeated markers and physical timing before collecting study data."
                if parallel else
                "Connect the TriggerBox USB port to this computer and use the vendor's "
                "amplifier-specific output cable. For TriggerBox Plus, set the lower "
                "eight output switches to PC. In BrainVision Recorder, enable the lower "
                "eight bits as high-active Stimulus inputs. Recorder and the amplifier "
                "own EEG acquisition; Studio cannot check that they are recording. "
                "Choose pulse width for the amplifier sample rate and confirm all codes, "
                "repeated markers and timing in an actual recording before collecting study data."
            )
        else:
            guidance = (
                "Configure the trigger-interface port in each project's Recording Setup. "
                if self._computer_default else "Start recording in ActiView before launch. "
            )
            guidance += "Test and Pilot modes never send markers."
            detail = (
                "ActiveThree uses BioSemi's compatible USB Trigger Interface and the "
                "current project's serial port/baud settings. Verify interface wiring, "
                "recorded markers and physical timing with your system. "
                "Studio sends triggers; BioSemi software owns EEG recording."
                if selected == "biosemi_active_three" else ""
            )
        self.guidance_label.setText(guidance)
        self.guidance_label.setToolTip(detail)
        self.guidance_label.setAccessibleDescription(detail)
        self.pulse_requirement_label.clear()
        if brainproducts:
            amplifier = self._selected_amplifier()
            rate = self.brainproducts_sampling_rate_combo.currentData()
            if (amplifier is not None and amplifier in AMPLIFIER_LABELS
                    and rate in supported_sampling_rates_hz(amplifier)):
                minimum = minimum_pulse_width_ms(amplifier, rate)
                self.pulse_requirement_label.setText(
                    f"Minimum pulse: {minimum:g} ms. Launch checks spacing between markers.",
                )
        draft = self._draft()
        try:
            if biosemi and not self._computer_default and not self.biosemi_port_selector.port:
                raise ValueError("Enter the BioSemi trigger-interface serial port.")
            validate_recording_configuration(draft)
            validated = ProjectRecordingSettings.model_validate(draft)
        except ValueError as exc:
            self.error_label.setText(str(exc))
            self.apply_button.setEnabled(False)
        else:
            self._valid_udp_port = validated.unicorn_udp_port
            self._valid_triggerbox_port = validated.brainproducts_serial_port
            self._valid_parallel_address = validated.brainproducts_parallel_address
            self._valid_pulse_width = validated.brainproducts_pulse_width_ms
            self._valid_amplifier = validated.brainproducts_amplifier
            self._valid_sampling_rate = validated.brainproducts_sampling_rate_hz
            self.error_label.clear()
            self.apply_button.setEnabled(True)
        self._maybe_detect_ports()

    def accept(self) -> None:
        self._refresh()
        if not self.apply_button.isEnabled():
            return
        self._configuration = self._draft()
        if (not self._computer_default
                and self.backend_combo.currentData() in ("serial", "biosemi_active_three")):
            self._accepted_biosemi_serial_port = self.biosemi_port_selector.port
        super().accept()
