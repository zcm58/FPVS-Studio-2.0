"""Registered simple-question authoring, scope, preview and output-action checks."""

from __future__ import annotations

import pytest
from PIL import Image
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton
from tests.gui.helpers import assert_visible_children_within_parent
from tests.gui.test_condition_modifier_dialog import _document

from fpvs_studio.core.compiler_tasks import compile_condition_tasks
from fpvs_studio.core.condition_modifiers import assign_modifier, create_backward_counting_modifier
from fpvs_studio.core.post_questions import (
    apply_post_questionnaire,
    apply_pre_questionnaire,
    make_post_questionnaire,
    make_pre_questionnaire,
    make_yes_no_question,
)
from fpvs_studio.core.task_models import (
    TaskBinding,
    TaskModule,
    TaskOccurrence,
    TaskPhase,
    TaskQuestion,
    TaskQuestionKind,
    TaskStep,
    TaskStepKind,
    TaskSubmissionMode,
)
from fpvs_studio.gui.condition_modifier_dialog import (
    _PRE_QUESTIONS_KEY,
    _QUESTIONS_KEY,
    ConditionModifierDialog,
    condition_modifier_summary,
)
from fpvs_studio.gui.condition_task_dialog import _module_from_draft, _module_to_draft
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.post_questions_dialog import PostQuestionPreview, PostQuestionsDialog
from fpvs_studio.runtime.post_condition_responses import POST_CONDITION_RESPONSES_FILENAME


class _ManualTask(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, **kwargs):
        super().__init__(kwargs["parent_widget"])
        self.callback = kwargs["callback"]

    def start(self):
        pass

    def complete(self):
        try:
            value = self.callback()
        except Exception as error:
            self.failed.emit(error)
        else:
            self.succeeded.emit(value)
        self.finished.emit()


class _ImmediateTask(_ManualTask):
    def start(self):
        self.complete()


def _questionnaire(phase=TaskPhase.POST_CONDITION):
    make = make_pre_questionnaire if phase == TaskPhase.PRE_CONDITION else make_post_questionnaire
    return make(
        [
            make_yes_no_question("Did you see a fearful face?", question_id="fearful-face"),
        ]
    )


def _shared_document(tmp_path, phase=TaskPhase.POST_CONDITION):
    document, first, second = _document(tmp_path)
    counting = create_backward_counting_modifier()
    project = assign_modifier(document.project, counting, [first, second])
    module = _questionnaire(phase)
    apply = (apply_pre_questionnaire if phase == TaskPhase.PRE_CONDITION
             else apply_post_questionnaire)
    project = apply(project, module, [first, second])
    document.apply_condition_modifier_project(project)
    return document, first, second, module, counting


def _fit(dialog):
    QApplication.processEvents()
    assert_visible_children_within_parent(dialog)
    for label in dialog.findChildren(QLabel):
        if label.isVisible() and label.text():
            if label.wordWrap():
                assert label.height() >= label.heightForWidth(label.width()), label.text()
            else:
                assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())
    for button in dialog.findChildren(QPushButton):
        if button.isVisible() and button.text():
            assert button.width() >= button.fontMetrics().horizontalAdvance(button.text()) + 16, (
                button.text()
            )


@pytest.mark.parametrize("phase", [TaskPhase.PRE_CONDITION, TaskPhase.POST_CONDITION])
def test_default_questions_use_natural_yes_no_and_apply_without_io(qtbot, tmp_path, phase):
    document, first, _second = _document(tmp_path)
    before = document.project.model_copy(deep=True)
    dialog = PostQuestionsDialog(
        document.project, project_root=document.project_root, condition_id=first, phase=phase,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    editor = dialog.editor
    assert dialog._selected_ids == [first]
    assert editor.add_kind_combo.currentData() == "yes_no"
    assert not editor.options_edit.isVisible()
    assert not editor.question_tabs.isTabVisible(2)
    assert editor.natural_options is not None
    assert [editor.natural_options.table.item(row, 0).text() for row in range(2)] == ["Yes", "No"]
    assert editor.required_checkbox.isChecked()
    assert not editor.natural_options.scoring_checkbox.isChecked()
    dialog.accept()
    assert dialog.project_result is None
    assert "question text" in dialog.status.text()
    editor.question_prompt_edit.setPlainText("Did you see a fearful face?")
    candidate = dialog._candidate()
    step = candidate.steps[0]
    assert candidate.simple_post_questions == (phase == TaskPhase.POST_CONDITION)
    assert step.submission_mode == TaskSubmissionMode.EXPLICIT
    assert step.submit_label == "Continue"
    assert step.timeout_seconds is None and step.duration_seconds is None
    assert all(
        option.correct is None and option.score is None for option in step.questions[0].options
    )
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert document.project == before
    condition = next(
        item for item in dialog.project_result.conditions if item.condition_id == first
    )
    assert len(condition.pre_task_bindings) == int(phase == TaskPhase.PRE_CONDITION)
    assert len(condition.post_task_bindings) == int(phase == TaskPhase.POST_CONDITION)
    other = next(item for item in dialog.project_result.conditions if item.condition_id != first)
    assert not other.pre_task_bindings and not other.post_task_bindings
    assert not (document.project_root / POST_CONDITION_RESPONSES_FILENAME).exists()


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("phase", [TaskPhase.PRE_CONDITION, TaskPhase.POST_CONDITION])
def test_private_and_explicit_shared_edits_preserve_other_activities(
    qtbot, tmp_path, shared, phase,
):
    document, first, second, module, counting = _shared_document(tmp_path, phase)
    before = document.project.model_copy(deep=True)
    dialog = PostQuestionsDialog(
        document.project,
        project_root=document.project_root,
        condition_id=first,
        task_id=module.task_id,
        phase=phase,
    )
    qtbot.addWidget(dialog)
    if shared:
        dialog.shared_checkbox.setChecked(True)
    dialog.editor.question_prompt_edit.setPlainText("Did you see an angry face?")
    dialog.accept()
    candidate = dialog.project_result
    assert candidate is not None
    conditions = {condition.condition_id: condition for condition in candidate.conditions}
    field = "pre_task_bindings" if phase == TaskPhase.PRE_CONDITION else "post_task_bindings"
    opposite = "post_task_bindings" if phase == TaskPhase.PRE_CONDITION else "pre_task_bindings"
    owned = {task.task_id for task in counting.task_modules}
    first_id = next(binding.task_id for binding in getattr(conditions[first], field)
                    if binding.task_id not in owned)
    second_id = next(binding.task_id for binding in getattr(conditions[second], field)
                     if binding.task_id not in owned)
    assert (first_id == second_id) == shared
    assert conditions[first].post_task_bindings[0].task_id == counting.modifier.post_task_ids[0]
    assert conditions[second].post_task_bindings[0] == before.conditions[1].post_task_bindings[0]
    for condition, original in zip(candidate.conditions, before.conditions, strict=True):
        assert getattr(condition, opposite) == getattr(original, opposite)
        assert [binding for binding in getattr(condition, field) if binding.task_id in owned] == [
            binding for binding in getattr(original, field) if binding.task_id in owned
        ]
    tasks = {task.task_id: task for task in candidate.task_modules}
    assert all(tasks[task.task_id] == task for task in counting.task_modules)
    assert tasks[first_id].steps[0].questions[0].question_id == "fearful-face"
    assert tasks[second_id].steps[0].questions[0].prompt == (
        "Did you see an angry face?" if shared else "Did you see a fearful face?"
    )
    assert candidate.settings.session == before.settings.session
    assert document.project == before


@pytest.mark.parametrize("phase", [TaskPhase.PRE_CONDITION, TaskPhase.POST_CONDITION])
def test_unchanged_apply_keeps_shared_identity_and_cancel_preserves_source(qtbot, tmp_path, phase):
    document, first, _second, module, _counting = _shared_document(tmp_path, phase)
    before = document.project.model_copy(deep=True)
    dialog = PostQuestionsDialog(
        document.project,
        project_root=document.project_root,
        condition_id=first,
        task_id=module.task_id,
        phase=phase,
    )
    qtbot.addWidget(dialog)
    dialog.accept()
    assert dialog.project_result == before
    cancelled = PostQuestionsDialog(
        document.project,
        project_root=document.project_root,
        condition_id=first,
        task_id=module.task_id,
        phase=phase,
    )
    qtbot.addWidget(cancelled)
    cancelled.editor.question_prompt_edit.setPlainText("Discard this draft")
    cancelled.reject()
    assert cancelled.project_result is None
    assert document.project == before


@pytest.mark.parametrize("phase", [TaskPhase.PRE_CONDITION, TaskPhase.POST_CONDITION])
def test_question_scope_explicitly_assigns_selected_conditions_in_the_chosen_phase(
    qtbot, tmp_path, monkeypatch, phase,
):
    document, first, second = _document(tmp_path)
    descriptions = []

    class SelectedConditions:
        condition_ids = [first, second]

        def __init__(self, _project, *, selected_ids, description, **_kwargs):
            assert selected_ids == [first]
            descriptions.append(description)

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "fpvs_studio.gui.post_questions_dialog.ModifierScopeDialog", SelectedConditions,
    )
    dialog = PostQuestionsDialog(
        document.project, project_root=document.project_root, condition_id=first, phase=phase,
    )
    qtbot.addWidget(dialog)
    assert dialog._selected_ids == [first]
    dialog.scope_button.click()
    assert dialog._selected_ids == [first, second]
    timing = "before" if phase == TaskPhase.PRE_CONDITION else "after"
    assert timing in descriptions[0]
    dialog.editor.question_prompt_edit.setPlainText("Are you ready for this condition?")
    before = document.project.model_copy(deep=True)
    dialog.accept()
    assert document.project == before
    field = "pre_task_bindings" if phase == TaskPhase.PRE_CONDITION else "post_task_bindings"
    opposite = "post_task_bindings" if phase == TaskPhase.PRE_CONDITION else "pre_task_bindings"
    bindings = [getattr(condition, field) for condition in dialog.project_result.conditions]
    assert all(len(assigned) == 1 for assigned in bindings)
    assert bindings[0][0].task_id == bindings[1][0].task_id
    assert all(not getattr(condition, opposite) for condition in dialog.project_result.conditions)


@pytest.mark.parametrize("phase", [TaskPhase.PRE_CONDITION, TaskPhase.POST_CONDITION])
def test_modifier_add_appends_one_blank_question_while_edit_keeps_existing_questions(
    qtbot, tmp_path, monkeypatch, phase,
):
    document, first, _second, module, _counting = _shared_document(tmp_path, phase)
    before = document.project.model_copy(deep=True)
    observed = []

    def inspect_and_cancel(child):
        questions = child.editor.questions()
        observed.append((child._phase, len(questions)))
        assert questions[0].question_id == module.steps[0].questions[0].question_id
        assert questions[0].prompt == "Did you see a fearful face?"
        if len(observed) == 1:
            assert len(questions) == 2
            assert not questions[-1].prompt
            assert [option.label for option in questions[-1].options] == ["Yes", "No"]
        else:
            assert len(questions) == 1
        child.reject()
        return child.result()

    monkeypatch.setattr(PostQuestionsDialog, "exec", inspect_and_cancel)
    dialog = ConditionModifierDialog(document, condition_id=first)
    qtbot.addWidget(dialog)
    dialog.show()
    button = (dialog.before_questions_button if phase == TaskPhase.PRE_CONDITION
              else dialog.questions_button)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    key = _PRE_QUESTIONS_KEY if phase == TaskPhase.PRE_CONDITION else _QUESTIONS_KEY
    item = next(dialog.modifier_list.item(row) for row in range(dialog.modifier_list.count())
                if dialog.modifier_list.item(row).data(Qt.ItemDataRole.UserRole) == key)
    dialog.modifier_list.setCurrentItem(item)
    assert dialog.edit_questions_button.isVisible()
    qtbot.mouseClick(dialog.edit_questions_button, Qt.MouseButton.LeftButton)
    assert observed == [(phase, 2), (phase, 1)]
    assert document.project == before
    assert dialog._build_project() == before


@pytest.mark.parametrize("special", ["occurrence", "start_gate"])
def test_special_before_question_bindings_stay_in_advanced_without_flattening(
    qtbot, tmp_path, special,
):
    document, first, _second = _document(tmp_path)
    module = _questionnaire(TaskPhase.PRE_CONDITION)
    project = apply_pre_questionnaire(document.project, module, [first])
    binding = project.conditions[0].pre_task_bindings[0]
    if special == "occurrence":
        binding.occurrence = TaskOccurrence.FIRST_OCCURRENCE
    else:
        binding.replaces_condition_start_gate = True
    before = project.model_copy(deep=True)
    with pytest.raises(ValueError, match="Advanced"):
        PostQuestionsDialog(
            project, project_root=document.project_root, condition_id=first,
            task_id=module.task_id, phase=TaskPhase.PRE_CONDITION,
        )
    document.apply_condition_modifier_project(project)
    dialog = ConditionModifierDialog(document, condition_id=first)
    qtbot.addWidget(dialog)
    assert dialog._question_tasks(TaskPhase.PRE_CONDITION) == []
    assert dialog._build_project() == before
    dialog.reject()
    assert document.project == before


def test_multiple_response_types_and_natural_option_edits_preserve_ids(qtbot, tmp_path):
    document, first, _second = _document(tmp_path)
    dialog = PostQuestionsDialog(
        document.project, project_root=document.project_root, condition_id=first
    )
    qtbot.addWidget(dialog)
    editor = dialog.editor
    editor.question_prompt_edit.setPlainText("First question")
    original_id = editor.questions()[0].options[1].option_id
    editor.natural_options.table.item(1, 0).setText('No, I did not see "fear" — 不确定')
    assert editor.questions()[0].options[1].option_id == original_id
    assert "不确定" in editor.natural_options.table.item(1, 0).toolTip()
    for kind in ("multiple_choice", "short_text", "long_text", "numeric", "rating"):
        editor.add_kind_combo.setCurrentIndex(editor.add_kind_combo.findData(kind))
        editor.add_button.click()
        editor.question_prompt_edit.setPlainText(f"Question for {kind}")
    assert len(editor.questions()) == 6
    final_id = editor.questions()[-1].question_id
    editor.up_button.click()
    assert editor.questions()[-2].question_id == final_id
    candidate = dialog._candidate()
    assert {question.kind for question in candidate.steps[0].questions} == set(TaskQuestionKind)
    assert candidate.steps[0].questions[0].options[1].option_id == original_id


def test_preview_requires_deliberate_continue_and_no_is_a_valid_answer(qtbot, tmp_path):
    question = make_yes_no_question("Did you see a fearful face?")
    preview = PostQuestionPreview([question])
    qtbot.addWidget(preview)
    preview.show()
    assert not preview.continue_button.isEnabled()
    preview.choice_buttons["yes"].click()
    assert preview.continue_button.isEnabled()
    assert not preview.answers
    preview.choice_buttons["no"].click()
    assert not preview.answers
    assert preview._index == 0
    preview.continue_button.click()
    assert preview.answers[0].selected_option_ids == ["no"]
    assert "No responses were saved" in preview.prompt.text()
    assert not list(tmp_path.rglob("*.csv"))


@pytest.mark.parametrize("kind", [TaskQuestionKind.NUMERIC, TaskQuestionKind.RATING])
def test_preview_zero_is_not_missing(qtbot, kind):
    question = TaskQuestion(
        question_id="zero-answer",
        kind=kind,
        prompt="Choose zero",
        min_value=0,
        max_value=2,
        step=1,
    )
    preview = PostQuestionPreview([question])
    qtbot.addWidget(preview)
    if kind == TaskQuestionKind.NUMERIC:
        preview.text_edit.setText("0")
    else:
        preview.rating_combo.setCurrentIndex(preview.rating_combo.findData(0))
    assert preview.continue_button.isEnabled()
    preview.continue_button.click()
    assert preview.answers[0].numeric_value == 0


def test_preview_preserves_ampersands_and_rating_endpoint_labels(qtbot):
    question = make_yes_no_question("Did you see R&D?")
    question.options[0].label = "R&D"
    preview = PostQuestionPreview([question])
    qtbot.addWidget(preview)
    assert preview.choice_buttons["yes"].findChild(QLabel).text() == "R&D"
    assert preview.choice_buttons["yes"].accessibleName() == "R&D"
    assert preview.choice_buttons["yes"].toolTip() == "R&D"
    rating = TaskQuestion(
        question_id="rating",
        kind=TaskQuestionKind.RATING,
        prompt="How clear?",
        min_value=0,
        max_value=0.3,
        step=0.1,
        min_label="Not at all",
        max_label="Very clear",
    )
    scale = PostQuestionPreview([rating])
    qtbot.addWidget(scale)
    assert scale.rating_combo.itemText(scale.rating_combo.findData(0)) == "0 — Not at all"
    assert scale.rating_combo.itemText(scale.rating_combo.findData(0.3)) == "0.3 — Very clear"
    scale.rating_combo.setCurrentIndex(scale.rating_combo.findData(0.3))
    assert scale.continue_button.isEnabled()


@pytest.mark.parametrize("kind", [TaskQuestionKind.NUMERIC, TaskQuestionKind.RATING])
def test_simple_edits_preserve_unspecified_numeric_increment(qtbot, tmp_path, kind):
    document, first, _second = _document(tmp_path)
    module = make_post_questionnaire(
        [
            TaskQuestion(
                question_id="number",
                kind=kind,
                prompt="Original prompt",
                min_value=0,
                max_value=2,
            )
        ]
    )
    project = apply_post_questionnaire(document.project, module, [first])
    dialog = PostQuestionsDialog(
        project,
        project_root=document.project_root,
        condition_id=first,
        task_id=module.task_id,
    )
    qtbot.addWidget(dialog)
    dialog.editor.question_prompt_edit.setPlainText("Revised prompt")
    assert dialog._candidate().steps[0].questions[0].step is None


def test_unchanged_question_keeps_exact_source_text_when_another_question_is_edited(
    qtbot, tmp_path
):
    document, first, _second = _document(tmp_path)
    original = make_yes_no_question("Original line\r\nSecond line", question_id="original")
    module = make_post_questionnaire(
        [original, make_yes_no_question("Edit this", question_id="edit")]
    )
    project = apply_post_questionnaire(document.project, module, [first])
    dialog = PostQuestionsDialog(
        project,
        project_root=document.project_root,
        condition_id=first,
        task_id=module.task_id,
    )
    qtbot.addWidget(dialog)
    dialog.editor.question_list.setCurrentRow(1)
    dialog.editor.question_prompt_edit.setPlainText("Changed")
    assert dialog._candidate().steps[0].questions[0] == original


def test_advanced_custom_tasks_keep_marker_and_are_not_flattened(qtbot, tmp_path):
    document, first, _second = _document(tmp_path)
    module = _questionnaire()
    assert (
        _module_from_draft(_module_to_draft(module, TaskBinding(task_id=module.task_id))) == module
    )
    complex_module = module.model_copy(deep=True)
    complex_module.steps[0].repeat_count = 2
    project = document.project.model_copy(update={"task_modules": [complex_module]})
    with pytest.raises(ValueError, match="[Aa]dvanced"):
        PostQuestionsDialog(
            project, project_root=document.project_root, condition_id=first, task_id=module.task_id
        )
    legacy = TaskModule(
        task_id="legacy",
        name="Legacy questions",
        steps=[
            TaskStep(
                step_id="legacy-step",
                kind=TaskStepKind.QUESTIONNAIRE,
                questions=[make_yes_no_question("Keep legacy")],
            )
        ],
    )
    project = document.project.model_copy(update={"task_modules": [legacy]})
    with pytest.raises(ValueError, match="Advanced"):
        PostQuestionsDialog(
            project, project_root=document.project_root, condition_id=first, task_id=legacy.task_id
        )


@pytest.mark.parametrize("complexity", ["timed", "two_screens", "image", "owned"])
def test_add_after_question_preserves_unsupported_marked_tasks_and_starts_a_new_set(
    qtbot, tmp_path, monkeypatch, complexity,
):
    if complexity == "owned":
        document, first, _second, module, counting = _shared_document(tmp_path)
        owner = next(item for item in document.project.condition_modifiers
                     if item.modifier_id == counting.modifier.modifier_id)
        owner.post_task_ids.append(module.task_id)
    else:
        document, first, _second = _document(tmp_path)
        module = _questionnaire()
    if complexity == "timed":
        module.steps[0].timeout_seconds = 5
    elif complexity == "two_screens":
        module.steps.append(module.steps[0].model_copy(
            update={
                "step_id": "second-screen",
                "questions": [make_yes_no_question(
                    "Second advanced question", question_id="second-advanced-question",
                )],
            },
            deep=True,
        ))
    elif complexity == "image":
        relative = f"stimuli/task-assets/{module.task_id}/answer.png"
        image_path = document.project_root / relative
        image_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (16, 16), "white").save(image_path)
        module.steps[0].questions[0].options[0].image_path = relative
    project = (type(document.project).model_validate(document.project.model_dump())
               if complexity == "owned" else
               apply_post_questionnaire(document.project, module, [first]))
    document.apply_condition_modifier_project(project)
    before = document.project.model_copy(deep=True)
    opened = []

    def accept_new_questions(child):
        assert not child._existing
        assert child._phase == TaskPhase.POST_CONDITION
        assert len(child.editor.questions()) == 1
        assert not child.editor.question_prompt_edit.toPlainText()
        child.editor.question_prompt_edit.setPlainText("A new simple after-condition question")
        child.accept()
        return child.result()

    def question_dialog(*args, **kwargs):
        opened.append((kwargs["task_id"], kwargs["phase"]))
        return PostQuestionsDialog(*args, **kwargs)

    monkeypatch.setattr(PostQuestionsDialog, "exec", accept_new_questions)
    monkeypatch.setattr(
        "fpvs_studio.gui.condition_modifier_dialog.PostQuestionsDialog", question_dialog,
    )
    monkeypatch.setattr("fpvs_studio.gui.condition_modifier_dialog.BackgroundTask", _ImmediateTask)
    dialog = ConditionModifierDialog(document, condition_id=first)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog._question_tasks(TaskPhase.POST_CONDITION) == []
    qtbot.mouseClick(dialog.questions_button, Qt.MouseButton.LeftButton)
    assert opened == [(None, TaskPhase.POST_CONDITION)]
    assert document.project == before
    candidate = dialog._build_project()
    assert candidate.condition_modifiers == before.condition_modifiers
    assert candidate.conditions[1:] == before.conditions[1:]
    bindings = next(condition for condition in candidate.conditions
                    if condition.condition_id == first).post_task_bindings
    original_bindings = before.conditions[0].post_task_bindings
    assert len(bindings) == len(original_bindings) + 1
    assert bindings[:-1] == original_bindings
    assert bindings[-1].task_id != module.task_id
    modules = {task.task_id: task for task in candidate.task_modules}
    assert modules[module.task_id] == module
    assert modules[bindings[-1].task_id].simple_post_questions
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted, dialog.status.toolTip()
    assert document.get_condition(first).post_task_bindings == bindings
    assert next(task for task in document.project.task_modules
                if task.task_id == module.task_id) == module


@pytest.mark.parametrize("action", ["cancel", "apply"])
@pytest.mark.parametrize("phase", [TaskPhase.PRE_CONDITION, TaskPhase.POST_CONDITION])
def test_modifier_question_draft_applies_once_and_save_reopens_without_response_file(
    qtbot,
    monkeypatch,
    tmp_path,
    action,
    phase,
):
    document, first, _second = _document(tmp_path)
    before = document.project.model_copy(deep=True)
    opened = []

    def accept_questions(child):
        opened.append(child)
        assert child._phase == phase
        assert child._selected_ids == [first]
        assert len(child.editor.questions()) == 1
        assert not child.editor.question_prompt_edit.toPlainText()
        child.editor.question_prompt_edit.setPlainText("Did you see a fearful face?")
        child.accept()
        return child.result()

    monkeypatch.setattr(PostQuestionsDialog, "exec", accept_questions)
    monkeypatch.setattr("fpvs_studio.gui.condition_modifier_dialog.BackgroundTask", _ImmediateTask)
    dialog = ConditionModifierDialog(document, condition_id=first)
    qtbot.addWidget(dialog)
    button = (dialog.before_questions_button if phase == TaskPhase.PRE_CONDITION
              else dialog.questions_button)
    button.click()
    assert len(opened) == 1
    assert document.project == before
    assert dialog._selected_questions
    assert dialog._question_phase == phase
    timing = "Before" if phase == TaskPhase.PRE_CONDITION else "After"
    assert timing.lower() in dialog.question_flow_label.text().lower()
    if action == "cancel":
        dialog.reject()
        assert document.project == before
    else:
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert f"{timing}-condition Questions" in condition_modifier_summary(document, first)
        document.save()
        reopened = ProjectDocument.open_existing(document.project_root)
        field = "pre_task_bindings" if phase == TaskPhase.PRE_CONDITION else "post_task_bindings"
        condition = reopened.get_condition(first)
        assert len(getattr(condition, field)) == 1
        module = next(task for task in reopened.project.task_modules
                      if task.task_id == getattr(condition, field)[0].task_id)
        assert module.simple_post_questions == (phase == TaskPhase.POST_CONDITION)
        assert reopened.project == document.project
    assert not (document.project_root / POST_CONDITION_RESPONSES_FILENAME).exists()


def test_multiple_before_and_after_questions_keep_independent_authored_order_after_reload(
    qtbot, tmp_path, monkeypatch,
):
    document, first, second = _document(tmp_path)
    before = document.project.model_copy(deep=True)
    phases = (TaskPhase.PRE_CONDITION, TaskPhase.POST_CONDITION)
    added_ids = {phase: [] for phase in phases}
    expected_ids = {phase: [] for phase in phases}

    def author_questions(child):
        phase = child._phase
        editor = child.editor
        child.show()
        QApplication.processEvents()
        questions = editor.questions()
        assert [question.question_id for question in questions[:-1]] == expected_ids[phase]
        assert not questions[-1].prompt
        added_ids[phase].append(questions[-1].question_id)
        number = len(added_ids[phase])
        editor.question_prompt_edit.setPlainText(f"{phase.value} question {number}")
        expected_ids[phase] = list(added_ids[phase])
        if number == 3:
            if phase == TaskPhase.PRE_CONDITION:
                editor.question_list.setCurrentRow(2)
                moves = (editor.up_button, editor.up_button, editor.down_button, editor.up_button)
                expected_ids[phase] = [added_ids[phase][index] for index in (2, 0, 1)]
            else:
                editor.question_list.setCurrentRow(0)
                moves = (editor.down_button, editor.down_button,
                         editor.up_button, editor.down_button)
                expected_ids[phase] = [added_ids[phase][index] for index in (1, 2, 0)]
            for button in moves:
                assert button.isVisible() and button.isEnabled()
                qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        candidate = child._candidate()
        assert [question.question_id for question in candidate.steps[0].questions] == (
            expected_ids[phase]
        )
        qtbot.mouseClick(child.apply_button, Qt.MouseButton.LeftButton)
        assert child.result() == QDialog.DialogCode.Accepted, child.status.text()
        return child.result()

    monkeypatch.setattr(PostQuestionsDialog, "exec", author_questions)
    monkeypatch.setattr("fpvs_studio.gui.condition_modifier_dialog.BackgroundTask", _ImmediateTask)
    dialog = ConditionModifierDialog(document, condition_id=first)
    qtbot.addWidget(dialog)
    dialog.show()
    for phase in phases:
        button = (dialog.before_questions_button if phase == TaskPhase.PRE_CONDITION
                  else dialog.questions_button)
        other = (TaskPhase.POST_CONDITION if phase == TaskPhase.PRE_CONDITION
                 else TaskPhase.PRE_CONDITION)
        for _ in range(3):
            other_questions = [
                module.model_copy(deep=True) for module in dialog._question_tasks(other)
            ]
            qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
            assert dialog._question_tasks(other) == other_questions
            assert document.project == before
            assert not dialog.advanced_toggle.isChecked()
    qtbot.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Accepted, dialog.status.toolTip()
    document.save()
    reopened = ProjectDocument.open_existing(document.project_root)
    assert reopened.project == document.project
    assert reopened.get_condition(second) == before.conditions[1]
    condition = reopened.get_condition(first)
    for phase in phases:
        compiled = compile_condition_tasks(
            reopened.project, condition, phase=phase, block_index=0, block_count=1,
            session_seed=77, run_id="ordered-questions", project_root=reopened.project_root,
        )
        assert len(compiled) == 1
        assert [question.question_id for question in compiled[0].steps[0].questions] == (
            expected_ids[phase]
        )
        numbers = (3, 1, 2) if phase == TaskPhase.PRE_CONDITION else (2, 3, 1)
        assert [question.prompt for question in compiled[0].steps[0].questions] == [
            f"{phase.value} question {number}" for number in numbers
        ]


def test_response_actions_use_active_project_and_rebuild_in_worker(
    qtbot,
    monkeypatch,
    tmp_path,
):
    document, first, _second = _document(tmp_path)
    opened, rebuilt = [], []
    monkeypatch.setattr(
        "fpvs_studio.gui.condition_modifier_dialog.open_folder",
        lambda path: opened.append(path) or True,
    )
    monkeypatch.setattr("fpvs_studio.gui.condition_modifier_dialog.BackgroundTask", _ManualTask)
    monkeypatch.setattr(
        "fpvs_studio.gui.condition_modifier_dialog.rebuild_post_condition_responses",
        lambda root: rebuilt.append(root) or None,
    )
    dialog = ConditionModifierDialog(
        document, condition_id=first, fpvs_root=tmp_path / "other-root"
    )
    qtbot.addWidget(dialog)
    dialog.advanced_toggle.setChecked(True)
    assert str(document.project_root) in dialog.responses_label.toolTip()
    dialog.open_responses_button.click()
    assert opened == [document.project_root]
    dialog.rebuild_responses_button.click()
    assert not rebuilt
    assert dialog._active_task is not None
    assert not dialog.apply_button.isEnabled()
    dialog._active_task.complete()
    assert rebuilt == [document.project_root]
    assert dialog._active_task is None
    assert "No saved question responses" in dialog.status.text()
    assert not (document.project_root / POST_CONDITION_RESPONSES_FILENAME).exists()

    def locked(_root):
        raise PermissionError("The file is open in Excel.")

    monkeypatch.setattr(
        "fpvs_studio.gui.condition_modifier_dialog.rebuild_post_condition_responses", locked
    )
    dialog.rebuild_responses_button.click()
    dialog._active_task.complete()
    assert (
        "Close post_condition_responses.csv in Excel, then rebuild responses."
        in dialog.status.toolTip()
    )
    assert dialog.apply_button.isEnabled()


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("size", [(1100, 720), (1120, 760)])
@pytest.mark.parametrize("state", ["empty", "before", "shared", "advanced", "busy", "error"])
def test_simplified_modifier_common_actions_and_output_summary_fit(
    qtbot,
    monkeypatch,
    tmp_path,
    dark,
    size,
    state,
):
    document, first, _second = _document(tmp_path)
    if state == "shared":
        document, first, _second, _module, _counting = _shared_document(tmp_path / "shared")
    elif state == "before":
        document, first, _second, _module, _counting = _shared_document(
            tmp_path / "before", TaskPhase.PRE_CONDITION,
        )
    dialog = ConditionModifierDialog(document, condition_id=first, fpvs_root=tmp_path)
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#202124" if dark else "#f4f7fb"))
    dialog.setPalette(palette)
    dialog.resize(*size)
    dialog.show()
    if state in {"before", "shared"}:
        dialog._refresh_list(_PRE_QUESTIONS_KEY if state == "before" else _QUESTIONS_KEY)
    if state == "advanced":
        dialog.advanced_toggle.setChecked(True)
    elif state == "busy":
        monkeypatch.setattr("fpvs_studio.gui.condition_modifier_dialog.BackgroundTask", _ManualTask)
        dialog._run_job(lambda: None, lambda _value: None, "Rebuilding saved question responses…")
    elif state == "error":
        dialog._show_error(
            ValueError("Close post_condition_responses.csv in Excel, then rebuild responses.")
        )
    _fit(dialog)
    assert dialog.size().toTuple() == size
    assert dialog.minimumSize().toTuple() == (1100, 720)
    assert dialog.advanced_toggle.text() == "Advanced modifiers"
    assert dialog.before_questions_button.text() == "Add before-condition question…"
    assert dialog.questions_button.text() == "Add after-condition question…"
    for button in (dialog.before_questions_button, dialog.questions_button):
        assert button.isVisible()
        assert button.width() >= button.sizeHint().width()
    for button in (dialog.counting_button, dialog.memory_button, dialog.masking_button,
                   dialog.add_button):
        assert button.isVisible() == (state == "advanced")
    assert dialog.custom_button.isVisible() == (state == "advanced")
    assert dialog.save_button.isVisible() == (state == "advanced")
    for widget in (dialog.responses_label, dialog.open_responses_button,
                   dialog.rebuild_responses_button):
        assert widget.isVisible() == (state == "advanced")
    if state == "advanced":
        assert dialog.responses_label.width() >= (
            dialog.responses_label.fontMetrics().horizontalAdvance(POST_CONDITION_RESPONSES_FILENAME)
        )
    if state == "busy":
        dialog._active_task.complete()


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("size", [(1000, 680), (1060, 740)])
@pytest.mark.parametrize("phase", [TaskPhase.PRE_CONDITION, TaskPhase.POST_CONDITION])
@pytest.mark.parametrize(
    "kind", ["single_choice", "multiple_choice", "short_text", "long_text", "numeric", "rating"]
)
def test_simple_question_controls_fit_all_types_and_long_text(
    qtbot, tmp_path, dark, size, kind, phase,
):
    document, first, _second = _document(tmp_path)
    dialog = PostQuestionsDialog(
        document.project, project_root=document.project_root, condition_id=first, phase=phase,
    )
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#202124" if dark else "#f4f7fb"))
    dialog.setPalette(palette)
    dialog.resize(*size)
    dialog.show()
    editor = dialog.editor
    editor.question_kind_combo.setCurrentIndex(editor.question_kind_combo.findData(kind))
    editor.question_prompt_edit.setPlainText(
        "Did you see a fearful face, even briefly, among the neutral faces in this presentation?"
    )
    editor.question_tabs.setCurrentIndex(1)
    _fit(dialog)
    assert dialog.size().toTuple() == size
    assert not editor.options_edit.isVisible()
    assert not editor.question_id_edit.isVisible()


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("size", [(700, 500), (760, 560)])
@pytest.mark.parametrize("kind", list(TaskQuestionKind))
def test_authoring_preview_fits_supported_response_controls(qtbot, dark, size, kind):
    values = {
        "question_id": "preview-question",
        "kind": kind,
        "prompt": (
            "Did you see a fearful face, even briefly, among the neutral faces "
            "in the presentation that just finished?"
        ),
    }
    if kind in {TaskQuestionKind.SINGLE_CHOICE, TaskQuestionKind.MULTIPLE_CHOICE}:
        options = make_yes_no_question("Question").options
        options[0].label = (
            "Yes, I saw a fearful face, even if only briefly, among the neutral faces "
            "in the presentation that just finished."
        )
        options[1].label = (
            "No, I did not see a fearful face in this presentation, although some "
            "of the faces may have appeared ambiguous."
        )
        values["options"] = options
    elif kind in {TaskQuestionKind.NUMERIC, TaskQuestionKind.RATING}:
        values.update(min_value=0, max_value=10, min_label="Not at all", max_label="Very clear")
    preview = PostQuestionPreview([TaskQuestion.model_validate(values)])
    qtbot.addWidget(preview)
    palette = preview.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#202124" if dark else "#f4f7fb"))
    preview.setPalette(palette)
    preview.resize(*size)
    preview.show()
    _fit(preview)
    assert preview.size().toTuple() == size
    assert preview.minimumSize().toTuple() == (700, 500)
    for button in preview.choice_buttons.values():
        label = button.findChild(QLabel)
        assert label.text() == button.accessibleName()
        assert label.height() >= label.heightForWidth(label.width())
        assert button.toolTip()


@pytest.mark.parametrize("dark", [False, True])
def test_preview_many_answers_scroll_without_hiding_continue(qtbot, dark):
    question = make_yes_no_question("Choose an answer from the complete list.")
    question.options = [
        question.options[0].model_copy(
            update={"option_id": f"answer-{index}", "label": f"Answer {index}"}, deep=True
        )
        for index in range(1, 17)
    ]
    preview = PostQuestionPreview([question])
    qtbot.addWidget(preview)
    palette = preview.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#202124" if dark else "#f4f7fb"))
    preview.setPalette(palette)
    preview.resize(700, 500)
    preview.show()
    QApplication.processEvents()
    assert preview.size().toTuple() == (700, 500)
    assert preview.controls_area.verticalScrollBar().maximum() > 0
    assert preview.controls_area.horizontalScrollBar().maximum() == 0
    assert preview.rect().contains(preview.continue_button.geometry())
    last = preview.choice_buttons["answer-16"]
    preview.controls_area.ensureWidgetVisible(last)
    last.click()
    assert not preview.answers
    assert preview.continue_button.isEnabled()
    preview.continue_button.click()
    assert preview.answers[0].selected_option_ids == ["answer-16"]
