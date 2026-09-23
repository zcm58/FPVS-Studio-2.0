"""Exact native scene geometry, frame composition and resource lifecycle regressions."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from tests.unit.test_masking import masking_project
from tests.unit.test_psychopy_engine import (
    _build_fake_psychopy,
    _patch_fake_psychopy,
    _RecordingTriggerBackend,
)

from fpvs_studio.core.compiler import compile_run_spec
from fpvs_studio.core.run_spec import TriggerEvent
from fpvs_studio.core.scene_models import SceneEvent, SceneStreamSpec, SceneVisual
from fpvs_studio.engines import psychopy_scenes
from fpvs_studio.engines.psychopy_engine import PsychoPyEngine


def _circle(visual_id: str, **kwargs) -> SceneVisual:
    return SceneVisual(kind="circle", visual_id=visual_id, size=(5, 5), **kwargs)


def _scene() -> SceneStreamSpec:
    return SceneStreamSpec(
        visuals=[_circle("base"), _circle("target"), _circle("mask")],
        events=[
            SceneEvent(visual_id="base", start_frame=1, duration_frames=3),
            SceneEvent(visual_id="target", start_frame=2, duration_frames=1, role="target"),
            SceneEvent(visual_id="mask", start_frame=3, duration_frames=2, role="mask"),
        ],
        target_id="target", requested_soa_ms=1000 / 60, soa_frames=1,
    )


class _Stimulus:
    def __init__(self, label, log):
        self.label = label
        self.log = log

    def draw(self):
        self.log.append(self.label)

    def clearTextures(self):
        self.log.append(f"released:{self.label}")


@pytest.mark.parametrize("soa", [1, 3, 6])
def test_masking_source_frame_intervals_keep_gaps_and_boundary_adjacency(soa):
    scene = SceneStreamSpec(
        visuals=[_circle("base"), _circle("target"), _circle("mask")],
        events=[
            SceneEvent(visual_id="base", start_frame=soa, duration_frames=6),
            SceneEvent(visual_id="target", start_frame=12, duration_frames=1, role="target"),
            SceneEvent(visual_id="mask", start_frame=12 + soa, duration_frames=6, role="mask"),
        ],
        requested_soa_ms=soa * 1000 / 60, soa_frames=soa,
    )
    log = []
    plan = psychopy_scenes.scene_frame_draws(
        scene, [_Stimulus(item.visual_id, log) for item in scene.visuals], 24,
    )
    observed = []
    for draw in plan:
        log.clear()
        if draw is not None:
            draw()
        observed.append(tuple(log))
    assert observed == [
        (("base",) if soa <= frame < soa + 6 else ())
        + (("target",) if frame == 12 else ())
        + (("mask",) if 12 + soa <= frame < 18 + soa else ())
        for frame in range(24)
    ]


def test_scene_overlaps_retain_authored_painter_order():
    scene = _scene()
    log = []
    plan = psychopy_scenes.scene_frame_draws(
        scene, [_Stimulus(item.visual_id, log) for item in scene.visuals], 6,
    )
    actual = []
    for draw in plan:
        log.clear()
        if draw is not None:
            draw()
        actual.append(tuple(log))
    assert actual == [(), ("base",), ("base", "target"), ("base", "mask"), ("mask",), ()]


def test_native_primitives_preserve_signed_rgb_units_shapes_and_fonts(monkeypatch, tmp_path):
    constructors = []

    def construct(kind):
        def build(_window, **kwargs):
            constructors.append((kind, kwargs))
            return object()
        return build

    visual = SimpleNamespace(**{
        kind: construct(kind) for kind in ("ShapeStim", "Circle", "Rect", "TextStim", "ImageStim")
    })
    fonts = []
    monkeypatch.setattr(psychopy_scenes, "require_scene_font", fonts.append)
    definitions = [
        _circle("colored-circle", units="cm", rgb=(0.97, 0.36, 0.37),
                line_rgb=(1, 1, 1), position=(-5, 5)),
        SceneVisual(kind="rectangle", visual_id="backdrop", units="deg", size=(5, 5),
                    position=(0, -0.5), rgb=(0.4, 0.4, 0.4), line_rgb=(-1, -1, -1)),
        SceneVisual(kind="text", visual_id="letter", units="deg", text="M", text_height=5,
                    font="Arial Black", rgb=(0.57, 0.57, 0.57)),
        SceneVisual(kind="image", visual_id="face", units="deg", size=(5, 5),
                    image_path="stimuli/face.jpg"),
    ]
    for definition in definitions:
        psychopy_scenes.prepare_scene_visual(visual, object(), tmp_path, definition)
    circle, rectangle, text, image = [kwargs for _kind, kwargs in constructors]
    assert [kind for kind, _kwargs in constructors] == [
        "ShapeStim", "Rect", "TextStim", "ImageStim",
    ]
    assert circle["vertices"] == "circle"
    assert circle["units"] == "cm"
    assert circle["size"] == (5, 5)
    assert circle["pos"] == (-5, 5)
    assert circle["fillColor"] == (0.97, 0.36, 0.37)
    assert circle["lineColor"] == (1, 1, 1)
    assert circle["colorSpace"] == "rgb"
    assert rectangle["width"] == rectangle["height"] == 5
    assert rectangle["pos"] == (0, -0.5)
    assert rectangle["fillColor"] == (0.4, 0.4, 0.4)
    assert rectangle["lineColor"] == (-1, -1, -1)
    assert text["font"] == "Arial Black"
    assert text["height"] == 5
    assert text["color"] == (0.57, 0.57, 0.57)
    assert fonts == ["Arial Black"]
    assert Path(image["image"]) == tmp_path / "stimuli" / "face.jpg"
    assert image["size"] == (5, 5)
    assert all(kwargs["autoLog"] is False for _, kwargs in constructors)


@pytest.mark.parametrize("viewing_distance_cm", [57, 80, 100])
def test_color_masking_circles_keep_equal_diameters_at_every_soa(
    tmp_path, viewing_distance_cm,
):
    project = masking_project(("color",))
    project.settings.display.viewing_distance_cm = viewing_distance_cm
    project.settings.display.screen_width_cm = 60.96
    project.settings.display.screen_width_px = 1920
    project.settings.display.screen_height_px = 1080
    circles = []
    visual = SimpleNamespace(ShapeStim=lambda _window, **kwargs: circles.append(kwargs))
    for condition in project.conditions:
        run = compile_run_spec(
            project, condition_id=condition.condition_id, project_root=tmp_path,
            refresh_hz=60, random_seed=124,
        )
        assert run.scene_stream is not None
        circles.clear()
        for definition in run.scene_stream.visuals:
            if definition.kind == "circle":
                psychopy_scenes.prepare_scene_visual(visual, object(), tmp_path, definition)
        # Base, all four targets and mask must scale together with monitor calibration.
        assert len(circles) == 6
        assert {(circle["units"], circle["size"]) for circle in circles} == {
            ("deg", (5, 5))
        }


def test_scene_resources_prime_sync_calibration_and_cleanup(monkeypatch, tmp_path):
    log = []
    scene = _scene()
    scene.visuals[0].units = "cm"
    monitor = SimpleNamespace(
        setWidth=lambda value: log.append(("width", value)),
        setDistance=lambda value: log.append(("distance", value)),
        setSizePix=lambda value: log.append(("pixels", value)),
    )
    window = SimpleNamespace(
        monitor=monitor, size=(1920, 1080), clearBuffer=lambda: log.append("clear"),
    )
    run_spec = SimpleNamespace(
        scene_stream=scene, fixation=SimpleNamespace(show_cross=False),
        display=SimpleNamespace(total_frames=6, screen_width_cm=52.0, viewing_distance_cm=60.0),
    )
    monkeypatch.setattr(psychopy_scenes, "prepare_scene_visual",
                        lambda _visual, _window, _root, item: _Stimulus(item.visual_id, log))
    resources = psychopy_scenes.prepare_scene_resources(
        visual=object(), window=window, project_root=tmp_path, run_spec=run_spec,
        gpu_sync=lambda: log.append("sync"),
    )
    assert log == [("width", 52.0), ("distance", 60.0), ("pixels", (1920, 1080)),
                   "base", "target", "mask", "clear", "sync"]
    assert resources.ready and resources.gpu_synchronized
    report = resources.release()
    assert report.succeeded and report.stimulus_count == 3
    assert not resources.prepared_sequence and not resources.stimuli
    assert log[-4:] == ["released:base", "released:target", "released:mask", "sync"]
    assert resources.release() is report


def test_partial_scene_preparation_releases_already_created_stimuli(monkeypatch, tmp_path):
    log = []
    run_spec = SimpleNamespace(
        scene_stream=_scene(), fixation=SimpleNamespace(show_cross=False),
        display=SimpleNamespace(total_frames=6),
    )

    def build(_visual, _window, _root, item):
        if item.visual_id == "target":
            raise RuntimeError("source image failed")
        return _Stimulus(item.visual_id, log)

    monkeypatch.setattr(psychopy_scenes, "prepare_scene_visual", build)
    with pytest.raises(RuntimeError, match="source image failed"):
        psychopy_scenes.prepare_scene_resources(
            visual=object(), window=object(), project_root=tmp_path, run_spec=run_spec,
            gpu_sync=lambda: log.append("sync"),
        )
    assert log == ["released:base", "sync"]


def test_scene_engine_plan_preserves_trigger_lookup(sample_project, sample_project_root):
    run = compile_run_spec(sample_project, project_root=sample_project_root, refresh_hz=60)
    run = run.model_copy(update={
        "scene_stream": _scene(), "stimulus_sequence": [], "fixation_events": [],
        "display": run.display.model_copy(update={"total_frames": 6}),
        "fixation": run.fixation.model_copy(update={"show_cross": False}),
        "trigger_events": [TriggerEvent(frame_index=2, code=55, label="target")],
    })
    log = []
    plan = PsychoPyEngine()._build_playback_plan(
        run, prepared_sequence=[_Stimulus(item.visual_id, log) for item in _scene().visuals],
        default_fixation_stim=None, target_fixation_stim=None,
    )
    assert len(plan) == 6
    assert [event.code for event in plan[2][2]] == [55]
    assert all(frame[1] is None for frame in plan)
    plan[2][0]()
    assert log == ["base", "target"]


def test_scene_condition_playback_uses_native_resources_background_and_offset(
    monkeypatch, sample_project, sample_project_root,
):
    run = compile_run_spec(sample_project, project_root=sample_project_root, refresh_hz=60)
    run = run.model_copy(update={
        "scene_stream": _scene(), "stimulus_sequence": [], "fixation_events": [],
        "pre_stream_fixation_frames": 0,
        "display": run.display.model_copy(update={"total_frames": 6}),
        "fixation": run.fixation.model_copy(update={"show_cross": False}),
        "trigger_events": [TriggerEvent(frame_index=2, code=55, label="target")],
    })
    captures = {}
    fake = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake)
    sync_calls = []
    monkeypatch.setattr(psychopy_scenes, "synchronize_gpu", lambda: sync_calls.append("sync"))
    backend = _RecordingTriggerBackend()
    try:
        engine.prepare_condition(
            run, sample_project_root,
            runtime_options={"experiment_test_mode": True, "timing_warmup_frames": 240},
        )
        assert captures["window"]._flip_index == 0
        # A real timed pre-task may draw 120 fixation frames after preparation.
        # No condition resource work is permitted between that task and frame zero.
        for _ in range(120):
            captures["window"].flip()
        monkeypatch.setattr(
            engine, "_prepare_condition_playback",
            lambda *_args, **_kwargs: pytest.fail("resources prepared after timed fixation"),
        )
        summary = engine.run_condition(
            run, sample_project_root, trigger_backend=backend,
            runtime_options={"experiment_test_mode": True, "timing_warmup_frames": 240},
        )
        assert summary.completed_frames == 6
        assert not summary.aborted
        assert captures["window"].colorSpace == "rgb"
        assert captures["window"].color == (0.0, 0.0, 0.0)
        assert [item.draw_count for item in captures["shape_stims"]] == [4, 2, 3]
        assert captures["window"]._flip_index == 127  # fixation + six frames + neutral offset
        assert summary.runtime_metadata.timing_qc_warmup_frames == 0
        assert engine._prepared_scene is None
        assert [(record["frame_index"], record["code"]) for record in backend.records] == [(2, 55)]
        assert sync_calls == ["sync", "sync"]
    finally:
        engine.close_session()


def test_scene_playback_requires_explicit_preparation(
    monkeypatch, sample_project, sample_project_root,
):
    run = compile_run_spec(sample_project, project_root=sample_project_root, refresh_hz=60)
    run = run.model_copy(update={"scene_stream": _scene()})
    captures = {}
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, _build_fake_psychopy(captures, flip_times=[]))
    with pytest.raises(RuntimeError, match="prepare_condition"):
        engine.run_condition(
            run, sample_project_root, trigger_backend=_RecordingTriggerBackend(),
            runtime_options={"experiment_test_mode": True},
        )
    assert captures["window"]._flip_index == 0
    assert captures["window"].closed


def test_unplayed_scene_is_released_on_session_abort(
    monkeypatch, sample_project, sample_project_root,
):
    run = compile_run_spec(sample_project, project_root=sample_project_root, refresh_hz=60)
    run = run.model_copy(update={
        "scene_stream": _scene(), "stimulus_sequence": [], "fixation_events": [],
        "display": run.display.model_copy(update={"total_frames": 6}),
        "fixation": run.fixation.model_copy(update={"show_cross": False}),
    })
    captures = {}
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, _build_fake_psychopy(captures, flip_times=[]))
    sync_calls = []
    monkeypatch.setattr(psychopy_scenes, "synchronize_gpu", lambda: sync_calls.append("sync"))
    engine.prepare_condition(run, sample_project_root)
    resources = engine._prepared_scene.resources
    with pytest.raises(RuntimeError, match="must be played"):
        engine.prepare_condition(run, sample_project_root)
    engine.abort()
    engine.close_session()
    assert not resources.stimuli and not resources.prepared_sequence
    assert engine._prepared_scene is None
    assert captures["window"].closed
    assert sync_calls == ["sync", "sync"]


@pytest.mark.parametrize("invalid", [True, 1.5, -1])
def test_scene_frame_counts_reject_nonintegers(invalid):
    with pytest.raises(ValidationError):
        SceneEvent(visual_id="base", start_frame=invalid, duration_frames=1)


def test_scene_rejects_unknown_identity_and_overflow():
    data = _scene().model_dump()
    data["events"][0]["visual_id"] = "unknown"
    with pytest.raises(ValidationError, match="unknown visual"):
        SceneStreamSpec.model_validate(data)
    with pytest.raises(ValueError, match="beyond"):
        _scene().validate_frame_bounds(4)
    with pytest.raises(ValidationError):
        _circle("bad-rgb", rgb=(1.01, 0, 0))
    with pytest.raises(ValidationError):
        SceneVisual(kind="image", visual_id="escaped", size=(1, 1), image_path="../secret.jpg")


def test_scene_image_memory_accounts_for_each_native_variant():
    scene = SceneStreamSpec(
        visuals=[SceneVisual(
            kind="image", visual_id="image", image_path="stimuli/a.png", size=(5, 5),
        )],
        events=[SceneEvent(visual_id="image", start_frame=0, duration_frames=1)],
        requested_soa_ms=50, soa_frames=3,
    )
    estimate = psychopy_scenes.estimate_scene_image_memory(
        scene, {"stimuli/a.png": (500, 400)}, {"stimuli/a.png": "L"},
    )
    assert estimate.complete
    assert estimate.unique_image_variant_count == 1
    assert estimate.estimated_gpu_bytes > 500 * 400 * 12
