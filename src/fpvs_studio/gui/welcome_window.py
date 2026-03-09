"""Welcome screen shown before a project is opened."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class WelcomeWindow(QWidget):
    """Simple launch page for creating or opening a project."""

    create_requested = Signal()
    open_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FPVS Studio")
        self.resize(760, 420)

        title_label = QLabel("FPVS Studio", self)
        title_label.setObjectName("welcome_title_label")
        title_label.setStyleSheet("font-size: 28px; font-weight: 600;")

        body_label = QLabel(
            "Author FPVS projects, import and materialize assets, validate the session, "
            "and launch the currently supported test-mode runtime path.",
            self,
        )
        body_label.setWordWrap(True)
        body_label.setObjectName("welcome_body_label")

        create_button = QPushButton("Create New Project", self)
        create_button.setObjectName("create_project_button")
        create_button.setMinimumHeight(48)
        create_button.clicked.connect(self.create_requested.emit)

        open_button = QPushButton("Open Existing Project", self)
        open_button.setObjectName("open_project_button")
        open_button.setMinimumHeight(48)
        open_button.clicked.connect(self.open_requested.emit)

        action_layout = QHBoxLayout()
        action_layout.addWidget(create_button)
        action_layout.addWidget(open_button)

        card = QFrame(self)
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(18)
        card_layout.addWidget(title_label)
        card_layout.addWidget(body_label)
        card_layout.addLayout(action_layout)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.addStretch(1)
        layout.addWidget(card)
        layout.addStretch(2)
