"""Project overview page for the FPVS Studio main window."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.models import ConditionTemplateProfile
from fpvs_studio.gui.components import (
    PathValueLabel,
    SectionCard,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import (
    LeftToRightPlainTextEdit,
    _show_error_dialog,
    _sync_text_editor_contents,
)


class ProjectOverviewEditor(QWidget):
    """Compact project metadata and condition template controls editor."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        load_condition_template_profiles: Callable[[], list[ConditionTemplateProfile]],
        manage_condition_templates: Callable[[], list[ConditionTemplateProfile]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._load_condition_template_profiles = load_condition_template_profiles
        self._manage_condition_templates = manage_condition_templates
        self._condition_profiles_by_id: dict[str, ConditionTemplateProfile] = {}

        self.project_name_edit = QLineEdit(self)
        self.project_name_edit.setObjectName("project_name_edit")
        self.project_name_edit.editingFinished.connect(self._apply_project_name)

        self.project_description_edit = LeftToRightPlainTextEdit(self)
        self.project_description_edit.setObjectName("project_description_edit")
        self.project_description_edit.setPlaceholderText(
            "Describe the project goal and participant instructions."
        )
        self.project_description_edit.setFixedHeight(64)
        self.project_description_edit.setMaximumBlockCount(20)
        self.project_description_edit.textChanged.connect(self._apply_project_description)

        self.project_root_value = PathValueLabel(self)
        self.project_root_value.setObjectName("project_root_value")
        self.project_root_value.setWordWrap(False)
        self.project_root_value.setMaximumHeight(34)
        self.project_root_value.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.condition_profile_combo = QComboBox(self)
        self.condition_profile_combo.setObjectName("project_condition_profile_combo")
        self.condition_profile_combo.setPlaceholderText("Select a condition template profile...")
        self.condition_profile_combo.currentIndexChanged.connect(
            self._apply_condition_profile_selection
        )
        self.manage_templates_button = QPushButton("Manage Templates...", self)
        self.manage_templates_button.setObjectName("project_manage_templates_button")
        self.manage_templates_button.clicked.connect(self._open_template_manager)
        self.apply_profile_to_conditions_button = QPushButton(
            "Apply Template To All Conditions", self
        )
        self.apply_profile_to_conditions_button.setObjectName("apply_profile_to_conditions_button")
        self.apply_profile_to_conditions_button.clicked.connect(self._apply_profile_to_conditions)

        condition_profile_row = QWidget(self)
        condition_profile_layout = QHBoxLayout(condition_profile_row)
        condition_profile_layout.setContentsMargins(0, 0, 0, 0)
        condition_profile_layout.setSpacing(8)
        condition_profile_layout.addWidget(self.condition_profile_combo, 1)
        condition_profile_layout.addWidget(self.manage_templates_button)
        condition_profile_layout.addWidget(self.apply_profile_to_conditions_button)

        self.project_overview_card = SectionCard(
            title="Project Details",
            object_name="dashboard_project_overview_card",
            parent=self,
        )
        self.project_overview_card.setMaximumWidth(920)
        self.project_overview_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        metadata_layout = QFormLayout()
        metadata_layout.setVerticalSpacing(10)
        metadata_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        metadata_layout.addRow("Name", self.project_name_edit)
        metadata_layout.addRow("Description", self.project_description_edit)
        metadata_layout.addRow("Project folder", self.project_root_value)
        metadata_layout.addRow("Condition Template", condition_profile_row)
        self.project_overview_card.card_layout.setContentsMargins(16, 14, 16, 14)
        self.project_overview_card.card_layout.setSpacing(10)
        self.project_overview_card.body_layout.setSpacing(10)
        self.project_overview_card.body_layout.addLayout(metadata_layout)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.project_overview_card, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        project = self._document.project
        with QSignalBlocker(self.project_name_edit):
            self.project_name_edit.setText(project.meta.name)
        _sync_text_editor_contents(self.project_description_edit, project.meta.description)
        self.project_root_value.set_path_text(str(self._document.project_root), max_length=92)
        self._refresh_condition_profile_widgets()

    def _refresh_condition_profile_widgets(self) -> None:
        profiles = self._load_condition_template_profiles()
        self._condition_profiles_by_id = {profile.profile_id: profile for profile in profiles}
        selected_profile_id = self._document.project.settings.condition_profile_id
        with QSignalBlocker(self.condition_profile_combo):
            self.condition_profile_combo.clear()
            for profile in profiles:
                self.condition_profile_combo.addItem(
                    profile.display_name,
                    userData=profile.profile_id,
                )
            if selected_profile_id is None:
                self.condition_profile_combo.setCurrentIndex(-1)
            else:
                selected_index = self.condition_profile_combo.findData(selected_profile_id)
                self.condition_profile_combo.setCurrentIndex(
                    selected_index if selected_index >= 0 else -1
                )

        selected_profile: ConditionTemplateProfile | None = (
            self._condition_profiles_by_id.get(selected_profile_id)
            if selected_profile_id is not None
            else None
        )
        self.apply_profile_to_conditions_button.setEnabled(
            selected_profile is not None and bool(self._document.project.conditions)
        )

    def _apply_project_name(self) -> None:
        try:
            self._document.update_project_name(self.project_name_edit.text())
        except Exception as error:  # pragma: no cover - exercised via GUI tests
            _show_error_dialog(self, "Project Name Error", error)
            self.refresh()

    def _apply_project_description(self) -> None:
        description = self.project_description_edit.toPlainText()
        if description == self._document.project.meta.description:
            return
        try:
            self._document.update_project_description(description)
        except Exception as error:  # pragma: no cover - exercised via GUI tests
            _show_error_dialog(self, "Project Description Error", error)
            self.refresh()

    def _apply_condition_profile_selection(self) -> None:
        profile_id = self.condition_profile_combo.currentData()
        if not profile_id:
            return
        profile = self._condition_profiles_by_id.get(str(profile_id))
        if profile is None:
            return
        try:
            self._document.apply_condition_template_profile(
                profile,
                apply_to_existing_conditions=False,
            )
        except Exception as error:
            _show_error_dialog(self, "Condition Template Error", error)
            self.refresh()

    def _open_template_manager(self) -> None:
        try:
            self._manage_condition_templates()
        except Exception as error:
            _show_error_dialog(self, "Condition Template Error", error)
            return
        self.refresh()

    def _apply_profile_to_conditions(self) -> None:
        profile_id = self._document.project.settings.condition_profile_id
        if profile_id is None:
            QMessageBox.warning(
                self,
                "No Condition Template Selected",
                "Select a condition template profile before applying defaults to all conditions.",
            )
            return
        profile = self._condition_profiles_by_id.get(profile_id)
        if profile is None:
            QMessageBox.warning(
                self,
                "Condition Template Missing",
                "The selected condition template profile is missing from the global library.",
            )
            return
        try:
            self._document.apply_condition_template_profile(
                profile,
                apply_to_existing_conditions=True,
            )
        except Exception as error:
            _show_error_dialog(self, "Condition Template Error", error)
            self.refresh()
