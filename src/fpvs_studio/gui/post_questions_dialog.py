"""Simple before/after question authoring and a non-recording participant preview."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.post_questions import (
    apply_post_questionnaire,
    apply_pre_questionnaire,
    make_post_questionnaire,
    make_pre_questionnaire,
    make_yes_no_question,
    remove_post_questionnaire,
    remove_pre_questionnaire,
    validate_simple_post_questionnaire,
    validate_simple_pre_questionnaire,
)
from fpvs_studio.core.task_models import (
    TaskModule,
    TaskOccurrence,
    TaskPhase,
    TaskQuestion,
    TaskQuestionKind,
    TaskResponseKind,
    TaskStepResult,
)
from fpvs_studio.gui.components import (
    DialogHeader,
    apply_dialog_theme,
    mark_destructive_action,
    mark_error_text,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.condition_task_dialog import (
    QuestionnaireEditor,
    _question_from_draft,
    _step_to_draft,
)
from fpvs_studio.gui.modifier_library_dialog import ModifierScopeDialog
from fpvs_studio.runtime.task_runner import question_response_is_valid


def _label(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


class PostQuestionPreview(QDialog):
    """Exercise neutral response controls without running or recording a session."""

    def __init__(self, questions: list[TaskQuestion], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Question preview")
        self.setMinimumSize(700, 500)
        self.resize(760, 560)
        self._questions = [question.model_copy(deep=True) for question in questions]
        self._index = 0
        self.answers: list[TaskStepResult] = []
        self.choice_buttons: dict[str, QPushButton] = {}
        self.text_edit: QLineEdit | QTextEdit | None = None
        self.rating_combo: QComboBox | None = None
        self.choice_group: QButtonGroup | None = None
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(_label("Authoring preview · no responses are saved.", self))
        self.prompt = _label("", self)
        self.prompt.setObjectName("post_question_preview_prompt")
        layout.addWidget(self.prompt)
        self.controls = QWidget(self)
        self.controls_layout = QVBoxLayout(self.controls)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_area = QScrollArea(self)
        self.controls_area.setWidgetResizable(True)
        self.controls_area.setFrameShape(QFrame.Shape.NoFrame)
        self.controls_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.controls_area.setWidget(self.controls)
        layout.addWidget(self.controls_area, 1)
        footer = QHBoxLayout()
        self.close_button = QPushButton("Close", self)
        self.close_button.clicked.connect(self.reject)
        self.close_button.setAutoDefault(False)
        mark_secondary_action(self.close_button)
        footer.addWidget(self.close_button)
        footer.addStretch(1)
        self.continue_button = QPushButton("Continue", self)
        self.continue_button.setObjectName("post_question_preview_continue")
        self.continue_button.clicked.connect(self._advance)
        self.continue_button.setDefault(True)
        mark_primary_action(self.continue_button)
        footer.addWidget(self.continue_button)
        layout.addLayout(footer)
        apply_dialog_theme(self)
        self._render()

    def _render(self) -> None:
        while (item := self.controls_layout.takeAt(0)) is not None:
            if widget := item.widget():
                widget.hide()
                widget.deleteLater()
        if self.choice_group is not None:
            self.choice_group.deleteLater()
            self.choice_group = None
        self.choice_buttons.clear()
        self.text_edit = None
        self.rating_combo = None
        if self._index >= len(self._questions):
            self.prompt.setText("Preview complete. No responses were saved.")
            self.continue_button.setEnabled(False)
            return
        question = self._questions[self._index]
        self.prompt.setText(question.prompt)
        self.prompt.setToolTip(question.prompt)
        if question.kind in {TaskQuestionKind.SINGLE_CHOICE, TaskQuestionKind.MULTIPLE_CHOICE}:
            self.choice_group = QButtonGroup(self.controls)
            self.choice_group.setExclusive(question.kind == TaskQuestionKind.SINGLE_CHOICE)
            for option in question.options:
                button = QPushButton(self.controls)
                button.setAccessibleName(option.label)
                button.setCheckable(True)
                button.setAutoDefault(False)
                button.setEnabled(option.selectable)
                button.setMinimumHeight(36)
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
                button.setToolTip(option.label)
                answer_layout = QVBoxLayout(button)
                answer_layout.setContentsMargins(10, 8, 10, 8)
                answer = _label(option.label, button)
                answer.setAlignment(Qt.AlignmentFlag.AlignCenter)
                answer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                answer.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
                answer_layout.addWidget(answer)
                button.toggled.connect(self._update_continue)
                self.choice_group.addButton(button)
                self.choice_buttons[option.option_id] = button
                self.controls_layout.addWidget(button)
        elif question.kind == TaskQuestionKind.RATING:
            self.rating_combo = QComboBox(self.controls)
            self.rating_combo.addItem("Choose a rating", None)
            minimum = question.min_value or 0
            maximum, step = question.max_value or 0, question.step or 1
            tick_count = int(round((maximum - minimum) / step)) + 1
            for tick in range(tick_count):
                value = round(minimum + tick * step, 10)
                endpoint = (question.min_label if tick == 0 else
                            question.max_label if tick == tick_count - 1 else None)
                self.rating_combo.addItem(
                    f"{value:g} — {endpoint}" if endpoint else f"{value:g}", value,
                )
            self.rating_combo.currentIndexChanged.connect(self._update_continue)
            self.controls_layout.addWidget(self.rating_combo)
        else:
            self.text_edit = (
                QTextEdit(self.controls) if question.kind == TaskQuestionKind.LONG_TEXT
                else QLineEdit(self.controls)
            )
            if isinstance(self.text_edit, QLineEdit):
                self.text_edit.setMaxLength(question.max_text_length)
                if question.kind == TaskQuestionKind.NUMERIC:
                    self.text_edit.setValidator(QDoubleValidator(
                        question.min_value or 0, question.max_value or 0, 8, self.text_edit,
                    ))
            self.text_edit.textChanged.connect(self._update_continue)
            self.controls_layout.addWidget(self.text_edit)
        self.controls_layout.addStretch(1)
        self._update_continue()

    def _result(self) -> TaskStepResult:
        question = self._questions[self._index]
        if self.choice_buttons:
            return TaskStepResult(
                response_kind=TaskResponseKind.OPTION_SELECTION,
                selected_option_ids=[key for key, button in self.choice_buttons.items()
                                     if button.isChecked()],
            )
        if self.rating_combo is not None:
            return TaskStepResult(
                response_kind=TaskResponseKind.RATING,
                numeric_value=self.rating_combo.currentData(),
            )
        assert self.text_edit is not None
        text = (self.text_edit.toPlainText() if isinstance(self.text_edit, QTextEdit)
                else self.text_edit.text())
        if question.kind == TaskQuestionKind.NUMERIC:
            value = float(text) if text.strip() else None
            return TaskStepResult(response_kind=TaskResponseKind.NUMERIC, numeric_value=value)
        return TaskStepResult(response_kind=TaskResponseKind.TEXT, text_value=text)

    def _update_continue(self, *_args: object) -> None:
        if self._index >= len(self._questions):
            return
        try:
            valid = question_response_is_valid(self._questions[self._index], self._result())
        except ValueError:
            valid = False
        self.continue_button.setEnabled(valid)

    def _advance(self) -> None:
        if self._index >= len(self._questions) or not self.continue_button.isEnabled():
            return
        self.answers.append(self._result())
        self._index += 1
        self._render()


def validate_question_editor_module(
    project: ProjectFile, module: TaskModule, phase: TaskPhase,
) -> None:
    """Keep unsupported existing task settings in the advanced editor."""
    if any(module.task_id in [*modifier.pre_task_ids, *modifier.post_task_ids,
                              modifier.baseline_task_id]
           for modifier in project.condition_modifiers):
        raise ValueError("Edit modifier-owned questions in Advanced modifiers.")
    before = phase == TaskPhase.PRE_CONDITION
    if before:
        validate_simple_pre_questionnaire(project, module)
    else:
        if not module.simple_post_questions:
            raise ValueError("Keep existing custom tasks in Advanced custom tasks.")
        validate_simple_post_questionnaire(module)
    if (len(module.steps) != 1 or module.steps[0].timeout_seconds is not None
            or module.steps[0].duration_seconds is not None
            or any(option.image_path is not None for question in module.steps[0].questions
                   for option in question.options)):
        raise ValueError("Keep timed, image or multiple-screen questions in Advanced custom tasks.")
    if any(binding.occurrence != TaskOccurrence.EVERY_ENTRY
           for condition in project.conditions
           for binding in (condition.pre_task_bindings if before else condition.post_task_bindings)
           if binding.task_id == module.task_id):
        raise ValueError("Keep special question occurrence rules in Advanced custom tasks.")


class PostQuestionsDialog(QDialog):
    """Keep question edits, assignment and private/shared scope in one detached draft."""

    def __init__(
        self, project: ProjectFile, *, project_root: Path, condition_id: str,
        task_id: str | None = None, phase: TaskPhase = TaskPhase.POST_CONDITION,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._phase = phase
        before = phase == TaskPhase.PRE_CONDITION
        self._timing = "Before" if before else "After"
        self.setObjectName("pre_condition_questions_dialog" if before
                           else "post_condition_questions_dialog")
        self.setWindowTitle(f"{self._timing}-condition Questions")
        self.setMinimumSize(1000, 680)
        self.resize(1060, 740)
        self._project = project.model_copy(deep=True)
        self._project_root = project_root
        self._condition_id = condition_id
        self.project_result: ProjectFile | None = None
        self.affected_condition_ids: set[str] = set()
        existing = next((task for task in project.task_modules if task.task_id == task_id), None)
        self._existing = existing is not None
        factory = make_pre_questionnaire if before else make_post_questionnaire
        self._module = existing or factory(
            [make_yes_no_question("Question")], name=f"{self._timing}-condition Questions",
        )
        self._validate_module(self._module)
        step = self._module.steps[0]
        self._using_ids = [condition.condition_id for condition in project.conditions
                           if any(binding.task_id == self._module.task_id
                                  for binding in (condition.pre_task_bindings if before
                                                  else condition.post_task_bindings))]
        self._selected_ids = [condition_id]
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        header = DialogHeader(self.windowTitle(), "", parent=self)
        header.subtitle_label.hide()
        header.title_label.setToolTip(
            f"{self._timing} every presentation of the selected conditions.",
        )
        layout.addWidget(header)
        top = QHBoxLayout()
        self.name_edit = QLineEdit(self._module.name, self)
        self.name_edit.setAccessibleName("Question set name")
        top.addWidget(self.name_edit, 1)
        self.scope_button = QPushButton("Choose conditions...", self)
        self.scope_button.clicked.connect(self._choose_conditions)
        mark_secondary_action(self.scope_button)
        top.addWidget(self.scope_button)
        layout.addLayout(top)
        self.shared_checkbox = QCheckBox("Edit the shared questions", self)
        self.shared_checkbox.setToolTip(
            "Unchecked edits create a private copy when other conditions share these questions.",
        )
        self.shared_checkbox.setVisible(len(self._using_ids) > 1)
        self.shared_checkbox.toggled.connect(self._shared_changed)
        layout.addWidget(self.shared_checkbox)
        self.scope_label = _label("", self)
        layout.addWidget(self.scope_label)
        self.editor = QuestionnaireEditor(self, simple=True)
        self.editor.set_questions(_step_to_draft(step).questions)
        if not self._existing:
            self.editor.question_prompt_edit.setPlainText("")
        self._original_questions = {question.question_id: question for question in step.questions}
        self._original_drafts = {draft.question_id: draft for draft in self.editor.questions()}
        layout.addWidget(self.editor, 1)
        self.status = _label("", self)
        self.status.setObjectName("post_question_status")
        self.status.hide()
        layout.addWidget(self.status)
        footer = QHBoxLayout()
        self.preview_button = QPushButton("Preview", self)
        self.preview_button.clicked.connect(self._preview)
        mark_secondary_action(self.preview_button)
        footer.addWidget(self.preview_button)
        self.remove_button = QPushButton("Remove from selected conditions", self)
        self.remove_button.setVisible(self._existing)
        self.remove_button.clicked.connect(self._remove)
        mark_destructive_action(self.remove_button)
        footer.addWidget(self.remove_button)
        footer.addStretch(1)
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.reject)
        mark_secondary_action(self.cancel_button)
        footer.addWidget(self.cancel_button)
        self.apply_button = QPushButton("Apply questions", self)
        self.apply_button.setToolTip(
            "Required, self-paced and unscored by default. Continue submits an answer.",
        )
        self.apply_button.clicked.connect(self.accept)
        mark_primary_action(self.apply_button)
        footer.addWidget(self.apply_button)
        layout.addLayout(footer)
        apply_dialog_theme(self)
        self._refresh_scope()
        self.editor.question_prompt_edit.setFocus()

    def _validate_module(self, module: TaskModule) -> None:
        validate_question_editor_module(self._project, module, self._phase)

    def add_question(self) -> None:
        """Start another blank Yes/No question when opened from the Add action."""
        self.editor.add_kind_combo.setCurrentIndex(0)
        self.editor.add_button.click()
        self.editor.question_prompt_edit.setFocus()

    def _shared_changed(self, checked: bool) -> None:
        self._selected_ids = self._using_ids[:] if checked else [self._condition_id]
        self._refresh_scope()

    def _refresh_scope(self) -> None:
        names = [condition.name for condition in self._project.conditions
                 if condition.condition_id in self._selected_ids]
        target = names[0] if len(names) == 1 else f"{len(names)} selected conditions"
        self.scope_label.setText(
            f"{self._timing} each presentation of {target}. Shared questions."
            if self.shared_checkbox.isChecked() else
            f"{self._timing} each presentation of {target}.",
        )
        self.scope_label.setToolTip("\n".join(
            condition.name for condition in self._project.conditions
            if condition.condition_id in self._selected_ids
        ))

    def _choose_conditions(self) -> None:
        dialog = ModifierScopeDialog(
            self._project, selected_ids=self._selected_ids, conflicts={},
            description=f"Questions run {self._timing.lower()} every presentation "
                        "of the selected conditions.",
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._selected_ids = dialog.condition_ids
            self._refresh_scope()

    def _candidate(self) -> TaskModule:
        drafts = self.editor.questions()
        if not drafts:
            raise ValueError("Add at least one question.")
        for index, draft in enumerate(drafts, 1):
            if not draft.prompt.strip():
                raise ValueError(f"Question {index} needs question text.")
            if any(not option.label.strip() for option in draft.options):
                raise ValueError(f"Question {index} needs text for every answer.")
        questions = [
            self._original_questions[draft.question_id].model_copy(deep=True)
            if self._existing and draft == self._original_drafts.get(draft.question_id)
            else _question_from_draft(draft)
            for draft in drafts
        ]
        step = self._module.steps[0].model_copy(update={"questions": questions}, deep=True)
        module = TaskModule.model_validate({
            **self._module.model_dump(), "name": self.name_edit.text(), "steps": [step],
        })
        self._validate_module(module)
        return module

    def _show_error(self, error: ValueError) -> None:
        self.status.setText(str(error))
        self.status.setToolTip(str(error))
        mark_error_text(self.status)
        self.status.show()

    def _preview(self) -> None:
        try:
            module = self._candidate()
        except ValueError as error:
            self._show_error(error)
            return
        self.status.clear()
        self.status.setToolTip("")
        self.status.hide()
        PostQuestionPreview(module.steps[0].questions, self).exec()

    def _remove(self) -> None:
        try:
            remove = (remove_pre_questionnaire if self._phase == TaskPhase.PRE_CONDITION
                      else remove_post_questionnaire)
            self.project_result = remove(
                self._project, self._module.task_id, self._selected_ids,
            )
            self.affected_condition_ids = set(self._selected_ids)
        except ValueError as error:
            self._show_error(error)
            return
        super().accept()

    def accept(self) -> None:
        try:
            candidate = self._candidate()
            selected, using = set(self._selected_ids), set(self._using_ids)
            if (self._existing and selected and candidate == self._module
                    and (selected == using if self.shared_checkbox.isChecked()
                         else selected <= using)):
                self.project_result = self._project.model_copy(deep=True)
                super().accept()
                return
            apply = (apply_pre_questionnaire if self._phase == TaskPhase.PRE_CONDITION
                     else apply_post_questionnaire)
            self.project_result = apply(
                self._project, candidate, self._selected_ids,
                scope="shared" if self.shared_checkbox.isChecked() else "private",
            )
            self.affected_condition_ids = set(self._selected_ids)
            if self.shared_checkbox.isChecked():
                self.affected_condition_ids.update(self._using_ids)
        except ValueError as error:
            self._show_error(error)
            return
        super().accept()
