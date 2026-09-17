"""Create two small, synthetic whole-project Library test bundles for sharing."""

from __future__ import annotations

import argparse
import json
import logging
import tempfile
from pathlib import Path

from fpvs_studio.core.enums import ExperimentCategory, StimulusModality
from fpvs_studio.core.library_publish import prepare_library_bundle
from fpvs_studio.core.models import Condition, StimulusSet
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import save_project_file


def create_test_bundles(output_dir: Path) -> list[dict]:
    """Use native scaffolds and artificial stimuli; never inspect real experiments."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    with tempfile.TemporaryDirectory(prefix=".library-demos-", dir=output_dir) as temporary:
        root = Path(temporary)
        for slug, category, title in (
            ("library-demo-words", ExperimentCategory.FPVS_ODDBALL, "Library Demo - Words"),
            (
                "library-demo-cognitive-load",
                ExperimentCategory.COGNITIVE_LOAD_FPVS,
                "Library Demo - Cognitive Load",
            ),
        ):
            scaffold = create_project(root, title, experiment_category=category)
            project = scaffold.project
            if category == ExperimentCategory.FPVS_ODDBALL:
                project.stimulus_sets = [
                    StimulusSet(
                        set_id="base-words",
                        name="Test base words",
                        modality=StimulusModality.WORD,
                        words=["TABLE", "CHAIR", "DESK"],
                    ),
                    StimulusSet(
                        set_id="oddball-words",
                        name="Test oddball words",
                        modality=StimulusModality.WORD,
                        words=["APPLE", "PEAR", "PLUM"],
                    ),
                ]
                project.conditions = [
                    Condition(
                        condition_id="demo-words",
                        name="Test word stream",
                        trigger_code=1,
                        sequence_count=1,
                        base_stimulus_set_id="base-words",
                        oddball_stimulus_set_id="oddball-words",
                    )
                ]
            project.settings.session.block_count = 1
            project.settings.session.session_seed = 42
            project.settings.fixation_task.enabled = False
            project.settings.fixation_task.accuracy_task_enabled = False
            project.settings.fixation_task.participant_tutorial_enabled = False
            project.settings.display.preferred_refresh_hz = 60.0
            for condition in project.conditions:
                condition.oddball_cycle_repeats_per_sequence = 6
                condition.instructions = (
                    "Library transfer test using artificial stimuli. "
                    "Not a validated research experiment. "
                    + condition.instructions
                )
            save_project_file(project, scaffold.project_root / "project.json")
            bundle_path = output_dir / f"{slug}-1.0.0.fpvsbundle"
            report = prepare_library_bundle(scaffold.project_root, bundle_path)
            payload = report.as_dict()
            payload["item_id"] = slug
            payload["version"] = "1.0.0"
            payload["asset_name"] = bundle_path.name
            payload["summary"] = (
                "Synthetic transfer test with authored words."
                if category == ExperimentCategory.FPVS_ODDBALL
                else "Synthetic test with geometric placeholders and backward-counting tasks."
            )
            with (output_dir / f"{slug}-1.0.0.json").open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
            results.append(payload)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output_dir", type=Path, help="Explicit destination for new test bundles and metadata"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.info(json.dumps(create_test_bundles(args.output_dir), indent=2))


if __name__ == "__main__":
    main()
