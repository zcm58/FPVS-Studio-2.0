"""Nonmodal review surface for library project versions and explicit project linking."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal, Slot
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

from fpvs_studio.gui.components import (
    DialogHeader,
    apply_dialog_theme,
    mark_primary_action,
    mark_text_role,
)
from fpvs_studio.gui.design_system import elide_middle
from fpvs_studio.gui.update_progress import UpdateProgressBar
from fpvs_studio.library.models import LibraryItem

MINIMUM_SIZE = (640, 470)
DEFAULT_SIZE = (700, 500)

_UPDATE_GUIDANCE = (
    "Updating replaces experiment settings and stimuli, keeps participant data and local "
    "recording/display setup, and backs up the previous version. Review changes before "
    "continuing data collection."
)
_UPDATE_DETAILS = (
    "Update this project's experiment settings and stimuli in the current folder. "
    "Keep participant data, local recording/display setup and a recoverable backup "
    "of the previous version. Review protocol changes before continuing an ongoing study."
)
_SEPARATE_GUIDANCE = (
    "Enter the installed version to update in place, or download a separate copy."
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
        self.setMinimumSize(*MINIMUM_SIZE)
        self.resize(*DEFAULT_SIZE)
        self._busy = False
        self._show_progress = False
        self._can_install = False
        self._can_update = False
        self._can_remind = False
        self._known_installed_version = False
        self._can_download_separately = False
        self._linked = False
        self._linking = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        self.header = DialogHeader(project_name, "", parent=self)
        layout.addWidget(self.header)
        self._review = QWidget(self)
        review_layout = QVBoxLayout(self._review)
        review_layout.setContentsMargins(0, 0, 0, 0)
        review_layout.setSpacing(8)
        layout.addWidget(self._review, 1)
        self.versions_label = QLabel(self)
        self.versions_label.setObjectName("project_version_summary")
        self.versions_label.setTextFormat(Qt.TextFormat.PlainText)
        self.versions_label.setWordWrap(True)
        self.versions_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        mark_text_role(self.versions_label, "supporting")
        review_layout.addWidget(self.versions_label)
        self.auto_check_checkbox = QCheckBox(
            "Check automatically", self,
        )
        self.auto_check_checkbox.setObjectName("project_version_auto_check")
        self.auto_check_checkbox.clicked.connect(
            lambda _checked: self.action_requested.emit("set_auto")
        )
        self.relink_button = QPushButton("Change library link...", self)
        self.relink_button.setObjectName("project_version_relink_button")
        self.relink_button.clicked.connect(lambda: self.action_requested.emit("relink"))
        self.check_button = QPushButton("Check again", self)
        self.check_button.setObjectName("project_version_check_button")
        self.check_button.clicked.connect(lambda: self.action_requested.emit("check"))
        review_actions = QHBoxLayout()
        review_actions.addWidget(self.auto_check_checkbox)
        review_actions.addStretch(1)
        review_actions.addWidget(self.relink_button)
        review_actions.addWidget(self.check_button)
        review_layout.addLayout(review_actions)

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
        review_layout.addWidget(self.link_panel)

        self.details_heading = QLabel("Release details", self)
        mark_text_role(self.details_heading, "sectionTitle")
        review_layout.addWidget(self.details_heading)

        self.details = QTextEdit(self)
        self.details.setObjectName("project_version_details")
        self.details.setAccessibleName("Library version details")
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(64)
        review_layout.addWidget(self.details, 1)
        self._details_layout = review_layout
        self._empty_details_index = review_layout.count()
        review_layout.addStretch(1)
        self.preservation_label = QLabel(_UPDATE_GUIDANCE, self)
        self.preservation_label.setToolTip(_UPDATE_DETAILS)
        self.preservation_label.setAccessibleDescription(_UPDATE_DETAILS)
        self.preservation_label.setTextFormat(Qt.TextFormat.PlainText)
        self.preservation_label.setWordWrap(True)
        self.preservation_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        review_layout.addWidget(self.preservation_label)
        self.status_label = QLabel(self)
        self.status_label.setObjectName("project_version_status")
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        review_layout.addWidget(self.status_label)
        self._activity = QWidget(self)
        activity_layout = QVBoxLayout(self._activity)
        activity_layout.setContentsMargins(0, 0, 0, 0)
        activity_layout.setSpacing(8)
        activity_layout.addStretch(1)
        self.progress_label = QLabel(self._activity)
        self.progress_label.setWordWrap(True)
        self.progress_label.setTextFormat(Qt.TextFormat.PlainText)
        mark_text_role(self.progress_label, "sectionTitle")
        activity_layout.addWidget(self.progress_label)
        self.progress_bar = UpdateProgressBar(self._activity, animate_download=True)
        self.progress_bar.setObjectName("project_version_progress")
        self.progress_bar.setAccessibleName("Project version transfer progress")
        activity_layout.addWidget(self.progress_bar)
        activity_layout.addStretch(1)
        layout.addWidget(self._activity, 1)
        buttons = QHBoxLayout()
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
        self.close_button = QPushButton("Close", self)
        self.close_button.setObjectName("project_version_keep_current_button")
        self.close_button.clicked.connect(self.reject)
        self.remind_button = QPushButton("Remind me later", self)
        self.remind_button.setObjectName("project_version_remind_button")
        self.remind_button.clicked.connect(lambda: self.action_requested.emit("remind"))
        reminder_help = "Offer this version again after 30 minutes while this project is open."
        self.remind_button.setToolTip(reminder_help)
        self.remind_button.setAccessibleDescription(reminder_help)
        buttons.addWidget(self.close_button)
        buttons.addWidget(self.remind_button)
        buttons.addStretch(1)
        buttons.addWidget(self.install_button)
        buttons.addWidget(self.update_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)
        apply_dialog_theme(self)
        self.set_link_items([])
        self.set_state(installed_version=None, latest=None, linked=False, auto_check=True)

    def set_state(
        self, *, installed_version: str | None, latest: LibraryItem | None,
        linked: bool, auto_check: bool, status: str = "", can_install: bool = False,
        can_update: bool = False, can_download_separately: bool | None = None,
        can_remind: bool = False,
    ) -> None:
        self._linked = linked
        self._linking = False
        self._can_install = can_install
        self._can_update = can_update and can_install and linked and installed_version is not None
        self._can_remind = can_remind and auto_check
        self._known_installed_version = installed_version is not None
        self._can_download_separately = (
            can_install and (True if can_download_separately is None else can_download_separately)
        )
        current = installed_version or "unknown"
        summary = f"Installed {elide_middle(current, 36)}" if linked else ""
        full_summary = f"Installed {current}" if linked else ""
        if latest is not None and latest.version != installed_version:
            summary += f"  ·  Library {elide_middle(latest.version, 36)}"
            full_summary += f"  ·  Library {latest.version}"
        self.versions_label.setText(summary)
        full_value = full_summary if summary != full_summary else ""
        self.versions_label.setToolTip(full_value)
        self.versions_label.setAccessibleDescription(full_value)
        self.auto_check_checkbox.setChecked(auto_check)
        self.link_panel.setVisible(not linked or installed_version is None)
        details = ""
        if latest is not None:
            details = f"Requires FPVS Studio {latest.min_studio_version} or later."
            if latest.title != self.header.title_label.text():
                details = f"{latest.title}\n{details}"
            if latest.description.strip():
                details += f"\n\n{latest.description}"
        self.details.setPlainText(details)
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

    def set_busy(self, busy: bool, status: str = "", *, show_progress: bool = False) -> None:
        self._busy = busy
        self._show_progress = busy and show_progress
        if self._show_progress:
            self.set_progress_stage(status)
        elif status:
            self.status_label.setText(status)
        self._update_controls()
        if self._show_progress:
            self.cancel_button.setFocus()

    @Slot(object, object)
    def set_download_progress(self, received: object, total: object) -> None:
        if not self._show_progress or not isinstance(received, int):
            return
        total_bytes = total if isinstance(total, int) else None
        self.progress_label.setText(
            "Verifying download…" if total_bytes and received >= total_bytes
            else "Downloading project files…"
        )
        self.progress_bar.set_byte_progress(received, total_bytes)

    def set_progress_stage(self, status: str) -> None:
        if self._show_progress:
            self.progress_label.setText(status)
            self.progress_bar.setRange(0, 0)

    def clear_install_candidate(self) -> None:
        """Require a successful fresh check before offering another installation."""
        self._can_install = False
        self._can_update = False
        self._can_remind = False
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
        self._review.setVisible(not self._show_progress)
        self._activity.setVisible(self._show_progress)
        self.versions_label.setVisible(bool(self.versions_label.text()) and not self._linking)
        self.details_heading.setText(
            "Library experiment" if not self._linked or self._linking else "Release details"
        )
        self.details_heading.setVisible(has_details)
        self.details.setVisible(has_details)
        self._details_layout.setStretch(self._empty_details_index, 0 if has_details else 1)
        self.preservation_label.setVisible(
            not self._linking and (
                self._can_update or (self._can_install and not self._known_installed_version)
            )
        )
        self.preservation_label.setText(
            _UPDATE_GUIDANCE if self._known_installed_version else _SEPARATE_GUIDANCE
        )
        guidance = _UPDATE_DETAILS if self._known_installed_version else _SEPARATE_DETAILS
        self.preservation_label.setToolTip(guidance)
        self.preservation_label.setAccessibleDescription(guidance)
        self.status_label.setVisible(bool(self.status_label.text()))
        self.check_button.setEnabled(not self._busy)
        show_install = self._can_download_separately and not self._linking
        show_update = self._can_update and not self._linking
        self.install_button.setEnabled(not self._busy and show_install)
        self.update_button.setEnabled(not self._busy and show_update)
        self.install_button.setVisible(not self._show_progress and show_install)
        self.update_button.setVisible(not self._show_progress and show_update)
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
        can_remind = self._can_remind and not self._linking
        self.remind_button.setVisible(not self._busy and can_remind)
        self.close_button.setVisible(not self._busy and not can_remind)

    def reject(self) -> None:
        self.closing.emit()
        super().reject()
