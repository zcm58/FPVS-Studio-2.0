"""Home and setup-guide pages for the FPVS Studio main window."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
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
    SectionCard,
    StatusBadgeLabel,
    apply_home_page_theme,
    create_home_project_icon,
    mark_home_launch_action,
    mark_secondary_action,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.project_overview_page import ProjectOverviewEditor
from fpvs_studio.gui.runtime_settings_page import DisplaySettingsEditor
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
    ("runtime", "Display", "Display Settings"),
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
        self.runtime_settings_editor = DisplaySettingsEditor(
            document,
            object_name_prefix="dashboard_",
            editable=False,
            framed=True,
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

    def sync_fullscreen_checkbox(self, _checked: bool) -> None:
        return

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
                f"{'Complete' if runtime_ready else 'Needs setup'}: Display - "
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

        self.open_project_button = QPushButton("Open Project", self)
        self.open_project_button.setObjectName("home_open_project_button")
        self.launch_button = QPushButton("Launch Experiment", self)
        self.launch_button.setObjectName("home_launch_experiment_button")
        mark_home_launch_action(self.launch_button)
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
            self.edit_setup_button,
        ):
            button.setMinimumHeight(38)
            button.setMinimumWidth(160)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.launch_button.setMinimumWidth(260)
        self.launch_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.launch_status_label = StatusBadgeLabel("Status: Setup Required", self)
        self.launch_status_label.setObjectName("home_launch_status_indicator")
        self.launch_status_label.setMinimumHeight(28)
        self.launch_status_summary = QLabel(self)
        self.launch_status_summary.setObjectName("home_launch_status_summary")
        self.launch_status_summary.setWordWrap(True)
        self.launch_status_summary.setMinimumHeight(28)

        launch_panel = QWidget(self)
        launch_panel.setObjectName("home_launch_panel")
        launch_panel.setMaximumWidth(860)
        launch_panel_layout = QVBoxLayout(launch_panel)
        launch_panel_layout.setContentsMargins(30, 28, 30, 28)
        launch_panel_layout.setSpacing(18)

        identity_row = QHBoxLayout()
        identity_row.setContentsMargins(0, 0, 0, 0)
        identity_row.setSpacing(PAGE_SECTION_GAP)
        self.project_icon = create_home_project_icon(launch_panel)
        identity_text = QWidget(launch_panel)
        identity_text_layout = QVBoxLayout(identity_text)
        identity_text_layout.setContentsMargins(0, 0, 0, 0)
        identity_text_layout.setSpacing(6)

        self.current_project_header = QLabel(identity_text)
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
            identity_text,
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

        identity_text_layout.addWidget(self.current_project_header)
        identity_text_layout.addWidget(self.current_project_subtitle)
        identity_row.addWidget(
            self.project_icon,
            0,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
        )
        identity_row.addWidget(identity_text, 1)
        identity_row.addWidget(
            self.launch_status_label,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )
        launch_panel_layout.addLayout(identity_row)

        action_layout = QGridLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setHorizontalSpacing(PAGE_SECTION_GAP)
        action_layout.setVerticalSpacing(PAGE_SECTION_GAP)
        for column, button in enumerate(
            (
                self.open_project_button,
                self.new_project_button,
                self.save_project_button,
                self.edit_setup_button,
            )
        ):
            action_layout.addWidget(button, 0, column)
            action_layout.setColumnStretch(column, 1)
        launch_panel_layout.addLayout(action_layout)

        self.condition_count_value = self._new_value_label(
            "home_condition_count_value",
            role="primary",
        )
        self.block_count_value = self._new_value_label(
            "home_block_count_value",
            role="primary",
        )
        self.fixation_task_value = self._new_value_label("home_fixation_task_value")
        self.accuracy_task_value = self._new_value_label("home_accuracy_task_value")

        launch_panel_layout.addWidget(self.launch_status_summary)

        metrics_panel = QFrame(launch_panel)
        metrics_panel.setObjectName("home_metrics_panel")
        metrics_layout = QGridLayout(metrics_panel)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setHorizontalSpacing(0)
        metrics_layout.setVerticalSpacing(0)
        self._add_metric(metrics_layout, 0, "Conditions", self.condition_count_value)
        self._add_metric(metrics_layout, 1, "Blocks", self.block_count_value)
        self._add_metric(metrics_layout, 2, "Fixation Task", self.fixation_task_value)
        self._add_metric(metrics_layout, 3, "Accuracy Task", self.accuracy_task_value)
        for column in range(4):
            metrics_layout.setColumnStretch(column, 1)
        launch_panel_layout.addWidget(metrics_panel)
        launch_panel_layout.addWidget(self.launch_button, 0, Qt.AlignmentFlag.AlignCenter)

        launch_panel_row = QHBoxLayout()
        launch_panel_row.setContentsMargins(0, 40, 0, 0)
        launch_panel_row.addStretch(1)
        launch_panel_row.addWidget(launch_panel, 4)
        launch_panel_row.addStretch(1)

        page_layout = self.page_container.content_layout
        page_layout.addLayout(launch_panel_row)
        page_layout.addStretch(1)

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
            self._project_description_text(project.meta.description)
        )

        self.condition_count_value.setText(str(len(ordered_conditions)))
        self.block_count_value.setText(str(session_settings.block_count))
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

    def _set_status_indicator(self, report: LauncherReadinessReport) -> None:
        self.launch_status_label.set_state(report.badge_state, f"Status: {report.status_label}")
        self.launch_status_summary.setText(report.status_summary)

    def _add_metric(
        self,
        layout: QGridLayout,
        column: int,
        label_text: str,
        value_widget: QLabel,
    ) -> None:
        metric_cell = QFrame(self)
        metric_cell.setObjectName("home_metric_cell")
        cell_layout = QVBoxLayout(metric_cell)
        cell_layout.setContentsMargins(14, 12, 14, 12)
        cell_layout.setSpacing(8)
        row_label = QLabel(label_text, metric_cell)
        row_label.setObjectName("home_metric_label")
        row_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_widget.setProperty("homeValueRole", "primary")
        value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cell_layout.addWidget(row_label)
        cell_layout.addWidget(value_widget)
        layout.addWidget(metric_cell, 0, column)

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

