"""Primary Phase 5 authoring window for FPVS Studio. It binds user actions to backend
document services for project editing, preprocessing, validation, preflight, and test-
mode launch workflows. The window owns top-level composition and honest runtime
messaging, not protocol semantics, RunSpec compilation rules, or execution flow."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QShowEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QStatusBar,
)

from fpvs_studio import __version__
from fpvs_studio.core.models import ConditionTemplateProfile
from fpvs_studio.core.paths import logs_dir
from fpvs_studio.core.project_bundle import PROJECT_BUNDLE_SUFFIX, project_bundle_filename
from fpvs_studio.core.project_config import PROJECT_CONFIG_SUFFIX, project_config_filename
from fpvs_studio.gui.animations import ButtonHoverAnimator
from fpvs_studio.gui.components import apply_studio_theme
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.home_page import HomePage
from fpvs_studio.gui.image_resizer_page import ImageResizerPage
from fpvs_studio.gui.run_page import ParticipantNumberDialog
from fpvs_studio.gui.setup_wizard_page import SetupWizardPage
from fpvs_studio.gui.update_dialog import UpdateDialog
from fpvs_studio.gui.window_helpers import (
    _LAUNCH_INTERSTITIAL_DURATION_MS,
    _show_error_dialog,
)
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
        self._apply_compact_window_size()

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
            on_save_project=self.save_project,
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
        self._create_actions()
        self.home_page.bind_quick_actions(
            new_project_action=self.new_project_action,
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
        self._set_home_chrome_visible(True)
        self._apply_setup_window_size()
        self.main_stack.setCurrentWidget(self.setup_wizard_page)
        self.setup_wizard_page.open_wizard(
            step_key=step_key,
            allow_step_jumps=allow_step_jumps,
        )

    def show_incomplete_setup_wizard(self) -> None:
        self.show_setup_wizard(
            step_key=self.setup_wizard_page.first_incomplete_step_key(),
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
        self.setup_wizard_page.flush_pending_edits()

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
        self.import_project_bundle_action = QAction("FPVS Studio Project...", self)
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
        self.launch_action.triggered.connect(self.run_page.launch_test_session)
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

    def export_project_config(self) -> bool:
        return self._export_config(include_completed=False)

    def export_completed_project_config(self) -> bool:
        return self._export_config(include_completed=True)

    def export_project_bundle(self) -> bool:
        self.flush_pending_edits()
        default_name = project_bundle_filename(self.document.project.meta.name)
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
            self.document.export_bundle_file(path)
        except Exception as error:
            _show_error_dialog(self, "Export Project Bundle Error", error)
            return False
        self.statusBar().showMessage(f"Project bundle exported: {path}", 3000)
        return True

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
