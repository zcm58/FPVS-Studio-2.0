"""Compact configured seed controls over the document's randomization lifecycle."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.randomization import (
    configured_randomization_seeds,
    effective_randomization_mode,
    supports_independent_randomization,
)
from fpvs_studio.gui.components import mark_error_text, mark_secondary_action
from fpvs_studio.gui.document import ProjectDocument


class RandomizationEditor(QWidget):
    """Edit one reuse policy and three seeds without conflating launch resolutions."""

    draft_changed = Signal()

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("randomization_editor")
        self._document = document
        self._syncing = False
        self._applying = False
        self._baseline: tuple[object, ...] = ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        policy = QHBoxLayout()
        policy.setSpacing(8)
        self.mode_combo = QComboBox(self)
        self.mode_combo.setObjectName("randomization_mode_combo")
        self.mode_combo.setAccessibleName("Randomization seed reuse")
        self.mode_combo.addItem("Same for every participant", "fixed")
        self.mode_combo.addItem("New for each participant", "new")
        self.mode_combo.setToolTip(
            "One policy covers image/word order, condition order and fixation schedules. "
            "The same inputs and fixed seeds reproduce corresponding condition presentations. "
            "AB, masking and pre/post-task randomness keep their existing behavior.",
        )
        policy.addWidget(self.mode_combo, 1)
        self.generate_button = QPushButton("Generate seeds", self)
        self.generate_button.setObjectName("generate_randomization_seeds_button")
        self.generate_button.setToolTip(
            "Replace all three configured seeds with newly generated values.",
        )
        mark_secondary_action(self.generate_button)
        policy.addWidget(self.generate_button)
        layout.addLayout(policy)
        fields = QGridLayout()
        fields.setContentsMargins(0, 0, 0, 0)
        fields.setHorizontalSpacing(8)
        fields.setVerticalSpacing(3)
        self.configured_label = QLabel("Configured seeds", self)
        fields.addWidget(self.configured_label, 0, 0, 1, 3)
        self.seed_edits: dict[str, QLineEdit] = {}
        for column, (key, text, help_text) in enumerate((
            ("stimulus_seed", "Images / words seed", "Balanced image and word order."),
            ("condition_order_seed", "Condition order seed",
             "Pooled condition order without adjacent repeats."),
            ("fixation_seed", "Fixation seed",
             "Randomized fixation target counts and onset timing."),
        )):
            label = QLabel(text, self)
            edit = QLineEdit(self)
            edit.setObjectName(f"configured_{key}_edit")
            edit.setAccessibleName(text)
            edit.setValidator(QIntValidator(0, 2_147_483_647, edit))
            edit.setMinimumWidth(112)
            edit.setToolTip(f"{help_text} Configured integer seed from 0 to 2147483647.")
            label.setBuddy(edit)
            fields.addWidget(label, 1, column)
            fields.addWidget(edit, 2, column)
            fields.setColumnStretch(column, 1)
            self.seed_edits[key] = edit
            edit.textChanged.connect(self._draft_changed)
            edit.editingFinished.connect(self.apply_pending_edits)
        layout.addLayout(fields)
        self.resolved_label = QLabel(self)
        self.resolved_label.setObjectName("resolved_randomization_seeds_label")
        self.resolved_label.setWordWrap(True)
        self.resolved_label.setToolTip(
            "The fields contain configured seeds. New mode uses them for previews and resolves "
            "fresh seeds once for a participant launch. A pending retry reuses its resolved seeds.",
        )
        layout.addWidget(self.resolved_label)
        self.error_label = QLabel(self)
        self.error_label.setObjectName("randomization_seed_error")
        self.error_label.setWordWrap(True)
        mark_error_text(self.error_label)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.generate_button.clicked.connect(self._generate)
        document.project_changed.connect(self.refresh)
        document.session_plan_changed.connect(self._refresh_resolved)
        document.randomization_changed.connect(self._refresh_resolved)
        self.refresh()

    def _state(self) -> tuple[object, ...]:
        return (self.mode_combo.currentData(), *(edit.text() for edit in self.seed_edits.values()))

    def has_pending_edits(self) -> bool:
        return (bool(self._baseline) and supports_independent_randomization(self._document.project)
                and self._state() != self._baseline)

    def _draft_changed(self) -> None:
        if not self._syncing:
            self.error_label.hide()
            self.draft_changed.emit()

    def _mode_changed(self) -> None:
        self._draft_changed()
        if not self._syncing:
            self.apply_pending_edits()

    def refresh(self) -> None:
        if self._applying:
            return
        project = self._document.project
        eligible = supports_independent_randomization(project)
        self.setVisible(eligible)
        if not eligible or self.has_pending_edits():
            self._refresh_resolved()
            return
        self._syncing = True
        with QSignalBlocker(self.mode_combo):
            self.mode_combo.setCurrentIndex(
                self.mode_combo.findData(effective_randomization_mode(project)),
            )
        try:
            seeds = configured_randomization_seeds(project)
        except ValueError as error:
            session = project.settings.session
            values = {
                "condition_order_seed": session.session_seed,
                "stimulus_seed": session.stimulus_seed, "fixation_seed": session.fixation_seed,
            }
            for key, edit in self.seed_edits.items():
                value = values[key]
                edit.setText("" if value is None else str(value))
            self.error_label.setText(str(error))
            self.error_label.show()
        else:
            for key, edit in self.seed_edits.items():
                edit.setText(str(getattr(seeds, key)))
            self.error_label.hide()
        self._baseline = self._state()
        self._syncing = False
        self._refresh_resolved()

    def _refresh_resolved(self) -> None:
        seeds, label = self._document.resolved_randomization_status()
        if seeds is None:
            text = ("Configured seeds reused for every participant."
                    if effective_randomization_mode(self._document.project) == "fixed"
                    else "New seeds are resolved at participant launch.")
        else:
            text = (f"{label}: images/words {seeds.stimulus_seed} · "
                    f"order {seeds.condition_order_seed} · fixation {seeds.fixation_seed}")
        self.resolved_label.setText(text)

    def apply_pending_edits(self) -> bool:
        if self._syncing or not supports_independent_randomization(self._document.project):
            return True
        if any(not edit.hasAcceptableInput() for edit in self.seed_edits.values()):
            self.error_label.setText("Enter an integer seed from 0 to 2147483647 in every field.")
            self.error_label.show()
            return False
        if not self.has_pending_edits():
            return True
        self._applying = True
        try:
            self._document.update_randomization_settings(
                mode=self.mode_combo.currentData(),
                **{key: int(edit.text()) for key, edit in self.seed_edits.items()},
            )
        except ValueError as error:
            self.error_label.setText(str(error))
            self.error_label.show()
            return False
        finally:
            self._applying = False
        self._baseline = self._state()
        self.error_label.hide()
        self.refresh()
        self.draft_changed.emit()
        return True

    def _generate(self) -> None:
        self._applying = True
        try:
            self._document.generate_new_randomization_seeds(mode=self.mode_combo.currentData())
        finally:
            self._applying = False
        self._baseline = self._state()
        self.refresh()
        self.draft_changed.emit()
