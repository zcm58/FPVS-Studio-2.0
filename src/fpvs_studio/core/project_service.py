"""Project scaffold and creation helpers for new FPVS Studio workspaces.
It assembles starter ProjectFile state, folder structure, template defaults, and empty preprocessing manifest records for the authoring flow.
The module owns project initialization on disk, not ongoing compilation, runtime execution, or engine control."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fpvs_studio.core.condition_template_profiles import (
    apply_condition_template_profile_to_settings,
)
from fpvs_studio.core.models import (
    ConditionTemplateProfile,
    ProjectFile,
    ProjectMeta,
    ProjectSettings,
)
from fpvs_studio.core.paths import (
    cache_dir,
    logs_dir,
    project_dir,
    project_json_path,
    runs_dir,
    slugify_project_name,
    stimuli_dir,
    stimulus_derived_root,
    stimulus_manifest_path,
    stimulus_source_root,
    validate_project_id,
)
from fpvs_studio.core.serialization import save_project_file
from fpvs_studio.core.template_library import DEFAULT_TEMPLATE_ID, get_template
from fpvs_studio.preprocessing.manifest import create_empty_manifest


@dataclass(frozen=True)
class ProjectScaffold:
    """Paths and models created when scaffolding a project."""

    project_root: Path
    project: ProjectFile


def build_starter_project(
    project_name: str,
    *,
    template_id: str = DEFAULT_TEMPLATE_ID,
    condition_template_profile: ConditionTemplateProfile | None = None,
) -> ProjectFile:
    """Build a minimal starter project with engine-neutral defaults."""

    template = get_template(template_id)
    project_id = slugify_project_name(project_name)
    validate_project_id(project_id)
    settings = ProjectSettings()
    if condition_template_profile is not None:
        settings = apply_condition_template_profile_to_settings(
            settings,
            condition_template_profile,
        )
    return ProjectFile(
        meta=ProjectMeta(
            project_id=project_id,
            name=project_name,
            template_id=template.template_id,
        ),
        settings=settings,
        stimulus_sets=[],
        conditions=[],
    )


def create_project(
    parent_dir: Path,
    project_name: str,
    *,
    template_id: str = DEFAULT_TEMPLATE_ID,
    condition_template_profile: ConditionTemplateProfile | None = None,
) -> ProjectScaffold:
    """Create the on-disk folder structure and starter files for a new project."""

    validate_project_id(slugify_project_name(project_name))
    project = build_starter_project(
        project_name,
        template_id=template_id,
        condition_template_profile=condition_template_profile,
    )
    target_dir = project_dir(parent_dir, project.meta.project_id)
    for folder in (
        target_dir,
        stimuli_dir(target_dir),
        stimulus_source_root(target_dir),
        stimulus_derived_root(target_dir),
        runs_dir(target_dir),
        cache_dir(target_dir),
        logs_dir(target_dir),
    ):
        folder.mkdir(parents=True, exist_ok=True)

    save_project_file(project, project_json_path(target_dir))
    save_project_file(
        create_empty_manifest(project.meta.project_id),
        stimulus_manifest_path(target_dir),
    )
    return ProjectScaffold(project_root=target_dir, project=project)
