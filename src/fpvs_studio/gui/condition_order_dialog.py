"""Plain ordered-list editor over pure core condition-order services."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from typing import cast

from PySide6.QtCore import QPoint, QSignalBlocker, QSize, Qt, QTimer, Slot
from PySide6.QtGui import QDrag, QDragEnterEvent, QDragMoveEvent, QDropEvent, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    "Setup changed. Close and reopen the Pseudorandom Condition Order Editor "
    "to use the current settings."
)
_BLOCK_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class _ConditionOrderList(QListWidget):
    """Move an existing presentation through the editor's guarded draft callback."""

    def __init__(
        self, *, can_reorder: Callable[[], bool], move_row: Callable[[int, int], bool],
        can_move_row: Callable[[int, int], bool] | None = None,
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self._can_reorder = can_reorder
        self._move_row = move_row
        self._can_move_row = can_move_row
        self._revision = 0
        self._drag_source_row = -1
        self._drag_revision = -1
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)

    def startDrag(self, supportedActions: Qt.DropAction) -> None:  # noqa: N802
        item = self.currentItem()
        if (not self._can_reorder() or item is None
                or item.data(Qt.ItemDataRole.UserRole) is None):
            return
        mime = self.mimeData([item])
        if mime is None:
            return
        self._drag_source_row = self.row(item)
        self._drag_revision = self._revision
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.viewport().grab(self.visualItemRect(item)))
        try:
            # The editor owns the move; avoid QAbstractItemView's source-row deletion.
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self._drag_source_row = -1
            self._drag_revision = -1
            self.setState(QAbstractItemView.State.NoState)
            self.viewport().update()

    def _drop_row(self, position: QPoint) -> int:
        item = self.itemAt(position)
        if item is None:
            return self.count()
        row = self.row(item)
        return row + int(position.y() >= self.visualItemRect(item).center().y())

    def _accepts_drag(self, event: QDropEvent) -> bool:
        return (event.source() is self and self._can_reorder()
                and self._drag_revision == self._revision and self._drag_source_row >= 0)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if not self._accepts_drag(event):
            event.ignore()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        if (not self._accepts_drag(event)
                or (self._can_move_row is not None and not self._can_move_row(
                    self._drag_source_row, self._drop_row(event.position().toPoint()),
                ))):
            event.ignore()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        if (not self._accepts_drag(event)
                or not self._move_row(
                    self._drag_source_row, self._drop_row(event.position().toPoint()),
                )):
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()


class ConditionOrderDialog(QDialog):
    """Retain a chosen list until one atomic Save accepts all parent drafts."""

    def __init__(
        self, project: ProjectFile, *, seeds: RandomizationSeeds,
        presentation_counts: Mapping[str, int], current_signature: Callable[[], object],
        save_order: Callable[[list[str], RandomizationSeeds], None], parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pseudorandom Condition Order Editor")
        self.setObjectName("condition_order_dialog")
        self.setMinimumSize(700, 520)
        self.resize(780, 620)
        self._source_project = project
        self._snapshot = project.model_copy(deep=True)
        self._snapshot.settings.session.condition_ordering = "randomized_blocks"
        self._pending_counts = dict(presentation_counts)
        self._counts = {**condition_presentation_counts(project), **presentation_counts}
        self._current_signature = current_signature
        self._signature = current_signature()
        self._save_order = save_order
        self._seeds = seeds
        self._order = list(project.settings.session.saved_condition_order or [])
        if self._order and Counter(self._order) == self._counts:
            # Group matching occurrences into rounds in the draft, never in the source.
            rounds: dict[int, list[str]] = {}
            seen: Counter[str] = Counter()
            for condition_id in self._order:
                seen[condition_id] += 1
                rounds.setdefault(seen[condition_id], []).append(condition_id)
            self._order = [item for block in rounds.values() for item in block]
        self._job: UpdateJob | None = None
        self._dismissed = False
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        self.instruction_label = QLabel(
            "Drag conditions within each randomized block. "
            "Alt+Up/Down also moves the selected condition.", self,
        )
        self.instruction_label.setWordWrap(True)
        layout.addWidget(self.instruction_label)
        commands = QHBoxLayout()
        commands.setSpacing(8)
        self.generate_button = QPushButton("Generate new order", self)
        self.generate_button.setObjectName("generate_condition_order_button")
        self.generate_button.setToolTip(
            "Generate a pseudorandom order for the requested presentations. "
            "Some counts allow only one valid order.",
        )
        self.generate_button.setAutoDefault(False)
        mark_secondary_action(self.generate_button)
        commands.addWidget(self.generate_button)
        commands.addStretch(1)
        layout.addLayout(commands)
        self.order_list = _ConditionOrderList(
            can_reorder=self._reorder_enabled, move_row=self._reorder_condition, parent=self,
            can_move_row=lambda source, target: self._move_positions(source, target) is not None,
        )
        self.order_list.setObjectName("condition_order_list")
        self.order_list.setAccessibleName("Ordered condition presentations")
        self.order_list.setAccessibleDescription(self.instruction_label.text())
        self.order_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.order_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.order_list, 1)
        self.error_label = QLabel(self)
        self.error_label.setObjectName("condition_order_error")
        self.error_label.setWordWrap(True)
        mark_error_text(self.error_label)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        effect = (
            "Every participant receives this saved block order."
            if project.settings.session.condition_ordering == "randomized_blocks" else
            "Saving switches this project to randomized blocks and uses this order "
            "for every participant."
        )
        self.effect_label = QLabel(effect, self)
        self.effect_label.setWordWrap(True)
        layout.addWidget(self.effect_label)
        footer = QHBoxLayout()
        footer.addStretch(1)
        self.cancel_button = QPushButton("Cancel", self)
        self.save_button = QPushButton("Save order", self)
        self.save_button.setObjectName("save_condition_order_button")
        mark_secondary_action(self.cancel_button)
        mark_primary_action(self.save_button)
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)
        self.generate_button.clicked.connect(self.generate)
        self.move_up_shortcut = QShortcut("Alt+Up", self.order_list)
        self.move_down_shortcut = QShortcut("Alt+Down", self.order_list)
        for shortcut in (self.move_up_shortcut, self.move_down_shortcut):
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        self.move_up_shortcut.activated.connect(lambda: self._move_selected(-1))
        self.move_down_shortcut.activated.connect(lambda: self._move_selected(1))
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
        condition_rows: list[int] = []
        self.order_list._revision += 1
        with QSignalBlocker(self.order_list):
            self.order_list.clear()
            offset = 0
            for block_index in range(max(self._counts.values(), default=0)):
                size = sum(count > block_index for count in self._counts.values())
                partial = size < len(self._counts)
                header = QListWidgetItem(
                    f"Block {block_index + 1}" + (" (partial)" if partial else ""),
                )
                header.setData(_BLOCK_ROLE, block_index)
                header.setFlags(Qt.ItemFlag.ItemIsEnabled)
                font = header.font()
                font.setBold(True)
                header.setFont(font)
                header.setBackground(self.order_list.palette().alternateBase())
                header.setSizeHint(QSize(0, self.order_list.fontMetrics().height() + 14))
                header.setToolTip(
                    "Only conditions with presentations remaining appear in this block."
                    if partial else "Each condition appears once in this block."
                )
                self.order_list.addItem(header)
                for condition_id in self._order[offset:offset + size]:
                    occurrences[condition_id] += 1
                    # Use global list order, independent of the separator rows.
                    text = (f"{len(condition_rows) + 1}. {names.get(condition_id, condition_id)} "
                            f"· presentation {occurrences[condition_id]}")
                    item = QListWidgetItem(text)
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                                  | Qt.ItemFlag.ItemIsDragEnabled)
                    item.setData(Qt.ItemDataRole.UserRole, condition_id)
                    item.setData(_BLOCK_ROLE, block_index)
                    item.setData(Qt.ItemDataRole.AccessibleTextRole, text)
                    item.setToolTip(text)
                    condition_rows.append(self.order_list.count())
                    self.order_list.addItem(item)
                offset += size
            # Retain obsolete draft occurrences for validation instead of discarding them.
            for condition_id in self._order[offset:]:
                text = f"{len(condition_rows) + 1}. {names.get(condition_id, condition_id)}"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, condition_id)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setData(Qt.ItemDataRole.AccessibleTextRole, text)
                item.setToolTip(text)
                condition_rows.append(self.order_list.count())
                self.order_list.addItem(item)
            if condition_rows:
                self.order_list.setCurrentRow(
                    condition_rows[min(selected, len(condition_rows) - 1)],
                )
        self._update_buttons()

    def _reorder_enabled(self) -> bool:
        return self._job is None and not self._dismissed and not self._stale()

    def _move_positions(self, source_row: int, insertion_row: int) -> tuple[int, int] | None:
        if not self._reorder_enabled():
            return None
        item = self.order_list.item(source_row)
        if item is None or item.data(Qt.ItemDataRole.UserRole) is None:
            return None
        block_index = item.data(_BLOCK_ROLE)
        if block_index is None:
            return None
        rows = [row for row in range(self.order_list.count())
                if self.order_list.item(row).data(Qt.ItemDataRole.UserRole) is not None]
        block_rows = [row for row in rows
                      if self.order_list.item(row).data(_BLOCK_ROLE) == block_index]
        if not block_rows[0] <= insertion_row <= block_rows[-1] + 1:
            return None
        target_row = insertion_row - int(source_row < insertion_row)
        if target_row == source_row or target_row not in block_rows:
            return None
        return rows.index(source_row), rows.index(target_row)

    def _reorder_condition(self, source_row: int, insertion_row: int) -> bool:
        positions = self._move_positions(source_row, insertion_row)
        if positions is None:
            return False
        source, target = positions
        candidate = list(self._order)
        candidate.insert(target, candidate.pop(source))
        if Counter(candidate) != Counter(self._order):
            return False
        self._order = candidate
        self._render(target)
        return True

    def _update_buttons(self) -> None:
        busy = self._job is not None
        editable = self._reorder_enabled()
        self.generate_button.setEnabled(editable)
        self.order_list.setDragEnabled(editable)
        self.order_list.setAcceptDrops(editable)
        self.order_list.viewport().setAcceptDrops(editable)
        self.move_up_shortcut.setEnabled(editable)
        self.move_down_shortcut.setEnabled(editable)
        try:
            validate_saved_condition_order(self._order, self._counts, randomized_blocks=True)
        except ValueError as error:
            valid = False
            if not busy:
                self._error(str(error))
        else:
            valid = bool(self._order)
            if not busy:
                self._error("")
        self.save_button.setEnabled(editable and valid)

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
        source_row = self.order_list.currentRow()
        self._reorder_condition(source_row, source_row - 1 if offset < 0 else source_row + 2)

    def save(self) -> None:
        if self._job is not None or self._dismissed:
            return
        if self._stale():
            self._error(_STALE_SETUP_MESSAGE)
            return
        try:
            validate_saved_condition_order(self._order, self._counts, randomized_blocks=True)
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
