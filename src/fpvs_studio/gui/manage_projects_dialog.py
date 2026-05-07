"""Project management dialog for opening or recycling known projects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.components import (
    PathValueLabel,
    SectionCard,
    StatusBadgeLabel,
    apply_studio_theme,
    mark_destructive_action,
    mark_primary_action,
    mark_secondary_action,
)


@dataclass(frozen=True)
class ProjectManagementEntry:
    """Display-ready project record owned by the top-level controller."""

    name: str
    root: Path
    status_text: str
    status_state: str
    can_open: bool
    can_delete: bool


class ManageProjectsDialog(QDialog):
    """Thin GUI surface for managing projects known to the Studio root/recent list."""

    open_requested = Signal(str)
    delete_requested = Signal(str)

    def __init__(
        self,
        *,
        entries: list[ProjectManagementEntry],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manage Projects")
        self.setMinimumSize(760, 460)
        self.resize(860, 520)
        self._entries_by_root: dict[str, ProjectManagementEntry] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.project_card = SectionCard(
            title="Manage Projects",
            subtitle="Open an existing project or move a project folder to the Recycle Bin.",
            object_name="manage_projects_card",
            parent=self,
        )
        layout.addWidget(self.project_card, 1)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)
        self.project_card.body_layout.addLayout(body)

        self.project_list = QListWidget(self.project_card)
        self.project_list.setObjectName("manage_projects_list")
        self.project_list.setMinimumWidth(320)
        self.project_list.currentRowChanged.connect(self._sync_selection)
        body.addWidget(self.project_list, 1)

        detail_panel = QWidget(self.project_card)
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(10)
        body.addWidget(detail_panel, 1)

        self.status_badge = StatusBadgeLabel(parent=detail_panel)
        self.status_badge.setObjectName("manage_projects_status_badge")
        detail_layout.addWidget(self.status_badge)

        self.name_label = QLabel("No project selected", detail_panel)
        self.name_label.setObjectName("manage_projects_name_label")
        self.name_label.setProperty("sectionCardRole", "title")
        self.name_label.setWordWrap(True)
        detail_layout.addWidget(self.name_label)

        folder_label = QLabel("Project Folder", detail_panel)
        folder_label.setProperty("setupMetricLabel", "true")
        detail_layout.addWidget(folder_label)

        self.path_label = PathValueLabel(detail_panel)
        self.path_label.setObjectName("manage_projects_path_label")
        detail_layout.addWidget(self.path_label)

        self.empty_label = QLabel("No projects are available to manage.", detail_panel)
        self.empty_label.setObjectName("manage_projects_empty_label")
        self.empty_label.setWordWrap(True)
        detail_layout.addWidget(self.empty_label)
        detail_layout.addStretch(1)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(8)
        action_row.addStretch(1)

        self.open_button = QPushButton("Open Project", self)
        self.open_button.setObjectName("manage_projects_open_button")
        mark_primary_action(self.open_button)
        self.open_button.clicked.connect(self._request_open)
        action_row.addWidget(self.open_button)

        self.delete_button = QPushButton("Move to Recycle Bin", self)
        self.delete_button.setObjectName("manage_projects_delete_button")
        mark_destructive_action(self.delete_button)
        self.delete_button.clicked.connect(self._request_delete)
        action_row.addWidget(self.delete_button)

        self.close_button = QPushButton("Close", self)
        self.close_button.setObjectName("manage_projects_close_button")
        mark_secondary_action(self.close_button)
        self.close_button.clicked.connect(self.reject)
        action_row.addWidget(self.close_button)
        layout.addLayout(action_row)

        self.set_project_entries(entries)
        apply_studio_theme(self)

    def set_project_entries(self, entries: list[ProjectManagementEntry]) -> None:
        """Replace the project list after controller-owned state changes."""

        self.project_list.clear()
        self._entries_by_root = {}
        for entry in entries:
            root_key = str(entry.root)
            self._entries_by_root[root_key] = entry
            item = QListWidgetItem(entry.name)
            item.setData(Qt.ItemDataRole.UserRole, root_key)
            item.setToolTip(root_key)
            self.project_list.addItem(item)

        if self.project_list.count() > 0:
            self.project_list.setCurrentRow(0)
        else:
            self._sync_selection(-1)

    def _selected_entry(self) -> ProjectManagementEntry | None:
        item = self.project_list.currentItem()
        if item is None:
            return None
        root_key = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(root_key, str):
            return None
        return self._entries_by_root.get(root_key)

    def _sync_selection(self, _row: int) -> None:
        entry = self._selected_entry()
        has_entry = entry is not None
        self.empty_label.setVisible(not has_entry)
        self.open_button.setEnabled(has_entry and entry.can_open if entry else False)
        self.delete_button.setEnabled(has_entry and entry.can_delete if entry else False)

        if entry is None:
            self.status_badge.set_state("pending", "No Selection")
            self.name_label.setText("No project selected")
            self.path_label.set_path_text("No project selected")
            return

        self.status_badge.set_state(entry.status_state, entry.status_text)
        self.name_label.setText(entry.name)
        self.path_label.set_path_text(str(entry.root), max_length=84)

    def _request_open(self) -> None:
        entry = self._selected_entry()
        if entry is not None and entry.can_open:
            self.open_requested.emit(str(entry.root))

    def _request_delete(self) -> None:
        entry = self._selected_entry()
        if entry is not None and entry.can_delete:
            self.delete_requested.emit(str(entry.root))
