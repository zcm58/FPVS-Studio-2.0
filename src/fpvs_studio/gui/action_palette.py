"""Search existing UI commands without duplicating their handlers or permissions."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QSignalBlocker, Qt
from PySide6.QtGui import QAction, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.components import (
    DialogHeader,
    apply_action_palette_theme,
    mark_primary_action,
)


@dataclass(frozen=True)
class ActionEntry:
    action: QAction
    category: str
    keywords: str = ""
    label: str | None = None

    @property
    def title(self) -> str:
        return self.label or self.action.text().replace("&", "").rstrip(".\u2026")


class ActionPaletteDialog(QDialog):
    """Window-modal action search; the QAction remains the source of availability."""

    def __init__(
        self,
        entries: Sequence[ActionEntry],
        parent: QWidget | None = None,
        *,
        can_dispatch: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("action_palette_dialog")
        self.setWindowTitle("Find Action")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumSize(600, 400)
        self.resize(680, 460)
        self._entries = tuple(entries)
        self._can_dispatch = can_dispatch
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        header = DialogHeader("Find Action", "", parent=self)
        header.subtitle_label.hide()
        layout.addWidget(header)
        self.search_edit = QLineEdit(self)
        self.search_edit.setObjectName("action_palette_search")
        self.search_edit.setPlaceholderText("Search actions, tools, and settings")
        self.search_edit.setAccessibleName("Search actions")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumHeight(36)
        self.search_edit.installEventFilter(self)
        layout.addWidget(self.search_edit)
        self.result_count_label = QLabel(self)
        self.result_count_label.setObjectName("action_palette_result_count")
        self.result_count_label.setProperty("dialogHelp", "true")
        layout.addWidget(self.result_count_label)
        self.results = QTreeWidget(self)
        self.results.setObjectName("action_palette_results")
        self.results.setAccessibleName("Matching actions")
        self.results.setHeaderLabels(["Action", "Location", "Shortcut"])
        self.results.setRootIsDecorated(False)
        self.results.setUniformRowHeights(True)
        self.results.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.results.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.header().setStretchLastSection(False)
        self.results.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.results.installEventFilter(self)
        self.empty_label = QLabel(
            "No matching actions. Try another word or clear the search.", self,
        )
        self.empty_label.setObjectName("action_palette_empty")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_stack = QStackedWidget(self)
        self.result_stack.addWidget(self.results)
        self.result_stack.addWidget(self.empty_label)
        layout.addWidget(self.result_stack, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, parent=self)
        self.open_button = buttons.addButton("Open", QDialogButtonBox.ButtonRole.ActionRole)
        self.open_button.setObjectName("action_palette_open")
        self.open_button.setAutoDefault(False)
        mark_primary_action(self.open_button)
        layout.addWidget(buttons)
        buttons.rejected.connect(self.reject)
        self.open_button.clicked.connect(self._activate_current)
        self.search_edit.textChanged.connect(self._refresh_results)
        self.results.currentItemChanged.connect(self._update_open_button)
        self.results.itemActivated.connect(self._activate_current)
        for entry in self._entries:
            entry.action.changed.connect(self._on_action_changed)
        apply_action_palette_theme(self)
        self._refresh_results()

    def open(self) -> None:
        with QSignalBlocker(self.search_edit):
            self.search_edit.clear()
        self._refresh_results()
        super().open()
        self.search_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _on_action_changed(self) -> None:
        # The retained dialog rebuilds from current actions when reopened.
        if self.isVisible():
            self._refresh_results()

    def _refresh_results(self, *_args: object) -> None:
        previous = self.results.currentItem()
        previous_action = previous.data(0, Qt.ItemDataRole.UserRole) if previous else None
        tokens = self.search_edit.text().casefold().split()
        selection = None
        available_count = 0
        with QSignalBlocker(self.results):
            self.results.clear()
            for entry in self._entries:
                action = entry.action
                shortcut = action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
                haystack = f"{entry.title} {entry.category} {entry.keywords} {shortcut}".casefold()
                if not action.isVisible() or not all(token in haystack for token in tokens):
                    continue
                item = QTreeWidgetItem([entry.title, entry.category, shortcut])
                item.setData(0, Qt.ItemDataRole.UserRole, action)
                detail = f"{entry.title}\n{entry.category}"
                if shortcut:
                    detail += f"\n{shortcut}"
                if not action.isEnabled():
                    detail += "\nUnavailable in the current state."
                    item.setDisabled(True)
                else:
                    available_count += 1
                    if selection is None or action is previous_action:
                        selection = item
                if action.toolTip() and action.toolTip() != action.text():
                    detail += f"\n{action.toolTip()}"
                for column in range(3):
                    item.setToolTip(column, detail)
                item.setData(0, Qt.ItemDataRole.AccessibleTextRole, detail)
                self.results.addTopLevelItem(item)
            if selection is not None:
                self.results.setCurrentItem(selection)
        count = self.results.topLevelItemCount()
        noun = "action" if count == 1 else "actions"
        status = f"{count} {noun}"
        if count > available_count:
            status += f" \u00b7 {count - available_count} unavailable"
        self.result_count_label.setText(status)
        self.result_stack.setCurrentWidget(self.results if count else self.empty_label)
        self._update_open_button()

    def _update_open_button(self, *_args: object) -> None:
        item = self.results.currentItem()
        self.open_button.setEnabled(item is not None and not item.isDisabled())

    def _activate_current(self, *_args: object) -> None:
        item = self.results.currentItem()
        if item is None:
            return
        action = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(action, QAction) or not action.isEnabled() or not action.isVisible():
            self._refresh_results()
            return
        if self._can_dispatch is not None and not self._can_dispatch():
            self.reject()
            return
        # Release the modal surface before a handler opens its own dialog or changes projects.
        self.accept()
        action.trigger()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if isinstance(event, QKeyEvent) and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._activate_current()
                return True
            if watched is self.search_edit and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                available = []
                for index in range(self.results.topLevelItemCount()):
                    row = self.results.topLevelItem(index)
                    if row is not None and not row.isDisabled():
                        available.append(row)
                if available:
                    current = self.results.currentItem()
                    index = available.index(current) if current in available else -1
                    delta = 1 if event.key() == Qt.Key.Key_Down else -1
                    item = available[max(0, min(len(available) - 1, index + delta))]
                    self.results.setCurrentItem(item)
                    self.results.scrollToItem(item)
                return True
        return super().eventFilter(watched, event)
