"""Participant controls shared by launch and the Setup preview."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from html import escape

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QAbstractButton,
    QBoxLayout,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.demographics import (
    DemographicsQuestion,
    DemographicsResponseError,
    DemographicsValue,
)
from fpvs_studio.gui.components import mark_secondary_action


@dataclass(frozen=True)
class _ResponseField:
    widget: QWidget
    read: Callable[[], DemographicsValue | None]
    focus: Callable[[], QWidget]
    full_width: bool = False


class _ChoiceField(QWidget):
    """Render independent checkboxes or an exclusive group of radio buttons."""

    changed = Signal()

    def __init__(self, question: DemographicsQuestion, parent: QWidget) -> None:
        super().__init__(parent)
        self._question_id = question.id
        self._multiple = question.kind == "checkboxes"
        self._group = QButtonGroup(self)
        self._group.setExclusive(not self._multiple)
        self._labels: dict[QAbstractButton, str] = {}
        self._other_button: QAbstractButton | None = None
        self._other_edit: QLineEdit | None = None
        self.setObjectName(f"participant_{question.id}_choices")
        self.setAccessibleName(question.prompt)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        # Compact short groups, including Studio's original default choices.
        widest_option = max(
            self.fontMetrics().horizontalAdvance(option) for option in question.options
        )
        self.compact = (
            len(question.options) <= 3 and len(question.options) * (widest_option + 26) <= 340
        )
        direction = (
            QBoxLayout.Direction.LeftToRight if self.compact else QBoxLayout.Direction.TopToBottom
        )
        options_layout = QBoxLayout(direction)
        options_layout.setSpacing(4)
        layout.addLayout(options_layout)
        self._options = [
            self._make_option(option, f"participant_{question.id}_option_{index}", options_layout)
            for index, option in enumerate(question.options)
        ]

        if question.allow_other:
            other_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
            other_layout.setSpacing(8)
            layout.addLayout(other_layout)
            self._other_button = self._make_option(
                "Other answer", f"participant_{question.id}_other_option", other_layout,
            )
            self._other_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self._other_edit = QLineEdit(self)
            self._other_edit.setObjectName(f"participant_{question.id}_other_edit")
            self._other_edit.setAccessibleName(f"Other answer for {question.prompt}")
            self._other_edit.setPlaceholderText("Enter another answer")
            self._other_edit.setEnabled(False)
            self._other_edit.textChanged.connect(self.changed)
            self._other_button.toggled.connect(self._other_edit.setEnabled)
            other_layout.addWidget(self._other_edit, 1)

        if not self._multiple and not question.required:
            clear = QPushButton("Clear answer", self)
            clear.setObjectName(f"participant_{question.id}_clear")
            clear.setAutoDefault(False)
            clear.setEnabled(False)
            mark_secondary_action(clear)
            clear.clicked.connect(self._clear_selection)
            self._group.buttonToggled.connect(lambda _button, _checked: clear.setEnabled(
                self._group.checkedButton() is not None,
            ))
            layout.addWidget(clear, alignment=Qt.AlignmentFlag.AlignLeft)

    def _make_option(self, label: str, name: str, layout: QBoxLayout) -> QAbstractButton:
        button = QCheckBox(self) if self._multiple else QRadioButton(self)
        button.setObjectName(name)
        button.setText(label.replace("&", "&&"))
        button.setAccessibleName(label)
        button.setToolTip(f"<p>{escape(label)}</p>")
        button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        button.installEventFilter(self)
        self._labels[button] = label
        self._group.addButton(button)
        button.toggled.connect(self.changed)
        layout.addWidget(button, 1)
        return button

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.Resize, QEvent.Type.FontChange) and isinstance(
            watched, QAbstractButton,
        ):
            if watched is not self._other_button:
                style = watched.style()
                indicator = (
                    QStyle.PixelMetric.PM_IndicatorWidth if self._multiple
                    else QStyle.PixelMetric.PM_ExclusiveIndicatorWidth
                )
                spacing = (
                    QStyle.PixelMetric.PM_CheckBoxLabelSpacing if self._multiple
                    else QStyle.PixelMetric.PM_RadioButtonLabelSpacing
                )
                text_width = (
                    watched.contentsRect().width()
                    - style.pixelMetric(indicator, None, watched)
                    - style.pixelMetric(spacing, None, watched)
                )
                text = watched.fontMetrics().elidedText(
                    self._labels[watched], Qt.TextElideMode.ElideRight, max(0, text_width),
                )
                watched.setText(text.replace("&", "&&"))
        return super().eventFilter(watched, event)

    def _clear_selection(self) -> None:
        if (checked := self._group.checkedButton()) is not None:
            self._group.setExclusive(False)
            checked.setChecked(False)
            self._group.setExclusive(True)

    def answer(self) -> DemographicsValue | None:
        values = [self._labels[option] for option in self._options if option.isChecked()]
        if (
            self._other_button is not None
            and self._other_button.isChecked()
            and self._other_edit is not None
        ):
            other = self._other_edit.text()
            if not other.strip():
                raise DemographicsResponseError(self._question_id, "Enter the other answer.")
            values.append(other)
        if self._multiple:
            return values
        return values[0] if values else None

    def response_focus(self) -> QWidget:
        if self._other_edit is not None and self._other_edit.isEnabled():
            return self._other_edit
        return next((option for option in self._options if option.isChecked()), self._options[0])


class DemographicsForm(QScrollArea):
    """Build an ordered questionnaire and return the exact values entered."""

    changed = Signal()

    def __init__(
        self, questions: Sequence[DemographicsQuestion], parent: QWidget, *, prompt_width: int,
    ) -> None:
        super().__init__(parent)
        self._fields: dict[str, _ResponseField] = {}
        self.setWidgetResizable(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        form = QFormLayout(content)
        form.setContentsMargins(0, 0, 0, 0)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for question in questions:
            prompt = question.prompt if question.required else f"{question.prompt} (optional)"
            label = QLabel(prompt, content)
            label.setObjectName(f"participant_{question.id}_prompt")
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setMinimumWidth(1)
            label.setToolTip(f"<p>{escape(prompt)}</p>")
            field = self._build_field(question, content, prompt)
            self._fields[question.id] = field
            if field.full_width:
                form.addRow(label)
                form.addRow(field.widget)
            else:
                label.setFixedWidth(prompt_width)
                form.addRow(label, field.widget)
        self.setWidget(content)

    def _build_field(
        self, question: DemographicsQuestion, parent: QWidget, prompt: str,
    ) -> _ResponseField:
        if question.kind in ("choice", "checkboxes"):
            choices = _ChoiceField(question, parent)
            choices.setAccessibleName(prompt)
            choices.changed.connect(self.changed)
            return _ResponseField(
                choices, choices.answer, choices.response_focus, full_width=not choices.compact,
            )
        if question.kind == "paragraph":
            paragraph = QPlainTextEdit(parent)
            paragraph.setObjectName(f"participant_{question.id}_paragraph")
            paragraph.setAccessibleName(prompt)
            paragraph.setFixedHeight(84)
            paragraph.textChanged.connect(self.changed)
            return _ResponseField(
                paragraph, paragraph.toPlainText, lambda: paragraph, full_width=True,
            )
        if question.kind in ("text", "age", "date", "time"):
            edit = QLineEdit(parent)
            edit.setObjectName(f"participant_{question.id}_edit")
            edit.setAccessibleName(prompt)
            if question.kind == "age":
                edit.setPlaceholderText("Whole number from 1 to 120")
                edit.setValidator(QIntValidator(1, 120, edit))
                edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            elif question.kind == "date":
                edit.setPlaceholderText("YYYY-MM-DD")
                edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            elif question.kind == "time":
                edit.setPlaceholderText("HH:MM (24-hour time)")
                edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            edit.textChanged.connect(self.changed)
            return _ResponseField(edit, edit.text, lambda: edit)

        combo = QComboBox(parent)
        combo.setObjectName(f"participant_{question.id}_combo")
        combo.setAccessibleName(prompt)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(14)
        combo.addItem("Select an answer…" if question.required else "No answer", None)
        for label, value in self._combo_items(question):
            combo.addItem(label, value)
            combo.setItemData(
                combo.count() - 1, f"<p>{escape(label)}</p>", Qt.ItemDataRole.ToolTipRole,
            )
        combo.currentTextChanged.connect(
            lambda current: combo.setToolTip(f"<p>{escape(current)}</p>"),
        )
        combo.currentIndexChanged.connect(self.changed)
        return _ResponseField(combo, combo.currentData, lambda: combo)

    @staticmethod
    def _combo_items(question: DemographicsQuestion) -> list[tuple[str, DemographicsValue]]:
        if question.kind == "yes_no":
            return [("No", False), ("Yes", True)]
        if question.kind == "rating":
            return [
                (f"{value} / {question.scale_max}", value)
                for value in range(1, question.scale_max + 1)
            ]
        if question.kind == "scale":
            endpoints = {
                question.scale_min: question.scale_min_label,
                question.scale_max: question.scale_max_label,
            }
            return [
                (f"{value} — {label}" if (label := endpoints.get(value)) else str(value), value)
                for value in range(question.scale_min, question.scale_max + 1)
            ]
        return [(option, option) for option in question.options]

    def answers(self) -> dict[str, DemographicsValue | None]:
        return {question_id: field.read() for question_id, field in self._fields.items()}

    def focus_answer(self, question_id: str) -> None:
        field = self._fields[question_id].focus()
        field.setFocus()
        self.ensureWidgetVisible(field)
