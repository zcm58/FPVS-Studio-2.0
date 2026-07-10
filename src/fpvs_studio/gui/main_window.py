"""Primary Phase 5 authoring window for FPVS Studio. It binds user actions to backend
document services for project editing, preprocessing, validation, preflight, and test-
mode launch workflows. The window owns top-level composition and honest runtime
messaging, not protocol semantics, RunSpec compilation rules, or execution flow."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QWidget,
)

from fpvs_studio import __version__
from fpvs_studio.core.models import ConditionTemplateProfile
from fpvs_studio.core.paths import logs_dir
from fpvs_studio.core.project_bundle import (
    PROJECT_BUNDLE_SUFFIX,
    BundleExportStage,
    BundleImportStage,
    ProjectBundleManifest,
    project_bundle_filename,
)
from fpvs_studio.core.project_bundle import (
    export_project_bundle as write_project_bundle,
)
from fpvs_studio.core.project_config import PROJECT_CONFIG_SUFFIX, project_config_filename
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.gui import folder_actions
from fpvs_studio.gui.animations import ButtonHoverAnimator
from fpvs_studio.gui.bundle_export_dialog import BundleExportOptionsDialog
from fpvs_studio.gui.components import apply_studio_theme
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.document_support import DocumentError, format_validation_report
from fpvs_studio.gui.home_page import HomePage
from fpvs_studio.gui.image_resizer_page import ImageResizerPage
from fpvs_studio.gui.processing_page import (
    BundleExportProcessingPage,
    BundleExportResultPage,
    BundleImportProcessingPage,
)
from fpvs_studio.gui.run_page import (
    BioSemiRecordingConfirmationDialog,
    LaunchTaskResult,
    ParticipantLaunchDetails,
    ParticipantNumberDialog,
)
from fpvs_studio.gui.setup_wizard_page import SetupWizardPage
from fpvs_studio.gui.update_dialog import UpdateDialog
from fpvs_studio.gui.window_helpers import (
    _LAUNCH_INTERSTITIAL_DURATION_MS,
    _show_error_dialog,
)
from fpvs_studio.gui.workers import BackgroundTask, ProgressTask
from fpvs_studio.runtime.session_export import GROUP_SUMMARY_XLSX_FILENAME

__all__ = [
    "ParticipantNumberDialog",
    "QFileDialog",
    "QMessageBox",
    "QProgressDialog",
    "StudioMainWindow",
    "_LAUNCH_INTERSTITIAL_DURATION_MS",
    "_show_error_dialog",
]

_COMPACT_HOME_MINIMUM_SIZE = (760, 520)
_COMPACT_HOME_DEFAULT_SIZE = (1120, 720)
_COMPACT_SETUP_MINIMUM_SIZE = (960, 640)
_COMPACT_SETUP_DEFAULT_SIZE = (1120, 720)
_WORKSPACE_MINIMUM_SIZE = (1366, 820)
_WORKSPACE_DEFAULT_SIZE = (1440, 920)
_UTILITY_MINIMUM_SIZE = (960, 640)
_UTILITY_DEFAULT_SIZE = (1120, 720)
_AUTO_WORKSPACE_SIZE_TOLERANCE = 16
_TUTORIALS_URL = "https://zcm58.github.io/FPVS-Studio-2.0/"

LOGGER = logging.getLogger(__name__)


class _BundleExportProgressBridge(QObject):
    """Carry worker-thread bundle export progress back to the GUI thread."""

    stage_changed = Signal(str)


@dataclass(frozen=True)
class _BundleExportTaskResult:
    path: Path
    manifest: ProjectBundleManifest


def _ensure_config_suffix(path: Path) -> Path:
    """Return a path with a `.fpvsconfig` suffix when no explicit suffix was selected."""

    return path if path.suffix else path.with_suffix(PROJECT_CONFIG_SUFFIX)


def _ensure_bundle_suffix(path: Path) -> Path:
    """Return a path with a `.fpvsbundle` suffix when no explicit suffix was selected."""

    return path if path.suffix else path.with_suffix(PROJECT_BUNDLE_SUFFIX)


def _ensure_xlsx_suffix(path: Path) -> Path:
    """Return a path with an `.xlsx` suffix for Excel workbook exports."""

    return path if path.suffix.lower() == ".xlsx" else path.with_suffix(".xlsx")


class StudioMainWindow(QMainWindow):
    """Main window hosting the Phase 5 authoring tabs."""

    def __init__(
        self,
        *,
        document: ProjectDocument,
        on_request_new_project: Callable[[], None],
        on_request_open_project: Callable[[], None],
        on_request_manage_projects: Callable[[], None],
        on_request_import_project_config: Callable[[], None],
        on_request_import_project_bundle: Callable[[], None],
        on_request_settings: Callable[[], None],
        on_load_condition_template_profiles: Callable[[], list[ConditionTemplateProfile]],
        on_manage_condition_templates: Callable[[], list[ConditionTemplateProfile]],
    ) -> None:
        super().__init__()
        self.setObjectName("studio_main_window")
        self.document = document
        self._on_request_new_project = on_request_new_project
        self._on_request_open_project = on_request_open_project
        self._on_request_manage_projects = on_request_manage_projects
        self._on_request_import_project_config = on_request_import_project_config
        self._on_request_import_project_bundle = on_request_import_project_bundle
        self._on_request_settings = on_request_settings
        self.setWindowTitle("FPVS Studio Beta")
        self._auto_workspace_sized = False
        self._auto_workspace_return_size: tuple[int, int] | None = None
        self._auto_workspace_size: tuple[int, int] | None = None
        self._active_bundle_export_task: BackgroundTask | None = None
        self._bundle_export_previous_widget: QWidget | None = None
        self._bundle_export_target_path: Path | None = None
        self._bundle_export_progress_bridge: _BundleExportProgressBridge | None = None
        self._bundle_export_completed_result: _BundleExportTaskResult | None = None
        self._bundle_import_previous_widget: QWidget | None = None
        self._bundle_import_processing_active = False
        self._setup_wizard_page: SetupWizardPage | None = None
        self._image_resizer_page: ImageResizerPage | None = None
        self._bundle_export_processing_page: BundleExportProcessingPage | None = None
        self._bundle_export_result_page: BundleExportResultPage | None = None
        self._bundle_import_processing_page: BundleImportProcessingPage | None = None
        self._on_load_condition_template_profiles = on_load_condition_template_profiles
        self._on_manage_condition_templates = on_manage_condition_templates
        self._deferred_open_tasks_started = False
        self._session_seed_ready = False
        self._session_seed_task: BackgroundTask | None = None
        self._launch_after_session_seed_ready = False
        self._active_launch_task: ProgressTask | None = None
        self._active_launch_session_plan: SessionPlan | None = None
        self._active_launch_participant_number: str | None = None
        self._apply_compact_window_size()

        self._runtime_fullscreen_ui_state = True
        self.home_page = HomePage(
            document,
            load_condition_template_profiles=on_load_condition_template_profiles,
            parent=self,
        )

        self.main_stack = QStackedWidget(self)
        self.main_stack.setObjectName("main_stack")
        self.main_stack.addWidget(self.home_page)
        self.main_tabs = self.main_stack
        self.setCentralWidget(self.main_stack)
        self._apply_chrome_styles()

        self.setStatusBar(QStatusBar(self))
        self._create_actions()
        self.home_page.bind_quick_actions(
            new_project_action=self.new_project_action,
            import_project_bundle_action=self.import_project_bundle_action,
            open_project_action=self.open_project_action,
            launch_action=self.launch_action,
        )
        self.home_page.bind_navigation_actions(
            edit_setup=lambda: self.show_setup_wizard(allow_step_jumps=True),
            complete_setup=self.show_incomplete_setup_wizard,
        )
        self._create_menu_and_toolbar()
        self._button_hover_animators: list[ButtonHoverAnimator] = []
        self._install_button_hover_animations()
        self._wire_document()
        self._update_window_title()
        self._show_initial_workflow_surface()

    def _wire_document(self) -> None:
        self.document.project_changed.connect(self._update_window_title)
        self.document.project_changed.connect(self._sync_home_after_document_update)
        self.document.session_plan_changed.connect(self._sync_home_after_document_update)
        self.document.dirty_changed.connect(self._update_window_title)
        self.document.saved.connect(lambda: self.statusBar().showMessage("Project saved.", 3000))

    @property
    def setup_wizard_page(self) -> SetupWizardPage:
        if self._setup_wizard_page is None:
            page = SetupWizardPage(
                self.document,
                load_condition_template_profiles=self._on_load_condition_template_profiles,
                manage_condition_templates=self._on_manage_condition_templates,
                fullscreen_state_getter=self._runtime_fullscreen_state,
                fullscreen_state_setter=self._set_runtime_fullscreen_state,
                on_return_home=self.show_home,
                on_save_project=self.save_project,
                parent=self,
            )
            self._setup_wizard_page = page
            self.main_stack.addWidget(page)
            self._install_button_hover_animations()
        return self._setup_wizard_page

    @property
    def setup_dashboard_page(self) -> SetupWizardPage:
        return self.setup_wizard_page

    @property
    def conditions_page(self) -> QWidget:
        return self.setup_wizard_page.conditions_page

    @property
    def assets_page(self) -> QWidget:
        return self.setup_wizard_page.assets_page

    @property
    def run_page(self) -> QWidget:
        return self.setup_wizard_page.run_page

    @property
    def session_structure_page(self) -> QWidget:
        return self.setup_wizard_page.session_structure_page

    @property
    def fixation_cross_settings_page(self) -> QWidget:
        return self.setup_wizard_page.fixation_cross_settings_page

    @property
    def image_resizer_page(self) -> ImageResizerPage:
        if self._image_resizer_page is None:
            page = ImageResizerPage(on_return_home=self.show_home, parent=self)
            self._image_resizer_page = page
            self.main_stack.addWidget(page)
            self._install_button_hover_animations()
        return self._image_resizer_page

    @property
    def bundle_export_processing_page(self) -> BundleExportProcessingPage:
        if self._bundle_export_processing_page is None:
            page = BundleExportProcessingPage(parent=self)
            self._bundle_export_processing_page = page
            self.main_stack.addWidget(page)
        return self._bundle_export_processing_page

    @property
    def bundle_export_result_page(self) -> BundleExportResultPage:
        if self._bundle_export_result_page is None:
            page = BundleExportResultPage(parent=self)
            page.done_requested.connect(self._restore_after_bundle_export)
            page.copy_path_requested.connect(self._copy_bundle_export_path)
            page.open_folder_requested.connect(self._open_bundle_export_folder)
            self._bundle_export_result_page = page
            self.main_stack.addWidget(page)
            self._install_button_hover_animations()
        return self._bundle_export_result_page

    @property
    def bundle_import_processing_page(self) -> BundleImportProcessingPage:
        if self._bundle_import_processing_page is None:
            page = BundleImportProcessingPage(parent=self)
            self._bundle_import_processing_page = page
            self.main_stack.addWidget(page)
        return self._bundle_import_processing_page

    def _runtime_fullscreen_state(self) -> bool:
        return self._runtime_fullscreen_ui_state

    def _set_runtime_fullscreen_state(self, checked: bool) -> None:
        checked_bool = bool(checked)
        if self._runtime_fullscreen_ui_state == checked_bool:
            return
        self._runtime_fullscreen_ui_state = checked_bool
        if self._setup_wizard_page is not None:
            self._setup_wizard_page.run_page.sync_fullscreen_checkbox(checked_bool)
            self._setup_wizard_page.sync_fullscreen_checkbox(checked_bool)
        self.home_page.refresh()

    def show_home(self) -> None:
        self.flush_pending_edits()
        self.home_page.refresh()
        self._set_home_chrome_visible(True, status_visible=False)
        self._apply_compact_window_size()
        self._sync_home_chrome_offset()
        self.main_stack.setCurrentWidget(self.home_page)

    def show_setup_wizard(
        self,
        *,
        step_key: str | None = None,
        allow_step_jumps: bool = False,
    ) -> None:
        setup_wizard_page = self.setup_wizard_page
        self._set_home_chrome_visible(True)
        self._apply_setup_window_size()
        self.main_stack.setCurrentWidget(setup_wizard_page)
        setup_wizard_page.open_wizard(
            step_key=step_key,
            allow_step_jumps=allow_step_jumps,
        )

    def show_incomplete_setup_wizard(self) -> None:
        setup_wizard_page = self.setup_wizard_page
        self.show_setup_wizard(
            step_key=setup_wizard_page.first_incomplete_step_key(),
            allow_step_jumps=False,
        )

    def show_image_resizer(self) -> None:
        self.flush_pending_edits()
        self._set_home_chrome_visible(True)
        self._apply_utility_window_size()
        self.main_stack.setCurrentWidget(self.image_resizer_page)

    def _show_initial_workflow_surface(self) -> None:
        self.show_home()

    def flush_pending_edits(self) -> None:
        if self._setup_wizard_page is not None:
            self._setup_wizard_page.flush_pending_edits()

    def _set_home_chrome_visible(
        self,
        visible: bool,
        *,
        status_visible: bool | None = None,
    ) -> None:
        self.menuBar().setVisible(visible)
        if self.statusBar() is not None:
            self.statusBar().setVisible(visible if status_visible is None else status_visible)

    def _sync_home_chrome_offset(self) -> None:
        menu_height = self.menuBar().height() or self.menuBar().sizeHint().height()
        self.home_page.set_top_chrome_offset(menu_height if self.menuBar().isVisible() else 0)

    def _sync_home_after_document_update(self) -> None:
        if self.main_stack.currentWidget() is self.home_page:
            self._sync_home_chrome_offset()

    def _apply_compact_window_size(self) -> None:
        was_below_compact_minimum = (
            self.width() < _COMPACT_HOME_MINIMUM_SIZE[0]
            or self.height() < _COMPACT_HOME_MINIMUM_SIZE[1]
        )
        self.setMinimumSize(*_COMPACT_HOME_MINIMUM_SIZE)
        if self._auto_workspace_sized and self._auto_workspace_return_size is not None:
            if self._window_still_at_auto_workspace_size():
                self.resize(*self._auto_workspace_return_size)
            self._clear_auto_workspace_size()
        elif was_below_compact_minimum:
            self.resize(*_COMPACT_HOME_DEFAULT_SIZE)

    def _apply_workspace_window_size(self) -> None:
        needs_workspace_resize = (
            self.width() < _WORKSPACE_MINIMUM_SIZE[0]
            or self.height() < _WORKSPACE_MINIMUM_SIZE[1]
        )
        compact_return_size = (self.width(), self.height())
        self.setMinimumSize(*_WORKSPACE_MINIMUM_SIZE)
        if needs_workspace_resize:
            self.resize(*_WORKSPACE_DEFAULT_SIZE)
            self._auto_workspace_sized = True
            self._auto_workspace_return_size = compact_return_size
            self._auto_workspace_size = (self.width(), self.height())
        else:
            self._clear_auto_workspace_size()

    def _apply_utility_window_size(self) -> None:
        needs_utility_resize = (
            self.width() < _UTILITY_MINIMUM_SIZE[0]
            or self.height() < _UTILITY_MINIMUM_SIZE[1]
        )
        compact_return_size = (self.width(), self.height())
        self.setMinimumSize(*_UTILITY_MINIMUM_SIZE)
        if needs_utility_resize:
            self.resize(*_UTILITY_DEFAULT_SIZE)
            self._auto_workspace_sized = True
            self._auto_workspace_return_size = compact_return_size
            self._auto_workspace_size = (self.width(), self.height())
        else:
            self._clear_auto_workspace_size()

    def _apply_setup_window_size(self) -> None:
        needs_setup_resize = (
            self.width() < _COMPACT_SETUP_MINIMUM_SIZE[0]
            or self.height() < _COMPACT_SETUP_MINIMUM_SIZE[1]
        )
        compact_return_size = (self.width(), self.height())
        self.setMinimumSize(*_COMPACT_SETUP_MINIMUM_SIZE)
        if needs_setup_resize:
            self.resize(*_COMPACT_SETUP_DEFAULT_SIZE)
            self._auto_workspace_sized = True
            self._auto_workspace_return_size = compact_return_size
            self._auto_workspace_size = (self.width(), self.height())
        else:
            self._clear_auto_workspace_size()

    def _window_still_at_auto_workspace_size(self) -> bool:
        if self._auto_workspace_size is None:
            return True
        auto_width, auto_height = self._auto_workspace_size
        return (
            self.width() <= auto_width + _AUTO_WORKSPACE_SIZE_TOLERANCE
            and self.height() <= auto_height + _AUTO_WORKSPACE_SIZE_TOLERANCE
        )

    def _clear_auto_workspace_size(self) -> None:
        self._auto_workspace_sized = False
        self._auto_workspace_return_size = None
        self._auto_workspace_size = None

    def _apply_chrome_styles(self) -> None:
        apply_studio_theme(self)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            if getattr(self, "_theme_refreshing", False):
                return
            self._theme_refreshing = True
            try:
                self._apply_chrome_styles()
            finally:
                self._theme_refreshing = False

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if self.main_stack.currentWidget() is self.home_page:
            self._sync_home_chrome_offset()
            QTimer.singleShot(0, self._sync_home_chrome_offset)
        QTimer.singleShot(0, self.start_deferred_open_tasks)

    def start_deferred_open_tasks(self) -> None:
        """Start non-critical project-open work after the Home surface has painted."""

        if self._deferred_open_tasks_started:
            return
        self._deferred_open_tasks_started = True
        self._start_deferred_session_seed_task()

    def _start_deferred_session_seed_task(self) -> None:
        if self._session_seed_ready or self._session_seed_task is not None:
            return
        task = BackgroundTask(
            parent_widget=self,
            callback=self.document.generate_session_seed_for_app_launch,
        )
        self._session_seed_task = task
        task.succeeded.connect(self._on_deferred_session_seed_generated)
        task.failed.connect(self._on_deferred_session_seed_failed)
        task.finished.connect(self._on_deferred_session_seed_finished)
        task.start()

    @Slot(object)
    def _on_deferred_session_seed_generated(self, result: object) -> None:
        if not isinstance(result, int):
            LOGGER.warning(
                "Deferred session seed generation returned unexpected result type: %s",
                type(result).__name__,
            )
            return
        self.document.apply_session_seed_for_app_launch(result)
        self._session_seed_ready = True

    @Slot(object)
    def _on_deferred_session_seed_failed(self, error: object) -> None:
        LOGGER.warning("Deferred session seed generation failed: %s", error)

    @Slot()
    def _on_deferred_session_seed_finished(self) -> None:
        self._session_seed_task = None
        if self._launch_after_session_seed_ready:
            self._launch_after_session_seed_ready = False
            QTimer.singleShot(0, self.launch_test_session)

    def _install_button_hover_animations(self) -> None:
        self._button_hover_animators.clear()
        for button in self.findChildren(QPushButton):
            if button.property("hoverAnimationEnabled") is True:
                continue
            self._button_hover_animators.append(ButtonHoverAnimator(button, parent=self))

    def _create_actions(self) -> None:
        self.new_project_action = QAction("Create New Project", self)
        self.new_project_action.triggered.connect(self._request_new_project)
        self.open_project_action = QAction("Open Project...", self)
        self.open_project_action.triggered.connect(self._request_open_project)
        self.manage_projects_action = QAction("Manage Projects...", self)
        self.manage_projects_action.setObjectName("manage_projects_action")
        self.manage_projects_action.triggered.connect(self._request_manage_projects)
        self.import_project_config_action = QAction("Project Config...", self)
        self.import_project_config_action.setObjectName("import_project_config_action")
        self.import_project_config_action.triggered.connect(self._request_import_project_config)
        self.import_project_bundle_action = QAction("Project Bundle...", self)
        self.import_project_bundle_action.setObjectName("import_project_bundle_action")
        self.import_project_bundle_action.triggered.connect(self._request_import_project_bundle)
        self.export_project_config_action = QAction("FPVS Toolbox Config...", self)
        self.export_project_config_action.setObjectName("export_project_config_action")
        self.export_project_config_action.triggered.connect(self.export_project_config)
        self.export_project_bundle_action = QAction("Project Bundle...", self)
        self.export_project_bundle_action.setObjectName("export_project_bundle_action")
        self.export_project_bundle_action.triggered.connect(self.export_project_bundle)
        self.export_completed_project_config_action = QAction(
            "Completed Project Config...",
            self,
        )
        self.export_completed_project_config_action.setObjectName(
            "export_completed_project_config_action"
        )
        self.export_completed_project_config_action.triggered.connect(
            self.export_completed_project_config
        )
        self.export_group_summary_action = QAction("Group Summary...", self)
        self.export_group_summary_action.setObjectName("export_group_summary_action")
        self.export_group_summary_action.triggered.connect(self.export_group_summary)
        self.save_project_action = QAction("Save", self)
        self.save_project_action.triggered.connect(self.save_project)
        self.settings_action = QAction("Settings...", self)
        self.settings_action.setObjectName("settings_action")
        self.settings_action.triggered.connect(self._request_settings)
        self.check_updates_action = QAction("Check for Updates", self)
        self.check_updates_action.setObjectName("check_updates_action")
        self.check_updates_action.triggered.connect(self.show_update_dialog)
        self.tutorials_action = QAction("Tutorials", self)
        self.tutorials_action.setObjectName("tutorials_action")
        self.tutorials_action.triggered.connect(self.open_tutorials)
        self.about_action = QAction("About", self)
        self.about_action.setObjectName("about_action")
        self.about_action.triggered.connect(self.show_about_dialog)
        self.launch_action = QAction("Launch Experiment", self)
        launch_help = (
            "Launch Experiment on the current beta test-mode runtime path. "
            "Participant details are collected before launch checks run."
        )
        self.launch_action.setToolTip(launch_help)
        self.launch_action.setStatusTip(launch_help)
        self.launch_action.triggered.connect(self.launch_test_session)
        self.image_resizer_action = QAction("Image Resizer", self)
        self.image_resizer_action.setObjectName("image_resizer_action")
        self.image_resizer_action.triggered.connect(self.show_image_resizer)

    def _create_menu_and_toolbar(self) -> None:
        self.file_menu = self.menuBar().addMenu("File")
        self.tools_menu = self.menuBar().addMenu("Tools")
        self.menuBar().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.file_menu.addAction(self.manage_projects_action)
        self.file_menu.addSeparator()
        self.import_menu = QMenu("Import", self.file_menu)
        self.import_menu.setObjectName("file_import_menu")
        self.import_menu.addAction(self.import_project_bundle_action)
        self.import_menu.addAction(self.import_project_config_action)
        self.file_menu.addMenu(self.import_menu)
        self.export_menu = QMenu("Export", self.file_menu)
        self.export_menu.setObjectName("file_export_menu")
        self.export_menu.addAction(self.export_project_bundle_action)
        self.export_menu.addAction(self.export_project_config_action)
        self.export_menu.addAction(self.export_completed_project_config_action)
        self.export_menu.addAction(self.export_group_summary_action)
        self.file_menu.addMenu(self.export_menu)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.settings_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.check_updates_action)
        self.file_menu.addAction(self.tutorials_action)
        self.file_menu.addAction(self.about_action)
        self.tools_menu.addAction(self.image_resizer_action)

    def show_update_dialog(self) -> None:
        dialog = UpdateDialog(parent=self, on_before_install=self.maybe_save_changes)
        dialog.exec()

    def open_tutorials(self) -> None:
        QDesktopServices.openUrl(QUrl(_TUTORIALS_URL))

    def show_about_dialog(self) -> None:
        QMessageBox.information(
            self,
            "About FPVS Studio",
            (
                f"FPVS Studio version {__version__} was developed by Zack Murphy, "
                "Neural Engineering Research Division, Mississippi State University"
            ),
        )

    def save_project(self) -> bool:
        self.flush_pending_edits()
        try:
            self.document.save()
        except Exception as error:
            _show_error_dialog(self, "Save Error", error)
            return False
        return True

    def launch_test_session(self) -> None:
        if self._active_launch_task is not None:
            return
        if not self._ensure_session_seed_ready_for_launch():
            return
        self.flush_pending_edits()
        try:
            refresh_hz = self._home_launch_refresh_hz()
            validation = self.document.validation_report(refresh_hz=refresh_hz)
            if not validation.is_valid:
                raise DocumentError(format_validation_report(validation))
        except Exception as error:
            _show_error_dialog(self, "Launch Blocked", error)
            return

        participant_details = self._collect_launch_participant_details()
        if participant_details is None:
            return
        participant_number = participant_details.participant_number
        try:
            session_plan = self.document.compile_session(refresh_hz=refresh_hz)
        except Exception as error:
            _show_error_dialog(self, "Launch Blocked", error)
            return
        if (
            self.document.require_biosemi_recording_confirmation
            and not self._confirm_biosemi_recording_started()
        ):
            return

        def _launch() -> LaunchTaskResult:
            self.document.preflight_compiled_session(session_plan)
            summary = self.document.launch_compiled_session(
                session_plan,
                participant_number=participant_number,
                participant_metadata=participant_details.participant_metadata,
                display_index=None,
                fullscreen=True,
            )
            return LaunchTaskResult(session_plan=session_plan, summary=summary)

        self._active_launch_session_plan = session_plan
        self._active_launch_participant_number = participant_number
        task = ProgressTask(
            parent_widget=self,
            label="Launching experiment: Please wait",
            callback=_launch,
            window_title="FPVS Studio",
            persistent_thread=True,
        )
        self._active_launch_task = task
        self.launch_action.setEnabled(False)
        task.succeeded.connect(self._on_home_launch_succeeded)
        task.failed.connect(self._on_home_launch_failed)
        task.finished.connect(self._on_home_launch_finished)
        task.start()

    def _home_launch_refresh_hz(self) -> float:
        preferred_refresh = self.document.project.settings.display.preferred_refresh_hz
        return float(preferred_refresh if preferred_refresh is not None else 60.0)

    def _prompt_participant_number(self) -> ParticipantLaunchDetails | None:
        dialog = ParticipantNumberDialog(self)
        if dialog.exec() != int(dialog.DialogCode.Accepted):
            return None
        return dialog.participant_details

    def _confirm_biosemi_recording_started(self) -> bool:
        dialog = BioSemiRecordingConfirmationDialog(self)
        return dialog.exec() == int(dialog.DialogCode.Accepted)

    def _collect_launch_participant_details(self) -> ParticipantLaunchDetails | None:
        while True:
            participant_details = self._prompt_participant_number()
            if participant_details is None:
                return None
            participant_number = participant_details.participant_number

            if not self.document.has_completed_session_for_participant(participant_number):
                return participant_details

            warning_text = (
                f"Warning: logs indicate that {participant_number} has already "
                "completed this study, "
                f"but you entered {participant_number}. Do you wish to overwrite the existing data?"
            )
            answer = QMessageBox.question(
                self,
                "Participant Already Completed",
                warning_text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                return participant_details

    def _ensure_session_seed_ready_for_launch(self) -> bool:
        if self._session_seed_ready:
            return True
        if self._session_seed_task is not None:
            self._launch_after_session_seed_ready = True
            self.statusBar().showMessage("Preparing random order seed for launch...", 3000)
            return False
        try:
            self.document.randomize_session_seed_for_app_launch()
        except Exception as error:
            _show_error_dialog(self, "Launch Blocked", error)
            return False
        self._session_seed_ready = True
        return True

    @Slot(object)
    def _on_home_launch_succeeded(self, result: object) -> None:
        if not isinstance(result, LaunchTaskResult):
            _show_error_dialog(
                self,
                "Launch Error",
                RuntimeError("Runtime launch returned an unexpected result."),
            )
            return
        participant_number = self._active_launch_participant_number
        if participant_number is None:
            return
        self._show_home_launch_summary(participant_number, result)

    @Slot(object)
    def _on_home_launch_failed(self, error: object) -> None:
        exception = error if isinstance(error, Exception) else RuntimeError(str(error))
        _show_error_dialog(self, "Launch Error", exception)

    @Slot()
    def _on_home_launch_finished(self) -> None:
        self._active_launch_task = None
        self._active_launch_session_plan = None
        self._active_launch_participant_number = None
        self.launch_action.setEnabled(True)
        self.home_page.refresh()

    def _show_home_launch_summary(
        self,
        participant_number: str,
        result: LaunchTaskResult,
    ) -> None:
        summary = result.summary
        output_line = (
            f"Output Dir: {summary.output_dir}"
            if summary.output_dir
            else "Output: Compact summary logs"
        )
        participant_value = summary.participant_number or participant_number
        if summary.aborted:
            abort_reason = summary.abort_reason or "No abort reason was provided."
            QMessageBox.warning(
                self,
                "Launch Aborted",
                "The experiment aborted on the current beta test-mode path.\n\n"
                f"Reason: {abort_reason}\n"
                "Completed Conditions: "
                f"{summary.completed_condition_count}/{summary.total_condition_count}\n"
                f"{output_line}\n\n"
                + (
                    "Review run exports in the project runs folder."
                    if summary.output_dir
                    else "Review participant summary files in the project logs folder."
                ),
            )
            self.statusBar().showMessage(
                f"Runtime launch aborted for participant {participant_value}.",
                5000,
            )
            return
        QMessageBox.information(
            self,
            "Launch Complete",
            (
                "The experiment finished on the current beta test-mode path. "
                "Review run exports in the project runs folder."
            )
            if summary.output_dir
            else (
                "The experiment finished on the current beta test-mode path. "
                "Review participant summary files in the project logs folder."
            ),
        )
        self.statusBar().showMessage(
            f"Runtime launch completed for participant {participant_value}.",
            5000,
        )

    def export_project_config(self) -> bool:
        return self._export_config(include_completed=False)

    def export_completed_project_config(self) -> bool:
        return self._export_config(include_completed=True)

    def export_project_bundle(self, *, bundle_project_name: str | None = None) -> bool:
        if self._active_bundle_export_task is not None:
            self.statusBar().showMessage("Project bundle export is already running.", 3000)
            return False
        self.flush_pending_edits()
        if bundle_project_name is None:
            options_dialog = BundleExportOptionsDialog(
                current_project_name=self.document.project.meta.name,
                parent=self,
            )
            if options_dialog.exec() != int(options_dialog.DialogCode.Accepted):
                return False
            bundle_project_name = options_dialog.export_project_name
        default_name = project_bundle_filename(bundle_project_name)
        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export FPVS Project Bundle",
            str(self.document.project_root / default_name),
            "FPVS Project Bundles (*.fpvsbundle);;All Files (*)",
        )
        if not selected_path:
            return False
        path = _ensure_bundle_suffix(Path(selected_path))
        try:
            self.document.save()
        except Exception as error:
            _show_error_dialog(self, "Export Project Bundle Error", error)
            return False
        self._start_bundle_export(path, project_name=bundle_project_name)
        return True

    def _start_bundle_export(self, path: Path, *, project_name: str) -> None:
        project_root = self.document.project_root
        progress_bridge = _BundleExportProgressBridge(self)
        progress_bridge.stage_changed.connect(self._on_bundle_export_stage_changed)
        self._bundle_export_progress_bridge = progress_bridge

        def _write_bundle() -> _BundleExportTaskResult:
            manifest = write_project_bundle(
                project_root,
                path,
                project_name=project_name,
                progress_callback=progress_bridge.stage_changed.emit,
            )
            return _BundleExportTaskResult(path=path, manifest=manifest)

        self._bundle_export_previous_widget = self.main_stack.currentWidget()
        self._bundle_export_target_path = path
        self._bundle_export_completed_result = None
        self.bundle_export_processing_page.reset_steps()
        self.bundle_export_processing_page.set_transfer_context(
            title=f"Exporting {project_name}",
            source_label="Project folder",
            source_path=project_root,
            destination_label="Bundle file",
            destination_path=path,
        )
        self.bundle_export_processing_page.set_stage("validate")
        self.bundle_export_processing_page.start()
        self._set_home_chrome_visible(True, status_visible=True)
        self.main_stack.setCurrentWidget(self.bundle_export_processing_page)
        self.statusBar().showMessage("Exporting project bundle...")
        self._set_bundle_processing_busy(True)

        task = BackgroundTask(
            parent_widget=self,
            callback=_write_bundle,
        )
        self._active_bundle_export_task = task
        task.succeeded.connect(self._on_bundle_export_succeeded)
        task.failed.connect(self._on_bundle_export_failed)
        task.finished.connect(self._on_bundle_export_finished)
        task.start()

    def start_bundle_import_processing(
        self,
        *,
        project_name: str,
        bundle_path: Path,
        root_dir: Path,
    ) -> None:
        self._bundle_import_previous_widget = self.main_stack.currentWidget()
        self._bundle_import_processing_active = True
        self.bundle_import_processing_page.reset_steps()
        self.bundle_import_processing_page.set_transfer_context(
            title=f"Importing {project_name}",
            source_label="Source",
            source_path=bundle_path,
            destination_label="Destination root",
            destination_path=root_dir,
        )
        self.bundle_import_processing_page.set_stage("verify")
        self.bundle_import_processing_page.start()
        self._set_home_chrome_visible(True, status_visible=True)
        self.main_stack.setCurrentWidget(self.bundle_import_processing_page)
        self.statusBar().showMessage("Importing FPVS Studio project bundle...")
        self._set_bundle_processing_busy(True)

    def set_bundle_import_stage(self, stage: BundleImportStage) -> None:
        self.bundle_import_processing_page.set_stage(stage)

    def finish_bundle_import_processing(self, *, restore_previous: bool) -> None:
        self.bundle_import_processing_page.stop()
        self._bundle_import_processing_active = False
        self._set_bundle_processing_busy(False)
        if restore_previous:
            self._restore_after_bundle_import()
        else:
            self._bundle_import_previous_widget = None

    def _set_bundle_processing_busy(self, busy: bool) -> None:
        actions = (
            self.new_project_action,
            self.open_project_action,
            self.manage_projects_action,
            self.import_project_bundle_action,
            self.import_project_config_action,
            self.export_project_bundle_action,
            self.export_project_config_action,
            self.export_completed_project_config_action,
            self.export_group_summary_action,
            self.save_project_action,
            self.settings_action,
            self.image_resizer_action,
            self.launch_action,
        )
        for action in actions:
            action.setEnabled(not busy)

    @Slot(object)
    def _on_bundle_export_succeeded(self, result: object) -> None:
        if not isinstance(result, _BundleExportTaskResult):
            _show_error_dialog(
                self,
                "Export Project Bundle Error",
                RuntimeError("FPVS Studio received an unexpected bundle export result."),
            )
            return
        self._bundle_export_completed_result = result
        self.statusBar().showMessage(f"Project bundle exported: {result.path}")

    @Slot(object)
    def _on_bundle_export_failed(self, error: object) -> None:
        exception = error if isinstance(error, Exception) else RuntimeError(str(error))
        _show_error_dialog(self, "Export Project Bundle Error", exception)

    @Slot(str)
    def _on_bundle_export_stage_changed(self, stage: str) -> None:
        if stage not in {"validate", "stimuli", "write", "complete"}:
            return
        self.bundle_export_processing_page.set_stage(cast(BundleExportStage, stage))

    @Slot()
    def _on_bundle_export_finished(self) -> None:
        self.bundle_export_processing_page.stop()
        self._active_bundle_export_task = None
        self._bundle_export_target_path = None
        progress_bridge = self._bundle_export_progress_bridge
        if progress_bridge is not None:
            progress_bridge.stage_changed.disconnect(self._on_bundle_export_stage_changed)
            progress_bridge.deleteLater()
        self._bundle_export_progress_bridge = None
        self._set_bundle_processing_busy(False)
        completed_result = self._bundle_export_completed_result
        if completed_result is not None:
            self.bundle_export_result_page.set_result(
                project_name=completed_result.manifest.project.name,
                bundle_path=completed_result.path,
                packaged_file_count=len(completed_result.manifest.files),
            )
            self._set_home_chrome_visible(True, status_visible=True)
            self._apply_compact_window_size()
            self.main_stack.setCurrentWidget(self.bundle_export_result_page)
            return
        self._restore_after_bundle_export()

    @Slot(str)
    def _copy_bundle_export_path(self, path: str) -> None:
        QApplication.clipboard().setText(path)
        self.statusBar().showMessage("Project bundle path copied.", 3000)

    @Slot(object)
    def _open_bundle_export_folder(self, path: object) -> None:
        if isinstance(path, (str, Path)):
            folder_actions.open_folder(Path(path))

    def _restore_after_bundle_export(self) -> None:
        previous_widget = self._bundle_export_previous_widget
        self._bundle_export_previous_widget = None
        self._bundle_export_completed_result = None
        if previous_widget is self.home_page:
            self.home_page.refresh()
            self._set_home_chrome_visible(True, status_visible=False)
            self._apply_compact_window_size()
            self._sync_home_chrome_offset()
            self.main_stack.setCurrentWidget(self.home_page)
            return
        if self._setup_wizard_page is not None and previous_widget is self._setup_wizard_page:
            self._set_home_chrome_visible(True)
            self._apply_setup_window_size()
            self.main_stack.setCurrentWidget(self._setup_wizard_page)
            return
        if self._image_resizer_page is not None and previous_widget is self._image_resizer_page:
            self._set_home_chrome_visible(True)
            self._apply_utility_window_size()
            self.main_stack.setCurrentWidget(self._image_resizer_page)
            return
        self.show_home()

    def _restore_after_bundle_import(self) -> None:
        previous_widget = self._bundle_import_previous_widget
        self._bundle_import_previous_widget = None
        if previous_widget is self.home_page:
            self.home_page.refresh()
            self._set_home_chrome_visible(True, status_visible=False)
            self._apply_compact_window_size()
            self._sync_home_chrome_offset()
            self.main_stack.setCurrentWidget(self.home_page)
            return
        if self._setup_wizard_page is not None and previous_widget is self._setup_wizard_page:
            self._set_home_chrome_visible(True)
            self._apply_setup_window_size()
            self.main_stack.setCurrentWidget(self._setup_wizard_page)
            return
        if self._image_resizer_page is not None and previous_widget is self._image_resizer_page:
            self._set_home_chrome_visible(True)
            self._apply_utility_window_size()
            self.main_stack.setCurrentWidget(self._image_resizer_page)
            return
        self.show_home()

    def export_group_summary(self) -> bool:
        self.flush_pending_edits()
        default_dir = logs_dir(self.document.project_root)
        if not default_dir.exists():
            default_dir = self.document.project_root
        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Group Summary",
            str(default_dir / GROUP_SUMMARY_XLSX_FILENAME),
            "Excel Workbooks (*.xlsx);;All Files (*)",
        )
        if not selected_path:
            return False
        path = _ensure_xlsx_suffix(Path(selected_path))
        try:
            exported_path = self.document.export_group_summary_file(path)
        except Exception as error:
            _show_error_dialog(self, "Export Group Summary Error", error)
            return False
        self.statusBar().showMessage(f"Group summary exported: {exported_path}", 3000)
        return True

    def _export_config(self, *, include_completed: bool) -> bool:
        self.flush_pending_edits()
        default_name = project_config_filename(
            self.document.project.meta.name,
            completed=include_completed,
        )
        dialog_title = (
            "Export Completed Project Config"
            if include_completed
            else "Export FPVS Toolbox Config"
        )
        error_title = (
            "Export Completed Project Config Error"
            if include_completed
            else "Export FPVS Toolbox Config Error"
        )
        status_label = "Completed project config" if include_completed else "FPVS Toolbox config"
        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            dialog_title,
            str(self.document.project_root / default_name),
            (
                "FPVS Config Files (*.fpvsconfig);;"
                "Legacy Config Files (*.config);;"
                "JSON Files (*.json);;"
                "All Files (*)"
            ),
        )
        if not selected_path:
            return False
        path = _ensure_config_suffix(Path(selected_path))
        try:
            self.document.export_config_file(path, include_completed=include_completed)
        except Exception as error:
            _show_error_dialog(self, error_title, error)
            return False
        self.statusBar().showMessage(f"{status_label} exported: {path}", 3000)
        return True

    def maybe_save_changes(self) -> bool:
        self.flush_pending_edits()
        if not self.document.dirty:
            return True
        result = QMessageBox.question(
            self,
            "Unsaved Changes",
            "Save changes to the current project before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if result == QMessageBox.StandardButton.Save:
            return self.save_project()
        if result == QMessageBox.StandardButton.Cancel:
            return False
        return True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._active_launch_task is not None:
            QMessageBox.information(
                self,
                "Launch In Progress",
                (
                    "FPVS Studio is still running the experiment launch. "
                    "Please wait for the launch to finish before closing."
                ),
            )
            event.ignore()
            return
        if self._active_bundle_export_task is not None:
            QMessageBox.information(
                self,
                "Export In Progress",
                (
                    "FPVS Studio is still compiling your project bundle. "
                    "Please wait for the export to finish before closing."
                ),
            )
            event.ignore()
            return
        if self._bundle_import_processing_active:
            QMessageBox.information(
                self,
                "Import In Progress",
                (
                    "FPVS Studio is still setting up the imported project. "
                    "Please wait for the import to finish before closing."
                ),
            )
            event.ignore()
            return
        if self.maybe_save_changes():
            event.accept()
        else:
            event.ignore()

    def _request_new_project(self) -> None:
        if self.maybe_save_changes():
            self._on_request_new_project()

    def _request_open_project(self) -> None:
        if self.maybe_save_changes():
            self._on_request_open_project()

    def _request_manage_projects(self) -> None:
        self._on_request_manage_projects()

    def _request_import_project_config(self) -> None:
        if self.maybe_save_changes():
            self._on_request_import_project_config()

    def _request_import_project_bundle(self) -> None:
        if self.maybe_save_changes():
            self._on_request_import_project_bundle()

    def _request_settings(self) -> None:
        self._on_request_settings()

    def _update_window_title(self, *_args: object) -> None:
        dirty_prefix = "*" if self.document.dirty else ""
        self.setWindowTitle(
            f"{dirty_prefix}{self.document.project.meta.name} - FPVS Studio Beta"
        )
