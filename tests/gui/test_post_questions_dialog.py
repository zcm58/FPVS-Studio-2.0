"""Registered simple-question authoring, scope, preview and output-action checks."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QLabel
from tests.gui.helpers import assert_visible_children_within_parent
from tests.gui.test_condition_modifier_dialog import _document

from fpvs_studio.core.condition_modifiers import assign_modifier, create_backward_counting_modifier
from fpvs_studio.core.post_questions import (
    apply_post_questionnaire,
    make_post_questionnaire,
    make_yes_no_question,
)
from fpvs_studio.core.task_models import (
    TaskBinding,
    TaskModule,
    TaskQuestion,
    TaskQuestionKind,
    TaskStep,
    TaskStepKind,
    TaskSubmissionMode,
)
from fpvs_studio.gui.condition_modifier_dialog import (
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


def _questionnaire():
    return make_post_questionnaire(
        [
            make_yes_no_question("Did you see a fearful face?", question_id="fearful-face"),
        ]
    )


def _shared_document(tmp_path):
    document, first, second = _document(tmp_path)
    counting = create_backward_counting_modifier()
    project = assign_modifier(document.project, counting, [first, second])
    module = _questionnaire()
    project = apply_post_questionnaire(project, module, [first, second])
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


def test_default_questions_use_natural_yes_no_and_apply_without_io(qtbot, tmp_path):
    document, first, _second = _document(tmp_path)
    before = document.project.model_copy(deep=True)
    dialog = PostQuestionsDialog(
        document.project, project_root=document.project_root, condition_id=first
    )
    qtbot.addWidget(dialog)
    dialog.show()
    editor = dialog.editor
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
    assert candidate.simple_post_questions
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
    assert not condition.pre_task_bindings
    assert len(condition.post_task_bindings) == 1
    assert not (document.project_root / POST_CONDITION_RESPONSES_FILENAME).exists()


@pytest.mark.parametrize("shared", [False, True])
def test_private_and_explicit_shared_edits_preserve_other_activities(qtbot, tmp_path, shared):
    document, first, second, module, counting = _shared_document(tmp_path)
    before = document.project.model_copy(deep=True)
    dialog = PostQuestionsDialog(
        document.project,
        project_root=document.project_root,
        condition_id=first,
        task_id=module.task_id,
    )
    qtbot.addWidget(dialog)
    if shared:
        dialog.shared_checkbox.setChecked(True)
    dialog.editor.question_prompt_edit.setPlainText("Did you see an angry face?")
    dialog.accept()
    candidate = dialog.project_result
    assert candidate is not None
    conditions = {condition.condition_id: condition for condition in candidate.conditions}
    first_id = conditions[first].post_task_bindings[-1].task_id
    second_id = conditions[second].post_task_bindings[-1].task_id
    assert (first_id == second_id) == shared
    assert conditions[first].post_task_bindings[0].task_id == counting.modifier.post_task_ids[0]
    assert conditions[second].post_task_bindings[0] == before.conditions[1].post_task_bindings[0]
    tasks = {task.task_id: task for task in candidate.task_modules}
    assert tasks[first_id].steps[0].questions[0].question_id == "fearful-face"
    assert tasks[second_id].steps[0].questions[0].prompt == (
        "Did you see an angry face?" if shared else "Did you see a fearful face?"
    )
    assert candidate.settings.session == before.settings.session
    assert document.project == before


def test_unchanged_apply_keeps_shared_identity_and_cancel_preserves_source(qtbot, tmp_path):
    document, first, _second, module, _counting = _shared_document(tmp_path)
    before = document.project.model_copy(deep=True)
    dialog = PostQuestionsDialog(
        document.project,
        project_root=document.project_root,
        condition_id=first,
        task_id=module.task_id,
    )
    qtbot.addWidget(dialog)
    dialog.accept()
    assert dialog.project_result == before
    cancelled = PostQuestionsDialog(
        document.project,
        project_root=document.project_root,
        condition_id=first,
        task_id=module.task_id,
    )
    qtbot.addWidget(cancelled)
    cancelled.editor.question_prompt_edit.setPlainText("Discard this draft")
    cancelled.reject()
    assert cancelled.project_result is None
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


@pytest.mark.parametrize("action", ["cancel", "apply"])
def test_modifier_question_draft_applies_once_and_save_reopens_without_response_file(
    qtbot,
    monkeypatch,
    tmp_path,
    action,
):
    document, first, _second = _document(tmp_path)
    before = document.project.model_copy(deep=True)
    candidate = apply_post_questionnaire(document.project, _questionnaire(), [first])

    class AcceptedQuestions:
        project_result = candidate
        affected_condition_ids = {first}

        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "fpvs_studio.gui.condition_modifier_dialog.PostQuestionsDialog", AcceptedQuestions
    )
    monkeypatch.setattr("fpvs_studio.gui.condition_modifier_dialog.BackgroundTask", _ImmediateTask)
    dialog = ConditionModifierDialog(document, condition_id=first)
    qtbot.addWidget(dialog)
    dialog.questions_button.click()
    assert document.project == before
    assert dialog._selected_questions
    assert "Post-condition Questions" in dialog.question_flow_label.text()
    if action == "cancel":
        dialog.reject()
        assert document.project == before
    else:
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert "Post-condition Questions" in condition_modifier_summary(document, first)
        document.save()
        reopened = ProjectDocument.open_existing(document.project_root)
        assert any(module.simple_post_questions for module in reopened.project.task_modules)
    assert not (document.project_root / POST_CONDITION_RESPONSES_FILENAME).exists()


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
@pytest.mark.parametrize("state", ["empty", "shared", "advanced", "busy", "error"])
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
    dialog = ConditionModifierDialog(document, condition_id=first, fpvs_root=tmp_path)
    qtbot.addWidget(dialog)
    palette = dialog.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#202124" if dark else "#f4f7fb"))
    dialog.setPalette(palette)
    dialog.resize(*size)
    dialog.show()
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
    assert all(
        button.isVisible()
        for button in (
            dialog.counting_button,
            dialog.memory_button,
            dialog.masking_button,
            dialog.questions_button,
        )
    )
    assert dialog.custom_button.isVisible() == (state == "advanced")
    assert dialog.save_button.isVisible() == (state == "advanced")
    assert dialog.responses_label.width() >= dialog.responses_label.fontMetrics().horizontalAdvance(
        POST_CONDITION_RESPONSES_FILENAME
    )
    if state == "busy":
        dialog._active_task.complete()


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("size", [(1000, 680), (1060, 740)])
@pytest.mark.parametrize(
    "kind", ["single_choice", "multiple_choice", "short_text", "long_text", "numeric", "rating"]
)
def test_simple_question_controls_fit_all_types_and_long_text(qtbot, tmp_path, dark, size, kind):
    document, first, _second = _document(tmp_path)
    dialog = PostQuestionsDialog(
        document.project, project_root=document.project_root, condition_id=first
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
