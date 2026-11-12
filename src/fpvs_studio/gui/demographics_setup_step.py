"""Build and preview the ordered participant questionnaire in Setup."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from html import escape
from uuid import uuid4

from pydantic import ValidationError
from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.demographics import (
    DEMOGRAPHICS_OPTION_COUNT_LIMIT,
    DEMOGRAPHICS_OPTION_KINDS,
    DEMOGRAPHICS_OTHER_KINDS,
    DEMOGRAPHICS_PROMPT_LIMIT,
    DemographicsQuestion,
    DemographicsQuestionKind,
    default_demographics_questions,
)
from fpvs_studio.gui.components import mark_error_text, mark_primary_action, mark_secondary_action
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.run_page import ParticipantNumberDialog
from fpvs_studio.gui.window_layout import SectionCard

_RESPONSE_TYPES: dict[DemographicsQuestionKind, str] = {
    "text": "Short answer",
    "paragraph": "Paragraph",
    "choice": "Multiple choice",
    "checkboxes": "Checkboxes",
    "dropdown": "Dropdown",
    "scale": "Linear scale",
    "rating": "Rating",
    "date": "Date",
    "time": "Time",
    "age": "Age in years",
    "yes_no": "Yes or no",
}


@dataclass
class _QuestionDraft:
    id: str
    prompt: str = ""
    kind: DemographicsQuestionKind = "text"
    options: list[str] = field(default_factory=list)
    allow_other: bool = False
    required: bool = True
    scale_min: int = 1
    scale_max: int = 5
    scale_min_label: str = ""
    scale_max_label: str = ""

    def validate(self) -> DemographicsQuestion:
        return DemographicsQuestion(
            id=self.id,
            prompt=self.prompt,
            kind=self.kind,
            options=self.options if self.kind in DEMOGRAPHICS_OPTION_KINDS else [],
            allow_other=self.allow_other and self.kind in DEMOGRAPHICS_OTHER_KINDS,
            required=self.required,
            scale_min=self.scale_min if self.kind == "scale" else 1,
            scale_max=self.scale_max if self.kind in {"scale", "rating"} else 5,
            scale_min_label=self.scale_min_label if self.kind == "scale" else "",
            scale_max_label=self.scale_max_label if self.kind == "scale" else "",
        )


class _QuestionOutline(QListWidget):
    order_changed = Signal()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        super().dropEvent(event)
        QTimer.singleShot(0, self.order_changed.emit)


class _QuestionEditor(SectionCard):
    changed = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(
            title="Question", object_name="setup_demographics_editor", framed=False, parent=parent,
        )
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self._draft: _QuestionDraft | None = None
        self._option_edits: list[QLineEdit] = []

        prompt_row = QHBoxLayout()
        self.prompt_edit = QLineEdit(self)
        self.prompt_edit.setPlaceholderText("Enter a question")
        self.prompt_edit.setAccessibleName("Question wording")
        self.prompt_edit.textChanged.connect(lambda text: self._set_value("prompt", text))
        self.kind_combo = QComboBox(self)
        self.kind_combo.setAccessibleName("Response type")
        for kind, label in _RESPONSE_TYPES.items():
            self.kind_combo.addItem(label, kind)
        self.kind_combo.currentIndexChanged.connect(self._kind_changed)
        prompt_row.addWidget(self.prompt_edit, 1)
        prompt_row.addWidget(self.kind_combo)
        self.body_layout.addLayout(prompt_row)

        self.options_panel = QWidget(self)
        option_layout = QVBoxLayout(self.options_panel)
        option_layout.setContentsMargins(0, 0, 0, 0)
        option_layout.setSpacing(6)
        self.options_scroll = QScrollArea(self.options_panel)
        self.options_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.options_scroll.setWidgetResizable(True)
        self.options_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.options_scroll.setAccessibleName("Answer options")
        self.options_scroll.setMinimumHeight(70)
        self.options_content = QWidget(self.options_scroll)
        self.option_rows = QVBoxLayout(self.options_content)
        self.option_rows.setContentsMargins(0, 0, 0, 0)
        self.option_rows.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.option_rows.setSpacing(6)
        self.options_scroll.setWidget(self.options_content)
        option_layout.addWidget(self.options_scroll, 1)
        self.add_option_button = QPushButton("Add option", self.options_panel)
        self.add_option_button.clicked.connect(self._add_option)
        self.other_button = QPushButton("Add Other", self.options_panel)
        self.other_button.clicked.connect(self._toggle_other)
        option_actions = QHBoxLayout()
        for button in (self.add_option_button, self.other_button):
            mark_secondary_action(button)
            option_actions.addWidget(button)
        option_actions.addStretch(1)
        option_layout.addLayout(option_actions)
        self.body_layout.addWidget(self.options_panel, 1)

        self.range_panel = QWidget(self)
        range_layout = QVBoxLayout(self.range_panel)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(8)
        range_row = QHBoxLayout()
        self.scale_min_combo = QComboBox(self.range_panel)
        self.scale_min_combo.addItems(["0", "1"])
        self.scale_min_combo.setAccessibleName("Scale minimum")
        self.scale_min_combo.currentIndexChanged.connect(
            lambda index: self._set_value("scale_min", index),
        )
        self.scale_min_title = QLabel("Minimum", self.range_panel)
        self.scale_min_title.setBuddy(self.scale_min_combo)
        range_row.addWidget(self.scale_min_title)
        range_row.addWidget(self.scale_min_combo)
        self.scale_max_spin = QSpinBox(self.range_panel)
        self.scale_max_spin.setRange(2, 10)
        self.scale_max_spin.setAccessibleName("Maximum score")
        self.scale_max_spin.valueChanged.connect(lambda value: self._set_value("scale_max", value))
        maximum_title = QLabel("Maximum", self.range_panel)
        maximum_title.setBuddy(self.scale_max_spin)
        range_row.addWidget(maximum_title)
        range_row.addWidget(self.scale_max_spin)
        range_row.addStretch(1)
        range_layout.addLayout(range_row)
        self.endpoint_labels = QWidget(self.range_panel)
        endpoint_row = QHBoxLayout(self.endpoint_labels)
        endpoint_row.setContentsMargins(0, 0, 0, 0)
        self.scale_min_label_edit = QLineEdit(self.endpoint_labels)
        self.scale_max_label_edit = QLineEdit(self.endpoint_labels)
        for end, edit in (("Minimum", self.scale_min_label_edit),
                          ("Maximum", self.scale_max_label_edit)):
            edit.setPlaceholderText(f"{end} label (optional)")
            edit.setAccessibleName(f"{end} label")
            endpoint_row.addWidget(edit)
        self.scale_min_label_edit.textChanged.connect(
            lambda text: self._set_value("scale_min_label", text),
        )
        self.scale_max_label_edit.textChanged.connect(
            lambda text: self._set_value("scale_max_label", text),
        )
        range_layout.addWidget(self.endpoint_labels)
        self.body_layout.addWidget(self.range_panel)

        self.body_layout.addStretch()
        self.error_label = QLabel(self)
        self.error_label.setWordWrap(True)
        self.error_label.setTextFormat(Qt.TextFormat.PlainText)
        self.error_label.hide()
        mark_error_text(self.error_label)
        self.body_layout.addWidget(self.error_label)

        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.HLine)
        self.body_layout.addWidget(separator)
        footer = QHBoxLayout()
        self.duplicate_button = QPushButton("Duplicate", self)
        self.remove_button = QPushButton("Delete", self)
        self.required_checkbox = QCheckBox("Required", self)
        self.required_checkbox.toggled.connect(lambda value: self._set_value("required", value))
        footer.addStretch(1)
        for button in (self.duplicate_button, self.remove_button):
            mark_secondary_action(button)
            footer.addWidget(button)
        footer.addWidget(self.required_checkbox)
        self.body_layout.addLayout(footer)

    def set_draft(self, draft: _QuestionDraft) -> None:
        self._draft = draft
        with (
            QSignalBlocker(self.prompt_edit),
            QSignalBlocker(self.kind_combo),
            QSignalBlocker(self.required_checkbox),
            QSignalBlocker(self.scale_min_combo),
            QSignalBlocker(self.scale_min_label_edit),
            QSignalBlocker(self.scale_max_label_edit),
        ):
            self.prompt_edit.setText(draft.prompt)
            self.kind_combo.setCurrentIndex(self.kind_combo.findData(draft.kind))
            self.required_checkbox.setChecked(draft.required)
            self.scale_min_combo.setCurrentIndex(draft.scale_min)
            self.scale_min_label_edit.setText(draft.scale_min_label)
            self.scale_max_label_edit.setText(draft.scale_max_label)
        self._refresh_kind_controls()
        self.error_label.hide()

    def show_error(self, message: str, location: tuple[str | int, ...]) -> None:
        self.error_label.setText(message)
        self.error_label.show()
        target: QWidget = self.prompt_edit
        if location and location[0] == "scale_min_label":
            target = self.scale_min_label_edit
        elif location and location[0] == "scale_max_label":
            target = self.scale_max_label_edit
        elif location and location[0] == "options":
            index = int(location[1]) if len(location) > 1 else 0
            target = (
                self._option_edits[index]
                if index < len(self._option_edits) else self.add_option_button
            )
            if target is not self.add_option_button:
                self.options_scroll.ensureWidgetVisible(target)
        target.setFocus()

    def _set_value(self, field_name: str, value: object) -> None:
        if self._draft is not None:
            setattr(self._draft, field_name, value)
            self._mark_changed()

    def _kind_changed(self) -> None:
        draft = self._draft
        if draft is None:
            return
        draft.kind = self.kind_combo.currentData()
        if draft.kind in DEMOGRAPHICS_OPTION_KINDS and not draft.options:
            draft.options = ["", ""]
        if draft.kind == "rating":
            draft.scale_max = max(3, draft.scale_max)
        self._refresh_kind_controls()
        self._mark_changed()

    def _refresh_kind_controls(self) -> None:
        assert self._draft is not None
        kind = self._draft.kind
        self.options_panel.setVisible(kind in DEMOGRAPHICS_OPTION_KINDS)
        self.other_button.setVisible(kind in DEMOGRAPHICS_OTHER_KINDS)
        self.range_panel.setVisible(kind in {"scale", "rating"})
        self.scale_min_title.setVisible(kind == "scale")
        self.scale_min_combo.setVisible(kind == "scale")
        self.endpoint_labels.setVisible(kind == "scale")
        with QSignalBlocker(self.scale_max_spin):
            self.scale_max_spin.setMinimum(3 if kind == "rating" else 2)
            self.scale_max_spin.setValue(self._draft.scale_max)
        if kind in DEMOGRAPHICS_OPTION_KINDS:
            self._refresh_option_rows()

    def _refresh_option_rows(self) -> None:
        assert self._draft is not None
        while self.option_rows.count():
            item = self.option_rows.takeAt(0)
            assert item is not None
            if widget := item.widget():
                widget.hide()
                widget.deleteLater()
        self._option_edits.clear()
        marker = "□" if self._draft.kind == "checkboxes" else "○"
        for index, value in enumerate(self._draft.options):
            row = QWidget(self.options_content)
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(QLabel(marker, row))
            edit = QLineEdit(value, row)
            edit.setPlaceholderText(f"Option {index + 1}")
            edit.setAccessibleName(f"Option {index + 1}")
            edit.setToolTip(f"<p>{escape(value)}</p>" if value else "")
            edit.textChanged.connect(lambda text, pos=index: self._update_option(pos, text))
            layout.addWidget(edit, 1)
            remove = QPushButton("Remove", row)
            remove.setAccessibleName(f"Remove option {index + 1}")
            remove.clicked.connect(lambda _checked=False, pos=index: self._remove_option(pos))
            mark_secondary_action(remove)
            layout.addWidget(remove)
            self._option_edits.append(edit)
            self.option_rows.addWidget(row)
        other_enabled = self._draft.allow_other and self._draft.kind in DEMOGRAPHICS_OTHER_KINDS
        if other_enabled:
            self.option_rows.addWidget(QLabel(f"{marker}  Other (free text)", self.options_content))
        self.other_button.setText("Remove Other" if other_enabled else "Add Other")
        self.add_option_button.setEnabled(
            len(self._draft.options) < DEMOGRAPHICS_OPTION_COUNT_LIMIT,
        )

    def _add_option(self) -> None:
        assert self._draft is not None
        self._draft.options.append("")
        self._refresh_option_rows()
        editor = self._option_edits[-1]
        editor.setFocus()
        self.options_scroll.ensureWidgetVisible(editor)
        self._mark_changed()

    def _update_option(self, index: int, value: str) -> None:
        assert self._draft is not None
        self._draft.options[index] = value
        self._option_edits[index].setToolTip(f"<p>{escape(value)}</p>" if value else "")
        self._mark_changed()

    def _remove_option(self, index: int) -> None:
        assert self._draft is not None
        self._draft.options.pop(index)
        self._refresh_option_rows()
        if self._option_edits:
            self._option_edits[min(index, len(self._option_edits) - 1)].setFocus()
        else:
            self.add_option_button.setFocus()
        self._mark_changed()

    def _toggle_other(self) -> None:
        assert self._draft is not None
        self._draft.allow_other = not self._draft.allow_other
        self._refresh_option_rows()
        self._mark_changed()

    def _mark_changed(self) -> None:
        self.error_label.hide()
        self.changed.emit()


class DemographicsSetupStep(QWidget):
    """Edit the questionnaire as a draft until normal Setup navigation or save."""

    pending_edits_changed = Signal()

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._document = document
        self._defaults = self._make_drafts(default_demographics_questions())
        self._committed: list[_QuestionDraft] = []
        self._draft: list[_QuestionDraft] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        toolbar = QHBoxLayout()
        toolbar.addStretch(1)
        self.discard_button = QPushButton("Discard draft", self)
        self.discard_button.setToolTip("Revert unapplied questionnaire edits.")
        self.restore_defaults_button = QPushButton("Restore defaults", self)
        self.restore_defaults_button.setToolTip("Replace all questions with the Studio defaults.")
        self.preview_button = QPushButton("Preview", self)
        self.preview_button.setToolTip("Try the participant questionnaire.")
        for button in (self.discard_button, self.restore_defaults_button, self.preview_button):
            mark_secondary_action(button)
            toolbar.addWidget(button)
        self.discard_button.clicked.connect(self._discard_draft)
        self.restore_defaults_button.clicked.connect(self._restore_defaults)
        self.preview_button.clicked.connect(self._preview)
        layout.addLayout(toolbar)

        workspace = QHBoxLayout()
        workspace.setSpacing(16)
        outline = SectionCard(title="Questions", framed=False, parent=self)
        outline.setMaximumWidth(265)
        outline.card_layout.setContentsMargins(0, 0, 0, 0)
        self.question_list = _QuestionOutline(outline)
        self.question_list.setAccessibleName("Questions in presentation order")
        self.question_list.setToolTip("Drag to change the question order.")
        self.question_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.question_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.question_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.question_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.question_list.setDropIndicatorShown(True)
        self.question_list.currentRowChanged.connect(self._select_question)
        self.question_list.order_changed.connect(self._sync_outline_order)
        outline.body_layout.addWidget(self.question_list, 1)
        move_buttons = QHBoxLayout()
        self.move_up_button = QPushButton("Move up", outline)
        self.move_down_button = QPushButton("Move down", outline)
        for button, offset in ((self.move_up_button, -1), (self.move_down_button, 1)):
            mark_secondary_action(button)
            move_buttons.addWidget(button)
            button.clicked.connect(lambda _checked=False, direction=offset: self._move(direction))
        outline.body_layout.addLayout(move_buttons)
        self.add_button = QPushButton("Add question", outline)
        mark_primary_action(self.add_button)
        self.add_button.clicked.connect(self._add_question)
        outline.body_layout.addWidget(self.add_button)
        workspace.addWidget(outline, 1)

        self.editor = _QuestionEditor(self)
        self.editor.changed.connect(self._question_changed)
        self.editor.remove_button.clicked.connect(self._delete)
        self.editor.duplicate_button.clicked.connect(self._duplicate)
        self.empty_label = QLabel("No demographics questions", self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.editor_stack = QStackedWidget(self)
        self.editor_stack.addWidget(self.editor)
        self.editor_stack.addWidget(self.empty_label)
        workspace.addWidget(self.editor_stack, 3)
        layout.addLayout(workspace, 1)
        self._discard_draft()

    @staticmethod
    def _make_drafts(questions: list[DemographicsQuestion]) -> list[_QuestionDraft]:
        return [_QuestionDraft(**question.model_dump()) for question in questions]

    def has_pending_edits(self) -> bool:
        return self._draft != self._committed

    def flush_pending_edits(self) -> bool:
        if not self.has_pending_edits():
            return True
        questions = self._validated_questions()
        if questions is None:
            return False
        self._document.update_demographics_questions(questions)
        self._discard_draft()
        return True

    def refresh(self) -> None:
        if not self.has_pending_edits():
            committed = self._make_drafts(self._document.project.demographics_questions)
            if self._committed != committed:
                self._discard_draft()

    def _discard_draft(self) -> None:
        row = self.question_list.currentRow()
        questions = self._document.project.demographics_questions
        self._committed = self._make_drafts(questions)
        self._draft = self._make_drafts(questions)
        self._rebuild_outline(row)
        self._update_draft_actions()

    def _restore_defaults(self) -> None:
        self._draft = [
            replace(question, options=list(question.options)) for question in self._defaults
        ]
        self._rebuild_outline(0)
        self._update_draft_actions()

    def _rebuild_outline(self, row: int) -> None:
        with QSignalBlocker(self.question_list):
            self.question_list.clear()
            for index, draft in enumerate(self._draft):
                item = QListWidgetItem()
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
                self._update_item(item, index, draft)
                self.question_list.addItem(item)
            if self._draft:
                self.question_list.setCurrentRow(max(0, min(row, len(self._draft) - 1)))
        self._select_question(self.question_list.currentRow())

    def _update_item(self, item: QListWidgetItem, row: int, draft: _QuestionDraft) -> None:
        prompt = draft.prompt.strip() or "Untitled question"
        label = f"{row + 1}. {prompt}"
        detail = _RESPONSE_TYPES[draft.kind]
        if draft.id == "colorblind" and any(
            question.id == draft.id and question.prompt == prompt and question.kind == draft.kind
            for question in self._defaults
        ):
            detail += ". A Yes answer selects accessible fixation colors."
        item.setText(f"⋮⋮  {label}")
        item.setData(Qt.ItemDataRole.UserRole, draft.id)
        item.setToolTip(f"<p>{escape(label)}<br>{detail}</p>")
        item.setData(Qt.ItemDataRole.AccessibleTextRole, f"{label} {detail}")

    def _select_question(self, row: int) -> None:
        self.move_up_button.setEnabled(row > 0)
        self.move_down_button.setEnabled(0 <= row < len(self._draft) - 1)
        self.editor_stack.setCurrentWidget(self.editor if row >= 0 else self.empty_label)
        if row >= 0:
            current = self.question_list.item(row).data(Qt.ItemDataRole.UserRole)
            draft = next((question for question in self._draft if question.id == current), None)
            if draft is not None:
                self.editor.set_draft(draft)

    def _question_changed(self) -> None:
        row = self.question_list.currentRow()
        if row >= 0:
            self._update_item(self.question_list.item(row), row, self._draft[row])
        self._update_draft_actions()

    def _update_draft_actions(self) -> None:
        self.restore_defaults_button.setEnabled(self._draft != self._defaults)
        self.discard_button.setEnabled(self.has_pending_edits())
        self.pending_edits_changed.emit()

    def _add_question(self) -> None:
        self._draft.append(_QuestionDraft(id=uuid4().hex, required=False))
        self._rebuild_outline(len(self._draft) - 1)
        self.editor.prompt_edit.setFocus()
        self._update_draft_actions()

    def _duplicate(self) -> None:
        row = self.question_list.currentRow()
        draft = self._draft[row]
        duplicate = replace(draft, id=uuid4().hex, options=list(draft.options))
        self._draft.insert(row + 1, duplicate)
        self._rebuild_outline(row + 1)
        self.editor.prompt_edit.setFocus()
        self.editor.prompt_edit.selectAll()
        self._update_draft_actions()

    def _delete(self) -> None:
        row = self.question_list.currentRow()
        self._draft.pop(row)
        self._rebuild_outline(row)
        if not self._draft:
            self.add_button.setFocus()
        self._update_draft_actions()

    def _move(self, offset: int) -> None:
        row = self.question_list.currentRow()
        target = row + offset
        if row >= 0 and 0 <= target < len(self._draft):
            self._draft[target], self._draft[row] = self._draft[row], self._draft[target]
            self._rebuild_outline(target)
            self._update_draft_actions()

    def _sync_outline_order(self) -> None:
        drafts = {question.id: question for question in self._draft}
        ids = [self.question_list.item(index).data(Qt.ItemDataRole.UserRole)
               for index in range(self.question_list.count())]
        if len(ids) == len(drafts) and set(ids) == drafts.keys():
            self._draft = [drafts[question_id] for question_id in ids]
        self._rebuild_outline(self.question_list.currentRow())
        self._update_draft_actions()

    def _validated_questions(self) -> list[DemographicsQuestion] | None:
        questions: list[DemographicsQuestion] = []
        for index, draft in enumerate(self._draft):
            try:
                questions.append(draft.validate())
            except ValidationError as error:
                issue = error.errors()[0]
                location = issue["loc"]
                message = issue["msg"].removeprefix("Value error, ")
                if location and location[0] == "prompt":
                    if not draft.prompt.strip():
                        message = "Enter the question wording."
                    elif len(draft.prompt.strip()) > DEMOGRAPHICS_PROMPT_LIMIT:
                        message = f"Keep questions to {DEMOGRAPHICS_PROMPT_LIMIT} characters."
                elif location and location[0] == "options" and len(location) > 1:
                    message = f"Option {int(location[1]) + 1}. {message}"
                elif not location and draft.kind in DEMOGRAPHICS_OPTION_KINDS:
                    location = ("options",)
                self.question_list.setCurrentRow(index)
                self.editor.show_error(message, location)
                return None
        return questions

    def _preview(self) -> None:
        questions = self._validated_questions()
        if questions is None:
            return
        dialog = ParticipantNumberDialog(self, demographics_questions=questions, preview=True)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
