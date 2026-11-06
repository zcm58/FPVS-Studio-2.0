"""Project questionnaire compatibility and launch answer snapshots."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from fpvs_studio.core.data_sharing import protocol_fingerprint
from fpvs_studio.core.demographics import (
    DemographicsQuestion,
    DemographicsResponseError,
    default_demographics_questions,
)
from fpvs_studio.core.execution import ParticipantMetadata, collect_demographics
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.project_config import (
    create_project_from_config,
    export_project_config,
    read_project_config,
    write_project_config,
)
from fpvs_studio.core.serialization import load_project_file, save_project_file


def test_older_project_loads_independent_studio_defaults(sample_project, tmp_path):
    path = tmp_path / "project.json"
    save_project_file(sample_project, path)
    assert "demographics_questions" not in json.loads(path.read_text(encoding="utf-8"))
    project = load_project_file(path)
    assert [question.id for question in project.demographics_questions] == [
        "age", "sex", "handedness", "colorblind",
    ]
    project.demographics_questions[1].options.clear()
    assert load_project_file(path).demographics_questions == default_demographics_questions()


@pytest.mark.parametrize("empty", [False, True])
def test_project_and_config_round_trip_retains_custom_order_or_empty_list(
    sample_project, tmp_path, empty,
):
    questions = [] if empty else [
        DemographicsQuestion(id="language", prompt="Primary language"),
        *reversed(default_demographics_questions()),
    ]
    project = ProjectFile.model_validate({
        **sample_project.model_dump(), "demographics_questions": questions,
    })
    path = tmp_path / "project.json"
    save_project_file(project, path)
    assert load_project_file(path).demographics_questions == questions

    config_path = tmp_path / "study.fpvsconfig"
    write_project_config(config_path, export_project_config(project, project_root=None))
    scaffold = create_project_from_config(tmp_path, read_project_config(config_path))
    assert load_project_file(scaffold.project_root / "project.json").demographics_questions == (
        questions
    )


def test_duplicate_question_ids_are_rejected(sample_project):
    question = DemographicsQuestion(id="duplicate", prompt="First prompt")
    with pytest.raises(ValidationError, match="question IDs must be unique"):
        ProjectFile.model_validate({
            **sample_project.model_dump(), "demographics_questions": [question, question],
        })


def test_answers_snapshot_authored_order_and_map_unchanged_studio_fields():
    age, sex, handedness, colorblind = default_demographics_questions()
    custom = DemographicsQuestion(id="language", prompt="Primary language")
    changed = sex.model_copy(update={"prompt": "Gender identity", "options": ["A", "B"]})
    result = collect_demographics(
        [colorblind, handedness, changed, custom, age],
        {"colorblind": False, "handedness": "Left handed", "sex": "A", "language": " 01 ",
         "age": "24"},
        manual_removed_electrodes=["P9"],
    )
    restored = ParticipantMetadata.model_validate_json(result.model_dump_json())
    assert restored.age == 24
    assert restored.sex is None
    assert restored.handedness == "Left handed"
    assert restored.colorblind is False
    assert restored.manual_removed_electrodes == ["P9"]
    assert [(item.prompt, item.answer) for item in restored.demographics_answers] == [
        ("Are you colorblind?", False), ("Handedness", "Left handed"),
        ("Gender identity", "A"), ("Primary language", "01"), ("Age", 24),
    ]


@pytest.mark.parametrize("bad_answer", [None, True, "121", "1.2", "²"])
def test_age_response_rejects_invalid_values_and_identifies_question(bad_answer):
    age = default_demographics_questions()[0]
    with pytest.raises(DemographicsResponseError) as error:
        collect_demographics([age], {"age": bad_answer})
    assert error.value.question_id == "age"


def test_text_response_rejects_overlong_input_without_truncating_it():
    question = DemographicsQuestion(id="notes", prompt="Additional notes")
    with pytest.raises(DemographicsResponseError, match="2,000 characters"):
        collect_demographics([question], {"notes": "x" * 2001})


def test_local_questionnaire_is_outside_reporting_protocol(sample_project, sample_project_root):
    baseline = protocol_fingerprint(sample_project, sample_project_root)
    sample_project.demographics_questions = [DemographicsQuestion(
        id="free-text", prompt="stimuli/task-assets/A question, not an asset",
    )]
    assert protocol_fingerprint(sample_project, sample_project_root) == baseline
