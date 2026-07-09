"""Welcome screen shown before a project document is opened. It presents entry actions for
creating or loading work without taking ownership of project scaffolding, compilation,
or runtime launch logic. The module owns introductory UI only; controller and document
layers handle application state transitions."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.project_bundle import PROJECT_BUNDLE_SUFFIX
from fpvs_studio.gui.components import (
    LaunchSurfaceFrame,
    apply_welcome_window_theme,
    mark_welcome_action,
)


class WelcomeWindow(QWidget):
    """Responsive start page for creating/opening FPVS projects."""

    create_requested = Signal()
    import_project_bundle_requested = Signal()
    project_bundle_dropped = Signal(object)
    manage_projects_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FPVS Studio")
        self.setMinimumSize(760, 520)
        self.resize(1120, 720)
        self.setAcceptDrops(True)
        self._adopt_app_icon()

        self.launch_surface = LaunchSurfaceFrame(
            frame_object_name="welcome_content_frame",
            hero_object_name="welcome_hero_container",
            parent=self,
        )
        self.content_frame = self.launch_surface.content_frame
        self.hero_container = self.launch_surface.hero_container
        hero_layout = self.launch_surface.hero_layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.launch_surface)

        self.headline_label = QLabel("Welcome to FPVS Studio", self.hero_container)
        self.headline_label.setObjectName("welcome_headline_label")
        self.headline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(self.headline_label)

        self.body_label = QLabel(
            "Create a project, import a project bundle, or open existing work.",
            self.hero_container,
        )
        self.body_label.setObjectName("welcome_body_label")
        self.body_label.setWordWrap(True)
        self.body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(self.body_label)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)
        action_layout.setContentsMargins(0, 10, 0, 0)
        action_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.create_button = QPushButton("Create Project", self.hero_container)
        self.create_button.setObjectName("create_project_button")
        mark_welcome_action(self.create_button, "primary")
        self.create_button.setMinimumHeight(52)
        self.create_button.setFixedWidth(220)
        self.create_button.clicked.connect(self.create_requested.emit)
        action_layout.addWidget(self.create_button)

        self.import_project_button = QPushButton("Import New Project", self.hero_container)
        self.import_project_button.setObjectName("import_project_bundle_button")
        mark_welcome_action(self.import_project_button, "secondary")
        self.import_project_button.setMinimumHeight(52)
        self.import_project_button.setFixedWidth(220)
        self.import_project_button.clicked.connect(
            self.import_project_bundle_requested.emit
        )
        action_layout.addWidget(self.import_project_button)

        self.manage_projects_button = QPushButton("Open Existing Project", self.hero_container)
        self.manage_projects_button.setObjectName("open_projects_button")
        mark_welcome_action(self.manage_projects_button, "secondary")
        self.manage_projects_button.setMinimumHeight(52)
        self.manage_projects_button.setFixedWidth(220)
        self.manage_projects_button.clicked.connect(self.manage_projects_requested.emit)
        action_layout.addWidget(self.manage_projects_button)
        hero_layout.addLayout(action_layout)

        self._apply_theme_styles()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        bundle_path = self._bundle_path_from_mime_data(event.mimeData())
        if bundle_path is None:
            event.ignore()
            return
        event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        bundle_path = self._bundle_path_from_mime_data(event.mimeData())
        if bundle_path is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self.project_bundle_dropped.emit(bundle_path)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            if getattr(self, "_theme_refreshing", False):
                return
            self._theme_refreshing = True
            try:
                self._apply_theme_styles()
            finally:
                self._theme_refreshing = False

    def _apply_theme_styles(self) -> None:
        apply_welcome_window_theme(self)

    def _adopt_app_icon(self) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication) and not app.windowIcon().isNull():
            self.setWindowIcon(app.windowIcon())
            return
        if self.windowIcon().isNull():
            fallback_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            if not fallback_icon.isNull():
                self.setWindowIcon(fallback_icon)

    @staticmethod
    def _bundle_path_from_mime_data(mime_data: object) -> Path | None:
        if not hasattr(mime_data, "urls"):
            return None
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.suffix.lower() == PROJECT_BUNDLE_SUFFIX:
                return path
        return None
