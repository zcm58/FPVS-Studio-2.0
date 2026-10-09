"""Project scaffolding tests."""

from __future__ import annotations

import json

import pytest

from fpvs_studio.core.condition_template_profiles import get_condition_template_profile
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.paths import (
    APP_DATA_DIRNAME,
    TEMPLATES_DIRNAME,
    condition_template_library_path,
    project_json_path,
    stimulus_manifest_path,
)
from fpvs_studio.core.project_service import create_project, discover_project_roots, rename_project
from fpvs_studio.core.serialization import load_project_file, read_json_file
from fpvs_studio.preprocessing.models import StimulusManifest


def test_rename_preserves_identity_files_and_legacy_payload(tmp_path):
    scaffold = create_project(tmp_path, "Original name")
    path = scaffold.project_root / "project.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schema_version"] = "1.3.0"
    payload.pop("experiment_category")
    path.write_text(json.dumps(payload), encoding="utf-8")
    marker = scaffold.project_root / "runs" / "keep.txt"
    marker.write_bytes(b"historical results")
    renamed = rename_project(scaffold.project_root, "  Recognition – session 2  ")
    actual = json.loads(path.read_text(encoding="utf-8"))
    assert renamed.name == "Recognition – session 2"
    payload["meta"]["name"] = renamed.name
    payload["meta"]["updated_at"] = renamed.updated_at.isoformat()
    assert actual == payload
    assert marker.read_bytes() == b"historical results"
    assert scaffold.project_root.name == "original-name"
    assert renamed.project_id == scaffold.project.meta.project_id


def test_discovery_stops_at_projects_and_excludes_app_data_and_links(tmp_path, monkeypatch):
    import stat
    from pathlib import Path

    for name in ("group/study", ".fpvs-studio/hidden", "study", "linked"):
        path = tmp_path / name
        path.mkdir(parents=True)
        (path / "project.json").write_text("{}")
    nested = tmp_path / "study" / "stimuli" / "nested"
    nested.mkdir(parents=True)
    (nested / "project.json").write_text("{}")
    original = Path.lstat

    def reparse(path):
        info = original(path)
        if path.name == "linked":
            return type("Info", (), {
                "st_mode": stat.S_IFDIR, "st_file_attributes": 0x400,
            })()
        return info

    monkeypatch.setattr(Path, "lstat", reparse)
    assert discover_project_roots(tmp_path) == [tmp_path / "group/study", tmp_path / "study"]


def test_discovery_missing_root_and_cancellation(tmp_path):
    assert discover_project_roots(tmp_path / "missing") == []
    with pytest.raises(InterruptedError, match="discovery cancelled"):
        discover_project_roots(tmp_path, cancelled=lambda: True)


@pytest.mark.parametrize("name", ["", "  \t "])
def test_rename_rejects_empty_names_without_writing(tmp_path, name):
    scaffold = create_project(tmp_path, "Original")
    path = scaffold.project_root / "project.json"
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Enter a project name"):
        rename_project(scaffold.project_root, name)
    assert path.read_bytes() == before


def test_rename_failed_replace_keeps_original_and_removes_temporary(tmp_path, monkeypatch):
    scaffold = create_project(tmp_path, "Original")
    path = scaffold.project_root / "project.json"
    before = path.read_bytes()

    def fail_replace(*args):
        raise PermissionError("Project file is read-only")

    monkeypatch.setattr("fpvs_studio.core.serialization.os.replace", fail_replace)
    with pytest.raises(PermissionError):
        rename_project(scaffold.project_root, "New name")
    assert path.read_bytes() == before
    assert not list(scaffold.project_root.glob(".project.json.*.tmp"))


def test_rename_same_name_is_no_op_and_missing_project_is_not_created(tmp_path):
    scaffold = create_project(tmp_path, "Original")
    path = scaffold.project_root / "project.json"
    before = path.read_bytes()
    rename_project(scaffold.project_root, " Original ")
    assert path.read_bytes() == before
    with pytest.raises(FileNotFoundError):
        rename_project(tmp_path / "missing", "New name")
    assert not (tmp_path / "missing").exists()


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
    assert project.settings.fixation_task.enabled is True
    assert project.settings.fixation_task.accuracy_task_enabled is True
    assert project.settings.fixation_task.participant_tutorial_enabled is True
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
    assert project.settings.fixation_task.target_count_min == 8
    assert project.settings.fixation_task.target_count_max == 13
    assert project.settings.fixation_task.no_immediate_repeat_count is True
    assert project.settings.fixation_task.target_duration_ms == 300
    assert project.settings.fixation_task.min_gap_ms == 1000
    assert project.settings.fixation_task.max_gap_ms == 3000


def test_project_scaffolding_applies_sinusoidal_profile_background(tmp_path) -> None:
    profile = get_condition_template_profile(tmp_path, "sinusoidal-contrast-v1")

    scaffold = create_project(
        tmp_path,
        "Contrast Project",
        condition_template_profile=profile,
    )
    project = load_project_file(project_json_path(scaffold.project_root))

    assert project.settings.condition_profile_id == "sinusoidal-contrast-v1"
    assert project.settings.condition_defaults.duty_cycle_mode.value == "sinusoidal"
    assert project.settings.display.background_color == "#808080"


def test_recording_device_save_changes_only_recording_and_failure_keeps_file(tmp_path, monkeypatch):
    from fpvs_studio.core.models import ProjectRecordingSettings
    from fpvs_studio.core.project_service import save_project_recording_settings
    from fpvs_studio.core.serialization import load_project_file

    scaffold = create_project(tmp_path, "Device configuration")
    path = scaffold.project_root / "project.json"
    original = json.loads(path.read_text())
    setting = ProjectRecordingSettings(recording_backend="unicorn_udp", unicorn_udp_port=65535)
    save_project_recording_settings(scaffold.project_root, setting)
    expected = dict(original)
    expected["settings"]["recording"] = setting.model_dump()
    assert json.loads(path.read_text()) == expected
    assert load_project_file(path).settings.recording == setting
    before = path.read_bytes()
    monkeypatch.setattr(
        "fpvs_studio.core.serialization.os.replace",
        lambda *_: (_ for _ in ()).throw(PermissionError("locked")),
    )
    with pytest.raises(PermissionError):
        save_project_recording_settings(scaffold.project_root, ProjectRecordingSettings())
    assert path.read_bytes() == before
    assert not list(scaffold.project_root.glob(".*.tmp"))


@pytest.mark.parametrize(
    "configuration",
    [
        {"recording_backend": "unknown"},
        {"recording_backend": None},
        {"unicorn_udp_port": True},
        {"unicorn_udp_port": "1000"},
        {"unicorn_udp_port": 0},
        {"unicorn_udp_port": 65536},
    ],
)
def test_project_recording_rejects_invalid_device_or_port(configuration):
    from fpvs_studio.core.models import ProjectRecordingSettings

    with pytest.raises(ValueError):
        ProjectRecordingSettings.model_validate(configuration)
