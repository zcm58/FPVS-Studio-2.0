"""Project questionnaire compatibility and launch answer snapshots."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from fpvs_studio.core.data_sharing import protocol_fingerprint
from fpvs_studio.core.demographics import (
    DemographicsAnswer,
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
        DemographicsQuestion(
            id="services", prompt="Services used", kind="checkboxes", options=["A", "B"],
            required=False, allow_other=True,
        ),
        DemographicsQuestion(
            id="frequency", prompt="How often?", kind="scale", scale_min=0, scale_max=7,
            scale_min_label="Never", scale_max_label="Daily",
        ),
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


def test_legacy_question_uses_required_default_and_keeps_old_serialized_shape():
    payload = {"id": "language", "prompt": "Primary language", "kind": "text", "options": []}
    question = DemographicsQuestion.model_validate(payload)
    assert question.required
    assert question.model_dump() == payload


@pytest.mark.parametrize(("question_options", "submitted", "recorded"), [
    ({"kind": "paragraph"}, "First line\r\nSecond line", "First line\nSecond line"),
    ({"kind": "choice", "options": ["A", "B"], "allow_other": True}, "Other text", "Other text"),
    ({"kind": "checkboxes", "options": ["A", "B"], "allow_other": True}, ["A", "C"], ["A", "C"]),
    ({"kind": "dropdown", "options": ["A", "B"]}, "A", "A"),
    ({"kind": "scale", "scale_min": 0}, 0, 0),
    ({"kind": "rating", "scale_max": 8}, 8, 8),
    ({"kind": "date"}, "2024-02-29", "2024-02-29"),
    ({"kind": "time"}, "00:00", "00:00"),
    ({"kind": "checkboxes", "options": ["A", "B"], "required": False}, [], None),
])
def test_form_answer_round_trip_preserves_typed_value(question_options, submitted, recorded):
    question = DemographicsQuestion(id="item", prompt="Question", **question_options)
    metadata = collect_demographics([question], {question.id: submitted})
    restored = ParticipantMetadata.model_validate_json(metadata.model_dump_json(exclude_none=True))
    snapshot, = restored.demographics_answers
    assert snapshot.question_id == "item"
    assert snapshot.prompt == "Question"
    assert type(snapshot.answer) is type(recorded)
    assert snapshot.answer == recorded


@pytest.mark.parametrize(("question_options", "submitted"), [
    ({"kind": "paragraph"}, "First line\x00Second line"),
    ({"kind": "text"}, "First line\nSecond line"),
    ({"kind": "checkboxes", "options": ["A", "B"]}, []),
    ({"kind": "checkboxes", "options": ["A", "B"]}, ["A", "C"]),
    ({"kind": "checkboxes", "options": ["A", "B"], "allow_other": True}, ["C", "D"]),
    ({"kind": "checkboxes", "options": ["A", "B"], "allow_other": True}, ["A", "A"]),
    ({"kind": "dropdown", "options": ["A", "B"]}, "C"),
    ({"kind": "scale", "scale_min": 0}, False),
    ({"kind": "rating"}, 6),
    ({"kind": "date"}, "2025-02-29"),
    ({"kind": "time"}, "10:00+00:00"),
])
def test_form_responses_reject_invalid_values(question_options, submitted):
    question = DemographicsQuestion(id="item", prompt="Question", **question_options)
    with pytest.raises(DemographicsResponseError) as error:
        collect_demographics([question], {question.id: submitted})
    assert error.value.question_id == "item"


def test_making_studio_colorblind_question_optional_preserves_meaning():
    question = default_demographics_questions()[-1].model_copy(update={"required": False})
    assert collect_demographics([question], {question.id: True}).colorblind is True
    assert collect_demographics([question], {}).colorblind is None


def test_checkbox_snapshot_bounds_the_number_and_length_of_selections():
    options = [f"Option {i:02d}".ljust(120, "-") for i in range(20)]
    question = DemographicsQuestion(
        id="choices", prompt="Which ones?", kind="checkboxes", options=options, allow_other=True,
    )
    selected = [*options, "x" * 2000]
    snapshot, = collect_demographics([question], {question.id: selected}).demographics_answers
    assert snapshot.answer == selected
    with pytest.raises(ValidationError, match="Only one checkbox answer"):
        DemographicsAnswer(question_id=question.id, prompt=question.prompt, answer=[
            "a" * 2000, "b" * 2000,
        ])


def test_local_questionnaire_is_outside_reporting_protocol(sample_project, sample_project_root):
    baseline = protocol_fingerprint(sample_project, sample_project_root)
    sample_project.demographics_questions = [DemographicsQuestion(
        id="free-text", prompt="stimuli/task-assets/A question, not an asset",
    )]
    assert protocol_fingerprint(sample_project, sample_project_root) == baseline
