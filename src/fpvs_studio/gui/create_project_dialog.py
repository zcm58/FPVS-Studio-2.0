"""Dialog for collecting the inputs needed to scaffold a new project. It gathers user-
facing values that feed core project_service and path helpers before the resulting
ProjectFile and folder layout are created. The module owns form interaction only;
validation, scaffolding, and template defaults stay in backend services."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
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

from fpvs_studio.core.condition_template_profiles import is_supported_condition_template
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.experiment_categories import experiment_category_label
from fpvs_studio.core.models import ConditionTemplateProfile
from fpvs_studio.core.paths import slugify_project_name, validate_project_id
from fpvs_studio.gui.components import (
    DialogHeader,
    apply_dialog_theme,
    mark_error_text,
    mark_primary_action,
    mark_secondary_action,
    refresh_widget_style,
)


class CreateProjectDialog(QDialog):
    """Choose a category before collecting project details and compatible templates."""

    def __init__(
        self,
        *,
        condition_template_profiles: list[ConditionTemplateProfile] | None = None,
        on_manage_templates: Callable[[], list[ConditionTemplateProfile]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set Up a New Experiment")
        self.setModal(True)
        self.setMinimumSize(760, 500)
        self.resize(800, 500)
        self._on_manage_templates = on_manage_templates
        self._experiment_category: ExperimentCategory | None = None
        self._condition_profiles: list[ConditionTemplateProfile] = []

        self.category_stack = QStackedWidget(self)
        self.category_stack.setObjectName("create_project_pages")
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
        self.category_cards.setFixedHeight(252)
        category_row = QGridLayout(self.category_cards)
        category_row.setContentsMargins(0, 0, 0, 0)
        category_row.setSpacing(16)
        self.category_button_group = QButtonGroup(self)
        self.category_button_group.setExclusive(True)
        self.category_buttons: dict[ExperimentCategory, QPushButton] = {}
        choices = (
            (ExperimentCategory.FPVS, "Standard FPVS\nComing soon"),
            (ExperimentCategory.FPVS_ODDBALL, "FPVS Oddball Paradigm\nBase images and oddballs"),
            (ExperimentCategory.ATTENTIONAL_BLINK, "Attentional-Blink\nTwo targets in a stream"),
            (
                ExperimentCategory.COGNITIVE_LOAD_FPVS,
                "Cognitive Load FPVS\nImages with backward counting",
            ),
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
            category_row.addWidget(button, index // 2, index % 2)
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

        self.condition_profile_combo = QComboBox(self)
        self.condition_profile_combo.setObjectName("condition_profile_combo")
        self.condition_profile_combo.setPlaceholderText("Select an experiment template...")
        self.condition_profile_combo.setMinimumContentsLength(22)
        self.condition_profile_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.condition_profile_combo.currentIndexChanged.connect(self._update_template_description)
        self.manage_templates_button = QPushButton("Manage Templates...", self)
        self.manage_templates_button.setObjectName("manage_condition_templates_button")
        self.manage_templates_button.clicked.connect(self._manage_templates)
        self.manage_templates_button.setEnabled(self._on_manage_templates is not None)

        profile_layout = QHBoxLayout()
        profile_layout.addWidget(self.condition_profile_combo, 1)
        profile_layout.addWidget(self.manage_templates_button)

        self.template_description_label = QLabel(self.details_page)
        self.template_description_label.setObjectName("create_project_template_description")
        self.folder_hint_label = QLabel(self.details_page)
        self.folder_hint_label.setObjectName("create_project_folder_hint")
        for label in (self.template_description_label, self.folder_hint_label):
            label.setProperty("dialogHelp", "true")
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.button_box.setObjectName("create_project_button_box")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.back_button = QPushButton("Back", self)
        self.back_button.clicked.connect(self._show_category_page)
        self.back_button.setVisible(False)
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        assert ok_button is not None
        mark_primary_action(ok_button)
        for button in (
            self.back_button, self.project_root_browse_button, self.manage_templates_button,
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
        details_layout.addWidget(
            self._field_label("Experiment Template", self.condition_profile_combo)
        )
        details_layout.addLayout(profile_layout)
        details_layout.addWidget(self.template_description_label)
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
            self.condition_profile_combo,
            self.manage_templates_button,
            self.project_root_edit,
            self.project_root_browse_button,
            self.back_button,
            ok_button,
            self.button_box.button(QDialogButtonBox.StandardButton.Cancel),
        )
        for current, following in zip(tab_order, tab_order[1:], strict=False):
            assert current is not None and following is not None
            self.setTabOrder(current, following)

        self.set_condition_template_profiles(
            condition_template_profiles or [], preserve_selection=False
        )
        self._update_project_name_validation()
        apply_dialog_theme(self)

    def _field_label(self, text: str, buddy: QWidget) -> QLabel:
        label = QLabel(text, self.details_page)
        label.setProperty("settingsSectionTitle", "true")
        label.setBuddy(buddy)
        return label

    @property
    def experiment_category(self) -> ExperimentCategory:
        """Return the explicit category choice after the first setup page."""
        if self._experiment_category is None:
            raise ValueError("Choose an experiment category first.")
        return self._experiment_category

    def select_category(self, category: ExperimentCategory) -> None:
        """Select one available category without creating or changing any project."""
        if category == ExperimentCategory.FPVS:
            return
        self._experiment_category = category
        for value, button in self.category_buttons.items():
            button.setChecked(value == category)
            button.setProperty("primaryActionRole", "true" if value == category else "false")
            refresh_widget_style(button)
        self.category_summary_label.setText(experiment_category_label(category))
        self.set_condition_template_profiles(self._condition_profiles, preserve_selection=False)
        self._update_project_name_validation()

    def _show_category_page(self) -> None:
        self.category_stack.setCurrentWidget(self.category_page)
        self.back_button.setVisible(False)
        self._update_project_name_validation()

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
        self.project_root_edit.setCursorPosition(0)

    def set_condition_template_profiles(
        self,
        profiles: list[ConditionTemplateProfile],
        *,
        preserve_selection: bool,
    ) -> None:
        """Update selectable condition-template profiles in the dialog."""

        self._condition_profiles = list(profiles)
        profiles = [
            profile
            for profile in profiles
            if profile.experiment_category == self._experiment_category
            and is_supported_condition_template(profile)
        ]
        current_profile_id = self.condition_profile_id if preserve_selection else None
        with QSignalBlocker(self.condition_profile_combo):
            self.condition_profile_combo.clear()
            for profile in profiles:
                self.condition_profile_combo.addItem(
                    profile.display_name,
                    userData=profile.profile_id,
                )
                self.condition_profile_combo.setItemData(
                    self.condition_profile_combo.count() - 1,
                    profile.description,
                    Qt.ItemDataRole.ToolTipRole,
                )
            if current_profile_id is None:
                self.condition_profile_combo.setCurrentIndex(0 if profiles else -1)
            else:
                selected_index = self.condition_profile_combo.findData(current_profile_id)
                self.condition_profile_combo.setCurrentIndex(
                    selected_index if selected_index >= 0 else -1
                )
        self._update_template_description()

    def _update_template_description(self, _index: int = -1) -> None:
        profile = next(
            (
                item for item in self._condition_profiles
                if item.profile_id == self.condition_profile_id
            ),
            None,
        )
        description = profile.description if profile is not None else "Choose a starting template."
        self.template_description_label.setText(description)
        self.template_description_label.setToolTip(description)
        self.condition_profile_combo.setToolTip(profile.display_name if profile else description)

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
        if self.condition_profile_id is None:
            QMessageBox.warning(
                self,
                "Experiment Template Required",
                "Select an experiment template before creating the project.",
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
            self.project_root_edit.setCursorPosition(0)

    def _manage_templates(self) -> None:
        if self._on_manage_templates is None:
            return
        profiles = self._on_manage_templates()
        self.set_condition_template_profiles(profiles, preserve_selection=True)

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
            choosing_category = self.category_stack.currentWidget() is self.category_page
            ok_button.setText("Continue" if choosing_category else "Create Experiment")
            ok_button.setEnabled(
                self._experiment_category is not None if choosing_category else error is None
            )
