"""Participant research sheets preserve identity, original labels and partial answers."""

from __future__ import annotations

import csv
import json
from copy import copy

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.demographics import DemographicsAnswer
from fpvs_studio.core.execution import (
    FixationResponseRecord,
    ParticipantMetadata,
    ResponseRecord,
    RunExecutionSummary,
    RuntimeMetadata,
    SessionExecutionSummary,
)
from fpvs_studio.core.post_questions import compile_post_question_context, make_post_questionnaire
from fpvs_studio.core.task_models import (
    TaskModuleSpec,
    TaskOption,
    TaskPhase,
    TaskQuestion,
    TaskResponseKind,
    TaskResponseRecord,
    TaskStepSpec,
)
from fpvs_studio.runtime.participant_results import (
    DEMOGRAPHIC_ANSWERS_SHEET_NAME,
    add_participant_results_sheets,
    capture_participant_results,
    freeze_legacy_participant_results,
    has_captured_participant_results,
    participant_results_source_paths,
)
from fpvs_studio.runtime.session_export import (
    SESSION_CONDITION_HISTORY_HEADER,
    _write_csv,
    append_compact_task_responses,
    append_session_condition_history,
    append_task_response_checkpoint,
    refresh_participant_summary_if_stale,
    write_participant_summary,
    write_session_artifacts,
)


@pytest.fixture
def results(sample_project, sample_project_root):
    plan = compile_session_plan(sample_project, project_root=sample_project_root,
                                refresh_hz=60.0, random_seed=31)
    entry = plan.ordered_entries()[0]
    entry.pre_tasks = [TaskModuleSpec(
        task_id="survey", name="Before survey", phase="pre_condition",
        occurrence="every_entry", random_seed=1,
        steps=[TaskStepSpec(step_id="questions", kind="questionnaire", random_seed=1,
            questions=[TaskQuestion(question_id="choice", kind="single_choice", prompt="Original?",
                                   options=[TaskOption(option_id="yes", label="Original yes")])])],
    )]
    choice = TaskResponseRecord(
        response_index=0, task_id="survey", step_id="questions", phase="pre_condition",
        condition_id=entry.condition_id, run_id=entry.run_id, block_index=0,
        global_order_index=0, repetition_index=0, question_id="choice",
        response_kind="option_selection", selected_option_ids=["yes"], reaction_time_s=0.325,
    )
    run = RunExecutionSummary(
        project_id=plan.project_id, session_id=plan.session_id, run_id=entry.run_id,
        condition_id=entry.condition_id, condition_name=entry.condition_name,
        engine_name="stub", run_mode="session", participant_number="009",
        participant_session_number=1, task_responses=[choice],
        fixation_responses=[
            FixationResponseRecord(event_index=0, start_frame=10, duration_frames=1,
                                   responded=True, first_response_key="space", response_frame=20,
                                   target_onset_time_s=1.0, response_time_s=1.167,
                                   rt_s=0.167, outcome="hit"),
            FixationResponseRecord(event_index=1, start_frame=80, duration_frames=1,
                                   responded=False, outcome="miss"),
        ],
        response_log=[
            ResponseRecord(response_index=0, key="space", frame_index=20,
                           matched_event_index=0, rt_s=0.167, outcome="hit"),
            ResponseRecord(response_index=1, key="space", frame_index=100,
                           outcome="false_alarm"),
        ],
    )
    summary = SessionExecutionSummary(
        project_id=plan.project_id, session_id=plan.session_id, engine_name="stub",
        run_mode="session", participant_number="009", participant_session_number=1,
        participant_metadata=ParticipantMetadata(age=30, sex="Female", colorblind=False),
        run_results=[run],
    )
    return plan, summary


def _rows(workbook, sheet):
    values = list(workbook[sheet].values)
    return [dict(zip(values[0], row, strict=True)) for row in values[1:]]


def _workbook(root, history=()):
    workbook = Workbook()
    workbook.active.title = "Participant Summary"
    workbook.active.append(["Existing header"])
    add_participant_results_sheets(workbook, root, list(history))
    return workbook


def _history(plan, summary, **extra):
    run = summary.run_results[0]
    return {
        "project_id": plan.project_id, "participant_number": "009",
        "participant_session_number": "1", "session_id": plan.session_id,
        "condition_id": run.condition_id, "condition_name": run.condition_name,
        "run_id": run.run_id, "session_aborted": "False", "run_aborted": "False",
        "total_targets": "2", "hit_count": "1", "miss_count": "1", "false_alarm_count": "1",
        "accuracy_percent": "50", "mean_rt_ms": "167", **extra,
    }


def test_capture_retry_preserves_labels_and_individual_responses(tmp_path, results):
    plan, summary = results
    first = capture_participant_results(tmp_path, plan, summary)
    assert capture_participant_results(tmp_path, plan, summary) == first
    assert len(list(first.parent.glob("*.json"))) == 1
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert "stimulus_sequence" not in first.read_text(encoding="utf-8")
    assert "frame_intervals" not in first.read_text(encoding="utf-8")
    assert len(payload["runs"][0]["fixation_responses"]) == 2
    # An editable project is neither needed nor read when reporting old questions.
    (tmp_path / "project.json").write_text('{"prompt":"Changed"}', encoding="utf-8")
    workbook = _workbook(tmp_path, [_history(plan, summary)])
    answer, = _rows(workbook, "Task Answers")
    assert (answer["Question"], answer["Answer"], answer["Phase"]) == (
        "Original?", "Original yes", "Before",
    )
    assert answer["PID"] == "009"
    assert answer["Reaction Time (s)"] == 0.325
    fixation = _rows(workbook, "Fixation Responses")
    assert [(row["Row Type"], row["Outcome"]) for row in fixation] == [
        ("Target", "hit"), ("Target", "miss"), ("Unmatched response", "false_alarm"),
    ]
    assert fixation[0]["Reaction Time (s)"] == 0.167
    assert fixation[1]["Reaction Time (s)"] is None
    assert workbook["Participant Summary"]["A1"].value == "Existing header"
    changed = plan.model_copy(deep=True)
    changed.ordered_entries()[0].pre_tasks[0].steps[0].questions[0].prompt = "Changed"
    original = first.read_bytes()
    with pytest.raises(ValueError, match="cannot be replaced"):
        capture_participant_results(tmp_path, changed, summary)
    assert first.read_bytes() == original


def test_before_and_after_attempts_formula_text_and_numeric_zero(tmp_path, results):
    plan, summary = results
    first = summary.run_results[0].task_responses[0]
    summary.run_results[0].task_responses += [first.model_copy(update={
        "response_index": 1, "phase": TaskPhase.POST_CONDITION, "question_id": None,
        "selected_option_ids": [], "text_value": "=HYPERLINK(\"bad\")", "attempt_index": 1,
        "correct": False,
    }), first.model_copy(update={
        "response_index": 2, "selected_option_ids": [], "numeric_value": 0,
        "reaction_time_s": 0.0, "text_value": None,
    }), first.model_copy(update={
        "response_index": 3, "selected_option_ids": [], "text_value": "'=literal apostrophe",
    })]
    capture_participant_results(tmp_path, plan, summary)
    workbook = _workbook(tmp_path)
    destination = tmp_path / "results.xlsx"
    workbook.save(destination)
    saved = load_workbook(destination)
    answers = _rows(saved, "Task Answers")
    assert len(answers) == 4
    assert answers[1]["Phase"] == "After"
    assert answers[1]["Answer"] == '=HYPERLINK("bad")'
    answer_column = list(saved["Task Answers"].values)[0].index("Answer") + 1
    assert saved["Task Answers"].cell(3, answer_column).data_type == "s"
    assert answers[1]["Attempt"] == 1
    assert answers[1]["Correct"] == "No"
    assert answers[2]["Answer"] == 0
    assert answers[2]["Reaction Time (s)"] == 0
    assert answers[2]["Status"] == "Answered"
    assert answers[3]["Answer"] == "'=literal apostrophe"
    saved.close()


def test_legacy_full_and_compact_numbered_sources_deduplicate(tmp_path, results):
    plan, summary = results
    output = tmp_path / "runs/old"
    write_session_artifacts(output, plan, summary)
    append_compact_task_responses(tmp_path, plan, summary)
    history = [_history(plan, summary, output_dir="runs/old")]
    workbook = _workbook(tmp_path, history)
    answer, = _rows(workbook, "Task Answers")
    assert answer["Answer"] == "Original yes"
    assert answer["Question"] == "Original?"
    assert len(_rows(workbook, "Fixation Responses")) == 3
    # A new private snapshot is preferred, and does not duplicate historical sources.
    capture_participant_results(tmp_path, plan, summary)
    assert len(_rows(_workbook(tmp_path, history), "Task Answers")) == 1


def test_legacy_compact_missing_labels_is_explicit_and_read_only(tmp_path, results):
    plan, summary = results
    append_compact_task_responses(tmp_path, plan, summary)
    path = tmp_path / "logs/task_responses.csv"
    original = path.read_bytes()
    answer, = _rows(_workbook(tmp_path), "Task Answers")
    assert answer["Question"] == "Unavailable (historical record)"
    assert answer["Answer"] == "Unavailable (historical record): yes"
    assert answer["Selected Option IDs"] == "yes"
    assert answer["Reaction Time (s)"] == 0.325
    assert path.read_bytes() == original


def test_pending_capture_recovers_partial_journal_before_any_history(tmp_path, results):
    plan, summary = results
    response = summary.run_results[0].task_responses[0]
    journal = tmp_path / "logs/.task-response-checkpoints/partial.jsonl"
    empty = summary.model_copy(update={"run_results": []})
    empty.participant_metadata.demographics_answers = [
        DemographicsAnswer(question_id="vision", prompt="Corrected vision?", answer=False),
    ]
    assert not has_captured_participant_results(tmp_path)
    capture = capture_participant_results(tmp_path, plan, empty, finalized=False,
                                        journal_paths={response.run_id: journal})
    assert has_captured_participant_results(tmp_path)
    append_task_response_checkpoint(journal, response)
    workbook = _workbook(tmp_path)
    answer, = _rows(workbook, "Task Answers")
    assert answer["Answer"] == "Original yes"
    assert answer["Session Aborted"] == "Not finalized"
    demographic, = _rows(workbook, "Demographics")
    assert demographic["Age"] == 30
    assert demographic["Session Aborted"] == "Not finalized"
    demographic_answer, = _rows(workbook, DEMOGRAPHIC_ANSWERS_SHEET_NAME)
    assert demographic_answer["Answer"] is False
    assert demographic_answer["Session Aborted"] == "Not finalized"
    assert set(participant_results_source_paths(tmp_path)) == {capture, journal}


def test_demographic_answers_keep_original_question_order_and_visit_identity(tmp_path, results):
    plan, first = results
    first.participant_metadata.demographics_answers = [
        DemographicsAnswer(question_id="comments", prompt="=Original wording", answer="=1+2"),
        DemographicsAnswer(question_id="age", prompt="Age", answer=30),
    ]
    output = tmp_path / "runs/first"
    write_session_artifacts(output, plan, first)
    full_history = _history(plan, first, output_dir="runs/first")
    assert [
        row["Answer"] for row in _rows(
            _workbook(tmp_path, [full_history]), DEMOGRAPHIC_ANSWERS_SHEET_NAME,
        )
    ] == ["=1+2", 30]
    first_capture = capture_participant_results(tmp_path, plan, first)
    saved_capture = first_capture.read_bytes()

    second = first.model_copy(deep=True)
    second.run_results = []
    second.participant_metadata.demographics_answers = [
        DemographicsAnswer(question_id="comments", prompt="Revised wording", answer="New answer"),
    ]
    with pytest.raises(ValueError, match="Original demographic answers cannot be replaced"):
        capture_participant_results(tmp_path, plan, second)
    assert first_capture.read_bytes() == saved_capture
    second.participant_session_number = 2
    capture_participant_results(tmp_path, plan, second)

    history = [
        full_history,
        _history(plan, first, participant_session_number="3", participant_age="41"),
    ]
    path = tmp_path / "results.xlsx"
    _workbook(tmp_path, history).save(path)
    workbook = load_workbook(path)
    try:
        sheet = workbook[DEMOGRAPHIC_ANSWERS_SHEET_NAME]
        answers = _rows(workbook, DEMOGRAPHIC_ANSWERS_SHEET_NAME)
        assert len(answers) == 3
        assert [row["PID"] for row in answers] == ["009"] * 3
        assert [
            (row["Question Position"], row["Question ID"], row["Question"], row["Answer"])
            for row in answers if row["Session Number"] == 1
        ] == [(1, "comments", "=Original wording", "=1+2"), (2, "age", "Age", 30)]
        assert [row["Question"] for row in answers if row["Session Number"] == 2] == [
            "Revised wording",
        ]
        for row in sheet.iter_rows(min_row=2, min_col=3, max_col=4):
            assert row[0].data_type == "s"
            if isinstance(row[1].value, str):
                assert row[1].data_type == "s"
        assert any(row["Session Number"] == 3 and row["Age"] == 41
                   for row in _rows(workbook, "Demographics"))
    finally:
        workbook.close()


def test_refresh_adds_demographic_answers_to_an_older_workbook(tmp_path, results):
    plan, summary = results
    capture_participant_results(tmp_path, plan, summary)
    path = write_participant_summary(tmp_path)
    workbook = load_workbook(path)
    del workbook[DEMOGRAPHIC_ANSWERS_SHEET_NAME]
    workbook.save(path)
    workbook.close()

    assert refresh_participant_summary_if_stale(tmp_path) == path
    updated = load_workbook(path)
    try:
        assert _rows(updated, DEMOGRAPHIC_ANSWERS_SHEET_NAME) == []
        demographic, = _rows(updated, "Demographics")
        assert demographic["Age"] == 30
    finally:
        updated.close()


def test_aborted_test_visit_and_missing_rt_are_retained(tmp_path, results):
    plan, summary = results
    summary.participant_number = "00"
    summary.aborted = True
    response = summary.run_results[0].task_responses[0]
    response.aborted = True
    response.reaction_time_s = None
    capture_participant_results(tmp_path, plan, summary)
    history = _history(plan, summary, participant_number="00", session_aborted="True",
                       mean_rt_ms="", accuracy_percent="0", hit_count="0")
    workbook = _workbook(tmp_path, [history])
    demographic, = _rows(workbook, "Demographics")
    assert demographic["Test Participant"] == "Yes"
    fixation, = _rows(workbook, "Fixation by Condition")
    assert fixation["Include In Analysis"] == "No"
    assert fixation["Accuracy (%)"] == 0
    assert fixation["Mean Reaction Time (ms)"] is None
    answer, = _rows(workbook, "Task Answers")
    assert answer["Status"] == "Aborted"
    assert answer["Reaction Time (s)"] is None


def test_unfinished_journal_conflict_and_path_escape_fail_read_only(tmp_path, results):
    plan, summary = results
    response = summary.run_results[0].task_responses[0]
    journal = tmp_path / "logs/partial.jsonl"
    capture = capture_participant_results(tmp_path, plan, summary, finalized=False,
                                        journal_paths={response.run_id: journal})
    append_task_response_checkpoint(journal, response.model_copy(update={"reaction_time_s": 9.0}))
    with pytest.raises(ValueError, match="conflicts"):
        _workbook(tmp_path)
    capture.unlink()
    with pytest.raises(ValueError, match="escape"):
        _workbook(tmp_path, [_history(plan, summary, output_dir="../outside")])
    with pytest.raises(ValueError):
        capture_participant_results(tmp_path, plan, summary,
                                    journal_paths={response.run_id: tmp_path.parent / "outside"})


def test_legacy_unnumbered_rows_remain_distinct(tmp_path, results):
    plan, summary = results
    summary.participant_session_number = None
    append_compact_task_responses(tmp_path, plan, summary)
    path = tmp_path / "logs/task_responses.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows + rows)
    assert len(_rows(_workbook(tmp_path), "Task Answers")) == 2
    first = capture_participant_results(tmp_path, plan, summary)
    assert capture_participant_results(tmp_path, plan, summary) != first


def test_legacy_full_uses_run_journal_when_session_csv_missing(tmp_path, results):
    plan, summary = results
    output = tmp_path / "runs/old"
    write_session_artifacts(output, plan, summary)
    (output / "task_responses.csv").unlink()
    response = summary.run_results[0].task_responses[0]
    append_task_response_checkpoint(output / response.run_id / "task_responses.jsonl", response)
    answer, = _rows(_workbook(tmp_path, [_history(plan, summary, output_dir="runs/old")]),
                    "Task Answers")
    assert answer["Answer"] == "Original yes"


def test_unknown_private_schema_leaves_existing_workbook_untouched(tmp_path, results):
    plan, summary = results
    capture = capture_participant_results(tmp_path, plan, summary)
    destination = tmp_path / "existing.xlsx"
    original = _workbook(tmp_path)
    original.save(destination)
    before = destination.read_bytes()
    data = json.loads(capture.read_text(encoding="utf-8"))
    data["schema_version"] = 999
    capture.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        _workbook(tmp_path)
    assert destination.read_bytes() == before


def test_conflicting_numbered_answer_rejects_workbook_without_rewriting_sources(tmp_path, results):
    plan, summary = results
    capture_participant_results(tmp_path, plan, summary)
    changed = summary.model_copy(deep=True)
    changed.run_results[0].task_responses[0].reaction_time_s = 9.0
    append_compact_task_responses(tmp_path, plan, changed)
    path = tmp_path / "logs/task_responses.csv"
    original = path.read_bytes()
    with pytest.raises(ValueError, match="Conflicting task answers"):
        _workbook(tmp_path)
    assert path.read_bytes() == original


def test_unnumbered_checkpoints_share_execution_identity_and_ratings_remain_numeric(
    tmp_path, results,
):
    plan, summary = results
    summary.participant_session_number = None
    response = summary.run_results[0].task_responses[0]
    response.response_kind = TaskResponseKind.RATING
    response.numeric_value = 3.0
    response.selected_option_ids = ["rating-3"]
    first = capture_participant_results(tmp_path, plan, summary, execution_id="execution-one",
                                       finalized=False)
    assert capture_participant_results(tmp_path, plan, summary,
                                       execution_id="execution-one") == first
    answer, = _rows(_workbook(tmp_path), "Task Answers")
    assert answer["Answer"] == 3
    assert capture_participant_results(tmp_path, plan, summary,
                                       execution_id="execution-two") != first


@pytest.mark.parametrize("state,expected", [
    ("completed", "No"), ("prepared", "Not finalized"), ("error", "Error"),
])
def test_historical_post_context_recovers_original_labels_read_only(
    tmp_path, results, state, expected,
):
    plan, summary = results
    entry = plan.ordered_entries()[0]
    question = entry.pre_tasks[0].steps[0].questions[0]
    module = make_post_questionnaire([question], task_id="survey", name="Original post survey")
    context = compile_post_question_context(
        module, condition_id=entry.condition_id, condition_name=entry.condition_name,
        presentation_index=1, presentation_count=1,
    )
    response = summary.run_results[0].task_responses[0]
    response.phase = TaskPhase.POST_CONDITION
    journal = tmp_path / "logs/retained-post.jsonl"
    append_task_response_checkpoint(journal, response)
    directory = tmp_path / "logs/post-condition-responses"
    directory.mkdir()
    path = directory / "historical.json"
    payload = {
        "project_id": plan.project_id, "participant_number": "009",
        "participant_session_number": 1, "session_id": plan.session_id,
        "execution_id": "historical-one", "state": state,
        "entries": [{"run_id": entry.run_id, "global_order_index": 0,
                     "journal_path": "logs/retained-post.jsonl",
                     "questionnaires": [context.model_dump(mode="json")],
                     "state": "running" if state == "prepared" else state,
                     "started_tasks": ["survey"], "playback_completed": True}],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    if state == "completed":
        append_compact_task_responses(tmp_path, plan, summary)
    (tmp_path / "project.json").write_text('{"prompt":"Current edited question"}', encoding="utf-8")
    sources = [path, journal]
    if state == "completed":
        sources.append(tmp_path / "logs/task_responses.csv")
    original = {source: source.read_bytes() for source in sources}
    assert has_captured_participant_results(tmp_path)
    answer, = _rows(_workbook(tmp_path), "Task Answers")
    assert (answer["Question"], answer["Answer"], answer["Task"]) == (
        "Original?", "Original yes", "Original post survey",
    )
    assert answer["Phase"] == "After"
    assert answer["Session Aborted"] == expected
    assert answer["Run Aborted"] == "No"  # A later task error did not abort completed playback.
    assert {source: source.read_bytes() for source in sources} == original
    assert set(sources) <= set(participant_results_source_paths(tmp_path))


def test_condition_fixation_modes_use_matching_numbered_capture(tmp_path, results):
    plan, summary = results
    summary.runtime_metadata = RuntimeMetadata(engine_name="stub", test_mode=True, pilot_mode=True)
    capture_participant_results(tmp_path, plan, summary)
    row, = _rows(_workbook(tmp_path, [_history(plan, summary)]), "Fixation by Condition")
    assert row["Test Mode"] == "Yes"
    assert row["Pilot Mode"] == "Yes"
    assert row["Test Participant"] == "No"
    assert row["Include In Analysis"] == "Yes"


@pytest.mark.parametrize("visit", [1, None])
def test_legacy_csv_only_answers_survive_archival_and_freezing_retry(tmp_path, results, visit):
    plan, summary = results
    summary.participant_session_number = visit
    output = tmp_path / "runs/original"
    write_session_artifacts(output, plan, summary)
    history = _history(plan, summary, output_dir="runs/original",
                       participant_session_number="" if visit is None else str(visit))
    _write_csv(tmp_path / "logs/session_condition_history.csv",
               SESSION_CONDITION_HISTORY_HEADER,
               [[history.get(column, "") for column in SESSION_CONDITION_HISTORY_HEADER]])

    def research_rows():
        workbook = _workbook(tmp_path, [history])
        try:
            return {
                sheet: [{key: value for key, value in row.items() if key != "Source"}
                        for row in _rows(workbook, sheet)]
                for sheet in ("Demographics", "Fixation Responses", "Task Answers")
            }
        finally:
            workbook.close()

    original = research_rows()
    retained, = freeze_legacy_participant_results(tmp_path)
    snapshot = retained.read_bytes()
    assert b"frame_intervals" not in snapshot
    (output / "task_responses.csv").unlink()
    assert research_rows() == original
    assert freeze_legacy_participant_results(tmp_path) == [retained]
    assert retained.read_bytes() == snapshot


def test_workbook_opens_with_measures_before_provenance(tmp_path, results):
    plan, summary = results
    capture_participant_results(tmp_path, plan, summary)
    workbook = _workbook(tmp_path, [_history(plan, summary)])
    try:
        assert workbook.active.title == "Fixation by Condition"
        headers = list(next(workbook["Task Answers"].values))
        assert headers.index("Answer") < headers.index("Session ID")
        assert headers.index("Reaction Time (s)") < headers.index("Realized Option Order")
        assert workbook["Task Answers"].freeze_panes == "C2"
    finally:
        workbook.close()


def test_question_answers_precede_task_activity_without_false_missing_answers(tmp_path, results):
    plan, summary = results
    answer = summary.run_results[0].task_responses[0]
    instruction = answer.model_copy(update={
        "question_id": None, "selected_option_ids": [], "response_kind": TaskResponseKind.KEY,
        "key": "space",
    })
    interval = instruction.model_copy(update={
        "response_index": 1, "response_kind": TaskResponseKind.NONE, "key": None,
    })
    answer = answer.model_copy(update={"response_index": 2})
    summary.run_results[0].task_responses = [instruction, interval, answer]
    capture_participant_results(tmp_path, plan, summary)
    workbook = _workbook(tmp_path)
    try:
        rows = _rows(workbook, "Task Answers")
        assert [row["Record Type"] for row in rows] == [
            "Question answer", "Task activity", "Task activity",
        ]
        assert rows[0]["Answer"] == "Original yes"
        assert [row["Status"] for row in rows] == ["Answered", "Completed", "Completed"]
        assert [row["Response Index"] for row in rows] == [2, 0, 1]
    finally:
        workbook.close()


def test_appending_visit_centers_existing_and_new_results_on_every_sheet(tmp_path, results):
    plan, summary = results
    capture_participant_results(tmp_path, plan, summary)
    append_session_condition_history(tmp_path, plan, summary)
    path = write_participant_summary(tmp_path)
    workbook = load_workbook(path)
    try:
        for sheet in workbook:
            for index in range(1, sheet.max_column + 1):
                column = sheet.column_dimensions[get_column_letter(index)]
                assert column.alignment.horizontal == "center"
                assert column.alignment.vertical == "center"
                alignment = copy(column.alignment)
                alignment.horizontal = "left"
                alignment.vertical = "top"
                column.alignment = alignment
            for row in sheet:
                for cell in row:
                    if cell.value is not None:
                        assert cell.alignment.horizontal == "center"
                        assert cell.alignment.vertical == "center"
                        assert cell.alignment.wrap_text
                        alignment = copy(cell.alignment)
                        alignment.horizontal = "left"
                        alignment.vertical = "top"
                        cell.alignment = alignment
        workbook.save(path)
    finally:
        workbook.close()

    second = summary.model_copy(deep=True)
    second.participant_session_number = 2
    for run in second.run_results:
        run.participant_session_number = 2
    capture_participant_results(tmp_path, plan, second)
    append_session_condition_history(tmp_path, plan, second)
    saved = load_workbook(path)
    try:
        answers = _rows(saved, "Task Answers")
        assert {row["Session Number"] for row in answers} == {1, 2}
        assert [row["Answer"] for row in answers] == ["Original yes", "Original yes"]
        assert all(row["Reaction Time (s)"] == 0.325 for row in answers)
        for sheet in saved:
            for index in range(1, sheet.max_column + 1):
                column = sheet.column_dimensions[get_column_letter(index)]
                assert column.alignment.horizontal == "center"
                assert column.alignment.vertical == "center"
                assert column.alignment.wrap_text
            for row in sheet:
                for cell in row:
                    if cell.value is not None:
                        assert cell.alignment.horizontal == "center"
                        assert cell.alignment.vertical == "center"
                        assert cell.alignment.wrap_text
    finally:
        saved.close()


def test_longer_appended_answers_refit_columns_and_wrapped_rows(tmp_path, results):
    plan, summary = results
    capture_participant_results(tmp_path, plan, summary)
    append_session_condition_history(tmp_path, plan, summary)
    path = write_participant_summary(tmp_path)
    before = load_workbook(path)
    try:
        sheet = before["Task Answers"]
        headings = {cell.value: cell.column for cell in sheet[1]}
        old_widths = {header: sheet.column_dimensions[get_column_letter(headings[header])].width
                      for header in ("Question", "Answer")}
    finally:
        before.close()

    second_plan = plan.model_copy(deep=True)
    prompt = "Describe the experience in detail. " * 15 + "\nInclude any other observations."
    second_plan.ordered_entries()[0].pre_tasks[0].steps[0].questions = [TaskQuestion(
        question_id="choice", kind="short_text", prompt=prompt,
    )]
    second = summary.model_copy(deep=True)
    second.participant_session_number = 2
    answer = "An extended participant answer with all details preserved. " * 8
    for run in second.run_results:
        run.participant_session_number = 2
        run.task_responses[0].selected_option_ids = []
        run.task_responses[0].response_kind = TaskResponseKind.TEXT
        run.task_responses[0].text_value = answer
    capture_participant_results(tmp_path, second_plan, second)
    append_session_condition_history(tmp_path, second_plan, second)

    after = load_workbook(path)
    try:
        sheet = after["Task Answers"]
        records = _rows(after, "Task Answers")
        assert {row["Session Number"]: row["Answer"] for row in records} == {
            1: "Original yes", 2: answer,
        }
        new_row = next(index for index, row in enumerate(records, 2)
                       if row["Session Number"] == 2)
        assert records[new_row - 2]["Question"] == prompt
        for header in ("Question", "Answer"):
            assert sheet.column_dimensions[get_column_letter(headings[header])].width > (
                old_widths[header]
            )
        assert sheet.row_dimensions[new_row].height > 36
        assert sheet.row_dimensions[new_row].height <= 409
        assert DEMOGRAPHIC_ANSWERS_SHEET_NAME in after.sheetnames
        assert len(after.sheetnames) == 7
    finally:
        after.close()
