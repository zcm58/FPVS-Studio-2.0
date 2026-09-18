"""Clean whole-project publishing preserves authored dependencies and source data."""

from __future__ import annotations

import hashlib
import json
import zipfile
from threading import Event

import pytest

import fpvs_studio.core.library_publish as publisher
from fpvs_studio.core.enums import StimulusVariant
from fpvs_studio.core.library_publish import prepare_library_bundle
from fpvs_studio.core.models import StimulusSet
from fpvs_studio.core.project_bundle import (
    ProjectBundleCancelled,
    ProjectBundleError,
    export_project_bundle,
    import_project_bundle,
)
from fpvs_studio.core.serialization import save_project_file
from fpvs_studio.core.task_models import (
    TaskBinding,
    TaskDisplayItem,
    TaskItemModality,
    TaskModule,
    TaskStep,
    TaskStepKind,
)
from fpvs_studio.preprocessing.inspection import inspect_source_directory
from fpvs_studio.preprocessing.manifest import (
    create_empty_manifest,
    inspection_summary_to_manifest_set,
    write_stimulus_manifest,
)
from fpvs_studio.preprocessing.models import DerivedImageRecord
from fpvs_studio.runtime.launcher import LaunchSettings, _validate_launch_settings


def _ready_project(project_root, project):
    manifest = create_empty_manifest(project.meta.project_id)
    for stimulus_set in project.stimulus_sets:
        summary = inspect_source_directory(
            project_root / stimulus_set.source_dir, relative_prefix=stimulus_set.source_dir
        )
        manifest.sets.append(
            inspection_summary_to_manifest_set(set_id=stimulus_set.set_id, summary=summary)
        )
    save_project_file(project, project_root / "project.json")
    write_stimulus_manifest(project_root, manifest)
    return manifest


def _snapshot(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_publishing_copies_only_declared_content_and_sanitizes_project(
    tmp_path,
    multi_condition_project,
    multi_condition_project_root,
):
    project = multi_condition_project
    source = multi_condition_project_root
    project.manual_removed_electrodes = {"001": ["A1", "A2"]}
    project.settings.display.monitor_name = "research workstation"
    project.settings.triggers.serial_port = "COM91"
    project.settings.condition_profile_id = "local-profile"
    manifest = _ready_project(source, project)
    derivative_path = "stimuli/generated-variants/base-set/grayscale-variants/test.png"
    derivative = source / derivative_path
    derivative.parent.mkdir(parents=True)
    derivative.write_bytes((source / manifest.sets[0].assets[0].source.relative_path).read_bytes())
    manifest.sets[0].assets[0].derivatives = [
        DerivedImageRecord(
            variant=StimulusVariant.GRAYSCALE,
            relative_path=derivative_path,
            resolution=manifest.sets[0].assets[0].source.resolution,
        )
    ]
    project.stimulus_sets.append(
        StimulusSet(
            set_id="unused",
            name="Unrelated set",
            source_dir="stimuli/original-images/unused",
            image_count=1,
        )
    )
    task_path = "stimuli/task-assets/review/test.png"
    (source / task_path).parent.mkdir(parents=True)
    (source / task_path).write_bytes(derivative.read_bytes())
    project.task_modules = [
        TaskModule(
            task_id="review",
            name="Review",
            steps=[
                TaskStep(
                    step_id="show",
                    kind=TaskStepKind.STUDY,
                    continue_key="space",
                    items=[
                        TaskDisplayItem(
                            item_id="test", modality=TaskItemModality.IMAGE, image_path=task_path
                        )
                    ],
                )
            ],
        )
    ]
    project.conditions[0].pre_task_bindings = [TaskBinding(task_id="review")]
    for relative in (
        "runs/participant.csv",
        "logs/participant.csv",
        "cache/auth.json",
        "stimuli/original-images/unused/private.png",
        "stimuli/task-assets/review/unused.png",
        "stimuli/original-images/base-set/untracked.png",
        "stimuli/credentials.json",
    ):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"must not publish")
    save_project_file(project, source / "project.json")
    write_stimulus_manifest(source, manifest)
    before = _snapshot(source)
    bundle_path = tmp_path / "clean.fpvsbundle"

    report = prepare_library_bundle(source, bundle_path)

    assert _snapshot(source) == before
    assert report.condition_count == len(project.conditions)
    assert report.size_bytes == bundle_path.stat().st_size
    assert report.sha256 == hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    assert derivative_path in report.included_paths and task_path in report.included_paths
    assert "stimuli/original-images/base-set/untracked.png" in report.excluded_paths
    with zipfile.ZipFile(bundle_path) as archive:
        assert set(archive.namelist()) == {"fpvs_bundle.json", *report.included_paths}
    imported = import_project_bundle(bundle_path, tmp_path / "receiver")
    assert imported.project.manual_removed_electrodes == {}
    assert imported.project.settings.display.monitor_name is None
    assert imported.project.settings.triggers.serial_port == "COM3"
    assert imported.project.settings.condition_profile_id is None
    assert imported.project.conditions == project.conditions
    assert imported.project.task_modules == project.task_modules
    assert all(item.set_id != "unused" for item in imported.project.stimulus_sets)
    assert (imported.project_root / derivative_path).is_file()


def test_publisher_dry_run_validates_without_writing_bundle(
    tmp_path, sample_project, sample_project_root
):
    _ready_project(sample_project_root, sample_project)
    before = _snapshot(sample_project_root)
    destination = tmp_path / "dry-run.fpvsbundle"
    report = prepare_library_bundle(sample_project_root, destination, dry_run=True)
    assert report.dry_run and report.size_bytes > 0 and len(report.sha256) == 64
    assert not destination.exists()
    assert not list(tmp_path.glob(".library-publish-*"))
    assert _snapshot(sample_project_root) == before


def test_publisher_keeps_condition_variant_resolved_without_manifest(
    tmp_path, sample_project, sample_project_root,
):
    sample_project.conditions[0].stimulus_variant = StimulusVariant.GRAYSCALE
    for stimulus_set in sample_project.stimulus_sets:
        folder = sample_project_root / "stimuli/generated-variants" / stimulus_set.set_id
        folder = folder / "grayscale-variants"
        folder.mkdir(parents=True)
        for source in (sample_project_root / stimulus_set.source_dir).glob("*.png"):
            (folder / source.name).write_bytes(source.read_bytes())
    save_project_file(sample_project, sample_project_root / "project.json")
    write_stimulus_manifest(
        sample_project_root, create_empty_manifest(sample_project.meta.project_id),
    )
    report = prepare_library_bundle(sample_project_root, tmp_path / "derived.fpvsbundle")
    assert len([path for path in report.included_paths if "grayscale-variants" in path]) == 6


def test_publisher_sanitizes_existing_bundle_and_keeps_ordinary_export_behavior(
    tmp_path,
    sample_project,
    sample_project_root,
):
    sample_project.manual_removed_electrodes = {"007": ["B1"]}
    _ready_project(sample_project_root, sample_project)
    ordinary = tmp_path / "ordinary.fpvsbundle"
    export_project_bundle(sample_project_root, ordinary)
    before = ordinary.read_bytes()
    normal = import_project_bundle(ordinary, tmp_path / "ordinary-import")
    assert normal.project.manual_removed_electrodes == sample_project.manual_removed_electrodes
    clean = tmp_path / "clean.fpvsbundle"
    prepare_library_bundle(ordinary, clean)
    assert ordinary.read_bytes() == before
    assert (
        import_project_bundle(clean, tmp_path / "clean-import").project.manual_removed_electrodes
        == {}
    )


@pytest.mark.parametrize("serial_port", [None, "", "COM91"])
@pytest.mark.parametrize("source_kind", ["project", "bundle"])
def test_library_bundle_uses_com3_and_preserves_source_port(
    tmp_path, sample_project, sample_project_root, serial_port, source_kind
):
    sample_project.settings.triggers.serial_port = serial_port
    _ready_project(sample_project_root, sample_project)
    before = _snapshot(sample_project_root)
    source = sample_project_root
    if source_kind == "bundle":
        source = tmp_path / "ordinary.fpvsbundle"
        export_project_bundle(sample_project_root, source)
        source_bytes = source.read_bytes()
        ordinary = import_project_bundle(source, tmp_path / "ordinary-import")
        # Existing serialization omits None and restores the model's COM3 default.
        assert ordinary.project.settings.triggers.serial_port == (
            "COM3" if serial_port is None else serial_port
        )

    clean = tmp_path / "clean.fpvsbundle"
    report = prepare_library_bundle(source, clean)
    with zipfile.ZipFile(clean) as archive:
        bundled_project = json.loads(archive.read("project.json"))
    assert bundled_project["settings"]["triggers"]["serial_port"] == "COM3"
    imported = import_project_bundle(clean, tmp_path / "clean-import")

    assert imported.project.settings.triggers.serial_port == "COM3"
    assert "settings.triggers.serial_port" in report.sanitized_fields
    assert _snapshot(sample_project_root) == before
    assert sample_project.settings.triggers.serial_port == serial_port
    if source_kind == "bundle":
        assert source.read_bytes() == source_bytes
    # Both test-mode and recording launch validation accept the imported port.
    for serial_enabled in (False, True):
        _validate_launch_settings(
            LaunchSettings(
                serial_enabled=serial_enabled,
                experiment_test_mode=not serial_enabled,
                serial_port=imported.project.settings.triggers.serial_port,
            )
        )


def test_publisher_enforces_github_asset_limit(
    tmp_path, sample_project, sample_project_root, monkeypatch
):
    _ready_project(sample_project_root, sample_project)
    monkeypatch.setattr(publisher, "GITHUB_RELEASE_ASSET_LIMIT", 1)
    destination = tmp_path / "large.fpvsbundle"
    with pytest.raises(ProjectBundleError, match="smaller than 2 GiB"):
        prepare_library_bundle(sample_project_root, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob(".library-publish-*"))


def test_publisher_cancel_during_copy_preserves_source_and_cleans_staging(
    tmp_path,
    sample_project,
    sample_project_root,
    monkeypatch,
):
    _ready_project(sample_project_root, sample_project)
    before = _snapshot(sample_project_root)
    cancel_event = Event()
    original_inventory = publisher._clean_inventory

    def cancel_after_inventory(*args):
        result = original_inventory(*args)
        cancel_event.set()
        return result

    monkeypatch.setattr(publisher, "_clean_inventory", cancel_after_inventory)
    destination = tmp_path / "cancelled.fpvsbundle"
    with pytest.raises(ProjectBundleCancelled):
        prepare_library_bundle(sample_project_root, destination, cancel_event=cancel_event)
    assert not destination.exists()
    assert not list(tmp_path.glob(".library-publish-*"))
    assert _snapshot(sample_project_root) == before


def test_publisher_never_overwrites_output_or_writes_inside_source(
    tmp_path, sample_project, sample_project_root
):
    _ready_project(sample_project_root, sample_project)
    destination = tmp_path / "existing.fpvsbundle"
    destination.write_bytes(b"keep")
    with pytest.raises(ProjectBundleError, match="already exists"):
        prepare_library_bundle(sample_project_root, destination)
    assert destination.read_bytes() == b"keep"
    with pytest.raises(ProjectBundleError, match="outside the source"):
        prepare_library_bundle(sample_project_root, sample_project_root / "output.fpvsbundle")


@pytest.mark.parametrize(
    "parameters", [{"source_path": "C:/private/photo.png"}, {"api_key": "secret"}]
)
def test_publisher_refuses_private_provenance(
    tmp_path, sample_project, sample_project_root, parameters
):
    manifest = _ready_project(sample_project_root, sample_project)
    asset = manifest.sets[0].assets[0]
    asset.derivatives = [
        DerivedImageRecord(
            variant=StimulusVariant.GRAYSCALE,
            relative_path=asset.source.relative_path,
            resolution=asset.source.resolution,
            parameters=parameters,
        )
    ]
    write_stimulus_manifest(sample_project_root, manifest)
    with pytest.raises(ProjectBundleError, match="provenance"):
        prepare_library_bundle(sample_project_root, tmp_path / "private.fpvsbundle")
