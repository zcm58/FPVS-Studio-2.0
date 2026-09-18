"""Staged image intake and selected-condition adoption, without Qt."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from fpvs_studio.core.compiler_assets import resolve_image_paths
from fpvs_studio.core.enums import StimulusVariant
from fpvs_studio.gui.document_conditions import DocumentConditionMixin
from fpvs_studio.gui.document_stimuli import DocumentStimulusMixin
from fpvs_studio.preprocessing import importer
from fpvs_studio.preprocessing.manifest import find_manifest_set, read_stimulus_manifest


class _Document(DocumentStimulusMixin, DocumentConditionMixin):
    def __init__(self, project, root):
        self._project = project.model_copy(deep=True)
        self._project_root = root
        self._manifest = None
        self.notifications = 0
        self.manifest_changed = SimpleNamespace(emit=self._notify)

    def _notify(self):
        self.notifications += 1

    def _replace_project(self, project):
        self._project = project


def _source(tmp_path, name, filenames):
    folder = tmp_path / name
    folder.mkdir()
    for filename in filenames:
        Image.new("RGB", (64, 64), "red").save(folder / filename)
    return folder


def _file_bytes(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_reimport_replaces_only_selected_pool_and_keeps_previous_files(
    sample_project, sample_project_root, tmp_path,
):
    document = _Document(sample_project, sample_project_root)
    original_files = _file_bytes(sample_project_root)
    old = _source(tmp_path, "old", ["old.png", "shared.png"])
    new = _source(tmp_path, "new", ["new.png", "shared.png"])
    first = document.import_condition_stimulus_folder("faces", role="base", source_dir=old)
    first_files = _file_bytes(sample_project_root / first.source_dir)

    second = document.import_condition_stimulus_folder("faces", role="base", source_dir=new)

    assert first.set_id != second.set_id
    assert document.get_condition_stimulus_set("faces", "base") == second
    assert document._project.stimulus_sets[0] == second
    assert document.get_stimulus_set(first.set_id) is None
    assert second.image_count == 2
    manifest = read_stimulus_manifest(sample_project_root)
    section = find_manifest_set(manifest, set_id=second.set_id)
    assert section is not None
    compiled = resolve_image_paths(
        second, variant=StimulusVariant.ORIGINAL,
        project_root=sample_project_root, manifest=manifest,
    )
    assert {Path(path).name for path in compiled} == {"new.png", "shared.png"}
    assert len(compiled) == len(section.assets) == second.image_count
    assert document._manifest == manifest
    assert _file_bytes(sample_project_root / first.source_dir) == first_files
    assert all(
        (sample_project_root / path).read_bytes() == data
        for path, data in original_files.items()
    )
    assert document.notifications == 2


def test_replacing_shared_source_preserves_other_conditions_and_manifest(
    multi_condition_project, multi_condition_project_root, tmp_path,
):
    document = _Document(multi_condition_project, multi_condition_project_root)
    document.refresh_stimulus_inspection()
    before = document._project.model_copy(deep=True)
    original_manifest = document._manifest
    original_files = _file_bytes(multi_condition_project_root)
    source = _source(tmp_path, "replacement", ["replacement.png"])
    selected = before.conditions[0]

    imported = document.import_condition_stimulus_folder(
        selected.condition_id, role="base", source_dir=source,
    )

    assert imported.set_id != selected.base_stimulus_set_id
    assert document._project.conditions[1:] == before.conditions[1:]
    for stimulus_set in before.stimulus_sets:
        assert document.get_stimulus_set(stimulus_set.set_id) == stimulus_set
    for section in original_manifest.sets:
        assert find_manifest_set(document._manifest, set_id=section.set_id) == section
    assert all((multi_condition_project_root / path).read_bytes() == data
               for path, data in original_files.items() if path != Path("stimuli/manifest.json"))


@pytest.mark.parametrize("failure", ["copy", "decode"])
def test_failed_import_keeps_project_manifest_and_existing_assets(
    sample_project, sample_project_root, tmp_path, monkeypatch, failure,
):
    document = _Document(sample_project, sample_project_root)
    document.refresh_stimulus_inspection()
    before_project = document._project.model_dump()
    before_manifest = document._manifest.model_dump()
    before_files = _file_bytes(sample_project_root)
    source = _source(tmp_path, "incoming", ["a.png", "b.png"])
    copy = importer.shutil.copy2

    def failing_copy(source_path, destination):
        if source_path.name == "b.png":
            if failure == "copy":
                raise OSError("Simulated copy failure")
            destination.write_bytes(b"Invalid copied image")
            return destination
        return copy(source_path, destination)

    monkeypatch.setattr(importer.shutil, "copy2", failing_copy)
    with pytest.raises(OSError):
        document.import_condition_stimulus_folder("faces", role="base", source_dir=source)

    assert document._project.model_dump() == before_project
    assert document._manifest.model_dump() == before_manifest
    assert _file_bytes(sample_project_root) == before_files
    assert not list(sample_project_root.rglob(".import-*"))


def test_existing_import_destination_is_never_overwritten(tmp_path):
    source = _source(tmp_path, "incoming", ["new.png"])
    project_root = tmp_path / "project"
    destination = project_root / "stimuli/original-images/existing"
    destination.mkdir(parents=True)
    (destination / "user.txt").write_text("Keep this file", encoding="utf-8")
    before = _file_bytes(project_root)

    with pytest.raises(FileExistsError, match="already exists"):
        importer.import_stimulus_source_directory(
            source_dir=source, project_root=project_root,
            set_id="existing", set_name="Existing",
        )

    assert _file_bytes(project_root) == before


def test_manifest_write_failure_preserves_previous_document_and_saved_manifest(
    sample_project, sample_project_root, tmp_path, monkeypatch,
):
    document = _Document(sample_project, sample_project_root)
    document.refresh_stimulus_inspection()
    before_project = document._project.model_dump()
    before_manifest = document._manifest.model_dump()
    before_files = _file_bytes(sample_project_root)
    notifications = document.notifications
    source = _source(tmp_path, "incoming", ["replacement.png"])

    def failing_write(*_args):
        raise OSError("Simulated manifest write failure")

    monkeypatch.setattr(
        "fpvs_studio.gui.document_stimuli.write_stimulus_manifest", failing_write,
    )
    with pytest.raises(OSError, match="manifest write failure"):
        document.import_condition_stimulus_folder("faces", role="base", source_dir=source)

    assert document._project.model_dump() == before_project
    assert document._manifest.model_dump() == before_manifest
    assert read_stimulus_manifest(sample_project_root).model_dump() == before_manifest
    assert document.notifications == notifications
    assert all(
        (sample_project_root / path).read_bytes() == data
        for path, data in before_files.items()
    )
    assert not list(sample_project_root.rglob(".import-*"))
    # Completed intake is retained safely; adoption never removes existing user assets.
    retained = list(sample_project_root.glob(
        "stimuli/original-images/faces-base-*/replacement.png"
    ))
    assert len(retained) == 1
    assert retained[0].read_bytes() == (source / "replacement.png").read_bytes()


def test_permissive_import_keeps_mixed_sizes_and_reports_ignored_files(tmp_path):
    source = _source(tmp_path, "incoming", ["square.png"])
    Image.new("RGB", (96, 32), "blue").save(source / "rectangle.bmp")
    (source / "notes.txt").write_text("Ignore this file", encoding="utf-8")
    before = _file_bytes(source)

    summary, stimulus_set = importer.import_fresh_stimulus_source_directory(
        source_dir=source, project_root=tmp_path / "project",
        set_id_prefix="condition-base", set_name="Base images", strict=False,
    )

    assert summary.mixed_resolution
    assert summary.unsupported_files == ["notes.txt"]
    assert stimulus_set.image_count == 2
    assert stimulus_set.resolution is None
    assert _file_bytes(source) == before
