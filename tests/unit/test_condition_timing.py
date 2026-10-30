"""Per-condition frequency ownership and atomic frame-preserving authoring edits."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fpvs_studio.core.compiler import compile_run_spec, compile_session_plan
from fpvs_studio.core.condition_timing import (
    effective_condition_base_hz,
    propose_condition_frequencies,
)
from fpvs_studio.core.enums import DutyCycleMode, ExperimentCategory, StimulusModality
from fpvs_studio.core.models import AttentionalBlinkSettings, Condition, ProjectFile
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.validation import (
    condition_fixation_guidance,
    validate_condition_repeat_cycle_consistency,
    validate_project,
)


@pytest.fixture
def timing_project(sample_project):
    project = sample_project.model_copy(deep=True)
    project.conditions[0].oddball_cycle_repeats_per_sequence = 144
    project.conditions.append(project.conditions[0].model_copy(update={
        "condition_id": "houses", "name": "Houses", "order_index": 1,
    }))
    return project


def test_inherited_legacy_rate_and_serialized_shape_are_preserved(sample_project):
    assert sample_project.settings.protocol.base_hz == 6
    sample_project.settings.protocol.base_hz = 5
    payload = sample_project.model_dump(mode="json")
    assert "base_hz" not in payload["conditions"][0]
    loaded = ProjectFile.model_validate(payload)
    assert loaded.schema_version == sample_project.schema_version
    assert effective_condition_base_hz(loaded, loaded.conditions[0]) == 5
    assert propose_condition_frequencies(loaded).model_dump(mode="json") == payload


@pytest.mark.parametrize("rate", [0, -1, float("nan"), float("inf"), -float("inf")])
def test_condition_override_requires_positive_finite_rate(sample_project, rate):
    with pytest.raises(ValidationError):
        Condition.model_validate({**sample_project.conditions[0].model_dump(), "base_hz": rate})


def test_native_ab_overrides_are_rejected_at_condition_and_project_boundaries(sample_project):
    with pytest.raises(ValidationError, match="Attentional-Blink"):
        Condition.model_validate({
            **sample_project.conditions[0].model_dump(), "base_hz": 3,
            "attentional_blink": AttentionalBlinkSettings().model_dump(),
        })
    payload = sample_project.model_dump(mode="json")
    payload["experiment_category"] = ExperimentCategory.ATTENTIONAL_BLINK.value
    payload["conditions"][0]["base_hz"] = 3
    with pytest.raises(ValidationError, match="Attentional-Blink"):
        ProjectFile.model_validate(payload)


def test_override_preserves_stream_frames_and_promotes_only_the_draft(timing_project):
    original = timing_project.model_dump(mode="json")
    condition_id = timing_project.conditions[0].condition_id
    draft = propose_condition_frequencies(
        timing_project, overrides={condition_id: 3}, refresh_hz=60,
    )
    assert timing_project.model_dump(mode="json") == original
    assert draft.schema_version.value == "1.12.0"
    assert draft.conditions[0].stream_duration_seconds == 120
    assert draft.conditions[0].base_hz == 3
    assert draft.conditions[0].oddball_cycle_repeats_per_sequence == 72
    assert draft.conditions[1].base_hz is None
    assert draft.conditions[1].oddball_cycle_repeats_per_sequence == 144
    assert validate_condition_repeat_cycle_consistency(draft) == []
    durations = condition_fixation_guidance(draft, refresh_hz=60)
    assert {row.condition_duration_seconds for row in durations} == {120}


def test_shared_rate_changes_only_inherited_conditions_and_preserves_seconds(timing_project):
    draft = propose_condition_frequencies(
        timing_project, overrides={"houses": 3}, refresh_hz=60,
    )
    draft = propose_condition_frequencies(draft, shared_base_hz=4, refresh_hz=60)
    assert draft.settings.protocol.base_hz == 4
    assert draft.conditions[0].oddball_cycle_repeats_per_sequence == 96
    assert draft.conditions[1].base_hz == 3
    assert draft.conditions[1].oddball_cycle_repeats_per_sequence == 72
    assert {row.condition_duration_seconds for row in condition_fixation_guidance(
        draft, refresh_hz=60,
    )} == {120}


def test_frequency_edits_require_explicit_refresh_without_inventing_legacy_seconds(timing_project):
    assert timing_project.settings.display.preferred_refresh_hz is None
    original = timing_project.model_dump(mode="json")
    with pytest.raises(ValueError, match="Select a monitor refresh rate"):
        propose_condition_frequencies(timing_project, shared_base_hz=3)
    assert timing_project.model_dump(mode="json") == original


def test_incompatible_seconds_are_rejected_with_valid_choices_and_no_mutation(sample_project):
    condition_id = sample_project.conditions[0].condition_id
    original = sample_project.model_dump(mode="json")
    with pytest.raises(ValueError, match="Valid durations.*121 or 122 seconds"):
        propose_condition_frequencies(sample_project, overrides={condition_id: 5}, refresh_hz=60)
    assert sample_project.model_dump(mode="json") == original


@pytest.mark.parametrize("mode,rate,match", [
    (DutyCycleMode.BLANK_50, 4, "even number of frames"),
    (DutyCycleMode.SINUSOIDAL, 30, "at least 4 frames"),
    (DutyCycleMode.CONTINUOUS, 61, "faster than"),
])
def test_incompatible_mode_or_display_rate_does_not_mutate(timing_project, mode, rate, match):
    timing_project.conditions[1].duty_cycle_mode = mode
    original = timing_project.model_dump(mode="json")
    with pytest.raises(ValueError, match=match):
        propose_condition_frequencies(timing_project, shared_base_hz=rate, refresh_hz=60)
    assert timing_project.model_dump(mode="json") == original


def test_shared_edit_is_atomic_when_only_a_later_condition_has_invalid_blank_timing(timing_project):
    timing_project.conditions[1].duty_cycle_mode = DutyCycleMode.BLANK_50
    original = timing_project.model_dump(mode="json")
    with pytest.raises(ValueError, match="Houses.*even number"):
        propose_condition_frequencies(timing_project, shared_base_hz=4, refresh_hz=60)
    assert timing_project.model_dump(mode="json") == original


@pytest.mark.parametrize("has_custom_conditions", [False, True])
def test_shared_rate_is_display_validated_without_inherited_conditions(
    timing_project, has_custom_conditions,
):
    if has_custom_conditions:
        for condition in timing_project.conditions:
            condition.base_hz = 6
    else:
        timing_project.conditions = []
    original = timing_project.model_dump(mode="json")
    with pytest.raises(ValueError, match="faster than"):
        propose_condition_frequencies(timing_project, shared_base_hz=61, refresh_hz=60)
    assert timing_project.model_dump(mode="json") == original


def test_explicit_masking_catch_source_frequency_mismatch_rejects_the_entire_draft():
    from tests.unit.test_masking_catch_conditions import explicit_catch_project

    project = explicit_catch_project()
    for condition in project.conditions:
        condition.oddball_cycle_repeats_per_sequence = 144
    original = project.model_dump(mode="json")
    with pytest.raises(ValueError, match="catch condition.*same stimulus presentation frequency"):
        propose_condition_frequencies(
            project, overrides={"color-1": project.settings.protocol.base_hz / 2}, refresh_hz=60,
        )
    assert project.model_dump(mode="json") == original


def test_reset_to_shared_preserves_valid_duration_and_rejects_incompatible_duration(timing_project):
    condition_id = timing_project.conditions[0].condition_id
    custom = propose_condition_frequencies(
        timing_project, overrides={condition_id: 3}, refresh_hz=60,
    )
    restored = propose_condition_frequencies(custom, overrides={condition_id: None}, refresh_hz=60)
    assert restored.conditions[0].base_hz is None
    assert restored.conditions[0].oddball_cycle_repeats_per_sequence == 144
    custom.conditions[0].base_hz = 5
    custom.conditions[0].oddball_cycle_repeats_per_sequence = 146
    custom.conditions[0].stream_duration_seconds = 146
    original = custom.model_dump(mode="json")
    with pytest.raises(ValueError, match="Valid durations"):
        propose_condition_frequencies(custom, overrides={condition_id: None}, refresh_hz=60)
    assert custom.model_dump(mode="json") == original


def test_requested_rate_with_same_frame_quantization_retains_counts(timing_project):
    condition_id = timing_project.conditions[0].condition_id
    draft = propose_condition_frequencies(
        timing_project, overrides={condition_id: 6.01}, refresh_hz=60,
    )
    assert draft.conditions[0].oddball_cycle_repeats_per_sequence == 144
    report = validate_project(draft, refresh_hz=60)
    assert any(issue.location == f"conditions.{condition_id}.base_hz"
               and "Approximate frame timing" in issue.message for issue in report.issues)


@pytest.mark.parametrize("refresh_hz", [59.94, 60, 120, 144, 240])
def test_preserved_stream_frames_follow_the_selected_refresh_not_nominal_hz(
    timing_project, refresh_hz,
):
    condition_id = timing_project.conditions[0].condition_id
    draft = propose_condition_frequencies(
        timing_project, overrides={condition_id: 3}, refresh_hz=refresh_hz,
    )
    assert {row.total_frames for row in condition_fixation_guidance(
        draft, refresh_hz=refresh_hz,
    )} == {round(refresh_hz / 6) * 144 * 5}


@pytest.mark.parametrize("modality", [StimulusModality.IMAGE, StimulusModality.WORD])
def test_run_and_session_compilers_use_each_condition_frequency(
    timing_project, sample_project_root, modality,
):
    if modality == StimulusModality.WORD:
        for stimulus_set in timing_project.stimulus_sets:
            stimulus_set.modality = modality
            stimulus_set.words = [f"{stimulus_set.set_id}-{index}" for index in range(3)]
            stimulus_set.source_dir = None
            stimulus_set.image_count = 0
            stimulus_set.resolution = None
    condition_id = timing_project.conditions[0].condition_id
    draft = propose_condition_frequencies(
        timing_project, overrides={condition_id: 3}, refresh_hz=60,
    )
    run = compile_run_spec(
        draft, condition_id=condition_id, refresh_hz=60, project_root=sample_project_root,
    )
    assert run.condition.base_hz == 3
    assert run.condition.oddball_hz == 0.6
    assert run.display.frames_per_stimulus == 20
    assert run.display.total_frames == 7200
    assert next(event.frame_index for event in run.trigger_events
                if event.label == "oddball_onset") == 80
    assert {event.code for event in run.trigger_events if event.label == "oddball_onset"} == {55}
    plan = compile_session_plan(draft, refresh_hz=60, project_root=sample_project_root)
    runs = [entry.run_spec for entry in plan.ordered_entries()]
    assert {item.condition.base_hz for item in runs} == {3, 6}
    assert {item.display.total_frames for item in runs} == {7200}
    assert {item.display.frames_per_stimulus for item in runs} == {10, 20}


def test_override_json_round_trip_keeps_inherited_conditions_omitted(
    timing_project, tmp_path,
):
    condition_id = timing_project.conditions[0].condition_id
    draft = propose_condition_frequencies(
        timing_project, overrides={condition_id: 3}, refresh_hz=60,
    )
    path = tmp_path / "project.json"
    save_project_file(draft, path)
    loaded = load_project_file(path)
    assert loaded == draft
    payload = loaded.model_dump(mode="json")
    assert payload["conditions"][0]["base_hz"] == 3
    assert "base_hz" not in payload["conditions"][1]
