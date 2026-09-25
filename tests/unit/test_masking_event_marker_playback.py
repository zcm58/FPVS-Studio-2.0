"""Masking event markers use their compiled scene flips without native playback."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from tests.unit.test_masking import masking_project
from tests.unit.test_psychopy_engine import (
    _build_fake_psychopy,
    _patch_fake_psychopy,
    _RecordingTriggerBackend,
)

from fpvs_studio.core.compiler_masking import compile_masking_run
from fpvs_studio.core.enums import ProjectSchemaVersion
from fpvs_studio.core.masking import MaskingEventTriggers, condition_masking
from fpvs_studio.engines import psychopy_scenes
from fpvs_studio.engines.psychopy_engine import PsychoPyEngine
from fpvs_studio.runtime import triggers as runtime_triggers
from fpvs_studio.runtime.triggers import LoggedTriggerBackend, build_trigger_backend


class _HardwareRecorder(_RecordingTriggerBackend):
    @property
    def emits_hardware_triggers(self) -> bool:
        return True


@pytest.mark.parametrize("soa_frames", [1, 3, 6])
@pytest.mark.parametrize("is_catch", [False, True])
@pytest.mark.parametrize("test_mode", [False, True], ids=["recording", "test-mode"])
def test_masking_markers_follow_target_and_mask_flips(
    monkeypatch, tmp_path, soa_frames, is_catch, test_mode,
):
    project = masking_project(("color",))
    project.schema_version = ProjectSchemaVersion.V1_10
    for modifier in project.condition_modifiers:
        modifier.masking.event_triggers = MaskingEventTriggers()
    condition = project.conditions[(1, 3, 6).index(soa_frames)]
    condition.oddball_cycle_repeats_per_sequence = 2
    condition.trigger_code = 10 if is_catch else (1, 3, 6).index(soa_frames) + 1
    condition.masking_catch = is_catch
    settings = condition_masking(project, condition)
    assert settings is not None
    run = compile_masking_run(
        project, condition, settings, refresh_hz=60, project_root=tmp_path,
        random_seed=17, run_id="event-marker-playback", is_catch_trial=is_catch,
    )
    # Independent 5 Hz / every-fifth-slot expectations: targets at 0.8 and 1.8 s.
    expected = [(0, condition.trigger_code, "condition_start")]
    for target_frame in (48, 108):
        expected.extend([
            (target_frame, 57 if is_catch else 55,
             "catch_slot_onset" if is_catch else "oddball_onset"),
            (target_frame + soa_frames, 56, "mask_onset"),
        ])
    assert [
        (event.frame_index, event.code, event.label) for event in run.trigger_events
    ] == expected
    assert len({event.frame_index for event in run.trigger_events}) == len(expected)

    captures = {}
    fake = _build_fake_psychopy(captures, flip_times=[])
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake)
    monkeypatch.setattr(psychopy_scenes, "synchronize_gpu", lambda: None)
    draws = []

    def prepare_visual(_visual, window, _root, definition):
        return SimpleNamespace(
            draw=lambda: draws.append((window._flip_index, definition.visual_id)),
        )

    monkeypatch.setattr(psychopy_scenes, "prepare_scene_visual", prepare_visual)
    options = {
        "experiment_test_mode": test_mode,
        "verify_graphics_memory": False,
        "timing_warmup_frames": 240,
    }
    hardware = _HardwareRecorder()
    if test_mode:
        monkeypatch.setattr(
            runtime_triggers, "_build_serial_backend",
            lambda _options: pytest.fail("Test mode must not construct serial hardware."),
        )
        backend, warnings = build_trigger_backend({
            "serial_enabled": False, "experiment_test_mode": True,
        })
        assert warnings == []
    else:
        backend = LoggedTriggerBackend(hardware, backend_name="serial")
    emitted_flips = []
    send = backend.send_prevalidated_trigger

    def record_flip(code, **kwargs):
        emitted_flips.append((captures["window"]._flip_index - 1, code))
        send(code, **kwargs)

    monkeypatch.setattr(backend, "send_prevalidated_trigger", record_flip)
    try:
        backend.connect()
        engine.open_session(runtime_options=options)
        window = captures["window"]
        window.monitor = SimpleNamespace(
            setWidth=lambda _value: None, setDistance=lambda _value: None,
            setSizePix=lambda _value: None,
        )
        engine.prepare_condition(run, tmp_path, runtime_options=options)
        assert window._flip_index == 0
        # Authored pre-task fixation remains outside the stream trigger clock.
        pre_task_flips = 7
        for _ in range(pre_task_flips):
            window.flip()
        draws.clear()
        summary = engine.run_condition(run, tmp_path, runtime_options=options,
                                       trigger_backend=backend)
        assert not summary.aborted
        assert summary.completed_frames == 120
        assert window._flip_index == pre_task_flips + 120 + 1
        assert window.callback_names == ["_emit_trigger"] * len(expected)
        assert emitted_flips == [(pre_task_flips + frame, code) for frame, code, _ in expected]
        assert len(summary.frame_intervals) == 120
        assert [interval.interval_s for interval in summary.frame_intervals] == pytest.approx(
            [1 / 60] * 120,
        )
        assert summary.runtime_metadata.timing_qc_warmup_frames == 0
        assert summary.runtime_metadata.timing_qc_strict_violation is False
    finally:
        engine.close_session()
        backend.close()

    records = backend.records
    assert [(item.frame_index, item.code, item.label) for item in records] == expected
    assert [item.time_s for item in records] == pytest.approx(
        [(frame + 1) / 60 for frame, _code, _label in expected],
    )
    assert {item.status for item in records} == {"skipped_disabled" if test_mode else "sent"}
    assert {item.backend_name for item in records} == {"null" if test_mode else "serial"}
    assert len(hardware.records) == (0 if test_mode else len(expected))
    assert (55 in [item.code for item in records]) == (not is_catch)
    scene = run.scene_stream
    assert scene is not None
    for target_frame in (48, 108):
        target_draws = {identity for frame, identity in draws
                        if frame == pre_task_flips + target_frame}
        if is_catch:
            assert not any(event.role == "target" for event in scene.events)
            assert {item.visual_id for item in settings.target_visuals}.isdisjoint(target_draws)
        else:
            assert scene.target_id in target_draws
        mask = next(event for event in scene.events
                    if event.role == "mask" and event.start_frame == target_frame + soa_frames)
        assert (pre_task_flips + target_frame + soa_frames, mask.visual_id) in draws
