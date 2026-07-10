"""Options dialog for creating a renamed portable project-bundle copy."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.paths import slugify_project_name, validate_project_id
from fpvs_studio.core.project_bundle import project_bundle_filename
from fpvs_studio.gui.components import (
    apply_studio_theme,
    mark_error_text,
    mark_primary_action,
    mark_secondary_action,
)


class BundleExportOptionsDialog(QDialog):
    """Collect the project identity embedded in an exported bundle copy."""

    def __init__(self, *, current_project_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("bundle_export_options_dialog")
        self.setWindowTitle("Export Project Bundle")
        self.setModal(True)
        self.setMinimumSize(560, 350)
        self.resize(620, 370)

        eyebrow = QLabel("PROJECT EXPORT", self)
        eyebrow.setProperty("bundleWorkflowRole", "eyebrow")
        title = QLabel("Export a portable project copy", self)
        title.setProperty("bundleWorkflowRole", "title")
        lead = QLabel(
            "Choose the project name that another FPVS Studio user will see after import.",
            self,
        )
        lead.setProperty("bundleWorkflowRole", "lead")
        lead.setWordWrap(True)

        options_card = QFrame(self)
        options_card.setObjectName("bundle_export_options_card")
        options_card.setProperty("bundleWorkflowCard", "true")
        options_layout = QGridLayout(options_card)
        options_layout.setContentsMargins(16, 14, 16, 14)
        options_layout.setHorizontalSpacing(12)
        options_layout.setVerticalSpacing(10)

        name_label = QLabel("Project name in bundle", options_card)
        name_label.setProperty("bundleWorkflowRole", "sectionTitle")
        self.project_name_edit = QLineEdit(current_project_name, options_card)
        self.project_name_edit.setObjectName("bundle_export_project_name_edit")
        self.project_name_edit.selectAll()
        options_layout.addWidget(name_label, 0, 0, 1, 2)
        options_layout.addWidget(self.project_name_edit, 1, 0, 1, 2)

        self.validation_label = QLabel(options_card)
        self.validation_label.setObjectName("bundle_export_project_name_validation")
        self.validation_label.setWordWrap(True)
        mark_error_text(self.validation_label)
        options_layout.addWidget(self.validation_label, 2, 0, 1, 2)

        folder_label = QLabel("Imported project folder", options_card)
        folder_label.setProperty("bundleWorkflowRole", "meta")
        self.folder_value_label = QLabel(options_card)
        self.folder_value_label.setObjectName("bundle_export_folder_preview")
        self.folder_value_label.setProperty("bundleWorkflowRole", "fileName")
        filename_label = QLabel("Suggested bundle file", options_card)
        filename_label.setProperty("bundleWorkflowRole", "meta")
        self.filename_value_label = QLabel(options_card)
        self.filename_value_label.setObjectName("bundle_export_filename_preview")
        self.filename_value_label.setProperty("bundleWorkflowRole", "fileName")
        options_layout.addWidget(folder_label, 3, 0)
        options_layout.addWidget(self.folder_value_label, 3, 1)
        options_layout.addWidget(filename_label, 4, 0)
        options_layout.addWidget(self.filename_value_label, 4, 1)
        options_layout.setColumnStretch(1, 1)

        note = QLabel(
            "This changes only the portable copy. "
            "The open project and its folder remain unchanged.",
            self,
        )
        note.setObjectName("bundle_export_options_note")
        note.setProperty("importDisplayRole", "info")
        note.setWordWrap(True)

        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.setObjectName("bundle_export_options_cancel")
        mark_secondary_action(self.cancel_button)
        self.cancel_button.clicked.connect(self.reject)
        self.continue_button = QPushButton("Choose Save Location…", self)
        self.continue_button.setObjectName("bundle_export_options_continue")
        mark_primary_action(self.continue_button)
        self.continue_button.clicked.connect(self.accept)
        self.continue_button.setDefault(True)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 2, 0, 0)
        buttons.setSpacing(10)
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.continue_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(11)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(lead)
        layout.addWidget(options_card)
        layout.addWidget(note)
        layout.addLayout(buttons)

        self.project_name_edit.textChanged.connect(self._refresh_validation)
        self._refresh_validation()
        apply_studio_theme(self)

    @property
    def export_project_name(self) -> str:
        return self.project_name_edit.text().strip()

    def _refresh_validation(self, _text: str = "") -> None:
        project_name = self.export_project_name
        error = ""
        if not project_name:
            error = "Enter a project name for the exported copy."
        else:
            try:
                validate_project_id(slugify_project_name(project_name))
            except ValueError as exc:
                error = str(exc)
        self.validation_label.setText(error)
        self.validation_label.setVisible(bool(error))
        self.continue_button.setEnabled(not error)
        if error:
            self.folder_value_label.setText("—")
            self.filename_value_label.setText("—")
            return
        self.folder_value_label.setText(slugify_project_name(project_name))
        self.filename_value_label.setText(project_bundle_filename(project_name))
