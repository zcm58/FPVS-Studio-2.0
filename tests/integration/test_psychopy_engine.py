"""Optional lightweight PsychoPy engine integration checks."""

from __future__ import annotations

import importlib.util

import pytest

from fpvs_studio.core.compiler import compile_run_spec
from fpvs_studio.engines.psychopy_engine import PsychoPyEngine
from fpvs_studio.triggers.null_backend import NullBackend

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("psychopy") is None,
    reason="PsychoPy is not installed.",
)


def test_psychopy_engine_can_open_and_close_session_in_test_mode() -> None:
    engine = PsychoPyEngine()
    engine.open_session(runtime_options={"test_mode": True, "display_index": 0})
    engine.close_session()


def test_psychopy_engine_can_execute_tiny_runspec_in_test_mode(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.settings.fixation_task.enabled = False
    sample_project.conditions[0].oddball_cycle_repeats_per_sequence = 1

    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="psychopy-smoke",
    )
    engine = PsychoPyEngine()

    try:
        summary = engine.run_condition(
            run_spec,
            sample_project_root,
            runtime_options={"test_mode": True, "display_index": 0},
            trigger_backend=NullBackend(),
        )
    finally:
        engine.close_session()

    assert summary.aborted is False
    assert summary.completed_frames == run_spec.display.total_frames
    assert summary.runtime_metadata is not None
    assert summary.runtime_metadata.test_mode is True
