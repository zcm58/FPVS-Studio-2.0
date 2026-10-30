"""Original post-question journals survive completion, partial failure, and projection errors."""

from __future__ import annotations

import csv
import json
from uuid import uuid4

import pytest
from tests.unit.runtime_launcher_helpers import StubEngine

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.post_questions import make_post_questionnaire, make_yes_no_question
from fpvs_studio.core.serialization import save_project_file
from fpvs_studio.core.task_models import (
    TaskBinding,
    TaskModule,
    TaskQuestion,
    TaskResponseRecord,
    TaskStep,
    TaskStepResult,
)
from fpvs_studio.engines.base import TaskEngineInput
from fpvs_studio.runtime.post_condition_responses import (
    PostConditionResponseRecorder,
    rebuild_post_condition_responses,
)
from fpvs_studio.runtime.run_worker import RuntimeWorker
from fpvs_studio.runtime.task_runner import (
    TaskResponseCheckpoint,
    question_response_is_valid,
    read_task_response_journal,
)

PRIVATE_ANSWER = "private research answer \"quoted\", café\nnext line"
PROMPT = 'Did you see a "fearful", face?\n怖い'


def _question_project(project, *, repeats=False, earlier_post=False):
    question = make_yes_no_question(PROMPT, question_id="seen-fear")
    detail = TaskQuestion(
        question_id="detail", kind="short_text", prompt="Describe anything else.", required=True,
    )
    module = make_post_questionnaire([question, detail], task_id="questions")
    project.task_modules = [module]
    first = project.conditions[0].model_copy(deep=True, update={
        "stream_duration_seconds": 30, "presentation_count": 3 if repeats else 1,
        "post_task_bindings": [TaskBinding(task_id="questions")],
    })
    project.conditions = [first]
    if repeats:
        project.conditions.append(first.model_copy(deep=True, update={
            "condition_id": "second", "name": "Second", "order_index": 1,
            "presentation_count": 2, "trigger_code": 2,
        }))
    if earlier_post:
        project.task_modules.insert(0, TaskModule(
            task_id="earlier-post", name="Existing modifier endpoint",
            steps=[TaskStep(step_id="endpoint", kind="instruction", text="Existing post task",
                            continue_key="space")],
        ))
        for condition in project.conditions:
            condition.post_task_bindings.insert(0, TaskBinding(task_id="earlier-post"))
    return ProjectFile.model_validate(project.model_dump())


class QuestionEngine(StubEngine):
    def __init__(self, captures, *, failure=None):
        super().__init__(captures)
        self.failure = failure

    def render_task_step(self, step, project_root):
        self._captures.setdefault("task_steps", []).append((step.task_id, step.question_id))
        if step.task_id == "earlier-post":
            if self.failure == "earlier_abort":
                return TaskEngineInput(aborted=True)
            if self.failure == "earlier_error":
                raise RuntimeError("Earlier modifier failed")
            return TaskEngineInput(key="space")
        assert step.submission_mode == "explicit"
        assert step.submit_label == "Continue"
        if step.question_id == "detail":
            if self.failure == "question_abort":
                return TaskEngineInput(aborted=True, reaction_time_s=0.4)
            if self.failure == "question_error":
                raise RuntimeError("Later questionnaire screen failed")
            return TaskEngineInput(text_value=PRIVATE_ANSWER, reaction_time_s=0.7)
        return TaskEngineInput(selected_item_ids=("no",), reaction_time_s=0.25)


def _execute(root, plan, engine, *, mode="compact", visit=1):
    return RuntimeWorker(engine).execute_session(
        root, plan, root / "runs" / f"visit-{visit}",
        participant_number="007", participant_session_number=visit,
        runtime_options={"experiment_test_mode": True, "export_mode": mode},
    )


def _rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _columns(row):
    answer = next(key for key in row if key.startswith(PROMPT))
    detail = next(key for key in row if key.startswith("Describe anything else."))
    return answer, detail


def _journal_paths(root):
    contexts = sorted((root / "logs/post-condition-responses").glob("*.json"))
    return contexts, {
        root / entry["journal_path"]
        for path in contexts for entry in json.loads(path.read_text(encoding="utf-8"))["entries"]
    }


@pytest.mark.parametrize("mode", ["full", "compact"])
def test_repeated_presentations_keep_original_context_and_answers_after_completion(
    sample_project, sample_project_root, mode, caplog,
):
    project = _question_project(sample_project, repeats=True)
    plan = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60)
    captures = {}
    summary = _execute(sample_project_root, plan, QuestionEngine(captures), mode=mode)
    assert not summary.aborted
    assert len(summary.run_results) == 5
    assert all(len(run.task_responses) == 2 for run in summary.run_results)
    assert all(run.task_responses[0].valid and run.task_responses[0].correct is None
               and run.task_responses[0].score is None for run in summary.run_results)
    assert all(response.repetition_index == 0 for run in summary.run_results
               for response in run.task_responses)
    path = sample_project_root / "post_condition_responses.csv"
    rows = _rows(path)
    assert len(rows) == 5
    answer, detail = _columns(rows[0])
    assert all(row[answer] == "No" and row[detail] == PRIVATE_ANSWER for row in rows)
    assert all(row["FPVS stream completed"] == "Yes" for row in rows)
    assert [row["Presentation"] for row in rows] == ["1", "1", "2", "2", "3"]
    contexts, journals = _journal_paths(sample_project_root)
    assert len(contexts) == 1
    assert len(journals) == (5 if mode == "full" else 1)
    assert sum(len(read_task_response_journal(journal)) for journal in journals) == 10
    assert all(journal.is_file() for journal in journals)
    assert PRIVATE_ANSWER not in contexts[0].read_text(encoding="utf-8")
    assert PRIVATE_ANSWER not in caplog.text
    assert PRIVATE_ANSWER not in (sample_project_root / "logs/participant_summary.csv").read_text(
        encoding="utf-8",
    )
    assert not list((sample_project_root / "logs/.condition-recovery").glob("*.plan.json"))
    project.conditions[0].name = "Renamed after collection"
    project.task_modules[0].steps[0].questions[0].prompt = "Edited after collection"
    save_project_file(project, sample_project_root / "project.json")
    assert rebuild_post_condition_responses(sample_project_root) == path
    assert _rows(path) == rows
    assert (sample_project_root / "runs").exists() == (mode == "full")


@pytest.mark.parametrize("mode", ["full", "compact"])
def test_question_abort_keeps_prior_no_answer_and_partial_original_journal(
    sample_project, sample_project_root, mode,
):
    project = _question_project(sample_project)
    project.task_modules[0].steps[0].questions.append(
        make_yes_no_question("Later third question", question_id="later"),
    )
    plan = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60)
    summary = _execute(sample_project_root, plan, QuestionEngine({}, failure="question_abort"),
                       mode=mode)
    assert summary.aborted
    run, = summary.run_results
    assert not run.aborted
    assert run.completed_frames == 1800
    assert run.task_flow_aborted and not run.task_flow_completed
    row, = _rows(sample_project_root / "post_condition_responses.csv")
    answer, detail = _columns(row)
    assert row[answer] == "No"
    assert row[f"Status: {answer}"] == "answered"
    assert row[detail] == ""
    assert row[f"Status: {detail}"] == "aborted"
    assert row["FPVS stream completed"] == "Yes"
    later = next(key for key in row if key.startswith("Later third question"))
    assert row[later] == ""
    assert row[f"Status: {later}"] == "not_presented"
    _, journals = _journal_paths(sample_project_root)
    assert sum(len(read_task_response_journal(path)) for path in journals) == 2


@pytest.mark.parametrize("mode", ["full", "compact"])
def test_mid_questionnaire_exception_reconciles_submitted_answers_into_raw_exports(
    sample_project, sample_project_root, mode,
):
    plan = compile_session_plan(_question_project(sample_project), project_root=sample_project_root,
                                refresh_hz=60)
    with pytest.raises(RuntimeError, match="Later questionnaire screen failed"):
        _execute(sample_project_root, plan, QuestionEngine({}, failure="question_error"), mode=mode)
    row, = _rows(sample_project_root / "post_condition_responses.csv")
    answer, detail = _columns(row)
    assert row[answer] == "No"
    assert row[f"Status: {detail}"] == "interrupted"
    assert row["Session status"] == "error"
    raw_path = (sample_project_root / "runs/visit-1/task_responses.csv" if mode == "full"
                else sample_project_root / "logs/task_responses.csv")
    raw, = _rows(raw_path)
    assert raw["question_id"] == "seen-fear"
    assert raw["selected_option_ids"] == "no"
    if mode == "full":
        run_path = sample_project_root / "runs/visit-1" / plan.ordered_entries()[0].run_id
        per_run, = _rows(run_path / "task_responses.csv")
        assert per_run["question_id"] == "seen-fear"
        assert per_run["selected_option_ids"] == "no"
        run_summary = json.loads((run_path / "run_summary.json").read_text(encoding="utf-8"))
        assert run_summary["task_flow_aborted"] is True
        assert run_summary["task_abort_stage"] == "post_condition"
    _, journals = _journal_paths(sample_project_root)
    assert sum(len(read_task_response_journal(path)) for path in journals) == 1


@pytest.mark.parametrize("failure", ["earlier_abort", "earlier_error"])
@pytest.mark.parametrize("mode", ["full", "compact"])
def test_earlier_post_activity_failure_has_a_not_presented_question_row(
    sample_project, sample_project_root, failure, mode,
):
    plan = compile_session_plan(_question_project(sample_project, earlier_post=True),
                                project_root=sample_project_root, refresh_hz=60)
    engine = QuestionEngine({}, failure=failure)
    if failure == "earlier_error":
        with pytest.raises(RuntimeError, match="Earlier modifier failed"):
            _execute(sample_project_root, plan, engine, mode=mode)
    else:
        assert _execute(sample_project_root, plan, engine, mode=mode).aborted
    row, = _rows(sample_project_root / "post_condition_responses.csv")
    answer, detail = _columns(row)
    assert row[answer] == row[detail] == ""
    assert row[f"Status: {answer}"] == row[f"Status: {detail}"] == "not_presented"
    assert row["FPVS stream completed"] == "Yes"


@pytest.mark.parametrize("mode", ["full", "compact"])
def test_locked_derived_csv_warns_without_losing_original_answers(
    sample_project, sample_project_root, monkeypatch, mode,
):
    plan = compile_session_plan(_question_project(sample_project), project_root=sample_project_root,
                                refresh_hz=60)
    with monkeypatch.context() as patch:
        def locked(_recorder):
            raise PermissionError("Excel has the derived CSV open")
        patch.setattr(PostConditionResponseRecorder, "write_csv", locked)
        summary = _execute(sample_project_root, plan, QuestionEngine({}), mode=mode)
    assert not summary.aborted
    assert any("Close post_condition_responses.csv in Excel" in warning
               and "Rebuild responses" in warning for warning in summary.warnings)
    _, journals = _journal_paths(sample_project_root)
    assert sum(len(read_task_response_journal(path)) for path in journals) == 2
    rebuild_post_condition_responses(sample_project_root)
    row, = _rows(sample_project_root / "post_condition_responses.csv")
    answer, detail = _columns(row)
    assert row[answer] == "No" and row[detail] == PRIVATE_ANSWER


def test_compact_retained_journals_use_distinct_execution_identity_without_visit_number(
    sample_project, sample_project_root,
):
    plan = compile_session_plan(_question_project(sample_project), project_root=sample_project_root,
                                refresh_hz=60)
    _execute(sample_project_root, plan, QuestionEngine({}), visit=None)
    _execute(sample_project_root, plan, QuestionEngine({}), visit=None)
    contexts, journals = _journal_paths(sample_project_root)
    assert len(contexts) == len(journals) == 2
    assert sum(len(read_task_response_journal(path)) for path in journals) == 4
    rows = _rows(sample_project_root / "post_condition_responses.csv")
    assert len(rows) == 2
    assert len({row["Execution ID"] for row in rows}) == 2


def test_context_initialization_failure_prevents_participant_screens(
    sample_project, sample_project_root, monkeypatch,
):
    plan = compile_session_plan(_question_project(sample_project), project_root=sample_project_root,
                                refresh_hz=60)
    def unavailable(*_args, **_kwargs):
        raise OSError("Question context cannot be persisted")
    monkeypatch.setattr(PostConditionResponseRecorder, "__init__", unavailable)
    captures = {}
    with pytest.raises(OSError, match="context cannot be persisted"):
        _execute(sample_project_root, plan, QuestionEngine(captures))
    assert "open_count" not in captures
    assert "task_steps" not in captures
    assert not (sample_project_root / "post_condition_responses.csv").exists()


def test_module_context_failure_prevents_question_screen_and_keeps_completed_stream(
    sample_project, sample_project_root, monkeypatch,
):
    plan = compile_session_plan(_question_project(sample_project), project_root=sample_project_root,
                                refresh_hz=60)
    def unavailable(*_args, **_kwargs):
        raise OSError("Question module intent cannot be persisted")
    monkeypatch.setattr(PostConditionResponseRecorder, "start_module", unavailable)
    captures = {}
    with pytest.raises(OSError, match="intent cannot be persisted"):
        _execute(sample_project_root, plan, QuestionEngine(captures))
    assert len(captures["run_ids"]) == 1
    assert "task_steps" not in captures
    row, = _rows(sample_project_root / "post_condition_responses.csv")
    answer, detail = _columns(row)
    assert row[f"Status: {answer}"] == row[f"Status: {detail}"] == "not_presented"
    assert row["FPVS stream completed"] == "Yes"


def test_start_gate_abort_records_no_completed_stream_and_not_presented_questions(
    sample_project, sample_project_root,
):
    plan = compile_session_plan(_question_project(sample_project), project_root=sample_project_root,
                                refresh_hz=60)
    summary = _execute(sample_project_root, plan, QuestionEngine({"abort_on_transition": True}))
    assert summary.aborted
    assert not summary.run_results
    row, = _rows(sample_project_root / "post_condition_responses.csv")
    answer, detail = _columns(row)
    assert row["FPVS stream completed"] == "No"
    assert row[f"Status: {answer}"] == row[f"Status: {detail}"] == "not_presented"


def test_later_export_failure_retains_completed_answers_and_records_session_error(
    sample_project, sample_project_root, monkeypatch,
):
    plan = compile_session_plan(_question_project(sample_project), project_root=sample_project_root,
                                refresh_hz=60)
    def unavailable(_root):
        raise PermissionError("Generic report is locked")
    monkeypatch.setattr("fpvs_studio.runtime.run_worker.write_participant_summary", unavailable)
    with pytest.raises(PermissionError, match="Generic report is locked"):
        _execute(sample_project_root, plan, QuestionEngine({}))
    row, = _rows(sample_project_root / "post_condition_responses.csv")
    answer, detail = _columns(row)
    assert row[answer] == "No" and row[detail] == PRIVATE_ANSWER
    assert row["FPVS stream completed"] == "Yes"
    assert row["Session status"] == "error"
    _, journals = _journal_paths(sample_project_root)
    assert sum(len(read_task_response_journal(path)) for path in journals) == 2


def test_rating_engine_selection_projects_its_canonical_numeric_value(
    sample_project, sample_project_root,
):
    project = _question_project(sample_project)
    project.task_modules = [make_post_questionnaire([TaskQuestion(
        question_id="confidence", kind="rating", prompt="Confidence?",
        min_value=1, max_value=5, step=1,
    )], task_id="questions")]
    plan = compile_session_plan(project, project_root=sample_project_root, refresh_hz=60)
    class RatingEngine(StubEngine):
        def render_task_step(self, step, project_root):
            assert step.response_kind == "rating"
            return TaskEngineInput(selected_item_ids=("rating-3",), reaction_time_s=0.5)
    summary = _execute(sample_project_root, plan, RatingEngine({}))
    record, = summary.run_results[0].task_responses
    assert record.selected_option_ids == ["rating-3"]
    assert record.numeric_value == 3
    row, = _rows(sample_project_root / "post_condition_responses.csv")
    answer = next(key for key in row if key.startswith("Confidence?"))
    assert row[answer] == "3.0"
    assert row[f"Status: {answer}"] == "answered"


def test_missing_completed_journal_preserves_prior_view_until_original_evidence_is_restored(
    sample_project, sample_project_root,
):
    plan = compile_session_plan(_question_project(sample_project), project_root=sample_project_root,
                                refresh_hz=60)
    _execute(sample_project_root, plan, QuestionEngine({}))
    path = sample_project_root / "post_condition_responses.csv"
    before = path.read_bytes()
    _, journals = _journal_paths(sample_project_root)
    journal, = journals
    original = journal.read_bytes()
    journal.unlink()
    with pytest.raises(ValueError, match="Restore the original task journal"):
        rebuild_post_condition_responses(sample_project_root)
    assert path.read_bytes() == before
    journal.write_bytes(original)
    assert rebuild_post_condition_responses(sample_project_root) == path
    assert path.read_bytes() == before


def _record(index=0):
    return TaskResponseRecord(
        response_index=index, task_id="questions", step_id="questions", phase="post_condition",
        condition_id="faces", run_id="run", block_index=0, global_order_index=0,
        repetition_index=0, question_id="seen-fear", selected_option_ids=["no"],
    )


def test_journal_reader_accepts_valid_json_without_newline_and_retains_prefix_after_torn_tail(
    tmp_path, caplog,
):
    path = tmp_path / "original.jsonl"
    assert read_task_response_journal(path) == []
    first, second = _record(), _record(1)
    path.write_bytes(first.model_dump_json().encode())
    assert read_task_response_journal(path) == [first]
    path.write_bytes(first.model_dump_json().encode() + b"\n" + second.model_dump_json().encode()
                     + b'\n{"text_value":"unfinished private answer')
    assert read_task_response_journal(path) == [first, second]
    assert "incomplete final record" in caplog.text
    assert "unfinished private answer" not in caplog.text


def test_middle_corrupt_journal_is_explicit_and_never_rewritten(tmp_path):
    path = tmp_path / "original.jsonl"
    original = (
        _record().model_dump_json() + "\nnot-json\n" + _record(1).model_dump_json()
    ).encode()
    path.write_bytes(original)
    with pytest.raises(ValueError, match="record 2 is invalid"):
        read_task_response_journal(path)
    assert path.read_bytes() == original


def test_complete_but_invalid_last_record_without_newline_is_not_treated_as_torn_tail(tmp_path):
    path = tmp_path / "original.jsonl"
    path.write_text(_record().model_dump_json() + '\n{"text_value":"private"}', encoding="utf-8")
    with pytest.raises(ValueError, match="record 2 is invalid"):
        read_task_response_journal(path)


def test_checkpoint_reconciliation_keeps_all_attempts_and_rejects_conflicting_identity(tmp_path):
    checkpoint = TaskResponseCheckpoint(tmp_path / "original.jsonl")
    first, second = _record(), _record(1)
    checkpoint.append(first)
    checkpoint.append(second)
    assert checkpoint.reconcile_run_responses("run", [first]) == [first, second]
    with pytest.raises(ValueError, match="conflicting response identities"):
        checkpoint.reconcile_run_responses("run", [
            first.model_copy(update={"text_value": "other"}),
        ])


def test_wide_projection_refuses_multiple_attempts_while_original_journal_retains_them(
    sample_project, sample_project_root,
):
    plan = compile_session_plan(_question_project(sample_project), project_root=sample_project_root,
                                refresh_hz=60)
    entry, = plan.ordered_entries()
    path = sample_project_root / "logs/original.jsonl"
    recorder = PostConditionResponseRecorder(
        sample_project_root, plan, participant_number="007", participant_session_number=1,
        execution_id=uuid4().hex, journal_paths={entry.run_id: path},
    )
    recorder.start_entry(entry.run_id)
    recorder.start_module(entry.run_id, "questions")
    checkpoint = TaskResponseCheckpoint(path)
    checkpoint.append(_record().model_copy(update={"run_id": entry.run_id}))
    checkpoint.append(_record(1).model_copy(update={"run_id": entry.run_id, "attempt_index": 1}))
    recorder.finish_entry(entry.run_id, state="error")
    recorder.finish_session(state="error")
    with pytest.raises(ValueError, match="Repeated question attempts"):
        recorder.write_csv()
    assert len(read_task_response_journal(path)) == 2


def test_preview_validation_accepts_no_and_requires_deliberate_answer_without_collection(tmp_path):
    question = make_yes_no_question("Seen?", question_id="seen")
    assert not question_response_is_valid(question, TaskStepResult())
    assert question_response_is_valid(question, TaskStepResult(selected_option_ids=["no"]))
    assert list(tmp_path.iterdir()) == []
