"""Detached native stimulus editing for a masking condition modifier."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.masking import MaskingSettings
from fpvs_studio.core.scene_models import SceneVisual
from fpvs_studio.gui.components import (
    DialogHeader,
    apply_condition_modifier_theme,
    mark_error_text,
    mark_primary_action,
    refresh_widget_style,
)


class MaskingSourceDialog(QDialog):
    """Edit pools without copying media or changing the live project on Cancel."""

    def __init__(
        self, settings: MaskingSettings, *, project_root: Path, task_id: str,
        answers: dict[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Masking sources")
        self.setMinimumSize(940, 660)
        self.resize(1020, 700)
        self.settings = settings.model_copy(deep=True)
        self.asset_sources: dict[str, Path] = {}
        self._project_root = project_root
        self._task_id = task_id
        self._answers = answers or {value: value for value in settings.target_answers.values()}
        self._pools = [
            self.settings.base_visuals, self.settings.target_visuals,
            list(self.settings.mask_visuals or []), self.settings.base_overlays,
            [self.settings.fixation_visual] if self.settings.fixation_visual is not None else [],
        ]
        self._role = 0
        self._index = -1
        self._loading = False
        self._loaded: dict[str, object] = {}
        layout = QVBoxLayout(self)
        layout.addWidget(DialogHeader(
            "Masking sources",
            "Edit native shapes, text and images. Sizes retain their selected physical units; "
            "RGB channels use the PsychoPy range −1 to 1.", parent=self,
        ))
        self.role_combo = QComboBox(self)
        self.role_combo.addItems([
            "Base pool", "Target pool", "Mask pool — empty uses the base pool",
            "Backdrops behind every base and mask", "Fixation above the stream",
        ])
        layout.addWidget(self.role_combo)
        body = QHBoxLayout()
        sidebar = QVBoxLayout()
        self.source_list = QListWidget(self)
        self.source_list.setMinimumWidth(210)
        self.source_list.setMaximumWidth(270)
        sidebar.addWidget(self.source_list, 1)
        self.add_kind = QComboBox(self)
        for label, value in (("Circle", "circle"), ("Text", "text"), ("Rectangle", "rectangle")):
            self.add_kind.addItem(label, value)
        sidebar.addWidget(self.add_kind)
        self.add_button = QPushButton("Add native stimulus", self)
        self.add_button.clicked.connect(self._add_native)
        sidebar.addWidget(self.add_button)
        self.import_button = QPushButton("Add images…", self)
        self.import_button.clicked.connect(self._import_images)
        sidebar.addWidget(self.import_button)
        self.remove_button = QPushButton("Remove selected", self)
        self.remove_button.clicked.connect(self._remove)
        sidebar.addWidget(self.remove_button)
        body.addLayout(sidebar)
        self.tabs = QTabWidget(self)
        body.addWidget(self.tabs, 1)
        layout.addLayout(body, 1)
        self._build_content()
        self._build_geometry()
        self._build_appearance()
        self.status = QLabel(self)
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(40)
        layout.addWidget(self.status)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self,
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Keep source changes")
        mark_primary_action(self.buttons.button(QDialogButtonBox.StandardButton.Ok))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.source_list.currentRowChanged.connect(self._select_source)
        self.role_combo.currentIndexChanged.connect(self._select_role)
        apply_condition_modifier_theme(self)
        self._refresh_sources()

    @staticmethod
    def _spin(parent: QWidget, minimum: float, maximum: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(parent)
        spin.setDecimals(9)
        spin.setRange(minimum, maximum)
        return spin

    def _row(self, *widgets: QWidget) -> QWidget:
        holder = QWidget(self)
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        for widget in widgets:
            row.addWidget(widget)
        return holder

    def _page(self, title: str) -> QFormLayout:
        page = QWidget(self.tabs)
        form = QFormLayout(page)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.tabs.addTab(page, title)
        return form

    def _build_content(self) -> None:
        form = self._page("Content")
        self.identity_label = QLabel(self)
        self.identity_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.identity_label.setWordWrap(True)
        form.addRow("Stimulus", self.identity_label)
        self.text_edit = QLineEdit(self)
        form.addRow("Native text", self.text_edit)
        self.font_combo = QComboBox(self)
        self.font_combo.setEditable(True)
        self.font_combo.addItems(["Arial", "Arial Black", "Open Sans"])
        form.addRow("Font", self.font_combo)
        self.path_edit = QLineEdit(self)
        self.path_edit.setReadOnly(True)
        self.path_button = QPushButton("Choose image…", self)
        self.path_button.clicked.connect(self._replace_image)
        form.addRow("Image", self._row(self.path_edit, self.path_button))
        self.answer_combo = QComboBox(self)
        self.answer_combo.addItem("Choose the correct response", "")
        for value, label in self._answers.items():
            self.answer_combo.addItem(label, value)
        form.addRow("Target answer", self.answer_combo)
        note = QLabel(
            "Target answers must match the identity question's response values. "
            "Edit those questions with Edit modifier screens. Images are copied into "
            "the project only when you Apply modifiers.", self,
        )
        note.setWordWrap(True)
        form.addRow(note)

    def _build_geometry(self) -> None:
        form = self._page("Geometry")
        self.units_combo = QComboBox(self)
        for label, value in (("Degrees", "deg"), ("Centimeters", "cm"),
                             ("Window height", "height"), ("Pixels", "pix")):
            self.units_combo.addItem(label, value)
        form.addRow("Units", self.units_combo)
        self.x_spin, self.y_spin = (self._spin(self, -100000, 100000) for _ in range(2))
        form.addRow("Position X / Y", self._row(self.x_spin, self.y_spin))
        self.width_spin, self.height_spin = (self._spin(self, 0.000001, 100000) for _ in range(2))
        form.addRow("Width / height", self._row(self.width_spin, self.height_spin))
        self.text_height_spin = self._spin(self, 0.000001, 100000)
        form.addRow("Text height", self.text_height_spin)
        self.wrap_checkbox = QCheckBox("Set text wrap width", self)
        self.wrap_spin = self._spin(self, 0.000001, 100000)
        self.wrap_checkbox.toggled.connect(self.wrap_spin.setEnabled)
        form.addRow(self.wrap_checkbox, self.wrap_spin)
        self.edges_spin = QSpinBox(self)
        self.edges_spin.setRange(0, 100000)
        self.edges_spin.setSpecialValueText("Automatic")
        form.addRow("Circle edges", self.edges_spin)
        note = QLabel(
            "Circle width and height are diameters. Images use the exact authored box. "
            "Physical units require the presentation monitor's calibration.", self,
        )
        note.setWordWrap(True)
        form.addRow(note)

    def _build_appearance(self) -> None:
        form = self._page("Color & outline")
        self.rgb_spins = [self._spin(self, -1, 1) for _ in range(3)]
        form.addRow("Fill / text RGB", self._row(*self.rgb_spins))
        self.line_checkbox = QCheckBox("Draw an outline", self)
        self.line_rgb_spins = [self._spin(self, -1, 1) for _ in range(3)]
        form.addRow(self.line_checkbox, self._row(*self.line_rgb_spins))
        self.line_width_spin = self._spin(self, 0, 1000)
        form.addRow("Outline width (px)", self.line_width_spin)
        self.opacity_spin = self._spin(self, 0, 1)
        form.addRow("Opacity", self.opacity_spin)
        self.interpolate_checkbox = QCheckBox("Interpolate edges / images", self)
        form.addRow(self.interpolate_checkbox)
        self.line_checkbox.toggled.connect(self._outline_enabled)
        note = QLabel(
            "Values are signed RGB: −1 is the lowest channel value and 1 the highest. "
            "0, 0, 0 is neutral gray. Numeric values are retained without an 8-bit conversion.",
            self,
        )
        note.setWordWrap(True)
        form.addRow(note)

    def _outline_enabled(self, enabled: bool) -> None:
        for widget in [*self.line_rgb_spins, self.line_width_spin]:
            widget.setEnabled(enabled)

    def _values(self) -> dict[str, object]:
        return {
            "text": self.text_edit.text(), "font": self.font_combo.currentText(),
            "image_path": self.path_edit.text(), "units": self.units_combo.currentData(),
            "position": (self.x_spin.value(), self.y_spin.value()),
            "size": (self.width_spin.value(), self.height_spin.value()),
            "text_height": self.text_height_spin.value(),
            "wrap_width": self.wrap_spin.value() if self.wrap_checkbox.isChecked() else None,
            "rgb": tuple(spin.value() for spin in self.rgb_spins),
            "line_rgb": tuple(spin.value() for spin in self.line_rgb_spins)
            if self.line_checkbox.isChecked() else None,
            "line_width": self.line_width_spin.value(), "opacity": self.opacity_spin.value(),
            "edges": self.edges_spin.value() or None,
            "interpolate": self.interpolate_checkbox.isChecked(),
        }

    def _save_source(self) -> bool:
        if self._loading or self._index < 0:
            return True
        source = self._pools[self._role][self._index]
        updates = {key: value for key, value in self._values().items()
                   if value != self._loaded.get(key)}
        if source.kind != "text":
            for key in ("text", "font", "text_height", "wrap_width"):
                updates.pop(key, None)
        if source.kind != "image":
            updates.pop("image_path", None)
        try:
            updated = SceneVisual.model_validate({**source.model_dump(), **updates})
        except ValueError as error:
            self._error(str(error))
            return False
        self._pools[self._role][self._index] = updated
        if self._role == 1:
            value = str(self.answer_combo.currentData() or "")
            if value:
                self.settings.target_answers[source.visual_id] = value
            else:
                self.settings.target_answers.pop(source.visual_id, None)
        self._loaded = self._values()
        return True

    def _select_role(self, role: int) -> None:
        if not self._save_source():
            self.role_combo.blockSignals(True)
            self.role_combo.setCurrentIndex(self._role)
            self.role_combo.blockSignals(False)
            return
        self._role, self._index = role, -1
        self._refresh_sources()

    def _refresh_sources(self, selected: int = 0) -> None:
        self._loading = True
        self.source_list.clear()
        for visual in self._pools[self._role]:
            label = visual.text or (
                Path(visual.image_path).name if visual.image_path else visual.kind
            )
            self.source_list.addItem(f"{visual.visual_id} · {label}")
            self.source_list.item(self.source_list.count() - 1).setToolTip(
                f"{visual.visual_id}\n{visual.image_path or visual.text or visual.kind}"
            )
        self._index = -1
        self._loading = False
        self.source_list.setCurrentRow(min(selected, self.source_list.count() - 1))
        self._select_source(self.source_list.currentRow())
        single_full = self._role == 4 and bool(self._pools[4])
        self.add_button.setEnabled(not single_full)
        self.import_button.setEnabled(not single_full)
        self.status.setText(
            "Empty mask pool uses the base pool. Keep source changes returns to the modifier draft."
            if self._role == 2 else
            "Source changes stay in this draft. Apply modifiers saves them into the experiment."
        )
        self.status.setProperty("errorText", "false")
        refresh_widget_style(self.status)

    def _select_source(self, index: int) -> None:
        if self._loading:
            return
        if not self._save_source():
            self.source_list.blockSignals(True)
            self.source_list.setCurrentRow(self._index)
            self.source_list.blockSignals(False)
            return
        self._index = index
        self.tabs.setEnabled(index >= 0)
        self.remove_button.setEnabled(index >= 0)
        if index < 0:
            return
        self._loading = True
        visual = self._pools[self._role][index]
        is_text, is_image = visual.kind == "text", visual.kind == "image"
        self.identity_label.setText(f"{visual.visual_id} ({visual.kind})")
        self.text_edit.setText(visual.text or "")
        self.text_edit.setEnabled(is_text)
        self.font_combo.setCurrentText(visual.font)
        self.font_combo.setEnabled(is_text)
        self.path_edit.setText(visual.image_path or "")
        self.path_edit.setToolTip(visual.image_path or "")
        self.path_button.setEnabled(is_image)
        answer = self.settings.target_answers.get(visual.visual_id, "")
        answer_index = self.answer_combo.findData(answer)
        if answer_index < 0:
            self.answer_combo.addItem(answer, answer)
            answer_index = self.answer_combo.count() - 1
        self.answer_combo.setCurrentIndex(answer_index)
        self.answer_combo.setEnabled(self._role == 1)
        self.units_combo.setCurrentIndex(self.units_combo.findData(visual.units))
        for spin, value in zip((self.x_spin, self.y_spin), visual.position, strict=True):
            spin.setValue(value)
        for spin, value in zip(
            (self.width_spin, self.height_spin), visual.size or (5, 5), strict=True,
        ):
            spin.setValue(value)
            spin.setEnabled(not is_text)
        self.text_height_spin.setValue(visual.text_height or 5)
        self.text_height_spin.setEnabled(is_text)
        self.wrap_checkbox.setChecked(visual.wrap_width is not None)
        self.wrap_checkbox.setEnabled(is_text)
        self.wrap_spin.setValue(visual.wrap_width or 30)
        self.wrap_spin.setEnabled(is_text and visual.wrap_width is not None)
        self.edges_spin.setValue(visual.edges or 0)
        self.edges_spin.setEnabled(visual.kind == "circle")
        for spin, value in zip(self.rgb_spins, visual.rgb, strict=True):
            spin.setValue(value)
        for spin, value in zip(self.line_rgb_spins, visual.line_rgb or (1, 1, 1), strict=True):
            spin.setValue(value)
        self.line_checkbox.setChecked(visual.line_rgb is not None)
        self.line_checkbox.setEnabled(visual.kind in ("circle", "rectangle"))
        self.line_width_spin.setValue(visual.line_width)
        self._outline_enabled(
            visual.line_rgb is not None and visual.kind in ("circle", "rectangle")
        )
        self.opacity_spin.setValue(visual.opacity)
        self.interpolate_checkbox.setChecked(visual.interpolate)
        self._loaded = self._values()
        self._loading = False

    def _add_native(self) -> None:
        if not self._save_source():
            return
        kind = str(self.add_kind.currentData())
        data: dict[str, object] = {
            "kind": kind, "visual_id": f"{kind}-{uuid4().hex[:10]}", "units": "deg",
        }
        data.update({"text": "A", "text_height": 5} if kind == "text" else {"size": (5, 5)})
        self._pools[self._role].append(SceneVisual.model_validate(data))
        self._refresh_sources(len(self._pools[self._role]) - 1)

    def _image_reference(self, source: Path) -> str:
        filename = f"masking-{uuid4().hex}{source.suffix.lower()}"
        relative = f"stimuli/task-assets/{self._task_id}/{filename}"
        self.asset_sources[relative] = source
        return relative

    def _import_images(self) -> None:
        if not self._save_source():
            return
        paths, _filter = QFileDialog.getOpenFileNames(
            self, "Add masking images", str(self._project_root), "Images (*.png *.jpg *.jpeg)",
        )
        if self._role == 4 and len(paths) > 1:
            self._error("Fixation accepts one visual. Choose one image.")
            return
        for filename in paths:
            self._pools[self._role].append(SceneVisual(
                visual_id=f"image-{uuid4().hex[:10]}", kind="image",
                image_path=self._image_reference(Path(filename)), size=(5, 5), units="deg",
            ))
        if paths:
            self._refresh_sources(len(self._pools[self._role]) - 1)

    def _replace_image(self) -> None:
        filename, _filter = QFileDialog.getOpenFileName(
            self, "Choose masking image", str(self._project_root), "Images (*.png *.jpg *.jpeg)",
        )
        if filename:
            relative = self._image_reference(Path(filename))
            self.path_edit.setText(relative)
            self.path_edit.setToolTip(relative)

    def _remove(self) -> None:
        if self._index < 0:
            return
        visual = self._pools[self._role].pop(self._index)
        if self._role == 1:
            self.settings.target_answers.pop(visual.visual_id, None)
        self._index = -1
        self._refresh_sources()

    def _error(self, message: str) -> None:
        self.status.setText(message)
        mark_error_text(self.status)

    def accept(self) -> None:
        if not self._save_source():
            return
        self.settings.base_visuals, self.settings.target_visuals = self._pools[:2]
        self.settings.mask_visuals = self._pools[2] or None
        self.settings.base_overlays = self._pools[3]
        self.settings.fixation_visual = self._pools[4][0] if self._pools[4] else None
        try:
            self.settings = MaskingSettings.model_validate(self.settings.model_dump())
        except ValueError as error:
            self._error(str(error))
            return
        super().accept()
