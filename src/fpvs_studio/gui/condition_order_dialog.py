"""Plain ordered-list editor over pure core condition-order services."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from typing import cast

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.randomization import RandomizationSeeds, generate_randomization_seeds
from fpvs_studio.core.session_ordering import (
    condition_presentation_counts,
    preview_condition_order,
    validate_saved_condition_order,
)
from fpvs_studio.gui.components import mark_error_text, mark_primary_action, mark_secondary_action
from fpvs_studio.gui.update_lifecycle import UpdateJob, UpdateTaskResult, update_lifecycle

_STALE_SETUP_MESSAGE = (
    "Setup changed. Close and reopen Condition order to use the current settings."
)


class ConditionOrderDialog(QDialog):
    """Retain a chosen list until one atomic Save accepts all parent drafts."""

    def __init__(
        self, project: ProjectFile, *, seeds: RandomizationSeeds,
        presentation_counts: Mapping[str, int], current_signature: Callable[[], object],
        save_order: Callable[[list[str], RandomizationSeeds], None], parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Condition order")
        self.setObjectName("condition_order_dialog")
        self.setMinimumSize(700, 520)
        self.resize(780, 620)
        self._source_project = project
        self._snapshot = project.model_copy(deep=True)
        self._pending_counts = dict(presentation_counts)
        self._counts = {**condition_presentation_counts(project), **presentation_counts}
        self._current_signature = current_signature
        self._signature = current_signature()
        self._save_order = save_order
        self._seeds = seeds
        self._order = list(project.settings.session.saved_condition_order or [])
        self._job: UpdateJob | None = None
        self._dismissed = False
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        commands = QHBoxLayout()
        commands.setSpacing(8)
        self.generate_button = QPushButton("Generate", self)
        self.generate_button.setObjectName("generate_condition_order_button")
        self.generate_button.setToolTip(
            "Generate a pseudorandom order for the requested presentations. "
            "Some counts allow only one valid order.",
        )
        self.move_up_button = QPushButton("Move up", self)
        self.move_down_button = QPushButton("Move down", self)
        for button in (self.generate_button, self.move_up_button, self.move_down_button):
            button.setAutoDefault(False)
            mark_secondary_action(button)
            commands.addWidget(button)
        commands.addStretch(1)
        layout.addLayout(commands)
        self.order_list = QListWidget(self)
        self.order_list.setObjectName("condition_order_list")
        self.order_list.setAccessibleName("Ordered condition presentations")
        self.order_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.order_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.order_list, 1)
        self.error_label = QLabel(self)
        self.error_label.setObjectName("condition_order_error")
        self.error_label.setWordWrap(True)
        mark_error_text(self.error_label)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        self.effect_label = QLabel("Save selects Same for every participant.", self)
        self.effect_label.setWordWrap(True)
        layout.addWidget(self.effect_label)
        footer = QHBoxLayout()
        footer.addStretch(1)
        self.cancel_button = QPushButton("Cancel", self)
        self.save_button = QPushButton("Save", self)
        self.save_button.setObjectName("save_condition_order_button")
        mark_secondary_action(self.cancel_button)
        mark_primary_action(self.save_button)
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)
        self.generate_button.clicked.connect(self.generate)
        self.move_up_button.clicked.connect(lambda: self._move_selected(-1))
        self.move_down_button.clicked.connect(lambda: self._move_selected(1))
        self.order_list.currentRowChanged.connect(self._update_buttons)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.save)
        self.finished.connect(self._cancel_generation)
        self._render()
        if not self._order:
            QTimer.singleShot(0, lambda: self.generate(fresh=False))

    def _stale(self) -> bool:
        return self._current_signature() != self._signature

    def _error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(bool(message))

    def _render(self, selected: int = 0) -> None:
        names = {condition.condition_id: condition.name for condition in self._snapshot.conditions}
        occurrences: Counter[str] = Counter()
        self.order_list.clear()
        for index, condition_id in enumerate(self._order, start=1):
            occurrences[condition_id] += 1
            name = names.get(condition_id, condition_id)
            text = f"{index}. {name} · presentation {occurrences[condition_id]}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, condition_id)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, text)
            item.setToolTip(text)
            self.order_list.addItem(item)
        if self._order:
            self.order_list.setCurrentRow(min(selected, len(self._order) - 1))
        self._update_buttons()

    def _update_buttons(self) -> None:
        busy = self._job is not None
        row = self.order_list.currentRow()
        self.generate_button.setEnabled(not busy)
        self.move_up_button.setEnabled(not busy and row > 0)
        self.move_down_button.setEnabled(not busy and 0 <= row < len(self._order) - 1)
        try:
            validate_saved_condition_order(self._order, self._counts)
        except ValueError as error:
            valid = False
            if not busy:
                self._error(str(error))
        else:
            valid = bool(self._order)
            if not busy:
                self._error("")
        self.save_button.setEnabled(not busy and valid and not self._stale())

    def generate(self, _checked: bool = False, *, fresh: bool = True) -> None:
        if self._job is not None or self._dismissed:
            return
        if self._stale():
            self._error(_STALE_SETUP_MESSAGE)
            self.save_button.setEnabled(False)
            return
        candidate = self._seeds
        if fresh:
            candidate = candidate.model_copy(update={
                "condition_order_seed": generate_randomization_seeds().condition_order_seed,
            })
        snapshot, counts = self._snapshot, dict(self._pending_counts)
        seed = candidate.condition_order_seed
        try:
            self._job = update_lifecycle().start_task(
                lambda _progress, cancel: preview_condition_order(
                    snapshot, presentation_counts=counts, condition_order_seed=seed,
                    cancelled=cancel.is_set,
                ),
            )
        except RuntimeError as error:
            self._error(str(error))
            return
        self._seeds = candidate
        self._job.finished.connect(self._generated)
        self._update_buttons()
        self._error("Generating condition order…")

    @Slot(object)
    def _generated(self, value: object) -> None:
        if self._job is None or self.sender() is not self._job:
            return
        self._complete_generation(cast(UpdateTaskResult, value))

    def _complete_generation(self, result: UpdateTaskResult) -> None:
        self._job = None
        if self._dismissed:
            return
        self._update_buttons()
        if self._stale():
            self._error(_STALE_SETUP_MESSAGE)
        elif result.cancelled:
            self._error("Generation cancelled. Generate again or keep editing the list.")
        elif result.error is not None:
            self._error(str(result.error))
        else:
            self._order = list(cast(list[str], result.value))
            self._render()

    def _move_selected(self, offset: int) -> None:
        row = self.order_list.currentRow()
        target = row + offset
        if self._job is not None or row < 0 or not 0 <= target < len(self._order):
            return
        self._order[row], self._order[target] = self._order[target], self._order[row]
        self._render(target)

    def save(self) -> None:
        if self._job is not None or self._dismissed:
            return
        if self._stale():
            self._error(_STALE_SETUP_MESSAGE)
            return
        try:
            validate_saved_condition_order(self._order, self._counts)
            self._save_order(list(self._order), self._seeds)
        except (ValueError, OSError) as error:
            self._error(str(error))
            return
        self.accept()

    def _cancel_generation(self, _result: int = 0) -> None:
        self._dismissed = True
        if self._job is not None:
            self._job.finished.disconnect(self._generated)
            self._job.cancel()
            self._job = None
