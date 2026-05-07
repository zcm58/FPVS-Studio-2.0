"""Dialog for creating derived-variant control conditions."""

from __future__ import annotations

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

from fpvs_studio.core.enums import StimulusVariant
from fpvs_studio.gui.components import (
    SectionCard,
    apply_studio_theme,
    mark_primary_action,
    mark_secondary_action,
)

_CONTROL_VARIANTS: tuple[tuple[StimulusVariant, str], ...] = (
    (StimulusVariant.GRAYSCALE, "Grayscale"),
    (StimulusVariant.ROT180, "180 degree rotated"),
    (StimulusVariant.PHASE_SCRAMBLED, "Phase-scrambled"),
)


def control_condition_default_name(source_name: str, variant: StimulusVariant) -> str:
    """Return the default display name for a derived control condition."""

    variant_label = {
        StimulusVariant.GRAYSCALE: "Grayscale",
        StimulusVariant.ROT180: "180 Degree Rotated",
        StimulusVariant.PHASE_SCRAMBLED: "Phase-Scrambled",
    }[variant]
    return f"{source_name} {variant_label} Control"


class ControlConditionDialog(QDialog):
    """Collect the variant and name for a control condition."""

    def __init__(
        self,
        *,
        source_condition_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._source_condition_name = source_condition_name
        self._auto_name = True
        self.setWindowTitle("Create Control Condition")
        self.setModal(True)
        self.resize(520, 260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        card = SectionCard(
            title="Create Control Condition",
            subtitle="Use the selected condition's image folders with a derived image version.",
            object_name="control_condition_card",
            parent=self,
        )
        layout.addWidget(card)

        source_label = QLabel(source_condition_name, card)
        source_label.setObjectName("control_condition_source_label")

        self.variant_combo = QComboBox(card)
        self.variant_combo.setObjectName("control_condition_variant_combo")
        for variant, label in _CONTROL_VARIANTS:
            self.variant_combo.addItem(label, userData=variant)
        self.variant_combo.currentIndexChanged.connect(self._sync_default_name)

        self.name_edit = QLineEdit(card)
        self.name_edit.setObjectName("control_condition_name_edit")
        self.name_edit.textEdited.connect(self._mark_name_edited)
        self._sync_default_name()

        form = QFormLayout()
        form.setVerticalSpacing(8)
        form.addRow("Source Condition", source_label)
        form.addRow("Image Version", self.variant_combo)
        form.addRow("New Condition Name", self.name_edit)
        card.body_layout.addLayout(form)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        ok_button.setText("Create")
        mark_primary_action(ok_button)
        mark_secondary_action(cancel_button)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        apply_studio_theme(self)

    def selected_variant(self) -> StimulusVariant:
        variant = self.variant_combo.currentData()
        if isinstance(variant, StimulusVariant):
            return variant
        return StimulusVariant.GRAYSCALE

    def condition_name(self) -> str:
        return self.name_edit.text().strip()

    def _mark_name_edited(self) -> None:
        self._auto_name = False

    def _sync_default_name(self) -> None:
        if not self._auto_name:
            return
        self.name_edit.setText(
            control_condition_default_name(
                self._source_condition_name,
                self.selected_variant(),
            )
        )
