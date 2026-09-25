"""Authored masking flow and durable full/compact experimental provenance."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from PIL import Image
from tests.unit.runtime_launcher_helpers import StubEngine

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.condition_modifiers import assign_modifier
from fpvs_studio.core.masking import MaskingCatchTrialSettings
from fpvs_studio.core.masking_presets import create_masking_modifier
from fpvs_studio.core.scene_models import SceneVisual
from fpvs_studio.core.task_models import TaskResponseRecord
from fpvs_studio.engines.base import TaskEngineInput
from fpvs_studio.runtime.masking_report import (
    MASKING_PLAN_DIRNAME,
    MASKING_SCENE_EVENTS_FILENAME,
    MASKING_SCENE_EVENTS_HEADER,
    MASKING_TRIALS_FILENAME,
    MASKING_TRIALS_HEADER,
    MASKING_TRIALS_V2_FILENAME,
    MASKING_TRIALS_V2_HEADER,
    masking_scene_event_rows,
    masking_trial_v2_row,
    write_masking_plan_checkpoint,
)
from fpvs_studio.runtime.run_worker import RuntimeWorker
from fpvs_studio.runtime.session_export import append_session_condition_history


def _plan(project, root: Path, *, catch_trials: bool = False):
    original = project.conditions[0]
    project.conditions = [original.model_copy(update={
        "condition_id": f"masking-{variant}", "name": variant.title(), "trigger_code": index + 1,
        "order_index": index, "oddball_cycle_repeats_per_sequence": 1, "sequence_count": 1,
    }, deep=True) for index, variant in enumerate(("color", "faces", "number"))]
    project.settings.protocol.base_hz = 5
    project.settings.session.block_count = 2
    project.settings.fixation_task.enabled = False
    project.settings.fixation_task.show_cross = False
    project.settings.fixation_task.accuracy_task_enabled = False
    project.settings.fixation_task.participant_tutorial_enabled = False
    for index, variant in enumerate(("color", "faces", "number")):
        definition = create_masking_modifier(variant=variant, modifier_id=f"masking-{variant}")
        if catch_trials:
            definition.modifier.masking.catch_trial = MaskingCatchTrialSettings(
                trigger_code=10 + index,
            )
        if variant == "faces":
            visuals = []
            for identity in ("object", "face"):
                owner = definition.modifier.pre_task_ids[0]
                relative = f"stimuli/task-assets/{owner}/{identity}.png"
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (12, 10), color=(120, 60, 20)).save(path)
                visuals.append(SceneVisual(kind="image", visual_id=identity, image_path=relative,
                                           units="deg", size=(5, 5)))
            definition.modifier.masking.base_visuals = visuals[:1]
            definition.modifier.masking.target_visuals = visuals[1:]
            definition.modifier.masking.target_answers = {"face": "angry"}
        project = assign_modifier(project, definition, [f"masking-{variant}"])
    return compile_session_plan(project, refresh_hz=60, project_root=root, random_seed=73)


class _MaskingEngine(StubEngine):
    def __init__(self, plan, *, abort_step=None, wrong_answer=False, pas_rating=1,
                 abort_catch_only=False):
        super().__init__({})
        self.events = []
        self.abort_step = abort_step
        self.wrong_answer = wrong_answer
        self.pas_rating = pas_rating
        self.abort_catch_only = abort_catch_only
        self.current_catch = False
        self.correct_options = [
            next((item.item_id for item in step.items if item.correct), None)
            for entry in plan.ordered_entries() for task in entry.post_tasks for step in task.steps
            if step.step_id == "masking-identification"
        ]

    def render_task_step(self, step, project_root):
        self.events.append(step.step_id)
        if (step.step_id == self.abort_step
                and (not self.abort_catch_only or self.current_catch)):
            return TaskEngineInput(aborted=True)
        if step.step_id == "masking-identification":
            correct = self.correct_options.pop(0)
            selected = (next(item.item_id for item in step.items if item.item_id != correct)
                        if self.wrong_answer else correct or step.items[0].item_id)
            return TaskEngineInput(selected_item_ids=(selected,),
                                   reaction_time_s=0.625)
        if step.step_id == "masking-pas":
            return TaskEngineInput(selected_item_ids=(f"masking-pas-{self.pas_rating}",),
                                   reaction_time_s=0.5)
        if step.kind == "choice_grid":
            return TaskEngineInput(selected_item_ids=(step.items[0].item_id,), reaction_time_s=0.5)
        return TaskEngineInput(key="space" if step.duration_s is None else None)

    def run_condition(self, run_spec, project_root, **kwargs):
        assert self.prepared_run_id == run_spec.run_id
        self.events.append("stream")
        return super().run_condition(run_spec, project_root, **kwargs)

    def prepare_condition(self, run_spec, project_root, **kwargs):
        self.prepared_run_id = run_spec.run_id
        self.current_catch = bool(run_spec.scene_stream.is_catch_trial)
        self.events.append("prepare")


def _rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.parametrize("mode", ["full", "compact"])
def test_all_masking_variants_follow_authored_tasks_and_keep_provenance(
    mode, sample_project, sample_project_root,
):
    plan = _plan(sample_project, sample_project_root)
    assert plan.authored_task_flow
    assert len(plan.blocks) == 3
    engine = _MaskingEngine(plan)
    output = sample_project_root / "runs" / "P007_session01"
    summary = RuntimeWorker(engine).execute_session(
        sample_project_root, plan, output, participant_number="007", participant_session_number=1,
        runtime_options={
            "serial_enabled": False, "export_mode": mode, "experiment_test_mode": True,
        },
        relative_output_dir="runs/P007_session01",
    )
    assert not summary.aborted
    trials = _rows(sample_project_root / "logs" / MASKING_TRIALS_V2_FILENAME)
    assert len(trials) == 6
    by_run = {row["run_id"]: row for row in trials}
    for entry in plan.ordered_entries():
        row = by_run[entry.run_id]
        assert row["target_id"] == entry.run_spec.scene_stream.target_id
        assert row["target_presented"] == "True"
        assert row["selected_target"] == row["expected_answer"]
        assert row["correct"] == "True"
        assert row["is_catch_trial"] == "False"
        assert row["pas_rating"] == "1"
        assert row["pas_selected_option_ids"] == "masking-pas-1"
        assert row["pas_response_valid"] == "True"
        assert row["detection_outcome"] == "miss"
        assert row["trigger_code"] == str(entry.run_spec.condition.trigger_code)
    expected = []
    for _ in range(3):
        expected.extend(["masking-instructions", "masking-start-fixation"])
        for _ in range(2):
            expected.extend(["stream", "masking-pas", "masking-identification",
                             "masking-frequency", "masking-break", "masking-break-fixation"])
        expected.append("masking-thanks")
    assert [event for event in engine.events if event != "prepare"] == expected
    assert engine.events.count("prepare") == 6
    for index, event in enumerate(engine.events):
        if event == "prepare":
            assert engine.events[index + 1] in {
                "masking-instructions", "masking-break-fixation",
            }
    for added_screen in ("transitions", "block_breaks", "completion_screens", "condition_feedback"):
        assert engine._captures.get(added_screen, []) == []
    for result in summary.run_results:
        identity = next(item for item in result.task_responses
                        if item.step_id == "masking-identification")
        assert identity.correct is True
        assert identity.reaction_time_s == 0.625
    events_path = sample_project_root / "logs" / MASKING_SCENE_EVENTS_FILENAME
    rows = _rows(events_path)
    event_count = sum(len(entry.run_spec.scene_stream.events) for entry in plan.ordered_entries())
    assert len(rows) == event_count
    assert all(row["observed_onset_s"] == "" for row in rows)
    assert all(row["observed_onset_source"] == "not_recorded" for row in rows)
    assert all(row["onset_frame_completed"] == "True" for row in rows)
    for entry in plan.ordered_entries():
        selected = [row for row in rows if row["run_id"] == entry.run_id]
        assert {row["target_id"] for row in selected} == {entry.run_spec.scene_stream.target_id}
        assert {int(row["run_seed"]) for row in selected} == {entry.run_spec.random_seed}
    if mode == "full":
        assert len(_rows(output / MASKING_SCENE_EVENTS_FILENAME)) == event_count
        for entry in plan.ordered_entries():
            assert len(_rows(output / entry.run_id / MASKING_SCENE_EVENTS_FILENAME)) == len(
                entry.run_spec.scene_stream.events
            )
    else:
        assert not output.exists()
    response_path = (
        output if mode == "full" else sample_project_root / "logs"
    ) / "task_responses.csv"
    identity_rows = [row for row in _rows(response_path)
                     if row["step_id"] == "masking-identification"]
    assert len(identity_rows) == 6
    assert all(row["correct"] == "True" and row["reaction_time_s"] == "0.625"
               for row in identity_rows)
    plans = list((sample_project_root / "logs" / MASKING_PLAN_DIRNAME).glob("*.json"))
    assert len(plans) == 1
    saved = json.loads(plans[0].read_text(encoding="utf-8"))
    assert saved["planned_only"] is True
    assert saved["session_plan"]["blocks"][0]["entries"][0]["run_spec"]["scene_stream"]
    append_session_condition_history(sample_project_root, plan, summary, refresh_reports=False)
    assert _rows(events_path) == rows
    assert _rows(sample_project_root / "logs" / MASKING_TRIALS_V2_FILENAME) == trials


@pytest.mark.parametrize("mode", ["full", "compact"])
def test_pre_task_abort_keeps_compiled_target_and_marks_no_stimulus_onsets(
    mode, sample_project, sample_project_root,
):
    plan = _plan(sample_project, sample_project_root)
    engine = _MaskingEngine(plan, abort_step="masking-instructions")
    output = sample_project_root / "runs" / "aborted"
    summary = RuntimeWorker(engine).execute_session(
        sample_project_root, plan, output, participant_number="008", participant_session_number=1,
        runtime_options={
            "serial_enabled": False, "export_mode": mode, "experiment_test_mode": True,
        },
    )
    assert summary.aborted and engine.events == ["prepare", "masking-instructions"]
    trials = _rows(sample_project_root / "logs" / MASKING_TRIALS_V2_FILENAME)
    assert len(trials) == 1
    assert trials[0]["target_presented"] == "False"
    assert trials[0]["target_flashes_completed"] == "0"
    assert trials[0]["correct"] == trials[0]["selected_target"] == ""
    assert trials[0]["pas_rating"] == trials[0]["detection_outcome"] == ""
    assert all(row["onset_frame_completed"] == "False" for row in _rows(
        sample_project_root / "logs" / MASKING_SCENE_EVENTS_FILENAME
    ))
    plans = list((sample_project_root / "logs" / MASKING_PLAN_DIRNAME).glob("*.json"))
    assert len(plans) == 1
    assert json.loads(plans[0].read_text(encoding="utf-8"))["planned_only"] is True


@pytest.mark.parametrize("mode", ["full", "compact"])
@pytest.mark.parametrize("abort_answer", [False, True])
def test_trial_table_distinguishes_wrong_and_aborted_answers(
    mode, abort_answer, sample_project, sample_project_root,
):
    plan = _plan(sample_project, sample_project_root)
    engine = _MaskingEngine(
        plan, wrong_answer=True,
        abort_step="masking-identification" if abort_answer else None,
    )
    RuntimeWorker(engine).execute_session(
        sample_project_root, plan, sample_project_root / "runs" / "answers",
        participant_number="009", participant_session_number=1,
        runtime_options={"serial_enabled": False, "export_mode": mode,
                         "experiment_test_mode": True},
    )
    trials = _rows(sample_project_root / "logs" / MASKING_TRIALS_V2_FILENAME)
    assert len(trials) == (1 if abort_answer else 6)
    for row in trials:
        assert row["target_presented"] == "True"
        assert row["correct"] == ("" if abort_answer else "False")
        assert row["selected_target"] != row["expected_answer"]
        assert row["response_aborted"] == str(abort_answer)


@pytest.mark.parametrize("mode", ["full", "compact"])
@pytest.mark.parametrize("pas_rating", [1, 2, 3, 4])
def test_catch_trials_export_detection_without_identity_and_preserve_legacy_data(
    mode, pas_rating, sample_project, sample_project_root,
):
    plan = _plan(sample_project, sample_project_root, catch_trials=True)
    legacy = sample_project_root / "logs" / MASKING_TRIALS_FILENAME
    legacy.parent.mkdir(parents=True, exist_ok=True)
    with legacy.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(MASKING_TRIALS_HEADER)
        writer.writerow(["1.0.0", "historical-project", "historical-session"]
                        + [""] * (len(MASKING_TRIALS_HEADER) - 3))
    original_bytes = legacy.read_bytes()
    output = sample_project_root / "runs" / "catch-session"
    summary = RuntimeWorker(_MaskingEngine(plan, pas_rating=pas_rating)).execute_session(
        sample_project_root, plan, output, participant_number="010", participant_session_number=1,
        runtime_options={"serial_enabled": False, "export_mode": mode,
                         "experiment_test_mode": True},
    )
    assert not summary.aborted
    path = sample_project_root / "logs" / MASKING_TRIALS_V2_FILENAME
    trials = _rows(path)
    assert len(trials) == 9
    catches = [row for row in trials if row["is_catch_trial"] == "True"]
    assert len(catches) == 3
    for row in catches:
        assert row["schema_version"] == "2.0.0"
        assert row["target_id"] == row["target_text"] == row["target_image_path"] == ""
        assert row["target_rgb"] == row["expected_answer"] == row["correct"] == ""
        assert row["target_presented"] == "False" and row["target_flashes_completed"] == "0"
        assert row["selected_target"] != ""
        assert row["response_valid"] == row["pas_response_valid"] == "True"
        assert row["pas_rating"] == str(pas_rating)
        assert row["pas_selected_option_ids"] == f"masking-pas-{pas_rating}"
        assert row["pas_response_aborted"] == "False" and row["pas_reaction_time_s"] == "0.5"
        expected_detection = "correct_rejection" if pas_rating == 1 else "false_alarm"
        assert row["detection_outcome"] == expected_detection
    assert all(row["detection_outcome"] == ("miss" if pas_rating == 1 else "hit")
               for row in trials if row["is_catch_trial"] == "False")
    catch_ids = {row["run_id"] for row in catches}
    scene_rows = _rows(sample_project_root / "logs" / MASKING_SCENE_EVENTS_FILENAME)
    assert all(row["target_id"] == "" and row["role"] != "target"
               for row in scene_rows if row["run_id"] in catch_ids)
    response_root = output if mode == "full" else sample_project_root / "logs"
    responses = _rows(response_root / "task_responses.csv")
    catch_answers = [row for row in responses if row["run_id"] in catch_ids
                     and row["step_id"] == "masking-identification"]
    assert len(catch_answers) == 3
    assert all(row["correct"] == row["score"] == "" for row in catch_answers)
    append_session_condition_history(sample_project_root, plan, summary, refresh_reports=False)
    assert _rows(path) == trials
    assert legacy.read_bytes() == original_bytes


@pytest.mark.parametrize("mode", ["full", "compact"])
@pytest.mark.parametrize("abort_step", ["masking-pas", "masking-frequency"])
def test_catch_abort_preserves_completed_pas_without_scoring_missing_pas(
    mode, abort_step, sample_project, sample_project_root,
):
    plan = _plan(sample_project, sample_project_root, catch_trials=True)
    summary = RuntimeWorker(_MaskingEngine(
        plan, abort_step=abort_step, abort_catch_only=True,
    )).execute_session(
        sample_project_root, plan, sample_project_root / "runs" / "catch-abort",
        participant_number="011", participant_session_number=1,
        runtime_options={"serial_enabled": False, "export_mode": mode,
                         "experiment_test_mode": True},
    )
    assert summary.aborted
    rows = _rows(sample_project_root / "logs" / MASKING_TRIALS_V2_FILENAME)
    catches = [row for row in rows if row["is_catch_trial"] == "True"]
    assert len(catches) == 1
    row = catches[0]
    assert row["correct"] == ""
    assert row["run_aborted"] == "False"
    assert summary.run_results[-1].task_flow_aborted
    assert row["detection_outcome"] == ("" if abort_step == "masking-pas" else "correct_rejection")
    assert row["pas_response_aborted"] == str(abort_step == "masking-pas")


@pytest.mark.parametrize("exposure", ["none", "partial", "complete"])
def test_catch_detection_requires_complete_stream_despite_valid_pas(
    exposure, sample_project, sample_project_root,
):
    plan = _plan(sample_project, sample_project_root, catch_trials=True)
    entry = next(item for item in plan.ordered_entries()
                 if item.run_spec.scene_stream.is_catch_trial)
    run = entry.run_spec
    response = TaskResponseRecord(
        response_index=0, task_id=entry.post_tasks[0].task_id, step_id="masking-pas",
        phase="post_condition", condition_id=entry.condition_id, run_id=entry.run_id,
        block_index=entry.block_index, global_order_index=entry.global_order_index,
        repetition_index=0, response_kind="option_selection",
        selected_option_ids=["masking-pas-1"], valid=True,
    )
    frames = {"none": 0, "partial": run.display.total_frames - 1,
              "complete": run.display.total_frames}[exposure]
    summary = StubEngine({}).run_condition(run, sample_project_root).model_copy(update={
        "completed_frames": frames, "aborted": True, "task_responses": [response],
    })
    row = dict(zip(MASKING_TRIALS_V2_HEADER, masking_trial_v2_row(entry, summary), strict=True))
    assert row["detection_outcome"] == ("correct_rejection" if exposure == "complete" else None)
    assert row["pas_rating"] == 1


@pytest.mark.parametrize("selected,valid,aborted", [
    (["masking-pas-1"], False, False), (["masking-pas-1"], True, True),
    (["custom-pas-option"], True, False), (["masking-pas-1", "masking-pas-2"], True, False),
])
def test_catch_detection_does_not_infer_invalid_or_unknown_pas_answers(
    selected, valid, aborted, sample_project, sample_project_root,
):
    plan = _plan(sample_project, sample_project_root, catch_trials=True)
    entry = next(item for item in plan.ordered_entries()
                 if item.run_spec.scene_stream.is_catch_trial)
    response = TaskResponseRecord(
        response_index=0, task_id=entry.post_tasks[0].task_id, step_id="masking-pas",
        phase="post_condition", condition_id=entry.condition_id, run_id=entry.run_id,
        block_index=entry.block_index, global_order_index=entry.global_order_index,
        repetition_index=0, response_kind="option_selection", selected_option_ids=selected,
        valid=valid, aborted=aborted,
    )
    summary = StubEngine({}).run_condition(entry.run_spec, sample_project_root).model_copy(
        update={"task_responses": [response]},
    )
    row = dict(zip(MASKING_TRIALS_V2_HEADER, masking_trial_v2_row(entry, summary), strict=True))
    assert row["detection_outcome"] is None
    assert row["pas_selected_option_ids"] == ";".join(selected)


def test_numbered_plan_checkpoint_is_idempotent_and_rejects_conflicting_plan(
    sample_project, sample_project_root,
):
    plan = _plan(sample_project, sample_project_root)
    arguments = {"participant_number": "009", "participant_session_number": 1}
    path = write_masking_plan_checkpoint(sample_project_root, plan, **arguments)
    before = path.read_bytes()
    assert write_masking_plan_checkpoint(sample_project_root, plan, **arguments) == path
    changed = plan.model_copy(deep=True)
    changed.ordered_entries()[0].run_spec.scene_stream.visuals[0].rgb = (0.1, 0.2, 0.3)
    with pytest.raises(ValueError, match="different masking plan"):
        write_masking_plan_checkpoint(sample_project_root, changed, **arguments)
    assert path.read_bytes() == before


def test_export_preserves_source_rgb_and_distinguishes_partial_playback(
    sample_project, sample_project_root,
):
    plan = _plan(sample_project, sample_project_root)
    entry = next(item for item in plan.ordered_entries() if item.condition_id == "masking-color")
    run = entry.run_spec
    summary = StubEngine({}).run_condition(run, sample_project_root).model_copy(
        update={"completed_frames": 2, "aborted": True},
    )
    rows = [dict(zip(MASKING_SCENE_EVENTS_HEADER, row, strict=True))
            for row in masking_scene_event_rows(run, summary, entry=entry)]
    assert {json.loads(row["rgb"])[0] for row in rows if row["role"] == "base"} == {0.57}
    assert all(row["onset_frame_completed"] is (row["planned_onset_frame"] < 2) for row in rows)
    assert all(row["observed_onset_s"] is None for row in rows)
    assert any(row["onset_frame_completed"] is False for row in rows)
