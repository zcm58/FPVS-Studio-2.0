"""Project document condition mutation tests."""

from __future__ import annotations

import pytest

from fpvs_studio.core.enums import StimulusModality, StimulusVariant
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.gui.document import DocumentError, ProjectDocument


def _document_for_project(tmp_path, project: ProjectFile) -> ProjectDocument:
    return ProjectDocument(project_root=tmp_path, project=project.model_copy(deep=True))


def test_create_control_condition_reuses_stimulus_sets_and_sets_variant(
    tmp_path,
    sample_project: ProjectFile,
) -> None:
    document = _document_for_project(tmp_path, sample_project)

    control_id = document.create_control_condition(
        "faces",
        variant=StimulusVariant.GRAYSCALE,
    )

    source = document.get_condition("faces")
    control = document.get_condition(control_id)
    assert source is not None
    assert control is not None
    assert control.name == "Faces Grayscale Control"
    assert control.base_stimulus_set_id == source.base_stimulus_set_id
    assert control.oddball_stimulus_set_id == source.oddball_stimulus_set_id
    assert control.stimulus_variant == StimulusVariant.GRAYSCALE
    assert control.trigger_code == 2
    assert control.order_index == 1
    assert len(document.project.stimulus_sets) == 2


def test_create_control_condition_uses_unique_name_and_rejects_original(
    tmp_path,
    sample_project: ProjectFile,
) -> None:
    document = _document_for_project(tmp_path, sample_project)

    first_id = document.create_control_condition(
        "faces",
        variant=StimulusVariant.ROT180,
        name="Faces Control",
    )
    second_id = document.create_control_condition(
        "faces",
        variant=StimulusVariant.PHASE_SCRAMBLED,
        name="Faces Control",
    )

    first = document.get_condition(first_id)
    second = document.get_condition(second_id)
    assert first is not None
    assert second is not None
    assert first.name == "Faces Control"
    assert second.name == "Faces Control 2"
    with pytest.raises(DocumentError, match="derived stimulus variant"):
        document.create_control_condition("faces", variant=StimulusVariant.ORIGINAL)


def test_word_condition_words_update_and_duplicate_with_new_sets(
    tmp_path,
    sample_project: ProjectFile,
) -> None:
    document = _document_for_project(tmp_path, sample_project)
    condition_id = document.create_condition(name="Animal Words")

    document.set_condition_stimulus_modality(condition_id, modality=StimulusModality.WORD)
    document.update_condition_words(condition_id, role="base", words=["cat", "dog", "cat"])
    document.update_condition_words(condition_id, role="oddball", words=["chair", "table"])
    duplicate_id = document.duplicate_condition(condition_id)

    source = document.get_condition(condition_id)
    duplicate = document.get_condition(duplicate_id)
    assert source is not None
    assert duplicate is not None
    assert duplicate.base_stimulus_set_id != source.base_stimulus_set_id
    assert duplicate.oddball_stimulus_set_id != source.oddball_stimulus_set_id
    duplicate_base = document.get_condition_stimulus_set(duplicate_id, "base")
    duplicate_oddball = document.get_condition_stimulus_set(duplicate_id, "oddball")
    assert duplicate_base.modality == StimulusModality.WORD
    assert duplicate_base.words == ["cat", "dog", "cat"]
    assert duplicate_oddball.words == ["chair", "table"]


def test_populated_condition_modality_switch_is_rejected(
    tmp_path,
    sample_project: ProjectFile,
) -> None:
    document = _document_for_project(tmp_path, sample_project)
    condition_id = document.create_condition(name="Animal Words")
    document.set_condition_stimulus_modality(condition_id, modality=StimulusModality.WORD)
    document.update_condition_words(condition_id, role="base", words=["cat"])

    with pytest.raises(DocumentError, match="before images or words are added"):
        document.set_condition_stimulus_modality(condition_id, modality=StimulusModality.IMAGE)


def test_word_condition_rejects_image_import_and_control_condition(
    tmp_path,
    sample_project: ProjectFile,
) -> None:
    document = _document_for_project(tmp_path, sample_project)
    condition_id = document.create_condition(name="Animal Words")
    document.set_condition_stimulus_modality(condition_id, modality=StimulusModality.WORD)

    with pytest.raises(DocumentError, match="Image folders can only be imported"):
        document.import_condition_stimulus_folder(
            condition_id,
            role="base",
            source_dir=tmp_path,
        )
    with pytest.raises(DocumentError, match="image conditions"):
        document.create_control_condition(condition_id, variant=StimulusVariant.GRAYSCALE)
