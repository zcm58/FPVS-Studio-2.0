"""Plain-language participant reuse choices over the document randomization lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from fpvs_studio.core.randomization import (
    RandomizationSeeds,
    configured_randomization_seeds,
    effective_randomization_modes,
    supports_independent_randomization,
)
from fpvs_studio.gui.components import PAGE_SECTION_GAP, mark_error_text, mark_secondary_action
from fpvs_studio.gui.condition_order_dialog import ConditionOrderDialog
from fpvs_studio.gui.document import ProjectDocument

if TYPE_CHECKING:
    from fpvs_studio.gui.condition_timing_table import ConditionTimingTable


class RandomizationEditor(QWidget):
    """Choose independently whether each pattern repeats across participants."""

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
        layout.setSpacing(PAGE_SECTION_GAP)
        self.mode_combos: dict[str, QComboBox] = {}
        self.heading_labels: dict[str, QLabel] = {}
        choice_layouts: dict[str, QVBoxLayout] = {}
        for domain, title in (
            ("stimulus", "Image / word display order"),
            ("condition_order", "Condition order"),
            ("fixation", "Fixation cross color change timing"),
        ):
            group = QVBoxLayout()
            group.setSpacing(6)
            label = QLabel(title, self)
            label.setObjectName(f"{domain}_randomization_heading")
            label.setProperty("sectionCardRole", "title")
            combo = QComboBox(self)
            combo.setObjectName(f"{domain}_randomization_mode_combo")
            combo.setAccessibleName(title)
            combo.addItem("Randomized — new for each participant", "new")
            combo.addItem("Pseudorandom — same for every participant", "fixed")
            label.setBuddy(combo)
            self.mode_combos[domain] = combo
            self.heading_labels[domain] = label
            choice_layouts[domain] = group
            group.addWidget(label)
            group.addWidget(combo)
            layout.addLayout(group)
            combo.currentIndexChanged.connect(self._mode_changed)
        commands = QHBoxLayout()
        commands.setSpacing(8)
        self.condition_order_button = QPushButton("Edit condition order...", self)
        self.condition_order_button.setObjectName("condition_order_button")
        self.condition_order_button.setToolTip(
            "Open the Pseudorandom Condition Order Editor to arrange the order "
            "for every participant.",
        )
        mark_secondary_action(self.condition_order_button)
        commands.addWidget(self.condition_order_button)
        self.clear_saved_order_button = QPushButton("Use automatic condition order", self)
        self.clear_saved_order_button.setObjectName("clear_saved_condition_order_button")
        self.clear_saved_order_button.setToolTip(
            "Remove the saved arrangement. The condition-order choice above still applies."
        )
        mark_secondary_action(self.clear_saved_order_button)
        commands.addWidget(self.clear_saved_order_button)
        commands.addStretch(1)
        choice_layouts["condition_order"].addLayout(commands)
        self.saved_order_status_label = QLabel(self)
        self.saved_order_status_label.setObjectName("saved_condition_order_status")
        self.saved_order_status_label.setProperty("setupMetricLabel", "true")
        self.saved_order_status_label.setWordWrap(True)
        self.saved_order_status_label.hide()
        choice_layouts["condition_order"].addWidget(self.saved_order_status_label)
        self.error_label = QLabel(self)
        self.error_label.setObjectName("randomization_error")
        self.error_label.setWordWrap(True)
        mark_error_text(self.error_label)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        self.reset_patterns_button = QPushButton("Create new random patterns", self)
        self.reset_patterns_button.setToolTip(
            "Replace the project's stored patterns, including any repeatable patterns."
        )
        mark_secondary_action(self.reset_patterns_button)
        self.reset_patterns_button.hide()
        layout.addWidget(self.reset_patterns_button)
        self.condition_order_button.clicked.connect(self._edit_order)
        self.clear_saved_order_button.clicked.connect(self._clear_saved_order)
        self.reset_patterns_button.clicked.connect(self._reset_patterns)
        QWidget.setTabOrder(self.mode_combos["condition_order"], self.condition_order_button)
        QWidget.setTabOrder(self.condition_order_button, self.clear_saved_order_button)
        QWidget.setTabOrder(self.clear_saved_order_button, self.mode_combos["fixation"])
        document.project_changed.connect(self.refresh)
        self.refresh()

    def set_timing_table(self, table: ConditionTimingTable) -> None:
        self._timing_table = table

    def _edit_order(self) -> None:
        if not self.apply_pending_edits():
            return
        table = self._timing_table
        signature: Callable[[], object] = (table.order_edit_signature if table is not None
                                          else lambda: (id(self._document.project),))

        def save_order(order: list[str], seeds: RandomizationSeeds) -> None:
            if table is not None:
                if not table.apply_condition_order(
                    order, seeds, condition_ordering="randomized_blocks",
                ):
                    raise ValueError(table.error_label.text() or "Changes were not saved.")
            else:
                self._document.update_condition_timing(
                    saved_condition_order=order, order_seeds=seeds, persist=True,
                    condition_ordering="randomized_blocks",
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
        return tuple(combo.currentData() for combo in self.mode_combos.values())

    def has_pending_edits(self) -> bool:
        return (bool(self._baseline) and supports_independent_randomization(self._document.project)
                and self._state() != self._baseline)

    def _mode_changed(self) -> None:
        if not self._syncing:
            self.error_label.hide()
            self._refresh_choice_details()
            self.draft_changed.emit()
            self.apply_pending_edits()

    def refresh(self) -> None:
        if self._applying:
            return
        eligible = supports_independent_randomization(self._document.project)
        self.setVisible(eligible)
        if not eligible:
            return
        if not self.has_pending_edits():
            modes = effective_randomization_modes(self._document.project)
            self._syncing = True
            for domain, combo in self.mode_combos.items():
                with QSignalBlocker(combo):
                    combo.setCurrentIndex(combo.findData(getattr(modes, domain)))
            self._baseline = self._state()
            self._syncing = False
            self.error_label.hide()
        self.clear_saved_order_button.setVisible(
            self._document.project.settings.session.saved_condition_order is not None,
        )
        self._refresh_choice_details()
        if self._validate_patterns() and self._timing_table is not None:
            if message := self._timing_table.saved_order_blocker():
                self.error_label.setText(message)
                self.error_label.show()

    def _refresh_choice_details(self) -> None:
        saved = self._document.project.settings.session.saved_condition_order is not None
        for domain, combo in self.mode_combos.items():
            fixed = combo.currentData() == "fixed"
            if domain == "stimulus":
                text = ("Every participant receives the same image / word order for each "
                        "condition presentation." if fixed else
                        "Image / word order is randomized separately for each participant.")
            elif domain == "fixation":
                text = ("Every participant receives the same fixation cross color change times "
                        "for each condition presentation." if fixed else
                        "Fixation cross color change times are randomized separately "
                        "for each participant.")
            else:
                text = ("Every participant receives the same condition order." if fixed else
                        "Condition order is randomized separately for each participant.")
            detail = (
                f"{text} Pseudorandom reuses a stored random pattern while the project "
                "settings stay the same. Existing balancing and timing rules apply to both choices."
            )
            combo.setToolTip(detail)
            combo.setAccessibleDescription(detail)
        fixed_order = self.mode_combos["condition_order"].currentData() == "fixed"
        self.saved_order_status_label.setText(
            "Saved order in use" if fixed_order else "Saved order inactive",
        )
        self.saved_order_status_label.setVisible(saved)

    def _validate_patterns(self) -> bool:
        try:
            configured_randomization_seeds(self._document.project)
        except ValueError:
            self.error_label.setText(
                "This project's stored random patterns need to be replaced. "
                "Choose Create new random patterns to continue."
            )
            self.error_label.show()
            self.reset_patterns_button.show()
            return False
        self.reset_patterns_button.hide()
        return True

    def apply_pending_edits(self) -> bool:
        if self._syncing or not supports_independent_randomization(self._document.project):
            return True
        if not self._validate_patterns():
            return False
        if not self.has_pending_edits():
            return True
        self._applying = True
        try:
            self._document.update_randomization_settings(
                modes={domain: combo.currentData() for domain, combo in self.mode_combos.items()},
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

    def _reset_patterns(self) -> None:
        self._applying = True
        try:
            self._document.generate_new_randomization_seeds()
        except ValueError as error:
            self.error_label.setText(str(error))
            self.error_label.show()
            return
        finally:
            self._applying = False
        self.error_label.hide()
        if not self.apply_pending_edits():
            return
        self.refresh()
        self.draft_changed.emit()
