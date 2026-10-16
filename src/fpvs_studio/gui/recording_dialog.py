"""Project recording preferences and Recorder launch-check guidance."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.models import ProjectRecordingSettings
from fpvs_studio.gui.components import (
    DialogHeader,
    apply_dialog_theme,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.runtime.recording import (
    UNICORN_VALIDATION_NOTE,
    recording_backend_label,
    validate_recording_configuration,
)


def recording_preference_summary(configuration: dict[str, object]) -> str:
    """Describe a saved choice while preserving actionable invalid-state feedback."""

    try:
        backend = validate_recording_configuration(configuration)
        label = recording_backend_label(configuration)
    except ValueError:
        return "Recording setup invalid. Open Recording Setup to select a valid choice and port."
    if backend == "unicorn_udp":
        return f"{label} — Recorder check before launch"
    if configuration.get("recording_backend") is None:
        return f"{label} (legacy project serial settings)"
    return label


class RecordingSetupDialog(QDialog):
    """Stage project recording hardware and endpoint settings until Apply."""

    def __init__(
        self, configuration: dict[str, object], parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("recording_setup_dialog")
        self.setWindowTitle("Recording Setup")
        self.setMinimumSize(640, 560)
        self.resize(self.minimumSize())
        self._configuration = dict(configuration)
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
        pulse_width = configuration.get("brainproducts_pulse_width_ms", 10)
        self._valid_pulse_width = (
            pulse_width if type(pulse_width) is int and 1 <= pulse_width <= 1000 else 10
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(DialogHeader(
            "Recording Setup", "For this project. Apply saves the selection.", parent=self,
        ))
        self.backend_combo = QComboBox(self)
        self.backend_combo.setObjectName("recording_backend_combo")
        self.backend_combo.addItem("BioSemi ActiveTwo (serial)", "serial")
        self.backend_combo.addItem("BioSemi ActiveThree (128 electrodes)", "biosemi_active_three")
        self.backend_combo.addItem(
            "Brain Products TriggerBox / TriggerBox Plus", "brainproducts_triggerbox",
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
        self.brainproducts_port_edit = QLineEdit(
            str(configuration.get("brainproducts_serial_port", "COM3")), self,
        )
        self.brainproducts_port_edit.setObjectName("brainproducts_serial_port_edit")
        self.brainproducts_port_edit.setAccessibleName("Brain Products TriggerBox COM port")
        self.brainproducts_port_edit.setToolTip(
            "Use the TriggerBox COM port from Windows Device Manager. "
            "Install the vendor driver and close other programs using that port. "
            "Studio uses the vendor's fixed 2,000,000 baud USB protocol.",
        )
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
        form.setSpacing(12)
        form.addRow("Recording device", self.backend_combo)
        form.addRow("Unicorn UDP port", self.port_edit)
        self.brainproducts_port_label = QLabel("TriggerBox COM port", self)
        self.brainproducts_pulse_label = QLabel("Trigger pulse width (ms)", self)
        form.addRow(self.brainproducts_port_label, self.brainproducts_port_edit)
        form.addRow(self.brainproducts_pulse_label, self.brainproducts_pulse_edit)
        layout.addLayout(form)
        layout.addWidget(self.endpoint_label)
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
        self.backend_combo.currentIndexChanged.connect(self._refresh)
        self.port_edit.textChanged.connect(self._refresh)
        self.brainproducts_port_edit.textChanged.connect(self._refresh)
        self.brainproducts_pulse_edit.textChanged.connect(self._refresh)
        self._refresh()
        apply_dialog_theme(self)

    @property
    def configuration(self) -> dict[str, object]:
        """Return only the accepted preference draft."""

        return dict(self._configuration)

    def _draft(self) -> dict[str, object]:
        selected = self.backend_combo.currentData()
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
            "brainproducts_pulse_width_ms": (
                pulse if selected == "brainproducts_triggerbox" else self._valid_pulse_width
            ),
        }

    def _refresh(self) -> None:
        selected = self.backend_combo.currentData()
        unicorn = selected == "unicorn_udp"
        brainproducts = selected == "brainproducts_triggerbox"
        self.port_edit.setEnabled(unicorn)
        self.endpoint_label.setVisible(unicorn)
        for widget in (
            self.brainproducts_port_label, self.brainproducts_port_edit,
            self.brainproducts_pulse_label, self.brainproducts_pulse_edit,
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
                "Start recording in BrainVision Recorder before launch. Verify the "
                "amplifier cable and trigger settings.\n\n"
                "Recorded marker and physical timing validation remain pending. "
                "Test and Pilot modes never send markers."
            )
            detail = (
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
                "BioSemi uses the current project's serial settings. The Sophia Mode "
                "recording prompt remains controlled by Settings > General. "
                "Test and Pilot modes never send markers."
            )
            detail = (
                "ActiveThree uses BioSemi's compatible USB Trigger Interface and the "
                "current project's serial port/baud settings. Verify interface wiring, "
                "recorded markers and physical timing with the 128-electrode system. "
                "Studio sends triggers; BioSemi software owns EEG recording."
                if selected == "biosemi_active_three" else ""
            )
        self.guidance_label.setText(guidance)
        self.guidance_label.setToolTip(detail)
        self.guidance_label.setAccessibleDescription(detail)
        draft = self._draft()
        try:
            validate_recording_configuration(draft)
            validated = ProjectRecordingSettings.model_validate(draft)
        except ValueError as exc:
            self.error_label.setText(str(exc))
            self.apply_button.setEnabled(False)
        else:
            self._valid_udp_port = validated.unicorn_udp_port
            self._valid_triggerbox_port = validated.brainproducts_serial_port
            self._valid_pulse_width = validated.brainproducts_pulse_width_ms
            self.error_label.clear()
            self.apply_button.setEnabled(True)

    def accept(self) -> None:
        self._refresh()
        if not self.apply_button.isEnabled():
            return
        self._configuration = self._draft()
        super().accept()
