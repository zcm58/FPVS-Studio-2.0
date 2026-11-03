"""Project document condition mutation tests."""

from __future__ import annotations

import pytest

from fpvs_studio.core.enums import StimulusModality, StimulusTransform, StimulusVariant
from fpvs_studio.core.models import (
    ConditionPresentationSettings,
    ProjectFile,
    StimulusPresentationOverride,
)
from fpvs_studio.core.serialization import load_project_file
from fpvs_studio.gui.document import DocumentError, ProjectDocument

pytestmark = pytest.mark.qt


def _document_for_project(tmp_path, project: ProjectFile) -> ProjectDocument:
    return ProjectDocument(project_root=tmp_path, project=project.model_copy(deep=True))


def test_manual_removed_electrodes_update_saves_participant_map(
    tmp_path,
    sample_project: ProjectFile,
) -> None:
    document = _document_for_project(tmp_path, sample_project)

    document.update_manual_removed_electrodes("0007", " ft7, P9; FT7 ")
    document.update_manual_removed_electrodes("0008", "")
    document.save()

    assert load_project_file(document.project_file_path).manual_removed_electrodes == {
        "0007": ["FT7", "P9"],
        "0008": [],
    }


@pytest.mark.parametrize(
    ("variant", "transform"),
    [
        (StimulusVariant.ORIGINAL, StimulusTransform.NONE),
        (StimulusVariant.GRAYSCALE, StimulusTransform.NONE),
        (StimulusVariant.ROT180, StimulusTransform.NONE),
        (StimulusVariant.PHASE_SCRAMBLED, StimulusTransform.NONE),
        (StimulusVariant.ORIGINAL, StimulusTransform.MIRROR_HORIZONTAL),
        (StimulusVariant.ORIGINAL, StimulusTransform.MIRROR_VERTICAL),
        (StimulusVariant.ORIGINAL, StimulusTransform.ROT180),
    ],
)
def test_manual_condition_variant_and_transform_survive_copy_and_save(
    tmp_path,
    sample_project: ProjectFile,
    variant: StimulusVariant,
    transform: StimulusTransform,
) -> None:
    document = _document_for_project(tmp_path, sample_project)
    original = document.get_condition("faces").model_copy(deep=True)
    condition_id = document.create_condition(name="Edited images")
    presentation = ConditionPresentationSettings(
        common=StimulusPresentationOverride(transform=transform),
    )
    document.update_condition(condition_id, stimulus_variant=variant)
    document.set_condition_presentation(condition_id, presentation)
    duplicate_id = document.duplicate_condition(condition_id)
    document.save()

    condition = document.get_condition(condition_id)
    duplicate = document.get_condition(duplicate_id)
    assert condition is not None
    assert duplicate is not None
    assert condition.stimulus_variant == duplicate.stimulus_variant == variant
    assert condition.presentation == duplicate.presentation == presentation
    assert duplicate.base_stimulus_set_id != condition.base_stimulus_set_id
    assert duplicate.oddball_stimulus_set_id != condition.oddball_stimulus_set_id
    assert document.get_condition("faces") == original
    loaded = load_project_file(document.project_file_path)
    saved = {item.condition_id: item for item in loaded.conditions}
    assert saved[condition_id] == condition
    assert saved[duplicate_id] == duplicate
    assert saved["faces"] == original


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


def test_word_condition_rejects_image_import(
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
