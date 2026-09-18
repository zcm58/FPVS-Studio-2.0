"""Project scaffold and creation helpers for new FPVS Studio workspaces. It assembles
starter ProjectFile state, folder structure, template defaults, and empty preprocessing
manifest records for the authoring flow. The module owns project initialization on disk,
not ongoing compilation, runtime execution, or engine control."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from fpvs_studio.core.attentional_blink_presets import populate_attentional_blink_stream
from fpvs_studio.core.cognitive_load_presets import populate_cognitive_load_fpvs
from fpvs_studio.core.condition_template_profiles import (
    ATTENTIONAL_BLINK_STREAM_PROFILE_ID,
    COGNITIVE_LOAD_PROFILE_ID,
    apply_condition_template_profile_to_settings,
    built_in_condition_template_profiles,
)
from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.migrations import migrate_project_payload
from fpvs_studio.core.models import (
    ConditionTemplateProfile,
    ProjectFile,
    ProjectMeta,
    ProjectPresentationSettings,
    ProjectSettings,
    ProtocolSettings,
    utc_now,
)
from fpvs_studio.core.paths import (
    cache_dir,
    filesystem_path,
    logs_dir,
    project_dir,
    project_json_path,
    runs_dir,
    slugify_project_name,
    stimuli_dir,
    stimulus_generated_variants_root,
    stimulus_original_images_root,
    task_assets_root,
    validate_project_id,
)
from fpvs_studio.core.serialization import atomic_text_write, save_project_file
from fpvs_studio.core.template_library import DEFAULT_TEMPLATE_ID, get_template
from fpvs_studio.preprocessing.cognitive_load_placeholders import (
    create_cognitive_load_placeholder_images,
)
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest


@dataclass(frozen=True)
class ProjectScaffold:
    """Paths and models created when scaffolding a project."""

    project_root: Path
    project: ProjectFile


def rename_project(project_root: Path, name: str) -> ProjectMeta:
    """Atomically change only saved display-name metadata, preserving identity and paths."""
    name = name.strip()
    if not name:
        raise ValueError("Enter a project name.")
    path = filesystem_path(project_json_path(project_root))
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Project file must contain a JSON object.")
    project = migrate_project_payload(payload)
    if project.meta.name == name:
        return project.meta
    meta = project.meta.model_copy(update={"name": name, "updated_at": utc_now()})
    # Renaming is metadata-only, including for legacy projects awaiting separation.
    # Do not rewrite schema versions, conditions, or any other authoring state.
    payload["meta"]["name"] = meta.name
    payload["meta"]["updated_at"] = meta.updated_at.isoformat()
    atomic_text_write(path, json.dumps(payload, indent=2, ensure_ascii=False))
    return meta


def build_starter_project(
    project_name: str,
    *,
    template_id: str = DEFAULT_TEMPLATE_ID,
    condition_template_profile: ConditionTemplateProfile | None = None,
    experiment_category: ExperimentCategory = ExperimentCategory.FPVS_ODDBALL,
) -> ProjectFile:
    """Build a minimal starter project with engine-neutral defaults."""

    experiment_category = ExperimentCategory(experiment_category)
    if experiment_category == ExperimentCategory.FPVS:
        raise ValueError(
            "Standard FPVS is coming soon. Choose FPVS Oddball Paradigm or Attentional-Blink."
        )
    if (
        experiment_category in {
            ExperimentCategory.ATTENTIONAL_BLINK, ExperimentCategory.COGNITIVE_LOAD_FPVS,
        }
        and condition_template_profile is None
    ):
        condition_template_profile = next(
            profile for profile in built_in_condition_template_profiles()
            if profile.profile_id == (
                ATTENTIONAL_BLINK_STREAM_PROFILE_ID
                if experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
                else COGNITIVE_LOAD_PROFILE_ID
            )
        )
    template = get_template(template_id)
    project_id = slugify_project_name(project_name)
    validate_project_id(project_id)
    settings = ProjectSettings(
        presentation=ProjectPresentationSettings(pre_stream_fixation_seconds=2.0),
        protocol=ProtocolSettings(
            base_hz=(
                10.0 if experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
                else template.base_hz
            ),
            oddball_every_n=(
                20 if experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
                else template.oddball_every_n
            ),
        ),
    )
    if condition_template_profile is not None:
        settings = apply_condition_template_profile_to_settings(
            settings,
            condition_template_profile,
            experiment_category=experiment_category,
        )
    project = ProjectFile(
        experiment_category=experiment_category,
        meta=ProjectMeta(
            project_id=project_id,
            name=project_name,
            template_id=template.template_id,
        ),
        settings=settings,
        stimulus_sets=[],
        conditions=[],
    )
    if (
        experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
        and condition_template_profile is not None
        and condition_template_profile.defaults.attentional_blink_layout == "letter_stream"
    ):
        return populate_attentional_blink_stream(project)
    if experiment_category == ExperimentCategory.COGNITIVE_LOAD_FPVS:
        return populate_cognitive_load_fpvs(project)
    return project


def create_project(
    parent_dir: Path,
    project_name: str,
    *,
    template_id: str = DEFAULT_TEMPLATE_ID,
    condition_template_profile: ConditionTemplateProfile | None = None,
    experiment_category: ExperimentCategory = ExperimentCategory.FPVS_ODDBALL,
) -> ProjectScaffold:
    """Create the on-disk folder structure and starter files for a new project."""

    validate_project_id(slugify_project_name(project_name))
    project = build_starter_project(
        project_name,
        template_id=template_id,
        condition_template_profile=condition_template_profile,
        experiment_category=experiment_category,
    )
    target_dir = project_dir(parent_dir, project.meta.project_id)
    if (experiment_category == ExperimentCategory.COGNITIVE_LOAD_FPVS and target_dir.exists()):
        raise FileExistsError(f"Project folder already exists: {target_dir}")
    for folder in (
        target_dir,
        stimuli_dir(target_dir),
        stimulus_original_images_root(target_dir),
        stimulus_generated_variants_root(target_dir),
        task_assets_root(target_dir),
        runs_dir(target_dir),
        cache_dir(target_dir),
        logs_dir(target_dir),
    ):
        folder.mkdir(parents=True, exist_ok=True)

    if experiment_category == ExperimentCategory.COGNITIVE_LOAD_FPVS:
        create_cognitive_load_placeholder_images(project, target_dir)
    else:
        write_stimulus_manifest(target_dir, create_empty_manifest(project.meta.project_id))
    save_project_file(project, project_json_path(target_dir))
    return ProjectScaffold(project_root=target_dir, project=project)
