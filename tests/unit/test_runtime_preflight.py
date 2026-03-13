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

    def show_block_break_screen(
        self,
        *,
        completed_block_index: int,
        total_block_count: int,
        next_block_index: int,
    ) -> bool:
        return False

    def show_condition_feedback_screen(
        self,
        *,
        heading: str,
        body: str,
        continue_key: str,
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


@pytest.mark.parametrize("refresh_hz", [60.0, 120.0, 144.0])
def test_preflight_accepts_refresh_rates_compatible_with_6hz(
    sample_project,
    sample_project_root,
    refresh_hz: float,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=refresh_hz,
        project_root=sample_project_root,
        run_id=f"faces-{int(refresh_hz)}hz",
    )

    preflight_run_spec(sample_project_root, run_spec, engine=_PreflightEngine())


def test_preflight_rejects_refresh_rate_incompatible_with_6hz(
    sample_project,
    sample_project_root,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="faces-run",
    )
    run_spec.display.refresh_hz = 75.0

    with pytest.raises(PreflightError, match="display timing is incompatible"):
        preflight_run_spec(sample_project_root, run_spec, engine=_PreflightEngine())


def test_preflight_rejects_blank_50_when_frames_per_stimulus_is_odd(
    sample_project,
    sample_project_root,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=90.0,
        project_root=sample_project_root,
        run_id="faces-run",
    )
    run_spec.display.on_frames = 8
    run_spec.display.off_frames = 7
    for event in run_spec.stimulus_sequence:
        event.on_frames = 8
        event.off_frames = 7

    with pytest.raises(PreflightError, match="blank_50"):
        preflight_run_spec(sample_project_root, run_spec, engine=_PreflightEngine())
