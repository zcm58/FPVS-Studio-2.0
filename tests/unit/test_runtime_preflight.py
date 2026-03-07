"""Runtime preflight validation tests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from fpvs_studio.core.compiler import compile_run_spec
from fpvs_studio.core.execution import RunExecutionSummary
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.engines.base import PresentationEngine
from fpvs_studio.runtime.preflight import PreflightError, preflight_run_spec
from fpvs_studio.triggers.base import TriggerBackend


class _PreflightEngine(PresentationEngine):
    @property
    def engine_id(self) -> str:
        return "preflight"

    def probe_displays(self) -> list[dict[str, object]]:
        return []

    def open_session(self, *, runtime_options: Mapping[str, object] | None = None) -> None:
        return None

    def show_transition_screen(
        self,
        *,
        heading: str,
        body: str | None = None,
        countdown_seconds: float | None = None,
        continue_key: str | None = None,
    ) -> bool:
        return False

    def run_condition(
        self,
        run_spec: RunSpec,
        project_root: Path,
        *,
        runtime_options: Mapping[str, object] | None = None,
        trigger_backend: TriggerBackend | None = None,
    ) -> RunExecutionSummary:
        raise AssertionError("run_condition should not be called during preflight tests")

    def show_completion_screen(
        self,
        *,
        completed_condition_count: int,
        total_condition_count: int,
        was_aborted: bool,
    ) -> bool:
        return False

    def close_session(self) -> None:
        return None

    def abort(self) -> None:
        return None


def test_preflight_rejects_non_contiguous_stimulus_timing(
    sample_project,
    sample_project_root,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="faces-run",
    )
    run_spec.stimulus_sequence[1].on_start_frame += 1

    with pytest.raises(PreflightError, match="on_start_frame values do not align"):
        preflight_run_spec(sample_project_root, run_spec, engine=_PreflightEngine())


def test_preflight_rejects_fixation_events_beyond_run_duration(
    sample_project,
    sample_project_root,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="faces-run",
    )
    run_spec.fixation_events[-1].start_frame = run_spec.display.total_frames

    with pytest.raises(PreflightError, match="fixation event extends beyond"):
        preflight_run_spec(sample_project_root, run_spec, engine=_PreflightEngine())


def test_preflight_rejects_trigger_events_outside_run_duration(
    sample_project,
    sample_project_root,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="faces-run",
    )
    run_spec.trigger_events[0].frame_index = run_spec.display.total_frames

    with pytest.raises(PreflightError, match="trigger event falls outside"):
        preflight_run_spec(sample_project_root, run_spec, engine=_PreflightEngine())
