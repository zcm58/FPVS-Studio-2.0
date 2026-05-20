"""Guided setup wizard for FPVS Studio projects."""

from __future__ import annotations

from collections.abc import Callable
from math import ceil

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.frame_validation import FrameValidationError
from fpvs_studio.core.models import ConditionTemplateProfile
from fpvs_studio.core.validation import condition_fixation_guidance
from fpvs_studio.gui.assets_pages import AssetsPage
from fpvs_studio.gui.components import (
    PAGE_SECTION_GAP,
    NonHomePageShell,
    SectionCard,
    SetupProgressStepper,
    StatusBadgeLabel,
    apply_setup_wizard_theme,
    mark_primary_action,
    mark_secondary_action,
    refresh_widget_style,
)
from fpvs_studio.gui.condition_pages import ConditionsPage
from fpvs_studio.gui.condition_setup_step import (
    ConditionSetupStep,
    is_guided_condition_name,
    is_guided_trigger_code,
)
from fpvs_studio.gui.design_system import PAGE_MARGIN_X
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.image_normalization_dialog import ImageNormalizationDialog
from fpvs_studio.gui.project_overview_page import ProjectOverviewEditor
from fpvs_studio.gui.run_page import RunPage
from fpvs_studio.gui.runtime_settings_page import DisplaySettingsEditor, ImageDisplaySizeEditor
from fpvs_studio.gui.session_pages import FixationSettingsEditor, SessionStructureEditor
from fpvs_studio.gui.window_helpers import (
    LauncherReadinessReport,
    _conditions_have_assigned_assets,
    _launcher_readiness_report,
    _show_error_dialog,
)
from fpvs_studio.gui.workers import ProgressTask

_WIZARD_STEPS: tuple[tuple[str, str], ...] = (
    ("project", "Project"),
    ("conditions", "Conditions"),
    ("experiment", "Experiment"),
    ("fixation", "Fixation"),
    ("response", "Response"),
    ("review", "Review"),
)
_CREATE_ALL_CONDITIONS_PROMPT = "Please ensure you create all conditions before proceeding."
_ESTIMATED_INTER_CONDITION_BREAK_SECONDS = 30
_SETUP_STEP_SURFACE_MAX_WIDTH = 880
_SETUP_STEP_WORKBENCH_SURFACE_MAX_WIDTH = 1040
_SETUP_STEP_SURFACE_MIN_HEIGHT = 360
_SETUP_STEP_CARD_MAX_HEIGHT = 552


class _CurrentWidgetStack(QStackedWidget):
    """Stacked widget whose size hint follows only the active page."""

    def sizeHint(self) -> QSize:
        widget = self.currentWidget()
        return widget.sizeHint() if widget is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        widget = self.currentWidget()
        return widget.minimumSizeHint() if widget is not None else super().minimumSizeHint()


class _NaturalSizePanel(QWidget):
    """Widget whose size hint follows its layout instead of its expanded geometry."""

    def sizeHint(self) -> QSize:
        layout = self.layout()
        return layout.sizeHint() if layout is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        layout = self.layout()
        return layout.minimumSize() if layout is not None else super().minimumSizeHint()


class _SetupStepSurface(_NaturalSizePanel):
    """Shared sizing and alignment surface for compact setup wizard steps."""

    def __init__(
        self,
        content: QWidget,
        *,
        object_name: str,
        max_width: int = _SETUP_STEP_SURFACE_MAX_WIDTH,
        center_vertically: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setProperty("setupStepSurface", "true")
        self.content = content
        self.setMinimumHeight(_SETUP_STEP_SURFACE_MIN_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        content.setMaximumWidth(max_width)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        if center_vertically:
            layout.addStretch(1)
        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        row_layout.addStretch(1)
        row_layout.addWidget(content)
        row_layout.addStretch(1)
        layout.addWidget(row)
        if center_vertically:
            layout.addStretch(1)

    def refresh(self) -> None:
        refresh = getattr(self.content, "refresh", None)
        if callable(refresh):
            refresh()


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
        on_save_project: Callable[[], bool] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("setup_wizard_page")
        self.setProperty("launchSurfaceRoot", "true")
        self._document = document
        self._on_return_home = on_return_home
        self._on_save_project = on_save_project
        self._active_step_index = 0
        self._readiness_cache: tuple[tuple[int, float, bool], LauncherReadinessReport] | None = (
            None
        )
        self._step_jump_enabled = False
        self._active_normalization_task: ProgressTask | None = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(0)
        self._refresh_timer.timeout.connect(self.refresh)

        self.conditions_page = ConditionsPage(document, embedded=True, parent=self)
        self.condition_setup_step = ConditionSetupStep(document, self)
        self.add_condition_button = self.condition_setup_step.add_condition_button
        self.add_condition_button.clicked.connect(self._show_first_condition_prompt_if_needed)
        self.assets_page = AssetsPage(document, self)
        self.run_page = RunPage(
            document,
            fullscreen_state_getter=fullscreen_state_getter,
            fullscreen_state_setter=fullscreen_state_setter,
            parent=self,
        )
        self.project_overview_editor = ProjectOverviewEditor(
            document,
            load_condition_template_profiles=load_condition_template_profiles,
            manage_condition_templates=manage_condition_templates,
            parent=self,
        )
        self.project_overview_editor.project_description_edit.textChanged.connect(
            self.schedule_refresh
        )
        self.runtime_settings_editor = DisplaySettingsEditor(
            document,
            framed=False,
            show_scope_label=False,
            parent=self,
        )
        self.image_display_size_editor = ImageDisplaySizeEditor(document, parent=self)
        self.session_structure_editor = SessionStructureEditor(
            document,
            title="Session",
            subtitle="Block order and participant start behavior.",
            framed=False,
            parent=self,
        )
        self.session_structure_page = self.session_structure_editor
        self.fixation_schedule_editor = FixationSettingsEditor(
            document,
            schedule_row_behavior="disable",
            layout_mode="grid",
            title="Fixation Cross",
            subtitle=None,
            compact=True,
            framed=False,
            section_mode="fixation",
            show_preview=False,
            parent=self,
        )
        self.fixation_response_editor = FixationSettingsEditor(
            document,
            schedule_row_behavior="disable",
            layout_mode="grid",
            title="Response and Appearance",
            subtitle=None,
            compact=True,
            framed=False,
            section_mode="response",
            show_preview=True,
            parent=self,
        )
        self.fixation_settings_editor = self.fixation_response_editor
        self.fixation_cross_settings_page = self.fixation_settings_editor
        self.shell = NonHomePageShell(
            title="Setup Wizard",
            subtitle="",
            layout_mode="single_column",
            width_preset="full",
            parent=self,
        )
        self.shell.page_container.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.shell.page_container.scroll_area.verticalScrollBar().setEnabled(False)
        self.shell.set_page_margins(PAGE_MARGIN_X, 12, PAGE_MARGIN_X, 6)
        self.shell.set_content_spacing(8)

        self.progress_steps = SetupProgressStepper(
            tuple(title for _key, title in _WIZARD_STEPS),
            parent=self,
        )
        self.progress_steps.step_requested.connect(self._go_to_step_from_progress)
        self.progress_step_labels = self.progress_steps.step_labels

        progress_panel = QWidget(self)
        progress_panel.setObjectName("setup_wizard_progress_panel")
        progress_panel.setMaximumWidth(1120)
        progress_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.progress_panel = progress_panel
        progress_layout = QVBoxLayout(progress_panel)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(0)
        progress_layout.addWidget(self.progress_steps)

        progress_panel_shell = QWidget(self)
        progress_panel_shell.setObjectName("setup_wizard_progress_panel_shell")
        progress_panel_shell.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        progress_panel_shell_layout = QHBoxLayout(progress_panel_shell)
        progress_panel_shell_layout.setContentsMargins(0, 0, 0, 0)
        progress_panel_shell_layout.addStretch(1)
        progress_panel_shell_layout.addWidget(progress_panel)
        progress_panel_shell_layout.addStretch(1)
        self.progress_panel_shell = progress_panel_shell

        self.step_title_label = QLabel(self)
        self.step_title_label.setObjectName("setup_wizard_step_title")
        self.step_title_label.setProperty("sectionCardRole", "title")
        self.step_title_label.setWordWrap(True)
        self.step_status_badge = StatusBadgeLabel("Step not checked", self)
        self.step_status_badge.setObjectName("setup_wizard_ready_badge")
        self.step_status_label = QLabel(self)
        self.step_status_label.setObjectName("setup_wizard_step_status_label")
        self.step_status_label.setWordWrap(True)

        self.step_stack = _CurrentWidgetStack(self)
        self.step_stack.setObjectName("setup_wizard_step_stack")
        self.step_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._build_step_pages()

        self.guided_panel = _NaturalSizePanel(self)
        self.guided_panel.setMinimumHeight(0)
        self.guided_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        guided_layout = QVBoxLayout(self.guided_panel)
        guided_layout.setContentsMargins(0, 0, 0, 0)
        guided_layout.setSpacing(8)
        guided_layout.addWidget(self.step_title_label)
        guided_layout.addWidget(self.step_status_badge)
        guided_layout.addWidget(self.step_status_label)
        guided_layout.addWidget(self.step_stack)

        step_card = SectionCard(
            title="",
            object_name="setup_wizard_current_step_card",
            parent=self,
        )
        self.step_card = step_card
        step_card.setProperty("sectionCard", "false")
        step_card.setProperty("launchSurfaceFrame", "true")
        step_card.setMinimumHeight(0)
        step_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        step_card.title_label.setVisible(False)
        step_card.card_layout.setContentsMargins(12, 8, 12, 8)
        step_card.body_layout.setSpacing(8)

        self.advanced_stack = _CurrentWidgetStack(self)
        self.advanced_stack.setObjectName("setup_wizard_advanced_stack")
        self.advanced_stack.addWidget(QWidget(self))
        self.advanced_stack.addWidget(self.conditions_page)

        self.content_stack = _CurrentWidgetStack(self)
        self.content_stack.setObjectName("setup_wizard_content_stack")
        self.content_stack.setMinimumHeight(0)
        self.content_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.content_stack.addWidget(self.guided_panel)
        self.content_stack.addWidget(self.advanced_stack)

        self.step_content_anchor = QWidget(self)
        self.step_content_anchor.setObjectName("setup_wizard_content_anchor")
        self.step_content_anchor.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        step_content_layout = QVBoxLayout(self.step_content_anchor)
        step_content_layout.setContentsMargins(0, 0, 0, 0)
        step_content_layout.setSpacing(0)
        step_content_layout.addWidget(self.content_stack, 1)

        step_card.body_layout.addWidget(progress_panel_shell, 0, Qt.AlignmentFlag.AlignTop)
        step_card.body_layout.addWidget(self.step_content_anchor, 1)

        self.setup_wizard_back_button = QPushButton("Back", self)
        self.setup_wizard_back_button.setObjectName("setup_wizard_back_button")
        self.setup_wizard_back_button.clicked.connect(self._go_back)
        self.setup_wizard_next_button = QPushButton("Next", self)
        self.setup_wizard_next_button.setObjectName("setup_wizard_next_button")
        self.setup_wizard_next_button.clicked.connect(self._go_next)
        next_button_size_policy = self.setup_wizard_next_button.sizePolicy()
        next_button_size_policy.setRetainSizeWhenHidden(True)
        self.setup_wizard_next_button.setSizePolicy(next_button_size_policy)
        mark_primary_action(self.setup_wizard_next_button)
        self.setup_wizard_return_home_button = QPushButton("Return Home", self)
        self.setup_wizard_return_home_button.setObjectName("setup_wizard_return_home_button")
        self.setup_wizard_return_home_button.clicked.connect(self._return_home)

        button_row = QWidget(self)
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(PAGE_MARGIN_X, 0, PAGE_MARGIN_X, 2)
        button_layout.setSpacing(PAGE_SECTION_GAP)
        button_layout.addWidget(self.setup_wizard_return_home_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.setup_wizard_back_button)
        button_layout.addWidget(self.setup_wizard_next_button)

        self.shell.add_content_widget(step_card, stretch=1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.shell, 1)
        layout.addWidget(button_row)
        layout.addWidget(self.shell.footer_strip)

        self._document.project_changed.connect(self.schedule_refresh)
        self._document.manifest_changed.connect(self.schedule_refresh)
        self._document.session_plan_changed.connect(self.schedule_refresh)
        apply_setup_wizard_theme(self)
        self.refresh()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._sync_guided_panel_height()
        QTimer.singleShot(0, self._sync_guided_panel_height)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            if getattr(self, "_theme_refreshing", False):
                return
            self._theme_refreshing = True
            try:
                apply_setup_wizard_theme(self)
            finally:
                self._theme_refreshing = False

    def sync_fullscreen_checkbox(self, _checked: bool) -> None:
        return

    def is_launch_ready(self) -> bool:
        return self._readiness_report().badge_state == "ready"

    def first_incomplete_step_key(self) -> str:
        for index, (step_key, _title) in enumerate(_WIZARD_STEPS):
            if not self._step_valid(index):
                return step_key
        return "review"

    def open_wizard(
        self,
        *,
        step_key: str | None = None,
        allow_step_jumps: bool | None = None,
    ) -> None:
        self.flush_pending_edits()
        if allow_step_jumps is not None:
            self._step_jump_enabled = allow_step_jumps
        if step_key is not None:
            self._active_step_index = self._step_index_for_key(step_key)
        self.refresh()

    def flush_pending_edits(self) -> None:
        self.project_overview_editor.flush_pending_edits()
        self.condition_setup_step.flush_pending_edits()
        self.conditions_page.flush_pending_edits()

    def schedule_refresh(self) -> None:
        self._readiness_cache = None
        if not self._refresh_timer.isActive():
            self._refresh_timer.start()

    def _build_step_pages(self) -> None:
        self.project_step_surface = _SetupStepSurface(
            self.project_overview_editor,
            object_name="setup_wizard_project_surface",
            center_vertically=True,
            parent=self,
        )
        self.conditions_step_surface = _SetupStepSurface(
            self.condition_setup_step,
            object_name="setup_wizard_conditions_surface",
            max_width=_SETUP_STEP_WORKBENCH_SURFACE_MAX_WIDTH,
            parent=self,
        )
        self.experiment_step_surface = _SetupStepSurface(
            self._experiment_settings_step_page(),
            object_name="setup_wizard_experiment_surface",
            center_vertically=True,
            parent=self,
        )
        self.fixation_step_surface = _SetupStepSurface(
            self.fixation_schedule_editor,
            object_name="setup_wizard_fixation_surface",
            center_vertically=True,
            parent=self,
        )
        self.response_step_surface = _SetupStepSurface(
            self.fixation_response_editor,
            object_name="setup_wizard_response_surface",
            max_width=_SETUP_STEP_WORKBENCH_SURFACE_MAX_WIDTH,
            parent=self,
        )
        self.review_step_surface = _SetupStepSurface(
            self._review_step_page(),
            object_name="setup_wizard_review_surface",
            center_vertically=True,
            parent=self,
        )
        self.step_stack.addWidget(self.project_step_surface)
        self.step_stack.addWidget(self.conditions_step_surface)
        self.step_stack.addWidget(self.experiment_step_surface)
        self.step_stack.addWidget(self.fixation_step_surface)
        self.step_stack.addWidget(self.response_step_surface)
        self.step_stack.addWidget(self.review_step_surface)

    def _experiment_settings_step_page(self) -> QWidget:
        page = QWidget(self)
        page.setObjectName("setup_wizard_experiment_settings_page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.experiment_settings_card = QWidget(page)
        self.experiment_settings_card.setObjectName("setup_wizard_experiment_settings_card")
        self.experiment_settings_card.setMaximumWidth(_SETUP_STEP_SURFACE_MAX_WIDTH)
        self.experiment_settings_card.setMinimumHeight(280)
        self.experiment_settings_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        experiment_layout = QVBoxLayout(self.experiment_settings_card)
        experiment_layout.setContentsMargins(0, 0, 0, 0)
        experiment_layout.setSpacing(0)

        content = QWidget(self.experiment_settings_card)
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(PAGE_SECTION_GAP + 4)

        display_column = QFrame(content)
        display_column.setProperty("experimentSettingsSection", "true")
        display_column.setMinimumHeight(224)
        display_column_layout = QVBoxLayout(display_column)
        display_column_layout.setContentsMargins(14, 12, 14, 12)
        display_column_layout.setSpacing(12)
        display_title = QLabel("Display Settings", display_column)
        display_title.setProperty("sectionCardRole", "title")
        display_column_layout.addWidget(display_title)
        display_column_layout.addWidget(self.runtime_settings_editor)
        display_column_layout.addStretch(1)

        image_size_column = QFrame(content)
        image_size_column.setProperty("experimentSettingsSection", "true")
        image_size_column.setMinimumHeight(224)
        image_size_column_layout = QVBoxLayout(image_size_column)
        image_size_column_layout.setContentsMargins(14, 12, 14, 12)
        image_size_column_layout.setSpacing(12)
        image_size_title = QLabel("Image Size", image_size_column)
        image_size_title.setProperty("sectionCardRole", "title")
        image_size_column_layout.addWidget(image_size_title)
        image_size_column_layout.addWidget(self.image_display_size_editor)

        session_column = QFrame(content)
        session_column.setProperty("experimentSettingsSection", "true")
        session_column.setMinimumHeight(224)
        session_column_layout = QVBoxLayout(session_column)
        session_column_layout.setContentsMargins(14, 12, 14, 12)
        session_column_layout.setSpacing(12)
        session_title = QLabel("Session", session_column)
        session_title.setProperty("sectionCardRole", "title")
        session_column_layout.addWidget(session_title)
        session_column_layout.addWidget(self.session_structure_editor)
        session_column_layout.addStretch(1)

        self.runtime_settings_editor.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.image_display_size_editor.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.session_structure_editor.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        content_layout.addWidget(display_column, 2)
        content_layout.addWidget(image_size_column, 2)
        content_layout.addWidget(session_column, 3)
        experiment_layout.addWidget(content)

        layout.addWidget(
            self.experiment_settings_card,
            0,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        )
        return page

    def _review_step_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.review_card = SectionCard(
            title="Review Your Experiment",
            subtitle="Please confirm your experiment settings.",
            object_name="setup_wizard_review_card",
            parent=page,
        )
        self.review_card.setMinimumWidth(700)
        self.review_card.setMaximumWidth(_SETUP_STEP_SURFACE_MAX_WIDTH)
        self.review_card.card_layout.setContentsMargins(14, 10, 14, 10)
        self.review_card.card_layout.setSpacing(6)
        self.review_card.body_layout.setSpacing(6)
        self.review_card.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if self.review_card.subtitle_label is not None:
            self.review_card.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout = self.review_card.card_layout.itemAt(0).layout()
        if header_layout is not None:
            header_layout.insertStretch(0, 1)

        self.review_checklist_container = QWidget(self.review_card)
        self.review_checklist_container.setObjectName("setup_wizard_review_checklist")
        self.review_checklist_layout = QGridLayout(self.review_checklist_container)
        self.review_checklist_layout.setContentsMargins(0, 0, 0, 0)
        self.review_checklist_layout.setHorizontalSpacing(8)
        self.review_checklist_layout.setVerticalSpacing(6)
        self.review_card.body_layout.addWidget(self.review_checklist_container)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.addStretch(1)
        self.review_save_button = QPushButton("Save and Return Home", self.review_card)
        self.review_save_button.setObjectName("setup_wizard_review_save_button")
        self.review_save_button.clicked.connect(self._save_from_review)
        mark_primary_action(self.review_save_button)
        self.review_return_home_button = QPushButton(
            "Return Home Without Saving",
            self.review_card,
        )
        self.review_return_home_button.setObjectName("setup_wizard_review_return_home_button")
        self.review_return_home_button.clicked.connect(self._return_home)
        mark_secondary_action(self.review_return_home_button)
        action_row.addWidget(self.review_save_button)
        action_row.addWidget(self.review_return_home_button)
        action_row.addStretch(1)
        self.review_card.body_layout.addLayout(action_row)

        layout.addWidget(self.review_card, 0, Qt.AlignmentFlag.AlignHCenter)
        return page

    def _show_first_condition_prompt_if_needed(self) -> None:
        step_key = _WIZARD_STEPS[self._active_step_index][0]
        if step_key != "conditions" or self.content_stack.currentWidget() is not self.guided_panel:
            return
        self.refresh()
        if len(self._document.ordered_conditions()) == 1:
            QMessageBox.information(
                self,
                "Create All Conditions",
                _CREATE_ALL_CONDITIONS_PROMPT,
            )

    def _go_back(self) -> None:
        self.flush_pending_edits()
        if self._active_step_index > 0:
            self._active_step_index -= 1
            self.refresh()

    def _go_next(self) -> None:
        self.flush_pending_edits()
        if self._active_normalization_task is not None:
            return
        if not self._current_step_valid():
            return
        if self._active_step_index == len(_WIZARD_STEPS) - 1:
            self._return_home()
            return
        if _WIZARD_STEPS[self._active_step_index][0] == "conditions":
            if self._maybe_normalize_condition_images_before_advance():
                return
        self._advance_to_next_step()

    def _advance_to_next_step(self) -> None:
        self._active_step_index += 1
        self.refresh()

    def _go_to_step_from_progress(self, step_index: int) -> None:
        if not self._step_jump_enabled or self._active_normalization_task is not None:
            return
        self.flush_pending_edits()
        self._active_step_index = max(0, min(step_index, len(_WIZARD_STEPS) - 1))
        self.refresh()

    def _maybe_normalize_condition_images_before_advance(self) -> bool:
        try:
            scan = self._document.scan_condition_image_normalization()
        except Exception as error:
            _show_error_dialog(self, "Image Readiness Error", error)
            return True
        if not scan.needs_normalization:
            return False
        if not scan.can_normalize:
            _show_error_dialog(
                self,
                "Image Readiness Error",
                RuntimeError("Selected image folders cannot be normalized automatically."),
            )
            return True
        dialog = ImageNormalizationDialog(scan, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return True
        self._start_condition_image_normalization(dialog.target_size())
        return True

    def _start_condition_image_normalization(self, target_size: int) -> None:
        task = ProgressTask(
            parent_widget=self,
            label="Normalizing condition images...",
            callback=lambda: self._document.normalize_condition_images(target_size=target_size),
            window_title="Normalizing Images",
        )
        self._active_normalization_task = task
        self.setup_wizard_next_button.setEnabled(False)
        task.succeeded.connect(lambda _result: self._advance_to_next_step())
        task.failed.connect(self._on_condition_image_normalization_failed)
        task.finished.connect(self._on_condition_image_normalization_finished)
        task.start()

    def _on_condition_image_normalization_failed(self, error: object) -> None:
        if isinstance(error, Exception):
            _show_error_dialog(self, "Image Normalization Error", error)
        else:
            _show_error_dialog(self, "Image Normalization Error", RuntimeError(str(error)))

    def _on_condition_image_normalization_finished(self) -> None:
        self._active_normalization_task = None
        self.refresh()

    def _return_home(self) -> None:
        self.flush_pending_edits()
        if self._current_step_key() == "review":
            answer = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Are you sure you want to return home without saving your changes?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
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

    def _save_from_review(self) -> None:
        self.flush_pending_edits()
        if self._on_save_project is not None:
            saved = self._on_save_project()
            if saved and self._on_return_home is not None:
                QMessageBox.information(
                    self,
                    "Experiment Saved",
                    "Experiment settings have been saved.",
                    QMessageBox.StandardButton.Ok,
                )
                self._on_return_home()

    def refresh(self) -> None:
        self._readiness_cache = None
        self._active_step_index = max(
            0,
            min(self._active_step_index, len(_WIZARD_STEPS) - 1),
        )
        step_key, title = _WIZARD_STEPS[self._active_step_index]
        self.step_stack.setCurrentIndex(self._active_step_index)
        self.advanced_stack.setCurrentIndex(0)
        self.content_stack.setCurrentWidget(self.guided_panel)
        self._refresh_current_editor_page()

        self._refresh_progress_steps()
        self.step_title_label.setText(title)
        self._refresh_review_summary()

        step_valid = self._current_step_valid()
        self.step_title_label.setVisible(False)
        self.step_status_badge.setVisible(False)
        self.step_status_label.setText(self._step_status_text(self._active_step_index))
        self.step_status_label.setVisible(False)
        self.step_card.setProperty(
            "wizardProjectStepFrame",
            "false",
        )
        refresh_widget_style(self.step_card)
        self.setup_wizard_back_button.setEnabled(self._active_step_index > 0)
        self.setup_wizard_next_button.setEnabled(step_valid)
        self.setup_wizard_next_button.setText("Next")
        self.setup_wizard_next_button.setVisible(step_key != "review")
        self.setup_wizard_return_home_button.setVisible(step_key != "review")
        self._sync_guided_panel_height()

    def _sync_guided_panel_height(self) -> None:
        viewport_height = self.shell.page_container.scroll_area.viewport().height()
        if viewport_height <= 0:
            return
        viewport_height = min(viewport_height, _SETUP_STEP_CARD_MAX_HEIGHT)

        card_margins = self.step_card.card_layout.contentsMargins()
        progress_height = self.progress_panel_shell.sizeHint().height()
        body_spacing = self.step_card.body_layout.spacing()
        content_height = max(
            0,
            viewport_height
            - card_margins.top()
            - card_margins.bottom()
            - progress_height
            - body_spacing,
        )
        self.step_card.setMaximumHeight(viewport_height)
        self.step_content_anchor.setMaximumHeight(content_height)
        self.content_stack.setMaximumHeight(content_height)
        self.guided_panel.setMaximumHeight(content_height)

    def _refresh_current_editor_page(self) -> None:
        current_guided_widget = self.step_stack.currentWidget()
        refresh = getattr(current_guided_widget, "refresh", None)
        if callable(refresh):
            refresh()

    def _readiness_report(self) -> LauncherReadinessReport:
        refresh_hz = self.runtime_settings_editor.current_refresh_hz()
        cache_key = (
            id(self._document.project),
            refresh_hz,
            self._document.last_session_plan is not None,
        )
        if self._readiness_cache is not None and self._readiness_cache[0] == cache_key:
            return self._readiness_cache[1]
        report = _launcher_readiness_report(self._document, refresh_hz=refresh_hz)
        self._readiness_cache = (cache_key, report)
        return report

    def _refresh_review_summary(self) -> None:
        while self.review_checklist_layout.count():
            item = self.review_checklist_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        for index, (section_title, lines) in enumerate(self._review_checklist_sections()):
            self.review_checklist_layout.addWidget(
                self._review_summary_section(section_title, lines),
                index // 2,
                index % 2,
            )

    def _review_summary_section(self, title: str, lines: tuple[str, ...]) -> QFrame:
        section = QFrame(self.review_checklist_container)
        section.setProperty("reviewSummarySection", "true")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(10, 6, 10, 6)
        section_layout.setSpacing(3)

        title_label = QLabel(title, section)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setProperty("reviewSummarySectionTitle", "true")
        section_layout.addWidget(title_label)

        body = QWidget(section)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(3)
        body_layout.addStretch(1)
        for line in lines:
            body_layout.addWidget(self._review_checklist_row(line, parent=body))
        body_layout.addStretch(1)
        section_layout.addWidget(body, 1)
        return section

    def _review_checklist_row(self, text: str, *, parent: QWidget) -> QFrame:
        row = QFrame(parent)
        row.setProperty("reviewChecklistRow", "true")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 1, 0, 1)
        row_layout.setSpacing(6)

        check_icon = QLabel("\u2713", row)
        check_icon.setProperty("reviewCheckIcon", "true")
        check_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row_layout.addWidget(check_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        label = QLabel(text, row)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setProperty("reviewChecklistLine", "true")
        row_layout.addWidget(label, 1, Qt.AlignmentFlag.AlignVCenter)
        return row

    def _review_checklist_sections(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        project = self._document.project
        conditions = self._document.ordered_conditions()
        session = project.settings.session
        display = project.settings.display

        condition_lines = (
            f"{len(conditions)} condition{'s' if len(conditions) != 1 else ''} configured",
        )

        block_count = session.block_count
        background_label = self._display_background_label(str(display.background_color))
        repeat_word = "time" if block_count == 1 else "times"
        experiment_lines = (
            f"Each condition will repeat {block_count} {repeat_word} "
            f"in randomized block order",
            "Condition order is randomized automatically at launch",
            f"Display: {self.runtime_settings_editor.current_refresh_hz():.2f} Hz, "
            f"{background_label}",
            f"Image width: {display.stimulus_width_degrees:.1f} deg at "
            f"{display.viewing_distance_cm:.0f} cm on "
            f"{display.screen_width_px} x {display.screen_height_px}",
            *self._review_timing_estimate_lines(),
        )
        return (
            ("Project Details", (f"Project details complete: {project.meta.name}",)),
            ("Conditions", tuple(condition_lines)),
            ("Experiment Settings", experiment_lines),
            ("Fixation Cross", (self._fixation_review_line(),)),
        )

    def _review_timing_estimate_lines(self) -> tuple[str, ...]:
        conditions = self._document.ordered_conditions()
        if not conditions:
            return ("Estimated run time: unavailable",)

        try:
            guidance = condition_fixation_guidance(
                self._document.project,
                refresh_hz=self.runtime_settings_editor.current_refresh_hz(),
            )
        except FrameValidationError:
            return ("Estimated run time: unavailable for current refresh rate",)
        condition_ids = {condition.condition_id for condition in conditions}
        ordered_guidance = [row for row in guidance if row.condition_id in condition_ids]
        block_count = self._document.project.settings.session.block_count
        condition_time_seconds = sum(row.condition_duration_seconds for row in ordered_guidance)
        total_condition_runs = len(ordered_guidance) * block_count
        break_count = max(0, total_condition_runs - 1)
        break_seconds = break_count * _ESTIMATED_INTER_CONDITION_BREAK_SECONDS
        total_seconds = (condition_time_seconds * block_count) + break_seconds
        estimated_minutes = max(1, ceil(total_seconds / 60))
        minute_word = "minute" if estimated_minutes == 1 else "minutes"
        return (f"Estimated run time: {estimated_minutes} {minute_word}",)

    @staticmethod
    def _display_background_label(background_color: str) -> str:
        return {
            "#000000": "Black background",
            "#101010": "Dark gray background",
        }.get(background_color, background_color)

    def _fixation_review_line(self) -> str:
        return "Fixation cross has been configured"

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
            if not self._conditions_have_required_trigger_codes(ordered_conditions):
                return "Set trigger codes"
            return "Assign base and oddball folders"
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
            return self._conditions_images_ready(ordered_conditions)
        if step_key == "experiment":
            return self.runtime_settings_editor.current_refresh_hz() > 0.0
        if step_key == "fixation":
            return True
        if step_key == "response":
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
                return "Enter descriptive condition names"
            if not self._conditions_have_required_trigger_codes(ordered_conditions):
                return "Set trigger codes above 0"
            return "Assign base and oddball folders"
        if step_key == "experiment":
            return "Set a valid refresh rate"
        if step_key == "review":
            return self._readiness_report().status_label
        return "Step needs attention"

    def _project_details_ready(self) -> bool:
        project = self._document.project
        return bool(
            project.meta.name.strip()
            and self.project_overview_editor.project_description_edit.toPlainText().strip()
            and self._document.project_root
        )

    def _project_details_blocker(self) -> str:
        project = self._document.project
        if not project.meta.name.strip():
            return "Enter a project name"
        if not self.project_overview_editor.project_description_edit.toPlainText().strip():
            return "Enter a project description"
        if not self._document.project_root:
            return "Choose a project folder"
        return "Project details needed"

    @staticmethod
    def _conditions_have_required_names(ordered_conditions: list) -> bool:
        return all(is_guided_condition_name(condition.name) for condition in ordered_conditions)

    @staticmethod
    def _conditions_have_required_trigger_codes(ordered_conditions: list) -> bool:
        return all(
            is_guided_trigger_code(condition.trigger_code)
            for condition in ordered_conditions
        )

    def _conditions_identity_ready(self, ordered_conditions: list) -> bool:
        return (
            bool(ordered_conditions)
            and self._conditions_have_required_names(ordered_conditions)
            and self._conditions_have_required_trigger_codes(ordered_conditions)
        )

    def _conditions_images_ready(self, ordered_conditions: list) -> bool:
        return (
            self._conditions_identity_ready(ordered_conditions)
            and _conditions_have_assigned_assets(self._document, ordered_conditions)
        )

    def _refresh_progress_steps(self) -> None:
        current = self._active_step_index
        self.progress_steps.set_navigation_enabled(self._step_jump_enabled)
        self.progress_steps.set_active_index(current)

    def _step_index_for_key(self, step_key: str) -> int:
        aliases = {
            "display": "experiment",
            "runtime": "experiment",
            "session": "experiment",
            "images": "conditions",
            "stimuli": "conditions",
            "assets": "conditions",
            "fixation_cross": "fixation",
            "accuracy": "response",
            "appearance": "response",
        }
        step_key = aliases.get(step_key, step_key)
        for index, (candidate, _title) in enumerate(_WIZARD_STEPS):
            if candidate == step_key:
                return index
        return 0

    def _current_step_key(self) -> str:
        return _WIZARD_STEPS[self._active_step_index][0]
