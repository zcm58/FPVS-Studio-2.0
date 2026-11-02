"""Synthetic cross-OS bundle handoff CLI; never opens Qt, PsychoPy or hardware.

Each command creates its own uniquely named working directory. It never removes or
replaces a caller's project. CI exchanges only the three files in the output folder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image

from fpvs_studio import __version__
from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.enums import ProjectSchemaVersion, StimulusModality, StimulusVariant
from fpvs_studio.core.models import (
    Condition,
    FixationTaskSettings,
    ImageResolution,
    ProjectFile,
    ProjectMeta,
    ProjectRecordingSettings,
    ProjectSettings,
    SessionSettings,
    StimulusSet,
)
from fpvs_studio.core.paths import filesystem_path, resolve_project_relative_path
from fpvs_studio.core.project_bundle import (
    ProjectBundleManifest,
    export_project_bundle,
    import_project_bundle,
)
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.session_ordering import randomized_condition_blocks
from fpvs_studio.core.task_models import (
    TaskBinding,
    TaskDisplayItem,
    TaskItemModality,
    TaskModule,
    TaskStep,
    TaskStepKind,
)
from fpvs_studio.preprocessing.importer import materialize_project_assets
from fpvs_studio.preprocessing.manifest import read_stimulus_manifest

_ARTIFACT_NAMES = ("project.fpvsbundle", "baseline.json", "evidence.json")
_REFRESH_HZ = 60.0


def _absolute_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("Use an absolute task-owned directory or file path.")
    return path.resolve()


def _new_work_directory(root: Path) -> Path:
    root = filesystem_path(root.resolve())
    root.mkdir(parents=True, exist_ok=True)
    work = root / f"fpvs-bundle-handoff-{uuid4().hex}"
    work.relative_to(root)
    work.mkdir(exist_ok=False)
    return work


def _prepare_output(root: Path) -> Path:
    root = filesystem_path(root.resolve())
    if any((root / name).exists() for name in _ARTIFACT_NAMES):
        raise ValueError(
            "Handoff output already contains artifacts; choose a new output directory."
        )
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_json(path: Path, payload: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _fixture(root: Path) -> ProjectFile:
    root.mkdir()
    counts = {"images": 3, "words": 2, "grayscale": 2}
    order = [identity for block in randomized_condition_blocks(counts, seed=101)
             for identity in block]
    sets = []
    for role in ("base", "oddball"):
        source_dir = f"stimuli/original-images/{role}-caf\u00e9"
        directory = root / source_dir
        directory.mkdir(parents=True)
        for index, name in enumerate(("image one.png", "\u753b\u50cf.png", "caf\u00e9.png")):
            Image.new("RGB", (48, 32), (40 + index * 20, 70, 90)).save(directory / name)
        sets.append(StimulusSet(
            set_id=role, name=role.title(), source_dir=source_dir,
            resolution=ImageResolution(width_px=48, height_px=32), image_count=3,
            available_variants=[StimulusVariant.ORIGINAL, StimulusVariant.GRAYSCALE],
        ))
    for role, words in (
        ("base", ["caf\u00e9", "cafe\u0301", "Stra\u00dfe", "\u753b\u50cf"]),
        ("oddball", ["tool", "na\u00efve", "word with spaces"]),
    ):
        sets.append(StimulusSet(
            set_id=f"{role}-words", name=f"{role.title()} words",
            modality=StimulusModality.WORD, words=words,
        ))
    task_path = "stimuli/task-assets/handoff-task/caf\u00e9 task.png"
    task_file = root / task_path
    task_file.parent.mkdir(parents=True)
    Image.new("RGB", (48, 32), "blue").save(task_file)
    task = TaskModule(
        task_id="handoff-task", name="Portable task",
        steps=[TaskStep(
            step_id="study", kind=TaskStepKind.STUDY, continue_key="space",
            items=[TaskDisplayItem(
                item_id="picture", modality=TaskItemModality.IMAGE, image_path=task_path,
            )],
        )],
    )
    conditions = []
    for index, (identity, count) in enumerate(counts.items()):
        is_words = identity == "words"
        conditions.append(Condition(
            condition_id=identity, name=f"Handoff {identity}",
            instructions="Synthetic portability check: caf\u00e9 / cafe\u0301 / \u753b\u50cf.",
            base_stimulus_set_id="base-words" if is_words else "base",
            oddball_stimulus_set_id="oddball-words" if is_words else "oddball",
            stimulus_variant=(StimulusVariant.GRAYSCALE if identity == "grayscale"
                              else StimulusVariant.ORIGINAL),
            sequence_count=1, stream_duration_seconds=10.0,
            presentation_count=count, trigger_code=index + 1, order_index=index,
            pre_task_bindings=[TaskBinding(task_id=task.task_id)],
        ))
    project = ProjectFile(
        schema_version=ProjectSchemaVersion.V1_17,
        meta=ProjectMeta(
            project_id=f"bundle-handoff-{uuid4().hex[:12]}", name="Synthetic bundle handoff",
            template_id="fpvs_6hz_every5_v1",
        ),
        settings=ProjectSettings(
            session=SessionSettings(
                condition_ordering="randomized_blocks", saved_condition_order=order,
                randomization_mode="fixed", session_seed=101, stimulus_seed=202, fixation_seed=303,
            ),
            fixation_task=FixationTaskSettings(
                changes_per_sequence=2, target_duration_ms=250, min_gap_ms=1000, max_gap_ms=2000,
                accuracy_task_enabled=False, participant_tutorial_enabled=False,
            ),
            recording=ProjectRecordingSettings(
                recording_backend="brainproducts_triggerbox", brainproducts_serial_port="COM47",
            ),
            supported_variants=[StimulusVariant.ORIGINAL, StimulusVariant.GRAYSCALE],
        ),
        stimulus_sets=sets, conditions=conditions, task_modules=[task],
    )
    project.settings.display.preferred_refresh_hz = _REFRESH_HZ
    materialize_project_assets(project, project_root=root)
    save_project_file(project, root / "project.json")
    return load_project_file(root / "project.json")


def _snapshot(root: Path, manifest: ProjectBundleManifest) -> dict[str, Any]:
    project = load_project_file(root / "project.json")
    semantic = project.model_dump(mode="json", exclude_none=True)
    plan = compile_session_plan(
        project, refresh_hz=_REFRESH_HZ, project_root=root,
        manifest=read_stimulus_manifest(root), session_id="synthetic-bundle-handoff",
    )
    if project.model_dump(mode="json", exclude_none=True) != semantic:
        raise ValueError("Compiling the handoff unexpectedly changed the editable project.")
    assets = {
        record.path: hashlib.sha256(
            resolve_project_relative_path(root, record.path).read_bytes(),
        ).hexdigest()
        for record in manifest.files if record.path.startswith("stimuli/")
    }
    if not any(entry.run_spec.fixation_events for entry in plan.ordered_entries()):
        raise ValueError("The handoff fixture must contain realized fixation schedules.")
    return {
        "fixture_version": 1, "refresh_hz": _REFRESH_HZ, "project": semantic,
        "assets": assets, "compiled_plan": plan.model_dump(mode="json", exclude_none=True),
    }


def _assert_matches(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    for key in ("fixture_version", "refresh_hz", "project", "assets", "compiled_plan"):
        if actual.get(key) != expected.get(key):
            raise ValueError(f"Cross-OS bundle handoff mismatch: {key}.")


def _evidence(operation: str, *, relocated: bool, baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "operation": operation, "result": "matched", "source_relocated": relocated,
        "system": platform.system(), "release": platform.release(), "cpu": platform.machine(),
        "python": platform.python_version(), "studio_version": __version__,
        "refresh_hz": _REFRESH_HZ, "asset_count": len(baseline["assets"]),
        "total_runs": baseline["compiled_plan"]["total_runs"],
        "checks": ["semantic_project", "asset_sha256", "compiled_plan_and_fixation_schedules"],
        "physical_gui_display_or_hardware_qualified": False,
    }


def create_handoff(work_root: Path, output_root: Path) -> None:
    output = _prepare_output(output_root)
    work = _new_work_directory(work_root)
    source = work / "source-project"
    _fixture(source)
    manifest = export_project_bundle(source, output / "project.fpvsbundle")
    baseline = _snapshot(source, manifest)
    moved_source = work / "moved-export-source"
    # Both move targets are checked inside this command's newly created namespace.
    source.relative_to(work)
    moved_source.relative_to(work)
    source.rename(moved_source)
    if source.exists():
        raise ValueError("Synthetic export source was not relocated.")
    imported = import_project_bundle(output / "project.fpvsbundle", work / "receiver")
    _assert_matches(_snapshot(imported.project_root, manifest), baseline)
    _write_json(output / "baseline.json", baseline)
    _write_json(output / "evidence.json", _evidence("create", relocated=True, baseline=baseline))


def roundtrip_handoff(input_bundle: Path, baseline_path: Path, work_root: Path,
                      output_root: Path) -> None:
    baseline_bytes = baseline_path.read_bytes()
    baseline = json.loads(baseline_bytes)
    output = _prepare_output(output_root)
    work = _new_work_directory(work_root)
    imported = import_project_bundle(input_bundle, work / "receiver")
    manifest = export_project_bundle(imported.project_root, output / "project.fpvsbundle")
    _assert_matches(_snapshot(imported.project_root, manifest), baseline)
    with (output / "baseline.json").open("xb") as handle:
        handle.write(baseline_bytes)
    _write_json(
        output / "evidence.json", _evidence("roundtrip", relocated=False, baseline=baseline),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("create", "roundtrip"):
        command = commands.add_parser(name)
        command.add_argument("--work-root", type=_absolute_path, required=True)
        command.add_argument("--output", type=_absolute_path, required=True)
        if name == "roundtrip":
            command.add_argument("--input", type=_absolute_path, required=True)
            command.add_argument("--baseline", type=_absolute_path, required=True)
    args = parser.parse_args(argv)
    if args.operation == "create":
        create_handoff(args.work_root, args.output)
    else:
        roundtrip_handoff(args.input, args.baseline, args.work_root, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
