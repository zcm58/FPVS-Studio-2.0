"""Compact configured seed controls over the document's randomization lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.randomization import (
    RandomizationSeeds,
    configured_randomization_seeds,
    effective_randomization_mode,
    supports_independent_randomization,
)
from fpvs_studio.gui.components import mark_error_text, mark_secondary_action
from fpvs_studio.gui.condition_order_dialog import ConditionOrderDialog
from fpvs_studio.gui.document import ProjectDocument

if TYPE_CHECKING:
    from fpvs_studio.gui.condition_timing_table import ConditionTimingTable


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
        self._timing_table: ConditionTimingTable | None = None
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
        self.condition_order_button = QPushButton("Condition order...", self)
        self.condition_order_button.setObjectName("condition_order_button")
        self.condition_order_button.setToolTip(
            "Preview, generate or arrange the exact condition order.",
        )
        mark_secondary_action(self.condition_order_button)
        policy.addWidget(self.condition_order_button)
        layout.addLayout(policy)
        self.seed_details_button = QToolButton(self)
        self.seed_details_button.setObjectName("seed_details_button")
        self.seed_details_button.setText("Seed details")
        self.seed_details_button.setCheckable(True)
        self.seed_details_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.seed_details_button.setArrowType(Qt.ArrowType.RightArrow)
        layout.addWidget(self.seed_details_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.seed_details = QWidget(self)
        self.seed_details.setObjectName("seed_details")
        self.seed_details.hide()
        details_layout = QVBoxLayout(self.seed_details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(6)
        seed_commands = QHBoxLayout()
        seed_commands.setSpacing(8)
        self.generate_button = QPushButton("Generate seeds", self)
        self.generate_button.setObjectName("generate_randomization_seeds_button")
        self.generate_button.setToolTip(
            "Replace all three configured seeds with newly generated values.",
        )
        mark_secondary_action(self.generate_button)
        seed_commands.addWidget(self.generate_button)
        self.clear_saved_order_button = QPushButton("Use seed-generated order", self)
        self.clear_saved_order_button.setObjectName("clear_saved_condition_order_button")
        self.clear_saved_order_button.setToolTip(
            "Remove the saved list and use the condition-order seed.",
        )
        mark_secondary_action(self.clear_saved_order_button)
        seed_commands.addWidget(self.clear_saved_order_button)
        seed_commands.addStretch(1)
        details_layout.addLayout(seed_commands)
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
             "Used when generating an order. Change a saved arrangement in Condition order..."),
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
        details_layout.addLayout(fields)
        self.resolved_label = QLabel(self)
        self.resolved_label.setObjectName("resolved_randomization_seeds_label")
        self.resolved_label.setWordWrap(True)
        self.resolved_label.setToolTip(
            "The fields contain configured seeds. New mode uses them for previews and resolves "
            "fresh seeds once for a participant launch. A pending retry reuses its resolved seeds.",
        )
        details_layout.addWidget(self.resolved_label)
        layout.addWidget(self.seed_details)
        self.error_label = QLabel(self)
        self.error_label.setObjectName("randomization_seed_error")
        self.error_label.setWordWrap(True)
        mark_error_text(self.error_label)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.generate_button.clicked.connect(self._generate)
        self.seed_details_button.toggled.connect(self._toggle_details)
        self.condition_order_button.clicked.connect(self._edit_order)
        self.clear_saved_order_button.clicked.connect(self._clear_saved_order)
        document.project_changed.connect(self.refresh)
        document.session_plan_changed.connect(self._refresh_resolved)
        document.randomization_changed.connect(self._refresh_resolved)
        self.refresh()

    def set_timing_table(self, table: ConditionTimingTable) -> None:
        self._timing_table = table

    def _toggle_details(self, expanded: bool) -> None:
        self.seed_details.setVisible(expanded)
        self.seed_details_button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow,
        )

    def _edit_order(self) -> None:
        if self.has_pending_edits() or any(
            not edit.hasAcceptableInput() for edit in self.seed_edits.values()
        ):
            self.seed_details_button.setChecked(True)
            self.error_label.setText(
                "Finish editing the seed details before opening Condition order.",
            )
            self.error_label.show()
            return
        table = self._timing_table
        signature: Callable[[], object] = (table.order_edit_signature if table is not None
                                          else lambda: (id(self._document.project),))

        def save_order(order: list[str], seeds: RandomizationSeeds) -> None:
            if table is not None:
                if not table.apply_condition_order(order, seeds):
                    raise ValueError(table.error_label.text() or "Changes were not saved.")
            else:
                self._document.update_condition_timing(
                    saved_condition_order=order, order_seeds=seeds, persist=True,
                )

        dialog = ConditionOrderDialog(
            self._document.project, seeds=configured_randomization_seeds(self._document.project),
            presentation_counts=table.pending_presentation_counts() if table is not None else {},
            current_signature=signature, save_order=save_order, parent=self,
        )
        dialog.exec()

    def _clear_saved_order(self) -> None:
        if self._timing_table is not None:
            if not self._timing_table.clear_saved_order():
                self.error_label.setText(self._timing_table.error_label.text())
                self.error_label.show()
        else:
            try:
                self._document.update_condition_timing(clear_saved_condition_order=True)
            except ValueError as error:
                self.error_label.setText(str(error))
                self.error_label.show()

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
        self.clear_saved_order_button.setVisible(
            project.settings.session.saved_condition_order is not None,
        )
        self.condition_order_button.setToolTip(
            "Preview, generate or arrange the exact condition order. "
            + ("The saved order is inactive in New mode."
               if project.settings.session.saved_condition_order is not None
               and effective_randomization_mode(project) == "new" else ""),
        )
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
            self.seed_details_button.setChecked(True)
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
            self.seed_details_button.setChecked(True)
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
