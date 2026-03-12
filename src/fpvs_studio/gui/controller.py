"""High-level GUI controller for welcome/create/open flows."""

from __future__ import annotations

import traceback
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget

from fpvs_studio.core.condition_template_profiles import (
    get_condition_template_profile,
    list_condition_template_profiles,
    normalize_condition_template_profile_root,
)
from fpvs_studio.core.models import ConditionTemplateProfile
from fpvs_studio.gui.condition_template_manager_dialog import ConditionTemplateManagerDialog
from fpvs_studio.gui.create_project_dialog import CreateProjectDialog
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.main_window import StudioMainWindow
from fpvs_studio.gui.settings_dialog import AppSettingsDialog
from fpvs_studio.gui.welcome_window import WelcomeWindow

_SETTINGS_ORGANIZATION = "FPVS Studio"
_SETTINGS_APPLICATION = "FPVS Studio"
_FPVS_ROOT_DIR_KEY = "paths/fpvs_root_dir"


def _show_error(parent: QWidget | None, title: str, error: Exception) -> None:
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Critical)
    dialog.setWindowTitle(title)
    dialog.setText(str(error))
    dialog.setDetailedText(
        "".join(traceback.format_exception(type(error), error, error.__traceback__))
    )
    dialog.exec()


class StudioController:
    """Own the top-level FPVS Studio windows and project-opening flows."""

    def __init__(self, app: QApplication) -> None:
        self._app = app
        self.welcome_window: WelcomeWindow | None = None
        self.main_window: StudioMainWindow | None = None
        self._settings = QSettings(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            _SETTINGS_ORGANIZATION,
            _SETTINGS_APPLICATION,
        )
        self._fpvs_root_dir: Path | None = None
        self._projects_parent_dir = Path.cwd()

    def show_welcome(self) -> None:
        """Show the welcome window."""

        if not self.ensure_fpvs_root_configured():
            return

        if self.welcome_window is None:
            self.welcome_window = WelcomeWindow()
            self.welcome_window.create_requested.connect(self.show_create_project_dialog)
            self.welcome_window.open_requested.connect(self.show_open_project_dialog)
        self.welcome_window.show()
        self.welcome_window.raise_()
        self.welcome_window.activateWindow()

    def load_fpvs_root_dir(self) -> Path | None:
        """Load the persisted FPVS Studio root folder when it still exists."""

        raw_root_dir = self._settings.value(_FPVS_ROOT_DIR_KEY, "", type=str)
        if not raw_root_dir:
            self._fpvs_root_dir = None
            return None

        root_dir = Path(raw_root_dir).expanduser()
        if root_dir.is_dir():
            self._fpvs_root_dir = root_dir
            self._projects_parent_dir = root_dir
            return root_dir

        self._settings.remove(_FPVS_ROOT_DIR_KEY)
        self._settings.sync()
        self._fpvs_root_dir = None
        return None

    def save_fpvs_root_dir(self, path: Path) -> None:
        """Persist the FPVS Studio root folder preference."""

        root_dir = Path(path).expanduser()
        if not root_dir.is_dir():
            raise ValueError("FPVS Studio Root Folder must be an existing directory.")
        self._settings.setValue(_FPVS_ROOT_DIR_KEY, str(root_dir))
        self._settings.sync()
        self._fpvs_root_dir = root_dir
        self._projects_parent_dir = root_dir
        self._normalize_fpvs_root_layout()

    def ensure_fpvs_root_configured(self) -> bool:
        """Require a valid FPVS Studio root folder before normal workflows are shown."""

        loaded_root_dir = self.load_fpvs_root_dir()
        if loaded_root_dir is not None and self._normalize_fpvs_root_layout():
            return True

        parent = self.main_window if self.main_window is not None else self.welcome_window
        while True:
            directory = QFileDialog.getExistingDirectory(
                parent,
                "Choose FPVS Studio Root Folder",
                str(Path.home()),
            )
            if directory:
                selected_path = Path(directory)
                if selected_path.is_dir():
                    self.save_fpvs_root_dir(selected_path)
                    if self._normalize_fpvs_root_layout():
                        return True
                    continue
                QMessageBox.warning(
                    parent,
                    "Invalid FPVS Studio Root Folder",
                    "Choose an existing folder for the FPVS Studio Root Folder.",
                )
                continue

            answer = QMessageBox.question(
                parent,
                "FPVS Studio Root Folder Required",
                "FPVS Studio Root Folder is required before opening or creating projects. "
                "Exit FPVS Studio now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.No:
                continue
            self._app.quit()
            return False

    def show_create_project_dialog(self) -> None:
        """Collect new-project inputs and scaffold a project when confirmed."""

        if not self.ensure_fpvs_root_configured():
            return
        if not self._normalize_fpvs_root_layout():
            return
        parent = self.main_window if self.main_window is not None else self.welcome_window
        if self._fpvs_root_dir is None:
            return
        dialog = CreateProjectDialog(
            condition_template_profiles=self._load_condition_template_profiles(),
            on_manage_templates=self._show_condition_template_manager,
            parent=parent,
        )
        dialog.set_parent_directory(self._projects_parent_dir)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self.create_project(
            dialog.project_name,
            dialog.parent_directory,
            condition_profile_id=dialog.condition_profile_id,
        )

    def show_open_project_dialog(self) -> None:
        """Open an existing project directory."""

        if not self.ensure_fpvs_root_configured():
            return
        if not self._normalize_fpvs_root_layout():
            return
        parent = self.main_window if self.main_window is not None else self.welcome_window
        directory = QFileDialog.getExistingDirectory(
            parent,
            "Open FPVS Project Directory",
            str(self._projects_parent_dir),
        )
        if not directory:
            return
        self.open_project(Path(directory))

    def create_project(
        self,
        project_name: str,
        parent_dir: Path,
        *,
        condition_profile_id: str | None = None,
    ) -> ProjectDocument | None:
        """Scaffold and open a new project."""

        if not self._normalize_fpvs_root_layout():
            return None
        condition_profile: ConditionTemplateProfile | None = None
        root_dir = self._fpvs_root_dir
        if condition_profile_id is not None and root_dir is not None:
            try:
                condition_profile = get_condition_template_profile(root_dir, condition_profile_id)
            except KeyError as error:
                _show_error(
                    self.main_window or self.welcome_window,
                    "Create Project Error",
                    ValueError(str(error)),
                )
                return None
        try:
            document = ProjectDocument.create_new(
                parent_dir=Path(parent_dir),
                project_name=project_name,
                condition_template_profile=condition_profile,
            )
        except Exception as error:
            _show_error(self.main_window or self.welcome_window, "Create Project Error", error)
            return None
        self._open_document(document)
        return document

    def open_project(self, project_location: Path) -> ProjectDocument | None:
        """Open an existing project directory or `project.json` path."""

        if not self._normalize_fpvs_root_layout():
            return None
        try:
            document = ProjectDocument.open_existing(Path(project_location))
        except Exception as error:
            _show_error(self.main_window or self.welcome_window, "Open Project Error", error)
            return None
        self._open_document(document)
        return document

    def show_settings_dialog(self) -> None:
        """Show application-level settings, including the FPVS Studio root folder."""

        if not self.ensure_fpvs_root_configured():
            return
        if not self._normalize_fpvs_root_layout():
            return
        parent = self.main_window if self.main_window is not None else self.welcome_window
        root_dir = self._fpvs_root_dir
        if root_dir is None:
            return
        dialog = AppSettingsDialog(
            fpvs_root_dir=root_dir,
            on_change_fpvs_root_dir=self.save_fpvs_root_dir,
            on_manage_condition_templates=self._show_condition_template_manager,
            parent=parent,
        )
        dialog.exec()

    def _open_document(self, document: ProjectDocument) -> None:
        document.randomize_session_seed_for_app_launch()
        previous_window = self.main_window
        self.main_window = StudioMainWindow(
            document=document,
            on_request_new_project=self.show_create_project_dialog,
            on_request_open_project=self.show_open_project_dialog,
            on_request_settings=self.show_settings_dialog,
            on_load_condition_template_profiles=self._load_condition_template_profiles,
            on_manage_condition_templates=self._show_condition_template_manager,
        )
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
        if self.welcome_window is not None:
            self.welcome_window.hide()
        if previous_window is not None and previous_window is not self.main_window:
            previous_window.close()

    def _load_condition_template_profiles(self) -> list[ConditionTemplateProfile]:
        root_dir = self._fpvs_root_dir
        if root_dir is None:
            return []
        return list_condition_template_profiles(root_dir)

    def _show_condition_template_manager(self) -> list[ConditionTemplateProfile]:
        if not self.ensure_fpvs_root_configured():
            return []
        root_dir = self._fpvs_root_dir
        if root_dir is None:
            return []
        parent = self.main_window if self.main_window is not None else self.welcome_window
        dialog = ConditionTemplateManagerDialog(root_dir=root_dir, parent=parent)
        dialog.exec()
        return self._load_condition_template_profiles()

    def _normalize_fpvs_root_layout(self) -> bool:
        root_dir = self._fpvs_root_dir
        if root_dir is None:
            return True
        try:
            normalize_condition_template_profile_root(root_dir)
        except Exception as error:
            _show_error(
                self.main_window or self.welcome_window,
                "FPVS Root Layout Error",
                error,
            )
            return False
        return True
