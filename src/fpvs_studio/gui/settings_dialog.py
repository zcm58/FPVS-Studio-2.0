"""Application settings dialog for local FPVS Studio preferences. It edits GUI-level
configuration that shapes the desktop authoring experience without becoming part of
ProjectFile, RunSpec, or SessionPlan data. The module owns app-preference widgets only;
experiment semantics and runtime settings stay in their respective backend layers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio import __version__


class AppSettingsDialog(QDialog):
    """Expose lightweight app-level settings that are not project-scoped."""

    def __init__(
        self,
        *,
        fpvs_root_dir: Path,
        on_show_root_folder_setup: Callable[[QWidget], Path | None] | None = None,
        on_manage_condition_templates: Callable[[], object] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("fpvs_root_settings_dialog")
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(700, 280)

        self._fpvs_root_dir = fpvs_root_dir
        self._on_show_root_folder_setup = on_show_root_folder_setup
        self._on_manage_condition_templates = on_manage_condition_templates

        form_layout = QFormLayout()
        self.root_folder_setup_button = QPushButton("Root Folder Setup...", self)
        self.root_folder_setup_button.setObjectName("root_folder_setup_button")
        self.root_folder_setup_button.setEnabled(self._on_show_root_folder_setup is not None)
        self.root_folder_setup_button.clicked.connect(self._show_root_folder_setup)
        form_layout.addRow("Root Folder Setup", self.root_folder_setup_button)
        self.manage_templates_button = QPushButton("Manage Condition Templates...", self)
        self.manage_templates_button.setObjectName("manage_condition_templates_button")
        self.manage_templates_button.setEnabled(self._on_manage_condition_templates is not None)
        self.manage_templates_button.clicked.connect(self._manage_condition_templates)
        form_layout.addRow("Condition Templates", self.manage_templates_button)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        self.button_box.setObjectName("settings_button_box")
        self.button_box.rejected.connect(self.reject)

        self.version_value = QLabel(f"FPVS Studio version {__version__}", self)
        self.version_value.setObjectName("app_version_value")
        self.version_value.setAlignment(Qt.AlignmentFlag.AlignCenter)

        footer_layout = QGridLayout()
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setColumnStretch(0, 1)
        footer_layout.setColumnStretch(1, 1)
        footer_layout.setColumnStretch(2, 1)
        footer_layout.addWidget(self.version_value, 0, 1, Qt.AlignmentFlag.AlignCenter)
        footer_layout.addWidget(self.button_box, 0, 2, Qt.AlignmentFlag.AlignRight)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addStretch(1)
        layout.addLayout(footer_layout)

    def _show_root_folder_setup(self) -> None:
        if self._on_show_root_folder_setup is None:
            return
        selected_path = self._on_show_root_folder_setup(self)
        if selected_path is None:
            return
        self._fpvs_root_dir = selected_path

    def _manage_condition_templates(self) -> None:
        if self._on_manage_condition_templates is None:
            return
        self._on_manage_condition_templates()
