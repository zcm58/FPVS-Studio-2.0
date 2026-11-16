"""Prepare the first public OpenFPVS Library project from original silhouettes."""

from __future__ import annotations

import argparse
import json
import logging
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from fpvs_studio.core.enums import DutyCycleMode, StimulusVariant
from fpvs_studio.core.library_publish import prepare_library_bundle
from fpvs_studio.core.models import Condition
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import save_project_file
from fpvs_studio.preprocessing.importer import (
    import_stimulus_source_directory,
    materialize_project_assets,
)

DEMO_ID = "color-oddball-demo"
DEMO_VERSION = "1.0.0"
DEMO_TITLE = "Color Oddball Demo"
BACKGROUND = (128, 128, 128)
# These foregrounds have approximately the same nominal sRGB relative luminance.
PALETTE = {"gray": (75, 75, 75), "red": (137, 41, 48), "green": (34, 85, 56)}


def make_silhouettes() -> dict[str, Image.Image]:
    """Draw original icons on a common 128 px grid, then antialias to 256 px."""
    masks: dict[str, Image.Image] = {}

    def draw(name: str) -> ImageDraw.ImageDraw:
        mask = Image.new("L", (128, 128))
        masks[name] = mask
        return ImageDraw.Draw(mask)

    d = draw("apple")
    d.ellipse((33, 47, 73, 97), fill=255)
    d.ellipse((56, 47, 95, 97), fill=255)
    d.line((63, 50, 67, 34), fill=255, width=6)
    d.ellipse((68, 30, 86, 40), fill=255)

    d = draw("bottle")
    d.rounded_rectangle((47, 44, 81, 100), radius=7, fill=255)
    d.rectangle((55, 31, 73, 51), fill=255)
    d.rectangle((54, 28, 74, 34), fill=255)

    d = draw("fish")
    d.ellipse((28, 43, 86, 85), fill=255)
    d.polygon([(70, 64), (99, 43), (99, 85)], fill=255)
    d.ellipse((39, 56, 45, 62), fill=0)

    d = draw("headphones")
    d.arc((32, 34, 96, 94), 180, 360, fill=255, width=8)
    d.rounded_rectangle((31, 60, 46, 89), radius=5, fill=255)
    d.rounded_rectangle((82, 60, 97, 89), radius=5, fill=255)

    d = draw("house")
    d.polygon([(29, 62), (64, 30), (99, 62)], fill=255)
    d.rectangle((39, 60, 89, 96), fill=255)
    d.rectangle((57, 74, 71, 97), fill=0)

    d = draw("key")
    d.ellipse((27, 45, 65, 83), fill=255)
    d.ellipse((37, 55, 55, 73), fill=0)
    d.rectangle((60, 60, 100, 68), fill=255)
    d.rectangle((77, 66, 84, 78), fill=255)
    d.rectangle((93, 66, 100, 76), fill=255)

    d = draw("lamp")
    d.polygon([(49, 30), (79, 30), (92, 64), (36, 64)], fill=255)
    d.rectangle((60, 63, 68, 91), fill=255)
    d.ellipse((44, 87, 84, 97), fill=255)

    d = draw("mug")
    d.ellipse((73, 42, 99, 75), outline=255, width=7)
    d.rounded_rectangle((31, 38, 81, 86), radius=7, fill=255)
    d.rounded_rectangle((26, 91, 91, 96), radius=2, fill=255)

    d = draw("pencil")
    d.polygon([(32, 81), (33, 95), (47, 94), (94, 47), (81, 34)], fill=255)
    d.line((74, 41, 87, 54), fill=0, width=3)

    d = draw("spoon")
    d.ellipse((46, 29, 82, 66), fill=255)
    d.rounded_rectangle((59, 60, 69, 100), radius=5, fill=255)

    d = draw("tree")
    d.polygon([(64, 24), (89, 60), (77, 58), (96, 83), (32, 83), (51, 58), (39, 60)], fill=255)
    d.rectangle((59, 81, 69, 101), fill=255)

    d = draw("umbrella")
    d.pieslice((29, 33, 99, 95), 180, 360, fill=255)
    d.line((64, 62, 64, 89), fill=255, width=5)
    d.arc((62, 78, 80, 99), 0, 180, fill=255, width=5)

    return {name: mask.resize((256, 256), Image.Resampling.LANCZOS) for name, mask in masks.items()}


def prepare_demo(output_dir: Path) -> Path:
    """Author, validate, and export a portable project with no machine-specific data."""
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = output_dir / f"{DEMO_ID}-{DEMO_VERSION}.fpvsbundle"
    metadata = bundle.with_suffix(".json")
    if bundle.exists() or metadata.exists():
        raise FileExistsError("Choose an empty output directory for the demo release.")

    with tempfile.TemporaryDirectory(prefix="fpvs-color-demo-") as temporary:
        temporary_root = Path(temporary)
        scaffold = create_project(temporary_root, DEMO_TITLE)
        project = scaffold.project
        masks = make_silhouettes()
        background = Image.new("RGB", (256, 256), BACKGROUND)
        for color, rgb in PALETTE.items():
            folder = temporary_root / color
            folder.mkdir()
            foreground = Image.new("RGB", (256, 256), rgb)
            for name, mask in masks.items():
                Image.composite(foreground, background, mask).save(folder / f"{name}.png")
            _, stimulus_set = import_stimulus_source_directory(
                source_dir=folder, project_root=scaffold.project_root,
                set_id=color, set_name=f"{color.title()} objects",
            )
            project.stimulus_sets.append(stimulus_set)

        project.settings.supported_variants = [StimulusVariant.ORIGINAL]
        project.settings.display.preferred_refresh_hz = 60
        project.settings.display.background_color = "#808080"
        project.settings.protocol.base_hz = 6
        project.settings.protocol.oddball_every_n = 5
        project.settings.session.block_count = 3
        project.settings.session.condition_ordering = "randomized_blocks"
        project.settings.condition_defaults.target_repeats_per_image = 16
        project.settings.fixation_task.changes_per_sequence = 4
        project.settings.fixation_task.base_color = "#FFFFFF"
        project.settings.fixation_task.target_color = "#0072B2"
        project.conditions = [
            Condition(
                condition_id=f"{color}-oddballs", name=f"{color.title()} oddballs",
                instructions=(
                    "Keep your eyes on the fixation cross. Press Space when it turns blue."
                ),
                base_stimulus_set_id="gray", oddball_stimulus_set_id=color,
                sequence_count=1, oddball_cycle_repeats_per_sequence=48,
                duty_cycle_mode=DutyCycleMode.SINUSOIDAL,
                order_index=index - 1, trigger_code=index,
            )
            for index, color in enumerate(("red", "green"), start=1)
        ]
        materialize_project_assets(project, project_root=scaffold.project_root)
        save_project_file(project, scaffold.project_root / "project.json")
        report = prepare_library_bundle(
            scaffold.project_root, bundle, minimum_studio_version="3.0.1",
        ).as_dict()

    report.update(
        item_id=DEMO_ID, version=DEMO_VERSION, asset_name=bundle.name,
        summary=("Try two color oddball conditions with original object silhouettes. "
                 "6 Hz base, 1.2 Hz oddball, three 40-second runs per condition, "
                 "and a fixation cross task."),
    )
    with metadata.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    return bundle


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path, help="Destination for the new bundle and metadata")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.info("Prepared %s", prepare_demo(parser.parse_args().output_dir))
