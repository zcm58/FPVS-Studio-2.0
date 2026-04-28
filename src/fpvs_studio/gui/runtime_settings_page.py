"""Runtime settings page for the FPVS Studio main window."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.design_system import (
    PAGE_SECTION_GAP,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import (
    _RUNTIME_BACKGROUND_COLOR_PRESETS,
    _canonical_runtime_background_hex,
    _prefixed_object_name,
    _show_error_dialog,
)
from fpvs_studio.gui.window_layout import SectionCard


class RuntimeSettingsEditor(QWidget):
    """Reusable runtime settings editor for refresh/display/serial controls."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        object_name_prefix: str = "",
        editable: bool = True,
        fullscreen_state_getter: Callable[[], bool] | None = None,
        fullscreen_state_setter: Callable[[bool], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._editable = editable
        self._fullscreen_state_getter = fullscreen_state_getter
        self._fullscreen_state_setter = fullscreen_state_setter
        self._runtime_background_refresh_guard = False

        self.refresh_hz_spin = QDoubleSpinBox(self)
        self.refresh_hz_spin.setObjectName(
            _prefixed_object_name(object_name_prefix, "refresh_hz_spin")
        )
        self.refresh_hz_spin.setRange(1.0, 500.0)
        self.refresh_hz_spin.setDecimals(2)
        self.refresh_hz_spin.valueChanged.connect(self._apply_refresh_hz)

        self.runtime_background_color_combo = QComboBox(self)
        self.runtime_background_color_combo.setObjectName(
            _prefixed_object_name(object_name_prefix, "runtime_background_color_combo")
        )
        for label, background_hex in _RUNTIME_BACKGROUND_COLOR_PRESETS:
            self.runtime_background_color_combo.addItem(label, userData=background_hex)
        self.runtime_background_color_combo.currentIndexChanged.connect(
            self._apply_runtime_background_color
        )
        self.runtime_background_scope_label = QLabel(
            "Used during FPVS image presentation.",
            self,
        )
        self.runtime_background_scope_label.setObjectName(
            _prefixed_object_name(object_name_prefix, "runtime_background_scope_label")
        )
        self.runtime_background_scope_label.setWordWrap(True)

        self.serial_port_edit = QLineEdit(self)
        self.serial_port_edit.setObjectName(
            _prefixed_object_name(object_name_prefix, "serial_port_edit")
        )
        self.serial_port_edit.setPlaceholderText("COM3")
        self.serial_port_edit.editingFinished.connect(self._apply_serial_settings)

        self.serial_baudrate_spin = QSpinBox(self)
        self.serial_baudrate_spin.setObjectName(
            _prefixed_object_name(object_name_prefix, "serial_baudrate_spin")
        )
        self.serial_baudrate_spin.setRange(1, 2_000_000)
        self.serial_baudrate_spin.setEnabled(False)
        self.serial_baudrate_spin.setToolTip(
            "Baud rate is stored in project settings and shown here for reference."
        )
        self.serial_baudrate_spin.valueChanged.connect(self._apply_serial_settings)

        self.test_mode_checkbox = QCheckBox(
            "Launch the currently supported alpha test-mode path",
            self,
        )
        self.test_mode_checkbox.setObjectName(
            _prefixed_object_name(object_name_prefix, "test_mode_checkbox")
        )
        self.test_mode_checkbox.setChecked(True)
        self.test_mode_checkbox.setEnabled(False)

        self.fullscreen_checkbox = QCheckBox("Present launched playback fullscreen", self)
        self.fullscreen_checkbox.setObjectName(
            _prefixed_object_name(object_name_prefix, "fullscreen_checkbox")
        )
        self.fullscreen_checkbox.stateChanged.connect(self._on_fullscreen_toggled)

        self.card = SectionCard(
            title="Runtime Settings",
            subtitle="Refresh, background, fullscreen, and trigger configuration.",
            object_name=_prefixed_object_name(object_name_prefix, "runtime_settings_card"),
            parent=self,
        )
        self.card.card_layout.setContentsMargins(12, 10, 12, 10)
        self.card.card_layout.setSpacing(8)
        self.card.body_layout.setSpacing(8)
        self.summary_note_label = QLabel(self.card)
        self.summary_note_label.setObjectName(
            _prefixed_object_name(object_name_prefix, "runtime_settings_summary_note")
        )
        self.summary_note_label.setWordWrap(True)
        self.summary_value_labels: dict[str, QLabel] = {}
        self.form_container = QWidget(self.card)
        self.form_layout = QGridLayout(self.form_container)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setHorizontalSpacing(PAGE_SECTION_GAP)
        self.form_layout.setVerticalSpacing(8)
        self.form_layout.addWidget(QLabel("Refresh (Hz)", self.form_container), 0, 0)
        self.form_layout.addWidget(self.refresh_hz_spin, 0, 1)
        self.form_layout.addWidget(QLabel("Background", self.form_container), 0, 2)
        self.form_layout.addWidget(self.runtime_background_color_combo, 0, 3)
        self.form_layout.addWidget(self.runtime_background_scope_label, 1, 0, 1, 4)
        self.form_layout.addWidget(QLabel("Serial Port", self.form_container), 2, 0)
        self.form_layout.addWidget(self.serial_port_edit, 2, 1)
        self.form_layout.addWidget(QLabel("Baud Rate", self.form_container), 2, 2)
        self.form_layout.addWidget(self.serial_baudrate_spin, 2, 3)
        self.form_layout.addWidget(self.test_mode_checkbox, 3, 0, 1, 2)
        self.form_layout.addWidget(self.fullscreen_checkbox, 3, 2, 1, 2)
        self.form_layout.setColumnStretch(1, 1)
        self.form_layout.setColumnStretch(3, 1)
        self.summary_container = QWidget(self.card)
        self.summary_layout = QFormLayout(self.summary_container)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_layout.setHorizontalSpacing(12)
        self.summary_layout.setVerticalSpacing(6)
        for key, label_text in (
            ("refresh", "Refresh"),
            ("background", "Background"),
            ("serial_port", "Serial Port"),
            ("serial_baudrate", "Baud Rate"),
            ("test_mode", "Runtime Path"),
            ("fullscreen", "Fullscreen"),
        ):
            value_label = QLabel(self.summary_container)
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.summary_value_labels[key] = value_label
            self.summary_layout.addRow(label_text, value_label)
        if not self._editable:
            self.card.title_label.setText("Runtime Settings Summary")
            if self.card.subtitle_label is not None:
                self.card.subtitle_label.setText("Mirrored from Run / Runtime.")
            self.summary_note_label.setText(
                "Open Run / Runtime to edit launch settings. This view is a compact mirror."
            )
            self.card.body_layout.addWidget(self.summary_note_label)
            self.card.body_layout.addWidget(self.summary_container)
        else:
            self.card.body_layout.addWidget(self.form_container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.card)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def current_refresh_hz(self) -> float:
        return self.refresh_hz_spin.value()

    def set_fullscreen_checked(self, checked: bool) -> None:
        with QSignalBlocker(self.fullscreen_checkbox):
            self.fullscreen_checkbox.setChecked(checked)

    def refresh(self) -> None:
        background_color = self._normalized_runtime_background_color()
        preferred_refresh = self._document.project.settings.display.preferred_refresh_hz or 60.0
        with QSignalBlocker(self.refresh_hz_spin):
            self.refresh_hz_spin.setValue(preferred_refresh)
        with QSignalBlocker(self.runtime_background_color_combo):
            selected_index = self.runtime_background_color_combo.findData(background_color)
            if selected_index < 0:
                selected_index = self.runtime_background_color_combo.findData("#000000")
            self.runtime_background_color_combo.setCurrentIndex(selected_index)
        with QSignalBlocker(self.serial_port_edit):
            self.serial_port_edit.setText(
                self._document.project.settings.triggers.serial_port or ""
            )
        with QSignalBlocker(self.serial_baudrate_spin):
            self.serial_baudrate_spin.setValue(self._document.project.settings.triggers.baudrate)
        target_fullscreen_value = (
            self._fullscreen_state_getter()
            if self._fullscreen_state_getter is not None
            else self.fullscreen_checkbox.isChecked()
        )
        self.set_fullscreen_checked(target_fullscreen_value)
        self.refresh_hz_spin.setEnabled(self._editable)
        self.runtime_background_color_combo.setEnabled(self._editable)
        self.serial_port_edit.setEnabled(self._editable)
        self.fullscreen_checkbox.setEnabled(self._editable)
        if not self._editable:
            self.summary_note_label.setVisible(True)
            self.summary_container.setVisible(True)
            self.form_container.setVisible(False)
            self.summary_value_labels["refresh"].setText(f"{preferred_refresh:.2f} Hz")
            self.summary_value_labels["background"].setText(
                self.runtime_background_color_combo.currentText()
            )
            self.summary_value_labels["serial_port"].setText(
                self._document.project.settings.triggers.serial_port or "Not set"
            )
            self.summary_value_labels["serial_baudrate"].setText(
                str(self._document.project.settings.triggers.baudrate)
            )
            self.summary_value_labels["test_mode"].setText("Alpha test-mode path only")
            self.summary_value_labels["fullscreen"].setText(
                "Enabled" if target_fullscreen_value else "Disabled"
            )
        else:
            self.summary_note_label.setVisible(False)
            self.summary_container.setVisible(False)
            self.form_container.setVisible(True)

    def _normalized_runtime_background_color(self) -> str:
        background_color = self._document.project.settings.display.background_color
        if isinstance(background_color, str):
            canonical_preset = _canonical_runtime_background_hex(background_color)
            if canonical_preset is not None:
                return canonical_preset

        if self._runtime_background_refresh_guard:
            return "#000000"

        self._runtime_background_refresh_guard = True
        try:
            self._document.update_display_settings(background_color="#000000")
        finally:
            self._runtime_background_refresh_guard = False
        return "#000000"

    def _apply_refresh_hz(self) -> None:
        try:
            self._document.update_display_settings(
                preferred_refresh_hz=self.refresh_hz_spin.value()
            )
        except Exception as error:
            _show_error_dialog(self, "Refresh Setting Error", error)
            self.refresh()

    def _apply_runtime_background_color(self) -> None:
        selected_background_color = self.runtime_background_color_combo.currentData()
        if not isinstance(selected_background_color, str):
            return
        try:
            self._document.update_display_settings(background_color=selected_background_color)
        except Exception as error:
            _show_error_dialog(self, "Display Settings Error", error)
            self.refresh()

    def _apply_serial_settings(self) -> None:
        serial_port = self.serial_port_edit.text().strip() or None
        try:
            self._document.update_trigger_settings(
                serial_port=serial_port,
                baudrate=self.serial_baudrate_spin.value(),
            )
        except Exception as error:
            _show_error_dialog(self, "Serial Settings Error", error)
            self.refresh()

    def _on_fullscreen_toggled(self) -> None:
        if self._fullscreen_state_setter is not None:
            self._fullscreen_state_setter(self.fullscreen_checkbox.isChecked())
