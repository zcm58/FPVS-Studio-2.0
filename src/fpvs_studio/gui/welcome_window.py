"""Welcome screen shown before a project document is opened. It presents entry actions for
creating or loading work without taking ownership of project scaffolding, compilation,
or runtime launch logic. The module owns introductory UI only; controller and document
layers handle application state transitions."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.components import apply_welcome_window_theme, mark_welcome_action


class WelcomeWindow(QWidget):
    """Responsive start page for creating/opening FPVS projects."""

    create_requested = Signal()
    open_requested = Signal()
    manage_projects_requested = Signal()
    recent_project_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FPVS Studio")
        self.setMinimumSize(760, 520)
        self.resize(1040, 680)
        self._adopt_app_icon()

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(32, 32, 32, 32)
        page_layout.setSpacing(16)

        self.content_frame = QFrame(self)
        self.content_frame.setObjectName("welcome_content_frame")
        self.content_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        page_layout.addWidget(self.content_frame, 1)

        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(44, 40, 44, 40)
        content_layout.setSpacing(0)

        content_layout.addStretch(1)

        self.hero_container = QWidget(self.content_frame)
        self.hero_container.setObjectName("welcome_hero_container")
        self.hero_container.setMaximumWidth(760)
        self.hero_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        content_layout.addWidget(self.hero_container, 0, Qt.AlignmentFlag.AlignHCenter)

        hero_layout = QVBoxLayout(self.hero_container)
        hero_layout.setContentsMargins(0, 0, 0, 0)
        hero_layout.setSpacing(18)

        self.brand_label = QLabel("FPVS Studio", self.hero_container)
        self.brand_label.setObjectName("welcome_brand_label")
        self.brand_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(self.brand_label)

        self.headline_label = QLabel("Welcome to FPVS Studio", self.hero_container)
        self.headline_label.setObjectName("welcome_headline_label")
        self.headline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(self.headline_label)

        self.body_label = QLabel(
            "Create a new FPVS project or open an existing one.",
            self.hero_container,
        )
        self.body_label.setObjectName("welcome_body_label")
        self.body_label.setWordWrap(True)
        self.body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(self.body_label)

        self.recent_projects_panel = QFrame(self.hero_container)
        self.recent_projects_panel.setObjectName("welcome_recent_projects_panel")
        self.recent_projects_panel.setVisible(False)
        recent_layout = QVBoxLayout(self.recent_projects_panel)
        recent_layout.setContentsMargins(0, 0, 0, 0)
        recent_layout.setSpacing(8)
        recent_header = QLabel("Recent Projects", self.recent_projects_panel)
        recent_header.setObjectName("welcome_recent_projects_header")
        recent_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recent_project_list = QListWidget(self.recent_projects_panel)
        self.recent_project_list.setObjectName("welcome_recent_project_list")
        self.recent_project_list.setMaximumHeight(128)
        self.recent_project_list.itemClicked.connect(self._open_recent_project_item)
        self.recent_project_list.itemActivated.connect(self._open_recent_project_item)
        recent_layout.addWidget(recent_header)
        recent_layout.addWidget(self.recent_project_list)
        hero_layout.addWidget(self.recent_projects_panel)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)
        action_layout.setContentsMargins(0, 10, 0, 0)
        action_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.create_button = QPushButton("New Project", self.hero_container)
        self.create_button.setObjectName("create_project_button")
        mark_welcome_action(self.create_button, "primary")
        self.create_button.setMinimumHeight(52)
        self.create_button.setFixedWidth(220)
        self.create_button.clicked.connect(self.create_requested.emit)
        action_layout.addWidget(self.create_button)

        self.open_button = QPushButton("Open Project", self.hero_container)
        self.open_button.setObjectName("open_project_button")
        mark_welcome_action(self.open_button, "secondary")
        self.open_button.setMinimumHeight(52)
        self.open_button.setFixedWidth(220)
        self.open_button.clicked.connect(self.open_requested.emit)
        action_layout.addWidget(self.open_button)

        self.manage_projects_button = QPushButton("Manage Projects", self.hero_container)
        self.manage_projects_button.setObjectName("manage_projects_button")
        mark_welcome_action(self.manage_projects_button, "secondary")
        self.manage_projects_button.setMinimumHeight(52)
        self.manage_projects_button.setFixedWidth(220)
        self.manage_projects_button.clicked.connect(self.manage_projects_requested.emit)
        action_layout.addWidget(self.manage_projects_button)
        hero_layout.addLayout(action_layout)

        content_layout.addStretch(1)

        self._apply_theme_styles()

    def set_recent_projects(self, projects: list[tuple[str, str]]) -> None:
        self.recent_project_list.clear()
        for project_name, project_root in projects:
            item = QListWidgetItem(project_name)
            item.setToolTip(project_root)
            item.setData(Qt.ItemDataRole.UserRole, project_root)
            self.recent_project_list.addItem(item)
        self.recent_projects_panel.setVisible(self.recent_project_list.count() > 0)

    def _open_recent_project_item(self, item: QListWidgetItem) -> None:
        project_root = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(project_root, str) and project_root:
            self.recent_project_requested.emit(project_root)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            self._apply_theme_styles()

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
