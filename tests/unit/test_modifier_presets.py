"""Local library isolation, transactional media, and portable modifier projects."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from fpvs_studio.core import modifier_presets
from fpvs_studio.core.condition_modifiers import (
    MemoryImage,
    assign_modifier,
    create_backward_counting_modifier,
    create_image_memory_modifier,
)
from fpvs_studio.core.enums import ExperimentCategory, ProjectSchemaVersion
from fpvs_studio.core.modifier_presets import (
    ModifierPresetError,
    apply_modifier_project,
    import_modifier_definition,
    list_modifier_presets,
    load_modifier_preset,
    modifier_preset_root,
    modifier_presets_dir,
    save_modifier_preset,
)
from fpvs_studio.core.paths import filesystem_path, resolve_project_relative_path
from fpvs_studio.core.project_bundle import export_project_bundle, import_project_bundle
from fpvs_studio.core.project_config import (
    create_project_from_config,
    export_project_config,
    read_project_config,
    write_project_config,
)
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import load_project_file, model_to_json, save_project_file
from fpvs_studio.core.task_assets import task_image_references


def memory_definition(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    targets, report_targets, foils = [], [], []
    for index in range(8):
        image_id = f"image-{index + 1}"
        relative = f"stimuli/task-assets/memory-recognition/{image_id}.png"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (8, 8), (index * 25, 80, 130)).save(path)
        item = MemoryImage(image_id=image_id, image_path=relative)
        if index < 4:
            report_targets.append(item)
            study_path = f"stimuli/task-assets/memory-study/{image_id}.png"
            destination = root / study_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(path.read_bytes())
            targets.append(MemoryImage(image_id=image_id, image_path=study_path))
        else:
            foils.append(item)
    return create_image_memory_modifier(
        modifier_id="memory", target_images=targets, foil_images=foils,
        recognition_target_images=report_targets,
    )


def test_library_read_does_not_create_folders(tmp_path):
    assert list_modifier_presets(tmp_path) == []
    assert not modifier_presets_dir(tmp_path).exists()


def test_counting_preset_has_independent_settings_and_remapped_links(tmp_path):
    definition = create_backward_counting_modifier(baseline_duration_seconds=30)
    preset = save_modifier_preset(tmp_path, definition, tmp_path, name="My counting")
    assert preset.definition.modifier.modifier_id != definition.modifier.modifier_id
    configs = [task.backward_counting for task in preset.definition.task_modules]
    assert configs[0].duration_seconds == 30
    assert configs[1].link_id == configs[2].link_id
    assert configs[0].link_id != configs[1].link_id
    assert list_modifier_presets(tmp_path) == [preset]
    assert preset.definition.task_modules != definition.task_modules
    assert "condition_ids" not in preset.model_dump_json()


def test_memory_library_and_import_own_complete_asset_copies(tmp_path):
    source = tmp_path / "source"
    definition = memory_definition(source)
    preset = save_modifier_preset(tmp_path / "library", definition, source, name="Memory")
    for image in source.rglob("*.png"):
        image.unlink()
    loaded = load_modifier_preset(tmp_path / "library", preset.preset_id)
    destination = tmp_path / "draft"
    destination.mkdir()
    imported = import_modifier_definition(
        destination, loaded.definition,
        modifier_preset_root(tmp_path / "library", preset.preset_id),
    )
    assert imported.modifier.modifier_id != loaded.definition.modifier.modifier_id
    links = {task.image_memory.link_id for task in imported.task_modules}
    assert len(links) == 1
    for task in imported.task_modules:
        for relative in task_image_references(task):
            assert relative.startswith(f"stimuli/task-assets/{task.task_id}/")
            assert resolve_project_relative_path(destination, relative).is_file()


def test_missing_media_does_not_create_preset_or_project_assets(tmp_path, sample_project):
    source = tmp_path / "source"
    definition = memory_definition(source)
    (source / task_image_references(definition.task_modules[0])[0]).unlink()
    with pytest.raises(ModifierPresetError, match="missing"):
        save_modifier_preset(tmp_path / "library", definition, source, name="Missing")
    assert not (tmp_path / "library").exists()
    draft = assign_modifier(sample_project, definition, [sample_project.conditions[0].condition_id])
    destination = tmp_path / "project"
    destination.mkdir()
    sources = {relative: source / relative for task in definition.task_modules
               for relative in task_image_references(task)}
    with pytest.raises(ModifierPresetError, match="missing"):
        apply_modifier_project(destination, draft, asset_sources=sources)
    assert list(destination.iterdir()) == []
    assert sample_project.condition_modifiers == []


def test_failed_staging_keeps_project_unchanged(tmp_path, sample_project, monkeypatch):
    source = tmp_path / "source"
    definition = memory_definition(source)
    project_root = tmp_path / "project"
    project_root.mkdir()
    draft = assign_modifier(sample_project, definition, [sample_project.conditions[0].condition_id])
    sources = {relative: source / relative for task in definition.task_modules
               for relative in task_image_references(task)}
    original = modifier_presets.shutil.copy2
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("Simulated failed media read")
        return original(*args, **kwargs)

    monkeypatch.setattr(modifier_presets.shutil, "copy2", fail_second)
    with pytest.raises(OSError, match="Simulated"):
        apply_modifier_project(project_root, draft, asset_sources=sources)
    assert list(project_root.iterdir()) == []


def test_explicit_preset_update_is_atomic_on_json_failure(tmp_path, monkeypatch):
    definition = create_backward_counting_modifier(baseline_duration_seconds=30)
    saved = save_modifier_preset(tmp_path, definition, tmp_path, name="Original")

    def fail_write(*args, **kwargs):
        raise OSError("Simulated disk full")

    monkeypatch.setattr(modifier_presets.json, "dump", fail_write)
    with pytest.raises(OSError, match="disk full"):
        save_modifier_preset(tmp_path, definition, tmp_path, name="Replacement",
                             preset_id=saved.preset_id)
    assert load_modifier_preset(tmp_path, saved.preset_id) == saved
    assert not list(modifier_preset_root(tmp_path, saved.preset_id).glob(".preset-*"))


def test_invalid_library_is_explicit_and_path_escape_rejected(tmp_path):
    with pytest.raises(ValueError):
        modifier_preset_root(tmp_path, "../escape")
    path = modifier_preset_root(tmp_path, "broken")
    path.mkdir(parents=True)
    (path / "preset.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ModifierPresetError, match="broken"):
        list_modifier_presets(tmp_path)


def test_modifier_config_and_bundle_retain_media_and_definitions(tmp_path):
    scaffold = create_project(tmp_path / "s", "Study",
                              experiment_category=ExperimentCategory.COGNITIVE_LOAD_FPVS)
    source = tmp_path / "images"
    definition = memory_definition(source)
    project = assign_modifier(scaffold.project, definition, ["condition-1-no-load"])
    sources = {relative: source / relative for task in definition.task_modules
               for relative in task_image_references(task)}
    project = apply_modifier_project(scaffold.project_root, project, asset_sources=sources)
    assert project.schema_version == ProjectSchemaVersion.V1_6
    save_project_file(project, scaffold.project_root / "project.json")
    assert load_project_file(scaffold.project_root / "project.json") == project
    config = export_project_config(project, scaffold.project_root)
    assert config.schema_version == "1.4.0"
    config_path = tmp_path / "study.fpvsconfig"
    write_project_config(config_path, config)
    restored = create_project_from_config(tmp_path / "c", read_project_config(config_path))
    assert restored.project.condition_modifiers == project.condition_modifiers
    assert restored.project.task_modules == project.task_modules
    bundle = tmp_path / "study.fpvsbundle"
    export_project_bundle(scaffold.project_root, bundle, refresh_hz=60)
    imported = import_project_bundle(bundle, tmp_path / "b")
    assert imported.project.condition_modifiers == project.condition_modifiers
    for task in definition.task_modules:
        for relative in task_image_references(task):
            assert resolve_project_relative_path(imported.project_root, relative).is_file()


def test_legacy_serialization_omits_new_empty_grouping(sample_project):
    payload = json.loads(model_to_json(sample_project))
    assert "condition_modifiers" not in payload
    assert payload["schema_version"] == "1.4.0"


def test_long_library_root_roundtrip(tmp_path):
    root = tmp_path / ("a" * 80) / ("b" * 80) / ("c" * 80)
    filesystem_path(root).mkdir(parents=True)
    definition = memory_definition(tmp_path / "images")
    saved = save_modifier_preset(root, definition, tmp_path / "images", name="Long path")
    assert load_modifier_preset(root, saved.preset_id) == saved


def test_long_project_and_external_source_paths(tmp_path, sample_project):
    source = tmp_path / "images"
    definition = memory_definition(source)
    long_root = tmp_path / ("a" * 80) / ("b" * 80) / ("c" * 80)
    filesystem_path(long_root).mkdir(parents=True)
    long_source = long_root / "source.png"
    filesystem_path(long_source).write_bytes(
        (source / task_image_references(definition.task_modules[0])[0]).read_bytes()
    )
    sources = {relative: source / relative for task in definition.task_modules
               for relative in task_image_references(task)}
    sources[task_image_references(definition.task_modules[0])[0]] = long_source
    draft = assign_modifier(sample_project, definition, [sample_project.conditions[0].condition_id])
    assert apply_modifier_project(long_root, draft, asset_sources=sources) == draft
    staging = long_root / "draft"
    filesystem_path(staging).mkdir()
    copied = import_modifier_definition(staging, definition, source)
    for task in copied.task_modules:
        assert all(resolve_project_relative_path(staging, path).is_file()
                   for path in task_image_references(task))


@pytest.mark.parametrize("failed_index", ["0", "1"])
def test_failed_staged_read_leaves_no_empty_published_image(tmp_path, monkeypatch, failed_index):
    source = tmp_path / "source.png"
    source.write_bytes(b"test-only-image")
    destination = tmp_path / "destination"
    destination.mkdir()
    original = Path.open

    def fail_staged_read(path, mode="r", *args, **kwargs):
        if (mode == "rb" and path.name == failed_index
                and path.parent.name.startswith(".modifier-stage-")):
            raise OSError("Simulated staged read failure")
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_staged_read)
    with pytest.raises(OSError, match="staged read failure"):
        modifier_presets._copy_assets(destination, {
            "stimuli/task-assets/test/image-1.png": source,
            "stimuli/task-assets/test/image-2.png": source,
        })
    assert list(destination.iterdir()) == []


def test_existing_different_image_is_never_overwritten(tmp_path):
    source = tmp_path / "source.png"
    source.write_bytes(b"new image bytes")
    destination = tmp_path / "destination"
    target = destination / "stimuli/task-assets/test/image.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"existing image bytes")
    with pytest.raises(ModifierPresetError, match="different image"):
        modifier_presets._copy_assets(destination, {"stimuli/task-assets/test/image.png": source})
    assert target.read_bytes() == b"existing image bytes"
