"""Host-independent bundle guards; these are not native macOS qualification."""

from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

import fpvs_studio.core.project_bundle as bundles
from fpvs_studio.core.enums import StimulusModality
from fpvs_studio.core.paths import app_data_dir, filesystem_path
from fpvs_studio.core.portable_paths import (
    validate_portable_path_inventory,
    validate_portable_relative_path,
)
from fpvs_studio.core.serialization import save_project_file
from fpvs_studio.preprocessing.importer import import_stimulus_source_directory
from fpvs_studio.preprocessing.inspection import inspect_source_directory
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest
from fpvs_studio.preprocessing.source_files import is_finder_metadata_file


def _save(root, project):
    save_project_file(project, root / "project.json")
    write_stimulus_manifest(root, create_empty_manifest(project.meta.project_id))


def _rewrite_bundle(path, replacements):
    with zipfile.ZipFile(path) as archive:
        payloads = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(payloads.pop(bundles.BUNDLE_MANIFEST_FILENAME))
    payloads.update(replacements)
    manifest["files"] = [
        {"path": name, "size_bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        for name, payload in payloads.items()
    ]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in payloads.items():
            archive.writestr(name, payload)
        archive.writestr(bundles.BUNDLE_MANIFEST_FILENAME, json.dumps(manifest))


@pytest.mark.parametrize("name", [
    "CON.png", "aux.txt", "CoM1.any", "COM\u00b9.jpg", "LPT\u00b3", "NUL", "CONIN$.png",
    "trailing. ", "folder.", "bad?name.png", 'bad"name.png', "bad\x01.png",
    "x" * 256, "\u00e9" * 126 + ".png", "\U0001f600" * 64 + ".png",
])
def test_bundle_rejects_unportable_components_without_host_filesystem(name):
    with pytest.raises(bundles.ProjectBundleError, match="Unportable project path"):
        bundles._validate_archive_member_name(f"stimuli/{name}")


@pytest.mark.parametrize("name", [
    "ordinary image.png", "\u753b\u50cf.png", "caf\u00e9.png", "cafe\u0301.png",
    "x" * 251 + ".png", "._authored.png", "CONscience.png",
])
def test_portable_filename_validation_preserves_original_spelling(name):
    path = f"stimuli/{name}"
    assert validate_portable_relative_path(path) == path


@pytest.mark.parametrize("paths", [
    ["stimuli/caf\u00e9.png", "stimuli/cafe\u0301.png"],
    ["stimuli/Stra\u00dfe.png", "stimuli/STRASSE.png"],
    ["stimuli/caf\u00e9/a.png", "stimuli/cafe\u0301/b.png"],
    ["stimuli/Folder/a.png", "stimuli/folder/b.png"],
])
def test_bundle_alias_guard_covers_unicode_casefold_and_folder_prefixes(paths):
    with pytest.raises(ValueError, match="case or Unicode normalization"):
        validate_portable_path_inventory(paths)


def test_bundle_rejects_file_folder_conflict():
    with pytest.raises(ValueError, match="both a file and a folder"):
        validate_portable_path_inventory(["stimuli/a.png", "stimuli/a.png/nested.png"])


@pytest.mark.parametrize("additional", [
    {"stimuli/caf\u00e9.png": b"one", "stimuli/cafe\u0301.png": b"two"},
    {"stimuli/NUL.png": b"inert"},
    {"stimuli/folder./image.png": b"inert"},
])
def test_unportable_archive_rejected_before_extraction(
    tmp_path, sample_project, sample_project_root, monkeypatch, additional,
):
    _save(sample_project_root, sample_project)
    bundle = tmp_path / "invalid.fpvsbundle"
    bundles.export_project_bundle(sample_project_root, bundle)
    _rewrite_bundle(bundle, additional)

    def unexpected_extraction(*args, **kwargs):
        pytest.fail("Unportable paths must be rejected before extracting any payload")

    monkeypatch.setattr(bundles, "_extract_verified_record", unexpected_extraction)
    receiver = tmp_path / "receiver"
    with pytest.raises(bundles.ProjectBundleError):
        bundles.import_project_bundle(bundle, receiver)
    assert not (receiver / sample_project.meta.project_id).exists()
    assert list((app_data_dir(receiver) / bundles.IMPORT_STAGING_DIRNAME).iterdir()) == []


def test_bundle_checks_reference_capitalization_without_host_case_sensitivity(
    sample_project, sample_project_root,
):
    _save(sample_project_root, sample_project)
    paths = bundles._collect_bundle_file_paths(sample_project_root)
    sample_project.stimulus_sets[0].source_dir = "stimuli/original-images/BASE-SET"
    with pytest.raises(bundles.ProjectBundleError, match="capitalization"):
        bundles._validate_bundle_references(
            sample_project, create_empty_manifest(sample_project.meta.project_id), paths,
        )


def test_export_retains_authored_unicode_reference_spelling(sample_project):
    sample_project.stimulus_sets[0].source_dir = "stimuli/caf\u00e9"
    sample_project.stimulus_sets[1].source_dir = "stimuli/other"
    manifest = create_empty_manifest(sample_project.meta.project_id)
    paths = bundles._bundle_export_paths(
        sample_project, manifest,
        ["project.json", "stimuli/cafe\u0301/a.png", "stimuli/other/b.png"],
    )
    assert "stimuli/caf\u00e9/a.png" in paths
    bundles._validate_bundle_references(sample_project, manifest, paths)


def test_reference_check_rejects_canonically_different_archive_spelling(sample_project):
    sample_project.stimulus_sets[0].source_dir = "stimuli/caf\u00e9"
    sample_project.stimulus_sets[1].source_dir = "stimuli/other"
    with pytest.raises(bundles.ProjectBundleError, match="Unicode spelling"):
        bundles._validate_bundle_references(
            sample_project, create_empty_manifest(sample_project.meta.project_id),
            ["project.json", "stimuli/cafe\u0301/a.png", "stimuli/other/b.png"],
        )


def test_export_rejects_conflicting_unicode_spellings_in_authored_references(sample_project):
    sample_project.stimulus_sets[0].source_dir = "stimuli/caf\u00e9"
    sample_project.stimulus_sets[1].source_dir = "stimuli/cafe\u0301"
    with pytest.raises(bundles.ProjectBundleError, match="inconsistent Unicode spelling"):
        bundles._bundle_export_paths(
            sample_project, create_empty_manifest(sample_project.meta.project_id),
            ["project.json", "stimuli/cafe\u0301/a.png"],
        )


def test_import_rejects_case_mismatch_in_authored_reference(
    tmp_path, sample_project, sample_project_root,
):
    _save(sample_project_root, sample_project)
    bundle = tmp_path / "case-reference.fpvsbundle"
    bundles.export_project_bundle(sample_project_root, bundle)
    sample_project.stimulus_sets[0].source_dir = "stimuli/original-images/BASE-SET"
    _rewrite_bundle(bundle, {"project.json": sample_project.model_dump_json().encode("utf-8")})
    with pytest.raises(bundles.ProjectBundleError, match="capitalization"):
        bundles.import_project_bundle(bundle, tmp_path / "receiver")


@pytest.mark.parametrize("relative", [
    "project.json", "stimuli", "stimuli/original-images/base-set",
    "stimuli/original-images/base-set/base-set-01.png",
])
def test_export_rejects_source_link_aliases_without_replacing_destination(
    tmp_path, sample_project, sample_project_root, monkeypatch, relative,
):
    _save(sample_project_root, sample_project)
    bundle = tmp_path / "existing.fpvsbundle"
    bundle.write_bytes(b"previous bundle")
    original_lstat = Path.lstat
    alias = filesystem_path(sample_project_root / relative)

    def linked_lstat(path, *args, **kwargs):
        if path == alias:
            return SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_file_attributes=0)
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", linked_lstat)
    with pytest.raises(bundles.ProjectBundleError, match="linked files or folders"):
        bundles.export_project_bundle(sample_project_root, bundle)
    assert bundle.read_bytes() == b"previous bundle"


def test_source_link_guard_rejects_windows_junction_metadata():
    path = SimpleNamespace(lstat=lambda: SimpleNamespace(
        st_mode=stat.S_IFDIR | 0o777, st_file_attributes=0x400,
    ))
    with pytest.raises(bundles.ProjectBundleError, match="linked files or folders"):
        bundles._reject_bundle_source_link(path, "stimuli/linked")


def test_extraction_cannot_overwrite_an_existing_staged_alias(tmp_path):
    bundle = tmp_path / "payload.zip"
    payload = b"new"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("stimuli/a.png", payload)
    stage = tmp_path / "stage"
    (stage / "stimuli").mkdir(parents=True)
    destination = stage / "stimuli/a.png"
    destination.write_bytes(b"previous")
    record = bundles.ProjectBundleFileRecord(
        path="stimuli/a.png", size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest(),
    )
    with zipfile.ZipFile(bundle) as archive, pytest.raises(FileExistsError):
        bundles._extract_verified_record(archive, record, stage)
    assert destination.read_bytes() == b"previous"


def test_finder_metadata_intake_preserves_authored_dot_images_and_bytes(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name in ("image.png", "._authored.png"):
        Image.new("RGB", (24, 24), "red").save(source / name)
    (source / ".DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1" + b"\x00" * 32)
    (source / "._image.png").write_bytes(
        b"\x00\x05\x16\x07\x00\x02\x00\x00" + b"\x00" * 18,
    )
    original = {path.name: path.read_bytes() for path in source.iterdir()}
    project = tmp_path / "project"
    project.mkdir()
    summary, stimulus_set = import_stimulus_source_directory(
        source_dir=source, project_root=project, set_id="images", set_name="Images",
    )
    imported = project / stimulus_set.source_dir
    assert summary.image_count == 2
    assert summary.unsupported_files == []
    assert {path.name: path.read_bytes() for path in imported.iterdir()} == {
        name: original[name] for name in ("image.png", "._authored.png")
    }
    assert inspect_source_directory(source).image_count == 2
    assert {path.name: path.read_bytes() for path in source.iterdir()} == original


def test_unrecognized_finder_named_file_is_not_discarded(tmp_path):
    source = tmp_path / ".DS_Store"
    source.write_bytes(b"authored research provenance")
    assert not is_finder_metadata_file(source)


def test_local_relocation_roundtrip_preserves_unicode_media_and_word_content(
    tmp_path, sample_project, sample_project_root,
):
    # One image condition plus an unused inline word pool exercise both payload forms.
    words = sample_project.stimulus_sets[0].model_copy(update={
        "set_id": "words", "modality": StimulusModality.WORD, "source_dir": None,
        "resolution": None, "image_count": 0, "words": ["caf\u00e9", "cafe\u0301", "Stra\u00dfe"],
    })
    sample_project.stimulus_sets.append(words)
    source = sample_project_root / "stimuli/original-images/base-set/base-set-01.png"
    source.rename(source.with_name("\u753b\u50cf caf\u00e9.png"))
    _save(sample_project_root, sample_project)
    first = tmp_path / "first.fpvsbundle"
    original = bundles.export_project_bundle(sample_project_root, first)
    relocated = bundles.import_project_bundle(first, tmp_path / "first receiver")
    second = tmp_path / "second.fpvsbundle"
    returned = bundles.export_project_bundle(relocated.project_root, second)
    final = bundles.import_project_bundle(second, tmp_path / "second receiver")
    assert final.project.stimulus_sets[-1].words == words.words
    original_assets = {
        item.path: item.sha256 for item in original.files if item.path != "project.json"
    }
    returned_assets = {
        item.path: item.sha256 for item in returned.files if item.path != "project.json"
    }
    assert returned_assets == original_assets



def test_bundle_omits_recognized_finder_metadata_but_keeps_authored_dot_image(
    tmp_path, sample_project, sample_project_root,
):
    _save(sample_project_root, sample_project)
    stimuli = sample_project_root / "stimuli"
    metadata = stimuli / ".DS_Store"
    metadata.write_bytes(b"\x00\x00\x00\x01Bud1" + b"\x00" * 32)
    authored = stimuli / "._authored.png"
    Image.new("RGB", (24, 24), "red").save(authored)
    bundle = tmp_path / "metadata.fpvsbundle"
    bundles.export_project_bundle(sample_project_root, bundle)
    with zipfile.ZipFile(bundle) as archive:
        assert "stimuli/.DS_Store" not in archive.namelist()
        assert archive.read("stimuli/._authored.png") == authored.read_bytes()
    assert metadata.exists()


def test_bundle_rejects_finder_metadata_inside_an_existing_image_pool(
    tmp_path, sample_project, sample_project_root,
):
    _save(sample_project_root, sample_project)
    metadata = sample_project_root / "stimuli/original-images/base-set/._image.png"
    metadata.write_bytes(b"\x00\x05\x16\x07\x00\x02\x00\x00" + b"\x00" * 18)
    with pytest.raises(bundles.ProjectBundleError, match="Reimport the source folder"):
        bundles.export_project_bundle(sample_project_root, tmp_path / "metadata.fpvsbundle")
    assert metadata.exists()



def test_source_intake_rejects_normalization_aliases_before_copying(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for name in ("caf\u00e9.png", "cafe\u0301.png"):
        Image.new("RGB", (24, 24), "red").save(source / name)
    if len(list(source.iterdir())) != 2:
        pytest.skip("The host filesystem cannot represent normalization-alias source fixtures")
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(ValueError, match="case or Unicode normalization"):
        import_stimulus_source_directory(
            source_dir=source, project_root=project, set_id="images", set_name="Images",
        )
    assert list(project.iterdir()) == []


def test_source_directory_link_is_rejected_before_traversal(
    sample_project, sample_project_root, monkeypatch,
):
    _save(sample_project_root, sample_project)
    alias = filesystem_path(sample_project_root / "stimuli/original-images/base-set")
    original_lstat, original_iterdir = Path.lstat, Path.iterdir

    def linked_lstat(path, *args, **kwargs):
        if path == alias:
            return SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_file_attributes=0)
        return original_lstat(path, *args, **kwargs)

    def guarded_iterdir(path):
        if path == alias:
            pytest.fail("Export must not traverse a linked directory")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "lstat", linked_lstat)
    monkeypatch.setattr(Path, "iterdir", guarded_iterdir)
    with pytest.raises(bundles.ProjectBundleError, match="linked files or folders"):
        bundles._collect_bundle_file_paths(sample_project_root)
