"""Launchable paired scaffold, persistence and placeholder provenance."""

from collections import Counter
from hashlib import sha256

import pytest

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.project_bundle import export_project_bundle, import_project_bundle
from fpvs_studio.core.project_config import create_project_from_config, export_project_config
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.task_models import BackwardCountingRole
from fpvs_studio.preprocessing.manifest import read_stimulus_manifest


@pytest.fixture
def scaffold(tmp_path):
    return create_project(tmp_path, "Cognitive Load FPVS",
                          experiment_category=ExperimentCategory.COGNITIVE_LOAD_FPVS)


def test_new_scaffold_has_three_matched_pairs_and_real_placeholder_assets(scaffold):
    project = scaffold.project
    assert len(project.conditions) == 6
    assert len(project.stimulus_sets) == 6
    assert project.settings.session.block_count == 1
    assert not project.settings.fixation_task.enabled
    assert not project.settings.fixation_task.accuracy_task_enabled
    assert project.settings.fixation_task.show_cross
    assert project.settings.presentation.pre_stream_fixation_seconds == 0
    for index in range(0, 6, 2):
        no_load, load = project.conditions[index:index + 2]
        assert no_load.base_stimulus_set_id == load.base_stimulus_set_id
        assert no_load.oddball_stimulus_set_id == load.oddball_stimulus_set_id
        assert not no_load.post_task_bindings
        assert len(load.post_task_bindings) == 1
    manifest = read_stimulus_manifest(scaffold.project_root)
    assert len(manifest.sets) == 6
    for stimulus_set in manifest.sets:
        asset = stimulus_set.assets[0].source
        path = scaffold.project_root / asset.relative_path
        assert path.is_file()
        assert sha256(path.read_bytes()).hexdigest() == asset.sha256
        assert asset.resolution.as_tuple() == (512, 512)


@pytest.mark.parametrize("selected", [None, ["condition-2-load"], ["condition-3-no-load"]])
def test_compilation_keeps_baseline_once_before_first_selected_entry(scaffold, selected):
    plan = compile_session_plan(scaffold.project, project_root=scaffold.project_root,
                                refresh_hz=60, random_seed=83, condition_ids=selected)
    entries = plan.ordered_entries()
    assert len(entries) == (6 if selected is None else 1)
    assert [entry.global_order_index for entry in entries] == list(range(len(entries)))
    baseline = [entry.global_order_index for entry in entries for task in entry.pre_tasks
                if task.backward_counting.role == BackwardCountingRole.BASELINE]
    expected_baselines = 0 if selected == ["condition-3-no-load"] else 1
    assert baseline == ([0] if expected_baselines else [])
    roles = Counter(task.backward_counting.role for entry in entries
                    for task in entry.pre_tasks + entry.post_tasks)
    assert roles[BackwardCountingRole.BASELINE] == expected_baselines
    for entry in entries:
        assert entry.run_spec.display.total_frames == 5400
        assert entry.run_spec.pre_stream_fixation_frames == 0
        if entry.post_tasks:
            start = entry.pre_tasks[-1].backward_counting
            report = entry.post_tasks[0].backward_counting
            assert start.start_number == report.start_number
            assert start.subtraction_step == report.subtraction_step == 13
            assert start.duration_seconds == report.duration_seconds == 90
            assert not entry.show_condition_start_gate
    repeat = compile_session_plan(scaffold.project, project_root=scaffold.project_root,
                                  refresh_hz=60, random_seed=83, condition_ids=selected)
    assert repeat == plan


def test_counting_settings_survive_save_config_and_portable_bundle(scaffold, tmp_path):
    project = load_project_file(scaffold.project_root / "project.json")
    assert project == scaffold.project
    config = export_project_config(project, scaffold.project_root)
    imported_config = create_project_from_config(tmp_path / "config", config)
    assert imported_config.project.experiment_category == ExperimentCategory.COGNITIVE_LOAD_FPVS
    assert imported_config.project.task_modules == project.task_modules
    assert [c.pre_task_bindings for c in imported_config.project.conditions] == [
        c.pre_task_bindings for c in project.conditions]
    bundle = tmp_path / "cognitive-load.fpvsbundle"
    export_project_bundle(scaffold.project_root, bundle, refresh_hz=60)
    imported = import_project_bundle(bundle, tmp_path / "bundled")
    plan = compile_session_plan(imported.project, project_root=imported.project_root, refresh_hz=60)
    assert plan.total_runs == 6
    assert imported.project.task_modules == project.task_modules


def test_existing_project_is_never_overwritten(scaffold):
    path = scaffold.project_root / "project.json"
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        create_project(scaffold.project_root.parent, "Cognitive Load FPVS",
                       experiment_category=ExperimentCategory.COGNITIVE_LOAD_FPVS)
    assert path.read_bytes() == before


def test_project_specific_short_repetitions_keep_counting_and_late_fixation(scaffold, tmp_path):
    """A saved study can opt in without changing the scaffold or stream scheduling."""
    payload = scaffold.project.model_dump(mode="json")
    payload["settings"]["session"]["block_count"] = 3
    payload["settings"]["fixation_task"].update({
        "enabled": True, "accuracy_task_enabled": True, "changes_per_sequence": 1,
        "target_count_mode": "fixed", "target_onset_window": {
            "earliest_seconds_before_end": 10, "latest_seconds_before_end": 3,
        },
    })
    for condition in payload["conditions"]:
        condition.update(sequence_count=1, oddball_cycle_repeats_per_sequence=48)
    for module in payload["task_modules"]:
        config = module["backward_counting"]
        config.update(subtraction_step=3, start_min=1000, start_max=2000)
        config["duration_seconds"] = 30 if config["role"] == "baseline" else 40
    project = ProjectFile.model_validate(payload)
    save_project_file(project, scaffold.project_root / "project.json")
    project = load_project_file(scaffold.project_root / "project.json")
    plan = compile_session_plan(project, project_root=scaffold.project_root,
                                refresh_hz=60, random_seed=83)
    entries = plan.ordered_entries()
    assert Counter(entry.condition_id for entry in entries) == {
        condition.condition_id: 3 for condition in project.conditions
    }
    assert len(entries) == 18
    baseline_count = endpoint_count = 0
    onsets = []
    for entry in entries:
        run = entry.run_spec
        assert run.display.total_frames == 2400
        assert run.fixation.realized_target_count == len(run.fixation_events) == 1
        assert run.fixation.response_key == "space"
        onset = run.fixation_events[0].start_frame
        assert 1800 <= onset <= 2220
        onsets.append(onset)
        baseline_count += sum(task.backward_counting.role == BackwardCountingRole.BASELINE
                              for task in entry.pre_tasks)
        if entry.post_tasks:
            start = entry.pre_tasks[-1].backward_counting
            report = entry.post_tasks[0].backward_counting
            assert report.role == BackwardCountingRole.LOAD_REPORT
            assert start.start_number == report.start_number
            assert 1000 <= start.start_number <= 2000
            assert start.subtraction_step == report.subtraction_step == 3
            assert start.duration_seconds == report.duration_seconds == 40
            assert entry.post_tasks[0].steps[-1].questions[0].prompt.startswith("What number")
            endpoint_count += 1
    assert baseline_count == 1
    assert endpoint_count == 9
    assert len(set(onsets)) > 1
    assert compile_session_plan(project, project_root=scaffold.project_root,
                                refresh_hz=60, random_seed=83) == plan

    # The onset window never changes the FPVS image/trigger schedule.
    original_window = project.settings.fixation_task.target_onset_window
    project.settings.fixation_task.target_onset_window = None
    unwindowed = compile_session_plan(project, project_root=scaffold.project_root,
                                      refresh_hz=60, random_seed=83)
    for entry, ordinary in zip(entries, unwindowed.ordered_entries(), strict=True):
        assert entry.run_spec.stimulus_sequence == ordinary.run_spec.stimulus_sequence
        assert entry.run_spec.trigger_events == ordinary.run_spec.trigger_events
    project.settings.fixation_task.target_onset_window = original_window

    bundle = tmp_path / "pilot.fpvsbundle"
    save_project_file(project, scaffold.project_root / "project.json")
    export_project_bundle(scaffold.project_root, bundle, refresh_hz=60)
    imported = import_project_bundle(bundle, tmp_path / "pilot-import")
    assert imported.project.settings.fixation_task == project.settings.fixation_task
