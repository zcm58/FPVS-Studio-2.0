"""Draft-based authoring dialog for stimulus presentation settings."""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from math import atan, degrees
from pathlib import Path
from typing import TypeVar

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.enums import (
    ImageGeometryMode,
    PresentationUnit,
    StimulusModality,
    StimulusTransform,
    StimulusVariant,
    TextHeightMode,
)
from fpvs_studio.core.models import (
    ConditionPresentationSettings,
    ImageGeometrySettings,
    ProjectPresentationSettings,
    StimulusPresentationDefaults,
    StimulusPresentationOverride,
    StimulusSet,
    TextHeightScheduleSettings,
    TextPositionSettings,
)
from fpvs_studio.core.paths import (
    resolve_project_relative_path,
    stimulus_derived_dir,
    stimulus_variant_dirname,
)
from fpvs_studio.core.presentation import resolve_role_presentation
from fpvs_studio.gui.components import (
    FiniteDoubleSpinBox,
    apply_studio_theme,
    mark_error_text,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.preprocessing.manifest import asset_variant_path, find_manifest_set

_GROUP_NAMES = ("transform", "image_geometry", "text_height", "text_color", "text_position")
_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})
_PREVIEW_SAMPLE_LIMIT = 60
_SampleItem = TypeVar("_SampleItem")


def _representative_sample(values: Sequence[_SampleItem]) -> list[_SampleItem]:
    """Return a deterministic bounded sample without filling a combo with thousands of rows."""

    if len(values) <= _PREVIEW_SAMPLE_LIMIT:
        return list(values)
    denominator = _PREVIEW_SAMPLE_LIMIT - 1
    indices = {
        round(index * (len(values) - 1) / denominator) for index in range(_PREVIEW_SAMPLE_LIMIT)
    }
    return [values[index] for index in sorted(indices)]


def _enum_label(value: object) -> str:
    labels: dict[object, str] = {
        StimulusTransform.NONE: "None",
        StimulusTransform.MIRROR_HORIZONTAL: "Mirror horizontally",
        StimulusTransform.MIRROR_VERTICAL: "Mirror vertically",
        StimulusTransform.ROT180: "Rotate 180 degrees",
        ImageGeometryMode.EXACT_BOX: "Exact box (may stretch)",
        ImageGeometryMode.CONTAIN: "Contain (preserve aspect)",
        ImageGeometryMode.COVER: "Cover (crop to fill)",
        ImageGeometryMode.NATURAL_ASPECT: "Natural aspect",
        PresentationUnit.DEGREES: "Degrees of visual angle",
        PresentationUnit.WINDOW_HEIGHT_FRACTION: "Fraction of window height",
        TextHeightMode.FIXED: "Fixed",
        TextHeightMode.BALANCED_RANDOMIZED: "Balanced randomized",
    }
    return labels[value]


def _preview_background_color(value: object) -> str:
    if (
        isinstance(value, tuple)
        and len(value) == 3
        and all(isinstance(channel, int) for channel in value)
    ):
        return "#{:02X}{:02X}{:02X}".format(*value)
    return str(value)


def presentation_defaults_summary(defaults: StimulusPresentationDefaults) -> str:
    """Return a compact project-default presentation summary."""

    geometry = defaults.image_geometry
    if geometry.mode == ImageGeometryMode.NATURAL_ASPECT:
        if geometry.width_degrees is not None:
            geometry_text = f"Natural aspect, {geometry.width_degrees:g} deg wide"
        else:
            geometry_text = f"Natural aspect, {geometry.height_degrees:g} deg high"
    else:
        geometry_text = (
            f"{_enum_label(geometry.mode).split(' (', 1)[0]}, "
            f"{geometry.width_degrees:g} x {geometry.height_degrees:g} deg"
        )
    return f"{geometry_text}; {_enum_label(defaults.transform).lower()}"


def condition_presentation_summary(document: ProjectDocument, condition_id: str) -> str:
    """Return a compact effective Base/Oddball summary for one condition."""

    condition = document.get_condition(condition_id)
    if condition is None:
        return "No condition selected"
    project_presentation = document.project.settings.presentation
    base = resolve_role_presentation(project_presentation, condition.presentation, "base")
    oddball = resolve_role_presentation(project_presentation, condition.presentation, "oddball")
    modality = document.get_condition_stimulus_set(condition_id, "base").modality

    def _role_summary(settings: StimulusPresentationDefaults) -> str:
        if modality == StimulusModality.WORD:
            values = ", ".join(f"{value:g}" for value in settings.text_height.values)
            return (
                f"Arial, {_enum_label(settings.transform).lower()}, "
                f"{_enum_label(settings.text_height.mode).lower()} {values} "
                f"({_enum_label(settings.text_height.unit).lower()})"
            )
        return presentation_defaults_summary(settings)

    if base == oddball:
        return _role_summary(base)
    return f"Base: {_role_summary(base)}; Oddball: {_role_summary(oddball)}"


def _double_spin(
    *,
    object_name: str,
    minimum: float,
    maximum: float | None = None,
    step: float = 0.1,
) -> FiniteDoubleSpinBox:
    spin = (
        FiniteDoubleSpinBox(minimum=minimum)
        if maximum is None
        else FiniteDoubleSpinBox(minimum=minimum, maximum=maximum)
    )
    spin.setObjectName(object_name)
    spin.setSingleStep(step)
    return spin


class PresentationDefaultsEditor(QWidget):
    """Edit complete defaults or atomic optional override groups."""

    changed = Signal()

    def __init__(
        self,
        *,
        inherited: StimulusPresentationDefaults,
        override: StimulusPresentationOverride | None,
        object_prefix: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(f"{object_prefix}_editor")
        self._inherited = inherited.model_copy(deep=True)
        self._optional = override is not None
        self._prefix = object_prefix
        self._loading = False
        self._legacy_text_height_fraction: float | None = None
        initial = override or StimulusPresentationOverride(
            transform=inherited.transform,
            image_geometry=inherited.image_geometry,
            text_height=inherited.text_height,
            text_color=inherited.text_color,
            text_position=inherited.text_position,
        )

        self.transform_combo = QComboBox(self)
        self.transform_combo.setObjectName(f"{object_prefix}_transform_combo")
        for transform in StimulusTransform:
            self.transform_combo.addItem(_enum_label(transform), transform)

        self.geometry_mode_combo = QComboBox(self)
        self.geometry_mode_combo.setObjectName(f"{object_prefix}_geometry_mode_combo")
        for geometry_mode in ImageGeometryMode:
            self.geometry_mode_combo.addItem(_enum_label(geometry_mode), geometry_mode)
        self.geometry_width_spin = _double_spin(
            object_name=f"{object_prefix}_geometry_width_spin",
            minimum=0.0,
        )
        self.geometry_width_spin.setSuffix(" deg")
        self.geometry_height_spin = _double_spin(
            object_name=f"{object_prefix}_geometry_height_spin",
            minimum=0.0,
        )
        self.geometry_height_spin.setSuffix(" deg")
        self.natural_dimension_combo = QComboBox(self)
        self.natural_dimension_combo.setObjectName(f"{object_prefix}_natural_dimension_combo")
        self.natural_dimension_combo.addItem("Specify width", "width")
        self.natural_dimension_combo.addItem("Specify height", "height")

        self.text_height_mode_combo = QComboBox(self)
        self.text_height_mode_combo.setObjectName(f"{object_prefix}_text_height_mode_combo")
        for text_height_mode in TextHeightMode:
            self.text_height_mode_combo.addItem(
                _enum_label(text_height_mode),
                text_height_mode,
            )
        self.text_height_unit_combo = QComboBox(self)
        self.text_height_unit_combo.setObjectName(f"{object_prefix}_text_height_unit_combo")
        for height_unit in PresentationUnit:
            self.text_height_unit_combo.addItem(_enum_label(height_unit), height_unit)
        self.text_height_values_edit = QLineEdit(self)
        self.text_height_values_edit.setObjectName(f"{object_prefix}_text_height_values_edit")
        self.text_height_values_edit.setPlaceholderText("Example: 0.03, 0.04, 0.05")
        self.text_height_values_edit.setToolTip(
            "Enter one fixed value or two or more unique randomized values."
        )
        self.font_value_label = QLabel("Arial (fixed)", self)
        self.font_value_label.setObjectName(f"{object_prefix}_font_value_label")

        self.text_color_edit = QLineEdit(self)
        self.text_color_edit.setObjectName(f"{object_prefix}_text_color_edit")
        self.text_color_edit.setPlaceholderText("#FFFFFF")
        self.position_unit_combo = QComboBox(self)
        self.position_unit_combo.setObjectName(f"{object_prefix}_position_unit_combo")
        for position_unit in PresentationUnit:
            self.position_unit_combo.addItem(_enum_label(position_unit), position_unit)
        self.position_x_spin = _double_spin(
            object_name=f"{object_prefix}_position_x_spin",
            minimum=-sys.float_info.max,
        )
        self.position_y_spin = _double_spin(
            object_name=f"{object_prefix}_position_y_spin",
            minimum=-sys.float_info.max,
        )

        self._override_checks: dict[str, QCheckBox] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        layout.addWidget(
            self._group_box(
                "Transform",
                "transform",
                self._form(("Runtime transform", self.transform_combo)),
            )
        )
        geometry_form = self._form(
            ("Fit mode", self.geometry_mode_combo),
            ("Natural dimension", self.natural_dimension_combo),
            ("Width", self.geometry_width_spin),
            ("Height", self.geometry_height_spin),
        )
        layout.addWidget(self._group_box("Image geometry", "image_geometry", geometry_form))
        height_form = self._form(
            ("Schedule", self.text_height_mode_combo),
            ("Units", self.text_height_unit_combo),
            ("Height values", self.text_height_values_edit),
            ("Experiment font", self.font_value_label),
        )
        layout.addWidget(self._group_box("Word height", "text_height", height_form))
        layout.addWidget(
            self._group_box(
                "Word color",
                "text_color",
                self._form(("Opaque sRGB", self.text_color_edit)),
            )
        )
        position_form = self._form(
            ("Units", self.position_unit_combo),
            ("Horizontal (x)", self.position_x_spin),
            ("Vertical (y)", self.position_y_spin),
        )
        layout.addWidget(self._group_box("Word position", "text_position", position_form))
        layout.addStretch(1)

        self.geometry_mode_combo.currentIndexChanged.connect(self._update_geometry_state)
        self.natural_dimension_combo.currentIndexChanged.connect(self._update_geometry_state)
        self.text_height_mode_combo.currentIndexChanged.connect(self._update_height_state)
        self.text_height_mode_combo.currentIndexChanged.connect(
            self._clear_legacy_text_height_compatibility
        )
        self.text_height_unit_combo.currentIndexChanged.connect(
            self._clear_legacy_text_height_compatibility
        )
        self.text_height_values_edit.textChanged.connect(
            self._clear_legacy_text_height_compatibility
        )
        for combo in (
            self.transform_combo,
            self.geometry_mode_combo,
            self.natural_dimension_combo,
            self.text_height_mode_combo,
            self.text_height_unit_combo,
            self.position_unit_combo,
        ):
            combo.currentIndexChanged.connect(self._emit_changed)
        for spin in (
            self.geometry_width_spin,
            self.geometry_height_spin,
            self.position_x_spin,
            self.position_y_spin,
        ):
            spin.valueChanged.connect(self._emit_changed)
        for edit in (self.text_height_values_edit, self.text_color_edit):
            edit.textChanged.connect(self._emit_changed)

        self._load(initial)

    @staticmethod
    def _form(*rows: tuple[str, QWidget]) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        for label, widget in rows:
            form.addRow(label, widget)
        return panel

    def _group_box(self, title: str, name: str, content: QWidget) -> QGroupBox:
        group = QGroupBox(title, self)
        group.setObjectName(f"{self._prefix}_{name}_group")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(10, 8, 10, 8)
        group_layout.setSpacing(6)
        if self._optional:
            check = QCheckBox("Override inherited value (clear to reset)", group)
            check.setObjectName(f"{self._prefix}_{name}_override_checkbox")
            check.toggled.connect(self._update_group_enablement)
            if name == "image_geometry":
                check.toggled.connect(self._update_geometry_state)
            check.toggled.connect(self._emit_changed)
            check.setToolTip("Clear this option to reset the entire group to its inherited value.")
            group_layout.addWidget(check)
            self._override_checks[name] = check
        group_layout.addWidget(content)
        content.setProperty("presentationGroupContent", name)
        return group

    def _emit_changed(self, *_args: object) -> None:
        """Normalize value-bearing widget signals to the editor's no-argument signal."""

        self.changed.emit()

    def _load(self, value: StimulusPresentationOverride) -> None:
        self._loading = True
        try:
            effective = self._inherited
            for group_name in _GROUP_NAMES:
                own_value = getattr(value, group_name)
                selected = own_value is not None
                if self._optional:
                    self._override_checks[group_name].setChecked(selected)
                group_value = own_value if selected else getattr(effective, group_name)
                if group_name == "transform":
                    self.transform_combo.setCurrentIndex(self.transform_combo.findData(group_value))
                elif group_name == "image_geometry":
                    self._set_geometry(group_value)
                elif group_name == "text_height":
                    self._legacy_text_height_fraction = group_value.legacy_stimulus_width_fraction
                    self.text_height_mode_combo.setCurrentIndex(
                        self.text_height_mode_combo.findData(group_value.mode)
                    )
                    self.text_height_unit_combo.setCurrentIndex(
                        self.text_height_unit_combo.findData(group_value.unit)
                    )
                    self.text_height_values_edit.setText(
                        ", ".join(repr(item) for item in group_value.values)
                    )
                elif group_name == "text_color":
                    self.text_color_edit.setText(group_value)
                elif group_name == "text_position":
                    self.position_unit_combo.setCurrentIndex(
                        self.position_unit_combo.findData(group_value.unit)
                    )
                    self.position_x_spin.setValue(group_value.x)
                    self.position_y_spin.setValue(group_value.y)
            self._update_group_enablement()
            self._update_geometry_state()
            self._update_height_state()
        finally:
            self._loading = False

    def _set_geometry(self, value: ImageGeometrySettings) -> None:
        self.geometry_mode_combo.setCurrentIndex(self.geometry_mode_combo.findData(value.mode))
        width_driven = value.width_degrees is not None
        self.natural_dimension_combo.setCurrentIndex(0 if width_driven else 1)
        self.geometry_width_spin.setValue(value.width_degrees or 5.0)
        self.geometry_height_spin.setValue(value.height_degrees or 5.0)

    def _update_group_enablement(self) -> None:
        if not self._optional:
            return
        for name, check in self._override_checks.items():
            group = self.findChild(QGroupBox, f"{self._prefix}_{name}_group")
            if group is None:
                continue
            for child in group.findChildren(QWidget):
                if child.property("presentationGroupContent") == name:
                    child.setEnabled(check.isChecked())

    def _update_geometry_state(self) -> None:
        mode = self.geometry_mode_combo.currentData()
        natural = mode == ImageGeometryMode.NATURAL_ASPECT
        self.natural_dimension_combo.setVisible(natural)
        width_driven = self.natural_dimension_combo.currentData() == "width"
        self.geometry_width_spin.setEnabled(not natural or width_driven)
        self.geometry_height_spin.setEnabled(not natural or not width_driven)
        if self._optional and not self._override_checks["image_geometry"].isChecked():
            self.geometry_width_spin.setEnabled(False)
            self.geometry_height_spin.setEnabled(False)
            self.natural_dimension_combo.setEnabled(False)
        self.changed.emit()

    def _update_height_state(self) -> None:
        randomized = self.text_height_mode_combo.currentData() == (
            TextHeightMode.BALANCED_RANDOMIZED
        )
        self.text_height_values_edit.setToolTip(
            "Enter two or more unique comma-separated values. Studio balances their use "
            "without immediate repeats."
            if randomized
            else "Enter exactly one fixed text-height value."
        )
        self.changed.emit()

    def _clear_legacy_text_height_compatibility(self) -> None:
        if not self._loading:
            self._legacy_text_height_fraction = None

    def set_inherited(self, inherited: StimulusPresentationDefaults) -> None:
        """Refresh disabled controls to show their newly inherited values."""

        if not self._optional:
            return
        current = self.build_override()
        self._inherited = inherited.model_copy(deep=True)
        self._load(current)

    def _parse_height_values(self) -> list[float]:
        parts = [item for item in re.split(r"[,;\s]+", self.text_height_values_edit.text()) if item]
        return [float(item) for item in parts]

    def _image_geometry(self) -> ImageGeometrySettings:
        mode = self.geometry_mode_combo.currentData()
        if mode == ImageGeometryMode.NATURAL_ASPECT:
            if self.natural_dimension_combo.currentData() == "width":
                return ImageGeometrySettings(
                    mode=mode,
                    width_degrees=self.geometry_width_spin.value(),
                    height_degrees=None,
                )
            return ImageGeometrySettings(
                mode=mode,
                width_degrees=None,
                height_degrees=self.geometry_height_spin.value(),
            )
        return ImageGeometrySettings(
            mode=mode,
            width_degrees=self.geometry_width_spin.value(),
            height_degrees=self.geometry_height_spin.value(),
        )

    def _text_height(self) -> TextHeightScheduleSettings:
        return TextHeightScheduleSettings(
            mode=self.text_height_mode_combo.currentData(),
            unit=self.text_height_unit_combo.currentData(),
            values=self._parse_height_values(),
            legacy_stimulus_width_fraction=self._legacy_text_height_fraction,
        )

    def _text_position(self) -> TextPositionSettings:
        return TextPositionSettings(
            unit=self.position_unit_combo.currentData(),
            x=self.position_x_spin.value(),
            y=self.position_y_spin.value(),
        )

    def build_defaults(self) -> StimulusPresentationDefaults:
        return StimulusPresentationDefaults(
            transform=self.transform_combo.currentData(),
            image_geometry=self._image_geometry(),
            text_height=self._text_height(),
            text_color=self.text_color_edit.text().strip(),
            text_position=self._text_position(),
        )

    def build_override(self) -> StimulusPresentationOverride:
        if not self._optional:
            defaults = self.build_defaults()
            return StimulusPresentationOverride(**defaults.model_dump())
        return StimulusPresentationOverride(
            transform=(
                self.transform_combo.currentData()
                if self._override_checks["transform"].isChecked()
                else None
            ),
            image_geometry=(
                self._image_geometry()
                if self._override_checks["image_geometry"].isChecked()
                else None
            ),
            text_height=(
                self._text_height() if self._override_checks["text_height"].isChecked() else None
            ),
            text_color=(
                self.text_color_edit.text().strip()
                if self._override_checks["text_color"].isChecked()
                else None
            ),
            text_position=(
                self._text_position()
                if self._override_checks["text_position"].isChecked()
                else None
            ),
        )


class _PresentationPreview(QWidget):
    """Scaled, timing-neutral preview for one effective role presentation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("presentation_live_preview")
        self.setMinimumSize(320, 280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._settings = StimulusPresentationDefaults()
        self._modality = StimulusModality.WORD
        self._text = "READ"
        self._image_path: Path | None = None
        self._height_value = self._settings.text_height.values[0]
        self._background = QColor("#000000")

    def set_preview(
        self,
        *,
        settings: StimulusPresentationDefaults,
        modality: StimulusModality,
        value: str | Path | None,
        height_value: float,
        background: str,
    ) -> None:
        self._settings = settings
        self._modality = modality
        self._text = str(value) if isinstance(value, str) else "READ"
        self._image_path = value if isinstance(value, Path) else None
        self._height_value = height_value
        self._background = QColor(background)
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), self._background)
        painter.setPen(QPen(QColor("#64748b"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if self._modality == StimulusModality.IMAGE:
            self._paint_image(painter)
        else:
            self._paint_word(painter)

    def _apply_transform(self, painter: QPainter, center_x: float, center_y: float) -> None:
        transform = self._settings.transform
        painter.translate(center_x, center_y)
        if transform == StimulusTransform.MIRROR_HORIZONTAL:
            painter.scale(-1.0, 1.0)
        elif transform == StimulusTransform.MIRROR_VERTICAL:
            painter.scale(1.0, -1.0)
        elif transform == StimulusTransform.ROT180:
            painter.rotate(180.0)
        painter.translate(-center_x, -center_y)

    def _geometry_box(self, aspect: float) -> QRectF:
        geometry = self._settings.image_geometry
        width = geometry.width_degrees
        height = geometry.height_degrees
        if geometry.mode == ImageGeometryMode.NATURAL_ASPECT:
            if width is not None:
                height = width / max(aspect, 0.01)
            else:
                height = height or 5.0
                width = height * aspect
        width = width or 5.0
        height = height or 5.0
        scale = min((self.width() - 44) / width, (self.height() - 44) / height, 46.0)
        box_width = max(1.0, width * scale)
        box_height = max(1.0, height * scale)
        return QRectF(
            (self.width() - box_width) / 2,
            (self.height() - box_height) / 2,
            box_width,
            box_height,
        )

    def _paint_image(self, painter: QPainter) -> None:
        pixmap = QPixmap(str(self._image_path)) if self._image_path else QPixmap()
        if pixmap.isNull():
            pixmap = QPixmap(320, 240)
            pixmap.fill(QColor("#e2e8f0"))
        aspect = pixmap.width() / max(1, pixmap.height())
        box = self._geometry_box(aspect)
        painter.setPen(QPen(QColor("#60a5fa"), 1, Qt.PenStyle.DashLine))
        painter.drawRect(box)
        painter.save()
        self._apply_transform(painter, box.center().x(), box.center().y())
        mode = self._settings.image_geometry.mode
        if mode == ImageGeometryMode.EXACT_BOX:
            painter.drawPixmap(box, pixmap, QRectF(pixmap.rect()))
        else:
            target = pixmap.scaled(
                int(box.width()),
                int(box.height()),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding
                if mode == ImageGeometryMode.COVER
                else Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            target_rect = QRectF(
                box.center().x() - target.width() / 2,
                box.center().y() - target.height() / 2,
                target.width(),
                target.height(),
            )
            if mode == ImageGeometryMode.COVER:
                painter.setClipRect(box)
            painter.drawPixmap(target_rect, target, QRectF(target.rect()))
        painter.restore()

    def _paint_word(self, painter: QPainter) -> None:
        position = self._settings.text_position
        if position.unit == PresentationUnit.WINDOW_HEIGHT_FRACTION:
            x_offset = position.x * self.height()
            y_offset = -position.y * self.height()
        else:
            x_offset = position.x * 26.0
            y_offset = -position.y * 26.0
        center_x = self.width() / 2 + x_offset
        center_y = self.height() / 2 + y_offset
        if self._settings.text_height.unit == PresentationUnit.WINDOW_HEIGHT_FRACTION:
            pixel_height = self._height_value * self.height()
        else:
            pixel_height = self._height_value * 30.0
        font = QFont("Arial")
        font.setPixelSize(max(1, min(int(round(pixel_height)), self.height() - 20)))
        painter.setFont(font)
        painter.setPen(QColor(self._settings.text_color))
        rect = QRectF(8, center_y - self.height() / 2, self.width() - 16, self.height())
        painter.save()
        self._apply_transform(painter, center_x, center_y)
        painter.drawText(rect.translated(x_offset, 0), Qt.AlignmentFlag.AlignCenter, self._text)
        painter.restore()


class PresentationSettingsDialog(QDialog):
    """Edit project defaults or one condition's inherited presentation settings."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        condition_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("presentation_settings_dialog")
        self.setWindowTitle("Condition Presentation" if condition_id else "Presentation Defaults")
        self.setModal(True)
        self.resize(1000, 640)
        self.setMinimumSize(900, 600)
        self._document = document
        self._condition_id = condition_id
        self._project_draft = document.project.settings.presentation.model_copy(deep=True)
        condition = document.get_condition(condition_id) if condition_id else None
        if condition_id is not None and condition is None:
            raise ValueError(f"Unknown condition '{condition_id}'.")
        self._condition_draft = (
            condition.presentation.model_copy(deep=True) if condition is not None else None
        )
        self._syncing_inheritance = False

        header = QLabel(
            (
                f"Presentation overrides for {condition.name}"
                if condition is not None
                else "Project presentation defaults"
            ),
            self,
        )
        header.setObjectName("presentation_settings_header")
        header.setProperty("sectionCardRole", "title")
        helper = QLabel(
            "Runtime transforms do not create stimulus files. Condition settings inherit "
            "from the project, then Base and Oddball may override complete groups.",
            self,
        )
        helper.setObjectName("presentation_settings_helper")
        helper.setWordWrap(True)

        self.editor_tabs = QTabWidget(self)
        self.editor_tabs.setObjectName("presentation_settings_tabs")
        self._editors: dict[str, PresentationDefaultsEditor] = {}
        if condition is None:
            editor = PresentationDefaultsEditor(
                inherited=self._project_draft.defaults,
                override=None,
                object_prefix="project_presentation",
                parent=self.editor_tabs,
            )
            self._editors["project"] = editor
            self.editor_tabs.addTab(self._scroll_editor(editor), "Project defaults")
        else:
            condition_draft = self._condition_draft
            assert condition_draft is not None
            common = PresentationDefaultsEditor(
                inherited=self._project_draft.defaults,
                override=condition_draft.common,
                object_prefix="condition_presentation",
                parent=self.editor_tabs,
            )
            self._editors["common"] = common
            common_effective = self._apply_override(
                self._project_draft.defaults, common.build_override()
            )
            for role in ("base", "oddball"):
                editor = PresentationDefaultsEditor(
                    inherited=common_effective,
                    override=getattr(condition_draft, role),
                    object_prefix=f"{role}_presentation",
                    parent=self.editor_tabs,
                )
                self._editors[role] = editor
            self.editor_tabs.addTab(self._scroll_editor(common), "Condition")
            self.editor_tabs.addTab(self._scroll_editor(self._editors["base"]), "Base")
            self.editor_tabs.addTab(self._scroll_editor(self._editors["oddball"]), "Oddball")

        self.condition_lead_in_checkbox: QCheckBox | None = None
        self.condition_lead_in_spin: FiniteDoubleSpinBox | None = None
        if condition is not None:
            condition_draft = self._condition_draft
            assert condition_draft is not None
            self.condition_lead_in_checkbox = QCheckBox(
                "Override the project's pre-stream fixation duration",
                self,
            )
            self.condition_lead_in_checkbox.setObjectName(
                "condition_pre_stream_fixation_override_checkbox"
            )
            self.condition_lead_in_spin = _double_spin(
                object_name="condition_pre_stream_fixation_seconds_spin",
                minimum=0.0,
                step=0.25,
            )
            self.condition_lead_in_spin.setSuffix(" s")
            own_lead_in = condition_draft.pre_stream_fixation_seconds
            self.condition_lead_in_checkbox.setChecked(own_lead_in is not None)
            self.condition_lead_in_spin.setValue(
                own_lead_in
                if own_lead_in is not None
                else self._project_draft.pre_stream_fixation_seconds
            )
            self.condition_lead_in_spin.setEnabled(own_lead_in is not None)
            self.condition_lead_in_checkbox.toggled.connect(self.condition_lead_in_spin.setEnabled)

        self.preview_role_combo = QComboBox(self)
        self.preview_role_combo.setObjectName("presentation_preview_role_combo")
        self.preview_role_combo.addItem("Base", "base")
        self.preview_role_combo.addItem("Oddball", "oddball")
        self.preview_modality_combo = QComboBox(self)
        self.preview_modality_combo.setObjectName("presentation_preview_modality_combo")
        self.preview_modality_combo.addItem("Image", StimulusModality.IMAGE)
        self.preview_modality_combo.addItem("Word", StimulusModality.WORD)
        if condition is not None:
            modality = document.get_condition_stimulus_set(
                condition.condition_id,
                "base",
            ).modality
            self.preview_modality_combo.setCurrentIndex(
                self.preview_modality_combo.findData(modality)
            )
            self.preview_modality_combo.setEnabled(False)
        self.preview_stimulus_combo = QComboBox(self)
        self.preview_stimulus_combo.setObjectName("presentation_preview_stimulus_combo")
        self.preview_size_combo = QComboBox(self)
        self.preview_size_combo.setObjectName("presentation_preview_size_combo")
        self.preview_widget = _PresentationPreview(self)
        self.preview_summary_label = QLabel(self)
        self.preview_summary_label.setObjectName("presentation_preview_summary")
        self.preview_summary_label.setWordWrap(True)

        preview_panel = QFrame(self)
        preview_panel.setObjectName("presentation_preview_panel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setSpacing(8)
        preview_title = QLabel("Live preview", preview_panel)
        preview_title.setProperty("sectionCardRole", "title")
        preview_layout.addWidget(preview_title)
        preview_form = QFormLayout()
        preview_form.setContentsMargins(0, 0, 0, 0)
        preview_form.addRow("Role", self.preview_role_combo)
        preview_form.addRow("Stimulus type", self.preview_modality_combo)
        preview_form.addRow("Example", self.preview_stimulus_combo)
        preview_form.addRow("Word height", self.preview_size_combo)
        preview_layout.addLayout(preview_form)
        preview_layout.addWidget(self.preview_widget, 1)
        preview_layout.addWidget(self.preview_summary_label)

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(12)
        content.addWidget(self.editor_tabs, 3)
        content.addWidget(preview_panel, 2)

        self.validation_label = QLabel(self)
        self.validation_label.setObjectName("presentation_settings_validation_label")
        self.validation_label.setWordWrap(True)
        mark_error_text(self.validation_label)
        self.validation_label.setVisible(False)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        apply_button = self.button_box.button(QDialogButtonBox.StandardButton.Apply)
        apply_button.setText("Apply")
        mark_primary_action(apply_button)
        mark_secondary_action(self.button_box.button(QDialogButtonBox.StandardButton.Cancel))
        self.button_box.clicked.connect(self._handle_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        layout.addWidget(header)
        layout.addWidget(helper)
        if self.condition_lead_in_checkbox is not None:
            assert self.condition_lead_in_spin is not None
            lead_in_row = QHBoxLayout()
            lead_in_row.addWidget(self.condition_lead_in_checkbox)
            lead_in_row.addWidget(self.condition_lead_in_spin)
            lead_in_row.addStretch(1)
            layout.addLayout(lead_in_row)
        layout.addLayout(content, 1)
        layout.addWidget(self.validation_label)
        layout.addWidget(self.button_box)

        for editor in self._editors.values():
            editor.changed.connect(self._on_draft_changed)
        for combo in (
            self.preview_role_combo,
            self.preview_modality_combo,
            self.preview_stimulus_combo,
            self.preview_size_combo,
        ):
            combo.currentIndexChanged.connect(self._refresh_preview)
        self.preview_role_combo.currentIndexChanged.connect(self._reload_stimulus_choices)
        self.preview_modality_combo.currentIndexChanged.connect(self._reload_stimulus_choices)
        apply_studio_theme(self)
        self._reload_stimulus_choices()
        self._refresh_preview()

    @staticmethod
    def _scroll_editor(editor: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setObjectName(f"{editor.objectName()}_scroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(editor)
        return scroll

    @staticmethod
    def _apply_override(
        inherited: StimulusPresentationDefaults,
        override: StimulusPresentationOverride,
    ) -> StimulusPresentationDefaults:
        updates = {
            name: getattr(override, name)
            for name in _GROUP_NAMES
            if getattr(override, name) is not None
        }
        return inherited.model_copy(update=updates, deep=True)

    def _build_condition(self) -> ConditionPresentationSettings:
        common = self._editors["common"].build_override()
        lead_in_seconds = None
        if (
            self.condition_lead_in_checkbox is not None
            and self.condition_lead_in_checkbox.isChecked()
        ):
            assert self.condition_lead_in_spin is not None
            lead_in_seconds = self.condition_lead_in_spin.value()
        return ConditionPresentationSettings(
            common=common,
            base=self._editors["base"].build_override(),
            oddball=self._editors["oddball"].build_override(),
            pre_stream_fixation_seconds=lead_in_seconds,
        )

    def _effective_preview_settings(self) -> StimulusPresentationDefaults:
        if self._condition_id is None:
            return self._editors["project"].build_defaults()
        presentation = self._build_condition()
        return resolve_role_presentation(
            self._project_draft,
            presentation,
            self.preview_role_combo.currentData(),
        )

    def _on_draft_changed(self) -> None:
        if self._syncing_inheritance:
            return
        if self._condition_id is not None:
            try:
                self._syncing_inheritance = True
                common = self._editors["common"].build_override()
                inherited = self._apply_override(self._project_draft.defaults, common)
                self._editors["base"].set_inherited(inherited)
                self._editors["oddball"].set_inherited(inherited)
            except (TypeError, ValueError):
                pass
            finally:
                self._syncing_inheritance = False
        self._refresh_preview()

    def _reload_stimulus_choices(self) -> None:
        current = self.preview_stimulus_combo.currentData()
        self.preview_stimulus_combo.clear()
        self.preview_stimulus_combo.setToolTip(
            f"The preview shows at most {_PREVIEW_SAMPLE_LIMIT} representative items; "
            "the experiment still uses the complete stimulus set."
        )
        role = self.preview_role_combo.currentData()
        modality = self.preview_modality_combo.currentData()
        if self._condition_id is None:
            self.preview_stimulus_combo.addItem(
                "Preview image" if modality == StimulusModality.IMAGE else "READ",
                None if modality == StimulusModality.IMAGE else "READ",
            )
        else:
            stimulus_set = self._document.get_condition_stimulus_set(self._condition_id, role)
            if modality == StimulusModality.WORD:
                for word in _representative_sample(stimulus_set.words):
                    self.preview_stimulus_combo.addItem(word, word)
            else:
                condition = self._document.get_condition(self._condition_id)
                variant = (
                    condition.stimulus_variant
                    if condition is not None
                    else StimulusVariant.ORIGINAL
                )
                paths = self._active_image_preview_paths(stimulus_set, variant)
                for path in paths:
                    self.preview_stimulus_combo.addItem(path.name, path)
                self.preview_stimulus_combo.setToolTip(
                    f"Showing up to {_PREVIEW_SAMPLE_LIMIT} representative "
                    f"{variant.value.replace('_', ' ')} assets; the experiment uses "
                    "the complete stimulus set."
                )
        if self.preview_stimulus_combo.count() == 0:
            self.preview_stimulus_combo.addItem("No example available", None)
        restored = self.preview_stimulus_combo.findData(current)
        if restored >= 0:
            self.preview_stimulus_combo.setCurrentIndex(restored)
        self._refresh_preview()

    def _active_image_preview_paths(
        self,
        stimulus_set: StimulusSet,
        variant: StimulusVariant,
    ) -> list[Path]:
        manifest = self._document.manifest
        set_id = stimulus_set.set_id
        if manifest is not None:
            manifest_set = find_manifest_set(manifest, set_id=set_id)
            if manifest_set is not None and manifest_set.assets:
                paths = []
                for asset in _representative_sample(manifest_set.assets):
                    relative_path = asset_variant_path(asset, variant=variant)
                    if relative_path is not None:
                        path = self._resolve_preview_path(relative_path)
                        if path is not None and path.is_file():
                            paths.append(path)
                return paths

        source_dir = stimulus_set.source_dir
        if variant == StimulusVariant.ORIGINAL:
            if source_dir is None:
                return []
            folder = self._resolve_preview_path(source_dir)
        else:
            nominal_folder = stimulus_derived_dir(
                self._document.project_root,
                set_id,
            ) / stimulus_variant_dirname(variant.value)
            try:
                relative_folder = nominal_folder.relative_to(self._document.project_root).as_posix()
            except ValueError:
                return []
            folder = self._resolve_preview_path(relative_folder)
        if folder is None or not folder.is_dir():
            return []
        paths = []
        try:
            entries = folder.iterdir()
            for path in entries:
                if path.suffix.lower() not in _IMAGE_SUFFIXES:
                    continue
                safe_path = self._contained_preview_file(path)
                if safe_path is not None and safe_path.is_file():
                    paths.append(safe_path)
                    if len(paths) >= _PREVIEW_SAMPLE_LIMIT:
                        break
        except OSError:
            return []
        return paths

    def _resolve_preview_path(self, relative_path: str) -> Path | None:
        try:
            return resolve_project_relative_path(
                self._document.project_root,
                relative_path,
            )
        except (OSError, RuntimeError, ValueError):
            return None

    def _contained_preview_file(self, path: Path) -> Path | None:
        try:
            relative_path = path.relative_to(
                self._document.project_root.resolve(strict=False)
            ).as_posix()
        except (OSError, RuntimeError, ValueError):
            return None
        return self._resolve_preview_path(relative_path)

    def _refresh_preview(self) -> None:
        try:
            settings = self._effective_preview_settings()
        except (TypeError, ValueError) as error:
            self.preview_summary_label.setText(f"Preview unavailable: {error}")
            return
        values = settings.text_height.values
        current_value = self.preview_size_combo.currentData()
        self.preview_size_combo.blockSignals(True)
        self.preview_size_combo.clear()
        for value in values:
            self.preview_size_combo.addItem(f"{value:g}", value)
        restored = self.preview_size_combo.findData(current_value)
        self.preview_size_combo.setCurrentIndex(restored if restored >= 0 else 0)
        self.preview_size_combo.blockSignals(False)
        modality = self.preview_modality_combo.currentData()
        self.preview_size_combo.setEnabled(modality == StimulusModality.WORD and len(values) > 1)
        self.preview_widget.set_preview(
            settings=settings,
            modality=modality,
            value=self.preview_stimulus_combo.currentData(),
            height_value=float(self.preview_size_combo.currentData() or values[0]),
            background=_preview_background_color(
                self._document.project.settings.display.background_color
            ),
        )
        summary = f"{_enum_label(settings.transform)}. " + (
            presentation_defaults_summary(settings)
            if modality == StimulusModality.IMAGE
            else f"Arial, {settings.text_height.mode.value.replace('_', ' ')}, "
            f"{settings.text_color}."
        )
        warning = self._clipping_warning(
            settings,
            modality=modality,
            height_value=float(self.preview_size_combo.currentData() or values[0]),
        )
        self.preview_summary_label.setText(f"{summary}\nWarning: {warning}" if warning else summary)

    def _clipping_warning(
        self,
        settings: StimulusPresentationDefaults,
        *,
        modality: StimulusModality,
        height_value: float,
    ) -> str | None:
        display = self._document.project.settings.display
        horizontal_fov = degrees(
            2 * atan(display.screen_width_cm / (2 * display.viewing_distance_cm))
        )
        vertical_cm = display.screen_width_cm * (display.screen_height_px / display.screen_width_px)
        vertical_fov = degrees(2 * atan(vertical_cm / (2 * display.viewing_distance_cm)))
        if modality == StimulusModality.IMAGE:
            geometry = settings.image_geometry
            if (geometry.width_degrees is not None and geometry.width_degrees > horizontal_fov) or (
                geometry.height_degrees is not None and geometry.height_degrees > vertical_fov
            ):
                return "the authored image box may extend beyond the active display."
            return None
        position = settings.text_position
        if position.unit == PresentationUnit.WINDOW_HEIGHT_FRACTION:
            height_fraction = (
                height_value
                if settings.text_height.unit == PresentationUnit.WINDOW_HEIGHT_FRACTION
                else height_value / vertical_fov
            )
            if abs(position.y) + (height_fraction / 2) > 0.5:
                return "the word may extend beyond the active display vertically."
            return None
        height_degrees = (
            height_value
            if settings.text_height.unit == PresentationUnit.DEGREES
            else height_value * vertical_fov
        )
        if abs(position.y) + (height_degrees / 2) > vertical_fov / 2:
            return "the word may extend beyond the active display vertically."
        return None

    def _handle_button(self, button: QPushButton) -> None:
        role = self.button_box.buttonRole(button)
        if role == QDialogButtonBox.ButtonRole.ApplyRole:
            self.accept()
        elif role == QDialogButtonBox.ButtonRole.RejectRole:
            self.reject()

    def accept(self) -> None:
        try:
            if self._condition_id is None:
                defaults = self._editors["project"].build_defaults()
                presentation = ProjectPresentationSettings(
                    pre_stream_fixation_seconds=self._project_draft.pre_stream_fixation_seconds,
                    defaults=defaults,
                )
                self._document.set_project_presentation(presentation)
            else:
                self._document.set_condition_presentation(
                    self._condition_id,
                    self._build_condition(),
                )
        except Exception as error:
            self.validation_label.setText(str(error))
            self.validation_label.setVisible(True)
            return
        self.validation_label.setVisible(False)
        super().accept()


__all__ = [
    "PresentationSettingsDialog",
    "PresentationDefaultsEditor",
    "condition_presentation_summary",
    "presentation_defaults_summary",
]
