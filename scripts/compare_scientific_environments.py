"""Measure scientific parity for two local source environments using synthetic inputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import shutil
import sys
import zipfile
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from xml.etree import ElementTree

IMAGE_SUFFIXES = {".png", ".jpeg", ".jpg", ".bmp", ".tif", ".tiff"}
LOGGER = logging.getLogger(__name__)


def write_json(path, value):
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )


def read_json(path):
    return json.loads(path.read_bytes())


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def prepare(inputs):
    """Create one shared source and observation fixture in the reference environment."""
    import numpy as np
    from PIL import Image
    from tests.conftest import _build_project, _populate_project_root
    from tests.unit.test_participant_results import results

    inputs.mkdir(parents=True)
    source = inputs / "mixed"
    source.mkdir()

    def pattern(width, height, shift):
        y, x = np.indices((height, width))
        channels = (
            (13 * x + 7 * y + shift) % 255,
            (5 * x + 7 * y + 19 * shift) % 251,
            (x // 4 * 13 + y // 5 * 9 + shift) % 243,
        )
        return Image.fromarray(np.dstack(channels).astype(np.uint8))

    mixed = [
        ("gradient.png", 111, 89),
        ("photo.jpg", 135, 97),
        ("luma.bmp", 102, 78),
        ("plate.tiff", 171, 109),
        ("alpha.png", 74, 135),
        ("portrait.jpeg", 67, 105),
    ]
    for index, (name, width, height) in enumerate(mixed, 1):
        image = pattern(width, height, index)
        options = {}
        if name == "luma.bmp":
            image = image.convert("L")
        elif name == "alpha.png":
            image = image.convert("RGBA")
        elif name == "portrait.jpeg":
            orientation = Image.Exif()
            orientation[274] = 6
            options["exif"] = orientation
        image.save(source / name, **options)

    project = _build_project("scientific-trial", "Scientific trial", condition_count=4)
    project.settings.session.block_count = 2
    for index, pool in enumerate(project.stimulus_sets):
        folder = inputs / pool.set_id
        folder.mkdir()
        for item, suffix in enumerate(("png", "jpg", "png")):
            pattern(256, 256, 13 * index + 7 * item).save(folder / f"sample{item}.{suffix}")
    (inputs / "project.json").write_text(project.model_dump_json(), encoding="utf-8")

    reporting = _build_project("report-trial", "Report trial", condition_count=1)
    reporting.settings.session.block_count = 1
    sample = inputs / "report-input"
    _populate_project_root(sample, reporting)
    plan, summary = results.__wrapped__(reporting, sample)
    (inputs / "report-plan.json").write_text(plan.model_dump_json(), encoding="utf-8")
    (inputs / "report-summary.json").write_text(summary.model_dump_json(), encoding="utf-8")


def image_hashes(path):
    from PIL import Image

    with Image.open(path) as image:
        return {
            "encoded": sha256(path.read_bytes()),
            "pixels": sha256(image.tobytes()),
            "mode": image.mode,
            "size": list(image.size),
        }


def measure_images(inputs, output, project):
    from fpvs_studio.core.enums import StimulusVariant
    from fpvs_studio.preprocessing.equalization import FolderPair, equalize_image_folders
    from fpvs_studio.preprocessing.importer import (
        import_stimulus_source_directory,
        materialize_project_assets,
    )
    from fpvs_studio.preprocessing.normalization import (
        normalize_stimulus_sets,
        optimize_image_folder_for_fpvs,
    )

    root = output / "project"
    root.mkdir()
    inspection, mixed_set = import_stimulus_source_directory(
        source_dir=inputs / "mixed",
        project_root=root,
        set_id="mixed-set",
        set_name="Mixed",
        strict=False,
    )
    normalize_stimulus_sets(project_root=root, stimulus_sets=[mixed_set], target_size=256)
    optimize_image_folder_for_fpvs(
        input_dir=inputs / "mixed",
        output_dir=output / "resized",
        target_size=512,
    )
    equalized = equalize_image_folders(
        [FolderPair(inputs / "mixed", output / "equalized")],
        max_workers=2,
    )
    for index, pool in enumerate(project.stimulus_sets):
        _, project.stimulus_sets[index] = import_stimulus_source_directory(
            source_dir=inputs / pool.set_id,
            project_root=root,
            set_id=pool.set_id,
            set_name=pool.name,
        )
    manifest = materialize_project_assets(
        project, project_root=root, variants=list(StimulusVariant)
    )
    images = {"decode/" + path.name: image_hashes(path) for path in (inputs / "mixed").iterdir()}
    for path in output.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            images[path.relative_to(output).as_posix()] = image_hashes(path)
    return manifest, {
        "images": images,
        "inspection": inspection.model_dump(mode="json"),
        "equalization": {
            "target": equalized.target_standard_deviation,
            "statistics": {
                item.source.name: {"before": asdict(item.before), "after": asdict(item.after)}
                for item in equalized.images
            },
        },
    }


def measure_compilation(root, project, manifest):
    from fpvs_studio.core.compiler import compile_run_spec, compile_session_plan
    from fpvs_studio.core.data_sharing import protocol_fingerprint_with_assets
    from fpvs_studio.core.enums import StimulusVariant

    folder = root.parent / "compiled"
    folder.mkdir()
    hashes, scopes = {}, {}
    for group in ("original", "derivatives"):
        for condition, variant in zip(project.conditions, StimulusVariant, strict=True):
            condition.stimulus_variant = (
                variant if group == "derivatives" else StimulusVariant.ORIGINAL
            )
        fingerprint, assets = protocol_fingerprint_with_assets(project, root)
        scopes[group] = {"protocol": fingerprint, "media": assets}
        for hz in (60.0, 60.02, 120.0):
            for seed in (11, 83):
                inputs = dict(project_root=root, manifest=manifest, random_seed=seed, refresh_hz=hz)
                run = compile_run_spec(
                    project,
                    condition_id=project.conditions[-1].condition_id,
                    run_id="fixed-run",
                    **inputs,
                )
                plan = compile_session_plan(project, session_id="fixed-session", **inputs)
                for kind, model in (("run", run), ("plan", plan)):
                    name = f"{group}-{hz}-{seed}-{kind}"
                    payload = model.model_dump_json().encode()
                    (folder / (name + ".json")).write_bytes(payload)
                    hashes[name] = sha256(payload)
    return {"compiles": hashes, "scopes": scopes}


def export_results(inputs, root):
    from openpyxl import load_workbook

    from fpvs_studio.core.execution import SessionExecutionSummary
    from fpvs_studio.core.session_plan import SessionPlan
    from fpvs_studio.runtime.participant_results import capture_participant_results
    from fpvs_studio.runtime.session_export import (
        append_session_condition_history,
        write_participant_summary,
    )

    plan = SessionPlan.model_validate_json((inputs / "report-plan.json").read_bytes())
    summary = SessionExecutionSummary.model_validate_json(
        (inputs / "report-summary.json").read_bytes()
    )
    participant = capture_participant_results(root, plan, summary)
    history = append_session_condition_history(root, plan, summary, refresh_reports=False)
    xlsx = write_participant_summary(root, require_data=True)
    with history.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        rows = list(reader)
    for row in rows:
        row["logged_at_utc"] = "<time>"
    workbook = load_workbook(xlsx)
    try:
        sheets = {sheet.title: list(sheet.values) for sheet in workbook}
    finally:
        workbook.close()
    members = {}
    with zipfile.ZipFile(xlsx) as archive:
        for name in archive.namelist():
            data = archive.read(name)
            if name == "docProps/core.xml":
                core = ElementTree.fromstring(data)
                for element in core.iter():
                    if element.tag.rsplit("}", 1)[-1] in {"created", "modified"}:
                        element.text = "<time>"
                data = ElementTree.tostring(core)
            members[name] = sha256(data)
    return {
        "participant": sha256(participant.read_bytes()),
        "history": [columns, rows],
        "workbook": {"sheets": sheets, "members": members},
        "raw_csv": sha256(history.read_bytes()),
        "raw_xlsx": sha256(xlsx.read_bytes()),
    }


def library_media(project_root, output):
    from fpvs_studio.core.library_publish import prepare_library_bundle

    receipt = prepare_library_bundle(project_root, output)
    with zipfile.ZipFile(output) as archive:
        inventory = json.loads(archive.read("fpvs_bundle.json"))
    media = {
        item["path"]: item["sha256"]
        for item in inventory["files"]
        if Path(item["path"]).suffix.lower() in IMAGE_SUFFIXES
    }
    return {"media": media, "bundle": receipt.sha256}


def measure(inputs, output):
    from PIL import features

    from fpvs_studio.core.models import ProjectFile
    from fpvs_studio.core.serialization import save_project_file

    output.mkdir(parents=True)
    project = ProjectFile.model_validate_json((inputs / "project.json").read_bytes())
    manifest, data = measure_images(inputs, output, project)
    root = output / "project"
    data.update(measure_compilation(root, project, manifest))
    save_project_file(project, root / "project.json")
    data["library"] = library_media(root, output / "example.fpvsbundle")
    data.update(export_results(inputs, root))
    data["environment"] = {
        "python": sys.version,
        "packages": {pkg: version(pkg) for pkg in ("Pillow", "numpy", "pydantic", "openpyxl")},
        "codecs": {
            name: features.version(name) for name in ("zlib_ng", "libjpeg_turbo", "libtiff")
        },
    }
    write_json(output / "evidence.json", data)


def differences(left, right, prefix=""):
    """Return differing leaf paths, including missing keys, without printing scientific data."""
    if left == right:
        return []
    if isinstance(left, dict) and isinstance(right, dict):
        paths = []
        for key in sorted(left.keys() | right.keys()):
            path = f"{prefix}/{key}"
            if key not in left or key not in right:
                paths.append(path)
            else:
                paths.extend(differences(left[key], right[key], path))
        return paths
    return [prefix]


def compare(reference, candidate):
    old, new = [read_json(path / "evidence.json") for path in (reference, candidate)]
    checks = (
        "images",
        "compiles",
        "inspection",
        "equalization",
        "scopes",
        "participant",
        "history",
        "workbook",
        "raw_csv",
        "raw_xlsx",
    )
    checks = {name: differences(old[name], new[name], name) for name in checks}
    checks["library_media"] = differences(old["library"]["media"], new["library"]["media"])
    LOGGER.info("%s", json.dumps(checks, indent=2))


def check_reuse(reference, candidate, output):
    """Read an existing project in the candidate engine, then review regenerated files in a copy."""
    from fpvs_studio.core.data_sharing import protocol_fingerprint_with_assets
    from fpvs_studio.core.enums import StimulusVariant
    from fpvs_studio.core.serialization import load_project_file
    from fpvs_studio.core.study_versions import ensure_working_setup, prepare_setup_change
    from fpvs_studio.preprocessing.importer import materialize_project_assets

    output.mkdir(parents=True)
    root = output / "project"
    shutil.copytree(reference / "project" / "stimuli", root / "stimuli")
    shutil.copyfile(reference / "project" / "project.json", root / "project.json")
    project = load_project_file(root / "project.json")
    ensure_working_setup(root)
    baseline = read_json(reference / "evidence.json")
    materialize_project_assets(project, project_root=root, variants=list(StimulusVariant))
    fingerprint, media = protocol_fingerprint_with_assets(project, root)
    library = library_media(root, output / "retained.fpvsbundle")
    unchanged_setup = prepare_setup_change(root, project)
    # Replace only files in this new trial copy, mirroring offline regeneration.
    candidate_project = candidate / "project"
    for relative in media:
        path = candidate_project / relative
        if sha256(path.read_bytes()) != media[relative]:
            shutil.copyfile(path, root / relative)
    manifest = Path("stimuli/manifest.json")
    shutil.copyfile(candidate_project / manifest, root / manifest)
    reviewed = prepare_setup_change(root, project)
    result = {
        "baseline_fingerprint_retained": baseline["scopes"]["derivatives"]["protocol"]
        == fingerprint,
        "baseline_selected_media_retained": baseline["scopes"]["derivatives"]["media"] == media,
        "baseline_library_media_retained": baseline["library"]["media"] == library["media"],
        "changes_after_reuse": unchanged_setup.changes,
        "changes_after_regeneration": reviewed.changes,
    }
    write_json(output / "reuse.json", result)
    LOGGER.info("%s", json.dumps(result, indent=2))


def main():
    logging.basicConfig(format="%(message)s", stream=sys.stdout)
    LOGGER.setLevel(logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Source tree to import when measuring another checkout.",
    )
    subcommands = parser.add_subparsers(dest="action", required=True)
    commands = (
        ("prepare", ("inputs",)),
        ("measure", ("inputs", "output")),
        ("compare", ("reference", "candidate")),
        ("reuse", ("reference", "candidate", "output")),
    )
    for name, arguments in commands:
        sub = subcommands.add_parser(name)
        for argument in arguments:
            sub.add_argument(argument, type=Path)
    args = parser.parse_args()
    sys.path[:0] = [str(args.repo / "src"), str(args.repo)]
    if args.action == "prepare":
        prepare(args.inputs)
    elif args.action == "measure":
        measure(args.inputs, args.output)
    elif args.action == "compare":
        compare(args.reference, args.candidate)
    else:
        check_reuse(args.reference, args.candidate, args.output)


if __name__ == "__main__":
    main()
