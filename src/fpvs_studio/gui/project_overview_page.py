"""Project overview page for the FPVS Studio main window."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QSignalBlocker, QSize, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.condition_template_profiles import (
    SINUSOIDAL_CONTRAST_PROFILE_ID,
    SIXTY_HZ_BLANK_FIXATION_PROFILE_ID,
    STUDIO_DEFAULT_PROFILE_ID,
    is_supported_condition_template,
)
from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.experiment_categories import experiment_category_label
from fpvs_studio.core.models import ConditionTemplateProfile
from fpvs_studio.gui.components import (
    PathValueLabel,
    SectionCard,
    apply_project_overview_theme,
    configure_setup_form,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import (
    DebouncedTextCommitter,
    LeftToRightPlainTextEdit,
    _show_error_dialog,
    _sync_text_editor_contents,
)

_CONDITION_PROFILE_TOOLTIPS = {
    STUDIO_DEFAULT_PROFILE_ID: (
        "Use this template if you want to display one image immediately after the "
        "previous image with no blanks in between."
    ),
    SIXTY_HZ_BLANK_FIXATION_PROFILE_ID: (
        "Use this template if you'd like to display images with 50% of the image "
        "display period being blank before the next image is shown."
    ),
    SINUSOIDAL_CONTRAST_PROFILE_ID: (
        "Use this template for image conditions with sinusoidal contrast modulation. "
        "It also selects the required Neutral Gray (#808080) presentation background."
    ),
}
_PARTICIPANT_TUTORIAL_TOOLTIP = (
    "Run three practice fixation color changes before the first condition starts when "
    "fixation accuracy tracking is enabled."
)
_REPEAT_PARTICIPANT_SESSIONS_TOOLTIP = (
    "Let a participant return using the same participant number for Session 2,\n"
    "Session 3, and later visits. Each visit has separate results.\n"
    "Previous session data is preserved.\n\n"
    "When off, a participant number with an earlier session cannot be used\n"
    "again in this project. This does not change condition repeats within a session."
)


class _ProjectFolderValueLabel(PathValueLabel):
    """Fit the folder path to its card while retaining the complete value."""

    def __init__(self, parent: QWidget) -> None:
        self._full_path = ""
        super().__init__(parent)
        self.setIndent(0)

    def set_full_path(self, path: str) -> None:
        self._full_path = path
        self.setToolTip(path)
        self.setAccessibleDescription(path)
        self._fit_path()

    def _fit_path(self) -> None:
        if self._full_path:
            available_width = max(0, self.contentsRect().width() - 2 * self.margin())
            self.setText(self.fontMetrics().elidedText(
                self._full_path, Qt.TextElideMode.ElideMiddle, available_width,
            ))

    def sizeHint(self) -> QSize:  # noqa: N802
        hint = super().sizeHint()
        hint.setWidth(0)
        return hint

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        hint = super().minimumSizeHint()
        hint.setWidth(0)
        return hint

    def event(self, event: QEvent) -> bool:
        handled = super().event(event)
        if event.type() in (
            QEvent.Type.Resize, QEvent.Type.FontChange,
            QEvent.Type.StyleChange, QEvent.Type.ContentsRectChange,
        ):
            self._fit_path()
        return handled


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
        self._displayed_condition_profiles: tuple[ConditionTemplateProfile, ...] | None = None

        self.project_name_edit = QLineEdit(self)
        self.project_name_edit.setObjectName("project_name_edit")
        self.project_name_edit.editingFinished.connect(self._apply_project_name)
        self.experiment_category_value = QLabel(self)
        self.experiment_category_value.setObjectName("project_experiment_category")
        self.experiment_category_value.setToolTip(
            "Experiment category is fixed. Create a new experiment to use another category."
        )

        self.project_description_edit = LeftToRightPlainTextEdit(self)
        self.project_description_edit.setObjectName("project_description_edit")
        self.project_description_edit.setPlaceholderText(
            "Describe the project goal and participant instructions."
        )
        self.project_description_edit.setFixedHeight(104)
        self.project_description_edit.setMaximumBlockCount(20)
        self._description_committer = DebouncedTextCommitter(
            self.project_description_edit,
            self._apply_project_description,
        )
        self.project_description_edit.textChanged.connect(self._description_committer.schedule)

        self.project_root_value = _ProjectFolderValueLabel(self)
        self.project_root_value.setObjectName("project_root_value")
        self.project_root_value.setWordWrap(False)
        self.project_root_value.setFixedHeight(32)
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
            "Apply Template To All Conditions",
            self,
        )
        self.apply_profile_to_conditions_button.setObjectName("apply_profile_to_conditions_button")
        self.apply_profile_to_conditions_button.setToolTip(
            "Apply the selected default timing template to all existing conditions."
        )
        self.apply_profile_to_conditions_button.clicked.connect(self._apply_profile_to_conditions)
        self.apply_profile_to_conditions_button.setVisible(False)
        self.participant_tutorial_checkbox = QCheckBox("Enable participant tutorial", self)
        self.participant_tutorial_checkbox.setObjectName("participant_tutorial_checkbox")
        self.participant_tutorial_checkbox.setToolTip(_PARTICIPANT_TUTORIAL_TOOLTIP)
        self.participant_tutorial_checkbox.stateChanged.connect(
            self._apply_participant_tutorial_enabled
        )
        self.repeat_participant_sessions_checkbox = QCheckBox(
            "Allow repeat participant sessions", self,
        )
        self.repeat_participant_sessions_checkbox.setObjectName(
            "allow_repeated_participant_sessions_checkbox"
        )
        self.repeat_participant_sessions_checkbox.setToolTip(
            _REPEAT_PARTICIPANT_SESSIONS_TOOLTIP
        )
        self.repeat_participant_sessions_checkbox.setWhatsThis(
            _REPEAT_PARTICIPANT_SESSIONS_TOOLTIP
        )
        self.repeat_participant_sessions_checkbox.setAccessibleDescription(
            _REPEAT_PARTICIPANT_SESSIONS_TOOLTIP
        )
        self.repeat_participant_sessions_checkbox.toggled.connect(
            self._apply_repeat_participant_sessions
        )

        condition_profile_group = QWidget(self)
        condition_profile_group.setObjectName("project_condition_profile_group")
        condition_profile_layout = QVBoxLayout(condition_profile_group)
        condition_profile_layout.setContentsMargins(0, 0, 0, 0)
        condition_profile_layout.setSpacing(4)
        condition_profile_layout.addWidget(self.condition_profile_combo)

        self.condition_profile_actions = QWidget(condition_profile_group)
        self.condition_profile_actions.setObjectName("project_condition_profile_actions")
        self.condition_profile_actions.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        condition_profile_actions_layout = QHBoxLayout(self.condition_profile_actions)
        condition_profile_actions_layout.setContentsMargins(0, 0, 0, 0)
        condition_profile_actions_layout.setSpacing(8)
        condition_profile_actions_layout.addWidget(self.apply_profile_to_conditions_button)
        condition_profile_actions_layout.addWidget(self.manage_templates_button)
        condition_profile_actions_layout.addStretch(1)
        condition_profile_layout.addWidget(self.condition_profile_actions)

        self.project_overview_card = SectionCard(
            title="Project Details",
            object_name="dashboard_project_overview_card",
            parent=self,
        )
        self.project_overview_card.setMaximumWidth(1040)
        self.project_overview_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        self.project_overview_card.title_label.setVisible(False)
        self.project_overview_card.setProperty("setupFlatSection", "true")

        self.project_details_card = SectionCard(
            title="Project details",
            object_name="project_details_card",
            parent=self.project_overview_card,
        )
        self.experiment_setup_card = SectionCard(
            title="Experiment setup",
            object_name="experiment_setup_card",
            parent=self.project_overview_card,
        )
        for card in (self.project_details_card, self.experiment_setup_card):
            card.card_layout.setContentsMargins(16, 16, 16, 16)
            card.card_layout.setSpacing(16)
            card.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            card.body_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            card.setMinimumWidth(0)
        self.project_details_heading = self.project_details_card.title_label
        self.experiment_setup_heading = self.experiment_setup_card.title_label

        self.project_details_column = QWidget(self.project_details_card)
        self.project_details_column.setObjectName("project_details_column")
        details_layout = QVBoxLayout(self.project_details_column)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(16)
        metadata_layout = QFormLayout()
        metadata_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        metadata_layout.addRow("Project Name", self.project_name_edit)
        metadata_layout.addRow("Description (optional)", self.project_description_edit)
        metadata_layout.addRow("Project Folder", self.project_root_value)
        configure_setup_form(metadata_layout, stacked=True)
        details_layout.addLayout(metadata_layout)
        details_layout.addStretch(1)

        self.experiment_setup_column = QWidget(self.experiment_setup_card)
        self.experiment_setup_column.setObjectName("experiment_setup_column")
        setup_layout = QVBoxLayout(self.experiment_setup_column)
        setup_layout.setContentsMargins(0, 0, 0, 0)
        setup_layout.setSpacing(16)
        experiment_layout = QFormLayout()
        experiment_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        experiment_layout.addRow("Experiment Category", self.experiment_category_value)
        experiment_layout.addRow("Experiment Template", condition_profile_group)
        configure_setup_form(experiment_layout, stacked=True)
        setup_layout.addLayout(experiment_layout)
        setup_layout.addWidget(self.participant_tutorial_checkbox)
        setup_layout.addWidget(self.repeat_participant_sessions_checkbox)
        setup_layout.addStretch(1)
        self.project_details_card.body_layout.addWidget(self.project_details_column)
        self.experiment_setup_card.body_layout.addWidget(self.experiment_setup_column)

        form_panel = QWidget(self.project_overview_card)
        form_layout = QHBoxLayout(form_panel)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(24)
        form_layout.addWidget(self.project_details_card, 3)
        form_layout.addWidget(self.experiment_setup_card, 2)
        QWidget.setTabOrder(self.project_name_edit, self.project_description_edit)
        QWidget.setTabOrder(self.project_description_edit, self.condition_profile_combo)
        QWidget.setTabOrder(self.condition_profile_combo, self.apply_profile_to_conditions_button)
        QWidget.setTabOrder(self.apply_profile_to_conditions_button, self.manage_templates_button)
        QWidget.setTabOrder(self.manage_templates_button, self.participant_tutorial_checkbox)
        QWidget.setTabOrder(self.participant_tutorial_checkbox,
                           self.repeat_participant_sessions_checkbox)

        self.project_overview_card.card_layout.setContentsMargins(0, 0, 0, 0)
        self.project_overview_card.card_layout.setSpacing(0)
        self.project_overview_card.body_layout.setSpacing(0)
        self.project_overview_card.body_layout.addWidget(form_panel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.project_overview_card, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

        self._document.project_changed.connect(self.refresh)
        self.refresh()
        apply_project_overview_theme(self)
        self._sync_template_action_sizes()

    def refresh(self) -> None:
        project = self._document.project
        self.experiment_category_value.setText(
            experiment_category_label(project.experiment_category)
        )
        if not self.project_name_edit.isModified():
            with QSignalBlocker(self.project_name_edit):
                self.project_name_edit.setText(project.meta.name)
        if not self._description_committer.pending:
            _sync_text_editor_contents(self.project_description_edit, project.meta.description)
        self.project_root_value.set_full_path(str(self._document.project_root))
        self._refresh_condition_profile_widgets()
        with QSignalBlocker(self.participant_tutorial_checkbox):
            self.participant_tutorial_checkbox.setChecked(
                project.settings.fixation_task.participant_tutorial_enabled
            )
        self.participant_tutorial_checkbox.setEnabled(project.settings.fixation_task.show_cross)
        with QSignalBlocker(self.repeat_participant_sessions_checkbox):
            self.repeat_participant_sessions_checkbox.setChecked(
                project.settings.allow_repeated_participant_sessions
            )
        self._sync_template_action_sizes()

    def _sync_template_action_sizes(self) -> None:
        """Keep action text and padding visible after the application theme is applied."""

        buttons = (
            self.apply_profile_to_conditions_button,
            self.manage_templates_button,
        )
        for button in buttons:
            button.ensurePolished()
            button.setMinimumWidth(button.fontMetrics().horizontalAdvance(button.text()) + 32)
        action_height = max(button.sizeHint().height() for button in buttons)
        self.condition_profile_actions.setFixedHeight(action_height)

    def flush_pending_edits(self) -> None:
        self._description_committer.flush()

    def has_pending_edits(self) -> bool:
        return (
            self._description_committer.pending
            or self.project_name_edit.text() != self._document.project.meta.name
        )

    def _refresh_condition_profile_widgets(self) -> None:
        profiles = [
            profile
            for profile in self._load_condition_template_profiles()
            if profile.experiment_category == self._document.project.experiment_category
            and is_supported_condition_template(profile)
        ]
        self._condition_profiles_by_id = {profile.profile_id: profile for profile in profiles}
        project = self._document.project
        selected_profile_id = project.settings.condition_profile_id
        displayed_profile_id = selected_profile_id or self._profile_id_for_duty_cycle(
            project.settings.condition_defaults.duty_cycle_mode,
            profiles,
        )
        profile_snapshot = tuple(profiles)
        with QSignalBlocker(self.condition_profile_combo):
            if profile_snapshot != self._displayed_condition_profiles:
                self.condition_profile_combo.clear()
                for profile in profiles:
                    self.condition_profile_combo.addItem(
                        profile.display_name,
                        userData=profile.profile_id,
                    )
                    item_index = self.condition_profile_combo.count() - 1
                    tooltip = _CONDITION_PROFILE_TOOLTIPS.get(profile.profile_id)
                    if tooltip is not None:
                        self.condition_profile_combo.setItemData(
                            item_index,
                            tooltip,
                            Qt.ItemDataRole.ToolTipRole,
                        )
                self._displayed_condition_profiles = profile_snapshot
            if displayed_profile_id is None:
                self.condition_profile_combo.setCurrentIndex(-1)
            else:
                selected_index = self.condition_profile_combo.findData(displayed_profile_id)
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
        self.apply_profile_to_conditions_button.setVisible(bool(self._document.project.conditions))

    def _profile_id_for_duty_cycle(
        self,
        duty_cycle_mode: DutyCycleMode,
        profiles: list[ConditionTemplateProfile],
    ) -> str | None:
        for profile in profiles:
            if profile.defaults.condition.duty_cycle_mode == duty_cycle_mode:
                return profile.profile_id
        return None

    def _apply_project_name(self) -> None:
        if not self.project_name_edit.text().strip():
            return
        try:
            self._document.update_project_name(self.project_name_edit.text())
            self.project_name_edit.setModified(False)
        except Exception as error:  # pragma: no cover - exercised via GUI tests
            _show_error_dialog(self, "Project Name Error", error)
            self.project_name_edit.setModified(False)
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

    def _apply_participant_tutorial_enabled(self) -> None:
        enabled = self.participant_tutorial_checkbox.isChecked()
        if enabled == self._document.project.settings.fixation_task.participant_tutorial_enabled:
            return
        try:
            self._document.update_fixation_settings(participant_tutorial_enabled=enabled)
        except Exception as error:
            _show_error_dialog(self, "Participant Tutorial Error", error)
            self.refresh()

    def _open_template_manager(self) -> None:
        try:
            self._manage_condition_templates()
        except Exception as error:
            _show_error_dialog(self, "Condition Template Error", error)
            return
        self.refresh()

    def _apply_repeat_participant_sessions(self, enabled: bool) -> None:
        try:
            self._document.update_allow_repeated_participant_sessions(enabled)
        except Exception as error:
            _show_error_dialog(self, "Participant Sessions Error", error)
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
