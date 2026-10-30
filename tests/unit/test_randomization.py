"""Independent, stable occurrence schedules and explicit seed provenance."""

import pytest
from pydantic import ValidationError

from fpvs_studio.core.compiler import CompileError, compile_run_spec, compile_session_plan
from fpvs_studio.core.condition_modifiers import assign_modifier
from fpvs_studio.core.data_sharing import protocol_fingerprint
from fpvs_studio.core.masking_presets import create_masking_modifier
from fpvs_studio.core.models import ProjectFile, RandomizationSeeds, SessionSettings, StimulusSet
from fpvs_studio.core.randomization import (
    configured_randomization_seeds,
    derive_schedule_seed,
    effective_randomization_mode,
    supports_independent_randomization,
)
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.session_plan import SessionBlock, SessionPlan


@pytest.fixture
def fixed_project(multi_condition_project):
    project = multi_condition_project
    project.settings.session = SessionSettings.model_validate({
        **project.settings.session.model_dump(), "randomization_mode": "fixed",
        "session_seed": 101, "stimulus_seed": 202, "fixation_seed": 303,
    })
    for condition in project.conditions:
        condition.oddball_cycle_repeats_per_sequence = 24
    fixation = project.settings.fixation_task
    fixation.enabled = True
    fixation.changes_per_sequence = 3
    fixation.target_duration_ms = 100
    fixation.min_gap_ms = 100
    return ProjectFile.model_validate(project.model_dump())


def _schedules(plan):
    return {
        (entry.condition_id, entry.condition_presentation_index): (
            [(event.role, event.image_path, event.text)
             for event in entry.run_spec.stimulus_sequence],
            entry.run_spec.fixation.realized_target_count,
            [(event.start_frame, event.duration_frames)
             for event in entry.run_spec.fixation_events],
        ) for entry in plan.ordered_entries()
    }


@pytest.mark.parametrize("modality", ["image", "word"])
@pytest.mark.parametrize("count_mode", ["fixed", "randomized"])
def test_domains_are_independent_and_repeats_match_across_participants(
    fixed_project, multi_condition_project_root, modality, count_mode,
):
    project = fixed_project
    if modality == "word":
        project.stimulus_sets = [StimulusSet(
            set_id=item.set_id, name=item.name, modality="word",
            words=[f"{item.set_id}-{index}" for index in range(7)],
        ) for item in project.stimulus_sets]
    project.settings.fixation_task.target_count_mode = count_mode
    project.settings.fixation_task.target_count_min = 2
    project.settings.fixation_task.target_count_max = 5
    project.settings.fixation_task.no_immediate_repeat_count = False

    def compile(project, participant="participant-a"):
        return compile_session_plan(project, refresh_hz=60,
                                    project_root=multi_condition_project_root,
                                    session_id=participant)

    first = compile(project)
    second = compile(project, "participant-b")
    schedules = _schedules(first)
    assert schedules == _schedules(second)
    assert first.schema_version == "1.7.0"
    assert first.randomization_mode == "fixed"
    assert first.randomization_seeds == configured_randomization_seeds(project)
    assert all(entry.run_spec.schema_version == "1.7.0" for entry in first.ordered_entries())
    for condition in project.conditions:
        one, two = schedules[(condition.condition_id, 1)], schedules[(condition.condition_id, 2)]
        assert one[0] != two[0]
        assert one[2] != two[2]

    order = project.model_copy(deep=True)
    order.settings.session.session_seed += 1
    assert _schedules(compile(order)) == schedules
    assert [entry.condition_id for entry in compile(order).ordered_entries()] != [
        entry.condition_id for entry in first.ordered_entries()
    ]
    stimulus = project.model_copy(deep=True)
    stimulus.settings.session.stimulus_seed += 1
    changed_stimulus = _schedules(compile(stimulus))
    assert all(changed_stimulus[key][1:] == values[1:] for key, values in schedules.items())
    assert any(changed_stimulus[key][0] != values[0] for key, values in schedules.items())
    fixation = project.model_copy(deep=True)
    fixation.settings.session.fixation_seed += 1
    changed_fixation = _schedules(compile(fixation))
    assert all(changed_fixation[key][0] == values[0] for key, values in schedules.items())
    assert any(changed_fixation[key][1:] != values[1:] for key, values in schedules.items())
    assert [entry.condition_id for entry in compile(fixation).ordered_entries()] == [
        entry.condition_id for entry in first.ordered_entries()
    ]


def test_chronological_namespaces_ignore_global_position_and_other_conditions(
    fixed_project, multi_condition_project_root,
):
    project = fixed_project
    first = compile_session_plan(project, refresh_hz=60, project_root=multi_condition_project_root)
    selected = [condition.condition_id for condition in project.conditions[:2]]
    subset = compile_session_plan(project, refresh_hz=60,
                                  project_root=multi_condition_project_root,
                                  condition_ids=selected)
    assert _schedules(subset) == {
        key: value for key, value in _schedules(first).items() if key[0] in selected
    }
    assert derive_schedule_seed(202, domain="stimulus-order", condition_id="a-b",
                                presentation_index=1) != derive_schedule_seed(
        202, domain="stimulus-order", condition_id="a", presentation_index=1,
    )


@pytest.mark.parametrize("mode", ["fixed", "new"])
def test_neighbor_count_conflicts_are_reported_without_seed_repair(
    fixed_project, multi_condition_project_root, mode,
):
    project = fixed_project
    project.settings.session.randomization_mode = mode
    fixation = project.settings.fixation_task
    fixation.target_count_mode = "randomized"
    fixation.target_count_min = fixation.target_count_max = 2
    fixation.no_immediate_repeat_count = True
    before = project.model_dump()
    with pytest.raises(CompileError,
                       match="Independent fixation schedules conflict.*not be rerolled"):
        compile_session_plan(project, refresh_hz=60, project_root=multi_condition_project_root)
    assert project.model_dump() == before
    fixation.target_count_mode = "fixed"
    compile_session_plan(project, refresh_hz=60, project_root=multi_condition_project_root)


@pytest.mark.parametrize("changes", [
    {"randomization_mode": "unknown"},
    {"randomization_mode": "fixed"},
    {"stimulus_seed": 1},
    {"randomization_mode": "new", "stimulus_seed": True, "fixation_seed": 2},
    {"randomization_mode": "fixed", "stimulus_seed": 1, "fixation_seed": -1},
    {"randomization_mode": "fixed", "stimulus_seed": 1.5, "fixation_seed": 2},
    {"randomization_mode": "fixed", "stimulus_seed": 1, "fixation_seed": 2**31},
    {"randomization_mode": "fixed", "stimulus_seed": 1, "fixation_seed": 2,
     "session_seed": True},
    {"randomization_mode": "fixed", "stimulus_seed": 1, "fixation_seed": 2,
     "session_seed": 1.0},
    {"randomization_mode": "fixed", "stimulus_seed": 1, "fixation_seed": 2,
     "session_seed": "1"},
])
def test_malformed_policy_and_seeds_are_rejected(changes):
    with pytest.raises(ValidationError):
        SessionSettings.model_validate({"session_seed": 1, **changes})


def test_explicit_policy_requires_order_seed_without_resolving_entropy(monkeypatch):
    monkeypatch.setattr("fpvs_studio.core.models.random.SystemRandom",
                        lambda: pytest.fail("Missing fixed seed must not generate entropy."))
    with pytest.raises(ValidationError, match="requires a condition-order seed"):
        SessionSettings.model_validate({
            "randomization_mode": "fixed", "stimulus_seed": 1, "fixation_seed": 2,
        })


def test_legacy_loading_has_no_rewrite_or_entropy_and_large_seeds_need_explicit_edit(
    sample_project, sample_project_root, monkeypatch,
):
    before = sample_project.model_dump_json()
    assert effective_randomization_mode(sample_project) == "new"
    assert "stimulus_seed" not in sample_project.settings.session.model_dump()
    monkeypatch.setattr("fpvs_studio.core.randomization.generate_randomization_seeds",
                        lambda: pytest.fail("Compilation must not resolve fresh entropy."))
    first = compile_session_plan(sample_project, refresh_hz=60, project_root=sample_project_root)
    second = compile_session_plan(sample_project, refresh_hz=60, project_root=sample_project_root)
    assert first.randomization_seeds == second.randomization_seeds
    assert sample_project.model_dump_json() == before
    sample_project.settings.session.session_seed = 2**80
    loaded = ProjectFile.model_validate_json(sample_project.model_dump_json())
    assert loaded.settings.session.session_seed == 2**80
    with pytest.raises(ValueError, match="Edit the condition-order seed"):
        configured_randomization_seeds(loaded)


def test_fixed_snapshot_override_is_rejected_and_new_snapshot_is_recorded(
    fixed_project, multi_condition_project_root,
):
    project = fixed_project
    seeds = RandomizationSeeds(condition_order_seed=4, stimulus_seed=5, fixation_seed=6)
    with pytest.raises(CompileError, match="configured seed triplet"):
        compile_session_plan(project, refresh_hz=60, resolved_seeds=seeds)
    project.settings.session.randomization_mode = "new"
    plan = compile_session_plan(project, refresh_hz=60, project_root=multi_condition_project_root,
                                resolved_seeds=seeds)
    assert plan.randomization_seeds == seeds
    assert plan.random_seed == 4
    assert all(entry.run_spec.randomization.seeds == seeds for entry in plan.ordered_entries())
    entry = plan.ordered_entries()[3]
    recovered = plan.model_copy(deep=True, update={
        "total_runs": 1, "blocks": [SessionBlock(block_index=0,
            condition_order=[entry.condition_id], entries=[entry])],
    })
    restored = SessionPlan.model_validate_json(recovered.model_dump_json())
    assert restored.ordered_entries()[0].run_spec.randomization == entry.run_spec.randomization
    assert restored.randomization_seeds == seeds


def test_standalone_legacy_run_seed_is_preserved_and_explicit_preview_uses_triplet(
    sample_project, sample_project_root,
):
    legacy = compile_run_spec(sample_project, refresh_hz=60,
                              project_root=sample_project_root, random_seed=42)
    assert legacy.random_seed == 42
    assert legacy.randomization is None
    assert "randomization" not in legacy.model_dump()
    preview = compile_run_spec(sample_project, refresh_hz=60, project_root=sample_project_root,
                              resolved_seeds=configured_randomization_seeds(sample_project))
    assert preview.randomization.condition_presentation_index == 1
    assert preview.schema_version == "1.7.0"


def test_protocol_identity_treats_fixed_and_fresh_seeds_intentionally(
    sample_project, sample_project_root,
):
    legacy = protocol_fingerprint(sample_project, sample_project_root)
    project = sample_project.model_copy(deep=True)
    project.settings.session = SessionSettings.model_validate({
        **project.settings.session.model_dump(), "randomization_mode": "new",
        "stimulus_seed": 100, "fixation_seed": 200,
    })
    project = ProjectFile.model_validate(project.model_dump())
    assert protocol_fingerprint(project, sample_project_root) == legacy
    for field in ("session_seed", "stimulus_seed", "fixation_seed"):
        setattr(project.settings.session, field, getattr(project.settings.session, field) + 1)
        assert protocol_fingerprint(project, sample_project_root) == legacy
    project.settings.session.randomization_mode = "fixed"
    fixed = protocol_fingerprint(project, sample_project_root)
    assert fixed != legacy
    for field in ("session_seed", "stimulus_seed", "fixation_seed"):
        changed = project.model_copy(deep=True)
        setattr(changed.settings.session, field, getattr(changed.settings.session, field) + 1)
        assert protocol_fingerprint(changed, sample_project_root) != fixed


def test_mixed_project_ordinary_subsets_use_independent_domains_without_changing_masking(
    sample_project, sample_project_root,
):
    sample_project.conditions.append(sample_project.conditions[0].model_copy(deep=True, update={
        "condition_id": "masked", "name": "Masked", "order_index": 1,
    }))
    project = assign_modifier(
        sample_project, create_masking_modifier(variant="color"), ["masked"],
    )
    assert not supports_independent_randomization(project)
    seeds = configured_randomization_seeds(project)
    ordinary = compile_session_plan(project, refresh_hz=60, project_root=sample_project_root,
                                    condition_ids=["faces"], resolved_seeds=seeds)
    assert ordinary.randomization_seeds == seeds
    assert ordinary.ordered_entries()[0].run_spec.randomization is not None
    preview = compile_run_spec(project, refresh_hz=60, project_root=sample_project_root,
                               condition_id="faces", resolved_seeds=seeds)
    assert preview.randomization is not None
    with pytest.raises(CompileError, match="unavailable for native AB/masking"):
        compile_session_plan(project, refresh_hz=60, condition_ids=["masked"],
                             resolved_seeds=seeds)


def test_seed_provenance_rejects_tampering_and_noninteger_algorithm_versions(
    fixed_project, multi_condition_project_root,
):
    plan = compile_session_plan(fixed_project, refresh_hz=60,
                                project_root=multi_condition_project_root)
    run = plan.ordered_entries()[0].run_spec
    for value in (True, 1.0, "1", 2):
        payload = run.model_dump()
        payload["randomization"]["algorithm_version"] = value
        with pytest.raises(ValidationError):
            RunSpec.model_validate(payload)
        session_payload = plan.model_dump()
        session_payload["randomization_algorithm_version"] = value
        with pytest.raises(ValidationError):
            SessionPlan.model_validate(session_payload)
    payload = run.model_dump()
    payload["randomization"]["fixation_onset_seed"] += 1
    with pytest.raises(ValidationError, match="stable namespace"):
        RunSpec.model_validate(payload)
    mutated = run.model_copy(deep=True)
    mutated.randomization.algorithm_version = True
    with pytest.raises(ValidationError):
        RunSpec.model_validate(mutated)
