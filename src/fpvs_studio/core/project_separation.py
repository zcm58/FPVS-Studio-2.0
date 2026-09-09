"""Explicit, preservation-first separation of legacy mixed experiments."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.experiment_categories import require_valid_experiment_category
from fpvs_studio.core.models import Condition, ProjectFile, utc_now
from fpvs_studio.core.paths import (
    filesystem_path,
    resolve_project_relative_path,
    slugify_project_name,
)
from fpvs_studio.core.serialization import model_to_json, save_project_file
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest
from fpvs_studio.preprocessing.models import StimulusManifest


@dataclass(frozen=True)
class SeparatedProjects:
    attentional_blink: ProjectFile
    oddball_root: Path


def _with_conditions(project: ProjectFile, conditions: list[Condition]) -> ProjectFile:
    set_ids = {
        set_id
        for condition in conditions
        for set_id in (
            condition.base_stimulus_set_id,
            condition.oddball_stimulus_set_id,
            condition.t2_stimulus_set_id,
            condition.isi_stimulus_set_id,
        )
        if set_id is not None
    }
    task_ids = {
        binding.task_id
        for condition in conditions
        for binding in (*condition.pre_task_bindings, *condition.post_task_bindings)
    }
    payload = project.model_dump()
    payload.update(
        conditions=[
            item.model_copy(update={"order_index": index})
            for index, item in enumerate(conditions)
        ],
        stimulus_sets=[item for item in project.stimulus_sets if item.set_id in set_ids],
        task_modules=[item for item in project.task_modules if item.task_id in task_ids],
    )
    return ProjectFile.model_validate(payload)


def _validated_source_inventory(
    root: Path, project: ProjectFile, manifest: StimulusManifest | None,
) -> tuple[set[Path], set[str]]:
    """Resolve source directories and referenced manifest files before any writes."""
    source_roots = {root / "stimuli"}
    for stimulus_set in project.stimulus_sets:
        if stimulus_set.source_dir is None:
            continue
        source_root = resolve_project_relative_path(root, stimulus_set.source_dir)
        if not source_root.is_dir() and (
            stimulus_set.image_count > 0 or source_root.exists()
        ):
            raise ValueError(
                f"Cannot separate: image folder for '{stimulus_set.name}' is missing "
                f"or is not a folder: {stimulus_set.source_dir}. Restore it first."
            )
        source_roots.add(source_root)
    manifest_files: set[str] = set()
    declared_sets = {item.set_id for item in project.stimulus_sets}
    for manifest_set in manifest.sets if manifest is not None else []:
        if manifest_set.set_id not in declared_sets:
            continue
        for asset in manifest_set.assets:
            for relative in (
                asset.source.relative_path,
                *(record.relative_path for record in asset.derivatives),
            ):
                path = resolve_project_relative_path(root, relative)
                if not path.is_file():
                    raise ValueError(
                        "Cannot separate: a declared stimulus file is missing or is not "
                        f"a file: {relative}. Restore it first."
                    )
                manifest_files.add(relative)
    return source_roots, manifest_files


def separate_legacy_mixed_project(
    project_root: Path,
    project: ProjectFile,
    manifest: StimulusManifest | None,
) -> SeparatedProjects:
    """Copy oddball conditions to a new sibling, then save the AB-only original.

    Invoke only after the user chooses separation. Images and old run records in
    the original project stay untouched. No original JSON is changed until the
    new experiment is completely written. Failed copies remove only their newly
    created destination. The caller must keep the snapshot unedited while working.
    """
    if project.experiment_category != ExperimentCategory.ATTENTIONAL_BLINK:
        raise ValueError("Only legacy mixed Attentional-Blink projects need separation.")
    ordered = sorted(project.conditions, key=lambda item: item.order_index)
    ab_conditions = [item for item in ordered if item.attentional_blink is not None]
    oddball_conditions = [item for item in ordered if item.attentional_blink is None]
    if not ab_conditions or not oddball_conditions:
        raise ValueError("This project does not contain both experiment types.")
    if manifest is not None and manifest.project_id != project.meta.project_id:
        raise ValueError(
            "Cannot separate: the stimulus manifest belongs to a different project. "
            "Restore the matching manifest first."
        )

    ab_project = _with_conditions(project, ab_conditions)
    ab_project.meta.updated_at = utc_now()
    # Dormant T2 sources are copied with the assets but have no role in oddball runs.
    oddball_conditions = [
        item.model_copy(update={"t2_stimulus_set_id": None, "isi_stimulus_set_id": None}, deep=True)
        for item in oddball_conditions
    ]
    oddball_payload = _with_conditions(project, oddball_conditions).model_dump()
    oddball_payload["experiment_category"] = ExperimentCategory.FPVS_ODDBALL
    oddball_project = ProjectFile.model_validate(oddball_payload)
    oddball_project.settings.condition_profile_id = None
    oddball_project.meta.created_at = utc_now()
    oddball_project.meta.updated_at = utc_now()
    require_valid_experiment_category(ab_project)
    require_valid_experiment_category(oddball_project)

    root = filesystem_path(project_root).resolve()
    source_roots, manifest_files = _validated_source_inventory(root, project, manifest)
    parent = root.parent
    stem = slugify_project_name(project.meta.name + " FPVS Oddball")
    suffix = 1
    while True:
        project_id = stem if suffix == 1 else f"{stem}-{suffix}"
        destination = parent / project_id
        try:
            destination.mkdir()
        except FileExistsError:
            suffix += 1
        else:
            break
    temporary_original = root / f".project-separation-{uuid4().hex}.json"
    try:
        oddball_project.meta.project_id = project_id
        oddball_project.meta.name = f"{project.meta.name} - FPVS-Oddball"
        copied: set[str] = set()
        for source_root in source_roots:
            if not source_root.is_dir():
                continue
            for source in filesystem_path(source_root).rglob("*"):
                if not source.is_file():
                    continue
                relative = source.relative_to(root).as_posix()
                if relative in copied:
                    continue
                checked_source = resolve_project_relative_path(root, relative)
                target = resolve_project_relative_path(destination, relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(checked_source, target)
                copied.add(relative)
        for relative in sorted(manifest_files - copied):
            source = resolve_project_relative_path(root, relative)
            target = resolve_project_relative_path(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for folder in ("stimuli", "runs", "logs", "cache"):
            (destination / folder).mkdir(exist_ok=True)
        (destination / "cache" / "legacy-mixed-project.json").write_text(
            project.model_dump_json(indent=2), encoding="utf-8"
        )
        if manifest is not None:
            (destination / "cache" / "legacy-mixed-manifest.json").write_text(
                manifest.model_dump_json(indent=2), encoding="utf-8"
            )
        copied_manifest = (manifest or create_empty_manifest(project_id)).model_copy(
            update={
                "project_id": project_id,
                "sets": [
                    item for item in manifest.sets
                    if item.set_id in {source.set_id for source in oddball_project.stimulus_sets}
                ] if manifest is not None else [],
            },
            deep=True,
        )
        write_stimulus_manifest(destination, copied_manifest)
        save_project_file(oddball_project, destination / "project.json")
        temporary_original.write_text(model_to_json(ab_project), encoding="utf-8")
        os.replace(temporary_original, root / "project.json")
    except Exception:
        temporary_original.unlink(missing_ok=True)
        # This exact directory was created by this call; never remove an existing project.
        resolved_destination = destination.resolve()
        if resolved_destination.parent == parent and resolved_destination != root:
            shutil.rmtree(resolved_destination)
        raise
    return SeparatedProjects(
        attentional_blink=ab_project,
        oddball_root=project_root.parent / project_id,
    )
