"""Project scaffolding tests."""

from __future__ import annotations

from fpvs_studio.core.paths import project_json_path, stimulus_manifest_path
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import load_project_file, read_json_file
from fpvs_studio.preprocessing.models import StimulusManifest


def test_project_scaffolding_creates_expected_directories_and_files(tmp_path) -> None:
    scaffold = create_project(tmp_path, "Example Project")
    project_root = scaffold.project_root

    assert project_root.name == "example-project"
    assert (project_root / "stimuli").is_dir()
    assert (project_root / "stimuli" / "source").is_dir()
    assert (project_root / "stimuli" / "derived").is_dir()
    assert (project_root / "runs").is_dir()
    assert (project_root / "cache").is_dir()
    assert (project_root / "logs").is_dir()

    project = load_project_file(project_json_path(project_root))
    manifest = read_json_file(stimulus_manifest_path(project_root), StimulusManifest)

    assert project.meta.template_id == "fpvs_6hz_every5_v1"
    assert project.conditions == []
    assert project.settings.supported_variants[0].value == "original"
    assert manifest.project_id == project.meta.project_id
