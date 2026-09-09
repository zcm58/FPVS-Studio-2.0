"""Real document mutation mixins exercised without importing or constructing Qt."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from fpvs_studio.core.enums import (
    DutyCycleMode,
    ExperimentCategory,
    StimulusModality,
    StimulusVariant,
)
from fpvs_studio.core.models import AttentionalBlinkSettings, ProjectFile
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.gui.document_conditions import DocumentConditionMixin
from fpvs_studio.gui.document_stimuli import DocumentStimulusMixin
from fpvs_studio.gui.document_support import DocumentError, validated_copy
from fpvs_studio.preprocessing.inspection import inspect_source_directory, summary_to_stimulus_set
from fpvs_studio.preprocessing.manifest import create_empty_manifest


class _Signal:
    def __init__(self):
        self.count = 0

    def emit(self):
        self.count += 1


class _Document(DocumentConditionMixin, DocumentStimulusMixin):
    """Use production mutations with only the Qt facade's replacement seam stubbed."""

    def __init__(self, project: ProjectFile, root: Path):
        self._project = project.model_copy(deep=True)
        self._project_root = root
        self._manifest = create_empty_manifest(project.meta.project_id)
        self._image_normalization_scan_cache = None
        self.manifest_changed = _Signal()
        self.replacements = 0

    def _replace_project(self, project):
        self._project = project
        self.replacements += 1

    def _apply_project_update(self, **updates):
        self._replace_project(validated_copy(self._project, **updates))


def _source(root, *, set_id="designer-t2", sizes=((48, 32),)):
    relative_dir = f"stimuli/original-images/{set_id}"
    source_dir = root / relative_dir
    source_dir.mkdir(parents=True)
    for index, size in enumerate(sizes):
        Image.new("RGB", size, (10, 20, 30)).save(source_dir / f"image-{index}.png")
    summary = inspect_source_directory(source_dir, relative_prefix=relative_dir, strict=False)
    stimulus_set = summary_to_stimulus_set(set_id=set_id, name="Designer T2", summary=summary)
    return stimulus_set, summary


@pytest.fixture
def document(sample_project, sample_project_root):
    project = sample_project.model_copy(
        update={"experiment_category": ExperimentCategory.ATTENTIONAL_BLINK}, deep=True
    )
    project.conditions[0].attentional_blink = AttentionalBlinkSettings()
    project.conditions[0].isi_stimulus_set_id = project.conditions[0].base_stimulus_set_id
    return _Document(project, sample_project_root)


def _attach_t2(document, *, mixed=False):
    stimulus_set, summary = _source(
        document._project_root,
        sizes=((48, 32), (64, 64)) if mixed else ((48, 32),),
    )
    document.apply_designer_source("faces", role="t2", stimulus_set=stimulus_set, summary=summary)
    return stimulus_set


def _apply_ab(document):
    document.apply_experiment_design(
        "faces",
        base_hz=4,
        slot_count=4,
        attentional_blink=AttentionalBlinkSettings(),
    )


def test_t2_import_preserves_ab_timing_and_persists_manifest_and_reference(document):
    stimulus_set = _attach_t2(document)
    condition = document.get_condition("faces")
    assert condition.t2_stimulus_set_id == stimulus_set.set_id
    assert condition.attentional_blink == AttentionalBlinkSettings()
    assert document.get_condition_stimulus_set("faces", "t2") == stimulus_set
    assert document._manifest.sets[0].set_id == stimulus_set.set_id
    assert document._manifest.sets[0].assets[0].source.relative_path.endswith("image-0.png")
    assert document.manifest_changed.count == 1
    assert document.get_condition_stimulus_set("faces", "separator").set_id == "base-set"
    assert document.get_condition_stimulus_set("faces", "t1").set_id == "oddball-set"


def test_apply_ab_saves_and_rejects_switch_to_oddball(document):
    source = _attach_t2(document)
    document.get_condition("faces").duty_cycle_mode = DutyCycleMode.BLANK_50
    _apply_ab(document)
    assert document._project.settings.protocol.base_hz == 4
    assert document._project.settings.protocol.oddball_every_n == 4
    assert document.get_condition("faces").duty_cycle_mode == DutyCycleMode.CONTINUOUS
    path = document._project_root / "project.json"
    save_project_file(document._project, path)
    restored = load_project_file(path)
    assert restored.conditions[0].attentional_blink == AttentionalBlinkSettings()
    with pytest.raises(DocumentError, match="locked experiment type"):
        document.apply_experiment_design("faces", base_hz=6, slot_count=5, attentional_blink=None)
    assert document.get_condition("faces").attentional_blink == AttentionalBlinkSettings()
    assert document.get_condition("faces").t2_stimulus_set_id == source.set_id
    assert document.get_stimulus_set(source.set_id) is not None


@pytest.mark.parametrize("case", ["missing_t2", "marker_collision", "overfull", "no_base_slot"])
def test_invalid_ab_apply_is_atomic(document, case):
    if case != "missing_t2":
        _attach_t2(document)
    settings = AttentionalBlinkSettings(
        t1_duration_ms=230 if case == "overfull" else 50,
        t2_trigger_code=55 if case == "marker_collision" else 56,
    )
    before = document._project.model_copy(deep=True)
    replacements = document.replacements
    with pytest.raises(ValueError):
        document.apply_experiment_design(
            "faces",
            base_hz=4,
            slot_count=1 if case == "no_base_slot" else 4,
            attentional_blink=settings,
        )
    assert document._project == before
    assert document.replacements == replacements


def test_global_cadence_change_cannot_invalidate_another_active_ab_condition(document):
    _attach_t2(document)
    _apply_ab(document)
    document.update_condition("faces", attentional_blink=AttentionalBlinkSettings(isi_ms=120))
    second_id = document.create_condition(name="Other target pairs")
    second = document.get_condition(second_id)
    second.base_stimulus_set_id = document.get_condition("faces").base_stimulus_set_id
    second.oddball_stimulus_set_id = document.get_condition("faces").oddball_stimulus_set_id
    second.t2_stimulus_set_id = document.get_condition("faces").t2_stimulus_set_id
    before = document._project.model_copy(deep=True)
    with pytest.raises(ValueError):
        document.apply_experiment_design(
            second_id,
            base_hz=6,
            slot_count=5,
            attentional_blink=AttentionalBlinkSettings(),
        )
    assert document._project == before


def test_apply_accepts_imported_sources_pending_normalization(document):
    _attach_t2(document, mixed=True)
    assert document.get_condition_stimulus_set("faces", "t2").resolution is None
    _apply_ab(document)
    assert document.get_condition("faces").attentional_blink is not None


def test_duplicate_ab_uses_dedicated_empty_t2_set_and_copied_timing(document):
    source = _attach_t2(document)
    _apply_ab(document)
    duplicate_id = document.duplicate_condition("faces")
    duplicate = document.get_condition(duplicate_id)
    assert duplicate.t2_stimulus_set_id != source.set_id
    assert duplicate.attentional_blink == AttentionalBlinkSettings()
    assert document.get_condition_stimulus_set(duplicate_id, "t2").image_count == 0
    duplicate.attentional_blink.isi_ms = 70
    assert document.get_condition("faces").attentional_blink.isi_ms == 50
    document.remove_condition(duplicate_id)
    assert document.get_stimulus_set(duplicate.t2_stimulus_set_id) is None
    assert document.get_stimulus_set(source.set_id) is not None


def test_remove_condition_keeps_t2_source_referenced_by_another_condition(document):
    source = _attach_t2(document)
    other_id = document.create_condition(name="Other condition")
    document.get_condition(other_id).t2_stimulus_set_id = source.set_id
    document.remove_condition("faces")
    assert document.get_condition_stimulus_set(other_id, "t2").set_id == source.set_id
    assert (document._project_root / source.source_dir).is_dir()


def test_control_condition_reuses_t2_source_with_independent_timing(document):
    source = _attach_t2(document)
    _apply_ab(document)
    control_id = document.create_control_condition("faces", variant=StimulusVariant.GRAYSCALE)
    control = document.get_condition(control_id)
    assert control.t2_stimulus_set_id == source.set_id
    assert control.attentional_blink == AttentionalBlinkSettings()
    control.attentional_blink.t1_duration_ms = 70
    assert document.get_condition("faces").attentional_blink.t1_duration_ms == 50


@pytest.mark.parametrize("enabled", [True, False])
def test_modality_switch_rejects_t2_images_even_before_ab_apply(document, enabled):
    _attach_t2(document)
    if enabled:
        _apply_ab(document)
    before = document._project.model_copy(deep=True)
    with pytest.raises(DocumentError, match="image sources"):
        document.set_condition_stimulus_modality("faces", modality=StimulusModality.WORD)
    assert document._project == before


def test_normalization_includes_ab_t2_source(document):
    source = _attach_t2(document, mixed=True)
    scan = document.scan_condition_image_normalization()
    t2_scan = next(item for item in scan.sets if item.set_id == source.set_id)
    assert len(t2_scan.resolutions) == 2
    assert document.get_condition("faces").attentional_blink is not None
    result = document.normalize_condition_images(target_size=256)
    assert {item.set_id for item in result.sets} == {source.set_id}
    assert document.get_condition_stimulus_set("faces", "t2").resolution.as_tuple() == (256, 256)
    assert document.get_condition_stimulus_set("faces", "base").resolution.as_tuple() == (256, 256)


def test_replacing_t2_discards_only_unreferenced_model_and_manifest_entries(document):
    original = _attach_t2(document)
    replacement, summary = _source(document._project_root, set_id="replacement-t2")
    document.apply_designer_source("faces", role="t2", stimulus_set=replacement, summary=summary)
    assert document.get_stimulus_set(original.set_id) is None
    assert document.get_stimulus_set(replacement.set_id) is not None
    assert {item.set_id for item in document._manifest.sets} == {replacement.set_id}
    assert (document._project_root / original.source_dir).is_dir()


def test_replacing_t2_keeps_source_and_manifest_used_by_another_condition(document):
    original = _attach_t2(document)
    other_id = document.create_condition(name="Other")
    document.get_condition(other_id).t2_stimulus_set_id = original.set_id
    replacement, summary = _source(document._project_root, set_id="replacement-t2")
    document.apply_designer_source("faces", role="t2", stimulus_set=replacement, summary=summary)
    assert document.get_condition_stimulus_set(other_id, "t2").set_id == original.set_id
    assert {item.set_id for item in document._manifest.sets} == {
        original.set_id,
        replacement.set_id,
    }


@pytest.mark.parametrize("case", ["unknown_role", "unknown_condition", "empty_images"])
def test_invalid_source_apply_preserves_document_and_manifest(document, case):
    source, summary = _source(document._project_root)
    if case == "empty_images":
        source.image_count = 0
    before = document._project.model_copy(deep=True)
    old_manifest = document._manifest.model_copy(deep=True)
    with pytest.raises(DocumentError):
        document.apply_designer_source(
            "unknown" if case == "unknown_condition" else "faces",
            role="mask" if case == "unknown_role" else "t2",
            stimulus_set=source,
            summary=summary,
        )
    assert document._project == before
    assert document._manifest == old_manifest
    assert document.replacements == 0


def test_source_apply_manifest_write_failure_preserves_document(document, monkeypatch):
    source, summary = _source(document._project_root)
    before = document._project.model_copy(deep=True)
    old_manifest = document._manifest.model_copy(deep=True)

    def fail_write(*args):
        raise PermissionError("read-only manifest")

    monkeypatch.setattr("fpvs_studio.gui.document_stimuli.write_stimulus_manifest", fail_write)
    with pytest.raises(PermissionError, match="read-only manifest"):
        document.apply_designer_source("faces", role="t2", stimulus_set=source, summary=summary)
    assert document._project == before
    assert document._manifest == old_manifest
    assert document.replacements == 0
    assert document.manifest_changed.count == 0


def test_new_ab_condition_has_four_image_pools_and_no_oddball_mode_switch(document):
    condition_id = document.create_condition(name="Short interval")
    condition = document.get_condition(condition_id)
    assert condition.attentional_blink == AttentionalBlinkSettings()
    assert condition.duty_cycle_mode == DutyCycleMode.CONTINUOUS
    sources = [
        document.get_condition_stimulus_set(condition_id, role)
        for role in ("base", "t1", "t2", "isi")
    ]
    assert len({source.set_id for source in sources}) == 4
    assert all(source.modality == StimulusModality.IMAGE for source in sources)
    with pytest.raises(DocumentError, match="image sources"):
        document.set_condition_stimulus_modality(condition_id, modality=StimulusModality.WORD)
    with pytest.raises(DocumentError, match="continuous"):
        document.update_condition_timing_template(condition_id, DutyCycleMode.SINUSOIDAL)
    with pytest.raises(DocumentError, match="locked"):
        document.update_condition(condition_id, attentional_blink=None)


def test_oddball_cannot_accept_ab_timing_or_target_pools(sample_project, sample_project_root):
    document = _Document(sample_project, sample_project_root)
    before = document._project.model_copy(deep=True)
    source, summary = _source(sample_project_root)
    with pytest.raises(DocumentError, match="locked"):
        _apply_ab(document)
    with pytest.raises(DocumentError, match="Attentional-Blink"):
        document.apply_designer_source("faces", role="t2", stimulus_set=source, summary=summary)
    assert document._project == before
    condition_id = document.create_condition(name="New oddball")
    assert document.get_condition(condition_id).attentional_blink is None
    assert document.get_condition(condition_id).t2_stimulus_set_id is None


def test_legacy_oddball_cannot_be_converted_through_generic_condition_update(document):
    document.get_condition("faces").attentional_blink = None
    before = document._project.model_copy(deep=True)
    with pytest.raises(DocumentError, match="Separate"):
        document.update_condition("faces", attentional_blink=AttentionalBlinkSettings())
    assert document._project == before
