"""Local modifier presets and transactional intake of project-owned task media.

The library is independent of project assignments. Applied projects retain complete
definitions and media, and never need their source library during execution.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import Field, field_validator

from fpvs_studio.core.condition_modifiers import (
    ModifierDefinition,
    modifier_task_ids,
    validate_image_memory_definition,
)
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.paths import filesystem_path, resolve_project_relative_path, templates_dir
from fpvs_studio.core.task_assets import SUPPORTED_TASK_ASSET_SUFFIXES, task_image_references
from fpvs_studio.core.task_models import (
    ConditionModifierKind,
    TaskBaseModel,
    TaskModule,
    validate_task_slug,
)


class ModifierPresetError(ValueError):
    """An invalid local definition, missing medium, or unsafe preset operation."""


class ModifierPreset(TaskBaseModel):
    """A versioned local copy; no condition assignments or participant responses."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    preset_id: str
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=16_384)
    definition: ModifierDefinition

    @field_validator("preset_id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return validate_task_slug(value, field_name="Preset id")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Preset name may not be blank.")
        return value.strip()


def modifier_presets_dir(fpvs_root: Path) -> Path:
    """Return the configured Studio root's modifier library without creating it."""

    return resolve_project_relative_path(
        Path(fpvs_root),
        (templates_dir(Path(".")) / "condition-modifiers").as_posix(),
    )


def modifier_preset_root(fpvs_root: Path, preset_id: str) -> Path:
    validate_task_slug(preset_id, field_name="Preset id")
    return resolve_project_relative_path(modifier_presets_dir(fpvs_root), preset_id)


def load_modifier_preset(fpvs_root: Path, preset_id: str) -> ModifierPreset:
    path = modifier_preset_root(fpvs_root, preset_id) / "preset.json"
    try:
        preset = ModifierPreset.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ModifierPresetError(f"Unable to read modifier preset '{preset_id}': {exc}") from exc
    if preset.preset_id != preset_id:
        raise ModifierPresetError(f"Preset identity does not match its folder: {preset_id}")
    _validate_definition(preset.definition)
    _asset_sources(preset.definition.task_modules, path.parent, None)
    return preset


def list_modifier_presets(fpvs_root: Path) -> list[ModifierPreset]:
    root = modifier_presets_dir(fpvs_root)
    if not root.exists():
        return []
    if not root.is_dir():
        raise ModifierPresetError(f"Modifier library is not a directory: {root}")
    result = [
        load_modifier_preset(fpvs_root, path.name)
        for path in sorted(root.iterdir())
        if path.is_dir() and not path.name.startswith(".")
    ]
    return sorted(result, key=lambda preset: (preset.name.casefold(), preset.preset_id))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with filesystem_path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_definition(definition: ModifierDefinition) -> None:
    if definition.modifier.kind == ConditionModifierKind.IMAGE_MEMORY:
        validate_image_memory_definition(definition, allow_incomplete=True)


def _asset_sources(
    tasks: Sequence[TaskModule],
    source_root: Path,
    overrides: Mapping[str, Path] | None,
) -> dict[str, Path]:
    sources: dict[str, Path] = {}
    for task in tasks:
        prefix = f"stimuli/task-assets/{task.task_id}/"
        for relative in task_image_references(task):
            if not relative.startswith(prefix):
                raise ModifierPresetError(f"Task '{task.task_id}' image must be beneath {prefix}")
            # Validate even when a staged override supplies the actual source.
            contained = resolve_project_relative_path(source_root, relative)
            source = filesystem_path(
                Path(overrides[relative]) if overrides and relative in overrides else contained
            )
            if source.suffix.lower() not in SUPPORTED_TASK_ASSET_SUFFIXES:
                raise ModifierPresetError(f"Unsupported modifier image: {source.name}")
            if not source.is_file():
                raise ModifierPresetError(f"Modifier image is missing: {relative}")
            sources[relative] = source
    return sources


def _copy_assets(destination_root: Path, sources: Mapping[str, Path]) -> list[Path]:
    """Stage all reads first; publish new assets only, rolling back our files on error."""

    destination_root = filesystem_path(destination_root)
    if not destination_root.is_dir():
        raise ModifierPresetError(f"Asset destination is not a directory: {destination_root}")
    planned: list[tuple[str, Path, Path]] = []
    for relative, source in sources.items():
        destination = resolve_project_relative_path(destination_root, relative)
        if destination.exists():
            if not destination.is_file() or _sha256(destination) != _sha256(source):
                raise ModifierPresetError(f"A different image already uses path: {relative}")
        else:
            planned.append((relative, source, destination))
    created: list[Path] = []
    created_dirs: list[Path] = []
    try:
        with tempfile.TemporaryDirectory(prefix=".modifier-stage-", dir=destination_root) as stage:
            staged: list[tuple[Path, Path]] = []
            for index, (_, source, destination) in enumerate(planned):
                temporary = Path(stage) / str(index)
                shutil.copy2(source, temporary)
                staged.append((temporary, destination))
            for temporary, destination in staged:
                missing: list[Path] = []
                parent = destination.parent
                while not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                for directory in reversed(missing):
                    directory.mkdir()
                    created_dirs.append(directory)
                # Opening exclusively avoids replacing another operation's media.
                with temporary.open("rb") as source_handle, destination.open("xb") as handle:
                    created.append(destination)
                    shutil.copyfileobj(source_handle, handle)
        return created
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        for directory in reversed(created_dirs):
            directory.rmdir()
        raise


def apply_modifier_project(
    project_root: Path,
    draft_project: ProjectFile,
    *,
    asset_sources: Mapping[str, Path] | None = None,
) -> ProjectFile:
    """Validate a detached draft and commit its staged media; never save project.json.

    The GUI replaces its live document only after this worker operation succeeds.
    Existing project assets remain owned by the user, including unused older images.
    """

    project = ProjectFile.model_validate(draft_project.model_dump(mode="python"))
    for modifier in project.condition_modifiers:
        owned = modifier_task_ids(modifier)
        _validate_definition(ModifierDefinition(
            modifier=modifier,
            task_modules=[task for task in project.task_modules if task.task_id in owned],
        ))
    sources = _asset_sources(project.task_modules, project_root, asset_sources)
    _copy_assets(Path(project_root), sources)
    return project


def _remap_definition(
    definition: ModifierDefinition,
    source_root: Path,
    *,
    modifier_id: str,
    asset_sources: Mapping[str, Path] | None = None,
) -> tuple[ModifierDefinition, dict[str, Path]]:
    validate_task_slug(modifier_id, field_name="Modifier id")
    _validate_definition(definition)
    sources = _asset_sources(definition.task_modules, source_root, asset_sources)
    task_ids = {
        task.task_id: f"{modifier_id}-task-{index + 1}"
        for index, task in enumerate(definition.task_modules)
    }
    links: dict[str, str] = {}
    media: dict[str, Path] = {}
    payload = definition.model_dump(mode="json")
    modifier = payload["modifier"]
    modifier["modifier_id"] = modifier_id
    for key in ("pre_task_ids", "post_task_ids"):
        modifier[key] = [task_ids[task_id] for task_id in modifier[key]]
    if modifier.get("baseline_task_id") is not None:
        modifier["baseline_task_id"] = task_ids[modifier["baseline_task_id"]]
    for task in payload["task_modules"]:
        task["task_id"] = task_ids[task["task_id"]]
        for key in ("backward_counting", "image_memory"):
            settings = task.get(key)
            if settings is not None:
                link = settings["link_id"]
                links.setdefault(link, f"{modifier_id}-link-{len(links) + 1}")
                settings["link_id"] = links[link]
        for step in task["steps"]:
            items = [*step["items"], *(
                option for question in step["questions"] for option in question["options"]
            )]
            for item in items:
                old_path = item.get("image_path")
                if old_path is None:
                    continue
                source = sources[old_path]
                name = f"{_sha256(source)}{source.suffix.lower()}"
                new_path = f"stimuli/task-assets/{task['task_id']}/{name}"
                item["image_path"] = new_path
                media[new_path] = source
    return ModifierDefinition.model_validate(payload), media


def import_modifier_definition(
    project_root: Path,
    definition: ModifierDefinition,
    source_root: Path,
    *,
    modifier_id: str | None = None,
    asset_sources: Mapping[str, Path] | None = None,
) -> ModifierDefinition:
    """Copy a preset into an explicit destination (usually the editor's staging root)."""

    copied, sources = _remap_definition(
        definition, source_root,
        modifier_id=modifier_id or f"modifier-{uuid4().hex[:16]}",
        asset_sources=asset_sources,
    )
    _copy_assets(Path(project_root), sources)
    return copied


def save_modifier_preset(
    fpvs_root: Path,
    definition: ModifierDefinition,
    source_root: Path,
    *,
    name: str,
    description: str = "",
    preset_id: str | None = None,
    asset_sources: Mapping[str, Path] | None = None,
) -> ModifierPreset:
    """Save or explicitly update one local preset with its own complete media copies."""

    chosen_id = preset_id or f"preset-{uuid4().hex[:16]}"
    validate_task_slug(chosen_id, field_name="Preset id")
    copied, sources = _remap_definition(
        definition, source_root, modifier_id=chosen_id, asset_sources=asset_sources,
    )
    preset = ModifierPreset(
        preset_id=chosen_id, name=name, description=description, definition=copied,
    )
    destination = modifier_preset_root(fpvs_root, chosen_id)
    existed = destination.exists()
    if existed and preset_id is None:
        raise ModifierPresetError(f"Preset already exists: {chosen_id}")
    destination.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    temporary: Path | None = None
    try:
        created = _copy_assets(destination, sources)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix=".preset-", suffix=".json",
            dir=destination, delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(preset.model_dump(mode="json"), handle, indent=2)
            handle.write("\n")
        temporary.replace(destination / "preset.json")
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        for path in reversed(created):
            path.unlink(missing_ok=True)
        if not existed:
            # This exact new UUID directory belongs solely to the failed operation.
            shutil.rmtree(destination)
        raise
    return preset
