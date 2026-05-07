"""Dialog prompting users to normalize condition image folders."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.components import SectionCard, mark_primary_action, mark_secondary_action
from fpvs_studio.preprocessing.normalization import ImageNormalizationScan


class ImageNormalizationDialog(QDialog):
    """Small confirmation dialog for Conditions-step image normalization."""

    def __init__(
        self,
        scan: ImageNormalizationScan,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("image_normalization_dialog")
        self.setWindowTitle("Normalize Condition Images")
        self.setModal(True)

        card = SectionCard(
            title="Normalize Condition Images",
            subtitle=_summary_text(scan),
            object_name="image_normalization_card",
            parent=self,
        )
        details = QLabel(_details_text(scan), card)
        details.setObjectName("image_normalization_details")
        details.setWordWrap(True)
        card.body_layout.addWidget(details)

        size_label = QLabel("Output size", card)
        self.size_combo = QComboBox(card)
        self.size_combo.setObjectName("image_normalization_size_combo")
        self.size_combo.addItem("512 x 512", userData=512)
        self.size_combo.addItem("256 x 256", userData=256)
        size_row = QHBoxLayout()
        size_row.addWidget(size_label)
        size_row.addWidget(self.size_combo, 1)
        card.body_layout.addLayout(size_row)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_button = QPushButton("Cancel", self)
        cancel_button.setObjectName("image_normalization_cancel_button")
        cancel_button.clicked.connect(self.reject)
        mark_secondary_action(cancel_button)
        normalize_button = QPushButton("Normalize Images", self)
        normalize_button.setObjectName("image_normalization_accept_button")
        normalize_button.clicked.connect(self.accept)
        mark_primary_action(normalize_button)
        button_row.addWidget(cancel_button)
        button_row.addWidget(normalize_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        layout.addWidget(card)
        layout.addLayout(button_row)
        self.resize(460, 260)

    def target_size(self) -> int:
        """Return the selected square output size."""

        value = self.size_combo.currentData()
        return int(value) if isinstance(value, int) else 512


def _summary_text(scan: ImageNormalizationScan) -> str:
    set_count = len(scan.sets)
    image_count = scan.image_count
    return (
        f"FPVS Studio found inconsistent image properties across {set_count} image "
        f"folders ({image_count} images)."
    )


def _details_text(scan: ImageNormalizationScan) -> str:
    issues: list[str] = []
    if scan.mixed_resolution:
        issues.append("mixed image sizes")
    if scan.mixed_file_type:
        issues.append("mixed file types")
    if scan.unsupported_source_type:
        issues.append("formats that should be converted before launch")
    issue_text = ", ".join(issues) if issues else "image properties that need normalization"
    return (
        f"The selected condition images include {issue_text}. Studio can create PNG copies "
        "at a consistent square size and update the affected condition folders."
    )
