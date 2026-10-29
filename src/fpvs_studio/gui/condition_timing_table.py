"""Staged shared and condition-specific FPVS presentation frequencies."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.condition_timing import (
    effective_condition_base_hz,
    propose_condition_frequencies,
)
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.gui.components import mark_error_text, mark_primary_action, mark_secondary_action
from fpvs_studio.gui.document import ProjectDocument

FREQUENCY_OVERRIDE_WARNING = (
    "Warning: you're about to change the stimulus presentation frequency of this condition. "
    "It will not match the other conditions in your experiment. Are you sure?"
)


class ConditionTimingTable(QWidget):
    """Keep frequency drafts together until validation and explicit confirmation pass."""

    draft_changed = Signal()

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("condition_timing_table")
        self._document = document
        self._syncing = False
        self._applying = False
        self._shared_hz = document.project.settings.protocol.base_hz
        self._shared_dirty = False
        self._overrides: dict[str, float | None] = {}
        self.frequency_spins: dict[str, QDoubleSpinBox] = {}
        self.source_labels: dict[str, QLabel] = {}
        self.reset_buttons: dict[str, QPushButton] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        shared = QHBoxLayout()
        shared.setSpacing(8)
        heading = QLabel("Shared stimulus frequency", self)
        heading.setProperty("settingsSectionTitle", "true")
        shared.addWidget(heading)
        self.shared_frequency_spin = self._frequency_spin("shared_stimulus_frequency_spin")
        self.shared_frequency_spin.setValue(self._shared_hz)
        self._display_shared_hz = self.shared_frequency_spin.value()
        self.shared_frequency_spin.setAccessibleName("Shared stimulus presentation frequency")
        self.shared_frequency_spin.setToolTip(
            "Stimulus presentations per second, independent of monitor refresh rate. "
            "Inherited conditions use this value; custom frequencies stay unchanged. "
            "Frequency changes preserve each condition's stream duration.",
        )
        shared.addWidget(self.shared_frequency_spin)
        shared.addStretch(1)
        self.apply_button = QPushButton("Apply frequencies", self)
        self.apply_button.setObjectName("apply_condition_frequencies_button")
        mark_primary_action(self.apply_button)
        self.apply_button.clicked.connect(self.apply_pending_edits)
        self.discard_button = QPushButton("Discard", self)
        self.discard_button.setObjectName("discard_condition_frequencies_button")
        mark_secondary_action(self.discard_button)
        self.discard_button.clicked.connect(self.discard_pending_edits)
        shared.addWidget(self.discard_button)
        shared.addWidget(self.apply_button)
        layout.addLayout(shared)
        self.table = QTableWidget(0, 4, self)
        self.table.setObjectName("condition_frequency_table")
        self.table.setHorizontalHeaderLabels(["Condition", "Frequency", "Source", ""])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(36)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        self.error_label = QLabel(self)
        self.error_label.setObjectName("condition_frequency_error")
        self.error_label.setWordWrap(True)
        self.error_label.setMinimumWidth(0)
        self.error_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        mark_error_text(self.error_label)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        self.shared_frequency_spin.valueChanged.connect(self._shared_frequency_changed)
        document.project_changed.connect(self.refresh)
        self.refresh()

    def _frequency_spin(self, name: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(self)
        spin.setObjectName(name)
        spin.setRange(0.01, 500)
        spin.setDecimals(4)
        spin.setSingleStep(0.1)
        spin.setSuffix(" Hz")
        spin.setMinimumWidth(112)
        spin.setKeyboardTracking(False)
        return spin

    def has_pending_edits(self) -> bool:
        return self._shared_dirty or bool(self._overrides)

    def refresh(self) -> None:
        if self._applying or self.has_pending_edits():
            return
        project = self._document.project
        self.setVisible(project.experiment_category != ExperimentCategory.ATTENTIONAL_BLINK)
        self._syncing = True
        self._shared_hz = project.settings.protocol.base_hz
        self.shared_frequency_spin.setValue(self._shared_hz)
        self._display_shared_hz = self.shared_frequency_spin.value()
        conditions = self._document.ordered_conditions()
        self.table.setRowCount(len(conditions))
        self.frequency_spins.clear()
        self.source_labels.clear()
        self.reset_buttons.clear()
        for row, condition in enumerate(conditions):
            name = QTableWidgetItem(condition.name)
            name.setToolTip(condition.name)
            name.setData(Qt.ItemDataRole.AccessibleTextRole, condition.name)
            self.table.setItem(row, 0, name)
            spin = self._frequency_spin(f"condition_frequency_{condition.condition_id}")
            spin.setAccessibleName(f"Stimulus frequency for {condition.name}")
            spin.setToolTip(f"{condition.name}: change this condition's stimulus frequency.")
            spin.setValue(effective_condition_base_hz(project, condition))
            spin.valueChanged.connect(
                lambda value, key=condition.condition_id:
                self._condition_frequency_changed(key, value),
            )
            self.frequency_spins[condition.condition_id] = spin
            self.table.setCellWidget(row, 1, spin)
            source = QLabel(self)
            source.setMinimumWidth(64)
            self.source_labels[condition.condition_id] = source
            self.table.setCellWidget(row, 2, source)
            reset = QPushButton("Use shared", self)
            reset.setAutoDefault(False)
            reset.setAccessibleName(f"Use shared frequency for {condition.name}")
            reset.clicked.connect(
                lambda _checked=False, key=condition.condition_id: self._reset(key),
            )
            mark_secondary_action(reset)
            self.reset_buttons[condition.condition_id] = reset
            self.table.setCellWidget(row, 3, reset)
            self.table.setRowHeight(
                row, max(36, spin.sizeHint().height(), reset.sizeHint().height()),
            )
        self.table.setFixedHeight(
            self.table.horizontalHeader().sizeHint().height()
            + sum(self.table.rowHeight(row) for row in range(min(3, len(conditions))))
            + (36 if not conditions else 0) + 2 * self.table.frameWidth(),
        )
        self._syncing = False
        self._sync_rows()
        self._update_actions()

    def _sync_rows(self) -> None:
        self._syncing = True
        for condition in self._document.ordered_conditions():
            if condition.condition_id not in self.frequency_spins:
                continue
            override = self._overrides.get(condition.condition_id, condition.base_hz)
            self.frequency_spins[condition.condition_id].setValue(
                self.shared_frequency_spin.value() if override is None else override,
            )
            self.source_labels[condition.condition_id].setText(
                "Shared" if override is None else "Custom",
            )
            self.reset_buttons[condition.condition_id].setEnabled(override is not None)
        self._syncing = False

    def _shared_frequency_changed(self) -> None:
        if self._syncing:
            return
        self._shared_dirty = self.shared_frequency_spin.value() != self._display_shared_hz
        self._sync_rows()
        self._draft_changed()

    def _condition_frequency_changed(self, condition_id: str, value: float) -> None:
        if self._syncing:
            return
        condition = self._document.get_condition(condition_id)
        if condition is None:
            return
        if (condition.base_hz is None and value == self.shared_frequency_spin.value()) or (
            condition.base_hz == value
        ):
            self._overrides.pop(condition_id, None)
        else:
            self._overrides[condition_id] = value
        self._sync_rows()
        self._draft_changed()

    def _reset(self, condition_id: str) -> None:
        condition = self._document.get_condition(condition_id)
        if condition is not None and condition.base_hz is not None:
            self._overrides[condition_id] = None
        else:
            self._overrides.pop(condition_id, None)
        self._sync_rows()
        self._draft_changed()

    def _draft_changed(self) -> None:
        self.error_label.hide()
        self._update_actions()
        self.draft_changed.emit()

    def _update_actions(self) -> None:
        pending = self.has_pending_edits()
        self.apply_button.setEnabled(pending)
        self.discard_button.setEnabled(pending)

    def discard_pending_edits(self) -> None:
        self._overrides.clear()
        self._shared_hz = self._document.project.settings.protocol.base_hz
        self._shared_dirty = False
        self._syncing = True
        self.shared_frequency_spin.setValue(self._shared_hz)
        self._syncing = False
        self.error_label.hide()
        self.refresh()
        self.draft_changed.emit()

    def apply_pending_edits(self) -> bool:
        if not self.has_pending_edits():
            return True
        shared = self.shared_frequency_spin.value() if self._shared_dirty else None
        overrides = dict(self._overrides)
        try:
            propose_condition_frequencies(
                self._document.project, shared_base_hz=shared, overrides=overrides,
                refresh_hz=self._document.project.settings.display.preferred_refresh_hz,
            )
        except ValueError as error:
            self.error_label.setText(str(error))
            self.error_label.show()
            return False
        for condition_id, value in overrides.items():
            if value is None:
                continue
            condition = self._document.get_condition(condition_id)
            assert condition is not None
            answer = QMessageBox.question(
                self, f"Condition frequency: {condition.name}", FREQUENCY_OVERRIDE_WARNING,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._overrides.pop(condition_id, None)
                self._sync_rows()
                self._draft_changed()
                return False
        self._applying = True
        try:
            self._document.update_condition_frequencies(shared_base_hz=shared, overrides=overrides)
        except ValueError as error:
            self.error_label.setText(str(error))
            self.error_label.show()
            return False
        finally:
            self._applying = False
        self.discard_pending_edits()
        return True
