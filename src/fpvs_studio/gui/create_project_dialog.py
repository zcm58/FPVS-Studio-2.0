"""Dialog for collecting the minimal new-project scaffold inputs."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
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


class CreateProjectDialog(QDialog):
    """Collect the project name and parent directory for project scaffolding."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create New Project")
        self.setModal(True)
        self.resize(520, 140)

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

        form_layout = QFormLayout()
        form_layout.addRow("Project Name", self.project_name_edit)
        form_layout.addRow("Project Folder", root_layout)

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

    @property
    def project_name(self) -> str:
        """Return the trimmed project name."""

        return self.project_name_edit.text().strip()

    @property
    def parent_directory(self) -> Path:
        """Return the selected parent directory."""

        return Path(self.project_root_edit.text().strip())

    def set_parent_directory(self, directory: Path) -> None:
        """Prefill the parent directory field."""

        self.project_root_edit.setText(str(directory))

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
        super().accept()

    def _browse_root_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose Project Parent Folder",
            self.project_root_edit.text().strip() or str(Path.home()),
        )
        if directory:
            self.project_root_edit.setText(directory)
