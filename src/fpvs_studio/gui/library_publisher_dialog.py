"""Developer-only review surface for explicitly publishing the open experiment."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio import __version__
from fpvs_studio.developer.library_publisher import PublicationRequest
from fpvs_studio.gui.components import (
    DialogHeader,
    apply_dialog_theme,
    mark_primary_action,
    mark_secondary_action,
)


class LibraryPublisherDialog(QDialog):
    """Prepare locally, review the exact artifact, then publish on an explicit click."""

    action_requested = Signal(str)
    closing = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("library_publisher_dialog")
        self.setWindowTitle("Publish to Experiment Library")
        self.setMinimumSize(860, 680)
        self.resize(940, 760)
        self.setModal(True)
        self._busy = False
        self._access = False
        self._prepared = False
        self._published = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(
            DialogHeader(
                "Publish to Experiment Library",
                "Prepare a local copy, review its contents, "
                "then publish it to the private library.",
                parent=self,
            )
        )
        self.access_label = QLabel("Checking developer publishing access…", self)
        self.access_label.setTextFormat(Qt.TextFormat.PlainText)
        self.access_label.setWordWrap(True)
        self.access_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.access_label)
        self.form = QWidget(self)
        form_layout = QFormLayout(self.form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setVerticalSpacing(8)
        self.title_edit = QLineEdit(self.form)
        self.title_edit.setObjectName("publisher_title")
        self.title_edit.setMaxLength(160)
        self.item_id_edit = QLineEdit(self.form)
        self.item_id_edit.setObjectName("publisher_item_id")
        self.item_id_edit.setMaxLength(80)
        self.item_id_edit.setToolTip(
            "Stable library ID using lowercase letters, digits and hyphens."
        )
        self.version_edit = QLineEdit("1.0.0", self.form)
        self.version_edit.setObjectName("publisher_version")
        self.version_edit.setMaxLength(64)
        self.minimum_version_edit = QLineEdit(__version__, self.form)
        self.minimum_version_edit.setObjectName("publisher_minimum_version")
        self.minimum_version_edit.setMaxLength(64)
        self.summary_edit = QPlainTextEdit(self.form)
        self.summary_edit.setObjectName("publisher_summary")
        self.summary_edit.setAccessibleName("Library description")
        self.summary_edit.setPlaceholderText(
            "Describe the experiment for people browsing the library."
        )
        self.summary_edit.setTabChangesFocus(True)
        self.summary_edit.setFixedHeight(76)
        versions = QHBoxLayout()
        versions.addWidget(self.version_edit, 1)
        minimum_label = QLabel("Minimum Studio version", self.form)
        minimum_label.setBuddy(self.minimum_version_edit)
        versions.addWidget(minimum_label)
        versions.addWidget(self.minimum_version_edit, 1)
        form_layout.addRow("Title", self.title_edit)
        form_layout.addRow("Library ID", self.item_id_edit)
        form_layout.addRow("Version", versions)
        form_layout.addRow("Description", self.summary_edit)
        layout.addWidget(self.form)
        self.review_edit = QPlainTextEdit(self)
        self.review_edit.setObjectName("publisher_review")
        self.review_edit.setAccessibleName("Prepared bundle review")
        self.review_edit.setReadOnly(True)
        self.review_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.review_edit.setMinimumHeight(130)
        self.review_edit.setPlainText(
            "Prepare a bundle to inspect included and omitted files, "
            "sanitized fields and SHA-256.\n"
            "Preparing saves the current experiment and creates a local copy. Nothing is uploaded."
        )
        layout.addWidget(self.review_edit, 1)
        self.status_label = QLabel("", self)
        self.status_label.setObjectName("publisher_status")
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.status_label)
        actions = QHBoxLayout()
        self.access_button = QPushButton("Check access", self)
        self.edit_button = QPushButton("Edit and prepare again", self)
        self.cancel_button = QPushButton("Cancel operation", self)
        self.close_button = QPushButton("Close", self)
        self.prepare_button = QPushButton("Prepare bundle", self)
        self.publish_button = QPushButton("Publish to library", self)
        for button, action in (
            (self.access_button, "access"),
            (self.edit_button, "edit"),
            (self.cancel_button, "cancel"),
            (self.prepare_button, "prepare"),
            (self.publish_button, "publish"),
        ):
            button.clicked.connect(
                lambda _checked=False, value=action: self.action_requested.emit(value)
            )
            mark_secondary_action(button)
        mark_primary_action(self.prepare_button)
        mark_primary_action(self.publish_button)
        mark_secondary_action(self.close_button)
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.access_button)
        actions.addWidget(self.edit_button)
        actions.addWidget(self.cancel_button)
        actions.addStretch(1)
        actions.addWidget(self.close_button)
        actions.addWidget(self.prepare_button)
        actions.addWidget(self.publish_button)
        layout.addLayout(actions)
        for edit in (
            self.title_edit,
            self.item_id_edit,
            self.version_edit,
            self.minimum_version_edit,
        ):
            edit.textChanged.connect(self._sync_actions)
        self.summary_edit.textChanged.connect(self._sync_actions)
        self._sync_actions()
        apply_dialog_theme(self)

    def set_context(self, *, title: str, item_id: str) -> None:
        self.title_edit.setText(title)
        self.item_id_edit.setText(item_id)

    def request(self) -> PublicationRequest:
        return PublicationRequest(
            item_id=self.item_id_edit.text().strip(),
            title=self.title_edit.text().strip(),
            version=self.version_edit.text().strip(),
            summary=self.summary_edit.toPlainText().strip(),
            minimum_studio_version=self.minimum_version_edit.text().strip(),
        )

    def set_access(self, allowed: bool, message: str) -> None:
        self._access = allowed
        self.access_label.setText(message)
        self._sync_actions()

    def set_prepared(self, prepared: bool, review: str = "") -> None:
        self._prepared = prepared
        self._published = False
        self.publish_button.setText("Publish to library")
        if review:
            self.review_edit.setPlainText(review)
        elif not prepared:
            self.review_edit.clear()
        self._sync_actions()

    def set_published(self) -> None:
        self._published = True
        self._sync_actions()

    def set_busy(self, busy: bool, message: str) -> None:
        self._busy = busy
        self.status_label.setText(message)
        self.cancel_button.setEnabled(busy)
        self._sync_actions()

    def _sync_actions(self, *_args: object) -> None:
        filled = all(
            edit.text().strip()
            for edit in (
                self.title_edit,
                self.item_id_edit,
                self.version_edit,
                self.minimum_version_edit,
            )
        ) and bool(self.summary_edit.toPlainText().strip())
        self.form.setEnabled(not self._busy and not self._prepared)
        self.access_button.setVisible(not self._access and not self._busy)
        self.edit_button.setVisible(self._prepared and not self._busy)
        self.cancel_button.setVisible(self._busy)
        self.prepare_button.setVisible(not self._prepared)
        self.prepare_button.setEnabled(not self._busy and self._access and filled)
        self.publish_button.setVisible(self._prepared)
        self.publish_button.setEnabled(
            self._prepared and not self._busy and self._access and not self._published
        )

    def reject(self) -> None:
        self.closing.emit()
        if not self._busy:
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._busy:
            self.closing.emit()
            event.ignore()
            return
        super().closeEvent(event)
