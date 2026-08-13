"""Portable project bundle import/export tests."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import fpvs_studio.core.project_bundle as project_bundle_module
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.paths import app_data_dir
from fpvs_studio.core.project_bundle import (
    BUNDLE_MANIFEST_FILENAME,
    IMPORT_STAGING_DIRNAME,
    PROJECT_BUNDLE_SUFFIX,
    ProjectBundleError,
    export_project_bundle,
    import_project_bundle,
    project_bundle_filename,
    read_project_bundle_manifest,
)
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.task_models import (
    TaskBinding,
    TaskDisplayItem,
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


def test_project_bundle_filename_uses_compact_project_title() -> None:
    assert project_bundle_filename("Semantic Categories") == "semanticcategories.fpvsbundle"
    assert project_bundle_filename("   ") == f"fpvsproject{PROJECT_BUNDLE_SUFFIX}"


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
    assert not (tmp_path / ".existing.fpvsbundle.tmp").exists()


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
    assert not (tmp_path / ".sample.fpvsbundle.tmp").exists()


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
