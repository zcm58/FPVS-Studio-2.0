"""Project scaffolding tests."""

from __future__ import annotations

from fpvs_studio.core.condition_template_profiles import get_condition_template_profile
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.paths import (
    APP_DATA_DIRNAME,
    TEMPLATES_DIRNAME,
    condition_template_library_path,
    project_json_path,
    stimulus_manifest_path,
)
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import load_project_file, read_json_file
from fpvs_studio.preprocessing.models import StimulusManifest


def test_project_scaffolding_allows_templates_project_name_separate_from_app_templates(
    tmp_path,
) -> None:
    profile = get_condition_template_profile(tmp_path, "sixty-hz-blank50-fixation-v1")

    scaffold = create_project(
        tmp_path,
        "Templates",
        condition_template_profile=profile,
    )

    assert scaffold.project_root == tmp_path / "templates"
    assert project_json_path(scaffold.project_root).is_file()
    assert condition_template_library_path(tmp_path).is_file()
    assert condition_template_library_path(tmp_path).parent == (
        tmp_path / APP_DATA_DIRNAME / TEMPLATES_DIRNAME
    )


def test_project_scaffolding_creates_expected_directories_and_files(tmp_path) -> None:
    scaffold = create_project(tmp_path, "Example Project")
    project_root = scaffold.project_root

    assert project_root.name == "example-project"
    assert (project_root / "stimuli").is_dir()
    assert (project_root / "stimuli" / "original-images").is_dir()
    assert (project_root / "stimuli" / "generated-variants").is_dir()
    assert (project_root / "runs").is_dir()
    assert (project_root / "cache").is_dir()
    assert (project_root / "logs").is_dir()

    project = load_project_file(project_json_path(project_root))
    manifest = read_json_file(stimulus_manifest_path(project_root), StimulusManifest)

    assert project.meta.template_id == "fpvs_6hz_every5_v1"
    assert project.conditions == []
    assert project.settings.protocol.base_hz == 6.0
    assert project.settings.protocol.oddball_every_n == 5
    assert project.settings.protocol.oddball_hz == 1.2
    assert project.settings.supported_variants[0].value == "original"
    assert manifest.project_id == project.meta.project_id


def test_project_without_protocol_fields_loads_current_timing_defaults(tmp_path) -> None:
    scaffold = create_project(tmp_path, "Legacy Timing Project")
    payload = scaffold.project.model_dump(mode="json")
    del payload["settings"]["protocol"]

    loaded = ProjectFile.model_validate(payload)

    assert loaded.settings.protocol.base_hz == 6.0
    assert loaded.settings.protocol.oddball_every_n == 5
    assert loaded.settings.protocol.oddball_hz == 1.2


def test_project_scaffolding_applies_condition_template_profile_snapshot(tmp_path) -> None:
    profile = get_condition_template_profile(tmp_path, "sixty-hz-blank50-fixation-v1")

    scaffold = create_project(
        tmp_path,
        "Profiled Project",
        condition_template_profile=profile,
    )
    project = load_project_file(project_json_path(scaffold.project_root))

    assert project.settings.condition_profile_id == "sixty-hz-blank50-fixation-v1"
    assert project.settings.condition_defaults.duty_cycle_mode.value == "blank_50"
    assert project.settings.condition_defaults.sequence_count == 1
    assert project.settings.condition_defaults.oddball_cycle_repeats_per_sequence == 146
    assert project.settings.condition_defaults.target_repeats_per_image == 7
    assert project.settings.display.preferred_refresh_hz is None
    assert project.settings.fixation_task.enabled is True
    assert project.settings.fixation_task.accuracy_task_enabled is True
    assert project.settings.fixation_task.changes_per_sequence == 7
    assert project.settings.fixation_task.target_count_mode == "randomized"
    assert project.settings.fixation_task.target_count_min == 6
    assert project.settings.fixation_task.target_count_max == 8
    assert project.settings.fixation_task.no_immediate_repeat_count is True
    assert project.settings.fixation_task.target_duration_ms == 250
    assert project.settings.fixation_task.min_gap_ms == 1000
    assert project.settings.fixation_task.max_gap_ms == 3000
