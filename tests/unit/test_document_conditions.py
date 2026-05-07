"""Project document condition mutation tests."""

from __future__ import annotations

import pytest

from fpvs_studio.core.enums import StimulusVariant
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
