"""Legacy separation preserves source data and never overwrites another experiment."""

from __future__ import annotations

import hashlib
import json

import pytest

from fpvs_studio.core.enums import ExperimentCategory, StimulusVariant
from fpvs_studio.core.models import AttentionalBlinkSettings
from fpvs_studio.core.paths import slugify_project_name
from fpvs_studio.core.project_separation import separate_legacy_mixed_project
from fpvs_studio.core.serialization import load_project_file
from fpvs_studio.preprocessing.manifest import create_empty_manifest
from fpvs_studio.preprocessing.models import (
    DerivedImageRecord,
    SourceImageRecord,
    StimulusAssetRecord,
    StimulusManifest,
    StimulusSetManifest,
)


@pytest.fixture
def mixed_project(sample_project, sample_project_root):
    original = sample_project.conditions[0]
    ab = original.model_copy(update={
        "condition_id": "target-pairs",
        "name": "Target pairs",
        "attentional_blink": AttentionalBlinkSettings(),
        "t2_stimulus_set_id": original.oddball_stimulus_set_id,
    }, deep=True)
    project = sample_project.model_copy(update={
        "experiment_category": ExperimentCategory.ATTENTIONAL_BLINK,
        "conditions": [ab, original],
    }, deep=True)
    project.settings.protocol.base_hz = 4
    project.settings.protocol.oddball_every_n = 4
    path = sample_project_root / "project.json"
    legacy = project.model_dump(mode="json")
    legacy.pop("experiment_category")
    legacy["schema_version"] = "1.3.0"
    path.write_text(json.dumps(legacy), encoding="utf-8")
    (sample_project_root / "logs").mkdir(exist_ok=True)
    (sample_project_root / "logs" / "old-run.txt").write_text("previous results")
    return project, sample_project_root


def test_separation_preserves_conditions_timing_assets_and_historical_results(mixed_project):
    project, root = mixed_project
    original_conditions = [item.model_copy(deep=True) for item in project.conditions]
    source_images = {
        path.relative_to(root): path.read_bytes()
        for path in (root / "stimuli").rglob("*.png")
    }
    result = separate_legacy_mixed_project(
        root, project, create_empty_manifest(project.meta.project_id)
    )
    ab = load_project_file(root / "project.json")
    oddball = load_project_file(result.oddball_root / "project.json")
    assert ab == result.attentional_blink
    assert ab.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
    assert oddball.experiment_category == ExperimentCategory.FPVS_ODDBALL
    assert ab.conditions[0] == original_conditions[0]
    assert oddball.conditions[0] == original_conditions[1]
    assert ab.settings.protocol == oddball.settings.protocol == project.settings.protocol
    assert len(ab.conditions) == len(oddball.conditions) == 1
    assert source_images
    for relative, data in source_images.items():
        assert (root / relative).read_bytes() == data
        assert (result.oddball_root / relative).read_bytes() == data
    assert (root / "logs" / "old-run.txt").read_text() == "previous results"
    assert not (result.oddball_root / "logs" / "old-run.txt").exists()
    assert project.conditions == original_conditions
    recovery = result.oddball_root / "cache" / "legacy-mixed-project.json"
    assert json.loads(recovery.read_text()) == project.model_dump(mode="json")


def test_separation_never_overwrites_existing_sibling(mixed_project):
    project, root = mixed_project
    existing = root.parent / slugify_project_name(project.meta.name + " FPVS Oddball")
    existing.mkdir()
    marker = existing / "keep.txt"
    marker.write_text("keep")
    result = separate_legacy_mixed_project(root, project, None)
    assert result.oddball_root != existing
    assert marker.read_text() == "keep"


def test_failed_copy_keeps_original_project_and_removes_only_new_destination(
    mixed_project, monkeypatch,
):
    project, root = mixed_project
    before_json = (root / "project.json").read_bytes()
    before_siblings = set(root.parent.iterdir())

    def fail_copy(*args, **kwargs):
        raise OSError("Copy failed")

    monkeypatch.setattr("fpvs_studio.core.project_separation.shutil.copy2", fail_copy)
    with pytest.raises(OSError, match="Copy failed"):
        separate_legacy_mixed_project(root, project, None)
    assert (root / "project.json").read_bytes() == before_json
    assert set(root.parent.iterdir()) == before_siblings


def test_separation_rejects_unmixed_project_without_creating_files(
    sample_project, sample_project_root,
):
    before = set(sample_project_root.parent.iterdir())
    with pytest.raises(ValueError, match="mixed"):
        separate_legacy_mixed_project(sample_project_root, sample_project, None)
    assert set(sample_project_root.parent.iterdir()) == before


def test_separation_copies_contained_sources_outside_stimuli(mixed_project):
    project, root = mixed_project
    alternate = root / "custom-images"
    alternate.mkdir()
    image = alternate / "original.png"
    image.write_bytes(b"preserve source")
    project.stimulus_sets[0].source_dir = "custom-images"
    project.manual_removed_electrodes = {"100": ["A1"]}
    result = separate_legacy_mixed_project(root, project, None)
    assert (result.oddball_root / "custom-images" / image.name).read_bytes() == image.read_bytes()
    oddball = load_project_file(result.oddball_root / "project.json")
    assert oddball.manual_removed_electrodes == project.manual_removed_electrodes


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_missing_populated_source_rejects_before_any_destination_is_created(
    mixed_project, monkeypatch, kind,
):
    project, root = mixed_project
    stimulus_set = project.stimulus_sets[0]
    stimulus_set.source_dir = "unavailable-images"
    if kind == "file":
        (root / stimulus_set.source_dir).write_text("This is a file, not a folder.")
    before = (root / "project.json").read_bytes()
    siblings = set(root.parent.iterdir())

    def reject_mkdir(*args, **kwargs):
        pytest.fail("Source validation must finish before creating a destination.")

    monkeypatch.setattr("pathlib.Path.mkdir", reject_mkdir)
    with pytest.raises(ValueError, match="image folder.*missing"):
        separate_legacy_mixed_project(root, project, None)
    assert (root / "project.json").read_bytes() == before
    assert set(root.parent.iterdir()) == siblings


def test_missing_empty_draft_source_can_be_separated(mixed_project):
    project, root = mixed_project
    stimulus_set = project.stimulus_sets[0]
    stimulus_set.source_dir = "empty-draft-images"
    stimulus_set.image_count = 0
    stimulus_set.resolution = None
    result = separate_legacy_mixed_project(root, project, None)
    copied = load_project_file(result.oddball_root / "project.json")
    source = next(item for item in copied.stimulus_sets if item.set_id == stimulus_set.set_id)
    assert source.source_dir == "empty-draft-images"
    assert source.image_count == 0


def _manifest_with_derived_file(project, root):
    stimulus_set = project.stimulus_sets[0]
    source_path = next((root / stimulus_set.source_dir).glob("*.png"))
    asset = StimulusAssetRecord(
        source=SourceImageRecord(
            relative_path=source_path.relative_to(root).as_posix(),
            sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
            source_format="png", resolution=stimulus_set.resolution,
        ),
        derivatives=[DerivedImageRecord(
            variant=StimulusVariant.GRAYSCALE,
            relative_path="custom-derivatives/control.png",
            resolution=stimulus_set.resolution,
        )],
    )
    manifest = StimulusManifest(project_id=project.meta.project_id, sets=[StimulusSetManifest(
        set_id=stimulus_set.set_id, source_dir=stimulus_set.source_dir, assets=[asset],
    )])
    return manifest, asset, source_path.read_bytes()


@pytest.mark.parametrize("kind", ["source", "derivative"])
def test_missing_manifest_file_preserves_original_and_creates_no_sibling(
    mixed_project, monkeypatch, kind,
):
    project, root = mixed_project
    manifest, asset, _ = _manifest_with_derived_file(project, root)
    if kind == "source":
        asset.source.relative_path = "stimuli/missing-source.png"
    before = (root / "project.json").read_bytes()
    siblings = set(root.parent.iterdir())

    def reject_mkdir(*args, **kwargs):
        pytest.fail("Manifest validation must finish before creating a destination.")

    monkeypatch.setattr("pathlib.Path.mkdir", reject_mkdir)
    with pytest.raises(ValueError, match="declared stimulus file is missing"):
        separate_legacy_mixed_project(root, project, manifest)
    assert (root / "project.json").read_bytes() == before
    assert set(root.parent.iterdir()) == siblings


def test_manifest_derivative_outside_source_directories_is_copied(mixed_project):
    project, root = mixed_project
    manifest, asset, payload = _manifest_with_derived_file(project, root)
    relative = asset.derivatives[0].relative_path
    derivative = root / relative
    derivative.parent.mkdir()
    derivative.write_bytes(payload)
    result = separate_legacy_mixed_project(root, project, manifest)
    assert (result.oddball_root / relative).read_bytes() == payload
    assert derivative.read_bytes() == payload


def test_final_replace_failure_rolls_back_copy_and_preserves_original(mixed_project, monkeypatch):
    project, root = mixed_project
    before = (root / "project.json").read_bytes()
    siblings = set(root.parent.iterdir())
    attempted = False

    def fail_replace(*args):
        nonlocal attempted
        attempted = True
        raise OSError("Original project is locked")

    monkeypatch.setattr("fpvs_studio.core.project_separation.os.replace", fail_replace)
    with pytest.raises(OSError, match="Original project is locked"):
        separate_legacy_mixed_project(root, project, None)
    assert attempted
    assert (root / "project.json").read_bytes() == before
    assert set(root.parent.iterdir()) == siblings
    assert not list(root.glob(".project-separation-*.json"))


def test_foreign_manifest_is_rejected_without_rewriting_provenance(mixed_project, monkeypatch):
    project, root = mixed_project
    manifest = create_empty_manifest("another-project")
    before = (root / "project.json").read_bytes()
    siblings = set(root.parent.iterdir())

    def reject_mkdir(*args, **kwargs):
        pytest.fail("Manifest identity must be checked before creating a destination.")

    monkeypatch.setattr("pathlib.Path.mkdir", reject_mkdir)
    with pytest.raises(ValueError, match="manifest belongs to a different project"):
        separate_legacy_mixed_project(root, project, manifest)
    assert manifest.project_id == "another-project"
    assert (root / "project.json").read_bytes() == before
    assert set(root.parent.iterdir()) == siblings
