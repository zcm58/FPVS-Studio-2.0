"""Model serialization tests."""

from __future__ import annotations

from fpvs_studio.core.serialization import load_project_file, save_project_file


def test_project_model_round_trip(tmp_path, sample_project) -> None:
    project_path = tmp_path / "project.json"

    save_project_file(sample_project, project_path)
    loaded = load_project_file(project_path)

    assert loaded == sample_project
    assert loaded.schema_version.value == "1.0.0"
