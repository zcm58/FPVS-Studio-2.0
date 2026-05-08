"""Reusable FPVS Studio Root Folder setup guidance dialog.

The dialog explains app-level root-folder ownership before the controller opens
the native directory picker. It owns introductory copy only; path validation,
settings persistence, and project discovery remain in the controller.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from fpvs_studio.gui.components import (
    PathValueLabel,
    apply_studio_theme,
    mark_primary_action,
    mark_secondary_action,
)


class RootFolderSetupDialog(QDialog):
    """Explain the FPVS Studio Root Folder before users choose or change it."""

    def __init__(
        self,
        *,
        current_root: Path | None = None,
        first_run: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("root_folder_setup_dialog")
        self.setWindowTitle("Set Up FPVS Studio")
        self.setModal(True)
        self.resize(660, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        self.title_label = QLabel("Set Up FPVS Studio", self)
        self.title_label.setObjectName("root_folder_setup_title")
        self.title_label.setProperty("sectionCardRole", "title")
        layout.addWidget(self.title_label)

        self.body_label = QLabel(
            "FPVS Studio needs an FPVS Studio Root Folder before you create or open "
            "projects. This folder is the shared location for your FPVS Studio work.",
            self,
        )
        self.body_label.setObjectName("root_folder_setup_body")
        self.body_label.setWordWrap(True)
        layout.addWidget(self.body_label)

        self.details_label = QLabel(
            "- Each FPVS experiment project gets its own folder inside the root folder.\n"
            "- Condition templates and other Studio-level information are stored there too.\n"
            "- Choose a durable location, not a temporary folder or downloads folder.\n"
            "- After setup, you can create a new project or open an existing one.",
            self,
        )
        self.details_label.setObjectName("root_folder_setup_details")
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)

        self.current_root_label = QLabel("Current FPVS Studio Root Folder", self)
        self.current_root_label.setObjectName("root_folder_setup_current_root_label")
        self.current_root_label.setProperty("setupMetricLabel", "true")
        self.current_root_label.setVisible(current_root is not None)
        layout.addWidget(self.current_root_label)

        self.current_root_value = PathValueLabel(self)
        self.current_root_value.setObjectName("root_folder_setup_current_root_value")
        self.current_root_value.setVisible(current_root is not None)
        if current_root is not None:
            self.current_root_value.set_path_text(str(current_root), max_length=92)
        layout.addWidget(self.current_root_value)

        layout.addStretch(1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(10)
        button_row.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.secondary_button = QPushButton("Exit FPVS Studio" if first_run else "Close", self)
        self.secondary_button.setObjectName("root_folder_setup_secondary_button")
        mark_secondary_action(self.secondary_button)
        self.secondary_button.clicked.connect(self.reject)
        button_row.addWidget(self.secondary_button)

        choose_text = (
            "Choose Root Folder..."
            if first_run
            else "Choose Different Root Folder..."
        )
        self.choose_button = QPushButton(choose_text, self)
        self.choose_button.setObjectName("root_folder_setup_choose_button")
        mark_primary_action(self.choose_button)
        self.choose_button.clicked.connect(self.accept)
        button_row.addWidget(self.choose_button)

        layout.addLayout(button_row)
        apply_studio_theme(self)
