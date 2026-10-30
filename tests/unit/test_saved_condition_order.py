"""Exact saved arrangements, repairable author drafts and unchanged occurrence schedules."""

import pytest
from pydantic import ValidationError

from fpvs_studio.core.compiler import CompileError, compile_session_plan
from fpvs_studio.core.condition_timing import propose_condition_timing
from fpvs_studio.core.data_sharing import protocol_fingerprint
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.models import ProjectFile, RandomizationSeeds, SessionSettings
from fpvs_studio.core.randomization import configured_randomization_seeds
from fpvs_studio.core.session_ordering import (
    active_saved_condition_order,
    condition_ordering_identity,
    preview_condition_order,
    validate_saved_condition_order,
)
from fpvs_studio.core.session_plan import SessionBlock, SessionPlan
from fpvs_studio.core.validation import validate_project


@pytest.fixture
def order_project(sample_project):
    project = sample_project.model_copy(deep=True)
    project.settings.fixation_task.enabled = False
    project.settings.session.session_seed = 10
    project.conditions.append(project.conditions[0].model_copy(deep=True, update={
        "condition_id": "houses", "name": "Houses", "order_index": 1,
    }))
    return project


def _candidate_seeds(project, condition_order_seed=123):
    seeds = configured_randomization_seeds(project)
    return RandomizationSeeds(
        condition_order_seed=condition_order_seed, stimulus_seed=seeds.stimulus_seed,
        fixation_seed=seeds.fixation_seed,
    )


@pytest.mark.parametrize("order, match", [
    (["faces", "houses", "faces", "houses", "unknown"], "unknown condition IDs"),
    (["faces", "houses"], "does not match"),
    (["faces", "faces", "houses", "faces", "houses"], "adjacent positions"),
    (["houses", "faces", "houses", "faces", "houses"], "does not match"),
    ([], "does not match"),
    ("faces", "list of condition IDs"),
    (["faces", 1], "list of condition IDs"),
])
def test_saved_order_validation_rejects_unknown_counts_or_adjacent_duplicates(order, match):
    with pytest.raises(ValueError, match=match):
        validate_saved_condition_order(order, {"faces": 3, "houses": 2})


def test_preview_is_pure_asset_free_and_accepts_pending_counts(order_project):
    project = order_project
    project.settings.display.preferred_refresh_hz = None
    before = project.model_dump_json()
    order = preview_condition_order(
        project, presentation_counts={"faces": 3, "houses": 2}, condition_order_seed=456,
    )
    assert order == ["faces", "houses", "faces", "houses", "faces"]
    assert project.model_dump_json() == before
    with pytest.raises(ValueError, match="only 1 other presentations"):
        preview_condition_order(project, presentation_counts={"faces": 3})
    with pytest.raises(ValueError, match="10,000"):
        preview_condition_order(project, presentation_counts={"faces": 5001, "houses": 5001})
    with pytest.raises(InterruptedError, match="preview cancelled"):
        preview_condition_order(project, cancelled=lambda: True)


def test_save_selects_fixed_and_captures_roots_without_deriving_them_from_order_seed(order_project):
    project = order_project
    before = project.model_dump_json()
    roots = configured_randomization_seeds(project)
    saved = propose_condition_timing(
        project, saved_condition_order=["houses", "faces"],
        order_seeds=_candidate_seeds(project, 999),
    )
    session = saved.settings.session
    assert session.randomization_mode == "fixed"
    assert session.saved_condition_order == ["houses", "faces"]
    assert session.session_seed == 999
    assert session.stimulus_seed == roots.stimulus_seed
    assert session.fixation_seed == roots.fixation_seed
    assert saved.schema_version.value == "1.15.0"
    assert project.model_dump_json() == before
    restored = ProjectFile.model_validate_json(saved.model_dump_json())
    assert restored.settings.session == session
    assert "saved_condition_order" not in project.settings.session.model_dump()


def test_counts_and_order_repair_apply_atomically_without_display_or_assets(order_project):
    saved = propose_condition_timing(order_project, saved_condition_order=["faces", "houses"])
    before = saved.model_dump_json()
    counts = {"faces": 3, "houses": 2}
    with pytest.raises(ValueError, match="Open Condition order"):
        propose_condition_timing(saved, presentation_counts=counts)
    assert saved.model_dump_json() == before
    replacement = preview_condition_order(saved, presentation_counts=counts)
    draft = propose_condition_timing(saved, presentation_counts=counts,
                                     saved_condition_order=replacement)
    assert draft.settings.session.saved_condition_order == replacement
    assert [condition.presentation_count for condition in draft.conditions] == [3, 2]
    assert saved.model_dump_json() == before
    with pytest.raises(ValueError, match="complete oddball cycles"):
        propose_condition_timing(saved, presentation_counts=counts,
                                 saved_condition_order=replacement,
                                 durations={"faces": 1}, refresh_hz=60)
    assert saved.model_dump_json() == before


def test_fixed_stale_author_draft_is_loadable_and_repairable_but_not_runnable(
    order_project, monkeypatch,
):
    saved = propose_condition_timing(order_project, saved_condition_order=["faces", "houses"])
    saved.conditions.pop()
    draft = ProjectFile.model_validate(saved.model_dump())
    assert draft.settings.session.saved_condition_order == ["faces", "houses"]
    assert any(issue.location == "settings.session.saved_condition_order"
               for issue in validate_project(draft).issues)
    monkeypatch.setattr("fpvs_studio.core.compiler.CompilationInputs", lambda *args, **kwargs:
                        pytest.fail("Stale Fixed order must fail before preparing assets."))
    with pytest.raises(CompileError, match="unknown condition IDs"):
        compile_session_plan(draft, refresh_hz=60)
    assert preview_condition_order(draft) == ["faces"]
    repaired = propose_condition_timing(draft, saved_condition_order=["faces"])
    assert active_saved_condition_order(repaired) == ["faces"]


def test_new_mode_retains_and_ignores_stale_order_in_compile_and_identity(
    order_project, sample_project_root,
):
    project = propose_condition_timing(order_project, saved_condition_order=["faces", "houses"])
    project.settings.session.randomization_mode = "new"
    project.settings.session.saved_condition_order = ["removed-condition", "removed-condition"]
    project = ProjectFile.model_validate(project.model_dump())
    assert active_saved_condition_order(project) is None
    assert not any(issue.location == "settings.session.saved_condition_order"
                   for issue in validate_project(project).issues)
    plan = compile_session_plan(project, refresh_hz=60, project_root=sample_project_root)
    assert plan.ordering_policy == "pooled_no_adjacent"
    assert plan.schema_version == "1.7.0"
    digest = protocol_fingerprint(project, sample_project_root)
    project.settings.session.saved_condition_order = None
    assert protocol_fingerprint(project, sample_project_root) == digest


def _occurrence_schedules(plan):
    return {(entry.condition_id, entry.condition_presentation_index): (
        [(event.role, event.image_path, event.text) for event in entry.run_spec.stimulus_sequence],
        [(event.start_frame, event.duration_frames) for event in entry.run_spec.fixation_events],
    ) for entry in plan.ordered_entries()}


def test_exact_manual_order_reuses_occurrence_schedules_and_has_distinct_protocol_identity(
    order_project, sample_project_root,
):
    project = order_project
    project.settings.fixation_task.enabled = True
    project.settings.fixation_task.changes_per_sequence = 2
    project.settings.fixation_task.target_duration_ms = 100
    project.settings.fixation_task.min_gap_ms = 100
    project.conditions.append(project.conditions[0].model_copy(deep=True, update={
        "condition_id": "objects", "name": "Objects", "order_index": 2,
    }))
    counts = {"faces": 2, "houses": 2, "objects": 1}
    first_order = ["faces", "houses", "faces", "objects", "houses"]
    second_order = ["houses", "faces", "objects", "houses", "faces"]
    first = propose_condition_timing(project, presentation_counts=counts,
                                     saved_condition_order=first_order)
    second = propose_condition_timing(first, saved_condition_order=second_order)
    plan = compile_session_plan(first, refresh_hz=60, project_root=sample_project_root,
                                session_id="participant-a")
    other = compile_session_plan(first, refresh_hz=60, project_root=sample_project_root,
                                 session_id="participant-b")
    moved = compile_session_plan(second, refresh_hz=60, project_root=sample_project_root)
    assert plan.schema_version == "1.8.0"
    assert plan.ordering_policy == "saved_no_adjacent"
    assert [entry.condition_id for entry in plan.ordered_entries()] == first_order
    assert [entry.condition_id for entry in moved.ordered_entries()] == second_order
    schedules = _occurrence_schedules(plan)
    assert schedules == _occurrence_schedules(other) == _occurrence_schedules(moved)
    assert schedules[("faces", 1)][1] != schedules[("faces", 2)][1]
    assert condition_ordering_identity(first)["condition_order"] == first_order
    assert protocol_fingerprint(first, sample_project_root) != protocol_fingerprint(
        second, sample_project_root,
    )
    # Removing a separator must not invent a different valid arrangement for a subset.
    with pytest.raises(CompileError, match="adjacent positions"):
        compile_session_plan(first, refresh_hz=60, condition_ids=["faces", "objects"])
    subset = compile_session_plan(first, refresh_hz=60, project_root=sample_project_root,
                                  condition_ids=["faces", "houses"])
    assert [entry.condition_id for entry in subset.ordered_entries()] == [
        "faces", "houses", "faces", "houses",
    ]
    entries = [entry for entry in plan.ordered_entries() if entry.condition_id == "faces"]
    recovered = plan.model_copy(deep=True, update={"total_runs": 2, "blocks": [SessionBlock(
        block_index=0, condition_order=["faces", "faces"], entries=entries,
    )]})
    decoded = SessionPlan.model_validate_json(recovered.model_dump_json())
    assert [entry.condition_presentation_index for entry in decoded.ordered_entries()] == [1, 2]
    assert decoded.ordering_policy == "saved_no_adjacent"


def test_stale_seed_snapshot_cannot_overwrite_current_stimulus_or_fixation_roots(order_project):
    captured = _candidate_seeds(order_project)
    project = propose_condition_timing(order_project, saved_condition_order=["faces", "houses"])
    project.settings.session.fixation_seed += 1
    before = project.model_dump_json()
    with pytest.raises(ValueError, match="seeds changed.*Reopen"):
        propose_condition_timing(project, saved_condition_order=["houses", "faces"],
                                 order_seeds=captured)
    assert project.model_dump_json() == before


@pytest.mark.parametrize("order", [[], [True], ["bad id"], [None]])
def test_saved_order_persisted_shape_is_strict(order):
    with pytest.raises(ValidationError):
        SessionSettings(saved_condition_order=order)


def test_native_ab_order_override_is_rejected_before_mutation(sample_project):
    payload = sample_project.model_dump()
    payload["experiment_category"] = ExperimentCategory.ATTENTIONAL_BLINK
    payload["settings"]["session"]["saved_condition_order"] = ["faces"]
    with pytest.raises(ValidationError, match="unavailable for Attentional-Blink"):
        ProjectFile.model_validate(payload)


def test_compiled_saved_policy_requires_fixed_mode(order_project, sample_project_root):
    project = propose_condition_timing(order_project, saved_condition_order=["faces", "houses"])
    plan = compile_session_plan(project, refresh_hz=60, project_root=sample_project_root)
    payload = plan.model_dump()
    payload["randomization_mode"] = "new"
    for entry in payload["blocks"][0]["entries"]:
        entry["run_spec"]["randomization"]["mode"] = "new"
    with pytest.raises(ValidationError, match="requires fixed randomization"):
        SessionPlan.model_validate(payload)
