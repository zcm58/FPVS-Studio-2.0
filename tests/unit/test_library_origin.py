"""Project-local origin receipts and import commit boundaries, without network or Qt."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from fpvs_studio.core import project_bundle, serialization
from fpvs_studio.core.library_origin import (
    MAX_ORIGIN_BYTES,
    ORIGIN_DIRECTORY,
    ORIGIN_FILENAME,
    LibraryOriginError,
    LibraryProjectOrigin,
    load_library_origin,
    save_library_origin,
)
from fpvs_studio.core.paths import app_data_dir, filesystem_path, project_dir
from fpvs_studio.core.project_bundle import (
    ProjectBundleCancelled,
    ProjectBundleError,
    export_project_bundle,
    import_project_bundle,
)
from fpvs_studio.core.serialization import save_project_file
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest


def origin(**changes):
    return LibraryProjectOrigin(**{
        "service_url": "https://library.example.test", "item_id": "masking",
        "installed_version": "1.0.0", "bundle_sha256": "a" * 64,
        "local_project_id": "local-masking", **changes,
    })


@pytest.fixture
def bundle(tmp_path, sample_project, sample_project_root):
    save_project_file(sample_project, sample_project_root / "project.json")
    write_stimulus_manifest(
        sample_project_root, create_empty_manifest(sample_project.meta.project_id),
    )
    path = tmp_path / "experiment.fpvsbundle"
    export_project_bundle(sample_project_root, path)
    return path, sample_project


def test_receipt_roundtrip_is_separate_and_unknown_legacy_version_is_explicit(tmp_path):
    project = tmp_path / "project.json"
    project.write_text('{"unchanged": true}', encoding="utf-8")
    before = project.read_bytes()
    assert load_library_origin(tmp_path) is None
    receipt = origin(installed_version=None, bundle_sha256=None, auto_check=False)
    save_library_origin(tmp_path, receipt)
    assert load_library_origin(tmp_path) == receipt
    assert project.read_bytes() == before
    assert LibraryProjectOrigin.model_validate_json(receipt.model_dump_json()) == receipt


@pytest.mark.parametrize("changes", [
    {"schema_version": "2.0"}, {"installed_version": "not-a-version"},
    {"service_url": "http://library.example.test"},
    {"service_url": "https://user:secret@library.example.test"},
    {"service_url": "https://library.example.test/path"},
    {"item_id": "../masking"}, {"local_project_id": "../project"},
    {"bundle_sha256": "bad"}, {"auto_check": "yes"}, {"token": "not-allowed"},
])
def test_origin_rejects_unsupported_or_untrusted_metadata(changes):
    with pytest.raises(ValidationError):
        origin(**changes)


@pytest.mark.parametrize("payload", [b"not-json", b"{}", b" " * (MAX_ORIGIN_BYTES + 1)])
def test_invalid_or_oversized_receipt_is_not_treated_as_unlinked(tmp_path, payload):
    path = tmp_path / ORIGIN_DIRECTORY / ORIGIN_FILENAME
    path.parent.mkdir()
    path.write_bytes(payload)
    with pytest.raises(LibraryOriginError):
        load_library_origin(tmp_path)


@pytest.mark.parametrize("link_directory", [False, True])
def test_origin_rejects_symlink_paths_without_reading_or_overwriting_target(
    tmp_path, link_directory,
):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / ORIGIN_FILENAME
    target.write_text("private sentinel", encoding="utf-8")
    linked = root / ORIGIN_DIRECTORY
    if not link_directory:
        linked.mkdir()
        linked /= ORIGIN_FILENAME
    try:
        linked.symlink_to(outside if link_directory else target, target_is_directory=link_directory)
    except OSError:
        pytest.skip("Creating Windows symlinks is unavailable in this environment.")
    for action in (lambda: load_library_origin(root), lambda: save_library_origin(root, origin())):
        with pytest.raises(LibraryOriginError, match="links or reparse"):
            action()
    assert target.read_text(encoding="utf-8") == "private sentinel"


def test_reparse_directory_is_rejected_without_native_symlink_privileges(tmp_path, monkeypatch):
    receipt_dir = tmp_path / ORIGIN_DIRECTORY
    receipt_dir.mkdir()
    filesystem_receipt_dir = filesystem_path(receipt_dir)
    original_lstat = Path.lstat

    def lstat(path, *args, **kwargs):
        info = original_lstat(path, *args, **kwargs)
        if path == filesystem_receipt_dir:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400, st_nlink=1)
        return info

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(LibraryOriginError, match="links or reparse"):
        load_library_origin(tmp_path)
    with pytest.raises(LibraryOriginError, match="links or reparse"):
        save_library_origin(tmp_path, origin())
    assert list(receipt_dir.iterdir()) == []


def test_failed_atomic_receipt_save_preserves_previous_receipt(tmp_path, monkeypatch):
    previous = origin()
    save_library_origin(tmp_path, previous)

    def reject_replace(*_args):
        raise PermissionError("synthetic replacement failure")

    monkeypatch.setattr(serialization, "replace_file_atomically", reject_replace)
    with pytest.raises(LibraryOriginError, match="could not be saved"):
        save_library_origin(tmp_path, origin(auto_check=False))
    assert load_library_origin(tmp_path) == previous
    assert [path.name for path in (tmp_path / ORIGIN_DIRECTORY).iterdir()] == [ORIGIN_FILENAME]


def test_import_receipt_uses_collision_safe_identity_without_changing_project_schema(
    bundle, tmp_path,
):
    path, project = bundle
    root = tmp_path / "studio"
    first = import_project_bundle(path, root)
    assert load_library_origin(first.project_root) is None
    receipt = origin(bundle_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    second = import_project_bundle(path, root, library_origin=receipt)
    saved = load_library_origin(second.project_root)
    assert saved == receipt.model_copy(update={"local_project_id": second.project.meta.project_id})
    assert second.project.meta.project_id != first.project.meta.project_id
    assert second.project.schema_version == project.schema_version
    assert "library_origin" not in second.project.model_dump()
    exported = tmp_path / "ordinary-export.fpvsbundle"
    export_project_bundle(second.project_root, exported)
    with zipfile.ZipFile(exported) as archive:
        assert not any(name.startswith(ORIGIN_DIRECTORY) for name in archive.namelist())


@pytest.mark.parametrize("failure", ["receipt-write", "cancel", "checksum"])
def test_import_failure_before_commit_leaves_no_project_or_receipt(
    bundle, tmp_path, monkeypatch, failure,
):
    path, project = bundle
    root = tmp_path / "studio"
    cancel = Event()
    receipt = origin(bundle_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    if failure == "checksum":
        receipt = receipt.model_copy(update={"bundle_sha256": "0" * 64})
    else:
        def save(root, receipt):
            if failure == "receipt-write":
                raise OSError("synthetic write failure")
            save_library_origin(root, receipt)
            cancel.set()
        monkeypatch.setattr(project_bundle, "save_library_origin", save)
    expected = ProjectBundleCancelled if failure == "cancel" else ProjectBundleError
    with pytest.raises(expected):
        import_project_bundle(path, root, library_origin=receipt, cancel_event=cancel)
    assert not project_dir(root, project.meta.project_id).exists()
    staging = app_data_dir(root) / project_bundle.IMPORT_STAGING_DIRNAME
    assert not staging.exists() or list(staging.iterdir()) == []
