"""Runtime preflight validation tests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from fpvs_studio.core.compiler import compile_run_spec, compile_session_plan
from fpvs_studio.core.enums import StimulusModality
from fpvs_studio.core.execution import RunExecutionSummary
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.engines.base import FixationTutorialAttemptResult, PresentationEngine
from fpvs_studio.runtime.preflight import (
    PreflightError,
    preflight_run_spec,
    preflight_session_plan,
)
from fpvs_studio.runtime.windows_display import WindowsDisplayMode
from fpvs_studio.triggers.base import TriggerBackend


class _PreflightEngine(PresentationEngine):
    def __init__(self, measured_refresh_hz: float | Exception = 60.0) -> None:
        self.measured_refresh_hz = measured_refresh_hz
        self.refresh_measurement_count = 0

    @property
    def engine_id(self) -> str:
        return "preflight"

    def probe_displays(self) -> list[dict[str, object]]:
        return []

    def measure_refresh_hz(
        self,
        *,
        runtime_options: Mapping[str, object] | None = None,
    ) -> float:
        self.refresh_measurement_count += 1
        if isinstance(self.measured_refresh_hz, Exception):
            raise self.measured_refresh_hz
        return self.measured_refresh_hz

    def open_session(self, *, runtime_options: Mapping[str, object] | None = None) -> None:
        return None

    def show_transition_screen(
        self,
        *,
        heading: str,
        body: str | None = None,
        countdown_seconds: float | None = None,
        continue_key: str | None = None,
        continue_prompt: str | None = None,
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

    def run_fixation_tutorial_attempt(
        self,
        run_spec: RunSpec,
        *,
        target_delay_seconds: float,
    ) -> FixationTutorialAttemptResult:
        raise AssertionError(
            "run_fixation_tutorial_attempt should not be called during preflight tests"
        )

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


def _patch_windows_mode(
    monkeypatch: pytest.MonkeyPatch,
    numerator: int,
    denominator: int = 1,
) -> None:
    monkeypatch.setattr(
        "fpvs_studio.runtime.display_refresh.query_primary_windows_display_mode",
        lambda: WindowsDisplayMode(r"\\.\DISPLAY1", numerator, denominator),
    )


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


def test_default_preflight_does_not_decode_image_assets(
    sample_project,
    sample_project_root,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="faces-run",
    )
    corrupt_path = sample_project_root / "stimuli" / "original-images" / "base-set" / "bad.png"
    corrupt_path.write_bytes(b"not an image")
    stimulus_id = run_spec.stimulus_sequence[0].stimulus_id
    for index, event in enumerate(run_spec.stimulus_sequence):
        if event.stimulus_id == stimulus_id:
            run_spec.stimulus_sequence[index] = event.model_copy(
                update={"image_path": "stimuli/original-images/base-set/bad.png"}
            )

    preflight_run_spec(sample_project_root, run_spec, engine=_PreflightEngine())


def test_full_preflight_rejects_corrupt_image_assets_before_engine_launch(
    sample_project,
    sample_project_root,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="faces-run",
    )
    corrupt_path = sample_project_root / "stimuli" / "original-images" / "base-set" / "bad.png"
    corrupt_path.write_bytes(b"not an image")
    stimulus_id = run_spec.stimulus_sequence[0].stimulus_id
    for index, event in enumerate(run_spec.stimulus_sequence):
        if event.stimulus_id == stimulus_id:
            run_spec.stimulus_sequence[index] = event.model_copy(
                update={"image_path": "stimuli/original-images/base-set/bad.png"}
            )

    with pytest.raises(PreflightError, match="could not be decoded"):
        preflight_run_spec(
            sample_project_root,
            run_spec,
            engine=_PreflightEngine(),
            decode_image_assets=True,
        )


@pytest.mark.parametrize("refresh_hz", [59.94, 60.0, 120.0, 144.0, 240.0])
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


def test_preflight_rejects_refresh_rate_inconsistent_with_compiled_frames(
    sample_project,
    sample_project_root,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="faces-run",
    )
    run_spec.display.refresh_hz = 120.0

    with pytest.raises(PreflightError, match="compiled frames_per_stimulus"):
        preflight_run_spec(sample_project_root, run_spec, engine=_PreflightEngine())


def test_preflight_rejects_blank_50_when_frames_per_stimulus_is_odd(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.settings.protocol.base_hz = 4.0
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
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


def test_preflight_accepts_measured_refresh_within_tolerance(
    sample_project,
    sample_project_root,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_windows_mode(monkeypatch, 144)
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=144.0,
        project_root=sample_project_root,
        run_id="faces-run",
    )
    engine = _PreflightEngine(143.8)

    preflight_run_spec(
        sample_project_root,
        run_spec,
        engine=engine,
        runtime_options={"verify_refresh_rate": True},
    )

    assert engine.refresh_measurement_count == 1


def test_preflight_rejects_measured_refresh_mismatch(
    sample_project,
    sample_project_root,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_windows_mode(monkeypatch, 60)
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=240.0,
        project_root=sample_project_root,
        run_id="faces-run",
    )

    with pytest.raises(PreflightError, match="Windows reports display mode.*expects 240 Hz"):
        preflight_run_spec(
            sample_project_root,
            run_spec,
            engine=_PreflightEngine(60.0),
            runtime_options={"verify_refresh_rate": True},
        )


def test_preflight_rejects_unavailable_refresh_measurement(
    sample_project,
    sample_project_root,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_windows_mode(monkeypatch, 60)
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="faces-run",
    )

    with pytest.raises(PreflightError, match="PsychoPy could not confirm.*unstable"):
        preflight_run_spec(
            sample_project_root,
            run_spec,
            engine=_PreflightEngine(RuntimeError("unstable")),
            runtime_options={"verify_refresh_rate": True},
        )


def test_session_preflight_measures_connected_refresh_once(
    sample_project,
    sample_project_root,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_windows_mode(monkeypatch, 60)
    session_plan = compile_session_plan(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=2026,
    )
    engine = _PreflightEngine(59.98)

    preflight_session_plan(
        sample_project_root,
        session_plan,
        engine=engine,
        runtime_options={"verify_refresh_rate": True},
    )

    assert engine.refresh_measurement_count == 1


def test_preflight_distinguishes_windows_5994_mode_from_compiled_60_hz(
    sample_project,
    sample_project_root,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_windows_mode(monkeypatch, 60_000, 1_001)
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="faces-run",
    )

    with pytest.raises(
        PreflightError,
        match=r"59\.940060 Hz \(60000/1001\).*expects 60 Hz",
    ):
        preflight_run_spec(
            sample_project_root,
            run_spec,
            engine=_PreflightEngine(59.998),
            runtime_options={"verify_refresh_rate": True},
        )


def test_preflight_accepts_word_stimuli_without_files(sample_project, sample_project_root) -> None:
    sample_project.stimulus_sets[0] = sample_project.stimulus_sets[0].model_copy(
        update={
            "modality": StimulusModality.WORD,
            "source_dir": None,
            "resolution": None,
            "image_count": 0,
            "words": ["cat", "dog"],
        }
    )
    sample_project.stimulus_sets[1] = sample_project.stimulus_sets[1].model_copy(
        update={
            "modality": StimulusModality.WORD,
            "source_dir": None,
            "resolution": None,
            "image_count": 0,
            "words": ["tool"],
        }
    )
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="word-run",
    )

    preflight_run_spec(sample_project_root, run_spec, engine=_PreflightEngine())


def test_preflight_rejects_stimulus_id_payload_collision(
    sample_project,
    sample_project_root,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="faces-run",
    )
    run_spec.stimulus_sequence[1] = run_spec.stimulus_sequence[1].model_copy(
        update={
            "stimulus_id": run_spec.stimulus_sequence[0].stimulus_id,
            "image_path": run_spec.stimulus_sequence[0].image_path,
        }
    )
    run_spec.stimulus_sequence[2] = run_spec.stimulus_sequence[2].model_copy(
        update={
            "stimulus_id": run_spec.stimulus_sequence[0].stimulus_id,
            "image_path": run_spec.stimulus_sequence[2].image_path,
        }
    )

    with pytest.raises(PreflightError, match="maps to multiple payloads"):
        preflight_run_spec(sample_project_root, run_spec, engine=_PreflightEngine())


def test_preflight_rejects_malformed_word_payload(sample_project, sample_project_root) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="faces-run",
    )
    run_spec.stimulus_sequence[0] = run_spec.stimulus_sequence[0].model_copy(
        update={
            "stimulus_modality": StimulusModality.WORD,
            "text": None,
            "image_path": None,
        }
    )

    with pytest.raises(PreflightError, match="word stimulus event has an inconsistent payload"):
        preflight_run_spec(sample_project_root, run_spec, engine=_PreflightEngine())


def test_preflight_rejects_unknown_stimulus_modality(sample_project, sample_project_root) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="faces-run",
    )
    run_spec.stimulus_sequence[0] = run_spec.stimulus_sequence[0].model_copy(
        update={"stimulus_modality": "audio"}
    )

    with pytest.raises(PreflightError, match="unknown modality"):
        preflight_run_spec(sample_project_root, run_spec, engine=_PreflightEngine())
