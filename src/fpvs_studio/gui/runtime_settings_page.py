"""Focused display settings editor for the FPVS Studio GUI."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.display_geometry import visual_angle_width_cm, visual_angle_width_px
from fpvs_studio.gui.components import SectionCard, mark_secondary_action
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import (
    _RUNTIME_BACKGROUND_COLOR_PRESETS,
    _canonical_runtime_background_hex,
    _prefixed_object_name,
    _show_error_dialog,
)


class DisplaySettingsEditor(QWidget):
    """Reusable display settings editor for refresh rate and background color."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        object_name_prefix: str = "",
        editable: bool = True,
        framed: bool = False,
        show_scope_label: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._editable = editable
        self._background_refresh_guard = False

        self.refresh_hz_spin = QDoubleSpinBox(self)
        self.refresh_hz_spin.setObjectName(
            _prefixed_object_name(object_name_prefix, "refresh_hz_spin")
        )
        self.refresh_hz_spin.setRange(1.0, 500.0)
        self.refresh_hz_spin.setDecimals(2)
        self.refresh_hz_spin.valueChanged.connect(self._apply_refresh_hz)

        self.runtime_background_color_combo = QComboBox(self)
        self.runtime_background_color_combo.setObjectName(
            _prefixed_object_name(object_name_prefix, "runtime_background_color_combo")
        )
        for label, background_hex in _RUNTIME_BACKGROUND_COLOR_PRESETS:
            self.runtime_background_color_combo.addItem(label, userData=background_hex)
        self.runtime_background_color_combo.currentIndexChanged.connect(
            self._apply_runtime_background_color
        )

        self.runtime_background_scope_label = QLabel(
            "Used during FPVS image presentation.",
            self,
        )
        self.runtime_background_scope_label.setObjectName(
            _prefixed_object_name(object_name_prefix, "runtime_background_scope_label")
        )
        self.runtime_background_scope_label.setWordWrap(True)

        self.summary_value_labels: dict[str, QLabel] = {}
        self.form_container = QWidget(self)
        self.form_layout = QFormLayout(self.form_container)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setHorizontalSpacing(12)
        self.form_layout.setVerticalSpacing(8)
        self.form_layout.addRow("Display refresh rate", self.refresh_hz_spin)
        self.form_layout.addRow("Background", self.runtime_background_color_combo)
        if show_scope_label:
            self.form_layout.addRow("", self.runtime_background_scope_label)
        else:
            self.runtime_background_scope_label.setText("")
            self.runtime_background_scope_label.setVisible(False)

        self.summary_container = QWidget(self)
        self.summary_layout = QFormLayout(self.summary_container)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_layout.setHorizontalSpacing(12)
        self.summary_layout.setVerticalSpacing(6)
        for key, label_text in (
            ("refresh", "Refresh"),
            ("background", "Background"),
        ):
            value_label = QLabel(self.summary_container)
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.summary_value_labels[key] = value_label
            self.summary_layout.addRow(label_text, value_label)

        content_parent: QWidget = self
        if framed:
            self.card = SectionCard(
                title="Display Settings",
                subtitle="Refresh rate and presentation background.",
                object_name=_prefixed_object_name(object_name_prefix, "display_settings_card"),
                parent=self,
            )
            self.card.card_layout.setContentsMargins(12, 10, 12, 10)
            self.card.card_layout.setSpacing(8)
            self.card.body_layout.setSpacing(8)
            content_parent = self.card
        else:
            self.card = None

        target_layout = self.card.body_layout if self.card is not None else QVBoxLayout(self)
        if self.card is None:
            target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.addWidget(self.form_container)
        target_layout.addWidget(self.summary_container)

        if self.card is not None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(content_parent)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def current_refresh_hz(self) -> float:
        return self.refresh_hz_spin.value()

    def refresh(self) -> None:
        background_color = self._normalized_background_color()
        preferred_refresh = self._document.project.settings.display.preferred_refresh_hz or 60.0
        with QSignalBlocker(self.refresh_hz_spin):
            self.refresh_hz_spin.setValue(preferred_refresh)
        with QSignalBlocker(self.runtime_background_color_combo):
            selected_index = self.runtime_background_color_combo.findData(background_color)
            if selected_index < 0:
                selected_index = self.runtime_background_color_combo.findData("#000000")
            self.runtime_background_color_combo.setCurrentIndex(selected_index)

        self.refresh_hz_spin.setEnabled(self._editable)
        self.runtime_background_color_combo.setEnabled(self._editable)
        self.form_container.setVisible(self._editable)
        self.summary_container.setVisible(not self._editable)
        if not self._editable:
            self.summary_value_labels["refresh"].setText(f"{preferred_refresh:.2f} Hz")
            self.summary_value_labels["background"].setText(
                self.runtime_background_color_combo.currentText()
            )

    def _normalized_background_color(self) -> str:
        background_color = self._document.project.settings.display.background_color
        if isinstance(background_color, str):
            canonical_preset = _canonical_runtime_background_hex(background_color)
            if canonical_preset is not None:
                return canonical_preset

        if self._background_refresh_guard:
            return "#000000"

        self._background_refresh_guard = True
        try:
            self._document.update_display_settings(background_color="#000000")
        finally:
            self._background_refresh_guard = False
        return "#000000"

    def _apply_refresh_hz(self) -> None:
        try:
            self._document.update_display_settings(
                preferred_refresh_hz=self.refresh_hz_spin.value()
            )
        except Exception as error:
            _show_error_dialog(self, "Refresh Setting Error", error)
            self.refresh()

    def _apply_runtime_background_color(self) -> None:
        selected_background_color = self.runtime_background_color_combo.currentData()
        if not isinstance(selected_background_color, str):
            return
        try:
            self._document.update_display_settings(background_color=selected_background_color)
        except Exception as error:
            _show_error_dialog(self, "Display Settings Error", error)
            self.refresh()


RuntimeSettingsEditor = DisplaySettingsEditor


class ImageSizePreview(QWidget):
    """Actual-size square preview for configured stimulus visual angle."""

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("image_size_preview")
        self._document = document
        self._preview_width_px = 1
        self._capped = False
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def refresh(self) -> None:
        display = self._document.project.settings.display
        self._preview_width_px = visual_angle_width_px(
            degrees=display.stimulus_width_degrees,
            viewing_distance_cm=display.viewing_distance_cm,
            screen_width_cm=display.screen_width_cm,
            screen_width_px=_display_screen_width_px(display),
        )
        max_preview = max(1, min(self.width(), self.height()) - 18)
        self._capped = self._preview_width_px > max_preview
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#101010"))
        painter.setPen(QPen(QColor("#6b7280"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        available = max(1, min(self.width(), self.height()) - 18)
        square_size = min(self._preview_width_px, available)
        left = (self.width() - square_size) // 2
        top = (self.height() - square_size) // 2
        painter.fillRect(left, top, square_size, square_size, QColor("#f8fafc"))
        painter.setPen(QPen(QColor("#2563eb"), 2))
        painter.drawRect(left, top, square_size, square_size)


class ImageSizePreviewDialog(QDialog):
    """Full-screen actual-size stimulus preview."""

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("image_size_preview_dialog")
        self._document = document
        self.setWindowTitle("Image Size Preview")
        self.setModal(True)
        self.setStyleSheet(
            "QDialog#image_size_preview_dialog { background: #101010; }"
            "QLabel#image_size_preview_value_label { color: #f8fafc; }"
            "QWidget#image_size_preview_control_panel { background: #f8fafc; border-radius: 8px; }"
        )

        self.preview = ImageSizePreview(document, self)
        self.preview.setObjectName("image_size_full_screen_preview")
        self.preview_value_label = QLabel(self)
        self.preview_value_label.setObjectName("image_size_preview_value_label")
        self.preview_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_value_label.setWordWrap(True)

        self.width_degrees_spin = _image_size_spin_box(
            parent=self,
            object_name="preview_stimulus_width_degrees_spin",
            minimum=0.1,
            maximum=90.0,
            decimals=1,
            step=0.5,
            suffix=" deg",
        )
        self.viewing_distance_spin = _image_size_spin_box(
            parent=self,
            object_name="preview_viewing_distance_cm_spin",
            minimum=1.0,
            maximum=500.0,
            decimals=1,
            step=5.0,
            suffix=" cm",
        )
        self.screen_width_spin = _image_size_spin_box(
            parent=self,
            object_name="preview_screen_width_cm_spin",
            minimum=1.0,
            maximum=500.0,
            decimals=1,
            step=1.0,
            suffix=" cm",
        )
        self.use_current_resolution_checkbox = QCheckBox(
            "Use current primary screen resolution",
            self,
        )
        self.use_current_resolution_checkbox.setObjectName(
            "preview_use_current_screen_resolution_checkbox"
        )
        self.screen_width_px_spin = _resolution_spin_box(
            parent=self,
            object_name="preview_screen_width_px_spin",
        )
        self.screen_height_px_spin = _resolution_spin_box(
            parent=self,
            object_name="preview_screen_height_px_spin",
        )
        self.width_degrees_spin.valueChanged.connect(self._apply_image_display_settings)
        self.viewing_distance_spin.valueChanged.connect(self._apply_image_display_settings)
        self.screen_width_spin.valueChanged.connect(self._apply_image_display_settings)
        self.use_current_resolution_checkbox.toggled.connect(
            self._apply_image_display_settings
        )
        self.screen_width_px_spin.valueChanged.connect(self._apply_image_display_settings)
        self.screen_height_px_spin.valueChanged.connect(self._apply_image_display_settings)

        self.exit_button = QPushButton("Exit Preview", self)
        self.exit_button.setObjectName("image_size_preview_exit_button")
        self.exit_button.clicked.connect(self.accept)
        mark_secondary_action(self.exit_button)

        control_panel = QWidget(self)
        control_panel.setObjectName("image_size_preview_control_panel")
        control_panel.setFixedWidth(300)
        control_panel_layout = QVBoxLayout(control_panel)
        control_panel_layout.setContentsMargins(18, 18, 18, 18)
        control_panel_layout.setSpacing(12)
        title_label = QLabel("Image Size", control_panel)
        title_label.setProperty("sectionCardRole", "title")
        control_panel_layout.addWidget(title_label)
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(10)
        form_layout.addRow("Image width (deg)", self.width_degrees_spin)
        form_layout.addRow("Viewing distance (cm)", self.viewing_distance_spin)
        form_layout.addRow("Screen width (cm)", self.screen_width_spin)
        form_layout.addRow("Resolution width (px)", self.screen_width_px_spin)
        form_layout.addRow("Resolution height (px)", self.screen_height_px_spin)
        control_panel_layout.addLayout(form_layout)

        checkbox_row = QHBoxLayout()
        checkbox_row.setContentsMargins(0, 0, 0, 0)
        checkbox_row.addWidget(self.use_current_resolution_checkbox)
        checkbox_row.addStretch(1)
        control_panel_layout.addLayout(checkbox_row)

        control_panel_layout.addWidget(self.exit_button)
        control_panel_layout.addStretch(1)

        preview_panel = QWidget(self)
        preview_panel_layout = QVBoxLayout(preview_panel)
        preview_panel_layout.setContentsMargins(0, 0, 0, 0)
        preview_panel_layout.setSpacing(16)
        preview_panel_layout.addWidget(self.preview, 1)
        preview_panel_layout.addWidget(self.preview_value_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(0)
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(18)
        row_layout.addWidget(control_panel)
        row_layout.addWidget(preview_panel, 1)
        layout.addLayout(row_layout)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self.preview.refresh()

    def refresh(self) -> None:
        display = self._document.project.settings.display
        with QSignalBlocker(self.width_degrees_spin):
            self.width_degrees_spin.setValue(display.stimulus_width_degrees)
        with QSignalBlocker(self.viewing_distance_spin):
            self.viewing_distance_spin.setValue(display.viewing_distance_cm)
        with QSignalBlocker(self.screen_width_spin):
            self.screen_width_spin.setValue(display.screen_width_cm)
        with QSignalBlocker(self.use_current_resolution_checkbox):
            self.use_current_resolution_checkbox.setChecked(
                display.use_current_screen_resolution
            )
        with QSignalBlocker(self.screen_width_px_spin):
            self.screen_width_px_spin.setValue(display.screen_width_px)
        with QSignalBlocker(self.screen_height_px_spin):
            self.screen_height_px_spin.setValue(display.screen_height_px)
        self.screen_width_px_spin.setEnabled(not display.use_current_screen_resolution)
        self.screen_height_px_spin.setEnabled(not display.use_current_screen_resolution)
        physical_width_cm = visual_angle_width_cm(
            degrees=display.stimulus_width_degrees,
            viewing_distance_cm=display.viewing_distance_cm,
        )
        screen_width_px = _display_screen_width_px(display)
        preview_width_px = visual_angle_width_px(
            degrees=display.stimulus_width_degrees,
            viewing_distance_cm=display.viewing_distance_cm,
            screen_width_cm=display.screen_width_cm,
            screen_width_px=screen_width_px,
        )
        self.preview_value_label.setText(
            f"{display.stimulus_width_degrees:.1f} deg at "
            f"{display.viewing_distance_cm:.1f} cm = "
            f"{physical_width_cm:.1f} cm wide, about {preview_width_px} px "
            f"on a {screen_width_px} px-wide display"
        )
        self.preview.refresh()

    def _apply_image_display_settings(self) -> None:
        try:
            self._document.update_display_settings(
                stimulus_width_degrees=self.width_degrees_spin.value(),
                viewing_distance_cm=self.viewing_distance_spin.value(),
                screen_width_cm=self.screen_width_spin.value(),
                screen_width_px=self.screen_width_px_spin.value(),
                screen_height_px=self.screen_height_px_spin.value(),
                use_current_screen_resolution=self.use_current_resolution_checkbox.isChecked(),
            )
        except Exception as error:
            _show_error_dialog(self, "Image Size Error", error)
            self.refresh()


class ImageDisplaySizeEditor(QWidget):
    """Project-wide stimulus display-size controls and preview."""

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("image_display_size_editor")
        self._document = document

        self.width_degrees_spin = _image_size_spin_box(
            parent=self,
            object_name="stimulus_width_degrees_spin",
            minimum=0.1,
            maximum=90.0,
            decimals=1,
            step=0.5,
            suffix=" deg",
        )
        self.width_degrees_spin.valueChanged.connect(self._apply_image_display_settings)

        self.viewing_distance_spin = _image_size_spin_box(
            parent=self,
            object_name="viewing_distance_cm_spin",
            minimum=1.0,
            maximum=500.0,
            decimals=1,
            step=5.0,
            suffix=" cm",
        )
        self.viewing_distance_spin.valueChanged.connect(self._apply_image_display_settings)

        self.screen_width_spin = _image_size_spin_box(
            parent=self,
            object_name="screen_width_cm_spin",
            minimum=1.0,
            maximum=500.0,
            decimals=1,
            step=1.0,
            suffix=" cm",
        )
        self.screen_width_spin.valueChanged.connect(self._apply_image_display_settings)
        self.use_current_resolution_checkbox = QCheckBox(
            "Use current primary screen resolution",
            self,
        )
        self.use_current_resolution_checkbox.setObjectName(
            "use_current_screen_resolution_checkbox"
        )
        self.screen_width_px_spin = _resolution_spin_box(
            parent=self,
            object_name="screen_width_px_spin",
        )
        self.screen_height_px_spin = _resolution_spin_box(
            parent=self,
            object_name="screen_height_px_spin",
        )
        self.use_current_resolution_checkbox.toggled.connect(
            self._apply_image_display_settings
        )
        self.screen_width_px_spin.valueChanged.connect(self._apply_image_display_settings)
        self.screen_height_px_spin.valueChanged.connect(self._apply_image_display_settings)

        self.preview_value_label = QLabel(self)
        self.preview_value_label.setObjectName("image_size_preview_value_label")
        self.preview_value_label.setWordWrap(True)
        self.preview_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.full_screen_preview_button = QPushButton("Full Screen Preview", self)
        self.full_screen_preview_button.setObjectName("image_size_full_screen_preview_button")
        self.full_screen_preview_button.clicked.connect(self._show_full_screen_preview)
        mark_secondary_action(self.full_screen_preview_button)

        self.form_layout = QFormLayout()
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setHorizontalSpacing(12)
        self.form_layout.setVerticalSpacing(8)
        self.form_layout.addRow("Image width (deg)", self.width_degrees_spin)
        self.form_layout.addRow("Viewing distance (cm)", self.viewing_distance_spin)
        self.form_layout.addRow("Screen width (cm)", self.screen_width_spin)
        self.form_layout.addRow("Resolution width (px)", self.screen_width_px_spin)
        self.form_layout.addRow("Resolution height (px)", self.screen_height_px_spin)

        checkbox_row = QHBoxLayout()
        checkbox_row.setContentsMargins(0, 0, 0, 0)
        checkbox_row.addWidget(self.use_current_resolution_checkbox)
        checkbox_row.addStretch(1)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.addStretch(1)
        button_row.addWidget(self.full_screen_preview_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(self.form_layout)
        layout.addLayout(checkbox_row)
        layout.addWidget(self.preview_value_label)
        layout.addLayout(button_row)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        display = self._document.project.settings.display
        with QSignalBlocker(self.width_degrees_spin):
            self.width_degrees_spin.setValue(display.stimulus_width_degrees)
        with QSignalBlocker(self.viewing_distance_spin):
            self.viewing_distance_spin.setValue(display.viewing_distance_cm)
        with QSignalBlocker(self.screen_width_spin):
            self.screen_width_spin.setValue(display.screen_width_cm)
        with QSignalBlocker(self.use_current_resolution_checkbox):
            self.use_current_resolution_checkbox.setChecked(
                display.use_current_screen_resolution
            )
        with QSignalBlocker(self.screen_width_px_spin):
            self.screen_width_px_spin.setValue(display.screen_width_px)
        with QSignalBlocker(self.screen_height_px_spin):
            self.screen_height_px_spin.setValue(display.screen_height_px)
        self.screen_width_px_spin.setEnabled(not display.use_current_screen_resolution)
        self.screen_height_px_spin.setEnabled(not display.use_current_screen_resolution)

        physical_width_cm = visual_angle_width_cm(
            degrees=display.stimulus_width_degrees,
            viewing_distance_cm=display.viewing_distance_cm,
        )
        screen_width_px = _display_screen_width_px(display)
        preview_width_px = visual_angle_width_px(
            degrees=display.stimulus_width_degrees,
            viewing_distance_cm=display.viewing_distance_cm,
            screen_width_cm=display.screen_width_cm,
            screen_width_px=screen_width_px,
        )
        self.preview_value_label.setText(
            f"{physical_width_cm:.1f} cm wide, about {preview_width_px} px "
            f"on a {screen_width_px} px-wide display"
        )

    def _apply_image_display_settings(self) -> None:
        try:
            self._document.update_display_settings(
                stimulus_width_degrees=self.width_degrees_spin.value(),
                viewing_distance_cm=self.viewing_distance_spin.value(),
                screen_width_cm=self.screen_width_spin.value(),
                screen_width_px=self.screen_width_px_spin.value(),
                screen_height_px=self.screen_height_px_spin.value(),
                use_current_screen_resolution=self.use_current_resolution_checkbox.isChecked(),
            )
        except Exception as error:
            _show_error_dialog(self, "Image Size Error", error)
            self.refresh()

    def _show_full_screen_preview(self) -> None:
        dialog = ImageSizePreviewDialog(self._document, self)
        screen = QApplication.primaryScreen()
        if screen is not None:
            dialog.setGeometry(screen.geometry())
        dialog.setWindowState(dialog.windowState() | Qt.WindowState.WindowFullScreen)
        dialog.exec()


def _primary_screen_width_px() -> int:
    screen = QApplication.primaryScreen()
    if screen is None:
        return 1920
    return max(1, screen.geometry().width())


def _display_screen_width_px(display: object) -> int:
    if bool(getattr(display, "use_current_screen_resolution", False)):
        return _primary_screen_width_px()
    return max(1, int(getattr(display, "screen_width_px", 1920)))


def _image_size_spin_box(
    *,
    parent: QWidget,
    object_name: str,
    minimum: float,
    maximum: float,
    decimals: int,
    step: float,
    suffix: str,
) -> QDoubleSpinBox:
    spin_box = QDoubleSpinBox(parent)
    spin_box.setObjectName(object_name)
    spin_box.setRange(minimum, maximum)
    spin_box.setDecimals(decimals)
    spin_box.setSingleStep(step)
    spin_box.setSuffix(suffix)
    return spin_box


def _resolution_spin_box(*, parent: QWidget, object_name: str) -> QSpinBox:
    spin_box = QSpinBox(parent)
    spin_box.setObjectName(object_name)
    spin_box.setRange(1, 20000)
    spin_box.setSingleStep(10)
    spin_box.setSuffix(" px")
    return spin_box
