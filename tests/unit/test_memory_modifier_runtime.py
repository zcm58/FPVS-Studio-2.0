"""Neutral runtime scoring, provenance, and private exports for image memory."""

from __future__ import annotations

import csv
import json

import pytest
from tests.unit.runtime_launcher_helpers import StubEngine

from fpvs_studio.core.compiler import compile_run_spec, compile_session_plan
from fpvs_studio.core.condition_modifiers import assign_modifier, create_backward_counting_modifier
from fpvs_studio.core.task_models import (
    ConditionModifierKind,
    ImageMemoryRole,
    ImageMemorySpec,
    ModifierProvenance,
    TaskDisplayItem,
    TaskItemModality,
    TaskModuleSpec,
    TaskOccurrence,
    TaskPhase,
    TaskStepKind,
    TaskStepSpec,
    TaskSubmissionMode,
)
from fpvs_studio.engines.base import TaskEngineInput
from fpvs_studio.runtime.run_worker import RuntimeWorker
from fpvs_studio.runtime.session_export import COMPACT_TASK_RESPONSES_HEADER
from fpvs_studio.runtime.task_runner import TaskResponseCheckpoint, run_task_modules

TARGETS = [f"target-{i}" for i in range(4)]
FOILS = [f"foil-{i}" for i in range(4)]
STUDY_ORDER = [TARGETS[i] for i in (2, 0, 3, 1)]
CHOICE_ORDER = [FOILS[1], TARGETS[3], TARGETS[0], FOILS[0],
                TARGETS[2], FOILS[3], FOILS[2], TARGETS[1]]


def _module(role):
    study = role == ImageMemoryRole.STUDY
    order = STUDY_ORDER if study else CHOICE_ORDER
    paths = {item_id: f"stimuli/task-assets/remember-images/{item_id}.png"
             for item_id in [*TARGETS, *FOILS]}
    step = TaskStepSpec(
        step_id="memory-study" if study else "memory-recognition",
        kind=TaskStepKind.STUDY if study else TaskStepKind.CHOICE_GRID,
        items=[TaskDisplayItem(
            item_id=item_id, modality=TaskItemModality.IMAGE, image_path=paths[item_id],
            selectable=not study, correct=item_id in TARGETS if not study else None,
            score=float(item_id in TARGETS) if not study else None,
        ) for item_id in order],
        min_selections=4 if not study else 1,
        max_selections=4 if not study else 1,
        require_response=True, continue_key="space" if study else None,
        submission_mode=TaskSubmissionMode.IMMEDIATE if study else TaskSubmissionMode.EXPLICIT,
        random_seed=32, realized_item_order=order,
    )
    return TaskModuleSpec(
        task_id=step.step_id, name="Remember four images",
        phase=TaskPhase.PRE_CONDITION if study else TaskPhase.POST_CONDITION,
        occurrence=TaskOccurrence.EVERY_ENTRY, random_seed=32, steps=[step],
        image_memory=ImageMemorySpec(
            role=role, link_id="remember-images", target_item_ids=TARGETS,
            foil_item_ids=FOILS, study_order=STUDY_ORDER, recognition_order=CHOICE_ORDER,
            image_paths=paths, random_seed=32,
        ),
        modifier=ModifierProvenance(
            modifier_id="remember-images", name="Remember four images",
            kind=ConditionModifierKind.IMAGE_MEMORY,
        ),
    )


class MemoryEngine(StubEngine):
    def __init__(self, *inputs, abort_stream=False):
        super().__init__({})
        self.inputs = list(inputs)
        self.steps = []
        self.events = []
        self.abort_stream = abort_stream

    def render_task_step(self, step, project_root):
        self.steps.append(step)
        self.events.append(step.step_id)
        return self.inputs.pop(0)

    def run_condition(self, run_spec, project_root, **kwargs):
        self.events.append("stream")
        summary = super().run_condition(run_spec, project_root, **kwargs)
        if self.abort_stream:
            return summary.model_copy(update={"aborted": True, "completed_frames": 1,
                                               "abort_reason": "Interrupted stream"})
        return summary


@pytest.mark.parametrize("hits", range(5))
def test_recognition_counts_targets_and_exact_set_without_retry(
    sample_project, sample_project_root, hits,
):
    run = compile_run_spec(sample_project, refresh_hz=60, project_root=sample_project_root)
    selected = (*TARGETS[:hits], *FOILS[:4-hits])
    engine = MemoryEngine(TaskEngineInput(selected_item_ids=selected, reaction_time_s=2.5))
    outcome = run_task_modules(engine, [_module(ImageMemoryRole.RECOGNITION)],
        project_root=sample_project_root, run_spec=run, block_index=0, global_order_index=0)
    assert not outcome.aborted
    assert len(engine.steps) == 1
    assert all(item.selectable for item in engine.steps[0].items)
    assert engine.steps[0].submission_mode == "explicit"
    response = outcome.responses[0]
    assert response.score == hits
    assert response.correct is (hits == 4)
    assert response.reaction_time_s == 2.5
    assert response.image_memory.targets_selected == hits
    assert response.image_memory.exact_set_correct is (hits == 4)
    assert response.image_memory.completed
    assert response.image_memory.target_item_ids == TARGETS
    assert response.image_memory.study_order == STUDY_ORDER
    assert response.image_memory.recognition_order == CHOICE_ORDER
    assert response.modifier.modifier_id == "remember-images"


@pytest.mark.parametrize("result", [
    TaskEngineInput(selected_item_ids=tuple(TARGETS), aborted=True),
    TaskEngineInput(selected_item_ids=tuple(TARGETS), timed_out=True),
    TaskEngineInput(selected_item_ids=(TARGETS[0], TARGETS[0], TARGETS[1], TARGETS[2])),
    TaskEngineInput(selected_item_ids=tuple([*TARGETS, *FOILS])),
    TaskEngineInput(),
])
def test_incomplete_recognition_preserves_raw_selection_without_score(
    sample_project, sample_project_root, result,
):
    run = compile_run_spec(sample_project, refresh_hz=60, project_root=sample_project_root)
    engine = MemoryEngine(result)
    journal = sample_project_root / "partial.jsonl"
    outcome = run_task_modules(engine, [_module(ImageMemoryRole.RECOGNITION)],
        project_root=sample_project_root, run_spec=run, block_index=0, global_order_index=0,
        checkpoint=TaskResponseCheckpoint(journal))
    assert outcome.aborted
    assert len(engine.steps) == 1
    response = outcome.responses[0]
    assert response.selected_option_ids == list(result.selected_item_ids)
    assert response.score is None and response.correct is None
    assert response.image_memory.targets_selected is None
    assert response.image_memory.exact_set_correct is None
    assert not response.image_memory.completed
    saved = json.loads(journal.read_text())
    assert saved["image_memory"]["targets_selected"] is None
    assert saved["selected_option_ids"] == list(result.selected_item_ids)


@pytest.mark.parametrize("mode", ["full", "compact"])
@pytest.mark.parametrize("abort_stage", [None, "study", "stream", "recognition"])
def test_memory_session_exports_keep_provenance_and_partial_data(
    sample_project, sample_project_root, tmp_path, mode, abort_stage,
):
    plan = compile_session_plan(sample_project, refresh_hz=60,
                                project_root=sample_project_root, random_seed=21)
    original = plan.ordered_entries()[0]
    entry = original.model_copy(update={
        "pre_tasks": [_module(ImageMemoryRole.STUDY)],
        "post_tasks": [_module(ImageMemoryRole.RECOGNITION)],
        "global_order_index": 0, "block_index": 0,
    })
    block = plan.blocks[0].model_copy(update={"entries": [entry],
                                             "condition_order": [entry.condition_id]})
    plan = plan.model_copy(update={"blocks": [block]})
    engine = MemoryEngine(
        TaskEngineInput(key="space", aborted=abort_stage == "study", reaction_time_s=9),
        TaskEngineInput(selected_item_ids=tuple(TARGETS), reaction_time_s=2,
                         aborted=abort_stage == "recognition"),
        abort_stream=abort_stage == "stream",
    )
    root = tmp_path / "project"
    root.mkdir()
    output = root / "runs" / "P007_session01"
    summary = RuntimeWorker(engine).execute_session(
        root, plan, output, participant_number="007", participant_session_number=1,
        runtime_options={"serial_enabled": False, "export_mode": mode},
        relative_output_dir="runs/P007_session01",
    )
    assert summary.aborted is (abort_stage is not None)
    expected = ["memory-study"]
    if abort_stage != "study":
        expected.append("stream")
    if abort_stage not in {"study", "stream"}:
        expected.append("memory-recognition")
    assert engine.events == expected
    responses = summary.run_results[0].task_responses
    assert responses[0].score is None and responses[0].correct is None
    if abort_stage is None:
        assert responses[-1].score == 4
        assert responses[-1].reaction_time_s == 2
    path = (output if mode == "full" else root / "logs") / "task_responses.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["modifier_id"] == "remember-images"
    assert rows[0]["modifier_kind"] == "image_memory"
    assert rows[0]["image_memory_target_item_ids"].split(";") == TARGETS
    assert json.loads(rows[0]["image_memory_image_paths"])[TARGETS[0]].endswith("target-0.png")
    assert rows[0]["image_memory_targets_selected"] == ""
    assert "image_memory" not in (root / "logs" / "participant_summary.csv").read_text()
    if mode == "full":
        assert "image_memory" not in (output / "session_summary.json").read_text()
    else:
        assert not (root / "runs").exists()


def test_modifier_columns_upgrade_old_compact_response_table(
    sample_project, sample_project_root,
):
    from fpvs_studio.runtime.session_export import _upgrade_csv_header

    path = sample_project_root / "legacy-task-responses.csv"
    header = [column for column in COMPACT_TASK_RESPONSES_HEADER
              if not column.startswith(("modifier_", "image_memory_"))]
    original = dict.fromkeys(header, "")
    original.update(participant_number="old", text_value="Manual response",
                    selected_option_ids="apple;purse", score="2", participant_session_number="3")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerow(original)
    _upgrade_csv_header(path, COMPACT_TASK_RESPONSES_HEADER)
    with path.open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert {column: row[column] for column in header} == original
    assert row["modifier_id"] == ""
    assert row["image_memory_targets_selected"] == ""


def test_compiled_session_baseline_records_modifier_identity_on_no_load_first_entry(
    multi_condition_project, multi_condition_project_root,
):
    project = multi_condition_project.model_copy(deep=True)
    project.settings.session.block_count = 1
    root = multi_condition_project_root
    ordinary = compile_session_plan(project, refresh_hz=60, project_root=root, random_seed=314)
    load_id = ordinary.ordered_entries()[-1].condition_id
    definition = create_backward_counting_modifier(name="=Counting", baseline_duration_seconds=30)
    project = assign_modifier(project, definition, [load_id])
    plan = compile_session_plan(project, refresh_hz=60, project_root=root, random_seed=314)
    first = plan.ordered_entries()[0]
    assert first.condition_id != load_id
    baseline = first.pre_tasks[0].backward_counting
    load = next(entry for entry in plan.ordered_entries() if entry.condition_id == load_id)
    start = load.pre_tasks[0].backward_counting
    engine = MemoryEngine(
        TaskEngineInput(key="space"), TaskEngineInput(reaction_time_s=30),
        TaskEngineInput(numeric_value=baseline.start_number - 130),
        TaskEngineInput(key="space"), TaskEngineInput(numeric_value=start.start_number - 65),
    )
    summary = RuntimeWorker(engine).execute_session(
        root, plan, root / "runs" / "unused", participant_number="007",
        runtime_options={"serial_enabled": False, "export_mode": "compact"},
    )
    assert not summary.aborted
    baseline_rows = summary.run_results[0].task_responses
    assert len(baseline_rows) == 3
    assert all(row.condition_id == first.condition_id for row in baseline_rows)
    assert all(row.modifier.session_baseline for row in baseline_rows)
    assert all(row.modifier.requested_modifier_ids == [definition.modifier.modifier_id]
               for row in baseline_rows)
    assert baseline_rows[-1].backward_counting.interval_seconds == 30
    with (root / "logs" / "task_responses.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["modifier_session_baseline"] == "True"
    assert rows[0]["modifier_name"] == "'=Counting"
    assert rows[-1]["modifier_session_baseline"] == "False"


def test_memory_factory_compilation_and_runtime_share_realized_targets(
    sample_project, sample_project_root,
):
    from tests.unit.test_modifier_presets import memory_definition

    root = sample_project_root
    definition = memory_definition(root)
    project = assign_modifier(
        sample_project, definition, [sample_project.conditions[0].condition_id],
    )
    project.settings.session.block_count = 1
    plan = compile_session_plan(project, refresh_hz=60, project_root=root, random_seed=47)
    entry = plan.ordered_entries()[0]
    study = entry.pre_tasks[0].image_memory
    recognition = entry.post_tasks[0].image_memory
    assert study.target_item_ids == recognition.target_item_ids
    engine = MemoryEngine(TaskEngineInput(key="space"),
        TaskEngineInput(selected_item_ids=tuple(study.target_item_ids), reaction_time_s=1.3))
    summary = RuntimeWorker(engine).execute_session(
        root, plan, root / "runs" / "unused", participant_number="007",
        runtime_options={"serial_enabled": False, "export_mode": "compact"},
    )
    assert not summary.aborted
    assert [item.item_id for item in engine.steps[0].items] == study.study_order
    assert [item.item_id for item in engine.steps[1].items] == study.recognition_order
    response = summary.run_results[0].task_responses[-1]
    assert response.image_memory.targets_selected == 4
    assert response.image_memory.exact_set_correct is True
