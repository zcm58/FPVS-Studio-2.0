"""Portable project bundle import/export tests."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import zipfile
from contextlib import contextmanager
from pathlib import Path
from threading import Event

import pytest

import fpvs_studio.core.project_bundle as project_bundle_module
from fpvs_studio.core.library_origin import LibraryProjectOrigin
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.paths import app_data_dir
from fpvs_studio.core.project_bundle import (
    BUNDLE_MANIFEST_FILENAME,
    IMPORT_STAGING_DIRNAME,
    PROJECT_BUNDLE_SUFFIX,
    ProjectBundleCancelled,
    ProjectBundleError,
    export_project_bundle,
    import_project_bundle,
    project_bundle_filename,
    read_project_bundle_manifest,
    validate_project_bundle,
)
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.task_models import (
    TaskBinding,
    TaskDisplayItem,
    TaskFontFamily,
    TaskItemModality,
    TaskModule,
    TaskStep,
    TaskStepKind,
)
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest
from fpvs_studio.preprocessing.models import StimulusManifest


def _save_bundle_ready_project(project_root: Path, project) -> None:
    save_project_file(project, project_root / "project.json")
    write_stimulus_manifest(project_root, create_empty_manifest(project.meta.project_id))


def _replace_bundle_payloads(bundle_path, replacements, *, special_mode=None):
    """Keep all integrity metadata valid while exercising hostile authored content."""
    with zipfile.ZipFile(bundle_path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(files.pop(BUNDLE_MANIFEST_FILENAME))
    files.update(replacements)
    manifest["files"] = [
        {"path": name, "size_bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        for name, payload in files.items()
    ]
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            if special_mode is not None and name in replacements:
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = (special_mode | 0o600) << 16
                archive.writestr(info, payload)
            else:
                archive.writestr(name, payload)
        archive.writestr(BUNDLE_MANIFEST_FILENAME, json.dumps(manifest))


def test_project_bundle_filename_uses_compact_project_title() -> None:
    assert project_bundle_filename("Semantic Categories") == "semanticcategories.fpvsbundle"
    assert project_bundle_filename("   ") == f"fpvsproject{PROJECT_BUNDLE_SUFFIX}"


@pytest.mark.parametrize("name", ["helper.cmd", "helper.exe", "helper.lnk", "unrelated.png"])
def test_library_import_rejects_unexpected_payload_before_extraction(
    tmp_path, sample_project, sample_project_root, monkeypatch, name,
):
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle = tmp_path / "unsafe.fpvsbundle"
    export_project_bundle(sample_project_root, bundle)
    _replace_bundle_payloads(bundle, {f"stimuli/{name}": b"inert test data"})
    origin = LibraryProjectOrigin(
        service_url="https://library.example", item_id="sample", installed_version="1.0.0",
        local_project_id=sample_project.meta.project_id,
        bundle_sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(),
    )

    def must_not_extract(*args, **kwargs):
        pytest.fail("Unexpected Library payload reached extraction")

    monkeypatch.setattr(project_bundle_module, "_extract_verified_record", must_not_extract)
    receiver = tmp_path / "receiver"
    with pytest.raises(ProjectBundleError, match="unexpected stimulus file"):
        import_project_bundle(bundle, receiver, library_origin=origin)
    assert not (receiver / sample_project.meta.project_id).exists()
    assert list((app_data_dir(receiver) / IMPORT_STAGING_DIRNAME).iterdir()) == []


@pytest.mark.parametrize("mode", [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR])
def test_bundle_rejects_special_members_before_extraction(
    tmp_path, sample_project, sample_project_root, monkeypatch, mode,
):
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle = tmp_path / "special.fpvsbundle"
    export_project_bundle(sample_project_root, bundle)
    image_path = "stimuli/original-images/base-set/base-set-01.png"
    _replace_bundle_payloads(bundle, {image_path: b"inert data"}, special_mode=mode)

    def must_not_extract(*args, **kwargs):
        pytest.fail("Special member reached extraction")

    monkeypatch.setattr(project_bundle_module, "_extract_verified_record", must_not_extract)
    with pytest.raises(ProjectBundleError, match="link or special file"):
        import_project_bundle(bundle, tmp_path / "receiver", library_safe=True)


def test_library_import_rejects_forged_image_content_and_cleans_staging(
    tmp_path, sample_project, sample_project_root,
):
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle = tmp_path / "false-image.fpvsbundle"
    export_project_bundle(sample_project_root, bundle)
    _replace_bundle_payloads(
        bundle, {"stimuli/original-images/base-set/base-set-01.png": b"not an image"},
    )
    receiver = tmp_path / "receiver"
    with pytest.raises(ProjectBundleError, match="stimulus validation failed"):
        import_project_bundle(bundle, receiver, library_safe=True)
    assert not (receiver / sample_project.meta.project_id).exists()
    assert list((app_data_dir(receiver) / IMPORT_STAGING_DIRNAME).iterdir()) == []


@pytest.mark.parametrize("method", [zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA])
def test_library_validation_rejects_other_compression_before_extraction(
    tmp_path, sample_project, sample_project_root, monkeypatch, method,
):
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle = tmp_path / "compression.fpvsbundle"
    export_project_bundle(sample_project_root, bundle)
    with zipfile.ZipFile(bundle) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    with zipfile.ZipFile(bundle, "w") as archive:
        for name, payload in files.items():
            archive.writestr(
                name, payload,
                compress_type=method if name == "project.json" else zipfile.ZIP_STORED,
            )

    def must_not_extract(*args, **kwargs):
        pytest.fail("Unsupported compression reached extraction")

    monkeypatch.setattr(project_bundle_module, "_extract_verified_record", must_not_extract)
    with pytest.raises(ProjectBundleError, match="unsupported compression method"):
        validate_project_bundle(bundle)


def test_library_inventory_cancellation_retains_cancelled_error(
    tmp_path, sample_project, sample_project_root, monkeypatch,
):
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle = tmp_path / "cancel.fpvsbundle"
    export_project_bundle(sample_project_root, bundle)
    cancel = Event()
    parse = project_bundle_module.project_from_json

    def cancel_after_project(payload):
        project = parse(payload)
        cancel.set()
        return project

    monkeypatch.setattr(project_bundle_module, "project_from_json", cancel_after_project)
    receiver = tmp_path / "receiver"
    with pytest.raises(ProjectBundleCancelled):
        import_project_bundle(bundle, receiver, library_safe=True, cancel_event=cancel)
    assert list((app_data_dir(receiver) / IMPORT_STAGING_DIRNAME).iterdir()) == []


@pytest.mark.parametrize(
    ("constant", "path"),
    [("MAX_BUNDLE_PROJECT_JSON_BYTES", "project.json"),
     ("MAX_BUNDLE_STIMULUS_JSON_BYTES", "stimuli/manifest.json"),
     ("MAX_BUNDLE_IMAGE_BYTES", "stimuli/original-images/base-set/base-set-01.png")],
)
def test_bundle_limits_payload_sizes_before_extraction(
    tmp_path, sample_project, sample_project_root, monkeypatch, constant, path,
):
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle = tmp_path / "oversized.fpvsbundle"
    export_project_bundle(sample_project_root, bundle)
    monkeypatch.setattr(project_bundle_module, constant, 2)

    def must_not_extract(*args, **kwargs):
        pytest.fail("Oversized payload reached extraction")

    monkeypatch.setattr(project_bundle_module, "_extract_verified_record", must_not_extract)
    with pytest.raises(ProjectBundleError, match="byte limit") as error:
        import_project_bundle(bundle, tmp_path / "receiver", library_safe=True)
    assert path in str(error.value)


def test_library_import_rejects_tiny_excessive_workload_before_scheduling(
    tmp_path, sample_project, sample_project_root, monkeypatch,
):
    import fpvs_studio.core.compiler as compiler

    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle = tmp_path / "excessive.fpvsbundle"
    export_project_bundle(sample_project_root, bundle)
    with zipfile.ZipFile(bundle) as archive:
        project = json.loads(archive.read("project.json"))
    project["conditions"][0]["oddball_cycle_repeats_per_sequence"] = 1_000_000_000
    _replace_bundle_payloads(bundle, {"project.json": json.dumps(project).encode()})

    def must_not_schedule(*args, **kwargs):
        pytest.fail("Excessive workload reached schedule allocation")

    monkeypatch.setattr(compiler, "build_stimulus_sequence", must_not_schedule)
    receiver = tmp_path / "receiver"
    with pytest.raises(ProjectBundleError, match="compilation exceeds"):
        import_project_bundle(bundle, receiver, library_safe=True)
    assert not (receiver / sample_project.meta.project_id).exists()


def test_full_library_validation_preserves_bytes_without_installing(
    tmp_path, sample_project, sample_project_root,
):
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle = tmp_path / "valid.fpvsbundle"
    expected = export_project_bundle(sample_project_root, bundle, library_safe=True)
    before = bundle.read_bytes()
    existing_paths = set(tmp_path.rglob("*"))
    assert validate_project_bundle(bundle) == expected
    assert bundle.read_bytes() == before
    assert set(tmp_path.rglob("*")) == existing_paths


def test_export_project_bundle_writes_project_stimuli_and_manifest(
    tmp_path,
    sample_project,
    sample_project_root,
) -> None:
    sample_project.settings.fixation_task.base_color = "#00FF00"
    _save_bundle_ready_project(sample_project_root, sample_project)
    (sample_project_root / "cache").mkdir()
    (sample_project_root / "cache" / "ignored.tmp").write_text("cache", encoding="utf-8")
    (sample_project_root / "logs").mkdir()
    (sample_project_root / "logs" / "ignored.csv").write_text("logs", encoding="utf-8")
    bundle_path = tmp_path / "sample.fpvsbundle"

    manifest = export_project_bundle(sample_project_root, bundle_path)

    assert bundle_path.is_file()
    assert manifest.project.project_id == sample_project.meta.project_id
    assert manifest.validation.status == "passed"
    assert "session_compile_dry_run_passed" in manifest.validation.checks
    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        assert BUNDLE_MANIFEST_FILENAME in names
        assert "project.json" in names
        assert "stimuli/manifest.json" in names
        assert "stimuli/original-images/base-set/base-set-01.png" in names
        assert "stimuli/original-images/oddball-set/oddball-set-03.png" in names
        assert "cache/ignored.tmp" not in names
        assert "logs/ignored.csv" not in names
        project_json = archive.read("project.json").decode("utf-8")
        assert "#00FF00" in project_json

    reloaded = read_project_bundle_manifest(bundle_path)
    assert reloaded == manifest
    assert {record.path for record in reloaded.files} == names - {BUNDLE_MANIFEST_FILENAME}


def test_project_bundle_preserves_task_definitions_and_assets(
    tmp_path,
    sample_project,
    sample_project_root,
) -> None:
    task_path = sample_project_root / "stimuli" / "task-assets" / "memory" / "apple.png"
    task_path.parent.mkdir(parents=True)
    task_path.write_bytes(
        (sample_project_root / "stimuli" / "original-images" / "base-set" / "base-set-01.png")
        .read_bytes()
    )
    sample_project.task_modules = [
        TaskModule(
            task_id="memory",
            name="Memory",
            steps=[
                TaskStep(
                    step_id="study",
                    kind=TaskStepKind.STUDY,
                    font_family=TaskFontFamily.OPEN_SANS,
                    continue_key="space",
                    items=[
                        TaskDisplayItem(
                            item_id="apple",
                            modality=TaskItemModality.IMAGE,
                            image_path="stimuli/task-assets/memory/apple.png",
                        )
                    ],
                )
            ],
        )
    ]
    sample_project.conditions[0].pre_task_bindings = [TaskBinding(task_id="memory")]
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "tasks.fpvsbundle"

    export_project_bundle(sample_project_root, bundle_path)

    with zipfile.ZipFile(bundle_path) as archive:
        assert "stimuli/task-assets/memory/apple.png" in archive.namelist()
    imported = import_project_bundle(bundle_path, tmp_path / "import-root")
    assert imported.project.task_modules[0].task_id == "memory"
    assert (
        imported.project.task_modules[0].steps[0].font_family
        == TaskFontFamily.OPEN_SANS
    )
    assert (
        imported.project_root / "stimuli" / "task-assets" / "memory" / "apple.png"
    ).is_file()


def test_export_project_bundle_can_rename_portable_copy_without_mutating_source(
    tmp_path,
    sample_project,
    sample_project_root,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    original_name = sample_project.meta.name
    original_id = sample_project.meta.project_id
    bundle_path = tmp_path / "renamed.fpvsbundle"

    bundle_manifest = export_project_bundle(
        sample_project_root,
        bundle_path,
        project_name="Semantic Categories Import Test",
    )

    assert bundle_manifest.project.name == "Semantic Categories Import Test"
    assert bundle_manifest.project.project_id == "semantic-categories-import-test"
    with zipfile.ZipFile(bundle_path) as archive:
        archived_project = ProjectFile.model_validate_json(archive.read("project.json"))
        archived_manifest = StimulusManifest.model_validate_json(
            archive.read("stimuli/manifest.json")
        )
    assert archived_project.meta.name == "Semantic Categories Import Test"
    assert archived_project.meta.project_id == "semantic-categories-import-test"
    assert archived_manifest.project_id == "semantic-categories-import-test"

    source_project = load_project_file(sample_project_root / "project.json")
    assert source_project.meta.name == original_name
    assert source_project.meta.project_id == original_id

    configured_root = tmp_path / "configured-fpvs-root"
    imported = import_project_bundle(bundle_path, configured_root)
    assert imported.project_root == configured_root / "semantic-categories-import-test"
    assert imported.project.meta.name == "Semantic Categories Import Test"


def test_export_project_bundle_rejects_empty_copy_name(
    tmp_path,
    sample_project,
    sample_project_root,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "empty-name.fpvsbundle"

    with pytest.raises(ProjectBundleError, match="name may not be empty"):
        export_project_bundle(sample_project_root, bundle_path, project_name="   ")

    assert not bundle_path.exists()


def test_export_project_bundle_hashes_every_payload_file(
    tmp_path,
    sample_project,
    sample_project_root,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "sample.fpvsbundle"

    manifest = export_project_bundle(sample_project_root, bundle_path)

    with zipfile.ZipFile(bundle_path) as archive:
        for record in manifest.files:
            assert len(record.sha256) == 64
            assert len(archive.read(record.path)) == record.size_bytes


def test_export_project_bundle_reports_progress_stages(
    tmp_path,
    sample_project,
    sample_project_root,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "sample.fpvsbundle"
    stages: list[str] = []

    export_project_bundle(sample_project_root, bundle_path, progress_callback=stages.append)

    assert stages == ["validate", "stimuli", "write", "complete"]


def test_export_project_bundle_requires_saved_project_json(
    tmp_path,
    sample_project_root,
) -> None:
    bundle_path = tmp_path / "missing-project.fpvsbundle"

    with pytest.raises(ProjectBundleError, match="requires project.json"):
        export_project_bundle(sample_project_root, bundle_path)

    assert not bundle_path.exists()


def test_export_project_bundle_rejects_missing_stimulus_folder(
    tmp_path,
    sample_project,
    sample_project_root,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    missing_dir = sample_project_root / Path(sample_project.stimulus_sets[0].source_dir)
    for path in missing_dir.iterdir():
        path.unlink()
    missing_dir.rmdir()
    bundle_path = tmp_path / "missing-stimuli.fpvsbundle"

    with pytest.raises(ProjectBundleError, match="Required project folder is missing"):
        export_project_bundle(sample_project_root, bundle_path)

    assert not bundle_path.exists()


def test_import_project_bundle_creates_project_and_deletes_staging(
    tmp_path,
    sample_project,
    sample_project_root,
) -> None:
    sample_project.settings.fixation_task.base_color = "#00FF00"
    sample_project.settings.protocol.oddball_every_n = 6
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "sample.fpvsbundle"
    export_project_bundle(sample_project_root, bundle_path)
    target_root = tmp_path / "receiver-root"

    scaffold = import_project_bundle(bundle_path, target_root)

    assert scaffold.project_root == target_root / sample_project.meta.project_id
    loaded = load_project_file(scaffold.project_root / "project.json")
    assert loaded.meta.name == sample_project.meta.name
    assert loaded.settings.fixation_task.base_color == "#00FF00"
    assert loaded.settings.protocol.base_hz == 6.0
    assert loaded.settings.protocol.oddball_every_n == 6
    assert (
        scaffold.project_root
        / "stimuli"
        / "original-images"
        / "base-set"
        / "base-set-01.png"
    ).is_file()
    assert (scaffold.project_root / "runs").is_dir()
    assert (scaffold.project_root / "cache").is_dir()
    assert (scaffold.project_root / "logs").is_dir()
    staging_root = app_data_dir(target_root) / IMPORT_STAGING_DIRNAME
    assert staging_root.is_dir()
    assert list(staging_root.iterdir()) == []


def test_import_project_bundle_reports_progress_stages(
    tmp_path,
    sample_project,
    sample_project_root,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "sample.fpvsbundle"
    export_project_bundle(sample_project_root, bundle_path)
    stages: list[str] = []

    import_project_bundle(
        bundle_path,
        tmp_path / "receiver-root",
        progress_callback=stages.append,
    )

    assert stages == ["verify", "base", "oddball", "project", "complete"]


def test_import_project_bundle_never_overwrites_existing_project_folder(
    tmp_path,
    sample_project,
    sample_project_root,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "sample.fpvsbundle"
    export_project_bundle(sample_project_root, bundle_path)
    target_root = tmp_path / "receiver-root"
    (target_root / sample_project.meta.project_id).mkdir(parents=True)

    first = import_project_bundle(bundle_path, target_root)
    second = import_project_bundle(bundle_path, target_root)

    assert first.project_root.name == f"{sample_project.meta.project_id}-from-bundle"
    assert first.project.meta.project_id == f"{sample_project.meta.project_id}-from-bundle"
    assert second.project_root.name == f"{sample_project.meta.project_id}-from-bundle-2"
    assert second.project.meta.project_id == f"{sample_project.meta.project_id}-from-bundle-2"


def test_import_project_bundle_rejects_checksum_mismatch_and_deletes_staging(
    tmp_path,
    sample_project,
    sample_project_root,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "sample.fpvsbundle"
    export_project_bundle(sample_project_root, bundle_path)
    tampered_path = tmp_path / "tampered.fpvsbundle"
    with zipfile.ZipFile(bundle_path) as source, zipfile.ZipFile(tampered_path, "w") as target:
        for info in source.infolist():
            payload = source.read(info.filename)
            if info.filename == "stimuli/original-images/base-set/base-set-01.png":
                payload = bytes([payload[0] ^ 0xFF]) + payload[1:]
            target.writestr(info, payload)
    target_root = tmp_path / "receiver-root"

    with pytest.raises(ProjectBundleError, match="checksum mismatch"):
        import_project_bundle(tampered_path, target_root)

    assert not (target_root / sample_project.meta.project_id).exists()
    staging_root = app_data_dir(target_root) / IMPORT_STAGING_DIRNAME
    assert staging_root.is_dir()
    assert list(staging_root.iterdir()) == []


def test_import_project_bundle_rejects_unsafe_archive_member(
    tmp_path,
    sample_project,
    sample_project_root,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "sample.fpvsbundle"
    export_project_bundle(sample_project_root, bundle_path)
    malicious_path = tmp_path / "malicious.fpvsbundle"
    with zipfile.ZipFile(bundle_path) as source, zipfile.ZipFile(malicious_path, "w") as target:
        for info in source.infolist():
            target.writestr(info, source.read(info.filename))
        target.writestr("../outside.txt", "nope")

    with pytest.raises(ProjectBundleError, match="unsafe member path"):
        import_project_bundle(malicious_path, tmp_path / "receiver-root")


def test_read_project_bundle_manifest_rejects_oversized_manifest(
    tmp_path,
    sample_project,
    sample_project_root,
    monkeypatch,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "sample.fpvsbundle"
    export_project_bundle(sample_project_root, bundle_path)
    monkeypatch.setattr(project_bundle_module, "MAX_BUNDLE_MANIFEST_BYTES", 1)

    with pytest.raises(ProjectBundleError, match="file exceeds the 1-byte limit"):
        read_project_bundle_manifest(bundle_path)


def test_export_project_bundle_rejects_resource_limit_without_replacing_destination(
    tmp_path,
    sample_project,
    sample_project_root,
    monkeypatch,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "existing.fpvsbundle"
    bundle_path.write_bytes(b"existing bundle")
    monkeypatch.setattr(
        project_bundle_module,
        "MAX_BUNDLE_TOTAL_UNCOMPRESSED_BYTES",
        1,
    )

    with pytest.raises(ProjectBundleError, match="total uncompressed-size limit"):
        export_project_bundle(sample_project_root, bundle_path)

    assert bundle_path.read_bytes() == b"existing bundle"
    assert not list(tmp_path.glob(".existing.fpvsbundle.*.tmp"))


def test_export_project_bundle_rejects_unsafe_compression_ratio(
    tmp_path,
    sample_project,
    sample_project_root,
    monkeypatch,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "sample.fpvsbundle"
    monkeypatch.setattr(project_bundle_module, "MIN_BUNDLE_COMPRESSION_CHECK_BYTES", 0)
    monkeypatch.setattr(project_bundle_module, "MAX_BUNDLE_COMPRESSION_RATIO", 0.01)

    with pytest.raises(ProjectBundleError, match="unsafe compression ratio"):
        export_project_bundle(sample_project_root, bundle_path)

    assert not bundle_path.exists()
    assert not list(tmp_path.glob(".sample.fpvsbundle.*.tmp"))


@pytest.mark.parametrize(
    ("limit_name", "error_match"),
    (
        ("MAX_BUNDLE_PAYLOAD_FILES", "too many payload files"),
        ("MAX_BUNDLE_FILE_BYTES", "file exceeds the 1-byte limit"),
        (
            "MAX_BUNDLE_TOTAL_UNCOMPRESSED_BYTES",
            "total uncompressed-size limit",
        ),
    ),
)
def test_import_project_bundle_rejects_resource_limits_and_deletes_staging(
    tmp_path,
    sample_project,
    sample_project_root,
    monkeypatch,
    limit_name: str,
    error_match: str,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "sample.fpvsbundle"
    export_project_bundle(sample_project_root, bundle_path)
    target_root = tmp_path / "receiver-root"
    monkeypatch.setattr(project_bundle_module, limit_name, 1)

    with pytest.raises(ProjectBundleError, match=error_match):
        import_project_bundle(bundle_path, target_root)

    staging_root = app_data_dir(target_root) / IMPORT_STAGING_DIRNAME
    assert staging_root.is_dir()
    assert list(staging_root.iterdir()) == []


def test_import_project_bundle_rejects_unsafe_compression_ratio(
    tmp_path,
    sample_project,
    sample_project_root,
    monkeypatch,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "sample.fpvsbundle"
    export_project_bundle(sample_project_root, bundle_path)
    target_root = tmp_path / "receiver-root"
    monkeypatch.setattr(project_bundle_module, "MIN_BUNDLE_COMPRESSION_CHECK_BYTES", 0)
    monkeypatch.setattr(project_bundle_module, "MAX_BUNDLE_COMPRESSION_RATIO", 0.01)

    with pytest.raises(ProjectBundleError, match="unsafe compression ratio"):
        import_project_bundle(bundle_path, target_root)

    staging_root = app_data_dir(target_root) / IMPORT_STAGING_DIRNAME
    assert staging_root.is_dir()
    assert list(staging_root.iterdir()) == []


@pytest.mark.parametrize("cancel_stage", ["verify", "base", "oddball", "project"])
def test_cancelled_bundle_import_leaves_existing_projects_unchanged(
    tmp_path, sample_project, sample_project_root, cancel_stage,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "sample.fpvsbundle"
    export_project_bundle(sample_project_root, bundle_path)
    receiver = tmp_path / "receiver"
    existing = receiver / sample_project.meta.project_id
    existing.mkdir(parents=True)
    marker = existing / "keep.txt"
    marker.write_bytes(b"existing project")
    cancel_event = Event()

    def progress(stage):
        if stage == cancel_stage:
            cancel_event.set()

    with pytest.raises(ProjectBundleCancelled, match="cancelled"):
        import_project_bundle(
            bundle_path, receiver, progress_callback=progress, cancel_event=cancel_event,
        )

    assert marker.read_bytes() == b"existing project"
    assert list(existing.iterdir()) == [marker]
    assert not (receiver / f"{sample_project.meta.project_id}-from-bundle").exists()
    staging = app_data_dir(receiver) / IMPORT_STAGING_DIRNAME
    assert not staging.exists() or list(staging.iterdir()) == []


def test_bundle_import_cancels_during_payload_extraction(
    tmp_path, sample_project, sample_project_root, monkeypatch,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "sample.fpvsbundle"
    export_project_bundle(sample_project_root, bundle_path)
    cancel_event = Event()
    original_read = zipfile.ZipExtFile.read

    def cancelling_read(handle, size=-1):
        payload = original_read(handle, size)
        if handle.name.endswith(".png"):
            cancel_event.set()
        return payload

    monkeypatch.setattr(zipfile.ZipExtFile, "read", cancelling_read)
    receiver = tmp_path / "receiver"
    with pytest.raises(ProjectBundleCancelled):
        import_project_bundle(bundle_path, receiver, cancel_event=cancel_event)
    assert not (receiver / sample_project.meta.project_id).exists()
    assert list((app_data_dir(receiver) / IMPORT_STAGING_DIRNAME).iterdir()) == []


def test_cancelled_bundle_export_preserves_previous_destination(
    tmp_path, sample_project, sample_project_root,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle_path = tmp_path / "sample.fpvsbundle"
    bundle_path.write_bytes(b"previous export")
    cancel_event = Event()

    def progress(stage):
        if stage == "write":
            cancel_event.set()

    with pytest.raises(ProjectBundleCancelled):
        export_project_bundle(sample_project_root, bundle_path,
                              progress_callback=progress, cancel_event=cancel_event)
    assert bundle_path.read_bytes() == b"previous export"
    assert not list(tmp_path.glob(f".{bundle_path.name}.*.tmp"))


def test_export_hashes_the_bytes_copied_after_source_changes(
    tmp_path, sample_project, sample_project_root,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    sidecar = sample_project_root / "stimuli" / "notes.txt"
    sidecar.write_bytes(b"before")
    destination = tmp_path / "changed.fpvsbundle"

    def change_at_write(stage):
        if stage == "write":
            sidecar.write_bytes(b"after!")

    manifest = export_project_bundle(
        sample_project_root, destination, progress_callback=change_at_write,
    )
    record = next(record for record in manifest.files if record.path == "stimuli/notes.txt")
    assert record.sha256 == hashlib.sha256(b"after!").hexdigest()
    imported = import_project_bundle(destination, tmp_path / "receiver")
    assert (imported.project_root / "stimuli" / "notes.txt").read_bytes() == b"after!"


def test_export_reads_each_payload_once_and_records_exact_sizes(
    tmp_path, sample_project, sample_project_root, monkeypatch,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    sidecar = sample_project_root / "stimuli" / "notes.txt"
    sidecar.write_bytes(b"unchanged source")
    original_open = Path.open
    reads = []

    def count_reads(path, mode="r", *args, **kwargs):
        if path == sidecar and mode == "rb":
            reads.append(path)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", count_reads)
    destination = tmp_path / "single-pass.fpvsbundle"
    manifest = export_project_bundle(sample_project_root, destination)
    assert len(reads) == 1
    with zipfile.ZipFile(destination) as archive:
        for record in manifest.files:
            payload = archive.read(record.path)
            assert len(payload) == record.size_bytes
            assert hashlib.sha256(payload).hexdigest() == record.sha256


@pytest.mark.parametrize("failure", ["cancel", "read"])
def test_export_failure_during_stream_preserves_destination_and_cleans_owned_temp(
    tmp_path, sample_project, sample_project_root, monkeypatch, failure,
) -> None:
    _save_bundle_ready_project(sample_project_root, sample_project)
    sidecar = sample_project_root / "stimuli" / "notes.txt"
    sidecar.write_bytes(b"x" * 200_000)
    destination = tmp_path / "existing.fpvsbundle"
    destination.write_bytes(b"previous bundle")
    unrelated_temp = tmp_path / ".existing.fpvsbundle.unrelated.tmp"
    unrelated_temp.write_bytes(b"unrelated work")
    cancel = Event()
    original_open = Path.open
    reads = []

    class InterruptedReader:
        def __init__(self, handle):
            self.handle = handle

        def read(self, size):
            reads.append(size)
            if len(reads) == 2:
                if failure == "read":
                    raise OSError("source became unavailable")
                cancel.set()
            return self.handle.read(size)

    @contextmanager
    def interrupted_handle(path, mode, *args, **kwargs):
        with original_open(path, mode, *args, **kwargs) as handle:
            yield InterruptedReader(handle)

    def interrupt_read(path, mode="r", *args, **kwargs):
        if path == sidecar and mode == "rb":
            return interrupted_handle(path, mode, *args, **kwargs)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", interrupt_read)
    expected = ProjectBundleCancelled if failure == "cancel" else OSError
    with pytest.raises(expected):
        export_project_bundle(sample_project_root, destination, cancel_event=cancel)

    assert len(reads) == 2
    assert destination.read_bytes() == b"previous bundle"
    assert list(tmp_path.glob(".existing.fpvsbundle.*.tmp")) == [unrelated_temp]
    assert unrelated_temp.read_bytes() == b"unrelated work"


def test_recording_device_and_port_survive_project_bundle(
    tmp_path, sample_project, sample_project_root
):
    from fpvs_studio.core.models import ProjectRecordingSettings

    setting = ProjectRecordingSettings(recording_backend="unicorn_udp", unicorn_udp_port=2345)
    sample_project.settings.recording = setting
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle = tmp_path / "device.fpvsbundle"
    export_project_bundle(sample_project_root, bundle)
    result = import_project_bundle(bundle, tmp_path / "imported")
    assert result.project.settings.recording == setting


@pytest.mark.skipif(os.name != "nt", reason="Windows namespace behavior")
@pytest.mark.parametrize("long_bundle", [False, True])
def test_bundle_transfer_without_windows_long_path_policy(
    tmp_path, sample_project, sample_project_root, monkeypatch, long_bundle,
):
    from fpvs_studio.core.paths import filesystem_path

    _save_bundle_ready_project(sample_project_root, sample_project)
    nested = tmp_path / ("different-user-" * 5) / ("研究室 folder " * 6) / ("root-folder-" * 5)
    while len(str(nested)) <= 270:
        nested /= "nested-root-folder"
    bundle = nested / "download.fpvsbundle" if long_bundle else tmp_path / "download.fpvsbundle"
    export_project_bundle(sample_project_root, bundle)
    receiver = nested / "receiver"
    original_mkdir, original_exists, original_open = Path.mkdir, Path.exists, zipfile.io.open

    def require_namespace(path):
        value = str(path)
        if len(value) >= 248 and not value.startswith("\\\\?\\"):
            raise OSError(206, "Windows long-path policy is disabled", value)

    def mkdir(path, *args, **kwargs):
        require_namespace(path)
        return original_mkdir(path, *args, **kwargs)

    def exists(path):
        require_namespace(path)
        return original_exists(path)

    def open_file(path, *args, **kwargs):
        if isinstance(path, (str, Path)):
            require_namespace(path)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(Path, "exists", exists)
    monkeypatch.setattr(zipfile.io, "open", open_file)
    read_project_bundle_manifest(bundle)
    from fpvs_studio.core.library_origin import LibraryProjectOrigin

    origin = LibraryProjectOrigin(
        service_url="https://library.example.test", item_id="sample-project",
        installed_version="1.0.0",
        bundle_sha256=hashlib.sha256(filesystem_path(bundle).read_bytes()).hexdigest(),
        local_project_id=sample_project.meta.project_id,
    )
    first = import_project_bundle(bundle, receiver, library_origin=origin)
    second = import_project_bundle(bundle, receiver)
    assert first.project_root == receiver / sample_project.meta.project_id
    assert second.project_root.name == f"{sample_project.meta.project_id}-from-bundle"
    assert filesystem_path(first.project_root / "project.json").is_file()
    assert list(filesystem_path(app_data_dir(receiver) / IMPORT_STAGING_DIRNAME).iterdir()) == []
    saved = filesystem_path(second.project_root / "project.json").read_text(encoding="utf-8")
    assert "different-user" not in saved and "\\\\?\\" not in saved


@pytest.mark.parametrize("error, message", [
    (PermissionError(13, "denied"), "writable"),
    (OSError(28, "full"), "space"),
])
def test_bundle_import_storage_failure_is_actionable_and_cleans_staging(
    tmp_path, sample_project, sample_project_root, monkeypatch, error, message,
):
    _save_bundle_ready_project(sample_project_root, sample_project)
    bundle = tmp_path / "download.fpvsbundle"
    export_project_bundle(sample_project_root, bundle)
    receiver = tmp_path / "receiver"

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(project_bundle_module, "_extract_verified_record", fail)
    with pytest.raises(ProjectBundleError, match=message):
        import_project_bundle(bundle, receiver)
    assert not (receiver / sample_project.meta.project_id).exists()
    assert list((app_data_dir(receiver) / IMPORT_STAGING_DIRNAME).iterdir()) == []


@pytest.mark.parametrize("alias", [
    "stimuli/original-images/base-set/BASE-SET-01.PNG",
    "stimuli/original-images/BASE-SET/other.png",
])
def test_bundle_rejects_paths_that_collide_on_windows(
    tmp_path, sample_project, sample_project_root, alias,
):
    _save_bundle_ready_project(sample_project_root, sample_project)
    original = tmp_path / "original.fpvsbundle"
    export_project_bundle(sample_project_root, original)
    bundle = tmp_path / "case-collision.fpvsbundle"
    with zipfile.ZipFile(original) as source, zipfile.ZipFile(bundle, "w") as target:
        manifest = read_project_bundle_manifest(original)
        payload = source.read("stimuli/original-images/oddball-set/oddball-set-01.png")
        record = project_bundle_module.ProjectBundleFileRecord(
            path=alias, size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(),
        )
        manifest.files.append(record)
        for info in source.infolist():
            if info.filename != BUNDLE_MANIFEST_FILENAME:
                target.writestr(info, source.read(info.filename))
        target.writestr(alias, payload)
        target.writestr(BUNDLE_MANIFEST_FILENAME, manifest.model_dump_json())
    with pytest.raises(ProjectBundleError, match="case"):
        read_project_bundle_manifest(bundle)
    receiver = tmp_path / "receiver"
    with pytest.raises(ProjectBundleError, match="case"):
        import_project_bundle(bundle, receiver)
    assert not (receiver / sample_project.meta.project_id).exists()
    assert list((app_data_dir(receiver) / IMPORT_STAGING_DIRNAME).iterdir()) == []
