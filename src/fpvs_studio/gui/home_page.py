"""Home and setup-guide pages for the FPVS Studio main window."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.models import ConditionTemplateProfile
from fpvs_studio.gui.assets_pages import AssetsReadinessEditor
from fpvs_studio.gui.components import (
    PAGE_SECTION_GAP,
    NonHomePageShell,
    PageContainer,
    PathValueLabel,
    SectionCard,
    StatusBadgeLabel,
    apply_home_page_theme,
    mark_launch_action,
    mark_secondary_action,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.project_overview_page import ProjectOverviewEditor
from fpvs_studio.gui.runtime_settings_page import RuntimeSettingsEditor
from fpvs_studio.gui.session_pages import FixationSettingsEditor, SessionStructureEditor
from fpvs_studio.gui.window_helpers import (
    LauncherReadinessReport,
    _conditions_have_assigned_assets,
    _configure_read_only_list,
    _launcher_readiness_report,
    _set_list_items,
)

_SETUP_GUIDE_STEPS: tuple[tuple[str, str, str], ...] = (
    ("project", "Project Details", "Edit Project"),
    ("conditions", "Conditions", "Edit Conditions"),
    ("stimuli", "Stimuli", "Open Stimuli"),
    ("session", "Session / Fixation", "Edit Session"),
    ("runtime", "Runtime", "Runtime Settings"),
    ("ready", "Validate / Ready", "Review Readiness"),
)


class SetupDashboardPage(QWidget):
    """Guided setup page that keeps the existing editors available for compatibility."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        load_condition_template_profiles: Callable[[], list[ConditionTemplateProfile]],
        manage_condition_templates: Callable[[], list[ConditionTemplateProfile]],
        fullscreen_state_getter: Callable[[], bool] | None = None,
        fullscreen_state_setter: Callable[[bool], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._step_callbacks: dict[str, Callable[[], None]] = {}
        self.shell = NonHomePageShell(
            title="Setup Guide",
            subtitle=(
                "Follow the setup steps once, then return to Home for routine launches."
            ),
            layout_mode="single_column",
            width_preset="wide",
            parent=self,
        )
        self.shell.set_footer_text(
            "Setup Guide actions use the same project state and detailed editors as the "
            "rest of FPVS Studio."
        )

        self.setup_summary_card = SectionCard(
            title="Setup Progress",
            subtitle="Step-by-step status for getting this project ready to launch.",
            object_name="dashboard_attention_card",
            parent=self,
        )
        self.setup_summary_card.card_layout.setContentsMargins(12, 10, 12, 10)
        self.setup_summary_card.card_layout.setSpacing(8)
        self.setup_summary_card.body_layout.setSpacing(6)
        self.setup_summary_badge = StatusBadgeLabel(
            "Checking readiness...", self.setup_summary_card
        )
        self.setup_summary_badge.setObjectName("setup_guide_ready_badge")
        self.setup_summary_note = QLabel(self.setup_summary_card)
        self.setup_summary_note.setObjectName("dashboard_attention_note")
        self.setup_summary_note.setWordWrap(True)
        self.setup_summary_count = QLabel(self.setup_summary_card)
        self.setup_summary_count.setObjectName("dashboard_attention_count")
        self.setup_summary_count.setWordWrap(True)
        summary_strip = QWidget(self.setup_summary_card)
        summary_strip_layout = QHBoxLayout(summary_strip)
        summary_strip_layout.setContentsMargins(0, 0, 0, 0)
        summary_strip_layout.setSpacing(PAGE_SECTION_GAP)
        summary_strip_layout.addWidget(self.setup_summary_badge, 0)
        summary_strip_layout.addWidget(self.setup_summary_count, 0)
        summary_strip_layout.addWidget(self.setup_summary_note, 1)
        self.setup_summary_card.body_layout.addWidget(summary_strip)

        self.setup_guide_step_list = QListWidget(self.setup_summary_card)
        self.setup_guide_step_list.setObjectName("setup_guide_step_list")
        _configure_read_only_list(self.setup_guide_step_list)
        self.setup_summary_card.body_layout.addWidget(self.setup_guide_step_list)

        self.step_actions_card = SectionCard(
            title="Setup Steps",
            subtitle="Use these actions to complete or review each setup area.",
            object_name="setup_guide_steps_card",
            parent=self,
        )
        self.step_action_buttons: dict[str, QPushButton] = {}
        step_actions_grid = QGridLayout()
        step_actions_grid.setContentsMargins(0, 0, 0, 0)
        step_actions_grid.setHorizontalSpacing(PAGE_SECTION_GAP)
        step_actions_grid.setVerticalSpacing(8)
        for index, (step_key, _step_title, action_label) in enumerate(_SETUP_GUIDE_STEPS):
            button = QPushButton(action_label, self.step_actions_card)
            button.setObjectName(f"setup_guide_{step_key}_button")
            mark_secondary_action(button)
            button.clicked.connect(lambda _checked=False, key=step_key: self._activate_step(key))
            self.step_action_buttons[step_key] = button
            step_actions_grid.addWidget(button, index // 3, index % 3)
        self.step_actions_card.body_layout.addLayout(step_actions_grid)

        self.project_overview_editor = ProjectOverviewEditor(
            document,
            load_condition_template_profiles=load_condition_template_profiles,
            manage_condition_templates=manage_condition_templates,
            parent=self.shell,
        )
        self.session_structure_editor = SessionStructureEditor(
            document,
            object_name_prefix="dashboard_",
            parent=self.shell,
        )
        self.fixation_settings_editor = FixationSettingsEditor(
            document,
            schedule_row_behavior="disable",
            parent=self.shell,
        )
        self.runtime_settings_editor = RuntimeSettingsEditor(
            document,
            object_name_prefix="dashboard_",
            editable=False,
            fullscreen_state_getter=fullscreen_state_getter,
            fullscreen_state_setter=fullscreen_state_setter,
            parent=self.shell,
        )
        self.assets_readiness_editor = AssetsReadinessEditor(
            document,
            object_name_prefix="dashboard_",
            parent=self.shell,
        )
        self.workspace = QWidget(self.shell)
        workspace_layout = QHBoxLayout(self.workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(PAGE_SECTION_GAP)

        self.workspace_left_column = QWidget(self.workspace)
        left_layout = QVBoxLayout(self.workspace_left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(PAGE_SECTION_GAP)
        left_layout.addWidget(self.project_overview_editor)
        left_layout.addWidget(self.session_structure_editor)

        self.workspace_center_column = QWidget(self.workspace)
        center_layout = QVBoxLayout(self.workspace_center_column)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addWidget(self.fixation_settings_editor)

        self.workspace_right_column = QWidget(self.workspace)
        right_layout = QVBoxLayout(self.workspace_right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(PAGE_SECTION_GAP)
        right_layout.addWidget(self.assets_readiness_editor)
        right_layout.addWidget(self.runtime_settings_editor)

        workspace_layout.addWidget(self.workspace_left_column, 3)
        workspace_layout.addWidget(self.workspace_center_column, 4)
        workspace_layout.addWidget(self.workspace_right_column, 3)

        self.shell.add_content_widget(self.setup_summary_card)
        self.shell.add_content_widget(self.step_actions_card)
        self.shell.add_content_widget(self.workspace, stretch=1)
        self.workspace.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.shell)

        self._document.project_changed.connect(self._refresh_attention_summary)
        self._document.session_plan_changed.connect(self._refresh_attention_summary)
        self._refresh_attention_summary()

    def sync_fullscreen_checkbox(self, checked: bool) -> None:
        self.runtime_settings_editor.set_fullscreen_checked(checked)

    def bind_step_navigation_actions(
        self,
        *,
        edit_conditions: Callable[[], None],
        open_stimuli_manager: Callable[[], None],
        open_runtime_settings: Callable[[], None],
    ) -> None:
        self._step_callbacks = {
            "project": self._show_embedded_setup_editors,
            "conditions": edit_conditions,
            "stimuli": open_stimuli_manager,
            "session": self._show_embedded_setup_editors,
            "runtime": open_runtime_settings,
            "ready": self._hide_embedded_setup_editors,
        }

    def _activate_step(self, step_key: str) -> None:
        callback = self._step_callbacks.get(step_key)
        if callback is not None:
            callback()

    def _show_embedded_setup_editors(self) -> None:
        self.workspace.setVisible(True)

    def _hide_embedded_setup_editors(self) -> None:
        self.workspace.setVisible(False)

    def _refresh_attention_summary(self) -> None:
        report = _launcher_readiness_report(
            self._document,
            refresh_hz=self.runtime_settings_editor.current_refresh_hz(),
        )
        action_items = tuple(
            item
            for item in report.readiness_items
            if item.startswith(("Needs setup:", "Warning:"))
        )
        issue_count = len(action_items)
        self.setup_summary_badge.set_state(report.badge_state, report.status_label)
        self.setup_summary_count.setText(f"Blockers: {issue_count}")
        first_blocker = (
            action_items[0]
            if action_items
            else "No blockers. Setup is ready for preview or launch."
        )
        summary_text = first_blocker
        if report.preview_note:
            summary_text = f"{summary_text} {report.preview_note}"
        self.setup_summary_note.setText(summary_text)
        _set_list_items(self.setup_guide_step_list, self._setup_step_lines(report))

    def _setup_step_lines(self, report: LauncherReadinessReport) -> tuple[str, ...]:
        ordered_conditions = self._document.ordered_conditions()
        project_name = self._document.project.meta.name.strip()
        project_ready = bool(project_name and self._document.project_root)
        assets_ready = _conditions_have_assigned_assets(self._document, ordered_conditions)
        runtime_ready = self.runtime_settings_editor.current_refresh_hz() > 0.0
        launch_ready = report.badge_state == "ready"

        project_label = project_name or "name required"
        stimuli_label = (
            "assigned for all conditions" if assets_ready else "base and oddball folders needed"
        )
        return (
            (
                f"{'Complete' if project_ready else 'Needs setup'}: "
                f"Project Details - {project_label}"
            ),
            (
                f"{'Complete' if ordered_conditions else 'Needs setup'}: Conditions - "
                f"{len(ordered_conditions)} configured"
            ),
            (
                f"{'Complete' if assets_ready else 'Needs setup'}: Stimuli - "
                f"{stimuli_label}"
            ),
            "Complete: Session / Fixation - settings available",
            (
                f"{'Complete' if runtime_ready else 'Needs setup'}: Runtime - "
                f"{self.runtime_settings_editor.current_refresh_hz():.2f} Hz"
            ),
            (
                f"{'Complete' if launch_ready else 'Needs setup'}: Validate / Ready - "
                f"{report.status_label}"
            ),
        )


class HomePage(QWidget):
    """Launcher-oriented overview page for the current project."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        load_condition_template_profiles: Callable[[], list[ConditionTemplateProfile]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._load_condition_template_profiles = load_condition_template_profiles
        self.setObjectName("home_page")
        self.page_container = PageContainer(width_preset="wide", parent=self)

        self.current_project_header = QLabel(self.page_container.header_widget)
        self.current_project_header.setObjectName("home_current_project_header")
        self.current_project_header.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.current_project_header.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.current_project_subtitle = QLabel(
            "Open a project, confirm its identity, and launch quickly.",
            self.page_container.header_widget,
        )
        self.current_project_subtitle.setObjectName("home_current_project_subtitle")
        self.current_project_subtitle.setWordWrap(True)
        self.current_project_subtitle.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.current_project_subtitle.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.page_container.header_layout.addWidget(self.current_project_header)
        self.page_container.header_layout.addWidget(self.current_project_subtitle)
        self.page_container.header_widget.setVisible(True)

        self.open_project_button = QPushButton("Open Project", self)
        self.open_project_button.setObjectName("home_open_project_button")
        self.launch_button = QPushButton("Launch Experiment", self)
        self.launch_button.setObjectName("home_launch_experiment_button")
        mark_launch_action(self.launch_button, home=True)
        self.save_project_button = QPushButton("Save", self)
        self.save_project_button.setObjectName("home_save_project_button")
        self.new_project_button = QPushButton("Create New Project", self)
        self.new_project_button.setObjectName("home_create_project_button")
        self.edit_setup_button = QPushButton("Edit Setup", self)
        self.edit_setup_button.setObjectName("home_edit_setup_button")
        mark_secondary_action(self.edit_setup_button)

        for button in (
            self.open_project_button,
            self.new_project_button,
            self.save_project_button,
            self.launch_button,
            self.edit_setup_button,
        ):
            button.setMinimumHeight(38)
            button.setFixedWidth(176)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(PAGE_SECTION_GAP)
        action_layout.addWidget(self.open_project_button)
        action_layout.addWidget(self.new_project_button)
        action_layout.addWidget(self.save_project_button)
        action_layout.addStretch(1)
        action_layout.addWidget(self.launch_button)

        navigation_layout = QHBoxLayout()
        navigation_layout.setContentsMargins(0, 0, 0, 0)
        navigation_layout.setSpacing(PAGE_SECTION_GAP)
        navigation_layout.addWidget(self.edit_setup_button)
        navigation_layout.addStretch(1)

        project_card = SectionCard(
            title="Project Info",
            subtitle="Project identity and template settings.",
            object_name="home_project_card",
            parent=self,
        )
        project_layout = QFormLayout()
        project_layout.setContentsMargins(0, 0, 0, 0)
        project_layout.setVerticalSpacing(6)
        project_layout.setHorizontalSpacing(12)
        self.project_name_value = self._new_value_label(
            "home_project_name_value",
            role="primary",
        )
        self.project_root_value = PathValueLabel(self)
        self.project_root_value.setObjectName("home_project_root_value")
        self.project_template_value = self._new_value_label("home_project_template_value")
        self.project_description_value = self._new_value_label("home_project_description_value")
        self._add_summary_row(project_layout, "Project Name", self.project_name_value)
        self._add_summary_row(project_layout, "Description", self.project_description_value)
        self._add_summary_row(project_layout, "Template", self.project_template_value)
        self._add_summary_row(project_layout, "Root Path", self.project_root_value)
        project_card.card_layout.setContentsMargins(12, 10, 12, 10)
        project_card.card_layout.setSpacing(6)
        project_card.body_layout.setSpacing(6)
        project_card.body_layout.addLayout(project_layout)

        session_card = SectionCard(
            title="Session Summary",
            subtitle="Compact launch essentials.",
            object_name="home_session_card",
            parent=self,
        )
        session_layout = QFormLayout()
        session_layout.setContentsMargins(0, 0, 0, 0)
        session_layout.setVerticalSpacing(6)
        session_layout.setHorizontalSpacing(12)
        self.condition_count_value = self._new_value_label(
            "home_condition_count_value",
            role="primary",
        )
        self.block_count_value = self._new_value_label(
            "home_block_count_value",
            role="primary",
        )
        self.session_randomization_value = self._new_value_label("home_session_randomization_value")
        self.fixation_task_value = self._new_value_label("home_fixation_task_value")
        self.accuracy_task_value = self._new_value_label("home_accuracy_task_value")
        self._add_summary_row(session_layout, "Condition Count", self.condition_count_value)
        self._add_summary_row(session_layout, "Block Count", self.block_count_value)
        self._add_summary_row(session_layout, "Order Strategy", self.session_randomization_value)
        self._add_summary_row(session_layout, "Fixation Task", self.fixation_task_value)
        self._add_summary_row(session_layout, "Accuracy Task", self.accuracy_task_value)
        session_card.card_layout.setContentsMargins(12, 10, 12, 10)
        session_card.card_layout.setSpacing(6)
        session_card.body_layout.setSpacing(6)
        session_card.body_layout.addLayout(session_layout)

        self.launch_status_label = StatusBadgeLabel("Status: Setup Required", self)
        self.launch_status_label.setObjectName("home_launch_status_indicator")
        self.launch_status_label.setMinimumHeight(28)
        self.launch_status_summary = QLabel(self)
        self.launch_status_summary.setObjectName("home_launch_status_summary")
        self.launch_status_summary.setWordWrap(True)
        self.launch_status_summary.setMinimumHeight(28)
        self.launch_readiness_list = QListWidget(self)
        self.launch_readiness_list.setObjectName("home_readiness_list")
        _configure_read_only_list(self.launch_readiness_list)

        status_card = SectionCard(
            title="Launch Readiness",
            subtitle="Project launch state, task checklist, and alpha runtime note.",
            object_name="home_status_card",
            parent=self,
        )
        status_card.card_layout.setContentsMargins(12, 10, 12, 10)
        status_card.card_layout.setSpacing(8)
        status_card.body_layout.setSpacing(PAGE_SECTION_GAP)
        status_card.body_layout.addWidget(self.launch_status_label)
        status_card.body_layout.addWidget(self.launch_status_summary)
        status_card.body_layout.addWidget(self.launch_readiness_list)

        left_column = QWidget(self)
        left_column_layout = QVBoxLayout(left_column)
        left_column_layout.setContentsMargins(0, 0, 0, 0)
        left_column_layout.setSpacing(PAGE_SECTION_GAP)
        left_column_layout.addWidget(project_card)
        left_column_layout.addWidget(session_card)

        main_row = QHBoxLayout()
        main_row.setContentsMargins(0, 0, 0, 0)
        main_row.setSpacing(PAGE_SECTION_GAP)
        main_row.addWidget(left_column, 5)
        main_row.addWidget(status_card, 4)

        page_layout = self.page_container.content_layout
        page_layout.addLayout(action_layout)
        page_layout.addLayout(navigation_layout)
        page_layout.addLayout(main_row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.page_container)

        apply_home_page_theme(self)

        self._document.project_changed.connect(self.refresh)
        self._document.session_plan_changed.connect(self.refresh)
        self.refresh()

    def bind_quick_actions(
        self,
        *,
        new_project_action: QAction,
        open_project_action: QAction,
        save_project_action: QAction,
        launch_action: QAction,
    ) -> None:
        self._bind_button_to_action(
            self.new_project_button,
            new_project_action,
            "Create New Project",
        )
        self._bind_button_to_action(
            self.open_project_button,
            open_project_action,
            "Open Project",
        )
        self._bind_button_to_action(self.save_project_button, save_project_action, "Save")
        self._bind_button_to_action(
            self.launch_button,
            launch_action,
            "Launch Experiment",
        )

    def bind_navigation_actions(
        self,
        *,
        edit_setup: Callable[[], None],
    ) -> None:
        self.edit_setup_button.clicked.connect(edit_setup)

    def refresh(self) -> None:
        project = self._document.project
        session_settings = project.settings.session
        fixation_settings = project.settings.fixation_task
        ordered_conditions = self._document.ordered_conditions()
        report = self._status_report()

        self.current_project_header.setText(project.meta.name)
        self.current_project_subtitle.setText(
            "Open a project, confirm readiness, and launch quickly."
        )
        self.project_name_value.setText(project.meta.name)
        project_root_text = str(self._document.project_root)
        self.project_root_value.set_path_text(project_root_text, max_length=96)
        self.project_template_value.setText(self._condition_template_summary_text())
        self.project_description_value.setText(
            self._project_description_text(project.meta.description)
        )

        self.condition_count_value.setText(str(len(ordered_conditions)))
        self.block_count_value.setText(str(session_settings.block_count))
        self.session_randomization_value.setText(self._session_order_text())
        self.fixation_task_value.setText("Enabled" if fixation_settings.enabled else "Disabled")
        self.accuracy_task_value.setText(
            "Enabled" if fixation_settings.accuracy_task_enabled else "Disabled"
        )
        self._set_status_indicator(report)

    def _status_report(self) -> LauncherReadinessReport:
        return _launcher_readiness_report(
            self._document,
            refresh_hz=self._status_refresh_hz(),
        )

    def _status_refresh_hz(self) -> float:
        preferred_refresh = self._document.project.settings.display.preferred_refresh_hz
        return float(preferred_refresh if preferred_refresh is not None else 60.0)

    @staticmethod
    def _project_description_text(description: str) -> str:
        compact = " ".join(description.split())
        if not compact:
            return "No description set yet."
        if len(compact) > 160:
            compact = f"{compact[:157]}..."
        return compact

    def _condition_template_summary_text(self) -> str:
        profile_id = self._document.project.settings.condition_profile_id
        if profile_id is None:
            return "No template selected"
        profiles_by_id = {
            profile.profile_id: profile for profile in self._load_condition_template_profiles()
        }
        profile = profiles_by_id.get(profile_id)
        if profile is None:
            return f"Missing template: {profile_id}"
        return profile.display_name

    def _set_status_indicator(self, report: LauncherReadinessReport) -> None:
        self.launch_status_label.set_state(report.badge_state, f"Status: {report.status_label}")
        summary_text = report.status_summary
        if report.preview_note:
            summary_text = f"{summary_text} {report.preview_note}"
        self.launch_status_summary.setText(summary_text)
        _set_list_items(self.launch_readiness_list, report.readiness_items)

    def _add_summary_row(
        self,
        layout: QFormLayout,
        label_text: str,
        value_widget: QWidget,
    ) -> None:
        row_label = QLabel(label_text, self)
        row_label.setProperty("homeFieldLabel", "true")
        row_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addRow(row_label, value_widget)

    def _new_value_label(
        self,
        object_name: str,
        *,
        role: str = "secondary",
        selectable: bool = False,
    ) -> QLabel:
        label = QLabel(self)
        label.setObjectName(object_name)
        label.setProperty("homeValueRole", role)
        label.setWordWrap(True)
        if selectable:
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    @staticmethod
    def _bind_button_to_action(button: QPushButton, action: QAction, label: str) -> None:
        button.setText(label)
        if action.toolTip():
            button.setToolTip(action.toolTip())
        if action.statusTip():
            button.setStatusTip(action.statusTip())
        button.clicked.connect(lambda _checked=False, target=action: target.trigger())

    def _session_order_text(self) -> str:
        ordered_conditions = self._document.ordered_conditions()
        if not ordered_conditions:
            return "No conditions configured yet."

        if (
            self._document.project.settings.session.randomize_conditions_per_block
            and len(ordered_conditions) > 1
        ):
            return "Randomized within each block."
        return "Fixed project order."
