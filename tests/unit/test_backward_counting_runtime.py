"""Headless counting flow, endpoint estimates, and durable participant records."""

from __future__ import annotations

import csv
import json

import pytest
from tests.unit.runtime_launcher_helpers import StubEngine

from fpvs_studio.core.backward_counting import (
    COUNTING_ENDPOINT_QUESTION_ID,
    COUNTING_INTERVAL_STEP_ID,
    COUNTING_READY_STEP_ID,
    COUNTING_REPORT_STEP_ID,
    create_backward_counting_baseline_task,
    create_backward_counting_report_task,
    create_backward_counting_start_task,
)
from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.execution import FrameIntervalRecord
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.task_models import BackwardCountingRole, TaskBinding, TaskOccurrence
from fpvs_studio.engines.base import ResolvedTaskStep, TaskEngineInput
from fpvs_studio.engines.psychopy_tasks import _completed_input, _handle_keys
from fpvs_studio.runtime.run_worker import RuntimeWorker
from fpvs_studio.runtime.session_export import (
    COMPACT_TASK_RESPONSES_HEADER,
    compact_task_checkpoint_path,
)


class CountingEngine(StubEngine):
    def __init__(self, plan, *, baseline_steps=24, load_difference=130,
                 abort_at=None, invalid_endpoint=False, fail_at_report=False):
        super().__init__({})
        self.plan = plan
        self.baseline_steps = baseline_steps
        self.load_difference = load_difference
        self.abort_at = abort_at
        self.invalid_endpoint = invalid_endpoint
        self.fail_at_report = fail_at_report
        self.events = []
        self.entry_index = 0

    def render_task_step(self, step, project_root):
        self.events.append((step.task_id, step.step_id))
        entry = self.plan.ordered_entries()[self.entry_index]
        module = next(m for m in [*entry.pre_tasks, *entry.post_tasks]
                      if m.task_id == step.task_id)
        spec = module.backward_counting
        role = spec.role
        if self.abort_at == (role, step.step_id):
            return TaskEngineInput(aborted=True, reaction_time_s=0.2)
        if step.step_id == COUNTING_READY_STEP_ID:
            return TaskEngineInput(key="space", reaction_time_s=0.4)
        if step.step_id == COUNTING_INTERVAL_STEP_ID:
            return TaskEngineInput(reaction_time_s=step.duration_s + 0.01)
        assert step.question_id == COUNTING_ENDPOINT_QUESTION_ID
        if role == BackwardCountingRole.LOAD_REPORT and self.fail_at_report:
            raise RuntimeError("Simulated display failure")
        if self.invalid_endpoint:
            return (TaskEngineInput() if self.invalid_endpoint == "missing"
                    else TaskEngineInput(numeric_value=100.5, text_value="100.5"))
        difference = (self.baseline_steps * spec.subtraction_step
                      if role == BackwardCountingRole.BASELINE else self.load_difference)
        endpoint = spec.start_number - difference
        return TaskEngineInput(numeric_value=endpoint, text_value=str(endpoint),
                               reaction_time_s=0.7)

    def show_transition_screen(self, **kwargs):
        self.events.append(("transition", self.entry_index))
        return super().show_transition_screen(**kwargs)

    def run_condition(self, run_spec, project_root, **kwargs):
        self.events.append(("stream", run_spec.condition.condition_id))
        result = super().run_condition(run_spec, project_root, **kwargs)
        if self.abort_at == "stream":
            return result.model_copy(update={"aborted": True, "completed_frames": 1,
                                              "abort_reason": "Stream aborted"})
        return result.model_copy(update={"frame_intervals": [
            FrameIntervalRecord(frame_index=i, interval_s=1 / run_spec.display.refresh_hz)
            for i in range(run_spec.display.total_frames)
        ]})

    def show_condition_feedback_screen(self, **kwargs):
        self.events.append(("feedback", self.entry_index))
        self.entry_index += 1
        return False


def _setup(tmp_path, *, load_first=False):
    scaffold = create_project(tmp_path, "Counting study",
                              experiment_category=ExperimentCategory.COGNITIVE_LOAD_FPVS)
    project = scaffold.project
    project.settings.fixation_task.accuracy_task_enabled = True
    project.settings.fixation_task.participant_tutorial_enabled = False
    plan = compile_session_plan(project, refresh_hz=60, project_root=scaffold.project_root,
                                random_seed=123,
                                condition_ids=["condition-1-load"] if load_first else None)
    return scaffold.project_root, plan


def _execute(root, plan, engine, mode):
    output = root / "runs" / "P007_session01"
    return RuntimeWorker(engine).execute_session(
        root, plan, output, participant_number="007", participant_session_number=1,
        runtime_options={
            "serial_enabled": False, "export_mode": mode,
            "experiment_test_mode": True,
        },
        relative_output_dir="runs/P007_session01",
    )


def _counting_rows(summary):
    return [r for run in summary.run_results for r in run.task_responses
            if r.backward_counting is not None]


@pytest.mark.parametrize("mode", ["full", "compact"])
def test_six_variants_baseline_once_immediate_report_and_private_exports(tmp_path, mode):
    root, plan = _setup(tmp_path)
    engine = CountingEngine(plan, load_difference=131)
    summary = _execute(root, plan, engine, mode)

    assert not summary.aborted
    assert summary.completed_condition_count == 6
    rows = _counting_rows(summary)
    reports = [r for r in rows if r.question_id == COUNTING_ENDPOINT_QUESTION_ID]
    assert len(reports) == 4
    baseline = reports[0].backward_counting
    assert baseline.role == BackwardCountingRole.BASELINE
    assert baseline.interval_seconds == 120
    assert baseline.estimated_steps == 24
    assert baseline.steps_per_second == pytest.approx(0.2)
    assert baseline.observed_interval_seconds == pytest.approx(120.01)
    for response in reports[1:]:
        counting = response.backward_counting
        assert counting.interval_seconds == 90
        assert counting.observed_interval_seconds == pytest.approx(90)
        assert counting.estimated_steps == pytest.approx(131 / 13)
        assert counting.subtraction_remainder == 1
        assert counting.steps_per_second == pytest.approx((131 / 13) / 90)
        assert counting.baseline_rate_ratio == pytest.approx(((131 / 13) / 90) / 0.2)
        assert counting.duration_basis == "planned"
        assert response.correct is None and response.score is None
    for index, event in enumerate(engine.events):
        if event[0] != "stream":
            continue
        if "no-load" in event[1]:
            assert engine.events[index + 1][0] == "feedback"
        else:
            assert engine.events[index - 1][1] == COUNTING_READY_STEP_ID
            assert engine.events[index + 1][1] == COUNTING_REPORT_STEP_ID
            assert engine.events[index + 2][0] == "feedback"
    output = root / "runs" / "P007_session01"
    response_path = (output if mode == "full" else root / "logs") / "task_responses.csv"
    with response_path.open(encoding="utf-8", newline="") as handle:
        exported = list(csv.DictReader(handle))
    assert len(exported) == 9
    assert exported[2]["backward_counting_steps_per_second"] == "0.2"
    assert "backward_counting" not in (root / "logs" / "participant_summary.csv").read_text()
    if mode == "full":
        assert "backward_counting" not in (output / "session_summary.json").read_text()
        for entry in plan.ordered_entries():
            if not entry.post_tasks:
                continue
            journal = [json.loads(line) for line in
                       (output / entry.run_id / "task_responses.jsonl").read_text().splitlines()]
            start = [row for row in journal
                     if row["backward_counting"]["role"] == "load_start"]
            completion = [row["backward_counting"]["interval_completed"] for row in start]
            assert completion == [False, True]
    else:
        assert not output.exists()
        assert not (root / "logs" / ".task-response-checkpoints").exists()


@pytest.mark.parametrize("abort_at", [
    (BackwardCountingRole.BASELINE, COUNTING_INTERVAL_STEP_ID),
    (BackwardCountingRole.BASELINE, COUNTING_REPORT_STEP_ID),
    (BackwardCountingRole.LOAD_START, COUNTING_READY_STEP_ID),
    "stream",
    (BackwardCountingRole.LOAD_REPORT, COUNTING_REPORT_STEP_ID),
])
def test_abort_retains_start_interval_and_available_baseline(tmp_path, abort_at):
    root, plan = _setup(tmp_path, load_first=True)
    summary = _execute(root, plan, CountingEngine(plan, abort_at=abort_at), "compact")
    assert summary.aborted
    rows = _counting_rows(summary)
    assert rows and all(row.backward_counting.start_number > 0 for row in rows)
    if abort_at == (BackwardCountingRole.LOAD_REPORT, COUNTING_REPORT_STEP_ID):
        assert rows[-1].backward_counting.interval_completed
        assert rows[-1].backward_counting.endpoint is None
        assert rows[-1].backward_counting.estimated_steps is None
    if abort_at == "stream":
        assert not rows[-1].backward_counting.interval_completed
    with (root / "logs" / "task_responses.csv").open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == len(rows)


def test_exception_during_report_preserves_compact_interval_checkpoint(tmp_path):
    root, plan = _setup(tmp_path, load_first=True)
    with pytest.raises(RuntimeError, match="Simulated display failure"):
        _execute(root, plan, CountingEngine(plan, fail_at_report=True), "compact")
    journal_path = compact_task_checkpoint_path(root, participant_number="007",
        session_id=plan.session_id, participant_session_number=1)
    journal = [json.loads(line) for line in journal_path.read_text().splitlines()]
    assert journal[-1]["backward_counting"]["interval_completed"]
    assert journal[-1]["backward_counting"]["endpoint"] is None


@pytest.mark.parametrize("baseline_steps", [0, -1])
def test_nonpositive_baseline_has_no_ratio(tmp_path, baseline_steps):
    root, plan = _setup(tmp_path)
    summary = _execute(root, plan, CountingEngine(plan, baseline_steps=baseline_steps), "compact")
    load_reports = [r.backward_counting for r in _counting_rows(summary)
                    if r.backward_counting.role == BackwardCountingRole.LOAD_REPORT]
    assert all(r.baseline_rate_ratio is None for r in load_reports)
    assert all(r.baseline_steps_per_second == baseline_steps / 120 for r in load_reports)


@pytest.mark.parametrize("invalid_endpoint", [True, "missing"])
def test_invalid_endpoints_are_retained_without_estimates(tmp_path, invalid_endpoint):
    root, plan = _setup(tmp_path)
    summary = _execute(root, plan, CountingEngine(plan, invalid_endpoint=invalid_endpoint),
                       "compact")
    assert summary.aborted
    reports = [r for r in _counting_rows(summary) if r.question_id]
    assert len(reports) == 3
    expected = None if invalid_endpoint == "missing" else 100.5
    assert all(r.numeric_value == expected and not r.valid for r in reports)
    assert all(r.backward_counting.estimated_steps is None for r in reports)


def test_old_compact_response_columns_preserve_values_when_counting_is_appended(tmp_path):
    root, plan = _setup(tmp_path)
    header = [column for column in COMPACT_TASK_RESPONSES_HEADER
              if not column.startswith("backward_counting_")]
    original = dict.fromkeys(header, "")
    original.update(participant_number="old-participant", session_id="old-session",
                    text_value="A preserved answer", participant_session_number="2",
                    numeric_value="-39", reaction_time_s="0.25")
    path = root / "logs" / "task_responses.csv"
    path.parent.mkdir(exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerow(original)
    _execute(root, plan, CountingEngine(plan), "compact")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 10
    assert {column: rows[0][column] for column in header} == original
    assert rows[0]["backward_counting_endpoint"] == ""


def test_counting_modules_execute_on_ordinary_oddball_project(sample_project, sample_project_root):
    project = sample_project.model_copy(deep=True)
    project.task_modules = [create_backward_counting_baseline_task(subtraction_step=7),
                            create_backward_counting_start_task(),
                            create_backward_counting_report_task()]
    condition = project.conditions[0]
    project.conditions = [condition]
    project.settings.session.block_count = 1
    project.settings.fixation_task.accuracy_task_enabled = True
    project.settings.fixation_task.participant_tutorial_enabled = False
    condition.pre_task_bindings = [
        TaskBinding(task_id=project.task_modules[0].task_id,
                    occurrence=TaskOccurrence.FIRST_SESSION_ENTRY),
        TaskBinding(task_id=project.task_modules[1].task_id, replaces_condition_start_gate=True),
    ]
    condition.post_task_bindings = [TaskBinding(task_id=project.task_modules[2].task_id)]
    plan = compile_session_plan(project, refresh_hz=60, project_root=sample_project_root,
                                random_seed=44)
    summary = _execute(sample_project_root, plan, CountingEngine(plan, load_difference=10000),
                       "compact")
    report = _counting_rows(summary)[-1].backward_counting
    assert report.endpoint < 0
    assert report.estimated_steps == pytest.approx(10000 / 13)
    assert report.baseline_steps_per_second is None
    assert report.baseline_rate_ratio is None


def test_duration_only_screen_ignores_space_until_interval_finishes():
    class Keyboard:
        def getKeys(self, **kwargs):
            return ["space"]
    result = _handle_keys(keyboard=Keyboard(),
        step=ResolvedTaskStep(task_id="baseline", step_id=COUNTING_INTERVAL_STEP_ID,
                              kind="timed_feedback", response_kind="none", duration_s=120),
        response_text="", selected_item_ids=[])
    assert result["submitted_key"] is None


def test_numeric_renderer_rejects_fraction_without_losing_precision():
    result = _completed_input(
        ResolvedTaskStep(task_id="baseline", step_id=COUNTING_REPORT_STEP_ID,
            kind="questionnaire", response_kind="numeric", numeric_minimum=-(2**53-1),
            numeric_maximum=2**53-1, numeric_step=1),
        key="return", selected_item_ids=[], response_text="100.5", reaction_time_s=1,
        displayed_item_ids=(),
    )
    assert result is None
