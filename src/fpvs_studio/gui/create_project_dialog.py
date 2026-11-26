"""Dialog for collecting the inputs needed to scaffold a new project. It gathers user-
facing values that feed core project_service and path helpers before the resulting
ProjectFile and folder layout are created. The module owns form interaction only;
scaffolding and category defaults stay in backend services."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.paths import slugify_project_name, validate_project_id
from fpvs_studio.gui.components import (
    DialogHeader,
    apply_dialog_theme,
    mark_compact_action,
    mark_error_text,
    mark_primary_action,
    mark_secondary_action,
    refresh_widget_style,
)


class CreateProjectDialog(QDialog):
    """Choose Library setup or collect a manual category and project details."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Up a New Experiment")
        self.setModal(True)
        self.setMinimumSize(760, 500)
        self.resize(800, 500)
        self._experiment_category: ExperimentCategory | None = None
        self.from_library = False

        self.category_stack = QStackedWidget(self)
        self.category_stack.setObjectName("create_project_pages")
        self.source_page = QWidget(self)
        source_layout = QVBoxLayout(self.source_page)
        source_layout.setContentsMargins(8, 8, 8, 8)
        source_layout.setSpacing(20)
        source_layout.addWidget(DialogHeader(
            "Start a new experiment",
            "Build an experiment yourself or download a complete project from your lab.",
            parent=self.source_page,
        ))
        source_layout.addStretch(1)
        source_choices = QHBoxLayout()
        source_choices.setSpacing(16)
        self.manual_button = QPushButton("Create manually", self.source_page)
        self.manual_button.setObjectName("create_experiment_manually")
        self.manual_button.setToolTip("Choose an experiment category, name and save location.")
        self.manual_button.clicked.connect(self._show_category_page)
        self.library_button = QPushButton("Download from library", self.source_page)
        self.library_button.setObjectName("create_experiment_from_library")
        self.library_button.setToolTip(
            "Browse complete experiments and set up an editable local copy."
        )
        self.library_button.clicked.connect(self._choose_library)
        for button in (self.manual_button, self.library_button):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            mark_secondary_action(button)
            mark_compact_action(button)
            source_choices.addWidget(button, 1)
        source_layout.addLayout(source_choices)
        source_layout.addStretch(1)
        self.category_stack.addWidget(self.source_page)
        self.category_page = QWidget(self)
        category_layout = QVBoxLayout(self.category_page)
        category_layout.setContentsMargins(8, 8, 8, 8)
        category_layout.setSpacing(20)
        category_heading = QLabel("What kind of experiment are you creating?", self.category_page)
        heading_font = category_heading.font()
        heading_font.setPointSize(18)
        heading_font.setBold(True)
        category_heading.setFont(heading_font)
        category_heading.setWordWrap(True)
        category_layout.addWidget(category_heading)
        category_layout.addStretch(1)
        self.category_cards = QWidget(self.category_page)
        self.category_cards.setFixedHeight(118)
        category_row = QGridLayout(self.category_cards)
        category_row.setContentsMargins(0, 0, 0, 0)
        category_row.setSpacing(16)
        self.category_button_group = QButtonGroup(self)
        self.category_button_group.setExclusive(True)
        self.category_buttons: dict[ExperimentCategory, QPushButton] = {}
        choices = (
            (ExperimentCategory.FPVS, "Standard FPVS\n(Coming Soon)"),
            (ExperimentCategory.FPVS_ODDBALL, "FPVS-Oddball\nBase images and oddballs"),
        )
        for index, (category, text) in enumerate(choices):
            button = QPushButton(text, self.category_page)
            button.setObjectName(f"experiment_category_{category.value}")
            button.setMinimumWidth(210)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            button.setCheckable(True)
            button.setEnabled(category != ExperimentCategory.FPVS)
            button.setAccessibleName(text.replace("\n", ": "))
            button.clicked.connect(
                lambda _checked=False, selected=category: self.select_category(selected)
            )
            self.category_button_group.addButton(button)
            self.category_buttons[category] = button
            category_row.addWidget(button, 0, index)
        category_layout.addWidget(self.category_cards)
        category_layout.addStretch(1)
        self.category_stack.addWidget(self.category_page)
        self.details_page = QWidget(self)
        self.details_header = DialogHeader("Name your experiment", "", parent=self.details_page)
        self.category_summary_label = self.details_header.subtitle_label
        self.category_summary_label.setObjectName("create_project_category_summary")

        self.project_name_edit = QLineEdit(self)
        self.project_name_edit.setObjectName("project_name_edit")
        self.project_name_edit.setPlaceholderText("e.g. Visual Recognition Study")
        self.project_name_edit.textChanged.connect(self._update_project_name_validation)
        self.project_name_validation_label = QLabel(self)
        self.project_name_validation_label.setObjectName("project_name_validation_label")
        self.project_name_validation_label.setWordWrap(True)
        mark_error_text(self.project_name_validation_label)
        self.project_name_validation_label.setVisible(False)
        self.project_root_edit = QLineEdit(self)
        self.project_root_edit.setObjectName("project_root_edit")
        self.project_root_edit.setAccessibleName("Save location")
        self.project_root_edit.textChanged.connect(self._update_folder_hint)
        self.project_root_browse_button = QPushButton("Browse...", self)
        self.project_root_browse_button.setObjectName("project_root_browse_button")
        self.project_root_browse_button.clicked.connect(self._browse_root_directory)

        root_layout = QHBoxLayout()
        root_layout.addWidget(self.project_root_edit, 1)
        root_layout.addWidget(self.project_root_browse_button)

        self.folder_hint_label = QLabel(self.details_page)
        self.folder_hint_label.setObjectName("create_project_folder_hint")
        self.folder_hint_label.setProperty("dialogHelp", "true")
        self.folder_hint_label.setTextFormat(Qt.TextFormat.PlainText)
        self.folder_hint_label.setWordWrap(True)
        self.folder_hint_label.setMinimumWidth(0)
        self.folder_hint_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred,
        )

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.button_box.setObjectName("create_project_button_box")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.back_button = QPushButton("Back", self)
        self.back_button.clicked.connect(self._go_back)
        self.back_button.setVisible(False)
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        assert ok_button is not None
        mark_primary_action(ok_button)
        for button in (
            self.back_button, self.project_root_browse_button,
            self.button_box.button(QDialogButtonBox.StandardButton.Cancel),
        ):
            assert button is not None
            mark_secondary_action(button)

        details_layout = QVBoxLayout(self.details_page)
        details_layout.setContentsMargins(8, 4, 8, 0)
        details_layout.setSpacing(6)
        details_layout.addWidget(self.details_header)
        details_layout.addSpacing(12)
        details_layout.addWidget(self._field_label("Project Name", self.project_name_edit))
        details_layout.addWidget(self.project_name_edit)
        details_layout.addWidget(self.project_name_validation_label)
        details_layout.addSpacing(12)
        details_layout.addWidget(self._field_label("Save Location", self.project_root_edit))
        details_layout.addLayout(root_layout)
        details_layout.addWidget(self.folder_hint_label)
        details_layout.addStretch(1)
        self.category_stack.addWidget(self.details_page)

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(8, 0, 8, 0)
        footer_layout.addWidget(self.back_button)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.button_box)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        layout.addWidget(self.category_stack, 1)
        layout.addLayout(footer_layout)

        tab_order = (
            self.project_name_edit,
            self.project_root_edit,
            self.project_root_browse_button,
            self.back_button,
            ok_button,
            self.button_box.button(QDialogButtonBox.StandardButton.Cancel),
        )
        for current, following in zip(tab_order, tab_order[1:], strict=False):
            assert current is not None and following is not None
            self.setTabOrder(current, following)

        self._update_project_name_validation()
        apply_dialog_theme(self)

    def _field_label(self, text: str, buddy: QWidget) -> QLabel:
        label = QLabel(text, self.details_page)
        label.setProperty("settingsSectionTitle", "true")
        label.setBuddy(buddy)
        return label

    @property
    def experiment_category(self) -> ExperimentCategory:
        """Return the explicit category selected for manual setup."""
        if self._experiment_category is None:
            raise ValueError("Choose an experiment category first.")
        return self._experiment_category

    def select_category(self, category: ExperimentCategory) -> None:
        """Select one available category without creating or changing any project."""
        selected_button = self.category_buttons.get(category)
        if selected_button is None or not selected_button.isEnabled():
            return
        if self.category_stack.currentWidget() is self.source_page:
            self._show_category_page()
        self._experiment_category = category
        for value, button in self.category_buttons.items():
            button.setChecked(value == category)
            button.setProperty("primaryActionRole", "true" if value == category else "false")
            refresh_widget_style(button)
        self.category_summary_label.setText(selected_button.text().splitlines()[0])
        self._update_project_name_validation()

    def _show_category_page(self) -> None:
        self.from_library = False
        self.category_stack.setCurrentWidget(self.category_page)
        self._update_project_name_validation()

    def _go_back(self) -> None:
        previous = (
            self.category_page
            if self.category_stack.currentWidget() is self.details_page
            else self.source_page
        )
        self.category_stack.setCurrentWidget(previous)
        self._update_project_name_validation()

    def _choose_library(self) -> None:
        self.from_library = True
        super().accept()

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
        self.project_root_edit.setCursorPosition(0)

    def _update_folder_hint(self, _text: str = "") -> None:
        folder = self.project_root_edit.text().strip()
        self.project_root_edit.setToolTip(folder)
        self.project_root_edit.setAccessibleDescription(folder)
        name = self.project_name
        if name and self._project_name_validation_error(name) is None:
            slug = slugify_project_name(name)
            self.folder_hint_label.setText(f"New folder: {slug}")
            self.folder_hint_label.setToolTip(str(Path(folder) / slug) if folder else slug)
        else:
            self.folder_hint_label.setText("Studio creates a new experiment folder here.")
            self.folder_hint_label.setToolTip("")

    def accept(self) -> None:
        """Validate the dialog fields before closing."""

        if self.category_stack.currentWidget() is self.source_page:
            return
        if self.category_stack.currentWidget() is self.category_page:
            if self._experiment_category is None:
                return
            self.category_stack.setCurrentWidget(self.details_page)
            self.back_button.setVisible(True)
            self._update_project_name_validation()
            self.project_name_edit.setFocus()
            return
        project_name = self.project_name
        parent_directory = self.project_root_edit.text().strip()
        if not project_name:
            QMessageBox.warning(self, "Project Name Required", "Enter a project name.")
            self.project_name_edit.setFocus()
            return
        project_name_error = self._project_name_validation_error(project_name)
        if project_name_error is not None:
            QMessageBox.warning(self, "Invalid Project Name", project_name_error)
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
            self.project_root_edit.setCursorPosition(0)

    def _project_name_validation_error(self, project_name: str) -> str | None:
        if not project_name.strip():
            return None
        try:
            validate_project_id(slugify_project_name(project_name))
        except ValueError as error:
            return str(error)
        return None

    def _update_project_name_validation(self, _text: str = "") -> None:
        error = self._project_name_validation_error(self.project_name_edit.text())
        self.project_name_validation_label.setVisible(error is not None)
        self.project_name_validation_label.setText(error or "")
        self._update_folder_hint()
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            choosing_source = self.category_stack.currentWidget() is self.source_page
            choosing_category = self.category_stack.currentWidget() is self.category_page
            self.back_button.setVisible(not choosing_source)
            ok_button.setVisible(not choosing_source)
            ok_button.setText("Continue" if choosing_category else "Create Experiment")
            ok_button.setEnabled(
                self._experiment_category is not None if choosing_category else error is None
            )
