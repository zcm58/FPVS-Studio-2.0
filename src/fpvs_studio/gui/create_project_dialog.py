"""Dialog for collecting the minimal new-project scaffold inputs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from fpvs_studio.core.models import ConditionTemplateProfile


class CreateProjectDialog(QDialog):
    """Collect the project name and parent directory for project scaffolding."""

    def __init__(
        self,
        *,
        condition_template_profiles: list[ConditionTemplateProfile] | None = None,
        on_manage_templates: Callable[[], list[ConditionTemplateProfile]] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create New Project")
        self.setModal(True)
        self.resize(640, 180)
        self._on_manage_templates = on_manage_templates

        self.project_name_edit = QLineEdit(self)
        self.project_name_edit.setObjectName("project_name_edit")
        self.project_root_edit = QLineEdit(self)
        self.project_root_edit.setObjectName("project_root_edit")
        self.project_root_browse_button = QPushButton("Browse...", self)
        self.project_root_browse_button.setObjectName("project_root_browse_button")
        self.project_root_browse_button.clicked.connect(self._browse_root_directory)

        root_layout = QHBoxLayout()
        root_layout.addWidget(self.project_root_edit, 1)
        root_layout.addWidget(self.project_root_browse_button)

        self.condition_profile_combo = QComboBox(self)
        self.condition_profile_combo.setObjectName("condition_profile_combo")
        self.condition_profile_combo.setPlaceholderText("Select a condition template profile...")
        self.manage_templates_button = QPushButton("Manage Templates...", self)
        self.manage_templates_button.setObjectName("manage_condition_templates_button")
        self.manage_templates_button.clicked.connect(self._manage_templates)
        self.manage_templates_button.setEnabled(self._on_manage_templates is not None)

        profile_layout = QHBoxLayout()
        profile_layout.addWidget(self.condition_profile_combo, 1)
        profile_layout.addWidget(self.manage_templates_button)

        form_layout = QFormLayout()
        form_layout.addRow("Project Name", self.project_name_edit)
        form_layout.addRow("Project Folder", root_layout)
        form_layout.addRow("Condition Template", profile_layout)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.button_box.setObjectName("create_project_button_box")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(self.button_box)

        self.set_condition_template_profiles(condition_template_profiles or [], preserve_selection=False)

    @property
    def project_name(self) -> str:
        """Return the trimmed project name."""

        return self.project_name_edit.text().strip()

    @property
    def parent_directory(self) -> Path:
        """Return the selected parent directory."""

        return Path(self.project_root_edit.text().strip())

    @property
    def condition_profile_id(self) -> str | None:
        """Return the selected condition-template profile id."""

        selected = self.condition_profile_combo.currentData()
        return str(selected) if selected else None

    def set_parent_directory(self, directory: Path) -> None:
        """Prefill the parent directory field."""

        self.project_root_edit.setText(str(directory))

    def set_condition_template_profiles(
        self,
        profiles: list[ConditionTemplateProfile],
        *,
        preserve_selection: bool,
    ) -> None:
        """Update selectable condition-template profiles in the dialog."""

        current_profile_id = self.condition_profile_id if preserve_selection else None
        with QSignalBlocker(self.condition_profile_combo):
            self.condition_profile_combo.clear()
            for profile in profiles:
                self.condition_profile_combo.addItem(
                    f"{profile.display_name} ({profile.profile_id})",
                    userData=profile.profile_id,
                )
            if current_profile_id is None:
                self.condition_profile_combo.setCurrentIndex(-1)
            else:
                selected_index = self.condition_profile_combo.findData(current_profile_id)
                self.condition_profile_combo.setCurrentIndex(selected_index if selected_index >= 0 else -1)

    def accept(self) -> None:
        """Validate the dialog fields before closing."""

        project_name = self.project_name
        parent_directory = self.project_root_edit.text().strip()
        if not project_name:
            QMessageBox.warning(self, "Project Name Required", "Enter a project name.")
            self.project_name_edit.setFocus()
            return
        if not parent_directory:
            QMessageBox.warning(
                self,
                "Project Folder Required",
                "Choose the parent folder where the project should be created.",
            )
            self.project_root_browse_button.setFocus()
            return
        if not Path(parent_directory).is_dir():
            QMessageBox.warning(
                self,
                "Project Folder Missing",
                "Choose an existing parent folder for the new project.",
            )
            self.project_root_browse_button.setFocus()
            return
        if self.condition_profile_id is None:
            QMessageBox.warning(
                self,
                "Condition Template Required",
                "Select a condition template profile before creating the project.",
            )
            self.condition_profile_combo.setFocus()
            return
        super().accept()

    def _browse_root_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose Project Parent Folder",
            self.project_root_edit.text().strip() or str(Path.home()),
        )
        if directory:
            self.project_root_edit.setText(directory)

    def _manage_templates(self) -> None:
        if self._on_manage_templates is None:
            return
        profiles = self._on_manage_templates()
        self.set_condition_template_profiles(profiles, preserve_selection=True)
