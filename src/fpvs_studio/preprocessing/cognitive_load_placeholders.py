"""Deterministic geometric starter images and their ordinary manifest provenance."""

from pathlib import Path

from PIL import Image, ImageDraw

from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.paths import filesystem_path, resolve_project_relative_path
from fpvs_studio.preprocessing.inspection import inspect_source_directory
from fpvs_studio.preprocessing.manifest import (
    create_empty_manifest,
    inspection_summary_to_manifest_set,
    upsert_manifest_set,
    write_stimulus_manifest,
)


def create_cognitive_load_placeholder_images(project: ProjectFile, project_root: Path) -> None:
    """Write clearly artificial images for a new scaffold; never replace existing assets."""
    manifest = create_empty_manifest(project.meta.project_id)
    for stimulus_set in project.stimulus_sets:
        if stimulus_set.source_dir is None:
            raise ValueError("Cognitive Load FPVS placeholders require image sources.")
        folder = filesystem_path(
            resolve_project_relative_path(project_root, stimulus_set.source_dir)
        )
        folder.mkdir(parents=True, exist_ok=False)
        image = Image.new("RGB", (512, 512), "#808080")
        draw = ImageDraw.Draw(image)
        bounds = (112, 112, 400, 400)
        color = "#EEEEEE" if stimulus_set.set_id.endswith("base") else "#303030"
        pair_index = int(stimulus_set.set_id.split("-")[1])
        if pair_index == 1:
            draw.ellipse(bounds, fill=color)
        elif pair_index == 2:
            draw.rectangle(bounds, fill=color)
        else:
            draw.polygon([(256, 100), (420, 400), (92, 400)], fill=color)
        image.save(folder / "placeholder.png")
        summary = inspect_source_directory(folder, relative_prefix=stimulus_set.source_dir)
        manifest = upsert_manifest_set(manifest, inspection_summary_to_manifest_set(
            set_id=stimulus_set.set_id, summary=summary,
        ))
    write_stimulus_manifest(project_root, manifest)
