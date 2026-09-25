"""Catch scenes must preserve playback timing without allowing hidden target events."""

from types import SimpleNamespace

import pytest
from tests.unit.test_masking import masking_project

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.engines.psychopy_scenes import scene_frame_draws
from fpvs_studio.runtime.preflight import PreflightError, _validate_scene_timing


def _catch_run(tmp_path):
    plan = compile_session_plan(masking_project(), project_root=tmp_path, refresh_hz=60,
                                random_seed=27)
    run = plan.ordered_entries()[0].run_spec
    scene = run.scene_stream.model_copy(update={
        "is_catch_trial": True, "target_id": None,
        "events": [event for event in run.scene_stream.events if event.role != "target"],
    })
    return run.model_copy(update={"schema_version": "1.5.0", "scene_stream": scene})


def test_target_absent_catch_passes_timing_preflight(tmp_path):
    _validate_scene_timing(_catch_run(tmp_path))


@pytest.mark.parametrize("corruption", ["missing_flag", "target_identity", "target_event", "mask"])
def test_corrupt_catch_fails_preflight(tmp_path, corruption):
    run = _catch_run(tmp_path)
    scene = run.scene_stream
    if corruption == "missing_flag":
        scene.is_catch_trial = None
    elif corruption == "target_identity":
        scene.target_id = scene.visuals[0].visual_id
    elif corruption == "target_event":
        scene.events.append(scene.events[0].model_copy(update={"role": "target"}))
    else:
        scene.events = scene.events[1:]
    with pytest.raises(PreflightError):
        _validate_scene_timing(run)


def test_catch_draws_all_mask_and_fixation_frames_but_no_target(tmp_path):
    run = _catch_run(tmp_path)
    scene = run.scene_stream
    drawn = []
    visuals = [SimpleNamespace(draw=lambda identity=visual.visual_id: drawn.append(identity))
               for visual in scene.visuals]
    draws = scene_frame_draws(scene, visuals, run.display.total_frames)
    for index, draw in enumerate(draws):
        drawn.clear()
        if draw:
            draw()
        expected = [event.visual_id for event in scene.events
                    if event.start_frame <= index < event.start_frame + event.duration_frames]
        assert drawn == expected
    assert not any(event.role == "target" for event in scene.events)
