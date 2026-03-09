"""Model serialization tests."""

from __future__ import annotations

from fpvs_studio.core.models import Condition
from fpvs_studio.core.serialization import load_project_file, save_project_file


def test_project_model_round_trip(tmp_path, sample_project) -> None:
    project_path = tmp_path / "project.json"

    save_project_file(sample_project, project_path)
    loaded = load_project_file(project_path)

    assert loaded == sample_project
    assert loaded.schema_version.value == "1.0.0"


def test_condition_instructions_strip_bidi_control_characters() -> None:
    condition = Condition(
        condition_id="faces",
        name="Faces",
        instructions="\u202eRead the instructions.\u202c",
        base_stimulus_set_id="base-set",
        oddball_stimulus_set_id="oddball-set",
        sequence_count=1,
    )

    assert condition.instructions == "Read the instructions."
