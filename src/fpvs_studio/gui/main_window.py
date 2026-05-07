"""Primary Phase 5 authoring window for FPVS Studio. It binds user actions to backend
document services for project editing, preprocessing, validation, preflight, and test-
mode launch workflows. The window owns top-level composition and honest runtime
messaging, not protocol semantics, RunSpec compilation rules, or execution flow."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QStyleFactory,
)

from fpvs_studio.core.models import ConditionTemplateProfile
from fpvs_studio.gui.animations import ButtonHoverAnimator
from fpvs_studio.gui.components import apply_studio_theme
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.home_page import HomePage
from fpvs_studio.gui.image_resizer_page import ImageResizerPage
from fpvs_studio.gui.run_page import ParticipantNumberDialog
from fpvs_studio.gui.setup_wizard_page import SetupWizardPage
from fpvs_studio.gui.window_helpers import (
    _LAUNCH_INTERSTITIAL_DURATION_MS,
    _launcher_readiness_report,
    _show_error_dialog,
)

__all__ = [
    "ParticipantNumberDialog",
    "QFileDialog",
    "QMessageBox",
    "QProgressDialog",
    "StudioMainWindow",
    "_LAUNCH_INTERSTITIAL_DURATION_MS",
    "_show_error_dialog",
]


class StudioMainWindow(QMainWindow):
    """Main window hosting the Phase 5 authoring tabs."""

    def __init__(
        self,
        *,
        document: ProjectDocument,
        on_request_new_project: Callable[[], None],
        on_request_open_project: Callable[[], None],
        on_request_manage_projects: Callable[[], None],
        on_request_settings: Callable[[], None],
        on_load_condition_template_profiles: Callable[[], list[ConditionTemplateProfile]],
        on_manage_condition_templates: Callable[[], list[ConditionTemplateProfile]],
    ) -> None:
        super().__init__()
        self.document = document
        self._on_request_new_project = on_request_new_project
        self._on_request_open_project = on_request_open_project
        self._on_request_manage_projects = on_request_manage_projects
        self._on_request_settings = on_request_settings
        self.setWindowTitle("FPVS Studio (Alpha)")
        self.resize(1440, 920)

        self._runtime_fullscreen_ui_state = True
        self.home_page = HomePage(
            document,
            load_condition_template_profiles=on_load_condition_template_profiles,
            parent=self,
        )
        self.setup_wizard_page = SetupWizardPage(
            document,
            load_condition_template_profiles=on_load_condition_template_profiles,
            manage_condition_templates=on_manage_condition_templates,
            fullscreen_state_getter=self._runtime_fullscreen_state,
            fullscreen_state_setter=self._set_runtime_fullscreen_state,
            on_return_home=self.show_home,
            parent=self,
        )
        self.setup_dashboard_page = self.setup_wizard_page
        self.conditions_page = self.setup_wizard_page.conditions_page
        self.assets_page = self.setup_wizard_page.assets_page
        self.run_page = self.setup_wizard_page.run_page
        self.session_structure_page = self.setup_wizard_page.session_structure_page
        self.fixation_cross_settings_page = self.setup_wizard_page.fixation_cross_settings_page

        self.main_stack = QStackedWidget(self)
        self.main_stack.setObjectName("main_stack")
        self.main_stack.addWidget(self.home_page)
        self.main_stack.addWidget(self.setup_wizard_page)
        self.image_resizer_page = ImageResizerPage(on_return_home=self.show_home, parent=self)
        self.main_stack.addWidget(self.image_resizer_page)
        self.main_tabs = self.main_stack
        self.setCentralWidget(self.main_stack)
        self._apply_chrome_styles()

        self.setStatusBar(QStatusBar(self))
        self.alpha_status_label = QLabel("Alpha: test-mode runtime path only", self)
        self.alpha_status_label.setObjectName("alpha_runtime_status_label")
        self.alpha_status_label.setToolTip(
            "Runtime launch currently supports the alpha test-mode path only (test_mode=True)."
        )
        self.statusBar().addPermanentWidget(self.alpha_status_label)
        self._create_actions()
        self.home_page.bind_quick_actions(
            new_project_action=self.new_project_action,
            open_project_action=self.open_project_action,
            save_project_action=self.save_project_action,
            launch_action=self.launch_action,
        )
        self.home_page.bind_navigation_actions(
            edit_setup=self.show_setup_wizard,
        )
        self._create_menu_and_toolbar()
        self._button_hover_animators: list[ButtonHoverAnimator] = []
        self._install_button_hover_animations()
        self._wire_document()
        self._update_window_title()
        self._show_initial_workflow_surface()

    def _wire_document(self) -> None:
        self.document.project_changed.connect(self._update_window_title)
        self.document.dirty_changed.connect(self._update_window_title)
        self.document.saved.connect(lambda: self.statusBar().showMessage("Project saved.", 3000))

    def _runtime_fullscreen_state(self) -> bool:
        return self._runtime_fullscreen_ui_state

    def _set_runtime_fullscreen_state(self, checked: bool) -> None:
        checked_bool = bool(checked)
        if self._runtime_fullscreen_ui_state == checked_bool:
            return
        self._runtime_fullscreen_ui_state = checked_bool
        self.run_page.sync_fullscreen_checkbox(checked_bool)
        self.setup_wizard_page.sync_fullscreen_checkbox(checked_bool)
        self.home_page.refresh()

    def show_home(self) -> None:
        self.flush_pending_edits()
        self.home_page.refresh()
        self.main_stack.setCurrentWidget(self.home_page)

    def show_setup_wizard(self) -> None:
        self.setup_wizard_page.open_wizard()
        self.main_stack.setCurrentWidget(self.setup_wizard_page)

    def show_image_resizer(self) -> None:
        self.flush_pending_edits()
        self.main_stack.setCurrentWidget(self.image_resizer_page)

    def _show_initial_workflow_surface(self) -> None:
        if self._current_project_is_ready_to_launch():
            self.show_home()
        else:
            self.show_setup_wizard()

    def _current_project_is_ready_to_launch(self) -> bool:
        report = _launcher_readiness_report(
            self.document,
            refresh_hz=self.document.project.settings.display.preferred_refresh_hz or 60.0,
        )
        return report.badge_state == "ready"

    def flush_pending_edits(self) -> None:
        self.setup_wizard_page.flush_pending_edits()

    def _apply_chrome_styles(self) -> None:
        apply_studio_theme(self)

    def _install_button_hover_animations(self) -> None:
        self._button_hover_animators.clear()
        for button in self.findChildren(QPushButton):
            self._button_hover_animators.append(ButtonHoverAnimator(button, parent=self))

    def _create_actions(self) -> None:
        self.new_project_action = QAction("Create New Project", self)
        self.new_project_action.triggered.connect(self._request_new_project)
        self.open_project_action = QAction("Open Project...", self)
        self.open_project_action.triggered.connect(self._request_open_project)
        self.manage_projects_action = QAction("Manage Projects...", self)
        self.manage_projects_action.setObjectName("manage_projects_action")
        self.manage_projects_action.triggered.connect(self._request_manage_projects)
        self.save_project_action = QAction("Save", self)
        self.save_project_action.triggered.connect(self.save_project)
        self.settings_action = QAction("Settings...", self)
        self.settings_action.setObjectName("settings_action")
        self.settings_action.triggered.connect(self._request_settings)
        self.launch_action = QAction("Launch Experiment", self)
        launch_help = (
            "Launch Experiment on the current alpha test-mode runtime path. "
            "Launch checks run automatically before participant entry."
        )
        self.launch_action.setToolTip(launch_help)
        self.launch_action.setStatusTip(launch_help)
        self.launch_action.triggered.connect(self.run_page.launch_test_session)
        self.image_resizer_action = QAction("Image Resizer", self)
        self.image_resizer_action.setObjectName("image_resizer_action")
        self.image_resizer_action.triggered.connect(self.show_image_resizer)

    def _create_menu_and_toolbar(self) -> None:
        self.file_menu = self.menuBar().addMenu("File")
        self.tools_menu = self.menuBar().addMenu("Tools")
        self._native_menu_style = QStyleFactory.create("WindowsVista") or QStyleFactory.create(
            "Windows"
        )
        if self._native_menu_style is not None:
            self.menuBar().setStyle(self._native_menu_style)
            self.file_menu.setStyle(self._native_menu_style)
            self.tools_menu.setStyle(self._native_menu_style)
        self.menuBar().setStyleSheet("")
        self.menuBar().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.file_menu.addAction(self.manage_projects_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.settings_action)
        self.tools_menu.addAction(self.image_resizer_action)

    def save_project(self) -> bool:
        self.flush_pending_edits()
        try:
            self.document.save()
        except Exception as error:
            _show_error_dialog(self, "Save Error", error)
            return False
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

    def _request_settings(self) -> None:
        self._on_request_settings()

    def _update_window_title(self, *_args: object) -> None:
        dirty_prefix = "*" if self.document.dirty else ""
        self.setWindowTitle(
            f"{dirty_prefix}{self.document.project.meta.name} - FPVS Studio (Alpha)"
        )
