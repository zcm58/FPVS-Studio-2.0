"""Guided setup wizard for FPVS Studio projects."""

from __future__ import annotations

import re
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.models import ConditionTemplateProfile
from fpvs_studio.gui.assets_pages import AssetsPage, AssetsReadinessEditor
from fpvs_studio.gui.components import (
    PAGE_SECTION_GAP,
    NonHomePageShell,
    SectionCard,
    StatusBadgeLabel,
    mark_primary_action,
    mark_secondary_action,
    refresh_widget_style,
)
from fpvs_studio.gui.condition_pages import ConditionsPage
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.project_overview_page import ProjectOverviewEditor
from fpvs_studio.gui.run_page import RunPage
from fpvs_studio.gui.runtime_settings_page import RuntimeSettingsEditor
from fpvs_studio.gui.session_pages import FixationSettingsEditor, SessionStructurePage
from fpvs_studio.gui.window_helpers import (
    LauncherReadinessReport,
    _conditions_have_assigned_assets,
    _configure_read_only_list,
    _launcher_readiness_report,
    _set_list_items,
)

_WIZARD_STEPS: tuple[tuple[str, str, str], ...] = (
    ("project", "Project Details", "Confirm the project name and template."),
    ("conditions", "Conditions", "Create and review the experiment conditions."),
    ("stimuli", "Stimuli", "Attach base and oddball image folders."),
    ("display", "Display Settings", "Set refresh rate and launch display options."),
    ("session", "Session Design", "Choose block order and inter-condition flow."),
    ("fixation", "Fixation Cross", "Configure fixation and accuracy-task essentials."),
    ("review", "Review", "Resolve blockers before returning to Home."),
)
_DEFAULT_CONDITION_NAME_RE = re.compile(r"^Condition \d+$")
_CREATE_ALL_CONDITIONS_PROMPT = "Please ensure you create all conditions before proceeding."


class SetupWizardPage(QWidget):
    """In-window guided setup flow backed by the shared project document."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        load_condition_template_profiles: Callable[[], list[ConditionTemplateProfile]],
        manage_condition_templates: Callable[[], list[ConditionTemplateProfile]],
        fullscreen_state_getter: Callable[[], bool] | None = None,
        fullscreen_state_setter: Callable[[bool], None] | None = None,
        on_return_home: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("setup_wizard_page")
        self._document = document
        self._on_return_home = on_return_home
        self._active_step_index = 0
        self._advanced_visible = False

        self.conditions_page = ConditionsPage(document, self)
        self.add_condition_button = self.conditions_page.add_condition_button
        self.add_condition_button.clicked.connect(self._show_first_condition_prompt_if_needed)
        self.assets_page = AssetsPage(document, self)
        self.run_page = RunPage(
            document,
            fullscreen_state_getter=fullscreen_state_getter,
            fullscreen_state_setter=fullscreen_state_setter,
            parent=self,
        )
        self.session_structure_page = SessionStructurePage(document, self)
        self.fixation_cross_settings_page = FixationSettingsEditor(
            document,
            schedule_row_behavior="disable",
            parent=self,
        )
        self.session_structure_editor = self.session_structure_page.editor
        self.fixation_settings_editor = self.fixation_cross_settings_page

        self.project_overview_editor = ProjectOverviewEditor(
            document,
            load_condition_template_profiles=load_condition_template_profiles,
            manage_condition_templates=manage_condition_templates,
            parent=self,
        )
        self.runtime_settings_editor = RuntimeSettingsEditor(
            document,
            fullscreen_state_getter=fullscreen_state_getter,
            fullscreen_state_setter=fullscreen_state_setter,
            parent=self,
        )
        self.assets_readiness_editor = AssetsReadinessEditor(
            document,
            object_name_prefix="wizard_",
            parent=self,
        )

        self.shell = NonHomePageShell(
            title="Setup Wizard",
            subtitle="Complete each setup step once, then use Home for routine launches.",
            layout_mode="single_column",
            width_preset="full",
            parent=self,
        )
        self.shell.set_footer_text(
            "Setup Wizard uses the same project document, validation, and launch checks as Home."
        )

        self.setup_wizard_step_list = QListWidget(self)
        self.setup_wizard_step_list.setObjectName("setup_wizard_step_list")
        _configure_read_only_list(self.setup_wizard_step_list)
        self.setup_wizard_step_list.setVisible(False)

        self.progress_header_label = QLabel(self)
        self.progress_header_label.setObjectName("setup_wizard_progress_header")
        self.progress_header_label.setProperty("sectionCardRole", "title")
        self.progress_header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress_steps = QWidget(self)
        self.progress_steps.setObjectName("setup_wizard_progress_steps")
        progress_steps_layout = QHBoxLayout(self.progress_steps)
        progress_steps_layout.setContentsMargins(0, 0, 0, 0)
        progress_steps_layout.setSpacing(6)
        self.progress_step_labels: list[QLabel] = []
        for index, (_key, title, _instruction) in enumerate(_WIZARD_STEPS):
            label = QLabel(f"{index + 1} {title}", self.progress_steps)
            label.setObjectName(f"setup_wizard_progress_step_{index + 1}")
            label.setProperty("wizardStep", "true")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            self.progress_step_labels.append(label)
            progress_steps_layout.addWidget(label, 1)

        progress_panel = QWidget(self)
        progress_layout = QVBoxLayout(progress_panel)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)
        progress_layout.addWidget(self.progress_header_label)
        progress_layout.addWidget(self.progress_steps)

        self.step_title_label = QLabel(self)
        self.step_title_label.setObjectName("setup_wizard_step_title")
        self.step_title_label.setProperty("sectionCardRole", "title")
        self.step_title_label.setWordWrap(True)
        self.step_instruction_label = QLabel(self)
        self.step_instruction_label.setObjectName("setup_wizard_step_instruction")
        self.step_instruction_label.setWordWrap(True)
        self.step_status_badge = StatusBadgeLabel("Step not checked", self)
        self.step_status_badge.setObjectName("setup_wizard_ready_badge")
        self.step_status_label = QLabel(self)
        self.step_status_label.setObjectName("setup_wizard_step_status_label")
        self.step_status_label.setWordWrap(True)

        self.step_stack = QStackedWidget(self)
        self.step_stack.setObjectName("setup_wizard_step_stack")
        self._build_step_pages()

        self.guided_panel = QWidget(self)
        guided_layout = QVBoxLayout(self.guided_panel)
        guided_layout.setContentsMargins(0, 0, 0, 0)
        guided_layout.setSpacing(8)
        guided_layout.addWidget(self.step_title_label)
        guided_layout.addWidget(self.step_instruction_label)
        guided_layout.addWidget(self.step_status_badge)
        guided_layout.addWidget(self.step_status_label)
        guided_layout.addWidget(self.step_stack, 1)

        step_card = SectionCard(
            title="",
            object_name="setup_wizard_current_step_card",
            parent=self,
        )
        step_card.title_label.setVisible(False)
        step_card.card_layout.setContentsMargins(12, 10, 12, 10)
        step_card.body_layout.setSpacing(8)

        self.advanced_stack = QStackedWidget(self)
        self.advanced_stack.setObjectName("setup_wizard_advanced_stack")
        self.advanced_stack.addWidget(self._advanced_empty_page())
        self.advanced_stack.addWidget(self.assets_page)
        self.advanced_stack.addWidget(self.run_page)
        self.advanced_stack.addWidget(self.session_structure_page)
        self.advanced_stack.addWidget(self.fixation_cross_settings_page)

        self.content_stack = QStackedWidget(self)
        self.content_stack.setObjectName("setup_wizard_content_stack")
        self.content_stack.addWidget(self.guided_panel)
        self.content_stack.addWidget(self.advanced_stack)
        step_card.body_layout.addWidget(self.content_stack, 1)

        self.setup_wizard_back_button = QPushButton("Back", self)
        self.setup_wizard_back_button.setObjectName("setup_wizard_back_button")
        self.setup_wizard_back_button.clicked.connect(self._go_back)
        self.setup_wizard_next_button = QPushButton("Next", self)
        self.setup_wizard_next_button.setObjectName("setup_wizard_next_button")
        self.setup_wizard_next_button.clicked.connect(self._go_next)
        mark_primary_action(self.setup_wizard_next_button)
        self.setup_wizard_return_home_button = QPushButton("Return Home", self)
        self.setup_wizard_return_home_button.setObjectName("setup_wizard_return_home_button")
        self.setup_wizard_return_home_button.clicked.connect(self._return_home)
        self.setup_wizard_advanced_button = QPushButton("Advanced", self)
        self.setup_wizard_advanced_button.setObjectName("setup_wizard_advanced_button")
        self.setup_wizard_advanced_button.clicked.connect(self._toggle_advanced)
        mark_secondary_action(self.setup_wizard_advanced_button)

        button_row = QWidget(self)
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(PAGE_SECTION_GAP)
        button_layout.addWidget(self.setup_wizard_return_home_button)
        button_layout.addWidget(self.setup_wizard_advanced_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.setup_wizard_back_button)
        button_layout.addWidget(self.setup_wizard_next_button)

        self.shell.add_content_widget(progress_panel)
        self.shell.add_content_widget(step_card, stretch=1)
        self.shell.add_content_widget(button_row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.shell)

        self._document.project_changed.connect(self.refresh)
        self._document.manifest_changed.connect(self.refresh)
        self._document.session_plan_changed.connect(self.refresh)
        self.refresh()

    def sync_fullscreen_checkbox(self, checked: bool) -> None:
        self.runtime_settings_editor.set_fullscreen_checked(checked)
        self.run_page.sync_fullscreen_checkbox(checked)

    def is_launch_ready(self) -> bool:
        return self._readiness_report().badge_state == "ready"

    def open_wizard(self, *, step_key: str | None = None) -> None:
        if step_key is not None:
            self._active_step_index = self._step_index_for_key(step_key)
        self._advanced_visible = False
        self.refresh()

    def _build_step_pages(self) -> None:
        self.step_stack.addWidget(self.project_overview_editor)
        self.step_stack.addWidget(self.conditions_page)
        self.step_stack.addWidget(self.assets_readiness_editor)
        self.step_stack.addWidget(self.runtime_settings_editor)
        self.step_stack.addWidget(self._session_step_page())
        self.step_stack.addWidget(self._fixation_step_page())
        self.step_stack.addWidget(self._review_step_page())

    def _session_step_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.session_guided_summary_label = QLabel(page)
        self.session_guided_summary_label.setObjectName("setup_wizard_session_summary")
        self.session_guided_summary_label.setWordWrap(True)
        summary_form = QFormLayout()
        summary_form.setVerticalSpacing(7)
        self.session_block_count_value = QLabel(page)
        self.session_order_value = QLabel(page)
        self.session_fixation_value = QLabel(page)
        self.session_accuracy_value = QLabel(page)
        summary_form.addRow("Block count", self.session_block_count_value)
        summary_form.addRow("Order strategy", self.session_order_value)
        summary_form.addRow("Session seed", self.session_fixation_value)
        summary_form.addRow("Transition", self.session_accuracy_value)
        layout.addWidget(self.session_guided_summary_label)
        layout.addLayout(summary_form)
        layout.addStretch(1)
        return page

    def _fixation_step_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.fixation_guided_summary_label = QLabel(page)
        self.fixation_guided_summary_label.setObjectName("setup_wizard_fixation_summary")
        self.fixation_guided_summary_label.setWordWrap(True)
        summary_form = QFormLayout()
        summary_form.setVerticalSpacing(7)
        self.fixation_enabled_value = QLabel(page)
        self.fixation_accuracy_value = QLabel(page)
        self.fixation_target_count_value = QLabel(page)
        self.fixation_response_value = QLabel(page)
        summary_form.addRow("Fixation task", self.fixation_enabled_value)
        summary_form.addRow("Accuracy task", self.fixation_accuracy_value)
        summary_form.addRow("Color changes", self.fixation_target_count_value)
        summary_form.addRow("Response key", self.fixation_response_value)
        layout.addWidget(self.fixation_guided_summary_label)
        layout.addLayout(summary_form)
        layout.addStretch(1)
        return page

    def _review_step_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.review_summary_label = QLabel(page)
        self.review_summary_label.setObjectName("setup_wizard_review_summary")
        self.review_summary_label.setWordWrap(True)
        self.review_readiness_list = QListWidget(page)
        self.review_readiness_list.setObjectName("setup_wizard_review_readiness_list")
        _configure_read_only_list(self.review_readiness_list)
        layout.addWidget(self.review_summary_label)
        layout.addWidget(self.review_readiness_list, 1)
        return page

    def _advanced_empty_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 10, 12, 10)
        label = QLabel("Advanced editor is not needed for this step.", page)
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch(1)
        return page

    def _show_first_condition_prompt_if_needed(self) -> None:
        step_key = _WIZARD_STEPS[self._active_step_index][0]
        if step_key != "conditions" or self.content_stack.currentWidget() is not self.guided_panel:
            return
        if len(self._document.ordered_conditions()) == 1:
            QMessageBox.information(
                self,
                "Create All Conditions",
                _CREATE_ALL_CONDITIONS_PROMPT,
            )

    def _go_back(self) -> None:
        if self._active_step_index > 0:
            self._active_step_index -= 1
            self._advanced_visible = False
            self.refresh()

    def _go_next(self) -> None:
        if not self._current_step_valid():
            return
        if self._active_step_index == len(_WIZARD_STEPS) - 1:
            self._return_home()
            return
        self._active_step_index += 1
        self._advanced_visible = False
        self.refresh()

    def _return_home(self) -> None:
        if not self.is_launch_ready():
            answer = QMessageBox.question(
                self,
                "Setup Incomplete",
                "This project is not ready to launch yet. Return Home anyway?\n\n"
                "Your setup changes are kept, but the experiment cannot launch until "
                "setup is complete.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        if self._on_return_home is not None:
            self._on_return_home()

    def _toggle_advanced(self) -> None:
        if not self._advanced_available_for_current_step():
            return
        self._advanced_visible = not self._advanced_visible
        self.refresh()

    def refresh(self) -> None:
        self._active_step_index = max(
            0,
            min(self._active_step_index, len(_WIZARD_STEPS) - 1),
        )
        self.runtime_settings_editor.refresh()
        self.run_page.refresh()
        self.session_structure_page.refresh()
        self.fixation_cross_settings_page.refresh()
        self.conditions_page.refresh()
        self.assets_page.refresh()
        self.assets_readiness_editor.refresh()

        self.step_stack.setCurrentIndex(self._active_step_index)
        self.setup_wizard_step_list.setCurrentRow(self._active_step_index)
        _set_list_items(self.setup_wizard_step_list, self._step_list_lines())
        self.setup_wizard_step_list.setCurrentRow(self._active_step_index)

        step_key, title, instruction = _WIZARD_STEPS[self._active_step_index]
        self._refresh_progress_header()
        self.step_title_label.setText(title)
        self.step_instruction_label.setText(instruction)
        self._refresh_session_guided_summary()
        self._refresh_fixation_guided_summary()
        report = self._readiness_report()
        self.review_summary_label.setText(report.status_summary)
        _set_list_items(self.review_readiness_list, self._human_readiness_items(report))

        step_valid = self._current_step_valid()
        show_step_intro = step_key != "conditions"
        self.step_title_label.setVisible(show_step_intro)
        self.step_instruction_label.setVisible(show_step_intro)
        self.step_status_badge.setVisible(show_step_intro)
        self.step_status_label.setText(self._step_status_text(self._active_step_index))
        self.step_status_label.setVisible(show_step_intro and not step_valid)
        self.step_status_badge.set_state(
            "ready" if step_valid else "warning",
            "Step Complete" if step_valid else self._current_step_blocker(),
        )
        self.setup_wizard_back_button.setEnabled(self._active_step_index > 0)
        self.setup_wizard_next_button.setEnabled(step_valid)
        self.setup_wizard_next_button.setText(
            "Return Home" if self._active_step_index == len(_WIZARD_STEPS) - 1 else "Next"
        )
        advanced_available = self._advanced_available_for_current_step()
        self.setup_wizard_advanced_button.setEnabled(advanced_available)
        self.setup_wizard_advanced_button.setText(
            "Back to Guided Step" if self._advanced_visible else "Advanced"
        )
        self.advanced_stack.setCurrentIndex(self._advanced_index_for_step(step_key))
        self.content_stack.setCurrentWidget(
            self.advanced_stack
            if self._advanced_visible and advanced_available
            else self.guided_panel
        )

    def _readiness_report(self) -> LauncherReadinessReport:
        return _launcher_readiness_report(
            self._document,
            refresh_hz=self.runtime_settings_editor.current_refresh_hz(),
        )

    def _step_list_lines(self) -> tuple[str, ...]:
        return tuple(
            f"{index + 1}. {title} - {self._step_status_text(index)}"
            for index, (_key, title, _instruction) in enumerate(_WIZARD_STEPS)
        )

    def _step_status_text(self, index: int) -> str:
        step_key = _WIZARD_STEPS[index][0]
        if step_key == "project" and not self._project_details_ready():
            return self._project_details_blocker()
        if self._step_valid(index):
            return "Ready" if step_key == "review" else "Complete"
        if step_key == "conditions":
            ordered_conditions = self._document.ordered_conditions()
            if not ordered_conditions:
                return "Add a condition"
            if not self._conditions_have_required_names(ordered_conditions):
                return "Name every condition"
            return "Assign base and oddball folders"
        if step_key == "stimuli":
            return "Needs images"
        if step_key == "review":
            return "Review blockers"
        return self._current_step_blocker() if index == self._active_step_index else "Needs setup"

    def _current_step_valid(self) -> bool:
        return self._step_valid(self._active_step_index)

    def _step_valid(self, index: int) -> bool:
        step_key = _WIZARD_STEPS[index][0]
        ordered_conditions = self._document.ordered_conditions()
        if step_key == "project":
            return self._project_details_ready()
        if step_key == "conditions":
            return self._conditions_ready_for_wizard(ordered_conditions)
        if step_key == "stimuli":
            return _conditions_have_assigned_assets(self._document, ordered_conditions)
        if step_key == "display":
            return self.runtime_settings_editor.current_refresh_hz() > 0.0
        if step_key in {"session", "fixation"}:
            return True
        if step_key == "review":
            return self.is_launch_ready()
        return False

    def _current_step_blocker(self) -> str:
        step_key = _WIZARD_STEPS[self._active_step_index][0]
        if step_key == "project":
            return self._project_details_blocker()
        if step_key == "conditions":
            ordered_conditions = self._document.ordered_conditions()
            if not ordered_conditions:
                return "Add at least one condition"
            if not self._conditions_have_required_names(ordered_conditions):
                return "Name every condition"
            return "Assign base and oddball folders"
        if step_key == "stimuli":
            return "Assign base and oddball folders"
        if step_key == "display":
            return "Set a valid refresh rate"
        if step_key == "review":
            return self._readiness_report().status_label
        return "Step needs attention"

    def _project_details_ready(self) -> bool:
        project = self._document.project
        return bool(
            project.meta.name.strip()
            and project.meta.description.strip()
            and self._document.project_root
        )

    def _project_details_blocker(self) -> str:
        project = self._document.project
        if not project.meta.name.strip():
            return "Enter a project name"
        if not project.meta.description.strip():
            return "Enter a project description"
        if not self._document.project_root:
            return "Choose a project folder"
        return "Project details needed"

    @staticmethod
    def _conditions_have_required_names(ordered_conditions: list) -> bool:
        return all(
            condition.name.strip()
            and _DEFAULT_CONDITION_NAME_RE.fullmatch(condition.name.strip()) is None
            for condition in ordered_conditions
        )

    def _conditions_ready_for_wizard(self, ordered_conditions: list) -> bool:
        return (
            bool(ordered_conditions)
            and self._conditions_have_required_names(ordered_conditions)
            and _conditions_have_assigned_assets(self._document, ordered_conditions)
        )

    @staticmethod
    def _human_readiness_items(report: LauncherReadinessReport) -> tuple[str, ...]:
        replacements = {
            "[OK] ": "Complete: ",
            "[TODO] ": "Needs setup: ",
            "[WARN] ": "Warning: ",
            "[INFO] ": "Note: ",
            "[ACTION] ": "Action: ",
        }
        lines: list[str] = []
        for item in report.readiness_items:
            line = item
            for prefix, replacement in replacements.items():
                if line.startswith(prefix):
                    line = f"{replacement}{line.removeprefix(prefix)}"
                    break
            lines.append(line)
        return tuple(lines)

    def _refresh_session_guided_summary(self) -> None:
        session = self._document.project.settings.session
        self.session_guided_summary_label.setText(
            "Review the session sequence below. Use Advanced for detailed session controls."
        )
        self.session_block_count_value.setText(str(session.block_count))
        self.session_order_value.setText(
            "Randomized within each block"
            if session.randomize_conditions_per_block
            else "Fixed project order"
        )
        self.session_fixation_value.setText(str(session.session_seed))
        self.session_accuracy_value.setText(
            "Fixed break"
            if session.inter_condition_mode.value == "fixed_break"
            else "Manual continue"
            if session.inter_condition_mode.value == "manual_continue"
            else "Unknown"
        )

    def _refresh_fixation_guided_summary(self) -> None:
        fixation = self._document.project.settings.fixation_task
        self.fixation_guided_summary_label.setText(
            "Review fixation behavior below. Use Advanced for timing, color, and appearance "
            "details."
        )
        self.fixation_enabled_value.setText("Enabled" if fixation.enabled else "Disabled")
        self.fixation_accuracy_value.setText(
            "Enabled" if fixation.accuracy_task_enabled else "Disabled"
        )
        if fixation.target_count_mode == "randomized":
            target_text = f"{fixation.target_count_min}-{fixation.target_count_max} randomized"
        else:
            target_text = f"{fixation.changes_per_sequence} fixed"
        self.fixation_target_count_value.setText(target_text)
        self.fixation_response_value.setText(fixation.response_key)

    def _advanced_available_for_current_step(self) -> bool:
        return _WIZARD_STEPS[self._active_step_index][0] in {
            "stimuli",
            "display",
            "session",
            "fixation",
        }

    def _advanced_index_for_step(self, step_key: str) -> int:
        return {
            "stimuli": 1,
            "display": 2,
            "session": 3,
            "fixation": 4,
        }.get(step_key, 0)

    def _refresh_progress_header(self) -> None:
        current = self._active_step_index
        _key, title, _instruction = _WIZARD_STEPS[current]
        self.progress_header_label.setText(f"Step {current + 1} of {len(_WIZARD_STEPS)}: {title}")
        for index, label in enumerate(self.progress_step_labels):
            if index < current:
                state = "complete"
            elif index == current:
                state = "current"
            else:
                state = "upcoming"
            label.setProperty("wizardStepState", state)
            refresh_widget_style(label)

    def _step_index_for_key(self, step_key: str) -> int:
        aliases = {"runtime": "display"}
        step_key = aliases.get(step_key, step_key)
        for index, (candidate, _title, _instruction) in enumerate(_WIZARD_STEPS):
            if candidate == step_key:
                return index
        return 0
