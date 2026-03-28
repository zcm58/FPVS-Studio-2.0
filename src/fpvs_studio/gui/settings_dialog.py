"""Application settings dialog for local FPVS Studio preferences.
It edits GUI-level configuration that shapes the desktop authoring experience without becoming part of ProjectFile, RunSpec, or SessionPlan data.
The module owns app-preference widgets only; experiment semantics and runtime settings stay in their respective backend layers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class AppSettingsDialog(QDialog):
    """Expose lightweight app-level settings that are not project-scoped."""

    def __init__(
        self,
        *,
        fpvs_root_dir: Path,
        on_change_fpvs_root_dir: Callable[[Path], None],
        on_manage_condition_templates: Callable[[], object] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("fpvs_root_settings_dialog")
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(700, 240)

        self._fpvs_root_dir = fpvs_root_dir
        self._on_change_fpvs_root_dir = on_change_fpvs_root_dir
        self._on_manage_condition_templates = on_manage_condition_templates

        self.fpvs_root_dir_value = QLabel(str(fpvs_root_dir), self)
        self.fpvs_root_dir_value.setObjectName("fpvs_root_dir_value")
        self.fpvs_root_dir_value.setWordWrap(True)

        self.change_fpvs_root_button = QPushButton("Change...", self)
        self.change_fpvs_root_button.setObjectName("change_fpvs_root_dir_button")
        self.change_fpvs_root_button.clicked.connect(self._change_fpvs_root_directory)

        fpvs_root_row = QWidget(self)
        fpvs_root_layout = QHBoxLayout(fpvs_root_row)
        fpvs_root_layout.setContentsMargins(0, 0, 0, 0)
        fpvs_root_layout.addWidget(self.fpvs_root_dir_value, 1)
        fpvs_root_layout.addWidget(self.change_fpvs_root_button)

        form_layout = QFormLayout()
        form_layout.addRow("FPVS Studio Root Folder", fpvs_root_row)
        self.manage_templates_button = QPushButton("Manage Condition Templates...", self)
        self.manage_templates_button.setObjectName("manage_condition_templates_button")
        self.manage_templates_button.setEnabled(self._on_manage_condition_templates is not None)
        self.manage_templates_button.clicked.connect(self._manage_condition_templates)
        form_layout.addRow("Condition Templates", self.manage_templates_button)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        self.button_box.setObjectName("settings_button_box")
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addStretch(1)
        layout.addWidget(self.button_box)

    def _change_fpvs_root_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose FPVS Studio Root Folder",
            str(self._fpvs_root_dir),
        )
        if not directory:
            return
        selected_path = Path(directory)
        if not selected_path.is_dir():
            return
        self._on_change_fpvs_root_dir(selected_path)
        self._fpvs_root_dir = selected_path
        self.fpvs_root_dir_value.setText(str(selected_path))

    def _manage_condition_templates(self) -> None:
        if self._on_manage_condition_templates is None:
            return
        self._on_manage_condition_templates()
