"""Focused display settings editor for the FPVS Studio GUI."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.components import SectionCard
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import (
    _RUNTIME_BACKGROUND_COLOR_PRESETS,
    _canonical_runtime_background_hex,
    _prefixed_object_name,
    _show_error_dialog,
)


class DisplaySettingsEditor(QWidget):
    """Reusable display settings editor for refresh rate and background color."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        object_name_prefix: str = "",
        editable: bool = True,
        framed: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._editable = editable
        self._background_refresh_guard = False

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

        self.summary_value_labels: dict[str, QLabel] = {}
        self.form_container = QWidget(self)
        self.form_layout = QFormLayout(self.form_container)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setHorizontalSpacing(12)
        self.form_layout.setVerticalSpacing(8)
        self.form_layout.addRow("Refresh (Hz)", self.refresh_hz_spin)
        self.form_layout.addRow("Background", self.runtime_background_color_combo)
        self.form_layout.addRow("", self.runtime_background_scope_label)

        self.summary_container = QWidget(self)
        self.summary_layout = QFormLayout(self.summary_container)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_layout.setHorizontalSpacing(12)
        self.summary_layout.setVerticalSpacing(6)
        for key, label_text in (
            ("refresh", "Refresh"),
            ("background", "Background"),
        ):
            value_label = QLabel(self.summary_container)
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.summary_value_labels[key] = value_label
            self.summary_layout.addRow(label_text, value_label)

        content_parent: QWidget = self
        if framed:
            self.card = SectionCard(
                title="Display Settings",
                subtitle="Refresh rate and presentation background.",
                object_name=_prefixed_object_name(object_name_prefix, "display_settings_card"),
                parent=self,
            )
            self.card.card_layout.setContentsMargins(12, 10, 12, 10)
            self.card.card_layout.setSpacing(8)
            self.card.body_layout.setSpacing(8)
            content_parent = self.card
        else:
            self.card = None

        target_layout = self.card.body_layout if self.card is not None else QVBoxLayout(self)
        if self.card is None:
            target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.addWidget(self.form_container)
        target_layout.addWidget(self.summary_container)

        if self.card is not None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(content_parent)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def current_refresh_hz(self) -> float:
        return self.refresh_hz_spin.value()

    def refresh(self) -> None:
        background_color = self._normalized_background_color()
        preferred_refresh = self._document.project.settings.display.preferred_refresh_hz or 60.0
        with QSignalBlocker(self.refresh_hz_spin):
            self.refresh_hz_spin.setValue(preferred_refresh)
        with QSignalBlocker(self.runtime_background_color_combo):
            selected_index = self.runtime_background_color_combo.findData(background_color)
            if selected_index < 0:
                selected_index = self.runtime_background_color_combo.findData("#000000")
            self.runtime_background_color_combo.setCurrentIndex(selected_index)

        self.refresh_hz_spin.setEnabled(self._editable)
        self.runtime_background_color_combo.setEnabled(self._editable)
        self.form_container.setVisible(self._editable)
        self.summary_container.setVisible(not self._editable)
        if not self._editable:
            self.summary_value_labels["refresh"].setText(f"{preferred_refresh:.2f} Hz")
            self.summary_value_labels["background"].setText(
                self.runtime_background_color_combo.currentText()
            )

    def _normalized_background_color(self) -> str:
        background_color = self._document.project.settings.display.background_color
        if isinstance(background_color, str):
            canonical_preset = _canonical_runtime_background_hex(background_color)
            if canonical_preset is not None:
                return canonical_preset

        if self._background_refresh_guard:
            return "#000000"

        self._background_refresh_guard = True
        try:
            self._document.update_display_settings(background_color="#000000")
        finally:
            self._background_refresh_guard = False
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


RuntimeSettingsEditor = DisplaySettingsEditor
