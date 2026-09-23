"""Portable native scene media, independent presets, and strict schema inventories."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from fpvs_studio.core import modifier_presets
from fpvs_studio.core.condition_modifiers import assign_modifier
from fpvs_studio.core.enums import ProjectSchemaVersion
from fpvs_studio.core.library_publish import prepare_library_bundle
from fpvs_studio.core.masking_presets import create_masking_modifier
from fpvs_studio.core.modifier_presets import (
    ModifierPreset,
    ModifierPresetError,
    apply_modifier_project,
    import_modifier_definition,
    load_modifier_preset,
    modifier_preset_root,
    save_modifier_preset,
)
from fpvs_studio.core.paths import filesystem_path
from fpvs_studio.core.project_bundle import (
    ProjectBundleError,
    export_project_bundle,
    import_project_bundle,
)
from fpvs_studio.core.project_config import (
    ProjectConfigError,
    ProjectConfigFile,
    create_project_from_config,
    export_project_config,
    read_project_config,
    write_project_config,
)
from fpvs_studio.core.scene_models import SceneVisual
from fpvs_studio.core.serialization import save_project_file
from fpvs_studio.core.task_assets import modifier_image_references, owned_image_references
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest


def _definition(source: Path):
    definition = create_masking_modifier(variant="faces", modifier_id="masking")
    owner = definition.modifier.pre_task_ids[0]
    visuals = []
    for index, identity in enumerate(("base-a", "base-b", "target", "mask-a", "mask-b",
                                      "overlay", "fixation")):
        relative = f"stimuli/task-assets/{owner}/{identity}.png"
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (12, 10), color=(index * 30, 70, 90)).save(path)
        visuals.append(SceneVisual(kind="image", visual_id=identity, image_path=relative,
                                   units="deg", size=(5, 5)))
    settings = definition.modifier.masking
    settings.base_visuals = visuals[:2]
    settings.target_visuals = visuals[2:3]
    settings.mask_visuals = visuals[3:5]
    settings.base_overlays = visuals[5:6]
    settings.fixation_visual = visuals[6]
    settings.target_answers = {"target": "angry"}
    return definition


def _project(sample_project, project_root: Path, source: Path):
    definition = _definition(source)
    sample_project.settings.protocol.base_hz = 5
    sample_project.settings.session.block_count = 1
    project = assign_modifier(
        sample_project, definition, [sample_project.conditions[0].condition_id],
    )
    project = apply_modifier_project(project_root, project, asset_sources={
        relative: source / relative for relative in modifier_image_references(definition.modifier)
    })
    save_project_file(project, project_root / "project.json")
    write_stimulus_manifest(project_root, create_empty_manifest(project.meta.project_id))
    return project


def test_masking_preset_rekeys_and_copies_all_media_independently(tmp_path):
    source = tmp_path / "source"
    definition = _definition(source)
    original_paths = modifier_image_references(definition.modifier)
    hashes = {hashlib.sha256((source / path).read_bytes()).hexdigest() for path in original_paths}
    library = tmp_path / "library"
    saved = save_modifier_preset(library, definition, source, name="Faces")
    assert saved.schema_version == "1.1.0"
    assert modifier_image_references(definition.modifier) == original_paths
    for path in original_paths:
        (source / path).unlink()
    loaded = load_modifier_preset(library, saved.preset_id)
    destination = tmp_path / "destination"
    destination.mkdir()
    imported = import_modifier_definition(destination, loaded.definition,
                                          modifier_preset_root(library, saved.preset_id))
    paths = modifier_image_references(imported.modifier)
    assert len(paths) == 7
    assert all(path.startswith(f"stimuli/task-assets/{imported.modifier.pre_task_ids[0]}/")
               for path in paths)
    assert imported.modifier.modifier_id != loaded.definition.modifier.modifier_id
    assert imported.modifier.masking.target_answers == {"target": "angry"}
    assert {
        hashlib.sha256(filesystem_path(destination / path).read_bytes()).hexdigest()
        for path in paths
    } == hashes
    payload = saved.model_dump(mode="json")
    payload["schema_version"] = "1.0.0"
    with pytest.raises(ValidationError, match="schema 1.1.0"):
        ModifierPreset.model_validate(payload)


def test_clean_library_bundle_preserves_native_scene_media_without_changing_source(
    tmp_path, sample_project, sample_project_root,
):
    project = _project(sample_project, sample_project_root, tmp_path / "source")
    project.stimulus_sets = []
    save_project_file(project, sample_project_root / "project.json")
    before = {path.relative_to(sample_project_root).as_posix(): path.read_bytes()
              for path in sample_project_root.rglob("*") if path.is_file()}
    media = modifier_image_references(project.condition_modifiers[0])
    expected_hashes = {path: hashlib.sha256(before[path]).hexdigest() for path in media}
    bundle = tmp_path / "masking-library.fpvsbundle"

    report = prepare_library_bundle(sample_project_root, bundle)
    imported = import_project_bundle(bundle, tmp_path / "recipient")

    assert set(report.included_paths) == {"project.json", "stimuli/manifest.json", *media}
    assert imported.project.condition_modifiers == project.condition_modifiers
    assert imported.project.task_modules == project.task_modules
    assert imported.project.conditions == project.conditions
    assert imported.project.settings.display == project.settings.display
    assert imported.project.settings.triggers == project.settings.triggers
    assert {path: hashlib.sha256((imported.project_root / path).read_bytes()).hexdigest()
            for path in media} == expected_hashes
    assert {path.relative_to(sample_project_root).as_posix(): path.read_bytes()
            for path in sample_project_root.rglob("*") if path.is_file()} == before


def test_masking_config_and_bundle_survive_source_deletion_and_relocation(
    tmp_path, sample_project, sample_project_root,
):
    source = tmp_path / "source"
    project = _project(sample_project, sample_project_root, source)
    modifier = project.condition_modifiers[0]
    paths = modifier_image_references(modifier)
    expected = {path: (sample_project_root / path).read_bytes() for path in paths}
    config = export_project_config(project, sample_project_root)
    assert config.schema_version == "1.5.0"
    assert len(config.task_assets) == 7
    assert {(asset.task_id, asset.relative_path) for asset in config.task_assets} == set(
        owned_image_references(project.task_modules, project.condition_modifiers)
    )
    config_path = tmp_path / "masking.fpvsconfig"
    write_project_config(config_path, config)
    bundle_path = tmp_path / "masking.fpvsbundle"
    export_project_bundle(sample_project_root, bundle_path, refresh_hz=60)
    for path in paths:
        (sample_project_root / path).unlink()
        (source / path).unlink()
    restored = create_project_from_config(
        tmp_path / "from-config", read_project_config(config_path),
    )
    imported = import_project_bundle(bundle_path, tmp_path / "from-bundle")
    for result in (restored, imported):
        assert result.project.schema_version.value == "1.7.0"
        assert result.project.condition_modifiers == project.condition_modifiers
        assert {path: (result.project_root / path).read_bytes() for path in paths} == expected


@pytest.mark.parametrize("failure", ["missing", "hash", "wrong-owner", "old-version"])
def test_masking_config_rejects_invalid_asset_inventory(
    failure, tmp_path, sample_project, sample_project_root,
):
    project = _project(sample_project, sample_project_root, tmp_path / "source")
    payload = export_project_config(project, sample_project_root).model_dump(mode="json")
    if failure == "missing":
        payload["task_assets"].pop()
    elif failure == "hash":
        payload["task_assets"][0]["data_base64"] = base64.b64encode(b"different").decode("ascii")
    elif failure == "wrong-owner":
        payload["task_assets"][0]["task_id"] = "other-task"
    else:
        payload["schema_version"] = "1.4.0"
    with pytest.raises(ValidationError):
        ProjectConfigFile.model_validate(payload)


def test_config_import_validates_mutated_inventory_before_creating_folders(
    tmp_path, sample_project, sample_project_root,
):
    project = _project(sample_project, sample_project_root, tmp_path / "source")
    config = export_project_config(project, sample_project_root)
    config.task_assets.pop()
    destination = tmp_path / "import"
    with pytest.raises(ProjectConfigError, match="inventory"):
        create_project_from_config(destination, config)
    assert not destination.exists()


def test_scene_asset_wrong_ownership_and_missing_source_do_not_apply(
    tmp_path, sample_project, sample_project_root,
):
    source = tmp_path / "source"
    definition = _definition(source)
    definition.modifier.masking.base_visuals[0].image_path = "stimuli/task-assets/other/a.png"
    with pytest.raises(ValueError, match="beneath"):
        owned_image_references(definition.task_modules, [definition.modifier])
    definition = _definition(source)
    project = assign_modifier(
        sample_project, definition, [sample_project.conditions[0].condition_id],
    )
    paths = modifier_image_references(definition.modifier)
    (source / paths[-1]).unlink()
    with pytest.raises(ModifierPresetError, match="missing"):
        apply_modifier_project(sample_project_root, project,
                               asset_sources={path: source / path for path in paths})
    assert not (sample_project_root / "stimuli" / "task-assets").exists()


def test_scene_asset_staging_failure_rolls_back(tmp_path, sample_project, monkeypatch):
    source, destination = tmp_path / "source", tmp_path / "destination"
    destination.mkdir()
    definition = _definition(source)
    project = assign_modifier(
        sample_project, definition, [sample_project.conditions[0].condition_id],
    )
    paths = modifier_image_references(definition.modifier)
    original = modifier_presets.shutil.copy2
    count = 0

    def fail_later(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("media read failed")
        return original(*args, **kwargs)

    monkeypatch.setattr(modifier_presets.shutil, "copy2", fail_later)
    with pytest.raises(OSError, match="media read failed"):
        apply_modifier_project(destination, project,
                               asset_sources={path: source / path for path in paths})
    assert list(destination.iterdir()) == []


def test_bundle_rejects_missing_scene_media(tmp_path, sample_project, sample_project_root):
    project = _project(sample_project, sample_project_root, tmp_path / "source")
    path = modifier_image_references(project.condition_modifiers[0])[0]
    (sample_project_root / path).unlink()
    with pytest.raises(ProjectBundleError, match="missing"):
        export_project_bundle(sample_project_root, tmp_path / "missing.fpvsbundle", refresh_hz=60)


def test_ordinary_config_still_uses_legacy_version(sample_project, sample_project_root, tmp_path):
    config = export_project_config(sample_project, sample_project_root)
    path = tmp_path / "ordinary.fpvsconfig"
    write_project_config(path, config)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.2.0"
    assert "condition_modifiers" not in payload


def test_native_task_without_masking_group_uses_scene_config_schema(
    sample_project, sample_project_root, tmp_path,
):
    sample_project.schema_version = ProjectSchemaVersion.V1_7
    sample_project.task_modules = create_masking_modifier().task_modules
    config = export_project_config(sample_project, sample_project_root)
    assert config.condition_modifiers == []
    assert config.schema_version == "1.5.0"
    restored = create_project_from_config(tmp_path / "native-task", config)
    assert restored.project.schema_version == ProjectSchemaVersion.V1_7
    assert restored.project.task_modules == sample_project.task_modules
