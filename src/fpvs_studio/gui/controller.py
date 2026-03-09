"""High-level GUI controller for welcome/create/open flows."""

from __future__ import annotations

from pathlib import Path
import traceback

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget

from fpvs_studio.gui.create_project_dialog import CreateProjectDialog
from fpvs_studio.gui.document import DocumentError, ProjectDocument
from fpvs_studio.gui.main_window import StudioMainWindow
from fpvs_studio.gui.welcome_window import WelcomeWindow


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
        self._projects_parent_dir = Path.cwd()

    def show_welcome(self) -> None:
        """Show the welcome window."""

        if self.welcome_window is None:
            self.welcome_window = WelcomeWindow()
            self.welcome_window.create_requested.connect(self.show_create_project_dialog)
            self.welcome_window.open_requested.connect(self.show_open_project_dialog)
        self.welcome_window.show()
        self.welcome_window.raise_()
        self.welcome_window.activateWindow()

    def show_create_project_dialog(self) -> None:
        """Collect new-project inputs and scaffold a project when confirmed."""

        parent = self.main_window if self.main_window is not None else self.welcome_window
        dialog = CreateProjectDialog(parent)
        dialog.set_parent_directory(self._projects_parent_dir)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self.create_project(dialog.project_name, dialog.parent_directory)

    def show_open_project_dialog(self) -> None:
        """Open an existing project directory."""

        parent = self.main_window if self.main_window is not None else self.welcome_window
        directory = QFileDialog.getExistingDirectory(
            parent,
            "Open FPVS Project Directory",
            str(self._projects_parent_dir),
        )
        if not directory:
            return
        self.open_project(Path(directory))

    def create_project(self, project_name: str, parent_dir: Path) -> ProjectDocument | None:
        """Scaffold and open a new project."""

        try:
            document = ProjectDocument.create_new(
                parent_dir=Path(parent_dir),
                project_name=project_name,
            )
        except Exception as error:
            _show_error(self.main_window or self.welcome_window, "Create Project Error", error)
            return None
        self._projects_parent_dir = Path(parent_dir)
        self._open_document(document)
        return document

    def open_project(self, project_location: Path) -> ProjectDocument | None:
        """Open an existing project directory or `project.json` path."""

        try:
            document = ProjectDocument.open_existing(Path(project_location))
        except Exception as error:
            _show_error(self.main_window or self.welcome_window, "Open Project Error", error)
            return None
        self._projects_parent_dir = document.project_root.parent
        self._open_document(document)
        return document

    def _open_document(self, document: ProjectDocument) -> None:
        previous_window = self.main_window
        self.main_window = StudioMainWindow(
            document=document,
            on_request_new_project=self.show_create_project_dialog,
            on_request_open_project=self.show_open_project_dialog,
        )
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()
        if self.welcome_window is not None:
            self.welcome_window.hide()
        if previous_window is not None and previous_window is not self.main_window:
            previous_window.close()
