"""Character-stream playback and exports through fakes, with no display or hardware."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from tests.unit.runtime_launcher_helpers import StubEngine
from tests.unit.test_psychopy_engine import (
    _build_fake_psychopy,
    _patch_fake_psychopy,
    _RecordingTriggerBackend,
)
from tests.unit.test_runtime_preflight import _PreflightEngine

from fpvs_studio.core.compiler import compile_run_spec, compile_session_plan
from fpvs_studio.core.enums import ExperimentCategory, PresentationUnit, StimulusModality
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.models import (
    AttentionalBlinkStreamSettings,
    StimulusSet,
    TextHeightScheduleSettings,
)
from fpvs_studio.core.project_bundle import export_project_bundle, import_project_bundle
from fpvs_studio.core.project_service import build_starter_project, create_project
from fpvs_studio.core.serialization import save_project_file
from fpvs_studio.core.task_models import TaskPhase
from fpvs_studio.engines.base import TaskEngineInput
from fpvs_studio.engines.graphics_readiness import estimate_run_spec_image_memory
from fpvs_studio.engines.psychopy_engine import PsychoPyEngine
from fpvs_studio.engines.psychopy_stimuli import stimulus_render_key
from fpvs_studio.runtime.preflight import PreflightError, preflight_run_spec
from fpvs_studio.runtime.run_worker import RuntimeWorker
from fpvs_studio.runtime.session_export import (
    ATTENTIONAL_BLINK_EVENTS_FILENAME,
    ATTENTIONAL_BLINK_STREAM_EVENTS_FILENAME,
    ATTENTIONAL_BLINK_STREAM_EVENTS_HEADER,
    append_session_condition_history,
    write_run_artifacts,
    write_session_artifacts,
)


@pytest.fixture
def stream_project(sample_project):
    project = sample_project.model_copy(
        update={"experiment_category": ExperimentCategory.ATTENTIONAL_BLINK}, deep=True,
    )
    project.settings.protocol.base_hz = 10.0
    project.settings.protocol.oddball_every_n = 20
    project.settings.fixation_task.enabled = False
    project.settings.fixation_task.accuracy_task_enabled = False
    project.settings.presentation.pre_stream_fixation_seconds = 0
    project.settings.session.block_count = 1
    condition = project.conditions[0]
    condition.oddball_cycle_repeats_per_sequence = 2
    condition.attentional_blink = AttentionalBlinkStreamSettings()
    condition.base_stimulus_set_id = "digits"
    condition.oddball_stimulus_set_id = "letters"
    condition.t2_stimulus_set_id = "letters"
    condition.isi_stimulus_set_id = None
    project.stimulus_sets = [
        StimulusSet(set_id="digits", name="Digits", modality=StimulusModality.WORD,
                    words=list("23456789")),
        StimulusSet(set_id="letters", name="Letters", modality=StimulusModality.WORD,
                    words=list("ABCDEFGHJKL")),
    ]
    return project


def _compile(project, soa_ms=300.0):
    project.conditions[0].attentional_blink.soa_ms = soa_ms
    return compile_run_spec(project, refresh_hz=60.0, random_seed=17, run_id="stream-run")


def _preflight(run, root):
    preflight_run_spec(
        root, run, engine=_PreflightEngine(), decode_image_assets=True,
        runtime_options={"verify_refresh_rate": False},
    )


def _play(monkeypatch, run, root, *, missing_flips=None, key_batches=None):
    captures = {}
    fake = _build_fake_psychopy(
        captures,
        flip_times=[10 + index / 60 for index in range(run.display.total_frames + 8)],
        flip_return_none_indices=missing_flips, key_batches=key_batches,
    )
    text_draws = []
    original_draw = fake.visual.TextStim.draw

    def record_draw(stimulus):
        original_draw(stimulus)
        text_draws.append((captures["window"]._flip_index, stimulus))

    monkeypatch.setattr(fake.visual.TextStim, "draw", record_draw)
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake)
    monkeypatch.setattr("fpvs_studio.engines.psychopy_stimuli.synchronize_gpu", lambda: None)
    triggers = _RecordingTriggerBackend()
    try:
        summary = engine.run_condition(
            run, root, runtime_options={"timing_warmup_frames": 2}, trigger_backend=triggers,
        )
    finally:
        engine.close_session()
    timed_draws = [stimulus for flip, stimulus in text_draws if flip >= 2]
    return summary, captures, triggers, timed_draws


@pytest.mark.parametrize("rate,soa_ms,lag,frames", [
    (10, 100, 1, 6), (10, 300, 3, 6), (10, 500, 5, 6),
    (7.5, 400, 3, 8), (12, 250, 3, 5), (20, 300, 6, 3),
])
@pytest.mark.parametrize("show_cross", [True, False])
def test_native_stream_preflight_and_fake_playback_preserve_every_character(
    monkeypatch, stream_project, tmp_path, rate, soa_ms, lag, frames, show_cross,
):
    stream_project.settings.protocol.base_hz = rate
    stream_project.settings.fixation_task.show_cross = show_cross
    stream_project.settings.fixation_task.participant_tutorial_enabled = False
    stream_project.settings.presentation.pre_stream_fixation_seconds = 2 / 60
    run = _compile(stream_project, soa_ms)
    _preflight(run, tmp_path)
    memory = estimate_run_spec_image_memory(run, decoded_dimensions={})
    assert memory.complete and memory.unique_image_variant_count == 0
    summary, captures, triggers, draws = _play(monkeypatch, run, tmp_path)
    assert summary.completed_frames == 40 * frames
    assert not summary.aborted
    assert not captures["image_stims"]
    assert len(captures["shape_stims"]) == (2 if show_cross else 0)
    assert len(draws) == 40 * frames
    for event in run.stimulus_sequence:
        segment = draws[event.on_start_frame:event.on_start_frame + event.on_frames]
        assert len(segment) == frames
        assert all(stimulus.text == event.text for stimulus in segment)
        color = "#FF0000" if event.phase == "t1" else "#FFFFFF"
        assert all(stimulus.color == color for stimulus in segment)
    assert [record["frame_index"] for record in triggers.records] == [
        0, (15 - lag) * frames, 15 * frames, (35 - lag) * frames, 35 * frames,
    ]
    onsets = summary.attentional_blink_onsets
    assert len(onsets) == 40
    assert [onset.time_s for onset in onsets] == pytest.approx(
        [index / rate for index in range(40)]
    )
    assert summary.runtime_metadata.condition_cache_cleanup_succeeded


def test_identical_letter_in_different_target_roles_does_not_share_color_cache(stream_project):
    run = _compile(stream_project)
    t1 = next(event for event in run.stimulus_sequence if event.phase == "t1")
    t2 = next(event for event in run.stimulus_sequence if event.phase == "t2")
    t2 = t2.model_copy(update={"text": t1.text})
    assert stimulus_render_key(t1, run_spec=run) != stimulus_render_key(t2, run_spec=run)


def test_shared_character_size_is_used_by_every_text_role(monkeypatch, stream_project, tmp_path):
    stream_project.settings.presentation.defaults.text_height = TextHeightScheduleSettings(
        unit=PresentationUnit.WINDOW_HEIGHT_FRACTION, values=[0.1],
    )
    run = _compile(stream_project)
    _preflight(run, tmp_path)
    _, captures, _, draws = _play(monkeypatch, run, tmp_path)
    expected_height = round(captures["window"].size[1] * 0.1)
    assert {stimulus.height for stimulus in draws} == {expected_height}


@pytest.mark.parametrize("field,value", [
    ("phase", "t2"), ("slot_index", 9), ("cycle_index", 1), ("on_start_frame", 1),
    ("on_frames", 5), ("off_frames", 1), ("role", "oddball"), ("is_blank", True),
])
def test_preflight_rejects_corrupted_stream_events(stream_project, tmp_path, field, value):
    run = _compile(stream_project)
    run.stimulus_sequence[0] = run.stimulus_sequence[0].model_copy(update={field: value})
    with pytest.raises(PreflightError, match="phase, slot, or frame timing"):
        _preflight(run, tmp_path)


@pytest.mark.parametrize("kind", ["bad_digit", "bad_letter", "same_targets", "adjacent_digits"])
def test_preflight_validates_actual_character_rules(stream_project, tmp_path, kind):
    run = _compile(stream_project)
    if kind == "bad_digit":
        run.stimulus_sequence[0].text = "A"
    elif kind == "bad_letter":
        run.stimulus_sequence[12].text = "7"
    elif kind == "same_targets":
        run.stimulus_sequence[15].text = run.stimulus_sequence[12].text
    else:
        run.stimulus_sequence[1].text = run.stimulus_sequence[0].text
    with pytest.raises(PreflightError, match="single digits|letters must differ|adjacent digits"):
        _preflight(run, tmp_path)


@pytest.mark.parametrize("field,value", [
    ("requested_soa_ms", 250.0), ("achieved_soa_ms", 299.0), ("lag", 2),
    ("t1_slot_index", 0), ("t2_slot_index", 19),
])
def test_preflight_rejects_inconsistent_soa_contract(stream_project, tmp_path, field, value):
    run = _compile(stream_project)
    run.attentional_blink = run.attentional_blink.model_copy(update={field: value})
    with pytest.raises(PreflightError, match="timing|frame grid"):
        _preflight(run, tmp_path)


def test_preflight_rejects_approximate_refresh_and_incomplete_coverage(stream_project, tmp_path):
    run = _compile(stream_project)
    run.display.refresh_hz = 59.94
    with pytest.raises(PreflightError, match="cannot display exact"):
        _preflight(run, tmp_path)
    run = _compile(stream_project)
    run.display.total_frames += 1
    with pytest.raises(PreflightError, match="complete cycle"):
        _preflight(run, tmp_path)


@pytest.mark.parametrize("kind", ["missing", "wrong_frame", "wrong_code", "duplicate"])
def test_preflight_requires_distinct_flip_target_markers(stream_project, tmp_path, kind):
    run = _compile(stream_project)
    marker = next(event for event in run.trigger_events if event.label == "t2_onset")
    if kind == "missing":
        run.trigger_events.remove(marker)
    elif kind == "duplicate":
        run.trigger_events.append(marker.model_copy())
    elif kind == "wrong_frame":
        marker.frame_index -= 1
    else:
        marker.code = 55
    with pytest.raises(PreflightError, match="markers|marker codes"):
        _preflight(run, tmp_path)


@pytest.mark.parametrize("kind", ["missing_start", "start_collision", "extra_marker"])
def test_preflight_rejects_ambiguous_stream_markers(stream_project, tmp_path, kind):
    run = _compile(stream_project)
    start = next(event for event in run.trigger_events if event.label == "condition_start")
    if kind == "missing_start":
        run.trigger_events.remove(start)
    elif kind == "start_collision":
        start.code = 55
        run.condition.trigger_code = 55
    else:
        run.trigger_events.append(start.model_copy(update={"label": "extra_marker"}))
    with pytest.raises(PreflightError, match="stream markers"):
        _preflight(run, tmp_path)


def _read_rows(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _session_summary(project, plan, run_summary):
    run_summary.session_id = plan.session_id
    run_summary.participant_number = "42"
    return SessionExecutionSummary(
        project_id=project.meta.project_id, session_id=plan.session_id,
        engine_name="psychopy", run_mode=run_summary.run_mode, participant_number="42",
        total_condition_count=1, completed_condition_count=int(not run_summary.aborted),
        run_results=[run_summary],
    )


def test_stream_exports_are_versioned_joinable_and_keep_missing_observations_blank(
    monkeypatch, stream_project, tmp_path,
):
    plan = compile_session_plan(stream_project, refresh_hz=60.0, session_id="stream-session")
    entry = plan.ordered_entries()[0]
    run = entry.run_spec
    result, _, _, _ = _play(monkeypatch, run, tmp_path, missing_flips={74})
    summary = _session_summary(stream_project, plan, result)
    append_session_condition_history(tmp_path, plan, summary)
    compact = _read_rows(tmp_path / "logs" / ATTENTIONAL_BLINK_STREAM_EVENTS_FILENAME)
    assert not (tmp_path / "logs" / ATTENTIONAL_BLINK_EVENTS_FILENAME).exists()
    assert not (tmp_path / "runs").exists()
    write_run_artifacts(tmp_path / "full-run", run, result)
    write_session_artifacts(tmp_path / "full-session", plan, summary)
    session_rows = _read_rows(tmp_path / "full-session" / ATTENTIONAL_BLINK_STREAM_EVENTS_FILENAME)
    assert session_rows == compact
    run_rows = _read_rows(tmp_path / "full-run" / ATTENTIONAL_BLINK_STREAM_EVENTS_FILENAME)
    assert run_rows[0]["block_index"] == ""
    assert len(compact) == 40
    assert list(compact[0]) == ATTENTIONAL_BLINK_STREAM_EVENTS_HEADER
    assert compact[0]["schema_version"] == "1.0"
    assert compact[0]["block_index"] == str(entry.block_index)
    assert compact[0]["global_order_index"] == str(entry.global_order_index)
    assert compact[12]["symbol"] == run.stimulus_sequence[12].text
    assert compact[12]["phase"] == "t1"
    assert compact[12]["presented"] == "True"
    assert compact[12]["actual_onset_s"] == ""
    assert compact[15]["observed_pair_soa_ms"] == ""
    assert float(compact[35]["observed_pair_soa_ms"]) == pytest.approx(300)
    assert compact[15]["requested_soa_ms"] == "300.0"
    assert compact[15]["achieved_soa_ms"] == "300.0"
    assert compact[15]["soa_frames"] == "18"
    assert compact[15]["intervening_digits"] == "2"
    path = tmp_path / "logs" / ATTENTIONAL_BLINK_STREAM_EVENTS_FILENAME
    path.write_text("incompatible,header\n", encoding="utf-8")
    with pytest.raises(ValueError, match="incompatible header"):
        append_session_condition_history(tmp_path, plan, summary)
    assert path.read_text(encoding="utf-8") == "incompatible,header\n"


def test_abort_records_only_presented_characters_and_no_invented_soa(
    monkeypatch, stream_project, tmp_path,
):
    run = _compile(stream_project)
    result, _, _, _ = _play(monkeypatch, run, tmp_path, key_batches=[[]] * 75 + [["escape"]])
    assert result.aborted and result.completed_frames == 76
    assert len(result.attentional_blink_onsets) == 13
    write_run_artifacts(tmp_path / "aborted", run, result)
    rows = _read_rows(tmp_path / "aborted" / ATTENTIONAL_BLINK_STREAM_EVENTS_FILENAME)
    assert rows[12]["presented"] == "True"
    assert rows[15]["presented"] == "False"
    assert rows[15]["actual_onset_s"] == ""
    assert rows[15]["observed_pair_soa_ms"] == ""


def test_default_study_questionnaire_follows_every_completed_condition_and_joins_exports(tmp_path):
    project = build_starter_project(
        "Default AB stream", experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
    )
    for condition in project.conditions:
        condition.oddball_cycle_repeats_per_sequence = 1
    project.settings.session.block_count = 2
    plan = compile_session_plan(project, refresh_hz=60.0, random_seed=20)
    sequence = []

    class QuestionnaireEngine(StubEngine):
        def run_condition(self, run_spec, project_root, **kwargs):
            sequence.append(("stream", run_spec.run_id))
            return super().run_condition(run_spec, project_root, **kwargs)

        def render_task_step(self, step, project_root):
            sequence.append(("question", step.prompt))
            return TaskEngineInput(selected_item_ids=("yes",), reaction_time_s=0.5)

    captures = {}
    summary = RuntimeWorker(QuestionnaireEngine(captures)).execute_session(
        tmp_path, plan, tmp_path / "runs" / "session", participant_number="0042",
        runtime_options={"export_mode": "compact", "serial_enabled": False},
    )
    assert not summary.aborted
    assert len(summary.run_results) == 6
    assert [kind for kind, _ in sequence] == ["stream", "question"] * 6
    assert {prompt for kind, prompt in sequence if kind == "question"} == {
        "Did you notice any white letters during that sequence?"
    }
    entries = {entry.run_id: entry for entry in plan.ordered_entries()}
    for result in summary.run_results:
        assert len(result.task_responses) == 1
        response = result.task_responses[0]
        entry = entries[result.run_id]
        assert response.phase == TaskPhase.POST_CONDITION
        assert response.run_id == result.run_id
        assert response.condition_id == entry.condition_id
        assert response.block_index == entry.block_index
        assert response.selected_option_ids == ["yes"]
        assert response.correct is None and response.score is None
    responses = _read_rows(tmp_path / "logs" / "task_responses.csv")
    assert len(responses) == 6
    assert all(row["participant_number"] == "0042" for row in responses)
    assert {row["run_id"] for row in responses} == set(entries)


def test_native_three_role_study_survives_portable_bundle_round_trip(tmp_path):
    scaffold = create_project(
        tmp_path / "source", "Portable letter study",
        experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
    )
    project = scaffold.project
    for condition in project.conditions:
        condition.oddball_cycle_repeats_per_sequence = 1
    save_project_file(project, scaffold.project_root / "project.json")
    original_project = (scaffold.project_root / "project.json").read_bytes()
    bundle = tmp_path / "letters.fpvsbundle"
    export_project_bundle(scaffold.project_root, bundle, refresh_hz=60.0)
    imported = import_project_bundle(bundle, tmp_path / "imported")
    assert (scaffold.project_root / "project.json").read_bytes() == original_project
    assert imported.project.schema_version == project.schema_version
    assert [item.words for item in imported.project.stimulus_sets] == [
        item.words for item in project.stimulus_sets
    ]
    assert len(imported.project.stimulus_sets) == 3
    assert all(item.source_dir is None for item in imported.project.stimulus_sets)
    assert imported.project.task_modules == project.task_modules
    plan = compile_session_plan(imported.project, refresh_hz=60.0)
    assert {entry.run_spec.attentional_blink.requested_soa_ms
            for entry in plan.ordered_entries()} == {100.0, 300.0, 500.0}
