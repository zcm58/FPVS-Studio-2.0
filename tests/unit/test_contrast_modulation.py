"""Core sinusoidal contrast-modulation contract tests."""

from __future__ import annotations

import pytest

from fpvs_studio.core.compiler import CompileError, compile_run_spec
from fpvs_studio.core.contrast_modulation import sinusoidal_contrast_envelope
from fpvs_studio.core.enums import DutyCycleMode, StimulusModality
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.template_library import default_template
from fpvs_studio.runtime.session_export import _display_report_for_run


def test_rossion_eight_frame_envelope_matches_documented_percentages() -> None:
    assert sinusoidal_contrast_envelope(8) == pytest.approx(
        (0.0, 0.1464466, 0.5, 0.8535534, 1.0, 0.8535534, 0.5, 0.1464466)
    )


@pytest.mark.parametrize("frame_count", [15, 12, 10])
def test_frequency_agnostic_envelope_is_bounded_symmetric_and_peaks(
    frame_count: int,
) -> None:
    envelope = sinusoidal_contrast_envelope(frame_count)

    assert envelope == sinusoidal_contrast_envelope(frame_count)
    assert len(envelope) == frame_count
    assert envelope[0] == 0.0
    assert envelope[-1] < 0.1
    assert min(envelope) >= 0.0
    assert max(envelope) == 1.0
    assert all(
        envelope[frame_index] == pytest.approx(envelope[-frame_index])
        for frame_index in range(1, frame_count)
    )


def test_odd_frame_envelope_normalizes_both_sampled_peak_frames() -> None:
    envelope = sinusoidal_contrast_envelope(15)

    assert envelope[7] == 1.0
    assert envelope[8] == 1.0


@pytest.mark.parametrize("frame_count", [-1, 0, 1, 2, 3])
def test_sinusoidal_envelope_rejects_degenerate_cycles(frame_count: int) -> None:
    with pytest.raises(ValueError, match="at least 4 frames"):
        sinusoidal_contrast_envelope(frame_count)


def test_sinusoidal_envelope_requires_integer_frame_count() -> None:
    with pytest.raises(TypeError, match="must be an integer"):
        sinusoidal_contrast_envelope(10.0)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("base_hz", "expected_frames_per_stimulus"),
    [(4.0, 15), (5.0, 12), (6.0, 10)],
)
def test_compiler_resolves_sinusoidal_mode_from_frequency_to_frames(
    sample_project,
    sample_project_root,
    base_hz: float,
    expected_frames_per_stimulus: int,
) -> None:
    sinusoidal_project = sample_project.model_copy(deep=True)
    sinusoidal_project.settings.protocol.base_hz = base_hz
    sinusoidal_project.settings.display.background_color = "#808080"
    sinusoidal_project.conditions[0].duty_cycle_mode = DutyCycleMode.SINUSOIDAL
    continuous_project = sinusoidal_project.model_copy(deep=True)
    continuous_project.conditions[0].duty_cycle_mode = DutyCycleMode.CONTINUOUS

    sinusoidal = compile_run_spec(
        sinusoidal_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=2026,
        run_id="sinusoidal-run",
    )
    continuous = compile_run_spec(
        continuous_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        random_seed=2026,
        run_id="continuous-run",
    )

    assert sinusoidal.display.duty_cycle_mode == DutyCycleMode.SINUSOIDAL
    assert sinusoidal.display.frames_per_stimulus == expected_frames_per_stimulus
    assert sinusoidal.display.on_frames == expected_frames_per_stimulus
    assert sinusoidal.display.off_frames == 0
    assert sinusoidal.display.duty_cycle == 1.0
    assert len(sinusoidal_contrast_envelope(expected_frames_per_stimulus)) == (
        expected_frames_per_stimulus
    )
    assert [
        (event.role, event.stimulus_id, event.on_start_frame)
        for event in sinusoidal.stimulus_sequence
    ] == [
        (event.role, event.stimulus_id, event.on_start_frame)
        for event in continuous.stimulus_sequence
    ]
    assert sinusoidal.trigger_events == continuous.trigger_events
    assert sinusoidal.fixation_events == continuous.fixation_events


def test_compiler_rejects_sinusoidal_mode_without_neutral_gray(
    sample_project,
) -> None:
    sample_project.conditions[0].duty_cycle_mode = DutyCycleMode.SINUSOIDAL

    with pytest.raises(CompileError, match=r"Neutral Gray \(#808080\)"):
        compile_run_spec(sample_project, refresh_hz=60.0)


def test_compiler_rejects_sinusoidal_word_condition(sample_project) -> None:
    for index, stimulus_set in enumerate(sample_project.stimulus_sets):
        sample_project.stimulus_sets[index] = stimulus_set.model_copy(
            update={
                "modality": StimulusModality.WORD,
                "source_dir": None,
                "resolution": None,
                "image_count": 0,
                "words": ["word"],
            }
        )
    sample_project.settings.display.background_color = "#808080"
    sample_project.conditions[0].duty_cycle_mode = DutyCycleMode.SINUSOIDAL

    with pytest.raises(CompileError, match="currently supports images only"):
        compile_run_spec(sample_project, refresh_hz=60.0)


def test_runspec_missing_explicit_mode_loads_as_continuous(
    sample_project,
    sample_project_root,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
    )
    payload = run_spec.model_dump(mode="json")
    payload["display"].pop("duty_cycle_mode")

    loaded = RunSpec.model_validate(payload)

    assert loaded.display.duty_cycle_mode == DutyCycleMode.CONTINUOUS


def test_runtime_display_report_uses_explicit_sinusoidal_mode(
    sample_project,
    sample_project_root,
) -> None:
    sample_project.settings.display.background_color = "#808080"
    sample_project.conditions[0].duty_cycle_mode = DutyCycleMode.SINUSOIDAL
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
    )

    report = _display_report_for_run(run_spec)

    assert report.compatible is True
    assert report.duty_cycle_mode == DutyCycleMode.SINUSOIDAL


def test_project_sinusoidal_mode_round_trips_as_persisted_enum(sample_project) -> None:
    sample_project.settings.display.background_color = "#808080"
    sample_project.conditions[0].duty_cycle_mode = DutyCycleMode.SINUSOIDAL

    loaded = ProjectFile.model_validate_json(sample_project.model_dump_json())

    assert loaded.settings.display.background_color == "#808080"
    assert loaded.conditions[0].duty_cycle_mode == DutyCycleMode.SINUSOIDAL


def test_protocol_template_advertises_all_three_presentation_modes() -> None:
    assert default_template().supported_duty_cycle_modes == (
        DutyCycleMode.CONTINUOUS,
        DutyCycleMode.BLANK_50,
        DutyCycleMode.SINUSOIDAL,
    )
