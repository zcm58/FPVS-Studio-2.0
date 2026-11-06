"""Edit the ordered participant questionnaire in Setup."""

from __future__ import annotations

from html import escape
from uuid import uuid4

from pydantic import ValidationError
from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.demographics import (
    DEMOGRAPHICS_OPTION_LIMIT,
    DEMOGRAPHICS_PROMPT_LIMIT,
    DemographicsQuestion,
    default_demographics_questions,
)
from fpvs_studio.gui.components import (
    apply_dialog_theme,
    configure_setup_form,
    mark_error_text,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.window_layout import SectionCard

_RESPONSE_TYPES = {
    "text": "Short text",
    "choice": "Single choice",
    "yes_no": "Yes or no",
    "age": "Age in years",
}


class _DemographicsQuestionDialog(QDialog):
    """Stage changes to a single question until the author applies them."""

    def __init__(
        self, question: DemographicsQuestion | None, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Question" if question is not None else "Add Question")
        self.setMinimumSize(520, 360)
        self.resize(600, 400)
        self.question: DemographicsQuestion | None = None
        self._question_id = question.id if question is not None else uuid4().hex

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        self.form = QFormLayout()
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.prompt_edit = QLineEdit(self)
        self.prompt_edit.setAccessibleName("Question")
        self.kind_combo = QComboBox(self)
        self.kind_combo.setAccessibleName("Response type")
        for kind, label in _RESPONSE_TYPES.items():
            self.kind_combo.addItem(label, kind)
        self.options_edit = QPlainTextEdit(self)
        self.options_edit.setAccessibleName("Choices, one per line")
        self.options_edit.setFixedHeight(106)
        self.options_edit.setTabChangesFocus(True)
        self.form.addRow("Question", self.prompt_edit)
        self.form.addRow("Response type", self.kind_combo)
        self.form.addRow("Choices (one per line)", self.options_edit)
        configure_setup_form(self.form, stacked=True)
        layout.addLayout(self.form)

        self.error_label = QLabel(self)
        self.error_label.setWordWrap(True)
        self.error_label.setTextFormat(Qt.TextFormat.PlainText)
        self.error_label.hide()
        mark_error_text(self.error_label)
        layout.addWidget(self.error_label)
        layout.addStretch(1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self,
        )
        apply_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        apply_button.setText("Apply" if question is not None else "Add")
        mark_primary_action(apply_button)
        mark_secondary_action(self.buttons.button(QDialogButtonBox.StandardButton.Cancel))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        if question is not None:
            self.prompt_edit.setText(question.prompt)
            self.kind_combo.setCurrentIndex(self.kind_combo.findData(question.kind))
            self.options_edit.setPlainText("\n".join(question.options))
        self.kind_combo.currentIndexChanged.connect(self._update_choice_visibility)
        self._update_choice_visibility()
        apply_dialog_theme(self)
        self.prompt_edit.setFocus()

    def _update_choice_visibility(self) -> None:
        self.form.setRowVisible(self.options_edit, self.kind_combo.currentData() == "choice")
        self.error_label.hide()

    def accept(self) -> None:
        kind = self.kind_combo.currentData()
        options = (
            [line.strip() for line in self.options_edit.toPlainText().splitlines() if line.strip()]
            if kind == "choice" else []
        )
        try:
            self.question = DemographicsQuestion(
                id=self._question_id, prompt=self.prompt_edit.text(), kind=kind, options=options,
            )
        except ValidationError as error:
            issue = error.errors()[0]
            location = issue["loc"]
            if location and location[0] == "prompt":
                message = f"Enter a question of up to {DEMOGRAPHICS_PROMPT_LIMIT} characters."
                self.prompt_edit.setFocus()
            else:
                message = (
                    f"Enter 2 to 20 distinct choices of up to {DEMOGRAPHICS_OPTION_LIMIT} "
                    "characters each."
                )
                self.options_edit.setFocus()
            self.error_label.setText(message)
            self.error_label.show()
            return
        super().accept()


class DemographicsSetupStep(SectionCard):
    """Manage the question list and its presentation order."""

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(
            title="Questions", object_name="setup_demographics_questions", parent=parent,
        )
        self._document = document
        self._displayed_questions: list[DemographicsQuestion] | None = None
        self.question_list = QListWidget(self)
        self.question_list.setAccessibleName("Demographics questions in presentation order")
        self.question_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.question_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.question_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.question_list.currentRowChanged.connect(self._refresh_actions)
        self.question_list.itemDoubleClicked.connect(self._edit_question)
        self.empty_label = QLabel("No demographics questions", self)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.question_stack = QStackedWidget(self)
        self.question_stack.addWidget(self.question_list)
        self.question_stack.addWidget(self.empty_label)
        self.body_layout.addWidget(self.question_stack, 1)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.add_button = QPushButton("Add question…", self)
        self.edit_button = QPushButton("Edit…", self)
        self.remove_button = QPushButton("Remove", self)
        self.move_up_button = QPushButton("Move up", self)
        self.move_down_button = QPushButton("Move down", self)
        self.restore_defaults_button = QPushButton("Restore defaults", self)
        self.add_button.clicked.connect(self._add_question)
        self.edit_button.clicked.connect(self._edit_question)
        self.remove_button.clicked.connect(self._remove_question)
        self.move_up_button.clicked.connect(lambda: self._move_question(-1))
        self.move_down_button.clicked.connect(lambda: self._move_question(1))
        self.restore_defaults_button.clicked.connect(self._restore_defaults)
        self.restore_defaults_button.setToolTip("Replace all questions with the Studio defaults.")
        mark_primary_action(self.add_button)
        toolbar.addWidget(self.add_button)
        for button in (
            self.edit_button, self.remove_button, self.move_up_button, self.move_down_button,
        ):
            mark_secondary_action(button)
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        mark_secondary_action(self.restore_defaults_button)
        toolbar.addWidget(self.restore_defaults_button)
        self.body_layout.addLayout(toolbar)
        self.refresh()

    def refresh(self) -> None:
        questions = self._document.project.demographics_questions
        if questions == self._displayed_questions:
            return
        defaults = default_demographics_questions()
        current_row = self.question_list.currentRow()
        with QSignalBlocker(self.question_list):
            self.question_list.clear()
            for question in questions:
                item = QListWidgetItem(question.prompt)
                detail = _RESPONSE_TYPES[question.kind]
                if question.id == "colorblind" and question in defaults:
                    detail += ". A Yes answer selects accessible fixation colors."
                item.setToolTip(f"<p>{escape(question.prompt)}<br>{detail}</p>")
                item.setData(
                    Qt.ItemDataRole.AccessibleTextRole, f"{question.prompt} {detail}",
                )
                self.question_list.addItem(item)
            if questions:
                self.question_list.setCurrentRow(max(0, min(current_row, len(questions) - 1)))
        self.question_stack.setCurrentWidget(self.question_list if questions else self.empty_label)
        self._displayed_questions = questions
        self.restore_defaults_button.setEnabled(questions != defaults)
        self._refresh_actions()

    def _refresh_actions(self) -> None:
        row = self.question_list.currentRow()
        self.edit_button.setEnabled(row >= 0)
        self.remove_button.setEnabled(row >= 0)
        self.move_up_button.setEnabled(row > 0)
        self.move_down_button.setEnabled(0 <= row < self.question_list.count() - 1)

    def _replace_questions(self, questions: list[DemographicsQuestion], row: int) -> None:
        self._document.update_demographics_questions(questions)
        self.refresh()
        if questions:
            self.question_list.setCurrentRow(min(row, len(questions) - 1))

    def _add_question(self) -> None:
        self._open_question_dialog(None)

    def _edit_question(self) -> None:
        row = self.question_list.currentRow()
        if row >= 0:
            self._open_question_dialog(row)

    def _open_question_dialog(self, row: int | None) -> None:
        questions = list(self._document.project.demographics_questions)
        dialog = _DemographicsQuestionDialog(questions[row] if row is not None else None, self)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted or dialog.question is None:
                return
            if row is None:
                row = len(questions)
                questions.append(dialog.question)
            else:
                questions[row] = dialog.question
            self._replace_questions(questions, row)
        finally:
            dialog.deleteLater()

    def _remove_question(self) -> None:
        row = self.question_list.currentRow()
        if row >= 0:
            questions = list(self._document.project.demographics_questions)
            questions.pop(row)
            self._replace_questions(questions, row)

    def _move_question(self, offset: int) -> None:
        questions = list(self._document.project.demographics_questions)
        row = self.question_list.currentRow()
        target = row + offset
        if row >= 0 and 0 <= target < len(questions):
            questions[row], questions[target] = questions[target], questions[row]
            self._replace_questions(questions, target)

    def _restore_defaults(self) -> None:
        self._replace_questions(default_demographics_questions(), 0)
