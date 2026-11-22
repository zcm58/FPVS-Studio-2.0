"""Windows long-path image intake preserves filenames and portable provenance."""

from __future__ import annotations

import errno
import os
from ctypes import POINTER, cast
from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image

from fpvs_studio.core.enums import StimulusVariant
from fpvs_studio.preprocessing.controls import (
    generate_phase_scrambled_png,
    generate_rot180_png,
)
from fpvs_studio.preprocessing.grayscale import generate_grayscale_png
from fpvs_studio.preprocessing.importer import (
    import_stimulus_source_directory,
    materialize_project_assets,
)
from fpvs_studio.preprocessing.inspection import compute_file_sha256, inspect_source_directory
from fpvs_studio.preprocessing.normalization import (
    normalize_stimulus_sets,
    scan_stimulus_sets_for_normalization,
)
from fpvs_studio.preprocessing.source_files import source_image_directory_files

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows extended filesystem paths")

LONG_FILENAME = (
    "u7659982228_asparagus_on_a_plain_gray_background_hyper_realis_"
    "940736f7-2738-4ce8-a1bc-26a91018375b_0.png"
)


def _fixture_path(path: Path) -> Path:
    """Build fixtures independently of the production helper being tested."""
    return Path("\\\\?\\" + str(path.absolute()))


def _long_project_root(tmp_path: Path, label: str) -> Path:
    component = label + "-" + "p" * max(1, 190 - len(str(tmp_path)) - len(label) - 2)
    project_root = tmp_path / component
    _fixture_path(project_root).mkdir(parents=True)
    return project_root


@pytest.fixture
def enable_windows_inventory_probe(monkeypatch):
    from fpvs_studio.preprocessing import source_files

    monkeypatch.setattr(source_files, "_WINDOWS_INVENTORY_MIN_ENTRIES", 1)


@pytest.mark.parametrize("label", ["ascii", "画像-é"])
def test_long_import_inspection_variants_and_normalization_preserve_paths(
    tmp_path, sample_project, label
):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / LONG_FILENAME
    Image.new("RGB", (32, 24), (40, 80, 120)).save(_fixture_path(source))
    source_bytes = _fixture_path(source).read_bytes()
    project_root = _long_project_root(tmp_path, label)
    set_id = "condition-1-t2-123456789abc"
    destination = project_root / "stimuli" / "original-images" / set_id / LONG_FILENAME
    assert len(str(destination)) > 260

    summary, stimulus_set = import_stimulus_source_directory(
        source_dir=source_dir,
        project_root=project_root,
        set_id=set_id,
        set_name="T2 images",
    )

    expected_relative = f"stimuli/original-images/{set_id}/{LONG_FILENAME}"
    assert summary.files[0].relative_path == expected_relative
    assert summary.files[0].sha256 == sha256(source_bytes).hexdigest()
    assert _fixture_path(destination).read_bytes() == source_bytes
    inspected = inspect_source_directory(
        project_root / stimulus_set.source_dir, relative_prefix=stimulus_set.source_dir
    )
    assert inspected.files == summary.files
    assert compute_file_sha256(destination) == summary.files[0].sha256

    project = sample_project.model_copy(
        update={"stimulus_sets": [stimulus_set], "conditions": []}, deep=True
    )
    variants = [StimulusVariant.GRAYSCALE, StimulusVariant.ROT180, StimulusVariant.PHASE_SCRAMBLED]
    manifest = materialize_project_assets(project, project_root=project_root, variants=variants)
    repeated = materialize_project_assets(project, project_root=project_root, variants=variants)
    asset = manifest.sets[0].assets[0]
    assert asset.source.relative_path == expected_relative
    assert {record.variant for record in asset.derivatives} == set(variants)
    assert repeated.sets[0].assets[0].derivatives == asset.derivatives
    assert repeated.sets[0].assets[0].source.sha256 == asset.source.sha256
    for derivative in asset.derivatives:
        assert "\\" not in derivative.relative_path
        assert not Path(derivative.relative_path).is_absolute()
        with Image.open(_fixture_path(project_root / derivative.relative_path)) as image:
            assert image.size == (32, 24)
    assert "\\\\?\\" not in _fixture_path(project_root / "stimuli/manifest.json").read_text(
        encoding="utf-8"
    )

    scan = scan_stimulus_sets_for_normalization(
        project_root=project_root, stimulus_sets=[stimulus_set]
    )
    assert scan.can_normalize
    assert scan.image_count == 1
    result = normalize_stimulus_sets(
        project_root=project_root, stimulus_sets=[stimulus_set], target_size=256
    )
    assert result.processed_count == 1
    normalized = result.sets[0]
    assert normalized.source_dir == f"stimuli/normalized-images/{set_id}"
    normalized_dir = _fixture_path(project_root / normalized.source_dir)
    normalized_file = next(normalized_dir.iterdir())
    with Image.open(normalized_file) as image:
        assert image.size == (256, 256)
    assert _fixture_path(destination).read_bytes() == source_bytes
    assert _fixture_path(source).read_bytes() == source_bytes


@pytest.mark.parametrize("kind", ["grayscale", "rot180", "phase_scrambled"])
def test_standalone_derivative_helpers_accept_long_source_and_destination(tmp_path, kind):
    root = _long_project_root(tmp_path, "画像")
    source = root / LONG_FILENAME
    Image.new("RGB", (32, 24), (40, 80, 120)).save(_fixture_path(source))
    destination = root / "derivatives" / LONG_FILENAME
    assert len(str(source)) > 260
    if kind == "grayscale":
        generate_grayscale_png(source, destination)
    elif kind == "rot180":
        generate_rot180_png(source, destination)
    else:
        generate_phase_scrambled_png(source, destination, seed=31)
    with Image.open(_fixture_path(destination)) as image:
        assert image.size == (32, 24)


@pytest.mark.usefixtures("enable_windows_inventory_probe")
def test_stimulus_inventory_checks_current_file_type_after_listing(tmp_path, monkeypatch):
    deleted = tmp_path / "deleted.png"
    changed_to_directory = tmp_path / "now-directory.png"
    changed_to_file = tmp_path / "now-file.png"
    retained = tmp_path / "retained.png"
    for path in (deleted, changed_to_directory, retained):
        path.touch()
    changed_to_file.mkdir()

    original_iterdir = Path.iterdir

    def change_entries_after_listing(directory):
        entries = list(original_iterdir(directory))
        if directory == tmp_path:
            deleted.unlink()
            changed_to_directory.unlink()
            changed_to_directory.mkdir()
            changed_to_file.rmdir()
            changed_to_file.touch()
            (tmp_path / "added-after-listing.png").touch()
        yield from entries

    monkeypatch.setattr(Path, "iterdir", change_entries_after_listing)

    assert source_image_directory_files(tmp_path) == [changed_to_file, retained]


@pytest.mark.usefixtures("enable_windows_inventory_probe")
def test_stimulus_inventory_preserves_hard_links_and_follows_junction_directories(tmp_path):
    import _winapi

    source = tmp_path / "source"
    source.mkdir()
    original = source / "original.png"
    original.touch()
    hard_link = source / "hard-link.png"
    os.link(original, hard_link)
    target = tmp_path / "target"
    target.mkdir()
    (target / "inside.png").touch()
    junction = source / "directory.png"
    try:
        _winapi.CreateJunction(str(target), str(junction))
    except OSError as error:
        pytest.skip(f"Windows directory junctions are unavailable: {error}")

    assert source_image_directory_files(source) == [hard_link, original]
    assert source_image_directory_files(junction) == [junction / "inside.png"]


@pytest.mark.usefixtures("enable_windows_inventory_probe")
def test_stimulus_inventory_preserves_windows_name_resolution(tmp_path):
    extended = _fixture_path(tmp_path)
    unusual = [extended / name for name in ("alias.png.", "trailing.png. ", "NUL.png")]
    (tmp_path / "alias.png").mkdir()
    (tmp_path / "control.png").touch()
    try:
        for path in unusual:
            path.touch()
        for folder in (tmp_path, extended):
            expected = sorted(path for path in folder.iterdir() if path.is_file())
            assert source_image_directory_files(folder) == expected
    finally:
        for path in unusual:
            path.unlink(missing_ok=True)


@pytest.mark.usefixtures("enable_windows_inventory_probe")
@pytest.mark.parametrize("query_available", [True, False])
def test_stimulus_inventory_preserves_denied_stat_when_query_cannot_help(
    tmp_path, monkeypatch, query_available,
):
    from fpvs_studio.preprocessing import windows_source_files

    denied = tmp_path / "denied.png"
    denied.touch()
    original_is_file = Path.is_file

    def is_file(path):
        if path == denied:
            raise PermissionError(errno.EACCES, "Access denied", str(path))
        return original_is_file(path)

    def query(filename, _information_class, buffer, _size):
        if filename == str(tmp_path):
            info = cast(buffer, POINTER(windows_source_files._FileStatBasicInformation)).contents
            info.device_type = windows_source_files._FILE_DEVICE_DISK
            info.attributes = windows_source_files.FILE_ATTRIBUTE_DIRECTORY
            return 1
        return 0

    monkeypatch.setattr(
        windows_source_files, "_file_information_query", lambda: query if query_available else None,
    )
    monkeypatch.setattr(Path, "is_file", is_file)

    with pytest.raises(PermissionError) as error:
        source_image_directory_files(tmp_path)
    assert error.value.filename == str(denied)


@pytest.mark.usefixtures("enable_windows_inventory_probe")
def test_stimulus_inventory_queries_an_unsupported_root_only_once(tmp_path, monkeypatch):
    from fpvs_studio.preprocessing import windows_source_files

    paths = [tmp_path / name for name in ("base.png", "oddball.png")]
    for path in paths:
        path.touch()
    queried = []

    def query(filename, *_args):
        queried.append(filename)
        return 0

    monkeypatch.setattr(windows_source_files, "_file_information_query", lambda: query)

    assert source_image_directory_files(tmp_path) == paths
    assert queried == [str(tmp_path)]
