"""Readable question responses retain original meanings across interruptions and edits."""

from __future__ import annotations

import csv
import json
import zipfile
from uuid import uuid4

import pytest
from tests.unit.test_library_publish import _ready_project

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.library_publish import prepare_library_bundle
from fpvs_studio.core.post_questions import make_post_questionnaire, make_yes_no_question
from fpvs_studio.core.project_bundle import export_project_bundle
from fpvs_studio.core.task_models import (
    TaskBinding,
    TaskPhase,
    TaskQuestion,
    TaskQuestionKind,
    TaskResponseRecord,
)
from fpvs_studio.runtime.post_condition_responses import (
    POST_CONDITION_RESPONSES_FILENAME,
    PostConditionResponseRecorder,
    post_condition_responses_path,
    rebuild_post_condition_responses,
)
from fpvs_studio.runtime.session_export import append_task_response_checkpoint


def _plan(project, root, questions=None, *, task_id="post-questions"):
    questions = questions or [
        make_yes_no_question("Did you see a fearful face?", question_id="fear"),
    ]
    module = make_post_questionnaire(questions, task_id=task_id)
    project.task_modules = [module]
    for condition in project.conditions:
        condition.post_task_bindings = [TaskBinding(task_id=module.task_id)]
    return compile_session_plan(project, project_root=root, refresh_hz=60.0, random_seed=123)


def _recorder(root, plan, *, participant="001", visit=1):
    execution_id = uuid4().hex
    journals = {entry.run_id: root / "logs" / f"{execution_id}-{index}.jsonl"
                for index, entry in enumerate(plan.ordered_entries())}
    recorder = PostConditionResponseRecorder(
        root, plan, participant_number=participant, participant_session_number=visit,
        execution_id=execution_id, journal_paths=journals,
    )
    return recorder, journals


def _submit(
    plan, journals, *, option="no", text=None, number=None, index=0, question_index=0, **changes,
):
    entry = plan.ordered_entries()[index]
    module = entry.post_tasks[0]
    definition = module.post_question_context.questions[question_index]
    payload = dict(
        response_index=question_index, task_id=module.task_id, step_id=definition.step_id,
        phase=TaskPhase.POST_CONDITION, condition_id=entry.condition_id, run_id=entry.run_id,
        block_index=entry.block_index, global_order_index=entry.global_order_index,
        repetition_index=0, question_id=definition.question_id,
        selected_option_ids=[option] if option else [], text_value=text,
        numeric_value=number, reaction_time_s=1.25,
    )
    payload.update(changes)
    append_task_response_checkpoint(journals[entry.run_id], TaskResponseRecord(**payload))


def _rows(root):
    with post_condition_responses_path(root).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def _complete(recorder, plan, journals, **response):
    entry = plan.ordered_entries()[0]
    recorder.start_entry(entry.run_id)
    recorder.start_module(entry.run_id, entry.post_tasks[0].task_id)
    for question_index in range(len(entry.post_tasks[0].post_question_context.questions)):
        _submit(plan, journals, question_index=question_index, **response)
    recorder.finish_entry(entry.run_id, state="completed")
    recorder.finish_session(state="completed")
    recorder.write_csv()


def test_no_is_answered_and_each_execution_and_visit_remains_distinct(
    sample_project, sample_project_root,
):
    root = sample_project_root
    plan = _plan(sample_project, root)
    for participant, visit in [("001", 1), ("002", 1), ("001", 2)]:
        recorder, journals = _recorder(root, plan, participant=participant, visit=visit)
        if participant == "001" and visit == 1:
            assert not (root / POST_CONDITION_RESPONSES_FILENAME).exists()
        _complete(recorder, plan, journals)
    header, rows = _rows(root)
    answer = next(column for column in header if column.startswith("Did you see"))
    assert len(rows) == 3
    assert [row["Participant"] for row in rows] == ["001", "002", "001"]
    assert rows[-1]["Session / visit"] == "2"
    assert len({row["Execution ID"] for row in rows}) == 3
    assert all(row[answer] == "No" and row[f"Status: {answer}"] == "answered" for row in rows)
    assert all(row[f"RT (s): {answer}"] == "1.25" for row in rows)


def test_partial_journal_rebuild_uses_original_context_and_marks_unknown(
    sample_project, sample_project_root,
):
    root = sample_project_root
    questions = [make_yes_no_question("Original wording", question_id="first"),
                 make_yes_no_question("Unanswered question", question_id="second")]
    plan = _plan(sample_project, root, questions)
    recorder, journals = _recorder(root, plan)
    entry = plan.ordered_entries()[0]
    recorder.start_entry(entry.run_id)
    recorder.start_module(entry.run_id, entry.post_tasks[0].task_id)
    _submit(plan, journals)
    # A later process failure never returned a task result or finalized the session.
    with journals[entry.run_id].open("a", encoding="utf-8") as handle:
        handle.write('{"response_index":')
    sample_project.conditions[0].name = "Renamed after collection"
    sample_project.task_modules[0].steps[0].questions[0].prompt = "Edited afterwards"
    assert rebuild_post_condition_responses(root)
    header, rows = _rows(root)
    first = next(column for column in header if column.startswith("Original wording"))
    second = next(column for column in header if column.startswith("Unanswered question"))
    assert rows[0][first] == "No"
    assert rows[0][f"Status: {second}"] == "interrupted"
    assert rows[0]["Condition"] != "Renamed after collection"
    assert rows[0]["Session status"] == "not_finalized"


def test_abort_before_questions_has_expected_row_without_fabricated_answer(
    sample_project, sample_project_root,
):
    plan = _plan(sample_project, sample_project_root)
    recorder, _ = _recorder(sample_project_root, plan)
    recorder.start_entry(plan.ordered_entries()[0].run_id)
    recorder.finish_entry(plan.ordered_entries()[0].run_id, state="aborted")
    recorder.finish_session(state="aborted")
    recorder.write_csv()
    header, rows = _rows(sample_project_root)
    answer = next(column for column in header if column.startswith("Did you see"))
    assert rows[0][answer] == ""
    assert rows[0][f"Status: {answer}"] == "not_presented"


def test_excel_lock_keeps_prior_csv_and_rebuild_recovers_all_answers(
    sample_project, sample_project_root, monkeypatch,
):
    import fpvs_studio.runtime.session_export as exporters

    root = sample_project_root
    plan = _plan(sample_project, root)
    recorder, journals = _recorder(root, plan)
    _complete(recorder, plan, journals)
    prior = post_condition_responses_path(root).read_bytes()
    recorder, journals = _recorder(root, plan, participant="002")
    original_replace = exporters.replace_file_atomically
    monkeypatch.setattr(exporters, "replace_file_atomically", lambda *_: (_ for _ in ()).throw(
        PermissionError("Excel has the CSV open"),
    ))
    with pytest.raises(PermissionError, match="Excel"):
        _complete(recorder, plan, journals, option="yes")
    assert post_condition_responses_path(root).read_bytes() == prior
    monkeypatch.setattr(exporters, "replace_file_atomically", original_replace)
    rebuild_post_condition_responses(root)
    assert len(_rows(root)[1]) == 2


def test_edited_definition_adds_column_while_unchanged_question_reuses_it(
    sample_project, sample_project_root,
):
    root = sample_project_root
    plan = _plan(sample_project, root)
    recorder, journals = _recorder(root, plan)
    _complete(recorder, plan, journals)
    plan = _plan(sample_project, root, [make_yes_no_question("New wording", question_id="fear")])
    recorder, journals = _recorder(root, plan, visit=2)
    _complete(recorder, plan, journals, option="yes")
    header, rows = _rows(root)
    old = next(column for column in header if column.startswith("Did you see"))
    new = next(column for column in header if column.startswith("New wording"))
    assert rows[0][old] == "No" and rows[0][new] == ""
    assert rows[1][new] == "Yes" and rows[1][f"Status: {old}"] == "not_assigned"


@pytest.mark.parametrize("kind,value,expected", [
    (TaskQuestionKind.LONG_TEXT, '=hello, "世界"\nnext', '\'=hello, "世界"\nnext'),
    (TaskQuestionKind.NUMERIC, 0, "0.0"),
])
def test_readable_unicode_quoted_formula_text_and_zero(
    sample_project, sample_project_root, kind, value, expected,
):
    question = TaskQuestion(question_id="answer", kind=kind, prompt="=Question, 世界?",
                            **({"min_value": 0, "max_value": 10} if kind == TaskQuestionKind.NUMERIC
                               else {}))
    plan = _plan(sample_project, sample_project_root, [question])
    recorder, journals = _recorder(sample_project_root, plan)
    _complete(recorder, plan, journals, option=None,
              **({"number": value} if kind == TaskQuestionKind.NUMERIC else {"text": value}))
    header, rows = _rows(sample_project_root)
    answer = next(column for column in header if column.startswith("'=Question"))
    assert rows[0][answer] == expected


def test_original_context_never_contains_answers_and_duplicate_execution_is_rejected(
    sample_project, sample_project_root,
):
    root = sample_project_root
    plan = _plan(sample_project, root)
    recorder, journals = _recorder(root, plan)
    _complete(recorder, plan, journals)
    context = next((root / "logs/post-condition-responses").glob("*.json"))
    payload = json.loads(context.read_text(encoding="utf-8"))
    assert "selected_option_ids" not in context.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        PostConditionResponseRecorder(root, plan, participant_number="001",
                                      participant_session_number=1,
                                      execution_id=payload["execution_id"], journal_paths=journals)


def test_redirected_response_csv_is_rejected(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.csv"
    outside.write_text("preserve", encoding="utf-8")
    try:
        (root / POST_CONDITION_RESPONSES_FILENAME).symlink_to(outside)
    except OSError:
        pytest.skip("Windows symlink creation unavailable")
    with pytest.raises(ValueError):
        post_condition_responses_path(root)
    assert outside.read_text(encoding="utf-8") == "preserve"


def test_response_view_and_retained_context_stay_out_of_portable_projects(
    sample_project, sample_project_root, tmp_path,
):
    root = sample_project_root
    plan = _plan(sample_project, root)
    recorder, journals = _recorder(root, plan)
    _complete(recorder, plan, journals)
    # Ordinary bundles preserve legitimate stimulus CSVs; no blanket CSV blacklist.
    stimulus_csv = root / "stimuli" / "word-source.csv"
    stimulus_csv.write_text("word\nface\n", encoding="utf-8")
    _ready_project(root, sample_project)
    ordinary, library = tmp_path / "ordinary.fpvsbundle", tmp_path / "library.fpvsbundle"
    export_project_bundle(root, ordinary)
    prepare_library_bundle(root, library)
    for bundle in (ordinary, library):
        with zipfile.ZipFile(bundle) as archive:
            names = archive.namelist()
            assert POST_CONDITION_RESPONSES_FILENAME not in names
            assert not any(name.startswith("logs/") for name in names)
    with zipfile.ZipFile(ordinary) as archive:
        assert "stimuli/word-source.csv" in archive.namelist()


def test_unsubmitted_abort_selection_is_retained_only_in_raw_journal(
    sample_project, sample_project_root,
):
    root = sample_project_root
    plan = _plan(sample_project, root)
    recorder, journals = _recorder(root, plan)
    entry = plan.ordered_entries()[0]
    recorder.start_entry(entry.run_id)
    recorder.start_module(entry.run_id, entry.post_tasks[0].task_id)
    _submit(plan, journals, option="yes", aborted=True)
    recorder.finish_entry(entry.run_id, state="aborted")
    recorder.finish_session(state="aborted")
    recorder.write_csv()
    header, rows = _rows(root)
    answer = next(column for column in header if column.startswith("Did you see"))
    assert rows[0][answer] == "" and rows[0][f"Status: {answer}"] == "aborted"
    assert '"selected_option_ids": ["yes"]' in journals[entry.run_id].read_text(encoding="utf-8")


def test_same_prompt_private_copy_keeps_distinct_columns(sample_project, sample_project_root):
    root = sample_project_root
    for task_id, visit in [("original-questions", 1), ("private-questions", 2)]:
        plan = _plan(sample_project, root, task_id=task_id)
        recorder, journals = _recorder(root, plan, visit=visit)
        _complete(recorder, plan, journals)
    header, rows = _rows(root)
    answers = [column for column in header if column.startswith("Did you see")]
    assert len(answers) == 2
    assert rows[0][answers[0]] == "No" and rows[0][answers[1]] == ""
    assert rows[1][answers[1]] == "No" and rows[1][answers[0]] == ""


def test_reordering_questions_keeps_original_columns(sample_project, sample_project_root):
    root = sample_project_root
    questions = [make_yes_no_question("First", question_id="first"),
                 make_yes_no_question("Second", question_id="second")]
    for visit, ordered in [(1, questions), (2, list(reversed(questions)))]:
        plan = _plan(sample_project, root, ordered)
        recorder, journals = _recorder(root, plan, visit=visit)
        _complete(recorder, plan, journals)
    header, rows = _rows(root)
    answers = [column for column in header if column.startswith(("First [", "Second ["))]
    assert len(answers) == 2
    assert rows[0][answers[0]] == "No" and rows[1][answers[1]] == "No"


def test_prepared_but_never_started_does_not_create_response_csv(
    sample_project, sample_project_root,
):
    plan = _plan(sample_project, sample_project_root)
    recorder, _ = _recorder(sample_project_root, plan)
    recorder.finish_session(state="aborted")
    assert recorder.write_csv() is None
    assert not post_condition_responses_path(sample_project_root).exists()


def test_added_csv_annotations_are_preserved_for_review_instead_of_blanked(
    sample_project, sample_project_root,
):
    root = sample_project_root
    plan = _plan(sample_project, root)
    recorder, journals = _recorder(root, plan)
    _complete(recorder, plan, journals)
    header, rows = _rows(root)
    path = post_condition_responses_path(root)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*header, "Researcher notes"])
        writer.writeheader()
        writer.writerows({**row, "Researcher notes": "Keep this annotation"} for row in rows)
    annotated = path.read_bytes()
    with pytest.raises(ValueError, match="header was changed"):
        rebuild_post_condition_responses(root)
    assert path.read_bytes() == annotated
