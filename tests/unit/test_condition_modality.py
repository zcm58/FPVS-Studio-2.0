"""Stimulus-type changes through the production document mixin, without Qt."""

from pathlib import Path

import pytest

from fpvs_studio.core.enums import DutyCycleMode, ExperimentCategory, StimulusModality
from fpvs_studio.core.models import ProjectFile, StimulusSet
from fpvs_studio.gui.document_conditions import DocumentConditionMixin
from fpvs_studio.gui.document_support import DocumentError, StimulusTypeChangeRequiresConfirmation


class _Document(DocumentConditionMixin):
    def __init__(self, project: ProjectFile, root: Path):
        self._project = project.model_copy(deep=True)
        self._project_root = root
        self.replacements = 0

    def _replace_project(self, project):
        self._project = project
        self.replacements += 1


@pytest.mark.parametrize("source", [StimulusModality.IMAGE, StimulusModality.WORD])
def test_populated_switch_requires_confirmation(sample_project, tmp_path, source):
    document = _Document(sample_project, tmp_path)
    if source == StimulusModality.WORD:
        document._project.stimulus_sets = [
            StimulusSet(set_id=item.set_id, name=item.name, modality=source, words=["cat"])
            for item in document._project.stimulus_sets
        ]
    before = document._project.model_dump()
    target = StimulusModality.WORD if source == StimulusModality.IMAGE else StimulusModality.IMAGE

    with pytest.raises(
        StimulusTypeChangeRequiresConfirmation, match="before images or words are added",
    ):
        document.set_condition_stimulus_modality("faces", modality=target)

    assert document._project.model_dump() == before
    assert document.replacements == 0


@pytest.mark.parametrize("source", [StimulusModality.IMAGE, StimulusModality.WORD])
def test_confirmed_switch_only_clears_selected_condition(
    multi_condition_project, tmp_path, source,
):
    document = _Document(multi_condition_project, tmp_path)
    if source == StimulusModality.WORD:
        document._project.stimulus_sets = [
            StimulusSet(set_id=item.set_id, name=item.name, modality=source, words=["cat", "dog"])
            for item in document._project.stimulus_sets
        ]
    before = document._project.model_copy(deep=True)
    target = StimulusModality.WORD if source == StimulusModality.IMAGE else StimulusModality.IMAGE
    condition_id = before.conditions[0].condition_id

    document.set_condition_stimulus_modality(
        condition_id, modality=target, clear_existing=True,
    )

    assert document.replacements == 1
    assert document._project.conditions[1:] == before.conditions[1:]
    for original in before.stimulus_sets:
        assert document.get_stimulus_set(original.set_id) == original
    for role in ("base", "oddball"):
        current = document.get_condition_stimulus_set(condition_id, role)
        assert current.modality == target
        assert current.image_count == current.word_count == 0
        assert current.set_id not in {item.set_id for item in before.stimulus_sets}
    updated = document.get_condition(condition_id)
    assert updated is not None
    assert updated.model_dump(exclude={"base_stimulus_set_id", "oddball_stimulus_set_id"}) == (
        before.conditions[0].model_dump(exclude={"base_stimulus_set_id", "oddball_stimulus_set_id"})
    )


def test_image_word_image_switch_preserves_files_without_reselecting_them(
    sample_project, sample_project_root,
):
    document = _Document(sample_project, sample_project_root)
    originals = {
        path: path.read_bytes() for path in sample_project_root.rglob("*.png")
    }
    assert originals
    original_ids = {item.set_id for item in document._project.stimulus_sets}
    document._project.conditions[0].duty_cycle_mode = DutyCycleMode.SINUSOIDAL

    document.set_condition_stimulus_modality(
        "faces", modality=StimulusModality.WORD, clear_existing=True,
    )
    assert document._project.conditions[0].duty_cycle_mode == DutyCycleMode.CONTINUOUS
    assert not original_ids.intersection(item.set_id for item in document._project.stimulus_sets)
    document.update_condition_words("faces", role="oddball", words=["chair"])
    document.set_condition_stimulus_modality(
        "faces", modality=StimulusModality.IMAGE, clear_existing=True,
    )

    for role in ("base", "oddball"):
        current = document.get_condition_stimulus_set("faces", role)
        assert current.modality == StimulusModality.IMAGE
        assert current.image_count == 0
        assert current.source_dir is not None
        assert not (sample_project_root / current.source_dir).exists()
    assert {path: path.read_bytes() for path in originals} == originals


def test_confirmed_same_modality_is_noop(sample_project, tmp_path):
    document = _Document(sample_project, tmp_path)
    before = document._project.model_dump()
    document.set_condition_stimulus_modality(
        "faces", modality=StimulusModality.IMAGE, clear_existing=True,
    )
    assert document._project.model_dump() == before
    assert document.replacements == 0


def test_empty_condition_switches_without_confirmation(sample_project, tmp_path):
    document = _Document(sample_project, tmp_path)
    condition_id = document.create_condition(name="Empty Condition")
    for modality in (StimulusModality.WORD, StimulusModality.IMAGE):
        document.set_condition_stimulus_modality(condition_id, modality=modality)
        assert document.get_condition_stimulus_set(condition_id, "base").modality == modality


def test_confirmation_does_not_bypass_category_guard(sample_project, tmp_path):
    document = _Document(sample_project, tmp_path)
    document._project = document._project.model_copy(
        update={"experiment_category": ExperimentCategory.ATTENTIONAL_BLINK},
    )
    before = document._project.model_dump()
    with pytest.raises(DocumentError, match="layout requires image sources"):
        document.set_condition_stimulus_modality(
            "faces", modality=StimulusModality.WORD, clear_existing=True,
        )
    assert document._project.model_dump() == before
    assert document.replacements == 0
