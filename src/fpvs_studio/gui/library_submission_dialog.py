"""Compact whole-project upload and read-only review status surface."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.components import (
    DialogHeader,
    apply_dialog_theme,
    mark_primary_action,
)


class LibrarySubmissionDialog(QDialog):
    action_requested = Signal(str)
    closing = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("library_submission_dialog")
        self.setWindowTitle("Upload Project for Review")
        self.setMinimumSize(760, 600)
        self.resize(820, 660)
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        header = DialogHeader("Upload Project for Review", "", parent=self)
        header.subtitle_label.hide()
        layout.addWidget(header)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs, 1)
        page = QWidget(self)
        body = QVBoxLayout(page)
        self.form = QWidget(page)
        form = QFormLayout(self.form)
        self.title_edit = QLineEdit(self.form)
        self.title_edit.setToolTip("Library titles may contain up to 160 characters.")
        self.author_edit = QLineEdit(self.form)
        self.author_edit.setMaxLength(200)
        self.email_edit = QLineEdit(self.form)
        self.email_edit.setMaxLength(254)
        self.description = QPlainTextEdit(self.form)
        self.description.setMaximumHeight(85)
        self.description.setToolTip(
            "Purpose, protocol and stimulus source; up to 4,000 characters."
        )
        for label, widget in (
            ("Project title", self.title_edit),
            ("Your name", self.author_edit),
            ("Contact email", self.email_edit),
            ("Description", self.description),
        ):
            form.addRow(label, widget)
        body.addWidget(self.form)
        self.rights = QCheckBox("I have permission to share this project.", page)
        self.rights.setToolTip(
            "I confirm that I may distribute all included stimuli and authored materials "
            "through the Experiment Library."
        )
        body.addWidget(self.rights)
        self.rights.setToolTip(
            self.rights.toolTip()
            + " "
            + "Participant data, results, logs and local credentials are excluded. "
            "Review authored text and images for identifying information before submitting. "
            "Maximum bundle size: 64 MiB.",
        )
        self.review = QPlainTextEdit(page)
        self.review.setReadOnly(True)
        self.review.setAccessibleName("Prepared submission inventory")
        body.addStretch()
        actions = QHBoxLayout()
        self.buttons: dict[str, QPushButton] = {}
        for action, label in (
            ("submit", "Upload for Review"),
            ("new", "New Upload"),
        ):
            control = QPushButton(label, page)
            control.setObjectName(f"submission_{action}")
            control.clicked.connect(
                lambda _checked=False, value=action: self.action_requested.emit(value)
            )
            actions.addWidget(control)
            self.buttons[action] = control
        mark_primary_action(self.buttons["submit"])
        actions.addStretch()
        body.addLayout(actions)
        self.tabs.addTab(page, "Project")
        history = QWidget(self)
        history_layout = QVBoxLayout(history)
        self.history = QPlainTextEdit(history)
        self.history.setReadOnly(True)
        self.history.setAccessibleName("Submission decisions for this computer")
        history_layout.addWidget(self.history)
        refresh = QPushButton("Refresh", history)
        refresh.clicked.connect(lambda: self.action_requested.emit("refresh"))
        self.buttons["refresh"] = refresh
        history_layout.addWidget(refresh)
        linking = QHBoxLayout()
        self.link_upload = QComboBox(history)
        self.link_upload.setObjectName("submission_link_upload")
        self.link_upload.setAccessibleName("Upload to link to your OpenFPVS account")
        self.link_upload.setPlaceholderText("Select an upload to link")
        self.link_upload.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.link_upload.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.link_upload.currentIndexChanged.connect(self._sync_link_action)
        linking.addWidget(self.link_upload, 1)
        link = QPushButton("Copy Linking Code", history)
        link.setToolTip("Paste the code in My experiments on your OpenFPVS account page.")
        link.clicked.connect(lambda: self.action_requested.emit("link"))
        self.buttons["link"] = link
        linking.addWidget(link)
        history_layout.addLayout(linking)
        self.tabs.addTab(history, "My Uploads")
        details = QWidget(self)
        details_layout = QVBoxLayout(details)
        details_layout.addWidget(self.review)
        self.tabs.addTab(details, "Files")
        self.status = QLabel("", self)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        footer = QHBoxLayout()
        footer.addStretch()
        cancel = QPushButton("Cancel Upload", self)
        cancel.clicked.connect(lambda: self.action_requested.emit("cancel"))
        self.buttons["cancel"] = cancel
        close = QPushButton("Close", self)
        close.clicked.connect(self.close)
        footer.addWidget(cancel)
        footer.addWidget(close)
        layout.addLayout(footer)
        self._busy: bool = False
        self._prepared: bool = False
        self._attempted: bool = False
        self._completed: bool = False
        self.rights.toggled.connect(
            lambda: self.set_state(self._busy, self._prepared, self._attempted, self._completed)
        )
        self.set_state(False, False, False)
        apply_dialog_theme(self)

    def set_state(
        self, busy: bool, prepared: bool, attempted: bool, completed: bool = False
    ) -> None:
        self._busy, self._prepared, self._attempted = busy, prepared, attempted
        self._completed = completed
        self.form.setEnabled(not busy and not prepared)
        self.rights.setEnabled(not busy and not attempted)
        self.buttons["submit"].setEnabled(not busy and not completed and self.rights.isChecked())
        self.buttons["submit"].setText(
            "Retry Upload" if attempted and not completed else "Upload for Review"
        )
        self.buttons["new"].setEnabled(not busy and prepared)
        self.buttons["refresh"].setEnabled(not busy)
        self.buttons["cancel"].setEnabled(busy)
        self._sync_link_action()

    def set_linkable_uploads(self, uploads: list[tuple[str, str]]) -> None:
        selected = self.link_upload.currentData()
        self.link_upload.clear()
        for submission_id, title in uploads:
            self.link_upload.addItem(title, submission_id)
            self.link_upload.setItemData(
                self.link_upload.count() - 1, title, Qt.ItemDataRole.ToolTipRole,
            )
        self.link_upload.setCurrentIndex(self.link_upload.findData(selected) if selected else -1)
        self._sync_link_action()

    def _sync_link_action(self) -> None:
        self.link_upload.setToolTip(self.link_upload.currentText())
        self.link_upload.setEnabled(not self._busy and self.link_upload.count() > 0)
        self.buttons["link"].setEnabled(not self._busy and self.link_upload.currentIndex() >= 0)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.closing.emit()
        super().closeEvent(event)
