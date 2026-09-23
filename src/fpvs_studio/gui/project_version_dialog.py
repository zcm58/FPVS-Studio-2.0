"""Nonmodal review surface for library project versions and explicit project linking."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.components import DialogHeader, apply_dialog_theme, mark_primary_action
from fpvs_studio.library.models import LibraryItem


class ProjectVersionDialog(QDialog):
    """Collect explicit user actions; the app-owned controller performs all work."""

    action_requested = Signal(str)
    closing = Signal()

    def __init__(self, project_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("project_version_dialog")
        self.setWindowTitle("Update Project Version")
        self.setModal(False)
        self.setMinimumSize(760, 680)
        self.resize(820, 720)
        self._busy = False
        self._can_install = False
        self._linked = False
        self._linking = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        self.header = DialogHeader("Project versions", project_name, parent=self)
        self.header.subtitle_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.header)
        self.versions_label = QLabel(self)
        self.versions_label.setObjectName("project_version_summary")
        self.versions_label.setTextFormat(Qt.TextFormat.PlainText)
        self.versions_label.setWordWrap(True)
        self.versions_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.versions_label)
        self.auto_check_checkbox = QCheckBox(
            "Check for library updates when this project opens", self,
        )
        self.auto_check_checkbox.setObjectName("project_version_auto_check")
        self.auto_check_checkbox.clicked.connect(
            lambda _checked: self.action_requested.emit("set_auto")
        )
        self.relink_button = QPushButton("Change library link...", self)
        self.relink_button.setObjectName("project_version_relink_button")
        self.relink_button.clicked.connect(lambda: self.action_requested.emit("relink"))
        link_actions = QHBoxLayout()
        link_actions.addWidget(self.auto_check_checkbox, 1)
        link_actions.addWidget(self.relink_button)
        layout.addLayout(link_actions)

        self.link_panel = QWidget(self)
        self.link_panel.setObjectName("project_version_link_panel")
        form = QFormLayout(self.link_panel)
        form.setContentsMargins(0, 0, 0, 0)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.link_help = QLabel(
            "Choose the library experiment this project came from. Enter its installed version "
            "only if you know it; a blank version is recorded as unknown.", self.link_panel,
        )
        self.link_help.setWordWrap(True)
        form.addRow(self.link_help)
        self.link_combo = QComboBox(self.link_panel)
        self.link_combo.setObjectName("project_version_link_item")
        self.link_combo.setMinimumWidth(0)
        self.link_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.link_combo.setMinimumContentsLength(20)
        self.link_combo.currentIndexChanged.connect(self._link_selection_changed)
        form.addRow("Library experiment", self.link_combo)
        self.installed_version_edit = QLineEdit(self.link_panel)
        self.installed_version_edit.setObjectName("project_version_installed_version")
        self.installed_version_edit.setPlaceholderText("Unknown — leave blank")
        self.installed_version_edit.setMaxLength(64)
        self.link_button = QPushButton("Link this project", self.link_panel)
        self.link_button.setObjectName("project_version_link_button")
        self.link_button.clicked.connect(lambda: self.action_requested.emit("link"))
        version_row = QHBoxLayout()
        version_row.addWidget(self.installed_version_edit, 1)
        version_row.addWidget(self.link_button)
        form.addRow("Installed version", version_row)
        layout.addWidget(self.link_panel)

        self.details = QTextEdit(self)
        self.details.setObjectName("project_version_details")
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(110)
        layout.addWidget(self.details, 1)
        self.preservation_label = QLabel(
            "The new version opens as a separate project. Your current project's edits and "
            "participant data stay in the existing folder.", self,
        )
        self.preservation_label.setWordWrap(True)
        layout.addWidget(self.preservation_label)
        self.status_label = QLabel(self)
        self.status_label.setObjectName("project_version_status")
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(40)
        layout.addWidget(self.status_label)
        buttons = QHBoxLayout()
        self.check_button = QPushButton("Check for new version", self)
        self.check_button.setObjectName("project_version_check_button")
        self.check_button.clicked.connect(lambda: self.action_requested.emit("check"))
        self.install_button = QPushButton("Open new version separately", self)
        self.install_button.setObjectName("project_version_install_button")
        self.install_button.clicked.connect(lambda: self.action_requested.emit("install"))
        mark_primary_action(self.install_button)
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.setObjectName("project_version_cancel_button")
        self.cancel_button.clicked.connect(lambda: self.action_requested.emit("cancel"))
        self.close_button = QPushButton("Close", self)
        self.close_button.clicked.connect(self.reject)
        buttons.addWidget(self.check_button)
        buttons.addStretch(1)
        buttons.addWidget(self.install_button)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        apply_dialog_theme(self)
        self.set_link_items([])
        self.set_state(installed_version=None, latest=None, linked=False, auto_check=True)

    def set_state(
        self, *, installed_version: str | None, latest: LibraryItem | None,
        linked: bool, auto_check: bool, status: str = "", can_install: bool = False,
    ) -> None:
        self._linked = linked
        self._linking = False
        self._can_install = can_install
        current = installed_version or ("Unknown" if linked else "Not linked")
        newest = latest.version if latest is not None else "Not checked"
        self.versions_label.setText(
            f"Installed library version: {current}\nLatest version: {newest}"
        )
        self.auto_check_checkbox.setChecked(auto_check)
        self.link_panel.setVisible(not linked or installed_version is None)
        self.details.setPlainText(
            f"{latest.title}\nVersion {latest.version}\n"
            f"Requires FPVS Studio {latest.min_studio_version} or later.\n\n{latest.description}"
            if latest is not None else
            "Check the library to see the newest available version and its description."
        )
        self.status_label.setText(status)
        self._update_controls()

    def begin_linking(self) -> None:
        """Start an explicit replacement link without guessing its installed version."""
        self._linking = True
        self.link_panel.show()
        self.installed_version_edit.clear()
        self.link_combo.setCurrentIndex(0)
        self.details.setPlainText("Choose the library experiment to link to this project.")
        self.status_label.setText("Choose the correct experiment, then link this project.")
        self._update_controls()

    def set_link_items(self, items: Sequence[LibraryItem]) -> None:
        self.link_combo.clear()
        self.link_combo.addItem("Choose a library experiment", None)
        for item in items:
            label = f"{item.title} — {item.version} ({item.item_id})"
            self.link_combo.addItem(label, item)
            self.link_combo.setItemData(
                self.link_combo.count() - 1,
                f"{label}\n{item.description}", Qt.ItemDataRole.ToolTipRole,
            )
        self._link_selection_changed()

    def selected_link_item(self) -> LibraryItem | None:
        item = self.link_combo.currentData()
        return item if isinstance(item, LibraryItem) else None

    def link_installed_version(self) -> str | None:
        return self.installed_version_edit.text().strip() or None

    def auto_check_enabled(self) -> bool:
        return self.auto_check_checkbox.isChecked()

    def set_busy(self, busy: bool, status: str = "") -> None:
        self._busy = busy
        if status:
            self.status_label.setText(status)
        self._update_controls()

    def clear_install_candidate(self) -> None:
        """Require a successful fresh check before offering another installation."""
        self._can_install = False
        self._update_controls()

    def _link_selection_changed(self, *_args: object) -> None:
        item = self.selected_link_item()
        self.link_combo.setToolTip(f"{item.title} ({item.item_id})" if item else "")
        if (not self._linked or self._linking) and item is not None:
            self.details.setPlainText(
                f"{item.title}\nLibrary version {item.version}\n\n{item.description}"
            )
        self._update_controls()

    def _update_controls(self) -> None:
        self.check_button.setEnabled(not self._busy)
        self.install_button.setEnabled(not self._busy and self._can_install and not self._linking)
        self.auto_check_checkbox.setEnabled(not self._busy and self._linked)
        self.relink_button.setVisible(self._linked)
        self.relink_button.setEnabled(not self._busy)
        self.link_combo.setEnabled(not self._busy)
        self.installed_version_edit.setEnabled(not self._busy)
        self.link_button.setEnabled(not self._busy and self.selected_link_item() is not None)
        self.cancel_button.setVisible(self._busy)
        self.close_button.setVisible(not self._busy)

    def reject(self) -> None:
        self.closing.emit()
        super().reject()
