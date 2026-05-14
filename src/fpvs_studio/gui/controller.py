"""Top-level GUI controller for welcome, project-open, and settings flows. It coordinates
windows and document lifecycle by delegating project creation, loading, and authoring
actions into backend-backed GUI objects. This module owns application navigation and
error surfacing, not core protocol semantics or runtime execution internals."""

from __future__ import annotations

import ctypes
import os
import shutil
import stat
import traceback
from collections.abc import Callable
from ctypes import wintypes
from pathlib import Path
from types import TracebackType

from PySide6.QtCore import QObject, QSettings, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget

from fpvs_studio.core.condition_template_profiles import (
    get_condition_template_profile,
    list_condition_template_profiles,
    normalize_condition_template_profile_root,
)
from fpvs_studio.core.models import ConditionTemplateProfile
from fpvs_studio.core.paths import project_json_path
from fpvs_studio.core.project_config import create_project_from_config, read_project_config
from fpvs_studio.core.serialization import load_project_file
from fpvs_studio.gui.condition_template_manager_dialog import ConditionTemplateManagerDialog
from fpvs_studio.gui.create_project_dialog import CreateProjectDialog
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.main_window import StudioMainWindow
from fpvs_studio.gui.manage_projects_dialog import ManageProjectsDialog, ProjectManagementEntry
from fpvs_studio.gui.root_folder_setup_dialog import RootFolderSetupDialog
from fpvs_studio.gui.settings_dialog import AppSettingsDialog
from fpvs_studio.gui.update_dialog import UpdateDialog
from fpvs_studio.gui.welcome_window import WelcomeWindow
from fpvs_studio.updates.github_releases import check_for_updates
from fpvs_studio.updates.models import UpdateCheckResult

_SETTINGS_ORGANIZATION = "FPVS Studio"
_SETTINGS_APPLICATION = "FPVS Studio"
_FPVS_ROOT_DIR_KEY = "paths/fpvs_root_dir"
_RECENT_PROJECT_ROOTS_KEY = "projects/recent_project_roots"
_MAX_RECENT_PROJECTS = 8


def _show_error(parent: QWidget | None, title: str, error: Exception) -> None:
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Critical)
    dialog.setWindowTitle(title)
    dialog.setText(str(error))
    dialog.setDetailedText(
        "".join(traceback.format_exception(type(error), error, error.__traceback__))
    )
    dialog.exec()


class _StartupUpdateCheckWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, callback: Callable[[], UpdateCheckResult]) -> None:
        super().__init__()
        self._callback = callback

    @Slot()
    def run(self) -> None:
        try:
            result = self._callback()
        except Exception as error:
            self.failed.emit(error)
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()


class StudioController(QObject):
    """Own the top-level FPVS Studio windows and project-opening flows."""

    def __init__(self, app: QApplication) -> None:
        super().__init__(app)
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
        self.startup_update_checks_enabled = True
        self._startup_update_check_started = False
        self._startup_update_thread: QThread | None = None
        self._startup_update_worker: _StartupUpdateCheckWorker | None = None
        self._startup_update_check_callback: Callable[[], UpdateCheckResult] = check_for_updates

    def show_welcome(self) -> None:
        """Show the welcome window."""

        if not self.ensure_fpvs_root_configured():
            return

        if self.welcome_window is None:
            self.welcome_window = WelcomeWindow()
            self.welcome_window.create_requested.connect(self.show_create_project_dialog)
            self.welcome_window.manage_projects_requested.connect(
                self.show_manage_projects_dialog
            )
        self.welcome_window.show()
        self.welcome_window.raise_()
        self.welcome_window.activateWindow()
        self._schedule_startup_update_check()

    def _schedule_startup_update_check(self) -> None:
        if not self.startup_update_checks_enabled or self._startup_update_check_started:
            return
        self._startup_update_check_started = True
        QTimer.singleShot(0, self._start_startup_update_check)

    def _start_startup_update_check(self) -> None:
        if self._startup_update_thread is not None:
            return
        worker = _StartupUpdateCheckWorker(self._startup_update_check_callback)
        thread = QThread(self._app)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._handle_startup_update_check_result)
        worker.failed.connect(lambda _error: None)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._handle_startup_update_thread_finished)
        self._startup_update_worker = worker
        self._startup_update_thread = thread
        thread.start()

    @Slot(object)
    def _handle_startup_update_check_result(self, result: object) -> None:
        if not isinstance(result, UpdateCheckResult):
            return
        if not result.update_available or result.installer_asset is None:
            return
        parent = self.main_window or self.welcome_window
        dialog = UpdateDialog(
            parent=parent,
            auto_check=False,
            initial_result=result,
            on_before_install=self._maybe_save_current_project,
        )
        dialog.exec()

    @Slot()
    def _handle_startup_update_thread_finished(self) -> None:
        self._startup_update_thread = None
        self._startup_update_worker = None

    def _maybe_save_current_project(self) -> bool:
        if self.main_window is None:
            return True
        return self.main_window.maybe_save_changes()

    def load_recent_project_roots(self) -> list[Path]:
        """Return valid recent project roots, pruning stale settings entries."""

        raw_value = self._settings.value(_RECENT_PROJECT_ROOTS_KEY, [], type=list)
        recent_paths: list[Path] = []
        seen: set[str] = set()
        for raw_path in raw_value if isinstance(raw_value, list) else []:
            if not isinstance(raw_path, str) or not raw_path:
                continue
            project_root = Path(raw_path).expanduser()
            normalized = str(project_root)
            if normalized in seen:
                continue
            if not (project_root / "project.json").is_file():
                continue
            recent_paths.append(project_root)
            seen.add(normalized)
            if len(recent_paths) >= _MAX_RECENT_PROJECTS:
                break
        self._settings.setValue(
            _RECENT_PROJECT_ROOTS_KEY,
            [str(path) for path in recent_paths],
        )
        self._settings.sync()
        return recent_paths

    def load_recent_project_entries(self) -> list[tuple[str, str]]:
        """Return display names and root paths for valid recent projects."""

        entries: list[tuple[str, str]] = []
        valid_roots: list[Path] = []
        recent_roots = self.load_recent_project_roots()
        for project_root in recent_roots:
            try:
                project = load_project_file(project_json_path(project_root))
            except Exception:
                continue
            entries.append((project.meta.name, str(project_root)))
            valid_roots.append(project_root)
        if len(valid_roots) != len(recent_roots):
            self._settings.setValue(
                _RECENT_PROJECT_ROOTS_KEY,
                [str(path) for path in valid_roots],
            )
            self._settings.sync()
        return entries

    def record_recent_project_root(self, project_root: Path) -> None:
        """Persist a project root as the most recent launch/open target."""

        normalized_root = Path(project_root).expanduser()
        if not (normalized_root / "project.json").is_file():
            return
        existing = [
            path
            for path in self.load_recent_project_roots()
            if str(path) != str(normalized_root)
        ]
        recent_paths = [normalized_root, *existing][:_MAX_RECENT_PROJECTS]
        self._settings.setValue(
            _RECENT_PROJECT_ROOTS_KEY,
            [str(path) for path in recent_paths],
        )
        self._settings.sync()

    def remove_recent_project_root(self, project_root: Path) -> None:
        """Remove one project root from the recent-project settings list."""

        normalized_root = self._normalize_path(project_root)
        recent_paths = [
            path
            for path in self.load_recent_project_roots()
            if self._normalize_path(path) != normalized_root
        ]
        self._settings.setValue(
            _RECENT_PROJECT_ROOTS_KEY,
            [str(path) for path in recent_paths],
        )
        self._settings.sync()

    def open_recent_project(self, project_root: str) -> None:
        """Open a project selected from the welcome screen recent-project list."""

        self.open_project(Path(project_root))

    def load_fpvs_root_dir(self) -> Path | None:
        """Load the persisted FPVS Studio root folder when it still exists."""

        raw_root_dir = self._settings.value(_FPVS_ROOT_DIR_KEY, "", type=str)
        if not isinstance(raw_root_dir, str) or not raw_root_dir:
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
            setup_dialog = RootFolderSetupDialog(
                current_root=None,
                first_run=True,
                parent=parent,
            )
            if setup_dialog.exec() != setup_dialog.DialogCode.Accepted:
                self._app.quit()
                return False

            selected_path = self._choose_fpvs_root_dir(parent=parent, initial_dir=Path.home())
            if selected_path is None:
                continue
            self.save_fpvs_root_dir(selected_path)
            if self._normalize_fpvs_root_layout():
                return True

    def show_root_folder_setup(self, parent: QWidget | None = None) -> Path | None:
        """Show root-folder guidance and optionally choose a different root folder."""

        current_root = self.load_fpvs_root_dir()
        dialog_parent = parent or self.main_window or self.welcome_window
        setup_dialog = RootFolderSetupDialog(
            current_root=current_root,
            first_run=False,
            parent=dialog_parent,
        )
        if setup_dialog.exec() != setup_dialog.DialogCode.Accepted:
            return None

        selected_path = self._choose_fpvs_root_dir(
            parent=dialog_parent,
            initial_dir=current_root or Path.home(),
        )
        if selected_path is None:
            return None
        self.save_fpvs_root_dir(selected_path)
        if self._normalize_fpvs_root_layout():
            return selected_path
        return None

    def _choose_fpvs_root_dir(
        self,
        *,
        parent: QWidget | None,
        initial_dir: Path,
    ) -> Path | None:
        directory = QFileDialog.getExistingDirectory(
            parent,
            "Choose FPVS Studio Root Folder",
            str(initial_dir),
        )
        if not directory:
            return None
        selected_path = Path(directory)
        if selected_path.is_dir():
            return selected_path
        QMessageBox.warning(
            parent,
            "Invalid FPVS Studio Root Folder",
            "Choose an existing folder for the FPVS Studio Root Folder.",
        )
        return None

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

    def show_manage_projects_dialog(self) -> None:
        """Show the project management dialog for known FPVS projects."""

        if not self.ensure_fpvs_root_configured():
            return
        if not self._normalize_fpvs_root_layout():
            return
        parent = self.main_window if self.main_window is not None else self.welcome_window
        dialog = ManageProjectsDialog(
            entries=self.load_manageable_project_entries(),
            parent=parent,
        )
        dialog.open_requested.connect(lambda root: self._open_managed_project(dialog, root))
        dialog.delete_requested.connect(lambda root: self._delete_managed_project(dialog, root))
        dialog.exec()

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
            on_show_root_folder_setup=self.show_root_folder_setup,
            on_manage_condition_templates=self._show_condition_template_manager,
            parent=parent,
        )
        dialog.exec()

    def _open_document(self, document: ProjectDocument) -> None:
        document.randomize_session_seed_for_app_launch()
        self.record_recent_project_root(document.project_root)
        previous_window = self.main_window
        self.main_window = StudioMainWindow(
            document=document,
            on_request_new_project=self.show_create_project_dialog,
            on_request_open_project=self.show_open_project_dialog,
            on_request_manage_projects=self.show_manage_projects_dialog,
            on_request_import_project_config=self.show_import_project_config_dialog,
            on_request_settings=self.show_settings_dialog,
            on_load_condition_template_profiles=self._load_condition_template_profiles,
            on_manage_condition_templates=self._show_condition_template_manager,
        )
        if (
            self.welcome_window is not None
            and self.main_window.main_stack.currentWidget() is self.main_window.home_page
        ):
            self.main_window.setGeometry(self.welcome_window.geometry())
        self._show_opened_main_window(previous_window)

    def _show_opened_main_window(self, previous_window: StudioMainWindow | None) -> None:
        target_window = self.main_window
        if target_window is None:
            return
        target_window.ensurePolished()
        target_window.main_stack.ensurePolished()
        target_window.show()
        target_window.raise_()
        target_window.activateWindow()
        target_window.repaint()

        QTimer.singleShot(
            0,
            lambda: self._finish_opened_main_window_handoff(
                target_window,
                previous_window,
            ),
        )

    def _finish_opened_main_window_handoff(
        self,
        target_window: StudioMainWindow,
        previous_window: StudioMainWindow | None,
    ) -> None:
        if self.main_window is not target_window:
            return
        if self.welcome_window is not None:
            self.welcome_window.hide()
        if previous_window is not None and previous_window is not target_window:
            previous_window.close()

    def _load_condition_template_profiles(self) -> list[ConditionTemplateProfile]:
        root_dir = self._fpvs_root_dir
        if root_dir is None:
            return []
        return list_condition_template_profiles(root_dir)

    def show_import_project_config_dialog(self) -> None:
        """Import a Studio `.fpvsconfig` file as a new project shell."""

        if not self.ensure_fpvs_root_configured():
            return
        if not self._normalize_fpvs_root_layout():
            return
        root_dir = self._fpvs_root_dir
        if root_dir is None:
            return
        parent = self.main_window if self.main_window is not None else self.welcome_window
        selected_path, _selected_filter = QFileDialog.getOpenFileName(
            parent,
            "Import FPVS Project Config",
            str(root_dir),
            (
                "FPVS Config Files (*.fpvsconfig);;"
                "Legacy Config Files (*.config);;"
                "JSON Files (*.json);;"
                "All Files (*)"
            ),
        )
        if not selected_path:
            return
        try:
            config = read_project_config(Path(selected_path))
            scaffold = create_project_from_config(root_dir, config)
            document = ProjectDocument.open_existing(scaffold.project_root)
        except Exception as error:
            _show_error(parent, "Import Project Config Error", error)
            return
        self._open_document(document)

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

    def load_manageable_project_entries(self) -> list[ProjectManagementEntry]:
        """Return projects discoverable from the Studio root and recent-project list."""

        self.load_fpvs_root_dir()
        roots: list[Path] = []
        seen: set[Path] = set()
        for project_root in (*self._discover_project_roots(), *self.load_recent_project_roots()):
            normalized_root = self._normalize_path(project_root)
            if normalized_root in seen:
                continue
            seen.add(normalized_root)
            roots.append(project_root)

        entries = [self._project_management_entry(root) for root in roots]
        return sorted(entries, key=lambda entry: entry.name.casefold())

    def _discover_project_roots(self) -> list[Path]:
        root_dir = self._fpvs_root_dir
        if root_dir is None or not root_dir.is_dir():
            return []
        project_roots: list[Path] = []
        pending_dirs = [root_dir]
        while pending_dirs:
            current_dir = pending_dirs.pop()
            if project_json_path(current_dir).is_file():
                project_roots.append(current_dir)
                continue
            try:
                children = list(current_dir.iterdir())
            except OSError:
                continue
            pending_dirs.extend(child for child in children if child.is_dir())
        return project_roots

    def _project_management_entry(self, project_root: Path) -> ProjectManagementEntry:
        normalized_root = self._normalize_path(project_root)
        is_current = self._current_project_root() == normalized_root
        try:
            project = load_project_file(project_json_path(project_root))
        except Exception:
            return ProjectManagementEntry(
                name=project_root.name,
                root=project_root,
                status_text="Invalid Project",
                status_state="warning",
                can_open=False,
                can_delete=False,
            )
        return ProjectManagementEntry(
            name=project.meta.name,
            root=project_root,
            status_text="Open Project" if is_current else "Ready",
            status_state="info" if is_current else "ready",
            can_open=not is_current,
            can_delete=not is_current,
        )

    def _open_managed_project(self, dialog: ManageProjectsDialog, project_root: str) -> None:
        if self.main_window is not None and not self.main_window.maybe_save_changes():
            return
        dialog.accept()
        self.open_project(Path(project_root))

    def _delete_managed_project(self, dialog: ManageProjectsDialog, project_root: str) -> None:
        self.delete_project(Path(project_root), parent=dialog)
        dialog.set_project_entries(self.load_manageable_project_entries())

    def delete_project(self, project_root: Path, *, parent: QWidget | None = None) -> bool:
        """Move an existing FPVS project folder to the Recycle Bin after confirmation."""

        normalized_root = self._normalize_path(project_root)
        if self._current_project_root() == normalized_root:
            QMessageBox.warning(
                parent,
                "Delete Project",
                "The currently open project cannot be deleted. Open a different project "
                "before deleting this project folder.",
            )
            return False
        if not project_root.exists():
            self.remove_recent_project_root(project_root)
            QMessageBox.warning(
                parent,
                "Delete Project",
                "This project folder no longer exists. It was removed from Recent Projects.",
            )
            return False
        if not project_root.is_dir() or not project_json_path(project_root).is_file():
            QMessageBox.warning(
                parent,
                "Delete Project",
                "Only folders containing an FPVS Studio project.json file can be deleted.",
            )
            return False

        try:
            project = load_project_file(project_json_path(project_root))
            project_name = project.meta.name
        except Exception as error:
            _show_error(parent, "Delete Project Error", error)
            return False

        answer = QMessageBox.question(
            parent,
            "Move Project to Recycle Bin",
            f'Are you sure you want to move this project to the Recycle Bin?\n\n'
            f'"{project_name}"\n\n'
            f"Folder:\n{project_root}\n\n"
            "You can restore it from the Windows Recycle Bin until the Recycle Bin is emptied.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False

        try:
            _move_project_tree_to_recycle_bin(project_root)
            if project_root.exists() and not project_json_path(project_root).exists():
                _remove_project_tree(project_root)
            if project_root.exists():
                raise OSError(
                    "Windows did not fully remove this project folder: "
                    f"{project_root}"
                )
        except Exception as error:
            _show_error(parent, "Delete Project Error", error)
            return False

        self.remove_recent_project_root(project_root)
        return True

    def _current_project_root(self) -> Path | None:
        if self.main_window is None:
            return None
        return self._normalize_path(self.main_window.document.project_root)

    @staticmethod
    def _normalize_path(path: Path) -> Path:
        return Path(path).expanduser().resolve()

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


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", wintypes.WORD),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", wintypes.LPVOID),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def _move_project_tree_to_recycle_bin(project_root: Path) -> None:
    """Move a project tree to the Windows Recycle Bin."""

    if os.name != "nt":
        _remove_project_tree(project_root)
        return

    file_operation = _SHFILEOPSTRUCTW()
    file_operation.hwnd = None
    file_operation.wFunc = 0x0003  # FO_DELETE
    file_operation.pFrom = f"{project_root.resolve()}\0\0"
    file_operation.pTo = None
    file_operation.fFlags = 0x0040 | 0x0010 | 0x0400 | 0x0004
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(file_operation))
    if result != 0:
        raise OSError(
            result,
            f"Windows could not move this project to the Recycle Bin: {project_root}",
        )
    if file_operation.fAnyOperationsAborted:
        raise OSError(f"Move to Recycle Bin was canceled for this project: {project_root}")


def _remove_project_tree(project_root: Path) -> None:
    """Remove a project tree, retrying Windows read-only permission failures."""

    def _make_writable_and_retry(
        function: Callable[[str], object],
        path: str,
        exc_info: tuple[type[BaseException], BaseException, TracebackType],
    ) -> None:
        error = exc_info[1]
        if not isinstance(error, PermissionError):
            raise error
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)
        function(path)

    shutil.rmtree(project_root, onerror=_make_writable_and_retry)
