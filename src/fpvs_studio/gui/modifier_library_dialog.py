"""Small selection and naming dialogs for the local modifier workflow."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.components import (
    DialogHeader,
    apply_condition_modifier_theme,
    mark_primary_action,
)

if TYPE_CHECKING:
    from fpvs_studio.core.models import ProjectFile
    from fpvs_studio.core.modifier_presets import ModifierPreset


class ModifierLibraryDialog(QDialog):
    """Choose a built-in workflow or a complete local saved copy."""

    def __init__(
        self,
        presets: list[ModifierPreset],
        *,
        library_path: Path | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add FPVS Condition Modifier")
        self.setMinimumSize(660, 500)
        self.resize(700, 540)
        self.selection: tuple[str, str] | None = None
        self._presets = {preset.preset_id: preset for preset in presets}
        layout = QVBoxLayout(self)
        layout.addWidget(
            DialogHeader(
                "Add a modifier",
                "Choose a complete participant activity to customize.",
                parent=self,
            )
        )
        self.tabs = QTabWidget(self)
        self.built_in_list = QListWidget(self)
        for key, label in (
            ("backward-counting", "Backward counting"),
            ("image-memory", "Remember four images"),
            ("masking-color", "Masking — Colors"),
            ("masking-faces", "Masking — Faces"),
            ("masking-number", "Masking — Numbers"),
        ):
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.built_in_list.addItem(item)
        self.preset_list = QListWidget(self)
        for preset in presets:
            item = QListWidgetItem(preset.name)
            item.setToolTip(preset.name)
            item.setData(Qt.ItemDataRole.UserRole, preset.preset_id)
            self.preset_list.addItem(item)
        self.tabs.addTab(self.built_in_list, "Built-in")
        self.tabs.addTab(self.preset_list, "My presets")
        layout.addWidget(self.tabs, 1)
        self.details = QLabel(self)
        self.details.setWordWrap(True)
        self.details.setMinimumHeight(90)
        layout.addWidget(self.details)
        self.location = QLabel(
            str(library_path)
            if library_path is not None
            else "Choose an FPVS Studio Root Folder in Settings to enable local presets.",
            self,
        )
        self.location.setWordWrap(True)
        self.location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.location.setToolTip(self.location.text())
        layout.addWidget(self.location)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.add_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.add_button.setText("Add modifier")
        mark_primary_action(self.add_button)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.tabs.currentChanged.connect(self._refresh)
        self.built_in_list.currentRowChanged.connect(self._refresh)
        self.preset_list.currentRowChanged.connect(self._refresh)
        self.built_in_list.setCurrentRow(0)
        apply_condition_modifier_theme(self)
        self._refresh()

    def _refresh(self, *_args: object) -> None:
        selected = self.built_in_list if self.tabs.currentIndex() == 0 else self.preset_list
        item = selected.currentItem()
        self.add_button.setEnabled(item is not None)
        if item is None:
            self.details.setText(
                "No local presets yet. Customize a modifier, then choose Save as local preset."
            )
            return
        key = str(item.data(Qt.ItemDataRole.UserRole))
        if self.tabs.currentIndex() == 1:
            preset = self._presets[key]
            self.details.setText(preset.description or preset.definition.modifier.description)
        elif key == "backward-counting":
            self.details.setText(
                "Optional session baseline → random starting number → count backward during "
                "FPVS → report the final number. Records an estimated counting rate and "
                "baseline comparison. New defaults: subtract 13, 120-second baseline."
            )
        elif key.startswith("masking-"):
            self.details.setText(
                "Brief repeated target → delayed mask → visibility, identity and frequency "
                "questions. Edit SOA, native stimulus geometry, colors and all pre/post screens. "
                + ("Faces requires your base and target image pools."
                   if key == "masking-faces"
                   else "Includes the source stimulus palette or character pools.")
            )
        else:
            self.details.setText(
                "Study four images → keep them in mind during FPVS → select four from eight. "
                "Supply four target and four foil images. Records selected images, response "
                "time, target hits and exact-set correctness."
            )

    def accept(self) -> None:
        selected = self.built_in_list if self.tabs.currentIndex() == 0 else self.preset_list
        item = selected.currentItem()
        if item is None:
            return
        self.selection = (
            "built-in" if self.tabs.currentIndex() == 0 else "preset",
            str(item.data(Qt.ItemDataRole.UserRole)),
        )
        super().accept()


class ModifierScopeDialog(QDialog):
    """Review the exact condition assignments changed by one modifier."""

    def __init__(
        self,
        project: ProjectFile,
        *,
        selected_ids: list[str],
        conflicts: dict[str, str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Choose conditions")
        self.setMinimumSize(650, 460)
        self.resize(700, 500)
        self.condition_ids = selected_ids[:]
        self._initial = set(selected_ids)
        layout = QVBoxLayout(self)
        layout.addWidget(
            DialogHeader(
                "Choose conditions",
                "Each condition supports one sustained activity. Remove an existing activity "
                "before assigning a different one.",
                parent=self,
            )
        )
        self.conditions = QListWidget(self)
        for condition in sorted(project.conditions, key=lambda value: value.order_index):
            conflict = conflicts.get(condition.condition_id)
            label = condition.name + (f" · Uses {conflict}" if conflict else "")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, condition.condition_id)
            item.setToolTip(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if condition.condition_id in self._initial
                else Qt.CheckState.Unchecked
            )
            if conflict:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.conditions.addItem(item)
        layout.addWidget(self.conditions, 1)
        self.summary = QLabel(self)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Keep selection")
        mark_primary_action(buttons.button(QDialogButtonBox.StandardButton.Ok))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.conditions.itemChanged.connect(self._refresh)
        apply_condition_modifier_theme(self)
        self._refresh()

    def _selected(self) -> list[str]:
        return [
            str(self.conditions.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.conditions.count())
            if self.conditions.item(index).checkState() == Qt.CheckState.Checked
        ]

    def _refresh(self, *_args: object) -> None:
        chosen = set(self._selected())
        self.summary.setText(
            f"{len(chosen)} selected · {len(chosen - self._initial)} additions · "
            f"{len(self._initial - chosen)} removals. Changes remain pending until Apply."
        )

    def accept(self) -> None:
        self.condition_ids = self._selected()
        super().accept()


class SaveModifierPresetDialog(QDialog):
    """Name an explicit independent save to this computer's preset library."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        image_count: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save as local preset")
        self.setMinimumSize(590, 380)
        self.resize(640, 400)
        layout = QVBoxLayout(self)
        layout.addWidget(
            DialogHeader(
                "Save an independent preset",
                f"Includes this modifier's settings and {image_count} image references. "
                "Condition assignments and participant responses are excluded.",
                parent=self,
            )
        )
        form = QFormLayout()
        self.name_edit = QLineEdit(name, self)
        self.description_edit = QTextEdit(self)
        self.description_edit.setPlainText(description)
        self.description_edit.setMaximumHeight(90)
        form.addRow("Preset name", self.name_edit)
        form.addRow("Description", self.description_edit)
        layout.addLayout(form)
        note = QLabel(
            "This save takes effect immediately. Canceling the modifier editor afterward "
            "will discard its project draft, but keep this local preset.",
            self,
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText("Save local preset")
        mark_primary_action(self.save_button)
        self.name_edit.textChanged.connect(
            lambda text: self.save_button.setEnabled(bool(text.strip()))
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        apply_condition_modifier_theme(self)
