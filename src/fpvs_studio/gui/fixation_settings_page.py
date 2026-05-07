"""Fixation-task authoring widgets for the FPVS Studio GUI."""

from __future__ import annotations

from pydantic import ValidationError
from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.validation import ConditionFixationGuidance
from fpvs_studio.gui.animations import ButtonHoverAnimator
from fpvs_studio.gui.components import (
    PAGE_SECTION_GAP,
    SectionCard,
    apply_fixation_settings_theme,
    mark_secondary_action,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_helpers import (
    _FIXATION_FEASIBILITY_TOOLTIP_TEXT,
    _canonical_runtime_background_hex,
    _set_form_row_visible,
    _show_error_dialog,
)

_BASE_COLOR_OPTIONS = (("Blue", "#0000FF"), ("White", "#FFFFFF"))
_TARGET_COLOR_OPTIONS = (("Red", "#FF0000"),)
_DEFAULT_BASE_COLOR = "#0000FF"
_DEFAULT_TARGET_COLOR = "#FF0000"
_BASE_COLOR_TOOLTIP = "Normal fixation cross color shown during presentation."
_TARGET_COLOR_TOOLTIP = (
    "Temporary fixation cross color participants respond to during the accuracy task."
)
_RESPONSE_KEY_TOOLTIP = (
    "Key participants press when the fixation cross changes color during the accuracy task."
)
_KEYBOARD_ROWS = (
    (
        ("`", "`"),
        ("1", "1"),
        ("2", "2"),
        ("3", "3"),
        ("4", "4"),
        ("5", "5"),
        ("6", "6"),
        ("7", "7"),
        ("8", "8"),
        ("9", "9"),
        ("0", "0"),
        ("-", "-"),
        ("=", "="),
        ("Backspace", "backspace"),
    ),
    (
        ("Tab", "tab"),
        ("Q", "q"),
        ("W", "w"),
        ("E", "e"),
        ("R", "r"),
        ("T", "t"),
        ("Y", "y"),
        ("U", "u"),
        ("I", "i"),
        ("O", "o"),
        ("P", "p"),
        ("[", "["),
        ("]", "]"),
        ("\\", "\\"),
    ),
    (
        ("A", "a"),
        ("S", "s"),
        ("D", "d"),
        ("F", "f"),
        ("G", "g"),
        ("H", "h"),
        ("J", "j"),
        ("K", "k"),
        ("L", "l"),
        (";", ";"),
        ("'", "'"),
        ("Enter", "enter"),
    ),
    (
        ("Z", "z"),
        ("X", "x"),
        ("C", "c"),
        ("V", "v"),
        ("B", "b"),
        ("N", "n"),
        ("M", "m"),
        (",", ","),
        (".", "."),
        ("/", "/"),
    ),
    (
        ("Space", "space"),
    ),
)


def _preview_color(color_text: str, *, fallback: str) -> QColor:
    color = QColor(color_text)
    if color.isValid():
        return color
    return QColor(fallback)


def _settings_section(title: str, body: QWidget, *, parent: QWidget) -> QFrame:
    section = QFrame(parent)
    section.setObjectName(f"fixation_{title.lower()}_section")
    section.setProperty("fixationSettingsSection", "true")
    layout = QVBoxLayout(section)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(6)
    title_label = QLabel(title, section)
    title_label.setProperty("sectionCardRole", "subtitle")
    title_label.setProperty("fixationSettingsSectionTitle", "true")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title_label)
    layout.addStretch(1)
    layout.addWidget(body)
    layout.addStretch(1)
    return section


def _color_combo(*, object_name: str, tooltip: str, parent: QWidget) -> QComboBox:
    combo = QComboBox(parent)
    combo.setObjectName(object_name)
    combo.setToolTip(tooltip)
    return combo


def _populate_color_combo(combo: QComboBox, options: tuple[tuple[str, str], ...]) -> None:
    for label, color in options:
        combo.addItem(label, userData=color)


def _select_color_combo_value(combo: QComboBox, color: str, *, fallback: str) -> None:
    index = combo.findData(color)
    if index < 0:
        index = combo.findData(fallback)
    combo.setCurrentIndex(max(0, index))


def _fixation_settings_error_message(error: Exception) -> str | None:
    if not isinstance(error, ValidationError):
        return None
    for issue in error.errors():
        message = str(issue.get("msg", ""))
        if "target_count_min" in message and "target_count_max" in message:
            return (
                "Minimum changes per condition cannot be higher than maximum changes. "
                "Lower Minimum changes or increase Maximum changes, then try again."
            )
    return None


class ResponseKeyPickerPopover(QFrame):
    """Transient keyboard-style picker for fixation response keys."""

    key_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("response_key_picker_popover")
        self._key_buttons: dict[str, QPushButton] = {}
        self._hover_animators: list[ButtonHoverAnimator] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        for row_index, row in enumerate(_KEYBOARD_ROWS):
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            if row_index == len(_KEYBOARD_ROWS) - 1:
                row_layout.addStretch(1)
            if row_index in {2, 3}:
                row_layout.addSpacing(18 if row_index == 2 else 34)
            for label, key in row:
                button = QPushButton(label, self)
                button.setObjectName(f"response_key_{key}_button")
                button.setProperty("keyboardKey", key)
                button.setToolTip(f"Use {label} as the fixation response key.")
                button.setMinimumHeight(28)
                if key == "space":
                    button.setMinimumWidth(150)
                elif len(label) > 1:
                    button.setMinimumWidth(74)
                else:
                    button.setMinimumWidth(36)
                button.clicked.connect(lambda _checked=False, value=key: self._select_key(value))
                self._key_buttons[key] = button
                self._hover_animators.append(ButtonHoverAnimator(button, parent=self))
                row_layout.addWidget(button)
            row_layout.addStretch(1)
            layout.addLayout(row_layout)

    def key_button(self, key: str) -> QPushButton | None:
        return self._key_buttons.get(key)

    def key_values(self) -> set[str]:
        return set(self._key_buttons)

    def _select_key(self, key: str) -> None:
        self.key_selected.emit(key)
        self.close()


class FixationCrossPreview(QWidget):
    """Paint a lightweight preview of default and changed fixation crosses."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("fixation_cross_preview")
        self.setMinimumSize(220, 150)
        self.setMaximumHeight(300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.background_color = "#000000"
        self.base_color = _DEFAULT_BASE_COLOR
        self.target_color = _DEFAULT_TARGET_COLOR
        self.cross_size_px = 44
        self.line_width_px = 3

    def set_preview_settings(
        self,
        *,
        background_color: str,
        base_color: str,
        target_color: str,
        cross_size_px: int,
        line_width_px: int,
    ) -> None:
        self.background_color = background_color
        self.base_color = base_color
        self.target_color = target_color
        self.cross_size_px = cross_size_px
        self.line_width_px = line_width_px
        self.update()

    def preview_state(self) -> tuple[str, str, str, int, int]:
        return (
            self.background_color,
            self.base_color,
            self.target_color,
            self.cross_size_px,
            self.line_width_px,
        )

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), _preview_color(self.background_color, fallback="#000000"))

        half_width = max(1, self.width() // 2)
        centers = (
            (half_width // 2, self.height() // 2),
            (half_width + half_width // 2, self.height() // 2),
        )
        labels = (("Default", self.base_color), ("Change", self.target_color))
        max_cross_size = max(8, min(half_width, self.height()) - 56)
        cross_size = max(4, min(self.cross_size_px, max_cross_size))
        line_width = max(1, min(self.line_width_px, 24))

        painter.setPen(QPen(QColor("#94a3b8")))
        painter.drawText(0, 10, half_width, 20, Qt.AlignmentFlag.AlignCenter, labels[0][0])
        painter.drawText(
            half_width,
            10,
            half_width,
            20,
            Qt.AlignmentFlag.AlignCenter,
            labels[1][0],
        )

        for center, (_label, color_text) in zip(centers, labels, strict=True):
            pen = QPen(_preview_color(color_text, fallback="#FFFFFF"))
            pen.setWidth(line_width)
            pen.setCapStyle(Qt.PenCapStyle.SquareCap)
            painter.setPen(pen)
            center_x, center_y = center
            radius = cross_size // 2
            painter.drawLine(center_x - radius, center_y, center_x + radius, center_y)
            painter.drawLine(center_x, center_y - radius, center_x, center_y + radius)


class FixationSettingsEditor(QWidget):
    """Reusable fixation-task settings editor."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        schedule_row_behavior: str = "hide",
        layout_mode: str = "grid",
        title: str = "Fixation Cross Task",
        subtitle: str | None = "Task enablement, behavior, timing, response, and appearance.",
        compact: bool = False,
        show_preview: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if schedule_row_behavior not in {"hide", "disable"}:
            raise ValueError(f"Unsupported schedule_row_behavior: {schedule_row_behavior}")
        if layout_mode not in {"grid", "single_column"}:
            raise ValueError(f"Unsupported fixation layout mode: {layout_mode}")
        self._document = document
        self._schedule_row_behavior = schedule_row_behavior
        self._layout_mode = layout_mode
        self._compact = compact
        self._show_preview = show_preview
        card_margin_y = 6 if compact else 10
        card_spacing = 5 if compact else 8
        form_spacing = 4 if compact else 7
        section_spacing = 5 if compact else 8

        self.fixation_enabled_checkbox = QCheckBox(
            "Enable fixation color changes per condition", self
        )
        self.fixation_enabled_checkbox.setObjectName("fixation_enabled_checkbox")
        self.fixation_enabled_checkbox.stateChanged.connect(self._on_fixation_enabled_toggled)

        self.fixation_accuracy_checkbox = QCheckBox(
            "Enable fixation accuracy task",
            self,
        )
        self.fixation_accuracy_checkbox.setObjectName("fixation_accuracy_checkbox")
        self.fixation_accuracy_checkbox.stateChanged.connect(self._on_fixation_accuracy_toggled)

        self.target_count_mode_combo = QComboBox(self)
        self.target_count_mode_combo.setObjectName("target_count_mode_combo")
        self.target_count_mode_combo.addItem("Fixed per condition", userData="fixed")
        self.target_count_mode_combo.addItem("Randomized per condition run", userData="randomized")
        self.target_count_mode_combo.currentIndexChanged.connect(self._on_target_count_mode_changed)

        self.changes_per_sequence_spin = QSpinBox(self)
        self.changes_per_sequence_spin.setObjectName("changes_per_sequence_spin")
        self.changes_per_sequence_spin.setRange(0, 1000)
        self.changes_per_sequence_spin.valueChanged.connect(self._apply_fixation_settings)

        self.target_count_min_spin = QSpinBox(self)
        self.target_count_min_spin.setObjectName("target_count_min_spin")
        self.target_count_min_spin.setRange(0, 1000)
        self.target_count_min_spin.valueChanged.connect(self._apply_fixation_settings)

        self.target_count_max_spin = QSpinBox(self)
        self.target_count_max_spin.setObjectName("target_count_max_spin")
        self.target_count_max_spin.setRange(0, 1000)
        self.target_count_max_spin.valueChanged.connect(self._apply_fixation_settings)

        self.no_repeat_count_checkbox = QCheckBox(
            "No immediate repeat between consecutive condition runs",
            self,
        )
        self.no_repeat_count_checkbox.setObjectName("no_immediate_repeat_count_checkbox")
        self.no_repeat_count_checkbox.stateChanged.connect(self._apply_fixation_settings)

        self.target_duration_spin = QSpinBox(self)
        self.target_duration_spin.setObjectName("target_duration_spin")
        self.target_duration_spin.setRange(0, 10000)
        self.target_duration_spin.valueChanged.connect(self._apply_fixation_settings)

        self.min_gap_spin = QSpinBox(self)
        self.min_gap_spin.setObjectName("min_gap_spin")
        self.min_gap_spin.setRange(0, 10000)
        self.min_gap_spin.valueChanged.connect(self._apply_fixation_settings)

        self.max_gap_spin = QSpinBox(self)
        self.max_gap_spin.setObjectName("max_gap_spin")
        self.max_gap_spin.setRange(0, 10000)
        self.max_gap_spin.valueChanged.connect(self._apply_fixation_settings)

        self.base_color_combo = _color_combo(
            object_name="fixation_base_color_combo",
            tooltip=_BASE_COLOR_TOOLTIP,
            parent=self,
        )
        _populate_color_combo(self.base_color_combo, _BASE_COLOR_OPTIONS)
        self.base_color_combo.currentIndexChanged.connect(self._apply_fixation_settings)

        self.target_color_combo = _color_combo(
            object_name="fixation_target_color_combo",
            tooltip=_TARGET_COLOR_TOOLTIP,
            parent=self,
        )
        _populate_color_combo(self.target_color_combo, _TARGET_COLOR_OPTIONS)
        self.target_color_combo.currentIndexChanged.connect(self._apply_fixation_settings)

        self.response_key_edit = QLineEdit(self)
        self.response_key_edit.setObjectName("response_key_edit")
        self.response_key_edit.setReadOnly(True)
        self.response_key_edit.setToolTip(_RESPONSE_KEY_TOOLTIP)
        self.response_key_edit.setText("space")
        self.response_key_button = QPushButton("Choose Key...", self)
        self.response_key_button.setObjectName("response_key_choose_button")
        self.response_key_button.setToolTip(_RESPONSE_KEY_TOOLTIP)
        mark_secondary_action(self.response_key_button)
        self.response_key_button.clicked.connect(self._show_response_key_picker)
        self.response_key_popover = ResponseKeyPickerPopover(self)
        self.response_key_popover.key_selected.connect(self._set_response_key)

        self.response_window_spin = QDoubleSpinBox(self)
        self.response_window_spin.setObjectName("response_window_seconds_spin")
        self.response_window_spin.setRange(0.1, 10.0)
        self.response_window_spin.setDecimals(2)
        self.response_window_spin.setSingleStep(0.1)
        self.response_window_spin.valueChanged.connect(self._apply_fixation_settings)

        self.cross_size_spin = QSpinBox(self)
        self.cross_size_spin.setObjectName("cross_size_spin")
        self.cross_size_spin.setRange(1, 1000)
        self.cross_size_spin.valueChanged.connect(self._apply_fixation_settings)

        self.line_width_spin = QSpinBox(self)
        self.line_width_spin.setObjectName("line_width_spin")
        self.line_width_spin.setRange(1, 1000)
        self.line_width_spin.valueChanged.connect(self._apply_fixation_settings)

        self.fixation_panel = SectionCard(
            title=title,
            subtitle=subtitle,
            object_name="fixation_settings_panel",
            parent=self,
        )
        self.fixation_panel.card_layout.setContentsMargins(12, card_margin_y, 12, card_margin_y)
        self.fixation_panel.card_layout.setSpacing(card_spacing)
        fixation_panel_layout = self.fixation_panel.body_layout
        fixation_panel_layout.setSpacing(section_spacing)

        enablement_layout = QVBoxLayout() if compact else QHBoxLayout()
        enablement_layout.setContentsMargins(0, 0, 0, 0)
        enablement_layout.setSpacing(5 if compact else 6)
        enablement_layout.addWidget(self.fixation_enabled_checkbox)
        enablement_layout.addWidget(self.fixation_accuracy_checkbox)
        if not compact:
            enablement_layout.addStretch(1)

        self.fixation_behavior_group = QWidget(self.fixation_panel)
        self.fixation_behavior_layout = QFormLayout(self.fixation_behavior_group)
        self.fixation_behavior_layout.setVerticalSpacing(form_spacing)
        self.fixation_behavior_layout.addRow("Color change schedule", self.target_count_mode_combo)
        self.fixation_behavior_layout.addRow(
            "Changes per condition", self.changes_per_sequence_spin
        )
        self.fixation_behavior_layout.addRow("Minimum changes", self.target_count_min_spin)
        self.fixation_behavior_layout.addRow("Maximum changes", self.target_count_max_spin)
        self.fixation_behavior_layout.addRow("No immediate repeat", self.no_repeat_count_checkbox)

        self.fixation_timing_group = QWidget(self.fixation_panel)
        timing_layout = QFormLayout(self.fixation_timing_group)
        timing_layout.setVerticalSpacing(form_spacing)
        timing_layout.addRow("Color change duration (ms)", self.target_duration_spin)
        timing_layout.addRow("Minimum gap (ms)", self.min_gap_spin)
        timing_layout.addRow("Maximum gap (ms)", self.max_gap_spin)

        self.fixation_response_group = QWidget(self.fixation_panel)
        response_layout = QFormLayout(self.fixation_response_group)
        response_layout.setVerticalSpacing(form_spacing)
        response_key_row = QWidget(self.fixation_response_group)
        response_key_row_layout = QHBoxLayout(response_key_row)
        response_key_row_layout.setContentsMargins(0, 0, 0, 0)
        response_key_row_layout.setSpacing(6)
        response_key_row_layout.addWidget(self.response_key_edit, 1)
        response_key_row_layout.addWidget(self.response_key_button)
        response_layout.addRow("Response key", response_key_row)
        response_layout.addRow("Response window (s)", self.response_window_spin)

        self.fixation_appearance_group = QWidget(self.fixation_panel)
        appearance_layout = QFormLayout(self.fixation_appearance_group)
        appearance_layout.setVerticalSpacing(form_spacing)
        appearance_layout.addRow("Default color", self.base_color_combo)
        appearance_layout.addRow("Change color", self.target_color_combo)
        appearance_layout.addRow("Cross size (px)", self.cross_size_spin)
        appearance_layout.addRow("Line width (px)", self.line_width_spin)

        feasibility_card = QFrame(self.fixation_panel)
        feasibility_card.setObjectName("fixation_feasibility_card")
        feasibility_card.setToolTip(_FIXATION_FEASIBILITY_TOOLTIP_TEXT)
        feasibility_card.setMaximumHeight(42)
        feasibility_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        feasibility_layout = QVBoxLayout(feasibility_card)
        feasibility_layout.setContentsMargins(10, 4, 10, 4)
        feasibility_layout.setSpacing(0)
        self.fixation_feasibility_label = QLabel(feasibility_card)
        self.fixation_feasibility_label.setObjectName("fixation_feasibility_label")
        self.fixation_feasibility_label.setToolTip(_FIXATION_FEASIBILITY_TOOLTIP_TEXT)
        self.fixation_feasibility_label.setWordWrap(True)
        self.fixation_feasibility_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        feasibility_layout.addWidget(self.fixation_feasibility_label)

        settings_column = QWidget(self.fixation_panel)
        settings_column_layout = QVBoxLayout(settings_column)
        settings_column_layout.setContentsMargins(0, 0, 0, 0)
        settings_column_layout.setSpacing(section_spacing)
        settings_column_layout.addLayout(enablement_layout)
        settings_column_layout.addWidget(feasibility_card)
        self.fixation_behavior_panel = _settings_section(
            "Behavior",
            self.fixation_behavior_group,
            parent=self.fixation_panel,
        )
        self.fixation_timing_panel = _settings_section(
            "Timing",
            self.fixation_timing_group,
            parent=self.fixation_panel,
        )
        self.fixation_response_panel = _settings_section(
            "Response",
            self.fixation_response_group,
            parent=self.fixation_panel,
        )
        self.fixation_appearance_panel = _settings_section(
            "Appearance",
            self.fixation_appearance_group,
            parent=self.fixation_panel,
        )
        if self._layout_mode == "single_column":
            settings_layout = QVBoxLayout()
            settings_layout.setContentsMargins(0, 0, 0, 0)
            settings_layout.setSpacing(section_spacing)
            for panel in (
                self.fixation_behavior_panel,
                self.fixation_timing_panel,
                self.fixation_response_panel,
                self.fixation_appearance_panel,
            ):
                settings_layout.addWidget(panel)
            settings_column_layout.addLayout(settings_layout)
        else:
            settings_grid = QGridLayout()
            settings_grid.setContentsMargins(0, 0, 0, 0)
            settings_grid.setHorizontalSpacing(PAGE_SECTION_GAP)
            settings_grid.setVerticalSpacing(section_spacing)
            settings_grid.addWidget(self.fixation_behavior_panel, 0, 0)
            settings_grid.addWidget(self.fixation_timing_panel, 0, 1)
            settings_grid.addWidget(self.fixation_response_panel, 1, 0)
            settings_grid.addWidget(self.fixation_appearance_panel, 1, 1)
            settings_grid.setColumnStretch(0, 1)
            settings_grid.setColumnStretch(1, 1)
            settings_column_layout.addLayout(settings_grid)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.preview_card: SectionCard | None = None
        self.preview_panel: QFrame | None = None
        self.preview_widget: FixationCrossPreview | None = None
        if show_preview:
            self.preview_panel = QFrame(self)
            self.preview_panel.setObjectName("fixation_cross_preview_panel")
            self.preview_panel.setProperty("fixationPreviewPanel", "true")
            self.preview_panel.setMaximumHeight(360)
            preview_panel_layout = QVBoxLayout(self.preview_panel)
            preview_panel_layout.setContentsMargins(10, 8, 10, 8)
            preview_panel_layout.setSpacing(8)
            preview_title = QLabel("Preview", self.preview_panel)
            preview_title.setProperty("sectionCardRole", "title")
            preview_panel_layout.addWidget(preview_title)

            self.preview_widget = FixationCrossPreview(self.preview_panel)
            preview_panel_layout.addWidget(self.preview_widget, 1)

            self.fixation_panel.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )
            self.preview_panel.setMinimumWidth(280)
            self.preview_panel.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Expanding,
            )
            content_layout = QHBoxLayout()
            content_layout.setContentsMargins(0, 0, 0, 0)
            content_layout.setSpacing(PAGE_SECTION_GAP)
            content_layout.addWidget(settings_column, 2)
            content_layout.addWidget(self.preview_panel, 1)
            fixation_panel_layout.addLayout(content_layout)
            layout.addWidget(self.fixation_panel)
        else:
            fixation_panel_layout.addWidget(settings_column)
            layout.addWidget(self.fixation_panel)

        apply_fixation_settings_theme(self)

        self._document.project_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        fixation = self._document.project.settings.fixation_task
        with QSignalBlocker(self.fixation_enabled_checkbox):
            self.fixation_enabled_checkbox.setChecked(fixation.enabled)
        with QSignalBlocker(self.fixation_accuracy_checkbox):
            self.fixation_accuracy_checkbox.setChecked(fixation.accuracy_task_enabled)
        with QSignalBlocker(self.target_count_mode_combo):
            self.target_count_mode_combo.setCurrentIndex(
                self.target_count_mode_combo.findData(fixation.target_count_mode)
            )
        with QSignalBlocker(self.changes_per_sequence_spin):
            self.changes_per_sequence_spin.setValue(fixation.changes_per_sequence)
        with QSignalBlocker(self.target_count_min_spin):
            self.target_count_min_spin.setValue(fixation.target_count_min)
        with QSignalBlocker(self.target_count_max_spin):
            self.target_count_max_spin.setValue(fixation.target_count_max)
        with QSignalBlocker(self.no_repeat_count_checkbox):
            self.no_repeat_count_checkbox.setChecked(fixation.no_immediate_repeat_count)
        with QSignalBlocker(self.target_duration_spin):
            self.target_duration_spin.setValue(fixation.target_duration_ms)
        with QSignalBlocker(self.min_gap_spin):
            self.min_gap_spin.setValue(fixation.min_gap_ms)
        with QSignalBlocker(self.max_gap_spin):
            self.max_gap_spin.setValue(fixation.max_gap_ms)
        with QSignalBlocker(self.base_color_combo):
            _select_color_combo_value(
                self.base_color_combo,
                str(fixation.base_color),
                fallback=_DEFAULT_BASE_COLOR,
            )
        with QSignalBlocker(self.target_color_combo):
            _select_color_combo_value(
                self.target_color_combo,
                str(fixation.target_color),
                fallback=_DEFAULT_TARGET_COLOR,
            )
        with QSignalBlocker(self.response_key_edit):
            self.response_key_edit.setText(fixation.response_key)
        with QSignalBlocker(self.response_window_spin):
            self.response_window_spin.setValue(fixation.response_window_seconds)
        with QSignalBlocker(self.cross_size_spin):
            self.cross_size_spin.setValue(fixation.cross_size_px)
        with QSignalBlocker(self.line_width_spin):
            self.line_width_spin.setValue(fixation.line_width_px)
        self._update_fixation_visibility_state()
        self._refresh_condition_guidance()
        self._refresh_preview()

    def _update_fixation_visibility_state(self) -> None:
        fixation_enabled = self.fixation_enabled_checkbox.isChecked()
        if not fixation_enabled and self.fixation_accuracy_checkbox.isChecked():
            with QSignalBlocker(self.fixation_accuracy_checkbox):
                self.fixation_accuracy_checkbox.setChecked(False)
        self.fixation_accuracy_checkbox.setEnabled(fixation_enabled)

        for group in (
            self.fixation_behavior_group,
            self.fixation_timing_group,
            self.fixation_appearance_group,
        ):
            group.setVisible(fixation_enabled)
            group.setEnabled(fixation_enabled)
        for panel in (
            self.fixation_behavior_panel,
            self.fixation_timing_panel,
            self.fixation_appearance_panel,
        ):
            panel.setVisible(fixation_enabled)
            panel.setEnabled(fixation_enabled)

        randomized_mode = self.target_count_mode_combo.currentData() == "randomized"
        if self._schedule_row_behavior == "hide":
            _set_form_row_visible(
                self.fixation_behavior_layout,
                self.changes_per_sequence_spin,
                not randomized_mode,
            )
            _set_form_row_visible(
                self.fixation_behavior_layout,
                self.target_count_min_spin,
                randomized_mode,
            )
            _set_form_row_visible(
                self.fixation_behavior_layout,
                self.target_count_max_spin,
                randomized_mode,
            )
            _set_form_row_visible(
                self.fixation_behavior_layout,
                self.no_repeat_count_checkbox,
                randomized_mode,
            )
        else:
            _set_form_row_visible(
                self.fixation_behavior_layout, self.changes_per_sequence_spin, True
            )
            _set_form_row_visible(self.fixation_behavior_layout, self.target_count_min_spin, True)
            _set_form_row_visible(self.fixation_behavior_layout, self.target_count_max_spin, True)
            _set_form_row_visible(
                self.fixation_behavior_layout,
                self.no_repeat_count_checkbox,
                True,
            )
            self.changes_per_sequence_spin.setEnabled(fixation_enabled and not randomized_mode)
            self.target_count_min_spin.setEnabled(fixation_enabled and randomized_mode)
            self.target_count_max_spin.setEnabled(fixation_enabled and randomized_mode)
            self.no_repeat_count_checkbox.setEnabled(fixation_enabled and randomized_mode)

        accuracy_enabled = fixation_enabled and self.fixation_accuracy_checkbox.isChecked()
        self.fixation_response_panel.setVisible(accuracy_enabled)
        self.fixation_response_panel.setEnabled(accuracy_enabled)
        self.fixation_response_group.setVisible(accuracy_enabled)
        self.fixation_response_group.setEnabled(accuracy_enabled)
        if not accuracy_enabled:
            self.response_key_popover.close()

    def _build_compact_feasibility_text(
        self,
        *,
        guidance_rows: list[ConditionFixationGuidance] | None,
        guidance_error: Exception | None,
    ) -> str:
        label = "Estimated maximum feasible cross changes per condition"
        if guidance_error is not None:
            return f"{label}: unavailable ({guidance_error})"
        if not guidance_rows:
            return f"{label}: unavailable (add a condition)."
        estimated_values = sorted(
            {row.estimated_max_color_changes_per_condition for row in guidance_rows}
        )
        if len(estimated_values) == 1:
            return f"{label}: {estimated_values[0]}"
        return f"{label}: {estimated_values[0]}-{estimated_values[-1]} (varies by condition)"

    def _refresh_condition_guidance(self) -> None:
        refresh_hz = self._document.project.settings.display.preferred_refresh_hz or 60.0
        guidance_rows: list[ConditionFixationGuidance] | None = None
        guidance_error: Exception | None = None
        try:
            guidance_rows = self._document.fixation_guidance(refresh_hz=refresh_hz)
        except Exception as error:
            guidance_error = error
        self.fixation_feasibility_label.setText(
            self._build_compact_feasibility_text(
                guidance_rows=guidance_rows,
                guidance_error=guidance_error,
            )
        )

    def _refresh_preview(self) -> None:
        if self.preview_widget is None:
            return
        fixation = self._document.project.settings.fixation_task
        background_color = self._document.project.settings.display.background_color
        if not isinstance(background_color, str):
            background_color = "#000000"
        canonical_background = _canonical_runtime_background_hex(background_color) or "#000000"
        self.preview_widget.set_preview_settings(
            background_color=canonical_background,
            base_color=str(fixation.base_color),
            target_color=str(fixation.target_color),
            cross_size_px=fixation.cross_size_px,
            line_width_px=fixation.line_width_px,
        )

    def _on_fixation_enabled_toggled(self) -> None:
        self._update_fixation_visibility_state()
        self._apply_fixation_settings()

    def _on_target_count_mode_changed(self) -> None:
        self._update_fixation_visibility_state()
        self._apply_fixation_settings()

    def _on_fixation_accuracy_toggled(self) -> None:
        self._update_fixation_visibility_state()
        self._apply_fixation_settings()

    def _show_response_key_picker(self) -> None:
        if self.response_key_popover.isVisible():
            self.response_key_popover.close()
            return
        self.response_key_popover.adjustSize()
        position = self.response_key_button.mapToGlobal(
            self.response_key_button.rect().bottomLeft()
        )
        self.response_key_popover.move(position)
        self.response_key_popover.show()
        self.response_key_popover.raise_()

    def _set_response_key(self, key: str) -> None:
        normalized = key.strip().lower() or "space"
        with QSignalBlocker(self.response_key_edit):
            self.response_key_edit.setText(normalized)
        self._apply_fixation_settings()

    def _apply_fixation_settings(self) -> None:
        try:
            response_key = self.response_key_edit.text().strip().lower() or "space"
            self._document.update_fixation_settings(
                enabled=self.fixation_enabled_checkbox.isChecked(),
                accuracy_task_enabled=self.fixation_accuracy_checkbox.isChecked(),
                target_count_mode=self.target_count_mode_combo.currentData(),
                changes_per_sequence=self.changes_per_sequence_spin.value(),
                target_count_min=self.target_count_min_spin.value(),
                target_count_max=self.target_count_max_spin.value(),
                no_immediate_repeat_count=self.no_repeat_count_checkbox.isChecked(),
                target_duration_ms=self.target_duration_spin.value(),
                min_gap_ms=self.min_gap_spin.value(),
                max_gap_ms=self.max_gap_spin.value(),
                base_color=str(self.base_color_combo.currentData()),
                target_color=str(self.target_color_combo.currentData()),
                response_key=response_key,
                response_window_seconds=self.response_window_spin.value(),
                response_keys=[response_key],
                cross_size_px=self.cross_size_spin.value(),
                line_width_px=self.line_width_spin.value(),
            )
            self._refresh_preview()
        except Exception as error:
            display_error = error
            if message := _fixation_settings_error_message(error):
                display_error = ValueError(message)
            _show_error_dialog(
                self,
                "Fixation Settings Error",
                display_error,
            )
            self.refresh()


class FixationCrossSettingsPage(FixationSettingsEditor):
    """Fixation-task settings page."""

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(document, schedule_row_behavior="hide", parent=parent)
