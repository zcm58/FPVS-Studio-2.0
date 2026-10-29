"""Authoritative stream seconds, exact frame resolution and atomic timing edits."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fpvs_studio.core.compiler import compile_run_spec, compile_session_plan
from fpvs_studio.core.condition_timing import (
    ConditionDurationError,
    condition_stream_duration_seconds,
    propose_condition_timing,
    resolve_condition_stream_timing,
)
from fpvs_studio.core.enums import DutyCycleMode, ExperimentCategory, StimulusModality
from fpvs_studio.core.models import Condition, ConditionDefaults, ProjectFile
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.validation import (
    condition_fixation_guidance,
    condition_stimulus_repeat_guidance,
    validate_condition_repeat_cycle_consistency,
    validate_project,
)


@pytest.fixture
def duration_project(sample_project):
    project = sample_project.model_copy(deep=True)
    project.settings.fixation_task.enabled = False
    project.conditions.append(project.conditions[0].model_copy(update={
        "condition_id": "houses", "name": "Houses", "order_index": 1,
    }))
    return project


def test_legacy_counts_and_unknown_duration_are_not_implicitly_migrated(duration_project):
    condition = duration_project.conditions[0]
    condition.sequence_count = 2
    condition.oddball_cycle_repeats_per_sequence = 144
    before = duration_project.model_dump(mode="json")
    assert condition_stream_duration_seconds(duration_project, condition, None) is None
    assert condition_stream_duration_seconds(duration_project, condition, 60) == 240
    assert propose_condition_timing(duration_project).model_dump(mode="json") == before
    assert "stream_duration_seconds" not in before["conditions"][0]
    assert "stream_duration_seconds" not in before["settings"]["condition_defaults"]


def test_explicit_total_seconds_do_not_multiply_legacy_sequences(duration_project):
    condition_id = duration_project.conditions[0].condition_id
    duration_project.conditions[0].sequence_count = 2
    draft = propose_condition_timing(
        duration_project, durations={condition_id: 5 / 6}, refresh_hz=60,
    )
    condition = draft.conditions[0]
    assert condition.sequence_count == 1
    assert condition.oddball_cycle_repeats_per_sequence == 1
    assert resolve_condition_stream_timing(draft, condition, 60).total_frames == 50
    assert duration_project.conditions[0].sequence_count == 2
    assert duration_project.conditions[1].stream_duration_seconds is None


def test_independent_durations_compile_and_keep_lead_in_outside_stream(
    duration_project, sample_project_root,
):
    ids = [condition.condition_id for condition in duration_project.conditions]
    draft = propose_condition_timing(
        duration_project, durations={ids[0]: 120, ids[1]: 60}, refresh_hz=60,
    )
    draft.settings.presentation.pre_stream_fixation_seconds = 10
    plan = compile_session_plan(draft, refresh_hz=60, project_root=sample_project_root)
    assert len(plan.ordered_entries()) == draft.settings.session.block_count * 2
    for entry in plan.ordered_entries():
        requested = 120 if entry.condition_id == ids[0] else 60
        assert entry.run_spec.display.total_frames == requested * 60
        assert entry.run_spec.condition.requested_duration_seconds == requested
        assert entry.run_spec.pre_stream_fixation_frames == 600
        assert entry.run_spec.schema_version == "1.6.0"


def test_frequency_and_seconds_are_one_atomic_recoverable_draft(duration_project):
    condition_id = duration_project.conditions[0].condition_id
    before = duration_project.model_dump(mode="json")
    with pytest.raises(ConditionDurationError):
        propose_condition_timing(duration_project, overrides={condition_id: 5}, refresh_hz=60)
    draft = propose_condition_timing(
        duration_project, overrides={condition_id: 5}, durations={condition_id: 122}, refresh_hz=60,
    )
    assert draft.conditions[0].stream_duration_seconds == 122
    assert draft.conditions[0].oddball_cycle_repeats_per_sequence == 122
    assert duration_project.model_dump(mode="json") == before


def test_explicit_duration_request_validates_even_when_its_value_is_unchanged(duration_project):
    condition_id = duration_project.conditions[0].condition_id
    draft = propose_condition_timing(
        duration_project, durations={condition_id: 10}, refresh_hz=60,
    )
    draft.settings.protocol.oddball_every_n = 7
    before = draft.model_dump(mode="json")
    with pytest.raises(ConditionDurationError):
        propose_condition_timing(draft, durations={condition_id: 10}, refresh_hz=60)
    assert draft.model_dump(mode="json") == before


def test_duration_error_exposes_full_precision_usable_neighbors_at_5994(duration_project):
    condition_id = duration_project.conditions[0].condition_id
    with pytest.raises(ConditionDurationError) as caught:
        propose_condition_timing(duration_project, durations={condition_id: 120}, refresh_hz=59.94)
    error = caught.value
    assert error.condition_id == condition_id
    assert error.requested_seconds == 120
    assert error.valid_durations[0] < 120 < error.valid_durations[1]
    for candidate in error.valid_durations:
        for value in (candidate, round(candidate, 9)):
            draft = propose_condition_timing(
                duration_project, durations={condition_id: value}, refresh_hz=59.94,
            )
            resolved = resolve_condition_stream_timing(draft, draft.conditions[0], 59.94)
            assert resolved.duration_seconds == pytest.approx(candidate, abs=1e-9)
            assert resolved.total_frames % 50 == 0


@pytest.mark.parametrize("seconds", [0, -1, float("nan"), float("inf"), -float("inf")])
def test_invalid_seconds_are_rejected_in_models_and_friendly_proposals(duration_project, seconds):
    condition = duration_project.conditions[0]
    with pytest.raises(ValidationError):
        Condition.model_validate({**condition.model_dump(), "stream_duration_seconds": seconds})
    with pytest.raises(ValidationError):
        ConditionDefaults(stream_duration_seconds=seconds)
    before = duration_project.model_dump(mode="json")
    with pytest.raises(ValueError, match="finite number greater than zero"):
        propose_condition_timing(
            duration_project, durations={condition.condition_id: seconds}, refresh_hz=60,
        )
    assert duration_project.model_dump(mode="json") == before


def test_finite_seconds_overflow_is_actionable_and_does_not_escape_validation(duration_project):
    condition_id = duration_project.conditions[0].condition_id
    with pytest.raises(ValueError, match="too large"):
        propose_condition_timing(duration_project, durations={condition_id: 1e308}, refresh_hz=240)
    duration_project.conditions[0].stream_duration_seconds = 1e308
    report = validate_project(duration_project, refresh_hz=240)
    assert not report.is_valid
    assert any("too large" in issue.message for issue in report.issues)


@pytest.mark.parametrize("mode", [
    DutyCycleMode.CONTINUOUS, DutyCycleMode.BLANK_50, DutyCycleMode.SINUSOIDAL,
])
@pytest.mark.parametrize("refresh_hz", [59.94, 60, 120, 144, 240])
def test_seconds_compile_as_complete_cycles_across_supported_image_modes_and_refreshes(
    duration_project, sample_project_root, mode, refresh_hz,
):
    condition = duration_project.conditions[0]
    condition.duty_cycle_mode = mode
    if mode == DutyCycleMode.SINUSOIDAL:
        duration_project.settings.display.background_color = "#808080"
    frame_count = round(refresh_hz / 6)
    seconds = 12 * 5 * frame_count / refresh_hz
    draft = propose_condition_timing(
        duration_project, durations={condition.condition_id: seconds}, refresh_hz=refresh_hz,
    )
    run = compile_run_spec(
        draft, condition_id=condition.condition_id, refresh_hz=refresh_hz,
        project_root=sample_project_root,
    )
    assert run.condition.total_oddball_cycles == 12
    assert run.display.total_frames == 12 * 5 * frame_count
    assert run.condition.requested_duration_seconds == seconds


def test_word_duration_uses_authoritative_seconds_and_ignores_stale_legacy_cache(
    duration_project, sample_project_root,
):
    for stimulus_set in duration_project.stimulus_sets:
        stimulus_set.modality = StimulusModality.WORD
        stimulus_set.words = [f"{stimulus_set.set_id}-{index}" for index in range(3)]
        stimulus_set.source_dir = None
        stimulus_set.image_count = 0
        stimulus_set.resolution = None
    condition = duration_project.conditions[0]
    draft = propose_condition_timing(
        duration_project, durations={condition.condition_id: 120}, refresh_hz=60,
    )
    draft.conditions[0].sequence_count = 99
    draft.conditions[0].oddball_cycle_repeats_per_sequence = 999
    run = compile_run_spec(
        draft, condition_id=condition.condition_id, refresh_hz=60, project_root=sample_project_root,
    )
    assert run.condition.total_stimuli == 720
    assert run.display.total_frames == 7200
    rows = condition_stimulus_repeat_guidance(draft, refresh_hz=60)
    assert next(row for row in rows if row.condition_id == condition.condition_id
                and row.role == "oddball").presentation_count == 144


def test_unknown_refresh_reports_requested_seconds_without_inventing_exposure_counts(
    duration_project,
):
    duration_project.conditions[0].stream_duration_seconds = 120
    condition = duration_project.conditions[0]
    assert condition_stream_duration_seconds(duration_project, condition, None) == 120
    assert not any(row.condition_id == condition.condition_id
                   for row in condition_stimulus_repeat_guidance(duration_project))
    report = validate_project(duration_project)
    assert any("Select a monitor refresh rate" in issue.message for issue in report.issues)
    with pytest.raises(ValueError, match="Select a monitor refresh rate"):
        propose_condition_timing(duration_project, durations={condition.condition_id: 60})


@pytest.mark.parametrize("minimum,accepted", [(2, True), (4, False)])
def test_short_stream_fixation_guard_uses_feasible_randomized_candidates(
    duration_project, minimum, accepted,
):
    settings = duration_project.settings.fixation_task
    settings.enabled = True
    settings.target_count_mode = "randomized"
    settings.target_count_min = minimum
    settings.target_count_max = 10
    condition_id = duration_project.conditions[0].condition_id
    before = duration_project.model_dump(mode="json")
    if accepted:
        draft = propose_condition_timing(
            duration_project, durations={condition_id: 5}, refresh_hz=60,
        )
        row = condition_fixation_guidance(draft, refresh_hz=60)[0]
        assert row.estimated_max_color_changes_per_condition == 3
    else:
        with pytest.raises(ValueError, match="fixation color-change settings do not fit"):
            propose_condition_timing(duration_project, durations={condition_id: 5}, refresh_hz=60)
    assert duration_project.model_dump(mode="json") == before


def test_native_ab_rejects_authored_duration_fields(duration_project):
    payload = duration_project.model_dump(mode="json")
    payload["experiment_category"] = ExperimentCategory.ATTENTIONAL_BLINK.value
    payload["conditions"][0]["stream_duration_seconds"] = 120
    with pytest.raises(ValidationError, match="Attentional-Blink"):
        ProjectFile.model_validate(payload)


def test_masking_same_cached_counts_cannot_hide_different_authored_seconds():
    from tests.unit.test_masking_catch_conditions import ordinary_project

    project = ordinary_project()
    project.conditions[0].stream_duration_seconds = 1
    project.conditions[1].stream_duration_seconds = 2
    assert validate_condition_repeat_cycle_consistency(project, refresh_hz=60)


def test_requested_source_and_compiled_metadata_round_trip_without_changing_legacy_shape(
    duration_project, sample_project_root, tmp_path,
):
    condition_id = duration_project.conditions[0].condition_id
    legacy_run = compile_run_spec(
        duration_project, condition_id=condition_id, refresh_hz=60,
        project_root=sample_project_root,
    )
    assert "requested_duration_seconds" not in legacy_run.model_dump()["condition"]
    draft = propose_condition_timing(duration_project, durations={condition_id: 120}, refresh_hz=60)
    assert draft.schema_version.value == "1.12.0"
    path = tmp_path / "project.json"
    save_project_file(draft, path)
    assert load_project_file(path) == draft
    run = compile_run_spec(
        draft, condition_id=condition_id, refresh_hz=60, project_root=sample_project_root,
    )
    assert RunSpec.model_validate_json(run.model_dump_json()) == run
    payload = run.model_dump(mode="json")
    payload["condition"]["requested_duration_seconds"] = 121
    with pytest.raises(ValidationError, match="does not match compiled"):
        RunSpec.model_validate(payload)
    payload["condition"]["requested_duration_seconds"] = 120
    payload["schema_version"] = "1.1.0"
    with pytest.raises(ValidationError, match="schema 1.6.0"):
        RunSpec.model_validate(payload)
