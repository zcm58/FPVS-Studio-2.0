"""Opt-in experiment reporting and aggregate fixation comparison surface."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.data_sharing.storage import CaptureArchiveReview
from fpvs_studio.gui.components import (
    DialogHeader,
    apply_dialog_theme,
    mark_primary_action,
    mark_secondary_action,
)


@dataclass(frozen=True)
class ComparisonRow:
    """Already formatted backend metrics; widgets do not score results."""

    condition: str
    condition_id: str
    local: str
    shared: str


class DataSharingDialog(QDialog):
    action_requested = Signal(str)
    enabled_requested = Signal(bool)
    closing = Signal()

    def __init__(self, *, configured: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("data_sharing_dialog")
        self.setWindowTitle("Data Sharing & Comparison")
        self.setMinimumSize(820, 480)
        self.resize(880, 540)
        self._configured = configured
        self._connected = False
        self._enabled = False
        self._loaded = False
        self._busy = False
        self._updating = False
        self._project_url = ""
        self._reviewable_captures = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)
        self.header = DialogHeader(
            "Data Sharing & Comparison", "", parent=self,
        )
        self.header.subtitle_label.hide()
        layout.addWidget(self.header)
        self.tabs = QTabWidget(self)
        sharing_page = QWidget(self.tabs)
        sharing_layout = QVBoxLayout(sharing_page)
        sharing_layout.setContentsMargins(12, 12, 12, 12)
        sharing_layout.setSpacing(8)
        comparison_page = QWidget(self.tabs)
        comparison_layout = QVBoxLayout(comparison_page)
        comparison_layout.setContentsMargins(12, 12, 12, 12)
        comparison_layout.setSpacing(8)
        self.tabs.addTab(sharing_page, "Sharing")
        self.tabs.addTab(comparison_page, "Comparison")
        self.profile_label = self._label("No experiment enrollment. Sharing is off.")
        self.profile_label.setObjectName("sharing_profile")
        sharing_layout.addWidget(self.profile_label)
        self.project_id_edit = QLineEdit(self)
        self.project_id_edit.setObjectName("sharing_project_id")
        self.project_id_edit.setPlaceholderText("OpenFPVS project ID")
        self.project_id_edit.setToolTip("Copy the project ID from the OpenFPVS project page.")
        self.project_id_edit.setAccessibleName("OpenFPVS project ID")
        self.project_id_edit.setMaxLength(36)
        sharing_layout.addWidget(self.project_id_edit)
        self.enabled_checkbox = QCheckBox(
            "Automatically share completed sessions", self,
        )
        self.enabled_checkbox.setObjectName("sharing_enabled")
        self.enabled_checkbox.toggled.connect(self._enabled_changed)
        sharing_layout.addWidget(self.enabled_checkbox)
        self.enabled_checkbox.setToolTip(
            "Share newly completed sessions for this experiment. Turning sharing off pauses "
            "unsent reports; Retry pending resumes them explicitly.\n\n"
            "Private reports include experiment/version, protocol fingerprint, random report ID, "
            "Studio version, completion time, condition IDs/order, fixation targets/hits/misses/"
            "false alarms/accuracy, mean response time and observation count, scoring method, "
            "refresh rate and response window. No participant IDs, demographics, raw EEG or "
            "individual answers. You see aggregate comparison only."
        )
        connection = QHBoxLayout()
        connection.setSpacing(8)
        self.invitation_edit = QLineEdit(self)
        self.invitation_edit.setObjectName("sharing_invitation_code")
        self.invitation_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.invitation_edit.setPlaceholderText("Lab-issued invitation code")
        self.invitation_edit.setAccessibleName("Lab-issued invitation code")
        self.invitation_edit.setMaxLength(128)
        self.invitation_edit.textChanged.connect(self._update_controls)
        connection.addWidget(self.invitation_edit, 1)
        self.connect_button = QPushButton("Connect", self)
        self.connect_button.setObjectName("sharing_connect")
        self.connect_button.setAutoDefault(False)
        self.connect_button.setToolTip("Connecting does not enable sharing or upload old sessions.")
        self.connect_button.clicked.connect(lambda: self.action_requested.emit("connect"))
        mark_primary_action(self.connect_button)
        connection.addWidget(self.connect_button)
        self.disconnect_button = QPushButton("Revoke access", self)
        self.disconnect_button.setObjectName("sharing_disconnect")
        self.disconnect_button.setToolTip("Revoking access leaves received reports with the owner.")
        self.disconnect_button.clicked.connect(lambda: self.action_requested.emit("disconnect"))
        mark_secondary_action(self.disconnect_button)
        connection.addWidget(self.disconnect_button)
        self.archive_button = QPushButton("Archive uploaded history", self)
        self.archive_button.setObjectName("sharing_archive")
        self.archive_button.setToolTip(
            "Archive older accepted upload history locally to make room for new contributions. "
            "Research records and shared results remain available; the latest comparison is kept."
        )
        self.archive_button.clicked.connect(lambda: self.action_requested.emit("archive"))
        mark_secondary_action(self.archive_button)
        connection.addWidget(self.archive_button)
        sharing_layout.addLayout(connection)
        project_actions = QHBoxLayout()
        self.protocol_button = QPushButton("Copy protocol fingerprint", self)
        self.protocol_button.setToolTip(
            "Copy the current protocol for the administrator to enable this project."
        )
        self.protocol_button.clicked.connect(lambda: self.action_requested.emit("protocol"))
        mark_secondary_action(self.protocol_button)
        project_actions.addWidget(self.protocol_button)
        self.website_button = QPushButton("View OpenFPVS project", self)
        self.website_button.clicked.connect(lambda: self.action_requested.emit("website"))
        mark_secondary_action(self.website_button)
        project_actions.addWidget(self.website_button)
        self.review_captures_button = QPushButton("Review captures…", self)
        self.review_captures_button.setObjectName("sharing_review_captures")
        self.review_captures_button.setToolTip(
            "Review excluded sessions before archiving their local reporting evidence. "
            "Research results, queued reports and captures needing recovery are preserved."
        )
        self.review_captures_button.clicked.connect(lambda: self.action_requested.emit("review"))
        mark_secondary_action(self.review_captures_button)
        project_actions.addWidget(self.review_captures_button)
        project_actions.addStretch(1)
        sharing_layout.addLayout(project_actions)
        sharing_layout.addStretch(1)
        self.status_label = self._label(
            "Sharing service is not configured. Local results remain available."
            if not configured else "Loading this experiment's sharing settings…"
        )
        self.status_label.setObjectName("sharing_status")
        layout.addWidget(self.status_label)
        self.counts_label = self._label("Pending: 0 · Held: 0 · Retained uploaded: 0")
        self.counts_label.setObjectName("sharing_counts")
        layout.addWidget(self.counts_label)
        layout.addWidget(self.tabs, 1)
        self.comparison_table = QTableWidget(0, 3, self)
        self.comparison_table.setObjectName("sharing_comparison_table")
        self.comparison_table.setHorizontalHeaderLabels(
            ["Condition", "Latest local session", "Shared dataset"]
        )
        self.comparison_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.comparison_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.comparison_table.setWordWrap(True)
        self.comparison_table.setMinimumHeight(125)
        self.comparison_table.verticalHeader().hide()
        self.comparison_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.comparison_table.setAccessibleName("Fixation task accuracy comparison by condition")
        comparison_layout.addWidget(self.comparison_table, 1)
        self.comparison_notice = self._label("")
        self.comparison_notice.setObjectName("sharing_comparison_notice")
        comparison_layout.addWidget(self.comparison_notice)
        self.set_comparison(
            [], scope="Local: latest eligible completed session. Shared: matching protocol.",
            notice="", details="Shared accuracy needs at least 10 session reports from "
            "3 device enrollments per condition. This is task performance; "
            "it does not measure EEG quality.",
        )
        footer = QHBoxLayout()
        self.retry_button = QPushButton("Retry pending / refresh", self)
        self.retry_button.setObjectName("sharing_retry")
        self.retry_button.setToolTip("Resume held reports explicitly and refresh the comparison.")
        self.retry_button.clicked.connect(lambda: self.action_requested.emit("retry"))
        mark_secondary_action(self.retry_button)
        footer.addWidget(self.retry_button)
        footer.addStretch(1)
        self.cancel_button = QPushButton("Cancel operation", self)
        self.cancel_button.setObjectName("sharing_cancel")
        self.cancel_button.clicked.connect(lambda: self.action_requested.emit("cancel"))
        footer.addWidget(self.cancel_button)
        self.close_button = QPushButton("Close", self)
        self.close_button.clicked.connect(self.close)
        footer.addWidget(self.close_button)
        layout.addLayout(footer)
        apply_dialog_theme(self)
        self._update_controls()

    def _label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        return label

    def invitation_code(self) -> str:
        return self.invitation_edit.text().strip()

    def clear_invitation(self) -> None:
        self.invitation_edit.clear()

    def project_id(self) -> str:
        return self.project_id_edit.text().strip()

    def set_project_url(self, url: str) -> None:
        self._project_url = url
        self._update_controls()

    def set_state(
        self, *, connected: bool, enabled: bool, profile: str, status: str,
        pending: int = 0, held: int = 0, uploaded: int = 0,
        captures: int = 0, capture_limit: int = 512, reviewable_captures: int = 0,
    ) -> None:
        self._connected, self._enabled = connected, enabled
        self._loaded = True
        self._reviewable_captures = reviewable_captures
        self._updating = True
        self.enabled_checkbox.setChecked(enabled)
        self._updating = False
        self.profile_label.setText(profile.partition("\n")[0])
        self.profile_label.setToolTip(profile)
        self.status_label.setText(status)
        self.counts_label.setText(
            f"Pending: {pending:,} · Held: {held:,} · Retained uploaded: {uploaded:,} "
            f"· Captures: {captures:,}/{capture_limit:,}"
        )
        self.counts_label.setToolTip(
            "Uploaded counts the retained local comparison cache. Older accepted reports "
            "are archived locally; their cloud contributions remain."
            " Active captures include excluded and unfinished sessions. Review captures "
            "archives only confirmed excluded evidence to free capture capacity."
        )
        self._update_controls()

    def confirm_capture_archive(self, review: CaptureArchiveReview) -> bool:
        reasons = "\n".join(
            f"{reason.replace('_', ' ').capitalize()}: {count:,}"
            for reason, count in review.reason_counts
        )
        answer = QMessageBox.question(
            self, "Archive excluded captures?",
            f"Archive {len(review.captures):,} excluded capture(s) from this experiment's "
            f"local reporting history?\n\n{reasons}\n\n"
            "These sessions were not eligible for sharing. Their evidence will be kept "
            "in the local archive. Research results, queued reports, accepted receipts "
            "and captures needing recovery stay unchanged.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def set_comparison(
        self, rows: Sequence[ComparisonRow], *, scope: str, notice: str, details: str,
    ) -> None:
        self.comparison_table.setToolTip(f"{scope}\n\n{details}")
        for column, tooltip in ((1, scope), (2, f"{scope}\n\n{details}")):
            header = self.comparison_table.horizontalHeaderItem(column)
            assert header is not None
            header.setToolTip(tooltip)
        self.comparison_notice.setText(notice)
        self.comparison_notice.setVisible(bool(notice))
        self.comparison_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            for column, value in enumerate((row.condition, row.local, row.shared)):
                item = QTableWidgetItem(value)
                item.setToolTip(
                    f"{row.condition}\nCondition ID: {row.condition_id}"
                    if column == 0 else value
                )
                self.comparison_table.setItem(index, column, item)
        self.comparison_table.resizeRowsToContents()

    def set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        if message:
            self.status_label.setText(message)
        self._update_controls()

    def _update_controls(self) -> None:
        ready = self._configured and not self._busy
        self.profile_label.setVisible(self._connected)
        self.project_id_edit.setEnabled(ready and not self._connected)
        self.protocol_button.setEnabled(not self._busy)
        self.website_button.setEnabled(not self._busy and bool(self._project_url))
        self.invitation_edit.setEnabled(ready and not self._connected)
        self.connect_button.setEnabled(
            ready and not self._connected and bool(self.invitation_code())
        )
        self.disconnect_button.setEnabled(not self._busy and self._connected)
        self.enabled_checkbox.setEnabled(
            self._connected and (not self._busy or self._enabled)
            and (self._configured or self._enabled)
        )
        self.retry_button.setEnabled(ready and self._connected and self._enabled)
        self.archive_button.setEnabled(not self._busy and self._loaded)
        self.review_captures_button.setEnabled(
            not self._busy and self._loaded and self._reviewable_captures > 0
        )
        self.cancel_button.setVisible(self._busy)

    def _enabled_changed(self, enabled: bool) -> None:
        if not self._updating:
            self.enabled_requested.emit(enabled)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.closing.emit()
        event.accept()

    def reject(self) -> None:
        self.close()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange):
            if not getattr(self, "_refreshing_theme", False):
                self._refreshing_theme = True
                try:
                    apply_dialog_theme(self)
                finally:
                    self._refreshing_theme = False
