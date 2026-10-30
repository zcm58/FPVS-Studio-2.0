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

_UPDATE_GUIDANCE = (
    "If data collection has started, review changes before switching versions.\n"
    "Updating replaces experiment settings and stimuli. Participant data and local "
    "recording/display setup are kept, with a backup of the previous version."
)
_UPDATE_DETAILS = (
    "Update this project's experiment settings and stimuli in the current folder. "
    "Keep participant data, local recording/display setup and a recoverable backup "
    "of the previous version. Review protocol changes before continuing an ongoing study."
)
_SEPARATE_GUIDANCE = (
    "The installed version is unknown. Set its version before updating this project, "
    "or download the new version separately."
)
_SEPARATE_DETAILS = (
    "Download the new version into a separate folder and review its changes before "
    "using it in an ongoing study. Your current project's edits and participant data "
    "stay in the existing folder."
)


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
        self._can_update = False
        self._known_installed_version = False
        self._can_download_separately = False
        self._linked = False
        self._linking = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)
        self.header = DialogHeader(project_name, "", parent=self)
        self.header.subtitle_label.hide()
        layout.addWidget(self.header)
        self.versions_label = QLabel(self)
        self.versions_label.setObjectName("project_version_summary")
        self.versions_label.setTextFormat(Qt.TextFormat.PlainText)
        self.versions_label.setWordWrap(True)
        self.versions_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.versions_label)
        self.auto_check_checkbox = QCheckBox(
            "Check for updates automatically", self,
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
        self.link_combo = QComboBox(self.link_panel)
        self.link_combo.setObjectName("project_version_link_item")
        self.link_combo.setMinimumWidth(0)
        self.link_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.link_combo.setMinimumContentsLength(20)
        self.link_combo.currentIndexChanged.connect(self._link_selection_changed)
        form.addRow("Library experiment", self.link_combo)
        self.installed_version_edit = QLineEdit(self.link_panel)
        self.installed_version_edit.setObjectName("project_version_installed_version")
        self.installed_version_edit.setPlaceholderText("Unknown")
        version_help = "Leave blank if the installed Library version is unknown."
        self.installed_version_edit.setToolTip(version_help)
        self.installed_version_edit.setAccessibleDescription(version_help)
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
        self.details.setAccessibleName("Library version details")
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(72)
        layout.addWidget(self.details, 1)
        self._details_layout = layout
        self._empty_details_index = layout.count()
        layout.addStretch(1)
        self.preservation_label = QLabel(_UPDATE_GUIDANCE, self)
        self.preservation_label.setToolTip(_UPDATE_DETAILS)
        self.preservation_label.setAccessibleDescription(_UPDATE_DETAILS)
        self.preservation_label.setTextFormat(Qt.TextFormat.PlainText)
        self.preservation_label.setWordWrap(True)
        self.preservation_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.preservation_label)
        self.status_label = QLabel(self)
        self.status_label.setObjectName("project_version_status")
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        buttons = QHBoxLayout()
        self.check_button = QPushButton("Check for updates", self)
        self.check_button.setObjectName("project_version_check_button")
        self.check_button.clicked.connect(lambda: self.action_requested.emit("check"))
        self.install_button = QPushButton("Download separately", self)
        self.install_button.setObjectName("project_version_install_button")
        self.install_button.setToolTip(_SEPARATE_DETAILS)
        self.install_button.setAccessibleDescription(_SEPARATE_DETAILS)
        self.install_button.clicked.connect(lambda: self.action_requested.emit("install"))
        self.update_button = QPushButton("Update current project", self)
        self.update_button.setObjectName("project_version_update_button")
        self.update_button.setToolTip(_UPDATE_DETAILS)
        self.update_button.setAccessibleDescription(_UPDATE_DETAILS)
        self.update_button.clicked.connect(lambda: self.action_requested.emit("update"))
        mark_primary_action(self.update_button)
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.setObjectName("project_version_cancel_button")
        self.cancel_button.clicked.connect(lambda: self.action_requested.emit("cancel"))
        self.close_button = QPushButton("Keep current version", self)
        self.close_button.setObjectName("project_version_keep_current_button")
        self.close_button.clicked.connect(self.reject)
        buttons.addWidget(self.check_button)
        buttons.addStretch(1)
        buttons.addWidget(self.install_button)
        buttons.addWidget(self.update_button)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)
        apply_dialog_theme(self)
        self.set_link_items([])
        self.set_state(installed_version=None, latest=None, linked=False, auto_check=True)

    def set_state(
        self, *, installed_version: str | None, latest: LibraryItem | None,
        linked: bool, auto_check: bool, status: str = "", can_install: bool = False,
        can_update: bool = False, can_download_separately: bool | None = None,
    ) -> None:
        self._linked = linked
        self._linking = False
        self._can_install = can_install
        self._can_update = can_update and can_install and linked and installed_version is not None
        self._known_installed_version = installed_version is not None
        self._can_download_separately = (
            can_install and (True if can_download_separately is None else can_download_separately)
        )
        current = installed_version or ("Unknown" if linked else "Not linked")
        newest = latest.version if latest is not None else "Not checked"
        self.versions_label.setText(
            f"Installed: {current}\nLatest: {newest}"
        )
        self.auto_check_checkbox.setChecked(auto_check)
        self.link_panel.setVisible(not linked or installed_version is None)
        self.details.setPlainText(
            f"{latest.title}\n"
            f"Requires FPVS Studio {latest.min_studio_version} or later.\n\n{latest.description}"
            if latest is not None else
            ""
        )
        self.status_label.setText(status)
        self._update_controls()

    def begin_linking(self) -> None:
        """Start an explicit replacement link without guessing its installed version."""
        self._linking = True
        self.link_panel.show()
        self.installed_version_edit.clear()
        self.link_combo.setCurrentIndex(0)
        self.details.clear()
        self.status_label.clear()
        self._update_controls()

    def set_link_items(self, items: Sequence[LibraryItem]) -> None:
        self.link_combo.clear()
        self.link_combo.addItem("Select experiment", None)
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
        self._can_update = False
        self._can_download_separately = False
        self._update_controls()

    def _link_selection_changed(self, *_args: object) -> None:
        item = self.selected_link_item()
        link_help = "Choose the Library experiment this project came from."
        self.link_combo.setToolTip(f"{item.title} ({item.item_id})" if item else link_help)
        self.link_combo.setAccessibleDescription(link_help)
        if not self._linked or self._linking:
            self.details.setPlainText(
                f"{item.title}\nLibrary version {item.version}\n\n{item.description}"
                if item is not None else ""
            )
        self._update_controls()

    def _update_controls(self) -> None:
        has_details = bool(self.details.toPlainText())
        self.details.setVisible(has_details)
        self._details_layout.setStretch(self._empty_details_index, 0 if has_details else 1)
        self.preservation_label.setVisible(self._can_install and not self._linking)
        self.preservation_label.setText(
            _UPDATE_GUIDANCE if self._known_installed_version else _SEPARATE_GUIDANCE
        )
        guidance = _UPDATE_DETAILS if self._known_installed_version else _SEPARATE_DETAILS
        self.preservation_label.setToolTip(guidance)
        self.preservation_label.setAccessibleDescription(guidance)
        self.status_label.setVisible(bool(self.status_label.text()))
        self.check_button.setEnabled(not self._busy)
        self.install_button.setEnabled(
            not self._busy and self._can_download_separately and not self._linking
        )
        self.update_button.setEnabled(not self._busy and self._can_update and not self._linking)
        self.update_button.setDefault(self.update_button.isEnabled())
        self.install_button.setDefault(
            not self.update_button.isEnabled() and self.install_button.isEnabled()
        )
        self.auto_check_checkbox.setEnabled(not self._busy and self._linked)
        self.auto_check_checkbox.setVisible(self._linked and not self._linking)
        self.relink_button.setVisible(self._linked and not self._linking)
        self.relink_button.setEnabled(not self._busy)
        self.link_combo.setEnabled(not self._busy)
        self.installed_version_edit.setEnabled(not self._busy)
        self.link_button.setEnabled(not self._busy and self.selected_link_item() is not None)
        self.cancel_button.setVisible(self._busy)
        self.close_button.setVisible(not self._busy)

    def reject(self) -> None:
        self.closing.emit()
        super().reject()
