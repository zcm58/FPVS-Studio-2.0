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
    QStatusBar,
    QStyleFactory,
    QTabWidget,
)

from fpvs_studio.core.models import ConditionTemplateProfile
from fpvs_studio.gui.animations import AnimatedTabBar, ButtonHoverAnimator
from fpvs_studio.gui.assets_pages import AssetsPage
from fpvs_studio.gui.components import apply_studio_theme
from fpvs_studio.gui.condition_pages import ConditionsPage
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.home_page import HomePage, SetupDashboardPage
from fpvs_studio.gui.run_page import ParticipantNumberDialog, RunPage
from fpvs_studio.gui.session_pages import FixationCrossSettingsPage, SessionStructurePage
from fpvs_studio.gui.window_helpers import (
    _LAUNCH_INTERSTITIAL_DURATION_MS,
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
        on_request_settings: Callable[[], None],
        on_load_condition_template_profiles: Callable[[], list[ConditionTemplateProfile]],
        on_manage_condition_templates: Callable[[], list[ConditionTemplateProfile]],
    ) -> None:
        super().__init__()
        self.document = document
        self._on_request_new_project = on_request_new_project
        self._on_request_open_project = on_request_open_project
        self._on_request_settings = on_request_settings
        self.setWindowTitle("FPVS Studio (Alpha)")
        self.resize(1440, 920)

        self.conditions_page = ConditionsPage(document, self)
        self.session_structure_page = SessionStructurePage(document, self)
        self.fixation_cross_settings_page = FixationCrossSettingsPage(document, self)
        self.assets_page = AssetsPage(document, self)
        self._runtime_fullscreen_ui_state = True
        self.run_page = RunPage(
            document,
            fullscreen_state_getter=self._runtime_fullscreen_state,
            fullscreen_state_setter=self._set_runtime_fullscreen_state,
            parent=self,
        )
        self.setup_dashboard_page = SetupDashboardPage(
            document,
            load_condition_template_profiles=on_load_condition_template_profiles,
            manage_condition_templates=on_manage_condition_templates,
            fullscreen_state_getter=self._runtime_fullscreen_state,
            fullscreen_state_setter=self._set_runtime_fullscreen_state,
            parent=self,
        )
        self.home_page = HomePage(
            document,
            load_condition_template_profiles=on_load_condition_template_profiles,
            parent=self,
        )

        self.main_tabs = QTabWidget(self)
        self.main_tabs.setObjectName("main_tabs")
        self.main_tabs.setTabBar(AnimatedTabBar(self.main_tabs))
        self.main_tabs.addTab(self.home_page, "Home")
        self.main_tabs.addTab(self.setup_dashboard_page, "Setup Guide")
        self.main_tabs.addTab(self.conditions_page, "Conditions")
        self.main_tabs.addTab(self.assets_page, "Stimuli Manager")
        self.main_tabs.addTab(self.run_page, "Runtime")
        self.setCentralWidget(self.main_tabs)
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
            edit_setup=lambda: self.main_tabs.setCurrentWidget(self.setup_dashboard_page),
            open_stimuli_manager=lambda: self.main_tabs.setCurrentWidget(self.assets_page),
            open_runtime_settings=lambda: self.main_tabs.setCurrentWidget(self.run_page),
        )
        self.setup_dashboard_page.bind_step_navigation_actions(
            edit_conditions=lambda: self.main_tabs.setCurrentWidget(self.conditions_page),
            open_stimuli_manager=lambda: self.main_tabs.setCurrentWidget(self.assets_page),
            open_runtime_settings=lambda: self.main_tabs.setCurrentWidget(self.run_page),
        )
        self._create_menu_and_toolbar()
        self._button_hover_animators: list[ButtonHoverAnimator] = []
        self._install_button_hover_animations()
        self._wire_document()
        self._update_window_title()

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
        self.setup_dashboard_page.sync_fullscreen_checkbox(checked_bool)
        self.home_page.refresh()

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

    def _create_menu_and_toolbar(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        self._native_menu_style = QStyleFactory.create("WindowsVista") or QStyleFactory.create(
            "Windows"
        )
        if self._native_menu_style is not None:
            self.menuBar().setStyle(self._native_menu_style)
            file_menu.setStyle(self._native_menu_style)
        self.menuBar().setStyleSheet("")
        self.menuBar().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        file_menu.addAction(self.settings_action)

    def save_project(self) -> bool:
        try:
            self.document.save()
        except Exception as error:
            _show_error_dialog(self, "Save Error", error)
            return False
        return True

    def maybe_save_changes(self) -> bool:
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

    def _request_settings(self) -> None:
        self._on_request_settings()

    def _update_window_title(self, *_args: object) -> None:
        dirty_prefix = "*" if self.document.dirty else ""
        self.setWindowTitle(
            f"{dirty_prefix}{self.document.project.meta.name} - FPVS Studio (Alpha)"
        )
