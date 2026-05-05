"""Guided setup wizard for FPVS Studio projects."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
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
    ("runtime", "Display / Runtime", "Set refresh rate and launch display options."),
    ("session", "Session / Fixation", "Choose block order and fixation task settings."),
    ("review", "Review / Ready", "Resolve blockers before returning to Home."),
)


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
            width_preset="wide",
            parent=self,
        )
        self.shell.set_footer_text(
            "Setup Wizard uses the same project document, validation, and launch checks as Home."
        )

        self.setup_wizard_step_list = QListWidget(self)
        self.setup_wizard_step_list.setObjectName("setup_wizard_step_list")
        _configure_read_only_list(self.setup_wizard_step_list)

        self.step_title_label = QLabel(self)
        self.step_title_label.setObjectName("setup_wizard_step_title")
        self.step_title_label.setProperty("sectionCardRole", "title")
        self.step_title_label.setWordWrap(True)
        self.step_instruction_label = QLabel(self)
        self.step_instruction_label.setObjectName("setup_wizard_step_instruction")
        self.step_instruction_label.setWordWrap(True)
        self.step_status_badge = StatusBadgeLabel("Step not checked", self)
        self.step_status_badge.setObjectName("setup_wizard_ready_badge")

        self.step_stack = QStackedWidget(self)
        self.step_stack.setObjectName("setup_wizard_step_stack")
        self._build_step_pages()

        step_card = SectionCard(
            title="Current Step",
            subtitle="Only the controls needed for this setup step are shown.",
            object_name="setup_wizard_current_step_card",
            parent=self,
        )
        step_card.card_layout.setContentsMargins(12, 10, 12, 10)
        step_card.body_layout.setSpacing(8)
        step_card.body_layout.addWidget(self.step_title_label)
        step_card.body_layout.addWidget(self.step_instruction_label)
        step_card.body_layout.addWidget(self.step_status_badge)
        step_card.body_layout.addWidget(self.step_stack, 1)

        self.advanced_stack = QStackedWidget(self)
        self.advanced_stack.setObjectName("setup_wizard_advanced_stack")
        self.advanced_stack.addWidget(self._advanced_empty_page())
        self.advanced_stack.addWidget(self.conditions_page)
        self.advanced_stack.addWidget(self.assets_page)
        self.advanced_stack.addWidget(self.run_page)
        self.advanced_frame = QFrame(self)
        self.advanced_frame.setObjectName("setup_wizard_advanced_frame")
        advanced_layout = QVBoxLayout(self.advanced_frame)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        advanced_layout.addWidget(self.advanced_stack)
        self.advanced_frame.setVisible(False)

        body_row = QWidget(self)
        body_layout = QHBoxLayout(body_row)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(PAGE_SECTION_GAP)
        body_layout.addWidget(self.setup_wizard_step_list, 2)
        body_layout.addWidget(step_card, 5)

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

        self.shell.add_content_widget(body_row)
        self.shell.add_content_widget(self.advanced_frame, stretch=1)
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
        self.advanced_frame.setVisible(False)
        self.refresh()

    def _build_step_pages(self) -> None:
        self.step_stack.addWidget(self.project_overview_editor)
        self.step_stack.addWidget(self._conditions_step_page())
        self.step_stack.addWidget(self.assets_readiness_editor)
        self.step_stack.addWidget(self.runtime_settings_editor)
        self.step_stack.addWidget(self._session_step_page())
        self.step_stack.addWidget(self._review_step_page())

    def _conditions_step_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.conditions_summary_label = QLabel(page)
        self.conditions_summary_label.setObjectName("setup_wizard_conditions_summary")
        self.conditions_summary_label.setWordWrap(True)
        self.add_condition_button = QPushButton("Add Condition", page)
        self.add_condition_button.setObjectName("setup_wizard_add_condition_button")
        self.add_condition_button.clicked.connect(self._add_condition)
        mark_primary_action(self.add_condition_button)
        layout.addWidget(self.conditions_summary_label)
        layout.addWidget(self.add_condition_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    def _session_step_page(self) -> QWidget:
        page = QWidget(self)
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(PAGE_SECTION_GAP)
        layout.addWidget(self.session_structure_page, 1)
        layout.addWidget(self.fixation_cross_settings_page, 1)
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

    def _add_condition(self) -> None:
        self._document.create_condition()
        self.conditions_page.refresh()
        self.refresh()

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
        self.step_title_label.setText(title)
        self.step_instruction_label.setText(instruction)
        self.conditions_summary_label.setText(self._conditions_summary_text())
        report = self._readiness_report()
        self.review_summary_label.setText(report.status_summary)
        _set_list_items(self.review_readiness_list, report.readiness_items)

        step_valid = self._current_step_valid()
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
            "Hide Advanced" if self._advanced_visible else "Advanced"
        )
        self.advanced_frame.setVisible(self._advanced_visible and advanced_available)
        self.advanced_stack.setCurrentIndex(self._advanced_index_for_step(step_key))

    def _readiness_report(self) -> LauncherReadinessReport:
        return _launcher_readiness_report(
            self._document,
            refresh_hz=self.runtime_settings_editor.current_refresh_hz(),
        )

    def _step_list_lines(self) -> tuple[str, ...]:
        return tuple(
            f"{'[OK]' if self._step_valid(index) else '[TODO]'} {title}"
            for index, (_key, title, _instruction) in enumerate(_WIZARD_STEPS)
        )

    def _current_step_valid(self) -> bool:
        return self._step_valid(self._active_step_index)

    def _step_valid(self, index: int) -> bool:
        step_key = _WIZARD_STEPS[index][0]
        ordered_conditions = self._document.ordered_conditions()
        if step_key == "project":
            return bool(self._document.project.meta.name.strip() and self._document.project_root)
        if step_key == "conditions":
            return bool(ordered_conditions)
        if step_key == "stimuli":
            return _conditions_have_assigned_assets(self._document, ordered_conditions)
        if step_key == "runtime":
            return self.runtime_settings_editor.current_refresh_hz() > 0.0
        if step_key == "session":
            return True
        if step_key == "review":
            return self.is_launch_ready()
        return False

    def _current_step_blocker(self) -> str:
        step_key = _WIZARD_STEPS[self._active_step_index][0]
        if step_key == "project":
            return "Project details needed"
        if step_key == "conditions":
            return "Add at least one condition"
        if step_key == "stimuli":
            return "Assign base and oddball folders"
        if step_key == "runtime":
            return "Set a valid refresh rate"
        if step_key == "review":
            return self._readiness_report().status_label
        return "Step needs attention"

    def _conditions_summary_text(self) -> str:
        ordered_conditions = self._document.ordered_conditions()
        if not ordered_conditions:
            return "No conditions are configured yet. Add a condition to continue."
        names = ", ".join(condition.name for condition in ordered_conditions)
        return f"{len(ordered_conditions)} condition(s) configured: {names}"

    def _advanced_available_for_current_step(self) -> bool:
        return _WIZARD_STEPS[self._active_step_index][0] in {
            "conditions",
            "stimuli",
            "runtime",
        }

    def _advanced_index_for_step(self, step_key: str) -> int:
        return {"conditions": 1, "stimuli": 2, "runtime": 3}.get(step_key, 0)

    def _step_index_for_key(self, step_key: str) -> int:
        for index, (candidate, _title, _instruction) in enumerate(_WIZARD_STEPS):
            if candidate == step_key:
                return index
        return 0
