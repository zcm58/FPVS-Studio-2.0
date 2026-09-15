"""Guided setup wizard for FPVS Studio projects."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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

from fpvs_studio.core.enums import ExperimentCategory, PresentationUnit, StimulusModality
from fpvs_studio.core.experiment_categories import category_conflict_condition_ids
from fpvs_studio.core.frame_validation import FrameValidationError
from fpvs_studio.core.models import AttentionalBlinkStreamSettings, ConditionTemplateProfile
from fpvs_studio.core.validation import condition_fixation_guidance
from fpvs_studio.gui.assets_pages import AssetsPage
from fpvs_studio.gui.attentional_blink_character_size import AttentionalBlinkCharacterSizeEditor
from fpvs_studio.gui.attentional_blink_stream_designer import is_letter_stream_project
from fpvs_studio.gui.components import (
    PAGE_SECTION_GAP,
    NonHomePageShell,
    SectionCard,
    SetupProgressStepper,
    StatusBadgeLabel,
    apply_setup_wizard_theme,
    configure_setup_form,
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
from fpvs_studio.gui.design_setup_step import DesignSetupStep
from fpvs_studio.gui.design_system import PAGE_MARGIN_X
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.document_stimuli import condition_image_set_requires_normalization
from fpvs_studio.gui.image_normalization_dialog import ImageNormalizationDialog
from fpvs_studio.gui.presentation_settings_dialog import presentation_defaults_summary
from fpvs_studio.gui.project_overview_page import ProjectOverviewEditor
from fpvs_studio.gui.run_page import RunPage
from fpvs_studio.gui.runtime_settings_page import DisplaySettingsEditor, ImageDisplaySizeEditor
from fpvs_studio.gui.session_pages import FixationSettingsEditor, SessionStructureEditor
from fpvs_studio.gui.window_helpers import (
    LauncherReadinessReport,
    _coerce_exception,
    _conditions_have_assigned_assets,
    _launcher_readiness_report,
    _show_error_dialog,
    _timing_template_label,
)
from fpvs_studio.gui.workers import BackgroundTask, ProgressTask
from fpvs_studio.preprocessing.normalization import ImageNormalizationScan

_WIZARD_STEPS: tuple[tuple[str, str], ...] = (
    ("project", "Project"),
    ("conditions", "Conditions"),
    ("design", "Design"),
    ("experiment", "Timing & Session"),
    ("image_size", "Image Size"),
    ("fixation", "Fixation"),
    ("response", "Response"),
    ("review", "Review"),
)
_ESTIMATED_INTER_CONDITION_BREAK_SECONDS = 30
_SETUP_STEP_SURFACE_MAX_WIDTH = 880
_SETUP_STEP_WORKBENCH_SURFACE_MAX_WIDTH = 1040
_SETUP_STEP_SURFACE_MIN_HEIGHT = 360
_SETUP_STEP_CARD_MAX_HEIGHT = 552


@dataclass
class _ReviewSummaryWidgets:
    section: QFrame
    title_label: QLabel
    body: QWidget
    body_layout: QVBoxLayout
    rows: list[tuple[QFrame, QLabel]]
    edit_button: QPushButton
    fixation_edit_button: QPushButton


def _scan_requires_setup_normalization(scan: ImageNormalizationScan) -> bool:
    """Return whether Setup must rewrite images before compilation.

    Uniform rectangular inputs are valid presentation sources now that geometry is
    explicit. Within-set mixed dimensions and genuinely unsupported files still use
    the existing normalization path; supported file types may remain mixed.
    """

    return any(condition_image_set_requires_normalization(item) for item in scan.sets)


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
        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        row_layout.addStretch(1)
        row_layout.addWidget(content, 10000)
        row_layout.addStretch(1)
        layout.addStretch(1)
        layout.addWidget(row)
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
        self._readiness_cache: tuple[tuple[int, float, bool], LauncherReadinessReport] | None = None
        self._step_jump_enabled = False
        self._active_image_readiness_task: ProgressTask | None = None
        self._active_image_prescan_task: BackgroundTask | None = None
        self._active_image_prescan_key: tuple[object, ...] | None = None
        self._image_prescan_pending_advance = False
        self._active_normalization_task: ProgressTask | None = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(0)
        self._refresh_timer.timeout.connect(self.refresh)

        self.conditions_page = ConditionsPage(document, embedded=True, parent=self)
        self.condition_setup_step = ConditionSetupStep(document, self)
        self.design_setup_step = DesignSetupStep(document, parent=self)
        self.design_setup_step.setMinimumWidth(1000)
        self.design_setup_step.applied.connect(self.schedule_refresh)
        self.design_setup_step.busy_changed.connect(self.schedule_refresh)
        self.design_setup_step.draft_changed.connect(self.schedule_refresh)
        self.add_condition_button = self.condition_setup_step.add_condition_button
        self.assets_page = AssetsPage(document, self)
        self.run_page = RunPage(document, parent=self)
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
            require_refresh_verification=True,
            parent=self,
        )
        self.runtime_settings_editor.refresh_verification_changed.connect(self.schedule_refresh)
        self.image_display_size_editor = (
            AttentionalBlinkCharacterSizeEditor(document, parent=self)
            if is_letter_stream_project(document)
            else ImageDisplaySizeEditor(document, parent=self)
        )
        if isinstance(self.image_display_size_editor, AttentionalBlinkCharacterSizeEditor):
            self.image_display_size_editor.draft_changed.connect(self.schedule_refresh)
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
        title_row = QHBoxLayout()
        title_row.setContentsMargins(12, 0, 12, 0)
        self.shell.page_container.header_layout.removeWidget(self.shell.title_label)
        title_row.addWidget(self.shell.title_label, 1)
        self.step_count_label = QLabel(self)
        self.step_count_label.setObjectName("setup_wizard_step_count")
        title_row.addWidget(self.step_count_label)
        self.shell.page_container.header_layout.insertLayout(0, title_row)

        self.progress_steps = SetupProgressStepper(
            tuple(
                "Character Size" if key == "image_size" and is_letter_stream_project(document)
                else title for key, title in _WIZARD_STEPS
            ),
            parent=self,
        )
        self.progress_steps.step_requested.connect(self._go_to_step_from_progress)
        self.progress_step_labels = self.progress_steps.step_labels

        progress_panel = QWidget(self)
        progress_panel.setObjectName("setup_wizard_progress_panel")
        progress_panel.setMaximumWidth(1400)
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
        mark_primary_action(self.setup_wizard_next_button)
        self.setup_wizard_return_home_button = QPushButton("Return Home", self)
        self.setup_wizard_return_home_button.setObjectName("setup_wizard_return_home_button")
        self.setup_wizard_return_home_button.clicked.connect(self._return_home)
        self.review_save_button = QPushButton("Save and Return Home", self)
        self.review_save_button.setObjectName("setup_wizard_review_save_button")
        self.review_save_button.clicked.connect(self._save_from_review)
        mark_primary_action(self.review_save_button)
        self.review_return_home_button = QPushButton("Return Home Without Saving", self)
        self.review_return_home_button.setObjectName("setup_wizard_review_return_home_button")
        self.review_return_home_button.clicked.connect(self._return_home)
        mark_secondary_action(self.review_return_home_button)
        self.setup_wizard_next_hint_label = QLabel(self)
        self.setup_wizard_next_hint_label.setObjectName("setup_wizard_next_hint_label")
        self.setup_wizard_next_hint_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.setup_wizard_next_hint_label.setWordWrap(True)
        self.setup_wizard_next_hint_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.setup_wizard_next_hint_container = QWidget(self)
        self.setup_wizard_next_hint_container.setObjectName("setup_wizard_next_hint_container")
        next_hint_layout = QHBoxLayout(self.setup_wizard_next_hint_container)
        next_hint_layout.setContentsMargins(0, 0, 0, 0)
        next_hint_layout.addWidget(self.setup_wizard_next_hint_label)
        self.setup_wizard_fix_button = QPushButton("Show field", self)
        self.setup_wizard_fix_button.setObjectName("setup_wizard_fix_button")
        mark_secondary_action(self.setup_wizard_fix_button)
        self.setup_wizard_fix_button.clicked.connect(self._focus_step_blocker)
        next_hint_layout.addWidget(self.setup_wizard_fix_button)

        button_row = QWidget(self)
        button_row.setObjectName("setup_wizard_navigation_row")
        self.navigation_row = button_row
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(PAGE_MARGIN_X, 0, PAGE_MARGIN_X, 2)
        button_layout.setSpacing(PAGE_SECTION_GAP)
        button_layout.addWidget(self.setup_wizard_return_home_button)
        button_layout.addWidget(self.review_return_home_button)
        button_layout.addWidget(self.setup_wizard_next_hint_container, 1)
        button_layout.addWidget(self.setup_wizard_back_button)
        button_layout.addWidget(self.setup_wizard_next_button)
        button_layout.addWidget(self.review_save_button)

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
        if not self.flush_pending_edits():
            return
        if allow_step_jumps is not None:
            self._step_jump_enabled = allow_step_jumps
        if step_key is not None:
            self._select_step(self._step_index_for_key(step_key))
        self.refresh()

    def flush_pending_edits(self) -> bool:
        if self._condition_image_task_active():
            return False
        if self.design_setup_step.has_pending_design():
            if not self.design_setup_step.apply_pending_design():
                self._active_step_index = self._step_index_for_key("design")
                self.refresh()
                return False
        self.project_overview_editor.flush_pending_edits()
        self.condition_setup_step.flush_pending_edits()
        self.conditions_page.flush_pending_edits()
        return True

    def _select_step(self, index: int) -> None:
        target_key = _WIZARD_STEPS[index][0]
        if target_key == "design" and self._current_step_key() != "design":
            self.design_setup_step.refresh()
            selected = self.condition_setup_step.selected_condition_id()
            if selected is not None and not self.design_setup_step.select_condition(selected):
                return
        elif target_key == "conditions" and self._current_step_key() == "design":
            selected = self.design_setup_step.selected_condition_id()
            condition_list = self.condition_setup_step.condition_list
            for row in range(condition_list.count()):
                if condition_list.item(row).data(Qt.ItemDataRole.UserRole) == selected:
                    condition_list.setCurrentRow(row)
                    break
        self._active_step_index = index

    def schedule_refresh(self) -> None:
        self._readiness_cache = None
        if not self._refresh_timer.isActive():
            self._refresh_timer.start()

    def _build_step_pages(self) -> None:
        project_layout = self.project_overview_editor.layout()
        assert project_layout is not None
        project_layout.setAlignment(
            self.project_overview_editor.project_overview_card, Qt.AlignmentFlag(0)
        )
        self.project_step_surface = _SetupStepSurface(
            self.project_overview_editor,
            object_name="setup_wizard_project_surface",
            max_width=760,
            parent=self,
        )
        self.conditions_step_surface = _SetupStepSurface(
            self.condition_setup_step,
            object_name="setup_wizard_conditions_surface",
            max_width=_SETUP_STEP_WORKBENCH_SURFACE_MAX_WIDTH,
            parent=self,
        )
        self.design_step_surface = _SetupStepSurface(
            self.design_setup_step,
            object_name="setup_wizard_design_surface",
            max_width=1400,
            parent=self,
        )
        self.experiment_step_surface = _SetupStepSurface(
            self._experiment_settings_step_page(),
            object_name="setup_wizard_experiment_surface",
            max_width=880,
            parent=self,
        )
        self.image_size_settings_card = self._settings_step_card(
            self.image_display_size_editor,
            title="Character Size" if is_letter_stream_project(self._document) else "Image Size",
            subtitle="Set the on-screen stimulus size and calibrate the viewing geometry.",
            object_name="setup_wizard_image_size_settings_card",
        )
        self.image_size_step_surface = _SetupStepSurface(
            self.image_size_settings_card,
            object_name="setup_wizard_image_size_surface",
            max_width=760,
            parent=self,
        )
        self.fixation_step_surface = _SetupStepSurface(
            self.fixation_schedule_editor,
            object_name="setup_wizard_fixation_surface",
            max_width=_SETUP_STEP_WORKBENCH_SURFACE_MAX_WIDTH,
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
            parent=self,
        )
        self.step_stack.addWidget(self.project_step_surface)
        self.step_stack.addWidget(self.conditions_step_surface)
        self.step_stack.addWidget(self.design_step_surface)
        self.step_stack.addWidget(self.experiment_step_surface)
        self.step_stack.addWidget(self.image_size_step_surface)
        self.step_stack.addWidget(self.fixation_step_surface)
        self.step_stack.addWidget(self.response_step_surface)
        self.step_stack.addWidget(self.review_step_surface)
        for card in (
            self.project_overview_editor.project_overview_card,
            self.experiment_settings_card,
            self.image_size_settings_card,
            self.session_settings_card,
            self.review_card,
        ):
            card.title_label.setVisible(
                card in (self.experiment_settings_card, self.session_settings_card)
            )
            if card.subtitle_label is not None:
                card.subtitle_label.hide()
            card.setProperty("setupFlatSection", "true")
            card.card_layout.setContentsMargins(0, 8, 0, 8)
            refresh_widget_style(card)

    def _settings_step_card(
        self, editor: QWidget, *, title: str, subtitle: str, object_name: str
    ) -> SectionCard:
        card = SectionCard(title=title, subtitle=subtitle, object_name=object_name, parent=self)
        card.setMaximumWidth(_SETUP_STEP_SURFACE_MAX_WIDTH)
        card.setMinimumWidth(0)
        card.body_layout.addWidget(editor)
        return card

    def _experiment_settings_step_page(self) -> QWidget:
        page = QWidget(self)
        page.setObjectName("setup_wizard_experiment_settings_page")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(32)
        self.experiment_settings_card = self._settings_step_card(
            self.runtime_settings_editor,
            title="Display",
            subtitle="Verify display timing and choose the experiment background.",
            object_name="setup_wizard_experiment_settings_card",
        )
        self.session_settings_card = self._settings_step_card(
            self.session_structure_editor,
            title="Session",
            subtitle="",
            object_name="setup_wizard_session_settings_card",
        )
        configure_setup_form(self.session_structure_editor.session_layout, stacked=True)
        self.session_structure_editor.block_count_spin.setFixedWidth(240)
        self.session_structure_editor.seed_help_label.setMinimumHeight(30)
        self.runtime_settings_editor.refresh_hz_combo.setFixedWidth(240)
        layout.addWidget(self.experiment_settings_card, 1, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.session_settings_card, 1, Qt.AlignmentFlag.AlignTop)
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

        self.review_checklist_container = QWidget(self.review_card)
        self.review_checklist_container.setObjectName("setup_wizard_review_checklist")
        self.review_checklist_layout = QGridLayout(self.review_checklist_container)
        self.review_checklist_layout.setContentsMargins(0, 0, 0, 0)
        self.review_checklist_layout.setHorizontalSpacing(8)
        self.review_checklist_layout.setVerticalSpacing(6)
        self._review_summary_widgets: list[_ReviewSummaryWidgets] = []
        self.review_card.body_layout.addWidget(self.review_checklist_container)

        layout.addWidget(self.review_card)
        return page

    def _go_back(self) -> None:
        if not self.flush_pending_edits():
            return
        if self._active_step_index > 0:
            self._select_step(self._active_step_index - 1)
            self.refresh()

    def _go_next(self) -> None:
        if not self.flush_pending_edits():
            return
        if not self._current_step_valid():
            return
        if self._active_step_index == len(_WIZARD_STEPS) - 1:
            self._return_home()
            return
        if self._current_step_key() == "design":
            if not self.design_setup_step.apply_pending_design():
                self.refresh()
                return
            self._start_condition_image_readiness_scan()
            return
        self._advance_to_next_step()

    def _advance_to_next_step(self) -> None:
        self._select_step(self._active_step_index + 1)
        self.refresh()

    def _go_to_step_from_progress(self, step_index: int) -> None:
        if not self._step_jump_enabled or self._condition_image_task_active():
            return
        if not self.flush_pending_edits():
            return
        self._select_step(max(0, min(step_index, len(_WIZARD_STEPS) - 1)))
        self.refresh()

    def _condition_image_task_active(self) -> bool:
        return (
            self._active_image_readiness_task is not None
            or self._active_normalization_task is not None
            or self._image_prescan_pending_advance
            or self.design_setup_step.is_importing()
        )

    def _active_condition_image_task_hint(self) -> str:
        if self._active_image_readiness_task is not None or self._image_prescan_pending_advance:
            return "Checking image readiness..."
        if self._active_normalization_task is not None:
            return "Normalizing condition images..."
        if self.design_setup_step.is_importing():
            return "Importing design images..."
        return ""

    def _start_condition_image_readiness_scan(self) -> None:
        if self._active_image_readiness_task is not None:
            return
        cache_key = self._document.condition_image_normalization_scan_key()
        cached_scan = self._document.cached_condition_image_normalization_scan(
            cache_key=cache_key,
        )
        if cached_scan is not None:
            self._on_condition_image_readiness_scan_succeeded(cached_scan)
            return
        if (
            self._active_image_prescan_task is not None
            and self._active_image_prescan_key == cache_key
        ):
            self._image_prescan_pending_advance = True
            self.refresh()
            return
        task = ProgressTask(
            parent_widget=self,
            label="Checking condition image readiness...",
            callback=self._document.scan_condition_image_normalization,
            window_title="Checking Images",
        )
        self._active_image_readiness_task = task
        self.refresh()
        task.succeeded.connect(self._on_condition_image_readiness_scan_succeeded)
        task.failed.connect(self._on_condition_image_readiness_scan_failed)
        task.finished.connect(self._on_condition_image_readiness_scan_finished)
        task.start()

    def _on_condition_image_readiness_scan_succeeded(
        self,
        scan: ImageNormalizationScan,
    ) -> None:
        if not _scan_requires_setup_normalization(scan):
            self._advance_to_next_step()
            return
        if not scan.can_normalize:
            _show_error_dialog(
                self,
                "Image Readiness Error",
                RuntimeError("Selected image folders cannot be normalized automatically."),
            )
            return
        dialog = ImageNormalizationDialog(scan, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._start_condition_image_normalization(dialog.target_size())

    def _on_condition_image_readiness_scan_failed(self, error: object) -> None:
        _show_error_dialog(self, "Image Readiness Error", _coerce_exception(error))

    def _on_condition_image_readiness_scan_finished(self) -> None:
        self._active_image_readiness_task = None
        self.refresh()

    def _ensure_condition_image_prescan_started(self) -> None:
        if self._current_step_key() != "design":
            return
        if (
            self._active_image_readiness_task is not None
            or self._active_normalization_task is not None
        ):
            return
        if not self._current_step_valid():
            return
        cache_key = self._document.condition_image_normalization_scan_key()
        if (
            self._document.cached_condition_image_normalization_scan(cache_key=cache_key)
            is not None
        ):
            return
        if self._active_image_prescan_task is not None:
            return

        task = BackgroundTask(
            parent_widget=self,
            callback=self._document.scan_condition_image_normalization,
        )
        self._active_image_prescan_task = task
        self._active_image_prescan_key = cache_key
        task.succeeded.connect(self._on_condition_image_prescan_succeeded)
        task.failed.connect(self._on_condition_image_prescan_failed)
        task.finished.connect(self._on_condition_image_prescan_finished)
        task.start()

    def _on_condition_image_prescan_succeeded(self, scan: ImageNormalizationScan) -> None:
        current_key = self._document.condition_image_normalization_scan_key()
        if not self._image_prescan_pending_advance:
            return
        self._image_prescan_pending_advance = False
        if self._active_image_prescan_key == current_key:
            self._on_condition_image_readiness_scan_succeeded(scan)

    def _on_condition_image_prescan_failed(self, error: object) -> None:
        if not self._image_prescan_pending_advance:
            return
        self._image_prescan_pending_advance = False
        self._on_condition_image_readiness_scan_failed(error)

    def _on_condition_image_prescan_finished(self) -> None:
        self._active_image_prescan_task = None
        self._active_image_prescan_key = None
        self.refresh()

    def _start_condition_image_normalization(self, target_size: int) -> None:
        task = ProgressTask(
            parent_widget=self,
            label="Normalizing condition images...",
            callback=lambda: self._document.normalize_condition_images(target_size=target_size),
            window_title="Normalizing Images",
        )
        self._active_normalization_task = task
        self.refresh()
        task.succeeded.connect(lambda _result: self._advance_to_next_step())
        task.failed.connect(self._on_condition_image_normalization_failed)
        task.finished.connect(self._on_condition_image_normalization_finished)
        task.start()

    def _on_condition_image_normalization_failed(self, error: object) -> None:
        _show_error_dialog(self, "Image Normalization Error", _coerce_exception(error))

    def _on_condition_image_normalization_finished(self) -> None:
        self._active_normalization_task = None
        self.refresh()

    def _return_home(self) -> None:
        if self._condition_image_task_active():
            return
        if self.design_setup_step.has_pending_design():
            answer = QMessageBox.question(
                self,
                "Unapplied Design",
                "Discard the unapplied design changes and return Home?\n\n"
                "The last applied timing and imported images remain in this open project.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            if not self.design_setup_step.discard_pending_design():
                return
            self.project_overview_editor.flush_pending_edits()
            self.condition_setup_step.flush_pending_edits()
            self.conditions_page.flush_pending_edits()
            if self._on_return_home is not None:
                self._on_return_home()
            return
        if not self.flush_pending_edits():
            return
        if self._current_step_key() == "review":
            answer = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Return Home without saving to disk?\n\n"
                "Your edits remain in this open project until you close it. "
                "Save the project to keep them for your next session.",
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
        if not self.flush_pending_edits():
            return
        if self._on_save_project is not None:
            saved = self._on_save_project()
            if saved and self._on_return_home is not None:
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
        is_design = step_key == "design"
        page_titles = {
            "project": "Set up your experiment",
            "conditions": "Configure your conditions",
            "design": "Design your sequence",
            "experiment": "Set your timing and session",
            "image_size": "Set your character size" if is_letter_stream_project(self._document)
            else "Set your image size",
            "fixation": "Configure fixation",
            "response": "Configure responses and appearance",
            "review": "Review your experiment",
        }
        self.shell.title_label.setText(page_titles[step_key])
        if is_design and is_letter_stream_project(self._document):
            self.shell.title_label.setText("Design your attentional blink study")
        self.shell.title_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self.step_count_label.setText(f"Step {self._active_step_index + 1} of {len(_WIZARD_STEPS)}")
        page_layout = self.shell.page_container.layout()
        assert page_layout is not None
        page_layout.setSpacing(8)
        self.step_title_label.setText(title)
        if step_key == "review":
            self._refresh_review_summary()

        step_valid = self._current_step_valid()
        condition_image_task_active = self._condition_image_task_active()
        self.step_title_label.setVisible(False)
        self.step_status_badge.setVisible(False)
        self.step_status_label.setText(self._step_status_text(self._active_step_index))
        self.step_status_label.setVisible(False)
        self.setup_wizard_back_button.setEnabled(
            self._active_step_index > 0 and not condition_image_task_active
        )
        self.setup_wizard_next_button.setEnabled(step_valid and not condition_image_task_active)
        self.setup_wizard_next_button.setText("Next")
        self.setup_wizard_next_button.setVisible(step_key != "review")
        self.setup_wizard_return_home_button.setEnabled(not condition_image_task_active)
        self.setup_wizard_return_home_button.setVisible(step_key != "review")
        self.review_save_button.setVisible(step_key == "review")
        self.review_return_home_button.setVisible(step_key == "review")
        self.review_save_button.setEnabled(not condition_image_task_active)
        self.review_return_home_button.setEnabled(not condition_image_task_active)
        hint_text = (
            self._active_condition_image_task_hint()
            if condition_image_task_active
            else ""
            if step_valid or step_key in {"review", "experiment"}
            else self._next_step_hint_text()
        )
        if is_design and step_valid and not condition_image_task_active:
            hint_text = "Changes apply when you select Next."
        self.setup_wizard_next_hint_label.setText(hint_text)
        self.setup_wizard_next_hint_label.setToolTip(hint_text)
        self.setup_wizard_next_hint_label.setVisible(bool(hint_text))
        self.setup_wizard_fix_button.setVisible(
            bool(hint_text)
            and not condition_image_task_active
            and step_key in {"project", "conditions"}
        )
        self._sync_guided_panel_height()
        QTimer.singleShot(0, self._sync_guided_panel_height)
        self._ensure_condition_image_prescan_started()

    def _sync_guided_panel_height(self) -> None:
        viewport_height = self.shell.page_container.scroll_area.viewport().height()
        if viewport_height <= 0:
            return
        maximum = _SETUP_STEP_CARD_MAX_HEIGHT + 100 + max(0, self.height() - 800)
        viewport_height = min(viewport_height, maximum)

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
        sections = self._review_checklist_sections()
        while len(self._review_summary_widgets) < len(sections):
            index = len(self._review_summary_widgets)
            widgets = self._create_review_summary_section()
            self._review_summary_widgets.append(widgets)
            self.review_checklist_layout.addWidget(
                widgets.section,
                index // 2,
                index % 2,
            )

        for widgets, (step_key, section_title, lines) in zip(
            self._review_summary_widgets,
            sections,
            strict=False,
        ):
            widgets.section.setVisible(True)
            widgets.title_label.setText(section_title)
            widgets.edit_button.setProperty("reviewStepKey", step_key)
            widgets.edit_button.setText("Response" if step_key == "response" else "Edit")
            widgets.edit_button.setAccessibleName(
                "Edit Response" if step_key == "response" else f"Edit {section_title}"
            )
            widgets.edit_button.setVisible(self._step_jump_enabled)
            widgets.edit_button.setEnabled(not self._condition_image_task_active())
            widgets.fixation_edit_button.setVisible(
                self._step_jump_enabled and step_key == "response"
            )
            widgets.fixation_edit_button.setEnabled(not self._condition_image_task_active())
            while len(widgets.rows) < len(lines):
                row_widgets = self._review_checklist_row(parent=widgets.body)
                widgets.rows.append(row_widgets)
                widgets.body_layout.insertWidget(
                    widgets.body_layout.count() - 1,
                    row_widgets[0],
                )
            for (row_frame, label), text in zip(widgets.rows, lines, strict=False):
                label.setText(text)
                label.setToolTip(text)
                row_frame.setVisible(True)
            for row_frame, _label in widgets.rows[len(lines) :]:
                row_frame.setVisible(False)

        for widgets in self._review_summary_widgets[len(sections) :]:
            widgets.section.setVisible(False)

    def _create_review_summary_section(self) -> _ReviewSummaryWidgets:
        section = QFrame(self.review_checklist_container)
        section.setProperty("reviewSummarySection", "true")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(10, 6, 10, 6)
        section_layout.setSpacing(3)

        title_label = QLabel(section)
        title_label.setProperty("reviewSummarySectionTitle", "true")
        header = QHBoxLayout()
        header.addWidget(title_label, 1)
        fixation_edit_button = QPushButton("Fixation", section)
        fixation_edit_button.setAccessibleName("Edit Fixation")
        mark_secondary_action(fixation_edit_button)
        fixation_edit_button.clicked.connect(
            lambda: self._go_to_step_from_progress(self._step_index_for_key("fixation"))
        )
        header.addWidget(fixation_edit_button)
        edit_button = QPushButton("Edit", section)
        mark_secondary_action(edit_button)
        edit_button.clicked.connect(
            lambda: self._go_to_step_from_progress(
                self._step_index_for_key(str(edit_button.property("reviewStepKey")))
            )
        )
        header.addWidget(edit_button)
        section_layout.addLayout(header)

        body = QWidget(section)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(3)
        body_layout.addStretch(1)
        section_layout.addWidget(body, 1)
        return _ReviewSummaryWidgets(
            section=section,
            title_label=title_label,
            body=body,
            body_layout=body_layout,
            rows=[],
            edit_button=edit_button,
            fixation_edit_button=fixation_edit_button,
        )

    def _review_checklist_row(self, *, parent: QWidget) -> tuple[QFrame, QLabel]:
        row = QFrame(parent)
        row.setProperty("reviewChecklistRow", "true")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 1, 0, 1)
        row_layout.setSpacing(6)

        label = QLabel(row)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setProperty("reviewChecklistLine", "true")
        row_layout.addWidget(label, 1, Qt.AlignmentFlag.AlignVCenter)
        return row, label

    def _review_checklist_sections(self) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
        project = self._document.project
        conditions = self._document.ordered_conditions()
        session = project.settings.session
        display = project.settings.display
        protocol = project.settings.protocol
        is_ab = project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
        letter_stream = is_letter_stream_project(self._document)
        cadence_summary = (
            f"{protocol.base_hz:g} slots/s · target pair every {protocol.oddball_every_n} "
            f"({protocol.oddball_hz:g} Hz)"
            if is_ab
            else f"{protocol.base_hz:g} Hz base · oddball every {protocol.oddball_every_n} "
            f"({protocol.oddball_hz:g} Hz)"
        )
        if letter_stream:
            cadence_summary = (
                f"{protocol.base_hz:g} Hz · 5 s bursts · one T1/T2 pair per burst"
                if session.randomize_across_blocks else
                f"{protocol.base_hz:g} Hz character stream · "
                f"{protocol.oddball_hz:g} Hz target repetition"
            )
        fixation = project.settings.fixation_task
        refresh_hz = self.runtime_settings_editor.current_refresh_hz()
        default_lead_in = project.settings.presentation.pre_stream_fixation_seconds
        modes = sorted({_timing_template_label(item.duty_cycle_mode) for item in conditions})
        mode_summary = modes[0] if len(modes) == 1 else f"Mixed presentation ({len(modes)} modes)"
        size_summary = presentation_defaults_summary(project.settings.presentation.defaults)
        if letter_stream:
            mode_summary = (
                "Letter distractors and target digits" if session.randomize_across_blocks
                else "Character distractors and targets"
            )
            height = project.settings.presentation.defaults.text_height
            unit = (
                "visual degrees" if height.unit == PresentationUnit.DEGREES
                else "of screen height"
            )
            size_summary = f"Character height: {height.values[0]:g} {unit}"
        pre_count = sum(len(item.pre_task_bindings) for item in conditions)
        post_count = sum(len(item.post_task_bindings) for item in conditions)
        verified = (
            "Verified on this display"
            if self.runtime_settings_editor.refresh_is_verified()
            else "Display verification required"
        )
        response = (
            f"Response: {fixation.response_key.upper()} "
            f"within {fixation.response_window_seconds:g} s"
            if fixation.accuracy_task_enabled
            else "Response scoring: Off"
        )
        tutorial = (
            "Off (accuracy tracking is off)"
            if not fixation.accuracy_task_enabled and fixation.participant_tutorial_enabled
            else "On"
            if fixation.participant_tutorial_enabled
            else "Off"
        )
        return (
            ("project", "Project", (project.meta.name, f"Participant tutorial: {tutorial}")),
            (
                "conditions",
                "Conditions",
                (
                    f"{len(conditions)} conditions · {mode_summary}"
                    if conditions
                    else "No conditions",
                    f"Task flow: {pre_count} pre-condition, {post_count} post-condition bindings",
                    *(
                        ("SOA: " + ", ".join(
                            f"{item.attentional_blink.soa_ms:g} ms" for item in conditions
                            if isinstance(item.attentional_blink, AttentionalBlinkStreamSettings)
                        ),)
                        if letter_stream else ()
                    ),
                ),
            ),
            (
                "experiment",
                "Timing",
                (
                    f"Monitor: {refresh_hz:g} Hz · {verified}",
                    cadence_summary,
                    self._display_background_label(str(display.background_color)),
                ),
            ),
            (
                "image_size",
                "Character Size" if letter_stream else "Image Size",
                (
                    size_summary,
                    f"Viewing distance: {display.viewing_distance_cm:g} cm · "
                    f"{display.screen_width_px} × {display.screen_height_px} px",
                ),
            ),
            (
                "session",
                "Session",
                (
                    (
                        f"{session.block_count} bursts per SOA · "
                        f"{session.block_count * len(conditions)} total · all shuffled together"
                        if session.randomize_across_blocks
                        else f"{session.block_count} repeats per condition · randomized order"
                    ),
                    *self._review_timing_estimate_lines(),
                ),
            ),
            (
                "response",
                "Fixation and Response",
                (
                    (
                        f"Color changes: {'On' if fixation.enabled else 'Off'} · "
                        f"default lead-in {default_lead_in:g} s"
                        if fixation.show_cross else
                        f"Fixation cross: Off · blank lead-in {default_lead_in:g} s"
                    ),
                    f"Accuracy tracking: {'On' if fixation.accuracy_task_enabled else 'Off'}",
                    response,
                ),
            ),
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
            "#808080": "Neutral gray background",
        }.get(background_color, background_color)

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
            return self._condition_setup_blocker()
        if step_key == "review":
            return "Review blockers"
        return self._current_step_blocker() if index == self._active_step_index else "Needs setup"

    def _current_step_valid(self) -> bool:
        return self._step_valid(self._active_step_index)

    def _step_valid(self, index: int) -> bool:
        step_key = _WIZARD_STEPS[index][0]
        if step_key == "project":
            return self._project_details_ready()
        if step_key == "conditions":
            return not self._condition_setup_blocker()
        if step_key == "design":
            return not self._design_setup_blocker()
        if step_key == "experiment":
            return self.runtime_settings_editor.timing_is_compatible()
        if step_key == "image_size" and isinstance(
            self.image_display_size_editor, AttentionalBlinkCharacterSizeEditor,
        ):
            return not self.image_display_size_editor.validation_message()
        if step_key in {"image_size", "fixation"}:
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
            return self._condition_setup_blocker()
        if step_key == "design":
            return self._design_setup_blocker()
        if step_key == "experiment":
            return self.runtime_settings_editor.timing_blocker()
        if step_key == "image_size" and isinstance(
            self.image_display_size_editor, AttentionalBlinkCharacterSizeEditor,
        ):
            return self.image_display_size_editor.validation_message()
        if step_key == "review":
            return self._readiness_report().status_label
        return "Step needs attention"

    def _next_step_hint_text(self) -> str:
        return f"To continue: {self._current_step_blocker()}"

    def _condition_setup_blocker(self) -> str:
        if category_conflict_condition_ids(self._document.project):
            return "Separate oddball conditions into another experiment"
        conditions = self._document.ordered_conditions()
        if not conditions:
            return "Add at least one condition"
        sets = {item.set_id: item for item in self._document.project.stimulus_sets}
        for index, condition in enumerate(conditions, start=1):
            if not is_guided_condition_name(condition.name):
                return f"Enter a descriptive name for condition {index}"
            if not is_guided_trigger_code(condition.trigger_code):
                return f"Set a trigger code above 0 for {condition.name}"
            for role, set_id in (
                ("base", condition.base_stimulus_set_id),
                ("oddball", condition.oddball_stimulus_set_id),
            ):
                stimulus_set = sets.get(set_id)
                if stimulus_set is not None and stimulus_set.modality == StimulusModality.WORD:
                    if not stimulus_set.word_count:
                        return f"Add {role} words to {condition.name}"
        return ""

    def _design_setup_blocker(self) -> str:
        conditions = self._document.ordered_conditions()
        if not conditions:
            return "Add a condition in Conditions"
        if category_conflict_condition_ids(self._document.project):
            return "Separate oddball conditions in Conditions before editing this design"
        if not _conditions_have_assigned_assets(self._document, conditions):
            return "Choose the image sources for every condition in Design"
        return self.design_setup_step.validation_message()

    def _focus_step_blocker(self) -> None:
        if self._current_step_key() == "conditions":
            if category_conflict_condition_ids(self._document.project):
                self.condition_setup_step.separate_conditions_button.setFocus(
                    Qt.FocusReason.OtherFocusReason
                )
            else:
                self.condition_setup_step.focus_setup_blocker()
        elif self._current_step_key() == "project":
            editor = self.project_overview_editor
            target = (
                editor.project_name_edit
                if not self._document.project.meta.name.strip()
                else editor.project_description_edit
            )
            target.setFocus(Qt.FocusReason.OtherFocusReason)

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
            is_guided_trigger_code(condition.trigger_code) for condition in ordered_conditions
        )

    def _refresh_progress_steps(self) -> None:
        current = self._active_step_index
        self.progress_steps.set_navigation_enabled(
            self._step_jump_enabled and not self._condition_image_task_active()
        )
        self.progress_steps.set_active_index(current)

    def _step_index_for_key(self, step_key: str) -> int:
        aliases = {
            "session": "experiment",
            "display": "experiment",
            "runtime": "experiment",
            "timing": "experiment",
            "geometry": "image_size",
            "images": "design",
            "stimuli": "design",
            "assets": "design",
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
