"""Execute target-pair frame plans through fakes without importing PsychoPy or Qt."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from PIL import Image
from tests.unit.test_psychopy_engine import (
    _build_fake_psychopy,
    _patch_fake_psychopy,
    _RecordingTriggerBackend,
    _timed_image_draws,
)
from tests.unit.test_runtime_preflight import _PreflightEngine

from fpvs_studio.core.compiler import compile_run_spec, compile_session_plan
from fpvs_studio.core.enums import DutyCycleMode, ExperimentCategory
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.core.models import AttentionalBlinkSettings, ImageResolution, StimulusSet
from fpvs_studio.engines.graphics_readiness import (
    estimate_run_spec_image_memory,
    image_render_key_for_event,
)
from fpvs_studio.engines.psychopy_engine import PsychoPyEngine
from fpvs_studio.engines.psychopy_stimuli import stimulus_render_key
from fpvs_studio.runtime.preflight import PreflightError, preflight_run_spec
from fpvs_studio.runtime.session_export import (
    ATTENTIONAL_BLINK_EVENTS_FILENAME,
    append_session_condition_history,
    write_run_artifacts,
    write_session_artifacts,
)


@pytest.fixture
def ab_project(sample_project, sample_project_root):
    project = sample_project.model_copy(
        update={"experiment_category": ExperimentCategory.ATTENTIONAL_BLINK}, deep=True
    )
    project.settings.protocol.base_hz = 4.0
    project.settings.protocol.oddball_every_n = 4
    project.settings.fixation_task.enabled = False
    project.settings.fixation_task.accuracy_task_enabled = False
    project.settings.presentation.pre_stream_fixation_seconds = 0
    project.settings.session.block_count = 1
    condition = project.conditions[0]
    condition.oddball_cycle_repeats_per_sequence = 1
    condition.attentional_blink = AttentionalBlinkSettings()
    condition.isi_stimulus_set_id = condition.base_stimulus_set_id
    condition.t2_stimulus_set_id = "t2-set"
    source_dir = "stimuli/original-images/t2-set"
    path = sample_project_root / source_dir
    path.mkdir(parents=True)
    Image.new("RGB", (128, 64), "green").save(path / "t2.png")
    project.stimulus_sets.append(
        StimulusSet(
            set_id="t2-set",
            name="T2",
            source_dir=source_dir,
            image_count=1,
            resolution=ImageResolution(width_px=128, height_px=64),
        )
    )
    return project, sample_project_root


def _compile(ab_project):
    project, root = ab_project
    return compile_run_spec(project, refresh_hz=60.0, project_root=root, run_id="ab-runtime")


def test_blank_isi_keeps_frames_markers_and_draws_no_image(monkeypatch, ab_project):
    project, root = ab_project
    condition = project.conditions[0]
    condition.attentional_blink.isi_mode = "blank"
    condition.isi_stimulus_set_id = None
    run = _compile(ab_project)
    _preflight(run, root, decode=True)
    separator = next(event for event in run.stimulus_sequence if event.phase == "separator")
    assert separator.is_blank and separator.image_path is None
    assert (separator.on_start_frame, separator.on_frames) == (48, 3)
    summary, captures, triggers = _play(monkeypatch, run, root)
    assert summary.completed_frames == 60
    assert len(_timed_image_draws(captures)) == 57
    assert [record["frame_index"] for record in triggers.records] == [0, 45, 51]
    assert summary.attentional_blink_onsets[-2].frame_index == 48


def test_independent_isi_source_uses_its_own_geometry(ab_project):
    project, root = ab_project
    isi = project.stimulus_sets[-1].model_copy(update={"set_id": "isi-set", "name": "ISI"})
    project.stimulus_sets.append(isi)
    project.conditions[0].isi_stimulus_set_id = isi.set_id
    run = _compile(ab_project)
    _preflight(run, root, decode=True)
    separator = next(event for event in run.stimulus_sequence if event.phase == "separator")
    assert not separator.is_blank
    assert separator.image_path.endswith("t2-set/t2.png")
    assert stimulus_render_key(separator, run_spec=run)[-2:] == (128, 64)


def _preflight(run_spec, root, *, decode=False):
    preflight_run_spec(
        root,
        run_spec,
        engine=_PreflightEngine(),
        decode_image_assets=decode,
        runtime_options={"verify_refresh_rate": False},
    )


def _play(monkeypatch, run_spec, root, *, missing_flips=None, key_batches=None):
    captures = {}
    fake = _build_fake_psychopy(
        captures,
        flip_times=[10 + index / 60 for index in range(65)],
        flip_return_none_indices=missing_flips,
        key_batches=key_batches,
    )
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake)
    monkeypatch.setattr("fpvs_studio.engines.psychopy_stimuli.synchronize_gpu", lambda: None)
    triggers = _RecordingTriggerBackend()
    try:
        summary = engine.run_condition(
            run_spec,
            root,
            runtime_options={"timing_warmup_frames": 2},
            trigger_backend=triggers,
        )
    finally:
        engine.close_session()
    return summary, captures, triggers


def test_preflight_accepts_exact_pair_and_t2_source_geometry(ab_project):
    run_spec = _compile(ab_project)
    _preflight(run_spec, ab_project[1], decode=True)
    assert (
        run_spec.attentional_blink.t2_presentation.image_geometry.source_resolution.as_tuple()
        == (128, 64)
    )
    t2 = run_spec.stimulus_sequence[-1]
    assert image_render_key_for_event(t2, run_spec=run_spec)[-2:] == (128, 64)
    dimensions = {
        event.image_path: ((128, 64) if event.phase == "t2" else (256, 256))
        for event in run_spec.stimulus_sequence
    }
    estimate = estimate_run_spec_image_memory(run_spec, decoded_dimensions=dimensions)
    assert estimate.complete, estimate.issues


def test_deep_preflight_uses_t2_source_resolution(ab_project):
    run_spec = _compile(ab_project)
    path = ab_project[1] / run_spec.stimulus_sequence[-1].image_path
    Image.new("RGB", (256, 256), "green").save(path)
    with pytest.raises(PreflightError, match="decoded image dimensions"):
        _preflight(run_spec, ab_project[1], decode=True)


@pytest.mark.parametrize(
    "field, value",
    [
        ("phase", "t2"),
        ("slot_index", 2),
        ("on_start_frame", 46),
        ("on_frames", 4),
        ("off_frames", 1),
        ("role", "base"),
        ("sequence_index", 4),
    ],
)
def test_preflight_rejects_malformed_pair_events(ab_project, field, value):
    run_spec = _compile(ab_project)
    run_spec.stimulus_sequence[3] = run_spec.stimulus_sequence[3].model_copy(update={field: value})
    with pytest.raises(PreflightError, match="phase, slot, or frame timing"):
        _preflight(run_spec, ab_project[1])


def test_preflight_checks_t2_asset_and_rounded_metadata(ab_project):
    run_spec = _compile(ab_project)
    run_spec.attentional_blink.t2_frames += 1
    with pytest.raises(PreflightError, match="frame durations"):
        _preflight(run_spec, ab_project[1])
    run_spec = _compile(ab_project)
    run_spec.stimulus_sequence[-1].image_path = "stimuli/missing-t2.png"
    with pytest.raises(PreflightError, match="assets are missing"):
        _preflight(run_spec, ab_project[1])


@pytest.mark.parametrize("kind", ["missing", "duplicate", "wrong_frame", "wrong_code"])
def test_preflight_requires_distinct_target_markers_at_their_onsets(ab_project, kind):
    run_spec = _compile(ab_project)
    marker = next(event for event in run_spec.trigger_events if event.label == "t2_onset")
    if kind == "missing":
        run_spec.trigger_events.remove(marker)
    elif kind == "duplicate":
        run_spec.trigger_events.append(marker.model_copy())
    elif kind == "wrong_frame":
        marker.frame_index -= 1
    else:
        marker.code = 55
    with pytest.raises(PreflightError, match="markers|marker codes"):
        _preflight(run_spec, ab_project[1])


def test_preflight_rejects_orphan_phases_and_noncontinuous_mode(ab_project):
    run_spec = _compile(ab_project)
    run_spec.attentional_blink = None
    with pytest.raises(PreflightError, match="require compiled target-pair timing"):
        _preflight(run_spec, ab_project[1])
    run_spec = _compile(ab_project)
    run_spec.display.duty_cycle_mode = DutyCycleMode.BLANK_50
    with pytest.raises(PreflightError):
        _preflight(run_spec, ab_project[1])


def test_engine_draws_exact_phase_frames_and_records_flip_relative_onsets(monkeypatch, ab_project):
    run_spec = _compile(ab_project)
    summary, captures, triggers = _play(monkeypatch, run_spec, ab_project[1])

    assert summary.completed_frames == 60
    assert summary.aborted is False
    onsets = summary.attentional_blink_onsets
    assert [item.phase for item in onsets] == ["base", "base", "base", "t1", "separator", "t2"]
    assert [item.frame_index for item in onsets] == [0, 15, 30, 45, 48, 51]
    assert [item.time_s for item in onsets] == pytest.approx([0, 0.25, 0.5, 0.75, 0.8, 0.85])
    draws = _timed_image_draws(captures)
    assert len(draws) == 60
    for event in run_spec.stimulus_sequence:
        expected_image = str((ab_project[1] / event.image_path).resolve())
        actual = draws[event.on_start_frame : event.on_start_frame + event.on_frames]
        assert all(str(stimulus.image) == expected_image for stimulus, _contrast in actual)
    assert [
        (record["frame_index"], record["label"], record["code"]) for record in triggers.records
    ] == [(0, "condition_start", 1), (45, "t1_onset", 55), (51, "t2_onset", 56)]
    t2 = run_spec.stimulus_sequence[-1]
    assert stimulus_render_key(t2, run_spec=run_spec)[-2:] == (128, 64)
    assert summary.runtime_metadata.condition_cache_cleanup_succeeded is True


@pytest.mark.parametrize("missing", [{2}, {47}])
def test_missing_flip_timestamps_are_never_replaced_with_planned_times(
    monkeypatch,
    ab_project,
    missing,
):
    run_spec = _compile(ab_project)
    summary, _captures, _triggers = _play(
        monkeypatch, run_spec, ab_project[1], missing_flips=missing
    )
    onsets = summary.attentional_blink_onsets
    assert len(onsets) == 6
    if 2 in missing:
        assert all(item.time_s is None for item in onsets)
    else:
        assert onsets[3].time_s is None
        assert onsets[-1].time_s == pytest.approx(0.85)


def test_early_abort_only_records_presented_images(monkeypatch, ab_project):
    run_spec = _compile(ab_project)
    summary, _captures, _triggers = _play(
        monkeypatch,
        run_spec,
        ab_project[1],
        key_batches=[[]] * 46 + [["escape"]],
    )
    assert summary.aborted
    assert summary.completed_frames == 47
    assert [item.phase for item in summary.attentional_blink_onsets] == [
        "base",
        "base",
        "base",
        "t1",
    ]


def _read_rows(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_full_and_compact_exports_preserve_phase_and_actual_timing(
    monkeypatch, ab_project, tmp_path
):
    project, root = ab_project
    plan = compile_session_plan(
        project, refresh_hz=60.0, project_root=root, session_id="ab-session"
    )
    run_spec = plan.ordered_entries()[0].run_spec
    run_summary, _captures, _triggers = _play(monkeypatch, run_spec, root, missing_flips={47})
    run_summary.session_id = plan.session_id
    run_summary.participant_number = "42"
    summary = SessionExecutionSummary(
        project_id=project.meta.project_id,
        session_id=plan.session_id,
        engine_name="psychopy",
        run_mode=run_summary.run_mode,
        participant_number="42",
        total_condition_count=1,
        completed_condition_count=1,
        run_results=[run_summary],
    )
    append_session_condition_history(root, plan, summary)
    assert not (root / "runs").exists()
    compact = _read_rows(root / "logs" / ATTENTIONAL_BLINK_EVENTS_FILENAME)
    output = tmp_path / "full-run"
    write_run_artifacts(output, run_spec, run_summary)
    assert _read_rows(output / ATTENTIONAL_BLINK_EVENTS_FILENAME) == compact
    write_session_artifacts(tmp_path / "full-session", plan, summary)
    assert _read_rows(tmp_path / "full-session" / ATTENTIONAL_BLINK_EVENTS_FILENAME) == compact
    assert [row["phase"] for row in compact] == ["base", "base", "base", "t1", "separator", "t2"]
    assert compact[3]["actual_onset_s"] == ""
    assert compact[3]["presented"] == "True"
    assert float(compact[-1]["actual_onset_s"]) == pytest.approx(0.85)
    assert compact[-1]["requested_t2_ms"] == "150.0"


def test_standard_run_keeps_existing_summary_and_event_export(monkeypatch, ab_project, tmp_path):
    project, root = ab_project
    project.conditions[0].attentional_blink = None
    project.conditions[0].t2_stimulus_set_id = None
    project.conditions[0].isi_stimulus_set_id = None
    project = project.model_copy(update={"experiment_category": ExperimentCategory.FPVS_ODDBALL})
    run_spec = _compile((project, root))
    summary, _captures, _triggers = _play(monkeypatch, run_spec, root)
    assert summary.attentional_blink_onsets is None
    assert "attentional_blink_onsets" not in summary.model_dump(exclude_none=True)
    output = tmp_path / "standard"
    write_run_artifacts(output, run_spec, summary)
    assert not (output / ATTENTIONAL_BLINK_EVENTS_FILENAME).exists()
    rows = _read_rows(output / "events.csv")
    assert len(rows) == 4
    assert "phase" not in rows[0]
