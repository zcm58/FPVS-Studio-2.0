"""Local recording preferences and Recorder launch-check guidance."""

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
    """Stage the two supported local transport choices until Apply."""

    def __init__(
        self, configuration: dict[str, object], parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("recording_setup_dialog")
        self.setWindowTitle("Recording Setup")
        self.setMinimumSize(640, 560)
        self.resize(self.minimumSize())
        self._configuration = dict(configuration)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        layout.addWidget(DialogHeader(
            "Recording Setup", "For this computer. Apply saves the selection.", parent=self,
        ))
        self.backend_combo = QComboBox(self)
        self.backend_combo.setObjectName("recording_backend_combo")
        self.backend_combo.addItem("BioSemi serial (legacy project settings)", None)
        self.backend_combo.addItem("BioSemi serial", "serial")
        self.backend_combo.addItem("Unicorn Recorder UDP", "unicorn_udp")
        backend = configuration.get("recording_backend")
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
        self.endpoint_label = QLabel("Host: 127.0.0.1 (this computer only)", self)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setSpacing(12)
        form.addRow("Recording device", self.backend_combo)
        form.addRow("Unicorn UDP port", self.port_edit)
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
        self._refresh()
        apply_dialog_theme(self)

    @property
    def configuration(self) -> dict[str, object]:
        """Return only the accepted preference draft."""

        return dict(self._configuration)

    def _draft(self) -> dict[str, object]:
        text = self.port_edit.text()
        # Parse decimal digits only; preserve malformed saved text for validation.
        port: object = int(text) if len(text) <= 5 and text.isascii() and text.isdecimal() else text
        return {"recording_backend": self.backend_combo.currentData(), "unicorn_udp_port": port}

    def _refresh(self) -> None:
        unicorn = self.backend_combo.currentData() == "unicorn_udp"
        self.port_edit.setEnabled(unicorn)
        self.endpoint_label.setVisible(unicorn)
        self.guidance_label.setText(
            "Launch checks that Unicorn Recorder is open and recording before the "
            "experiment starts. Start recording in Recorder first.\n\n"
            "Select real electrodes and raw BDF or BDF+ logging in Recorder, with "
            "matching UDP input. These remain operator responsibilities.\n\n"
            f"{UNICORN_VALIDATION_NOTE}\n\n"
            "Test and Pilot modes never send markers."
            if unicorn else
            "BioSemi uses the current project's serial settings. The Sophia Mode "
            "recording prompt remains controlled by Settings > General. "
            "Test and Pilot modes never send markers."
        )
        self.guidance_label.setToolTip(UNICORN_VALIDATION_NOTE if unicorn else "")
        self.guidance_label.setAccessibleDescription(
            UNICORN_VALIDATION_NOTE if unicorn else "",
        )
        try:
            validate_recording_configuration(self._draft())
        except ValueError as exc:
            self.error_label.setText(str(exc))
            self.apply_button.setEnabled(False)
        else:
            self.error_label.clear()
            self.apply_button.setEnabled(True)

    def accept(self) -> None:
        self._refresh()
        if not self.apply_button.isEnabled():
            return
        self._configuration = self._draft()
        super().accept()
