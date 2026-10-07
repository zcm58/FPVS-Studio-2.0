"""Explicit selected-condition submission and read-only review status surface."""

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
    mark_secondary_action,
)


class LibrarySubmissionDialog(QDialog):
    action_requested = Signal(str)
    closing = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("library_submission_dialog")
        self.setWindowTitle("Request Library publication")
        self.setMinimumSize(860, 740)
        self.resize(940, 800)
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(
            DialogHeader(
                "Request Library publication",
                "Submit one condition for administrator review. "
                "Only the reviewed bundle can be published.",
                parent=self,
            )
        )
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs, 1)
        page = QWidget(self)
        body = QVBoxLayout(page)
        self.form = QWidget(page)
        form = QFormLayout(self.form)
        self.conditions = QComboBox(self.form)
        self.conditions.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.conditions.setMinimumContentsLength(20)
        self.conditions.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.conditions.currentIndexChanged.connect(
            lambda: self.conditions.setToolTip(self.conditions.currentText())
        )
        self.title_edit = QLineEdit(self.form)
        self.title_edit.setMaxLength(160)
        self.author_edit = QLineEdit(self.form)
        self.author_edit.setMaxLength(200)
        self.email_edit = QLineEdit(self.form)
        self.email_edit.setMaxLength(254)
        self.description = QPlainTextEdit(self.form)
        self.description.setMaximumHeight(85)
        self.description.setPlaceholderText(
            "Purpose, protocol and stimulus source (up to 4,000 characters)"
        )
        for label, widget in (
            ("Condition", self.conditions),
            ("Library title", self.title_edit),
            ("Your name", self.author_edit),
            ("Contact email", self.email_edit),
            ("Description", self.description),
        ):
            form.addRow(label, widget)
        body.addWidget(self.form)
        self.rights = QCheckBox(
            "I have permission to share these stimuli and authored materials.", page
        )
        self.rights.setToolTip(
            "I confirm that I may distribute all included stimuli and authored materials "
            "through the Experiment Library."
        )
        body.addWidget(self.rights)
        notice = QLabel(
            "Participant data, results, logs and local credentials are excluded. "
            "Review authored text and images for identifying information before submitting. "
            "Maximum bundle size: 64 MiB.",
            page,
        )
        notice.setWordWrap(True)
        notice.setTextFormat(Qt.TextFormat.PlainText)
        body.addWidget(notice)
        self.review = QPlainTextEdit(page)
        self.review.setReadOnly(True)
        self.review.setAccessibleName("Prepared submission inventory")
        body.addWidget(self.review, 1)
        actions = QHBoxLayout()
        self.buttons: dict[str, QPushButton] = {}
        for action, label in (
            ("prepare", "Prepare condition"),
            ("submit", "Submit for review"),
            ("new", "New submission"),
        ):
            control = QPushButton(label, page)
            control.setObjectName(f"submission_{action}")
            control.clicked.connect(
                lambda _checked=False, value=action: self.action_requested.emit(value)
            )
            actions.addWidget(control)
            self.buttons[action] = control
        mark_primary_action(self.buttons["submit"])
        mark_secondary_action(self.buttons["prepare"])
        actions.addStretch()
        body.addLayout(actions)
        self.tabs.addTab(page, "Submit a condition")
        history = QWidget(self)
        history_layout = QVBoxLayout(history)
        self.history = QPlainTextEdit(history)
        self.history.setReadOnly(True)
        self.history.setAccessibleName("Submission decisions for this computer")
        history_layout.addWidget(self.history)
        refresh = QPushButton("Refresh my requests", history)
        refresh.clicked.connect(lambda: self.action_requested.emit("refresh"))
        self.buttons["refresh"] = refresh
        history_layout.addWidget(refresh)
        self.tabs.addTab(history, "My requests")
        self.status = QLabel(
            "Connect through Settings > Experiment Library before submitting.", self
        )
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        footer = QHBoxLayout()
        footer.addStretch()
        cancel = QPushButton("Cancel operation", self)
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
        self.rights.toggled.connect(
            lambda: self.set_state(self._busy, self._prepared, self._attempted)
        )
        self.set_state(False, False, False)
        apply_dialog_theme(self)

    def set_state(self, busy: bool, prepared: bool, attempted: bool) -> None:
        self._busy, self._prepared, self._attempted = busy, prepared, attempted
        self.form.setEnabled(not busy and not prepared)
        self.rights.setEnabled(not busy and not attempted)
        self.buttons["prepare"].setEnabled(
            not busy and not prepared and self.conditions.count() > 0
        )
        self.buttons["submit"].setEnabled(not busy and prepared and self.rights.isChecked())
        self.buttons["new"].setEnabled(not busy and prepared)
        self.buttons["refresh"].setEnabled(not busy)
        self.buttons["cancel"].setEnabled(busy)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.closing.emit()
        super().closeEvent(event)
